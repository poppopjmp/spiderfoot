from .db import SpiderFootDb
from .event import SpiderFootEvent
from .threadpool import SpiderFootThreadPool
from .plugin import SpiderFootPlugin
from .target import SpiderFootTarget
from .helpers import SpiderFootHelpers
from .correlation import SpiderFootCorrelator
from spiderfoot.__version__ import __version__

class SpiderFootPlugin():
    # Will be set to True by the controller if the user aborts the scan
    # Plugins should check this variable during loops to exit if requested.
    _stopScanning = False
    # Modules that will be notified when this module produces events
    _listenerModules = list()
    # Current event being processed
    _currentEvent = None
    # Target currently being acted against
    _currentTarget = None
    # Debug
    _debug = False
    # Database handle
    __sfdb__ = None
    # Configuration
    __sfconfig__ = None
    # Cache
    __sfcache__ = None
    # Result set
    _resdata = dict()

    # Not really needed in most cases.
    # def __init__(self):
    #    pass

    # Prevent some information from being logged, just to prevent noise
    _debugUnlistedEvents = list(["WEBSERVER_TECHNOLOGY", "URL_JAVASCRIPT_FRAMEWORK",
                                 "HTTP_CODE"])

    # Will be set to True by the controller if the user aborts the scan
    # Plugins should check this variable during loops to exit if requested
    def checkForStop(self):
        """Check whether the user requested to stop the scan."""
        return self._stopScanning

    # Common functions for dynamic event type generation
    def _genSourceEvent(self, original_event, _type):
        if not original_event:
            return None

        if isinstance(original_event, SpiderFootEvent):
            e = SpiderFootEvent(_type, original_event.data, self.__name__, original_event)
            self._listenerModules.append(e)
            self._currentEvent = e
            return e
        return None

    def _genWebformEvent(self, original_event):
        return self._genSourceEvent(original_event, 'WEBFORM_SUBMITTED')

    def _genAuth0Event(self, original_event):
        return self._genSourceEvent(original_event, 'AUTH0_DETECTED')

    def _genPaypalAppEvent(self, original_event):
        return self._genSourceEvent(original_event, 'PAYPAL_APP_DETECTED')

    def _genAwsS3BucketEvent(self, original_event):
        return self._genSourceEvent(original_event, 'AWS_S3_BUCKET_DETECTED')

    def _genOktaLoginEvent(self, original_event):
        return self._genSourceEvent(original_event, 'OKTA_LOGIN_FORM_DETECTED')

    def _genExtraFileMetadataEvent(self, original_event):
        return self._genSourceEvent(original_event, 'EXTRA_FILE_METADATA')

    def _genGoogleTagManagerIdEvent(self, original_event):
        return self._genSourceEvent(original_event, 'GOOGLE_TAGMANAGER_ID')

    def _genGoogleAnalyticsIdEvent(self, original_event):
        return self._genSourceEvent(original_event, 'GOOGLE_ANALYTICS_ID')

    def _genGoogleRecaptchaEvent(self, original_event):
        return self._genSourceEvent(original_event, 'GOOGLE_RECAPTCHA_DETECTED')

    def debugEvent(self, event):
        """Debug received events in a consistent format across all modules.
        
        Args:
            event: SpiderFoot event
        """
        if event.eventType not in self._debugUnlistedEvents:
            self.debug(f"Received event, {event.eventType}, from {event.module}")

    def processEvent(self, event):
        """Override this method to implement the module's event processing logic.
        
        This method should be implemented by modules instead of handleEvent.
        It will be called after standard checks like errorState, duplicate events, etc.
        
        Args:
            event (SpiderFootEvent): Event to process
            
        Returns:
            None
        """
        return None
        
    def handleEvent(self, event):
        """Default implementation for handling events that performs standard checks.
        
        Modules should generally not override this method and instead implement
        the processEvent method. This ensures consistent behavior across modules.
        
        Args:
            event (SpiderFootEvent): Event to process
            
        Returns:
            None
        """
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data

        # Log receiving the event
        self.debug(f"Received event, {eventName}, from {srcModuleName}")
        
        # Check if we're in an error state
        if hasattr(self, "errorState") and self.errorState:
            return
            
        # Check if we've already processed this event data
        if hasattr(self, "results") and eventData in self.results:
            self.debug(f"Skipping {eventData}, already checked.")
            return
            
        # Store the event data as processed if we have a results attribute
        if hasattr(self, "results"):
            self.results[eventData] = True
            
        # Check if the module is watching this event type
        watchedEvents = self.watchedEvents()
        if watchedEvents != ["*"] and eventName not in watchedEvents:
            return
            
        # Call the module's custom processing logic
        self.processEvent(event)
