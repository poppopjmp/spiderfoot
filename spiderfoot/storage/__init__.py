"""
SpiderFoot Object Storage layer.

Provides S3-compatible (MinIO) storage for reports, logs, backups,
and general data artefacts.
"""

from .minio_manager import MinIOStorageManager, MinIOConfig

__all__ = ["MinIOStorageManager", "MinIOConfig"]
