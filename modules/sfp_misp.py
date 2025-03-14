# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         sfp_misp
# Purpose:      SpiderFoot plug-in for creating MISP compatible output
#
# Author:       <your name>
#
# Created:      <date>
# Copyright:    (c) <your name>
# Licence:      MIT
# -------------------------------------------------------------------------------

import json
import time
from typing import Dict, List, Any

from spiderfoot import SpiderFootEvent, SpiderFootPlugin
from spiderfoot.misp_integration import MispEvent, MispObject, MispAttribute


class sfp_misp(SpiderFootPlugin):
    """MISP Integration:
    Generates MISP-compatible output from SpiderFoot scan results.
    """

    meta = {
        'name': "MISP Integration",
        'summary': "Generates MISP-compatible output from SpiderFoot scan results.",
        'flags': ["slow"],
        'useCases': ["Threat Intel"],
        'categories': ["Reputation Systems"],
        'dataSource': {
            'website': "https://www.misp-project.org/",
            'model': "FREE_OPEN_SOURCE",
            'description': "MISP (Malware Information Sharing Platform) is an open-source threat intelligence platform."
        }
    }

    # Default options
    opts = {
        'misp_url': '',
        'misp_key': '',
        'create_misp_event': False,
        'create_misp_objects': True,
        'tag_tlp': 'tlp:amber',
        'confidence_threshold': 50,
        'enable_auto_publishing': False
    }

    # Option descriptions
    optdescs = {
        'misp_url': "MISP URL for direct publishing (optional)",
        'misp_key': "MISP API key for direct publishing (optional)",
        'create_misp_event': "Create a MISP event from the scan",
        'create_misp_objects': "Create MISP objects from SpiderFoot events",
        'tag_tlp': "TLP tag to apply to MISP events",
        'confidence_threshold': "Minimum confidence score (0-100) for including events",
        'enable_auto_publishing': "Automatically publish events to MISP"
    }

    # Required for proper setup
    results = None
    errorState = False
    misp_event = None
    scan_object_count = 0

    def setup(self, sfc, userOpts=dict()):
        """Set up the module.

        Args:
            sfc (SpiderFoot): SpiderFoot object
            userOpts (dict): User-defined options
        """
        self.sf = sfc
        self.results = self.tempStorage()

        # Initialize MISP integration
        self.misp_integration = self.sf._dbh and self.sf.get_misp_integration(
            self.sf._dbh)

        # Process user options
        for opt in list(userOpts.keys()):
            self.opts[opt] = userOpts[opt]

        # Create MISP event for this scan
        if self.opts['create_misp_event']:
            self._create_misp_event()

    def _create_misp_event(self):
        """Create a MISP event for this scan."""
        if not self.misp_integration:
            self.sf.error("MISP integration not available")
            return

        scan_info = self.sf._dbh.scanInstanceGet(self.getScanId())
        if not scan_info:
            self.sf.error(f"Could not find scan {self.getScanId()}")
            return

        scan_name = scan_info[0]
        scan_target = scan_info[1]

        # Initialize MISP event
        self.misp_event = MispEvent(
            info=f"SpiderFoot Scan: {scan_name}",
            threat_level_id=4,  # Undefined
            analysis=0,  # Initial
            distribution=0,  # Your organization only
            timestamp=int(time.time())
        )

        # Add TLP tag
        if self.opts['tag_tlp']:
            self.misp_event.add_tag(self.opts['tag_tlp'])

        # Add basic target attribute
        if "." in scan_target:
            attr_type = "domain" if scan_target.count(".") == 1 else "hostname"
        elif scan_target.count(":") >= 2:
            attr_type = "ip-dst" if "://" not in scan_target else "url"
        else:
            attr_type = "text"

        self.misp_event.add_attribute(
            MispAttribute(
                type=attr_type,
                value=scan_target,
                category="Network activity",
                to_ids=False,
                comment="SpiderFoot scan target"
            )
        )

    def watchedEvents(self) -> List[str]:
        """Events this module watches for.

        Returns:
            list: Event types to watch for
        """
        return ["*"]

    def producedEvents(self) -> List[str]:
        """Events produced by this module.

        Returns:
            list: Event types produced
        """
        return []

    def handleEvent(self, sfEvent):
        """Handle events and convert to MISP format.

        Args:
            sfEvent (SpiderFootEvent): SpiderFoot event
        """
        eventName = sfEvent.eventType

        # Skip internal events and events with low confidence
        if eventName == "ROOT" or sfEvent.confidence < self.opts['confidence_threshold']:
            return

        # Skip if no MISP integration available
        if not self.misp_integration:
            return

        # Convert SF event to MISP attribute
        misp_attribute = self.sf.convert_sf_event_to_misp_attribute(sfEvent)

        # Add to MISP event if we're creating one
        if self.misp_event and self.opts['create_misp_event']:
            if self.opts['create_misp_objects']:
                # Group by type into objects
                obj_name = f"sf-{eventName.lower().replace('_', '-')}"
                obj = MispObject(
                    name=obj_name,
                    description=f"SpiderFoot {eventName} findings",
                    timestamp=int(sfEvent.generated)
                )
                obj.add_attribute(misp_attribute)
                self.misp_event.add_object(obj)
                self.scan_object_count += 1
            else:
                # Add attributes directly to event
                self.misp_event.add_attribute(misp_attribute)

        # Store tags in database
        if hasattr(sfEvent, 'tags') and sfEvent.tags:
            for tag in sfEvent.tags:
                self.sf._dbh.eventAddTag(self.getScanId(), sfEvent.hash, tag)

    def finish(self):
        """Finalize processing and export MISP data."""
        if not self.misp_event:
            return

        # Export the MISP event to JSON
        misp_json = self.sf.export_misp_event(self.misp_event, "json")

        # Log some information about what we created
        self.sf.info(
            f"Created MISP event with {len(self.misp_event.attributes)} attributes and {len(self.misp_event.objects)} objects")

        # If direct publishing is configured, publish to MISP
        if self.opts['enable_auto_publishing'] and self.opts['misp_url'] and self.opts['misp_key']:
            self._publish_to_misp()

    def _publish_to_misp(self):
        """Publish the event to a MISP instance."""
        try:
            from pymisp import PyMISP, MISPEvent

            # Convert our MISP event to PyMISP format
            misp_json = self.sf.export_misp_event(self.misp_event, "json")
            pymisp_event = MISPEvent()
            pymisp_event.from_dict(**json.loads(misp_json))

            # Connect to MISP
            misp = PyMISP(self.opts['misp_url'], self.opts['misp_key'], False)

            # Add event to MISP
            response = misp.add_event(pymisp_event)

            if 'errors' in response:
                self.sf.error(
                    f"Error publishing to MISP: {response['errors']}")
            else:
                self.sf.info(
                    f"Successfully published event to MISP with ID: {response['Event']['id']}")
        except Exception as e:
            self.sf.error(f"Failed to publish to MISP: {e}")
