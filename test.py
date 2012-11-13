# vim: tabstop=4 shiftwidth=4 softtabstop=4
import unittest
import socket
import os
import time

class BoothTestCase(unittest.TestCase):
    def setUp(self):
        os.system('sh test.sh restart')
        self.c1 = socket.socket()
        self.c1.connect(('127.0.0.1',1235))

        self.c2 = socket.socket()
        self.c2.connect(('127.0.0.1',1236))

        self.c3 = socket.socket()
        self.c3.connect(('127.0.0.1',1237))

        self.s1 = 'sid:1, address:127.0.0.1, port:9991'
        self.s2 = 'sid:2, address:127.0.0.1, port:9992'
        self.s3 = 'sid:3, address:127.0.0.1, port:9993'

    def tearDown(self):
        self.c1.close()
        self.c2.close()
        self.c3.close()
        os.system('sh test.sh stop')

    def connect_all(self):
        self.c1.sendall('network connect all\n')
        self.c2.sendall('network connect all\n')
        self.c3.sendall('network connect all\n')
        self.c1.recv(1024)
        self.c2.recv(1024)
        self.c3.recv(1024)
        time.sleep(2)

    def test_network_list(self):
        self.connect_all()


        self.c1.sendall('network list\n')
        self.c2.sendall('network list\n')
        self.c3.sendall('network list\n')


        self.assertEqual(self.c1.recv(1024), '%s CONNECTED\n%s CONNECTED\n%s CONNECTED\n' % (self.s1, self.s2, self.s3))
        self.assertEqual(self.c2.recv(1024), '%s CONNECTED\n%s CONNECTED\n%s CONNECTED\n' % (self.s1, self.s2, self.s3))
        self.assertEqual(self.c3.recv(1024), '%s CONNECTED\n%s CONNECTED\n%s CONNECTED\n' % (self.s1, self.s2, self.s3))
       
    def test_network_disconnect(self):
        self.connect_all()

        self.c1.sendall('network disconnect 3\n')
        self.c1.recv(1024)
        time.sleep(1)

        self.c1.sendall('network list\n')
        self.c2.sendall('network list\n')
        self.c3.sendall('network list\n')
        self.assertEqual(self.c1.recv(1024), '%s CONNECTED\n%s CONNECTED\n%s NOT CONNECTED\n' % (self.s1, self.s2, self.s3))
        self.assertEqual(self.c2.recv(1024), '%s CONNECTED\n%s CONNECTED\n%s CONNECTED\n' % (self.s1, self.s2, self.s3))
        self.assertEqual(self.c3.recv(1024), '%s NOT CONNECTED\n%s CONNECTED\n%s CONNECTED\n'% (self.s1, self.s2, self.s3))



        self.c3.sendall('network connect 1\n')
        self.c3.recv(1024)
        time.sleep(2)

        self.c1.sendall('network list\n')
        self.c3.sendall('network list\n')
        self.assertEqual(self.c1.recv(1024), '%s CONNECTED\n%s CONNECTED\n%s CONNECTED\n' % (self.s1, self.s2, self.s3))
        self.assertEqual(self.c3.recv(1024), '%s CONNECTED\n%s CONNECTED\n%s CONNECTED\n'% (self.s1, self.s2, self.s3))


        self.c2.sendall('network disconnect 1\n')
        self.c2.sendall('network disconnect 2\n')
        self.c2.sendall('network disconnect 3\n')
        #omit return value
        self.c2.recv(1024)
        self.c2.recv(1024)
        self.c2.recv(1024)

        time.sleep(2)
        self.c1.sendall('network list\n')
        self.c2.sendall('network list\n')
        self.c3.sendall('network list\n')
        self.assertEqual(self.c1.recv(1024), '%s CONNECTED\n%s NOT CONNECTED\n%s CONNECTED\n' % (self.s1, self.s2, self.s3))
        self.assertEqual(self.c2.recv(1024), '%s NOT CONNECTED\n%s NOT CONNECTED\n%s NOT CONNECTED\n' % (self.s1, self.s2, self.s3))
        self.assertEqual(self.c3.recv(1024), '%s CONNECTED\n%s NOT CONNECTED\n%s CONNECTED\n'% (self.s1, self.s2, self.s3))


        self.c2.sendall('network connect all\n')
        self.c2.recv(1024)
        time.sleep(2)

        self.c1.sendall('network list\n')
        self.c2.sendall('network list\n')
        self.c3.sendall('network list\n')
        self.assertEqual(self.c1.recv(1024), '%s CONNECTED\n%s CONNECTED\n%s CONNECTED\n' % (self.s1, self.s2, self.s3))
        self.assertEqual(self.c2.recv(1024), '%s CONNECTED\n%s CONNECTED\n%s CONNECTED\n' % (self.s1, self.s2, self.s3))
        self.assertEqual(self.c3.recv(1024), '%s CONNECTED\n%s CONNECTED\n%s CONNECTED\n'% (self.s1, self.s2, self.s3))

    def test_network_send(self):
        self.connect_all()
        self.c1.sendall('network send 3 abc1\n')
        self.c2.sendall('network send 2 abc2\n')
        self.c3.sendall('network send 1 abc3\n')

        self.c1.sendall('network send 1 abc1\n')

        self.c1.recv(1024)
        self.c2.recv(1024)
        self.c3.recv(1024)





if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(BoothTestCase)
    unittest.TextTestRunner(verbosity=2).run(suite)

