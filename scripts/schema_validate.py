from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from _common import ROOT
from workflow_errors import issue, print_issues


SCHEMA_KEYWORDS = {
    "$schema",
    "title",
    "description",
    "type",
    "required",
    "properties",
    "items",
    "enum",
    "const",
    "additionalProperties",
    "minLength",
    "minItems",
    "pattern",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, str):
        return "string"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _matches_type(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    return True


def _json_path(base: str, key: str | int) -> str:
    if isinstance(key, int):
        return f"{base}[{key}]"
    if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key):
        return f"{base}.{key}"
    return f"{base}[{key!r}]"


def validate_instance(instance: Any, schema: dict[str, Any], path: str = "$") -> list[str]:
    errors: list[str] = []

    if "type" in schema:
        expected = schema["type"]
        expected_values = expected if isinstance(expected, list) else [expected]
        if not any(isinstance(item, str) and _matches_type(instance, item) for item in expected_values):
            errors.append(f"{path}: expected type {expected!r}, got {_type_name(instance)}")
            return errors

    if "const" in schema and instance != schema["const"]:
        errors.append(f"{path}: expected const {schema['const']!r}, got {instance!r}")

    if "enum" in schema:
        allowed = schema["enum"]
        if isinstance(allowed, list) and instance not in allowed:
            errors.append(f"{path}: value {instance!r} is not in enum {allowed!r}")

    if isinstance(instance, str):
        min_length = schema.get("minLength")
        if isinstance(min_length, int) and len(instance) < min_length:
            errors.append(f"{path}: string shorter than minLength {min_length}")
        pattern = schema.get("pattern")
        if isinstance(pattern, str) and re.search(pattern, instance) is None:
            errors.append(f"{path}: string does not match pattern {pattern!r}")

    if isinstance(instance, dict):
        required = schema.get("required", [])
        if isinstance(required, list):
            for key in required:
                if isinstance(key, str) and key not in instance:
                    errors.append(f"{path}: missing required property {key!r}")

        properties = schema.get("properties", {})
        if isinstance(properties, dict):
            for key, subschema in properties.items():
                if key in instance and isinstance(subschema, dict):
                    errors.extend(validate_instance(instance[key], subschema, _json_path(path, key)))

        additional = schema.get("additionalProperties", True)
        if additional is False and isinstance(properties, dict):
            allowed = set(properties)
            for key in sorted(set(instance) - allowed):
                errors.append(f"{path}: unexpected additional property {key!r}")

    if isinstance(instance, list):
        min_items = schema.get("minItems")
        if isinstance(min_items, int) and len(instance) < min_items:
            errors.append(f"{path}: array shorter than minItems {min_items}")
        items = schema.get("items")
        if isinstance(items, dict):
            for index, value in enumerate(instance):
                errors.extend(validate_instance(value, items, _json_path(path, index)))

    return errors


def validate_schema_document(schema: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(schema, dict):
        return ["schema top-level value must be an object"]
    if "$schema" not in schema:
        errors.append("schema must define $schema")
    if "title" not in schema:
        errors.append("schema must define title")
    if "type" in schema:
        value = schema["type"]
        values = value if isinstance(value, list) else [value]
        for item in values:
            if item not in {"object", "array", "string", "integer", "number", "boolean", "null"}:
                errors.append(f"unsupported schema type {item!r}")
    if "required" in schema and not isinstance(schema["required"], list):
        errors.append("required must be a list")
    if "properties" in schema:
        if not isinstance(schema["properties"], dict):
            errors.append("properties must be an object")
        else:
            for key, subschema in schema["properties"].items():
                if isinstance(subschema, dict):
                    errors.extend(f"properties.{key}: {item}" for item in validate_schema_document({"$schema": "internal", "title": key, **subschema}))
    if "items" in schema and isinstance(schema["items"], dict):
        errors.extend(f"items: {item}" for item in validate_schema_document({"$schema": "internal", "title": "items", **schema["items"]}))
    unknown = sorted(set(schema) - SCHEMA_KEYWORDS)
    for key in unknown:
        errors.append(f"unsupported schema keyword {key!r}")
    return errors


def validate_json_file(json_path: Path, schema_path: Path) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    try:
        instance = load_json(json_path)
    except Exception as exc:
        return [issue("SCHEMA", f"invalid JSON: {exc}", _rel(json_path))]
    try:
        schema = load_json(schema_path)
    except Exception as exc:
        return [issue("SCHEMA", f"invalid schema JSON: {exc}", _rel(schema_path))]
    for message in validate_instance(instance, schema):
        issues.append(issue("SCHEMA", message, _rel(json_path)))
    return issues


def validate_jsonl_file(jsonl_path: Path, schema_path: Path) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if not jsonl_path.exists():
        return issues
    try:
        schema = load_json(schema_path)
    except Exception as exc:
        return [issue("SCHEMA", f"invalid schema JSON: {exc}", _rel(schema_path))]
    for line_number, line in enumerate(jsonl_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            instance = json.loads(line)
        except json.JSONDecodeError as exc:
            issues.append(issue("SCHEMA", f"line {line_number}: invalid JSON: {exc}", _rel(jsonl_path)))
            continue
        for message in validate_instance(instance, schema):
            issues.append(issue("SCHEMA", f"line {line_number}: {message}", _rel(jsonl_path)))
    return issues


def _rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate one JSON file with the repository's stdlib schema validator.")
    parser.add_argument("--schema", required=True)
    parser.add_argument("--json", required=True)
    parser.add_argument("--jsonl", action="store_true")
    args = parser.parse_args()

    schema_path = ROOT / args.schema
    json_path = ROOT / args.json
    if args.jsonl:
        issues = validate_jsonl_file(json_path, schema_path)
    else:
        issues = validate_json_file(json_path, schema_path)
    if issues:
        print_issues(issues)
        return 1
    print("OK: schema validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
