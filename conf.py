# vim: tabstop=4 shiftwidth=4 softtabstop=4 et
from utils import Server, ServerList
import logging
import argparse
import ConfigParser
import sys

server_list =None
myself = None

#default value
test_mode = False
lease_timeout = 60
d_max = 1
require_retry_times = 3
proposer_timeout = 40
renew_internal = 30
client_port = 1234

#http://stackoverflow.com/questions/2819696/parsing-properties-file-in-python/2819788#2819788
class FakeSecHead(object):
    def __init__(self, fp):
        self.fp = fp
        self.sechead = '[asection]\n'
    def readline(self):
        if self.sechead:
            try: return self.sechead
            finally: self.sechead = None
        else: return self.fp.readline()



def initlog(logfile):
    log = logging.getLogger()
    hdlr = logging.FileHandler(logfile)
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    hdlr.setFormatter(formatter)
    log.addHandler(hdlr)
    log.setLevel(logging.NOTSET)


def parse_cmdline(argv):
    parser = argparse.ArgumentParser(description='py-booth is an application')
    parser.add_argument('-c',dest='config_file',action='store', nargs=1, type=file, help="configuration file")
    result = parser.parse_args(argv)
    read_conf(result.config_file[0])

def read_conf(config_file):
    global log
    global server_list
    global myself

    global client_port
    global test_mode
    global lease_timeout
    global d_max
    global require_retry_times
    global proposer_timeout
    global renew_internal


    myid = None
    server_list = ServerList()

    cp = ConfigParser.SafeConfigParser()
    cp.readfp(FakeSecHead(config_file))

    ##TODO
    now_parsing = ''
    try:
        for k,v in cp.items('asection'):
            now_parsing = "%s=%s" % (k, v)
            if k == 'client_port':
                client_port = int(v)
            elif k == 'test_mode':
                test_mode = bool(v)
            elif k =='lease_timeout':
                lease_timeout = int(v)
            elif k == 'd_max':
                d_max = int(v)
            elif k == 'require_retry_times':
                require_retry_times = int(v)
            elif k == 'proposer_timeout':
                proposer_timeout = int(v)
            elif k == 'renew_internal':
                renew_internal = int(v)
            elif k == 'myid':
                myid = int(v)
            elif k.startswith('server'):
                sid = k.split('.')[1]
                ip,port = v.split(':')
                s = Server(int(sid), ip , int(port))
                server_list.add_server(s)
            else:
                raise Exception('Dont know the key %s', k)
    except Exception, e:
        print e
        print "PARSING %s ERROR" % now_parsing
        sys.exit(-1)
    finally:
        config_file.close()

    check_conf(myid)


    if test_mode:
        initlog('server'+str(myid)+'.log')
    else:
        initlog('server' + '.log')

    myself = server_list.get(myid)


def check_conf(myid):
    try:
        #server_list as least has itself
        if myid not in server_list.keys():
            raise Exception("myid %s is not in server_list" % myid)
        #
    except Exception, e:
        print e
        sys.exit(-1)




