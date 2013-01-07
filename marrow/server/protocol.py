# encoding: utf-8

__all__ = ['Protocol']
log = __import__('logging').getLogger(__name__)



class Protocol(object):
    def __init__(self, server, testing=False, **options):
        super(Protocol, self).__init__()
        
        self.server = server
        self.testing = testing
        self.options = options
    
    def start(self):
        pass
    
    def stop(self):
        pass
    
    def accept(self, stream):
        pass
