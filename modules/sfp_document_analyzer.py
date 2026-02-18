from __future__ import annotations

"""SpiderFoot plug-in module: sfp_document_analyzer.

Tika-powered document analysis module.  Processes user-uploaded documents
through Apache Tika (full) for text/metadata extraction and then applies
IOC/entity extraction patterns to produce standard SpiderFoot events.

Architecture
~~~~~~~~~~~~
This module **replaces** the former standalone enrichment and user-input
HTTP micro-services.  Instead of a separate container, document processing
now runs inside the scan pipeline as a regular SpiderFoot plug-in:

  1. User optionally attaches a file on the *New Scan* form.
  2. The WebUI generates a ``DOCUMENT_UPLOAD`` event containing the
     file payload (base64 or raw bytes).
  3. This module picks up the event, sends the file to the in-stack
     Apache Tika container for text + metadata extraction.
  4. Extracted text is run through the ``EntityExtractor`` regex engine
     (IPs, domains, e-mails, URLs, hashes, CVEs, crypto addresses …).
  5. Each discovered entity is published as a normal SpiderFoot event
     so downstream modules can investigate it further.
  6. Optionally, the full analysis is forwarded to the AI Agents
     service for deeper LLM-powered intelligence.

Standalone / Correlation
~~~~~~~~~~~~~~~~~~~~~~~~
The module can also be triggered via the REST API (``POST /api/analyze-doc``)
or by workspace-level correlation rules that reference document data.
"""

# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         sfp_document_analyzer
# Purpose:      Tika-powered document analysis integrated into the scan pipeline.
#
# Author:       SpiderFoot Team
# Created:      2026-02-18
# Copyright:    (c) SpiderFoot Team 2026
# Licence:      MIT
# -------------------------------------------------------------------------------

import base64
import hashlib
import io
import json
import logging
import os
import re
import urllib.error
import urllib.request

from spiderfoot import SpiderFootEvent
from spiderfoot.plugins.modern_plugin import SpiderFootModernPlugin

log = logging.getLogger("spiderfoot.module.sfp_document_analyzer")


# ---- Inline lightweight IOC extractor (mirrors enrichment/extractor.py) ----

_PATTERNS = {
    "ipv4": re.compile(
        r"\b(?:(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)\.){3}"
        r"(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)\b"
    ),
    "ipv6": re.compile(r"\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b"),
    "domain": re.compile(
        r"\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)"
        r"+(?:com|net|org|io|co|gov|edu|mil|int|biz|info|name|us|uk|de|"
        r"fr|jp|cn|ru|br|au|ca|in|it|nl|es|se|no|fi|ch|at|be|cz|pl|"
        r"pt|dk|ie|za|nz|mx|ar|kr|sg|hk|tw|id|th|my|ph|vn|xyz|"
        r"online|site|top|club|app|dev|cloud|tech|ai)\b",
    ),
    "email": re.compile(
        r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Z|a-z]{2,}\b"
    ),
    "url": re.compile(r"https?://[^\s<>\"')\]]+"),
    "md5": re.compile(r"\b[a-fA-F0-9]{32}\b"),
    "sha1": re.compile(r"\b[a-fA-F0-9]{40}\b"),
    "sha256": re.compile(r"\b[a-fA-F0-9]{64}\b"),
    "cve": re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.IGNORECASE),
    "bitcoin": re.compile(r"\b[13][a-km-zA-HJ-NP-Z1-9]{25,34}\b"),
    "ethereum": re.compile(r"\b0x[a-fA-F0-9]{40}\b"),
    "phone": re.compile(r"\+\d{1,3}[\s.-]?\(?\d{1,4}\)?[\s.-]?\d{3,4}[\s.-]?\d{3,4}"),
}

_SKIP_DOMAINS = {
    "example.com", "example.org", "example.net",
    "localhost", "localdomain",
    "w3.org", "schema.org", "xmlns.com",
    "apache.org", "openxmlformats.org",
    "purl.org", "dublincore.org",
}

_PRIVATE_IPV4 = re.compile(
    r"^(10\.|172\.(1[6-9]|2\d|3[01])\.|192\.168\.|127\.|0\.)"
)


def _extract_entities(text: str) -> dict[str, list[str]]:
    """Run all IOC patterns against *text* and return grouped results."""
    entities: dict[str, list[str]] = {}
    for name, pattern in _PATTERNS.items():
        matches = set(pattern.findall(text))
        # Filter noise
        filtered: list[str] = []
        for m in matches:
            # Skip private/reserved IPs
            if name in ("ipv4",) and _PRIVATE_IPV4.match(m):
                continue
            # Skip placeholder / well-known domains
            if name == "domain" and m.lower() in _SKIP_DOMAINS:
                continue
            # Skip very short hash-like hex that's actually just noise
            if name in ("md5", "sha1", "sha256"):
                # Skip if it's all zeros or all same char
                if len(set(m.lower())) <= 2:
                    continue
            filtered.append(m)
        if filtered:
            entities[name] = sorted(set(filtered))
    return entities


# ---- Module class ----


class sfp_document_analyzer(SpiderFootModernPlugin):
    """Tika-powered document analysis — extracts text, metadata and IOCs
    from user-uploaded files and publishes them as SpiderFoot events.

    Replaces the former enrichment + user-input microservices.  Documents
    are converted via the Apache Tika container (``tika:9998``), then
    scanned for IOCs using compiled regex patterns.
    """

    meta = {
        "name": "Document Analyzer (Tika)",
        "summary": (
            "Upload documents (PDF, DOCX, XLSX, HTML, images …) for Tika-powered "
            "text extraction and IOC/entity discovery.  Results feed into the "
            "normal scan pipeline."
        ),
        "flags": ["interactive", "slow"],
        "useCases": ["Footprint", "Investigate", "Passive"],
        "categories": ["Content Analysis"],
        "dataSource": {
            "website": "https://tika.apache.org/",
            "model": "FREE_NOAUTH_UNLIMITED",
            "description": (
                "Apache Tika extracts text and metadata from over one thousand "
                "different file types (PDF, DOCX, XLSX, PPTX, RTF, HTML, images "
                "via OCR, etc.).  Extracted text is scanned for IOCs: IP addresses, "
                "domains, email addresses, URLs, file hashes, CVEs, cryptocurrency "
                "addresses, and more."
            ),
        },
    }

    opts = {
        "tika_url": "http://tika:9998",
        "agents_url": "http://agents:8100",
        "max_file_size_mb": 100,
        "forward_to_agents": True,
        "tika_timeout": 120,
        "ocr_enabled": True,
    }

    optdescs = {
        "tika_url": "URL of the Apache Tika server.",
        "agents_url": "URL of the AI agents service for deeper analysis.",
        "max_file_size_mb": "Maximum file size in MB to accept for processing.",
        "forward_to_agents": "Forward extracted text to AI agents for LLM analysis?",
        "tika_timeout": "Timeout in seconds for Tika processing requests.",
        "ocr_enabled": "Enable OCR for images and scanned PDFs? (requires Tika-full image).",
    }

    results = None
    errorState = False

    def setup(self, sfc, userOpts=None) -> None:
        super().setup(sfc, userOpts or {})
        self.errorState = False
        self.results = self.tempStorage()

    # ---- Events ----

    def watchedEvents(self) -> list:
        return [
            "DOCUMENT_UPLOAD",
            "USER_DOCUMENT",
            "USER_INPUT_DATA",
            "REPORT_UPLOAD",
        ]

    def producedEvents(self) -> list:
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

    # ---- Tika interaction ----

    def _tika_extract(self, file_data: bytes, filename: str) -> dict | None:
        """Send *file_data* to Tika and return ``{text, metadata}`` or None."""
        tika_url = self.opts.get("tika_url", "http://tika:9998")
        timeout = int(self.opts.get("tika_timeout", 120))

        # 1) Extract text via /tika endpoint
        headers = {
            "Content-Type": "application/octet-stream",
            "Accept": "text/plain",
        }
        if filename:
            headers["Content-Disposition"] = f'attachment; filename="{filename}"'
        if self.opts.get("ocr_enabled"):
            headers["X-Tika-OCRskipOcr"] = "false"
        else:
            headers["X-Tika-OCRskipOcr"] = "true"

        req_text = urllib.request.Request(
            f"{tika_url}/tika",
            data=file_data,
            headers=headers,
            method="PUT",
        )

        text = ""
        try:
            with urllib.request.urlopen(req_text, timeout=timeout) as resp:
                text = resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            self.error(f"Tika text extraction failed for {filename}: {e}")
            return None

        # 2) Extract metadata via /meta endpoint
        meta_headers = dict(headers)
        meta_headers["Accept"] = "application/json"
        req_meta = urllib.request.Request(
            f"{tika_url}/meta",
            data=file_data,
            headers=meta_headers,
            method="PUT",
        )

        metadata = {}
        try:
            with urllib.request.urlopen(req_meta, timeout=timeout) as resp:
                metadata = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            self.info(f"Tika metadata extraction failed (non-fatal): {e}")

        return {"text": text, "metadata": metadata}

    def _call_agents(self, doc_text: str, filename: str) -> dict | None:
        """Forward extracted text to AI agents for deeper analysis."""
        url = f"{self.opts.get('agents_url', 'http://agents:8100')}/agents/process"
        payload = json.dumps({
            "event_type": "DOCUMENT_UPLOAD",
            "data": doc_text[:50000],
            "source": filename,
        }).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            self.info(f"Agent analysis unavailable for {filename}: {e}")
            return None

    # ---- Entity emission ----

    _TYPE_MAP = {
        "ipv4": "IP_ADDRESS",
        "ipv6": "IP_ADDRESS",
        "email": "EMAILADDR",
        "domain": "DOMAIN_NAME",
        "url": "URL_STATIC",
        "md5": "HASH",
        "sha1": "HASH",
        "sha256": "HASH",
        "cve": "VULNERABILITY_CVE_MEDIUM",
        "bitcoin": "BITCOIN_ADDRESS",
        "ethereum": "ETHEREUM_ADDRESS",
        "phone": "PHONE_NUMBER",
    }

    def _emit_entities(
        self, entities: dict[str, list[str]], source_event: SpiderFootEvent
    ) -> int:
        count = 0
        for etype, values in entities.items():
            sf_type = self._TYPE_MAP.get(etype)
            if not sf_type:
                continue
            for value in values:
                if value in self.results:
                    continue
                self.results[value] = True
                evt = SpiderFootEvent(sf_type, str(value), self.__name__, source_event)
                self.notifyListeners(evt)
                count += 1
                if self.checkForStop():
                    return count
        return count

    # ---- Main handler ----

    def handleEvent(self, event: SpiderFootEvent) -> None:
        eventData = event.data

        if self.errorState:
            return

        # De-duplicate by content hash
        raw_bytes: bytes
        filename = "upload.bin"

        if isinstance(eventData, str):
            try:
                doc_info = json.loads(eventData)
                filename = doc_info.get("filename", filename)
                if doc_info.get("content_base64"):
                    raw_bytes = base64.b64decode(doc_info["content_base64"])
                else:
                    raw_bytes = doc_info.get("content", eventData).encode("utf-8")
            except (json.JSONDecodeError, TypeError):
                raw_bytes = eventData.encode("utf-8")
        else:
            raw_bytes = eventData

        data_hash = hashlib.sha256(raw_bytes).hexdigest()[:16]
        if data_hash in self.results:
            self.debug(f"Skipping duplicate document: {data_hash}")
            return
        self.results[data_hash] = True

        max_size = int(self.opts.get("max_file_size_mb", 100)) * 1024 * 1024
        if len(raw_bytes) > max_size:
            self.error(f"File too large ({len(raw_bytes)} bytes > {max_size} limit)")
            return

        self.info(f"Processing document: {filename} ({len(raw_bytes)} bytes)")

        # --- 1. Tika extraction ---
        tika_result = self._tika_extract(raw_bytes, filename)
        text_content = ""
        metadata = {}

        if tika_result:
            text_content = tika_result.get("text", "")
            metadata = tika_result.get("metadata", {})
            self.info(f"Tika extracted {len(text_content)} chars from {filename}")
        else:
            # Fallback: try to read as plain text
            self.info("Tika unavailable — attempting plain-text fallback")
            try:
                text_content = raw_bytes.decode("utf-8", errors="replace")
            except Exception:
                text_content = raw_bytes.decode("latin-1", errors="replace")

        if not text_content.strip():
            self.info(f"No text extracted from {filename}")
            return

        # --- 2. Emit DOCUMENT_TEXT event ---
        doc_evt = SpiderFootEvent(
            "DOCUMENT_TEXT",
            text_content[:200000],
            self.__name__,
            event,
        )
        self.notifyListeners(doc_evt)

        # --- 3. Emit RAW_RIR_DATA with metadata ---
        if metadata:
            meta_evt = SpiderFootEvent(
                "RAW_RIR_DATA",
                json.dumps(
                    {"source": "tika", "filename": filename, "metadata": metadata},
                    indent=2,
                ),
                self.__name__,
                event,
            )
            self.notifyListeners(meta_evt)

        # --- 4. IOC extraction & emission ---
        entities = _extract_entities(text_content)
        if entities:
            emitted = self._emit_entities(entities, event)
            self.info(f"Emitted {emitted} events from {filename}")
        else:
            self.info(f"No IOCs found in {filename}")

        # --- 5. AI agent analysis (optional) ---
        if self.opts.get("forward_to_agents") and text_content:
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


# End of sfp_document_analyzer
