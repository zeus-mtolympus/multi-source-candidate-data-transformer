import pytest
from pipeline.stage1 import merge_engine


def _tagged(value, method="direct", source="csv"):
    return {"value": value, "method": method, "source": source}


def _rec(extracted: dict, load_failed=None, csv_row=None, resume_raw=None, github_parsed=None, earlier_rows=None):
    rec = {
        "csv": csv_row or {},
        "load_failed": load_failed or [],
        "resume_raw": resume_raw,
        "github_parsed": github_parsed,
        "extracted": {
            "full_name": [], "emails": [], "phones": [], "location": [],
            "headline": [], "years_experience": [], "current_company": [],
            "title": [], "links": [], "skills": [], "experience": [], "education": [], "certifications": [],
            **extracted,
        },
    }
    if earlier_rows:
        rec["_earlier_rows"] = earlier_rows
        rec["_has_conflict"] = True
    return rec


def test_csv_beats_github_for_scalar() -> None:
    rec = _rec({
        "full_name": [_tagged("CSV Name", "direct", "csv"), _tagged("GH Name", "direct", "github")],
    })
    profiles = merge_engine.merge([rec])
    assert profiles[0]["full_name"] == "CSV Name"


def test_loser_in_provenance_as_alternate() -> None:
    rec = _rec({
        "full_name": [_tagged("CSV Name", "direct", "csv"), _tagged("GH Name", "direct", "github")],
    })
    profiles = merge_engine.merge([rec])
    alts = [p for p in profiles[0]["provenance"] if p.get("role") == "conflicting_alternate"]
    assert any(a["value"] == "GH Name" for a in alts)


def test_skills_are_unioned() -> None:
    rec = _rec({
        "skills": [
            _tagged("python", "regex_extracted", "resume"),
            _tagged("go", "language_inferred", "github"),
        ],
    })
    profiles = merge_engine.merge([rec])
    skill_names = set(profiles[0]["_skill_map"].keys())
    assert {"python", "go"} == skill_names


def test_emails_collected_and_deduped() -> None:
    rec = _rec({
        "emails": [
            _tagged("a@test.com", "direct", "csv"),
            _tagged("A@TEST.COM", "direct", "github"),
            _tagged("b@test.com", "regex_extracted", "resume"),
        ],
    })
    profiles = merge_engine.merge([rec])
    emails_lower = [e.lower() for e in profiles[0]["emails"]]
    assert emails_lower.count("a@test.com") == 1
    assert "b@test.com" in emails_lower


def test_earlier_duplicate_in_provenance() -> None:
    earlier_extracted = {
        "emails": [_tagged("dup@test.com", "direct", "csv")],
        "phones": [_tagged("+911234567890", "direct", "csv")],
        "full_name": [_tagged("Old Name", "direct", "csv")],
        "headline": [], "years_experience": [], "current_company": [], "title": [],
        "links": [], "skills": [], "experience": [], "education": [], "location": [],
    }
    earlier = {"csv": {"email": "dup@test.com"}, "load_failed": [], "extracted": earlier_extracted}
    rec = _rec({"emails": [_tagged("dup@test.com", "direct", "csv")]}, earlier_rows=[earlier])
    profiles = merge_engine.merge([rec])
    roles = [p["role"] for p in profiles[0]["provenance"]]
    assert "conflicting_alternate" in roles


def test_location_null_when_absent() -> None:
    rec = _rec({"location": []})
    profiles = merge_engine.merge([rec])
    assert profiles[0]["location"] == {"city": None, "region": None, "country": None}


def test_experience_sorted_most_recent_first() -> None:
    rec = _rec({
        "experience": [
            _tagged({"company": "Old Co", "title": "Dev", "start": "2015-01", "end": "2018-12", "summary": ""}, "section_heuristic", "resume"),
            _tagged({"company": "New Co", "title": "Lead", "start": "2020-06", "end": None, "summary": ""}, "section_heuristic", "resume"),
            _tagged({"company": "Mid Co", "title": "Eng", "start": "2019-01", "end": "2020-05", "summary": ""}, "section_heuristic", "resume"),
        ],
    })
    profiles = merge_engine.merge([rec])
    exp = profiles[0]["experience"]
    assert exp[0]["company"] == "New Co"   # current role (end=None) first
    assert exp[1]["company"] == "Mid Co"
    assert exp[2]["company"] == "Old Co"


def test_years_experience_derived_from_spans_when_csv_absent() -> None:
    rec = _rec({
        "years_experience": [],  # nothing from CSV
        "experience": [
            _tagged({"company": "Co", "title": "Eng", "start": "2015-01", "end": None, "summary": ""}, "section_heuristic", "resume"),
        ],
    })
    profiles = merge_engine.merge([rec])
    assert profiles[0]["years_experience"] is not None
    assert profiles[0]["years_experience"] >= 9  # at least 9 years since 2015
    derived = [e for e in profiles[0]["provenance"] if e["field"] == "years_experience" and e["method"] == "derived"]
    assert len(derived) == 1


def test_years_experience_not_overwritten_when_csv_present() -> None:
    rec = _rec({
        "years_experience": [_tagged(5, "direct", "csv")],
        "experience": [
            _tagged({"company": "Co", "title": "Eng", "start": "2015-01", "end": None, "summary": ""}, "section_heuristic", "resume"),
        ],
    })
    profiles = merge_engine.merge([rec])
    assert profiles[0]["years_experience"] == 5  # CSV wins, derivation skipped


def test_headline_derived_from_experience_when_absent() -> None:
    rec = _rec({
        "headline": [],
        "experience": [
            _tagged({"company": "Acme", "title": "Staff Eng", "start": "2022-01", "end": None, "summary": ""}, "section_heuristic", "resume"),
        ],
    })
    profiles = merge_engine.merge([rec])
    assert profiles[0]["headline"] == "Staff Eng at Acme"
    derived = [e for e in profiles[0]["provenance"] if e["field"] == "headline" and e["method"] == "derived"]
    assert len(derived) == 1


def test_headline_not_overwritten_when_present() -> None:
    rec = _rec({
        "headline": [_tagged("Senior Engineer", "direct", "csv")],
        "experience": [
            _tagged({"company": "Acme", "title": "Staff Eng", "start": "2022-01", "end": None, "summary": ""}, "section_heuristic", "resume"),
        ],
    })
    profiles = merge_engine.merge([rec])
    assert profiles[0]["headline"] == "Senior Engineer"  # CSV wins, derivation skipped


def test_certifications_unioned_and_deduped() -> None:
    cert = {"name": "AWS Certified Solutions Architect", "year": 2023}
    rec = _rec({
        "certifications": [
            _tagged(cert, "section_heuristic", "resume"),
            _tagged(cert, "section_heuristic", "resume"),  # duplicate
        ],
    })
    profiles = merge_engine.merge([rec])
    certs = profiles[0]["certifications"]
    assert len(certs) == 1
    assert certs[0]["name"] == "AWS Certified Solutions Architect"
    assert certs[0]["year"] == 2023


def test_links_are_provenance_tracked() -> None:
    rec = _rec({
        "links": [
            _tagged({"linkedin": "https://linkedin.com/in/x", "github": None, "portfolio": None, "other": []}, "direct", "csv"),
        ],
    })
    profiles = merge_engine.merge([rec])
    links_prov = [p for p in profiles[0]["provenance"] if p["field"] == "links"]
    assert len(links_prov) == 1
    assert links_prov[0]["role"] == "primary"
    assert links_prov[0]["value"] == "https://linkedin.com/in/x"


def test_links_conflict_recorded_as_alternate() -> None:
    rec = _rec({
        "links": [
            _tagged({"linkedin": "https://linkedin.com/in/csv", "github": None, "portfolio": None, "other": []}, "direct", "csv"),
            _tagged({"linkedin": "https://linkedin.com/in/resume", "github": None, "portfolio": None, "other": []}, "regex_extracted", "resume"),
        ],
    })
    profiles = merge_engine.merge([rec])
    roles = {p["role"] for p in profiles[0]["provenance"] if p["field"] == "links"}
    assert roles == {"primary", "conflicting_alternate"}


def test_experience_education_certifications_are_provenance_tracked() -> None:
    rec = _rec({
        "experience": [_tagged({"company": "Co", "title": "Eng", "start": "2020-01", "end": None, "summary": ""}, "section_heuristic", "resume")],
        "education": [_tagged({"institution": "IIT", "degree": "B.Tech", "field": "CS", "end_year": 2018}, "section_heuristic", "resume")],
        "certifications": [_tagged({"name": "AWS Cert", "year": 2023}, "section_heuristic", "resume")],
    })
    profiles = merge_engine.merge([rec])
    prov_fields = {p["field"] for p in profiles[0]["provenance"]}
    assert {"experience", "education", "certifications"} <= prov_fields


def test_duplicate_provenance_uses_singular_field_names() -> None:
    earlier_extracted = {
        "emails": [_tagged("dup@test.com", "direct", "csv")],
        "phones": [_tagged("+911234567890", "direct", "csv")],
        "full_name": [_tagged("Old Name", "direct", "csv")],
        "headline": [], "years_experience": [], "current_company": [], "title": [],
        "links": [], "skills": [], "experience": [], "education": [], "location": [],
    }
    earlier = {"csv": {}, "load_failed": [], "extracted": earlier_extracted}
    rec = _rec({"emails": [_tagged("dup@test.com", "direct", "csv")]}, earlier_rows=[earlier])
    profiles = merge_engine.merge([rec])
    prov_fields = {e["field"] for e in profiles[0]["provenance"]}
    assert "phones" not in prov_fields  # must be "phone" not "phones"
    assert "emails" not in prov_fields  # must be "email" not "emails"
    assert "phone" in prov_fields
    assert "email" in prov_fields
