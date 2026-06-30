from __future__ import annotations
import re
from typing import Any

_TYPE_CHECKS: dict[str, Any] = {
    "string":   lambda v: isinstance(v, str),
    "number":   lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean":  lambda v: isinstance(v, bool),
    "string[]": lambda v: isinstance(v, list) and all(isinstance(i, str) for i in v),
    "number[]": lambda v: isinstance(v, list) and all(isinstance(i, (int, float)) and not isinstance(i, bool) for i in v),
    "object":   lambda v: isinstance(v, dict),
    "object[]": lambda v: isinstance(v, list) and all(isinstance(i, dict) for i in v),
}


def validate_config(config: dict) -> None:
    for field in config.get("fields", []):
        from_expr = field.get("from", "")
        ftype = field.get("type", "")
        if re.search(r'\[\]', from_expr) and not ftype.endswith("[]"):
            raise ValueError(
                f"Config error: field '{field['path']}' uses wildcard from ({from_expr!r}) "
                f"but declares scalar type '{ftype}' - use a list type (e.g. '{ftype}[]')"
            )


def _get_path(obj: Any, path: str) -> Any:
    for part in path.split("."):
        if not isinstance(obj, dict):
            return None
        obj = obj.get(part)
    return obj


def validate_output(output: dict, config: dict) -> list[str]:
    errors: list[str] = []
    for field in config.get("fields", []):
        path = field["path"]
        ftype = field.get("type", "string")
        value = _get_path(output, path)
        if value is None:
            continue
        if (isinstance(value, list) and value
                and isinstance(value[0], dict) and "value" in value[0]):
            base = ftype.rstrip("[]")
            check = _TYPE_CHECKS.get(base)
            if check and any(not check(item.get("value")) for item in value if item.get("value") is not None):
                errors.append(f"field '{path}': enriched item type mismatch, expected {base}")
        else:
            check = _TYPE_CHECKS.get(ftype)
            if check and not check(value):
                errors.append(f"field '{path}': expected {ftype}, got {type(value).__name__}")
    return errors
