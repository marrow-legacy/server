# encoding: utf-8

import errno
import socket
import functools

from marrow.util.compat import exception
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
        pass
    
    def stop(self):
        pass
    
    def _accept(self, sock, fd, events):
        try:
            connection, address = sock.accept()
        
        except socket.error:
            exc = exception().exception
            
            if exc.args[0] not in (errno.EWOULDBLOCK, errno.EAGAIN):
                raise
            
            return
        
        client = self.client(connection)
        
        self.accept(client)
    
    def accept(self, client):
        pass
