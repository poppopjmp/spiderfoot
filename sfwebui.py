# -*- coding: utf-8 -*-
# -----------------------------------------------------------------
# Name:         sfwebui
# Purpose:      User interface class for use with a web browser
#
# Author:       Steve Micallef <steve@binarypool.com>
#
# Created:      30/09/2012
# Copyright:    (c) Steve Micallef 2012
# License:      MIT
# -----------------------------------------------------------------
import csv
import html
import json
import logging
import multiprocessing as mp
import random
import requests
import string
import time
from copy import deepcopy
from io import BytesIO, StringIO
from operator import itemgetter

import cherrypy
from cherrypy import _cperror

from mako.lookup import TemplateLookup
from mako.template import Template

import openpyxl

import secure

from sflib import SpiderFoot

from spiderfoot import SpiderFootDb
from spiderfoot import SpiderFootHelpers
from spiderfoot import __version__
from spiderfoot.logger import logListenerSetup, logWorkerSetup

mp.set_start_method("spawn", force=True)


class APIClient:
    """Client for communicating with SpiderFoot API."""

    def __init__(self: 'APIClient', api_url: str = "http://127.0.0.1:8000/api") -> None:
        """Initialize API client.

        Args:
            api_url (str): URL for SpiderFoot API
        """
        self.api_url = api_url.rstrip('/')
        self.token = None
        self.session = requests.Session()
        
    def _request(self, endpoint: str, method: str = 'GET', params: dict = None, data: dict = None, json_data: dict = None) -> dict:
        """Make a request to the API.

        Args:
            endpoint (str): API endpoint
            method (str): HTTP method
            params (dict): URL parameters
            data (dict): Form data
            json_data (dict): JSON data

        Returns:
            dict: API response
        """
        url = f"{self.api_url}/{endpoint.lstrip('/')}"
        
        try:
            if method == 'GET':
                resp = self.session.get(url, params=params)
            elif method == 'POST':
                if json_data is not None:
                    resp = self.session.post(url, json=json_data, params=params)
                else:
                    resp = self.session.post(url, data=data, params=params)
            elif method == 'DELETE':
                resp = self.session.delete(url, params=params)
            
            if resp.status_code != 200:
                return {"error": {"http_status": resp.status_code, "message": resp.text}}
            
            return resp.json()
        except Exception as e:
            return {"error": {"http_status": 500, "message": str(e)}}
    
    def scan_list(self) -> list:
        """Get list of scans.

        Returns:
            list: List of scans
        """
        return self._request("scanlist")
    
    def scan_status(self, scan_id: str) -> dict:
        """Get scan status.

        Args:
            scan_id (str): Scan ID

        Returns:
            dict: Scan status
        """
        return self._request(f"scanstatus", params={"id": scan_id})
    
    def scan_delete(self, scan_id: str) -> dict:
        """Delete a scan.

        Args:
            scan_id (str): Scan ID

        Returns:
            dict: API response
        """
        return self._request(f"scandelete", params={"id": scan_id}, method='DELETE')
    
    def scan_options(self, scan_id: str) -> dict:
        """Get scan options.

        Args:
            scan_id (str): Scan ID

        Returns:
            dict: Scan options
        """
        return self._request(f"scanopts", params={"id": scan_id})
    
    def start_scan(self, scanname: str, scantarget: str, modulelist: str = None, typelist: str = None, usecase: str = None) -> dict:
        """Start a scan.

        Args:
            scanname (str): Scan name
            scantarget (str): Scan target
            modulelist (str): Module list
            typelist (str): Event type list
            usecase (str): Use case

        Returns:
            dict: API response
        """
        params = {
            "scanname": scanname,
            "scantarget": scantarget
        }
        if modulelist:
            params["modulelist"] = modulelist
        if typelist:
            params["typelist"] = typelist
        if usecase:
            params["usecase"] = usecase
        
        return self._request("startscan", method='POST', params=params)
    
    def stop_scan(self, scan_id: str) -> dict:
        """Stop a scan.

        Args:
            scan_id (str): Scan ID

        Returns:
            dict: API response
        """
        return self._request(f"stopscan", params={"id": scan_id}, method='POST')
    
    def rerun_scan(self, scan_id: str) -> dict:
        """Rerun a scan.

        Args:
            scan_id (str): Scan ID

        Returns:
            dict: API response
        """
        return self._request(f"rerunscan", params={"id": scan_id}, method='POST')
    
    def get_system_settings(self) -> dict:
        """Get system settings.

        Returns:
            dict: System settings
        """
        result = self._request("optsraw")
        if isinstance(result, list) and len(result) > 1 and result[0] == "SUCCESS":
            self.token = result[1].get('token')
            return result[1].get('data', {})
        return {}
    
    def save_system_settings(self, settings: dict) -> dict:
        """Save system settings.

        Args:
            settings (dict): System settings

        Returns:
            dict: API response
        """
        if not self.token:
            self.get_system_settings()
            
        return self._request("savesettingsraw", method='POST', params={
            "allopts": json.dumps(settings),
            "token": self.token
        })
    
    def reset_system_settings(self) -> dict:
        """Reset system settings.

        Returns:
            dict: API response
        """
        if not self.token:
            self.get_system_settings()
            
        return self._request("savesettingsraw", method='POST', params={
            "allopts": "RESET",
            "token": self.token
        })
    
    def get_event_types(self) -> list:
        """Get list of event types.

        Returns:
            list: Event types
        """
        return self._request("eventtypes")
    
    def get_modules(self) -> list:
        """Get list of modules.

        Returns:
            list: Modules
        """
        return self._request("modules")
    
    def get_correlation_rules(self) -> list:
        """Get list of correlation rules.

        Returns:
            list: Correlation rules
        """
        return self._request("correlationrules")
    
    def get_scan_results(self, scan_id: str, eventType: str = None, filterfp: bool = False) -> list:
        """Get scan results.

        Args:
            scan_id (str): Scan ID
            eventType (str): Event type
            filterfp (bool): Filter false positives

        Returns:
            list: Scan results
        """
        params = {"id": scan_id}
        if eventType:
            params["eventType"] = eventType
        if filterfp:
            params["filterfp"] = "1"
        
        return self._request("scaneventresults", params=params)
    
    def get_scan_correlations(self, scan_id: str) -> list:
        """Get scan correlations.

        Args:
            scan_id (str): Scan ID

        Returns:
            list: Scan correlations
        """
        return self._request("scancorrelations", params={"id": scan_id})


class SpiderFootWebUi:
    """SpiderFoot web interface."""

    lookup = TemplateLookup(directories=[''])
    defaultConfig = dict()
    config = dict()
    token = None
    docroot = ''

    def __init__(self: 'SpiderFootWebUi', web_config: dict, config: dict, loggingQueue: 'logging.handlers.QueueListener' = None) -> None:
        """Initialize web server.

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

        self.docroot = web_config.get('root', '/').rstrip('/')

        # 'config' supplied will be the defaults, let's supplement them
        # now with any configuration which may have previously been saved.
        self.defaultConfig = deepcopy(config)
        dbh = SpiderFootDb(self.defaultConfig, init=True)
        sf = SpiderFoot(self.defaultConfig)
        self.config = sf.configUnserialize(dbh.configGet(), self.defaultConfig)
        
        # Initialize API client - connecting to the API running on the same host
        # Use the web_config to get API host/port details if available, otherwise use defaults
        api_host = web_config.get('api_host', '127.0.0.1')
        api_port = web_config.get('api_port', 8000)  # API server usually runs on port 8000
        api_url = f"http://{api_host}:{api_port}/api"
        self.log = logging.getLogger(f"spiderfoot.{__name__}")
        self.log.info(f"Initializing API client with URL: {api_url}")
        self.api_client = APIClient(api_url)

        # Set up logging
        if loggingQueue is None:
            self.loggingQueue = mp.Queue()
            logListenerSetup(self.loggingQueue, self.config)
        else:
            self.loggingQueue = loggingQueue
        logWorkerSetup(self.loggingQueue)

        cherrypy.config.update({
            'error_page.401': self.error_page_401,
            'error_page.404': self.error_page_404,
            'request.error_response': self.error_page
        })

        csp = (
            secure.ContentSecurityPolicy()
            .default_src("'self'")
            .script_src("'self'", "'unsafe-inline'", "blob:")
            .style_src("'self'", "'unsafe-inline'")
            .base_uri("'self'")
            .connect_src("'self'", "data:")
            .frame_src("'self'", 'data:')
            .img_src("'self'", "data:")
        )

        secure_headers = secure.Secure(
            server=secure.Server().set("server"),
            cache=secure.CacheControl().must_revalidate(),
            csp=csp,
            referrer=secure.ReferrerPolicy().no_referrer(),
        )

        cherrypy.config.update({
            "tools.response_headers.on": True,
            "tools.response_headers.headers": secure_headers.framework.cherrypy()
        })

    def error_page(self: 'SpiderFootWebUi') -> None:
        """Error page."""
        cherrypy.response.status = 500

        if self.config.get('_debug'):
            cherrypy.response.body = _cperror.get_error_page(
                status=500, traceback=_cperror.format_exc())
        else:
            cherrypy.response.body = b"<html><body>Error</body></html>"

    def error_page_401(self: 'SpiderFootWebUi', status: str, message: str, traceback: str, version: str) -> str:
        """Unauthorized access HTTP 401 error page.

        Args:
            status (str): HTTP response status code and message
            message (str): Error message
            traceback (str): Error stack trace
            version (str): CherryPy version

        Returns:
            str: HTML response
        """
        return ""

    def error_page_404(self: 'SpiderFootWebUi', status: str, message: str, traceback: str, version: str) -> str:
        """Not found error page 404.

        Args:
            status (str): HTTP response status code and message
            message (str): Error message
            traceback (str): Error stack trace
            version (str): CherryPy version

        Returns:
            str: HTTP response template
        """
        templ = Template(
            filename='spiderfoot/templates/error.tmpl', lookup=self.lookup)
        return templ.render(message='Not Found', docroot=self.docroot, status=status, version=__version__)

    def jsonify_error(self: 'SpiderFootWebUi', status: str, message: str) -> dict:
        """Jsonify error response.

        Args:
            status (str): HTTP response status code and message
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

    def error(self: 'SpiderFootWebUi', message: str) -> None:
        """Show generic error page with error message.

        Args:
            message (str): error message

        Returns:
            None
        """
        templ = Template(
            filename='spiderfoot/templates/error.tmpl', lookup=self.lookup)
        return templ.render(message=message, docroot=self.docroot, version=__version__)

    def cleanUserInput(self: 'SpiderFootWebUi', inputList: list) -> list:
        """Convert data to HTML entities; except quotes and ampersands.

        Args:
            inputList (list): list of strings to sanitize

        Returns:
            list: sanitized input

        Raises:
            TypeError: inputList type was invalid

        Todo:
            Review all uses of this function, then remove it.
            Use of this function is overloaded.
        """
        if not isinstance(inputList, list):
            raise TypeError(f"inputList is {type(inputList)}; expected list()")

        ret = list()

        for item in inputList:
            if not item:
                ret.append('')
                continue
            c = html.escape(item, True)

            # Decode '&' and '"' HTML entities
            c = c.replace("&amp;", "&").replace("&quot;", "\"")
            ret.append(c)

        return ret

    def searchBase(self: 'SpiderFootWebUi', id: str = None, eventType: str = None, value: str = None) -> list:
        """Search.

        Args:
            id (str): scan ID
            eventType (str): TBD
            value (str): TBD

        Returns:
            list: search results
        """
        retdata = []

        if not id and not eventType and not value:
            return retdata

        if not value:
            value = ''

        regex = ""
        if value.startswith("/") and value.endswith("/"):
            regex = value[1:len(value) - 1]
            value = ""

        value = value.replace('*', '%')
        if value in [None, ""] and regex in [None, ""]:
            value = "%"
            regex = ""

        dbh = SpiderFootDb(self.config)
        criteria = {
            'scan_id': id or '',
            'type': eventType or '',
            'value': value or '',
            'regex': regex or '',
        }

        try:
            data = dbh.search(criteria)
        except Exception:
            return retdata

        for row in data:
            lastseen = time.strftime(
                "%Y-%m-%d %H:%M:%S", time.localtime(row[0]))
            escapeddata = html.escape(row[1])
            escapedsrc = html.escape(row[2])
            retdata.append([lastseen, escapeddata, escapedsrc,
                            row[3], row[5], row[6], row[7], row[8], row[10],
                            row[11], row[4], row[13], row[14]])

        return retdata

    def buildExcel(self: 'SpiderFootWebUi', data: list, columnNames: list, sheetNameIndex: int = 0) -> str:
        """Convert supplied raw data into GEXF (Graph Exchange XML Format)
        format (e.g. for Gephi).

        Args:
            data (list): Scan result as list
            columnNames (list): column names
            sheetNameIndex (int): TBD

        Returns:
            str: Excel workbook
        """
        rowNums = dict()
        workbook = openpyxl.Workbook()
        defaultSheet = workbook.active
        columnNames.pop(sheetNameIndex)
        allowed_sheet_chars = string.ascii_uppercase + string.digits + '_'
        for row in data:
            sheetName = "".join(
                [c for c in str(row.pop(sheetNameIndex)) if c.upper() in allowed_sheet_chars])
            try:
                sheet = workbook[sheetName]
            except KeyError:
                # Create sheet
                workbook.create_sheet(sheetName)
                sheet = workbook[sheetName]
                # Write headers
                for col_num, column_title in enumerate(columnNames, 1):
                    cell = sheet.cell(row=1, column=col_num)
                    cell.value = column_title
                rowNums[sheetName] = 2

            # Write row
            for col_num, cell_value in enumerate(row, 1):
                cell = sheet.cell(row=rowNums[sheetName], column=col_num)
                cell.value = cell_value

            rowNums[sheetName] += 1

        if rowNums:
            workbook.remove(defaultSheet)

        # Sort sheets alphabetically
        workbook._sheets.sort(key=lambda ws: ws.title)

        # Save workbook
        with BytesIO() as f:
            workbook.save(f)
            f.seek(0)
            return f.read()

    #
    # USER INTERFACE PAGES
    #

    @cherrypy.expose
    def scanexportlogs(self: 'SpiderFootWebUi', id: str, dialect: str = "excel") -> bytes:
        """Get scan log.

        Args:
            id (str): scan ID
            dialect (str): CSV dialect (default: excel)

        Returns:
            bytes: scan logs in CSV format
        """
        dbh = SpiderFootDb(self.config)

        try:
            data = dbh.scanLogs(id, None, None, True)
        except Exception:
            return self.error("Scan ID not found.")

        if not data:
            return self.error("Scan ID not found.")

        fileobj = StringIO()
        parser = csv.writer(fileobj, dialect=dialect)
        parser.writerow(["Date", "Component", "Type", "Event", "Event ID"])
        for row in data:
            parser.writerow([
                time.strftime("%Y-%m-%d %H:%M:%S",
                              time.localtime(row[0] / 1000)),
                str(row[1]),
                str(row[2]),
                str(row[3]),
                row[4]
            ])

        cherrypy.response.headers[
            'Content-Disposition'] = f"attachment; filename=SpiderFoot-{id}.log.csv"
        cherrypy.response.headers['Content-Type'] = "application/csv"
        cherrypy.response.headers['Pragma'] = "no-cache"
        return fileobj.getvalue().encode('utf-8')

    @cherrypy.expose
    def scancorrelationsexport(self: 'SpiderFootWebUi', id: str, filetype: str = "csv", dialect: str = "excel") -> str:
        """Get scan correlation data in CSV or Excel format.

        Args:
            id (str): scan ID
            filetype (str): type of file ("xlsx|excel" or "csv")
            dialect (str): CSV dialect (default: excel)

        Returns:
            str: results in CSV or Excel format
        """
        dbh = SpiderFootDb(self.config)

        try:
            scaninfo = dbh.scanInstanceGet(id)
            scan_name = scaninfo[0]
        except Exception:
            return json.dumps(["ERROR", "Could not retrieve info for scan."]).encode('utf-8')

        try:
            correlations = dbh.scanCorrelationList(id)
        except Exception:
            return json.dumps(["ERROR", "Could not retrieve correlations for scan."]).encode('utf-8')

        headings = ["Rule Name", "Correlation", "Risk", "Description"]

        if filetype.lower() in ["xlsx", "excel"]:
            rows = []
            for row in correlations:
                correlation = row[1]
                rule_name = row[2]
                rule_risk = row[3]
                rule_description = row[5]
                rows.append([rule_name, correlation,
                            rule_risk, rule_description])

            if scan_name:
                fname = f"{scan_name}-SpiderFoot-correlations.xlxs"
            else:
                fname = "SpiderFoot-correlations.xlxs"

            cherrypy.response.headers[
                'Content-Disposition'] = f"attachment; filename={fname}"
            cherrypy.response.headers['Content-Type'] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            cherrypy.response.headers['Pragma'] = "no-cache"
            return self.buildExcel(rows, headings, sheetNameIndex=0)

        if filetype.lower() == 'csv':
            fileobj = StringIO()
            parser = csv.writer(fileobj, dialect=dialect)
            parser.writerow(headings)

            for row in correlations:
                correlation = row[1]
                rule_name = row[2]
                rule_risk = row[3]
                rule_description = row[5]
                parser.writerow(
                    [rule_name, correlation, rule_risk, rule_description])

            if scan_name:
                fname = f"{scan_name}-SpiderFoot-correlations.csv"
            else:
                fname = "SpiderFoot-correlations.csv"

            cherrypy.response.headers[
                'Content-Disposition'] = f"attachment; filename={fname}"
            cherrypy.response.headers['Content-Type'] = "application/csv"
            cherrypy.response.headers['Pragma'] = "no-cache"
            return fileobj.getvalue().encode('utf-8')

        return self.error("Invalid export filetype.")

    @cherrypy.expose
    def scaneventresultexport(self: 'SpiderFootWebUi', id: str, type: str, filetype: str = "csv", dialect: str = "excel") -> str:
        """Get scan event result data in CSV or Excel format.

        Args:
            id (str): scan ID
            type (str): TBD
            filetype (str): type of file ("xlsx|excel" or "csv")
            dialect (str): CSV dialect (default: excel)

        Returns:
            str: results in CSV or Excel format
        """
        dbh = SpiderFootDb(self.config)
        data = dbh.scanResultEvent(id, type)

        if filetype.lower() in ["xlsx", "excel"]:
            rows = []
            for row in data:
                if row[4] == "ROOT":
                    continue
                lastseen = time.strftime(
                    "%Y-%m-%d %H:%M:%S", time.localtime(row[0]))
                datafield = str(row[1]).replace(
                    "<SFURL>", "").replace("</SFURL>", "")
                rows.append([lastseen, str(row[4]), str(row[3]),
                            str(row[2]), row[13], datafield])

            fname = "SpiderFoot.xlsx"
            cherrypy.response.headers[
                'Content-Disposition'] = f"attachment; filename={fname}"
            cherrypy.response.headers['Content-Type'] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            cherrypy.response.headers['Pragma'] = "no-cache"
            return self.buildExcel(rows, ["Updated", "Type", "Module", "Source",
                                   "F/P", "Data"], sheetNameIndex=1)

        if filetype.lower() == 'csv':
            fileobj = StringIO()
            parser = csv.writer(fileobj, dialect=dialect)
            parser.writerow(
                ["Updated", "Type", "Module", "Source", "F/P", "Data"])
            for row in data:
                if row[4] == "ROOT":
                    continue
                lastseen = time.strftime(
                    "%Y-%m-%d %H:%M:%S", time.localtime(row[0]))
                datafield = str(row[1]).replace(
                    "<SFURL>", "").replace("</SFURL>", "")
                parser.writerow([lastseen, str(row[4]), str(
                    row[3]), str(row[2]), row[13], datafield])

            fname = "SpiderFoot.csv"
            cherrypy.response.headers[
                'Content-Disposition'] = f"attachment; filename={fname}"
            cherrypy.response.headers['Content-Type'] = "application/csv"
            cherrypy.response.headers['Pragma'] = "no-cache"
            return fileobj.getvalue().encode('utf-8')

        return self.error("Invalid export filetype.")

    @cherrypy.expose
    def scaneventresultexportmulti(self: 'SpiderFootWebUi', ids: str, filetype: str = "csv", dialect: str = "excel") -> str:
        """Get scan event result data in CSV or Excel format for multiple
        scans.

        Args:
            ids (str): comma separated list of scan IDs
            filetype (str): type of file ("xlsx|excel" or "csv")
            dialect (str): CSV dialect (default: excel)

        Returns:
            str: results in CSV or Excel format
        """
        dbh = SpiderFootDb(self.config)
        scaninfo = dict()
        data = list()
        scan_name = ""

        for id in ids.split(','):
            scaninfo[id] = dbh.scanInstanceGet(id)
            if scaninfo[id] is None:
                continue
            scan_name = scaninfo[id][0]
            data = data + dbh.scanResultEvent(id)

        if not data:
            return None

        if filetype.lower() in ["xlsx", "excel"]:
            rows = []
            for row in data:
                if row[4] == "ROOT":
                    continue
                lastseen = time.strftime(
                    "%Y-%m-%d %H:%M:%S", time.localtime(row[0]))
                datafield = str(row[1]).replace(
                    "<SFURL>", "").replace("</SFURL>", "")
                rows.append([scaninfo[row[12]][0], lastseen, str(row[4]), str(row[3]),
                            str(row[2]), row[13], datafield])

            if len(ids.split(',')) > 1 or scan_name == "":
                fname = "SpiderFoot.xlsx"
            else:
                fname = scan_name + "-SpiderFoot.xlsx"

            cherrypy.response.headers[
                'Content-Disposition'] = f"attachment; filename={fname}"
            cherrypy.response.headers['Content-Type'] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            cherrypy.response.headers['Pragma'] = "no-cache"
            return self.buildExcel(rows, ["Scan Name", "Updated", "Type", "Module",
                                   "Source", "F/P", "Data"], sheetNameIndex=2)

        if filetype.lower() == 'csv':
            fileobj = StringIO()
            parser = csv.writer(fileobj, dialect=dialect)
            parser.writerow(["Scan Name", "Updated", "Type",
                            "Module", "Source", "F/P", "Data"])
            for row in data:
                if row[4] == "ROOT":
                    continue
                lastseen = time.strftime(
                    "%Y-%m-%d %H:%M:%S", time.localtime(row[0]))
                datafield = str(row[1]).replace(
                    "<SFURL>", "").replace("</SFURL>", "")
                parser.writerow([scaninfo[row[12]][0], lastseen, str(row[4]), str(row[3]),
                                str(row[2]), row[13], datafield])

            if len(ids.split(',')) > 1 or scan_name == "":
                fname = "SpiderFoot.csv"
            else:
                fname = scan_name + "-SpiderFoot.csv"

            cherrypy.response.headers[
                'Content-Disposition'] = f"attachment; filename={fname}"
            cherrypy.response.headers['Content-Type'] = "application/csv"
            cherrypy.response.headers['Pragma'] = "no-cache"
            return fileobj.getvalue().encode('utf-8')

        return self.error("Invalid export filetype.")

    @cherrypy.expose
    def scansearchresultexport(self: 'SpiderFootWebUi', id: str, eventType: str = None, value: str = None, filetype: str = "csv", dialect: str = "excel") -> str:
        """Get search result data in CSV or Excel format.

        Args:
            id (str): scan ID
            eventType (str): TBD
            value (str): TBD
            filetype (str): type of file ("xlsx|excel" or "csv")
            dialect (str): CSV dialect (default: excel)

        Returns:
            str: results in CSV or Excel format
        """
        data = self.searchBase(id, eventType, value)

        if not data:
            return None

        if filetype.lower() in ["xlsx", "excel"]:
            rows = []
            for row in data:
                if row[10] == "ROOT":
                    continue
                datafield = str(row[1]).replace(
                    "<SFURL>", "").replace("</SFURL>", "")
                rows.append([row[0], str(row[10]), str(row[3]),
                            str(row[2]), row[11], datafield])
            cherrypy.response.headers['Content-Disposition'] = "attachment; filename=SpiderFoot.xlsx"
            cherrypy.response.headers['Content-Type'] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            cherrypy.response.headers['Pragma'] = "no-cache"
            return self.buildExcel(rows, ["Updated", "Type", "Module", "Source",
                                   "F/P", "Data"], sheetNameIndex=1)

        if filetype.lower() == 'csv':
            fileobj = StringIO()
            parser = csv.writer(fileobj, dialect=dialect)
            parser.writerow(
                ["Updated", "Type", "Module", "Source", "F/P", "Data"])
            for row in data:
                if row[10] == "ROOT":
                    continue
                datafield = str(row[1]).replace(
                    "<SFURL>", "").replace("</SFURL>", "")
                parser.writerow([row[0], str(row[10]), str(
                    row[3]), str(row[2]), row[11], datafield])
            cherrypy.response.headers['Content-Disposition'] = "attachment; filename=SpiderFoot.csv"
            cherrypy.response.headers['Content-Type'] = "application/csv"
            cherrypy.response.headers['Pragma'] = "no-cache"
            return fileobj.getvalue().encode('utf-8')

        return self.error("Invalid export filetype.")

    @cherrypy.expose
    def scanexportjsonmulti(self: 'SpiderFootWebUi', ids: str) -> str:
        """Get scan event result data in JSON format for multiple scans.

        Args:
            ids (str): comma separated list of scan IDs

        Returns:
            str: results in JSON format
        """
        dbh = SpiderFootDb(self.config)
        scaninfo = list()
        scan_name = ""

        for id in ids.split(','):
            scan = dbh.scanInstanceGet(id)

            if scan is None:
                continue

            scan_name = scan[0]

            for row in dbh.scanResultEvent(id):
                lastseen = time.strftime(
                    "%Y-%m-%d %H:%M:%S", time.localtime(row[0]))
                event_data = str(row[1]).replace(
                    "<SFURL>", "").replace("</SFURL>", "")
                source_data = str(row[2])
                source_module = str(row[3])
                event_type = row[4]
                false_positive = row[13]

                if event_type == "ROOT":
                    continue

                scaninfo.append({
                    "data": event_data,
                    "event_type": event_type,
                    "module": source_module,
                    "source_data": source_data,
                    "false_positive": false_positive,
                    "last_seen": lastseen,
                    "scan_name": scan_name,
                    "scan_target": scan[1]
                })

        if len(ids.split(',')) > 1 or scan_name == "":
            fname = "SpiderFoot.json"
        else:
            fname = scan_name + "-SpiderFoot.json"

        cherrypy.response.headers[
            'Content-Disposition'] = f"attachment; filename={fname}"
        cherrypy.response.headers['Content-Type'] = "application/json; charset=utf-8"
        cherrypy.response.headers['Pragma'] = "no-cache"
        return json.dumps(scaninfo).encode('utf-8')

    @cherrypy.expose
    def scanviz(self: 'SpiderFootWebUi', id: str, gexf: str = "0") -> str:
        """Export entities from scan results for visualising.

        Args:
            id (str): scan ID
            gexf (str): TBD

        Returns:
            str: GEXF data
        """
        if not id:
            return None

        dbh = SpiderFootDb(self.config)
        data = dbh.scanResultEvent(id, filterFp=True)
        scan = dbh.scanInstanceGet(id)

        if not scan:
            return None

        scan_name = scan[0]

        root = scan[1]

        if gexf == "0":
            return SpiderFootHelpers.buildGraphJson([root], data)

        if not scan_name:
            fname = "SpiderFoot.gexf"
        else:
            fname = scan_name + "SpiderFoot.gexf"

        cherrypy.response.headers[
            'Content-Disposition'] = f"attachment; filename={fname}"
        cherrypy.response.headers['Content-Type'] = "application/gexf"
        cherrypy.response.headers['Pragma'] = "no-cache"
        return SpiderFootHelpers.buildGraphGexf([root], "SpiderFoot Export", data)

    @cherrypy.expose
    def scanvizmulti(self: 'SpiderFootWebUi', ids: str, gexf: str = "1") -> str:
        """Export entities results from multiple scans in GEXF format.

        Args:
            ids (str): scan IDs
            gexf (str): TBD

        Returns:
            str: GEXF data
        """
        dbh = SpiderFootDb(self.config)
        data = list()
        roots = list()
        scan_name = ""

        if not ids:
            return None

        for id in ids.split(','):
            scan = dbh.scanInstanceGet(id)
            if not scan:
                continue
            data = data + dbh.scanResultEvent(id, filterFp=True)
            roots.append(scan[1])
            scan_name = scan[0]

        if not data:
            return None

        if gexf == "0":
            # Not implemented yet
            return None

        if len(ids.split(',')) > 1 or scan_name == "":
            fname = "SpiderFoot.gexf"
        else:
            fname = scan_name + "-SpiderFoot.gexf"

        cherrypy.response.headers[
            'Content-Disposition'] = f"attachment; filename={fname}"
        cherrypy.response.headers['Content-Type'] = "application/gexf"
        cherrypy.response.headers['Pragma'] = "no-cache"
        return SpiderFootHelpers.buildGraphGexf(roots, "SpiderFoot Export", data)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def scanopts(self: 'SpiderFootWebUi', id: str) -> dict:
        """Return configuration used for the specified scan as JSON.

        Args:
            id: scan ID

        Returns:
            dict: scan options for the specified scan
        """
        dbh = SpiderFootDb(self.config)
        ret = dict()

        meta = dbh.scanInstanceGet(id)
        if not meta:
            return ret

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
        for key in list(ret['config'].keys()):
            if ':' not in key:
                globaloptdescs = self.config['__globaloptdescs__']
                if globaloptdescs:
                    ret['configdesc'][key] = globaloptdescs.get(
                        key, f"{key} (legacy)")
            else:
                [modName, modOpt] = key.split(':')
                if modName not in list(self.config['__modules__'].keys()):
                    continue

                if modOpt not in list(self.config['__modules__'][modName]['optdescs'].keys()):
                    continue

                ret['configdesc'][key] = self.config['__modules__'][modName]['optdescs'][modOpt]

        return ret

    @cherrypy.expose
    def rerunscan(self: 'SpiderFootWebUi', id: str) -> None:
        """Rerun a scan.

        Args:
            id (str): scan ID

        Returns:
            None

        Raises:
            HTTPRedirect: redirect to info page for new scan
        """
        # Use the API client to rerun the scan
        try:
            result = self.api_client.rerun_scan(id)
            
            if "error" in result:
                return self.error(result["error"].get("message", "Failed to rerun scan"))
                
            # Extract the new scan ID
            new_scan_id = result.get("scan_id")
            if not new_scan_id:
                return self.error("API returned success but no scan ID was provided")
                
            # Redirect to the new scan's info page
            raise cherrypy.HTTPRedirect(
                f"{self.docroot}/scaninfo?id={new_scan_id}", status=302)
                
        except Exception as e:
            self.log.error(f"Error rerunning scan: {e}", exc_info=True)
            return self.error(f"Error rerunning scan: {e}")

    @cherrypy.expose
    def rerunscanmulti(self: 'SpiderFootWebUi', ids: str) -> str:
        """Rerun scans.

        Args:
            ids (str): comma separated list of scan IDs

        Returns:
            str: Scan list page HTML
        """
        # Snapshot the current configuration to be used by the scan
        cfg = deepcopy(self.config)
        modlist = list()
        dbh = SpiderFootDb(cfg)

        for id in ids.split(","):
            info = dbh.scanInstanceGet(id)
            if not info:
                return self.error("Invalid scan ID.")

            scanconfig = dbh.scanConfigGet(id)
            scanname = info[0]
            scantarget = info[1]
            targetType = None

            if len(scanconfig) == 0:
                return self.error("Something went wrong internally.")

            modlist = scanconfig['_modulesenabled'].split(',')
            if "sfp__stor_stdout" in modlist:
                modlist.remove("sfp__stor_stdout")

            targetType = SpiderFootHelpers.targetTypeFromString(scantarget)
            if targetType is None:
                # Should never be triggered for a re-run scan..
                return self.error("Invalid target type. Could not recognize it as a target SpiderFoot supports.")

            # Start running a new scan
            scanId = SpiderFootHelpers.genScanInstanceId()
            try:
                p = mp.Process(target=startSpiderFootScanner, args=(
                    self.loggingQueue, scanname, scanId, scantarget, targetType, modlist, cfg))
                p.daemon = True
                p.start()
            except Exception as e:
                self.log.error(
                    f"[-] Scan [{scanId}] failed: {e}", exc_info=True)
                return self.error(f"[-] Scan [{scanId}] failed: {e}")

            # Wait until the scan has initialized
            while dbh.scanInstanceGet(scanId) is None:
                self.log.info("Waiting for the scan to initialize...")
                time.sleep(1)

        templ = Template(
            filename='spiderfoot/templates/scanlist.tmpl', lookup=self.lookup)
        return templ.render(rerunscans=True, docroot=self.docroot, pageid="SCANLIST", version=__version__)

    @cherrypy.expose
    def newscan(self: 'SpiderFootWebUi') -> str:
        """Configure a new scan.

        Returns:
            str: New scan page HTML
        """
        dbh = SpiderFootDb(self.config)
        types = dbh.eventTypes()
        templ = Template(
            filename='spiderfoot/templates/newscan.tmpl', lookup=self.lookup)
        return templ.render(pageid='NEWSCAN', types=types, docroot=self.docroot,
                            modules=self.config['__modules__'], scanname="",
                            selectedmods="", scantarget="", version=__version__)

    @cherrypy.expose
    def clonescan(self: 'SpiderFootWebUi', id: str) -> str:
        """Clone an existing scan (pre-selected options in the newscan page).

        Args:
            id (str): scan ID to clone

        Returns:
            str: New scan page HTML pre-populated with options from cloned scan.
        """
        dbh = SpiderFootDb(self.config)
        types = dbh.eventTypes()
        info = dbh.scanInstanceGet(id)

        if not info:
            return self.error("Invalid scan ID.")

        scanconfig = dbh.scanConfigGet(id)
        scanname = info[0]
        scantarget = info[1]
        targetType = None

        if scanname == "" or scantarget == "" or len(scanconfig) == 0:
            return self.error("Something went wrong internally.")

        targetType = SpiderFootHelpers.targetTypeFromString(scantarget)
        if targetType is None:
            # It must be a name, so wrap quotes around it
            scantarget = "&quot;" + scantarget + "&quot;"

        modlist = scanconfig['_modulesenabled'].split(',')

        templ = Template(
            filename='spiderfoot/templates/newscan.tmpl', lookup=self.lookup)
        return templ.render(pageid='NEWSCAN', types=types, docroot=self.docroot,
                            modules=self.config['__modules__'], selectedmods=modlist,
                            scanname=str(scanname),
                            scantarget=str(scantarget), version=__version__)

    @cherrypy.expose
    def scaninfo(self: 'SpiderFootWebUi', id: str) -> str:
        """Information about a selected scan.

        Args:
            id (str): scan id

        Returns:
            str: scan info page HTML
        """
        # Use API client to get scan status
        result = self.api_client.scan_status(id)
        
        if "error" in result:
            return self.error(f"Scan ID not found: {id}")
        
        name = result[0]
        status = result[5]

        templ = Template(filename='spiderfoot/templates/scaninfo.tmpl',
                         lookup=self.lookup, input_encoding='utf-8')
        return templ.render(id=id, name=html.escape(name), status=status, 
                           docroot=self.docroot, version=__version__, pageid="SCANLIST")

    @cherrypy.expose
    def index(self: 'SpiderFootWebUi') -> str:
        """Show scan list page.

        Returns:
            str: Scan list page HTML
        """
        templ = Template(
            filename='spiderfoot/templates/scanlist.tmpl', lookup=self.lookup)
        return templ.render(pageid='SCANLIST', docroot=self.docroot, version=__version__)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def scanlog(self: 'SpiderFootWebUi', id: str, limit: str = None, rowId: str = None, reverse: str = None) -> list:
        """Scan log data.

        Args:
            id (str): scan ID
            limit (str): TBD
            rowId (str): TBD
            reverse (str): TBD

        Returns:
            list: scan log
        """
        dbh = SpiderFootDb(self.config)
        retdata = []

        try:
            data = dbh.scanLogs(id, limit, rowId, reverse)
        except Exception:
            return retdata

        for row in data:
            generated = time.strftime(
                "%Y-%m-%d %H:%M:%S", time.localtime(row[0] / 1000))
            retdata.append([generated, row[1], row[2],
                           html.escape(row[3]), row[4]])

        return retdata

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def scanerrors(self: 'SpiderFootWebUi', id: str, limit: str = None) -> list:
        """Scan error data.

        Args:
            id (str): scan ID
            limit (str): limit number of results

        Returns:
            list: scan errors
        """
        dbh = SpiderFootDb(self.config)
        retdata = []

        try:
            data = dbh.scanErrors(id, limit)
        except Exception:
            return retdata

        for row in data:
            generated = time.strftime(
                "%Y-%m-%d %H:%M:%S", time.localtime(row[0] / 1000))
            retdata.append([generated, row[1], html.escape(str(row[2]))])

        return retdata

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def scanlist(self: 'SpiderFootWebUi') -> list:
        """Produce a list of scans.

        Returns:
            list: scan list
        """
        # Use API client to get scan list
        result = self.api_client.scan_list()
        
        if "error" in result:
            self.log.error(f"Error fetching scan list: {result['error']['message']}")
            return []
            
        return result

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def scandelete(self: 'SpiderFootWebUi', id: str) -> str:
        """Delete scan(s).

        Args:
            id (str): comma separated list of scan IDs

        Returns:
            str: JSON response
        """
        if not id:
            return self.jsonify_error('404', "No scan specified")

        # Use API client to delete scans
        result = self.api_client.scan_delete(id)
        
        if "error" in result:
            return self.jsonify_error(result["error"].get("http_status", "500"), 
                                      result["error"].get("message", "Unknown error"))
                                      
        return result

    @cherrypy.expose
    def savesettings(self: 'SpiderFootWebUi', allopts: str, token: str, configFile: 'cherrypy._cpreqbody.Part' = None) -> None:
        """Save settings, also used to completely reset them to default.

        Args:
            allopts: TBD
            token (str): CSRF token
            configFile (cherrypy._cpreqbody.Part): TBD

        Returns:
            None

        Raises:
            HTTPRedirect: redirect to scan settings
        """
        if str(token) != str(self.token):
            return self.error(f"Invalid token ({token})")

        # configFile seems to get set even if a file isn't uploaded
        if configFile and configFile.file:
            try:
                contents = configFile.file.read()

                if isinstance(contents, bytes):
                    contents = contents.decode('utf-8')

                tmp = dict()
                for line in contents.split("\n"):
                    if "=" not in line:
                        continue

                    opt_array = line.strip().split("=")
                    if len(opt_array) == 1:
                        opt_array[1] = ""

                    tmp[opt_array[0]] = '='.join(opt_array[1:])

                allopts = json.dumps(tmp).encode('utf-8')
            except Exception as e:
                return self.error(f"Failed to parse input file. Was it generated from SpiderFoot? ({e})")

        # Reset config to default
        if allopts == "RESET":
            try:
                # Use API client to reset settings
                result = self.api_client._request("savesettingsraw", method='POST', params={
                    "allopts": "RESET",
                    "token": self.token
                })
                
                if "error" in result:
                    return self.error(f"Failed to reset settings: {result['error'].get('message', 'Unknown error')}")
                    
                raise cherrypy.HTTPRedirect(f"{self.docroot}/opts?updated=1")
            except Exception as e:
                if isinstance(e, cherrypy.HTTPRedirect):
                    raise
                self.log.error(f"Error resetting settings via API: {e}", exc_info=True)
                return self.error(f"Failed to reset settings: {e}")
                
        # Save settings
        try:
            # Use API client to save settings
            result = self.api_client._request("savesettingsraw", method='POST', params={
                "allopts": allopts,
                "token": self.token
            })
            
            if "error" in result:
                return self.error(f"Failed to save settings: {result['error'].get('message', 'Unknown error')}")
                
            raise cherrypy.HTTPRedirect(f"{self.docroot}/opts?updated=1")
            
        except Exception as e:
            if isinstance(e, cherrypy.HTTPRedirect):
                raise
            self.log.error(f"Error saving settings via API: {e}", exc_info=True)
            return self.error(f"Failed to save settings: {e}")

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def savesettingsraw(self: 'SpiderFootWebUi', allopts: str, token: str) -> str:
        """Save settings, also used to completely reset them to default.

        Args:
            allopts: TBD
            token (str): CSRF token

        Returns:
            str: save success as JSON
        """
        cherrypy.response.headers['Content-Type'] = "application/json; charset=utf-8"

        if str(token) != str(self.token):
            return json.dumps(["ERROR", f"Invalid token ({token})."]).encode('utf-8')

        try:
            # Use API client to save settings
            result = self.api_client._request("savesettingsraw", method='POST', params={
                "allopts": allopts,
                "token": self.token
            })
            
            if "error" in result:
                return json.dumps(["ERROR", result["error"].get("message", "Unknown error")]).encode('utf-8')
                
            return json.dumps(["SUCCESS", ""]).encode('utf-8')
            
        except Exception as e:
            self.log.error(f"Error saving settings via API: {e}", exc_info=True)
            return json.dumps(["ERROR", f"Processing one or more of your inputs failed: {e}"]).encode('utf-8')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def resultsetfp(self: 'SpiderFootWebUi', id: str, resultids: str, fp: str) -> str:
        """Set a bunch of results (hashes) as false positive.

        Args:
            id (str): scan ID
            resultids (str): comma separated list of result IDs (hashes)
            fp (str): 0 or 1

        Returns:
            str: set false positive status as JSON
        """
        cherrypy.response.headers['Content-Type'] = "application/json; charset=utf-8"

        # Make API request to set false positive status
        try:
            result = self.api_client._request("resultsetfp", method='POST', params={
                "id": id,
                "resultids": resultids,
                "fp": fp
            })
            
            if "error" in result:
                return json.dumps(["ERROR", result["error"].get("message", "Unknown error")]).encode('utf-8')
                
            if isinstance(result, list) and len(result) > 0 and result[0] == "SUCCESS":
                return json.dumps(["SUCCESS", ""]).encode('utf-8')
                
            return json.dumps(["ERROR", "Unexpected API response"]).encode('utf-8')
            
        except Exception as e:
            self.log.error(f"Error setting FP status via API: {e}", exc_info=True)
            
            # Fallback to direct database access
            dbh = SpiderFootDb(self.config)

            if fp not in ["0", "1"]:
                return json.dumps(["ERROR", "No FP flag set or not set correctly."]).encode('utf-8')

            try:
                ids = json.loads(resultids)
            except Exception:
                return json.dumps(["ERROR", "No IDs supplied."]).encode('utf-8')

            # Cannot set FPs if a scan is not completed
            status = dbh.scanInstanceGet(id)
            if not status:
                return self.error(f"Invalid scan ID: {id}")

            if status[5] not in ["ABORTED", "FINISHED", "ERROR-FAILED"]:
                return json.dumps([
                    "WARNING",
                    "Scan must be in a finished state when setting False Positives."
                ]).encode('utf-8')

            # Make sure the user doesn't set something as non-FP when the
            # parent is set as an FP.
            if fp == "0":
                data = dbh.scanElementSourcesDirect(id, ids)
                for row in data:
                    if str(row[14]) == "1":
                        return json.dumps([
                            "WARNING",
                            f"Cannot unset element {id} as False Positive if a parent element is still False Positive."
                        ]).encode('utf-8')

            # Set all the children as FPs too.. it's only logical afterall, right?
            childs = dbh.scanElementChildrenAll(id, ids)
            allIds = ids + childs

            ret = dbh.scanResultsUpdateFP(id, allIds, fp)
            if ret:
                return json.dumps(["SUCCESS", ""]).encode('utf-8')

            return json.dumps(["ERROR", "Exception encountered."]).encode('utf-8')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def eventtypes(self: 'SpiderFootWebUi') -> list:
        """List all event types.

        Returns:
            list: list of event types
        """
        cherrypy.response.headers['Content-Type'] = "application/json; charset=utf-8"
        
        try:
            # Use API client to get event types
            result = self.api_client.get_event_types()
            
            if "error" in result:
                self.log.error(f"Error fetching event types via API: {result['error']['message']}")
                # Fall back to direct DB access
                raise Exception("API error")
                
            # Format the API response for the UI
            ret = list()
            for event_type in result:
                ret.append([event_type['descr'], event_type['name']])
                
            return sorted(ret, key=itemgetter(0))
            
        except Exception as e:
            self.log.error(f"Error getting event types via API: {e}", exc_info=True)
            
            # Fallback to direct DB access
            dbh = SpiderFootDb(self.config)
            types = dbh.eventTypes()
            ret = list()

            for r in types:
                ret.append([r[1], r[0]])

            return sorted(ret, key=itemgetter(0))

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def modules(self: 'SpiderFootWebUi') -> list:
        """List all modules.

        Returns:
            list: list of modules
        """
        cherrypy.response.headers['Content-Type'] = "application/json; charset=utf-8"
        
        try:
            # Use API client to get modules
            result = self.api_client.get_modules()
            
            if "error" in result:
                self.log.error(f"Error fetching modules via API: {result['error']['message']}")
                # Fall back to direct DB access
                raise Exception("API error")
                
            return result
            
        except Exception as e:
            self.log.error(f"Error getting modules via API: {e}", exc_info=True)
            
            # Fallback to direct module access
            ret = list()
            modinfo = list(self.config['__modules__'].keys())
            
            if not modinfo:
                return ret

            modinfo.sort()

            for m in modinfo:
                if "__" in m:
                    continue
                ret.append({
                    'name': m, 
                    'descr': self.config['__modules__'][m].get('descr', 'No description available.')
                })

            return ret

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def correlationrules(self: 'SpiderFootWebUi') -> list:
        """List all correlation rules.

        Returns:
            list: list of correlation rules
        """
        cherrypy.response.headers['Content-Type'] = "application/json; charset=utf-8"
        
        try:
            # Use API client to get correlation rules
            result = self.api_client.get_correlation_rules()
            
            if "error" in result:
                self.log.error(f"Error fetching correlation rules via API: {result['error']['message']}")
                # Fall back to direct rule access
                raise Exception("API error")
                
            return result
            
        except Exception as e:
            self.log.error(f"Error getting correlation rules via API: {e}", exc_info=True)
            
            # Fallback to direct access
            ret = list()
            rules = self.config.get('__correlationrules__')
            
            if not rules:
                return ret

            for r in rules:
                meta = r.get('meta', {})
                ret.append({
                    'id': r.get('id', 'Unknown ID'),
                    'name': meta.get('name', 'Unknown Name'),
                    'descr': meta.get('description', 'No description available.'),
                    'risk': meta.get('risk', 'Unknown')
                })

            return sorted(ret, key=itemgetter('name'))

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def ping(self: 'SpiderFootWebUi') -> list:
        """For the CLI to test connectivity to this server.

        Returns:
            list: SpiderFoot version as JSON
        """
        return ["SUCCESS", __version__]

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def query(self: 'SpiderFootWebUi', query: str) -> str:
        """For the CLI to run queries against the database.

        Args:
            query (str): SQL query

        Returns:
            str: query results as JSON
        """
        dbh = SpiderFootDb(self.config)

        if not query:
            return self.jsonify_error('400', "Invalid query.")

        if not query.lower().startswith("select"):
            # Use jsonify_error for consistency
            return self.jsonify_error('400', "Non-SELECTs are unpredictable and not recommended.")

        try:
            ret = dbh.dbh.execute(query)
            data = ret.fetchall()
            columnNames = [c[0] for c in dbh.dbh.description]
            return [dict(zip(columnNames, row)) for row in data]
        except Exception as e:
            # Use jsonify_error for consistency
            return self.jsonify_error('500', str(e))

    @cherrypy.expose
    def startscan(self: 'SpiderFootWebUi', scanname: str, scantarget: str, modulelist: str, typelist: str, usecase: str) -> str:
        """Initiate a scan.

        Args:
            scanname (str): scan name
            scantarget (str): scan target
            modulelist (str): comma separated list of modules to use
            typelist (str): selected modules based on produced event data types
            usecase (str): selected module group (passive, investigate, footprint, all)

        Returns:
            str: start scan status as JSON

        Raises:
            HTTPRedirect: redirect to new scan info page
        """
        scanname = self.cleanUserInput([scanname])[0]
        scantarget = self.cleanUserInput([scantarget])[0]

        if not scanname:
            if cherrypy.request.headers.get('Accept') and 'application/json' in cherrypy.request.headers.get('Accept'):
                cherrypy.response.headers['Content-Type'] = 'application/json'
                return json.dumps({"error": {"message": "Scan name was not specified."}}).encode('utf-8')
            return self.error("Invalid request: scan name was not specified.")

        if not scantarget:
            if cherrypy.request.headers.get('Accept') and 'application/json' in cherrypy.request.headers.get('Accept'):
                cherrypy.response.headers['Content-Type'] = 'application/json'
                return json.dumps({"error": {"message": "Scan target was not specified."}}).encode('utf-8')
            return self.error("Invalid request: scan target was not specified.")

        if not typelist and not modulelist and not usecase:
            if cherrypy.request.headers.get('Accept') and 'application/json' in cherrypy.request.headers.get('Accept'):
                cherrypy.response.headers['Content-Type'] = 'application/json'
                return json.dumps({"error": {"message": "No modules specified for scan."}}).encode('utf-8')
            return self.error("Invalid request: no modules specified for scan.")

        # Use the API client to start the scan
        try:
            # Pass the parameters to the API client
            result = self.api_client.start_scan(
                scanname=scanname,
                scantarget=scantarget,
                modulelist=modulelist.replace('module_', '') if modulelist else None,
                typelist=typelist.replace('type_', '') if typelist else None,
                usecase=usecase if usecase else None
            )
            
            if "error" in result:
                if cherrypy.request.headers.get('Accept') and 'application/json' in cherrypy.request.headers.get('Accept'):
                    cherrypy.response.headers['Content-Type'] = 'application/json'
                    return json.dumps(result).encode('utf-8')
                return self.error(result["error"]["message"])
            
            # Extract the scan ID
            scan_id = result.get("scan_id")
            
            if cherrypy.request.headers.get('Accept') and 'application/json' in cherrypy.request.headers.get('Accept'):
                cherrypy.response.headers['Content-Type'] = "application/json; charset=utf-8"
                return json.dumps(["SUCCESS", scan_id]).encode('utf-8')
            
            # Redirect to scan info page
            raise cherrypy.HTTPRedirect(f"{self.docroot}/scaninfo?id={scan_id}")
            
        except Exception as e:
            self.log.error(f"Error starting scan: {e}", exc_info=True)
            if cherrypy.request.headers.get('Accept') and 'application/json' in cherrypy.request.headers.get('Accept'):
                cherrypy.response.headers['Content-Type'] = 'application/json'
                return json.dumps({"error": {"message": f"Error starting scan: {e}"}}).encode('utf-8')
            return self.error(f"Error starting scan: {e}")

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def stopscan(self: 'SpiderFootWebUi', id: str) -> dict:
        """Stop a scan.

        Args:
            id (str): comma separated list of scan IDs

        Returns:
            dict: JSON response
        """
        if not id:
            return self.jsonify_error('404', "No scan specified")
        
        # Use the API client to stop the scan
        result = self.api_client.stop_scan(id)
        
        if "error" in result:
            return self.jsonify_error(result["error"].get("http_status", "500"), result["error"].get("message", "Unknown error"))
        
        return result

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def vacuum(self):
        """Clean database of old data."""
        try:
            # Use API client to vacuum the database
            result = self.api_client._request("vacuum", method='POST')
            
            if "error" in result:
                raise Exception(result["error"].get("message", "API error"))
                
            if result.get("status") == "SUCCESS":
                return ["SUCCESS", ""]
            
            return self.jsonify_error('500', "Vacuuming the database failed")
            
        except Exception as e:
            self.log.error(f"Error vacuuming DB via API: {e}", exc_info=True)
            
            # Fallback to direct database access
            dbh = SpiderFootDb(self.config)
            try:
                if dbh.vacuumDB():
                    return ["SUCCESS", ""]
                return self.jsonify_error('500', "Vacuuming the database failed")
            except Exception as ex:
                return self.jsonify_error('500', f"Vacuuming the database failed: {ex}")

    #
    # DATA PROVIDERS
    #

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def scaneventresults(self: 'SpiderFootWebUi', id: str, eventType: str = None, filterfp: bool = False, correlationId: str = None) -> list:
        """Return all event results for a scan as JSON.

        Args:
            id (str): scan ID
            eventType (str): filter by event type
            filterfp (bool): remove false positives from search results
            correlationId (str): filter by events associated with a correlation

        Returns:
            list: scan results
        """
        retdata = []

        # Use the API client to get scan results
        try:
            # Convert filterfp parameter to boolean
            filter_fp = False
            if filterfp:
                if isinstance(filterfp, bool):
                    filter_fp = filterfp
                else:
                    filter_fp = str(filterfp).lower() in ["1", "true", "yes"]
            
            # Make the API call
            results = self.api_client.get_scan_results(id, eventType, filter_fp)
            
            if "error" in results:
                self.log.error(f"Error fetching scan results via API: {results['error']['message']}")
                return retdata
                
            # Process the API response
            for row in results:
                # Ensure we have the right data structure
                if not isinstance(row, list) or len(row) < 11:
                    continue
                    
                lastseen = row[0]  # The API already formats this as a string
                retdata.append([
                    lastseen,
                    html.escape(row[1]),
                    html.escape(row[2]),
                    row[3],
                    row[5],
                    row[6],
                    row[7],
                    row[8],
                    row[9],
                    row[10],
                    row[4]
                ])
            
            return retdata
                
        except Exception as e:
            self.log.error(f"Error getting scan results via API: {e}", exc_info=True)
            
            # Fallback to direct DB access
            dbh = SpiderFootDb(self.config)
            
            try:
                data = dbh.scanResultEvent(
                    id, eventType if eventType else 'ALL', filterfp, correlationId=correlationId)
            except Exception as e:
                self.log.error(f"Error getting scan results from DB: {e}", exc_info=True)
                return retdata

            for row in data:
                lastseen = time.strftime(
                    "%Y-%m-%d %H:%M:%S", time.localtime(row[0]))
                retdata.append([
                    lastseen,
                    html.escape(row[1]),
                    html.escape(row[2]),
                    row[3],
                    row[5],
                    row[6],
                    row[7],
                    row[8],
                    row[13],
                    row[14],
                    row[4]
                ])

            return retdata

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def scancorrelations(self: 'SpiderFootWebUi', id: str) -> list:
        """Correlation results from a scan.

        Args:
            id (str): scan ID

        Returns:
            list: correlation result list or error message
        """
        # Use the API client to get scan correlations
        try:
            correlations = self.api_client.get_scan_correlations(id)
            
            if "error" in correlations:
                self.log.error(f"Error fetching correlations via API: {correlations['error']['message']}")
                return []
                
            return correlations
                
        except Exception as e:
            self.log.error(f"Error getting correlations via API: {e}", exc_info=True)
            
            # Fallback to direct DB access
            retdata = []
            dbh = SpiderFootDb(self.config)

            try:
                self.log.debug(f"Fetching correlations for scan {id}")
                corrdata = dbh.scanCorrelationList(id)
                self.log.debug(f"Found {len(corrdata)} correlations")

                if not corrdata:
                    self.log.debug(f"No correlations found for scan {id}")
                    return retdata

                for row in corrdata:
                    # Check if we have a valid row of data
                    if len(row) < 6:  # Need at least 6 elements to extract all required fields
                        self.log.error(
                            f"Correlation data format error: missing required fields, got {len(row)} fields")
                        continue

                    # Extract specific fields based on their indices
                    correlation_id = row[0]
                    correlation = row[1]
                    rule_name = row[2]
                    rule_risk = row[3]
                    rule_id = row[4]
                    rule_description = row[5]
                    events = row[6] if len(row) > 6 else ""
                    created = row[7] if len(row) > 7 else ""

                    retdata.append([correlation_id, correlation, rule_name, rule_risk,
                                rule_id, rule_description, events, created])

            except Exception as e:
                self.log.error(
                    f"Error fetching correlations for scan {id}: {e}", exc_info=True)

            return retdata

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def search(self: 'SpiderFootWebUi', id: str = None, eventType: str = None, value: str = None) -> list:
        """Search scans.

        Args:
            id (str): filter search results by scan ID
            eventType (str): filter search results by event type
            value (str): filter search results by event value

        Returns:
            list: search results
        """
        try:
            # Use the API client's search functionality if implemented
            # Since the searchBase method contains complex logic, we'll keep using it for now
            # This is a good candidate for future API implementation
            return self.searchBase(id, eventType, value)
        except Exception as e:
            self.log.error(f"Error searching via API: {e}", exc_info=True)
            return []

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def scanhistory(self: 'SpiderFootWebUi', id: str) -> list:
        """Historical data for a scan.

        Args:
            id (str): scan ID

        Returns:
            list: scan history
        """
        if not id:
            return self.jsonify_error('404', "No scan specified")

        # Try to use API client to get scan history if implemented
        try:
            result = self.api_client._request("scanhistory", params={"id": id})
            
            if "error" in result:
                # Fall back to direct DB access
                raise Exception(result["error"].get("message", "API error"))
                
            return result
            
        except Exception as e:
            self.log.error(f"Error getting scan history via API: {e}", exc_info=True)
            
            # Fallback to direct database access
            dbh = SpiderFootDb(self.config)
            try:
                return dbh.scanResultHistory(id)
            except Exception as ex:
                self.log.error(f"Error getting scan history from DB: {ex}", exc_info=True)
                return []

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def scanelementtypediscovery(self: 'SpiderFootWebUi', id: str, eventType: str) -> dict:
        """Scan element type discovery.

        Args:
            id (str): scan ID
            eventType (str): filter by event type

        Returns:
            dict
        """
        dbh = SpiderFootDb(self.config)
        pc = dict()
        datamap = dict()
        retdata = dict()

        # Get the events we will be tracing back from
        try:
            leafSet = dbh.scanResultEvent(id, eventType)
            [datamap, pc] = dbh.scanElementSourcesAll(id, leafSet)
        except Exception:
            return retdata

        # Delete the ROOT key as it adds no value from a viz perspective
        del pc['ROOT']
        retdata['tree'] = SpiderFootHelpers.dataParentChildToTree(pc)
        retdata['data'] = datamap

        return retdata

    @cherrypy.expose
    def active_maintenance_status(self: 'SpiderFootWebUi') -> str:
        """Display the active maintenance status of the project.

        Returns:
            str: Active maintenance status page HTML
        """
        templ = Template(
            filename='spiderfoot/templates/active_maintenance_status.tmpl', lookup=self.lookup)
        return templ.render(docroot=self.docroot, version=__version__)

    @cherrypy.expose
    def footer(self: 'SpiderFootWebUi') -> str:
        """Display the footer with active maintenance status.

        Returns:
            str: Footer HTML
        """
        templ = Template(
            filename='spiderfoot/templates/footer.tmpl', lookup=self.lookup)
        return templ.render(docroot=self.docroot, version=__version__)

    @cherrypy.expose
    def opts(self: 'SpiderFootWebUi', updated: str = None) -> str:
        """Settings page.

        Args:
            updated (str): TBD

        Returns:
            str: settings page HTML
        """
        # Get current settings from API
        try:
            settings = self.api_client.get_system_settings()
            
            # Create the new token
            self.token = random.SystemRandom().randint(0, 99999999)
            
            # Remove any globals that don't make sense to be configured
            # by the user via the UI
            for k in settings.copy().keys():
                if k.startswith("__") or k in ["_debug", "_stdout"]:
                    del settings[k]
            
            templ = Template(
                filename='spiderfoot/templates/opts.tmpl', lookup=self.lookup)
            return templ.render(opts=settings, docroot=self.docroot,
                                token=self.token, updated=updated, version=__version__, 
                                pageid="SETTINGS")
                                
        except Exception as e:
            self.log.error(f"Error getting settings via API: {e}", exc_info=True)
            # Fallback to direct DB access in case of API error
            dbh = SpiderFootDb(self.config)
            sf = SpiderFoot(self.config)
            
            # Create a new token
            self.token = random.SystemRandom().randint(0, 99999999)
            
            # Get the current settings
            opts = sf.configUnserialize(dbh.configGet(), self.config)
            
            # Remove any globals that don't make sense to be configured
            # by the user via the UI
            for k in list(opts.keys()):
                if k.startswith("__") or k in ["_debug", "_stdout"]:
                    del opts[k]
                    
            templ = Template(
                filename='spiderfoot/templates/opts.tmpl', lookup=self.lookup)
            return templ.render(opts=opts, docroot=self.docroot,
                                token=self.token, updated=updated, version=__version__, 
                                pageid="SETTINGS")

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def optsraw(self: 'SpiderFootWebUi') -> list:
        """Return settings as JSON.

        Returns:
            list: settings as JSON
        """
        try:
            # Get settings via API client
            result = self.api_client._request("optsraw")
            
            if "error" in result:
                raise Exception(result["error"].get("message", "Unknown API error"))
                
            if isinstance(result, list) and len(result) > 1 and result[0] == "SUCCESS":
                self.token = result[1].get('token')
                return result
            
            raise Exception("Unexpected API response format")
            
        except Exception as e:
            self.log.error(f"Error getting settings via API: {e}", exc_info=True)
            # Fallback to direct DB access in case of API error
            ret = dict()
            
            dbh = SpiderFootDb(self.config)
            sf = SpiderFoot(self.config)
            
            # Create a new token
            self.token = random.SystemRandom().randint(0, 99999999)
            
            # Get the current settings
            opts = sf.configUnserialize(dbh.configGet(), self.config)
            
            for opt in list(opts.keys()):
                ret[opt] = opts[opt]
                
            return ["SUCCESS", {"opts": ret, "token": self.token}]
