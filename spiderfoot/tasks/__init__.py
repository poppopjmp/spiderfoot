# -*- coding: utf-8 -*-
"""SpiderFoot Celery task modules.

All tasks are auto-discovered by the Celery app.  Each submodule defines
tasks for a specific domain:

    scan        — scan lifecycle (run, abort, rerun)
    report      — PDF / HTML report generation
    export      — data export (JSON, CSV, STIX, SARIF)
    agents      — AI agent execution
    monitor     — subdomain monitoring & change detection
    maintenance — cleanup, health checks, backups
"""
