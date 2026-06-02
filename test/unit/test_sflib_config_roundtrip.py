"""Round-trip tests for SpiderFoot config (de)serialization.

configSerialize/configUnserialize move scan configuration to/from the DB. A
type-mismatch bug flipped boolean options True -> False on an in-memory round
trip: serialize emits int 1/0, but unserialize compared the value against the
string "1" (and 1 == "1" is False). The DB path survived only because the DB
stringifies everything; this guards both paths and both the global and
per-module option tables.
"""
from __future__ import annotations

import pytest

from spiderfoot.sflib.config import configSerialize, configUnserialize


REFERENCE = {
    "enable_x": True,
    "disable_y": False,
    "count": 5,
    "name": "hello",
    "tags": ["a", "b"],
    "empty_list": [],
    "__system": "kept-out-when-filtered",
    "__modules__": {
        "sfp_x": {
            "opts": {
                "verify": True,
                "disabled": False,
                "max_results": 10,
                "label": "z",
            }
        }
    },
}


def _modopts(cfg):
    return cfg["__modules__"]["sfp_x"]["opts"]


class TestBooleanRoundTrip:
    def test_inmemory_round_trip_preserves_booleans(self):
        ser = configSerialize(REFERENCE, filterSystem=True)
        out = configUnserialize(ser, REFERENCE, filterSystem=True)
        assert out["enable_x"] is True
        assert out["disable_y"] is False
        assert _modopts(out)["verify"] is True
        assert _modopts(out)["disabled"] is False

    def test_db_path_round_trip_preserves_booleans(self):
        # The DB returns everything as strings.
        ser = {k: str(v) for k, v in
               configSerialize(REFERENCE, filterSystem=True).items()}
        out = configUnserialize(ser, REFERENCE, filterSystem=True)
        assert out["enable_x"] is True
        assert out["disable_y"] is False
        assert _modopts(out)["verify"] is True


class TestScalarRoundTrip:
    def test_int_and_str_and_list(self):
        ser = configSerialize(REFERENCE, filterSystem=True)
        out = configUnserialize(ser, REFERENCE, filterSystem=True)
        assert out["count"] == 5
        assert out["name"] == "hello"
        assert out["tags"] == ["a", "b"]
        assert _modopts(out)["max_results"] == 10
        assert _modopts(out)["label"] == "z"


class TestSystemFiltering:
    def test_system_keys_filtered_when_requested(self):
        ser = configSerialize(REFERENCE, filterSystem=True)
        assert "__system" not in ser

    def test_serialize_rejects_non_dict(self):
        with pytest.raises(TypeError):
            configSerialize(["not", "a", "dict"])
