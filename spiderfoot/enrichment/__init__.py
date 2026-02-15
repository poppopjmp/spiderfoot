"""
SpiderFoot Enrichment Service
==============================
File and document enrichment pipeline inspired by the Nemesis architecture.

Pipeline stages:
  1. Ingestion  — Accept files via HTTP upload or MinIO events
  2. Conversion — Extract text from PDFs, Office docs, images (OCR)
  3. Extraction — Extract strings, metadata, IOCs, entities
  4. Analysis   — Run YARA rules, classify content, score relevance
  5. Storage    — Store enriched data in MinIO + metadata in PostgreSQL
  6. Dispatch   — Forward enriched content to agents for LLM analysis

Supported formats:
  - PDF, DOCX, XLSX, PPTX, RTF
  - HTML, XML, JSON, CSV
  - Plain text, source code
  - Images (OCR via Tesseract when available)
"""

__version__ = "0.1.0"
