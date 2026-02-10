"""Database migration framework — version-controlled schema evolution.

Provides a lightweight, dependency-free migration system for SpiderFoot's
SQLite and PostgreSQL databases.  Features:

* **Sequential migrations** — numbered Python migration files with
  ``upgrade()`` and ``downgrade()`` functions.
* **Migration tracking** — ``_sf_migrations`` table records applied
  migrations with checksums.
* **Forward and rollback** — upgrade to latest/target or rollback to
  a specific version.
* **Dry-run mode** — preview SQL without applying.
* **Migration generation** — scaffold new migration files.
* **Checksum validation** — detect tampered migrations.
"""

from __future__ import annotations

import hashlib
import importlib.util
import logging
import os
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Protocol

log = logging.getLogger("spiderfoot.db_migrate")


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

class MigrationDirection(Enum):
    UP = "up"
    DOWN = "down"


class MigrationStatus(Enum):
    PENDING = "pending"
    APPLIED = "applied"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


class DbDialect(Enum):
    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"


@dataclass
class MigrationRecord:
    """Represents a single migration file."""

    version: int
    name: str
    description: str = ""
    checksum: str = ""
    filepath: str = ""
    upgrade_fn: Callable | None = None
    downgrade_fn: Callable | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "name": self.name,
            "description": self.description,
            "checksum": self.checksum,
            "filepath": self.filepath,
        }


@dataclass
class AppliedMigration:
    """A migration that has been applied to the database."""

    version: int
    name: str
    checksum: str
    applied_at: float = 0.0
    execution_time_ms: float = 0.0
    direction: str = "up"

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "name": self.name,
            "checksum": self.checksum,
            "applied_at": self.applied_at,
            "execution_time_ms": round(self.execution_time_ms, 2),
            "direction": self.direction,
        }


@dataclass
class MigrationPlan:
    """A set of migrations to apply."""

    direction: MigrationDirection
    steps: list[MigrationRecord] = field(default_factory=list)
    dry_run: bool = False
    warnings: list[str] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.steps)

    def to_dict(self) -> dict[str, Any]:
        return {
            "direction": self.direction.value,
            "steps": [s.to_dict() for s in self.steps],
            "count": self.count,
            "dry_run": self.dry_run,
            "warnings": self.warnings,
        }


# ---------------------------------------------------------------------------
# Database adapter protocol
# ---------------------------------------------------------------------------

class DbAdapter(Protocol):
    """Minimal database interface for migrations."""

    def execute(self, sql: str, params: tuple | None = None) -> None: ...
    def fetchall(self, sql: str, params: tuple | None = None) -> list[tuple]: ...
    def fetchone(self, sql: str, params: tuple | None = None) -> tuple | None: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...


class InMemoryDbAdapter:
    """Simple in-memory adapter for testing."""

    def __init__(self) -> None:
        self._tables: dict[str, list[dict]] = {}
        self._log: list[str] = []

    def execute(self, sql: str, params: tuple | None = None) -> None:
        self._log.append(sql)

    def fetchall(self, sql: str, params: tuple | None = None) -> list[tuple]:
        return []

    def fetchone(self, sql: str, params: tuple | None = None) -> tuple | None:
        return None

    def commit(self) -> None:
        self._log.append("COMMIT")

    def rollback(self) -> None:
        self._log.append("ROLLBACK")

    @property
    def sql_log(self) -> list[str]:
        return list(self._log)


class SqliteAdapter:
    """SQLite database adapter."""

    def __init__(self, db_path: str) -> None:
        import sqlite3
        self._conn = sqlite3.connect(db_path)

    def execute(self, sql: str, params: tuple | None = None) -> None:
        self._conn.execute(sql, params or ())

    def fetchall(self, sql: str, params: tuple | None = None) -> list[tuple]:
        return self._conn.execute(sql, params or ()).fetchall()

    def fetchone(self, sql: str, params: tuple | None = None) -> tuple | None:
        return self._conn.execute(sql, params or ()).fetchone()

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def close(self) -> None:
        self._conn.close()


# ---------------------------------------------------------------------------
# Migration manager
# ---------------------------------------------------------------------------

_MIGRATION_FILE_PATTERN = re.compile(r"^(\d{4})_(.+)\.py$")
_TRACKING_TABLE = "_sf_migrations"

_CREATE_TRACKING_SQL = f"""
CREATE TABLE IF NOT EXISTS {_TRACKING_TABLE} (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    checksum TEXT NOT NULL,
    applied_at REAL NOT NULL,
    execution_time_ms REAL DEFAULT 0,
    direction TEXT DEFAULT 'up'
)
"""


class MigrationManager:
    """Manage database schema migrations.

    Usage::

        mgr = MigrationManager(
            db=SqliteAdapter("spiderfoot.db"),
            migrations_dir="migrations/",
        )
        plan = mgr.plan_upgrade()
        if plan.count > 0:
            mgr.execute_plan(plan)
    """

    def __init__(
        self,
        db: DbAdapter,
        migrations_dir: str = "migrations",
        dialect: DbDialect = DbDialect.SQLITE,
    ) -> None:
        self._db = db
        self._dir = migrations_dir
        self._dialect = dialect
        self._migrations: dict[int, MigrationRecord] = {}
        self._callbacks: list[Callable[[AppliedMigration], None]] = []

        self._ensure_tracking_table()
        self._load_migrations()

    # -------------------------------------------------------------------
    # Setup
    # -------------------------------------------------------------------

    def _ensure_tracking_table(self) -> None:
        try:
            self._db.execute(_CREATE_TRACKING_SQL)
            self._db.commit()
        except Exception as e:
            log.debug("Could not create tracking table: %s", e)

    def _load_migrations(self) -> None:
        """Discover migration files in the migrations directory."""
        if not os.path.isdir(self._dir):
            return

        for fname in sorted(os.listdir(self._dir)):
            match = _MIGRATION_FILE_PATTERN.match(fname)
            if not match:
                continue

            version = int(match.group(1))
            name = match.group(2)
            fpath = os.path.join(self._dir, fname)

            checksum = self._file_checksum(fpath)

            # Import the module
            upgrade_fn = None
            downgrade_fn = None
            description = ""
            try:
                spec = importlib.util.spec_from_file_location(
                    f"migration_{version}", fpath
                )
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    upgrade_fn = getattr(mod, "upgrade", None)
                    downgrade_fn = getattr(mod, "downgrade", None)
                    description = getattr(mod, "description", name.replace("_", " "))
            except Exception as e:
                log.warning("Failed to load migration %s: %s", fname, e)

            self._migrations[version] = MigrationRecord(
                version=version,
                name=name,
                description=description,
                checksum=checksum,
                filepath=fpath,
                upgrade_fn=upgrade_fn,
                downgrade_fn=downgrade_fn,
            )

    @staticmethod
    def _file_checksum(path: str) -> str:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()[:16]

    # -------------------------------------------------------------------
    # State query
    # -------------------------------------------------------------------

    def current_version(self) -> int:
        """Get the highest applied migration version, or 0."""
        try:
            row = self._db.fetchone(
                f"SELECT MAX(version) FROM {_TRACKING_TABLE} WHERE direction = 'up'"
            )
            return row[0] if row and row[0] is not None else 0
        except Exception:
            return 0

    def applied_migrations(self) -> list[AppliedMigration]:
        """Return all applied migrations."""
        try:
            rows = self._db.fetchall(
                f"SELECT version, name, checksum, applied_at, execution_time_ms, direction "
                f"FROM {_TRACKING_TABLE} ORDER BY version"
            )
            return [
                AppliedMigration(
                    version=r[0], name=r[1], checksum=r[2],
                    applied_at=r[3], execution_time_ms=r[4],
                    direction=r[5],
                )
                for r in rows
            ]
        except Exception:
            return []

    def pending_migrations(self) -> list[MigrationRecord]:
        """Return migrations that have not yet been applied."""
        current = self.current_version()
        return sorted(
            [m for v, m in self._migrations.items() if v > current],
            key=lambda m: m.version,
        )

    def available_migrations(self) -> list[MigrationRecord]:
        """Return all discovered migrations."""
        return sorted(self._migrations.values(), key=lambda m: m.version)

    def is_up_to_date(self) -> bool:
        return len(self.pending_migrations()) == 0

    # -------------------------------------------------------------------
    # Planning
    # -------------------------------------------------------------------

    def plan_upgrade(
        self,
        target_version: int | None = None,
        dry_run: bool = False,
    ) -> MigrationPlan:
        """Create a plan to upgrade to ``target_version`` (or latest)."""
        self.current_version()  # validate current state
        pending = self.pending_migrations()
        warnings: list[str] = []

        if target_version is not None:
            pending = [m for m in pending if m.version <= target_version]

        # Checksum validation
        for m in pending:
            if not m.upgrade_fn:
                warnings.append(
                    f"Migration {m.version}_{m.name} has no upgrade() function"
                )

        return MigrationPlan(
            direction=MigrationDirection.UP,
            steps=pending,
            dry_run=dry_run,
            warnings=warnings,
        )

    def plan_downgrade(
        self,
        target_version: int = 0,
        dry_run: bool = False,
    ) -> MigrationPlan:
        """Create a plan to downgrade to ``target_version``."""
        current = self.current_version()
        warnings: list[str] = []

        # Migrations to roll back (in reverse order)
        to_rollback = sorted(
            [m for v, m in self._migrations.items()
             if v <= current and v > target_version],
            key=lambda m: m.version,
            reverse=True,
        )

        for m in to_rollback:
            if not m.downgrade_fn:
                warnings.append(
                    f"Migration {m.version}_{m.name} has no downgrade() function"
                )

        return MigrationPlan(
            direction=MigrationDirection.DOWN,
            steps=to_rollback,
            dry_run=dry_run,
            warnings=warnings,
        )

    # -------------------------------------------------------------------
    # Execution
    # -------------------------------------------------------------------

    def execute_plan(self, plan: MigrationPlan) -> list[AppliedMigration]:
        """Execute a migration plan, returning applied migrations."""
        results: list[AppliedMigration] = []

        for migration in plan.steps:
            fn = (migration.upgrade_fn if plan.direction == MigrationDirection.UP
                  else migration.downgrade_fn)

            if fn is None:
                log.warning(
                    "Skipping migration %d_%s: no %s function",
                    migration.version, migration.name, plan.direction.value,
                )
                continue

            if plan.dry_run:
                results.append(AppliedMigration(
                    version=migration.version,
                    name=migration.name,
                    checksum=migration.checksum,
                    direction=plan.direction.value,
                ))
                continue

            start = time.time()
            try:
                fn(self._db, self._dialect)
                elapsed_ms = (time.time() - start) * 1000

                now = time.time()
                self._record_migration(
                    migration, plan.direction, now, elapsed_ms
                )
                self._db.commit()

                applied = AppliedMigration(
                    version=migration.version,
                    name=migration.name,
                    checksum=migration.checksum,
                    applied_at=now,
                    execution_time_ms=elapsed_ms,
                    direction=plan.direction.value,
                )
                results.append(applied)

                for cb in self._callbacks:
                    try:
                        cb(applied)
                    except Exception as e:
                        log.debug("migration callback cb(applied) failed: %s", e)

                log.info(
                    "Applied migration %d_%s (%s) in %.1fms",
                    migration.version, migration.name,
                    plan.direction.value, elapsed_ms,
                )

            except Exception as e:
                self._db.rollback()
                log.error(
                    "Migration %d_%s failed: %s",
                    migration.version, migration.name, e,
                )
                raise MigrationError(
                    f"Migration {migration.version}_{migration.name} failed: {e}"
                ) from e

        return results

    def upgrade(self, target_version: int | None = None) -> list[AppliedMigration]:
        """Shortcut: plan and execute upgrade."""
        plan = self.plan_upgrade(target_version)
        return self.execute_plan(plan)

    def downgrade(self, target_version: int = 0) -> list[AppliedMigration]:
        """Shortcut: plan and execute downgrade."""
        plan = self.plan_downgrade(target_version)
        return self.execute_plan(plan)

    def _record_migration(
        self,
        migration: MigrationRecord,
        direction: MigrationDirection,
        applied_at: float,
        elapsed_ms: float,
    ) -> None:
        if direction == MigrationDirection.UP:
            self._db.execute(
                f"INSERT OR REPLACE INTO {_TRACKING_TABLE} "
                "(version, name, checksum, applied_at, execution_time_ms, direction) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (migration.version, migration.name, migration.checksum,
                 applied_at, elapsed_ms, "up"),
            )
        else:
            self._db.execute(
                f"DELETE FROM {_TRACKING_TABLE} WHERE version = ?",
                (migration.version,),
            )

    # -------------------------------------------------------------------
    # Generation
    # -------------------------------------------------------------------

    def generate(
        self,
        name: str,
        description: str = "",
    ) -> str:
        """Scaffold a new migration file.  Returns the file path."""
        os.makedirs(self._dir, exist_ok=True)

        # Next version number
        existing = list(self._migrations.keys())
        next_ver = (max(existing) + 1) if existing else 1

        # Sanitize name
        safe_name = re.sub(r"[^a-z0-9_]", "_", name.lower().strip())
        fname = f"{next_ver:04d}_{safe_name}.py"
        fpath = os.path.join(self._dir, fname)

        content = f'''"""Migration {next_ver:04d}: {description or name}"""

description = "{description or name}"


def upgrade(db, dialect):
    """Apply this migration."""
    # db.execute("ALTER TABLE ...")
    pass


def downgrade(db, dialect):
    """Reverse this migration."""
    # db.execute("DROP TABLE ...")
    pass
'''
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(content)

        # Register it
        self._migrations[next_ver] = MigrationRecord(
            version=next_ver,
            name=safe_name,
            description=description or name,
            checksum=self._file_checksum(fpath),
            filepath=fpath,
        )

        return fpath

    # -------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------

    def validate_checksums(self) -> list[str]:
        """Check applied migrations against on-disk checksums.

        Returns list of warning messages for mismatches.
        """
        warnings: list[str] = []
        applied = {m.version: m for m in self.applied_migrations()}

        for version, record in self._migrations.items():
            if version in applied:
                if applied[version].checksum != record.checksum:
                    warnings.append(
                        f"Migration {version}_{record.name}: checksum mismatch "
                        f"(applied={applied[version].checksum}, "
                        f"file={record.checksum})"
                    )
        return warnings

    # -------------------------------------------------------------------
    # Hooks
    # -------------------------------------------------------------------

    def on_migration(self, callback: Callable[[AppliedMigration], None]) -> None:
        self._callbacks.append(callback)

    # -------------------------------------------------------------------
    # Stats
    # -------------------------------------------------------------------

    def stats(self) -> dict[str, Any]:
        return {
            "current_version": self.current_version(),
            "total_available": len(self._migrations),
            "total_pending": len(self.pending_migrations()),
            "is_up_to_date": self.is_up_to_date(),
            "dialect": self._dialect.value,
            "migrations_dir": self._dir,
        }


class MigrationError(Exception):
    """Raised when a migration fails."""
    pass
