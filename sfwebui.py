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
import string
import time
import traceback
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

from sfscan import startSpiderFootScanner

from spiderfoot import SpiderFootDb
from spiderfoot import SpiderFootHelpers
from spiderfoot import __version__
from spiderfoot.logger import logListenerSetup, logWorkerSetup

mp.set_start_method("spawn", force=True)


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

        # Set up logging
        if loggingQueue is None:
            self.loggingQueue = mp.Queue()
            logListenerSetup(self.loggingQueue, self.config)
        else:
            self.loggingQueue = loggingQueue
        logWorkerSetup(self.loggingQueue)
        self.log = logging.getLogger(f"spiderfoot.{__name__}")

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
        try:
            templ = Template(
                filename='spiderfoot/templates/error.tmpl', lookup=self.lookup)
            return templ.render(message='Not Found', docroot=self.docroot, status=status, version=__version__)
        except Exception as e:
            self.log.error(f"Error rendering 404 page: {e}\n{traceback.format_exc()}")
            # Fallback to a simple response if template rendering fails
            cherrypy.response.status = 404
            return "<html><body>Not Found</body></html>"

    def jsonify_error(self: 'SpiderFootWebUi', status: int, message: str) -> dict:
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

    def error(self: 'SpiderFootWebUi', message: str) -> None:
        """Show generic error page with error message.

        Args:
            message (str): error message

        Returns:
            None
        """
        try:
            templ = Template(
                filename='spiderfoot/templates/error.tmpl', lookup=self.lookup)
            return templ.render(message=message, docroot=self.docroot, version=__version__)
        except Exception as e:
            self.log.error(f"Error rendering error page: {e}\n{traceback.format_exc()}")
            # Fallback to a simple response if template rendering fails
            cherrypy.response.status = 500
            return f"<html><body>Error: {html.escape(message)}</body></html>"

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
        # Add warning log as requested by TODO
        self.log.debug("cleanUserInput usage - review for potential removal/replacement with context-specific escaping.")

        if not isinstance(inputList, list):
            raise TypeError(f"inputList is {type(inputList)}; expected list()")

        ret = list()

        for item in inputList:
            if item is None: # Handle None explicitly
                ret.append('')
                continue
            # Ensure item is string before escaping
            c = html.escape(str(item), True)

            # Decode '&' and '"' HTML entities - Retaining original logic
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

    def buildExcel(self: 'SpiderFootWebUi', data: list, columnNames: list, sheetNameIndex: int = -1) -> bytes:
        """Convert supplied data into an Excel workbook.

        Args:
            data (list): List of lists representing rows.
            columnNames (list): List of column header names.
            sheetNameIndex (int): Index of the column in `data` rows to use for sheet names.
                                  If < 0, a single sheet named 'SpiderFoot Data' is used.

        Returns:
            bytes: Excel workbook content as bytes.
        """
        rowNums = dict()
        workbook = openpyxl.Workbook()
        defaultSheet = workbook.active
        defaultSheet.title = "SpiderFoot Data" # Default sheet name

        # Prepare headers and data based on sheetNameIndex
        headers = list(columnNames) # Copy to avoid modifying original
        use_sheet_names = sheetNameIndex >= 0
        if use_sheet_names:
            try:
                # Remove the column used for sheet names from the headers list
                sheet_name_header = headers.pop(sheetNameIndex)
                self.log.debug(f"Using column '{sheet_name_header}' (index {sheetNameIndex}) for Excel sheet names.")
            except IndexError:
                self.log.warning(f"sheetNameIndex {sheetNameIndex} is out of bounds for headers. Using default sheet.")
                use_sheet_names = False

        allowed_sheet_chars = string.ascii_uppercase + string.digits + '_ '
        sheets_created = {} # Keep track of created sheets and their next row number

        if not use_sheet_names:
            # Write headers to the default sheet
            for col_num, column_title in enumerate(headers, 1):
                cell = defaultSheet.cell(row=1, column=col_num)
                cell.value = column_title
            sheets_created[defaultSheet.title] = 2 # Next row is 2

        for row_data in data:
            row = list(row_data) # Copy row to modify
            sheetName = defaultSheet.title
            target_sheet = defaultSheet

            if use_sheet_names:
                try:
                    # Extract and remove the sheet name value from the row
                    rawSheetName = str(row.pop(sheetNameIndex))
                    # Sanitize sheet name (max 31 chars, no invalid chars)
                    sanitized_name = "".join([c for c in rawSheetName if c in allowed_sheet_chars])[:31].strip()
                    sheetName = sanitized_name if sanitized_name else f"Sheet_{len(sheets_created)}"
                except IndexError:
                    # Should not happen if header index was valid, but handle defensively
                    self.log.warning("Index error getting sheet name from row, using default sheet.")
                    sheetName = defaultSheet.title
                    # Adjust row data if pop failed unexpectedly? Assume row is still original length.
                    # If pop succeeded but header pop failed, row is already shorter. Difficult to reconcile.
                    # Safest is to proceed with potentially incorrect data on default sheet.

                if sheetName not in sheets_created:
                    # Create sheet if it doesn't exist
                    try:
                        target_sheet = workbook.create_sheet(sheetName)
                        self.log.debug(f"Created new Excel sheet: {sheetName}")
                        # Write headers to the new sheet
                        for col_num, column_title in enumerate(headers, 1):
                            cell = target_sheet.cell(row=1, column=col_num)
                            cell.value = column_title
                        sheets_created[sheetName] = 2 # Next row is 2
                    except Exception as e:
                         self.log.error(f"Failed to create sheet '{sheetName}': {e}. Using default sheet.")
                         sheetName = defaultSheet.title # Fallback to default
                         target_sheet = defaultSheet
                         # Ensure default sheet has headers if this is the first fallback
                         if defaultSheet.title not in sheets_created:
                             for col_num, column_title in enumerate(headers, 1):
                                 cell = defaultSheet.cell(row=1, column=col_num)
                                 cell.value = column_title
                             sheets_created[defaultSheet.title] = 2
                else:
                    target_sheet = workbook[sheetName]

            # Write row data
            current_row_num = sheets_created[sheetName]
            for col_num, cell_value in enumerate(row, 1):
                try:
                    cell = target_sheet.cell(row=current_row_num, column=col_num)
                    # Attempt to convert numeric strings, handle potential errors
                    try:
                        if isinstance(cell_value, str) and cell_value.isdigit():
                            cell.value = int(cell_value)
                        elif isinstance(cell_value, str) and '.' in cell_value:
                             parts = cell_value.split('.')
                             if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                                 cell.value = float(cell_value)
                             else:
                                 cell.value = cell_value # Keep as string if not simple float/int
                        else:
                            cell.value = cell_value
                    except ValueError:
                        cell.value = cell_value # Keep original value if conversion fails
                except Exception as cell_error:
                    self.log.error(f"Error writing cell ({current_row_num}, {col_num}) in sheet '{sheetName}': {cell_error}. Value: {cell_value}")
            sheets_created[sheetName] += 1

        # Remove the initial default sheet only if other sheets were created AND it wasn't used
        if len(workbook.sheetnames) > 1 and defaultSheet.title == "Sheet" and defaultSheet.max_row == 1:
             try:
                 workbook.remove(defaultSheet)
                 self.log.debug("Removed initial unused default sheet.")
             except Exception as e:
                 self.log.warning(f"Could not remove initial default sheet: {e}")
        elif len(workbook.sheetnames) == 1 and defaultSheet.max_row == 1:
             # If only the default sheet exists and it's empty (only headers potentially), log it
             self.log.warning("Excel export resulted in an empty sheet (or headers only).")


        # Sort sheets alphabetically if multiple sheets exist
        if len(workbook.sheetnames) > 1:
            try:
                workbook._sheets.sort(key=lambda ws: ws.title)
            except Exception as e:
                self.log.warning(f"Could not sort Excel sheets: {e}")

        # Save workbook to memory
        with BytesIO() as f:
            workbook.save(f)
            f.seek(0)
            return f.read()

    #
    # Helper Methods
    #

    def _set_download_headers(self: 'SpiderFootWebUi', filename: str, content_type: str) -> None:
        """Set common headers for file downloads."""
        # Ensure filename is safe for header
        safe_filename = filename.replace('"', '_').replace('\r', '_').replace('\n', '_')
        cherrypy.response.headers['Content-Disposition'] = f"attachment; filename=\"{safe_filename}\""
        cherrypy.response.headers['Content-Type'] = content_type
        cherrypy.response.headers['Pragma'] = "no-cache"
        cherrypy.response.headers['Cache-Control'] = "no-store, no-cache, must-revalidate, max-age=0"

    def _generate_csv(self: 'SpiderFootWebUi', data: list, headers: list, dialect: str = "excel") -> bytes:
        """Generate CSV data from a list of lists."""
        try:
            fileobj = StringIO()
            parser = csv.writer(fileobj, dialect=dialect)
            parser.writerow(headers)
            if data: # Avoid error if data is empty
                parser.writerows(data) # Use writerows for efficiency
            return fileobj.getvalue().encode('utf-8')
        except csv.Error as e:
            self.log.error(f"CSV writing error: {e}")
            raise # Re-raise the exception to be handled by the caller
        except Exception as e:
            self.log.error(f"Error generating CSV: {e}")
            raise

    def _get_scan_name(self: 'SpiderFootWebUi', dbh: 'SpiderFootDb', scan_id: str) -> str | None:
        """Retrieve the name of a scan, returning ID on failure."""
        try:
            scaninfo = dbh.scanInstanceGet(scan_id)
            # Return scan name if found, otherwise return the ID itself as a fallback name
            return scaninfo[0] if scaninfo and scaninfo[0] else scan_id
        except Exception as e:
            self.log.error(f"Could not retrieve info for scan {scan_id}: {e}")
            return scan_id # Return ID as fallback name on error

    #
    # USER INTERFACE PAGES
    #

    @cherrypy.expose
    def scanexportlogs(self: 'SpiderFootWebUi', id: str, dialect: str = "excel") -> bytes:
        """Get scan log."""
        dbh = SpiderFootDb(self.config)
        scan_name = self._get_scan_name(dbh, id)

        try:
            data = dbh.scanLogs(id, None, None, True)
        except Exception as e:
            self.log.error(f"Error fetching logs for scan {id}: {e}")
            return self.error(f"Could not retrieve logs for scan {id}.")

        if not data:
            return self.error(f"No logs found for scan {id}.")

        headers = ["Date", "Component", "Type", "Event", "Event ID"]
        rows = [
            [
                time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(row[0] / 1000)),
                str(row[1]),
                str(row[2]),
                str(row[3]), # Keep as string, escaping handled by CSV writer if needed
                row[4]
            ] for row in data
        ]

        fname = f"{scan_name}-SpiderFoot-logs.csv"
        self._set_download_headers(fname, "application/csv")
        try:
            return self._generate_csv(rows, headers, dialect)
        except Exception as e:
             return self.error(f"Failed to generate CSV log export for scan {id}: {e}")

    @cherrypy.expose
    def scancorrelationsexport(self: 'SpiderFootWebUi', id: str, filetype: str = "csv", dialect: str = "excel") -> str | bytes:
        """Get scan correlation data in CSV or Excel format."""
        dbh = SpiderFootDb(self.config)
        scan_name = self._get_scan_name(dbh, id)

        try:
            correlations = dbh.scanCorrelationList(id)
        except Exception as e:
            self.log.error(f"Error fetching correlations for scan {id}: {e}")
            # Return error suitable for the expected format (JSON might be better here)
            return self.error(f"Could not retrieve correlations for scan {id}.")

        if not correlations:
             return self.error(f"No correlations found for scan {id}.")

        headings = ["Rule Name", "Correlation", "Risk", "Description"]
        rows = [
            # Ensure all elements are strings for consistency in export
            [str(row[2]), str(row[1]), str(row[3]), str(row[5])]
            for row in correlations if len(row) > 5 # Basic safety check
        ]

        filetype_lower = filetype.lower()
        fname_base = f"{scan_name}-SpiderFoot-correlations"

        try:
            if filetype_lower in ["xlsx", "excel"]:
                fname = f"{fname_base}.xlsx"
                self._set_download_headers(fname, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                # Use sheetNameIndex=-1 for a single sheet
                return self.buildExcel(rows, headings, sheetNameIndex=-1)
            elif filetype_lower == 'csv':
                fname = f"{fname_base}.csv"
                self._set_download_headers(fname, "application/csv")
                return self._generate_csv(rows, headings, dialect)
            else:
                return self.error("Invalid export filetype specified.")
        except Exception as e:
            self.log.error(f"Failed to generate {filetype} correlation export for scan {id}: {e}")
            return self.error(f"Failed to generate export file for scan {id}.")


    @cherrypy.expose
    def scaneventresultexport(self: 'SpiderFootWebUi', id: str, type: str, filetype: str = "csv", dialect: str = "excel") -> str | bytes:
        """Get scan event result data in CSV or Excel format."""
        dbh = SpiderFootDb(self.config)
        scan_name = self._get_scan_name(dbh, id)

        try:
            # Ensure type is somewhat safe for filename use
            safe_type_name = "".join(c for c in type if c.isalnum() or c in ('_', '-')).strip() or "export"
            data = dbh.scanResultEvent(id, type)
        except Exception as e:
            self.log.error(f"Error fetching event results for scan {id}, type {type}: {e}")
            return self.error(f"Could not retrieve event results for scan {id}.")

        if not data:
            return self.error(f"No event results found for scan {id}, type {type}.")

        headings = ["Updated", "Type", "Module", "Source", "F/P", "Data"]
        rows = []
        for row in data:
            if row[4] == "ROOT": # event_type
                continue
            lastseen = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(row[0])) # last_seen
            # Remove SFURL tags, ensure string conversion
            datafield = str(row[1]).replace("<SFURL>", "").replace("</SFURL>", "") # data
            rows.append([
                lastseen,
                str(row[4]), # event_type
                str(row[3]), # module
                str(row[2]), # source_data_element
                str(row[13]),     # false_positive (as string '0' or '1')
                datafield
            ])

        filetype_lower = filetype.lower()
        fname_base = f"{scan_name}-SpiderFoot-results-{safe_type_name}"

        try:
            if filetype_lower in ["xlsx", "excel"]:
                fname = f"{fname_base}.xlsx"
                self._set_download_headers(fname, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                # Use 'Type' (index 1) for sheet names
                return self.buildExcel(rows, headings, sheetNameIndex=1)
            elif filetype_lower == 'csv':
                fname = f"{fname_base}.csv"
                self._set_download_headers(fname, "application/csv")
                return self._generate_csv(rows, headings, dialect)
            else:
                return self.error("Invalid export filetype specified.")
        except Exception as e:
            self.log.error(f"Failed to generate {filetype} event export for scan {id}, type {type}: {e}")
            return self.error(f"Failed to generate export file for scan {id}.")

    @cherrypy.expose
    def scaneventresultexportmulti(self: 'SpiderFootWebUi', ids: str, filetype: str = "csv", dialect: str = "excel") -> str | bytes | None:
        """Get scan event result data in CSV or Excel format for multiple scans."""
        dbh = SpiderFootDb(self.config)
        scan_ids = [scan_id.strip() for scan_id in ids.split(',') if scan_id.strip()]
        if not scan_ids:
            return self.error("No valid scan IDs provided.")

        all_rows = []
        scan_names = {}
        combined_scan_name = "SpiderFoot-multi-scan"

        try:
            for scan_id in scan_ids:
                # Use _get_scan_name which handles errors and provides fallback
                scan_name = self._get_scan_name(dbh, scan_id)
                scan_names[scan_id] = scan_name # Store name (or ID if lookup failed)

                # Fetch data for the current scan
                data = dbh.scanResultEvent(scan_id)
                for row in data:
                    if row[4] == "ROOT": # event_type
                        continue
                    lastseen = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(row[0])) # last_seen
                    datafield = str(row[1]).replace("<SFURL>", "").replace("</SFURL>", "") # data
                    all_rows.append([
                        scan_names[scan_id], # Scan Name added
                        lastseen,
                        str(row[4]), # event_type
                        str(row[3]), # module
                        str(row[2]), # source_data_element
                        str(row[13]),     # false_positive
                        datafield
                    ])
        except Exception as e:
            self.log.error(f"Error fetching multi-scan event results for JSON export (IDs: {ids}): {e}")
            return self.error("Could not retrieve event results for one or more scans.")

        if not all_rows:
            # Return None or error? Returning error is more informative.
            return self.error("No event results found for the specified scans.")

        # Determine filename
        if len(scan_ids) == 1:
            # Use the retrieved name (or ID fallback) for single scan export
            fname_base = f"{scan_names[scan_ids[0]]}-SpiderFoot-results"
        else:
            fname_base = combined_scan_name + "-results"

        headings = ["Scan Name", "Updated", "Type", "Module", "Source", "F/P", "Data"]
        filetype_lower = filetype.lower()

        try:
            if filetype_lower in ["xlsx", "excel"]:
                fname = f"{fname_base}.xlsx"
                self._set_download_headers(fname, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                # Use 'Type' (index 2 now) for sheet names
                return self.buildExcel(all_rows, headings, sheetNameIndex=2)
            elif filetype_lower == 'csv':
                fname = f"{fname_base}.csv"
                self._set_download_headers(fname, "application/csv")
                return self._generate_csv(all_rows, headings, dialect)
            else:
                return self.error("Invalid export filetype specified.")
        except Exception as e:
            self.log.error(f"Failed to generate multi-scan {filetype} event export for IDs {ids}: {e}")
            return self.error(f"Failed to generate multi-scan export file.")

    @cherrypy.expose
    def scansearchresultexport(self: 'SpiderFootWebUi', id: str, eventType: str = None, value: str = None, filetype: str = "csv", dialect: str = "excel") -> str | bytes | None:
        """Get search result data in CSV or Excel format."""
        dbh = SpiderFootDb(self.config)
        scan_name = self._get_scan_name(dbh, id)

        try:
            # searchBase returns already formatted/escaped data in a specific structure
            data = self.searchBase(id, eventType, value)
        except Exception as e:
            self.log.error(f"Error performing search for scan {id}: {e}")
            return self.error(f"Could not perform search for scan {id}.")

        if not data:
            # Return None or error? Error is better.
            return self.error(f"No search results found for scan {id} with the given criteria.")

        headings = ["Updated", "Type", "Module", "Source", "F/P", "Data"]
        rows = []
        for row in data:
            # Indices based on searchBase return structure:
            # [0:lastseen, 1:escapeddata, 2:escapedsrc, 3:module, ..., 10:type, 11:fp, ...]
            if row[10] == "ROOT": # Type
                continue
            # Data is already escaped by searchBase, remove SFURL tags if present
            datafield = str(row[1]).replace("<SFURL>", "").replace("</SFURL>", "")
            rows.append([
                row[0],      # Updated (lastseen string)
                str(row[10]),# Type
                str(row[3]), # Module
                str(row[2]), # Source (already escaped)
                str(row[11]),# F/P (as string '0' or '1')
                datafield    # Data (already escaped)
            ])

        filetype_lower = filetype.lower()
        # Create a safe filename part from eventType and value if they exist
        criteria_part = ""
        if eventType:
            criteria_part += f"_type-{eventType}"
        if value:
            # Basic sanitization for value in filename
            safe_value = "".join(c for c in value if c.isalnum() or c in ('_', '-'))[:20] # Limit length
            criteria_part += f"_val-{safe_value}"
        fname_base = f"{scan_name}-SpiderFoot-search{criteria_part}"


        try:
            if filetype_lower in ["xlsx", "excel"]:
                fname = f"{fname_base}.xlsx"
                self._set_download_headers(fname, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                # Use 'Type' (index 1) for sheet names
                return self.buildExcel(rows, headings, sheetNameIndex=1)
            elif filetype_lower == 'csv':
                fname = f"{fname_base}.csv"
                self._set_download_headers(fname, "application/csv")
                return self._generate_csv(rows, headings, dialect)
            else:
                return self.error("Invalid export filetype specified.")
        except Exception as e:
            self.log.error(f"Failed to generate {filetype} search export for scan {id}: {e}")
            return self.error(f"Failed to generate search export file for scan {id}.")

    @cherrypy.expose
    def scanexportjsonmulti(self: 'SpiderFootWebUi', ids: str) -> bytes:
        """Get scan event result data in JSON format for multiple scans."""
        dbh = SpiderFootDb(self.config)
        scan_ids = [scan_id.strip() for scan_id in ids.split(',') if scan_id.strip()]
        if not scan_ids:
            cherrypy.response.status = 400
            # Use jsonify_error structure for consistency, even though it returns dict
            err_data = self.jsonify_error(400, "No valid scan IDs provided.")
            return json.dumps(err_data).encode('utf-8')


        scaninfo_list = list()
        scan_names = {} # To store retrieved names
        combined_scan_name = "SpiderFoot-multi-scan"

        try:
            for scan_id in scan_ids:
                scan = dbh.scanInstanceGet(scan_id)
                if scan is None:
                    self.log.warning(f"Scan ID {scan_id} not found for JSON export, skipping.")
                    scan_names[scan_id] = scan_id # Use ID as fallback name
                    continue

                scan_name = scan[0] or f"Scan_{scan_id}" # Use name or generate one
                scan_names[scan_id] = scan_name
                scan_target = scan[1]

                for row in dbh.scanResultEvent(scan_id):
                    if row[4] == "ROOT": # event_type
                        continue

                    lastseen = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(row[0])) # last_seen
                    event_data = str(row[1]).replace("<SFURL>", "").replace("</SFURL>", "") # data
                    source_data = str(row[2]) # source_data_element
                    source_module = str(row[3]) # module
                    event_type = row[4] # event_type
                    # Ensure false_positive is boolean or 0/1 int for JSON consistency?
                    # Current code uses row[13] directly, which might be string '0'/'1' or int.
                    # Let's keep it as is for now, assuming consumers handle it.
                    false_positive = row[13] # false_positive

                    scaninfo_list.append({
                        "data": event_data,
                        "event_type": event_type,
                        "module": source_module,
                        "source_data": source_data,
                        "false_positive": false_positive,
                        "last_seen": lastseen,
                        "scan_name": scan_name,
                        "scan_target": scan_target
                    })
        except Exception as e:
            self.log.error(f"Error fetching multi-scan event results for JSON export (IDs: {ids}): {e}")
            return self.error("Could not retrieve event results for one or more scans.")

        # Determine filename
        if len(scan_ids) == 1:
            # Use the retrieved name (or ID fallback) for single scan export
            fname_base = f"{scan_names[scan_ids[0]]}-SpiderFoot-results"
        else:
            fname_base = combined_scan_name + "-results"

        headings = ["Scan Name", "Updated", "Type", "Module", "Source", "F/P", "Data"]
        filetype_lower = filetype.lower()

        try:
            if filetype_lower in ["xlsx", "excel"]:
                fname = f"{fname_base}.xlsx"
                self._set_download_headers(fname, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                # Use 'Type' (index 2 now) for sheet names
                return self.buildExcel(scaninfo_list, headings, sheetNameIndex=2)
            elif filetype_lower == 'csv':
                fname = f"{fname_base}.csv"
                self._set_download_headers(fname, "application/csv")
                return self._generate_csv(scaninfo_list, headings, dialect)
            else:
                return self.error("Invalid export filetype specified.")
        except Exception as e:
            self.log.error(f"Failed to generate multi-scan {filetype} event export for IDs {ids}: {e}")
            return self.error(f"Failed to generate multi-scan export file.")

    @cherrypy.expose
    def scansearchresultexport(self: 'SpiderFootWebUi', id: str, eventType: str = None, value: str = None, filetype: str = "csv", dialect: str = "excel") -> str | bytes | None:
        """Get search result data in CSV or Excel format."""
        dbh = SpiderFootDb(self.config)
        scan_name = self._get_scan_name(dbh, id)

        try:
            # searchBase returns already formatted/escaped data in a specific structure
            data = self.searchBase(id, eventType, value)
        except Exception as e:
            self.log.error(f"Error performing search for scan {id}: {e}")
            return self.error(f"Could not perform search for scan {id}.")

        if not data:
            # Return None or error? Error is better.
            return self.error(f"No search results found for scan {id} with the given criteria.")

        headings = ["Updated", "Type", "Module", "Source", "F/P", "Data"]
        rows = []
        for row in data:
            # Indices based on searchBase return structure:
            # [0:lastseen, 1:escapeddata, 2:escapedsrc, 3:module, ..., 10:type, 11:fp, ...]
            if row[10] == "ROOT": # Type
                continue
            # Data is already escaped by searchBase, remove SFURL tags if present
            datafield = str(row[1]).replace("<SFURL>", "").replace("</SFURL>", "")
            rows.append([
                row[0],      # Updated (lastseen string)
                str(row[10]),# Type
                str(row[3]), # Module
                str(row[2]), # Source (already escaped)
                str(row[11]),# F/P (as string '0' or '1')
                datafield    # Data (already escaped)
            ])

        filetype_lower = filetype.lower()
        # Create a safe filename part from eventType and value if they exist
        criteria_part = ""
        if eventType:
            criteria_part += f"_type-{eventType}"
        if value:
            # Basic sanitization for value in filename
            safe_value = "".join(c for c in value if c.isalnum() or c in ('_', '-'))[:20] # Limit length
            criteria_part += f"_val-{safe_value}"
        fname_base = f"{scan_name}-SpiderFoot-search{criteria_part}"


        try:
            if filetype_lower in ["xlsx", "excel"]:
                fname = f"{fname_base}.xlsx"
                self._set_download_headers(fname, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                # Use 'Type' (index 1) for sheet names
                return self.buildExcel(rows, headings, sheetNameIndex=1)
            elif filetype_lower == 'csv':
                fname = f"{fname_base}.csv"
                self._set_download_headers(fname, "application/csv")
                return self._generate_csv(rows, headings, dialect)
            else:
                return self.error("Invalid export filetype specified.")
        except Exception as e:
            self.log.error(f"Failed to generate {filetype} search export for scan {id}: {e}")
            return self.error(f"Failed to generate search export file for scan {id}.")

    @cherrypy.expose
    def scanexportjsonmulti(self: 'SpiderFootWebUi', ids: str) -> bytes:
        """Get scan event result data in JSON format for multiple scans."""
        dbh = SpiderFootDb(self.config)
        scan_ids = [scan_id.strip() for scan_id in ids.split(',') if scan_id.strip()]
        if not scan_ids:
            cherrypy.response.status = 400
            # Use jsonify_error structure for consistency, even though it returns dict
            err_data = self.jsonify_error(400, "No valid scan IDs provided.")
            return json.dumps(err_data).encode('utf-8')


        scaninfo_list = list()
        scan_names = {} # To store retrieved names
        combined_scan_name = "SpiderFoot-multi-scan"

        try:
            for scan_id in scan_ids:
                # Use _get_scan_name which handles errors and provides fallback
                scan_name = self._get_scan_name(dbh, scan_id)
                scan_names[scan_id] = scan_name # Store name (or ID if lookup failed)

                # Fetch data for the current scan
                data = dbh.scanResultEvent(scan_id)
                for row in data:
                    if row[4] == "ROOT": # event_type
                        continue

                    lastseen = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(row[0])) # last_seen
                    datafield = str(row[1]).replace("<SFURL>", "").replace("</SFURL>", "") # data
                    all_rows.append([
                        scan_names[scan_id], # Scan Name added
                        lastseen,
                        str(row[4]), # event_type
                        str(row[3]), # module
                        str(row[2]), # source_data_element
                        str(row[13]),     # false_positive
                        datafield
                    ])
        except Exception as e:
            self.log.error(f"Error fetching multi-scan event results for JSON export (IDs: {ids}): {e}")
            return self.error("Could not retrieve event results for one or more scans.")

        if not all_rows:
            # Return None or error? Returning error is more informative.
            return self.error("No event results found for the specified scans.")

        # Determine filename
        if len(scan_ids) == 1:
            # Use the retrieved name (or ID fallback) for single scan export
            fname_base = f"{scan_names[scan_ids[0]]}-SpiderFoot-results"
        else:
            fname_base = combined_scan_name + "-results"

        headings = ["Scan Name", "Updated", "Type", "Module", "Source", "F/P", "Data"]
        filetype_lower = filetype.lower()

        try:
            if filetype_lower in ["xlsx", "excel"]:
                fname = f"{fname_base}.xlsx"
                self._set_download_headers(fname, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                # Use 'Type' (index 2 now) for sheet names
                return self.buildExcel(all_rows, headings, sheetNameIndex=2)
            elif filetype_lower == 'csv':
                fname = f"{fname_base}.csv"
                self._set_download_headers(fname, "application/csv")
                return self._generate_csv(all_rows, headings, dialect)
            else:
                return self.error("Invalid export filetype specified.")
        except Exception as e:
            self.log.error(f"Failed to generate multi-scan {filetype} event export for IDs {ids}: {e}")
            return self.error(f"Failed to generate multi-scan export file.")

    @cherrypy.expose
    def scansearchresultexport(self: 'SpiderFootWebUi', id: str, eventType: str = None, value: str = None, filetype: str = "csv", dialect: str = "excel") -> str | bytes | None:
        """Get search result data in CSV or Excel format."""
        dbh = SpiderFootDb(self.config)
        scan_name = self._get_scan_name(dbh, id)

        try:
            # searchBase returns already formatted/escaped data in a specific structure
            data = self.searchBase(id, eventType, value)
        except Exception as e:
            self.log.error(f"Error performing search for scan {id}: {e}")
            return self.error(f"Could not perform search for scan {id}.")

        if not data:
            # Return None or error? Error is better.
            return self.error(f"No search results found for scan {id} with the given criteria.")

        headings = ["Updated", "Type", "Module", "Source", "F/P", "Data"]
        rows = []
        for row in data:
            # Indices based on searchBase return structure:
            # [0:lastseen, 1:escapeddata, 2:escapedsrc, 3:module, ..., 10:type, 11:fp, ...]
            if row[10] == "ROOT": # Type
                continue
            # Data is already escaped by searchBase, remove SFURL tags if present
            datafield = str(row[1]).replace("<SFURL>", "").replace("</SFURL>", "")
            rows.append([
                row[0],      # Updated (lastseen string)
                str(row[10]),# Type
                str(row[3]), # Module
                str(row[2]), # Source (already escaped)
                str(row[11]),# F/P (as string '0' or '1')
                datafield    # Data (already escaped)
            ])

        filetype_lower = filetype.lower()
        # Create a safe filename part from eventType and value if they exist
        criteria_part = ""
        if eventType:
            criteria_part += f"_type-{eventType}"
        if value:
            # Basic sanitization for value in filename
            safe_value = "".join(c for c in value if c.isalnum() or c in ('_', '-'))[:20] # Limit length
            criteria_part += f"_val-{safe_value}"
        fname_base = f"{scan_name}-SpiderFoot-search{criteria_part}"


        try:
            if filetype_lower in ["xlsx", "excel"]:
                fname = f"{fname_base}.xlsx"
                self._set_download_headers(fname, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                # Use 'Type' (index 1) for sheet names
                return self.buildExcel(rows, headings, sheetNameIndex=1)
            elif filetype_lower == 'csv':
                fname = f"{fname_base}.csv"
                self._set_download_headers(fname, "application/csv")
                return self._generate_csv(rows, headings, dialect)
            else:
                return self.error("Invalid export filetype specified.")
        except Exception as e:
            self.log.error(f"Failed to generate {filetype} search export for scan {id}: {e}")
            return self.error(f"Failed to generate search export file for scan {id}.")

    @cherrypy.expose
    def scanexportjsonmulti(self: 'SpiderFootWebUi', ids: str) -> bytes:
        """Get scan event result data in JSON format for multiple scans."""
        dbh = SpiderFootDb(self.config)
        scan_ids = [scan_id.strip() for scan_id in ids.split(',') if scan_id.strip()]
        if not scan_ids:
            cherrypy.response.status = 400
            # Use jsonify_error structure for consistency, even though it returns dict
            err_data = self.jsonify_error(400, "No valid scan IDs provided.")
            return json.dumps(err_data).encode('utf-8')


        scaninfo_list = list()
        scan_names = {} # To store retrieved names
        combined_scan_name = "SpiderFoot-multi-scan"

        try:
            for scan_id in scan_ids:
                scan = dbh.scanInstanceGet(scan_id)
                if scan is None:
                    self.log.warning(f"Scan ID {scan_id} not found for JSON export, skipping.")
                    scan_names[scan_id] = scan_id # Use ID as fallback name
                    continue

                scan_name = scan[0] or f"Scan_{scan_id}" # Use name or generate one
                scan_names[scan_id] = scan_name
                scan_target = scan[1]

                for row in dbh.scanResultEvent(scan_id):
                    if row[4] == "ROOT": # event_type
                        continue

                    lastseen = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(row[0])) # last_seen
                    datafield = str(row[1]).replace("<SFURL>", "").replace("</SFURL>", "") # data
                    scaninfo_list.append({
                        "data": datafield,
                        "event_type": row[4],
                        "module": str(row[3]),
                        "source_data": str(row[2]),
                        "false_positive": str(row[13]),
                        "last_seen": lastseen,
                        "scan_name": scan_name,
                        "scan_target": scan_target
                    })
        except Exception as e:
            self.log.error(f"Error fetching multi-scan event results for JSON export (IDs: {ids}): {e}")
            return self.error("Could not retrieve event results for one or more scans.")

        # Determine filename
        if len(scan_ids) == 1:
            # Use the retrieved name (or ID fallback) for single scan export
            fname_base = f"{scan_names[scan_ids[0]]}-SpiderFoot-results"
        else:
            fname_base = combined_scan_name + "-results"

        # --- JSON Export ---
        # Indent for readability
        json_export = json.dumps(scaninfo_list, indent=2)

        # Safeguard filename
        fname = f"{fname_base}.json"
        self._set_download_headers(fname, "application/json; charset=utf-8")
        return json_export.encode('utf-8')

    def _start_scan_process(self: 'SpiderFootWebUi', scanname: str, scantarget: str, targetType: str, modlist: list, cfg: dict) -> str | None:
        """Helper function to initiate the scan process and wait for initialization."""
        scanId = SpiderFootHelpers.genScanInstanceId()
        dbh = SpiderFootDb(cfg) # Use the passed config for DB interaction during init check

        # Ensure mandatory DB storage module is present and stdout is absent
        if "sfp__stor_db" not in modlist:
            modlist.append("sfp__stor_db")
        if "sfp__stor_stdout" in modlist:
            try:
                modlist.remove("sfp__stor_stdout")
            except ValueError:
                pass # Ignore if not found
        modlist.sort()

        # Adjust target format based on type
        effective_scantarget = scantarget
        if targetType in ["HUMAN_NAME", "USERNAME", "BITCOIN_ADDRESS"]:
             # Remove quotes if present, as targetTypeFromString handles them
             effective_scantarget = scantarget.strip('"')
        else:
            effective_scantarget = scantarget.lower()

        try:
            self.log.info(f"Starting scan process for '{scanname}' [{scanId}] targeting '{effective_scantarget}' ({targetType}) with {len(modlist)} modules.")
            p = mp.Process(target=startSpiderFootScanner, args=(
                self.loggingQueue, scanname, scanId, effective_scantarget, targetType, modlist, cfg))
            p.daemon = True
            p.start()
            self.log.info(f"Scan process [{scanId}] spawned successfully (PID: {p.pid}).")
        except Exception as e:
            self.log.error(f"[-] Failed to spawn scan process [{scanId}]: {e}", exc_info=True)
            return None # Indicate failure

        # Wait until the scan has initialized in the database
        max_wait_time = 60 # Increased wait time (seconds)
        wait_interval = 1
        start_wait = time.time()
        while True:
            try:
                if dbh.scanInstanceGet(scanId) is not None:
                    self.log.info(f"Scan [{scanId}] initialized successfully in database.")
                    return scanId # Return the new scan ID on success
            except Exception as db_err:
                 # Log DB error during check but continue waiting
                 self.log.warning(f"DB error checking scan [{scanId}] initialization: {db_err}. Retrying...")

            if time.time() - start_wait > max_wait_time:
                self.log.error(f"Scan [{scanId}] did not initialize in the database within {max_wait_time} seconds. Aborting wait.")
                # Consider additional error handling: maybe try to terminate the process `p`?
                # p.terminate() # This might be risky depending on process state
                return None # Indicate failure

            self.log.debug(f"Waiting for scan [{scanId}] to initialize in database...")
            time.sleep(wait_interval)


    @cherrypy.expose
    def rerunscan(self: 'SpiderFootWebUi', id: str) -> None:
        """Rerun a scan."""
        cfg = deepcopy(self.config)
        dbh = SpiderFootDb(cfg) # DB handle with current config for fetching old scan data

        try:
            info = dbh.scanInstanceGet(id)
            if not info:
                return self.error(f"Invalid scan ID: {id}")

            scanname = info[0]
            scantarget = info[1]

            scanconfig = dbh.scanConfigGet(id)
            if not scanconfig:
                return self.error(f"Error loading config from original scan: {id}")

            modlist = scanconfig.get('_modulesenabled', '').split(',')
            if not modlist or modlist == ['']:
                 return self.error(f"No modules found in configuration for original scan: {id}")

            # Determine target type (try raw, then quoted for names)
            targetType = SpiderFootHelpers.targetTypeFromString(scantarget)
            if not targetType:
                targetType = SpiderFootHelpers.targetTypeFromString(f'"{scantarget}"')
                if not targetType:
                     return self.error(f"Could not determine target type for '{html.escape(scantarget)}' from original scan {id}.")

        except Exception as e:
             self.log.error(f"Error preparing rerun for scan {id}: {e}")
             return self.error(f"Failed to retrieve information for scan {id}.")

        # Start the scan using the helper, passing the *current* config (cfg)
        newScanId = self._start_scan_process(scanname, scantarget, targetType, modlist, cfg)

        if newScanId:
            self.log.info(f"Successfully started rerun of scan {id} as new scan {newScanId}.")
            raise cherrypy.HTTPRedirect(f"{self.docroot}/scaninfo?id={newScanId}", status=302)
        else:
            # Handle scan start failure
            return self.error(f"Failed to start the rerun scan process for original scan ID {id}.")

    @cherrypy.expose
    def rerunscanmulti(self: 'SpiderFootWebUi', ids: str) -> str:
        """Rerun scans."""
        cfg = deepcopy(self.config) # Snapshot current config once for all reruns
        dbh = SpiderFootDb(cfg) # DB handle with current config
        scan_ids = [scan_id.strip() for scan_id in ids.split(',') if scan_id.strip()]
        started_scans_count = 0
        failed_scans = []

        if not scan_ids:
            return self.error("No valid scan IDs provided for multi-rerun.")

        for scan_id in scan_ids:
            try:
                info = dbh.scanInstanceGet(scan_id)
                if not info:
                    self.log.warning(f"Invalid scan ID {scan_id} provided for multi-rerun, skipping.")
                    failed_scans.append(f"{scan_id} (not found)")
                    continue

                scanconfig = dbh.scanConfigGet(scan_id)
                if not scanconfig:
                    self.log.warning(f"Error loading config from scan {scan_id}, skipping.")
                    failed_scans.append(f"{scan_id} (config error)")
                    continue

                scanname = info[0]
                scantarget = info[1]

                modlist = scanconfig.get('_modulesenabled', '').split(',')
                if not modlist or modlist == ['']:
                    self.log.warning(f"No modules found in configuration for scan {scan_id}, skipping.")
                    failed_scans.append(f"{scan_id} (no modules)")
                    continue

                # Determine target type
                targetType = SpiderFootHelpers.targetTypeFromString(scantarget)
                if not targetType:
                    targetType = SpiderFootHelpers.targetTypeFromString(f'"{scantarget}"')
                    if not targetType:
                        self.log.warning(f"Could not determine target type for '{html.escape(scantarget)}' from scan {scan_id}, skipping.")
                        failed_scans.append(f"{scan_id} (bad target type)")
                        continue

                # Start the scan using the helper
                newScanId = self._start_scan_process(scanname, scantarget, targetType, modlist, cfg)

                if newScanId:
                    started_scans_count += 1
                    self.log.info(f"Successfully started multi-rerun for scan {scan_id} as new scan {newScanId}.")
                else:
                    # Log failure but continue with others
                    self.log.error(f"Failed to start the rerun scan process for original scan ID {scan_id}.")
                    failed_scans.append(f"{scan_id} (start failed)")

            except Exception as e:
                 self.log.error(f"Unexpected error processing scan {scan_id} for multi-rerun: {e}")
                 failed_scans.append(f"{scan_id} (unexpected error)")

        # Redirect to scan list, potentially passing info about success/failure
        # For simplicity, just indicate if *any* scans were started.
        # A more complex approach could use query params or flash messages.
        try:
            templ = Template(
                filename='spiderfoot/templates/scanlist.tmpl', lookup=self.lookup)
            # Pass counts to template for potential display
            return templ.render(rerun_started=started_scans_count, rerun_failed=len(failed_scans),
                                docroot=self.docroot, pageid="SCANLIST", version=__version__)
        except Exception as e:
             self.log.error(f"Failed to render scanlist template after multi-rerun: {e}")
             return self.error("Completed multi-rerun request, but failed to load scan list page.")

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def scandelete(self: 'SpiderFootWebUi', id: str) -> str | dict:
        """Delete scan(s).

        Args:
            id (str): comma separated list of scan IDs

        Returns:
            str: JSON response
        """
        if not id:
            return self.jsonify_error(400, "No scan specified") # Use 400 Bad Request

        dbh = SpiderFootDb(self.config)
        ids = [scan_id.strip() for scan_id in id.split(',') if scan_id.strip()]
        if not ids:
            return self.jsonify_error(400, "No valid scan IDs provided.")

        errors = {}
        success_ids = []

        # First, check status of all scans before attempting deletion
        for scan_id in ids:
            try:
                res = dbh.scanInstanceGet(scan_id)
                if not res:
                    errors[scan_id] = "Does not exist"
                    continue

                status = res[5]
                # More robust check for deletable states
                if status in ["RUNNING", "STARTING", "STARTED", "ABORT-REQUESTED"]:
                    errors[scan_id] = f"Scan is {status}. Cannot delete."
            except Exception as e:
                 self.log.error(f"Error checking status for scan {scan_id} before delete: {e}")
                 errors[scan_id] = "Error checking status."

        if errors:
             # If any scan cannot be deleted, return error immediately without deleting others
             return self.jsonify_error(400, f"Cannot delete scans: {errors}")

        # If all checks passed, proceed with deletion
        deleted_count = 0
        delete_errors = {}
        for scan_id in ids:
            try:
                # Re-check existence is redundant if first check passed and no errors occurred
                dbh.scanInstanceDelete(scan_id)
                self.log.info(f"Deleted scan {scan_id}")
                deleted_count += 1
                success_ids.append(scan_id)
            except Exception as e:
                self.log.error(f"Failed to delete scan {scan_id}: {e}")
                delete_errors[scan_id] = str(e)

        if delete_errors:
             # Report which scans failed deletion
             return self.jsonify_error(500, f"Failed to delete some scans: {delete_errors}. Successfully deleted: {success_ids}")

        # Return success (HTTP 204 No Content is appropriate)
        cherrypy.response.status = 204
        return "" # Return empty body for 204

    def _save_settings_logic(self: 'SpiderFootWebUi', settings_data: dict) -> bool:
        """Core logic for saving settings."""
        try:
            dbh = SpiderFootDb(self.config)
            # Directly use the parsed settings_data.
            # DO NOT use cleanUserInput here. Validation/escaping should be context-specific.
            # Assume settings_data is a dict from JSON parsing or file reading.
            useropts = settings_data

            currentopts = deepcopy(self.config) # Get current config state

            # Create a SpiderFoot instance with current config to use its methods
            sf = SpiderFoot(currentopts)
            # Unserialize the user options onto the current config to get the new state
            # This handles merging global and module options correctly
            self.config = sf.configUnserialize(useropts, currentopts)

            # Persist the *serialized* version of the *new* config state
            dbh.configSet(sf.configSerialize(self.config))
            self.log.info("Settings saved successfully.")
            return True
        except json.JSONDecodeError as e:
            # This shouldn't happen if called after successful parsing, but good practice
            self.log.error(f"Internal error: Failed to process settings data (JSON): {e}")
            return False
        except Exception as e:
            self.log.error(f"Error processing or saving settings: {e}", exc_info=True)
            return False

    @cherrypy.expose
    def savesettings(self: 'SpiderFootWebUi', allopts: str, token: str, configFile: 'cherrypy._cpreqbody.Part' = None) -> None:
        """Save settings from UI form, also used to reset them to default."""
        if str(token) != str(self.token):
            return self.error(f"Invalid token ({token})")

        settings_to_save = None

        # Handle file upload first
        # Check for filename attribute as well, as configFile might exist but be empty
        if configFile and configFile.file and getattr(configFile, 'filename', None):
            try:
                contents = configFile.file.read()
                if isinstance(contents, bytes):
                    contents = contents.decode('utf-8', errors='ignore') # Be lenient with decoding

                tmp = dict()
                for line in contents.splitlines(): # Use splitlines for robustness
                    line = line.strip()
                    # Skip empty lines, comments, and lines without '='
                    if not line or line.startswith('#') or "=" not in line:
                        continue
                    # Split only on the first '=', allowing '=' in values
                    opt_key, opt_value = line.split("=", 1)
                    tmp[opt_key.strip()] = opt_value.strip() # Store cleaned key/value

                settings_to_save = tmp
                self.log.info(f"Loaded {len(tmp)} settings from uploaded file: {configFile.filename}")
            except Exception as e:
                self.log.error(f"Failed to parse uploaded settings file {configFile.filename}: {e}")
                return self.error(f"Failed to parse input file. Ensure it's a valid SpiderFoot config file. ({e})")
        else:
            # Handle RESET command if no file uploaded
            if allopts == "RESET":
                self.log.info("Resetting settings to default via UI.")
                if self.reset_settings():
                    # Use HTTPRedirect for UI flow
                    raise cherrypy.HTTPRedirect(f"{self.docroot}/opts?updated=1")
                else:
                    return self.error("Failed to reset settings")

            # Handle JSON data from form field if no file and not RESET
            try:
                # Ensure allopts is treated as a string before loading
                settings_to_save = json.loads(str(allopts))
                if not isinstance(settings_to_save, dict):
                     raise ValueError("Settings data must be a JSON object.")
            except json.JSONDecodeError as e:
                 self.log.error(f"Failed to parse settings JSON from form: {e}")
                 return self.error(f"Invalid settings format submitted: {e}")
            except ValueError as e: # Catches the isinstance check failure
                 self.log.error(f"Invalid settings data structure: {e}")
                 return self.error(f"Invalid settings data structure: {e}")

        # Save the determined settings using the helper logic
        if settings_to_save is not None:
            if self._save_settings_logic(settings_to_save):
                # Redirect on success for UI flow
                raise cherrypy.HTTPRedirect(f"{self.docroot}/opts?updated=1")
            else:
                # _save_settings_logic logs details
                return self.error("Failed to save settings. Check logs for details.")
        else:
             # This case should ideally not be reached if logic is correct
             self.log.warning("savesettings called but no settings data found to save (not file, RESET, or valid JSON).")
             return self.error("No settings data provided or data was invalid.")


    @cherrypy.expose
    @cherrypy.tools.json_out() # Ensures response is JSON
    def savesettingsraw(self: 'SpiderFootWebUi', allopts: str, token: str) -> list | dict:
        """Save settings via API, also used to completely reset them to default."""
        if str(token) != str(self.token):
            # Use jsonify_error for consistent API error format
            return self.jsonify_error(403, f"Invalid token.") # 403 Forbidden, hide token value

        # Reset config to default
        if allopts == "RESET":
            self.log.info("Resetting settings to default via API.")
            if self.reset_settings():
                return ["SUCCESS", "Settings reset successfully."]
            else:
                return self.jsonify_error(500, "Failed to reset settings")

        # Save settings from JSON string
        try:
            useropts = json.loads(allopts)
            if not isinstance(useropts, dict):
                 raise ValueError("Invalid format: settings must be a JSON object.")

            if self._save_settings_logic(useropts):
                return ["SUCCESS", "Settings saved successfully."]
            else:
                # _save_settings_logic logs details, return generic error
                return self.jsonify_error(500, "Failed to save settings. Check logs for details.")
        except json.JSONDecodeError as e:
            return self.jsonify_error(400, f"Invalid JSON format for settings: {e}")
        except ValueError as e: # Catches the isinstance check failure
            return self.jsonify_error(400, str(e))
        except Exception as e:
            # Catch unexpected errors during the process
            self.log.error(f"Unexpected error in savesettingsraw: {e}", exc_info=True)
            return self.jsonify_error(500, "An unexpected error occurred while saving settings.")

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
    def query(self: 'SpiderFootWebUi', query: str) -> str | list | dict:
        """For the CLI to run queries against the database.

        Args:
            query (str): SQL query

        Returns:
            str: query results as JSON
        """
        dbh = SpiderFootDb(self.config)

        if not query:
            return self.jsonify_error(400, "Invalid query: No query provided.")

        query_strip = query.strip()
        query_lower = query_strip.lower()

        # Basic validation: Allow only SELECT for safety via API
        # Also block potentially harmful PRAGMA commands
        if not query_lower.startswith("select") or "pragma" in query_lower:
            self.log.warning(f"Blocked potentially unsafe query attempt via API: {query_strip}")
            return self.jsonify_error(403, "Only SELECT queries (excluding PRAGMA) are permitted via this endpoint.") # 403 Forbidden

        try:
            # Use execute directly for read-only SELECT
            cursor = dbh.dbh.execute(query_strip) # Use stripped query

            # Fetch column names safely (handle case where query returns no results/columns)
            columnNames = [description[0] for description in cursor.description] if cursor.description else []

            # Fetch all results
            data = cursor.fetchall()

            # Convert rows to dictionaries
            # Use a list comprehension for conciseness
            return [dict(zip(columnNames, row)) for row in data]
        except Exception as e:
            self.log.error(f"Error executing query via API: {e}. Query: {query_strip}")
            # Return a 500 error with the database error message
            return self.jsonify_error(500, f"Database query failed: {e}")

    @cherrypy.expose
    def startscan(self: 'SpiderFootWebUi', scanname: str, scantarget: str, modulelist: str = None, typelist: str = None, usecase: str = None) -> str:
        """Initiate a scan."""
        # Use original values directly, cleanUserInput is problematic here.
        # Validation and sanitization happen later or are context-specific.
        # scanname = self.cleanUserInput([scanname])[0] # Removed
        # scantarget = self.cleanUserInput([scantarget])[0] # Removed

        is_api_request = cherrypy.request.headers.get('Accept') and 'application/json' in cherrypy.request.headers.get('Accept')

        # --- Input Validation ---
        if not scanname:
            msg = "Scan name was not specified."
            if is_api_request: return json.dumps(self.jsonify_error(400, msg)).encode('utf-8')
            return self.error(f"Invalid request: {msg}")

        if not scantarget:
            msg = "Scan target was not specified."
            if is_api_request: return json.dumps(self.jsonify_error(400, msg)).encode('utf-8')
            return self.error(f"Invalid request: {msg}")

        if not typelist and not modulelist and not usecase:
            msg = "No modules specified for scan (select modules, types, or a use case)."
            if is_api_request: return json.dumps(self.jsonify_error(400, msg)).encode('utf-8')
            return self.error(f"Invalid request: {msg}")

        # --- Target Type Determination ---
        targetType = SpiderFootHelpers.targetTypeFromString(scantarget)
        if targetType is None:
            # Try quoting for names/addresses if initial detection failed
            targetType = SpiderFootHelpers.targetTypeFromString(f'"{scantarget}"')
            if targetType is None:
                # Escape target for safe display in error message
                safe_target = html.escape(scantarget)
                msg = f"Unrecognised target type for '{safe_target}'."
                if is_api_request: return json.dumps(self.jsonify_error(400, msg)).encode('utf-8')
                return self.error(f"Invalid target type. Could not recognize '{safe_target}' as a target SpiderFoot supports.")

        # --- Configuration and Module Selection ---
        cfg = deepcopy(self.config) # Snapshot the current configuration
        sf = SpiderFoot(cfg) # Needed for module/type lookups based on current config

        final_modlist = []

        # Determine module list based on input priority: modulelist > typelist > usecase
        if modulelist:
            # Split, strip whitespace, remove 'module_' prefix, filter empty strings
            final_modlist = [mod.strip() for mod in modulelist.replace('module_', '').split(',') if mod.strip()]
            self.log.info(f"Using specified module list for scan '{scanname}': {len(final_modlist)} modules.")
        elif typelist:
            typesx = [t.strip() for t in typelist.replace('type_', '').split(',') if t.strip()]
            if typesx:
                try:
                    # 1. Find all modules that produce the requested types
                    initial_mods = sf.modulesProducing(typesx)
                    final_modlist = list(initial_mods) # Start with producers
                    mods_to_process = list(initial_mods) # Queue for dependency resolution

                    # 2. Iteratively find dependencies (modules producing inputs for current modules)
                    processed_modules = set(initial_mods) # Track processed to avoid cycles/redundancy
                    max_iterations = 10 # Safety break for potential complex dependencies
                    iterations = 0

                    while mods_to_process and iterations < max_iterations:
                        iteration_mods_added = []
                        # Find event types consumed by the modules we just added/are processing
                        consumed_types = sf.eventsToModules(mods_to_process)
                        if consumed_types:
                            # Find modules producing these consumed types
                            dependency_mods = sf.modulesProducing(consumed_types)
                            for mod in dependency_mods:
                                if mod not in processed_modules:
                                    iteration_mods_added.append(mod)
                                    processed_modules.add(mod)
                                    final_modlist.append(mod) # Add to the final list

                        mods_to_process = iteration_mods_added # Process the newly added dependencies
                        iterations += 1

                    if iterations == max_iterations:
                        self.log.warning(f"Reached maximum iterations ({max_iterations}) resolving module dependencies for types: {typesx}. Module list might be incomplete.")

                    self.log.info(f"Resolved module list from types for scan '{scanname}': {len(final_modlist)} modules.")
                except Exception as e:
                     self.log.error(f"Error resolving modules from types for scan '{scanname}': {e}")
                     msg = "Error determining modules based on selected types."
                     if is_api_request: return json.dumps(self.jsonify_error(500, msg)).encode('utf-8')
                     return self.error(msg)
            else:
                 self.log.warning(f"Typelist provided but was empty for scan '{scanname}'.")
        elif usecase:
            usecase = usecase.strip()
            if usecase:
                try:
                    # Iterate through modules available in the current config
                    for mod, mod_data in self.config.get('__modules__', {}).items():
                        # Skip internal/storage modules unless explicitly part of 'all' (though usually excluded)
                        if mod.startswith("sfp__"):
                             continue
                        # Check if module belongs to the use case group
                        if usecase == 'all' or usecase in mod_data.get('group', []):
                            final_modlist.append(mod)

                    self.log.info(f"Using use case '{usecase}' for scan '{scanname}': {len(final_modlist)} modules.")
                except Exception as e:
                     self.log.error(f"Error selecting modules by use case '{usecase}' for scan '{scanname}': {e}")
                     msg = f"Error determining modules based on use case '{usecase}'."
                     if is_api_request: return json.dumps(self.jsonify_error(500, msg)).encode('utf-8')
                     return self.error(msg)
            else:
                 self.log.warning(f"Usecase provided but was empty for scan '{scanname}'.")

        # --- Final Module List Check ---
        # Remove duplicates just in case
        final_modlist = sorted(list(set(final_modlist)))

        if not final_modlist:
            msg = "No modules selected for scan after processing inputs."
            if is_api_request: return json.dumps(self.jsonify_error(400, msg)).encode('utf-8')
            return self.error(f"Invalid request: {msg}")

        # --- Start Scan Process ---
        # The helper function _start_scan_process handles adding sfp__stor_db, removing stdout,
        # adjusting scantarget based on type, creating the process, and waiting for init.
        scanId = self._start_scan_process(scanname, scantarget, targetType, final_modlist, cfg)

        # --- Handle Result ---
        if scanId:
            self.log.info(f"Successfully initiated scan '{scanname}' with ID {scanId}.")
            if is_api_request:
                # Return success JSON for API requests
                return json.dumps(["SUCCESS", scanId]).encode('utf-8')
            else:
                # Redirect for UI requests
                raise cherrypy.HTTPRedirect(f"{self.docroot}/scaninfo?id={scanId}")
        else:
            # Handle scan start failure (logged in helper)
            msg = f"Failed to start the scan process for '{scanname}'."
            if is_api_request: return json.dumps(self.jsonify_error(500, msg)).encode('utf-8')
            return self.error(msg)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def scancorrelations(self: 'SpiderFootWebUi', id: str) -> list | dict:
        """Correlation results from a scan."""
        retdata = []
        dbh = SpiderFootDb(self.config)

        try:
            self.log.debug(f"Fetching correlations for scan {id}")
            # Assuming dbh.scanCorrelationList returns rows with expected structure
            # [correlation_id, correlation, rule_name, rule_risk, rule_id, rule_description, events_json, created_ts]
            corrdata = dbh.scanCorrelationList(id)
            self.log.debug(f"Found {len(corrdata)} correlations for scan {id}")

            if not corrdata:
                # Return empty list, not an error, if no correlations found
                return retdata

            for row in corrdata:
                # Basic check for expected number of fields
                if len(row) < 8:
                    self.log.warning(f"Correlation data row format unexpected for scan {id}: got {len(row)} fields, expected at least 8. Row: {row}")
                    continue # Skip malformed row

                try:
                    correlation_id = row[0]
                    correlation = row[1] # The actual correlated value/entity
                    rule_name = row[2]
                    rule_risk = row[3]
                    rule_id = row[4] # The ID of the rule definition
                    rule_description = row[5]
                    events_json = row[6] # JSON string of event IDs/hashes
                    created_ts = row[7] # Timestamp

                    # Attempt to parse events JSON, default to empty list on error
                    events = []
                    if events_json:
                        try:
                            parsed_events = json.loads(events_json)
                            # Ensure it's a list
                            events = list(parsed_events) if isinstance(parsed_events, list) else []
                        except json.JSONDecodeError:
                             self.log.warning(f"Could not decode events JSON for correlation {correlation_id} in scan {id}: {events_json[:100]}...") # Log truncated JSON
                        except TypeError:
                             self.log.warning(f"Events JSON was not a string for correlation {correlation_id} in scan {id}")

                    # Format timestamp safely
                    created_str = "Invalid Timestamp"
                    if isinstance(created_ts, (int, float)) and created_ts > 0:
                         try:
                             created_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(created_ts))
                         except ValueError:
                              self.log.warning(f"Invalid timestamp value {created_ts} for correlation {correlation_id}")
                    elif created_ts:
                         self.log.warning(f"Non-numeric timestamp {created_ts} for correlation {correlation_id}")


                    # Append data as a list (matching original structure)
                    retdata.append([correlation_id, correlation, rule_name, rule_risk,
                                   rule_id, rule_description, events, created_str])
                except IndexError as ie:
                     self.log.error(f"Index error processing correlation row for scan {id}: {ie}. Row: {row}")
                except Exception as row_err:
                     self.log.error(f"Unexpected error processing correlation row for scan {id}: {row_err}. Row: {row}")

        except Exception as e:
            self.log.error(f"Error fetching or processing correlations for scan {id}: {e}", exc_info=True)
            # Return an error structure instead of empty list on major exception
            return self.jsonify_error(500, f"Error fetching correlations for scan {id}: {e}")

        return retdata

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

        dbh = SpiderFootDb(self.config)

        if not eventType:
            eventType = 'ALL'

        try:
            data = dbh.scanResultEvent(
                id, eventType, filterfp, correlationId=correlationId)
        except Exception:
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
    def scaneventresultsunique(self: 'SpiderFootWebUi', id: str, eventType: str, filterfp: bool = False) -> list:
        """Return unique event results for a scan as JSON.

        Args:
            id (str): filter search results by scan ID
            eventType (str): filter search results by event type
            filterfp (bool): remove false positives from search results

        Returns:
            list: unique search results
        """
        dbh = SpiderFootDb(self.config)
        retdata = []

        try:
            data = dbh.scanResultEventUnique(id, eventType, filterfp)
        except Exception:
            return retdata

        for row in data:
            escaped = html.escape(row[0])
            retdata.append([escaped, row[1], row[2]])

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
            return self.searchBase(id, eventType, value)
        except Exception:
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
            return self.jsonify_error(404, "No scan specified")

        dbh = SpiderFootDb(self.config)

        try:
            return dbh.scanResultHistory(id)
        except Exception:
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