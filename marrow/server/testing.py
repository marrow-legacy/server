# encoding: utf-8

"""Unit testing helpers for asynchronous marrow.io IOLoop and IOStream.

This is a barely-modified version of the unit testing rig from Tornado.
"""

import os
import sys
import time
import socket
import unittest

from marrow.io.testing import AsyncTestCase
from marrow.io.iostream import IOStream
from marrow.server.base import Server


_next_port = 10000
log = __import__('logging').getLogger(__name__)
__all__ = ['ServerTestCase']



def get_unused_port():
    global _next_port
    port = _next_port
    _next_port = _next_port + 1
    return port


class ServerTestCase(AsyncTestCase):
    protocol = None
    arguments = dict()
    
    def __init__(self, *args, **kwargs):
        super(ServerTestCase, self).__init__(*args, **kwargs)
        self.server = None
        self.port = None
        self.client = None
    
    def setUp(self):
        super(ServerTestCase, self).setUp()
        
        self.port = get_unused_port()
        self.server = Server('127.0.0.1', self.port, self.protocol, **self.arguments)
        self.server.start(testing=self.io_loop)
        
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        s.connect(("127.0.0.1", self.port))
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        s.setblocking(0)
        
        self.client = IOStream(s, self.io_loop)
    
    def tearDown(self):
        super(ServerTestCase, self).tearDown()
        self.client = None
        self.port = None
        self.server = None
