import cherrypy
import csv
import json
from io import StringIO
from spiderfoot import SpiderFootDb, SpiderFootHelpers

class ExportEndpoints:
    @cherrypy.expose
    def scanexportlogs(self, id, dialect="excel"):
        from sfwebui import SpiderFootDb
        dbh = SpiderFootDb(self.config)
        try:
            data = dbh.scanLogs(id)
        except Exception:
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
    def scancorrelationsexport(self, id, filetype="csv", dialect="excel"):
        from sfwebui import SpiderFootDb
        dbh = SpiderFootDb(self.config)
        try:
            data = dbh.scanCorrelations(id)
        except Exception:
            return self.error("Scan ID not found")
        try:
            scan = dbh.scanInstanceGet(id)
        except Exception:
            return self.error("Scan ID not found")
        headings = ["Rule Name", "Correlation", "Risk", "Description"]
        if filetype.lower() in ["xlsx", "excel"]:
            cherrypy.response.headers['Content-Disposition'] = f"attachment; filename=SpiderFoot-{id}-correlations.xlsx"
            cherrypy.response.headers['Content-Type'] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
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
    def scaneventresultexport(self, id, type, filetype="csv", dialect="excel"):
        from sfwebui import SpiderFootDb
        dbh = SpiderFootDb(self.config)
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
            cherrypy.response.headers['Content-Type'] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
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
    def scaneventresultexportmulti(self, ids, filetype="csv", dialect="excel"):
        from sfwebui import SpiderFootDb
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
            cherrypy.response.headers['Content-Type'] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            cherrypy.response.headers['Pragma'] = "no-cache"
            return self.buildExcel(rows, ["Scan Name", "Updated", "Type", "Module", "Source", "F/P", "Data"], sheetNameIndex=2)
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
                parser.writerow([scaninfo[row[12]][0], lastseen, str(row[4]), str(row[3]), str(row[2]), row[13], datafield])
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
    def scansearchresultexport(self, id, eventType=None, value=None, filetype="csv", dialect="excel"):
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
            cherrypy.response.headers['Content-Type'] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
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
    def scanexportjsonmulti(self, ids):
        dbh = SpiderFootDb(self.config)
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
    def scanviz(self, id, gexf="0"):
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
        cherrypy.response.headers['Content-Disposition'] = f"attachment; filename={fname}"
        cherrypy.response.headers['Content-Type'] = "application/gexf"
        cherrypy.response.headers['Pragma'] = "no-cache"
        return SpiderFootHelpers.buildGraphGexf([root], "SpiderFoot Export", data)

    @cherrypy.expose
    def scanvizmulti(self, ids, gexf="1"):
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
