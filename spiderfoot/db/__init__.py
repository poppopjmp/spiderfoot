# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         sfdb
# Purpose:      Common functions for working with the database back-end.
#
# Author:      Steve Micallef <steve@binarypool.com>
#
# Created:     15/05/2012
# Copyright:   (c) Steve Micallef 2012
# Licence:     MIT
# -------------------------------------------------------------------------------

from pathlib import Path
import hashlib
import random
import re
import sqlite3
import threading
import time
import psycopg2
import psycopg2.extras
from spiderfoot.db.db_core import DbCore
from spiderfoot.db.db_scan import ScanManager
from spiderfoot.db.db_event import EventManager
from spiderfoot.db.db_config import ConfigManager
from spiderfoot.db.db_correlation import CorrelationManager
from spiderfoot.db.db_utils import DbUtils


class SpiderFootDb:
    """SpiderFoot database.
    Attributes:
        conn: Database connection
        dbh: Database cursor
        dbhLock (_thread.RLock): thread lock on database handle
    """
    dbh = None
    conn = None
    dbhLock = threading.RLock()
    # Queries for creating the SpiderFoot database
    createSchemaQueries = [
        "PRAGMA journal_mode=WAL",
        "CREATE TABLE tbl_event_types ( \
            event       VARCHAR NOT NULL PRIMARY KEY, \
            event_descr VARCHAR NOT NULL, \
            event_raw   INT NOT NULL DEFAULT 0, \
            event_type  VARCHAR NOT NULL \
        )",
        "CREATE TABLE tbl_config ( \
            scope   VARCHAR NOT NULL, \
            opt     VARCHAR NOT NULL, \
            val     VARCHAR NOT NULL, \
            PRIMARY KEY (scope, opt) \
        )",
        "CREATE TABLE tbl_scan_instance ( \
            guid        VARCHAR NOT NULL PRIMARY KEY, \
            name        VARCHAR NOT NULL, \
            seed_target VARCHAR NOT NULL, \
            created     INT DEFAULT 0, \
            started     INT DEFAULT 0, \
            ended       INT DEFAULT 0, \
            status      VARCHAR NOT NULL \
        )",
        "CREATE TABLE tbl_scan_log ( \
            scan_instance_id    VARCHAR NOT NULL REFERENCES tbl_scan_instance(guid), \
            generated           INT NOT NULL, \
            component           VARCHAR, \
            type                VARCHAR NOT NULL, \
            message             VARCHAR \
        )",
        "CREATE TABLE tbl_scan_config ( \
            scan_instance_id    VARCHAR NOT NULL REFERENCES tbl_scan_instance(guid), \
            component           VARCHAR NOT NULL, \
            opt                 VARCHAR NOT NULL, \
            val                 VARCHAR NOT NULL \
        )",
        "CREATE TABLE tbl_scan_results ( \
            scan_instance_id    VARCHAR NOT NULL REFERENCES tbl_scan_instance(guid), \
            hash                VARCHAR NOT NULL, \
            type                VARCHAR NOT NULL REFERENCES tbl_event_types(event), \
            generated           INT NOT NULL, \
            confidence          INT NOT NULL DEFAULT 100, \
            visibility          INT NOT NULL DEFAULT 100, \
            risk                INT NOT NULL DEFAULT 0, \
            module              VARCHAR NOT NULL, \
            data                TEXT, \
            false_positive      INT NOT NULL DEFAULT 0, \
            source_event_hash  VARCHAR DEFAULT 'ROOT' \
        )",
        "CREATE TABLE tbl_scan_correlation_results ( \
            id                  VARCHAR NOT NULL PRIMARY KEY, \
            scan_instance_id    VARCHAR NOT NULL REFERENCES tbl_scan_instance(guid), \
            title               VARCHAR NOT NULL, \
            rule_risk           VARCHAR NOT NULL, \
            rule_id             VARCHAR NOT NULL, \
            rule_name           VARCHAR NOT NULL, \
            rule_descr          VARCHAR NOT NULL, \
            rule_logic          VARCHAR NOT NULL \
        )",
        "CREATE TABLE tbl_scan_correlation_results_events ( \
            correlation_id      VARCHAR NOT NULL REFERENCES tbl_scan_correlation_results(id), \
            event_hash          VARCHAR NOT NULL REFERENCES tbl_scan_results(hash) \
        )",
        "CREATE INDEX idx_scan_results_id ON tbl_scan_results (scan_instance_id)",
        "CREATE INDEX idx_scan_results_type ON tbl_scan_results (scan_instance_id, type)",
        "CREATE INDEX idx_scan_results_hash ON tbl_scan_results (scan_instance_id, hash)",
        "CREATE INDEX idx_scan_results_module ON tbl_scan_results(scan_instance_id, module)",
        "CREATE INDEX idx_scan_results_srchash ON tbl_scan_results (scan_instance_id, source_event_hash)",
        "CREATE INDEX idx_scan_logs ON tbl_scan_log (scan_instance_id)",
        "CREATE INDEX idx_scan_correlation ON tbl_scan_correlation_results (scan_instance_id, id)",
        "CREATE INDEX idx_scan_correlation_events ON tbl_scan_correlation_results_events (correlation_id)"
    ]

    # PostgreSQL-specific schema queries
    createPostgreSQLSchemaQueries = [
        "CREATE TABLE IF NOT EXISTS tbl_event_types ( \
            event       VARCHAR NOT NULL PRIMARY KEY, \
            event_descr VARCHAR NOT NULL, \
            event_raw   INT NOT NULL DEFAULT 0, \
            event_type  VARCHAR NOT NULL \
        )",
        "CREATE TABLE IF NOT EXISTS tbl_config ( \
            scope   VARCHAR NOT NULL, \
            opt     VARCHAR NOT NULL, \
            val     VARCHAR NOT NULL, \
            PRIMARY KEY (scope, opt) \
        )",
        "CREATE TABLE IF NOT EXISTS tbl_scan_instance ( \
            guid        VARCHAR NOT NULL PRIMARY KEY, \
            name        VARCHAR NOT NULL, \
            seed_target VARCHAR NOT NULL, \
            created     BIGINT DEFAULT 0, \
            started     BIGINT DEFAULT 0, \
            ended       BIGINT DEFAULT 0, \
            status      VARCHAR NOT NULL \
        )",
        "CREATE TABLE IF NOT EXISTS tbl_scan_log ( \
            scan_instance_id    VARCHAR NOT NULL REFERENCES tbl_scan_instance(guid), \
            generated           BIGINT NOT NULL, \
            component           VARCHAR, \
            type                VARCHAR NOT NULL, \
            message             VARCHAR \
        )",
        "CREATE TABLE IF NOT EXISTS tbl_scan_config ( \
            scan_instance_id    VARCHAR NOT NULL REFERENCES tbl_scan_instance(guid), \
            component           VARCHAR NOT NULL, \
            opt                 VARCHAR NOT NULL, \
            val                 VARCHAR NOT NULL \
        )",
        "CREATE TABLE IF NOT EXISTS tbl_scan_results ( \
            scan_instance_id    VARCHAR NOT NULL REFERENCES tbl_scan_instance(guid), \
            hash                VARCHAR NOT NULL, \
            type                VARCHAR NOT NULL REFERENCES tbl_event_types(event), \
            generated           BIGINT NOT NULL, \
            confidence          INT NOT NULL DEFAULT 100, \
            visibility          INT NOT NULL DEFAULT 100, \
            risk                INT NOT NULL DEFAULT 0, \
            module              VARCHAR NOT NULL, \
            data                TEXT, \
            false_positive      INT NOT NULL DEFAULT 0, \
            source_event_hash  VARCHAR DEFAULT 'ROOT' \
        )",
        "CREATE TABLE IF NOT EXISTS tbl_scan_correlation_results ( \
            id                  VARCHAR NOT NULL PRIMARY KEY, \
            scan_instance_id    VARCHAR NOT NULL REFERENCES tbl_scan_instance(guid), \
            title               VARCHAR NOT NULL, \
            rule_risk           VARCHAR NOT NULL, \
            rule_id             VARCHAR NOT NULL, \
            rule_name           VARCHAR NOT NULL, \
            rule_descr          VARCHAR NOT NULL, \
            rule_logic          VARCHAR NOT NULL \
        )",
        "CREATE TABLE IF NOT EXISTS tbl_scan_correlation_results_events ( \
            correlation_id      VARCHAR NOT NULL REFERENCES tbl_scan_correlation_results(id), \
            event_hash          VARCHAR NOT NULL REFERENCES tbl_scan_results(hash) \
        )",
        "CREATE INDEX IF NOT EXISTS idx_scan_results_id ON tbl_scan_results (scan_instance_id)",
        "CREATE INDEX IF NOT EXISTS idx_scan_results_type ON tbl_scan_results (scan_instance_id, type)",
        "CREATE INDEX IF NOT EXISTS idx_scan_results_hash ON tbl_scan_results (scan_instance_id, hash)",
        "CREATE INDEX IF NOT EXISTS idx_scan_results_module ON tbl_scan_results(scan_instance_id, module)",
        "CREATE INDEX IF NOT EXISTS idx_scan_results_srchash ON tbl_scan_results (scan_instance_id, source_event_hash)",
        "CREATE INDEX IF NOT EXISTS idx_scan_logs ON tbl_scan_log (scan_instance_id)",
        "CREATE INDEX IF NOT EXISTS idx_scan_correlation ON tbl_scan_correlation_results (scan_instance_id, id)",
        "CREATE INDEX IF NOT EXISTS idx_scan_correlation_events ON tbl_scan_correlation_results_events (correlation_id)"
    ]

    eventDetails = [
        ['ROOT', 'Internal SpiderFoot Root event', 1, 'INTERNAL'],
        ['ACCOUNT_EXTERNAL_OWNED', 'Account on External Site', 0, 'ENTITY'],
        ['ACCOUNT_EXTERNAL_OWNED_COMPROMISED',
            'Hacked Account on External Site', 0, 'DESCRIPTOR'],
        ['ACCOUNT_EXTERNAL_USER_SHARED_COMPROMISED',
            'Hacked User Account on External Site', 0, 'DESCRIPTOR'],
        ['AFFILIATE_EMAILADDR', 'Affiliate - Email Address', 0, 'ENTITY'],
        ['AFFILIATE_INTERNET_NAME', 'Affiliate - Internet Name', 0, 'ENTITY'],
        ['AFFILIATE_INTERNET_NAME_HIJACKABLE',
            'Affiliate - Internet Name Hijackable', 0, 'ENTITY'],
        ['AFFILIATE_INTERNET_NAME_UNRESOLVED',
            'Affiliate - Internet Name - Unresolved', 0, 'ENTITY'],
        ['AFFILIATE_IPADDR', 'Affiliate - IP Address', 0, 'ENTITY'],
        ['AFFILIATE_IPV6_ADDRESS', 'Affiliate - IPv6 Address', 0, 'ENTITY'],
        ['AFFILIATE_WEB_CONTENT', 'Affiliate - Web Content', 1, 'DATA'],
        ['AFFILIATE_DOMAIN_NAME', 'Affiliate - Domain Name', 0, 'ENTITY'],
        ['AFFILIATE_DOMAIN_UNREGISTERED',
            'Affiliate - Domain Name Unregistered', 0, 'ENTITY'],
        ['AFFILIATE_COMPANY_NAME', 'Affiliate - Company Name', 0, 'ENTITY'],
        ['AFFILIATE_DOMAIN_WHOIS', 'Affiliate - Domain Whois', 1, 'DATA'],
        ['AFFILIATE_DESCRIPTION_CATEGORY',
            'Affiliate Description - Category', 0, 'DESCRIPTOR'],
        ['AFFILIATE_DESCRIPTION_ABSTRACT',
            'Affiliate Description - Abstract', 0, 'DESCRIPTOR'],
        ['APPSTORE_ENTRY', 'App Store Entry', 0, 'ENTITY'],
        ['CLOUD_STORAGE_BUCKET', 'Cloud Storage Bucket', 0, 'ENTITY'],
        ['CLOUD_STORAGE_BUCKET_OPEN', 'Cloud Storage Bucket Open', 0, 'DESCRIPTOR'],
        ['COMPANY_NAME', 'Company Name', 0, 'ENTITY'],
        ['CREDIT_CARD_NUMBER', 'Credit Card Number', 0, 'ENTITY'],
        ['BASE64_DATA', 'Base64-encoded Data', 1, 'DATA'],
        ['BITCOIN_ADDRESS', 'Bitcoin Address', 0, 'ENTITY'],
        ['BITCOIN_BALANCE', 'Bitcoin Balance', 0, 'DESCRIPTOR'],
        ['BGP_AS_OWNER', 'BGP AS Ownership', 0, 'ENTITY'],
        ['BGP_AS_MEMBER', 'BGP AS Membership', 0, 'ENTITY'],
        ['BLACKLISTED_COHOST', 'Blacklisted Co-Hosted Site', 0, 'DESCRIPTOR'],
        ['BLACKLISTED_INTERNET_NAME', 'Blacklisted Internet Name', 0, 'DESCRIPTOR'],
        ['BLACKLISTED_AFFILIATE_INTERNET_NAME',
            'Blacklisted Affiliate Internet Name', 0, 'DESCRIPTOR'],
        ['BLACKLISTED_IPADDR', 'Blacklisted IP Address', 0, 'DESCRIPTOR'],
        ['BLACKLISTED_AFFILIATE_IPADDR',
            'Blacklisted Affiliate IP Address', 0, 'DESCRIPTOR'],
        ['BLACKLISTED_SUBNET', 'Blacklisted IP on Same Subnet', 0, 'DESCRIPTOR'],
        ['BLACKLISTED_NETBLOCK', 'Blacklisted IP on Owned Netblock', 0, 'DESCRIPTOR'],
        ['COUNTRY_NAME', 'Country Name', 0, 'ENTITY'],
        ['CO_HOSTED_SITE', 'Co-Hosted Site', 0, 'ENTITY'],
        ['CO_HOSTED_SITE_DOMAIN', 'Co-Hosted Site - Domain Name', 0, 'ENTITY'],
        ['CO_HOSTED_SITE_DOMAIN_WHOIS', 'Co-Hosted Site - Domain Whois', 1, 'DATA'],
        ['DARKNET_MENTION_URL', 'Darknet Mention URL', 0, 'DESCRIPTOR'],
        ['DARKNET_MENTION_CONTENT', 'Darknet Mention Web Content', 1, 'DATA'],
        ['DATE_HUMAN_DOB', 'Date of Birth', 0, 'ENTITY'],
        ['DEFACED_INTERNET_NAME', 'Defaced', 0, 'DESCRIPTOR'],
        ['DEFACED_IPADDR', 'Defaced IP Address', 0, 'DESCRIPTOR'],
        ['DEFACED_AFFILIATE_INTERNET_NAME', 'Defaced Affiliate', 0, 'DESCRIPTOR'],
        ['DEFACED_COHOST', 'Defaced Co-Hosted Site', 0, 'DESCRIPTOR'],
        ['DEFACED_AFFILIATE_IPADDR', 'Defaced Affiliate IP Address', 0, 'DESCRIPTOR'],
        ['DESCRIPTION_CATEGORY', 'Description - Category', 0, 'DESCRIPTOR'],
        ['DESCRIPTION_ABSTRACT', 'Description - Abstract', 0, 'DESCRIPTOR'],
        ['DEVICE_TYPE', 'Device Type', 0, 'DESCRIPTOR'],
        ['DNS_TEXT', 'DNS TXT Record', 0, 'DATA'],
        ['DNS_SRV', 'DNS SRV Record', 0, 'DATA'],
        ['DNS_SPF', 'DNS SPF Record', 0, 'DATA'],
        ['DOMAIN_NAME', 'Domain Name', 0, 'ENTITY'],
        ['DOMAIN_NAME_PARENT', 'Domain Name (Parent)', 0, 'ENTITY'],
        ['DOMAIN_REGISTRAR', 'Domain Registrar', 0, 'ENTITY'],
        ['DOMAIN_WHOIS', 'Domain Whois', 1, 'DATA'],
        ['EMAILADDR', 'Email Address', 0, 'ENTITY'],
        ['EMAILADDR_COMPROMISED', 'Hacked Email Address', 0, 'DESCRIPTOR'],
        ['EMAILADDR_DELIVERABLE', 'Deliverable Email Address', 0, 'DESCRIPTOR'],
        ['EMAILADDR_DISPOSABLE', 'Disposable Email Address', 0, 'DESCRIPTOR'],
        ['EMAILADDR_GENERIC', 'Email Address - Generic', 0, 'ENTITY'],
        ['EMAILADDR_UNDELIVERABLE', 'Undeliverable Email Address', 0, 'DESCRIPTOR'],
        ['ERROR_MESSAGE', 'Error Message', 0, 'DATA'],
        ['ETHEREUM_ADDRESS', 'Ethereum Address', 0, 'ENTITY'],
        ['ETHEREUM_BALANCE', 'Ethereum Balance', 0, 'DESCRIPTOR'],
        ['GEOINFO', 'Physical Location', 0, 'DESCRIPTOR'],
        ['HASH', 'Hash', 0, 'DATA'],
        ['HASH_COMPROMISED', 'Compromised Password Hash', 0, 'DATA'],
        ['HTTP_CODE', 'HTTP Status Code', 0, 'DATA'],
        ['HUMAN_NAME', 'Human Name', 0, 'ENTITY'],
        ['IBAN_NUMBER', 'IBAN Number', 0, 'ENTITY'],
        ['INTERESTING_FILE', 'Interesting File', 0, 'DESCRIPTOR'],
        ['INTERESTING_FILE_HISTORIC', 'Historic Interesting File', 0, 'DESCRIPTOR'],
        ['JUNK_FILE', 'Junk File', 0, 'DESCRIPTOR'],
        ['INTERNAL_IP_ADDRESS', 'IP Address - Internal Network', 0, 'ENTITY'],
        ['INTERNET_NAME', 'Internet Name', 0, 'ENTITY'],
        ['INTERNET_NAME_UNRESOLVED', 'Internet Name - Unresolved', 0, 'ENTITY'],
        ['IP_ADDRESS', 'IP Address', 0, 'ENTITY'],
        ['IPV6_ADDRESS', 'IPv6 Address', 0, 'ENTITY'],
        ['LEI', 'Legal Entity Identifier', 0, 'ENTITY'],
        ['JOB_TITLE', 'Job Title', 0, 'DESCRIPTOR'],
        ['LINKED_URL_INTERNAL', 'Linked URL - Internal', 0, 'SUBENTITY'],
        ['LINKED_URL_EXTERNAL', 'Linked URL - External', 0, 'SUBENTITY'],
        ['MALICIOUS_ASN', 'Malicious AS', 0, 'DESCRIPTOR'],
        ['MALICIOUS_BITCOIN_ADDRESS', 'Malicious Bitcoin Address', 0, 'DESCRIPTOR'],
        ['MALICIOUS_IPADDR', 'Malicious IP Address', 0, 'DESCRIPTOR'],
        ['MALICIOUS_COHOST', 'Malicious Co-Hosted Site', 0, 'DESCRIPTOR'],
        ['MALICIOUS_EMAILADDR', 'Malicious E-mail Address', 0, 'DESCRIPTOR'],
        ['MALICIOUS_INTERNET_NAME', 'Malicious Internet Name', 0, 'DESCRIPTOR'],
        ['MALICIOUS_AFFILIATE_INTERNET_NAME',
            'Malicious Affiliate', 0, 'DESCRIPTOR'],
        ['MALICIOUS_AFFILIATE_IPADDR',
            'Malicious Affiliate IP Address', 0, 'DESCRIPTOR'],
        ['MALICIOUS_NETBLOCK', 'Malicious IP on Owned Netblock', 0, 'DESCRIPTOR'],
        ['MALICIOUS_PHONE_NUMBER', 'Malicious Phone Number', 0, 'DESCRIPTOR'],
        ['MALICIOUS_SUBNET', 'Malicious IP on Same Subnet', 0, 'DESCRIPTOR'],
        ['NETBLOCK_OWNER', 'Netblock Ownership', 0, 'ENTITY'],
        ['NETBLOCKV6_OWNER', 'Netblock IPv6 Ownership', 0, 'ENTITY'],
        ['NETBLOCK_MEMBER', 'Netblock Membership', 0, 'ENTITY'],
        ['NETBLOCKV6_MEMBER', 'Netblock IPv6 Membership', 0, 'ENTITY'],
        ['NETBLOCK_WHOIS', 'Netblock Whois', 1, 'DATA'],
        ['OPERATING_SYSTEM', 'Operating System', 0, 'DESCRIPTOR'],
        ['LEAKSITE_URL', 'Leak Site URL', 0, 'ENTITY'],
        ['LEAKSITE_CONTENT', 'Leak Site Content', 1, 'DATA'],
        ['PASSWORD_COMPROMISED', 'Compromised Password', 0, 'DATA'],
        ['PERSON_NAME', 'Person Name', 0, 'ENTITY'],
        ['PHONE_NUMBER', 'Phone Number', 0, 'ENTITY'],
        ['PHONE_NUMBER_COMPROMISED', 'Phone Number Compromised', 0, 'DESCRIPTOR'],
        ['PHONE_NUMBER_TYPE', 'Phone Number Type', 0, 'DESCRIPTOR'],
        ['PHYSICAL_ADDRESS', 'Physical Address', 0, 'ENTITY'],
        ['PHYSICAL_COORDINATES', 'Physical Coordinates', 0, 'ENTITY'],
        ['PGP_KEY', 'PGP Public Key', 0, 'DATA'],
        ['PROXY_HOST', 'Proxy Host', 0, 'DESCRIPTOR'],
        ['PROVIDER_DNS', 'Name Server (DNS ''NS'' Records)', 0, 'ENTITY'],
        ['PROVIDER_JAVASCRIPT', 'Externally Hosted Javascript', 0, 'ENTITY'],
        ['PROVIDER_MAIL', 'Email Gateway (DNS ''MX'' Records)', 0, 'ENTITY'],
        ['PROVIDER_HOSTING', 'Hosting Provider', 0, 'ENTITY'],
        ['PROVIDER_TELCO', 'Telecommunications Provider', 0, 'ENTITY'],
        ['PUBLIC_CODE_REPO', 'Public Code Repository', 0, 'ENTITY'],
        ['RAW_RIR_DATA', 'Raw Data from RIRs/APIs', 1, 'DATA'],
        ['RAW_DNS_RECORDS', 'Raw DNS Records', 1, 'DATA'],
        ['RAW_FILE_META_DATA', 'Raw File Meta Data', 1, 'DATA'],
        ['SEARCH_ENGINE_WEB_CONTENT', 'Search Engine Web Content', 1, 'DATA'],
        ['SOCIAL_MEDIA', 'Social Media Presence', 0, 'ENTITY'],
        ['SIMILAR_ACCOUNT_EXTERNAL', 'Similar Account on External Site', 0, 'ENTITY'],
        ['SIMILARDOMAIN', 'Similar Domain', 0, 'ENTITY'],
        ['SIMILARDOMAIN_WHOIS', 'Similar Domain - Whois', 1, 'DATA'],
        ['SOFTWARE_USED', 'Software Used', 0, 'SUBENTITY'],
        ['SSL_CERTIFICATE_RAW', 'SSL Certificate - Raw Data', 1, 'DATA'],
        ['SSL_CERTIFICATE_ISSUED', 'SSL Certificate - Issued to', 0, 'ENTITY'],
        ['SSL_CERTIFICATE_ISSUER', 'SSL Certificate - Issued by', 0, 'ENTITY'],
        ['SSL_CERTIFICATE_MISMATCH', 'SSL Certificate Host Mismatch', 0, 'DESCRIPTOR'],
        ['SSL_CERTIFICATE_EXPIRED', 'SSL Certificate Expired', 0, 'DESCRIPTOR'],
        ['SSL_CERTIFICATE_EXPIRING', 'SSL Certificate Expiring', 0, 'DESCRIPTOR'],
        ['TARGET_WEB_CONTENT', 'Web Content', 1, 'DATA'],
        ['TARGET_WEB_COOKIE', 'Cookies', 0, 'DATA'],
        ['TCP_PORT_OPEN', 'Open TCP Port', 0, 'SUBENTITY'],
        ['TCP_PORT_OPEN_BANNER', 'Open TCP Port Banner', 0, 'DATA'],
        ['TOR_EXIT_NODE', 'TOR Exit Node', 0, 'DESCRIPTOR'],
        ['UDP_PORT_OPEN', 'Open UDP Port', 0, 'SUBENTITY'],
        ['UDP_PORT_OPEN_INFO', 'Open UDP Port Information', 0, 'DATA'],
        ['URL_ADBLOCKED_EXTERNAL',
            'URL (AdBlocked External)', 0, 'DESCRIPTOR'],
        ['URL_ADBLOCKED_INTERNAL',
            'URL (AdBlocked Internal)', 0, 'DESCRIPTOR'],
        ['URL_FORM', 'URL (Form)', 0, 'DESCRIPTOR'],
        ['URL_FLASH', 'URL (Uses Flash)', 0, 'DESCRIPTOR'],
        ['URL_JAVASCRIPT', 'URL (Uses Javascript)', 0, 'DESCRIPTOR'],
        ['URL_WEB_FRAMEWORK', 'URL (Uses a Web Framework)', 0, 'DESCRIPTOR'],
        ['URL_JAVA_APPLET', 'URL (Uses Java Applet)', 0, 'DESCRIPTOR'],
        ['URL_STATIC', 'URL (Purely Static)', 0, 'DESCRIPTOR'],
        ['URL_PASSWORD', 'URL (Accepts Passwords)', 0, 'DESCRIPTOR'],
        ['URL_UPLOAD', 'URL (Accepts Uploads)', 0, 'DESCRIPTOR'],
        ['URL_FORM_HISTORIC', 'Historic URL (Form)', 0, 'DESCRIPTOR'],
        ['URL_FLASH_HISTORIC', 'Historic URL (Uses Flash)', 0, 'DESCRIPTOR'],
        ['URL_JAVASCRIPT_HISTORIC',
            'Historic URL (Uses Javascript)', 0, 'DESCRIPTOR'],
        ['URL_WEB_FRAMEWORK_HISTORIC',
            'Historic URL (Uses a Web Framework)', 0, 'DESCRIPTOR'],
        ['URL_JAVA_APPLET_HISTORIC',
            'Historic URL (Uses Java Applet)', 0, 'DESCRIPTOR'],
        ['URL_STATIC_HISTORIC',
            'Historic URL (Purely Static)', 0, 'DESCRIPTOR'],
        ['URL_PASSWORD_HISTORIC',
            'Historic URL (Accepts Passwords)', 0, 'DESCRIPTOR'],
        ['URL_UPLOAD_HISTORIC',
            'Historic URL (Accepts Uploads)', 0, 'DESCRIPTOR'],
        ['USERNAME', 'Username', 0, 'ENTITY'],
        ['VPN_HOST', 'VPN Host', 0, 'DESCRIPTOR'],
        ['VULNERABILITY_DISCLOSURE',
            'Vulnerability - Third Party Disclosure', 0, 'DESCRIPTOR'],
        ['VULNERABILITY_CVE_CRITICAL', 'Vulnerability - CVE Critical', 0, 'DESCRIPTOR'],
        ['VULNERABILITY_CVE_HIGH', 'Vulnerability - CVE High', 0, 'DESCRIPTOR'],
        ['VULNERABILITY_CVE_MEDIUM', 'Vulnerability - CVE Medium', 0, 'DESCRIPTOR'],
        ['VULNERABILITY_CVE_LOW', 'Vulnerability - CVE Low', 0, 'DESCRIPTOR'],
        ['VULNERABILITY_GENERAL', 'Vulnerability - General', 0, 'DESCRIPTOR'],
        ['WEB_ANALYTICS_ID', 'Web Analytics', 0, 'ENTITY'],
        ['WEBSERVER_BANNER', 'Web Server', 0, 'DATA'],
        ['WEBSERVER_HTTPHEADERS', 'HTTP Headers', 1, 'DATA'],
        ['WEBSERVER_STRANGEHEADER', 'Non-Standard HTTP Header', 0, 'DATA'],
        ['WEBSERVER_TECHNOLOGY', 'Web Technology', 0, 'DESCRIPTOR'],
        ['WIFI_ACCESS_POINT', 'WiFi Access Point Nearby', 0, 'ENTITY'],
        ['WIKIPEDIA_PAGE_EDIT', 'Wikipedia Page Edit', 0, 'DESCRIPTOR'],
    ]

    def __init__(self, *args, **kwargs):
        """
        Initialize database and create handle to the database file. Supports both legacy positional and new dict-based signatures.
        """
        # Modular signature: SpiderFootDb(opts, init=True)
        if len(args) >= 1 and isinstance(args[0], dict):
            opts = args[0]
            init = kwargs.get('init', False)
        # Legacy signature: SpiderFootDb(dbhost, dbport, dbname, dbuser, dbpass, ...)
        else:
            # Accept at least 5 positional args for legacy
            if len(args) < 5:
                raise TypeError("SpiderFootDb() missing required positional arguments: 'dbhost', 'dbport', 'dbname', 'dbuser', and 'dbpass'")
            dbhost, dbport, dbname, dbuser, dbpass = args[:5]
            opts = {
                '__dbtype': 'sqlite',  # or 'postgresql' if you want to support both
                '__database': dbname,
                '__dbhost': dbhost,
                '__dbport': dbport,
                '__dbuser': dbuser,
                '__dbpass': dbpass
            }
            # If more args, allow override of dbtype
            if len(args) > 5:
                opts['__dbtype'] = args[5]
            init = kwargs.get('init', False)
        self._core = DbCore(opts, init)
        self.dbh = self._core.dbh
        self.conn = self._core.conn
        self.dbhLock = self._core.dbhLock
        self.db_type = self._core.db_type
        self._scan = ScanManager(self.dbh, self.conn, self.dbhLock, self.db_type)
        self._event = EventManager(self.dbh, self.conn, self.dbhLock, self.db_type)
        self._config = ConfigManager(self.dbh, self.conn, self.dbhLock, self.db_type)
        self._correlation = CorrelationManager(self.dbh, self.conn, self.dbhLock, self.db_type)
        if not isinstance(opts, dict):
            raise TypeError(f"opts is {type(opts)}; expected dict()")
        if not opts:
            raise ValueError("opts is empty")
        if not opts.get('__database'):
            raise ValueError("opts['__database'] is empty")
        # ...existing code for sqlite/postgresql init...
        if self.db_type == 'sqlite':
            database_path = opts['__database']
            Path(database_path).parent.mkdir(exist_ok=True, parents=True)
            try:
                dbh = sqlite3.connect(database_path)
            except Exception as e:
                raise IOError(
                    f"Error connecting to internal database {database_path}") from e
            if dbh is None:
                raise IOError(
                    f"Could not connect to internal database, and could not create {database_path}") from None
            dbh.text_factory = str
            self.conn = dbh
            self.dbh = dbh.cursor()
            def __dbregex__(qry: str, data: str) -> bool:
                try:
                    rx = re.compile(qry, re.IGNORECASE | re.DOTALL)
                    ret = rx.match(data)
                except Exception:
                    return False
                return ret is not None
            with self.dbhLock:
                try:
                    self.dbh.execute('SELECT COUNT(*) FROM tbl_scan_config')
                    self.conn.create_function("REGEXP", 2, __dbregex__)
                except sqlite3.Error:
                    init = True
                    try:
                        self.create()
                    except Exception as e:
                        raise IOError(
                            "Tried to set up the SpiderFoot database schema, but failed") from e
                try:
                    self.dbh.execute(
                        "SELECT COUNT(*) FROM tbl_scan_correlation_results")
                except sqlite3.Error:
                    try:
                        for query in self.createSchemaQueries:
                            if "correlation" in query:
                                self.dbh.execute(query)
                        self.conn.commit()
                    except sqlite3.Error:
                        raise IOError("Looks like you are running a pre-4.0 database. Unfortunately "
                                      "SpiderFoot wasn't able to migrate you, so you'll need to delete "
                                      "your SpiderFoot database in order to proceed.") from None
                if init:
                    for row in self.eventDetails:
                        event = row[0]
                        event_descr = row[1]
                        event_raw = row[2]
                        event_type = row[3]
                        qry = "INSERT INTO tbl_event_types (event, event_descr, event_raw, event_type) VALUES (?, ?, ?, ?)"
                        try:
                            self.dbh.execute(qry, (
                                event, event_descr, event_raw, event_type
                            ))
                            self.conn.commit()
                        except Exception:
                            continue
                    self.conn.commit()
        elif self.db_type == 'postgresql':
            try:
                self.conn = psycopg2.connect(opts['__database'])
                self.dbh = self.conn.cursor(
                    cursor_factory=psycopg2.extras.DictCursor)
            except Exception as e:
                raise IOError(
                    f"Error connecting to PostgreSQL database {opts['__database']}") from e
            with self.dbhLock:
                try:
                    self.dbh.execute('SELECT COUNT(*) FROM tbl_scan_config')
                except psycopg2.Error:
                    init = True
                    try:
                        self.create()
                    except Exception as e:
                        raise IOError(
                            "Tried to set up the SpiderFoot database schema, but failed") from e
                if init:
                    for row in self.eventDetails:
                        event = row[0]
                        event_descr = row[1]
                        event_raw = row[2]
                        event_type = row[3]
                        qry = "INSERT INTO tbl_event_types (event, event_descr, event_raw, event_type) VALUES (%s, %s, %s, %s)"
                        try:
                            self.dbh.execute(qry, (
                                event, event_descr, event_raw, event_type
                            ))
                            self.conn.commit()
                        except Exception:
                            continue
                    self.conn.commit()
        else:
            raise ValueError(f"Unsupported database type: {self.db_type}")

    def connect(self):
        """
        Connect to the database using the provided parameters.
        """
        try:
            if self.dbtype == "sqlite":
                self.conn = sqlite3.connect(self.dbname)
            elif self.dbtype == "postgres":
                self.conn = psycopg2.connect(
                    host=self.dbhost,
                    port=self.dbport,
                    database=self.dbname,
                    user=self.dbuser,
                    password=self.dbpass
                )
            else:
                raise ValueError("Unsupported database type: {}".format(self.dbtype))

            self.cursor = self.conn.cursor()
            self._setup_managers()

        except Exception as e:
            print("Error connecting to database: {}".format(e))
            raise

    def _setup_managers(self):
        """
        Set up the various manager instances for interacting with the database.
        """
        self.managers['config'] = ConfigManager(self)
        self.managers['event'] = EventManager(self)
        self.managers['scan'] = ScanManager(self)
        self.managers['correlation'] = CorrelationManager(self)
        self.managers['utils'] = DbUtils(self)

    def close(self):
        """
        Close the database connection and release all resources.
        """
        import gc
        try:
            # Close all manager resources if they exist
            if hasattr(self, 'managers') and isinstance(self.managers, dict):
                for key, mgr in self.managers.items():
                    if hasattr(mgr, 'close'):
                        try:
                            mgr.close()
                        except Exception:
                            pass
                    self.managers[key] = None
                self.managers = None
            # Dereference all manager attributes
            for attr in ['_event', '_scan', '_config', '_correlation', '_core']:
                if hasattr(self, attr):
                    setattr(self, attr, None)
            if hasattr(self, 'cursor') and self.cursor:
                try:
                    self.cursor.close()
                except Exception:
                    pass
                self.cursor = None
            if hasattr(self, 'conn') and self.conn:
                try:
                    self.conn.close()
                except Exception:
                    pass
                self.conn = None
        except Exception:
            pass
        gc.collect()

    # --- Back-end database operations ---
    def create(self) -> None:
        return self._core.create()
    def close(self) -> None:
        return self._core.close()
    def vacuumDB(self) -> bool:
        return self._core.vacuumDB()
    # --- SCAN INSTANCE MANAGEMENT ---
    def scanInstanceCreate(self, *args, **kwargs):
        return self._scan.scanInstanceCreate(*args, **kwargs)
    def scanInstanceGet(self, scan_id):
        result = self._scan.scanInstanceGet(scan_id)
        if not result or result == []:
            return None
        return result[0]
    def scanInstanceUpdate(self, *args, **kwargs):
        return self._scan.scanInstanceUpdate(*args, **kwargs)
    def scanInstanceDelete(self, *args, **kwargs):
        return self._scan.scanInstanceDelete(*args, **kwargs)
    def scanInstanceList(self):
        return self._scan.scanInstanceList()
    # --- CONFIGURATION MANAGEMENT ---
    def configSet(self, *args, **kwargs):
        return self._config.configSet(*args, **kwargs)
    def configGet(self, *args, **kwargs):
        return self._config.configGet(*args, **kwargs)
    def configGetAll(self, *args, **kwargs):
        return self._config.configGetAll(*args, **kwargs)
    def scanConfigSet(self, scan_id, optMap):
        return self._config.scanConfigSet(scan_id, optMap)
    def scanConfigGet(self, scan_id):
        return self._config.scanConfigGet(scan_id)
    # --- EVENT TYPES ---
    def eventTypes(self, *args, **kwargs):
        return self._core.eventTypes(*args, **kwargs)
    # --- EVENT MANAGEMENT ---
    def eventAdd(self, *args, **kwargs):
        return self._event.eventAdd(*args, **kwargs)
    def eventGet(self, *args, **kwargs):
        return self._event.eventGet(*args, **kwargs)
    def scanEventStore(self, instanceId, sfEvent, truncateSize=0):
        return self._event.scanEventStore(instanceId, sfEvent, truncateSize)
    # --- CORRELATION MANAGEMENT ---
    def correlationAdd(self, *args, **kwargs):
        return self._correlation.correlationAdd(*args, **kwargs)
    def correlationGet(self, *args, **kwargs):
        return self._correlation.correlationGet(*args, **kwargs)
    # --- LOGGING ---
    def scanLogEvent(self, instanceId, classification, message, component=None):
        return self._event.scanLogEvent(instanceId, classification, message, component)
    def scanLogEvents(self, batch: list) -> bool:
        return self._event.scanLogEvents(batch)
    def scanLogs(self, instanceId: str, limit: int = None, fromRowId: int = 0, reverse: bool = False) -> list:
        return self._event.scanLogs(instanceId, limit, fromRowId, reverse)
    def scanErrors(self, instanceId: str, limit: int = 0) -> list:
        return self._event.scanErrors(instanceId, limit)
    # --- SEARCH ---
    def search(self, criteria: dict, filterFp: bool = False) -> list:
        return self._event.search(criteria, filterFp)
    # --- SCAN RESULT / EVENT FUNCTIONS ---
    def scanResultEvent(self, instanceId: str, eventType: str = 'ALL', srcModule: str = None, data: list = None, sourceId: list = None, correlationId: str = None, filterFp: bool = False) -> list:
        return self._event.scanResultEvent(instanceId, eventType, srcModule, data, sourceId, correlationId, filterFp)
    def scanResultEventUnique(self, instanceId: str, eventType: str = 'ALL', filterFp: bool = False) -> list:
        return self._event.scanResultEventUnique(instanceId, eventType, filterFp)
    def scanResultSummary(self, instanceId: str, by: str = "type") -> list:
        return self._event.scanResultSummary(instanceId, by)
    def scanResultHistory(self, instanceId: str) -> list:
        return self._event.scanResultHistory(instanceId)
    def scanResultsUpdateFP(self, instanceId: str, resultHashes: list, fpFlag: int) -> bool:
        return self._event.scanResultsUpdateFP(instanceId, resultHashes, fpFlag)
    # --- CORRELATION RESULTS ---
    def correlationResultCreate(self, instanceId: str, event_hash: str, ruleId: str, ruleName: str, ruleDescr: str, ruleRisk: str, ruleYaml: str, correlationTitle: str, eventHashes: list) -> str:
        return self._correlation.correlationResultCreate(instanceId, event_hash, ruleId, ruleName, ruleDescr, ruleRisk, ruleYaml, correlationTitle, eventHashes)
    def scanCorrelationSummary(self, instanceId: str, by: str = "rule") -> list:
        return self._correlation.scanCorrelationSummary(instanceId, by)
    def scanCorrelationList(self, instanceId: str) -> list:
        return self._correlation.scanCorrelationList(instanceId)
