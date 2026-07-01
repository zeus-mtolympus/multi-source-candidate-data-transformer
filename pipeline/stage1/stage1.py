from __future__ import annotations
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import source_loader, parser, field_extractor, normalizer, entity_resolver, merge_engine, confidence_calculator


def _normalize_records(records: list[dict]) -> None:
    for rec in records:
        ext = rec["extracted"]

        for t in ext["full_name"]:
            v = normalizer.normalize_name(t["value"])
            if v:
                t["value"] = v

        normalized_phones: list[dict] = []
        for t in ext["phones"]:
            v = normalizer.normalize_phone(t["value"])
            if v is not None:
                t["value"] = v
                normalized_phones.append(t)
        ext["phones"] = normalized_phones

        for t in ext["location"]:
            loc = t["value"]
            if isinstance(loc, dict) and loc.get("country"):
                loc["country"] = normalizer.normalize_country(loc["country"])

        normalized_skills: list[dict] = []
        for t in ext["skills"]:
            v = normalizer.normalize_skill(t["value"])
            if v:
                t["value"] = v
                normalized_skills.append(t)
        ext["skills"] = normalized_skills

        for t in ext["experience"]:
            exp = t["value"]
            if exp.get("start"):
                exp["start"] = normalizer.normalize_date(exp["start"])
            if exp.get("end"):
                exp["end"] = normalizer.normalize_date(exp["end"])

        for t in ext["links"]:
            lv = t["value"]
            for k in ("linkedin", "github", "portfolio"):
                if lv.get(k):
                    lv[k] = normalizer.normalize_url(lv[k])


def _candidate_id(profile: dict[str, Any]) -> str:
    emails = profile.get("emails", [])
    phones = profile.get("phones", [])

    if emails:
        seed = emails[0].lower()
    elif phones:
        seed = phones[0]
    else:
        raise ValueError(f"Cannot generate candidate_id: no email or phone for candidate '{profile.get('full_name')}'")

    digest = hashlib.sha256(seed.encode()).hexdigest()[:12]
    return f"cand_{digest}"


def _ensure_schema(profile: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "candidate_id": profile.get("candidate_id"),
        "full_name": profile.get("full_name"),
        "emails": profile.get("emails") or [],
        "phones": profile.get("phones") or [],
        "location": profile.get("location") or {"city": None, "region": None, "country": None},
        "links": profile.get("links") or {"linkedin": None, "github": None, "portfolio": None, "other": []},
        "headline": profile.get("headline"),
        "current_company": profile.get("current_company"),
        "title": profile.get("title"),
        "years_experience": profile.get("years_experience"),
        "skills": profile.get("skills") or [],
        "experience": profile.get("experience") or [],
        "education": profile.get("education") or [],
        "certifications": profile.get("certifications") or [],
        "provenance": profile.get("provenance") or [],
        "overall_confidence": profile.get("overall_confidence"),
        "match_confidence": profile.get("match_confidence"),
        "_meta": profile.get("_meta") or {"sources_used": [], "sources_failed": [], "generated_at": ""},
    }
    return out


def run(data_root: Path) -> list[dict[str, Any]]:
    records = source_loader.load(data_root)
    records = parser.parse(records)
    records = field_extractor.extract(records)
    _normalize_records(records)
    records = entity_resolver.resolve(records)
    profiles = merge_engine.merge(records)
    profiles = confidence_calculator.score(profiles)

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    kept: list[dict[str, Any]] = []
    skipped = 0
    for p in profiles:
        try:
            p["candidate_id"] = _candidate_id(p)
        except ValueError:
            skipped += 1
            continue
        p["_meta"]["generated_at"] = generated_at
        kept.append(p)
    profiles = [_ensure_schema(p) for p in kept]

    # Data quality warnings — surfaced in _meta for downstream consumers
    for p in profiles:
        warnings: list[str] = []
        if not p["skills"]:
            warnings.append("no_skills")
        if not p["experience"]:
            warnings.append("no_experience")
        if p["_meta"]["sources_used"] == ["csv"]:
            warnings.append("no_enrichment")
        p["_meta"]["data_quality"] = warnings

    output_path = data_root / "canonical_profiles.json"
    output_path.write_text(json.dumps(profiles, indent=2, default=str), encoding="utf-8")

    # Run summary
    total = len(profiles)
    enriched = sum(1 for p in profiles if len(p["_meta"]["sources_used"]) > 1)
    no_skills = sum(1 for p in profiles if not p["skills"])
    source_failures = sum(len(p["_meta"]["sources_failed"]) for p in profiles)
    with_certs = sum(1 for p in profiles if p["certifications"])
    print(f"Stage 1 complete: {total} profiles -> {output_path}")
    print(f"  Enrichment : {enriched}/{total} profiles have resume or github")
    print(f"  Skills     : {total - no_skills}/{total} profiles have skills")
    print(f"  Certs      : {with_certs} profiles have certifications")
    if source_failures:
        print(f"  Failures   : {source_failures} source load failures (see sources_failed in _meta)")
    if skipped:
        print(f"  Skipped    : {skipped} candidate(s) dropped - no email or phone to build a candidate_id from")

    return profiles
