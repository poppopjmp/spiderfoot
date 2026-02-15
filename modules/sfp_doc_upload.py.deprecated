from __future__ import annotations

"""SpiderFoot plug-in module: sfp_doc_upload.

A special interactive module that processes user-uploaded documents through
the enrichment pipeline. Unlike standard modules, this one requires user
interaction on every scan run — the user must supply at least one document
or data file before the module can produce results.

The module is flagged with 'interactive' so the UI highlights it distinctly
in the module selection list.
"""

# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         sfp_doc_upload
# Purpose:      Process user-uploaded documents through the enrichment pipeline
#               and produce OSINT events from extracted entities.
#
# Author:       SpiderFoot Team
# Created:      2026-02-13
# Copyright:    (c) SpiderFoot Team 2026
# Licence:      MIT
# -------------------------------------------------------------------------------

import json
import logging
import os
import hashlib

from spiderfoot import SpiderFootEvent
from spiderfoot.plugins.modern_plugin import SpiderFootModernPlugin

log = logging.getLogger("spiderfoot.module.sfp_doc_upload")


class sfp_doc_upload(SpiderFootModernPlugin):
    """Process user-uploaded documents through the enrichment pipeline.

    This is an interactive module — it requires the user to upload documents
    for each scan run. It appears highlighted in the module selection UI
    with an 'interactive' badge.

    Uploaded documents are sent to the enrichment service for conversion
    and entity extraction. Extracted entities (IPs, domains, emails, hashes,
    CVEs, etc.) are published as SpiderFoot events for other modules to
    consume and investigate further.
    """

    meta = {
        'name': "Document Upload & Enrichment",
        'summary': "Upload documents (PDF, DOCX, XLSX, HTML, TXT) to extract entities and IOCs. "
                   "Requires user interaction — you must upload files for each scan run.",
        'flags': ["interactive", "slow"],
        'useCases': ["Footprint", "Investigate", "Passive"],
        'categories': ["Content Analysis"],
        'dataSource': {
            'website': "https://github.com/poppopjmp/spiderfoot",
            'model': "FREE_NOAUTH_UNLIMITED",
            'description': "Extracts intelligence from user-supplied documents by converting "
                           "them to text and applying entity/IOC extraction patterns. "
                           "Supports PDF, DOCX, XLSX, HTML, RTF, and plain text files.\n"
                           "Extracted entities include IP addresses, domains, email addresses, "
                           "URLs, file hashes (MD5/SHA1/SHA256), CVEs, Bitcoin/Ethereum addresses, "
                           "and more.",
        },
    }

    opts = {
        'enrichment_url': 'http://enrichment:8200',
        'agents_url': 'http://agents:8100',
        'max_file_size_mb': 100,
        'extract_iocs': True,
        'extract_entities': True,
        'forward_to_agents': True,
        'supported_extensions': 'pdf,docx,xlsx,html,htm,rtf,txt,csv,json,xml,md',
    }

    optdescs = {
        'enrichment_url': "URL of the enrichment service for document processing.",
        'agents_url': "URL of the AI agents service for document analysis.",
        'max_file_size_mb': "Maximum file size in MB to accept for processing.",
        'extract_iocs': "Extract IOCs (hashes, IPs, domains, CVEs) from documents?",
        'extract_entities': "Extract named entities (emails, phone numbers, URLs) from documents?",
        'forward_to_agents': "Forward documents to AI agents for deeper analysis?",
        'supported_extensions': "Comma-separated list of supported file extensions.",
    }

    results = None
    errorState = False
    _uploaded_docs = None

    def setup(self, sfc, userOpts=None) -> None:
        """Set up the module."""
        super().setup(sfc, userOpts or {})
        self.results = self.tempStorage()
        self._uploaded_docs = []

    def watchedEvents(self) -> list:
        """Return the list of events this module watches.

        DOCUMENT_UPLOAD: Triggered when a user uploads a document via the UI.
        USER_INPUT_DATA: Triggered when user provides raw data/text.
        SCAN_TARGET: The initial scan target (used to associate documents with scan).
        """
        return [
            "DOCUMENT_UPLOAD",
            "USER_INPUT_DATA",
            "USER_DOCUMENT",
            "REPORT_UPLOAD",
        ]

    def producedEvents(self) -> list:
        """Return the list of events this module produces."""
        return [
            "IP_ADDRESS",
            "DOMAIN_NAME",
            "EMAILADDR",
            "INTERNET_NAME",
            "URL_STATIC",
            "HASH",
            "VULNERABILITY_CVE_CRITICAL",
            "VULNERABILITY_CVE_HIGH",
            "VULNERABILITY_CVE_MEDIUM",
            "VULNERABILITY_CVE_LOW",
            "BITCOIN_ADDRESS",
            "ETHEREUM_ADDRESS",
            "PHONE_NUMBER",
            "RAW_RIR_DATA",
            "DOCUMENT_TEXT",
            "TARGET_WEB_CONTENT",
        ]

    def _call_enrichment(self, file_data: bytes, filename: str) -> dict | None:
        """Send a document to the enrichment service for processing.

        Args:
            file_data: Raw file bytes.
            filename: Original filename.

        Returns:
            Enrichment result dict or None on failure.
        """
        import urllib.request
        import urllib.error

        url = f"{self.opts['enrichment_url']}/enrichment/process-text"

        # For binary files, we'd use the upload endpoint
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'txt'
        if ext in ('pdf', 'docx', 'xlsx', 'rtf'):
            url = f"{self.opts['enrichment_url']}/enrichment/upload"
            # Build multipart form data
            boundary = '---SpiderFootUploadBoundary'
            body = (
                f'--{boundary}\r\n'
                f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
                f'Content-Type: application/octet-stream\r\n\r\n'
            ).encode('utf-8') + file_data + f'\r\n--{boundary}--\r\n'.encode('utf-8')

            req = urllib.request.Request(
                url,
                data=body,
                headers={
                    'Content-Type': f'multipart/form-data; boundary={boundary}',
                },
                method='POST',
            )
        else:
            # For text-based files, use process-text endpoint
            try:
                text_content = file_data.decode('utf-8', errors='replace')
            except Exception:
                text_content = file_data.decode('latin-1', errors='replace')

            payload = json.dumps({
                'text': text_content,
                'source': filename,
            }).encode('utf-8')

            req = urllib.request.Request(
                url,
                data=payload,
                headers={'Content-Type': 'application/json'},
                method='POST',
            )

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except urllib.error.URLError as e:
            self.error(f"Enrichment service error for {filename}: {e}")
            return None
        except Exception as e:
            self.error(f"Failed to process {filename}: {e}")
            return None

    def _call_agents(self, doc_text: str, filename: str) -> dict | None:
        """Forward document to AI agents for deeper analysis.

        Args:
            doc_text: Extracted text content.
            filename: Source filename.

        Returns:
            Agent analysis result dict or None on failure.
        """
        import urllib.request
        import urllib.error

        url = f"{self.opts['agents_url']}/agents/process"
        payload = json.dumps({
            'event_type': 'DOCUMENT_UPLOAD',
            'data': doc_text[:50000],  # Limit to 50k chars for agent processing
            'source': filename,
        }).encode('utf-8')

        req = urllib.request.Request(
            url,
            data=payload,
            headers={'Content-Type': 'application/json'},
            method='POST',
        )

        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except Exception as e:
            self.info(f"Agent analysis unavailable for {filename}: {e}")
            return None

    def _emit_entities(self, entities: dict, source_event: SpiderFootEvent) -> int:
        """Emit SpiderFoot events from extracted entities.

        Args:
            entities: Dict of entity_type → list of values.
            source_event: Parent event to link new events to.

        Returns:
            Number of events emitted.
        """
        count = 0
        type_map = {
            'ipv4': 'IP_ADDRESS',
            'ipv6': 'IP_ADDRESS',
            'ip_addresses': 'IP_ADDRESS',
            'email': 'EMAILADDR',
            'emails': 'EMAILADDR',
            'domain': 'DOMAIN_NAME',
            'domains': 'DOMAIN_NAME',
            'url': 'URL_STATIC',
            'urls': 'URL_STATIC',
            'hash_md5': 'HASH',
            'hash_sha1': 'HASH',
            'hash_sha256': 'HASH',
            'hashes': 'HASH',
            'cve': 'VULNERABILITY_CVE_MEDIUM',
            'cves': 'VULNERABILITY_CVE_MEDIUM',
            'bitcoin': 'BITCOIN_ADDRESS',
            'bitcoin_addresses': 'BITCOIN_ADDRESS',
            'ethereum': 'ETHEREUM_ADDRESS',
            'ethereum_addresses': 'ETHEREUM_ADDRESS',
            'phone': 'PHONE_NUMBER',
            'phone_numbers': 'PHONE_NUMBER',
            'hostname': 'INTERNET_NAME',
            'hostnames': 'INTERNET_NAME',
        }

        for entity_type, values in entities.items():
            sf_type = type_map.get(entity_type.lower())
            if not sf_type:
                continue

            if isinstance(values, str):
                values = [values]

            for value in values:
                if not value or value in self.results:
                    continue
                self.results[value] = True

                evt = SpiderFootEvent(sf_type, str(value), self.__name__, source_event)
                self.notifyListeners(evt)
                count += 1

                if self.checkForStop():
                    return count

        return count

    def handleEvent(self, event: SpiderFootEvent) -> None:
        """Handle an event received by this module.

        Processes document upload/user input events through the enrichment
        pipeline, extracts entities, and optionally forwards to AI agents.
        """
        eventData = event.data
        eventType = event.eventType

        if self.errorState:
            return

        # Generate a hash-based key for dedup
        data_hash = hashlib.sha256(eventData.encode('utf-8', errors='replace')
                                   if isinstance(eventData, str)
                                   else eventData).hexdigest()[:16]

        if data_hash in self.results:
            self.debug(f"Skipping duplicate document: {data_hash}")
            return
        self.results[data_hash] = True

        # Determine the filename from event data or generate one
        filename = f"upload_{data_hash}.txt"
        if eventType in ('DOCUMENT_UPLOAD', 'USER_DOCUMENT', 'REPORT_UPLOAD'):
            # Event data might be JSON with filename and content
            try:
                doc_info = json.loads(eventData)
                filename = doc_info.get('filename', filename)
                content = doc_info.get('content', '')
                if doc_info.get('content_base64'):
                    import base64
                    file_data = base64.b64decode(doc_info['content_base64'])
                else:
                    file_data = content.encode('utf-8') if isinstance(content, str) else content
            except (json.JSONDecodeError, TypeError):
                # Treat raw data as text content
                file_data = eventData.encode('utf-8') if isinstance(eventData, str) else eventData
        else:
            file_data = eventData.encode('utf-8') if isinstance(eventData, str) else eventData

        self.info(f"Processing document: {filename} ({len(file_data)} bytes)")

        # Emit raw document text event
        try:
            text_content = file_data.decode('utf-8', errors='replace')
        except Exception:
            text_content = str(file_data)

        doc_evt = SpiderFootEvent("DOCUMENT_TEXT", text_content[:100000], self.__name__, event)
        self.notifyListeners(doc_evt)

        # Call enrichment service
        enrichment_result = self._call_enrichment(file_data, filename)
        if enrichment_result:
            # Emit RAW_RIR_DATA with full enrichment response
            raw_evt = SpiderFootEvent(
                "RAW_RIR_DATA",
                json.dumps(enrichment_result, indent=2),
                self.__name__,
                event,
            )
            self.notifyListeners(raw_evt)

            # Extract and emit individual entity events
            entities = enrichment_result.get('entities', {})
            if not entities:
                entities = enrichment_result.get('extracted', {})
            if entities:
                emitted = self._emit_entities(entities, event)
                self.info(f"Emitted {emitted} events from {filename}")
            else:
                self.info(f"No entities extracted from {filename}")
        else:
            self.info(f"Enrichment service unavailable; extracting locally from {filename}")
            # Fallback: basic local entity extraction
            self._local_extract(text_content, event)

        # Forward to AI agents for deeper analysis
        if self.opts.get('forward_to_agents') and text_content:
            agent_result = self._call_agents(text_content, filename)
            if agent_result:
                raw_evt = SpiderFootEvent(
                    "RAW_RIR_DATA",
                    json.dumps(agent_result, indent=2),
                    self.__name__,
                    event,
                )
                raw_evt.moduleDataSource = "AI Agent Analysis"
                self.notifyListeners(raw_evt)

    def _local_extract(self, text: str, source_event: SpiderFootEvent) -> None:
        """Fallback local entity extraction when enrichment service is unavailable.

        Uses basic regex patterns to find common IOCs in text.
        """
        import re

        patterns = {
            'IP_ADDRESS': r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
            'EMAILADDR': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            'DOMAIN_NAME': r'\b(?:[a-zA-Z0-9-]+\.)+(?:com|net|org|io|co|gov|edu|mil|int)\b',
            'HASH': r'\b[a-fA-F0-9]{32}\b|\b[a-fA-F0-9]{40}\b|\b[a-fA-F0-9]{64}\b',
            'URL_STATIC': r'https?://[^\s<>"\']+',
        }

        for event_type, pattern in patterns.items():
            matches = set(re.findall(pattern, text))
            for match in matches:
                if match not in self.results:
                    self.results[match] = True
                    evt = SpiderFootEvent(event_type, match, self.__name__, source_event)
                    self.notifyListeners(evt)

                    if self.checkForStop():
                        return


# End of sfp_doc_upload class
