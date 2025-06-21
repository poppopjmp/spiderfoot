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

try:
    import psycopg2
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False

from spiderfoot import SpiderFootPlugin


class sfp__stor_db(SpiderFootPlugin):
    """SpiderFoot plug-in for storing events to the configured database
    backend.

    This class is responsible for storing scan results into the back-end
    SpiderFoot database (SQLite or PostgreSQL).
    """

    meta = {
        'name': "Database Storage",
        'summary': "Stores scan results into the back-end database. You will need this.",
        'flags': ["slow"]
    }

    _priority = 0    # Default options
    opts = {
        # max bytes for any piece of info stored (0 = unlimited)
        'maxstorage': 1024,
        '_store': True,
        'db_type': 'sqlite',  # sqlite or postgresql
        'postgresql_host': 'localhost',
        'postgresql_port': 5432,
        'postgresql_database': 'spiderfoot',
        'postgresql_username': 'spiderfoot',
        'postgresql_password': '',
        'postgresql_timeout': 30,
        # Phase 2 enterprise features (stub implementations)
        'enable_auto_recovery': False,
        'enable_connection_monitoring': False,
        'enable_performance_monitoring': False,
        'enable_graceful_shutdown': False,
        'enable_health_monitoring': False,
        'enable_connection_pooling': False,
        'enable_load_balancing': False,
        'enable_auto_scaling': False,
        'enable_query_optimization': False,
        'enable_performance_benchmarking': False,
        'collect_metrics': False
    }    # Option descriptions
    optdescs = {        'maxstorage': "Maximum bytes to store for any piece of information retrieved (0 = unlimited.)",
        'db_type': "Database type to use (sqlite or postgresql)",
        'postgresql_host': "PostgreSQL host if using postgresql as db_type",
        'postgresql_port': "PostgreSQL port if using postgresql as db_type",
        'postgresql_database': "PostgreSQL database name if using postgresql as db_type",
        'postgresql_username': "PostgreSQL username if using postgresql as db_type",
        'postgresql_password': "PostgreSQL password if using postgresql as db_type",
        'postgresql_timeout': "Connection timeout in seconds for PostgreSQL",
        # Phase 2 enterprise features
        'enable_auto_recovery': "Enable automatic error recovery (enterprise feature)",
        'enable_connection_monitoring': "Enable connection health monitoring (enterprise feature)",
        'enable_performance_monitoring': "Enable performance monitoring (enterprise feature)",
        'enable_graceful_shutdown': "Enable graceful shutdown procedures (enterprise feature)",
        'enable_health_monitoring': "Enable health monitoring (enterprise feature)",
        'enable_connection_pooling': "Enable connection pooling (enterprise feature)",
        'enable_load_balancing': "Enable load balancing (enterprise feature)",
        'enable_auto_scaling': "Enable auto scaling (enterprise feature)",
        'enable_query_optimization': "Enable query optimization (enterprise feature)",
        'enable_performance_benchmarking': "Enable performance benchmarking (enterprise feature)",
        'collect_metrics': "Enable metrics collection (enterprise feature)"
    }

    def setup(self, sfc, userOpts=dict()):
        """Set up the module with user options.

        Args:
            sfc: SpiderFoot instance
            userOpts (dict): User options
        """
        self.sf = sfc
        self.errorState = False
        self.pg_conn = None
        
        # CRITICAL FIX: Properly initialize the database handle from SpiderFoot
        if not hasattr(sfc, 'dbh') or sfc.dbh is None:
            self.error("SpiderFoot database handle not initialized - cannot store events")
            self.errorState = True
            return
            
        self.__sfdb__ = self.sf.dbh

        for opt in list(userOpts.keys()):
            self.opts[opt] = userOpts[opt]

        # Validate configuration
        if not self._validateConfig():
            self.errorState = True
            return

        # Initialize the appropriate database connection
        if self.opts['db_type'] == 'postgresql':
            if not HAS_PSYCOPG2:
                self.error("psycopg2 module is required for PostgreSQL support but not installed")
                self.errorState = True
                return
            
            self._connect_postgresql()

    def _validateConfig(self):
        """Validate configuration options.
        
        Returns:
            bool: True if config is valid, False otherwise
        """
        if self.opts['db_type'] not in ['sqlite', 'postgresql']:
            self.error(f"Invalid db_type: {self.opts['db_type']}. Must be 'sqlite' or 'postgresql'")
            return False
            
        if self.opts['db_type'] == 'postgresql':
            required_opts = ['postgresql_host', 'postgresql_database', 'postgresql_username']
            for opt in required_opts:
                if not self.opts.get(opt):
                    self.error(f"Required PostgreSQL option '{opt}' is not set")
                    return False
                    
            # Validate port
            try:
                port = int(self.opts['postgresql_port'])
                if not (1 <= port <= 65535):
                    raise ValueError("Port out of range")
            except (ValueError, TypeError):
                self.error(f"Invalid PostgreSQL port: {self.opts['postgresql_port']}")
                return False                
        return True

    def _connect_postgresql(self):
        """Establish PostgreSQL connection."""
        try:
            self.pg_conn = psycopg2.connect(
                host=self.opts['postgresql_host'],
                port=int(self.opts['postgresql_port']),
                database=self.opts['postgresql_database'],
                user=self.opts['postgresql_username'],
                password=self.opts['postgresql_password'],
                connect_timeout=self.opts['postgresql_timeout']
            )
            self.debug("Connected to PostgreSQL database")
        except Exception as e:
            self.error(f"Could not connect to PostgreSQL database: {e}")
            # Only set error state if auto recovery is disabled
            if not self.opts.get('enable_auto_recovery', False):
                self.errorState = True

    def _check_postgresql_connection(self):
        """Check if PostgreSQL connection is healthy.
        
        Returns:
            bool: True if connection is healthy, False otherwise
        """
        if not self.pg_conn:
            return False
            
        try:
            # Test connection with a simple query
            cursor = self.pg_conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
            return True
        except:
            return False

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

        # Choose storage method based on database type
        if self.opts['db_type'] == 'postgresql' and self.pg_conn:
            # Check connection health and reconnect if needed
            if not self._check_postgresql_connection():
                self.debug("PostgreSQL connection lost, attempting to reconnect...")
                self._connect_postgresql()
                
            if not self.errorState and self.pg_conn:
                self._store_postgresql(sfEvent)
            else:            self._store_sqlite(sfEvent)
        else:
            self._store_sqlite(sfEvent)

    def _store_sqlite(self, sfEvent):
        """Store the event in the SQLite database.
        
        Args:
            sfEvent: SpiderFoot event
        """
        # CRITICAL FIX: Check database handle before using
        if not self.__sfdb__:
            self.error("Database handle not available for SQLite storage")
            return
            
        if self.opts['maxstorage'] != 0 and len(sfEvent.data) > self.opts['maxstorage']:
            self.debug("Storing an event: " + sfEvent.eventType)
            self.__sfdb__.scanEventStore(
                self.getScanId(), sfEvent, self.opts['maxstorage'])
            return

        self.debug("Storing an event: " + sfEvent.eventType)
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

            # CORRECTED: Use proper table and column names matching the schema
            cursor.execute(
                """INSERT INTO tbl_scan_results 
                   (scan_instance_id, hash, type, generated, confidence, 
                    visibility, risk, module, data, source_event_hash) 
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    self.getScanId(),
                    sfEvent.hash,
                    sfEvent.eventType,
                    sfEvent.generated,
                    sfEvent.confidence,
                    sfEvent.visibility,
                    sfEvent.risk,
                    sfEvent.module,
                    data,
                    getattr(sfEvent, 'sourceEventHash', 'ROOT')
                )
            )

            self.pg_conn.commit()
            cursor.close()

            self.debug("Stored event in PostgreSQL: " + sfEvent.eventType)
        except Exception as e:
            self.error(f"Error storing event in PostgreSQL: {e}")
            if self.pg_conn:
                try:
                    self.pg_conn.rollback()
                except:
                    pass
            # Fall back to SQLite storage
            self.debug("Falling back to SQLite storage")
            self._store_sqlite(sfEvent)

    def __del__(self):
        """Clean up database connections."""
        if hasattr(self, 'pg_conn') and self.pg_conn:
            try:
                self.pg_conn.close()
                self.debug("PostgreSQL connection closed")
            except Exception as e:
                # Use print since self.debug may not be available during destruction
                print(f"Error closing PostgreSQL connection: {e}")

# End of sfp__stor_db class
