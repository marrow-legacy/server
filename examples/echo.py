# encoding: utf-8

import logging

from functools import partial

from marrow.server.base import Server
from marrow.server.protocol import Protocol


log = logging.getLogger(__name__)



class EchoProtocol(Protocol):
    def accept(self, client):
        log.info(b"Accepted connection from %r.", client.address)
        
        client.write(b"Hello!  Type something and press enter.  Type /quit to quit.\n")
        client.read_until(b"\r\n", partial(self.on_line, client))
    
    def on_line(self, client, data):
        if data[:-2] == b"/quit":
            client.write(b"Goodbye!\r\n", client.close)
            return
        
        client.write(data)
        client.read_until(b"\r\n", partial(self.on_line, client))



if __name__ == '__main__':
    import logging
    
    logging.basicConfig(level=logging.INFO)
    
    # For multi-process add "fork=" and a non-zero value.
    # Zero or None auto-detect the logical processors.
    Server(None, 8000, EchoProtocol).start()
