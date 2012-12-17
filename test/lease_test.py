# vim: tabstop=4 shiftwidth=4 softtabstop=4
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

class BoothTestCase(unittest.TestCase):
    def setUp(self):
        os.system('sh fireup.sh restart')
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

    def kill(self, id):
        os.system('''pkill -f "run.py %s"''' % id);

    def test_normal_renew(self):
        time.sleep(4)
        self.c1.sendall('lease list\n');
        self.assertEqual(self.c1.recv(1024),'LOCALLY_UNKNOWN')

        self.c2.sendall('lease list\n');
        self.assertEqual(self.c2.recv(1024),'LOCALLY_UNKNOWN')

        self.c3.sendall('lease list\n');
        self.assertEqual(self.c3.recv(1024),'LOCALLY_UNKNOWN')

        for i in (self.c1, self.c2, self.c3):
            i.sendall('lease acquire\n');
            r = parse_result(i.recv(1024));
            self.assertEqual(r['sid'], '1')
            self.assertEqual(r['epoch'], '0')

        time.sleep(35)
        for i in (self.c1, self.c2, self.c3):
            i.sendall('lease acquire\n');
            r = parse_result(i.recv(1024));
            self.assertEqual(r['sid'], '1')
            self.assertEqual(r['epoch'], '1')

        time.sleep(35)
        for i in (self.c1, self.c2, self.c3):
            i.sendall('lease acquire\n');
            r = parse_result(i.recv(1024));
            self.assertEqual(r['sid'], '1')
            self.assertEqual(r['epoch'], '2')

    def test_abandon_lease(self):
        time.sleep(4)

        self.c1.sendall('lease acquire\n');
        r = parse_result(self.c1.recv(1024));
        self.assertEqual(r['sid'], '1')
        self.assertEqual(r['epoch'], '0')

        self.kill(2)
        self.kill(3)
        time.sleep(65)

        self.c1.sendall('lease list\n');
        self.assertEqual(self.c1.recv(1024), 'LOCALLY_UNKNOWN')

    def test_unormal(self):
        time.sleep(4)
        self.c1.sendall('lease acquire\n');
        r = parse_result(self.c1.recv(1024));
        self.assertEqual(r['sid'], '1')
        self.assertEqual(r['epoch'], '0')

        self.kill(1)
        time.sleep(65)
        for i in (self.c2, self.c3):
            i.sendall('lease list\n')
            r = parse_result(i.recv(1024));
            self.assertEqual(r['sid'], '3')
            self.assertEqual(r['epoch'], '1')

    def test_unormal_back(self):
        time.sleep(4)
        self.c3.sendall('lease acquire\n');
        r = parse_result(self.c3.recv(1024));
        self.assertEqual(r['sid'], '3')
        self.assertEqual(r['epoch'], '0')

        self.kill(3)









if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(BoothTestCase)
    unittest.TextTestRunner(verbosity=2).run(suite)
