# encoding: utf-8

"""A higher-level socket server API.

Uses Protocols to implement common callbacks without restricting advanced capabilities.

Additionally, provides prefork and worker thread pool capabilities.
"""

import os
import socket
import time
import random

from inspect import isclass
from binascii import hexlify

try:
    import fcntl
except ImportError:
    if os.name == 'nt':
        from marrow.io import win32_support as fcntl
    else:
        raise

try:
    from concurrent import futures
except ImportError:
    futures = None

try:
    from tornado import ioloop, iostream
except ImportError:
    from marrow.io import ioloop, iostream


__all__ = ['Server']
log = __import__('logging').getLogger(__name__)



class Server(object):
    """A basic multi-process and/or multi-threaded socket server.
    
    The protocol class attriubte should be overridden in subclasses or instances to provide actual functionality.
    """
    
    protocol = None
    callbacks = {'start': [], 'stop': []}
    
    def __init__(self, host=None, port=None, protocol=None, pool=128, fork=1, threaded=False, **options):
        """Accept the minimal server configuration.
        
        If port is omitted, the host is assumed to be an on-disk UNIX domain socket file.
        
        The protocol is instantiated here, if it is a class, and passed a reference to the server and any additional arguments.
        
        If fork is None or less than 1, automatically detect the number of logical processors (i.e. cores) and fork that many copies.
        
        If threaded is False, no threading is used.  If set to None, an unlimited number of threads is used (careful with that!), otherwise, if an integer, no more than that number of threads will be utilized.
        
        Do not utilze forking when you need to debug or automatically reload your code in development.
        """
        
        super(Server, self).__init__()
        
        self.socket = None
        self.io_loop = None
        self.name = socket.gethostname()
        
        self.address = (host if host is not None else '', port)
        if protocol: self.protocol = protocol
        self.pool = pool
        self.fork = fork
        self.threaded = threaded
        self.options = options
        
        if threaded is not False and futures is None:
            raise NotImplementedError("You need to install the `futures` package to utilize threading.")
    
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
    
    def serve(self, master=True, io_loop=None):
        self.io_loop = io_loop or ioloop.IOLoop.instance()
        
        if isclass(self.protocol):
            self.protocol = self.protocol(self, io_loop, **self.options)
        
        if self.threaded is not False:
            log.debug("Initializing the thread pool.")
            self.executor = futures.ThreadPoolExecutor(max_workers=self.threaded)
        
        log.debug("Executing startup hooks.")
        
        self.protocol.start()
        
        for callback in self.callbacks['start']:
            callback(self)
        
        # Register for new connection notifications.
        self.io_loop.add_handler(
                self.socket.fileno(),
                self._accept,
                self.io_loop.READ
            )
        
        log.info("Server running with PID %d, serving on %s.", os.getpid(), ("%s:%d" % (self.address[0] if self.address[0] else '*', self.address[1])) if isinstance(self.address, tuple) else self.address)
        
        if io_loop: return
        
        try:
            self.io_loop.start()
        except KeyboardInterrupt:
            log.info("Received Control+C.")
        except SystemExit:
            log.info("Received SystemExit.")
            raise
        except:
            log.exception("Unknown server error.")
            raise
        finally:
            if master: self.stop(master)
            else: self.io_loop.remove_handler(self.socket.fileno())
    
    def start(self, io_loop=None):
        """Primary reactor loop.
        
        This handles standard signals as interpreted by Python, such as Ctrl+C.
        """
        
        log.info("Starting up.")
        
        socket = self.socket = self._socket()
        socket.bind(self.address)
        socket.listen(self.pool)
        
        if self.fork is None:
            self.fork = self.processors()
        elif self.fork < 1:
            self.fork = min(1, self.processors() + self.fork)
        
        # Single-process operation.
        if self.fork == 1:
            self.serve(io_loop=io_loop)
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
            log.info("Received Control+C.")
        except SystemExit:
            log.info("Received SystemExit.")
            raise
        except:
            log.exception("Unknown server error.")
            raise
        
        self.stop()
        
        return
    
    def stop(self, close=False, io_loop=None):
        log.info("Shutting down.")
        
        if self.threaded is not False:
            log.debug("Stopping worker thread pool; waiting for threads.")
            self.executor.shutdown()
        
        if self.io_loop is not None:
            log.debug("Executing shutdown callbacks.")
            
            # self.io_loop.remove_handler(self.socket.fileno())
            self.protocol.stop()
            if not io_loop: self.io_loop.stop()
            
            for callback in self.callbacks['stop']:
                callback(self)
        elif close:
            self.socket.close()
        
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
        
        flags = fcntl.fcntl(sock.fileno(), fcntl.F_GETFD)
        flags |= fcntl.FD_CLOEXEC
        fcntl.fcntl(sock.fileno(), fcntl.F_SETFD, flags)
        
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        
        sock.setblocking(0)
        
        # If listening on the IPV6 any address ('::' = IN6ADDR_ANY), activate dual-stack.
        if family == socket.AF_INET6 and addr[0] in ('::', '::0', '::0.0.0.0'):
            try:
                sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
            except (AttributeError, socket.error):
                pass
        
        return sock

    def _accept(self, fd, events):
        connection, address = self.socket.accept()
        stream = iostream.IOStream(connection, io_loop=self.io_loop)
        self.protocol.accept(stream)
