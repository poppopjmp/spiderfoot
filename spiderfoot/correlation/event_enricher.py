# -------------------------------------------------------------------------------
# Name:         Modular SpiderFoot Correlation Engine
# Purpose:      Common functions for enriching events with contextual information.
#
# Author:      Agostino Panico @poppopjmp
#
# Created:     30/06/2025
# Copyright:   (c) Agostino Panico 2025
# Licence:     MIT
# -------------------------------------------------------------------------------
from __future__ import annotations

"""Enriches scan events with source, child, and summary metadata for correlation."""

import logging
from typing import Any

class EventEnricher:
    """Enrich scan events with source, child, and summary metadata.

    Used by the correlation pipeline to attach additional context
    (source modules, child events) to raw scan results before
    correlation rules are evaluated.
    """

    def __init__(self, dbh: Any) -> None:
        """Initialize the event enricher with a database handle."""
        self.log = logging.getLogger("spiderfoot.correlation.enricher")
        self.dbh = dbh

    def enrich_sources(self, scan_id: str, events: list) -> list:
        """Attach source module information to each event."""
        # Example: Add source info to each event
        for event in events:
            event_hash = event.get('hash', event.get('id', ''))
            event['sources'] = self.dbh.get_sources(scan_id, event_hash)
        return events

    def enrich_children(self, scan_id: str, events: list) -> list:
        """Attach child event information to each event."""
        # Example: Add child info to each event
        for event in events:
            event['children'] = self.dbh.get_children(scan_id, event['id'])
        return events

    def enrich_entities(self, scan_id: str, events: list) -> list:
        """Attach entity summary information to each event."""
        # Example: Add entity info to each event
        for event in events:
            event_hash = event.get('hash', event.get('id', ''))
            event['entities'] = self.dbh.get_entities(scan_id, event_hash)
        return events
