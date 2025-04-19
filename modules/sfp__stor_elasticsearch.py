# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         sfp__stor_elasticsearch
# Purpose:      SpiderFoot plug-in for storing events to ElasticSearch.
#
# Author:      <van1sh@van1shland.io>
#
# Created:     2025-03-15
# Copyright:   (c) poppopjmp 2025
# Licence:     MIT
# -------------------------------------------------------------------------------

from elasticsearch import Elasticsearch
from spiderfoot import SpiderFootPlugin
import threading


class sfp__stor_elasticsearch(SpiderFootPlugin):
    """SpiderFoot plug-in for storing events to an ElasticSearch instance.

    This module sends scan results to an external ElasticSearch instance
    for storage and analysis.
    """

    meta = {
        'name': "ElasticSearch Storage",
        'summary': "Stores scan results into an ElasticSearch instance for indexing and visualization."
    }

    _priority = 0

    # Default options
    opts = {
        'enabled': False,
        'host': 'localhost',
        'port': 9200,
        'index': 'spiderfoot',
        'use_ssl': False,
        'verify_certs': True,
        'username': '',
        'password': '',
        'api_key': '',
        'bulk_size': 100,  # Number of events to bulk insert at once
        'timeout': 30,  # Connection timeout in seconds
    }

    # Option descriptions
    optdescs = {
        'enabled': "Enable storing events to ElasticSearch",
        'host': "ElasticSearch host",
        'port': "ElasticSearch port",
        'index': "ElasticSearch index name",
        'use_ssl': "Use SSL for the connection",
        'verify_certs': "Verify SSL certificates",
        'username': "ElasticSearch username (if using authentication)",
        'password': "ElasticSearch password (if using authentication)",
        'api_key': "ElasticSearch API key (if using API key authentication)",
        'bulk_size': "Number of events to bulk insert at once",
        'timeout': "Connection timeout in seconds"
    }

    def setup(self, sfc, userOpts=dict()):
        """Set up the module with user options.

        Args:
            sfc: SpiderFoot instance
            userOpts (dict): User options
        """
        self.sf = sfc
        self.es = None
        self.buffer = []  # Buffer for bulk insertion
        self.errorState = False
        self.lock = threading.Lock()  # Ensure thread-safe operations

        for opt in list(userOpts.keys()):
            self.opts[opt] = userOpts[opt]

        if not self.opts['enabled']:
            self.debug("ElasticSearch storage module not enabled")
            return

        # Set up ElasticSearch connection
        try:
            es_conn_config = {
                'hosts': [f"{self.opts['host']}:{self.opts['port']}"],
                'timeout': self.opts['timeout'],
                'use_ssl': self.opts['use_ssl'],
                'verify_certs': self.opts['verify_certs'],
            }

            # Add authentication if provided
            if self.opts['username'] and self.opts['password']:
                es_conn_config['http_auth'] = (
                    self.opts['username'], self.opts['password'])
            elif self.opts['api_key']:
                es_conn_config['api_key'] = self.opts['api_key']

            self.es = Elasticsearch(**es_conn_config)

            if not self.es.ping():
                self.error("Could not connect to ElasticSearch")
                self.errorState = True
                return

            self.debug(
                f"Connected to ElasticSearch at {self.opts['host']}:{self.opts['port']}")
        except Exception as e:
            self.error(f"ElasticSearch connection failed: {e}")
            self.errorState = True

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
        if not self.opts['enabled'] or self.errorState or not self.es:
            return

        # Prepare document for ElasticSearch
        event_data = {
            'scan_id': self.getScanId(),
            'event_type': sfEvent.eventType,
            'data': sfEvent.data,
            'module': sfEvent.module,
            'source_event': sfEvent.sourceEvent.data if sfEvent.sourceEvent else None,
            'source_event_hash': sfEvent.sourceEventHash if hasattr(sfEvent, 'sourceEventHash') else None,
            'generated': sfEvent.generated,
            '@timestamp': sfEvent.generated
        }

        # Add to buffer for bulk insertion
        with self.lock:
            self.buffer.append({
                '_index': self.opts['index'],
                '_source': event_data
            })

        # If buffer reaches bulk size, insert documents
        if len(self.buffer) >= self.opts['bulk_size']:
            self._flush_buffer()

        # Store correlation data for interscan correlation
        self._store_correlation_data(sfEvent)

    def _flush_buffer(self):
        """Insert buffered events to ElasticSearch."""
        if not self.buffer:
            return

        try:
            from elasticsearch.helpers import bulk
            with self.lock:
                success, errors = bulk(self.es, self.buffer, refresh=True)
                self.debug(
                    f"Inserted {success} events to ElasticSearch, {len(errors)} errors")

                if errors:
                    for error in errors:
                        self.error(f"ElasticSearch insertion error: {error}")

                # Clear the buffer
                self.buffer = []
        except Exception as e:
            self.error(f"Failed to bulk insert events to ElasticSearch: {e}")

    def _store_correlation_data(self, sfEvent):
        """Store correlation data for interscan correlation.

        Args:
            sfEvent: SpiderFoot event
        """
        try:
            # Ensure thread-safe operations when accessing shared resources
            with self.lock:
                # Store correlation data in ElasticSearch
                correlation_data = {
                    'scan_id': self.getScanId(),
                    'event_type': sfEvent.eventType,
                    'data': sfEvent.data,
                    'module': sfEvent.module,
                    'source_event': sfEvent.sourceEvent.data if sfEvent.sourceEvent else None,
                    'source_event_hash': sfEvent.sourceEventHash if hasattr(sfEvent, 'sourceEventHash') else None,
                    'generated': sfEvent.generated,
                    '@timestamp': sfEvent.generated,
                    'correlation': True
                }
                self.buffer.append({
                    '_index': self.opts['index'],
                    '_source': correlation_data
                })
        except Exception as e:
            self.error(f"Error storing correlation data: {e}")
            self.errorState = True

    def shutdown(self):
        """Clean up after this module."""
        # Flush any remaining events in the buffer
        if self.opts['enabled'] and self.es and self.buffer:
            self._flush_buffer()

# End of sfp__stor_elasticsearch class
