from __future__ import annotations

"""SpiderFoot plug-in module: example."""

from spiderfoot.modern_plugin import SpiderFootModernPlugin

class sfp_example(SpiderFootModernPlugin):
    """Example SpiderFoot plugin."""
    meta = {
        'name': 'sfp_example',
        'title': 'Example',
        'summary': 'Example module for testing',
        'flags': [],
        'categories': ['test'],
        'labels': ['test'],
        'targetType': 'INTERNET_NAME',
    }
    def __init__(self) -> None:
        """Initialize the sfp example."""
        super().__init__()
        self.opts = {'example_option': 'default_value'}
        self.optdescs = {'example_option': 'Example option description'}
        self.errorState = False
    def watchedEvents(self):
        """Return the list of events this module watches."""
        return ['ROOT']
    def enrichTarget(self, target):
        """Enrich the target with additional data."""
        return None
    def setup(self, sf, opts):
        """Set up the module."""
        pass
    def clearListeners(self):
        """ClearListeners."""
        pass
    def setScanId(self, scan_id):
        """Set ScanId."""
        pass
    def setSharedThreadPool(self, pool):
        """Set SharedThreadPool."""
        pass
    def setDbh(self, dbh):
        """Set Dbh."""
        pass
    def setTarget(self, target):
        """Set Target."""
        pass
