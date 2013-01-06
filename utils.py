# vim: tabstop=4 shiftwidth=4 softtabstop=4 et
class Server(object):
    def __init__(self, sid, address, port):
        self.sid = sid
        self.address = address
        self.port = port
    def equal(self,server):
        if self.sid == server.sid and self.address == server.address \
        and self.port == server.port:
            return True
        else:
            return False
    def __str__(self):
        return "sid:%d, address:%s, port:%d" % (self.sid, self.address, self.port)


class ServerList(dict):
    __getattr__ = dict.__getitem__
    def __init__(self,*args):
        for i in args:
            self[i.sid] = i
    def add_server(self, s):
        self[s.sid] = s
