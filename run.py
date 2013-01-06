# vim: tabstop=4 shiftwidth=4 softtabstop=4 expandtab
import conf
import sys
from fatlease import Acceptor
from fatlease import Proposer
from fatlease import Dispatcher
from fatlease import LeaseManager
from fatlease import LeaseAdmin

from controler import Controler


if __name__  == '__main__':
    myid = int(sys.argv[1])
    if len(sys.argv) > 2:
        conf.test_mode = True

    conf.read_conf(myid)


    delegate = Dispatcher()
    acceptor = Acceptor(delegate)
    proposer = Proposer(delegate)
    #60 == lease expire time
    lease_manager = LeaseManager(proposer, acceptor, conf.lease_timeout)
    admin = LeaseAdmin(1234 + conf.myself.sid,lease_manager)


    control = Controler()
    control.set_admin(admin)
    control.add_event_thread(delegate)
    control.add_event_thread(acceptor)
    #control.add_event_thread(p)

    control.start()
