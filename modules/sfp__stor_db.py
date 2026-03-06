from __future__ import annotations

"""SpiderFoot plug-in module: _stor_db."""

# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         sfp_stor_db
# Purpose:      SpiderFoot plug-in for storing events to the configured database
#               backend (PostgreSQL).
#
# Author:      Steve Micallef <steve@binarypool.com>
#
# Created:     14/05/2012
# Copyright:   (c) Steve Micallef 2012
# Licence:     MIT
# -------------------------------------------------------------------------------

import logging

try:
    import psycopg2
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False

from spiderfoot.plugins.modern_plugin import SpiderFootModernPlugin


class sfp__stor_db(SpiderFootModernPlugin):
    """SpiderFoot plug-in for storing events to the configured database
    backend.

    This class is responsible for storing scan results into the back-end
    SpiderFoot database (PostgreSQL).
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
        'db_type': 'postgresql',  # postgresql
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
        'db_type': "Database type to use (postgresql)",
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

    def setup(self, sfc: SpiderFoot, userOpts: dict = None) -> None:
        """Set up the module with user options.

        Args:
            sfc: SpiderFoot instance
            userOpts (dict): User options
        """
        super().setup(sfc, userOpts or {})
        self.errorState = False
        self.pg_conn = None

        # Mandatory: shared DB handle from the running SpiderFoot instance.
        # This is the PRIMARY storage path and must always be available.
        if not hasattr(sfc, 'dbh') or sfc.dbh is None:
            self.error("SpiderFoot database handle not initialized - cannot store events")
            self.errorState = True
            return

        self.__sfdb__ = self.sf.dbh

        # Override postgresql_* opts from __database DSN when present.
        # global_opts carries __database = SF_POSTGRES_DSN (e.g.
        # "postgresql://spiderfoot:secret@postgres:5432/spiderfoot").
        # The module's built-in defaults (postgresql_host='localhost') are wrong
        # in any Docker / remote deployment, so we always prefer the DSN.
        dsn = self.opts.get('__database', '')
        if dsn and (dsn.startswith('postgresql://') or dsn.startswith('postgres://')):
            try:
                from urllib.parse import urlparse
                _p = urlparse(dsn)
                if _p.hostname:
                    self.opts['postgresql_host'] = _p.hostname
                if _p.port:
                    self.opts['postgresql_port'] = _p.port
                if _p.path and _p.path != '/':
                    self.opts['postgresql_database'] = _p.path.lstrip('/')
                if _p.username:
                    self.opts['postgresql_username'] = _p.username
                if _p.password:
                    self.opts['postgresql_password'] = _p.password
                self.debug(f"Populated postgresql opts from __database DSN (host={self.opts['postgresql_host']})")
            except Exception as _e:
                self.debug(f"Could not parse __database DSN: {_e}")

        # Validate configuration before attempting connection.
        if not self._validateConfig():
            self.errorState = True
            return

        # Optionally open a dedicated direct connection for _store_postgresql.
        # If this fails we fall back to _store_default (self.__sfdb__) which
        # uses the pooled connection already established by SpiderFoot.
        # A failure here must NOT set errorState — events must still be stored.
        if self.opts['db_type'] == 'postgresql' and HAS_PSYCOPG2:
            self._connect_postgresql()

    def _validateConfig(self):
        """Validate configuration options.
        
        Returns:
            bool: True if config is valid, False otherwise
        """
        if self.opts['db_type'] not in ['postgresql']:
            self.error(f"Invalid db_type: {self.opts['db_type']}. Must be 'postgresql'")
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
        """Establish a dedicated PostgreSQL connection for direct storage.

        Failure leaves self.pg_conn = None which causes handleEvent to fall back
        to _store_default (self.__sfdb__).  We never set errorState here because
        the shared DB handle is always the authoritative storage path.
        """
        try:
            self.pg_conn = psycopg2.connect(
                host=self.opts['postgresql_host'],
                port=int(self.opts['postgresql_port']),
                database=self.opts['postgresql_database'],
                user=self.opts['postgresql_username'],
                password=self.opts['postgresql_password'],
                connect_timeout=self.opts['postgresql_timeout']
            )
            self.debug("Connected to PostgreSQL database (direct)")
        except Exception as e:
            self.error(f"Direct PostgreSQL connection failed ({e}); will use shared DB handle instead")
            self.pg_conn = None  # fall back to _store_default
            # If auto-recovery is disabled, treat connection failure as fatal
            if not self.opts.get('enable_auto_recovery', True):
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
        except Exception as e:
            return False

    def watchedEvents(self) -> list:
        """Define the events this module is interested in for input.

        Returns:
            list: List of event types
        """
        return ["*"]

    def handleEvent(self, sfEvent: SpiderFootEvent) -> None:
        """Handle events sent to this module.

        Args:
            sfEvent: SpiderFoot event
        """
        if not self.opts['_store']:
            return

        if self.errorState:
            return

        # Prefer the dedicated direct pg connection when available and healthy;
        # fall back to the shared pooled handle (_store_default) otherwise.
        if self.pg_conn:
            if not self._check_postgresql_connection():
                self.debug("Direct PostgreSQL connection lost, reconnecting...")
                self._connect_postgresql()
            if self.pg_conn:
                self._store_postgresql(sfEvent)
                return
        self._store_default(sfEvent)

    def _store_default(self, sfEvent):
        """Store the event in the default database.
        
        Args:
            sfEvent: SpiderFoot event
        """
        # CRITICAL FIX: Check database handle before using
        if not self.__sfdb__:
            self.error("Database handle not available for default storage")
            return

        max_retries = 3
        for attempt in range(max_retries):
            try:
                if self.opts['maxstorage'] != 0 and len(sfEvent.data) > self.opts['maxstorage']:
                    self.debug("Storing an event: " + sfEvent.eventType)
                    self.__sfdb__.scanEventStore(
                        self.getScanId(), sfEvent, self.opts['maxstorage'])
                    return

                self.debug("Storing an event: " + sfEvent.eventType)
                self.__sfdb__.scanEventStore(self.getScanId(), sfEvent)
                return
            except Exception as e:
                err_msg = str(e)
                if "database is locked" in err_msg and attempt < max_retries - 1:
                    import time as _time
                    _time.sleep(0.1 * (attempt + 1))
                    continue
                import traceback
                self.error(f"_store_default failed for event type={sfEvent.eventType} "
                           f"module={sfEvent.module} hash={sfEvent.hash} "
                           f"generated={sfEvent.generated} data_len={len(sfEvent.data) if sfEvent.data else 0}: "
                           f"{type(e).__name__}: {e}")
                self.error(f"Full traceback: {traceback.format_exc()}")
                # Do NOT re-raise — keep sfp__stor_db alive for subsequent events
                return

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
                except (OSError, psycopg2.Error):
                    pass
            # Fall back to default storage
            self.debug("Falling back to default storage")
            self._store_default(sfEvent)

    def __del__(self):
        """Clean up database connections."""
        if hasattr(self, 'pg_conn') and self.pg_conn:
            try:
                self.pg_conn.close()
                self.debug("PostgreSQL connection closed")
            except Exception as e:
                logging.getLogger(__name__).debug("Error closing PostgreSQL connection: %s", e)

# End of sfp__stor_db class
