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
import threading
import time
from spiderfoot import SpiderFootPlugin


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
        self.buffer_lock = threading.Lock()  # Thread safety for buffer
        self.errorState = False
        self.connection_retries = 0
        self.max_connection_retries = 3

        for opt in list(userOpts.keys()):
            self.opts[opt] = userOpts[opt]

        if not self.opts['enabled']:
            self.debug("ElasticSearch storage module not enabled")
            return        # Set up ElasticSearch connection with retry logic
        self._setup_elasticsearch_connection()

    def _setup_elasticsearch_connection(self):
        """Setup Elasticsearch connection with retry logic."""
        try:
            es_conn_config = {
                'hosts': [f"{self.opts['host']}:{self.opts['port']}"],
                'request_timeout': self.opts['timeout'],  # FIXED: Use request_timeout instead of timeout
                'use_ssl': self.opts['use_ssl'],
                'verify_certs': self.opts['verify_certs'],
                'retry_on_timeout': True,
                'max_retries': 3,
                'retry_on_status': [429, 502, 503, 504]
            }

            # Add authentication if provided
            if self.opts['username'] and self.opts['password']:
                es_conn_config['http_auth'] = (
                    self.opts['username'], self.opts['password'])
            elif self.opts['api_key']:
                es_conn_config['api_key'] = self.opts['api_key']

            self.es = Elasticsearch(**es_conn_config)

            # Test connection and create index if needed
            if not self._test_connection():
                self.error("Could not connect to ElasticSearch")
                self.errorState = True
                return

            # Create index if it doesn't exist
            self._ensure_index_exists()

            self.debug(
                f"Connected to ElasticSearch at {self.opts['host']}:{self.opts['port']}")
            self.connection_retries = 0  # Reset retry counter on success
            
        except Exception as e:
            self.error(f"ElasticSearch connection failed: {e}")
            self.errorState = True

    def _test_connection(self):
        """Test Elasticsearch connection with retry logic."""
        for attempt in range(self.max_connection_retries):
            try:
                if self.es.ping():
                    return True
                else:
                    self.debug(f"ElasticSearch ping failed (attempt {attempt + 1})")
            except Exception as e:
                self.debug(f"ElasticSearch connection test failed (attempt {attempt + 1}): {e}")
            
            if attempt < self.max_connection_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
        
        return False

    def _ensure_index_exists(self):
        """Ensure the target index exists with proper mapping."""
        try:
            if not self.es.indices.exists(index=self.opts['index']):
                # Create index with proper mapping
                mapping = {
                    "mappings": {
                        "properties": {
                            "scan_id": {"type": "keyword"},
                            "event_type": {"type": "keyword"},
                            "data": {"type": "text"},
                            "module": {"type": "keyword"},
                            "source_event": {"type": "text"},
                            "source_event_hash": {"type": "keyword"},
                            "generated": {"type": "date", "format": "epoch_millis"},
                            "@timestamp": {"type": "date", "format": "epoch_millis"}
                        }
                    }
                }
                self.es.indices.create(index=self.opts['index'], body=mapping)
                self.debug(f"Created ElasticSearch index: {self.opts['index']}")
        except Exception as e:
            self.error(f"Failed to create ElasticSearch index: {e}")
            # Don't fail completely, index might exist with different mapping

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

        # Test connection health and reconnect if needed
        if not self._test_connection():
            self.debug("ElasticSearch connection lost, attempting to reconnect...")
            self._setup_elasticsearch_connection()
            if self.errorState:
                return

        # Prepare document for ElasticSearch
        event_data = {
            'scan_id': self.getScanId(),
            'event_type': sfEvent.eventType,
            'data': sfEvent.data,
            'module': sfEvent.module,
            'source_event': sfEvent.sourceEvent.data if sfEvent.sourceEvent else None,
            'source_event_hash': getattr(sfEvent, 'sourceEventHash', None),
            'generated': sfEvent.generated,
            '@timestamp': sfEvent.generated
        }

        # Thread-safe buffer management
        with self.buffer_lock:
            self.buffer.append({
                '_index': self.opts['index'],
                '_source': event_data
            })

            # If buffer reaches bulk size, flush it
            if len(self.buffer) >= self.opts['bulk_size']:
                self._flush_buffer()

    def _flush_buffer(self):
        """Insert buffered events to ElasticSearch with retry logic."""
        if not self.buffer:
            return

        buffer_to_flush = self.buffer.copy()
        
        try:
            from elasticsearch.helpers import bulk
            
            # Retry logic for bulk operations
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    success, errors = bulk(
                        self.es, 
                        buffer_to_flush, 
                        refresh=True,
                        timeout=f"{self.opts['timeout']}s",
                        max_retries=3,
                        retry_on_timeout=True
                    )
                    
                    self.debug(f"Inserted {success} events to ElasticSearch")
                    
                    if errors:
                        for error in errors:
                            self.error(f"ElasticSearch insertion error: {error}")
                    
                    # Clear the buffer on success
                    self.buffer = []
                    return
                    
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise e
                    else:
                        self.debug(f"Bulk insert attempt {attempt + 1} failed: {e}, retrying...")
                        time.sleep(2 ** attempt)
                        
        except Exception as e:
            self.error(f"Failed to bulk insert events to ElasticSearch: {e}")
            # Don't clear buffer on failure - events will be retried later
            # But limit buffer size to prevent memory issues
            if len(self.buffer) > self.opts['bulk_size'] * 10:
                self.error("ElasticSearch buffer too large, discarding oldest events")
                self.buffer = self.buffer[-self.opts['bulk_size']:]

    def shutdown(self):
        """Clean up after this module."""
        # Flush any remaining events in the buffer
        if self.opts['enabled'] and self.es and self.buffer:
            self._flush_buffer()

# End of sfp__stor_elasticsearch class
