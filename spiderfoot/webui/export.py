"""WebUI endpoints for exporting scan data in CSV, Excel, and JSON formats."""

from __future__ import annotations

import cherrypy
import csv
import json
import time
from spiderfoot import SpiderFootHelpers

class ExportEndpoints:
    """WebUI endpoints for exporting scan data."""
    @cherrypy.expose
    def scanexportlogs(self, id: str, dialect: str = "excel") -> bytes:
        """Export scan logs as a CSV file download."""
        dbh = self._get_dbh()
        try:
            data = dbh.scanLogs(id)
        except Exception as e:
            return json.dumps(self.jsonify_error("404", "Scan ID not found")).encode("utf-8")
        if not data:
            return json.dumps(self.jsonify_error("404", "No scan logs found")).encode("utf-8")
        from sfwebui import StringIO
        fileobj = StringIO()
        parser = csv.writer(fileobj, dialect=dialect)
        parser.writerow(["Date", "Component", "Type", "Event", "Event ID"])
        for row in data:
            parser.writerow([str(x) for x in row])
        cherrypy.response.headers['Content-Disposition'] = f"attachment; filename=SpiderFoot-{id}.log.csv"
        cherrypy.response.headers['Content-Type'] = "application/csv"
        cherrypy.response.headers['Pragma'] = "no-cache"
        return fileobj.getvalue().encode('utf-8')

    @cherrypy.expose
    def scancorrelationsexport(self, id: str, filetype: str = "csv", dialect: str = "excel") -> str | bytes:
        """Export scan correlations as a CSV or Excel file download."""
        dbh = self._get_dbh()
        try:
            data = dbh.scanCorrelations(id)
        except Exception as e:
            return self.error("Scan ID not found")
        try:
            scan = dbh.scanInstanceGet(id)
        except Exception as e:
            return self.error("Scan ID not found")
        headings = ["Rule Name", "Correlation", "Risk", "Description"]
        if filetype.lower() in ["xlsx", "excel"]:
            cherrypy.response.headers['Content-Disposition'] = f"attachment; filename=SpiderFoot-{id}-correlations.xlsx"
            cherrypy.response.headers['Content-Type'] = (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            cherrypy.response.headers['Pragma'] = "no-cache"
            return self.buildExcel(data, headings)
        if filetype.lower() == 'csv':
            cherrypy.response.headers['Content-Disposition'] = f"attachment; filename=SpiderFoot-{id}-correlations.csv"
            cherrypy.response.headers['Content-Type'] = "application/csv"
            cherrypy.response.headers['Pragma'] = "no-cache"
            from sfwebui import StringIO
            fileobj = StringIO()
            parser = csv.writer(fileobj, dialect=dialect)
            parser.writerow(headings)
            for row in data:
                parser.writerow([str(x) for x in row])
            return fileobj.getvalue()
        return self.error("Invalid export filetype.")

    @cherrypy.expose
    def scaneventresultexport(self, id: str, type: str, filetype: str = "csv", dialect: str = "excel") -> str | bytes:
        """Export scan event results filtered by type as CSV or Excel."""
        dbh = self._get_dbh()
        data = dbh.scanResultEvent(id, type)
        if filetype.lower() in ["xlsx", "excel"]:
            rows = []
            import time
            for row in data:
                if row[4] == "ROOT":
                    continue
                lastseen = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(row[0]))
                datafield = str(row[1]).replace("<SFURL>", "").replace("</SFURL>", "")
                rows.append([lastseen, str(row[4]), str(row[3]), str(row[2]), row[13], datafield])
            fname = "SpiderFoot.xlsx"
            cherrypy.response.headers['Content-Disposition'] = f"attachment; filename={fname}"
            cherrypy.response.headers['Content-Type'] = (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            cherrypy.response.headers['Pragma'] = "no-cache"
            return self.buildExcel(rows, ["Updated", "Type", "Module", "Source", "F/P", "Data"], sheetNameIndex=1)
        if filetype.lower() == 'csv':
            from sfwebui import StringIO
            fileobj = StringIO()
            parser = csv.writer(fileobj, dialect=dialect)
            parser.writerow(["Updated", "Type", "Module", "Source", "F/P", "Data"])
            import time
            for row in data:
                if row[4] == "ROOT":
                    continue
                lastseen = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(row[0]))
                datafield = str(row[1]).replace("<SFURL>", "").replace("</SFURL>", "")
                parser.writerow([lastseen, str(row[4]), str(row[3]), str(row[2]), row[13], datafield])
            fname = "SpiderFoot.csv"
            cherrypy.response.headers['Content-Disposition'] = f"attachment; filename={fname}"
            cherrypy.response.headers['Content-Type'] = "application/csv"
            cherrypy.response.headers['Pragma'] = "no-cache"
            return fileobj.getvalue().encode('utf-8')
        return self.error("Invalid export filetype.")

    @cherrypy.expose
    def scaneventresultexportmulti(self, ids: str, filetype: str = "csv", dialect: str = "excel") -> str | bytes | None:
        """Export event results from multiple scans as CSV or Excel."""
        dbh = self._get_dbh()
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
            import time
            for row in data:
                if row[4] == "ROOT":
                    continue
                lastseen = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(row[0]))
                datafield = str(row[1]).replace("<SFURL>", "").replace("</SFURL>", "")
                rows.append([scaninfo[row[12]][0], lastseen, str(row[4]), str(row[3]), str(row[2]), row[13], datafield])
            if len(ids.split(',')) > 1 or scan_name == "":
                fname = "SpiderFoot.xlsx"
            else:
                fname = scan_name + "-SpiderFoot.xlsx"
            cherrypy.response.headers['Content-Disposition'] = f"attachment; filename={fname}"
            cherrypy.response.headers['Content-Type'] = (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            cherrypy.response.headers['Pragma'] = "no-cache"
            return self.buildExcel(
                rows,
                ["Scan Name", "Updated", "Type", "Module", "Source", "F/P", "Data"],
                sheetNameIndex=2,
            )
        if filetype.lower() == 'csv':
            from sfwebui import StringIO
            fileobj = StringIO()
            parser = csv.writer(fileobj, dialect=dialect)
            parser.writerow(["Scan Name", "Updated", "Type", "Module", "Source", "F/P", "Data"])
            import time
            for row in data:
                if row[4] == "ROOT":
                    continue
                lastseen = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(row[0]))
                datafield = str(row[1]).replace("<SFURL>", "").replace("</SFURL>", "")
                parser.writerow([
                    scaninfo[row[12]][0], lastseen,
                    str(row[4]), str(row[3]), str(row[2]),
                    row[13], datafield,
                ])
            if len(ids.split(',')) > 1 or scan_name == "":
                fname = "SpiderFoot.csv"
            else:
                fname = scan_name + "-SpiderFoot.csv"
            cherrypy.response.headers['Content-Disposition'] = f"attachment; filename={fname}"
            cherrypy.response.headers['Content-Type'] = "application/csv"
            cherrypy.response.headers['Pragma'] = "no-cache"
            return fileobj.getvalue().encode('utf-8')
        return self.error("Invalid export filetype.")

    @cherrypy.expose
    def scansearchresultexport(
        self, id: str,
        eventType: str | None = None,
        value: str | None = None,
        filetype: str = "csv",
        dialect: str = "excel",
    ) -> str | bytes | None:
        """Export scan search results as CSV or Excel."""
        data = self.searchBase(id, eventType, value)
        if not data:
            return None
        if filetype.lower() in ["xlsx", "excel"]:
            rows = []
            for row in data:
                if row[10] == "ROOT":
                    continue
                datafield = str(row[1]).replace("<SFURL>", "").replace("</SFURL>", "")
                rows.append([row[0], str(row[10]), str(row[3]), str(row[2]), row[11], datafield])
            cherrypy.response.headers['Content-Disposition'] = "attachment; filename=SpiderFoot.xlsx"
            cherrypy.response.headers['Content-Type'] = (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            cherrypy.response.headers['Pragma'] = "no-cache"
            return self.buildExcel(rows, ["Updated", "Type", "Module", "Source", "F/P", "Data"], sheetNameIndex=1)
        if filetype.lower() == 'csv':
            from sfwebui import StringIO
            fileobj = StringIO()
            parser = csv.writer(fileobj, dialect=dialect)
            parser.writerow(["Updated", "Type", "Module", "Source", "F/P", "Data"])
            for row in data:
                if row[10] == "ROOT":
                    continue
                datafield = str(row[1]).replace("<SFURL>", "").replace("</SFURL>", "")
                parser.writerow([row[0], str(row[10]), str(row[3]), str(row[2]), row[11], datafield])
            cherrypy.response.headers['Content-Disposition'] = "attachment; filename=SpiderFoot.csv"
            cherrypy.response.headers['Content-Type'] = "application/csv"
            cherrypy.response.headers['Pragma'] = "no-cache"
            return fileobj.getvalue().encode('utf-8')
        return self.error("Invalid export filetype.")

    @cherrypy.expose
    def scanexportjsonmulti(self, ids: str) -> bytes:
        """Export event results from multiple scans as a JSON file download."""
        dbh = self._get_dbh()
        scaninfo = list()
        scan_name = ""
        for id in ids.split(','):
            scan = dbh.scanInstanceGet(id)
            if scan is None:
                continue
            scan_name = scan[0]
            for row in dbh.scanResultEvent(id):
                scaninfo.append(row)
        if len(ids.split(',')) > 1 or scan_name == "":
            fname = "SpiderFoot.json"
        else:
            fname = scan_name + "-SpiderFoot.json"
        cherrypy.response.headers['Content-Disposition'] = f"attachment; filename={fname}"
        cherrypy.response.headers['Content-Type'] = "application/json; charset=utf-8"
        cherrypy.response.headers['Pragma'] = "no-cache"
        return json.dumps(scaninfo).encode('utf-8')

    @cherrypy.expose
    def scanviz(self, id: str, gexf: str = "0") -> str | None:
        """Generate scan result visualization as JSON graph or GEXF export."""
        if not id:
            return None
        dbh = self._get_dbh()
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
        cherrypy.response.headers['Content-Disposition'] = f"attachment; filename={fname}"
        cherrypy.response.headers['Content-Type'] = "application/gexf"
        cherrypy.response.headers['Pragma'] = "no-cache"
        return SpiderFootHelpers.buildGraphGexf([root], "SpiderFoot Export", data)

    @cherrypy.expose
    def scanvizmulti(self, ids: str, gexf: str = "1") -> str | None:
        """Generate combined visualization from multiple scans as JSON or GEXF."""
        dbh = self._get_dbh()
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
        if not data:
            return None
        if gexf == "0":
            return SpiderFootHelpers.buildGraphJson(roots, data)
        if len(ids.split(',')) > 1 or scan_name == "":
            fname = "SpiderFoot.gexf"
        else:
            fname = scan_name + "SpiderFoot.gexf"
        cherrypy.response.headers['Content-Disposition'] = f"attachment; filename={fname}"
        cherrypy.response.headers['Content-Type'] = "application/gexf"
        cherrypy.response.headers['Pragma'] = "no-cache"
        return SpiderFootHelpers.buildGraphGexf(roots, "SpiderFoot Export", data)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def scanreport(
        self, id: str, format: str = "json",
        include_results: str = "true",
        include_correlations: str = "true",
        include_logs: str = "false",
        include_graph: str = "false",
        max_results: str = "1000",
    ) -> dict:
        """Unified report generator — single entry point for comprehensive scan reports.

        Combines scan metadata, results, correlations, logs, and graph data
        into a single downloadable report. Supports JSON, CSV, and HTML formats.

        Args:
            id: Scan instance ID
            format: Output format (json, csv, html)
            include_results: Include scan event results
            include_correlations: Include correlation analysis
            include_logs: Include scan execution logs
            include_graph: Include relationship graph data
            max_results: Maximum number of result events to include
        """
        dbh = self._get_dbh()
        inc_results = str(include_results).lower() in ('true', '1', 'yes')
        inc_corr = str(include_correlations).lower() in ('true', '1', 'yes')
        inc_logs = str(include_logs).lower() in ('true', '1', 'yes')
        inc_graph = str(include_graph).lower() in ('true', '1', 'yes')

        try:
            limit = int(max_results)
        except (ValueError, TypeError):
            limit = 1000

        try:
            scan = dbh.scanInstanceGet(id)
            if not scan:
                return {"success": False, "error": "Scan not found"}

            # Normalize scan info (handle both DictRow and tuple)
            scan_row = list(scan[0]) if isinstance(scan, list) and scan else list(scan) if scan else []

            report = {
                "success": True,
                "report_format": format,
                "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "scan": {
                    "id": id,
                    "name": scan_row[0] if len(scan_row) > 0 else "",
                    "target": scan_row[1] if len(scan_row) > 1 else "",
                    "created": scan_row[2] if len(scan_row) > 2 else 0,
                    "started": scan_row[3] if len(scan_row) > 3 else 0,
                    "ended": scan_row[4] if len(scan_row) > 4 else 0,
                    "status": scan_row[5] if len(scan_row) > 5 else "",
                },
            }

            if inc_results:
                events = dbh.scanResultEvent(id, 'ALL')
                results = []
                for ev in (events or [])[:limit]:
                    ev_list = list(ev) if hasattr(ev, 'keys') else ev
                    results.append({
                        "timestamp": ev_list[0] if len(ev_list) > 0 else 0,
                        "data": ev_list[1] if len(ev_list) > 1 else "",
                        "module": ev_list[3] if len(ev_list) > 3 else "",
                        "type": ev_list[4] if len(ev_list) > 4 else "",
                        "confidence": ev_list[6] if len(ev_list) > 6 else 0,
                        "visibility": ev_list[7] if len(ev_list) > 7 else 0,
                        "risk": ev_list[8] if len(ev_list) > 8 else 0,
                    })
                report["results"] = results
                report["result_count"] = len(events or [])

            if inc_corr:
                try:
                    correlations = dbh.scanCorrelationList(id)
                    report["correlations"] = [
                        {
                            "title": list(c)[3] if len(list(c)) > 3 else "",
                            "risk": list(c)[4] if len(list(c)) > 4 else "",
                            "rule_name": list(c)[5] if len(list(c)) > 5 else "",
                            "description": list(c)[6] if len(list(c)) > 6 else "",
                        }
                        for c in (correlations or [])
                    ]
                except Exception:
                    report["correlations"] = []

            if inc_logs:
                try:
                    logs = dbh.scanLogs(id, limit=200)
                    report["logs"] = [
                        {
                            "timestamp": list(l)[0] if len(list(l)) > 0 else 0,
                            "component": list(l)[1] if len(list(l)) > 1 else "",
                            "type": list(l)[2] if len(list(l)) > 2 else "",
                            "message": list(l)[3] if len(list(l)) > 3 else "",
                        }
                        for l in (logs or [])
                    ]
                except Exception:
                    report["logs"] = []

            if inc_graph:
                try:
                    graph_data = dbh.scanResultEvent(id, filterFp=True)
                    root = scan_row[1] if len(scan_row) > 1 else ""
                    report["graph"] = json.loads(
                        SpiderFootHelpers.buildGraphJson([root], graph_data)
                    ) if graph_data else {}
                except Exception:
                    report["graph"] = {}

            # For non-JSON formats, set download headers
            if format.lower() == "csv":
                cherrypy.response.headers['Content-Type'] = "application/csv"
                cherrypy.response.headers['Content-Disposition'] = (
                    f"attachment; filename=SpiderFoot-{id}-report.csv"
                )
            elif format.lower() == "html":
                cherrypy.response.headers['Content-Type'] = "text/html"

            return report

        except Exception as e:
            return {"success": False, "error": str(e)}
