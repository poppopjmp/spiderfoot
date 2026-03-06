"""
Enrichment Pipeline — orchestrates document processing stages.

Coordinates: Ingestion → Conversion → Extraction → Analysis → Storage → Dispatch
"""

import hashlib
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .converter import ConversionResult, DocumentConverter
from .extractor import EntityExtractor, ExtractionResult

logger = logging.getLogger("sf.enrichment.pipeline")


@dataclass
class EnrichmentResult:
    """Complete enrichment output for a processed document."""

    document_id: str
    filename: str
    content_type: str
    file_hash_sha256: str
    file_size: int
    conversion: Optional[ConversionResult] = None
    extraction: Optional[ExtractionResult] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    processing_time_ms: float = 0.0
    errors: List[str] = field(default_factory=list)
    stored_path: str = ""

    @property
    def is_success(self) -> bool:
        return self.conversion is not None and self.conversion.is_success

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "filename": self.filename,
            "content_type": self.content_type,
            "file_hash_sha256": self.file_hash_sha256,
            "file_size": self.file_size,
            "text_length": self.conversion.char_count if self.conversion else 0,
            "pages": self.conversion.pages if self.conversion else 0,
            "format_detected": self.conversion.format_detected if self.conversion else "unknown",
            "entities": self.extraction.to_dict() if self.extraction else {},
            "total_entities": self.extraction.total_entities if self.extraction else 0,
            "metadata": self.metadata,
            "processing_time_ms": self.processing_time_ms,
            "errors": self.errors,
            "stored_path": self.stored_path,
        }


class EnrichmentPipeline:
    """
    Document enrichment pipeline.

    Usage:
        pipeline = EnrichmentPipeline()
        result = pipeline.process(file_bytes, "report.pdf")
    """

    def __init__(
        self,
        minio_endpoint: str = "",
        minio_bucket: str = "sf-enrichment",
        minio_access_key: str = "",
        minio_secret_key: str = "",
    ):
        self.converter = DocumentConverter()
        self.extractor = EntityExtractor()
        self.minio_endpoint = minio_endpoint or os.environ.get(
            "SF_MINIO_ENDPOINT", "minio:9000"
        )
        self.minio_bucket = minio_bucket
        self.minio_access_key = minio_access_key or os.environ.get(
            "SF_MINIO_ACCESS_KEY", "spiderfoot"
        )
        self.minio_secret_key = minio_secret_key or os.environ.get(
            "SF_MINIO_SECRET_KEY", ""
        )

    def process(
        self,
        content: bytes,
        filename: str,
        content_type: str = "",
        scan_id: str = "",
        target: str = "",
        store: bool = True,
    ) -> EnrichmentResult:
        """
        Process a document through the full enrichment pipeline.

        Args:
            content: Raw file bytes
            filename: Original filename
            content_type: MIME type (auto-detected if empty)
            scan_id: Associated scan ID
            target: Investigation target
            store: Whether to store in MinIO

        Returns:
            EnrichmentResult with all extracted data
        """
        start_time = time.monotonic()

        # Generate document ID from content hash
        file_hash = hashlib.sha256(content).hexdigest()
        doc_id = f"{file_hash[:12]}-{int(time.time())}"

        result = EnrichmentResult(
            document_id=doc_id,
            filename=filename,
            content_type=content_type,
            file_hash_sha256=file_hash,
            file_size=len(content),
            metadata={
                "scan_id": scan_id,
                "target": target,
                "ingested_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
        )

        # Stage 1: Convert to text
        logger.info("Converting %s (%d bytes)", filename, len(content))
        try:
            result.conversion = self.converter.convert(content, filename, content_type)
            if result.conversion.metadata:
                result.metadata.update(result.conversion.metadata)
            result.errors.extend(result.conversion.errors)
        except Exception as exc:
            result.errors.append(f"Conversion failed: {exc}")
            logger.error("Conversion failed for %s: %s", filename, exc)

        # Stage 2: Extract entities
        if result.conversion and result.conversion.text:
            logger.info("Extracting entities from %s", filename)
            try:
                result.extraction = self.extractor.extract(result.conversion.text)
                logger.info(
                    "Extracted %d entities from %s",
                    result.extraction.total_entities,
                    filename,
                )
            except Exception as exc:
                result.errors.append(f"Extraction failed: {exc}")
                logger.error("Extraction failed for %s: %s", filename, exc)

        # Stage 3: Store in MinIO
        if store and result.is_success:
            try:
                stored_path = self._store_to_minio(content, filename, doc_id, file_hash)
                result.stored_path = stored_path

                # Also store extracted text
                if result.conversion and result.conversion.text:
                    self._store_to_minio(
                        result.conversion.text.encode("utf-8"),
                        f"{doc_id}.txt",
                        doc_id,
                        file_hash,
                        prefix="extracted-text",
                    )

            except Exception as exc:
                result.errors.append(f"Storage failed: {exc}")
                logger.warning("MinIO storage failed for %s: %s", filename, exc)

        result.processing_time_ms = (time.monotonic() - start_time) * 1000
        logger.info(
            "Enrichment complete for %s: %d entities, %.1fms",
            filename,
            result.extraction.total_entities if result.extraction else 0,
            result.processing_time_ms,
        )

        return result

    def _store_to_minio(
        self,
        content: bytes,
        filename: str,
        doc_id: str,
        file_hash: str,
        prefix: str = "documents",
    ) -> str:
        """Store file in MinIO and return the object path."""
        try:
            from minio import Minio

            client = Minio(
                self.minio_endpoint,
                access_key=self.minio_access_key,
                secret_key=self.minio_secret_key,
                secure=False,
            )

            # Ensure bucket exists
            if not client.bucket_exists(self.minio_bucket):
                client.make_bucket(self.minio_bucket)

            import io

            object_path = f"{prefix}/{doc_id}/{filename}"
            client.put_object(
                self.minio_bucket,
                object_path,
                io.BytesIO(content),
                length=len(content),
            )

            logger.info("Stored %s → %s/%s", filename, self.minio_bucket, object_path)
            return f"{self.minio_bucket}/{object_path}"

        except ImportError:
            logger.warning("minio package not installed — storage skipped")
            return ""
