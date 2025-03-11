from contextlib import suppress
import io
import logging
import os
import queue
import sys
import threading
from time import sleep
import traceback
import inspect
from typing import Any, Dict, Optional

from .threadpool import SpiderFootThreadPool
from spiderfoot import SpiderFootDb, SpiderFootEvent

# begin logging overrides
# these are copied from the python logging module
# https://github.com/python/cpython/blob/main/Lib/logging/__init__.py

if hasattr(sys, "frozen"):  # support for py2exe
    _srcfile = f"logging{os.sep}__init__{__file__[-4:]}"
elif __file__[-4:].lower() in [".pyc", ".pyo"]:
    _srcfile = __file__[:-4] + ".py"
else:
    _srcfile = __file__
_srcfile = os.path.normcase(_srcfile)


class SpiderFootPluginLogger(logging.Logger):
    """Logger class for SpiderFoot plugins.

    This class extends the standard Logger to provide additional context
    for plugin-specific logging, making debugging and monitoring easier.
    """

    def findCaller(self, stack_info=False, stacklevel=1):
        """Find the caller of the logging method.

        Overrides the standard findCaller to skip over this file when determining
        the calling file and line number, ensuring logs show the actual plugin
        code location rather than logger implementation details.

        Args:
            stack_info: If true, include stack information
            stacklevel: Number of frames to skip

        Returns:
            tuple: (filename, line number, function name, stack info)
        """
        f = logging.currentframe()
        if f is not None:
            f = f.f_back
        orig_f = f
        while f and stacklevel > 1:
            f = f.f_back
            stacklevel -= 1
        if f is not None:
            f = f.f_back
        rv = "(unknown file)", 0, "(unknown function)", None
        while hasattr(f, "f_code"):
            co = f.f_code
            filename = os.path.normcase(co.co_filename)
            if filename == _srcfile:
                f = f.f_back
                continue
            sinfo = None
            if stack_info:
                sio = io.StringIO()
                sio.write("Stack (most recent call last):\n")
                traceback.print_stack(f, file=sio)
                sinfo = sio.getvalue()
                if sinfo[-1] == "\n":
                    sinfo = sinfo[:-1]
                sio.close()
            rv = (co.co_filename, f.f_lineno, co.co_name, sinfo)
            break
        return rv

    def makeRecord(
        self,
        name,
        level,
        fn,
        lno,
        msg,
        args,
        exc_info,
        func=None,
        extra=None,
        sinfo=None,
    ):
        """Create a LogRecord with plugin-specific context.

        Args:
            name: Logger name
            level: Log level
            fn: Filename
            lno: Line number
            msg: Log message
            args: Message arguments
            exc_info: Exception information
            func: Function name
            extra: Extra information
            sinfo: Stack information

        Returns:
            LogRecord: Record with plugin context
        """
        rv = logging.LogRecord(name, level, fn, lno, msg,
                               args, exc_info, func, sinfo)
        if extra is not None:
            for key in extra:
                if (key in ["message", "asctime"]) or (key in rv.__dict__):
                    raise KeyError(f"Attempt to overwrite {key} in LogRecord")
                rv.__dict__[key] = extra[key]
        return rv


# end of logging overrides


class SpiderFootPlugin:
    """Base class for SpiderFoot plugins."""

    # Will be set by the controller
    __sfdb__: Optional[SpiderFootDb] = None
    __scanId__: Optional[str] = None
    __dataSource__: Optional[str] = None
    __outputFilter__: Optional[str] = None

    meta: Dict[str, Any] = {
        "name": "Plugin Base",
        "summary": "This is the base class that all SpiderFoot plugins inherit from.",
        "useCases": [],
        "categories": [],
        "flags": [],
    }

    opts: Dict[str, Any] = {}
    optdescs: Dict[str, str] = {}
    errorState = False

    def _log(self, level: int, message: str) -> None:
        """Log a message to the SpiderFoot log facility.

        Args:
            level: Logging level (logging.ERROR|WARNING|INFO|DEBUG)
            message: Message string to log
        """
        # Get the logger
        log = logging.getLogger("spiderfoot")

        # Get the calling function name (debug, info, error, etc.)
        frame = inspect.currentframe().f_back
        func_name = frame.f_code.co_name if frame else "unknown"

        # Get the module name for context
        extra = {
            "module": self.__class__.__name__,
            "scanId": self.__scanId__ if hasattr(self, "__scanId__") else None,
        }

        # Log with extra context that will be used by handlers
        log.log(level, message, extra=extra)

    def debug(self, message: str) -> None:
        """Log a debug message.

        Args:
            message: Message string to log
        """
        self._log(logging.DEBUG, message)

    def info(self, message: str) -> None:
        """Log an info message.

        Args:
            message: Message string to log
        """
        self._log(logging.INFO, message)

    def error(self, message: str) -> None:
        """Log an error message.

        Args:
            message: Message string to log
        """
        self._log(logging.ERROR, message)

    def log(self, message: str) -> None:
        """Log a message.

        Args:
            message: Message string to log
        """
        self._log(logging.INFO, message)

    def status(self, message: str) -> None:
        """Log a status message.

        Args:
            message: Message string to log
        """
        # Status messages are treated as INFO in the logging system
        self._log(logging.INFO, f"STATUS: {message}")

    # Will be set to True by the controller if the user aborts scanning
    _stopScanning = False
    # Modules that will be notified when this module produces events
    _listenerModules = list()
    # Current event being processed
    _currentEvent = None
    # Target currently being acted against
    _currentTarget = None
    # Name of this module, set at startup time
    __name__ = "module_name_not_set!"
    # Direct handle to the database - not to be directly used
    # by modules except the sfp__stor_db module.
    __sfdb__ = None
    # ID of the scan the module is running against
    __scanId__ = None
    # (only used in SpiderFoot HX) tracking of data sources
    __dataSource__ = None
    # If set, events not matching this list are dropped
    __outputFilter__ = None
    # Priority, smaller numbers should run first
    _priority = 1
    # Plugin meta information
    meta = None
    # Error state of the module
    errorState = False
    # SOCKS proxy
    socksProxy = None
    # Queue for incoming events
    incomingEventQueue = None
    # Queue for produced events
    outgoingEventQueue = None
    # SpiderFoot object, set in each module's setup() function
    sf = None
    # Configuration, set in each module's setup() function
    opts = dict()
    # Maximum threads
    maxThreads = 1

    def __init__(self) -> None:
        # Holds the thread object when module threading is enabled
        self.thread = None
        # logging overrides
        self._log = None
        # Shared thread pool for all modules
        self.sharedThreadPool = None
        self.log = logging.getLogger(__name__)  # Ensure logger is initialized

    @property
    def log(self):
        """Get a module-specific logger instance."""
        if not hasattr(self, "_log"):
            self._log = get_module_logger(self.__module__)
        return self._log

    # For backward compatibility
    def debug(self, message):
        """Log a debug message."""
        if self.log:
            self.log.debug(message)
        else:
            # Fallback for when log isn't initialized
            print(f"DEBUG: {message}")

    def info(self, message):
        """Log an info message."""
        self.log.info(message)

    def warning(self, message):
        """Log a warning message."""
        self.log.warning(message)

    def error(self, message):
        """Log an error message."""
        self.log.error(message)

    def _updateSocket(self, socksProxy: str) -> None:
        """Hack to override module's use of socket, replacing it with
        one that uses the supplied SOCKS server.

        Args:
            socksProxy (str): SOCKS proxy
        """
        self.socksProxy = socksProxy

    def clearListeners(self) -> None:
        """Used to clear any listener relationships, etc. This is needed because
        Python seems to cache local variables even between threads."""

        self._listenerModules = list()
        self._stopScanning = False

    def setup(self, sf, userOpts: dict = {}) -> None:
        """Will always be overriden by the implementer.

        Args:
            sf (SpiderFoot): SpiderFoot object
            userOpts (dict): TBD
        """
        pass

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
        """Used to set the database handle, which is only to be used
        by modules in very rare/exceptional cases (e.g. sfp__stor_db)

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
        """Listener modules which will get notified once we have data for them to
        work with.

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

        Note:
            Required for SpiderFoot HX compatibility of modules.

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

        if not isinstance(sfEvent, SpiderFootEvent):
            raise TypeError(
                f"sfEvent is {type(sfEvent)}; expected SpiderFootEvent")

        eventName = sfEvent.eventType
        eventData = sfEvent.data

        # Be strict about what events to pass on, unless they are
        # the ROOT event or the event type of the target.
        if self.__outputFilter__ and eventName not in [
            "ROOT",
            self.getTarget().targetType,
            self.__outputFilter__,
        ]:
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
            if (
                prevEvent.sourceEvent is not None and
                prevEvent.sourceEvent.eventType == sfEvent.eventType and
                prevEvent.sourceEvent.data.lower() == eventData.lower()
            ):
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
                if (
                    eventName not in listener.watchedEvents() and
                    "*" not in listener.watchedEvents()
                ):
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
                        f"Module ({listener.__module__}) encountered an error: {e}"
                    )
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
        """Indicates whether the module is currently processing data.
        Modules that process data in pools/batches typically override this method.

        Returns:
            bool: True if the module is currently processing data.
        """
        return (
            self.sharedThreadPool.countQueuedTasks(
                f"{self.__name__}_threadWorker") > 0
        )

    def watchedEvents(self) -> list:
        """What events is this module interested in for input. The format is a list
        of event types that are applied to event types that this module wants to
        be notified of, or * if it wants everything.
        Will usually be overriden by the implementer, unless it is interested
        in all events (default behavior).

        Returns:
            list: list of events this modules watches
        """

        return ["*"]

    def producedEvents(self) -> list:
        """What events this module produces
        This is to support the end user in selecting modules based on events
        produced.

        Returns:
            list: list of events produced by this module
        """

        return []

    def handleEvent(self, sfEvent) -> None:
        """Handle events to this module.
        Will usually be overriden by the implementer, unless it doesn't handle any events.

        Args:
            sfEvent (SpiderFootEvent): event
        """

        return

    def asdict(self) -> dict:
        return {
            "name": self.meta.get("name"),
            "descr": self.meta.get("summary"),
            "cats": self.meta.get("categories", []),
            "group": self.meta.get("useCases", []),
            "labels": self.meta.get("flags", []),
            "provides": self.producedEvents(),
            "consumes": self.watchedEvents(),
            "meta": self.meta,
            "opts": self.opts,
            "optdescs": self.optdescs,
        }

    def start(self) -> None:
        self.thread = threading.Thread(target=self.threadWorker, daemon=True)
        self.thread.start()

    def finish(self):
        """Perform final/cleanup functions before module exits
        Note that this function may be called multiple times
        Overridden by the implementer
        """

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
                    sleep(0.3)
                    continue
                if sfEvent == "FINISHED":
                    self.sf.debug(
                        f'{self.__name__}.threadWorker() got "FINISHED" from incomingEventQueue.'
                    )
                    self.poolExecute(self.finish)
                else:
                    self.sf.debug(
                        f"{self.__name__}.threadWorker() got event, {sfEvent.eventType}, from incomingEventQueue."
                    )
                    self.poolExecute(self.handleEvent, sfEvent)
        except KeyboardInterrupt:
            self.sf.debug(f"Interrupted module {self.__name__}.")
            self._stopScanning = True
        except Exception as e:
            import traceback

            self.sf.error(
                f"Exception ({e.__class__.__name__}) in module {self.__name__}." +
                traceback.format_exc()
            )
            # set errorState
            self.sf.debug(f"Setting errorState for module {self.__name__}.")
            self.errorState = True
            # clear incoming queue
            if self.incomingEventQueue:
                self.sf.debug(
                    f"Emptying incomingEventQueue for module {self.__name__}."
                )
                with suppress(queue.Empty):
                    while 1:
                        self.incomingEventQueue.get_nowait()
                # set queue to None to prevent its use
                # if there are leftover objects in the queue, the scan will hang.
                self.incomingEventQueue = None

    def poolExecute(self, callback, *args, **kwargs) -> None:
        """Execute a callback with the given args.
        If we're in a storage module, execute normally.
        Otherwise, use the shared thread pool.

        Args:
            callback: function to call
            args: args (passed through to callback)
            kwargs: kwargs (passed through to callback)
        """
        if self.__name__.startswith("sfp__stor_"):
            callback(*args, **kwargs)
        else:
            self.sharedThreadPool.submit(
                callback,
                *args,
                taskName=f"{self.__name__}_threadWorker",
                maxThreads=self.maxThreads,
                **kwargs,
            )

    def threadPool(self, *args, **kwargs):
        return SpiderFootThreadPool(*args, **kwargs)

    def setSharedThreadPool(self, sharedThreadPool) -> None:
        self.sharedThreadPool = sharedThreadPool


# end of SpiderFootPlugin class
