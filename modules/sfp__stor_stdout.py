# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         sfp_stor_stdout
# Purpose:      SpiderFoot plug-in for dumping events to standard output.
#
# Author:      Steve Micallef <steve@binarypool.com>
# Maintainer:  poppopjmp
#
# Created:     22/10/2018
# Copyright:   (c) Steve Micallef 2018
# Licence:     MIT
# -------------------------------------------------------------------------------

import json
from elasticsearch import Elasticsearch
from spiderfoot import SpiderFootPlugin
# Module now uses the logging from the SpiderFootPlugin base class


class sfp__stor_stdout(SpiderFootPlugin):
    """
    SpiderFoot plug-in for dumping events to standard output.

    This class is responsible for outputting scan results to the standard output.
    """

    meta = {
        'name': "Command-line output",
        'summary': "Dumps output to standard out. Used for when a SpiderFoot scan is run via the command-line."
    }

    _priority = 0
    firstEvent = True

    # Default options
    opts = {
        "_format": "tab",  # tab, csv, json
        "_requested": [],
        "_showonlyrequested": False,
        "_stripnewline": False,
        "_showsource": False,
        "_csvdelim": ",",
        "_maxlength": 0,
        "_eventtypes": dict(),
        'use_elasticsearch': False,
        'elasticsearch_host': 'localhost',
        'elasticsearch_port': 9200,
        'elasticsearch_index': 'spiderfoot'
    }

    # Option descriptions
    optdescs = {
        'use_elasticsearch': "Store events in ElasticSearch instead of standard output.",
        'elasticsearch_host': "ElasticSearch host.",
        'elasticsearch_port': "ElasticSearch port.",
        'elasticsearch_index': "ElasticSearch index name.",
        'fileextensions': "File extensions to include in results",
        'maxfilesize': "Maximum file size to download for processing (bytes)",
        'maxage': "Maximum age of data to be considered valid (hours)",
        'usecache': "Use cached data where available",
        'type': "Event types to be processed",
        '_dnsserver': "Override the default resolver",
        '_fetchtimeout': "Seconds before giving up on a HTTP request",
        'ssl_verify': "Verify SSL certificates",
        'sslcertwarndays': "Warn about expiring certs days in advance",
        '_useragent': "User-Agent string to use",
        '_dnsserver_recursive': "If specified, use this resolver for recursive lookups",
        'socksProxy': "SOCKS proxy",
    }

    def setup(self, sfc, userOpts=dict()):
        """
        Set up the module with user options.

        Args:
            sfc: SpiderFoot instance
            userOpts (dict): User options
        """
        self.sf = sfc

        for opt in list(userOpts.keys()):
            self.opts[opt] = userOpts[opt]

        if self.opts['use_elasticsearch']:
            self.es = Elasticsearch([{'host': self.opts['elasticsearch_host'], 'port': self.opts['elasticsearch_port']}])

    def watchedEvents(self):
        """
        Define the events this module is interested in for input.

        Returns:
            list: List of event types
        """
        return ["*"]

    def output(self, event):
        """
        Output the event data to standard output.

        Args:
            event: SpiderFoot event
        """
        d = self.opts['_csvdelim']
        if type(event.data) in [list, dict]:
            data = str(event.data)
        else:
            data = event.data

        if not isinstance(data, str):
            data = str(event.data)

        if type(event.sourceEvent.data) in [list, dict]:
            srcdata = str(event.sourceEvent.data)
        else:
            srcdata = event.sourceEvent.data

        if not isinstance(srcdata, str):
            srcdata = str(event.sourceEvent.data)

        if self.opts['_stripnewline']:
            data = data.replace("\n", " ").replace("\r", "")
            srcdata = srcdata.replace("\n", " ").replace("\r", "")

        if "<SFURL>" in data:
            data = data.replace("<SFURL>", "").replace("</SFURL>", "")
        if "<SFURL>" in srcdata:
            srcdata = srcdata.replace("<SFURL>", "").replace("</SFURL>", "")

        if self.opts['_maxlength'] > 0:
            data = data[0:self.opts['_maxlength']]
            srcdata = srcdata[0:self.opts['_maxlength']]

        if self.opts['_format'] == "tab":
            event_type = self.opts['_eventtypes'][event.eventType]
            if self.opts['_showsource']:
                print(f"{event.module.ljust(30)}\t{event_type.ljust(45)}\t{srcdata}\t{data}")
            else:
                print(f"{event.module.ljust(30)}\t{event_type.ljust(45)}\t{data}")

        if self.opts['_format'] == "csv":
            print((event.module + d + self.opts['_eventtypes'][event.eventType] + d + srcdata + d + data))

        if self.opts['_format'] == "json":
            d = event.asDict()
            d['type'] = self.opts['_eventtypes'][event.eventType]
            if self.firstEvent:
                self.firstEvent = False
            else:
                print(",")
            print(json.dumps(d), end='')

    def handleEvent(self, sfEvent):
        """
        Handle events sent to this module.

        Args:
            sfEvent: SpiderFoot event
        """
        if sfEvent.eventType == "ROOT":
            return

        if self.opts['use_elasticsearch']:
            event_data = {
                'eventType': sfEvent.eventType,
                'data': sfEvent.data,
                'module': sfEvent.module,
                'sourceEvent': sfEvent.sourceEvent.data if sfEvent.sourceEvent else None,
                'generated': sfEvent.generated
            }
            try:
                self.es.index(index=self.opts['elasticsearch_index'], body=event_data)
            except Exception as e:
                self.self.error(f"Error indexing to ElasticSearch: {e}")
            return

        if self.opts['_showonlyrequested']:
            if sfEvent.eventType in self.opts['_requested']:
                self.output(sfEvent)
        else:
            self.output(sfEvent)

# End of sfp__stor_stdout class
