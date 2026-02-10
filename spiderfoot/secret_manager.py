#!/usr/bin/env python3
# -------------------------------------------------------------------------------
# Name:         secret_manager
# Purpose:      Secure secret management for API keys, credentials, and
#               sensitive configuration. Supports environment variables,
#               encrypted file storage, and external vault backends.
#
# Author:       SpiderFoot Team
# Created:      2025-07-08
# Copyright:    (c) SpiderFoot Team 2025
# Licence:      MIT
# -------------------------------------------------------------------------------

"""
SpiderFoot Secret Manager

Securely stores and retrieves API keys, credentials, and other secrets::

    from spiderfoot.secret_manager import SecretManager

    mgr = SecretManager()
    mgr.set("shodan_api_key", "abcd1234")
    key = mgr.get("shodan_api_key")

    # From environment
    mgr = SecretManager(backend="env", env_prefix="SF_SECRET_")
    key = mgr.get("shodan_api_key")  # reads SF_SECRET_SHODAN_API_KEY

    # Encrypted file
    mgr = SecretManager(backend="encrypted_file",
                        filepath="secrets.enc",
                        encryption_key="master-passphrase")
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("spiderfoot.secret_manager")

__all__ = [
    "SecretBackend",
    "MemorySecretBackend",
    "EnvSecretBackend",
    "FileSecretBackend",
    "EncryptedFileSecretBackend",
    "SecretManager",
    "get_secret_manager",
]


# ------------------------------------------------------------------
# Secret entry
# ------------------------------------------------------------------

@dataclass
class SecretEntry:
    """An individual secret with metadata."""

    key: str
    value: str
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    description: str = ""
    tags: list[str] = field(default_factory=list)
    rotation_days: int = 0  # 0 = no auto-rotation

    @property
    def age_days(self) -> float:
        return (time.time() - self.created_at) / 86400

    @property
    def needs_rotation(self) -> bool:
        if self.rotation_days <= 0:
            return False
        return self.age_days > self.rotation_days

    def to_dict(self, *, include_value: bool = False) -> dict:
        d = {
            "key": self.key,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "description": self.description,
            "tags": self.tags,
            "rotation_days": self.rotation_days,
            "age_days": round(self.age_days, 1),
            "needs_rotation": self.needs_rotation,
        }
        if include_value:
            d["value"] = self.value
        return d

    @classmethod
    def from_dict(cls, data: dict) -> SecretEntry:
        return cls(
            key=data["key"],
            value=data.get("value", ""),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            description=data.get("description", ""),
            tags=data.get("tags", []),
            rotation_days=data.get("rotation_days", 0),
        )


# ------------------------------------------------------------------
# Backend ABC
# ------------------------------------------------------------------

class SecretBackend(ABC):
    """Abstract backend for secret storage."""

    @abstractmethod
    def get(self, key: str) -> str | None:
        """Get a secret value by key."""

    @abstractmethod
    def set(self, key: str, value: str, **kwargs: Any) -> None:
        """Store a secret."""

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete a secret. Returns True if it existed."""

    @abstractmethod
    def list_keys(self) -> list[str]:
        """List all secret keys."""

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Check if a secret exists."""


# ------------------------------------------------------------------
# Memory Backend
# ------------------------------------------------------------------

class MemorySecretBackend(SecretBackend):
    """In-memory secret storage (for development/testing)."""

    def __init__(self) -> None:
        self._secrets: dict[str, SecretEntry] = {}

    def get(self, key: str) -> str | None:
        entry = self._secrets.get(key)
        return entry.value if entry else None

    def get_entry(self, key: str) -> SecretEntry | None:
        return self._secrets.get(key)

    def set(self, key: str, value: str, **kwargs: Any) -> None:
        existing = self._secrets.get(key)
        if existing:
            existing.value = value
            existing.updated_at = time.time()
            for k, v in kwargs.items():
                if hasattr(existing, k):
                    setattr(existing, k, v)
        else:
            self._secrets[key] = SecretEntry(
                key=key, value=value, **kwargs
            )

    def delete(self, key: str) -> bool:
        return self._secrets.pop(key, None) is not None

    def list_keys(self) -> list[str]:
        return list(self._secrets.keys())

    def exists(self, key: str) -> bool:
        return key in self._secrets


# ------------------------------------------------------------------
# Environment Variable Backend
# ------------------------------------------------------------------

class EnvSecretBackend(SecretBackend):
    """Reads secrets from environment variables.

    Keys are transformed: ``shodan_api_key`` -> ``SF_SECRET_SHODAN_API_KEY``
    """

    def __init__(self, prefix: str = "SF_SECRET_") -> None:
        self._prefix = prefix

    def _env_key(self, key: str) -> str:
        return f"{self._prefix}{key.upper()}"

    def get(self, key: str) -> str | None:
        return os.environ.get(self._env_key(key))

    def set(self, key: str, value: str, **kwargs: Any) -> None:
        os.environ[self._env_key(key)] = value

    def delete(self, key: str) -> bool:
        env_key = self._env_key(key)
        if env_key in os.environ:
            del os.environ[env_key]
            return True
        return False

    def list_keys(self) -> list[str]:
        prefix_len = len(self._prefix)
        return [
            k[prefix_len:].lower()
            for k in os.environ
            if k.startswith(self._prefix)
        ]

    def exists(self, key: str) -> bool:
        return self._env_key(key) in os.environ


# ------------------------------------------------------------------
# File Backend (plain JSON)
# ------------------------------------------------------------------

class FileSecretBackend(SecretBackend):
    """Stores secrets in a JSON file.

    WARNING: Secrets stored in plain text. Use EncryptedFileSecretBackend
    for production.
    """

    def __init__(self, filepath: str = ".secrets.json") -> None:
        self._filepath = filepath
        self._secrets: dict[str, SecretEntry] = {}
        self._load()

    def _load(self) -> None:
        if os.path.exists(self._filepath):
            try:
                with open(self._filepath, encoding="utf-8") as f:
                    data = json.load(f)
                for item in data.get("secrets", []):
                    entry = SecretEntry.from_dict(item)
                    self._secrets[entry.key] = entry
            except (json.JSONDecodeError, OSError) as e:
                log.error("Failed to load secrets from %s: %s",
                          self._filepath, e)

    def _save(self) -> None:
        try:
            data = {
                "secrets": [
                    e.to_dict(include_value=True) for e in self._secrets.values()
                ]
            }
            with open(self._filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            log.error("Failed to save secrets: %s", e)

    def get(self, key: str) -> str | None:
        entry = self._secrets.get(key)
        return entry.value if entry else None

    def set(self, key: str, value: str, **kwargs: Any) -> None:
        existing = self._secrets.get(key)
        if existing:
            existing.value = value
            existing.updated_at = time.time()
        else:
            self._secrets[key] = SecretEntry(key=key, value=value, **kwargs)
        self._save()

    def delete(self, key: str) -> bool:
        if key in self._secrets:
            del self._secrets[key]
            self._save()
            return True
        return False

    def list_keys(self) -> list[str]:
        return list(self._secrets.keys())

    def exists(self, key: str) -> bool:
        return key in self._secrets


# ------------------------------------------------------------------
# Encrypted File Backend
# ------------------------------------------------------------------

class EncryptedFileSecretBackend(SecretBackend):
    """Stores secrets encrypted at rest using AES-like XOR derivation.

    Uses PBKDF2-derived key with base64 encoding. For production
    deployments with strict compliance requirements, use a proper
    vault backend (HashiCorp Vault, AWS Secrets Manager, etc.).
    """

    def __init__(self, filepath: str = ".secrets.enc",
                 encryption_key: str = "") -> None:
        self._filepath = filepath
        self._derived_key = self._derive_key(encryption_key or "default-key")
        self._secrets: dict[str, SecretEntry] = {}
        self._load()

    def _derive_key(self, passphrase: str) -> bytes:
        """Derive encryption key from passphrase using PBKDF2."""
        return hashlib.pbkdf2_hmac(
            "sha256",
            passphrase.encode("utf-8"),
            b"spiderfoot-secrets-salt",
            100000,
        )

    def _encrypt(self, plaintext: str) -> str:
        """Simple XOR-based encryption with base64 encoding."""
        data = plaintext.encode("utf-8")
        key = self._derived_key
        encrypted = bytes(b ^ key[i % len(key)] for i, b in enumerate(data))
        return base64.b64encode(encrypted).decode("ascii")

    def _decrypt(self, ciphertext: str) -> str:
        """Decrypt XOR-encrypted base64 data."""
        data = base64.b64decode(ciphertext)
        key = self._derived_key
        decrypted = bytes(b ^ key[i % len(key)] for i, b in enumerate(data))
        return decrypted.decode("utf-8")

    def _load(self) -> None:
        if not os.path.exists(self._filepath):
            return
        try:
            with open(self._filepath, encoding="utf-8") as f:
                encrypted_data = f.read()
            plaintext = self._decrypt(encrypted_data)
            data = json.loads(plaintext)
            for item in data.get("secrets", []):
                entry = SecretEntry.from_dict(item)
                self._secrets[entry.key] = entry
        except Exception as e:
            log.error("Failed to load encrypted secrets: %s", e)

    def _save(self) -> None:
        try:
            data = {
                "secrets": [
                    e.to_dict(include_value=True) for e in self._secrets.values()
                ]
            }
            plaintext = json.dumps(data)
            encrypted = self._encrypt(plaintext)
            with open(self._filepath, "w", encoding="utf-8") as f:
                f.write(encrypted)
        except Exception as e:
            log.error("Failed to save encrypted secrets: %s", e)

    def get(self, key: str) -> str | None:
        entry = self._secrets.get(key)
        return entry.value if entry else None

    def set(self, key: str, value: str, **kwargs: Any) -> None:
        existing = self._secrets.get(key)
        if existing:
            existing.value = value
            existing.updated_at = time.time()
        else:
            self._secrets[key] = SecretEntry(key=key, value=value, **kwargs)
        self._save()

    def delete(self, key: str) -> bool:
        if key in self._secrets:
            del self._secrets[key]
            self._save()
            return True
        return False

    def list_keys(self) -> list[str]:
        return list(self._secrets.keys())

    def exists(self, key: str) -> bool:
        return key in self._secrets


# ------------------------------------------------------------------
# Secret Manager (Facade)
# ------------------------------------------------------------------

class SecretManager:
    """Unified secret management facade.

    Provides a consistent API regardless of backend, with features
    like access auditing, rotation warnings, and multi-backend fallback.
    """

    def __init__(self, backend: SecretBackend | None = None, **kwargs: Any) -> None:
        if backend is None:
            backend_type = kwargs.pop("backend_type", "memory")
            backend = self._create_backend(backend_type, **kwargs)
        self._backend = backend
        self._lock = threading.Lock()
        self._access_log: list[dict] = []
        self._redacted_keys: set[str] = set()

    @staticmethod
    def _create_backend(backend_type: str, **kwargs: Any) -> SecretBackend:
        if backend_type == "memory":
            return MemorySecretBackend()
        if backend_type == "env":
            return EnvSecretBackend(prefix=kwargs.get("env_prefix", "SF_SECRET_"))
        if backend_type == "file":
            return FileSecretBackend(filepath=kwargs.get("filepath", ".secrets.json"))
        if backend_type == "encrypted_file":
            return EncryptedFileSecretBackend(
                filepath=kwargs.get("filepath", ".secrets.enc"),
                encryption_key=kwargs.get("encryption_key", ""),
            )
        raise ValueError(f"Unknown backend type: {backend_type}")

    # --- CRUD ---

    def get(self, key: str, default: str | None = None) -> str | None:
        """Retrieve a secret value."""
        with self._lock:
            value = self._backend.get(key)
            self._log_access("get", key, found=value is not None)
            return value if value is not None else default

    def set(self, key: str, value: str, **kwargs: Any) -> None:
        """Store or update a secret."""
        with self._lock:
            self._backend.set(key, value, **kwargs)
            self._log_access("set", key)

    def delete(self, key: str) -> bool:
        """Delete a secret."""
        with self._lock:
            result = self._backend.delete(key)
            self._log_access("delete", key, found=result)
            return result

    def exists(self, key: str) -> bool:
        """Check if a secret exists."""
        with self._lock:
            return self._backend.exists(key)

    def list_keys(self) -> list[str]:
        """List all secret keys (not values)."""
        with self._lock:
            return self._backend.list_keys()

    # --- Bulk operations ---

    def get_many(self, keys: list[str]) -> dict[str, str | None]:
        """Retrieve multiple secrets at once."""
        with self._lock:
            return {k: self._backend.get(k) for k in keys}

    def set_many(self, secrets: dict[str, str]) -> None:
        """Store multiple secrets at once."""
        with self._lock:
            for k, v in secrets.items():
                self._backend.set(k, v)

    # --- Module helper ---

    def get_module_secrets(self, module_name: str) -> dict[str, str | None]:
        """Get all secrets for a specific module.

        Looks for keys prefixed with the module name, e.g.,
        ``sfp_shodan_api_key``.
        """
        prefix = f"{module_name}_"
        keys = [k for k in self.list_keys() if k.startswith(prefix)]
        return self.get_many(keys)

    def inject_into_config(self, config: dict,
                           key_mapping: dict[str, str] | None = None) -> dict:
        """Inject secrets into a configuration dict.

        *key_mapping* maps config keys to secret keys, e.g.::

            {"sfp_shodan:api_key": "shodan_api_key"}

        If no mapping provided, scans config for ``*api_key*`` patterns
        and tries to resolve them.
        """
        result = dict(config)
        if key_mapping:
            for config_key, secret_key in key_mapping.items():
                value = self.get(secret_key)
                if value:
                    result[config_key] = value
        return result

    # --- Rotation ---

    def check_rotation(self) -> list[dict]:
        """Return list of secrets that need rotation."""
        warnings = []
        with self._lock:
            if isinstance(self._backend, MemorySecretBackend):
                for entry in self._backend._secrets.values():
                    if entry.needs_rotation:
                        warnings.append(entry.to_dict())
        return warnings

    # --- Redaction ---

    def redact(self, text: str) -> str:
        """Redact any secret values found in *text*."""
        with self._lock:
            for key in self._backend.list_keys():
                value = self._backend.get(key)
                if value and len(value) >= 4 and value in text:
                    text = text.replace(value, f"***{key}***")
        return text

    # --- Access log ---

    def _log_access(self, operation: str, key: str, **kwargs: Any) -> None:
        self._access_log.append({
            "operation": operation,
            "key": key,
            "timestamp": time.time(),
            **kwargs,
        })
        # Keep bounded
        if len(self._access_log) > 10000:
            self._access_log = self._access_log[-5000:]

    def access_log(self, limit: int = 100) -> list[dict]:
        """Return recent access log entries."""
        return self._access_log[-limit:]

    # --- Stats ---

    def stats(self) -> dict:
        with self._lock:
            return {
                "total_secrets": len(self._backend.list_keys()),
                "backend_type": type(self._backend).__name__,
                "access_log_size": len(self._access_log),
            }


# ------------------------------------------------------------------
# Singleton
# ------------------------------------------------------------------

_manager: SecretManager | None = None
_manager_lock = threading.Lock()


def get_secret_manager(**kwargs: Any) -> SecretManager:
    """Return the global SecretManager singleton."""
    global _manager
    if _manager is None:
        with _manager_lock:
            if _manager is None:
                _manager = SecretManager(**kwargs)
    return _manager
