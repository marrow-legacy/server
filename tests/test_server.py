# encoding: utf-8

from __future__ import unicode_literals

import time
import socket

from unittest import TestCase
from functools import partial

from marrow.io.iostream import IOStream
from marrow.server.base import Server
from marrow.server.testing import ServerTestCase
from marrow.server.protocol import Protocol


log = __import__('logging').getLogger(__name__)



class SimpleProtocol(Protocol):
    def accept(self, client):
        log.info("Accepted connection from %r.", client.address)
        client.write(b"Welcome.\n", client.close)


class TestProtocol(ServerTestCase):
    protocol = SimpleProtocol
    
    def test_serving(self):
        self.client.read_until(b"\n", self.stop)
        self.assertEquals(self.wait(), b"Welcome.\n")

