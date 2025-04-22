# -*- coding: utf-8 -*-
# -----------------------------------------------------------------
# Name:         sfapi
# Purpose:      REST API interface
#
# Author:       Agostino Panico @poppopjmp
#
# Created:      22/04/2025
# Copyright:    (c) Agostino Panico 2025
# License:      MIT
# -----------------------------------------------------------------
import json
import logging
import multiprocessing as mp
import random
import time
from copy import deepcopy
from operator import itemgetter

import cherrypy

from sflib import SpiderFoot
from sfscan import startSpiderFootScanner
from spiderfoot import SpiderFootDb, SpiderFootHelpers, __version__
from spiderfoot.logger import logListenerSetup, logWorkerSetup

mp.set_start_method("spawn", force=True)


class SpiderFootApi:
    """SpiderFoot REST API."""

    defaultConfig = dict()
    config = dict()
    token = None  # Used for CSRF protection on settings changes

    def __init__(self: 'SpiderFootApi', web_config: dict, config: dict, loggingQueue: 'logging.handlers.QueueListener' = None) -> None:
        """Initialize API.

        Args:
            web_config (dict): config settings for web interface (interface, port, root path)
            config (dict): SpiderFoot config
            loggingQueue: TBD

        Raises:
            TypeError: arg type is invalid
            ValueError: arg value is invalid
        """
        if not isinstance(config, dict):
            raise TypeError(f"config is {type(config)}; expected dict()")
        if not config:
            raise ValueError("config is empty")

        if not isinstance(web_config, dict):
            raise TypeError(
                f"web_config is {type(web_config)}; expected dict()")
        if not config:
            raise ValueError("web_config is empty")

        # 'config' supplied will be the defaults, let's supplement them
        # now with any configuration which may have previously been saved.
        self.defaultConfig = deepcopy(config)
        dbh = SpiderFootDb(self.defaultConfig, init=True)
        sf = SpiderFoot(self.defaultConfig)
        self.config = sf.configUnserialize(dbh.configGet(), self.defaultConfig)

        # Set up logging
        if loggingQueue is None:
            self.loggingQueue = mp.Queue()
            logListenerSetup(self.loggingQueue, self.config)
        else:
            self.loggingQueue = loggingQueue
        logWorkerSetup(self.loggingQueue)
        self.log = logging.getLogger(f"spiderfoot.{__name__}")

        # Generate initial token for settings changes
        self.token = random.SystemRandom().randint(0, 99999999)

    def jsonify_error(self: 'SpiderFootApi', status: int, message: str) -> dict:
        """Jsonify error response.

        Args:
            status (int): HTTP response status code
            message (str): Error message

        Returns:
            dict: HTTP error response template
        """
        cherrypy.response.headers['Content-Type'] = 'application/json'
        cherrypy.response.status = status
        return {
            'error': {
                'http_status': status,
                'message': message,
            }
        }

    #
    # API ENDPOINTS
    #

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def scanopts(self: 'SpiderFootApi', id: str) -> dict:
        """Return configuration used for the specified scan as JSON.

        Args:
            id: scan ID

        Returns:
            dict: scan options for the specified scan or error JSON
        """
        dbh = SpiderFootDb(self.config)
        ret = dict()

        meta = dbh.scanInstanceGet(id)
        if not meta:
            return self.jsonify_error(404, "Scan ID not found.")

        if meta[3] != 0:
            started = time.strftime(
                "%Y-%m-%d %H:%M:%S", time.localtime(meta[3]))
        else:
            started = "Not yet"

        if meta[4] != 0:
            finished = time.strftime(
                "%Y-%m-%d %H:%M:%S", time.localtime(meta[4]))
        else:
            finished = "Not yet"

        ret['meta'] = [meta[0], meta[1], meta[2], started, finished, meta[5]]
        ret['config'] = dbh.scanConfigGet(id)
        ret['configdesc'] = dict()
        sf = SpiderFoot(self.config)
        for key in list(ret['config'].keys()):
            if ':' not in key:
                # Global option
                desc = sf.config[key]['_description']
                if desc:
                    ret['configdesc'][key] = desc
            else:
                # Module option
                mod = key.split(":")[0]
                opt = key.split(":")[1]
                desc = sf.config['__modules__'][mod]['opts'][opt]['_description']
                if desc:
                    ret['configdesc'][key] = desc

        return ret

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def rerunscan(self: 'SpiderFootApi', id: str) -> dict:
        """Rerun a scan.

        Args:
            id (str): scan ID

        Returns:
            dict: JSON containing status and new scan ID or error JSON
        """
        # Snapshot the current configuration to be used by the scan
        cfg = deepcopy(self.config)
        modlist = list()
        dbh = SpiderFootDb(cfg)
        info = dbh.scanInstanceGet(id)

        if not info:
            return self.jsonify_error(404, "Invalid scan ID.")

        scanname = info[0]
        scantarget = info[1]

        scanconfig = dbh.scanConfigGet(id)
        if not scanconfig:
            return self.jsonify_error(500, f"Error loading config from scan: {id}")

        modlist = scanconfig['_modulesenabled'].split(',')
        if "sfp__stor_stdout" in modlist:
            modlist.remove("sfp__stor_stdout")

        targetType = SpiderFootHelpers.targetTypeFromString(scantarget)
        if not targetType:
            # It must then be a name, as a re-run scan should always have a clean
            # target. Put quotes around the target value and try to determine the
            # target type again.
            targetType = SpiderFootHelpers.targetTypeFromString(
                f'"{scantarget}"')

        if targetType not in ["HUMAN_NAME", "BITCOIN_ADDRESS"]:
            scantarget = scantarget.lower()

        # Start running a new scan
        scanId = SpiderFootHelpers.genScanInstanceId()
        try:
            p = mp.Process(target=startSpiderFootScanner, args=(
                self.loggingQueue, scanname, scanId, scantarget, targetType, modlist, cfg))
            p.daemon = True
            p.start()
        except Exception as e:
            self.log.error(f"[-] Scan [{scanId}] failed: {e}", exc_info=True)
            return self.jsonify_error(500, f"Scan [{scanId}] failed to start: {e}")

        # Wait until the scan has initialized (with a timeout)
        start_time = time.time()
        while dbh.scanInstanceGet(scanId) is None:
            self.log.info("Waiting for the scan to initialize...")
            if time.time() - start_time > 30:  # 30 second timeout
                return self.jsonify_error(500, f"Scan [{scanId}] failed to initialize within timeout.")
            time.sleep(1)

        return {"status": "SUCCESS", "scan_id": scanId}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def rerunscanmulti(self: 'SpiderFootApi', ids: str) -> dict:
        """Rerun scans.

        Args:
            ids (str): comma separated list of scan IDs

        Returns:
            dict: JSON containing status and list of new scan IDs or errors
        """
        # Snapshot the current configuration to be used by the scan
        cfg = deepcopy(self.config)
        dbh = SpiderFootDb(cfg)
        results = {"started": [], "errors": []}

        for id in ids.split(","):
            info = dbh.scanInstanceGet(id)
            if not info:
                results["errors"].append({"id": id, "error": "Invalid scan ID."})
                continue

            scanconfig = dbh.scanConfigGet(id)
            if not scanconfig:
                results["errors"].append({"id": id, "error": f"Error loading config from scan: {id}"})
                continue

            scanname = info[0]
            scantarget = info[1]
            targetType = None

            modlist = scanconfig['_modulesenabled'].split(',')
            if "sfp__stor_stdout" in modlist:
                modlist.remove("sfp__stor_stdout")

            targetType = SpiderFootHelpers.targetTypeFromString(scantarget)
            if not targetType:
                targetType = SpiderFootHelpers.targetTypeFromString(f'"{scantarget}"')

            if targetType not in ["HUMAN_NAME", "BITCOIN_ADDRESS"]:
                scantarget = scantarget.lower()

            # Start running a new scan
            scanId = SpiderFootHelpers.genScanInstanceId()
            try:
                p = mp.Process(target=startSpiderFootScanner, args=(
                    self.loggingQueue, scanname, scanId, scantarget, targetType, modlist, cfg))
                p.daemon = True
                p.start()
                results["started"].append({"original_id": id, "new_id": scanId})
            except Exception as e:
                self.log.error(f"[-] Scan [{scanId}] failed: {e}", exc_info=True)
                results["errors"].append({"id": id, "error": f"Scan [{scanId}] failed to start: {e}"})

        return results

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def optsraw(self: 'SpiderFootApi') -> list:
        """Return global and module settings as json.

        Returns:
            list: ['SUCCESS', {'token': CSRF_token, 'data': settings_dict}]
        """
        ret = dict()
        self.token = random.SystemRandom().randint(0, 99999999)
        sf = SpiderFoot(self.config)
        serialized_config = sf.configSerialize(self.config, filterSystem=False)
        for opt in serialized_config:
            ret[opt] = serialized_config[opt]

        return ['SUCCESS', {'token': self.token, 'data': ret}]

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def scandelete(self: 'SpiderFootApi', id: str) -> dict:
        """Delete scan(s).

        Args:
            id (str): comma separated list of scan IDs

        Returns:
            dict: JSON response indicating success or failure for each ID
        """
        results = {"deleted": [], "errors": []}
        if not id:
            return self.jsonify_error(400, "No scan IDs provided.")

        dbh = SpiderFootDb(self.config)
        ids = id.split(',')

        for scan_id in ids:
            status = dbh.scanInstanceGet(scan_id)
            if not status:
                results["errors"].append({"id": scan_id, "error": "Scan ID not found."})
                continue
            if status[5] in ["RUNNING", "STARTING", "STARTED"]:
                results["errors"].append({"id": scan_id, "error": "Scan is running, stop it first."})
                continue

        valid_ids_to_delete = [scan_id for scan_id in ids if not any(err['id'] == scan_id for err in results["errors"])]

        for scan_id in valid_ids_to_delete:
            self.log.info(f"Deleting scan: {scan_id}")
            try:
                if dbh.scanInstanceDelete(scan_id):
                    results["deleted"].append(scan_id)
                else:
                    results["errors"].append({"id": scan_id, "error": "Deletion failed unexpectedly."})
            except Exception as e:
                self.log.error(f"Error deleting scan {scan_id}: {e}", exc_info=True)
                results["errors"].append({"id": scan_id, "error": f"Exception during deletion: {e}"})

        return results

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def savesettingsraw(self: 'SpiderFootApi', allopts: str, token: str) -> list:
        """Save settings passed as a JSON string.

        Args:
            allopts (str): JSON string containing settings to save.
                           Use "RESET" to reset all settings to default.
            token (str): CSRF token obtained from optsraw endpoint.

        Returns:
            list: ['SUCCESS', ''] or ['ERROR', 'message']
        """
        if str(token) != str(self.token):
            return self.jsonify_error(403, "Invalid token.")

        if allopts == "RESET":
            if self.reset_settings():
                self.token = random.SystemRandom().randint(0, 99999999)
                return ["SUCCESS", "Settings reset to default."]
            else:
                return self.jsonify_error(500, "Failed to reset settings.")

        try:
            newopts = json.loads(allopts)
            if not isinstance(newopts, dict):
                raise ValueError("Invalid format for settings, must be a JSON object.")

            dbh = SpiderFootDb(self.config)
            sf = SpiderFoot(self.config)
            current_config_structure = deepcopy(self.config)
            unserialized_opts = sf.configUnserialize(newopts, current_config_structure)

            self.config.update(unserialized_opts)

            serialized_for_db = sf.configSerialize(self.config)
            dbh.configSet(serialized_for_db)
            self.token = random.SystemRandom().randint(0, 99999999)
            return ["SUCCESS", "Settings saved."]
        except json.JSONDecodeError:
            return self.jsonify_error(400, "Invalid JSON format for settings.")
        except ValueError as e:
            return self.jsonify_error(400, str(e))
        except Exception as e:
            self.log.error(f"Error saving settings: {e}", exc_info=True)
            return self.jsonify_error(500, f"Error saving settings: {e}")

    def reset_settings(self: 'SpiderFootApi') -> bool:
        """Reset settings to default.

        Returns:
            bool: success
        """
        try:
            dbh = SpiderFootDb(self.config)
            dbh.configClear()
            self.config = deepcopy(self.defaultConfig)
            self.log.info("Configuration reset to defaults.")
            return True
        except Exception as e:
            self.log.error(f"Exception resetting settings: {e}", exc_info=True)
            return False

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def resultsetfp(self: 'SpiderFootApi', id: str, resultids: str, fp: str) -> list:
        """Set a bunch of results (hashes) as false positive.

        Args:
            id (str): scan ID
            resultids (str): comma separated list of result IDs (hashes)
            fp (str): 0 or 1

        Returns:
            list: ['SUCCESS', ''] or ['ERROR', 'message']
        """
        dbh = SpiderFootDb(self.config)

        if fp not in ["0", "1"]:
            return self.jsonify_error(400, "Invalid FP value, must be 0 or 1.")

        try:
            ids = resultids.split(',')
            if not ids:
                return self.jsonify_error(400, "No result IDs provided.")
        except Exception:
            return self.jsonify_error(400, "Invalid result IDs format.")

        status = dbh.scanInstanceGet(id)
        if not status:
            return self.jsonify_error(404, "Scan ID not found.")

        if fp == "0":
            parents = dbh.scanElementParents(id, ids)
            if parents:
                parent_fps = dbh.scanResultGet(id, ids=parents)
                for p_fp in parent_fps:
                    if p_fp[10] == 1:
                        return self.jsonify_error(400, f"Cannot mark as not FP as parent element {p_fp[4]} is marked as FP.")

        childs = dbh.scanElementChildrenAll(id, ids)
        allIds = ids + childs

        try:
            ret = dbh.scanResultsUpdateFP(id, allIds, fp)
            if ret:
                return ["SUCCESS", f"FP status updated for {len(allIds)} elements."]
            else:
                return self.jsonify_error(500, "Failed to update FP status in database.")
        except Exception as e:
            self.log.error(f"Error updating FP status for scan {id}: {e}", exc_info=True)
            return self.jsonify_error(500, f"Exception updating FP status: {e}")

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def eventtypes(self: 'SpiderFootApi') -> list:
        """List all event types.

        Returns:
            list: list of event type dictionaries [{'name': name, 'descr': descr}]
        """
        dbh = SpiderFootDb(self.config)
        types = dbh.eventTypes()
        ret = list()

        for r in types:
            ret.append({'name': r[0], 'descr': r[1]})

        return sorted(ret, key=itemgetter('name'))

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def modules(self: 'SpiderFootApi') -> list:
        """List all modules.

        Returns:
            list: list of module dictionaries [{'name': name, 'descr': descr}]
        """
        ret = list()

        modinfo = list(self.config['__modules__'].keys())
        if not modinfo:
            return self.jsonify_error(500, "Module information not loaded.")

        modinfo.sort()

        for m in modinfo:
            descr = self.config['__modules__'][m].get('summary', 'No description available.')
            ret.append({'name': m, 'descr': descr})

        return ret

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def correlationrules(self: 'SpiderFootApi') -> list:
        """List all correlation rules.

        Returns:
            list: list of correlation rule dictionaries [{'id': id, 'name': name, 'descr': descr}]
        """
        ret = list()

        rules = self.config.get('__correlationrules__')
        if not rules:
            return ret

        for r in rules:
            meta = r.get('meta', {})
            ret.append({
                'id': r.get('id', 'Unknown ID'),
                'name': meta.get('name', 'Unknown Name'),
                'descr': meta.get('description', 'No description available.')
            })

        return sorted(ret, key=itemgetter('name'))

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def ping(self: 'SpiderFootApi') -> list:
        """For the CLI to test connectivity to this server.

        Returns:
            list: ['SUCCESS', __version__]
        """
        return ["SUCCESS", __version__]

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def query(self: 'SpiderFootApi', query: str) -> list:
        """For the CLI to run SELECT queries against the database.

        Args:
            query (str): SQL SELECT query

        Returns:
            list: ['SUCCESS', [results]] or ['ERROR', 'message']
        """
        dbh = SpiderFootDb(self.config)

        if not query:
            return self.jsonify_error(400, "Query cannot be empty.")

        if not query.lower().strip().startswith("select"):
            return self.jsonify_error(403, "Only SELECT queries are allowed.")

        try:
            res = dbh.dbh.execute(query)
            return ["SUCCESS", res.fetchall()]
        except Exception as e:
            self.log.error(f"Error executing query '{query}': {e}", exc_info=True)
            return self.jsonify_error(500, f"Query execution failed: {e}")

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def startscan(self: 'SpiderFootApi', scanname: str, scantarget: str, modulelist: str = None, typelist: str = None, usecase: str = None) -> dict:
        """Initiate a scan.

        Args:
            scanname (str): scan name
            scantarget (str): scan target
            modulelist (str): comma separated list of modules to use
            typelist (str): comma separated list of event types to select modules by
            usecase (str): selected module group (all, footprint, investigate, passive)

        Returns:
            dict: JSON containing status and new scan ID or error JSON
        """
        scanname = str(scanname).strip()
        scantarget = str(scantarget).strip()

        if not scanname:
            return self.jsonify_error(400, "Scan name cannot be empty.")

        if not scantarget:
            return self.jsonify_error(400, "Scan target cannot be empty.")

        if not typelist and not modulelist and not usecase:
            return self.jsonify_error(400, "Must specify modules, types, or a use case.")

        targetType = SpiderFootHelpers.targetTypeFromString(scantarget)
        if targetType is None:
            return self.jsonify_error(400, f"Could not determine target type for: {scantarget}")

        dbh = SpiderFootDb(self.config)

        cfg = deepcopy(self.config)
        sf = SpiderFoot(cfg)

        final_modlist = list()

        if modulelist:
            final_modlist = modulelist.split(',')
            valid_mods = list(cfg.get('__modules__', {}).keys())
            invalid_mods = [m for m in final_modlist if m not in valid_mods]
            if invalid_mods:
                return self.jsonify_error(400, f"Invalid modules specified: {', '.join(invalid_mods)}")

        if len(final_modlist) == 0 and typelist:
            types = typelist.split(',')
            final_modlist = sf.modulesProducing(types)
            if not final_modlist:
                return self.jsonify_error(400, f"No modules found producing specified types: {typelist}")

        if len(final_modlist) == 0 and usecase:
            if usecase == 'all':
                final_modlist = list(cfg.get('__modules__', {}).keys())
            elif usecase == 'footprint':
                final_modlist = sf.modulesProducing(cfg['_internettargets'])
            elif usecase == 'investigate':
                final_modlist = sf.modulesProducing(cfg['_genericusers'])
            elif usecase == 'passive':
                all_mods = cfg.get('__modules__', {})
                final_modlist = [m for m in all_mods if not all_mods[m].get('invasive', False)]
            else:
                return self.jsonify_error(400, f"Invalid use case specified: {usecase}")

        if not final_modlist:
            return self.jsonify_error(400, "No modules selected for scan.")

        if "sfp__stor_db" not in final_modlist:
            final_modlist.append("sfp__stor_db")
        final_modlist.sort()

        if "sfp__stor_stdout" in final_modlist:
            final_modlist.remove("sfp__stor_stdout")

        if targetType not in ["HUMAN_NAME", "USERNAME", "BITCOIN_ADDRESS"]:
            scantarget_normalized = scantarget.lower()
        else:
            scantarget_normalized = scantarget

        scanId = SpiderFootHelpers.genScanInstanceId()
        try:
            p = mp.Process(target=startSpiderFootScanner, args=(
                self.loggingQueue, scanname, scanId, scantarget_normalized, targetType, final_modlist, cfg))
            p.daemon = True
            p.start()
            self.log.info(f"Started scan: {scanname} ({scanId}) for target {scantarget_normalized}")
        except Exception as e:
            self.log.error(f"[-] Scan [{scanId}] failed to start: {e}", exc_info=True)
            return self.jsonify_error(500, f"Scan [{scanId}] failed to start: {e}")

        start_time = time.time()
        while dbh.scanInstanceGet(scanId) is None:
            self.log.info(f"Waiting for scan {scanId} to initialize...")
            if time.time() - start_time > 30:
                self.log.error(f"Scan [{scanId}] failed to initialize within timeout.")
                return self.jsonify_error(500, f"Scan [{scanId}] failed to initialize within timeout.")
            time.sleep(1)

        return {"status": "SUCCESS", "scan_id": scanId}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def stopscan(self: 'SpiderFootApi', id: str) -> dict:
        """Stop a scan.

        Args:
            id (str): comma separated list of scan IDs

        Returns:
            dict: JSON response indicating success or failure for each ID
        """
        results = {"stopped": [], "errors": []}
        if not id:
            return self.jsonify_error(400, "No scan IDs provided.")

        dbh = SpiderFootDb(self.config)
        ids = id.split(',')

        for scan_id in ids:
            status = dbh.scanInstanceGet(scan_id)
            if not status:
                results["errors"].append({"id": scan_id, "error": "Scan ID not found."})
                continue
            if status[5] not in ["RUNNING", "STARTING", "STARTED"]:
                results["errors"].append({"id": scan_id, "error": f"Scan not running (status: {status[5]})."})
                continue

        valid_ids_to_stop = [scan_id for scan_id in ids if not any(err['id'] == scan_id for err in results["errors"])]

        for scan_id in valid_ids_to_stop:
            self.log.info(f"Stopping scan: {scan_id}")
            try:
                if dbh.scanInstanceSet(scan_id, status='ABORT-REQUEST'):
                    results["stopped"].append(scan_id)
                else:
                    results["errors"].append({"id": scan_id, "error": "Failed to set ABORT-REQUEST status."})
            except Exception as e:
                self.log.error(f"Error requesting stop for scan {scan_id}: {e}", exc_info=True)
                results["errors"].append({"id": scan_id, "error": f"Exception requesting stop: {e}"})

        return results

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def vacuum(self):
        """ Trigger database vacuum. Returns status. """
        dbh = SpiderFootDb(self.config)
        try:
            self.log.info("Starting database vacuum...")
            dbh.vacuum()
            self.log.info("Database vacuum finished.")
            return {"status": "SUCCESS", "message": "Database vacuum completed."}
        except Exception as e:
            self.log.error(f"Database vacuum failed: {e}", exc_info=True)
            return self.jsonify_error(500, f"Database vacuum failed: {e}")
