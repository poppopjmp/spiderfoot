"""
Tests for the Database Repository Pattern (Cycle 23).

Covers:
- AbstractRepository lifecycle (context manager, close, repr)
- ScanRepository CRUD operations + ScanRecord dataclass
- EventRepository delegation methods
- ConfigRepository get/set/clear
- RepositoryFactory creation + singleton lifecycle
- FastAPI Depends providers
- Service integration wiring
"""
from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, patch, PropertyMock

import pytest


# ---------------------------------------------------------------------------
# Helper: Fake DB handle
# ---------------------------------------------------------------------------

class FakeDbh:
    """Minimal SpiderFootDb stand-in with stub methods."""

    def __init__(self):
        self.closed = False
        self.calls = []

    def close(self):
        self.closed = True

    # Scan methods
    def scanInstanceCreate(self, scan_id, name, target):
        self.calls.append(("scanInstanceCreate", scan_id, name, target))

    def scanInstanceGet(self, scan_id):
        self.calls.append(("scanInstanceGet", scan_id))
        return ("id-1", "TestScan", "example.com", 1000.0, 1001.0, 1002.0, "FINISHED")

    def scanInstanceList(self):
        self.calls.append(("scanInstanceList",))
        return [
            ("id-1", "Scan1", "a.com", 1000.0, 1001.0, 1002.0, "FINISHED"),
            ("id-2", "Scan2", "b.com", 2000.0, 2001.0, 0, "RUNNING"),
        ]

    def scanInstanceSet(self, scan_id, started=None, ended=None, status=None):
        self.calls.append(("scanInstanceSet", scan_id, started, ended, status))

    def scanInstanceDelete(self, scan_id):
        self.calls.append(("scanInstanceDelete", scan_id))
        return True

    def scanConfigSet(self, scan_id, config_data):
        self.calls.append(("scanConfigSet", scan_id, config_data))

    def scanConfigGet(self, scan_id):
        self.calls.append(("scanConfigGet", scan_id))
        return {"key": "value"}

    def scanLogs(self, scan_id, limit=None, fromRowId=0, reverse=False):
        self.calls.append(("scanLogs", scan_id))
        return [("log1",), ("log2",)]

    def scanErrors(self, scan_id, limit=0):
        self.calls.append(("scanErrors", scan_id))
        return [("err1",)]

    # Event methods
    def scanEventStore(self, scan_id, event, truncateSize=0):
        self.calls.append(("scanEventStore", scan_id))

    def scanResultEvent(self, scan_id, eventType="ALL", srcModule=None, filterFp=False):
        self.calls.append(("scanResultEvent", scan_id, eventType))
        return [("result1",)]

    def scanResultEventUnique(self, scan_id, eventType="ALL", filterFp=False):
        self.calls.append(("scanResultEventUnique", scan_id))
        return [("unique1",)]

    def scanResultSummary(self, scan_id, by="type"):
        self.calls.append(("scanResultSummary", scan_id))
        return [("summary1",)]

    def scanResultHistory(self, scan_id):
        self.calls.append(("scanResultHistory", scan_id))
        return []

    def scanResultsUpdateFP(self, scan_id, result_hashes, fp_flag):
        self.calls.append(("scanResultsUpdateFP", scan_id))
        return True

    def scanElementSourcesDirect(self, scan_id, element_ids):
        self.calls.append(("scanElementSourcesDirect", scan_id))
        return [("src1",)]

    def scanElementSourcesAll(self, scan_id, element_ids):
        self.calls.append(("scanElementSourcesAll", scan_id))
        return [("src_all1",)]

    def scanElementChildrenDirect(self, scan_id, element_ids):
        self.calls.append(("scanElementChildrenDirect", scan_id))
        return [("child1",)]

    def scanElementChildrenAll(self, scan_id, element_ids):
        self.calls.append(("scanElementChildrenAll", scan_id))
        return [("child_all1",)]

    def search(self, criteria, filterFp=False):
        self.calls.append(("search",))
        return [("found1",)]

    def scanLogEvent(self, scan_id, classification, message, component):
        self.calls.append(("scanLogEvent", scan_id, classification))

    def scanLogEvents(self, batch):
        self.calls.append(("scanLogEvents", len(batch)))
        return True

    # Config methods
    def configSet(self, config_data):
        self.calls.append(("configSet",))

    def configGet(self):
        self.calls.append(("configGet",))
        return {"global_key": "global_value"}

    def configClear(self):
        self.calls.append(("configClear",))


# ===========================================================================
# AbstractRepository
# ===========================================================================

class TestAbstractRepository:
    """AbstractRepository lifecycle tests."""

    def test_init_with_dbh(self):
        from spiderfoot.db.repositories.base import AbstractRepository

        class ConcreteRepo(AbstractRepository):
            pass

        dbh = FakeDbh()
        repo = ConcreteRepo(dbh)
        assert repo.is_connected
        assert repo.dbh is dbh

    def test_init_without_dbh(self):
        from spiderfoot.db.repositories.base import AbstractRepository

        class ConcreteRepo(AbstractRepository):
            pass

        repo = ConcreteRepo()
        assert not repo.is_connected

    def test_dbh_raises_when_none(self):
        from spiderfoot.db.repositories.base import AbstractRepository

        class ConcreteRepo(AbstractRepository):
            pass

        repo = ConcreteRepo()
        with pytest.raises(RuntimeError, match="no database handle"):
            _ = repo.dbh

    def test_context_manager(self):
        from spiderfoot.db.repositories.base import AbstractRepository

        class ConcreteRepo(AbstractRepository):
            pass

        dbh = FakeDbh()
        with ConcreteRepo(dbh) as repo:
            assert repo.is_connected
        # After exit, handle is closed
        assert dbh.closed
        assert not repo.is_connected

    def test_close_is_idempotent(self):
        from spiderfoot.db.repositories.base import AbstractRepository

        class ConcreteRepo(AbstractRepository):
            pass

        dbh = FakeDbh()
        repo = ConcreteRepo(dbh)
        repo.close()
        repo.close()  # Should not raise
        assert not repo.is_connected

    def test_close_handles_exception(self):
        from spiderfoot.db.repositories.base import AbstractRepository

        class ConcreteRepo(AbstractRepository):
            pass

        dbh = MagicMock()
        dbh.close.side_effect = Exception("close error")
        repo = ConcreteRepo(dbh)
        repo.close()  # Should not raise
        assert not repo.is_connected

    def test_repr_connected(self):
        from spiderfoot.db.repositories.base import AbstractRepository

        class ConcreteRepo(AbstractRepository):
            pass

        repo = ConcreteRepo(FakeDbh())
        assert "connected" in repr(repo)
        assert "ConcreteRepo" in repr(repo)

    def test_repr_disconnected(self):
        from spiderfoot.db.repositories.base import AbstractRepository

        class ConcreteRepo(AbstractRepository):
            pass

        repo = ConcreteRepo()
        assert "disconnected" in repr(repo)


# ===========================================================================
# ScanRecord
# ===========================================================================

class TestScanRecord:
    """ScanRecord dataclass tests."""

    def test_from_row(self):
        from spiderfoot.db.repositories.scan_repository import ScanRecord

        row = ("id-1", "MyScan", "example.com", 1000.0, 1001.0, 1002.0, "FINISHED")
        rec = ScanRecord.from_row(row)
        assert rec.scan_id == "id-1"
        assert rec.name == "MyScan"
        assert rec.target == "example.com"
        assert rec.status == "FINISHED"
        assert rec.created == 1000.0
        assert rec.started == 1001.0
        assert rec.ended == 1002.0

    def test_from_row_with_none_timestamps(self):
        from spiderfoot.db.repositories.scan_repository import ScanRecord

        row = ("id-2", "Scan2", "b.com", None, None, None, "CREATED")
        rec = ScanRecord.from_row(row)
        assert rec.created == 0.0
        assert rec.started == 0.0
        assert rec.ended == 0.0

    def test_from_row_invalid(self):
        from spiderfoot.db.repositories.scan_repository import ScanRecord

        with pytest.raises(ValueError, match="Invalid scan row"):
            ScanRecord.from_row(("too", "short"))

    def test_from_row_none(self):
        from spiderfoot.db.repositories.scan_repository import ScanRecord

        with pytest.raises(ValueError, match="Invalid scan row"):
            ScanRecord.from_row(None)

    def test_to_dict(self):
        from spiderfoot.db.repositories.scan_repository import ScanRecord

        rec = ScanRecord(scan_id="id-1", name="S", target="t", status="RUNNING")
        d = rec.to_dict()
        assert d["scan_id"] == "id-1"
        assert d["status"] == "RUNNING"
        assert "name" in d
        assert "created" in d


# ===========================================================================
# ScanRepository
# ===========================================================================

class TestScanRepository:
    """ScanRepository delegation tests."""

    def _make_repo(self):
        from spiderfoot.db.repositories.scan_repository import ScanRepository
        return ScanRepository(FakeDbh())

    def test_create_scan(self):
        repo = self._make_repo()
        repo.create_scan("id-1", "Test", "example.com")
        assert ("scanInstanceCreate", "id-1", "Test", "example.com") in repo._dbh.calls

    def test_get_scan(self):
        repo = self._make_repo()
        rec = repo.get_scan("id-1")
        assert rec is not None
        assert rec.scan_id == "id-1"
        assert rec.name == "TestScan"

    def test_get_scan_not_found(self):
        from spiderfoot.db.repositories.scan_repository import ScanRepository
        dbh = FakeDbh()
        dbh.scanInstanceGet = lambda sid: None
        repo = ScanRepository(dbh)
        assert repo.get_scan("missing") is None

    def test_list_scans(self):
        repo = self._make_repo()
        scans = repo.list_scans()
        assert len(scans) == 2
        assert scans[0].scan_id == "id-1"
        assert scans[1].scan_id == "id-2"

    def test_list_scans_empty(self):
        from spiderfoot.db.repositories.scan_repository import ScanRepository
        dbh = FakeDbh()
        dbh.scanInstanceList = lambda: None
        repo = ScanRepository(dbh)
        assert repo.list_scans() == []

    def test_update_status(self):
        repo = self._make_repo()
        repo.update_status("id-1", "RUNNING", started=1000.0)
        assert ("scanInstanceSet", "id-1", 1000.0, None, "RUNNING") in repo._dbh.calls

    def test_delete_scan(self):
        repo = self._make_repo()
        assert repo.delete_scan("id-1") is True

    def test_set_config(self):
        repo = self._make_repo()
        repo.set_config("id-1", '{"key":"val"}')
        assert ("scanConfigSet", "id-1", '{"key":"val"}') in repo._dbh.calls

    def test_get_config(self):
        repo = self._make_repo()
        cfg = repo.get_config("id-1")
        assert cfg == {"key": "value"}

    def test_get_scan_log(self):
        repo = self._make_repo()
        logs = repo.get_scan_log("id-1", limit=10)
        assert len(logs) == 2

    def test_get_scan_errors(self):
        repo = self._make_repo()
        errs = repo.get_scan_errors("id-1")
        assert len(errs) == 1


# ===========================================================================
# EventRepository
# ===========================================================================

class TestEventRepository:
    """EventRepository delegation tests."""

    def _make_repo(self):
        from spiderfoot.db.repositories.event_repository import EventRepository
        return EventRepository(FakeDbh())

    def test_store_event(self):
        repo = self._make_repo()
        evt = MagicMock()
        repo.store_event("id-1", evt, truncate_size=1024)
        assert ("scanEventStore", "id-1") in repo._dbh.calls

    def test_get_results(self):
        repo = self._make_repo()
        results = repo.get_results("id-1", event_type="IP_ADDRESS")
        assert len(results) == 1
        assert ("scanResultEvent", "id-1", "IP_ADDRESS") in repo._dbh.calls

    def test_get_results_default(self):
        repo = self._make_repo()
        results = repo.get_results("id-1")
        assert ("scanResultEvent", "id-1", "ALL") in repo._dbh.calls

    def test_get_unique_results(self):
        repo = self._make_repo()
        results = repo.get_unique_results("id-1")
        assert len(results) == 1

    def test_get_result_summary(self):
        repo = self._make_repo()
        summary = repo.get_result_summary("id-1")
        assert len(summary) == 1

    def test_get_result_history(self):
        repo = self._make_repo()
        history = repo.get_result_history("id-1")
        assert isinstance(history, list)

    def test_update_false_positive(self):
        repo = self._make_repo()
        result = repo.update_false_positive("id-1", ["hash1"], 1)
        assert result is True

    def test_get_element_sources_direct(self):
        repo = self._make_repo()
        sources = repo.get_element_sources("id-1", ["elem1"])
        assert ("scanElementSourcesDirect", "id-1") in repo._dbh.calls

    def test_get_element_sources_recursive(self):
        repo = self._make_repo()
        sources = repo.get_element_sources("id-1", ["elem1"], recursive=True)
        assert ("scanElementSourcesAll", "id-1") in repo._dbh.calls

    def test_get_element_children_direct(self):
        repo = self._make_repo()
        children = repo.get_element_children("id-1", ["elem1"])
        assert ("scanElementChildrenDirect", "id-1") in repo._dbh.calls

    def test_get_element_children_recursive(self):
        repo = self._make_repo()
        children = repo.get_element_children("id-1", ["elem1"], recursive=True)
        assert ("scanElementChildrenAll", "id-1") in repo._dbh.calls

    def test_search(self):
        repo = self._make_repo()
        results = repo.search({"query": "test"}, filter_fp=True)
        assert len(results) == 1

    def test_log_event(self):
        repo = self._make_repo()
        repo.log_event("id-1", "INFO", "Test message", "sfp_test")
        assert ("scanLogEvent", "id-1", "INFO") in repo._dbh.calls

    def test_log_events_batch(self):
        repo = self._make_repo()
        result = repo.log_events_batch([("e1",), ("e2",)])
        assert result is True
        assert ("scanLogEvents", 2) in repo._dbh.calls


# ===========================================================================
# ConfigRepository
# ===========================================================================

class TestConfigRepository:
    """ConfigRepository delegation tests."""

    def _make_repo(self):
        from spiderfoot.db.repositories.config_repository import ConfigRepository
        return ConfigRepository(FakeDbh())

    def test_set_config(self):
        repo = self._make_repo()
        repo.set_config({"option": "val"})
        assert ("configSet",) in repo._dbh.calls

    def test_get_config(self):
        repo = self._make_repo()
        cfg = repo.get_config()
        assert cfg == {"global_key": "global_value"}

    def test_get_config_empty(self):
        from spiderfoot.db.repositories.config_repository import ConfigRepository
        dbh = FakeDbh()
        dbh.configGet = lambda: None
        repo = ConfigRepository(dbh)
        assert repo.get_config() == {}

    def test_clear_config(self):
        repo = self._make_repo()
        repo.clear_config()
        assert ("configClear",) in repo._dbh.calls


# ===========================================================================
# RepositoryFactory
# ===========================================================================

class TestRepositoryFactory:
    """RepositoryFactory creation + singleton tests."""

    def test_create_scan_repo(self):
        from spiderfoot.db.repositories.factory import RepositoryFactory
        factory = RepositoryFactory()
        dbh = FakeDbh()
        repo = factory.scan_repo(dbh=dbh)
        assert repo.is_connected
        assert repo._dbh is dbh

    def test_create_event_repo(self):
        from spiderfoot.db.repositories.factory import RepositoryFactory
        factory = RepositoryFactory()
        dbh = FakeDbh()
        repo = factory.event_repo(dbh=dbh)
        assert repo.is_connected

    def test_create_config_repo(self):
        from spiderfoot.db.repositories.factory import RepositoryFactory
        factory = RepositoryFactory()
        dbh = FakeDbh()
        repo = factory.config_repo(dbh=dbh)
        assert repo.is_connected

    def test_create_dbh_without_config(self):
        from spiderfoot.db.repositories.factory import RepositoryFactory
        factory = RepositoryFactory()
        # Without SpiderFootDb available, should raise RuntimeError
        with patch("spiderfoot.db.SpiderFootDb", side_effect=Exception("no db")):
            with pytest.raises(RuntimeError, match="Failed to create DB handle"):
                factory.create_dbh()

    def test_scan_repo_auto_creates_dbh(self):
        """When no dbh given, factory calls create_dbh()."""
        from spiderfoot.db.repositories.factory import RepositoryFactory
        factory = RepositoryFactory({"__database": ":memory:"})
        fake_dbh = FakeDbh()
        with patch.object(factory, "create_dbh", return_value=fake_dbh):
            repo = factory.scan_repo()
            assert repo.is_connected
            assert repo._dbh is fake_dbh

    def test_repr(self):
        from spiderfoot.db.repositories.factory import RepositoryFactory
        f1 = RepositoryFactory({"key": "val"})
        assert "config=yes" in repr(f1)
        f2 = RepositoryFactory()
        assert "config=no" in repr(f2)


class TestFactorySingleton:
    """Module-level singleton lifecycle tests."""

    def setup_method(self):
        from spiderfoot.db.repositories import factory
        factory._global_factory = None

    def teardown_method(self):
        from spiderfoot.db.repositories import factory
        factory._global_factory = None

    def test_init_and_get(self):
        from spiderfoot.db.repositories.factory import (
            init_repository_factory,
            get_repository_factory,
        )
        assert get_repository_factory() is None
        f = init_repository_factory({"key": "val"})
        assert f is not None
        assert get_repository_factory() is f

    def test_init_idempotent(self):
        from spiderfoot.db.repositories.factory import init_repository_factory
        f1 = init_repository_factory({"a": 1})
        f2 = init_repository_factory({"b": 2})
        assert f1 is f2  # Second call returns same instance

    def test_reset(self):
        from spiderfoot.db.repositories.factory import (
            init_repository_factory,
            get_repository_factory,
            reset_repository_factory,
        )
        init_repository_factory()
        assert get_repository_factory() is not None
        reset_repository_factory()
        assert get_repository_factory() is None

    def test_thread_safety(self):
        from spiderfoot.db.repositories.factory import (
            init_repository_factory,
            reset_repository_factory,
        )
        results = []

        def worker():
            f = init_repository_factory({"thread": True})
            results.append(id(f))

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All threads should get the same factory instance
        assert len(set(results)) == 1
        reset_repository_factory()


# ===========================================================================
# Package re-exports
# ===========================================================================

class TestPackageExports:
    """Verify __init__.py re-exports."""

    def test_all_exports(self):
        from spiderfoot.db import repositories
        assert hasattr(repositories, "AbstractRepository")
        assert hasattr(repositories, "ScanRepository")
        assert hasattr(repositories, "EventRepository")
        assert hasattr(repositories, "ConfigRepository")
        assert hasattr(repositories, "RepositoryFactory")
        assert hasattr(repositories, "get_repository_factory")
        assert hasattr(repositories, "init_repository_factory")
        assert hasattr(repositories, "reset_repository_factory")


# ===========================================================================
# FastAPI Depends Providers
# ===========================================================================

class TestDependsProviders:
    """Tests for the FastAPI Depends generator functions."""

    def setup_method(self):
        from spiderfoot.db.repositories import factory
        factory._global_factory = None

    def teardown_method(self):
        from spiderfoot.db.repositories import factory
        factory._global_factory = None

    def test_get_scan_repository_provider(self):
        from spiderfoot.api.dependencies import get_scan_repository
        from spiderfoot.db.repositories.factory import RepositoryFactory

        factory = RepositoryFactory()
        fake_dbh = FakeDbh()
        with patch.object(factory, "create_dbh", return_value=fake_dbh):
            with patch(
                "spiderfoot.db.repositories.factory.get_repository_factory",
                return_value=factory,
            ):
                gen = get_scan_repository()
                repo = next(gen)
                assert repo.is_connected
                # Cleanup
                try:
                    next(gen)
                except StopIteration:
                    pass
                assert not repo.is_connected

    def test_get_event_repository_provider(self):
        from spiderfoot.api.dependencies import get_event_repository
        from spiderfoot.db.repositories.factory import RepositoryFactory

        factory = RepositoryFactory()
        fake_dbh = FakeDbh()
        with patch.object(factory, "create_dbh", return_value=fake_dbh):
            with patch(
                "spiderfoot.db.repositories.factory.get_repository_factory",
                return_value=factory,
            ):
                gen = get_event_repository()
                repo = next(gen)
                assert repo.is_connected
                try:
                    next(gen)
                except StopIteration:
                    pass
                assert not repo.is_connected

    def test_get_config_repository_provider(self):
        from spiderfoot.api.dependencies import get_config_repository
        from spiderfoot.db.repositories.factory import RepositoryFactory

        factory = RepositoryFactory()
        fake_dbh = FakeDbh()
        with patch.object(factory, "create_dbh", return_value=fake_dbh):
            with patch(
                "spiderfoot.db.repositories.factory.get_repository_factory",
                return_value=factory,
            ):
                gen = get_config_repository()
                repo = next(gen)
                assert repo.is_connected
                try:
                    next(gen)
                except StopIteration:
                    pass
                assert not repo.is_connected

    def test_provider_fallback_without_global_factory(self):
        """When no global factory exists, providers create one from app config."""
        from spiderfoot.api.dependencies import get_scan_repository

        fake_config = MagicMock()
        fake_config.get_config.return_value = {"__database": ":memory:"}
        fake_dbh = FakeDbh()

        with patch(
            "spiderfoot.api.dependencies.get_app_config",
            return_value=fake_config,
        ):
            with patch(
                "spiderfoot.db.repositories.factory.get_repository_factory",
                return_value=None,
            ):
                with patch(
                    "spiderfoot.db.repositories.factory.RepositoryFactory.create_dbh",
                    return_value=fake_dbh,
                ):
                    gen = get_scan_repository()
                    repo = next(gen)
                    assert repo.is_connected
                    try:
                        next(gen)
                    except StopIteration:
                        pass


# ===========================================================================
# Service Integration Wiring
# ===========================================================================

class TestServiceIntegrationWiring:
    """Test _wire_repository_factory in service_integration.py."""

    def setup_method(self):
        from spiderfoot.db.repositories import factory
        factory._global_factory = None

    def teardown_method(self):
        from spiderfoot.db.repositories import factory
        factory._global_factory = None

    def test_wire_attaches_factory_to_scanner(self):
        from spiderfoot.service_integration import _wire_repository_factory

        scanner = MagicMock()
        scanner._SpiderFootScanner__config = {"__database": ":memory:"}
        _wire_repository_factory(scanner)
        assert hasattr(scanner, "_repo_factory")

    def test_wire_reuses_existing_factory(self):
        from spiderfoot.service_integration import _wire_repository_factory
        from spiderfoot.db.repositories.factory import (
            init_repository_factory,
            reset_repository_factory,
        )
        existing = init_repository_factory({"preset": True})

        scanner = MagicMock()
        scanner._SpiderFootScanner__config = {}
        _wire_repository_factory(scanner)
        assert scanner._repo_factory is existing
        reset_repository_factory()

    def test_wire_handles_import_error(self):
        """If repository module is missing, wiring is a no-op."""
        from spiderfoot.service_integration import _wire_repository_factory

        scanner = MagicMock()
        scanner._SpiderFootScanner__config = {}
        with patch(
            "spiderfoot.db.repositories.factory.init_repository_factory",
            side_effect=ImportError("no module"),
        ):
            # Should not raise
            _wire_repository_factory(scanner)

    def test_wire_handles_missing_config(self):
        """Scanner without __config still wires with empty dict."""
        from spiderfoot.service_integration import _wire_repository_factory

        scanner = MagicMock(spec=[])  # No attributes
        _wire_repository_factory(scanner)
        assert hasattr(scanner, "_repo_factory")


# ===========================================================================
# Cross-cutting: Context Manager + Repository
# ===========================================================================

class TestCrossCutting:
    """Integration-style tests combining multiple components."""

    def test_factory_context_manager_flow(self):
        from spiderfoot.db.repositories.factory import RepositoryFactory

        factory = RepositoryFactory()
        fake_dbh = FakeDbh()

        with patch.object(factory, "create_dbh", return_value=fake_dbh):
            with factory.scan_repo() as repo:
                repo.create_scan("id-x", "Test", "target.com")
                assert not fake_dbh.closed
            assert fake_dbh.closed

    def test_scan_record_roundtrip(self):
        from spiderfoot.db.repositories.scan_repository import ScanRecord

        original = ScanRecord(
            scan_id="abc", name="RoundTrip", target="example.com",
            status="FINISHED", created=1.0, started=2.0, ended=3.0,
        )
        d = original.to_dict()
        restored = ScanRecord(**d)
        assert restored.scan_id == original.scan_id
        assert restored.status == original.status
        assert restored.ended == original.ended

    def test_multiple_repos_share_dbh(self):
        from spiderfoot.db.repositories.factory import RepositoryFactory

        factory = RepositoryFactory()
        dbh = FakeDbh()
        scan = factory.scan_repo(dbh=dbh)
        event = factory.event_repo(dbh=dbh)
        config = factory.config_repo(dbh=dbh)

        # All share the same handle
        assert scan._dbh is dbh
        assert event._dbh is dbh
        assert config._dbh is dbh

        # Operations work independently
        scan.create_scan("id-1", "S", "T")
        event.store_event("id-1", MagicMock())
        config.set_config({"x": 1})

        assert len(dbh.calls) == 3
