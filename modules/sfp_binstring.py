from __future__ import annotations

"""SpiderFoot plug-in module: binstring."""

# coding: utf-8
# -------------------------------------------------------------------------------
# Name:         sfp_binstring
# Purpose:      Identify strings in binary content.
#
# Author:      Steve Micallef <steve@binarypool.com>
#
# Created:     03/12/2016
# Copyright:   (c) Steve Micallef
# Licence:     MIT
# -------------------------------------------------------------------------------

import string

from spiderfoot import SpiderFootEvent, SpiderFootHelpers
from spiderfoot.modern_plugin import SpiderFootModernPlugin


class sfp_binstring(SpiderFootModernPlugin):
    """SpiderFoot plugin to identify strings in binary content."""
    meta = {
        'name': "Binary String Extractor",
        'summary': "Attempt to identify strings in binary content.",
        'flags': ["errorprone"],
        'useCases': ["Footprint"],
        'categories': ["Content Analysis"]
    }

    # Default options
    opts = {
        'minwordsize': 5,
        'maxwords': 100,
        'maxfilesize': 1000000,
        'usedict': True,
        'fileexts': ['png', 'gif', 'jpg', 'jpeg', 'tiff', 'tif',
                     'ico', 'flv', 'mp4', 'mp3', 'avi', 'mpg',
                     'mpeg', 'dat', 'mov', 'swf', 'exe', 'bin'],
        'filterchars': '#}{|%^&*()=+,;[]~'
    }

    # Option descriptions
    optdescs = {
        'minwordsize': "Upon finding a string in a binary, ensure it is at least this length. Helps weed out false positives.",
        'usedict': "Use the dictionary to further reduce false positives - any string found must contain a word from the dictionary (can be very slow, especially for larger files).",
        'fileexts': "File types to fetch and analyse.",
        'maxfilesize': "Maximum file size in bytes to download for analysis.",
        'maxwords': "Stop reporting strings from a single binary after this many are found.",
        'filterchars': "Ignore strings with these characters, as they may just be garbage ASCII."
    }

    results = list()
    d = None
    n = None
    fq = None

    def setup(self, sfc: SpiderFoot, userOpts: dict = None) -> None:
        """Set up the module."""
        super().setup(sfc, userOpts or {})
        self.results = list()
        self.__dataSource__ = "Target Website"

        self.d = SpiderFootHelpers.dictionaryWordsFromWordlists()
    def getStrings(self, content):
        """Get Strings."""
        words = list()
        result = ""

        if not content:
            return None

        for c in content:
            c = str(c)
            if len(words) >= self.opts['maxwords']:
                break
            if c in string.printable and c not in string.whitespace:
                result += c
                continue
            if len(result) >= self.opts['minwordsize']:
                if self.opts['usedict']:
                    accept = False
                    for w in self.d:
                        if result.startswith(w) or result.endswith(w):
                            accept = True
                            break

                if self.opts['filterchars']:
                    accept = True
                    for x in self.opts['filterchars']:
                        if x in result:
                            accept = False
                            break

                if not self.opts['filterchars'] and not self.opts['usedict']:
                    accept = True

                if accept:
                    words.append(result)

                result = ""

        if len(words) == 0:
            return None

        return words

    # What events is this module interested in for input
    def watchedEvents(self) -> list:
        """Return the list of events this module watches."""
        return ["LINKED_URL_INTERNAL"]

    # What events this module produces
    def producedEvents(self) -> list:
        """Return the list of events this module produces."""
        return ["RAW_FILE_META_DATA"]

    # Handle events sent to this module
    def handleEvent(self, event: SpiderFootEvent) -> None:
        """Handle an event received by this module."""
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data

        self.debug(f"Received event, {eventName}, from {srcModuleName}")

        if eventData in self.results:
            return

        self.results.append(eventData)

        for fileExt in self.opts['fileexts']:
            if eventData.lower().endswith(f".{fileExt.lower()}") or f".{fileExt.lower()}?" in eventData.lower():
                res = self.fetch_url(
                    eventData,
                    useragent=self.opts['_useragent'],
                    disableContentEncoding=True,
                    sizeLimit=self.opts['maxfilesize'],
                    verify=False
                )

                if not res:
                    continue

                self.debug(f"Searching {eventData} for strings")
                words = self.getStrings(res['content'])

                if words:
                    wordstr = '\n'.join(words[0:self.opts['maxwords']])
                    evt = SpiderFootEvent(
                        "RAW_FILE_META_DATA", wordstr, self.__name__, event)
                    self.notifyListeners(evt)

# End of sfp_binstring class
