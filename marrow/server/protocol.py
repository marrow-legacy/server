# encoding: utf-8

import socket
import functools

from marrow.io import iostream


__all__ = ['Protocol']
log = __import__('logging').getLogger(__name__)



class Protocol(object):
    client = iostream.IOStream
    
    def __init__(self, server, **options):
        super(Protocol, self).__init__()
        
        self.server = server
        self.options = options
    
    def start(self):
        # Register for new connection notifications.
        callback = functools.partial(self._accept, self.server.socket)
        self.server.io.add_handler(self.server.socket.fileno(), callback, self.server.io.READ)
    
    def stop(self):
        self.server.io.remove_handler(self.server.socket.fileno())
    
    def _accept(self, sock, fd, events):
        try:
            connection, address = sock.accept()
        
        except socket.error, e:
            if e[0] not in (errno.EWOULDBLOCK, errno.EAGAIN):
                raise
            
            return
        
        client = self.client(connection)
        
        self.accept(client)
    
    def accept(self, client):
        pass
