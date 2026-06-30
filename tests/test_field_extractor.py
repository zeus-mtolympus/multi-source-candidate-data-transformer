import pytest
from pipeline.stage1 import field_extractor


def _rec(csv_row: dict, resume_raw: str | None = None, github_parsed: dict | None = None):
    return {
        "csv": csv_row,
        "resume_raw": resume_raw,
        "github_raw": None,
        "github_parsed": github_parsed,
        "load_failed": [],
    }


def test_csv_direct_fields_extracted() -> None:
    rec = _rec({"name": "Alice Smith", "email": "alice@test.com", "phone": "+91 98765 43210",
                "headline": "Engineer", "years_experience": "5", "current_company": "Acme",
                "title": "SWE", "location_city": "Bangalore", "location_region": "Karnataka",
                "location_country": "India", "linkedin_url": "", "github_url": "", "portfolio_url": "",
                "resume_file": ""})
    result = field_extractor.extract([rec])[0]
    ext = result["extracted"]
    assert ext["full_name"][0]["value"] == "Alice Smith"
    assert ext["emails"][0]["value"] == "alice@test.com"
    assert ext["emails"][0]["method"] == "direct"
    assert ext["years_experience"][0]["value"] == 5
    assert ext["location"][0]["value"]["city"] == "Bangalore"


def test_resume_contact_extraction() -> None:
    resume = "Alice Smith\nalice@test.com | +91 98765 43210\n\nSkills\nPython"
    rec = _rec({"name": "Alice Smith", "email": "", "phone": "", "headline": "", "years_experience": "",
                "current_company": "", "title": "", "location_city": "", "location_region": "",
                "location_country": "", "linkedin_url": "", "github_url": "", "portfolio_url": "",
                "resume_file": "x"}, resume_raw=resume)
    result = field_extractor.extract([rec])[0]
    ext = result["extracted"]
    emails = [t["value"] for t in ext["emails"]]
    phones = [t["value"] for t in ext["phones"]]
    assert "alice@test.com" in emails
    assert any("+91" in p or "98765" in p for p in phones)


def test_reference_contacts_rejected() -> None:
    resume = "Alice Smith\nalice@test.com\n\nSkills\nPython\n\nReferences: Contact Bob at bob.ref@oldco.com or +91 99999 11111"
    rec = _rec({"name": "Alice Smith", "email": "", "phone": "", "headline": "", "years_experience": "",
                "current_company": "", "title": "", "location_city": "", "location_region": "",
                "location_country": "", "linkedin_url": "", "github_url": "", "portfolio_url": "",
                "resume_file": "x"}, resume_raw=resume)
    result = field_extractor.extract([rec])[0]
    ext = result["extracted"]
    emails = [t["value"] for t in ext["emails"]]
    phones = [t["value"] for t in ext["phones"]]
    assert "bob.ref@oldco.com" not in emails
    assert not any("99999" in p for p in phones)
    assert "alice@test.com" in emails


def test_github_language_inferred_skills() -> None:
    gh = {"name": "Alice", "repos": [{"name": "r1", "language": "Python"}, {"name": "r2", "language": "Go"}]}
    rec = _rec({"name": "Alice", "email": "", "phone": "", "headline": "", "years_experience": "",
                "current_company": "", "title": "", "location_city": "", "location_region": "",
                "location_country": "", "linkedin_url": "", "github_url": "https://github.com/alice",
                "portfolio_url": "", "resume_file": ""}, github_parsed=gh)
    result = field_extractor.extract([rec])[0]
    skills = result["extracted"]["skills"]
    methods = {s["method"] for s in skills}
    assert "language_inferred" in methods
    langs = {s["value"] for s in skills}
    assert "Python" in langs and "Go" in langs


def test_education_parsed_from_resume() -> None:
    resume = "Alice Smith\nalice@test.com\n\nEducation\nB.Tech Computer Science, IIT Madras, 2018\n"
    rec = _rec({"name": "Alice Smith", "email": "", "phone": "", "headline": "", "years_experience": "",
                "current_company": "", "title": "", "location_city": "", "location_region": "",
                "location_country": "", "linkedin_url": "", "github_url": "", "portfolio_url": "",
                "resume_file": "x"}, resume_raw=resume)
    result = field_extractor.extract([rec])[0]
    edu = result["extracted"]["education"]
    assert len(edu) == 1
    assert edu[0]["value"]["institution"] == "IIT Madras"
    assert edu[0]["value"]["end_year"] == 2018
    assert edu[0]["value"]["field"] == "Computer Science"


def test_experience_parsed_with_dates() -> None:
    resume = "Alice Smith\nalice@test.com\n\nExperience\nAcme Corp - Engineer\nJan 2022 - Present\nBuilt things.\n"
    rec = _rec({"name": "Alice Smith", "email": "", "phone": "", "headline": "", "years_experience": "",
                "current_company": "", "title": "", "location_city": "", "location_region": "",
                "location_country": "", "linkedin_url": "", "github_url": "", "portfolio_url": "",
                "resume_file": "x"}, resume_raw=resume)
    result = field_extractor.extract([rec])[0]
    exp = result["extracted"]["experience"]
    assert len(exp) == 1
    assert exp[0]["value"]["company"] == "Acme Corp"
    assert exp[0]["value"]["start"] == "Jan 2022"
    assert exp[0]["value"]["end"] is None


def test_name_extracted_from_resume_header() -> None:
    resume = "Alice Smith\nalice@test.com\n\nSkills\nPython"
    rec = _rec({"name": "", "email": "", "phone": "", "headline": "", "years_experience": "",
                "current_company": "", "title": "", "location_city": "", "location_region": "",
                "location_country": "", "linkedin_url": "", "github_url": "", "portfolio_url": "",
                "resume_file": "x"}, resume_raw=resume)
    result = field_extractor.extract([rec])[0]
    names = [t["value"] for t in result["extracted"]["full_name"] if t["source"] == "resume"]
    assert "Alice Smith" in names


def test_linkedin_url_extracted_from_resume() -> None:
    resume = "Alice Smith\nalice@test.com | linkedin.com/in/alice\n\nSkills\nPython"
    rec = _rec({"name": "Alice", "email": "", "phone": "", "headline": "", "years_experience": "",
                "current_company": "", "title": "", "location_city": "", "location_region": "",
                "location_country": "", "linkedin_url": "", "github_url": "", "portfolio_url": "",
                "resume_file": "x"}, resume_raw=resume)
    result = field_extractor.extract([rec])[0]
    resume_links = [t["value"] for t in result["extracted"]["links"] if t["source"] == "resume"]
    assert any(lv.get("linkedin") for lv in resume_links)


def test_certifications_extracted_from_resume() -> None:
    resume = "Alice Smith\nalice@test.com\n\nCertifications\n• AWS Certified Solutions Architect – Associate (2023)\n• Certified Kubernetes Administrator (CKA)\n\nSkills\nPython"
    rec = _rec({"name": "Alice Smith", "email": "", "phone": "", "headline": "", "years_experience": "",
                "current_company": "", "title": "", "location_city": "", "location_region": "",
                "location_country": "", "linkedin_url": "", "github_url": "", "portfolio_url": "",
                "resume_file": "x"}, resume_raw=resume)
    result = field_extractor.extract([rec])[0]
    certs = [t["value"] for t in result["extracted"]["certifications"]]
    names = [c["name"] for c in certs]
    assert any("AWS" in n for n in names)
    aws = next(c for c in certs if "AWS" in c["name"])
    assert aws["year"] == 2023
    cka = next(c for c in certs if "Kubernetes" in c["name"])
    assert cka["year"] is None


def test_github_location_split_into_city_country() -> None:
    gh = {"name": "Alice", "location": "Bangalore, India", "repos": []}
    rec = _rec({"name": "Alice", "email": "", "phone": "", "headline": "", "years_experience": "",
                "current_company": "", "title": "", "location_city": "", "location_region": "",
                "location_country": "", "linkedin_url": "", "github_url": "https://github.com/alice",
                "portfolio_url": "", "resume_file": ""}, github_parsed=gh)
    result = field_extractor.extract([rec])[0]
    locs = [t["value"] for t in result["extracted"]["location"] if t["source"] == "github"]
    assert len(locs) == 1
    assert locs[0]["city"] == "Bangalore"
    assert locs[0]["country"] == "India"
