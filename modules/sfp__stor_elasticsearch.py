# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         sfp__stor_elasticsearch
# Purpose:      SpiderFoot plug-in for storing events to an ElasticSearch cluster.
#
# Author:      Agostino Panico <van1sh@van1shland.io>
#
# Created:     24/02/2025
# Copyright:   (c) poppopjmp 2025
# Licence:     MIT
# -------------------------------------------------------------------------------

from elasticsearch import Elasticsearch
from spiderfoot import SpiderFootPlugin


class sfp__stor_elasticsearch(SpiderFootPlugin):
    """
    SpiderFoot plug-in for storing events to an ElasticSearch cluster.

    This class is responsible for storing scan results into an ElasticSearch cluster.
    """

    meta = {
        'name': "ElasticSearch Storage",
        'summary': "Stores scan results into an ElasticSearch cluster."
    }

    _priority = 0

    # Default options
    opts = {
        'host': 'localhost',
        'port': 9200,
        'index': 'spiderfoot',
        'use_https': False,  # Add option to use HTTPS
        'skip_cert_verification': False  # Add option to skip certificate verification
    }

    # Option descriptions
    optdescs = {
        'host': "ElasticSearch host.",
        'port': "ElasticSearch port.",
        'index': "ElasticSearch index name.",
        'use_https': "Use HTTPS to connect to ElasticSearch.",
        'skip_cert_verification': "Skip certificate verification when using HTTPS."
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

        scheme = 'https' if self.opts['use_https'] else 'http'
        verify_certs = not self.opts['skip_cert_verification']

        self.es = Elasticsearch([{
            'host': self.opts['host'],
            'port': self.opts['port'],
            'scheme': scheme
        }], verify_certs=verify_certs)

    def watchedEvents(self):
        """
        Define the events this module is interested in for input.

        Returns:
            list: List of event types
        """
        return ["*"]

    def handleEvent(self, sfEvent):
        """
        Handle events sent to this module.

        Args:
            sfEvent: SpiderFoot event
        """
        if not self.opts['_store']:
            return

        event_data = {
            'eventType': sfEvent.eventType,
            'data': sfEvent.data,
            'module': sfEvent.module,
            'sourceEvent': sfEvent.sourceEvent.data if sfEvent.sourceEvent else None,
            'generated': sfEvent.generated
        }

        self.es.index(index=self.opts['index'], body=event_data)

# End of sfp__stor_elasticsearch class
