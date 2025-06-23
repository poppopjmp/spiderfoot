# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         plugin
# Purpose:      Base class for SpiderFoot modules/plugins
#
# Author:      Steve Micallef <steve@binarypool.com>
#
# Created:     26/03/2012
# Copyright:   (c) Steve Micallef 2012
# Licence:     MIT
# -------------------------------------------------------------------------------

from contextlib import suppress
import io
import logging
import os
import queue
import sys
import threading
from time import sleep
import traceback
from typing import List, Dict, Any, Optional

from spiderfoot import SpiderFootEvent, SpiderFootHelpers
from .threadpool import SpiderFootThreadPool

# begin logging overrides
# these are copied from the python logging module
# https://github.com/python/cpython/blob/main/Lib/logging/__init__.py

if hasattr(sys, 'frozen'):  # support for py2exe
    _srcfile = f"logging{os.sep}__init__{__file__[-4:]}"
elif __file__[-4:].lower() in ['.pyc', '.pyo']:
    _srcfile = __file__[:-4] + '.py'
else:
    _srcfile = __file__
_srcfile = os.path.normcase(_srcfile)


class SpiderFootPluginLogger(logging.Logger):
    """Used only in SpiderFootPlugin to prevent modules from having to
    initialize their own loggers.

    Preserves filename, module, line numbers, etc. from the caller.
    """

    def findCaller(self, stack_info: bool = False, stacklevel: int = 1) -> tuple:
        """Find the stack frame of the caller so that we can note the source
        file name, line number and function name.

        Args:
            stack_info (bool): TBD
            stacklevel (int): TBD

        Returns:
            tuple: filename, line number, module name, and stack trace
        """
        f = logging.currentframe()
        # On some versions of IronPython, currentframe() returns None if
        # IronPython isn't run with -X:Frames.
        if f is not None:
            f = f.f_back
        orig_f = f
        while f and stacklevel > 1:
            f = f.f_back
            stacklevel -= 1
        if not f:
            f = orig_f
        rv = "(unknown file)", 0, "(unknown function)", None
        while hasattr(f, "f_code"):
            co = f.f_code
            filename = os.path.normcase(co.co_filename)
            if filename in (logging._srcfile, _srcfile):  # This is the only change
                f = f.f_back
                continue
            sinfo = None
            if stack_info:
                sio = io.StringIO()
                sio.write('Stack (most recent call last):\n')
                traceback.print_stack(f, file=sio)
                sinfo = sio.getvalue()
                if sinfo[-1] == '\n':
                    sinfo = sinfo[:-1]
                sio.close()
            rv = (co.co_filename, f.f_lineno, co.co_name, sinfo)
            break
        return rv  # noqa R504

# end of logging overrides


class SpiderFootPlugin:
    """Base class for SpiderFoot modules/plugins.
    
    All SpiderFoot modules should inherit from this class and implement
    the required methods.
    """
    
    # Module metadata
    _name = "module_template"
    _description = "Base SpiderFoot Plugin"
    _flags = []
    _useragent = None
    _priority = 3
    
    # Module state
    errorState = False
    incomingEventQueue = None
    outgoingEventQueue = None
      # Threading
    _stopScanning = False
    _currentEvent = None
    _currentTarget = None
    _scanId = None
    _sharedThreadPool = None
    _thread = None
    running = False
    maxThreads = 10  # Default maximum threads for this module
    
    # Database and listeners
    _dbh = None
    _listeners = []
    
    def __init__(self):
        """Initialize the plugin."""
        self._listeners = []
        self.errorState = False
        self._stopScanning = False
        self.__outputFilter__ = None
        self._log = None
        self.__scanId__ = None
        # self.running = False  # Removed: conflicts with running property
        
    def setup(self, sf, userOpts=dict()):
        """Setup the module with configuration.
        
        Args:
            sf: SpiderFoot object
            userOpts: User configuration options
        """
        self.sf = sf
        self.opts = userOpts
        
    def enrichTarget(self, target):
        """Enrich the target with additional information.
        
        Args:
            target: Target to enrich
            
        Returns:
            Enriched target or None
        """
        return None
        
    def setTarget(self, target):
        """Set the target for this module.
        
        Args:
            target: Target object
        """
        self._currentTarget = target
        
    def setScanId(self, scanId: str):
        """Set the scan ID.
        
        Args:
            scanId: Scan instance ID
        """
        self._scanId = scanId
        
    def setDbh(self, dbh):
        """Set the database handle.
        
        Args:
            dbh: Database handle
        """
        self._dbh = dbh
        
    def setSharedThreadPool(self, pool):
        """Set the shared thread pool.
        
        Args:
            pool: Thread pool object
        """
        self._sharedThreadPool = pool
        
    def clearListeners(self):
        """Clear all listeners."""
        self._listeners = []
        
    def registerListener(self, listener):
        """Register an event listener.
        
        Args:
            listener: Listener to register
        """
        self._listeners.append(listener)
        
    def notifyListeners(self, sfEvent):
        """Notify all listeners of an event.
        
        Args:
            sfEvent: SpiderFootEvent to send
        """
        if self.outgoingEventQueue:
            self.outgoingEventQueue.put(sfEvent)
            
    def watchedEvents(self) -> List[str]:
        """Return list of events this module watches for.
        
        Returns:
            List of event types
        """
        return []
        
    def producedEvents(self) -> List[str]:
        """Return list of events this module produces.
        
        Returns:
            List of event types
        """
        return []
        
    def handleEvent(self, sfEvent):
        """Handle an incoming event.
        
        Args:
            sfEvent: SpiderFootEvent to handle
        """
        pass
        
    def start(self):
        """Start the module thread."""
        if self.running:
            return
            
        self.running = True
        self._thread = threading.Thread(target=self._run)
        self._thread.daemon = True
        self._thread.start()
        
    def _run(self):
        """Main module execution loop."""
        try:
            while not self._stopScanning and self.incomingEventQueue:
                try:
                    sfEvent = self.incomingEventQueue.get(timeout=1)
                    if sfEvent == 'FINISHED':
                        self.finished()
                        break
                    if isinstance(sfEvent, SpiderFootEvent):
                        self._currentEvent = sfEvent
                        self.handleEvent(sfEvent)
                except queue.Empty:
                    continue
                except Exception as e:
                    self.sf.error(f"Error in module {self._name}: {e}")
                    self.errorState = True
                    break
        finally:
            self.running = False
            
    def finished(self):
        """Called when the module should finish processing."""
        pass
        
    def sendEvent(self, eventType: str, eventData: str, parentEvent=None, confidenceLevel: int = 100):
        """Send an event.
        
        Args:
            eventType: Type of event
            eventData: Event data
            parentEvent: Parent event
            confidenceLevel: Confidence level (0-100)
        """
        if not parentEvent:
            parentEvent = self._currentEvent
            
        if parentEvent:
            evt = SpiderFootEvent(eventType, eventData, self._name, parentEvent)
            self.notifyListeners(evt)

    @property
    def log(self):
        if self._log is None:
            # temporarily set logger class
            logging.setLoggerClass(SpiderFootPluginLogger)
            # init SpiderFootPluginLogger
            self._log = logging.getLogger(f"spiderfoot.{getattr(self, '__name__', self.__class__.__name__)}")
            # reset logger class to default
            logging.setLoggerClass(logging.Logger)
        return self._log

    def _updateSocket(self, socksProxy: str) -> None:
        """Hack to override module's use of socket, replacing it with one that
        uses the supplied SOCKS server.

        Args:
            socksProxy (str): SOCKS proxy
        """
        self.socksProxy = socksProxy

    def clearListeners(self) -> None:
        """Used to clear any listener relationships, etc.

        This is needed because Python seems to cache local variables
        even between threads.
        """

        self._listenerModules = list()
        self._stopScanning = False

    def setup(self, sf, userOpts: dict = {}) -> None:
        """Will always be overriden by the implementer.

        Args:
            sf (SpiderFoot): SpiderFoot object
            userOpts (dict): TBD
        """
        pass

    def debug(self, *args, **kwargs) -> None:
        """For logging. A wrapper around logging.debug() that adds the scanId
        to LogRecord.

        Args:
            *args: passed through to logging.debug()
            *kwargs: passed through to logging.debug()
        """
        self.log.debug(*args, extra={'scanId': self.__scanId__}, **kwargs)

    def info(self, *args, **kwargs) -> None:
        """For logging. A wrapper around logging.info() that adds the scanId to
        LogRecord.

        Args:
            *args: passed through to logging.info()
            *kwargs: passed through to logging.info()
        """
        self.log.info(*args, extra={'scanId': self.__scanId__}, **kwargs)

    def error(self, *args, **kwargs) -> None:
        """For logging. A wrapper around logging.error() that adds the scanId
        to LogRecord.

        Args:
            *args: passed through to logging.error()
            *kwargs: passed through to logging.error()
        """
        extra = kwargs.pop('extra', {})
        extra = {**extra, 'scanId': self.__scanId__}
        self.log.error(*args, extra=extra, **kwargs)

    def enrichTarget(self, target: str) -> None:
        """Find aliases for a target.

        Note: rarely used in special cases

        Args:
            target (str): TBD
        """
        pass

    def setTarget(self, target) -> None:
        """Assigns the current target this module is acting against.

        Args:
            target (SpiderFootTarget): target

        Raises:
            TypeError: target argument was invalid type
        """
        from spiderfoot import SpiderFootTarget

        if not isinstance(target, SpiderFootTarget):
            raise TypeError(
                f"target is {type(target)}; expected SpiderFootTarget")

        self._currentTarget = target

    def setDbh(self, dbh) -> None:
        """Used to set the database handle, which is only to be used by modules
        in very rare/exceptional cases (e.g. sfp__stor_db)

        Args:
            dbh (SpiderFootDb): database handle
        """
        self.__sfdb__ = dbh

    def setScanId(self, scanId: str) -> None:
        """Set the scan ID.

        Args:
            scanId (str): scan instance ID

        Raises:
            TypeError: scanId argument was invalid type
        """
        if not isinstance(scanId, str):
            raise TypeError(f"scanId is {type(scanId)}; expected str")

        self.__scanId__ = scanId

    def getScanId(self) -> str:
        """Get the scan ID.

        Returns:
            str: scan ID

        Raises:
            TypeError: Module called getScanId() but no scanId is set.
        """
        if not self.__scanId__:
            raise TypeError("Module called getScanId() but no scanId is set.")

        return self.__scanId__

    def getTarget(self) -> str:
        """Gets the current target this module is acting against.

        Returns:
            str: current target

        Raises:
            TypeError: Module called getTarget() but no target is set.
        """
        if not self._currentTarget:
            raise TypeError("Module called getTarget() but no target is set.")

        return self._currentTarget

    def registerListener(self, listener) -> None:
        """Listener modules which will get notified once we have data for them
        to work with.

        Args:
            listener: TBD
        """

        self._listenerModules.append(listener)

    def setOutputFilter(self, types) -> None:
        self.__outputFilter__ = types

    def tempStorage(self) -> dict:
        """For future use. Module temporary storage.

        A dictionary used to persist state (in memory) for a module.

        Todo:
            Move all module state to use this, which then would enable a scan to be paused/resumed.


        Returns:
            dict: module temporary state data
        """
        return dict()

    def notifyListeners(self, sfEvent) -> None:
        """Call the handleEvent() method of every other plug-in listening for
        events from this plug-in. Remember that those plug-ins will be called
        within the same execution context of this thread, not on their own.

        Args:
            sfEvent (SpiderFootEvent): event

        Raises:
            TypeError: sfEvent argument was invalid type
        """

        from spiderfoot import SpiderFootEvent

        if not isinstance(sfEvent, SpiderFootEvent):
            raise TypeError(
                f"sfEvent is {type(sfEvent)}; expected SpiderFootEvent")

        eventName = sfEvent.eventType
        eventData = sfEvent.data

        # Be strict about what events to pass on, unless they are
        # the ROOT event or the event type of the target.
        if self.__outputFilter__ and eventName not in ['ROOT', self.getTarget().targetType, self.__outputFilter__]:
            return

        storeOnly = False  # Under some conditions, only store and don't notify

        if not eventData:
            return

        if self.checkForStop():
            return

        # Look back to ensure the original notification for an element
        # is what's linked to children. For instance, sfp_dns may find
        # xyz.abc.com, and then sfp_ripe obtains some raw data for the
        # same, and then sfp_dns finds xyz.abc.com in there, we should
        # suppress the notification of that to other modules, as the
        # original xyz.abc.com notification from sfp_dns will trigger
        # those modules anyway. This also avoids messy iterations that
        # traverse many many levels.

        # storeOnly is used in this case so that the source to dest
        # relationship is made, but no further events are triggered
        # from dest, as we are already operating on dest's original
        # notification from one of the upstream events.

        prevEvent = sfEvent.sourceEvent
        while prevEvent is not None:
            if prevEvent.sourceEvent is not None and prevEvent.sourceEvent.eventType == sfEvent.eventType and prevEvent.sourceEvent.data.lower() == eventData.lower():
                storeOnly = True
                break
            prevEvent = prevEvent.sourceEvent

        # output to queue if applicable
        if self.outgoingEventQueue is not None:
            self.outgoingEventQueue.put(sfEvent)
        # otherwise, call other modules directly
        else:
            self._listenerModules.sort(key=lambda m: m._priority)

            for listener in self._listenerModules:
                if eventName not in listener.watchedEvents() and '*' not in listener.watchedEvents():
                    continue

                if storeOnly and "__stor" not in listener.__module__:
                    continue

                listener._currentEvent = sfEvent

                # Check if we've been asked to stop in the meantime, so that
                # notifications stop triggering module activity.
                if self.checkForStop():
                    return

                try:
                    listener.handleEvent(sfEvent)
                except Exception as e:
                    self.sf.error(
                        f"Module ({listener.__module__}) encountered an error: {e}")
                    # set errorState
                    self.errorState = True
                    # clear incoming queue
                    if self.incomingEventQueue:
                        with suppress(queue.Empty):
                            while 1:
                                self.incomingEventQueue.get_nowait()

    def checkForStop(self) -> bool:
        """For modules to use to check for when they should give back control.

        Returns:
            bool: True if scan should stop
        """
        # Stop if module is in error state.
        if self.errorState:
            return True

        # If threading is enabled, check the _stopScanning attribute instead.
        # This is to prevent each thread needing its own sqlite db handle.
        if self.outgoingEventQueue is not None and self.incomingEventQueue is not None:
            return self._stopScanning

        if not self.__scanId__:
            return False

        scanstatus = self.__sfdb__.scanInstanceGet(self.__scanId__)

        if not scanstatus:
            return False

        if scanstatus[5] == "ABORT-REQUESTED":
            self._stopScanning = True
            return True

        return False

    @property
    def running(self) -> bool:
        """Indicates whether the module is currently processing data. Modules
        that process data in pools/batches typically override this method.

        Returns:
            bool: True if the module is currently processing data.
        """
        return self.sharedThreadPool.countQueuedTasks(f"{getattr(self, '__name__', self.__class__.__name__)}_threadWorker") > 0

    def watchedEvents(self) -> list:
        """What events is this module interested in for input. The format is a
        list.

        of event types that are applied to event types that this module wants to
        be notified of, or * if it wants everything.
        Will usually be overriden by the implementer, unless it is interested
        in all events (default behavior).

        Returns:
            list: list of events this modules watches
        """

        return ['*']

    def producedEvents(self) -> list:
        """What events this module produces This is to support the end user in
        selecting modules based on events produced.

        Returns:
            list: list of events produced by this module
        """

        return []

    def handleEvent(self, sfEvent) -> None:
        """Handle events to this module. Will usually be overriden by the
        implementer, unless it doesn't handle any events.

        Args:
            sfEvent (SpiderFootEvent): event
        """

        return

    def asdict(self) -> dict:
        return {
            'name': self.meta.get('name'),
            'descr': self.meta.get('summary'),
            'cats': self.meta.get('categories', []),
            'group': self.meta.get('useCases', []),
            'labels': self.meta.get('flags', []),
            'provides': self.producedEvents(),
            'consumes': self.watchedEvents(),
            'meta': self.meta,
            'opts': self.opts,
            'optdescs': self.optdescs,
        }

    def start(self) -> None:
        """Start the module thread, no actual use."""
        # Check if queues are set up before starting thread
        if not (self.incomingEventQueue and self.outgoingEventQueue):
            # Use self._log if sf is not available
            error_msg = f"Module {getattr(self, '__name__', 'unknown')} cannot start: queues not initialized (incoming={self.incomingEventQueue is not None}, outgoing={self.outgoingEventQueue is not None})"
            if hasattr(self, 'sf') and self.sf:
                self.sf.error(error_msg)
            elif hasattr(self, '_log') and self._log:
                self._log.error(error_msg)
            else:
                print(f"ERROR: {error_msg}")
            return
            
        if hasattr(self, 'sf') and self.sf:
            self.sf.debug(f"Starting module {getattr(self, '__name__', 'unknown')} thread")
        
        # Replace the undefined 'thread' with a proper thread creation
        import threading
        thread = threading.Thread(target=self.threadWorker)
        thread.daemon = True
        self.thread = thread
        self.thread.start()

    def finish(self):
        """Perform final/cleanup functions before module exits Note that this
        function may be called multiple times Overridden by the implementer."""

        return

    def threadWorker(self) -> None:
        try:
            # create new database handle since we're in our own thread
            from spiderfoot import SpiderFootDb
            self.setDbh(SpiderFootDb(self.opts))
            self.sf._dbh = self.__sfdb__

            if not (self.incomingEventQueue and self.outgoingEventQueue):
                self.sf.error(
                    "Please set up queues before starting module as thread")
                return

            while not self.checkForStop():
                try:
                    sfEvent = self.incomingEventQueue.get_nowait()
                except queue.Empty:
                    sleep(.3)
                    continue
                if sfEvent == 'FINISHED':
                    self.sf.debug(
                        f"{getattr(self, '__name__', self.__class__.__name__)}.threadWorker() got \"FINISHED\" from incomingEventQueue.")
                    self.poolExecute(self.finish)
                else:
                    self.sf.debug(
                        f"{getattr(self, '__name__', self.__class__.__name__)}.threadWorker() got event, {sfEvent.eventType}, from incomingEventQueue.")
                    self.poolExecute(self.handleEvent, sfEvent)
        except KeyboardInterrupt:
            self.sf.debug(f"Interrupted module {getattr(self, '__name__', self.__class__.__name__)}.")
            self._stopScanning = True
        except Exception as e:
            import traceback
            self.sf.error(f"Exception ({e.__class__.__name__}) in module {getattr(self, '__name__', self.__class__.__name__)}." +
                          traceback.format_exc())
            # set errorState
            self.sf.debug(f"Setting errorState for module {getattr(self, '__name__', self.__class__.__name__)}.")
            self.errorState = True
            # clear incoming queue
            if self.incomingEventQueue:
                self.sf.debug(
                    f"Emptying incomingEventQueue for module {getattr(self, '__name__', self.__class__.__name__)}.")
                with suppress(queue.Empty):
                    while 1:
                        self.incomingEventQueue.get_nowait()
                # set queue to None to prevent its use
                # if there are leftover objects in the queue, the scan will hang.
                self.incomingEventQueue = None

    def poolExecute(self, callback, *args, **kwargs) -> None:
        """Execute a callback with the given args. If we're in a storage
        module, execute normally. Otherwise, use the shared thread pool.

        Args:
            callback: function to call
            args: args (passed through to callback)
            kwargs: kwargs (passed through to callback)
        """
        if getattr(self, '__name__', self.__class__.__name__).startswith('sfp__stor_'):
            callback(*args, **kwargs)
        else:
            self.sharedThreadPool.submit(
                callback, *args, taskName=f"{getattr(self, '__name__', self.__class__.__name__)}_threadWorker", maxThreads=self.maxThreads, **kwargs)

    def threadPool(self, *args, **kwargs):
        return SpiderFootThreadPool(*args, **kwargs)

    def setSharedThreadPool(self, sharedThreadPool) -> None:
        self.sharedThreadPool = sharedThreadPool

# end of SpiderFootPlugin class
