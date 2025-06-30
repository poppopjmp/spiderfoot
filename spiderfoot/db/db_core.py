# db_core.py
"""
Core DB connection, locking, schema management, and shared resources for SpiderFootDb.
"""
import threading
import sqlite3
import psycopg2
from pathlib import Path

class DbCore:
    """
    Core database connection and management class for SpiderFootDb.
    """
    # Shared resources
    dbh = None
    conn = None
    dbhLock = threading.RLock()
    # Add schema and event details as class attributes for use in schema creation
    createSchemaQueries = [
        "PRAGMA journal_mode=WAL",
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
            created     INT DEFAULT 0, \
            started     INT DEFAULT 0, \
            ended       INT DEFAULT 0, \
            status      VARCHAR NOT NULL \
        )",
        "CREATE TABLE IF NOT EXISTS tbl_scan_log ( \
            scan_instance_id    VARCHAR NOT NULL REFERENCES tbl_scan_instance(guid), \
            generated           INT NOT NULL, \
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
            generated           INT NOT NULL, \
            confidence          INT NOT NULL DEFAULT 100, \
            visibility          INT NOT NULL DEFAULT 100, \
            risk                INT NOT NULL DEFAULT 0, \
            module              VARCHAR NOT NULL, \
            data                VARCHAR, \
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
        ("whois", "Whois data", 1, "text"),
        ("dns", "DNS resolution", 2, "text"),
        ("http", "HTTP headers", 3, "text"),
        ("ssl", "SSL certificate", 4, "text"),
        ("port", "Open ports", 5, "text"),
        ("vuln", "Vulnerabilities", 6, "text"),
        ("cve", "CVEs", 7, "text"),
        ("asn", "ASN information", 8, "text"),
        ("geo", "Geolocation data", 9, "text"),
        ("email", "Email addresses", 10, "text"),
        ("domain", "Domain names", 11, "text"),
        ("ip", "IP addresses", 12, "text"),
        ("url", "URLs", 13, "text"),
        ("hash", "File hashes", 14, "text"),
        ("mutex", "Mutexes", 15, "text"),
        ("reg", "Registry keys", 16, "text"),
        ("file", "Files", 17, "text"),
        ("process", "Processes", 18, "text"),
        ("service", "Services", 19, "text"),
        ("network", "Network connections", 20, "text"),
        ("os", "Operating system", 21, "text"),
        ("software", "Installed software", 22, "text"),
        ("credential", "Credentials", 23, "text"),
        ("token", "Tokens", 24, "text"),
        ("key", "Encryption keys", 25, "text"),
        ("sensitive", "Sensitive data", 26, "text"),
        ("backup", "Backup files", 27, "text"),
        ("config", "Configuration files", 28, "text"),
        ("log", "Log files", 29, "text"),
        ("monitor", "Monitoring data", 30, "text"),
        ("alert", "Alerts", 31, "text"),
        ("event", "Events", 32, "text"),
        ("incident", "Incidents", 33, "text"),
        ("report", "Reports", 34, "text"),
        ("dashboard", "Dashboards", 35, "text"),
        ("workflow", "Workflows", 36, "text"),
        ("automation", "Automations", 37, "text"),
        ("orchestration", "Orchestrations", 38, "text"),
        ("integration", "Integrations", 39, "text"),
        ("api", "APIs", 40, "text"),
        ("webhook", "Webhooks", 41, "text"),
        ("socket", "Sockets", 42, "text"),
        ("stream", "Streams", 43, "text"),
        ("queue", "Queues", 44, "text"),
        ("topic", "Topics", 45, "text"),
        ("subscription", "Subscriptions", 46, "text"),
        ("notification", "Notifications", 47, "text"),
        ("message", "Messages", 48, "text"),
        ("email_alert", "Email alerts", 49, "text"),
        ("sms_alert", "SMS alerts", 50, "text"),
        ("push_alert", "Push alerts", 51, "text"),
        ("webhook_alert", "Webhook alerts", 52, "text"),
        ("script", "Scripts", 53, "text"),
        ("command", "Commands", 54, "text"),
        ("control", "Control commands", 55, "text"),
        ("data", "Data exports", 56, "text"),
        ("import", "Data imports", 57, "text"),
        ("export", "Data exports", 58, "text"),
        ("sync", "Data synchronization", 59, "text"),
        ("backup_config", "Backup configurations", 60, "text"),
        ("restore_config", "Restore configurations", 61, "text"),
        ("snapshot", "Snapshots", 62, "text"),
        ("clone", "Clones", 63, "text"),
        ("template", "Templates", 64, "text"),
        ("profile", "Profiles", 65, "text"),
        ("role", "Roles", 66, "text"),
        ("permission", "Permissions", 67, "text"),
        ("policy", "Policies", 68, "text"),
        ("audit", "Audit logs", 69, "text"),
        ("access", "Access logs", 70, "text"),
        ("error", "Error logs", 71, "text"),
        ("eventlog", "Event logs", 72, "text"),
        ("system", "System events", 73, "text"),
        ("security", "Security events", 74, "text"),
        ("network_alert", "Network alerts", 75, "text"),
        ("host_alert", "Host alerts", 76, "text"),
        ("service_alert", "Service alerts", 77, "text"),
        ("process_alert", "Process alerts", 78, "text"),
        ("file_alert", "File alerts", 79, "text"),
        ("registry_alert", "Registry alerts", 80, "text"),
        ("mutex_alert", "Mutex alerts", 81, "text"),
        ("credential_alert", "Credential alerts", 82, "text"),
        ("token_alert", "Token alerts", 83, "text"),
        ("key_alert", "Key alerts", 84, "text"),
        ("sensitive_alert", "Sensitive data alerts", 85, "text"),
        ("backup_alert", "Backup alerts", 86, "text"),
        ("config_alert", "Configuration alerts", 87, "text"),
        ("log_alert", "Log alerts", 88, "text"),
        ("monitor_alert", "Monitoring alerts", 89, "text"),
        ("incident_alert", "Incident alerts", 90, "text"),
        ("report_alert", "Report alerts", 91, "text"),
        ("dashboard_alert", "Dashboard alerts", 92, "text"),
        ("workflow_alert", "Workflow alerts", 93, "text"),
        ("automation_alert", "Automation alerts", 94, "text"),
        ("orchestration_alert", "Orchestration alerts", 95, "text"),
        ("integration_alert", "Integration alerts", 96, "text"),
        ("api_alert", "API alerts", 97, "text"),
        ("webhook_alert", "Webhook alerts", 98, "text"),
        ("socket_alert", "Socket alerts", 99, "text"),
        ("stream_alert", "Stream alerts", 100, "text"),
        ("queue_alert", "Queue alerts", 101, "text"),
        ("topic_alert", "Topic alerts", 102, "text"),
        ("subscription_alert", "Subscription alerts", 103, "text"),
        ("notification_alert", "Notifications alerts", 104, "text"),
        ("message_alert", "Message alerts", 105, "text"),
        ("email_alert", "Email alerts", 106, "text"),
        ("sms_alert", "SMS alerts", 107, "text"),
        ("push_alert", "Push alerts", 108, "text"),
        ("webhook_alert", "Webhook alerts", 109, "text"),
        ("script_alert", "Script alerts", 110, "text"),
        ("command_alert", "Command alerts", 111, "text"),
        ("control_alert", "Control alerts", 112, "text"),
        ("data_alert", "Data export alerts", 113, "text"),
        ("import_alert", "Data import alerts", 114, "text"),
        ("export_alert", "Data export alerts", 115, "text"),
        ("sync_alert", "Data synchronization alerts", 116, "text"),
        ("backup_config_alert", "Backup configuration alerts", 117, "text"),
        ("restore_config_alert", "Restore configuration alerts", 118, "text"),
        ("snapshot_alert", "Snapshot alerts", 119, "text"),
        ("clone_alert", "Clone alerts", 120, "text"),
        ("template_alert", "Template alerts", 121, "text"),
        ("profile_alert", "Profile alerts", 122, "text"),
        ("role_alert", "Role alerts", 123, "text"),
        ("permission_alert", "Permission alerts", 124, "text"),
        ("policy_alert", "Policy alerts", 125, "text"),
        ("audit_alert", "Audit log alerts", 126, "text"),
        ("access_alert", "Access log alerts", 127, "text"),
        ("error_alert", "Error log alerts", 128, "text"),
        ("eventlog_alert", "Event log alerts", 129, "text"),
        ("system_alert", "System event alerts", 130, "text"),
        ("security_alert", "Security event alerts", 131, "text"),
        ("network_alert", "Network alert", 132, "text"),
        ("host_alert", "Host alert", 133, "text"),
        ("service_alert", "Service alert", 134, "text"),
        ("process_alert", "Process alert", 135, "text"),
        ("file_alert", "File alert", 136, "text"),
        ("registry_alert", "Registry alert", 137, "text"),
        ("mutex_alert", "Mutex alert", 138, "text"),
        ("credential_alert", "Credential alert", 139, "text"),
        ("token_alert", "Token alert", 140, "text"),
        ("key_alert", "Key alert", 141, "text"),
        ("sensitive_alert", "Sensitive data alert", 142, "text"),
        ("backup_alert", "Backup alert", 143, "text"),
        ("config_alert", "Configuration alert", 144, "text"),
        ("log_alert", "Log alert", 145, "text"),
        ("monitor_alert", "Monitoring alert", 146, "text"),
        ("incident_alert", "Incident alert", 147, "text"),
        ("report_alert", "Report alert", 148, "text"),
        ("dashboard_alert", "Dashboard alert", 149, "text"),
        ("workflow_alert", "Workflow alert", 150, "text"),
        ("automation_alert", "Automation alert", 151, "text"),
        ("orchestration_alert", "Orchestration alert", 152, "text"),
        ("integration_alert", "Integration alert", 153, "text"),
        ("api_alert", "API alert", 154, "text"),
        ("webhook_alert", "Webhook alert", 155, "text"),
        ("socket_alert", "Socket alert", 156, "text"),
        ("stream_alert", "Stream alert", 157, "text"),
        ("queue_alert", "Queue alert", 158, "text"),
        ("topic_alert", "Topic alert", 159, "text"),
        ("subscription_alert", "Subscription alert", 160, "text"),
        ("notification_alert", "Notification alert", 161, "text"),
        ("message_alert", "Message alert", 162, "text"),
        ("email_alert", "Email alert", 163, "text"),
        ("sms_alert", "SMS alert", 164, "text"),
        ("push_alert", "Push alert", 165, "text"),
        ("webhook_alert", "Webhook alert", 166, "text"),
        ("script_alert", "Script alert", 167, "text"),
        ("command_alert", "Command alert", 168, "text"),
        ("control_alert", "Control alert", 169, "text"),
        ("data_alert", "Data export alert", 170, "text"),
        ("import_alert", "Data import alert", 171, "text"),
        ("export_alert", "Data export alert", 172, "text"),
        ("sync_alert", "Data synchronization alert", 173, "text"),
        ("backup_config_alert", "Backup configuration alert", 174, "text"),
        ("restore_config_alert", "Restore configuration alert", 175, "text"),
        ("snapshot_alert", "Snapshot alert", 176, "text"),
        ("clone_alert", "Clone alert", 177, "text"),
        ("template_alert", "Template alert", 178, "text"),
        ("profile_alert", "Profile alert", 179, "text"),
        ("role_alert", "Role alert", 180, "text"),
        ("permission_alert", "Permission alert", 181, "text"),
        ("policy_alert", "Policy alert", 182, "text"),
        ("audit_alert", "Audit log alert", 183, "text"),
        ("access_alert", "Access log alert", 184, "text"),
        ("error_alert", "Error log alert", 185, "text"),
        ("eventlog_alert", "Event log alert", 186, "text"),
        ("system_alert", "System event alert", 187, "text"),
        ("security_alert", "Security event alert", 188, "text"),
        ("network_alert", "Network alert", 189, "text"),
        ("host_alert", "Host alert", 190, "text"),
        ("service_alert", "Service alert", 191, "text"),
        ("process_alert", "Process alert", 192, "text"),
        ("file_alert", "File alert", 193, "text"),
        ("registry_alert", "Registry alert", 194, "text"),
        ("mutex_alert", "Mutex alert", 195, "text"),
        ("credential_alert", "Credential alert", 196, "text"),
        ("token_alert", "Token alert", 197, "text"),
        ("key_alert", "Key alert", 198, "text"),
        ("sensitive_alert", "Sensitive data alert", 199, "text"),
        ("backup_alert", "Backup alert", 200, "text"),
        ("config_alert", "Configuration alert", 201, "text"),
        ("log_alert", "Log alert", 202, "text"),
        ("monitor_alert", "Monitoring alert", 203, "text"),
        ("incident_alert", "Incident alert", 204, "text"),
        ("report_alert", "Report alert", 205, "text"),
        ("dashboard_alert", "Dashboard alert", 206, "text"),
        ("workflow_alert", "Workflow alert", 207, "text"),
        ("automation_alert", "Automation alert", 208, "text"),
        ("orchestration_alert", "Orchestration alert", 209, "text"),
        ("integration_alert", "Integration alert", 210, "text"),
        ("api_alert", "API alert", 211, "text"),
        ("webhook_alert", "Webhook alert", 212, "text"),
        ("socket_alert", "Socket alert", 213, "text"),
        ("stream_alert", "Stream alert", 214, "text"),
        ("queue_alert", "Queue alert", 215, "text"),
        ("topic_alert", "Topic alert", 216, "text"),
        ("subscription_alert", "Subscription alert", 217, "text"),
        ("notification_alert", "Notification alert", 218, "text"),
        ("message_alert", "Message alert", 219, "text"),
        ("email_alert", "Email alert", 220, "text"),
        ("sms_alert", "SMS alert", 221, "text"),
        ("push_alert", "Push alert", 222, "text"),
        ("webhook_alert", "Webhook alert", 223, "text"),
        ("script_alert", "Script alert", 224, "text"),
        ("command_alert", "Command alert", 225, "text"),
        ("control_alert", "Control alert", 226, "text"),
        ("data_alert", "Data export alert", 227, "text"),
        ("import_alert", "Data import alert", 228, "text"),
        ("export_alert", "Data export alert", 229, "text"),
        ("sync_alert", "Data synchronization alert", 230, "text"),
        ("backup_config_alert", "Backup configuration alert", 231, "text"),
        ("restore_config_alert", "Restore configuration alert", 232, "text"),
        ("snapshot_alert", "Snapshot alert", 233, "text"),
        ("clone_alert", "Clone alert", 234, "text"),
        ("template_alert", "Template alert", 235, "text"),
        ("profile_alert", "Profile alert", 236, "text"),
        ("role_alert", "Role alert", 237, "text"),
        ("permission_alert", "Permission alert", 238, "text"),
        ("policy_alert", "Policy alert", 239, "text"),
        ("audit_alert", "Audit log alert", 240, "text"),
        ("access_alert", "Access log alert", 241, "text"),
        ("error_alert", "Error log alert", 242, "text"),
        ("eventlog_alert", "Event log alert", 243, "text"),
        ("system_alert", "System event alert", 244, "text"),
        ("security_alert", "Security event alert", 245, "text"),
        ("network_alert", "Network alert", 246, "text"),
        ("host_alert", "Host alert", 247, "text"),
        ("service_alert", "Service alert", 248, "text"),
        ("process_alert", "Process alert", 249, "text"),
        ("file_alert", "File alert", 250, "text"),
        ("registry_alert", "Registry alert", 251, "text"),
        ("mutex_alert", "Mutex alert", 252, "text"),
        ("credential_alert", "Credential alert", 253, "text"),
        ("token_alert", "Token alert", 254, "text"),
        ("key_alert", "Key alert", 255, "text"),
        ("sensitive_alert", "Sensitive data alert", 256, "text"),
        ("backup_alert", "Backup alert", 257, "text"),
        ("config_alert", "Configuration alert", 258, "text"),
        ("log_alert", "Log alert", 259, "text"),
        ("monitor_alert", "Monitoring alert", 260, "text"),
        ("incident_alert", "Incident alert", 261, "text"),
        ("report_alert", "Report alert", 262, "text"),
        ("dashboard_alert", "Dashboard alert", 263, "text"),
        ("workflow_alert", "Workflow alert", 264, "text"),
        ("automation_alert", "Automation alert", 265, "text"),
        ("orchestration_alert", "Orchestration alert", 266, "text"),
        ("integration_alert", "Integration alert", 267, "text"),
        ("api_alert", "API alert", 268, "text"),
        ("webhook_alert", "Webhook alert", 269, "text"),
        ("socket_alert", "Socket alert", 270, "text"),
        ("stream_alert", "Stream alert", 271, "text"),
        ("queue_alert", "Queue alert", 272, "text"),
        ("topic_alert", "Topic alert", 273, "text"),
        ("subscription_alert", "Subscription alert", 274, "text"),
        ("notification_alert", "Notification alert", 275, "text"),
        ("message_alert", "Message alert", 276, "text"),
        ("email_alert", "Email alert", 277, "text"),
        ("sms_alert", "SMS alert", 278, "text"),
        ("push_alert", "Push alert", 279, "text"),
        ("webhook_alert", "Webhook alert", 280, "text"),
        ("script_alert", "Script alert", 281, "text"),
        ("command_alert", "Command alert", 282, "text"),
        ("control_alert", "Control alert", 283, "text"),
        ("data_alert", "Data export alert", 284, "text"),
        ("import_alert", "Data import alert", 285, "text"),
        ("export_alert", "Data export alert", 286, "text"),
        ("sync_alert", "Data synchronization alert", 287, "text"),
        ("backup_config_alert", "Backup configuration alert", 288, "text"),
        ("restore_config_alert", "Restore configuration alert", 289, "text"),
        ("snapshot_alert", "Snapshot alert", 290, "text"),
        ("clone_alert", "Clone alert", 291, "text"),
        ("template_alert", "Template alert", 292, "text"),
        ("profile_alert", "Profile alert", 293, "text"),
        ("role_alert", "Role alert", 294, "text"),
        ("permission_alert", "Permission alert", 295, "text"),
        ("policy_alert", "Policy alert", 296, "text"),
        ("audit_alert", "Audit log alert", 297, "text"),
        ("access_alert", "Access log alert", 298, "text"),
        ("error_alert", "Error log alert", 299, "text"),
        ("eventlog_alert", "Event log alert", 300, "text"),
        ("system_alert", "System event alert", 301, "text"),
        ("security_alert", "Security event alert", 302, "text"),
        ("network_alert", "Network alert", 303, "text"),
        ("host_alert", "Host alert", 304, "text"),
        ("service_alert", "Service alert", 305, "text"),
        ("process_alert", "Process alert", 306, "text"),
        ("file_alert", "File alert", 307, "text"),
        ("registry_alert", "Registry alert", 308, "text"),
        ("mutex_alert", "Mutex alert", 309, "text"),
        ("credential_alert", "Credential alert", 310, "text"),
        ("token_alert", "Token alert", 311, "text"),
        ("key_alert", "Key alert", 312, "text"),
        ("sensitive_alert", "Sensitive data alert", 313, "text"),
        ("backup_alert", "Backup alert", 314, "text"),
        ("config_alert", "Configuration alert", 315, "text"),
        ("log_alert", "Log alert", 316, "text"),
        ("monitor_alert", "Monitoring alert", 317, "text"),
        ("incident_alert", "Incident alert", 318, "text"),
        ("report_alert", "Report alert", 319, "text"),
        ("dashboard_alert", "Dashboard alert", 320, "text"),
        ("workflow_alert", "Workflow alert", 321, "text"),
        ("automation_alert", "Automation alert", 322, "text"),
        ("orchestration_alert", "Orchestration alert", 323, "text"),
        ("integration_alert", "Integration alert", 324, "text"),
        ("api_alert", "API alert", 325, "text"),
        ("webhook_alert", "Webhook alert", 326, "text"),
        ("socket_alert", "Socket alert", 327, "text"),
        ("stream_alert", "Stream alert", 328, "text"),
        ("queue_alert", "Queue alert", 329, "text"),
        ("topic_alert", "Topic alert", 330, "text"),
        ("subscription_alert", "Subscription alert", 331, "text"),
        ("notification_alert", "Notification alert", 332, "text"),
        ("message_alert", "Message alert", 333, "text"),
        ("email_alert", "Email alert", 334, "text"),
        ("sms_alert", "SMS alert", 335, "text"),
        ("push_alert", "Push alert", 336, "text"),
        ("webhook_alert", "Webhook alert", 337, "text"),
        ("script_alert", "Script alert", 338, "text"),
        ("command_alert", "Command alert", 339, "text"),
        ("control_alert", "Control alert", 340, "text"),
        ("data_alert", "Data export alert", 341, "text"),
        ("import_alert", "Data import alert", 342, "text"),
        ("export_alert", "Data export alert", 343, "text"),
        ("sync_alert", "Data synchronization alert", 344, "text"),
        ("backup_config_alert", "Backup configuration alert", 345, "text"),
        ("restore_config_alert", "Restore configuration alert", 346, "text"),
        ("snapshot_alert", "Snapshot alert", 347, "text"),
        ("clone_alert", "Clone alert", 348, "text"),
        ("template_alert", "Template alert", 349, "text"),
        ("profile_alert", "Profile alert", 350, "text"),
        ("role_alert", "Role alert", 351, "text"),
        ("permission_alert", "Permission alert", 352, "text"),
        ("policy_alert", "Policy alert", 353, "text"),
        ("audit_alert", "Audit log alert", 354, "text"),
        ("access_alert", "Access log alert", 355, "text"),
        ("error_alert", "Error log alert", 356, "text"),
        ("eventlog_alert", "Event log alert", 357, "text"),
        ("system_alert", "System event alert", 358, "text"),
        ("security_alert", "Security event alert", 359, "text"),
        ("network_alert", "Network alert", 360, "text"),
        ("host_alert", "Host alert", 361, "text"),
        ("service_alert", "Service alert", 362, "text"),
        ("process_alert", "Process alert", 363, "text"),
        ("file_alert", "File alert", 364, "text"),
        ("registry_alert", "Registry alert", 365, "text"),
        ("mutex_alert", "Mutex alert", 366, "text"),
        ("credential_alert", "Credential alert", 367, "text"),
        ("token_alert", "Token alert", 368, "text"),
        ("key_alert", "Key alert", 369, "text"),
        ("sensitive_alert", "Sensitive data alert", 370, "text"),
        ("backup_alert", "Backup alert", 371, "text"),
        ("config_alert", "Configuration alert", 372, "text"),
        ("log_alert", "Log alert", 373, "text"),
        ("monitor_alert", "Monitoring alert", 374, "text"),
        ("incident_alert", "Incident alert", 375, "text"),
        ("report_alert", "Report alert", 376, "text"),
        ("dashboard_alert", "Dashboard alert", 377, "text"),
        ("workflow_alert", "Workflow alert", 378, "text"),
        ("automation_alert", "Automation alert", 379, "text"),
        ("orchestration_alert", "Orchestration alert", 380, "text"),
        ("integration_alert", "Integration alert", 381, "text"),
        ("api_alert", "API alert", 382, "text"),
        ("webhook_alert", "Webhook alert", 383, "text"),
        ("socket_alert", "Socket alert", 384, "text"),
        ("stream_alert", "Stream alert", 385, "text"),
        ("queue_alert", "Queue alert", 386, "text"),
        ("topic_alert", "Topic alert", 387, "text"),
        ("subscription_alert", "Subscription alert", 388, "text"),
        ("notification_alert", "Notification alert", 389, "text"),
        ("message_alert", "Message alert", 390, "text"),
        ("email_alert", "Email alert", 391, "text"),
        ("sms_alert", "SMS alert", 392, "text"),
        ("push_alert", "Push alert", 393, "text"),
        ("webhook_alert", "Webhook alert", 394, "text"),
        ("script_alert", "Script alert", 395, "text"),
        ("command_alert", "Command alert", 396, "text"),
        ("control_alert", "Control alert", 397, "text"),
        ("data_alert", "Data export alert", 398, "text"),
        ("import_alert", "Data import alert", 399, "text"),
        ("export_alert", "Data export alert", 400, "text"),
        ("sync_alert", "Data synchronization alert", 401, "text"),
        ("backup_config_alert", "Backup configuration alert", 402, "text"),
        ("restore_config_alert", "Restore configuration alert", 403, "text"),
        ("snapshot_alert", "Snapshot alert", 404, "text"),
        ("clone_alert", "Clone alert", 405, "text"),
        ("template_alert", "Template alert", 406, "text"),
        ("profile_alert", "Profile alert", 407, "text"),
        ("role_alert", "Role alert", 408, "text"),
        ("permission_alert", "Permission alert", 409, "text"),
        ("policy_alert", "Policy alert", 410, "text"),
        ("audit_alert", "Audit log alert", 411, "text"),
        ("access_alert", "Access log alert", 412, "text"),
        ("error_alert", "Error log alert", 413, "text"),
        ("eventlog_alert", "Event log alert", 414, "text"),
        ("system_alert", "System event alert", 415, "text"),
        ("security_alert", "Security event alert", 416, "text"),
        ("network_alert", "Network alert", 417, "text"),
        ("host_alert", "Host alert", 418, "text"),
        ("service_alert", "Service alert", 419, "text"),
        ("process_alert", "Process alert", 420, "text"),
        ("file_alert", "File alert", 421, "text"),
        ("registry_alert", "Registry alert", 422, "text"),
        ("mutex_alert", "Mutex alert", 423, "text"),
        ("credential_alert", "Credential alert", 424, "text"),
        ("token_alert", "Token alert", 425, "text"),
        ("key_alert", "Key alert", 426, "text"),
        ("sensitive_alert", "Sensitive data alert", 427, "text"),
        ("backup_alert", "Backup alert", 428, "text"),
        ("config_alert", "Configuration alert", 429, "text"),
        ("log_alert", "Log alert", 430, "text"),
        ("monitor_alert", "Monitoring alert", 431, "text"),
        ("incident_alert", "Incident alert", 432, "text"),
        ("report_alert", "Report alert", 433, "text"),
        ("dashboard_alert", "Dashboard alert", 434, "text"),
        ("workflow_alert", "Workflow alert", 435, "text"),
        ("automation_alert", "Automation alert", 436, "text"),
        ("orchestration_alert", "Orchestration alert", 437, "text"),
        ("integration_alert", "Integration alert", 438, "text"),
        ("api_alert", "API alert", 439, "text"),
        ("webhook_alert", "Webhook alert", 440, "text"),
        ("socket_alert", "Socket alert", 441, "text"),
        ("stream_alert", "Stream alert", 442, "text"),
        ("queue_alert", "Queue alert", 443, "text"),
        ("topic_alert", "Topic alert", 444, "text"),
        ("subscription_alert", "Subscription alert", 445, "text"),
        ("notification_alert", "Notification alert", 446, "text"),
        ("message_alert", "Message alert", 447, "text"),
        ("email_alert", "Email alert", 448, "text"),
        ("sms_alert", "SMS alert", 449, "text"),
        ("push_alert", "Push alert", 450, "text"),
        ("webhook_alert", "Webhook alert", 451, "text"),
        ("script_alert", "Script alert", 452, "text"),
        ("command_alert", "Command alert", 453, "text"),
        ("control_alert", "Control alert", 454, "text"),
        ("data_alert", "Data export alert", 455, "text"),
        ("import_alert", "Data import alert", 456, "text"),
        ("export_alert", "Data export alert", 457, "text"),
        ("sync_alert", "Data synchronization alert", 458, "text"),
        ("backup_config_alert", "Backup configuration alert", 459, "text"),
        ("restore_config_alert", "Restore configuration alert", 460, "text"),
        ("snapshot_alert", "Snapshot alert", 461, "text"),
        ("clone_alert", "Clone alert", 462, "text"),
        ("template_alert", "Template alert", 463, "text"),
        ("profile_alert", "Profile alert", 464, "text"),
        ("role_alert", "Role alert", 465, "text"),
        ("permission_alert", "Permission alert", 466, "text"),
        ("policy_alert", "Policy alert", 467, "text"),
        ("audit_alert", "Audit log alert", 468, "text"),
        ("access_alert", "Access log alert", 469, "text"),
        ("error_alert", "Error log alert", 470, "text"),
        ("eventlog_alert", "Event log alert", 471, "text"),
        ("system_alert", "System event alert", 472, "text"),
        ("security_alert", "Security event alert", 473, "text"),
        ("network_alert", "Network alert", 474, "text"),
        ("host_alert", "Host alert", 475, "text"),
        ("service_alert", "Service alert", 476, "text"),
        ("process_alert", "Process alert", 477, "text"),
        ("file_alert", "File alert", 478, "text"),
        ("registry_alert", "Registry alert", 479, "text"),
        ("mutex_alert", "Mutex alert", 480, "text"),
        ("credential_alert", "Credential alert", 481, "text"),
        ("token_alert", "Token alert", 482, "text"),
        ("key_alert", "Key alert", 483, "text"),
        ("sensitive_alert", "Sensitive data alert", 484, "text"),
        ("backup_alert", "Backup alert", 485, "text"),
        ("config_alert", "Configuration alert", 486, "text"),
        ("log_alert", "Log alert", 487, "text"),
        ("monitor_alert", "Monitoring alert", 488, "text"),
        ("incident_alert", "Incident alert", 489, "text"),
        ("report_alert", "Report alert", 490, "text"),
        ("dashboard_alert", "Dashboard alert", 491, "text"),
        ("workflow_alert", "Workflow alert", 492, "text"),
        ("automation_alert", "Automation alert", 493, "text"),
        ("orchestration_alert", "Orchestration alert", 494, "text"),
        ("integration_alert", "Integration alert", 495, "text"),
        ("api_alert", "API alert", 496, "text"),
        ("webhook_alert", "Webhook alert", 497, "text"),
        ("socket_alert", "Socket alert", 498, "text"),
        ("stream_alert", "Stream alert", 499, "text"),
        ("queue_alert", "Queue alert", 500, "text"),
        ("topic_alert", "Topic alert", 501, "text"),
        ("subscription_alert", "Subscription alert", 502, "text"),
        ("notification_alert", "Notification alert", 503, "text"),
        ("message_alert", "Message alert", 504, "text"),
        ("email_alert", "Email alert", 505, "text"),
        ("sms_alert", "SMS alert", 506, "text"),
        ("push_alert", "Push alert", 507, "text"),
        ("webhook_alert", "Webhook alert", 508, "text"),
        ("script_alert", "Script alert", 509, "text"),
        ("command_alert", "Command alert", 510, "text"),
        ("control_alert", "Control alert", 511, "text")
    ]

    def __init__(self, opts: dict, init: bool = False) -> None:
        """
        Initialize the DbCore object.

        Args:
            opts (dict): Options for the database connection.
            init (bool, optional): Flag to initialize the database. Defaults to False.
        """
        if not isinstance(opts, dict):
            raise TypeError(f"opts is {type(opts)}; expected dict()")
        if not opts:
            raise ValueError("opts is empty")
        if '__database' not in opts:
            raise ValueError("__database key missing in opts")
        if '__dbtype' not in opts:
            opts['__dbtype'] = 'sqlite'
        self.db_type = opts['__dbtype']
        database_path = opts['__database']
        if self.db_type == 'sqlite':
            Path(database_path).parent.mkdir(exist_ok=True, parents=True)
            try:
                dbh = sqlite3.connect(database_path)
            except Exception as e:
                raise IOError(f"Error connecting to internal database {database_path}") from e
            if dbh is None:
                raise IOError(f"Could not connect to internal database, and could not create {database_path}") from None
            dbh.text_factory = str
            self.conn = dbh
            self.dbh = dbh.cursor()
            def __dbregex__(qry: str, data: str) -> bool:
                import re
                return re.search(qry, data) is not None
            self.conn.create_function("REGEXP", 2, __dbregex__)
            with self.dbhLock:
                # Always create schema first
                try:
                    self.create()
                except Exception as e:
                    raise IOError("Tried to set up the SpiderFoot database schema, but failed") from e
                # Only populate event types if the table is empty
                self.dbh.execute("SELECT COUNT(*) FROM tbl_event_types")
                if self.dbh.fetchone()[0] == 0:
                    for row in self.eventDetails:
                        event = row[0]
                        event_descr = row[1]
                        event_raw = row[2]
                        event_type = row[3]
                        qry = "INSERT OR IGNORE INTO tbl_event_types (event, event_descr, event_raw, event_type) VALUES (?, ?, ?, ?)"
                        try:
                            self.dbh.execute(qry, (
                                event, event_descr, event_raw, event_type
                            ))
                        except Exception:
                            continue
                    self.conn.commit()
        elif self.db_type == 'postgresql':
            try:
                import psycopg2.extras
                self.conn = psycopg2.connect(database_path)
                self.dbh = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            except Exception as e:
                raise IOError(f"Error connecting to PostgreSQL database {database_path}") from e
            with self.dbhLock:
                # Always create schema first
                try:
                    self.create()
                except Exception as e:
                    raise IOError("Tried to set up the SpiderFoot database schema, but failed") from e
                self.dbh.execute("SELECT COUNT(*) FROM tbl_event_types")
                if self.dbh.fetchone()[0] == 0:
                    for row in self.eventDetails:
                        event = row[0]
                        event_descr = row[1]
                        event_raw = row[2]
                        event_type = row[3]
                        qry = "INSERT INTO tbl_event_types (event, event_descr, event_raw, event_type) VALUES (%s, %s, %s, %s) ON CONFLICT (event) DO NOTHING"
                        try:
                            self.dbh.execute(qry, (
                                event, event_descr, event_raw, event_type
                            ))
                        except Exception:
                            continue
                    self.conn.commit()
        else:
            raise ValueError(f"Unsupported database type: {self.db_type}")

    def create(self) -> None:
        """
        Create the database and initialize schema.

        Raises:
            IOError: Database I/O failed
        """
        with self.dbhLock:
            try:
                if self.db_type == 'sqlite':
                    for qry in self.createSchemaQueries:
                        self.dbh.execute(qry)
                    self.conn.commit()
                    # Only insert event types if the table is empty
                    self.dbh.execute("SELECT COUNT(*) FROM tbl_event_types")
                    if self.dbh.fetchone()[0] == 0:
                        for row in self.eventDetails:
                            event, event_descr, event_raw, event_type = row
                            qry = "INSERT OR IGNORE INTO tbl_event_types (event, event_descr, event_raw, event_type) VALUES (?, ?, ?, ?)"
                            params = (event, event_descr, event_raw, event_type)
                            self.dbh.execute(qry, params)
                        self.conn.commit()
                elif self.db_type == 'postgresql':
                    for qry in self.createPostgreSQLSchemaQueries:
                        self.dbh.execute(qry)
                    self.conn.commit()
                    self.dbh.execute("SELECT COUNT(*) FROM tbl_event_types")
                    if self.dbh.fetchone()[0] == 0:
                        for row in self.eventDetails:
                            event, event_descr, event_raw, event_type = row
                            qry = "INSERT INTO tbl_event_types (event, event_descr, event_raw, event_type) VALUES (%s, %s, %s, %s) ON CONFLICT (event) DO NOTHING"
                            params = (event, event_descr, event_raw, event_type)
                            self.dbh.execute(qry, params)
                        self.conn.commit()
            except (sqlite3.Error, psycopg2.Error) as e:
                raise IOError("SQL error encountered when setting up database") from e

    def close(self) -> None:
        """
        Close the database connection.

        Raises:
            IOError: Database I/O failed
        """
        with self.dbhLock:
            if self.dbh:
                self.dbh.close()
                self.dbh = None
            if self.conn:
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
            try:
                if ((self.db_type == 'sqlite') or (self.db_type == 'postgresql')):
                    self.dbh.execute("VACUUM")
                self.conn.commit()
                return True
            except (sqlite3.Error, psycopg2.Error) as e:
                raise IOError("SQL error encountered when vacuuming the database") from e
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
            except (sqlite3.Error, psycopg2.Error) as e:
                raise IOError("SQL error encountered when retrieving event types") from e
