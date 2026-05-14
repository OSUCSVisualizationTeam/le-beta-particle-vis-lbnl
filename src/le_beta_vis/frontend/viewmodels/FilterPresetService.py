"""Serialization and schema validation for filter pipeline presets (.rcfilt).

A preset captures the full filter stack — structural (pinned) filters and
user-added filters — as a versioned JSON document. The JSON Schema is
derived at runtime from ``BUILTIN_FILTERS`` so adding a new filter to the
registry automatically makes its ``type_id`` valid in saved files.

File format::

    {
        "schema_version": "1.0",
        "annotation": "Gaussian Blur (σ=1.5); Display Range (Min=0, Max=4)",
        "filters": [
            { "type_id": "builtin.adu_to_kev",   "pinned": true,  "enabled": true, "parameters": {} },
            { "type_id": "builtin.gaussian_blur", "pinned": false, "enabled": true, "parameters": {"sigma": 1.5} },
            { "type_id": "builtin.scale_preset",  "pinned": true,  "enabled": true, "parameters": {"mode": "linear"} },
            { "type_id": "builtin.window",        "pinned": true,  "enabled": true, "parameters": {"vmin": 0.0, "vmax": 4.0} }
        ]
    }

``type_id`` uses a ``builtin.`` namespace so future plugin filters can
coexist without clashing. The ADU→keV conversion factor is intentionally
omitted — it has no ``ParameterSpec`` and is treated as an instrument
calibration constant that must come from config, not from a preset file.
"""

import json
from enum import Enum
from typing import List, Optional, Tuple

import jsonschema

from le_beta_vis.common.filter_pipeline import BUILTIN_FILTERS, FilterSpec, ParameterType
from .FilterStackViewModel import FilterStackEntry

_SCHEMA_VERSION = "1.0"
_BUILTIN_PREFIX = "builtin."
_schema_cache: Optional[dict] = None
_spec_lookup: Optional[dict] = None


def generate_schema() -> dict:
    """Build the JSON Schema for .rcfilt files from the current BUILTIN_FILTERS.

    Calling this more than once is safe (the result is cached by ``_get_schema``).
    The schema uses JSON Schema draft-07 ``oneOf`` so each filter entry is
    validated against the parameter constraints declared in its ``ParameterSpec``.
    """
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "required": ["schema_version", "filters"],
        "additionalProperties": False,
        "properties": {
            "schema_version": {"type": "string", "const": _SCHEMA_VERSION},
            "annotation": {"type": "string"},
            "filters": {
                "type": "array",
                "items": {"oneOf": [_filter_entry_schema(s) for s in BUILTIN_FILTERS]},
            },
        },
    }


def _filter_entry_schema(spec: FilterSpec) -> dict:
    props: dict = {}
    required: List[str] = []
    for ps in spec.parameters:
        if ps.type == ParameterType.ENUM:
            prop: dict = {"type": "string"}
            if ps.enum_values:
                prop["enum"] = list(ps.enum_values)
        else:
            prop = {"type": "number"}
            if ps.min_value is not None:
                prop["minimum"] = ps.min_value
            if ps.max_value is not None:
                prop["maximum"] = ps.max_value
        props[ps.name] = prop
        required.append(ps.name)
    return {
        "type": "object",
        "required": ["type_id", "enabled", "pinned", "parameters"],
        "additionalProperties": False,
        "properties": {
            "type_id": {"type": "string", "const": f"{_BUILTIN_PREFIX}{spec.type_id}"},
            "enabled": {"type": "boolean"},
            "pinned": {"type": "boolean"},
            "parameters": {
                "type": "object",
                "properties": props,
                "required": required,
                "additionalProperties": False,
            },
        },
    }


def serialize_stack(entries: List[FilterStackEntry]) -> List[dict]:
    """Convert a filter stack to a list of JSON-serializable dicts."""
    return [_serialize_entry(e) for e in entries]


def _serialize_entry(entry: FilterStackEntry) -> dict:
    spec = entry.filter.SPEC
    params = {}
    for ps in spec.parameters:
        val = getattr(entry.filter, ps.name)
        params[ps.name] = val.value if isinstance(val, Enum) else val
    return {
        "type_id": f"{_BUILTIN_PREFIX}{spec.type_id}",
        "pinned": entry.pinned,
        "enabled": entry.enabled,
        "parameters": params,
    }


def deserialize_stack(filter_dicts: List[dict]) -> List[FilterStackEntry]:
    """Reconstruct a filter stack from a list of serialized dicts.

    Raises:
        ValueError: if a ``type_id`` is not found in the current registry.
    """
    return [_deserialize_entry(fd) for fd in filter_dicts]


def _deserialize_entry(fd: dict) -> FilterStackEntry:
    lookup = _get_spec_lookup()
    spec = lookup.get(fd["type_id"])
    if spec is None:
        raise ValueError(f"Unknown filter type: {fd['type_id']!r}")
    if spec.filter_class is None:
        raise ValueError(f"Filter {fd['type_id']!r} has no constructor")
    instance = spec.filter_class()
    for ps in spec.parameters:
        raw = fd["parameters"].get(ps.name, ps.default)
        setattr(instance, ps.name, ps.clamp(raw))
    return FilterStackEntry(filter=instance, enabled=fd["enabled"], pinned=fd["pinned"])


def compose_annotation(entries: List[FilterStackEntry]) -> str:
    """Build a human-readable summary of the enabled filter stack.

    Used to pre-fill the annotation field in the save preset dialog.
    Enum parameter values are rendered as their string value; numeric
    values use Python's ``:.2g`` format to keep the string compact.
    """
    parts = []
    for entry in entries:
        if not entry.enabled:
            continue
        spec = entry.filter.SPEC
        if not spec.parameters:
            parts.append(spec.display_name)
            continue
        param_strs = []
        for ps in spec.parameters:
            val = getattr(entry.filter, ps.name)
            if ps.type == ParameterType.ENUM:
                str_val = val.value if isinstance(val, Enum) else str(val)
            else:
                str_val = f"{val:.2g}"
            param_strs.append(f"{ps.label}={str_val}")
        parts.append(f"{spec.display_name} ({', '.join(param_strs)})")
    return "; ".join(parts)


def save_preset(path: str, entries: List[FilterStackEntry], annotation: str) -> None:
    """Serialize *entries* to a .rcfilt file at *path*.

    Validates against the schema before writing so serialization bugs are
    caught before a corrupt file reaches disk.

    Raises:
        jsonschema.ValidationError: if the serialized data fails schema validation.
        OSError: if the file cannot be written.
    """
    data = {
        "schema_version": _SCHEMA_VERSION,
        "annotation": annotation,
        "filters": serialize_stack(entries),
    }
    jsonschema.validate(data, _get_schema())
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)


def load_preset(path: str) -> Tuple[List[FilterStackEntry], str]:
    """Load and validate a .rcfilt file.

    Returns:
        A ``(entries, annotation)`` tuple. ``annotation`` is an empty
        string when the file omits the field.

    Raises:
        jsonschema.ValidationError: if the file fails schema validation.
        json.JSONDecodeError: if the file is not valid JSON.
        OSError: if the file cannot be read.
        ValueError: if a filter ``type_id`` is not in the registry.
    """
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    jsonschema.validate(data, _get_schema())
    entries = deserialize_stack(data["filters"])
    return entries, data.get("annotation", "")


def _get_schema() -> dict:
    global _schema_cache
    if _schema_cache is None:
        _schema_cache = generate_schema()
    return _schema_cache


def _get_spec_lookup() -> dict:
    global _spec_lookup
    if _spec_lookup is None:
        _spec_lookup = {f"{_BUILTIN_PREFIX}{s.type_id}": s for s in BUILTIN_FILTERS}
    return _spec_lookup
