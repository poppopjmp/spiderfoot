# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         sfp_stor_db
# Purpose:      SpiderFoot plug-in for storing events to the local SpiderFoot
#               SQLite database.
#
# Author:      Steve Micallef <steve@binarypool.com>
#
# Created:     14/05/2012
# Copyright:   (c) Steve Micallef 2012
# Licence:     MIT
# -------------------------------------------------------------------------------

from elasticsearch import Elasticsearch
from spiderfoot import SpiderFootPlugin


class sfp__stor_db(SpiderFootPlugin):
    """SpiderFoot plug-in for storing events to the local SpiderFoot SQLite
    database.

    This class is responsible for storing scan results into the back-end
    SpiderFoot database.
    """

    meta = {
        'name': "Storage",
        'summary': "Stores scan results into the back-end SpiderFoot database. You will need this."
    }

    _priority = 0

    # Default options
    opts = {
        'maxstorage': 1024,  # max bytes for any piece of info stored (0 = unlimited)
        '_store': True,
        'use_elasticsearch': False,
        'elasticsearch_host': 'localhost',
        'elasticsearch_port': 9200,
        'elasticsearch_index': 'spiderfoot'
    }

    # Option descriptions
    optdescs = {
        'maxstorage': "Maximum bytes to store for any piece of information retrieved (0 = unlimited.)",
        'use_elasticsearch': "Store events in ElasticSearch instead of SQLite.",
        'elasticsearch_host': "ElasticSearch host.",
        'elasticsearch_port': "ElasticSearch port.",
        'elasticsearch_index': "ElasticSearch index name."
    }

    def setup(self, sfc, userOpts=dict()):
        """Set up the module with user options.

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
        """Define the events this module is interested in for input.

        Returns:
            list: List of event types
        """
        return ["*"]

    def handleEvent(self, sfEvent):
        """Handle events sent to this module.

        Args:
            sfEvent: SpiderFoot event
        """
        if not self.opts['_store']:
            return

        if self.opts['use_elasticsearch']:
            event_data = {
                'eventType': sfEvent.eventType,
                'data': sfEvent.data,
                'module': sfEvent.module,
                'sourceEvent': sfEvent.sourceEvent.data if sfEvent.sourceEvent else None,
                'generated': sfEvent.generated
            }
            self.es.index(index=self.opts['elasticsearch_index'], body=event_data)
            return

        if self.opts['maxstorage'] != 0 and len(sfEvent.data) > self.opts['maxstorage']:
            self.debug("Storing an event: " + sfEvent.eventType)
            self.__sfdb__.scanEventStore(self.getScanId(), sfEvent, self.opts['maxstorage'])
            return

        self.debug("Storing an event: " + sfEvent.eventType)
        self.__sfdb__.scanEventStore(self.getScanId(), sfEvent)

# End of sfp__stor_db class
