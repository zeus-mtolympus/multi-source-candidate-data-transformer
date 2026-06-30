from __future__ import annotations
from typing import Any

import pipeline.config as _cfg


def _base_score(source: str, method: str) -> float:
    return _cfg.BASE_SCORES.get((source, method), 0.50)


def score(profiles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for p in profiles:
        skill_map: dict[str, list[tuple[str, str]]] = p.pop("_skill_map", {})
        skills: list[dict] = []
        for name, source_methods in skill_map.items():
            unique_sources = list({sm[0] for sm in source_methods})
            base = max(_base_score(s, m) for s, m in source_methods)
            # ponytail: additive corroboration, documented simplification — not proportional
            conf = min(base + (len(unique_sources) - 1) * _cfg.CORROBORATION_BONUS, 1.0)
            skills.append({"name": name, "confidence": round(conf, 2), "sources": unique_sources})
        p["skills"] = sorted(skills, key=lambda s: s["confidence"], reverse=True)

        prov = p.get("provenance", [])
        prov_by_field: dict[str, list[dict]] = {}
        for entry in prov:
            if entry.get("role") == "primary":
                prov_by_field.setdefault(entry["field"], []).append(entry)

        def _field_conf(entries: list[dict]) -> float:
            if not entries:
                return 0.0
            base = max(_base_score(t["source"], t["method"]) for t in entries)
            unique_sources = {t["source"] for t in entries}
            return min(base + (len(unique_sources) - 1) * _cfg.CORROBORATION_BONUS, 1.0)

        # overall_confidence: ALL fields always included in denominator (weights sum to 1.0).
        # Missing fields score 0.0, so sparse stubs correctly score lower than enriched profiles.
        score_sum = 0.0
        for field, weight in _cfg.FIELD_WEIGHTS.items():
            if field == "skills":
                conf = (sum(s["confidence"] for s in skills) / len(skills)) if skills else 0.0
            elif field == "experience":
                # experience has no scalar provenance; presence implies resume section_heuristic
                conf = _base_score("resume", "section_heuristic") if p.get("experience") else 0.0
            elif field == "education":
                conf = _base_score("resume", "section_heuristic") if p.get("education") else 0.0
            elif field in ("emails", "phones"):
                key = "email" if field == "emails" else "phone"
                conf = _field_conf(prov_by_field.get(key, []))
            else:
                conf = _field_conf(prov_by_field.get(field, []))
            score_sum += conf * weight

        p["overall_confidence"] = round(score_sum, 3)

        had_github = p.pop("_had_github_url", False)
        had_resume = p.pop("_had_resume_file", False)
        load_failed = p.pop("_load_failed", [])
        has_conflict = p.pop("_has_conflict", False)

        if not had_github and not had_resume:
            match_conf: float | None = None
        else:
            any_loaded = (had_resume and "resume" not in load_failed) or (had_github and "github" not in load_failed)
            match_conf = 1.0 if any_loaded else 0.5
            if has_conflict:
                match_conf = round(match_conf - 0.10, 2) if match_conf is not None else None

        p["match_confidence"] = match_conf

    return profiles
