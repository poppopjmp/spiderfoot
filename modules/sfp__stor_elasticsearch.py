# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:        sfp__stor_elasticsearch
# Purpose:     Store SpiderFoot scan results in Elasticsearch.
#
# Author:      <van1sh@van1shland.io>
#
# Created:     2025-03-10
# Copyright:   (c) Agostino Panico
# Licence:     MIT
# -------------------------------------------------------------------------------


try:
    from elasticsearch import Elasticsearch
    from elasticsearch.helpers import bulk
    from elasticsearch.exceptions import (
        AuthenticationException,
        ConnectionError,
        NotFoundError,
    )

    moduleEnabled = True
except ImportError:
    moduleEnabled = False

from spiderfoot import SpiderFootPlugin


class sfp__stor_elasticsearch(SpiderFootPlugin):
    """Storage module for pushing scan data into Elasticsearch."""

    meta = {
        "name": "Elasticsearch Storage",
        "summary": "Store SpiderFoot scan results in Elasticsearch.",
        "flags": [],
        "useCases": [],
        "categories": ["Storage"],
        "dataSource": {
            "website": "https://www.elastic.co/elasticsearch/",
            "model": "N/A",
            "references": [
                "https://www.elastic.co/guide/en/elasticsearch/reference/current/index.html",
                "https://www.elastic.co/guide/en/elasticsearch/client/python-api/current/index.html",
            ],
            "favIcon": "https://www.elastic.co/favicon.ico",
            "logo": "https://www.elastic.co/static-res/images/elastic-logo-200.png",
            "description": "Elasticsearch is a distributed, RESTful search and analytics engine "
            "capable of addressing a growing number of use cases.",
        },
    }

    # Default options
    opts = {
        "elasticsearch_host": "127.0.0.1",
        "elasticsearch_port": 9200,
        "elasticsearch_index_prefix": "spiderfoot-",
        "elasticsearch_ssl": False,
        "elasticsearch_api_key": "",
        "elasticsearch_username": "",
        "elasticsearch_password": "",
        "elasticsearch_timeout": 60,
        "elasticsearch_retry_on_timeout": True,
        "elasticsearch_max_retries": 3,
        "elasticsearch_verify_certs": True,
        "elasticsearch_bulk_size": 100,
        "elasticsearch_create_indexes": True,
        "enabled": True,
    }

    # Option descriptions
    optdescs = {
        "elasticsearch_host": "Elasticsearch server hostname or IP address.",
        "elasticsearch_port": "Elasticsearch server TCP port.",
        "elasticsearch_index_prefix": "Prefix for the Elasticsearch index name.",
        "elasticsearch_ssl": "Connect to Elasticsearch over SSL.",
        "elasticsearch_api_key": "Elasticsearch API key for authentication.",
        "elasticsearch_username": "Elasticsearch username for authentication.",
        "elasticsearch_password": "Elasticsearch password for authentication.",
        "elasticsearch_timeout": "Elasticsearch connection timeout in seconds.",
        "elasticsearch_retry_on_timeout": "Retry on timeout.",
        "elasticsearch_max_retries": "Maximum number of retries.",
        "elasticsearch_verify_certs": "Verify SSL certificates.",
        "elasticsearch_bulk_size": "Number of documents to index in a single bulk operation.",
        "elasticsearch_create_indexes": "Create Elasticsearch indexes if they don't exist.",
        "enabled": "Enable this module.",
    }

    es_client = None
    bulk_data = []
    errorState = False
    scanId = None
    indexName = None

    def setup(self, sfc, userOpts=dict()):
        super().setup(sfc, userOpts)

        if not moduleEnabled:
            self.error(
                "Elasticsearch module dependencies missing. Install them with 'pip install elasticsearch'"
            )
            self.errorState = True
            return

        if not self.opts["enabled"]:
            self.info("Module is not enabled")
            self.errorState = True
            return

    # What events is this module interested in for input
    def watchedEvents(self):
        return ["*"]

    # What events this module produces
    def producedEvents(self):
        return None  # This module does not produce any SpiderFoot events

    def initializeElasticsearch(self):
        """Initialize the Elasticsearch connection."""
        if self.es_client:
            return True

        try:
            # Build connection parameters
            es_args = {
                "hosts": [
                    {
                        "host": self.opts["elasticsearch_host"],
                        "port": self.opts["elasticsearch_port"],
                        "scheme": "https" if self.opts["elasticsearch_ssl"] else "http",
                    }
                ],
                "timeout": self.opts["elasticsearch_timeout"],
                "retry_on_timeout": self.opts["elasticsearch_retry_on_timeout"],
                "max_retries": self.opts["elasticsearch_max_retries"],
                "verify_certs": self.opts["elasticsearch_verify_certs"],
            }

            # Add authentication if provided
            if self.opts["elasticsearch_api_key"]:
                es_args["api_key"] = self.opts["elasticsearch_api_key"]
            elif (
                self.opts["elasticsearch_username"] and
                self.opts["elasticsearch_password"]
            ):
                es_args["basic_auth"] = (
                    self.opts["elasticsearch_username"],
                    self.opts["elasticsearch_password"],
                )

            # Create Elasticsearch client
            self.es_client = Elasticsearch(**es_args)

            # Check connection
            if not self.es_client.ping():
                self.error("Unable to connect to Elasticsearch")
                self.errorState = True
                return False

            if self.scanId:
                self.indexName = (
                    f"{self.opts['elasticsearch_index_prefix']}{self.scanId}"
                )
                self.debug(f"Using Elasticsearch index: {self.indexName}")

                # Create index if it doesn't exist and option is enabled
                if self.opts["elasticsearch_create_indexes"]:
                    self.create_index()

            return True
        except AuthenticationException as e:
            self.error(f"Elasticsearch authentication error: {e}")
        except ConnectionError as e:
            self.error(f"Elasticsearch connection error: {e}")
        except Exception as e:
            self.error(f"Elasticsearch error: {e}")

        self.errorState = True
        return False

    def create_index(self):
        """Create the Elasticsearch index if it doesn't exist."""
        try:
            if not self.es_client.indices.exists(index=self.indexName):
                # Define the index mapping for SpiderFoot events
                mapping = {
                    "mappings": {
                        "properties": {
                            "scanId": {"type": "keyword"},
                            "type": {"type": "keyword"},
                            "data": {"type": "text"},
                            "module": {"type": "keyword"},
                            "source": {"type": "keyword"},
                            "sourceEventHash": {"type": "keyword"},
                            "confidence": {"type": "integer"},
                            "visibility": {"type": "integer"},
                            "risk": {"type": "integer"},
                            "timestamp": {"type": "date"},
                            "sourceData": {"type": "text"},
                            "sourceDataSource": {"type": "keyword"},
                            "hash": {"type": "keyword"},
                        }
                    }
                }
                self.es_client.indices.create(
                    index=self.indexName, body=mapping)
                self.debug(f"Created Elasticsearch index: {self.indexName}")
        except Exception as e:
            self.error(f"Error creating Elasticsearch index: {e}")
            self.errorState = True

    def index_event(self, event):
        """Add an event to the bulk indexing queue."""
        if not self.es_client:
            if not self.initializeElasticsearch():
                return

        # Convert SpiderFoot event to dict for Elasticsearch
        doc = {
            "scanId": self.scanId,
            "type": event.eventType,
            "data": event.data,
            "module": event.module,
            "source": event.source,
            "sourceEventHash": event.sourceEventHash,
            "confidence": event.confidence,
            "visibility": event.visibility,
            "risk": event.risk,
            "timestamp": event.generated,
            "sourceData": event.sourceData if hasattr(event, "sourceData") else None,
            "sourceDataSource": (
                event.sourceDataSource if hasattr(
                    event, "sourceDataSource") else None
            ),
            "hash": event.hash,
        }

        # Add to bulk processing queue
        self.bulk_data.append(
            {"_index": self.indexName, "_source": doc, "_id": event.hash}
        )

        # Perform bulk indexing when we reach the threshold
        if len(self.bulk_data) >= self.opts["elasticsearch_bulk_size"]:
            self.process_bulk_data()

    def process_bulk_data(self):
        """Process the bulk indexing queue."""
        if not self.bulk_data:
            return

        if not self.es_client:
            if not self.initializeElasticsearch():
                self.bulk_data = []
                return

        try:
            success, failed = bulk(
                self.es_client, self.bulk_data, stats_only=True, refresh=True
            )
            self.debug(
                f"Indexed {success} events to Elasticsearch, {failed} failed")
        except Exception as e:
            self.error(f"Error indexing events to Elasticsearch: {e}")
            self.errorState = True

        # Clear the bulk data list
        self.bulk_data = []

    def setScanId(self, scanId):
        """Set the scan ID - called by SpiderFoot."""
        self.scanId = scanId
        self.indexName = f"{self.opts['elasticsearch_index_prefix']}{self.scanId}"
        self.debug(f"Set scan ID: {scanId}, index name: {self.indexName}")

    def handleEvent(self, event):
        """Handle events for storage in Elasticsearch."""
        if self.errorState:
            return

        # Don't process if we're not ready
        if not self.scanId:
            self.debug("No scanId set, not processing event")
            return

        # Initialize Elasticsearch if not already done
        if not self.es_client:
            if not self.initializeElasticsearch():
                return

        # Index the event
        try:
            self.index_event(event)
        except Exception as e:
            self.error(f"Error handling event for Elasticsearch: {e}")
            self.errorState = True

    def closeSession(self):
        """Called at the end of the scan to clean up."""
        try:
            # Process any remaining events in the bulk queue
            if self.bulk_data:
                self.process_bulk_data()

            # Refresh the index
            if self.es_client and self.indexName:
                self.es_client.indices.refresh(index=self.indexName)

            # Close the Elasticsearch client
            if self.es_client:
                self.es_client.close()
                self.es_client = None
                self.debug("Closed Elasticsearch connection")
        except Exception as e:
            self.error(f"Error closing Elasticsearch session: {e}")

    def asdict(self):
        """Return a dictionary of attributes of this instance."""
        exclude_list = ["sf", "opts", "es_client", "bulk_data"]
        return {
            k: v
            for k, v in self.__dict__.items()
            if k not in exclude_list and not k.startswith("_")
        }

    def dbh(self, scanId):
        """
        Connect to the database. Since we're not using a database,
        just initialize the Elasticsearch connection.
        """
        self.setScanId(scanId)
        return self.initializeElasticsearch()
