from __future__ import annotations
from datetime import date
from typing import Any

Tagged = dict[str, Any]

_SOURCE_PRIORITY: dict[str, int] = {"csv": 0, "resume": 1, "github": 2}
_SCALAR_FIELDS = ["full_name", "headline", "years_experience", "current_company", "title"]


def _priority(t: Tagged) -> int:
    return _SOURCE_PRIORITY.get(t["source"], 99)


def _pick_scalar(tagged: list[Tagged], field: str, provenance: list[dict]) -> Any:
    if not tagged:
        return None
    ranked = sorted(tagged, key=_priority)
    winner = ranked[0]
    provenance.append({"field": field, "source": winner["source"], "method": winner["method"], "value": winner["value"], "role": "primary"})
    for loser in ranked[1:]:
        if loser["value"] != winner["value"]:
            provenance.append({"field": field, "source": loser["source"], "method": loser["method"], "value": loser["value"], "role": "conflicting_alternate"})
    return winner["value"]


def merge(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    profiles: list[dict] = []
    for rec in records:
        ext = rec["extracted"]
        provenance: list[dict] = []

        _PROV_SINGULAR = {"emails": "email", "phones": "phone"}
        for earlier in rec.get("_earlier_rows", []):
            e_ext = earlier["extracted"]
            for field in _SCALAR_FIELDS + ["phones", "emails"]:
                for t in e_ext.get(field, []):
                    if t["source"] == "csv":
                        provenance.append({
                            "field": _PROV_SINGULAR.get(field, field), "source": "csv_duplicate",
                            "method": "direct", "value": t["value"],
                            "role": "conflicting_alternate",
                        })

        profile: dict[str, Any] = {}

        profile["full_name"] = _pick_scalar(ext["full_name"], "full_name", provenance)
        profile["headline"] = _pick_scalar(ext["headline"], "headline", provenance)
        profile["years_experience"] = _pick_scalar(ext["years_experience"], "years_experience", provenance)
        profile["current_company"] = _pick_scalar(ext["current_company"], "current_company", provenance)
        profile["title"] = _pick_scalar(ext["title"], "title", provenance)

        seen_emails: set[str] = set()
        profile["emails"] = []
        for t in sorted(ext["emails"], key=_priority):
            v = t["value"].lower()
            if v not in seen_emails:
                seen_emails.add(v)
                profile["emails"].append(v)
                provenance.append({"field": "email", "source": t["source"], "method": t["method"], "value": t["value"], "role": "primary"})

        seen_phones: set[str] = set()
        profile["phones"] = []
        for t in sorted(ext["phones"], key=_priority):
            v = t["value"]
            if v and v not in seen_phones:
                seen_phones.add(v)
                profile["phones"].append(v)
                provenance.append({"field": "phone", "source": t["source"], "method": t["method"], "value": v, "role": "primary"})

        loc_ranked = sorted(ext["location"], key=_priority)
        if loc_ranked:
            profile["location"] = loc_ranked[0]["value"]
            provenance.append({"field": "location", "source": loc_ranked[0]["source"], "method": loc_ranked[0]["method"], "value": loc_ranked[0]["value"], "role": "primary"})
            for loser in loc_ranked[1:]:
                if loser["value"] != loc_ranked[0]["value"]:
                    provenance.append({"field": "location", "source": loser["source"], "method": loser["method"], "value": loser["value"], "role": "conflicting_alternate"})
        else:
            profile["location"] = {"city": None, "region": None, "country": None}

        links: dict[str, Any] = {"linkedin": None, "github": None, "portfolio": None, "other": []}
        for t in sorted(ext["links"], key=_priority):
            lv = t["value"]
            for k in ("linkedin", "github", "portfolio"):
                val = lv.get(k)
                if not val:
                    continue
                if not links[k]:
                    links[k] = val
                    provenance.append({"field": "links", "source": t["source"], "method": t["method"], "value": val, "role": "primary"})
                elif val != links[k]:
                    provenance.append({"field": "links", "source": t["source"], "method": t["method"], "value": val, "role": "conflicting_alternate"})
        profile["links"] = links

        skill_map: dict[str, list[tuple[str, str]]] = {}
        for t in ext["skills"]:
            name = t.get("value")
            if not name:
                continue
            skill_map.setdefault(name, []).append((t["source"], t["method"]))
        profile["_skill_map"] = skill_map

        edu_seen: set[str] = set()
        profile["education"] = []
        for t in ext["education"]:
            key = str(t["value"])
            if key not in edu_seen:
                edu_seen.add(key)
                profile["education"].append(t["value"])
                provenance.append({"field": "education", "source": t["source"], "method": t["method"], "value": t["value"], "role": "primary"})

        cert_seen: set[str] = set()
        profile["certifications"] = []
        for t in ext.get("certifications", []):
            key = t["value"]["name"].lower()
            if key not in cert_seen:
                cert_seen.add(key)
                profile["certifications"].append(t["value"])
                provenance.append({"field": "certifications", "source": t["source"], "method": t["method"], "value": t["value"], "role": "primary"})

        for t in ext["experience"]:
            provenance.append({"field": "experience", "source": t["source"], "method": t["method"], "value": t["value"], "role": "primary"})

        profile["experience"] = sorted(
            [t["value"] for t in ext["experience"]],
            key=lambda e: (e.get("end") is None, e.get("start") or ""),
            reverse=True,
        )

        if profile["years_experience"] is None and profile["experience"]:
            starts = [e.get("start") for e in profile["experience"] if e.get("start")]
            if starts:
                try:
                    y, m = map(int, min(starts).split("-"))
                    today = date.today()
                    years = max(0, round((today.year - y) + (today.month - m) / 12))
                    profile["years_experience"] = years
                    provenance.append({"field": "years_experience", "source": "resume", "method": "derived", "value": years, "role": "primary"})
                except (ValueError, TypeError):
                    pass

        if profile["headline"] is None and profile["experience"]:
            e = profile["experience"][0]
            if e.get("title") and e.get("company"):
                profile["headline"] = f"{e['title']} at {e['company']}"
                provenance.append({"field": "headline", "source": "resume", "method": "derived", "value": profile["headline"], "role": "primary"})

        profile["provenance"] = provenance

        sources_used: list[str] = ["csv"]
        if rec.get("resume_raw") is not None:
            sources_used.append("resume")
        if rec.get("github_parsed") is not None:
            sources_used.append("github")

        profile["_meta"] = {
            "sources_used": sources_used,
            "sources_failed": rec["load_failed"],
            "generated_at": "",
        }
        profile["_has_conflict"] = rec.get("_has_conflict", False)
        profile["_load_failed"] = rec["load_failed"]
        profile["_had_github_url"] = bool((rec["csv"].get("github_url") or "").strip())
        profile["_had_resume_file"] = bool((rec["csv"].get("resume_file") or "").strip())

        profiles.append(profile)
    return profiles
