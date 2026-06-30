from __future__ import annotations
import json
from typing import Any


def parse(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for rec in records:
        rec["github_parsed"] = None
        raw = rec.get("github_raw")
        if raw is not None:
            try:
                rec["github_parsed"] = json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                rec["load_failed"].append("github_parse_failed")
    return records
