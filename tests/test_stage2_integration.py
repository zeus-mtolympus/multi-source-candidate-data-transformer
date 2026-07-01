from __future__ import annotations
import json
import pytest
from pathlib import Path

DATA_ROOT = Path(__file__).parent.parent
CONFIGS = DATA_ROOT / "configs"
OUTPUT = DATA_ROOT / "output"


def _load(stem: str) -> dict:
    return json.loads((OUTPUT / f"{stem}_output.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module", autouse=True)
def outputs_exist() -> None:
    for stem in ("minimal_ats", "default_full", "display_export",
                 "strict_required_linkedin", "optional_strict_on_missing_error"):
        assert (OUTPUT / f"{stem}_output.json").exists(), f"Run stage2 with {stem}.json first"


def test_broken_config_rejected_before_any_output() -> None:
    from pipeline.stage2.schema_validator import validate_config
    cfg = json.loads((CONFIGS / "broken_type_mismatch.json").read_text())
    with pytest.raises(ValueError, match="wildcard"):
        validate_config(cfg)


def test_minimal_ats_all_succeed() -> None:
    out = _load("minimal_ats")
    assert out["_meta"]["total"] == 38
    assert out["_meta"]["succeeded"] == 38
    assert out["_meta"]["failed"] == 0
    assert out["failures"] == []


def test_minimal_ats_on_missing_omit_removes_keys() -> None:
    out = _load("minimal_ats")
    by_name = {r["full_name"]: r for r in out["results"]}
    sneha = by_name["Sneha Reddy"]
    assert "current_title" not in sneha
    assert "current_company" not in sneha


def test_minimal_ats_csv_only_current_role_not_dropped() -> None:
    # Priya Singh is CSV-only (no resume/experience[]) but the CSV directly gives
    # current_company/title — that must not be silently dropped from the output.
    out = _load("minimal_ats")
    by_name = {r["full_name"]: r for r in out["results"]}
    priya = by_name["Priya Singh"]
    assert priya["current_title"] == "Lead Product Manager"
    assert priya["current_company"] == "Innovate Solutions"


def test_minimal_ats_has_required_fields() -> None:
    out = _load("minimal_ats")
    for r in out["results"]:
        assert "full_name" in r
        assert "email" in r


def test_minimal_ats_phone_is_e164() -> None:
    out = _load("minimal_ats")
    by_name = {r["full_name"]: r for r in out["results"]}
    arjun = by_name["Arjun Mehta"]
    assert arjun["phone"].startswith("+")


def test_display_export_national_phone_format() -> None:
    out = _load("display_export")
    by_name = {r["full_name"]: r for r in out["results"]}
    arjun = by_name["Arjun Mehta"]
    assert arjun["phone_display"] is not None
    assert not arjun["phone_display"].startswith("+91")


def test_display_export_skills_title_cased() -> None:
    out = _load("display_export")
    by_name = {r["full_name"]: r for r in out["results"]}
    skills = by_name["Arjun Mehta"]["top_skills"]
    assert "Python" in skills
    assert "python" not in skills


def test_display_export_human_date() -> None:
    out = _load("display_export")
    by_name = {r["full_name"]: r for r in out["results"]}
    assert by_name["Arjun Mehta"]["most_recent_start"] == "Jan 2022"


def test_display_export_missing_optional_is_null() -> None:
    out = _load("display_export")
    by_name = {r["full_name"]: r for r in out["results"]}
    sneha = by_name["Sneha Reddy"]
    assert sneha["most_recent_role"] is None
    assert sneha["most_recent_start"] is None


def test_default_full_all_succeed() -> None:
    out = _load("default_full")
    assert out["_meta"]["succeeded"] == 38
    assert out["_meta"]["failed"] == 0


def test_default_full_confidence_scalar_sibling() -> None:
    out = _load("default_full")
    arjun = next(r for r in out["results"] if r["full_name"] == "Arjun Mehta")
    assert arjun.get("full_name_confidence") == 0.90
    assert arjun.get("full_name_provenance") == {"source": "csv", "method": "direct"}


def test_default_full_skills_wildcard_confidence_embedded() -> None:
    out = _load("default_full")
    arjun = next(r for r in out["results"] if r["full_name"] == "Arjun Mehta")
    skill = next(s for s in arjun["skills"] if s["value"] == "python")
    assert "confidence" in skill
    assert "provenance" in skill
    assert skill["confidence"] > 0


def test_default_full_nested_location_output() -> None:
    out = _load("default_full")
    arjun = next(r for r in out["results"] if r["full_name"] == "Arjun Mehta")
    assert arjun["location"]["city"] == "Bangalore"


def test_strict_required_linkedin_counts() -> None:
    out = _load("strict_required_linkedin")
    assert out["_meta"]["succeeded"] == 35
    assert out["_meta"]["failed"] == 3


def test_strict_required_linkedin_known_failures() -> None:
    out = _load("strict_required_linkedin")
    failed_ids = {f["candidate_id"] for f in out["failures"]}
    assert "cand_36b03b610e89" in failed_ids  # Sneha Reddy
    assert "cand_5ce35f3097ae" in failed_ids  # Pooja Nair
    assert "cand_4203bb21031a" in failed_ids  # Farhan Ali


def test_strict_required_linkedin_failure_fields() -> None:
    out = _load("strict_required_linkedin")
    for f in out["failures"]:
        assert f["field"] == "linkedin"


def test_optional_strict_on_missing_error_counts() -> None:
    out = _load("optional_strict_on_missing_error")
    assert out["_meta"]["total"] == 38
    assert out["_meta"]["succeeded"] == 11
    assert out["_meta"]["failed"] == 27


def test_optional_strict_on_missing_error_failure_reason() -> None:
    out = _load("optional_strict_on_missing_error")
    for f in out["failures"]:
        assert "on_missing=error" in f["reason"]
        assert f["field"] == "portfolio"


def test_optional_strict_success_has_portfolio() -> None:
    out = _load("optional_strict_on_missing_error")
    arjun = next(r for r in out["results"] if r["full_name"] == "Arjun Mehta")
    assert arjun["portfolio"] is not None
    assert arjun["portfolio"].startswith("http")


def test_meta_shape_present_on_all_outputs() -> None:
    for stem in ("minimal_ats", "default_full", "display_export",
                 "strict_required_linkedin", "optional_strict_on_missing_error"):
        out = _load(stem)
        meta = out["_meta"]
        assert "config_used" in meta
        assert "generated_at" in meta
        assert meta["total"] == meta["succeeded"] + meta["failed"]
