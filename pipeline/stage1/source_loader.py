from __future__ import annotations
import csv
from pathlib import Path
from typing import Any

import pipeline.config as _cfg


def load(data_root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with open(data_root / _cfg.CSV_FILENAME, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            entry: dict[str, Any] = {"csv": row, "resume_raw": None, "github_raw": None, "load_failed": []}
            name = row.get("name", "").strip()

            if (row.get("resume_file") or "").strip():
                path = data_root / _cfg.RESUME_DIR / f"{name}{_cfg.RESUME_SUFFIX}"
                try:
                    entry["resume_raw"] = path.read_text(encoding="utf-8")
                except OSError:
                    entry["load_failed"].append("resume")

            if (row.get("github_url") or "").strip():
                path = data_root / _cfg.GITHUB_DIR / f"{name}{_cfg.GITHUB_SUFFIX}"
                try:
                    entry["github_raw"] = path.read_text(encoding="utf-8")
                except OSError:
                    entry["load_failed"].append("github")

            records.append(entry)
    return records
