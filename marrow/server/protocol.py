# encoding: utf-8

import errno
import socket

from marrow.util.compat import exception
from marrow.io import iostream


__all__ = ['Protocol']
log = __import__('logging').getLogger(__name__)



class Protocol(object):
    client = iostream.IOStream
    
    def __init__(self, server, testing=False, **options):
        super(Protocol, self).__init__()
        
        self.server = server
        self.testing = testing
        self.options = options
    
    def start(self):
        pass
    
    def stop(self):
        pass
    
    def _accept(self, sock, fd, events):
        # TODO: Move this into the Server class.
        # Work that needs to be done can be issued within the real accept method.
        
        try:
            connection, address = sock.accept()
        except socket.error:
            exc = exception().exception
            
            if exc.args[0] not in (errno.EWOULDBLOCK, errno.EAGAIN):
                raise
            
            return
        
        client = self.client(connection, io_loop=self.testing or None)
        
        self.accept(client)
    
    def accept(self, client):
        pass
