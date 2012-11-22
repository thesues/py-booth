# vim: tabstop=4 shiftwidth=4 softtabstop=4 expandtab
from datetime import datetime
import calendar
import time
import simplejson as json
from controler import EventThread, do_recv, do_send, Admin, public
from eventlet import Queue
import logging as log
from eventlet import sleep, Timeout
from eventlet import kill
import conf



VERSION = (0,0,1)

#renew is much like prepare, but it requires acceptor to check
#the previous instance_number
PREPARE, LEARN, ACCEPT, RENEW = ('PREPARE', 'LEARN', 'ACCEPT', 'RENEW')

ECHO_PREPARE, ECHO_ACCEPT = ('ECHO_PREPARE', 'ECHO_ACCEPT')

ACK, NACK, OUTDATE = ('ACK', 'NACK', 'OUTDATE')

REVOKING = 'REVOKING'

#lease stat
OUTDATE, LOCALLY_UNKNOWN, WAIT = ('OUTDATE', 'LOCALLY_UNKNOWN', 'WAIT')


class Message(object):
    def __init__(self, **kwargs):
        self.method = kwargs.get('method')
        self.sid = kwargs.get('sid')
        self.suggested_host_timeout= kwargs.get('suggested_host_timeout')
        self.suggested_host = kwargs.get('suggested_host')
        self.ballot = kwargs.get('ballot')
        self.instance_number = kwargs.get('instance_number')
        self.echo= kwargs.get('echo')
    def add_sid(self, sid):
        self.sid = sid
    def add_echo(self,state):
        self.echo = state
    def enpack(self):
        msg = json.dumps(dict(method=self.method,sid=self.sid,
            ballot=self.ballot, suggested_host=self.suggested_host,
            suggested_host_timeout=self.suggested_host_timeout,
            instance_number=self.instance_number,
            echo=self.echo
            ))
        return msg
    #TODO depack format check
    def depack(self, d):
        d.strip()
        try:
            data = json.loads(d)
        except:
            log.error('parse json error:%s' % d)
            return False
        #must hava the 2 element below
        self.method = data['method']
        self.sid= data['sid']

        #maybe have in protocol
        self.ballot = data.get('ballot')
        self.instance_number = data.get('instance_number')
        self.suggested_host = data.get('suggested_host')
        self.suggested_host_timeout = data.get('suggested_host_timeout')
        self.echo = data.get('echo')
        return True
    def __str__(self):
        return self.enpack();


class Lease(object):
    def __init__(self, sid, timeout):
        self.sid = sid
        self.timeout = timeout
        #no meaning in accepted lease
        self.instance_number = -1
    def set_none(self):
        self.sid = None
        self.timeout = None
        self.instance_number = None
    def __str__(self):
        return "SID: %s, TIMEOUT: %s, epoch %d" % (self.sid , time.ctime(self.timeout), self.instance_number)

#when using recv, there are 2 different msg
# 1. for acceptors , methods are PREPARE, ACCEPT , LEARN, RENEW: go to acceptor
# 2. for propser, methods are ACK, NACK: go to proposer
class Dispatcher(EventThread):
    def __init__(self):
        self.proposer_queue = Queue()
        self.acceptor_queue = Queue()
    def _run(self):
        while True:
            #get recved string
            u = do_recv()
            m = Message()
            if not m.depack(u):
                continue
            if m.method == PREPARE or m.method == ACCEPT or m.method == LEARN or m.method == RENEW:
                self.acceptor_queue.put(m)
            elif m.method == NACK or m.method == ACK or m.method == OUTDATE:
                self.proposer_queue.put(m)


class Acceptor(EventThread):
    def __init__(self, dispatcher):
        self.ballot = 0
        self.last_lease = Lease(None, None)
        self.accepted_lease = Lease(None, None)
        self.instance_number = 0
        self.queue = dispatcher.acceptor_queue
        #need to update proposer's data

    def set_lease_manager(self,manager):
        self.lease_manager = manager

    def get_instance_number(self):
        return self.instance_number

    def _run(self):
        while True:
            m = self.queue.get()
            #if not m.depack(m):
            #    continue
            #renew and prepare is like
            if m.method == PREPARE or m.method == RENEW:
                self.on_prepare(m)
            elif m.method == ACCEPT:
                self.on_accept(m)
            elif m.method == LEARN:
                self.on_learn(m)

    def on_prepare(self, msg):
        #maybe RENEW and PREPARE
        log.info('ACCEPTOR: start on_%s', msg.method)
        log.debug('GET msg %s', msg)
        #if msg.instance_number < self.instance_number and self.last_lease.sid == None:
        if msg.instance_number < self.instance_number:
            log.info('ACCEPTOR: proposer has missed some instance')
            #proposer has missed some instance
            m = Message(method=OUTDATE,
                    suggested_host=self.accepted_lease.sid,
                    suggested_host_timeout=self.accepted_lease.timeout,
                    ballot=self.ballot,
                    instance_number=self.instance_number)
            #SEND OUTDATE(None, local_lamda_acc, local_ballot,
            #local_instance_nubmer
        else:
            if  msg.instance_number > self.instance_number:
                #local acceptor has missed some instacne
                #work instance_number or last lease instance_number?
                if msg.method == RENEW and self.last_lease.sid and \
                        msg.instance_number == self.last_lease.instance_number + 1:

                    log.info('ACCEPTOR: agree to RENEW msg')
                    self.accepted_lease.sid = self.last_lease.sid
                    self.accepted_lease.timeout = self.last_lease.timeout
                    self.ballot = msg.ballot
                    self.instance_number = msg.instance_number
                    m = Message(method=ACK,
                            ballot=msg.ballot,
                            instance_number=msg.instance_number,
                            suggested_host=self.accepted_lease.sid,
                            suggested_host_timeout=None)
                else:
                    log.info('ACCEPTOR: local acceptor has missed some instacne')
                    self.accepted_lease.set_none()
                    self.last_lease.set_none()
                    self.ballot = msg.ballot
                    self.instance_number = msg.instance_number
                    m = Message(method=ACK,
                            ballot=msg.ballot,
                            instance_number=msg.instance_number,
                            suggested_host=None,
                            suggested_host_timeout=None)

            elif msg.ballot < self.ballot:
                #acceptor has seen a newer proposal
                log.info('ACCEPTOR: acceptor has seen a newer proposal')
                m = Message(method=NACK,
                        ballot=self.ballot,
                        instance_number=self.instance_number,
                        suggested_host=None,
                        suggested_host_timeout=None)
            else:
                #accept agree to the proposal
                log.info('ACCEPTOR: accept agree to proposal')
                self.ballot = msg.ballot
                if self.accepted_lease.sid != None and \
                        self.accepted_lease.timeout != None:
                    #!!!acceptor force proposer to use prior value!!!
                    log.info('ACCEPTOR: acceptor force proposer to use prior value')
                    m = Message(method=ACK,
                            ballot=self.ballot,
                            instance_number=msg.instance_number,
                            suggested_host=self.accepted_lease.sid,
                            suggested_host_timeout=self.accepted_lease.timeout)
                else:
                    log.info('ACCEPTOR: no accecpted lease , so accept this')
                    m = Message(method=ACK,
                            ballot=self.ballot,
                            instance_number=msg.instance_number,
                            suggested_host=None,
                            suggested_host_timeout=None)

            #update dict to add sid
        m.add_sid(conf.myself.sid)
        m.add_echo(ECHO_PREPARE)
        do_send(msg.sid, m.enpack())
        log.debug('ACCEPTOR: response from on_prepare %s', m.enpack())

    def on_accept(self,msg):
        log.info('ACCEPTOR: start on_accept')
        if msg.instance_number < self.instance_number:
            #acceptor dose not vote for values in outdated instance
            log.info('ACCEPTOR: acceptor dose not vote for values in outdated instance')

            m = Message(method=NACK,
                    instance_number=self.instance_number)

        elif msg.instance_number > self.instance_number:
            #acceptor has missed instance and votes for value
            log.info('ACCEPTOR: acceptor has missed instance and votes for value')
            self.last_lease.set_none()
            self.accepted_lease.sid = msg.suggested_host
            self.accepted_lease.timeout= msg.suggested_host_timeout
            self.ballot = msg.ballot
            self.instance_number = msg.instance_number
            #SEND ACK
            m = Message(method=ACK,
                    instance_number=self.instance_number,
                    suggested_host=self.accepted_lease.sid,
                    suggested_host_timeout=self.accepted_lease.timeout,
                    ballot=self.ballot)

        elif msg.ballot >= self.ballot:
            #acceptor votes for proposal
            log.info('ACCEPTOR: acceptor has voted for proposal, now accept')
            log.info('ACCEPTOR: acceptor get %s', msg)
            self.accepted_lease.sid = msg.suggested_host
            self.accepted_lease.timeout = msg.suggested_host_timeout
            #TODO
            #maybe need to in on_accept, usually self.ballot was
            #updated in on_prepare.
            #self.ballot = msg.ballot

            #SEND ACK
            m = Message(method=ACK,
                    instance_number=self.instance_number,
                    suggested_host=self.accepted_lease.sid,
                    suggested_host_timeout=self.accepted_lease.timeout,
                    ballot=msg.ballot)

        else:
            #acceptor has seen newer proposal and connot accept
            #SEND NACK
            log.info('ACCEPTOR: acceptor has seen newer proposal and connot accept')
            m = Message(method=NACK,
                    instance_number=self.instance_number)

        m.add_sid(conf.myself.sid)
        m.add_echo(ECHO_ACCEPT)
        log.debug('ACCEPTOR: response from on_accept %s', m.enpack())
        do_send(msg.sid, m.enpack())


    def on_learn(self, msg):
        log.info('ACCEPTOR: start on_learn')
        tmp_last_lease_timeout = self.last_lease.timeout

        if msg.instance_number > self.instance_number:
            log.info('ACCEPTOR: instance number is unknown and needs to be created')
            self.last_lease.sid = msg.suggested_host
            self.last_lease.timeout = msg.suggested_host_timeout
            self.accepted_lease.sid = None
            self.ballot = 0
            self.instance_number = msg.instance_number
        elif msg.instance_number == self.instance_number:
            log.info(msg)
            log.info('ACCEPTOR: instance number is known')
            log.info('the consensus outcome (lease) is stored in the instance')
            #when in revoke situation, this is usefull
            self.accepted_lease.sid = msg.suggested_host
            #when in revoke situation, this is usefull
            self.last_lease.sid = msg.suggested_host
            self.last_lease.timeout = msg.suggested_host_timeout
            self.last_lease.instance_number = self.instance_number
            log.info('LEASE %s', self.last_lease)

        #fire timer
        #if I have the lease, start a renew process
        if self.lease_manager.require_thead:
            self.lease_manager.require_thead.stop()
        #only propose has it
        if self.lease_manager.renew_thread:
            self.lease_manager.renew_thread.stop()
        if self.lease_manager.expire_thread:
            self.lease_manager.expire_thread.stop()


        #when in revoking
        if self.last_lease.sid == REVOKING:
            #calculate revoking time
            if tmp_last_lease_timeout:
                resume_timeout = tmp_last_lease_timeout + conf.require_retry_times * (conf.proposer_timeout + conf.d_max)
            else:
                resume_timeout = get_utc_time() + conf.require_retry_times * (conf.proposer_timeout + conf.d_max)
            #start revoking timer, after resume_timeout , set accepted and last lease to None,
            #which means the revoking is finally finished.
            self.last_lease.timeout = resume_timeout
            #if revoking_timeout_thread is running, start will not work
            self.lease_manager.revoking_timeout_thread.start(resume_timeout)
            return

        if self.last_lease.sid == conf.myself.sid:
            self.lease_manager.renew_thread = RenewLeaseThread(self.lease_manager)
            self.lease_manager.renew_thread.start()
            self.lease_manager.expire_thread = ExpireLeaseThread(self.lease_manager)
            self.lease_manager.expire_thread.start()
        else:
            self.lease_manager.require_thead = RequireLeaseThread(self.lease_manager)
            self.lease_manager.require_thead.start()

        #if Others have the lease, start a acquire process
        #else:
            #if self.lease_manager.renew_thread:
                #self.lease_manager.renew_thread.stop()
            #self.lease_manager.require_thead = RequireLeaseThread(self.lease_manager)
            #self.lease_manager.require_thead.start()

        #update expire thread
        #self.lease_manager.clean_expire_timer()
        #self.lease_manager.create_expire_timer(self.last_lease)


    def check_local_state(self):
        if self.last_lease.sid == REVOKING:
            return self.last_lease
        elif self.last_lease.sid == None:
            #no local information available
            log.info('check local state , no local information available')
            return LOCALLY_UNKNOWN
        elif self.last_lease.sid == conf.myself.sid:
            log.info('local host is primary, I hold the lease')
            if get_utc_time() < self.last_lease.timeout:
                log.info('local host\'s lease still valid')
                return self.last_lease
            else:
                log.info('local host\'s lease outdate')
                return OUTDATE
        elif self.last_lease.sid != conf.myself.sid:
            log.info('other host is primary')
            if get_utc_time() + conf.d_max <= self.last_lease.timeout:
                log.info('other lease is valid')
                return self.last_lease
            elif get_utc_time() - conf.d_max > self.last_lease.timeout:
                log.info('other host\'s lease outdate')
                return OUTDATE
            else:
                log.info('lease is in safe period')
                return WAIT


class Proposer():
    def __init__(self, dispatcher):
        self.ballot = 0
        self.queue = dispatcher.proposer_queue
        #self.last_lease = Lease()
        #self.accepted_lease = Lease()
        #self.instance_number=0
        self.running = False

    #def get_instance_number(self):
    #    return self.instance_number;

    def clear_queue(self):
        while not self.queue.empty():
            self.queue.get_nowait()

    def _run(self,*args):
        timeout = Timeout(conf.proposer_timeout)
        try:
            self.initiate_consensus(*args)
        except Timeout, t:
            if t is not timeout:
                raise
            log.error('!!proposer timeout: cancel !!')
        finally:
            timeout.cancel()
            self.clear_queue()
            self.running = False

    #def start_async(self, *args):
        #log.debug('start_async')
        #if not self.running:
            #self.running = True
            #super(Proposer, self).start(*args)


    def wait_sync(self):
        while self.running:
            log.debug('propser\'s running,waiting')
            sleep(1);

    def start_sync(self, *args):
        log.debug('start_sync')
        if not self.running:
            self.running = True
            self._run(*args)


    def _increase_ballot(self):
        log.debug('gernerate new ballot %d', self.ballot)
        self.ballot += len(conf.server_list) + conf.myself.sid

    def _check_majority(self, recv_set):
        #TODO Dose it have other things to do?
        log.debug('CHECK MAJORITY')
        for k,v in recv_set.iteritems():
            log.debug("User %d , Select %s", k, v)
        return len(recv_set) >= len(conf.server_list)/2 + 1

    def _notify_all(self, m):
        m.add_sid(conf.myself.sid)
        for server in conf.server_list.itervalues():
            do_send(server.sid, m.enpack())


    #only one initiate_consensus could run in the same time
    #TODO need error handle
    def initiate_consensus(self, suggested_host, suggested_host_timeout,
            instance_number, renew=False, revoke=False):


        self._increase_ballot()
        log.info('Proposer start initiate_consensus')
        #list of ack sid
        recv_set = dict()

        if renew :
            prepare_msg = Message(method=RENEW,
                    ballot=self.ballot,
                    instance_number=instance_number)
        else:
            prepare_msg = Message(method=PREPARE,
                    ballot=self.ballot,
                    instance_number=instance_number)

        #START SEND PREPARE
        self._notify_all(prepare_msg)

        while True:
            #TODO some timeout maybe happen,to return failed
            #must be ECHO_PREPARE
            recv_msg = self.queue.get()
            if recv_msg.echo != ECHO_PREPARE:
                continue

            if recv_msg.method == OUTDATE and recv_msg.instance_number > instance_number:

                log.info('PROPOSER: Multipaxos messages to find current instance')

                #self.last_lease.sid = None
                #self.last_lease.timeout = None
                suggested_host = recv_msg.suggested_host
                suggested_host_timeout = recv_msg.suggested_host_timeout
                self.ballot = recv_msg.ballot
                instance_number = recv_msg.instance_number

                self.initiate_consensus(suggested_host , suggested_host_timeout,
                        instance_number)
                return

            elif recv_msg.method == NACK and \
                    recv_msg.ballot > self.ballot and \
                    recv_msg.instance_number == instance_number:

                #NOT POSSIBLE when RENEW
                log.info('PROPOSER: another proposal had a higher ballot number')
                #FIXME sleep random?
                sleep(1)
                self.initiate_consensus(suggested_host, suggested_host_timeout,
                        instance_number)
                return
            elif recv_msg.method == ACK and \
                    recv_msg.instance_number == instance_number and \
                    recv_msg.ballot >= self.ballot:

                #maybe got majority
                recv_set[recv_msg.sid] = recv_msg
                if self._check_majority(recv_set):
                    break;

        #get all accecpted ballot, you have to accept it
        accepted_hosts = [msg for msg in recv_set.itervalues() if msg.suggested_host != None]
        if len(accepted_hosts) != 0:
            #find the biggest ballot number
            #is that possible to receive to the same max ballot, but have
            #different suggestec host? NO
            #there
            log.debug('PROPOSER: already accepted_hosts is %s', accepted_hosts)
            max_ballot = 0
            max_index = 0
            for i, msg in enumerate(accepted_hosts):
                if max_ballot < msg.ballot:
                    max_ballot = msg.ballot
                    max_index = i

            #find the max acceptecd host
            self.ballot = accepted_hosts[max_index].ballot
            suggested_host = accepted_hosts[max_index].suggested_host

            #when acceptor had already acceptor some host, there is two conditions.
            #1. they have accepted other, proposer has to accepte host and host_timeout
            #2. they have accepted one, but the one is proposer itself(RENEW), proposer only
            #   need to refresh host_timeout
            if not renew:
                suggested_host_timeout = accepted_hosts[max_index].suggested_host_timeout

        #normal situation, msg.suggested_host == None
        #start SEND ACCEPT
        accept_msg = Message(method=ACCEPT,
                ballot=self.ballot,
                instance_number=instance_number,
                suggested_host=suggested_host,
                suggested_host_timeout=suggested_host_timeout)
        self._notify_all(accept_msg)


        recv_set = dict()
        get_majority_accept = False
        while True:
            recv_msg = self.queue.get()
            if recv_msg.echo != ECHO_ACCEPT:
                continue

            if recv_msg.method == ACK and \
            instance_number == recv_msg.instance_number and \
            suggested_host == recv_msg.suggested_host:
                recv_set[recv_msg.sid] = recv_msg
                if self._check_majority(recv_set):
                    log.debug('accept majority accepted')
                    get_majority_accept = True
                    break;
        if get_majority_accept:
            #update local data
            #self.last_lease.sid = recv_msg.suggested_host
            #self.last_lease.timeout = recv_msg.suggested_host_timeout
            #self.accepted_lease.sid = recv_msg.suggested_host
            #self.accepted_lease.timeout = recv_msg.suggested_host_timeout
            log.debug(recv_set)

            self.ballot = recv_msg.ballot

            #start SEND LEARN
            if not revoke:
                learn_msg = Message(method=LEARN,
                        ballot=self.ballot,
                        instance_number=instance_number,
                        suggested_host=suggested_host,
                        suggested_host_timeout=suggested_host_timeout)
            else:
                learn_msg = Message(method=LEARN,
                        ballot=self.ballot,
                        instance_number=instance_number,
                        suggested_host=REVOKING,
                        suggested_host_timeout=0)

            #store information
            self._notify_all(learn_msg)



#I can only get the success ret from Acceptor:on_learn, but if renew or requirelease
#failes, I can not know. so make them to be threads
class RenewLeaseThread(EventThread):
    def __init__(self, lease_manager):
        self._stop = True
        self.lease_manager = lease_manager

    def stop(self):
        self._stop= True
        kill(self.id)

    def start(self, *args):
        self._stop =False
        super(RenewLeaseThread, self).start()

    def _run(self):
        try:
            while not self._stop and self.lease_manager.acceptor.last_lease.sid == conf.myself.sid:
                log.info("RenewThread is running")
                time_to_expire = self.lease_manager.acceptor.last_lease.timeout - get_utc_time()
                log.info("time_to_expire %d", time_to_expire)
                sleep(min(conf.renew_internal , time_to_expire))
                if not self._stop:
                    self.lease_manager.renew_lease()
                    sleep(1)
        finally:
            log.info("RenewThread is closed")


class RequireLeaseThread(EventThread):
    def __init__(self, lease_manager):
        self._stop = True
        self.lease_manager = lease_manager

    def start(self, *args):
        self._stop =False
        super(RequireLeaseThread, self).start()

    def stop(self):
        self._stop= True
        kill(self.id)

    def _run(self):
        retries = 0
        try:
            while not self._stop and self.lease_manager.acceptor.last_lease.sid != conf.myself.sid and retries < conf.require_retry_times:
                retries += 1;
                lease_status = self.lease_manager.lease_status()
                #sleep(self.lease_manager.acceptor.last_lease.timeout - get_utc_time())
                log.info("RequireLeaseThread is running %s", lease_status)

                while lease_status == WAIT and not self._stop:
                    sleep(conf.d_max)
                    lease_status = self.lease_manager.lease_status()

                if (lease_status == OUTDATE or lease_status == LOCALLY_UNKNOWN) and not self._stop:
                    log.info("LEASE is MISSING, ACQUIRE IT!")
                    self.lease_manager.require_lease()
                    sleep(1)
                elif not self._stop:
                    sleep(self.lease_manager.acceptor.last_lease.timeout - get_utc_time())
        finally:
            log.info("RequireLeaseThread is close")

#not need to update timer ,this is different from other timer ,such as
#renew_thread, require_thread
class RevokingTimeoutThread(EventThread):
    def __init__(self, lease_manager):
        self.lease_manager = lease_manager
        self.resume_timeout = None
        self.running = False

    def start(self, *args):
        if not self.running:
            super(RevokingTimeoutThread, self).start(*args)

    def _run(self, resume_timeout):
        self.running = True
        self.resume_timeout = resume_timeout
        log.debug('start sleep to ensure remote requires stop, system OK on %s', time.ctime(self.resume_timeout))
        sleep(resume_timeout - get_utc_time() + 1)
        self.lease_manager.acceptor.accepted_lease.set_none()
        self.lease_manager.acceptor.last_lease.set_none()
        log.debug('RevokingTimeoutThread finished')
        self.running = False

class ExpireLeaseThread(EventThread):
    def __init__(self, lease_manager):
        self._stop = True
        self.lease_manager = lease_manager

    def start(self, *args):
        self._stop =False
        super(ExpireLeaseThread, self).start()

    def _run(self):
        try:
            while not self._stop:
                log.info("ExpireLeaseThread is running")
                sleep(self.lease_manager.acceptor.last_lease.timeout -get_utc_time())
                if self.lease_manager.lease_status() == OUTDATE and not self._stop:
                    log.info("SET NONE!!")
                    self.lease_manager.acceptor.last_lease.sid = None
                    self.lease_manager.acceptor.last_lease.timeout= None
                    self.lease_manager.acceptor.accepted_lease.sid = None
                    self.lease_manager.acceptor.accepted_lease.timeout= None
                    #start require_lease
                    if self.lease_manager.require_thead:
                        self.lease_manager.require_thead.stop()
                    self.lease_manager.require_thead = RequireLeaseThread(self.lease_manager)
                    self.lease_manager.require_thead.start()
                    break;
                sleep(conf.d_max)
        finally:
            log.info("ExpireLeaseThread is closed")

    def stop(self):
        self._stop= True
        kill(self.id)


class LeaseManager(object):
    def __init__(self,propser,acceptor,timeout):
        self.lease_timeout = timeout
        self.propser = propser
        self.acceptor = acceptor
        self.acceptor.set_lease_manager(self)

        #renew and require thread to make sure HA
        #self.renew_thread = RenewLeaseThread(self)
        self.renew_thread = None
        #self.require_thead = RequireLeaseThread(self)
        self.require_thead = None
        self.expire_thread = None
        self.revoking_timeout_thread = RevokingTimeoutThread(self)

    def set_propser(self, propser):
        self.propser = propser

    def set_acceptor(self, acceptor):
        self.acceptor = acceptor

    #run in timeout and command mode
    #tell the difference between NORMAL and AUTOMATIC
    def require_lease(self):
        while True:
            x = self.lease_status()
            if x == OUTDATE:
                #the local information is outdated
                #next information is used
                self.propser.wait_sync()
                self.propser.start_sync(conf.myself.sid,
                        get_utc_time() + self.lease_timeout,
                        self.acceptor.get_instance_number()+1)
                return
            elif x == LOCALLY_UNKNOWN:
                #no information, means ticket is empty,
                #could grant
                self.propser.wait_sync()
                self.propser.start_sync(conf.myself.sid,
                        get_utc_time() + self.lease_timeout,
                        self.acceptor.get_instance_number())
                return
            elif x == WAIT:
                 sleep(conf.d_max)
                 continue;
            else:
                 return x

    def lease_status(self):
        return self.acceptor.check_local_state()

    def catchup_lease(self):
        self.propser.wait_sync()
        self.propser.start_sync(None,
                get_utc_time() + self.lease_timeout,
                self.acceptor.get_instance_number())
        return self.acceptor.check_local_state()

    #run in timeout
    def renew_lease(self):
        #ensure we have last_lease
        lease = self.lease_status()
        if lease not in (OUTDATE, WAIT, LOCALLY_UNKNOWN):
            if lease.sid == conf.myself.sid:
                self.propser.wait_sync()
                self.propser.start_sync(conf.myself.sid,
                        get_utc_time() + self.lease_timeout,
                        self.acceptor.last_lease.instance_number + 1, True)

    def revoke_lease(self):
        #ensure we have last_lease
        lease = self.lease_status()
        if lease not in (OUTDATE, WAIT, LOCALLY_UNKNOWN):
            if lease.sid == conf.myself.sid:
                if self.renew_thread:
                    self.renew_thread.stop()
                    self.renew_thread = None
                log.debug("revoke start")
                self.propser.wait_sync()
                self.propser.start_sync(conf.myself.sid,
                        get_utc_time() + self.lease_timeout,
                        self.acceptor.last_lease.instance_number + 1, True,True)
                log.debug("revoke end")

class LeaseAdmin(Admin):
    def __init__(self,port, lease_manager):
         super(LeaseAdmin, self).__init__(port)
         self.lease_manager = lease_manager

    @public
    def lease_list(self, *args):
        return self.lease_manager.lease_status()

    @public
    def lease_slowlist(self, *args):
        return self.lease_manager.catchup_lease()

    @public
    def lease_acquire(self, *args):
        return self.lease_manager.require_lease()

    @public
    def lease_revoke(self, *args):
        return self.lease_manager.revoke_lease()

#unix format
#from Ruslan's Blog
def get_utc_time():
    d = datetime.utcnow()
    return calendar.timegm(d.utctimetuple())

class CheckUTCTime(EventThread):
    def _run(self):
        pass
