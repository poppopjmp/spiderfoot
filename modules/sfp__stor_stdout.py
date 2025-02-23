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

from spiderfoot import SpiderFootPlugin


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
        "_eventtypes": dict()
    }

    # Option descriptions
    optdescs = {
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

        if self.opts['_showonlyrequested']:
            if sfEvent.eventType in self.opts['_requested']:
                self.output(sfEvent)
        else:
            self.output(sfEvent)

# End of sfp__stor_stdout class
