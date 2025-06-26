from spiderfoot import SpiderFootPlugin

class sfp_example(SpiderFootPlugin):
    meta = {
        'name': 'sfp_example',
        'title': 'Example',
        'summary': 'Example module for testing',
        'flags': [],
        'categories': ['test'],
        'labels': ['test'],
        'targetType': 'INTERNET_NAME',
    }
    def __init__(self):
        super().__init__()
        self.opts = {'example_option': 'default_value'}
        self.optdescs = {'example_option': 'Example option description'}
        self.errorState = False
    def watchedEvents(self):
        return ['ROOT']
    def enrichTarget(self, target):
        return None
    def setup(self, sf, opts):
        pass
    def clearListeners(self):
        pass
    def setScanId(self, scan_id):
        pass
    def setSharedThreadPool(self, pool):
        pass
    def setDbh(self, dbh):
        pass
    def setTarget(self, target):
        pass
