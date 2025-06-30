# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         Modular SpiderFoot Scanner
# Purpose:      Common functions for working with the scanning process.
#
# Author:      Agostino Panico @poppopjmp
#
# Created:     30/06/2025
# Copyright:   (c) Agostino Panico 2025
# Licence:     MIT
# -------------------------------------------------------------------------------
import socket
import time
import queue
from time import sleep
from copy import deepcopy
from contextlib import suppress
from collections import OrderedDict
import traceback

import dns.resolver

from spiderfoot.sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootPlugin, SpiderFootTarget, SpiderFootHelpers, SpiderFootThreadPool
from spiderfoot.logger import logWorkerSetup
from spiderfoot import SpiderFootDb


def startSpiderFootScanner(loggingQueue, *args, **kwargs):
    """Initialize and start the SpiderFootScanner.

    Args:
        loggingQueue (Queue): Queue for logging events
        *args: Additional arguments for SpiderFootScanner
        **kwargs: Additional keyword arguments for SpiderFootScanner

    Returns:
        SpiderFootScanner: Initialized SpiderFootScanner object
    """
    # Ensure modules directory is in Python path for dynamic imports
    import sys
    import os
    modules_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'modules')
    modules_dir = os.path.abspath(modules_dir)
    if modules_dir not in sys.path:
        sys.path.insert(0, modules_dir)
    logWorkerSetup(loggingQueue)
    return SpiderFootScanner(*args, **kwargs)


class SpiderFootScanner():
    """SpiderFootScanner object.

    Attributes:
        scanId (str): unique ID of the scan
        status (str): status of the scan
    """

    def __init__(self, scanName: str, scanId: str, targetValue: str, targetType: str, moduleList: list, globalOpts: dict, start: bool = True) -> None:
        # Instance attribute initialization (moved from class-level)
        self.__scanId = None
        self.__status = None
        self.__config = None
        self.__sf = None
        self.__dbh = None
        self.__targetValue = None
        self.__targetType = None
        self.__moduleList = []
        self.__target = None
        self.__moduleInstances = {}
        self.__modconfig = {}
        self.__scanName = None

        if not isinstance(globalOpts, dict):
            raise TypeError(
                f"globalOpts is {type(globalOpts)}; expected dict()")
        if not globalOpts:
            raise ValueError("globalOpts is empty")

        self.__config = deepcopy(globalOpts)
        self.__dbh = SpiderFootDb(self.__config)

        if not isinstance(scanName, str):
            raise TypeError(f"scanName is {type(scanName)}; expected str()")
        if not scanName:
            raise ValueError("scanName value is blank")

        self.__scanName = scanName

        if not isinstance(scanId, str):
            raise TypeError(f"scanId is {type(scanId)}; expected str()")
        if not scanId:
            raise ValueError("scanId value is blank")

        self.__scanId = scanId

        if not isinstance(targetValue, str):
            raise TypeError(
                f"targetValue is {type(targetValue)}; expected str()")
        if not targetValue:
            raise ValueError("targetValue value is blank")

        self.__targetValue = targetValue

        if not isinstance(targetType, str):
            raise TypeError(
                f"targetType is {type(targetType)}; expected str()")
        if not targetType:
            raise ValueError("targetType value is blank")

        self.__targetType = targetType
        if not isinstance(moduleList, list):
            raise TypeError(
                f"moduleList is {type(moduleList)}; expected list()")
        if not moduleList:
            raise ValueError("moduleList is empty")

        self.__moduleList = moduleList
        self.__sf = SpiderFoot(self.__config)
        self.__sf.dbh = self.__dbh

        # Create a unique ID for this scan in the back-end DB.
        if scanId:
            self.__scanId = scanId
        else:
            self.__scanId = SpiderFootHelpers.genScanInstanceId()

        # Improved exception handling for scanInstanceCreate
        try:
            self.__sf.scanId = self.__scanId
            self.__dbh.scanInstanceCreate(
                self.__scanId, self.__scanName, self.__targetValue)
        except Exception as e:
            self.__sf.status(f"Scan [{self.__scanId}] failed to create scan instance: {e}\n{traceback.format_exc()}")
            self.__setStatus("ERROR-FAILED", None, time.time() * 1000)
            raise

        # Create our target
        # Improved exception handling: log exception details for debugging
        try:
            self.__target = SpiderFootTarget(
                self.__targetValue, self.__targetType)
        except (TypeError, ValueError) as e:
            self.__sf.status(f"Scan [{self.__scanId}] failed: {e}\n{traceback.format_exc()}")
            self.__setStatus("ERROR-FAILED", None, time.time() * 1000)
            raise ValueError(f"Invalid target: {e}") from None

        # Ensure all modules have an 'opts' key to prevent KeyError in configSerialize
        if '__modules__' in self.__config:
            for modname, modcfg in self.__config['__modules__'].items():
                if 'opts' not in modcfg:
                    modcfg['opts'] = {}

        # Save the config current set for this scan
        # Improved exception handling for scanConfigSet
        try:
            self.__config['_modulesenabled'] = self.__moduleList
            self.__dbh.scanConfigSet(
                self.__scanId, self.__sf.configSerialize(deepcopy(self.__config)))
        except Exception as e:
            self.__sf.status(f"Scan [{self.__scanId}] failed to save config: {e}\n{traceback.format_exc()}")
            self.__setStatus("ERROR-FAILED", None, time.time() * 1000)
            raise

        # Process global options that point to other places for data

        # If a proxy server was specified, set it up
        proxy_type = self.__config.get('_socks1type')
        if proxy_type:
            # Proxy type mapping for clarity and maintainability
            proxy_types = {'4': 'socks4://', '5': 'socks5://', 'HTTP': 'http://', 'TOR': 'socks5h://'}
            proxy_proto = proxy_types.get(proxy_type.upper() if isinstance(proxy_type, str) else proxy_type)
            if not proxy_proto:
                self.__sf.status(
                    f"Scan [{self.__scanId}] failed: Invalid proxy type: {proxy_type}")
                self.__setStatus("ERROR-FAILED", None, time.time() * 1000)
                raise ValueError(f"Invalid proxy type: {proxy_type}")

            proxy_host = self.__config.get('_socks2addr', '')

            if not proxy_host:
                self.__sf.status(
                    f"Scan [{self.__scanId}] failed: Proxy type is set ({proxy_type}) but proxy address value is blank")
                self.__setStatus("ERROR-FAILED", None, time.time() * 1000)
                raise ValueError(
                    f"Proxy type is set ({proxy_type}) but proxy address value is blank")

            proxy_port = int(self.__config.get('_socks3port') or 0)

            if not proxy_port:
                if proxy_type in ['4', '5']:
                    proxy_port = 1080
                elif proxy_type.upper() == 'HTTP':
                    proxy_port = 8080
                elif proxy_type.upper() == 'TOR':
                    proxy_port = 9050

            proxy_username = self.__config.get('_socks4user', '')
            proxy_password = self.__config.get('_socks5pwd', '')

            if proxy_username or proxy_password:
                proxy_auth = f"{proxy_username}:{proxy_password}"
                proxy = f"{proxy_proto}{proxy_auth}@{proxy_host}:{proxy_port}"
            else:
                proxy = f"{proxy_proto}{proxy_host}:{proxy_port}"

            self.__sf.debug(f"Using proxy: {proxy}")
            self.__sf.socksProxy = proxy
        else:
            self.__sf.socksProxy = None

        # Improved exception handling for DNS override
        try:
            if self.__config['_dnsserver']:
                res = dns.resolver.Resolver()
                res.nameservers = [self.__config['_dnsserver']]
                dns.resolver.override_system_resolver(res)
            else:
                dns.resolver.restore_system_resolver()
        except Exception as e:
            self.__sf.status(f"Scan [{self.__scanId}] failed to set DNS resolver: {e}\n{traceback.format_exc()}")
            self.__setStatus("ERROR-FAILED", None, time.time() * 1000)
            raise

        # Set the user agent
        # Improved exception handling for user agent setup
        try:
            self.__config['_useragent'] = self.__sf.optValueToData(
                self.__config['_useragent'])
        except Exception as e:
            self.__sf.status(f"Scan [{self.__scanId}] failed to set user agent: {e}\n{traceback.format_exc()}")
            self.__setStatus("ERROR-FAILED", None, time.time() * 1000)
            raise

        # Improved exception handling for TLD setup
        try:
            tld_data = self.__sf.cacheGet(
                "internet_tlds", self.__config['_internettlds_cache'])
            if tld_data is None:
                tld_data = self.__sf.optValueToData(self.__config['_internettlds'])
                if tld_data is None:
                    self.__sf.status(
                        f"Scan [{self.__scanId}] failed: Could not update TLD list")
                    self.__setStatus("ERROR-FAILED", None, time.time() * 1000)
                    raise ValueError("Could not update TLD list")
                self.__sf.cachePut("internet_tlds", tld_data)
            self.__config['_internettlds'] = tld_data.splitlines()
        except Exception as e:
            self.__sf.status(f"Scan [{self.__scanId}] failed to set up TLDs: {e}\n{traceback.format_exc()}")
            self.__setStatus("ERROR-FAILED", None, time.time() * 1000)
            raise

        self.__setStatus("INITIALIZING", time.time() * 1000, None)

        self.__sharedThreadPool = SpiderFootThreadPool(
            threads=self.__config.get("_maxthreads", 3), name='sharedThreadPool')

        self.eventQueue = None

        # --- BEGIN: Module config validation and instance creation for test coverage ---
        for modName in self.__moduleList:
            if not modName:
                continue
            if modName not in self.__config['__modules__']:
                continue
            try:
                module = __import__('modules.' + modName, globals(), locals(), [modName])
            except ImportError:
                continue
            try:
                mod = getattr(module, modName)()
                mod.__name__ = modName
            except Exception:
                continue
            # Defensive: handle missing or malformed module config
            modcfg = self.__config['__modules__'].get(modName)
            if not isinstance(modcfg, dict):
                modcfg = {}
                self.__config['__modules__'][modName] = modcfg
            if 'opts' not in modcfg or modcfg['opts'] is None:
                modcfg['opts'] = {}
            if 'opts' in modcfg and not isinstance(modcfg['opts'], dict):
                raise TypeError(f"Module {modName} 'opts' is not a dict")
            # Only add to __moduleInstances, do not run setup etc. here
            self.__moduleInstances[modName] = mod
        # --- END: Module config validation and instance creation ---

        if start:
            self.__startScan()

    @property
    def scanId(self) -> str:
        return self.__scanId

    @property
    def status(self) -> str:
        return self.__status

    def __setStatus(self, status: str, started: float = None, ended: float = None) -> None:
        if not isinstance(status, str):
            raise TypeError(f"status is {type(status)}; expected str()")

        if status not in [
            "INITIALIZING",
            "STARTING",
            "STARTED",
            "RUNNING",
            "ABORT-REQUESTED",
            "ABORTED",
            "ABORTING",
            "FINISHED",
            "ERROR-FAILED"
        ]:
            raise ValueError(f"Invalid scan status {status}")

        self.__status = status
        self.__dbh.scanInstanceSet(self.__scanId, started, ended, status)

    def _log_module_error(self, modName, msg, exc):
        self.__sf.error(f"Module {modName} {msg}: {exc}\n{traceback.format_exc()}")

    def __startScan(self) -> None:
        failed = True

        try:
            self.__setStatus("STARTING", time.time() * 1000, None)
            self.__sf.status(
                f"Scan [{self.__scanId}] for '{self.__target.targetValue}' initiated.")

            self.eventQueue = queue.Queue()

            self.__sharedThreadPool.start()

            self.__sf.debug(f"Loading {len(self.__moduleList)} modules ...")
            for modName in self.__moduleList:
                if not modName:
                    continue

                if modName not in self.__config['__modules__']:
                    self.__sf.error(f"Failed to load module: {modName}")
                    continue

                try:
                    module = __import__(
                        'modules.' + modName, globals(), locals(), [modName])
                except ImportError:
                    self.__sf.error(f"Failed to load module: {modName}")
                    continue

                try:
                    mod = getattr(module, modName)()
                    mod.__name__ = modName
                except Exception:
                    self.__sf.error(
                        f"Module {modName} initialization failed")
                    continue

                # Defensive: handle missing or malformed module config
                modcfg = self.__config['__modules__'].get(modName)
                if not isinstance(modcfg, dict):
                    modcfg = {}
                    self.__config['__modules__'][modName] = modcfg
                # If 'opts' is missing or None, set to {}
                if 'opts' not in modcfg or modcfg['opts'] is None:
                    modcfg['opts'] = {}
                # If 'opts' is present and not a dict, raise TypeError
                if 'opts' in modcfg and not isinstance(modcfg['opts'], dict):
                    raise TypeError(f"Module {modName} 'opts' is not a dict")
                # Ignore extra keys, do not require 'meta', always proceed

                try:
                    self.__modconfig[modName] = deepcopy(modcfg['opts'])
                    for opt in list(self.__config.keys()):
                        self.__modconfig[modName][opt] = deepcopy(self.__config[opt])

                    mod.clearListeners()
                    mod.setScanId(self.__scanId)
                    mod.setSharedThreadPool(self.__sharedThreadPool)
                    mod.setDbh(self.__dbh)
                    mod.setup(self.__sf, self.__modconfig[modName])
                except Exception:
                    self.__sf.error(
                        f"Module {modName} setup failed")
                    mod.errorState = True
                    continue

                if self.__config['_socks1type'] != '':
                    try:
                        mod._updateSocket(socket)
                    except Exception as e:
                        self.__sf.error(
                            f"Module {modName} socket setup failed: {e}")
                        continue

                if self.__config['__outputfilter']:
                    try:
                        mod.setOutputFilter(self.__config['__outputfilter'])
                    except Exception as e:
                        self.__sf.error(
                            f"Module {modName} output filter setup failed: {e}")
                        continue

                try:
                    newTarget = mod.enrichTarget(self.__target)
                    if newTarget is not None:
                        self.__target = newTarget
                except Exception as e:
                    self._log_module_error(modName, "target enrichment failed", e)
                    continue

                try:
                    mod.setTarget(self.__target)
                except Exception as e:
                    self._log_module_error(modName, f"failed to set target '{self.__target}'", e)
                    continue

                try:
                    mod.outgoingEventQueue = self.eventQueue
                    mod.incomingEventQueue = queue.Queue()
                    self.__sf.debug(f"Module {modName} queues initialized: incoming={{mod.incomingEventQueue is not None}}, outgoing={{mod.outgoingEventQueue is not None}}")
                    # Explicitly check both queues
                    if mod.incomingEventQueue is None or mod.outgoingEventQueue is None:
                        self.__sf.error(f"Module {modName} queue validation failed after setup")
                        continue
                except Exception as e:
                    self._log_module_error(modName, "event queue setup failed", e)
                    continue

                self.__moduleInstances[modName] = mod
                self.__sf.status(f"{modName} module loaded.")

            self.__sf.debug(
                f"Scan [{self.__scanId}] loaded {len(self.__moduleInstances)} modules.")

            if not self.__moduleInstances:
                self.__setStatus("ERROR-FAILED", None, time.time() * 1000)
                self.__dbh.close()
                return

            self.__moduleInstances = OrderedDict(
                sorted(self.__moduleInstances.items(), key=lambda m: m[-1]._priority))

            self.__setStatus("RUNNING")

            psMod = SpiderFootPlugin()
            psMod.__name__ = "SpiderFoot UI"
            psMod.setTarget(self.__target)
            psMod.setDbh(self.__dbh)
            psMod.clearListeners()
            psMod.outgoingEventQueue = self.eventQueue
            psMod.incomingEventQueue = queue.Queue()

            rootEvent = SpiderFootEvent("ROOT", self.__targetValue, "", None)
            psMod.notifyListeners(rootEvent)
            firstEvent = SpiderFootEvent(self.__targetType, self.__targetValue,
                                         "SpiderFoot UI", rootEvent)
            psMod.notifyListeners(firstEvent)

            if self.__targetType == 'INTERNET_NAME' and self.__sf.isDomain(self.__targetValue, self.__config['_internettlds']):
                firstEvent = SpiderFootEvent(
                    'DOMAIN_NAME', self.__targetValue, "SpiderFoot UI", rootEvent)
                psMod.notifyListeners(firstEvent)

            scanstatus = self.__dbh.scanInstanceGet(self.__scanId)
            if scanstatus and scanstatus[5] == "ABORT-REQUESTED":
                raise AssertionError("ABORT-REQUESTED")

            self.waitForThreads()
            failed = False

        except (KeyboardInterrupt, AssertionError):
            self.__sf.status(f"Scan [{self.__scanId}] aborted.")
            self.__setStatus("ABORTED", None, time.time() * 1000)

        except Exception as e:
            self.__sf.error(f"Scan [{self.__scanId}] failed: {str(e)}")

        finally:
            if not failed:
                self.__setStatus("FINISHED", None, time.time() * 1000)
                self.runCorrelations()
                self.__sf.status(f"Scan [{self.__scanId}] completed.")
            self.__dbh.close()

    def runCorrelations(self) -> None:
        from spiderfoot.correlation.rule_executor import RuleExecutor
        from spiderfoot.correlation.event_enricher import EventEnricher
        from spiderfoot.correlation.result_aggregator import ResultAggregator

        self.__sf.status(
            f"Running {len(self.__config['__correlationrules__'])} correlation rules on scan {self.__scanId}.")
        rules = self.__config['__correlationrules__']
        executor = RuleExecutor(self.__dbh, rules, scan_ids=[self.__scanId])
        results = executor.run()
        enricher = EventEnricher(self.__dbh)
        for rule_id, result in results.items():
            if 'events' in result:
                result['events'] = enricher.enrich_sources(self.__scanId, result['events'])
                result['events'] = enricher.enrich_entities(self.__scanId, result['events'])
        aggregator = ResultAggregator()
        agg_count = aggregator.aggregate(list(results.values()), method='count')
        self.__sf.status(f"Correlated {agg_count} results for scan {self.__scanId}")

    def waitForThreads(self) -> None:
        if not self.eventQueue:
            return

        counter = 0

        try:
            for mod in self.__moduleInstances.values():
                if not (mod.incomingEventQueue and mod.outgoingEventQueue):
                    self.__sf.error(f"Module {mod.__name__} has uninitialized queues, skipping")
                    continue
                mod.start()
            final_passes = 3

            while True:
                log_status = counter % 10 == 0
                counter += 1

                if log_status:
                    scanstatus = self.__dbh.scanInstanceGet(self.__scanId)
                    if scanstatus and scanstatus[5] == "ABORT-REQUESTED":
                        raise AssertionError("ABORT-REQUESTED")

                try:
                    sfEvent = self.eventQueue.get_nowait()
                    self.__sf.debug(
                        f"waitForThreads() got event, {sfEvent.eventType}, from eventQueue.")
                except queue.Empty:
                    if self.threadsFinished(log_status):
                        sleep(.1)
                        if self.threadsFinished(log_status):
                            if final_passes < 1:
                                break
                            for mod in self.__moduleInstances.values():
                                if not mod.errorState and mod.incomingEventQueue is not None:
                                    mod.incomingEventQueue.put('FINISHED')
                            sleep(.1)
                            while not self.threadsFinished(log_status):
                                log_status = counter % 100 == 0
                                counter += 1
                                sleep(.01)
                            final_passes -= 1
                    else:
                        sleep(.1)
                    continue

                if not isinstance(sfEvent, SpiderFootEvent):
                    raise TypeError(
                        f"sfEvent is {type(sfEvent)}; expected SpiderFootEvent")

                for mod in self.__moduleInstances.values():
                    if mod._stopScanning:
                        raise AssertionError(f"{mod.__name__} requested stop")

                    if not mod.errorState and mod.incomingEventQueue is not None:
                        watchedEvents = mod.watchedEvents()
                        if sfEvent.eventType in watchedEvents or "*" in watchedEvents:
                            mod.incomingEventQueue.put(deepcopy(sfEvent))

        finally:
            for mod in self.__moduleInstances.values():
                mod._stopScanning = True
            self.__sharedThreadPool.shutdown(wait=True)

    def threadsFinished(self, log_status: bool = False) -> bool:
        if self.eventQueue is None:
            return True

        modules_waiting = dict()
        for m in self.__moduleInstances.values():
            try:
                if m.incomingEventQueue is not None:
                    modules_waiting[m.__name__] = m.incomingEventQueue.qsize()
            except Exception:
                with suppress(Exception):
                    m.errorState = True
        modules_waiting = sorted(
            modules_waiting.items(), key=lambda x: x[-1], reverse=True)

        modules_running = []
        for m in self.__moduleInstances.values():
            try:
                if m.running:
                    modules_running.append(m.__name__)
            except Exception:
                with suppress(Exception):
                    m.errorState = True

        modules_errored = []
        for m in self.__moduleInstances.values():
            try:
                if m.errorState:
                    modules_errored.append(m.__name__)
            except Exception:
                with suppress(Exception):
                    m.errorState = True

        queues_empty = [qsize == 0 for m, qsize in modules_waiting]

        for mod in self.__moduleInstances.values():
            if mod.errorState and mod.incomingEventQueue is not None:
                self.__sf.debug(
                    f"Clearing and unsetting incomingEventQueue for errored module {mod.__name__}.")
                with suppress(Exception):
                    while 1:
                        mod.incomingEventQueue.get_nowait()
                mod.incomingEventQueue = None

        if not modules_running and not queues_empty:
            self.__sf.debug("Clearing queues for stalled/aborted modules.")
            for mod in self.__moduleInstances.values():
                with suppress(Exception):
                    while True:
                        mod.incomingEventQueue.get_nowait()

        if log_status:
            events_queued = ", ".join(
                [f"{mod}: {qsize:,}" for mod, qsize in modules_waiting[:5] if qsize > 0])
            if not events_queued:
                events_queued = 'None'
            self.__sf.debug(
                f"Events queued: {sum([m[-1] for m in modules_waiting]):,} ({events_queued})")
            if modules_running:
                self.__sf.debug(
                    f"Modules running: {len(modules_running):,} ({', '.join(modules_running)})")
            if modules_errored:
                self.__sf.debug(
                    f"Modules errored: {len(modules_errored):,} ({', '.join(modules_errored)})")

        if all(queues_empty) and not modules_running:
            return True
        return False

# End of scanner.py
