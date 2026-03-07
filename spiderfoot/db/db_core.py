# -------------------------------------------------------------------------------
# Name:         Modular SpiderFoot Database Module
# Purpose:      Common functions for working with the database back-end.
#
# Author:      Agostino Panico @poppopjmp
#
# Created:     30/06/2025
# Copyright:   (c) Agostino Panico 2025
# Licence:     MIT
# -------------------------------------------------------------------------------
"""
Core DB connection, locking, schema management, and shared resources for SpiderFootDb.
"""
from __future__ import annotations

import logging
import threading
import psycopg2
import time
from ..config.constants import DB_RETRY_BACKOFF_BASE
from spiderfoot.db.db_utils import (
    get_placeholder, get_upsert_clause,
    get_schema_version_queries, is_transient_error, normalize_db_type
)
from typing import Any

log = logging.getLogger(__name__)

class DbCore:
    """
    Core database connection and management class for SpiderFootDb.
    
    NOTE: dbh, conn, and dbhLock are instance-level attributes (set in
    __init__) to ensure microservice isolation — each SpiderFootDb
    instance owns its own connection and lock.  Former class-level
    shared state was removed in RC190 (Cycle 28).
    """
    # Class-level pool lock – initialised eagerly to avoid TOCTOU races
    _pool_lock: threading.Lock = threading.Lock()
    _pool: "psycopg2.pool.ThreadedConnectionPool | None" = None

    # PostgreSQL schema queries (sole database backend)
    createSchemaQueries = [
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
        "CREATE INDEX IF NOT EXISTS idx_scan_correlation_events ON tbl_scan_correlation_results_events (correlation_id)",
        "CREATE INDEX IF NOT EXISTS idx_scan_results_type_time ON tbl_scan_results (scan_instance_id, type, generated DESC)",
        "CREATE INDEX IF NOT EXISTS idx_scan_results_fp ON tbl_scan_results (false_positive) WHERE false_positive = 1",
    ]
    # Cycle 73: GIN trigram index for substring search on event data.
    # pg_trgm extension must be available — creation failure is non-fatal.
    trigram_schema_queries = [
        "CREATE EXTENSION IF NOT EXISTS pg_trgm",
        "CREATE INDEX IF NOT EXISTS idx_scan_results_data_trgm ON tbl_scan_results USING gin(data gin_trgm_ops)",
    ]
    # Canonical SpiderFoot event type catalog.
    # Format: (event_key, description, is_raw, category)
    #   is_raw: 0 = structured, 1 = raw/large blob
    #   category: ENTITY | DESCRIPTOR | DATA | SUBENTITY | INTERNAL
    eventDetails = [
        # --- Internal ---
        ("ROOT", "Internal root event", 0, "INTERNAL"),
        ("INITIAL_TARGET", "Initial scan target", 0, "INTERNAL"),
        # --- Network Entities ---
        ("IP_ADDRESS", "IPv4 address", 0, "ENTITY"),
        ("IPV6_ADDRESS", "IPv6 address", 0, "ENTITY"),
        ("INTERNAL_IP_ADDRESS", "Internal/private IP address", 0, "ENTITY"),
        ("NETBLOCK_MEMBER", "Netblock membership", 0, "ENTITY"),
        ("NETBLOCK_OWNER", "Netblock owner", 0, "ENTITY"),
        ("NETBLOCKV6_MEMBER", "IPv6 netblock membership", 0, "ENTITY"),
        ("NETBLOCKV6_OWNER", "IPv6 netblock owner", 0, "ENTITY"),
        ("BGP_AS_MEMBER", "BGP AS membership", 0, "ENTITY"),
        ("BGP_AS_OWNER", "BGP AS owner", 0, "ENTITY"),
        # --- DNS / Infrastructure Entities ---
        ("INTERNET_NAME", "Hostname/FQDN", 0, "ENTITY"),
        ("INTERNET_NAME_UNRESOLVED", "Hostname that does not resolve", 0, "ENTITY"),
        ("DOMAIN_NAME", "Domain name", 0, "ENTITY"),
        ("DOMAIN_NAME_PARENT", "Parent domain name", 0, "ENTITY"),
        ("SIMILARDOMAIN", "Similar/lookalike domain", 0, "ENTITY"),
        ("CO_HOSTED_SITE", "Co-hosted website", 0, "ENTITY"),
        # --- Identity Entities ---
        ("EMAILADDR", "Email address", 0, "ENTITY"),
        ("EMAILADDR_COMPROMISED", "Compromised email address", 0, "ENTITY"),
        ("EMAILADDR_GENERIC", "Generic email address", 0, "ENTITY"),
        ("EMAILADDR_DELIVERABLE", "Deliverable email address", 0, "ENTITY"),
        ("EMAILADDR_DISPOSABLE", "Disposable email address", 0, "ENTITY"),
        ("EMAILADDR_UNDELIVERABLE", "Undeliverable email address", 0, "ENTITY"),
        ("PHONE_NUMBER", "Phone number", 0, "ENTITY"),
        ("PHONE_NUMBER_COMPROMISED", "Compromised phone number", 0, "ENTITY"),
        ("HUMAN_NAME", "Person name", 0, "ENTITY"),
        ("USERNAME", "Username", 0, "ENTITY"),
        ("COMPANY_NAME", "Company/organization name", 0, "ENTITY"),
        ("ACCOUNT_EXTERNAL_OWNED", "External account owned", 0, "ENTITY"),
        ("ACCOUNT_EXTERNAL_OWNED_COMPROMISED", "Compromised external account", 0, "ENTITY"),
        ("SOCIAL_MEDIA", "Social media presence", 0, "ENTITY"),
        ("SOCIAL_MEDIA_PROFILE", "Social media profile", 0, "ENTITY"),
        ("SIMILAR_ACCOUNT_EXTERNAL", "Similar external account", 0, "ENTITY"),
        ("JOB_TITLE", "Job title", 0, "ENTITY"),
        ("DATE_HUMAN_DOB", "Date of birth", 0, "ENTITY"),
        # --- Crypto / Blockchain Entities ---
        ("BITCOIN_ADDRESS", "Bitcoin address", 0, "ENTITY"),
        ("BITCOIN_BALANCE", "Bitcoin balance", 0, "DESCRIPTOR"),
        ("ETHEREUM_ADDRESS", "Ethereum address", 0, "ENTITY"),
        ("ETHEREUM_BALANCE", "Ethereum balance", 0, "DESCRIPTOR"),
        ("ARBITRUM_ADDRESS", "Arbitrum address", 0, "ENTITY"),
        ("ARBITRUM_TX", "Arbitrum transaction", 0, "DESCRIPTOR"),
        # --- Financial ---
        ("CREDIT_CARD_NUMBER", "Credit card number", 0, "ENTITY"),
        ("IBAN_NUMBER", "IBAN number", 0, "ENTITY"),
        ("LEI", "Legal Entity Identifier", 0, "ENTITY"),
        # --- Affiliate / Sub-entities ---
        ("AFFILIATE_DOMAIN_NAME", "Affiliated domain name", 0, "SUBENTITY"),
        ("AFFILIATE_DOMAIN_UNREGISTERED", "Unregistered affiliate domain", 0, "SUBENTITY"),
        ("AFFILIATE_DOMAIN_WHOIS", "Affiliate domain WHOIS data", 1, "SUBENTITY"),
        ("AFFILIATE_EMAILADDR", "Affiliate email address", 0, "SUBENTITY"),
        ("AFFILIATE_INTERNET_NAME", "Affiliate hostname", 0, "SUBENTITY"),
        ("AFFILIATE_INTERNET_NAME_HIJACKABLE", "Hijackable affiliate hostname", 0, "SUBENTITY"),
        ("AFFILIATE_IPADDR", "Affiliate IP address", 0, "SUBENTITY"),
        ("AFFILIATE_IPV6_ADDRESS", "Affiliate IPv6 address", 0, "SUBENTITY"),
        ("AFFILIATE_WEB_CONTENT", "Affiliate web page content", 1, "SUBENTITY"),
        # --- Infrastructure Descriptors ---
        ("DNS_TEXT", "DNS TXT record", 0, "DESCRIPTOR"),
        ("DNS_SPF", "DNS SPF record", 0, "DESCRIPTOR"),
        ("DNS_SRV", "DNS SRV record", 0, "DESCRIPTOR"),
        ("DOMAIN_REGISTRAR", "Domain registrar", 0, "DESCRIPTOR"),
        ("DOMAIN_WHOIS", "Domain WHOIS data", 1, "DESCRIPTOR"),
        ("SIMILARDOMAIN_WHOIS", "Similar domain WHOIS data", 1, "DESCRIPTOR"),
        ("NETBLOCK_WHOIS", "Netblock WHOIS data", 1, "DESCRIPTOR"),
        ("PROVIDER_DNS", "DNS provider", 0, "DESCRIPTOR"),
        ("PROVIDER_HOSTING", "Hosting provider", 0, "DESCRIPTOR"),
        ("PROVIDER_JAVASCRIPT", "JavaScript CDN provider", 0, "DESCRIPTOR"),
        ("PROVIDER_MAIL", "Mail provider", 0, "DESCRIPTOR"),
        ("PROVIDER_TELCO", "Telecom provider", 0, "DESCRIPTOR"),
        ("CARRIER_NAME", "Phone carrier name", 0, "DESCRIPTOR"),
        ("CARRIER_TYPE", "Phone carrier type", 0, "DESCRIPTOR"),
        # --- Web Descriptors ---
        ("WEBSERVER_BANNER", "Web server banner", 0, "DESCRIPTOR"),
        ("WEBSERVER_HTTPHEADERS", "HTTP response headers", 1, "DESCRIPTOR"),
        ("WEBSERVER_STRANGEHEADER", "Unusual HTTP header", 0, "DESCRIPTOR"),
        ("WEBSERVER_TECHNOLOGY", "Web technology detected", 0, "DESCRIPTOR"),
        ("HTTP_CODE", "HTTP status code", 0, "DESCRIPTOR"),
        ("WEB_ANALYTICS_ID", "Web analytics tracking ID", 0, "DESCRIPTOR"),
        ("CDN_DETECTED", "CDN detected", 0, "DESCRIPTOR"),
        # --- SSL/TLS ---
        ("SSL_CERTIFICATE_ISSUED", "SSL certificate details", 0, "DESCRIPTOR"),
        ("SSL_CERTIFICATE_ISSUER", "SSL certificate issuer", 0, "DESCRIPTOR"),
        ("SSL_CERTIFICATE_EXPIRED", "Expired SSL certificate", 0, "DESCRIPTOR"),
        ("SSL_CERTIFICATE_EXPIRING", "SSL certificate nearing expiry", 0, "DESCRIPTOR"),
        ("SSL_CERTIFICATE_MISMATCH", "SSL cert hostname mismatch", 0, "DESCRIPTOR"),
        ("SSL_CERTIFICATE_RAW", "Raw SSL certificate data", 1, "DATA"),
        # --- Ports / Services ---
        ("TCP_PORT_OPEN", "Open TCP port", 0, "DESCRIPTOR"),
        ("TCP_PORT_OPEN_BANNER", "TCP port service banner", 0, "DESCRIPTOR"),
        ("UDP_PORT_OPEN", "Open UDP port", 0, "DESCRIPTOR"),
        ("UDP_PORT_OPEN_INFO", "UDP port service information", 0, "DESCRIPTOR"),
        # --- Cloud ---
        ("CLOUD_PROVIDER", "Cloud provider", 0, "DESCRIPTOR"),
        ("CLOUD_INSTANCE_TYPE", "Cloud instance type", 0, "DESCRIPTOR"),
        ("CLOUD_STORAGE_BUCKET", "Cloud storage bucket", 0, "ENTITY"),
        ("CLOUD_STORAGE_BUCKET_OPEN", "Open cloud storage bucket", 0, "ENTITY"),
        ("CLOUD_STORAGE_OPEN", "Open cloud storage", 0, "ENTITY"),
        # --- System / Software ---
        ("OPERATING_SYSTEM", "Operating system", 0, "DESCRIPTOR"),
        ("SOFTWARE_USED", "Software detected", 0, "DESCRIPTOR"),
        ("DEVICE_TYPE", "Device type", 0, "DESCRIPTOR"),
        ("DESCRIPTION_ABSTRACT", "Entity description/abstract", 0, "DESCRIPTOR"),
        # --- Geolocation ---
        ("GEOINFO", "Geolocation data", 0, "DESCRIPTOR"),
        ("COUNTRY_NAME", "Country", 0, "DESCRIPTOR"),
        ("REGION_NAME", "Region/state", 0, "DESCRIPTOR"),
        ("PHYSICAL_ADDRESS", "Physical address", 0, "DESCRIPTOR"),
        ("PHYSICAL_COORDINATES", "GPS coordinates", 0, "DESCRIPTOR"),
        # --- URLs ---
        ("LINKED_URL_INTERNAL", "Internal URL", 0, "ENTITY"),
        ("LINKED_URL_EXTERNAL", "External URL", 0, "ENTITY"),
        ("URL_FORM", "Web form URL", 0, "ENTITY"),
        ("URL_UPLOAD", "File upload URL", 0, "ENTITY"),
        ("URL_JAVASCRIPT", "JavaScript resource URL", 0, "ENTITY"),
        ("URL_WEB_FRAMEWORK", "Web framework URL", 0, "ENTITY"),
        ("URL_WEB", "Web page URL", 0, "ENTITY"),
        ("URL_STATIC", "Static resource URL", 0, "ENTITY"),
        ("URL_DIRECTORY", "Directory listing URL", 0, "ENTITY"),
        ("URL_ADBLOCKED_EXTERNAL", "Ad-blocked external URL", 0, "ENTITY"),
        ("URL_ADBLOCKED_INTERNAL", "Ad-blocked internal URL", 0, "ENTITY"),
        # --- Vulnerability ---
        ("VULNERABILITY_CVE_CRITICAL", "Critical severity CVE", 0, "DESCRIPTOR"),
        ("VULNERABILITY_CVE_HIGH", "High severity CVE", 0, "DESCRIPTOR"),
        ("VULNERABILITY_CVE_MEDIUM", "Medium severity CVE", 0, "DESCRIPTOR"),
        ("VULNERABILITY_CVE_LOW", "Low severity CVE", 0, "DESCRIPTOR"),
        ("VULNERABILITY_GENERAL", "General vulnerability", 0, "DESCRIPTOR"),
        ("VULNERABILITY_DISCLOSURE", "Vulnerability disclosure", 0, "DESCRIPTOR"),
        # --- Reputation / Threat Intel ---
        ("MALICIOUS_IPADDR", "Malicious IP address", 0, "DESCRIPTOR"),
        ("MALICIOUS_INTERNET_NAME", "Malicious hostname", 0, "DESCRIPTOR"),
        ("MALICIOUS_AFFILIATE_IPADDR", "Malicious affiliate IP", 0, "DESCRIPTOR"),
        ("MALICIOUS_AFFILIATE_INTERNET_NAME", "Malicious affiliate hostname", 0, "DESCRIPTOR"),
        ("MALICIOUS_EMAILADDR", "Malicious email address", 0, "DESCRIPTOR"),
        ("MALICIOUS_SUBNET", "Malicious subnet", 0, "DESCRIPTOR"),
        ("MALICIOUS_COHOST", "Malicious co-hosted site", 0, "DESCRIPTOR"),
        ("MALICIOUS_PHONE_NUMBER", "Malicious phone number", 0, "DESCRIPTOR"),
        ("MALICIOUS_ASN", "Malicious AS number", 0, "DESCRIPTOR"),
        ("MALICIOUS_BITCOIN_ADDRESS", "Malicious Bitcoin address", 0, "DESCRIPTOR"),
        ("MALICIOUS_NETBLOCK", "Malicious netblock", 0, "DESCRIPTOR"),
        ("BLACKLISTED_IPADDR", "Blacklisted IP address", 0, "DESCRIPTOR"),
        ("BLACKLISTED_AFFILIATE_IPADDR", "Blacklisted affiliate IP", 0, "DESCRIPTOR"),
        ("BLACKLISTED_INTERNET_NAME", "Blacklisted hostname", 0, "DESCRIPTOR"),
        ("BLACKLISTED_AFFILIATE_INTERNET_NAME", "Blacklisted affiliate hostname", 0, "DESCRIPTOR"),
        ("BLACKLISTED_COHOST", "Blacklisted co-hosted site", 0, "DESCRIPTOR"),
        ("BLACKLISTED_NETBLOCK", "Blacklisted netblock", 0, "DESCRIPTOR"),
        ("BLACKLISTED_SUBNET", "Blacklisted subnet", 0, "DESCRIPTOR"),
        ("DEFACED_INTERNET_NAME", "Defaced hostname", 0, "DESCRIPTOR"),
        ("DEFACED_IPADDR", "Defaced IP address", 0, "DESCRIPTOR"),
        ("DEFACED_AFFILIATE_INTERNET_NAME", "Defaced affiliate hostname", 0, "DESCRIPTOR"),
        ("DEFACED_AFFILIATE_IPADDR", "Defaced affiliate IP", 0, "DESCRIPTOR"),
        ("DEFACED_COHOST", "Defaced co-hosted site", 0, "DESCRIPTOR"),
        ("PROXY_HOST", "Proxy/anonymizer host", 0, "DESCRIPTOR"),
        ("TOR_EXIT_NODE", "Tor exit node", 0, "DESCRIPTOR"),
        ("VPN_HOST", "VPN server", 0, "DESCRIPTOR"),
        # --- Data Leaks ---
        ("PASSWORD_COMPROMISED", "Compromised password", 0, "DESCRIPTOR"),
        ("HASH_COMPROMISED", "Compromised hash", 0, "DESCRIPTOR"),
        ("CREDENTIAL_LEAK", "Credential leak", 0, "DESCRIPTOR"),
        ("API_KEY_LEAK", "Exposed API key", 0, "DESCRIPTOR"),
        ("LEAKSITE_CONTENT", "Leak site content", 1, "DATA"),
        ("LEAKSITE_URL", "Leak site URL", 0, "ENTITY"),
        ("DARKNET_MENTION_CONTENT", "Dark web mention content", 1, "DATA"),
        ("DARKNET_MENTION_URL", "Dark web mention URL", 0, "ENTITY"),
        ("SANCTIONS_LIST_MATCH", "Sanctions list match", 0, "DESCRIPTOR"),
        ("MONEY_LAUNDERING_INDICATOR", "Money laundering indicator", 0, "DESCRIPTOR"),
        # --- Raw / Large Data ---
        ("RAW_DNS_RECORDS", "Raw DNS records", 1, "DATA"),
        ("RAW_RIR_DATA", "Raw regional internet registry data", 1, "DATA"),
        ("RAW_FILE_META_DATA", "Raw file metadata", 1, "DATA"),
        ("TARGET_WEB_CONTENT", "Target web page content", 1, "DATA"),
        ("TARGET_WEB_CONTENT_TYPE", "Target web content MIME type", 0, "DESCRIPTOR"),
        ("TARGET_WEB_COOKIE", "Web cookie", 0, "DESCRIPTOR"),
        ("SEARCH_ENGINE_WEB_CONTENT", "Search engine result content", 1, "DATA"),
        ("DOCUMENT_TEXT", "Extracted document text", 1, "DATA"),
        ("BASE64_DATA", "Base64 encoded data", 1, "DATA"),
        # --- Files ---
        ("INTERESTING_FILE", "Interesting file discovered", 0, "DESCRIPTOR"),
        ("INTERESTING_FILE_HISTORIC", "Historic interesting file", 0, "DESCRIPTOR"),
        ("JUNK_FILE", "Junk/uninteresting file", 0, "DESCRIPTOR"),
        ("PUBLIC_CODE_REPO", "Public code repository", 0, "ENTITY"),
        ("PGP_KEY", "PGP public key", 0, "ENTITY"),
        ("WIFI_ACCESS_POINT", "WiFi access point", 0, "ENTITY"),
        # --- Social Media Content ---
        ("SOCIAL_MEDIA_CONTENT", "Social media content", 1, "DATA"),
        ("SOCIAL_MEDIA_HASHTAG", "Social media hashtag", 0, "DESCRIPTOR"),
        ("APARAT_VIDEO", "Aparat video", 0, "ENTITY"),
        ("BLUESKY_POST", "Bluesky post", 0, "ENTITY"),
        ("DIDEO_VIDEO", "Dideo video", 0, "ENTITY"),
        ("DISCORD_MESSAGE", "Discord message", 0, "ENTITY"),
        ("DOUYIN_VIDEO", "Douyin video", 0, "ENTITY"),
        ("FOURCHAN_POST", "4chan post", 0, "ENTITY"),
        ("TELEGRAM_MESSAGE", "Telegram message", 0, "ENTITY"),
        ("WECHAT_MESSAGE", "WeChat message", 0, "ENTITY"),
        ("WIKIPEDIA_PAGE_EDIT", "Wikipedia page edit", 0, "ENTITY"),
        ("XIAOHONGSHU_POST", "Xiaohongshu post", 0, "ENTITY"),
        # --- AI / Analysis (v6) ---
        ("AI_ANOMALY_DETECTED", "AI-detected anomaly", 0, "DESCRIPTOR"),
        ("AI_IOC_CORRELATION", "AI indicator-of-compromise correlation", 0, "DESCRIPTOR"),
        ("AI_NLP_ANALYSIS", "AI NLP analysis result", 1, "DATA"),
        ("AI_THREAT_PREDICTION", "AI threat prediction", 0, "DESCRIPTOR"),
        ("AI_THREAT_SCORE", "AI threat score", 0, "DESCRIPTOR"),
        ("AI_THREAT_SIGNATURE", "AI threat signature", 0, "DESCRIPTOR"),
        # --- Blockchain Analysis (v6) ---
        ("BLOCKCHAIN_ANALYSIS", "Blockchain analysis result", 0, "DESCRIPTOR"),
        ("BLOCKCHAIN_TRANSACTION_FLOW", "Blockchain transaction flow", 1, "DATA"),
        ("CRYPTOCURRENCY_EXCHANGE_ATTRIBUTION", "Cryptocurrency exchange attribution", 0, "DESCRIPTOR"),
        ("CRYPTOCURRENCY_RISK_ASSESSMENT", "Cryptocurrency risk assessment", 0, "DESCRIPTOR"),
        ("WALLET_CLUSTER", "Cryptocurrency wallet cluster", 0, "DESCRIPTOR"),
        # --- Advanced Pattern Analysis (v6) ---
        ("BEHAVIORAL_PATTERN", "Behavioral pattern detected", 0, "DESCRIPTOR"),
        ("TEMPORAL_PATTERN", "Temporal pattern detected", 0, "DESCRIPTOR"),
        ("ENTITY_RELATIONSHIP", "Entity relationship link", 0, "DESCRIPTOR"),
        ("GEOSPATIAL_CLUSTER", "Geospatial cluster", 0, "DESCRIPTOR"),
        ("IDENTITY_RESOLUTION", "Resolved identity", 0, "DESCRIPTOR"),
        ("SUSPICIOUS_ACTIVITY", "Suspicious activity detected", 0, "DESCRIPTOR"),
        ("OPTIMIZATION_SUGGESTION", "Optimization suggestion", 0, "INTERNAL"),
        # --- Legacy compatibility (from SpiderFootDb catalog) ---
        ("ACCOUNT_EXTERNAL_USER_SHARED_COMPROMISED", "Compromised shared external account", 0, "ENTITY"),
        ("AFFILIATE_INTERNET_NAME_UNRESOLVED", "Unresolved affiliate hostname", 0, "SUBENTITY"),
        ("AFFILIATE_COMPANY_NAME", "Affiliate company name", 0, "SUBENTITY"),
        ("AFFILIATE_DESCRIPTION_CATEGORY", "Affiliate entity category", 0, "SUBENTITY"),
        ("AFFILIATE_DESCRIPTION_ABSTRACT", "Affiliate entity abstract", 0, "SUBENTITY"),
        ("APPSTORE_ENTRY", "App store entry", 0, "ENTITY"),
        ("CO_HOSTED_SITE_DOMAIN", "Co-hosted site domain", 0, "ENTITY"),
        ("CO_HOSTED_SITE_DOMAIN_WHOIS", "Co-hosted site domain WHOIS data", 1, "DESCRIPTOR"),
        ("DESCRIPTION_CATEGORY", "Entity category/classification", 0, "DESCRIPTOR"),
        ("ERROR_MESSAGE", "Error/warning message", 0, "INTERNAL"),
        ("HASH", "File/data hash", 0, "DESCRIPTOR"),
        ("PERSON_NAME", "Person name (legacy)", 0, "ENTITY"),
        ("PHONE_NUMBER_TYPE", "Phone number type", 0, "DESCRIPTOR"),
        # --- Historic URL variants ---
        ("URL_FLASH", "Flash content URL", 0, "ENTITY"),
        ("URL_JAVA_APPLET", "Java applet URL", 0, "ENTITY"),
        ("URL_PASSWORD", "Password-containing URL", 0, "ENTITY"),
        ("URL_FILE", "File URL", 0, "ENTITY"),
        ("URL_FORM_HISTORIC", "Historic form URL", 0, "ENTITY"),
        ("URL_FLASH_HISTORIC", "Historic Flash URL", 0, "ENTITY"),
        ("URL_JAVASCRIPT_HISTORIC", "Historic JavaScript URL", 0, "ENTITY"),
        ("URL_WEB_FRAMEWORK_HISTORIC", "Historic web framework URL", 0, "ENTITY"),
        ("URL_JAVA_APPLET_HISTORIC", "Historic Java applet URL", 0, "ENTITY"),
        ("URL_STATIC_HISTORIC", "Historic static resource URL", 0, "ENTITY"),
        ("URL_PASSWORD_HISTORIC", "Historic password URL", 0, "ENTITY"),
        ("URL_UPLOAD_HISTORIC", "Historic upload URL", 0, "ENTITY"),
        # --- Additional blockchain ---
        ("BITCOIN_TRANSACTION", "Bitcoin transaction", 0, "DESCRIPTOR"),
        ("ETHEREUM_TRANSACTION", "Ethereum transaction", 0, "DESCRIPTOR"),
        ("ETHEREUM_TX", "Ethereum transaction hash", 0, "DESCRIPTOR"),
        ("BNB_ADDRESS", "BNB chain address", 0, "ENTITY"),
        ("BNB_TX", "BNB chain transaction", 0, "DESCRIPTOR"),
        ("TRON_ADDRESS", "TRON address", 0, "ENTITY"),
        ("TRON_TX", "TRON transaction", 0, "DESCRIPTOR"),
        ("CRYPTOCURRENCY_ADDRESS", "Cryptocurrency address (generic)", 0, "ENTITY"),
        # --- Additional infrastructure ---
        ("CELL_TOWER", "Cell tower identifier", 0, "ENTITY"),
        ("MAC_ADDRESS", "MAC address", 0, "ENTITY"),
        # --- Documents / user data ---
        ("DOCUMENT_UPLOAD", "Uploaded document", 1, "DATA"),
        ("REPORT_UPLOAD", "Uploaded report", 1, "DATA"),
        ("USER_DOCUMENT", "User document", 1, "DATA"),
        ("USER_INPUT_DATA", "User-supplied input data", 1, "DATA"),
        # --- Additional social media platforms ---
        ("INSTAGRAM_POST", "Instagram post", 0, "ENTITY"),
        ("MASTODON_POST", "Mastodon post", 0, "ENTITY"),
        ("MATRIX_MESSAGE", "Matrix message", 0, "ENTITY"),
        ("MATTERMOST_MESSAGE", "Mattermost message", 0, "ENTITY"),
        ("REDDIT_POST", "Reddit post", 0, "ENTITY"),
        ("ROCKETCHAT_MESSAGE", "Rocket.Chat message", 0, "ENTITY"),
        ("RUBIKA_MESSAGE", "Rubika message", 0, "ENTITY"),
        ("SOROUSH_MESSAGE", "Soroush message", 0, "ENTITY"),
        ("WHATSAPP_MESSAGE", "WhatsApp message", 0, "ENTITY"),
        ("SOCIAL_MEDIA_MENTION", "Social media mention", 0, "DESCRIPTOR"),
        ("SOCIAL_MEDIA_NETWORK", "Social media network identified", 0, "DESCRIPTOR"),
        # --- WiFi hotspot sources ---
        ("OPENWIFIMAP_HOTSPOT", "OpenWiFiMap hotspot", 0, "ENTITY"),
        ("WIFICAFESPOTS_HOTSPOT", "WiFiCafeSpots hotspot", 0, "ENTITY"),
        ("WIFIMAPIO_HOTSPOT", "WiFiMap.io hotspot", 0, "ENTITY"),
        ("UNWIREDLABS_GEOINFO", "UnwiredLabs geolocation data", 0, "DESCRIPTOR"),
        # --- Threat intelligence / correlation ---
        ("THREAT_INTELLIGENCE", "Threat intelligence data", 0, "DESCRIPTOR"),
        ("CORRELATION_ANALYSIS", "Correlation analysis result", 0, "DESCRIPTOR"),
        # --- Performance / monitoring (internal) ---
        ("PERFORMANCE_STATS", "Performance statistics", 0, "INTERNAL"),
        ("CACHE_STATS", "Cache statistics", 0, "INTERNAL"),
        ("RESOURCE_USAGE", "Resource usage data", 0, "INTERNAL"),
        # --- Security events (from sfp__security_hardening) ---
        ("SECURITY_AUDIT_EVENT", "Security audit event", 0, "INTERNAL"),
        ("SECURITY_VIOLATION", "Security violation detected", 0, "DESCRIPTOR"),
        ("ZERO_TRUST_VIOLATION", "Zero-trust policy violation", 0, "DESCRIPTOR"),
        ("AUTHENTICATION_FAILURE", "Authentication failure", 0, "DESCRIPTOR"),
        ("AUTHORIZATION_DENIED", "Authorization denied", 0, "DESCRIPTOR"),
    ]
    schema_version_table = """
        CREATE TABLE IF NOT EXISTS tbl_schema_version (
            version INTEGER NOT NULL,
            applied_at BIGINT NOT NULL
        )
    """
    if schema_version_table not in createSchemaQueries:
        createSchemaQueries.insert(0, schema_version_table)
    SCHEMA_VERSION = 1  # Increment this on every schema change

    def _log_db_error(self, msg, exc):
        log.error("[DB] %s: %s", msg, exc)

    def __init__(self, opts: dict, init: bool = False) -> None:
        """
        Initialize the DbCore object.

        Args:
            opts (dict): Options for the database connection.
            init (bool, optional): Flag to initialize the database. Defaults to False.
        """
        # Instance-level connection state (not shared across instances)
        self.dbh = None
        self.conn = None
        self.dbhLock = threading.RLock()

        if not isinstance(opts, dict):
            raise TypeError(f"opts is {type(opts)}; expected dict()")
        if not opts:
            raise ValueError("opts is empty")
        if '__database' not in opts:
            raise ValueError("__database key missing in opts")
        if '__dbtype' not in opts:
            opts['__dbtype'] = 'postgresql'
        self.db_type = normalize_db_type(opts['__dbtype'])
        if self.db_type != 'postgresql':
            raise ValueError(f"Unsupported database type: {self.db_type}. Only PostgreSQL is supported.")
        database_path = opts['__database']
        if not database_path or not isinstance(database_path, str):
            raise ValueError("__database must be a non-empty connection string")
        if self.db_type == 'postgresql':
            try:
                import psycopg2.extras
                from psycopg2.pool import ThreadedConnectionPool

                # Thread-safe, class-level connection pool (created once per DSN)
                with DbCore._pool_lock:
                    if DbCore._pool is None or DbCore._pool.closed:
                        DbCore._pool = ThreadedConnectionPool(
                            minconn=2,
                            maxconn=int(opts.get('__db_max_connections', 20)),
                            dsn=database_path,
                        )
                        log.info("Created PostgreSQL connection pool (max=%s)",
                                 opts.get('__db_max_connections', 20))

                self.conn = DbCore._pool.getconn()
                self.dbh = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
                self._owns_pooled_conn = True
            except Exception as e:
                self._log_db_error(f"Error connecting to PostgreSQL database {database_path}", e)
                raise OSError(f"Error connecting to PostgreSQL database {database_path}") from e
            with self.dbhLock:
                try:
                    self.create()
                except Exception as e:
                    self._log_db_error("Tried to set up the SpiderFoot database schema, but failed", e)
                    raise OSError("Tried to set up the SpiderFoot database schema, but failed") from e
                try:
                    self.dbh.execute("SELECT COUNT(*) FROM tbl_event_types")
                    if self.dbh.fetchone()[0] == 0:
                        for row in self.eventDetails:
                            event = row[0]
                            event_descr = row[1]
                            event_raw = row[2]
                            event_type = row[3]
                            ph = get_placeholder(self.db_type)
                            upsert_clause = get_upsert_clause(self.db_type, 'tbl_event_types', ['event'], ['event_descr', 'event_raw', 'event_type'])
                            qry = f"INSERT INTO tbl_event_types (event, event_descr, event_raw, event_type) VALUES ({ph}, {ph}, {ph}, {ph}) {upsert_clause}"
                            try:
                                self.dbh.execute(qry, (
                                    event, event_descr, event_raw, event_type
                                ))
                            except Exception as e:
                                self._log_db_error("Failed to insert event type", e)
                                continue
                        self.conn.commit()
                except Exception as e:
                    self._log_db_error("Failed to populate event types", e)
                    raise OSError("Failed to populate event types") from e
        else:
            raise ValueError(f"Unsupported database type: {self.db_type}")

    def get_schema_version(self) -> int:
        """Return the current schema version (int) or 0 if not set."""
        with self.dbhLock:
            try:
                queries = get_schema_version_queries(self.db_type)
                self.dbh.execute(queries['get'])
                row = self.dbh.fetchone()
                return int(row[0]) if row else 0
            except Exception:
                # Rollback failed transaction for PostgreSQL
                try:
                    self.conn.rollback()
                except Exception:
                    pass
                return 0

    def set_schema_version(self, version: int | None = None) -> None:
        """Set the schema version to the given value (or current if None)."""
        if version is None:
            version = self.SCHEMA_VERSION
        now = int(time.time())
        with self.dbhLock:
            for attempt in range(3):
                try:
                    queries = get_schema_version_queries(self.db_type)
                    self.dbh.execute(queries['set'], (version, now))
                    self.conn.commit()
                    return
                except Exception as e:
                    self._log_db_error("Unable to set schema version", e)
                    if is_transient_error(e) and attempt < 2:
                        time.sleep(DB_RETRY_BACKOFF_BASE * (attempt + 1))
                        continue
                    raise OSError("Unable to set schema version") from e

    def create(self) -> None:
        """
        Create the database and initialize schema.
        """
        with self.dbhLock:
            for attempt in range(3):
                try:
                    # Use backend-aware schema creation
                    from spiderfoot.db.__init__ import get_schema_queries
                    for qry in get_schema_queries(self.db_type):
                        try:
                            self.dbh.execute(qry)
                            self.conn.commit()
                        except psycopg2.Error as qe:
                            # PostgreSQL raises UniqueViolation on
                            # CREATE TABLE IF NOT EXISTS when the type
                            # already exists (pg_type_typname_nsp_index).
                            # This is harmless — rollback and continue.
                            err_str = str(qe).lower()
                            if "already exists" in err_str or "unique" in err_str:
                                try:
                                    self.conn.rollback()
                                except Exception:
                                    pass
                                continue
                            raise
                    self.conn.commit()
                    # Cycle 73: attempt trigram index creation (non-fatal)
                    for tqry in self.trigram_schema_queries:
                        try:
                            self.dbh.execute(tqry)
                            self.conn.commit()
                        except Exception as te:
                            log.debug("Trigram index setup skipped: %s", te)
                            try:
                                self.conn.rollback()
                            except Exception:
                                pass
                    if self.get_schema_version() < self.SCHEMA_VERSION:
                        self.set_schema_version(self.SCHEMA_VERSION)
                    self.dbh.execute("SELECT COUNT(*) FROM tbl_event_types")
                    if self.dbh.fetchone()[0] == 0:
                        ph = get_placeholder(self.db_type)
                        upsert = get_upsert_clause(self.db_type, 'tbl_event_types', ['event'], ['event_descr', 'event_raw', 'event_type'])
                        for row in self.eventDetails:
                            event, event_descr, event_raw, event_type = row
                            qry = f"INSERT INTO tbl_event_types (event, event_descr, event_raw, event_type) VALUES ({ph}, {ph}, {ph}, {ph}) {upsert}"
                            params = (event, event_descr, event_raw, event_type)
                            try:
                                self.dbh.execute(qry, params)
                            except Exception as e:
                                self._log_db_error("Failed to insert event type", e)
                                self.conn.rollback()
                                continue
                        self.conn.commit()
                    return
                except psycopg2.Error as e:
                    self._log_db_error("SQL error encountered when setting up database", e)
                    try:
                        self.conn.rollback()
                    except Exception:
                        pass
                    if is_transient_error(e) and attempt < 2:
                        time.sleep(DB_RETRY_BACKOFF_BASE * (attempt + 1))
                        continue
                    raise OSError("SQL error encountered when setting up database") from e

    def close(self) -> None:
        """
        Close the database cursor and return the connection to the pool.

        Raises:
            IOError: Database I/O failed
        """
        with self.dbhLock:
            if self.dbh:
                self.dbh.close()
                self.dbh = None
            if self.conn:
                if getattr(self, '_owns_pooled_conn', False) and hasattr(DbCore, '_pool') and DbCore._pool and not DbCore._pool.closed:
                    try:
                        DbCore._pool.putconn(self.conn)
                    except Exception:
                        self.conn.close()
                else:
                    self.conn.close()
                self.conn = None

    def vacuumDB(self) -> bool:
        """Vacuum the database. Clears unused database file pages.

        Returns:
            bool: success

        Raises:
            IOError: database I/O failed
        """
        with self.dbhLock:
            for attempt in range(3):
                try:
                    self.dbh.execute("VACUUM")
                    self.conn.commit()
                    return True
                except psycopg2.Error as e:
                    self._log_db_error("SQL error encountered when vacuuming the database", e)
                    if is_transient_error(e) and attempt < 2:
                        time.sleep(DB_RETRY_BACKOFF_BASE * (attempt + 1))
                        continue
                    raise OSError("SQL error encountered when vacuuming the database") from e
        return False

    def eventTypes(self) -> list:
        """Get event types.

        Returns:
            list: event types

        Raises:
            IOError: database I/O failed
        """
        qry = "SELECT event_descr, event, event_raw, event_type FROM tbl_event_types"
        with self.dbhLock:
            try:
                self.dbh.execute(qry)
                return self.dbh.fetchall()
            except psycopg2.Error as e:
                raise OSError("SQL error encountered when retrieving event types") from e
