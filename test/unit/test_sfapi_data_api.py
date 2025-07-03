import sfapi
import pytest
from fastapi.testclient import TestClient
from spiderfoot.db import SpiderFootDb
from spiderfoot.api.dependencies import Config
import os
import tempfile
import shutil

client = TestClient(sfapi.app)


def setup_real_db():
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "spiderfoot.db")
    config = {
        '__database': db_path,
        '__dbtype': 'sqlite',
        '__modules__': {},
        '__eventtypes__': [],
    }
    dbh = SpiderFootDb(config, init=True)
    with dbh.conn:
        dbh.conn.execute("INSERT INTO tbl_event_types (event, event_descr, event_raw, event_type) VALUES (?, ?, ?, ?)",
                         ("REAL_TYPE", "A real event type", 0, "ENTITY"))
        dbh.conn.execute("INSERT INTO tbl_config (scope, opt, val) VALUES (?, ?, ?)",
                         ("modreal", "optdescs", '{"opt1": "desc1"}'))
    config['__modules__'] = {
        'modreal': {
            'optdescs': {'opt1': 'desc1'},
            'categories': ['cat1'],
            'type': 'passive'
        }
    }
    config['__eventtypes__'] = ["REAL_TYPE"]
    return temp_dir, db_path, config


@pytest.fixture(scope="function", autouse=True)
def real_db(monkeypatch):
    temp_dir, db_path, config = setup_real_db()
    def custom_init(self):
        self.config = config
        self.dbh = SpiderFootDb(self.config)
    monkeypatch.setattr(Config, '__init__', custom_init)
    monkeypatch.setattr(Config, 'get_config', lambda self: config)
    yield
    shutil.rmtree(temp_dir)


def test_list_entity_types():
    resp = client.get("/api/data/entity-types")
    assert resp.status_code == 200
    assert "entity_types" in resp.json()
    assert isinstance(resp.json()["entity_types"], list)


def test_list_modules():
    resp = client.get("/api/data/modules")
    assert resp.status_code == 200
    assert "modules" in resp.json()
    assert isinstance(resp.json()["modules"], dict)


def test_list_sources():
    resp = client.get("/api/data/sources")
    assert resp.status_code == 200
    assert "sources" in resp.json()
    assert isinstance(resp.json()["sources"], list)


def test_get_module_details_success():
    # Get a valid module name from the list
    resp = client.get("/api/data/modules")
    modules = resp.json()["modules"]
    if modules:
        module_name = next(iter(modules))
        resp2 = client.get(f"/api/data/modules/{module_name}")
        assert resp2.status_code == 200
        assert "module" in resp2.json()
    else:
        pytest.skip("No modules available to test details endpoint.")


def test_get_module_details_not_found():
    resp = client.get("/api/data/modules/FAKEMODULE")
    assert resp.status_code == 404


def test_get_entity_type_details_success():
    resp = client.get("/api/data/entity-types")
    types = resp.json()["entity_types"]
    if types:
        type_name = types[0]
        resp2 = client.get(f"/api/data/entity-types/{type_name}")
        assert resp2.status_code == 200
        assert "entity_type" in resp2.json()
    else:
        pytest.skip("No entity types available to test details endpoint.")


def test_get_entity_type_details_not_found():
    resp = client.get("/api/data/entity-types/FAKETYPE")
    assert resp.status_code == 404


def test_list_global_options():
    resp = client.get("/api/data/global-options")
    assert resp.status_code == 200
    assert "global_options" in resp.json()
    assert isinstance(resp.json()["global_options"], dict)


def test_list_module_options_success():
    resp = client.get("/api/data/modules")
    modules = resp.json()["modules"]
    if modules:
        module_name = next(iter(modules))
        resp2 = client.get(f"/api/data/modules/{module_name}/options")
        assert resp2.status_code == 200
        assert "options" in resp2.json()
    else:
        pytest.skip("No modules available to test options endpoint.")


def test_list_module_options_not_found():
    resp = client.get("/api/data/modules/FAKEMODULE/options")
    assert resp.status_code == 404


def test_list_module_categories():
    resp = client.get("/api/data/module-categories")
    assert resp.status_code == 200
    assert "module_categories" in resp.json()
    assert isinstance(resp.json()["module_categories"], list)


def test_list_module_types():
    resp = client.get("/api/data/module-types")
    assert resp.status_code == 200
    assert "module_types" in resp.json()
    assert isinstance(resp.json()["module_types"], list)


def test_list_risk_levels():
    resp = client.get("/api/data/risk-levels")
    assert resp.status_code == 200
    assert "risk_levels" in resp.json()
    assert set(resp.json()["risk_levels"]) == {"info", "low", "medium", "high", "critical"}
