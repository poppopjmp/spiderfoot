# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:        sfp_xref
# Purpose:     Cross-reference data collected from various sources to identify
#              relationships between entities.
#
# Author:      <van1sh@van1shland.io>
#
# Created:     2025-03-08
# Copyright:   (c) Agostino Panico
# Licence:     MIT
# -------------------------------------------------------------------------------

from spiderfoot import SpiderFootEvent, SpiderFootPlugin


class sfp_xref(SpiderFootPlugin):
    meta = {
        "name": "Cross-Referencer",
        "summary": "Cross-references data collected from various sources to identify relationships between entities.",
        "flags": [],
        "useCases": ["Footprint", "Investigate"],
        "categories": ["Passive"],
        "dataSource": {
            "website": "https://github.com/smicallef/spiderfoot",
            "model": "FREE_NOAUTH_UNLIMITED",
            "description": "SpiderFoot's internal cross-referencing capability to identify relationships between discovered entities.",
        },
    }

    # Default options
    opts = {
        "cross_types": True,  # Cross-reference across different event types
        "same_type": True,  # Cross-reference events of the same type
        "max_correlations": 100,  # Maximum number of correlations to identify per event
    }

    # Option descriptions
    optdescs = {
        "cross_types": "Cross-reference data across different event types.",
        "same_type": "Cross-reference events of the same type.",
        "max_correlations": "Maximum number of correlations to identify per event.",
    }

    # This will be used to track all data collected so far
    eventMap = None
    entityMap = None

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.eventMap = {}  # Maps event types to event data
        self.entityMap = {}  # Maps entities to their attributes and relationships
        self.results = self.tempStorage()

        for opt in list(userOpts.keys()):
            self.opts[opt] = userOpts[opt]

    # What events is this module interested in for input
    def watchedEvents(self):
        return ["*"]  # We want to see everything to build the cross-reference map

    # What events this module produces
    def producedEvents(self):
        return [
            "CROSS_REFERENCE",  # Generic cross-reference relationship
            "CROSS_DOMAIN",  # Domain cross-references
            "CROSS_IP",  # IP cross-references
            "CROSS_EMAIL",  # Email cross-references
            "CROSS_ACCOUNT",  # Account cross-references
            "ENTITY_ASSOCIATION",  # General entity association
        ]

    def handleEvent(self, event):
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data

        # We want to track everything, but not report on everything
        if not self.opts["cross_types"] and not self.opts["same_type"]:
            return

        # Add the data to our internal maps
        if eventName not in self.eventMap:
            self.eventMap[eventName] = []

        # Skip if we've already processed this event data
        if eventData in self.eventMap[eventName] or eventData in self.results:
            return

        # Store the event data
        self.eventMap[eventName].append(eventData)
        self.results[eventData] = True

        # Now let's find cross-references
        correlations = []

        # Cross-reference with the same event type if enabled
        if self.opts["same_type"]:
            # Find other events of the same type that might be related
            for data in self.eventMap.get(eventName, []):
                if data != eventData and self._is_related(eventData, data):
                    correlations.append(
                        {"type": eventName, "data": data,
                            "relationship": "SAME_TYPE"}
                    )

        # Cross-reference with different event types if enabled
        if self.opts["cross_types"]:
            for otherType in self.eventMap:
                if otherType == eventName:
                    continue  # Skip same type as we handled it above

                for data in self.eventMap.get(otherType, []):
                    if self._is_related(eventData, data):
                        correlations.append(
                            {
                                "type": otherType,
                                "data": data,
                                "relationship": "CROSS_TYPE",
                            }
                        )

        # Limit the number of correlations to prevent overwhelming the user
        correlations = correlations[: self.opts["max_correlations"]]

        # Now generate the appropriate events based on the correlations found
        for correlation in correlations:
            corr_type = correlation["type"]
            corr_data = correlation["data"]

            # Determine the appropriate event type based on what we're correlating
            evt_type = "ENTITY_ASSOCIATION"  # Default

            # More specific cross-reference types based on the correlation
            if "DOMAIN" in eventName and "DOMAIN" in corr_type:
                evt_type = "CROSS_DOMAIN"
            elif "IP_ADDRESS" in eventName and "IP_ADDRESS" in corr_type:
                evt_type = "CROSS_IP"
            elif "EMAILADDR" in eventName and "EMAILADDR" in corr_type:
                evt_type = "CROSS_EMAIL"
            elif "ACCOUNT" in eventName or "USERNAME" in eventName:
                evt_type = "CROSS_ACCOUNT"
            else:
                evt_type = "CROSS_REFERENCE"

            # Create a descriptive message about the relationship
            relationship_desc = f"{eventData} is related to {corr_data} ({corr_type})"

            evt = SpiderFootEvent(
                evt_type, relationship_desc, self.__name__, event)
            self.notifyListeners(evt)

    def _is_related(self, data1, data2):
        """
        Determines if two pieces of data are related.
        This is a simple implementation - more sophisticated
        implementations could use string similarity, common tokens, etc.

        Args:
            data1 (str): First data item
            data2 (str): Second data item

        Returns:
            bool: True if the items are related, False otherwise
        """
        # Check for common substrings (minimum 6 chars to avoid false positives)
        min_substr_len = 6

        # Skip short strings
        if len(data1) < min_substr_len or len(data2) < min_substr_len:
            return False

        # Convert both to lowercase for comparison
        d1 = data1.lower()
        d2 = data2.lower()

        # Check if one string contains the other
        if d1 in d2 or d2 in d1:
            return True

        # Check for common substrings of significant length
        for i in range(len(d1) - min_substr_len + 1):
            substr = d1[i: i + min_substr_len]
            if substr in d2:
                return True

        # If we get here, no significant relationship was found
        return False
