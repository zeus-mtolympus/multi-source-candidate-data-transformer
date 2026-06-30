from __future__ import annotations
import pytest
from pipeline.stage2.projection_engine import project

_P: dict = {
    "candidate_id": "cand_test001",
    "full_name": "Test User",
    "emails": ["test@example.com"],
    "phones": ["+919876543210"],
    "location": {"city": "Mumbai", "region": "Maharashtra", "country": "IN"},
    "links": {"linkedin": "https://linkedin.com/in/test", "github": None, "portfolio": None, "other": []},
    "headline": "Senior Engineer",
    "years_experience": 5,
    "skills": [
        {"name": "python", "confidence": 0.90, "sources": ["csv", "resume"]},
        {"name": "javascript", "confidence": 0.75, "sources": ["resume"]},
    ],
    "experience": [
        {"company": "TechCorp", "title": "Engineer", "start": "2022-01", "end": "2024-06"},
    ],
    "education": [],
    "provenance": [
        {"field": "full_name", "source": "csv", "method": "direct", "value": "Test User", "role": "primary"},
        {"field": "email", "source": "csv", "method": "direct", "value": "test@example.com", "role": "primary"},
        {"field": "phone", "source": "csv", "method": "direct", "value": "+919876543210", "role": "primary"},
        {"field": "location", "source": "csv", "method": "direct", "value": {"city": "Mumbai"}, "role": "primary"},
    ],
    "overall_confidence": 0.875,
    "match_confidence": 1.0,
    "_meta": {"sources_used": ["csv", "resume"], "sources_failed": [], "generated_at": ""},
}

_SPARSE: dict = {
    **_P,
    "emails": [],
    "phones": [],
    "skills": [],
    "experience": [],
    "links": {"linkedin": None, "github": None, "portfolio": None, "other": []},
}


def _cfg(**kwargs) -> dict:
    return {"fields": kwargs.pop("fields"), "on_missing": "null",
            "include_confidence": False, "include_provenance": False, **kwargs}


def test_from_omitted_defaults_to_path_segment() -> None:
    cfg = _cfg(fields=[{"path": "full_name", "type": "string"}])
    out, failures = project(_P, cfg)
    assert out["full_name"] == "Test User"
    assert not failures


def test_dot_path_from_builds_nested_output() -> None:
    cfg = _cfg(fields=[{"path": "city", "from": "location.city", "type": "string"}])
    out, failures = project(_P, cfg)
    assert out["city"] == "Mumbai"


def test_dot_path_output_nesting() -> None:
    cfg = _cfg(fields=[{"path": "loc.city", "from": "location.city", "type": "string"}])
    out, _ = project(_P, cfg)
    assert out["loc"]["city"] == "Mumbai"


def test_wildcard_maps_field_across_array() -> None:
    cfg = _cfg(fields=[{"path": "skills", "from": "skills[].name", "type": "string[]"}])
    out, failures = project(_P, cfg)
    assert out["skills"] == ["python", "javascript"]
    assert not failures


def test_index_picks_specific_item() -> None:
    cfg = _cfg(fields=[{"path": "first_email", "from": "emails[0]", "type": "string"}])
    out, _ = project(_P, cfg)
    assert out["first_email"] == "test@example.com"


def test_index_out_of_bounds_is_missing() -> None:
    cfg = _cfg(fields=[{"path": "second_email", "from": "emails[1]", "type": "string"}])
    out, _ = project(_P, cfg)
    assert out["second_email"] is None


def test_on_missing_null_adds_null_key() -> None:
    cfg = _cfg(fields=[{"path": "portfolio", "from": "links.portfolio", "type": "string"}])
    out, failures = project(_P, cfg)
    assert "portfolio" in out
    assert out["portfolio"] is None
    assert not failures


def test_on_missing_omit_removes_key() -> None:
    cfg = _cfg(on_missing="omit",
               fields=[{"path": "portfolio", "from": "links.portfolio", "type": "string"}])
    out, failures = project(_P, cfg)
    assert "portfolio" not in out
    assert not failures


def test_on_missing_error_produces_failure() -> None:
    cfg = _cfg(on_missing="error",
               fields=[{"path": "portfolio", "from": "links.portfolio", "type": "string"}])
    out, failures = project(_P, cfg)
    assert len(failures) == 1
    assert failures[0]["field"] == "portfolio"
    assert "on_missing=error" in failures[0]["reason"]


def test_required_overrides_on_missing_null() -> None:
    cfg = _cfg(on_missing="null",
               fields=[{"path": "email", "from": "emails[0]", "type": "string", "required": True}])
    _, failures = project(_SPARSE, cfg)
    assert any(f["field"] == "email" for f in failures)


def test_required_overrides_on_missing_omit() -> None:
    cfg = _cfg(on_missing="omit",
               fields=[{"path": "email", "from": "emails[0]", "type": "string", "required": True}])
    _, failures = project(_SPARSE, cfg)
    assert any(f["field"] == "email" for f in failures)


def test_normalize_national_reformats_phone() -> None:
    cfg = _cfg(fields=[{"path": "phone", "from": "phones[0]", "type": "string", "normalize": "national"}])
    out, _ = project(_P, cfg)
    assert out["phone"] != "+919876543210"
    assert "+" not in out["phone"]


def test_normalize_display_title_cases_skills() -> None:
    cfg = _cfg(fields=[{"path": "skills", "from": "skills[].name", "type": "string[]", "normalize": "display"}])
    out, _ = project(_P, cfg)
    assert "Python" in out["skills"]
    assert "Javascript" in out["skills"]


def test_normalize_human_converts_date() -> None:
    cfg = _cfg(fields=[{"path": "start", "from": "experience[0].start", "type": "string", "normalize": "human"}])
    out, _ = project(_P, cfg)
    assert out["start"] == "Jan 2022"


def test_normalize_human_end_date() -> None:
    cfg = _cfg(fields=[{"path": "end", "from": "experience[0].end", "type": "string", "normalize": "human"}])
    out, _ = project(_P, cfg)
    assert out["end"] == "Jun 2024"


def test_include_confidence_scalar_adds_sibling() -> None:
    cfg = _cfg(include_confidence=True,
               fields=[{"path": "full_name", "type": "string"}])
    out, _ = project(_P, cfg)
    assert "full_name_confidence" in out
    assert out["full_name_confidence"] == 0.90


def test_include_confidence_wildcard_embeds_in_items() -> None:
    cfg = _cfg(include_confidence=True,
               fields=[{"path": "skills", "from": "skills[].name", "type": "string[]"}])
    out, _ = project(_P, cfg)
    assert isinstance(out["skills"], list)
    assert isinstance(out["skills"][0], dict)
    assert "value" in out["skills"][0]
    assert "confidence" in out["skills"][0]
    assert out["skills"][0]["value"] == "python"
    assert out["skills"][0]["confidence"] == 0.90


def test_include_provenance_scalar_adds_sibling() -> None:
    cfg = _cfg(include_provenance=True,
               fields=[{"path": "full_name", "type": "string"}])
    out, _ = project(_P, cfg)
    assert "full_name_provenance" in out
    pv = out["full_name_provenance"]
    assert pv["source"] == "csv"
    assert pv["method"] == "direct"


def test_include_provenance_wildcard_embeds_in_items() -> None:
    cfg = _cfg(include_provenance=True,
               fields=[{"path": "skills", "from": "skills[].name", "type": "string[]"}])
    out, _ = project(_P, cfg)
    item = out["skills"][0]
    assert "provenance" in item
    assert "sources" in item["provenance"]


def test_confidence_and_provenance_both_in_wildcard_item() -> None:
    cfg = _cfg(include_confidence=True, include_provenance=True,
               fields=[{"path": "skills", "from": "skills[].name", "type": "string[]"}])
    out, _ = project(_P, cfg)
    item = out["skills"][0]
    assert {"value", "confidence", "provenance"} <= item.keys()


def test_raw_array_passthrough() -> None:
    cfg = _cfg(fields=[{"path": "experience", "from": "experience", "type": "object[]"}])
    out, _ = project(_P, cfg)
    assert isinstance(out["experience"], list)
    assert out["experience"][0]["company"] == "TechCorp"
