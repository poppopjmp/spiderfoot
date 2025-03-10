from .db import SpiderFootDb
from .event import SpiderFootEvent
from .helpers import SpiderFootHelpers
from .logger import logListenerSetup, logWorkerSetup
from .plugin import SpiderFootPlugin
from .target import SpiderFootTarget
from .threadpool import SpiderFootThreadPool
from .correlation import SpiderFootCorrelator

class SpiderFootStaticJS:
    """
    SpiderFoot static JavaScript class to handle JS dependencies
    """
    
    def __init__(self):
        self.js_resources = {}
    
    def add_resource(self, name, content):
        """
        Add a JavaScript resource
        """
        self.js_resources[name] = content
        
    def get_resource(self, name):
        """
        Get a JavaScript resource by name
        """
        if name in self.js_resources:
            return self.js_resources[name]
        return None

__all__ = [
    'SpiderFootDb',
    'SpiderFootEvent',
    'SpiderFootHelpers',
    'SpiderFootPlugin',
    'SpiderFootTarget',
    'logListenerSetup',
    'logWorkerSetup',
    'SpiderFootThreadPool',
    'SpiderFootCorrelator'
]
