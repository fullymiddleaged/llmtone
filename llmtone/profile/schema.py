"""A small validator for voice-profile.schema.json.

The schema itself is real JSON Schema, published so that other tools can consume
the format with their own validator. llmtone does not take a ``jsonschema``
dependency to read its own file: this covers the subset the schema uses --
type, required, properties, additionalProperties, items, enum, minimum,
maximum and pattern -- in about a hundred lines, and raises a clear error
listing every problem it found rather than only the first.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

__all__ = ["SchemaError", "load_schema", "validate", "validate_or_raise", "SCHEMA_PATH"]

_HERE = Path(__file__).resolve()

#: The canonical schema lives at the repository root so it is easy to find and
#: link to. It is also copied into the package at build time, so an installed
#: wheel can still validate without the repository present.
_CANDIDATES = (
    _HERE.parents[1] / "voice-profile.schema.json",   # installed package
    _HERE.parents[2] / "voice-profile.schema.json",   # source checkout
)

SCHEMA_PATH = next((p for p in _CANDIDATES if p.exists()), _CANDIDATES[-1])

_TYPES: dict[str, type | tuple[type, ...]] = {
    "object": dict,
    "array": list,
    "string": str,
    "number": (int, float),
    "integer": int,
    "boolean": bool,
    "null": type(None),
}


class SchemaError(ValueError):
    """Raised when a profile does not match the published schema."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        joined = "\n  - ".join(errors)
        super().__init__(f"profile does not match the schema:\n  - {joined}")


@lru_cache(maxsize=1)
def load_schema(path: str | None = None) -> dict:
    """Load the published schema. Cached; the file does not change at runtime."""
    target = Path(path) if path else SCHEMA_PATH
    return json.loads(target.read_text(encoding="utf-8"))


def _check_type(value, expected: str, where: str, errors: list[str]) -> bool:
    python_type = _TYPES.get(expected)
    if python_type is None:
        return True
    # bool is a subclass of int in Python; a boolean is not a number here.
    if expected in ("number", "integer") and isinstance(value, bool):
        errors.append(f"{where}: expected {expected}, got boolean")
        return False
    if not isinstance(value, python_type):
        errors.append(
            f"{where}: expected {expected}, got {type(value).__name__}"
        )
        return False
    return True


def _validate_node(value, schema: dict, where: str, errors: list[str]) -> None:
    expected = schema.get("type")
    if expected and not _check_type(value, expected, where, errors):
        return

    if "enum" in schema and value not in schema["enum"]:
        errors.append(
            f"{where}: {value!r} is not one of {schema['enum']}"
        )

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{where}: {value} is below minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{where}: {value} is above maximum {schema['maximum']}")

    if isinstance(value, str) and "pattern" in schema:
        if not re.search(schema["pattern"], value):
            errors.append(f"{where}: {value!r} does not match {schema['pattern']}")

    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{where}: missing required key {key!r}")
        properties = schema.get("properties", {})
        for key, child in value.items():
            if key in properties:
                _validate_node(child, properties[key], f"{where}.{key}", errors)
            elif isinstance(schema.get("additionalProperties"), dict):
                _validate_node(
                    child, schema["additionalProperties"], f"{where}.{key}", errors
                )

    if isinstance(value, list) and isinstance(schema.get("items"), dict):
        for index, item in enumerate(value):
            _validate_node(item, schema["items"], f"{where}[{index}]", errors)


def validate(profile: dict, schema: dict | None = None) -> list[str]:
    """Return a list of problems. Empty means valid."""
    errors: list[str] = []
    _validate_node(profile, schema or load_schema(), "profile", errors)
    return errors


def validate_or_raise(profile: dict, schema: dict | None = None) -> None:
    errors = validate(profile, schema)
    if errors:
        raise SchemaError(errors)
