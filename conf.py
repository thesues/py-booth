# vim: tabstop=4 shiftwidth=4 softtabstop=4
from utils import Server, ServerList
import logging

server_list =None
myself = None
interact_mode = True
lease_timeout = 120
d_max = 1
require_retry_times = 3
proposer_timeout = 40
renew_internal = 30

def initlog(logfile):
    log = logging.getLogger()
    hdlr = logging.FileHandler(logfile)
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    hdlr.setFormatter(formatter)
    log.addHandler(hdlr)
    log.setLevel(logging.NOTSET)

def read_conf(myid):
    global log
    global server_list
    global myself

    server_list = ServerList()
    for i in [('127.0.0.1', 9991, 1), ('127.0.0.1', 9992, 2), ('127.0.0.1', 9993, 3)]:
        s = Server(i[2], i[0], i[1])
        server_list.add_server(s)

    initlog('server'+str(myid)+'.log')
    myself = server_list.get(myid)


