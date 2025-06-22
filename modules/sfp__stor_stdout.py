# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         sfp_stor_stdout
# Purpose:      SpiderFoot plug-in for dumping events to standard output.
#
# Author:      Steve Micallef <steve@binarypool.com>
#
# Created:     22/10/2018
# Copyright:   (c) Steve Micallef 2018
# Licence:     MIT
# -------------------------------------------------------------------------------

import json

from spiderfoot import SpiderFootPlugin


class sfp__stor_stdout(SpiderFootPlugin):

    meta = {
        'name': "Command-line output",
        'summary': "Dumps output to standard out. Used for when a SpiderFoot scan is run via the command-line."
    }

    _priority = 0

    def __init__(self):
        super().__init__()
        self.firstEvent = True
        self.opts = {
            "_format": "tab",  # tab, csv, json
            "_requested": [],
            "_showonlyrequested": False,
            "_stripnewline": False,
            "_showsource": False,
            "_csvdelim": ",",
            "_maxlength": 0,
            "_eventtypes": {}  # Changed from [] to {}
        }

    # Option descriptions
    optdescs = {
    }

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        # Always start with a fresh opts dict for this instance
        for opt in list(userOpts.keys()):
            self.opts[opt] = userOpts[opt]
        # Also allow 'enabled' to be set via userOpts
        if 'enabled' in userOpts:
            self.opts['enabled'] = userOpts['enabled']
        # For backward compatibility, treat '_store' as 'enabled'
        if '_store' in userOpts:
            self.opts['enabled'] = bool(userOpts['_store'])
        self.firstEvent = True

    # What events is this module interested in for input
    # Because this is a storage plugin, we are interested in everything so we
    # can store all events for later analysis.    def watchedEvents(self):
        return ["*"]

    def output(self, event):
        # If the module is disabled, do not output anything
        if not self.opts.get('enabled', True):
            return
        d = self.opts['_csvdelim']
        # Handle None data gracefully
        if event.data is None:
            data = "Null Data"
        elif isinstance(event.data, (list, dict)):
            data = str(event.data)
        else:
            data = event.data

        if not isinstance(data, str):
            data = str(event.data)

        # Handle case where sourceEvent might be None
        if event.sourceEvent is not None:
            if event.sourceEvent.data is None:
                srcdata = "Null Data"
            elif isinstance(event.sourceEvent.data, (list, dict)):
                srcdata = str(event.sourceEvent.data)
            else:
                srcdata = event.sourceEvent.data

            if not isinstance(srcdata, str):
                srcdata = str(event.sourceEvent.data)
        else:
            srcdata = ""

        if self.opts['_stripnewline']:
            data = data.replace("\n", " ").replace("\r", "")
            srcdata = srcdata.replace("\n", " ").replace("\r", "")

        if "<SFURL>" in data:
            data = data.replace("<SFURL>", "").replace("</SFURL>", "")
        if "<SFURL>" in srcdata:
            srcdata = srcdata.replace("<SFURL>", "").replace("</SFURL>", "")

        if self.opts['_maxlength'] > 0:
            data = data[:self.opts['_maxlength']]
            srcdata = srcdata[:self.opts['_maxlength']]

        # Gracefully handle unknown event types
        event_type = self.opts['_eventtypes'].get(event.eventType, event.eventType)

        try:
            if self.opts['_format'] == "tab":
                if self.opts['_showsource']:
                    print(
                        f"{event.module.ljust(30)}\t{event_type.ljust(45)}\t{srcdata}\t{data}")
                else:
                    print(f"{event.module.ljust(30)}\t{event_type.ljust(45)}\t{data}")

            if self.opts['_format'] == "csv":
                print((event.module + d + event_type + d + srcdata + d + data))

            if self.opts['_format'] == "json":
                d = event.asDict()
                d['type'] = event_type
                if self.firstEvent:
                    self.firstEvent = False
                else:
                    print(",")
                print(json.dumps(d), end='')
        except Exception as e:
            self.error(f"Stdout write failed: {e}")

    # Handle events sent to this module
    def handleEvent(self, sfEvent):
        if not self.opts.get('enabled', True):
            return
        if sfEvent.eventType == "ROOT":
            return
        if self.opts.get('_showonlyrequested', False):
            if sfEvent.eventType in self.opts.get('_requested', []):
                self.output(sfEvent)
        else:
            self.output(sfEvent)

# End of sfp__stor_stdout class
