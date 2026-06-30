from __future__ import annotations
import re
from typing import Any

import phonenumbers

import pipeline.config as _cfg
_PROV_REMAP: dict[str, str] = {"emails": "email", "phones": "phone"}
_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _parse(expr: str) -> list[tuple[str, int | str | None]]:
    parts = []
    for seg in expr.split("."):
        m = re.match(r'^(\w+)(?:\[(\d*)\])?$', seg)
        if not m:
            return []
        key, bracket = m.group(1), m.group(2)
        idx: int | str | None = None if bracket is None else ("wildcard" if bracket == "" else int(bracket))
        parts.append((key, idx))
    return parts


def _walk(node: Any, parts: list[tuple[str, Any]]) -> Any:
    if not parts or node is None:
        return node
    key, idx = parts[0]
    rest = parts[1:]
    if not isinstance(node, dict):
        return None
    val = node.get(key)
    if idx is None:
        return _walk(val, rest)
    if idx == "wildcard":
        if not isinstance(val, list):
            return []
        return val if not rest else [_walk(item, rest) for item in val]
    if not isinstance(val, list) or idx >= len(val):
        return None
    return _walk(val[idx], rest)


def _resolve(profile: dict, from_expr: str) -> Any:
    return _walk(profile, _parse(from_expr))


def _normalize_one(value: Any, norm: str) -> Any:
    if not isinstance(value, str):
        return value
    if norm == "national":
        try:
            p = phonenumbers.parse(value, None)
            return phonenumbers.format_number(p, phonenumbers.PhoneNumberFormat.NATIONAL)
        except Exception:
            return value
    if norm == "display":
        return value.title()
    if norm == "human":
        m = re.match(r'^(\d{4})-(\d{2})$', value)
        if m:
            return f"{_MONTHS[int(m.group(2)) - 1]} {m.group(1)}"
        return value
    # ponytail: "E164", "canonical", "iso" are pass-throughs — Stage 1 already normalizes these
    return value


def _prov_key(from_expr: str) -> str:
    root = re.split(r'[\.\[]', from_expr)[0]
    return _PROV_REMAP.get(root, root)


def _field_confidence(profile: dict, field: str) -> float | None:
    for e in profile.get("provenance", []):
        if e.get("role") == "primary" and e.get("field") == field:
            return _cfg.BASE_SCORES.get((e["source"], e["method"]))
    return None


def _field_provenance(profile: dict, field: str) -> dict | None:
    for e in profile.get("provenance", []):
        if e.get("role") == "primary" and e.get("field") == field:
            return {"source": e["source"], "method": e["method"]}
    return None


def _skill_confidence(profile: dict, name: str) -> float | None:
    for s in profile.get("skills", []):
        if s.get("name") == name:
            return s.get("confidence")
    return None


def _skill_provenance(profile: dict, name: str) -> dict | None:
    for s in profile.get("skills", []):
        if s.get("name") == name:
            return {"sources": s.get("sources", [])}
    return None


def _set_path(output: dict, path: str, value: Any) -> None:
    parts = path.split(".")
    node = output
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = value


def project(profile: dict, config: dict) -> tuple[dict, list[dict]]:
    on_missing = config.get("on_missing", "null")
    inc_conf = config.get("include_confidence", False)
    inc_prov = config.get("include_provenance", False)
    output: dict = {}
    failures: list[dict] = []

    for field in config["fields"]:
        path = field["path"]
        from_expr = field.get("from") or path.split(".")[-1]
        norm = field.get("normalize")
        required = field.get("required", False)
        limit = field.get("limit")
        is_wildcard = bool(re.search(r'\[\]', from_expr))

        raw = _resolve(profile, from_expr)
        if isinstance(raw, list) and limit:
            raw = raw[:limit]

        if raw is None:
            if required:
                failures.append({"field": path, "reason": f"missing required field '{path}'"})
            elif on_missing == "error":
                failures.append({"field": path, "reason": f"missing optional field '{path}' (on_missing=error)"})
            elif on_missing != "omit":
                _set_path(output, path, None)
            continue

        if is_wildcard:
            if not isinstance(raw, list):
                raw = []
            display = [_normalize_one(v, norm) if norm else v for v in raw]
            if inc_conf or inc_prov:
                canonical_key = from_expr.split("[")[0]
                lookup_conf = _skill_confidence if canonical_key == "skills" else lambda _p, _n: None
                lookup_prov = _skill_provenance if canonical_key == "skills" else lambda _p, _n: None
                items: list[dict] = []
                for rv, dv in zip(raw, display):
                    item: dict = {"value": dv}
                    if inc_conf:
                        item["confidence"] = lookup_conf(profile, rv)
                    if inc_prov:
                        item["provenance"] = lookup_prov(profile, rv)
                    items.append(item)
                _set_path(output, path, items)
            else:
                _set_path(output, path, display)
        else:
            value = _normalize_one(raw, norm) if norm else raw
            _set_path(output, path, value)
            if inc_conf or inc_prov:
                pf = _prov_key(from_expr)
                if inc_conf:
                    _set_path(output, path + "_confidence", _field_confidence(profile, pf))
                if inc_prov:
                    _set_path(output, path + "_provenance", _field_provenance(profile, pf))

    return output, failures
