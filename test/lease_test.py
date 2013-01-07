# vim: tabstop=4 shiftwidth=4 softtabstop=4 et
import unittest
import socket
import os
import time
import datetime
import re
def parse_result(string):
    pattern = r'SID: (\S+), TIMEOUT: (.*), epoch (\S+)'
    obj = re.match(pattern, string)
    if obj:
        sid = obj.group(1)
        timeout = time.strptime(obj.group(2))
        epoch = obj.group(3)
        return dict(sid=sid, timeout=timeout, epoch=epoch)


def stop_booth(id):
    os.system('''pkill -f "run.py %s"''' % id)

def start_booth(id):
    os.system("python ../run.py %s -t&" % id)
    time.sleep(2)

def connect_client(id):
    c = socket.socket()
    c.connect(('127.0.0.1',1234 + int(id)))
    return c

def send_cmd(s, msg):
    if msg[-1] != '\n':
        msg += '\n'
    s.sendall(msg)
    return s.recv(1024)

class BoothTestCase(unittest.TestCase):
    def setUp(self):
        os.system('sh fireup.sh restart')
        time.sleep(2)
        self.c1 = socket.socket()
        self.c1.connect(('127.0.0.1',1235))

        self.c2 = socket.socket()
        self.c2.connect(('127.0.0.1',1236))

        self.c3 = socket.socket()
        self.c3.connect(('127.0.0.1',1237))

    def tearDown(self):
        self.c1.close()
        self.c2.close()
        self.c3.close()
        os.system('sh fireup.sh stop')


    def test_normal_renew(self):
        r = send_cmd(self.c1, 'lease list')
        self.assertEqual(r,'LOCALLY_UNKNOWN')

        for i in (self.c1, self.c2, self.c3):
            r = parse_result(send_cmd(i, 'lease acquire'))
            self.assertEqual(r['sid'], '1')
            self.assertEqual(r['epoch'], '0')

        time.sleep(35)
        for i in (self.c1, self.c2, self.c3):
            r = parse_result(send_cmd(i, 'lease slowlist'))
            self.assertEqual(r['sid'], '1')
            self.assertEqual(r['epoch'], '1')

        time.sleep(35)
        for i in (self.c1, self.c2, self.c3):
            r = parse_result(send_cmd(i, 'lease acquire'))
            self.assertEqual(r['sid'], '1')
            self.assertEqual(r['epoch'], '2')

    def test_abandon_lease(self):

        r = parse_result(send_cmd(self.c1, 'lease acquire'))
        self.assertEqual(r['sid'], '1')
        self.assertEqual(r['epoch'], '0')

        stop_booth(2)
        stop_booth(3)
        time.sleep(65)

        r = send_cmd(self.c1, 'lease list')
        self.assertEqual(r , 'LOCALLY_UNKNOWN')

    def test_unormal(self):
        r = send_cmd(self.c1 ,'lease acquire')
        r = parse_result(r)
        self.assertEqual(r['sid'], '1')
        self.assertEqual(r['epoch'], '0')

        stop_booth(1)
        time.sleep(65)
        for i in (self.c2, self.c3):
            r = parse_result(send_cmd(i, 'lease list'))
            self.assertEqual(r['sid'], '3')
            self.assertEqual(r['epoch'], '1')

    def test_unormal_others_back(self):
        r = parse_result(send_cmd(self.c3, 'lease acquire'))
        self.assertEqual(r['sid'], '3')
        self.assertEqual(r['epoch'], '0')

        stop_booth(1)

        start_booth(1)

        self.c1 = connect_client(1)
        r = send_cmd(self.c1, 'lease slowlist')
        r = parse_result(r)
        self.assertEqual(r['sid'], '3')
        self.assertEqual(r['epoch'], '0')


    def test_unormal_leader_back(self):
        r = parse_result(send_cmd(self.c3, 'lease acquire'))
        self.assertEqual(r['sid'], '3')
        self.assertEqual(r['epoch'], '0')

        #lost leader
        stop_booth(3)

        time.sleep(10)

        #leader back
        start_booth(3)
        self.c3 = connect_client(3)
        r = parse_result(send_cmd(self.c3, 'lease slowlist'))
        self.assertEqual(r['sid'], '3')
        self.assertEqual(r['epoch'], '0')


    def test_normal_revoke(self):
        send_cmd(self.c1, 'lease acquire')

        revoke_time=''
        for i in (self.c1, self.c2, self.c3):
            r = send_cmd(i, 'lease revoke')
            r = parse_result(r)
            self.assertEqual(r['sid'], 'REVOKING')
            self.assertEqual(r['epoch'], '1')
            #the revoke time should be the same, it was
            #caculated by the leader
            if revoke_time:
                self.assertEqual(r['timeout'], revoke_time)
                revoke_time = r['timeout']

    def test_unnormal_revoke(self):
        send_cmd(self.c1, 'lease acquire')

        send_cmd(self.c1, 'lease revoke')


        stop_booth(1)
        time.sleep(1)

        start_booth(1)
        self.c1 = connect_client(1)


        revoke_time=''
        for i in (self.c1, self.c2, self.c3):
            r = send_cmd(i, 'lease slowlist')
            r = parse_result(r)
            self.assertEqual(r['sid'], 'REVOKING')
            self.assertEqual(r['epoch'], '1')
            #the revoke time should be the same, it was
            #caculated by the leader
            if revoke_time:
                self.assertEqual(r['timeout'], revoke_time)
                revoke_time = r['timeout']




if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(BoothTestCase)
    unittest.TextTestRunner(verbosity=2).run(suite)
