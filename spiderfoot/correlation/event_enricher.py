# -*- coding: utf-8 -*-
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
import logging

class EventEnricher:
    def __init__(self, dbh):
        self.log = logging.getLogger("spiderfoot.correlation.enricher")
        self.dbh = dbh

    def enrich_sources(self, scan_id, events):
        # Example: Add source info to each event
        for event in events:
            event_hash = event.get('hash', event.get('id', ''))
            event['sources'] = self.dbh.get_sources(scan_id, event_hash)
        return events

    def enrich_children(self, scan_id, events):
        # Example: Add child info to each event
        for event in events:
            event['children'] = self.dbh.get_children(scan_id, event['id'])
        return events

    def enrich_entities(self, scan_id, events):
        # Example: Add entity info to each event
        for event in events:
            event_hash = event.get('hash', event.get('id', ''))
            event['entities'] = self.dbh.get_entities(scan_id, event_hash)
        return events
