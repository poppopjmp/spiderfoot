# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         sfp_stor_db
# Purpose:      SpiderFoot plug-in for storing events to the configured database
#               backend (SQLite or PostgreSQL).
#
# Author:      Steve Micallef <steve@binarypool.com>
#
# Created:     14/05/2012
# Copyright:   (c) Steve Micallef 2012
# Licence:     MIT
# -------------------------------------------------------------------------------

import psycopg2
from spiderfoot import SpiderFootPlugin


class sfp__stor_db(SpiderFootPlugin):
    """SpiderFoot plug-in for storing events to the configured database
    backend.

    This class is responsible for storing scan results into the back-end
    SpiderFoot database (SQLite or PostgreSQL).
    """

    meta = {
        'name': "Database Storage",
        'summary': "Stores scan results into the back-end database. You will need this."
    }

    _priority = 0

    # Default options
    opts = {
        'maxstorage': 1024,  # max bytes for any piece of info stored (0 = unlimited)
        '_store': True,
        'db_type': 'sqlite',  # sqlite or postgresql
        'postgresql_host': 'localhost',
        'postgresql_port': 5432,
        'postgresql_database': 'spiderfoot',
        'postgresql_username': 'spiderfoot',
        'postgresql_password': ''
    }

    # Option descriptions
    optdescs = {
        'maxstorage': "Maximum bytes to store for any piece of information retrieved (0 = unlimited.)",
        'db_type': "Database type to use (sqlite or postgresql)",
        'postgresql_host': "PostgreSQL host if using postgresql as db_type",
        'postgresql_port': "PostgreSQL port if using postgresql as db_type",
        'postgresql_database': "PostgreSQL database name if using postgresql as db_type",
        'postgresql_username': "PostgreSQL username if using postgresql as db_type",
        'postgresql_password': "PostgreSQL password if using postgresql as db_type"
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

        # Initialize the appropriate database connection
        if self.opts['db_type'] == 'postgresql':
            try:
                self.pg_conn = psycopg2.connect(
                    host=self.opts['postgresql_host'],
                    port=self.opts['postgresql_port'],
                    database=self.opts['postgresql_database'],
                    user=self.opts['postgresql_username'],
                    password=self.opts['postgresql_password']
                )
                self.debug("Connected to PostgreSQL database")
            except Exception as e:
                self.error(f"Could not connect to PostgreSQL database: {e}")
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
        if not self.opts['_store']:
            return

        if self.errorState:
            return

        # Handle storage based on database type
        if self.opts['db_type'] == 'postgresql' and hasattr(self, 'pg_conn'):
            self._store_postgresql(sfEvent)
        else:
            self._store_sqlite(sfEvent)

    def _store_sqlite(self, sfEvent):
        """Store the event in the SQLite database.

        Args:
            sfEvent: SpiderFoot event
        """
        if self.opts['maxstorage'] != 0 and len(sfEvent.data) > self.opts['maxstorage']:
            self.debug("Storing an event in SQLite: " + sfEvent.eventType)
            self.__sfdb__.scanEventStore(
                self.getScanId(), sfEvent, self.opts['maxstorage'])
            return

        self.debug("Storing an event in SQLite: " + sfEvent.eventType)
        self.__sfdb__.scanEventStore(self.getScanId(), sfEvent)

    def _store_postgresql(self, sfEvent):
        """Store the event in the PostgreSQL database.

        Args:
            sfEvent: SpiderFoot event
        """
        try:
            cursor = self.pg_conn.cursor()
            
            # Truncate data if necessary
            data = sfEvent.data
            if self.opts['maxstorage'] != 0 and len(data) > self.opts['maxstorage']:
                data = data[:self.opts['maxstorage']]
            
            # Store event in PostgreSQL
            cursor.execute(
                "INSERT INTO tbl_scan_events (scan_id, type, data, module, source_event_hash, generated) VALUES (%s, %s, %s, %s, %s, %s)",
                (
                    self.getScanId(),
                    sfEvent.eventType,
                    data,
                    sfEvent.module,
                    sfEvent.sourceEventHash if hasattr(sfEvent, 'sourceEventHash') else None,
                    sfEvent.generated
                )
            )
            
            self.pg_conn.commit()
            cursor.close()
            
            self.debug("Stored event in PostgreSQL: " + sfEvent.eventType)
        except Exception as e:
            self.error(f"Error storing event in PostgreSQL: {e}")
            self.errorState = True

# End of sfp__stor_db class
