# encoding: utf-8

"""A higher-level socket server API.

Uses Protocols to implement common callbacks without restricting advanced capabilities.

Additionally, provides prefork and worker thread pool capabilities.
"""

import os
import sys
import functools
import socket
import time
import random

from inspect import isclass
from binascii import hexlify

if sys.version_info < (3, 0):
    from Queue import Queue, Empty

else:
    from queue import Queue, Empty

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
    
    def __init__(self, host=None, port=None, protocol=None, pool=128, fork=1, **options):
        """Accept the minimal server configuration.
        
        If port is omitted, the host is assumed to be an on-disk UNIX domain socket file.
        
        The protocol is instantiated here, if it is a class, and passed a reference to the server and any additional arguments.
        
        If fork is None or less than 1, automatically detect the number of logical processors (i.e. cores) and fork that many copies.
        
        Do not utilze forking when you need to debug or automatically reload your code in development.
        """
        
        super(Server, self).__init__()
        
        self.socket = None
        self.address = (host if host is not None else '', port)
        self.pool = pool
        self.fork = fork
        
        if protocol:
            self.protocol = protocol
        
        if isclass(self.protocol):
            self.protocol = self.protocol(self, **options)
        
        # self.wake = None
        self.io = None
        
        self.name = socket.gethostname()
    
    def processors(self):
        try:
            import multiprocessing
            
            return multiprocessing.cpu_count()
        
        except ImportError:
            pass
        
        except NotImplementedError:
            pass
        
        try:
            return os.sysconf('SC_NPROCESSORS_CONF')
        
        except ValueError:
            pass
        
        log.error("Unable to automatically detect logical processor count; assuming one.")
        
        return 1
    
    def serve(self, master=True):
        self.io = ioloop.IOLoop.instance()
        
        log.debug("Executing startup hooks.")
        
        self.protocol.start()
        
        for callback in self.callbacks['start']:
            callback(self)
        
        # Register for new connection notifications.
        self.io.add_handler(
                self.socket.fileno(),
                functools.partial(self.protocol._accept, self.socket),
                self.io.READ
            )
        
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
            if master: self.stop(master)
            else: self.io.remove_handler(self.socket.fileno())
    
    def start(self):
        """Primary reactor loop.
        
        This handles standard signals as interpreted by Python, such as Ctrl+C.
        """
        
        log.info("Starting up.")
        
        # self.wake = WaitableEvent()
        
        socket = self.socket = self._socket()
        socket.bind(self.address)
        socket.listen(self.pool)
        
        # self.io.add_handler(self.wake.fileno(), self.responder, self.io.READ)
        
        if self.fork is None or self.fork < 1:
            self.fork = self.processors()
        
        # Single-process operation.
        if self.fork == 1:
            self.serve()
            self.stop()
            return
        
        # Multi-process operation.
        log.info("Pre-forking %d processes from PID %d.", self.fork, os.getpid())
        
        for i in range(self.fork):
            if os.fork() == 0:
                try:
                    random.seed(long(hexlify(os.urandom(16)), 16))
                
                except NotImplementedError:
                    random.seed(int(time.time() * 1000) ^ os.getpid())
                
                self.serve(False)
                
                return
            
        try:
            os.waitpid(-1, 0)
        
        except OSError:
            pass
        
        except KeyboardInterrupt:
            log.info("Recieved Control+C.")
        
        except SystemExit:
            log.info("Recieved SystemExit.")
            raise
        
        except:
            log.exception("Unknown server error.")
            raise
        
        self.stop()
        
        return
    
    def stop(self, close=False):
        log.info("Shutting down.")
        
        # log.debug("Stopping worker thread pool.")
        # self.worker.stop()
        
        if self.io is not None:
            log.debug("Executing shutdown callbacks.")
            
            # self.io.remove_handler(self.socket.fileno())
            self.protocol.stop()
            self.io.stop()
            
            for callback in self.callbacks['stop']:
                callback(self)
        
        elif close:
            self.socket.close()
        
        # self.wake.close()
        # self.wake = None
        
        log.info("Stopped.")
    
    def _socket(self):
        """Create a listening socket.
        
        This handles IPv6 and allows socket re-use by spawned processes.
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
        # sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.setblocking(0)
        
        # If listening on the IPV6 any address ('::' = IN6ADDR_ANY), activate dual-stack.
        if family == socket.AF_INET6 and addr[0] in ('::', '::0', '::0.0.0.0'):
            try:
                sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
            
            except (AttributeError, socket.error):
                pass
        
        return sock
