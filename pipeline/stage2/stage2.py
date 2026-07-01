from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import projection_engine, schema_validator


def run(data_root: Path, config_path: Path, input_path: Path) -> dict[str, Any]:
    profiles: list[dict] = json.loads(input_path.read_text(encoding="utf-8"))
    config: dict = json.loads(config_path.read_text(encoding="utf-8"))

    schema_validator.validate_config(config)

    results: list[dict] = []
    failures: list[dict] = []
    failed_ids: set[str] = set()

    for profile in profiles:
        cid = profile.get("candidate_id", "unknown")
        output, field_failures = projection_engine.project(profile, config)

        if field_failures:
            failed_ids.add(cid)
            for f in field_failures:
                failures.append({"candidate_id": cid, **f})
            continue

        type_errors = schema_validator.validate_output(output, config)
        if type_errors:
            failed_ids.add(cid)
            for e in type_errors:
                failures.append({"candidate_id": cid, "field": "?", "reason": e})
            continue

        results.append(output)

    out_dir = data_root / "output"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"{config_path.stem}_output.json"

    result: dict[str, Any] = {
        "results": results,
        "failures": failures,
        "_meta": {
            "config_used": str(config_path),
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "total": len(profiles),
            "succeeded": len(results),
            "failed": len(failed_ids),
        },
    }
    out_path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(f"Stage 2 [{config_path.name}]: {len(results)} ok, {len(failed_ids)} failed -> {out_path}")
    return result
