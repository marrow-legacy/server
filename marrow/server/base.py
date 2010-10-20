# encoding: utf-8

"""A higher-level socket server API.

Uses Protocols to implement common callbacks without restricting advanced capabilities.

Additionally, provides prefork and worker thread pool capabilities.
"""

import os
import functools
import socket

from inspect import isclass
from Queue import Queue, Empty

from marrow.io import ioloop, iostream
from marrow.server.util import WaitableEvent


__all__ = ['Server']
log = __import__('logging').getLogger(__name__)



class Server(object):
    """A basic multi-process and/or multi-threaded socket server.
    
    The protocol class attriubte should be overridden in subclasses or instances to provide actual functionality.
    """
    
    protocol = None
    callbacks = {'start': [], 'stop': []}
    requests = Queue()
    responses = Queue()
    
    def __init__(self, host=None, port=None, protocol=None, pool=5000, fork=1, **options):
        """Accept the minimal server configuration.
        
        If port is omitted, the host is assumed to be an on-disk UNIX domain socket file.
        
        The protocol is instantiated here, if it is a class, and passed a reference to the server and any additional arguments.
        """
        
        super(Server, self).__init__()
        
        self.socket = None
        self.address = (host if host is not None else '', port)
        self.pool = pool
        
        if protocol:
            self.protocol = protocol
        
        if isclass(self.protocol):
            self.protocol = self.protocol(self, **options)
        
        self.io = ioloop.IOLoop.instance()
        self.wake = None
    
    def start(self):
        """Primary reactor loop.
        
        This handles standard signals as interpreted by Python, such as Ctrl+C.
        """
        
        log.info("Starting up.")
        
        self.wake = WaitableEvent()
        
        self.socket = self._socket()
        self.socket.bind(self.address)
        self.socket.listen(self.pool)
        
        self.io.add_handler(self.wake.fileno(), self.responder, self.io.READ)
        
        log.debug("Executing startup hooks.")
        
        self.protocol.start()
        
        for callback in self.callbacks['start']:
            callback(self)
        
        log.info("Server running with PID %d, serving on %s.", os.getpid(), ("%s:%d" % (self.address[0] if self.address[0] else '*', self.address[1])) if isinstance(self.address, tuple) else self.address)
        
        try:
            self.io.start()
        
        except KeyboardInterrupt:
            log.info("Recieved Control+C.")
            
        except SystemExit:
            log.info("Recieved SystemExit.")
            raise
        
        except:
            log.exception("Unknown server error.")
            raise
        
        finally:
            self.stop()
    
    def stop(self):
        log.info("Shutting down.")
        
        # log.debug("Stopping worker thread pool.")
        # self.worker.stop()
        
        self.io.stop()
        
        log.debug("Executing shutdown callbacks.")
        
        self.protocol.stop()
        
        for callback in self.callbacks['stop']:
            callback(self)
        
        self.wake.close()
        self.wake = None
        
        log.info("Stopped.")
    
    def _socket(self):
        """Create a listening socket.
        
        This handles IPv6 and allows socket re-use by spawned processes.
        
        TCP_NODELAY should be set on client sockets as needed by the protocol.
        """
        
        host, port = self.address
        
        try:
            addr, family, kind, protocol, name, sa = ((host, port), ) + socket.getaddrinfo(host, port, socket.AF_UNSPEC, socket.SOCK_STREAM, 0, socket.AI_PASSIVE)[0]
        
        except socket.gaierror:
            if ':' in host:
                addr, family, kind, protocol, name, sa = ((host, port), socket.AF_INET6, socket.SOCK_STREAM, 0, "", (host, port, 0, 0))
            
            else:
                addr, family, kind, protocol, name, sa = ((host, port), socket.AF_INET, socket.SOCK_STREAM, 0, "", (host, port))
        
        sock = socket.socket(family, kind, protocol)
        # fixes.prevent_socket_inheritance(sock)
        
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setblocking(0)
        
        # If listening on the IPV6 any address ('::' = IN6ADDR_ANY), activate dual-stack.
        if family == socket.AF_INET6 and addr[0] in ('::', '::0', '::0.0.0.0'):
            try:
                sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
            
            except (AttributeError, socket.error):
                pass
        
        return sock
    
    def respond(self, client, *args):
        self.responses.put((client, args))
        self.wake.set()
    
    def responder(self, fd, events):
        self.wake.clear()
        responses = self.responses
        
        try:
            client, response = responses.get(True, 10)
        
        except Empty:
            pass
            
        if client.closed():
            log.debug("Attempted to write to disconnected client: %r", client)
            responses.task_done()
            return
        
        try:
            client.write(*response)
        
        except:
            log.exception("Error writing to client: %r", client)
        
        responses.task_done()


if __name__ == '__main__':
    import logging
    
    logging.basicConfig(level=logging.INFO)
    
    from marrow.io.protocol import Protocol
    
    class EchoProtocol(Protocol):
        def accept(self, client):
            log.info("Accepted connection from %r.", client.address)
            
            self.server.respond(client, "Hello!  Type something and press enter.  Type /quit to quit.\n")
            
            client.read_until("\r\n", functools.partial(self.on_line, client))
        
        def on_line(self, client, data):
            if data[:-2] == "/quit":
                self.server.respond(client, "Goodbye!\r\n", client.close)
                return
            
            self.server.respond(client, data)
            client.read_until("\r\n", functools.partial(self.on_line, client))
    
    Server(None, 8000, EchoProtocol).start()
