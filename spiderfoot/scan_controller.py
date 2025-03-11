import time
import queue
import logging
import multiprocessing as mp
from copy import deepcopy
from typing import List, Dict

from sflib import SpiderFoot
from spiderfoot import (
    SpiderFootDb,
    SpiderFootEvent,
    SpiderFootPlugin,
    SpiderFootTarget,
    SpiderFootHelpers,
    SpiderFootThreadPool,
    SpiderFootCorrelator,
    logger,
)


class SpiderFootScanController:
    def __init__(self, scanId: str, target: str, targetType: str, modlist: List[str], cfg: Dict):
        self.scanId = scanId
        self.target = target
        self.targetType = targetType
        self.modlist = modlist
        self.cfg = cfg
        self.dbh = SpiderFootDb(cfg)
        self.sf = SpiderFoot(cfg)
        self.log = logging.getLogger(f"spiderfoot.{__name__}")

    def start_scan(self):
        try:
            self.log.info(f"Starting scan [{self.scanId}] for target [{self.target}]")
            self.sf.scan(self.scanId, self.target, self.targetType, self.modlist)
        except Exception as e:
            self.log.error(f"Scan [{self.scanId}] failed: {e}")
            self.dbh.scanInstanceSet(self.scanId, None, None, "ERROR-FAILED")
            raise e

    def stop_scan(self):
        try:
            self.log.info(f"Stopping scan [{self.scanId}] for target [{self.target}]")
            self.sf.stopScan(self.scanId)
        except Exception as e:
            self.log.error(f"Failed to stop scan [{self.scanId}]: {e}")
            raise e


def start_spiderfoot_scanner(loggingQueue: queue.Queue, scanName: str, scanId: str, target: str, targetType: str, modlist: List[str], cfg: Dict):
    try:
        log = logging.getLogger(f"spiderfoot.{__name__}")
        log.info(f"Starting SpiderFoot scanner for scan [{scanId}]")

        # Set up logging
        queueHandler = logging.handlers.QueueHandler(loggingQueue)
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG if cfg.get("_debug", False) else logging.INFO)
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        listener = logging.handlers.QueueListener(loggingQueue, handler)
        listener.start()

        # Initialize the scan controller
        scan_controller = SpiderFootScanController(scanId, target, targetType, modlist, cfg)
        scan_controller.start_scan()

        # Poll for scan status until completion
        while True:
            time.sleep(1)
            info = scan_controller.dbh.scanInstanceGet(scanId)
            if not info:
                continue
            if info[5] in ["ERROR-FAILED", "ABORT-REQUESTED", "ABORTED", "FINISHED"]:
                # allow 60 seconds for post-scan correlations to complete
                timeout = 60
                listener.stop()
                break

        log.info(f"SpiderFoot scanner for scan [{scanId}] completed")
    except Exception as e:
        log.error(f"Unhandled exception in start_spiderfoot_scanner: {e}", exc_info=True)
        raise e
