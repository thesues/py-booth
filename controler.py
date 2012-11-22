# vim: tabstop=4 shiftwidth=4 softtabstop=4
import eventlet
from eventlet.green import socket
from eventlet import Queue
from eventlet import kill
from greenlet import GreenletExit
import struct
import sys
import errno
import functools
from utils import Server, ServerList
import conf
import logging as log


_pool = eventlet.GreenPool(200)

_shutdown = False



_sender_worker_map = dict()

#sid => class Queue
#which means I have the same Queue number as server number
_send_queue_map = dict()

#only one recv queue is needed,
_recv_queue = Queue()


class EventThread(object):
    def start(self,*args):
        self.id = _pool.spawn(self._run, *args)
    def _run(self, *args):
        pass


class _SendWorker(EventThread):
    def __init__(self, sock, sid):
        self._dout = sock.makefile('w')
        self._sid = sid
        self._recvWorker = None
        self._running = True

    def set_recv(self, rw):
        self._recvWorker = rw

    def finish(self):
        if not self._running:
            return
        self._dout.close()
        if(self._recvWorker):
            self._recvWorker.finish()
        _sender_worker_map.pop(self._sid)
        self._running = False
        log.debug('finish send worker with sid %d', self._sid)
        kill(self.id)
        kill(self._recvWorker.id)

    def _run(self):
        try:
            while not _shutdown and self._running:
                my_queue = _send_queue_map.get(self._sid)
                msg = my_queue.get()
                self._dout.write(struct.pack('=I',len(msg)))
                self._dout.write(msg)
                self._dout.flush()
        except GreenletExit, err:
            pass
        except:
            log.error(sys.exc_info())
            log.error("send work Failed to sid %d", self._sid)
        finally:
            self.finish()


class _RecvWorker(EventThread):
    def __init__(self, sock, sid, sw):
        self._din = sock.makefile('r')
        self._sid = sid
        self._sw = sw
        self._running = True

    def _run(self):
        try:
            while not _shutdown and self._running:

                #byte4 = self._sock.recv(4)
                byte4 = self._din.read(4)

                if byte4 and len(byte4) == 4:
                    length = struct.unpack('=I', byte4)
                else:
                    if byte4 == '':
                        log.debug('received close msg from sid %d',
                                self._sid)
                    else:
                        log.error('received ERROR msg %s from sid %d',
                                byte4, self._sid)
                    break;

                length = length[0]
                data = self._din.read(length)
                _recv_queue.put(data)
                log.debug('received msg %s from sid %d', data, self._sid)
        except GreenletExit, err:
            pass
        except:
            log.error(sys.exc_info())
        finally:
            self._sw.finish()

    def finish(self):
        if not self._running:
            return
        self._running = False
        self._din.close()
        log.debug('finish recv worker with sid %d', self._sid)

def do_send(sid, msg):

    if not _send_queue_map.get(sid):
        _send_queue_map[sid] = Queue()
    #loop back
    if sid == conf.myself.sid:
        _recv_queue.put(msg)
    else:
        _send_queue_map.get(sid).put(msg)

    connect_one(sid)

def do_recv():
    return _recv_queue.get()



def receive_connection(sock):
    try:
        byte4 = sock.recv(4)
        sid = struct.unpack('=I', byte4)
    except:
        log.error(sys.exc_info())
        log.error('receive_connection error (receive_connection)')
        sock.close()
        return False


    sid = sid[0]
    if sid > len(conf.server_list) or sid < 0:
        log.warn('input sid wrong %d', sid)
        sock.close()
        return False

    log.debug('request from sid %d(my %d)', sid, conf.myself.sid)

#    if sid == conf.myself.sid:
#        log.info("connected to myself")
#        return


    #If wins the challenge, then close the old connection.
    if sid < conf.myself.sid:
        log.debug('get lower sid %d, I will connection it insdead',sid)
        #FIXME:
        sw = _sender_worker_map.get(sid)
        #every connect would close old sw/recv thread
        if sw:
            sw.finish()
        sock.close()
        connect_one(sid)
    #lose the challenge, the connection is OK
    else:
        sw = _SendWorker(sock, sid)
        rw = _RecvWorker(sock, sid, sw)
        sw.set_recv(rw)
        sock.close()

        #add to _sender_worker_map
        vsw = _sender_worker_map.get(sid)
        if vsw:
            vsw.finish()
        _sender_worker_map[sid] = sw

        #add to _send_queue_map
        if not _send_queue_map.get(sid):
            _send_queue_map[sid] = Queue()
        sw.start()
        rw.start()
        log.info('SUCCESS recv connect sid %d',sid)


def connect_one(sid):
    if sid == conf.myself.sid:
        if _sender_worker_map.get(sid):
            log.debug('already has connection to %d', sid)
        else:
            _sender_worker_map[sid] = 1
            log.debug('connect to myself')
        return True

    if not _sender_worker_map.get(sid):
        try:
            sock = socket.socket()
            remote = conf.server_list.get(sid)
            if remote:
                log.debug('try to connnect sid:%d, %s:%d', remote.sid, remote.address, remote.port);
                sock.connect((remote.address, remote.port))
                return initiate_connection(sock, sid)
            else:
                log.error('try to connect remote sid %s which does not exsits', sid)
                return False
        except socket.error as err:
            if err[0] == errno.ECONNREFUSED:
                log.warn('connect to %s refused', remote)
                sock.close()
                return False
            else:
                #TODO maybe we can re-try;
                sock.close()
                log.warn('failed to connect %s(%s)', remote, err)
                return False
    else:
        log.debug('already has connection to %d', sid)
        return True


def connect_all():
    for i in conf.server_list.itervalues():
        connect_one(i.sid)


# If this server has initiated the connection, then it gives up on the
# connection if it loses challenge. Otherwise, it keeps the connection.
def initiate_connection(sock, sid):

    sock.sendall(struct.pack('=I', conf.myself.sid))

    if sid > conf.myself.sid:  #lose the challenge
        log.debug('notify higher sid %d to connect me', sid)
        sock.close()
        return True
    else:
        sw = _SendWorker(sock, sid)
        rw = _RecvWorker(sock, sid, sw)
        sw.set_recv(rw)
        sock.close()

        #add to _sender_worker_map
        vsw = _sender_worker_map.get(sid)
        if vsw:
            vsw.finish()
        _sender_worker_map[sid] = sw
        sw.start()
        rw.start()

        #add to _send_queue_map
        if not _send_queue_map.get(sid):
            _send_queue_map[sid] = Queue()
        log.info('SUCCESS to connect sid %d' % sid);
        return True


class _Listen(EventThread):
    def _run(self):
        log.info('========= START CYCLE %s:%d ========', conf.myself.address,
                conf.myself.port)
        self.localserver = eventlet.listen((conf.myself.address, conf.myself.port))
        while not _shutdown:
            try:
                new_sock, address = self.localserver.accept()
                receive_connection(new_sock)
            except Exception, e:
                log.error(e)
                break;
        log.info('Close listener')
        self.localserver.close()


#copy from openstack-swift
def public(func):
    """
    Decorator to declare which methods are public accessible as HTTP requests

    :param func: function to make public
    """
    func.publicly_accessible = True

    @functools.wraps(func)
    def wrapped(*a, **kw):
        return func(*a, **kw)
    return wrapped


class Admin(EventThread):
    def __init__(self, port):
        self._port = port
        self._help = '''
network list
network connect %s
network disconnect %s
network send %s %s
'''

    def _run(self):
        log.info('========= START ADMIN %s:%d ========', conf.myself.address, self._port)
        self.localserver = eventlet.listen((conf.myself.address, self._port))
        while not _shutdown:
            try:
                new_sock, address = self.localserver.accept()
                _pool.spawn_n(self._handle, new_sock, address)
            except Exception, e:
                log.error(e)
                break;
        log.info('Close Admin')
        self.localserver.close()


    @public
    def network_list(self, *args):
        ret = ''
        for v in conf.server_list.itervalues():
            ret += '%s' % v
            if v.sid in _sender_worker_map.keys():
                ret += ' CONNECTED'
            else:
                ret += ' NOT CONNECTED'
            ret += '\n'
        return ret

    @public
    def network_connect(self, *args):
        ret = ''
        try:
            server_sid = args[0]
        except:
            return "need target"

        if server_sid== 'all':
            connect_all();
            ret += 'waiting for result'
            return ret

        try:
            sid = int(server_sid)
            #other checks
        except:
            ret += 'sid is not a number'
            return ret

        if connect_one(sid):
            ret += 'success\n'
        else:
            ret += 'failed\n'
        #TODO give better info
        return ret

    @public
    def network_disconnect(self, *args):
        ret = ''
        try:
            server_sid = args[0]
        except:
            return "need target"
        #TODO check sid
        server_sid = int(server_sid)
        #loopback sid
        if server_sid == conf.myself.sid:
            _sender_worker_map.pop(server_sid)
            return 'success'
        x = _sender_worker_map.get(server_sid)
        if x:
            x.finish()
            return 'success'
        else:
            return 'no such connection'

    @public
    def shutdown(self):
        global _shutdown
        for sw in _sender_worker_map.itervalues():
            sw.finish()
        #TODO finish other thread
        _shutdown = True


    @public
    def network_send(self, *args):
        try:
            server_sid = args[0]
            msg = args[1]
        except:
            return "need target or msg content"

        try:
            sid = int(server_sid)
            #other checks
        except:
            ret += ' sid is not a number'
            return ret
        if not msg:
            return "no msg"
        if sid in _sender_worker_map.keys():
            #ensuse sid was connected
            do_send(sid, msg)
            return 'OK'
        else:
            return 'Not connected to sid %s' % sid

    def _promote(self, channel):
        channel.write('\nPyBooth(sid:%d)>' % conf.myself.sid)
        channel.flush()

    def _handle(self, sock, address):
        channel = sock.makefile('rw')
        try:
            while not _shutdown:
                if conf.interact_mode:
                    self._promote(channel)

                msg = channel.readline()
                if not msg:
                    break;
                #parse commands
                msg = msg.strip()
                u = msg.split()

                if len(u) == 0:
                    continue
                #single commands
                #TODO use getattr to
                #easy to extends function
                if len(u) == 1:
                    if msg == 'help':
                        channel.write(self._help)
                        channel.flush()
                        continue
                    elif msg == 'shutdown':
                        self.shutdown()
                        continue
                    if msg == 'bye' or msg == 'quit' or msg == 'exit':
                        channel.write('bye!\n')
                        channel.close()
                        sock.close()
                        break;

                #double commands
                if len(u)>=2:
                    method = u[0]
                    submethod = u[1]
                    #find a method to do
                    req = '%s_%s' % (method, submethod)
                    args = tuple(u[2:])
                    try:
                        func = getattr(self, req)
                        if not getattr(func, 'publicly_accessible'):
                            func = None
                    except AttributeError:
                        func = None
                    if func:
                        ret = func(*args)
                        channel.write(ret)
                        channel.flush()
                        continue

                channel.write('Your command is wrong')
                channel.flush()
        except:
            log.error(sys.exc_info())
            channel.write('internal error occur, close connection\n')
        finally:
            log.info('remote client %s disconnected\n', address)
            channel.close()
            sock.close()


#TODO add a magic number
#TODO add add timer function
class HeartBeat(EventThread):
    pass


class Controler(object):
    def __init__(self):
        self.thread_list=[]
        #self._admin = Admin(1234 + conf.myself.sid)
        self._listener = _Listen()

    def add_event_thread(self, t):
        self.thread_list.append(t)

    def set_admin(self, admin):
        self._admin = admin

    def start(self):
        log.info('                                    ')
        log.info('|----------------------------------|')
        log.info('|-----------START PYBOOTH----------|')
        log.info('|----------------------------------|')
        log.info('                                    ')


        self.add_event_thread(self._listener)
        self.add_event_thread(self._admin)

        for i in self.thread_list:
            i.start()

        _pool.waitall()
