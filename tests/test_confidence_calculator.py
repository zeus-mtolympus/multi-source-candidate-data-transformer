import pytest
from pipeline.stage1 import confidence_calculator


def _profile(skill_map=None, provenance=None, had_github=False, had_resume=False, load_failed=None, has_conflict=False):
    return {
        "_skill_map": skill_map or {},
        "provenance": provenance or [],
        "full_name": None, "headline": None, "years_experience": None,
        "current_company": None, "title": None,
        "emails": [], "phones": [], "location": {}, "links": {}, "experience": [], "education": [],
        "_had_github_url": had_github,
        "_had_resume_file": had_resume,
        "_load_failed": load_failed or [],
        "_has_conflict": has_conflict,
    }


def test_csv_skill_base_score() -> None:
    p = _profile(skill_map={"python": [("resume", "regex_extracted")]})
    result = confidence_calculator.score([p])[0]
    skill = next(s for s in result["skills"] if s["name"] == "python")
    assert skill["confidence"] == 0.65


def test_corroboration_bonus() -> None:
    p = _profile(skill_map={"python": [("resume", "regex_extracted"), ("github", "language_inferred")]})
    result = confidence_calculator.score([p])[0]
    skill = next(s for s in result["skills"] if s["name"] == "python")
    assert skill["confidence"] == 0.75


def test_confidence_capped_at_1() -> None:
    p = _profile(skill_map={"python": [("csv", "direct"), ("resume", "regex_extracted"), ("github", "language_inferred")]})
    result = confidence_calculator.score([p])[0]
    skill = next(s for s in result["skills"] if s["name"] == "python")
    assert skill["confidence"] <= 1.0


def test_match_confidence_none_when_no_enrichment() -> None:
    p = _profile()
    result = confidence_calculator.score([p])[0]
    assert result["match_confidence"] is None


def test_match_confidence_1_when_github_loaded() -> None:
    p = _profile(had_github=True, load_failed=[])
    result = confidence_calculator.score([p])[0]
    assert result["match_confidence"] == 1.0


def test_match_confidence_05_when_link_failed() -> None:
    p = _profile(had_github=True, load_failed=["github"])
    result = confidence_calculator.score([p])[0]
    assert result["match_confidence"] == 0.5


def test_match_confidence_lowered_for_conflict() -> None:
    p = _profile(had_github=True, load_failed=[], has_conflict=True)
    result = confidence_calculator.score([p])[0]
    assert result["match_confidence"] == 0.9


def test_overall_confidence_computed_from_fields() -> None:
    prov = [{"field": "full_name", "source": "csv", "method": "direct", "role": "primary", "value": "Alice"}]
    p = _profile(provenance=prov)
    result = confidence_calculator.score([p])[0]
    assert result["overall_confidence"] > 0


def test_enriched_profile_scores_higher_than_stub() -> None:
    prov = [
        {"field": "full_name", "source": "csv", "method": "direct", "role": "primary", "value": "X"},
        {"field": "email", "source": "csv", "method": "direct", "role": "primary", "value": "x@x.com"},
    ]
    stub = _profile(provenance=prov)

    rich = _profile(
        skill_map={"python": [("resume", "regex_extracted")]},
        provenance=prov,
    )
    rich["experience"] = [{"company": "Co", "title": "Eng", "start": "2020-01", "end": None, "summary": ""}]
    rich["education"] = [{"institution": "IIT", "degree": "B.Tech", "field": "CS", "end_year": 2018}]

    stub_result = confidence_calculator.score([stub])[0]
    rich_result = confidence_calculator.score([rich])[0]
    assert rich_result["overall_confidence"] > stub_result["overall_confidence"]


def test_missing_key_fields_penalise_overall_confidence() -> None:
    # Only full_name populated: 0.90 * 0.20 = 0.18; all other fields 0
    prov = [{"field": "full_name", "source": "csv", "method": "direct", "role": "primary", "value": "X"}]
    p = _profile(provenance=prov)
    result = confidence_calculator.score([p])[0]
    assert abs(result["overall_confidence"] - 0.18) < 0.01
