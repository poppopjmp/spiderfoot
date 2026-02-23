"""Tests for spiderfoot.db_migrate."""
from __future__ import annotations

import os
import pytest
if not os.environ.get('SF_POSTGRES_DSN'):
    pytest.skip('PostgreSQL not available (SF_POSTGRES_DSN not set)', allow_module_level=True)

import tempfile
import unittest

from spiderfoot.db_migrate import (
    AppliedMigration,
    DbDialect,
    InMemoryDbAdapter,
    MigrationDirection,
    MigrationError,
    MigrationManager,
    MigrationPlan,
    MigrationRecord,
    MigrationStatus,
    PostgresAdapter,
)


class TestMigrationRecord(unittest.TestCase):
    def test_to_dict(self):
        r = MigrationRecord(version=1, name="init", description="Initial")
        d = r.to_dict()
        self.assertEqual(d["version"], 1)
        self.assertEqual(d["name"], "init")


class TestAppliedMigration(unittest.TestCase):
    def test_to_dict(self):
        a = AppliedMigration(
            version=1, name="init", checksum="abc", execution_time_ms=12.345
        )
        d = a.to_dict()
        self.assertEqual(d["execution_time_ms"], 12.35)


class TestMigrationPlan(unittest.TestCase):
    def test_count(self):
        plan = MigrationPlan(
            direction=MigrationDirection.UP,
            steps=[
                MigrationRecord(version=1, name="a"),
                MigrationRecord(version=2, name="b"),
            ],
        )
        self.assertEqual(plan.count, 2)

    def test_to_dict(self):
        plan = MigrationPlan(direction=MigrationDirection.DOWN, dry_run=True)
        d = plan.to_dict()
        self.assertEqual(d["direction"], "down")
        self.assertTrue(d["dry_run"])


class TestMigrationManagerWithPostgres(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test.db")
        self.migrations_dir = os.path.join(self.tmpdir, "migrations")
        os.makedirs(self.migrations_dir)

        # Create migration files
        self._write_migration(1, "create_users", """
description = "Create users table"

def upgrade(db, dialect):
    db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")

def downgrade(db, dialect):
    db.execute("DROP TABLE IF EXISTS users")
""")
        self._write_migration(2, "add_email", """
description = "Add email column"

def upgrade(db, dialect):
    db.execute("ALTER TABLE users ADD COLUMN email TEXT")

def downgrade(db, dialect):
    pass
""")

        self.db = PostgresAdapter(self.db_path)
        self.mgr = MigrationManager(
            db=self.db,
            migrations_dir=self.migrations_dir,
        )

    def _write_migration(self, version, name, content):
        fpath = os.path.join(self.migrations_dir, f"{version:04d}_{name}.py")
        with open(fpath, "w") as f:
            f.write(content)

    def tearDown(self):
        self.db.close()
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_discover_migrations(self):
        available = self.mgr.available_migrations()
        self.assertEqual(len(available), 2)
        self.assertEqual(available[0].version, 1)

    def test_current_version_initial(self):
        self.assertEqual(self.mgr.current_version(), 0)

    def test_pending_migrations(self):
        pending = self.mgr.pending_migrations()
        self.assertEqual(len(pending), 2)

    def test_is_up_to_date(self):
        self.assertFalse(self.mgr.is_up_to_date())

    def test_plan_upgrade(self):
        plan = self.mgr.plan_upgrade()
        self.assertEqual(plan.direction, MigrationDirection.UP)
        self.assertEqual(plan.count, 2)

    def test_plan_upgrade_target(self):
        plan = self.mgr.plan_upgrade(target_version=1)
        self.assertEqual(plan.count, 1)

    def test_upgrade_all(self):
        results = self.mgr.upgrade()
        self.assertEqual(len(results), 2)
        self.assertEqual(self.mgr.current_version(), 2)
        self.assertTrue(self.mgr.is_up_to_date())

    def test_upgrade_step(self):
        self.mgr.upgrade(target_version=1)
        self.assertEqual(self.mgr.current_version(), 1)
        self.assertFalse(self.mgr.is_up_to_date())

    def test_downgrade(self):
        self.mgr.upgrade()
        self.assertEqual(self.mgr.current_version(), 2)
        self.mgr.downgrade(target_version=0)
        self.assertEqual(self.mgr.current_version(), 0)

    def test_applied_migrations(self):
        self.mgr.upgrade()
        applied = self.mgr.applied_migrations()
        self.assertEqual(len(applied), 2)
        self.assertGreater(applied[0].applied_at, 0)

    def test_dry_run(self):
        plan = self.mgr.plan_upgrade(dry_run=True)
        results = self.mgr.execute_plan(plan)
        self.assertEqual(len(results), 2)
        # But nothing actually applied
        self.assertEqual(self.mgr.current_version(), 0)

    def test_generate(self):
        fpath = self.mgr.generate("add_roles", description="Add roles table")
        self.assertTrue(os.path.exists(fpath))
        self.assertIn("0003", os.path.basename(fpath))

    def test_validate_checksums_ok(self):
        self.mgr.upgrade()
        warnings = self.mgr.validate_checksums()
        self.assertEqual(len(warnings), 0)

    def test_on_migration_callback(self):
        results = []
        self.mgr.on_migration(lambda m: results.append(m))
        self.mgr.upgrade()
        self.assertEqual(len(results), 2)

    def test_stats(self):
        s = self.mgr.stats()
        self.assertEqual(s["total_available"], 2)
        self.assertEqual(s["total_pending"], 2)
        self.assertFalse(s["is_up_to_date"])

    def test_failed_migration(self):
        self._write_migration(3, "bad_migration", """
description = "This will fail"

def upgrade(db, dialect):
    raise RuntimeError("intentional failure")

def downgrade(db, dialect):
    pass
""")
        mgr2 = MigrationManager(
            db=self.db,
            migrations_dir=self.migrations_dir,
        )
        mgr2.upgrade(target_version=2)
        with self.assertRaises(MigrationError):
            mgr2.upgrade()


class TestInMemoryAdapter(unittest.TestCase):
    def test_sql_log(self):
        db = InMemoryDbAdapter()
        db.execute("CREATE TABLE x (id INT)")
        db.commit()
        self.assertEqual(len(db.sql_log), 2)

    def test_fetchall_empty(self):
        db = InMemoryDbAdapter()
        self.assertEqual(db.fetchall("SELECT 1"), [])

    def test_fetchone_none(self):
        db = InMemoryDbAdapter()
        self.assertIsNone(db.fetchone("SELECT 1"))


if __name__ == "__main__":
    unittest.main()
