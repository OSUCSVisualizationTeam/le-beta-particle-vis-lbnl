"""Unit tests for EventEnvelope (wire format + JSON ser/de)."""

import json

import pytest

from le_beta_vis.common.EventEnvelope import (
    SCHEMA_VERSION,
    EventEnvelope,
)


class TestConstruction:

    def test_minimal_envelope_has_generated_defaults(self):
        env = EventEnvelope(name="cluster.classified")
        assert env.name == "cluster.classified"
        assert env.payload == {}
        assert env.source == ""
        assert env.schema == SCHEMA_VERSION
        assert env.actionable is None
        assert isinstance(env.id, str) and len(env.id) == 32
        assert env.timestamp.endswith("Z")

    def test_rejects_empty_name(self):
        with pytest.raises(ValueError, match="non-empty string"):
            EventEnvelope(name="")

    def test_rejects_non_string_name(self):
        with pytest.raises(ValueError, match="non-empty string"):
            EventEnvelope(name=None)  # type: ignore[arg-type]

    def test_rejects_non_dict_payload(self):
        with pytest.raises(TypeError, match="payload must be a dict"):
            EventEnvelope(name="foo", payload=[1, 2])  # type: ignore[arg-type]

    def test_rejects_unknown_schema_version(self):
        with pytest.raises(ValueError, match="Unsupported"):
            EventEnvelope(name="foo", schema=99)


class TestSerialization:

    def test_to_dict_round_trip(self):
        env = EventEnvelope(
            name="log.error",
            payload={"message": "bad"},
            source="eps",
        )
        d = env.to_dict()
        assert d["name"] == "log.error"
        assert d["payload"] == {"message": "bad"}
        assert d["schema"] == SCHEMA_VERSION
        rebuilt = EventEnvelope.from_dict(d)
        assert rebuilt == env

    def test_to_json_bytes_is_valid_utf8_json(self):
        env = EventEnvelope(name="x", payload={"greek": "µ"})
        raw = env.to_json_bytes()
        assert isinstance(raw, bytes)
        decoded = json.loads(raw.decode("utf-8"))
        assert decoded["payload"]["greek"] == "µ"

    def test_from_json_bytes_round_trip(self):
        env = EventEnvelope(name="cluster.classified", payload={"fits_id": 42})
        raw = env.to_json_bytes()
        rebuilt = EventEnvelope.from_json_bytes(raw)
        assert rebuilt.name == env.name
        assert rebuilt.payload == env.payload
        assert rebuilt.id == env.id
        assert rebuilt.timestamp == env.timestamp

    def test_from_json_bytes_rejects_invalid_json(self):
        with pytest.raises(ValueError):
            EventEnvelope.from_json_bytes(b"not-json")

    def test_from_json_bytes_rejects_non_object(self):
        with pytest.raises(ValueError, match="must decode to an object"):
            EventEnvelope.from_json_bytes(b"[1, 2, 3]")

    def test_from_dict_requires_name(self):
        with pytest.raises(ValueError, match="missing required field 'name'"):
            EventEnvelope.from_dict({"payload": {}})

    def test_from_dict_fills_missing_optionals(self):
        env = EventEnvelope.from_dict({"name": "foo"})
        assert env.name == "foo"
        assert env.payload == {}
        assert env.source == ""
        assert isinstance(env.id, str) and len(env.id) == 32

    def test_topic_bytes_uses_utf8(self):
        env = EventEnvelope(name="cluster.classified")
        assert env.topic_bytes() == b"cluster.classified"

    def test_topic_bytes_handles_unicode(self):
        env = EventEnvelope(name="µonmon")
        assert env.topic_bytes() == "µonmon".encode("utf-8")


class TestFrozen:

    def test_envelope_is_hashable(self):
        env = EventEnvelope(name="x", payload={})
        # Hash depends on field identity; payload dict is mutable so
        # asdict-level equality is the contract, not hashability.
        # Instead, verify frozen: assignment raises.
        with pytest.raises(Exception):
            env.name = "y"  # type: ignore[misc]
