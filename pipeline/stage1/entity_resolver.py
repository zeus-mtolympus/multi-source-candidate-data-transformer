from __future__ import annotations
from collections import defaultdict
from typing import Any


def resolve(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_email: dict[str, list[dict]] = defaultdict(list)
    no_email: list[dict] = []

    for rec in records:
        csv_emails = [t["value"].lower() for t in rec["extracted"]["emails"] if t["source"] == "csv"]
        if csv_emails:
            by_email[csv_emails[0]].append(rec)
        else:
            no_email.append(rec)

    result: list[dict] = []
    for recs in by_email.values():
        winner = recs[-1]
        if len(recs) > 1:
            winner["_earlier_rows"] = recs[:-1]
            winner["_has_conflict"] = True
        result.append(winner)

    result.extend(no_email)
    return result
