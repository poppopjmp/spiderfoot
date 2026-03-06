# -------------------------------------------------------------------------------
# Name:         Steps 110-120 Security Tests (Checkpoint 6)
# Purpose:      Verify SQL hardening, pagination caps, upload validation,
#               secrets check, input validation, response filtering, error
#               standardisation, and dependency audit configuration.
#
# Created:      2025-07-17
# Licence:      MIT
# -------------------------------------------------------------------------------
"""
Checkpoint 6 — Tests for Steps 110-120 security hardening.

Coverage:
  - Steps 110-111: SQL identifier injection prevention (PartitionManager)
  - Step 112: API pagination limit capping
  - Step 113: File upload validation (size, type, extension, filename)
  - Step 114: Startup secrets checker (insecure defaults detection)
  - Step 115: Input length validation helpers
  - Step 116: Response data filtering (strip internal fields)
  - Step 117: API error standardisation
  - Step 118: Dependency audit config existence
"""
from __future__ import annotations

import os
import re
import sys
import json
import pytest
from unittest.mock import MagicMock, patch

# Ensure project root is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")


# ====================================================================== #
# Steps 110-111: SQL Identifier Injection Prevention                     #
# ====================================================================== #

class TestPartitionManagerSecurity:
    """Verify PartitionManager validates scan IDs and uses safe SQL."""

    def _make_pm(self):
        from spiderfoot.db.db_performance import PartitionManager
        conn = MagicMock()
        cursor = MagicMock()
        conn.cursor.return_value = cursor
        cursor.fetchone.return_value = None  # partition doesn't exist
        return PartitionManager(conn), cursor

    def test_valid_uuid_accepted(self):
        pm, _ = self._make_pm()
        pm._validate_scan_id("550e8400-e29b-41d4-a716-446655440000")

    def test_short_hex_accepted(self):
        pm, _ = self._make_pm()
        pm._validate_scan_id("abc123")

    def test_empty_rejected(self):
        pm, _ = self._make_pm()
        with pytest.raises(ValueError, match="Invalid scan_id"):
            pm._validate_scan_id("")

    def test_sql_injection_rejected(self):
        pm, _ = self._make_pm()
        with pytest.raises(ValueError, match="Invalid scan_id"):
            pm._validate_scan_id("'; DROP TABLE users; --")

    def test_path_traversal_rejected(self):
        pm, _ = self._make_pm()
        with pytest.raises(ValueError, match="Invalid scan_id"):
            pm._validate_scan_id("../../etc/passwd")

    def test_long_string_rejected(self):
        pm, _ = self._make_pm()
        with pytest.raises(ValueError, match="Invalid scan_id"):
            pm._validate_scan_id("a" * 65)

    def test_unicode_rejected(self):
        pm, _ = self._make_pm()
        with pytest.raises(ValueError, match="Invalid scan_id"):
            pm._validate_scan_id("scan-🎯-id")

    def test_partition_name_safe(self):
        from spiderfoot.db.db_performance import PartitionManager
        name = PartitionManager.partition_name("550e8400-e29b-41d4-a716-446655440000")
        assert name == "tbl_scan_results_550e8400_e29b_41d4_a716_446655440000"

    def test_ensure_partition_validates(self):
        pm, _ = self._make_pm()
        with pytest.raises(ValueError, match="Invalid scan_id"):
            pm.ensure_partition("'; DROP TABLE --")

    def test_drop_partition_validates(self):
        pm, _ = self._make_pm()
        with pytest.raises(ValueError, match="Invalid scan_id"):
            pm.drop_partition("invalid chars!")


class TestVacuumAnalyzeSecurity:
    """Verify VacuumAnalyze only allows safe table names."""

    def test_analyze_only_allows_known_tables(self):
        from spiderfoot.db.db_performance import VacuumAnalyze
        conn = MagicMock()
        va = VacuumAnalyze(conn)
        with pytest.raises(ValueError, match="not in allow-list"):
            va.analyze_only("users; DROP TABLE --")

    def test_analyze_only_accepts_valid_table(self):
        from spiderfoot.db.db_performance import VacuumAnalyze
        conn = MagicMock()
        va = VacuumAnalyze(conn)
        # Should not raise (execution may fail because of mock, but validation passes)
        try:
            va.analyze_only("tbl_scan_results")
        except Exception as e:
            # Mock connection errors are fine — we just care validation passed
            assert "not in allow-list" not in str(e)


# ====================================================================== #
# Step 112: Pagination Limit Capping                                     #
# ====================================================================== #

class TestPaginationLimits:
    """Verify pagination enforces MAX_PAGE_SIZE."""

    def test_max_page_size_enforced(self):
        from spiderfoot.api.pagination import PaginationParams
        # Create with excessive page_size
        p = object.__new__(PaginationParams)
        p.__init__(page=1, page_size=9999)
        assert p.page_size <= 1000

    def test_min_page_size_enforced(self):
        from spiderfoot.api.pagination import PaginationParams
        p = object.__new__(PaginationParams)
        p.__init__(page=1, page_size=0)
        assert p.page_size >= 1

    def test_negative_offset_rejected(self):
        from spiderfoot.api.pagination import make_params
        p = make_params(page=1, page_size=50)
        assert p.offset >= 0

    def test_make_params_caps_page_size(self):
        from spiderfoot.api.pagination import make_params
        p = make_params(page_size=5000)
        assert p.page_size == 1000


# ====================================================================== #
# Step 113: File Upload Validation                                       #
# ====================================================================== #

class TestUploadSecurity:
    """Verify upload validation — sizes, types, extensions, filenames."""

    def test_sanitize_strips_path(self):
        from spiderfoot.security.upload_validation import sanitize_filename
        assert sanitize_filename("../../etc/passwd") == "passwd"

    def test_sanitize_null_bytes(self):
        from spiderfoot.security.upload_validation import sanitize_filename
        result = sanitize_filename("file\x00.txt")
        assert "\x00" not in result

    def test_sanitize_empty(self):
        from spiderfoot.security.upload_validation import sanitize_filename
        assert sanitize_filename(None) == "upload"
        assert sanitize_filename("") == "upload"

    def test_sanitize_long_filename(self):
        from spiderfoot.security.upload_validation import sanitize_filename
        long = "a" * 300 + ".pdf"
        result = sanitize_filename(long)
        assert len(result) <= 255

    def test_validate_blocked_extension(self):
        from spiderfoot.security.upload_validation import validate_extension
        assert validate_extension("malware.exe") is not None
        assert validate_extension("script.ps1") is not None
        assert validate_extension("shell.sh") is not None

    def test_validate_safe_extension(self):
        from spiderfoot.security.upload_validation import validate_extension
        assert validate_extension("document.pdf") is None
        assert validate_extension("data.csv") is None

    def test_validate_content_type_allowed(self):
        from spiderfoot.security.upload_validation import validate_content_type
        assert validate_content_type("application/pdf") is None
        assert validate_content_type("text/plain") is None

    def test_validate_content_type_blocked(self):
        from spiderfoot.security.upload_validation import validate_content_type
        assert validate_content_type("application/x-executable") is not None

    def test_validate_content_type_missing(self):
        from spiderfoot.security.upload_validation import validate_content_type
        assert validate_content_type(None) is not None

    def test_validate_upload_too_large(self):
        from spiderfoot.security.upload_validation import validate_upload
        _, err = validate_upload("file.pdf", "application/pdf", 200 * 1024 * 1024)
        assert err is not None
        assert "large" in err.lower()

    def test_validate_upload_empty(self):
        from spiderfoot.security.upload_validation import validate_upload
        _, err = validate_upload("file.pdf", "application/pdf", 0)
        assert err is not None

    def test_validate_upload_success(self):
        from spiderfoot.security.upload_validation import validate_upload
        name, err = validate_upload("report.pdf", "application/pdf", 1024)
        assert err is None
        assert name == "report.pdf"

    def test_validate_upload_exe_blocked(self):
        from spiderfoot.security.upload_validation import validate_upload
        # octet-stream is now blocked; test that an exe with a permitted
        # content type still fails on extension check
        _, err = validate_upload("trojan.exe", "application/pdf", 1024)
        assert err is not None
        assert ".exe" in err

    def test_validate_upload_octet_stream_blocked(self):
        from spiderfoot.security.upload_validation import validate_upload
        _, err = validate_upload("data.bin", "application/octet-stream", 1024)
        assert err is not None
        assert "not permitted" in err


# ====================================================================== #
# Step 114: Startup Secrets Checker                                      #
# ====================================================================== #

class TestStartupSecretsCheck:
    """Verify insecure default detection."""

    def test_detects_default_jwt_secret(self):
        from spiderfoot.security.startup_check import check_startup_secrets
        with patch.dict(
            os.environ,
            {"SF_JWT_SECRET": "change-me-in-production-please"},
            clear=False,
        ):
            warnings = check_startup_secrets(mode="development", fail_in_production=False)
            assert any("SF_JWT_SECRET" in w for w in warnings)

    def test_detects_default_postgres_password(self):
        from spiderfoot.security.startup_check import check_startup_secrets
        with patch.dict(
            os.environ,
            {"POSTGRES_PASSWORD": "changeme"},
            clear=False,
        ):
            warnings = check_startup_secrets(mode="development", fail_in_production=False)
            assert any("POSTGRES_PASSWORD" in w for w in warnings)

    def test_detects_short_secret(self):
        from spiderfoot.security.startup_check import check_startup_secrets
        with patch.dict(
            os.environ,
            {"SF_JWT_SECRET": "short"},
            clear=False,
        ):
            warnings = check_startup_secrets(mode="development", fail_in_production=False)
            assert any("WEAK SECRET" in w and "SF_JWT_SECRET" in w for w in warnings)

    def test_strong_secret_no_warning(self):
        from spiderfoot.security.startup_check import check_startup_secrets
        with patch.dict(
            os.environ,
            {
                "SF_JWT_SECRET": "a" * 64,
                "POSTGRES_PASSWORD": "x" * 32,
            },
            clear=False,
        ):
            warnings = check_startup_secrets(mode="development", fail_in_production=False)
            jwt_warnings = [w for w in warnings if "SF_JWT_SECRET" in w]
            pg_warnings = [w for w in warnings if "POSTGRES_PASSWORD" in w]
            assert len(jwt_warnings) == 0
            assert len(pg_warnings) == 0

    def test_production_mode_would_exit(self):
        from spiderfoot.security.startup_check import check_startup_secrets
        with patch.dict(
            os.environ,
            {"SF_ADMIN_PASSWORD": "admin"},
            clear=False,
        ):
            with pytest.raises(SystemExit):
                check_startup_secrets(mode="production", fail_in_production=True)


# ====================================================================== #
# Step 115: Input Length Validation                                      #
# ====================================================================== #

class TestInputValidation:
    """Verify input length validation constants and helpers."""

    def test_max_target_length_defined(self):
        from spiderfoot.security.input_validation import MAX_TARGET_LENGTH
        assert MAX_TARGET_LENGTH == 2048

    def test_max_batch_targets_defined(self):
        from spiderfoot.security.input_validation import MAX_BATCH_TARGETS
        assert MAX_BATCH_TARGETS == 500

    def test_validate_string_length_ok(self):
        from spiderfoot.security.input_validation import validate_string_length
        result = validate_string_length("hello", "field", 100)
        assert result == "hello"

    def test_validate_string_length_too_long(self):
        from spiderfoot.security.input_validation import validate_string_length
        with pytest.raises(ValueError, match="at most"):
            validate_string_length("x" * 300, "field", 255)

    def test_validate_string_length_too_short(self):
        from spiderfoot.security.input_validation import validate_string_length
        with pytest.raises(ValueError, match="at least"):
            validate_string_length("", "field", 100, min_length=1)

    def test_validate_batch_targets_too_many(self):
        from spiderfoot.security.input_validation import validate_batch_targets
        targets = [f"target-{i}.example.com" for i in range(600)]
        with pytest.raises(ValueError, match="Too many"):
            validate_batch_targets(targets)

    def test_validate_batch_targets_deduplicates(self):
        from spiderfoot.security.input_validation import validate_batch_targets
        result = validate_batch_targets(["a.com", "b.com", "a.com", "  ", "b.com"])
        assert result == ["a.com", "b.com"]

    def test_validate_tags_caps_count(self):
        from spiderfoot.security.input_validation import validate_tags, MAX_TAGS_COUNT
        tags = [f"tag-{i}" for i in range(100)]
        result = validate_tags(tags)
        assert len(result) <= MAX_TAGS_COUNT

    def test_validate_tags_deduplicates(self):
        from spiderfoot.security.input_validation import validate_tags
        result = validate_tags(["Test", "test", "TEST", "other"])
        assert len(result) == 2  # "Test" and "other"


# ====================================================================== #
# Step 116: Response Data Filtering                                      #
# ====================================================================== #

class TestResponseFilter:
    """Verify sensitive fields are stripped from API responses."""

    def test_strips_password_hash(self):
        from spiderfoot.api.response_filter import strip_internal_fields
        data = {"id": "1", "username": "admin", "password_hash": "bcrypt$..."}
        result = strip_internal_fields(data)
        assert "password_hash" not in result
        assert result["username"] == "admin"

    def test_strips_password(self):
        from spiderfoot.api.response_filter import strip_internal_fields
        data = {"id": "1", "password": "secret123"}
        result = strip_internal_fields(data)
        assert "password" not in result

    def test_redacts_api_key(self):
        from spiderfoot.api.response_filter import strip_internal_fields
        data = {"id": "1", "api_key": "sk-abc123xyz"}
        result = strip_internal_fields(data)
        assert result["api_key"] == "[REDACTED]"

    def test_redacts_client_secret(self):
        from spiderfoot.api.response_filter import strip_internal_fields
        data = {"client_secret": "very-secret"}
        result = strip_internal_fields(data)
        assert result["client_secret"] == "[REDACTED]"

    def test_preserves_safe_fields(self):
        from spiderfoot.api.response_filter import strip_internal_fields
        data = {"id": "1", "name": "test", "status": "active"}
        result = strip_internal_fields(data)
        assert result == data

    def test_recursive_stripping(self):
        from spiderfoot.api.response_filter import strip_internal_fields
        data = {
            "user": {
                "id": "1",
                "password": "hidden",
                "profile": {"name": "Alice"},
            }
        }
        result = strip_internal_fields(data)
        assert "password" not in result["user"]
        assert result["user"]["profile"]["name"] == "Alice"

    def test_strips_from_list(self):
        from spiderfoot.api.response_filter import strip_internal_fields
        data = [
            {"id": "1", "password": "a"},
            {"id": "2", "password": "b"},
        ]
        result = strip_internal_fields(data)
        assert all("password" not in item for item in result)

    def test_strips_database_internals(self):
        from spiderfoot.api.response_filter import strip_internal_fields
        data = {"xmin": 123, "ctid": "(0,1)", "name": "test"}
        result = strip_internal_fields(data)
        assert "xmin" not in result
        assert "ctid" not in result
        assert result["name"] == "test"

    def test_strips_dsn(self):
        from spiderfoot.api.response_filter import strip_internal_fields
        data = {"dsn": "postgres://user:pass@host/db", "status": "ok"}
        result = strip_internal_fields(data)
        assert "dsn" not in result

    def test_does_not_mutate_original(self):
        from spiderfoot.api.response_filter import strip_internal_fields
        data = {"password": "secret", "name": "test"}
        _ = strip_internal_fields(data)
        assert "password" in data  # Original unchanged

    def test_max_depth_protection(self):
        from spiderfoot.api.response_filter import strip_internal_fields
        # Build deeply nested structure
        deep = {"password": "x"}
        current = deep
        for _ in range(30):
            current["nested"] = {"password": "x"}
            current = current["nested"]
        # Should not raise RecursionError
        result = strip_internal_fields(deep, max_depth=5)
        assert isinstance(result, dict)


# ====================================================================== #
# Step 117: API Error Standardisation                                    #
# ====================================================================== #

class TestErrorHandling:
    """Verify standardised error response structure."""

    def test_error_response_shape(self):
        from spiderfoot.api.error_handling import error_response
        resp = error_response(404, "NOT_FOUND", "Resource not found", request_id="req-123")
        body = json.loads(resp.body)
        assert body["error"]["code"] == "NOT_FOUND"
        assert body["error"]["message"] == "Resource not found"
        assert body["error"]["status"] == 404
        assert body["error"]["request_id"] == "req-123"

    def test_error_response_no_request_id(self):
        from spiderfoot.api.error_handling import error_response
        resp = error_response(500, "INTERNAL_ERROR", "Something broke")
        body = json.loads(resp.body)
        assert "request_id" not in body["error"]

    def test_error_response_with_details(self):
        from spiderfoot.api.error_handling import error_response
        resp = error_response(
            422, "VALIDATION_ERROR", "Bad input",
            details={"fields": [{"field": "name", "message": "too long"}]}
        )
        body = json.loads(resp.body)
        assert "details" in body["error"]
        assert body["error"]["details"]["fields"][0]["field"] == "name"

    def test_api_error_creates_exception(self):
        from spiderfoot.api.error_handling import api_error
        exc = api_error(404, "SCAN_NOT_FOUND", "No such scan")
        assert exc.status_code == 404
        assert exc.detail["code"] == "SCAN_NOT_FOUND"

    def test_error_codes_defined(self):
        from spiderfoot.api.error_handling import ErrorCode
        assert ErrorCode.INTERNAL_ERROR == "INTERNAL_ERROR"
        assert ErrorCode.VALIDATION_ERROR == "VALIDATION_ERROR"
        assert ErrorCode.NOT_FOUND == "NOT_FOUND"
        assert ErrorCode.RATE_LIMITED == "RATE_LIMITED"
        assert ErrorCode.SCAN_NOT_FOUND == "SCAN_NOT_FOUND"


# ====================================================================== #
# Step 118: Dependency Audit Configuration                               #
# ====================================================================== #

class TestDependencyAudit:
    """Verify dependency scanning configuration is in place."""

    def test_pip_audit_config_exists(self):
        path = os.path.join(ROOT, "pip-audit.toml")
        assert os.path.isfile(path), "pip-audit.toml missing"

    def test_audit_script_exists(self):
        path = os.path.join(ROOT, "scripts", "audit-deps.sh")
        assert os.path.isfile(path), "audit-deps.sh missing"

    def test_audit_script_runs_pip_audit(self):
        path = os.path.join(ROOT, "scripts", "audit-deps.sh")
        with open(path) as f:
            content = f.read()
        assert "pip-audit" in content

    def test_audit_script_runs_npm_audit(self):
        path = os.path.join(ROOT, "scripts", "audit-deps.sh")
        with open(path) as f:
            content = f.read()
        assert "npm audit" in content

    def test_requirements_pinned(self):
        """All requirements should have version pins."""
        path = os.path.join(ROOT, "requirements.txt")
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("-"):
                    continue
                assert (
                    "==" in line or ">=" in line or "<" in line
                ), f"Unpinned dependency: {line}"
