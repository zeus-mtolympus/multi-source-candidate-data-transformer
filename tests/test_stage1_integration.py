import json
import pytest
from pathlib import Path

DATA_ROOT = Path(__file__).parent.parent


@pytest.fixture(scope="module")
def profiles():
    output = DATA_ROOT / "canonical_profiles.json"
    assert output.exists(), "Run orchestrator.py --stage stage1 first"
    return json.loads(output.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def by_name(profiles):
    return {p["full_name"]: p for p in profiles}


def test_total_profile_count(profiles) -> None:
    # 42 CSV rows - 4 duplicate pairs (Priya/Amitabh/Shruti/Nikhil) = 38 profiles
    assert len(profiles) == 38


def test_all_schema_keys_present(profiles) -> None:
    required = {"candidate_id", "full_name", "emails", "phones", "location", "links",
                "headline", "years_experience", "skills", "experience", "education",
                "certifications", "provenance", "overall_confidence", "match_confidence", "_meta"}
    for p in profiles:
        missing = required - p.keys()
        assert not missing, f"{p['full_name']} missing keys: {missing}"


def test_duplicate_email_collapses_to_one_profile(by_name) -> None:
    assert "Priya Singh" in by_name
    priya_count = sum(1 for p in by_name.values() if p["emails"] == ["priya.singh@innovate.co.in"])
    assert priya_count == 1


def test_duplicate_has_conflicting_alternate_in_provenance(by_name) -> None:
    p = by_name["Priya Singh"]
    alts = [x for x in p["provenance"] if x.get("role") == "conflicting_alternate"]
    assert len(alts) > 0
    alt_fields = {a["field"] for a in alts}
    assert "years_experience" in alt_fields


def test_broken_resume_in_sources_failed(by_name) -> None:
    # Ravi Shankar: resume_file set in CSV but file doesn't exist
    assert "resume" in by_name["Ravi Shankar"]["_meta"]["sources_failed"]
    assert "resume" in by_name["Neha Gupta"]["_meta"]["sources_failed"]


def test_broken_github_in_sources_failed(by_name) -> None:
    assert "github" in by_name["Vikram Patel"]["_meta"]["sources_failed"]
    assert "github" in by_name["Suresh Menon"]["_meta"]["sources_failed"]


def test_broken_github_gives_partial_match_confidence(by_name) -> None:
    assert by_name["Vikram Patel"]["match_confidence"] == 0.5


def test_minimal_candidate_has_null_not_missing_keys(by_name) -> None:
    p = by_name["Sneha Reddy"]
    assert p["headline"] is None
    assert p["years_experience"] is None
    assert p["skills"] == []
    assert p["experience"] == []
    assert p["education"] == []
    assert isinstance(p["emails"], list)
    assert isinstance(p["phones"], list)


def test_skills_alias_normalization(by_name) -> None:
    karan = by_name["Karan Iyer"]
    skill_names = {s["name"] for s in karan["skills"]}
    assert "python" in skill_names
    assert "javascript" in skill_names
    assert "postgresql" in skill_names
    assert "machine learning" in skill_names
    assert "pyhton" not in skill_names
    assert "JS" not in skill_names
    assert "ML" not in skill_names


def test_corroboration_boosts_confidence(by_name) -> None:
    karan = by_name["Karan Iyer"]
    skill_map = {s["name"]: s for s in karan["skills"]}
    assert "python" in skill_map
    assert skill_map["python"]["confidence"] > 0.65


def test_reference_contacts_not_in_profile(by_name) -> None:
    p = by_name["Deepak Malhotra"]
    assert "priya.hr@oldfirm.com" not in p["emails"]
    assert not any("99988" in ph for ph in p["phones"])


def test_unmerged_identity_pair_stays_separate(by_name) -> None:
    assert "Vivek Singh" in by_name
    assert "Vivek S. Singh" in by_name
    assert by_name["Vivek Singh"]["emails"] != by_name["Vivek S. Singh"]["emails"]


def test_candidate_id_format(profiles) -> None:
    for p in profiles:
        assert p["candidate_id"].startswith("cand_")
        assert len(p["candidate_id"]) == 17


def test_candidate_id_unique(profiles) -> None:
    ids = [p["candidate_id"] for p in profiles]
    assert len(ids) == len(set(ids))


def test_education_parsed_correctly(by_name) -> None:
    arjun = by_name["Arjun Mehta"]
    assert len(arjun["education"]) == 1
    edu = arjun["education"][0]
    assert edu["institution"] == "IIT Madras"
    assert edu["field"] == "Computer Science"
    assert edu["end_year"] == 2016


def test_experience_dates_normalized(by_name) -> None:
    arjun = by_name["Arjun Mehta"]
    exp = arjun["experience"]
    assert any(e["start"] == "2022-01" for e in exp)
    assert any(e["end"] == "2021-12" for e in exp)


def test_github_loaded_candidate_has_match_confidence_1(by_name) -> None:
    assert by_name["Neha Gupta"]["match_confidence"] == 1.0


def test_meta_generated_at_present(profiles) -> None:
    for p in profiles:
        assert p["_meta"]["generated_at"]


def test_new_duplicate_pair_collapses(by_name) -> None:
    # Shruti Kapoor and Shruti R. Kapoor share same email → only winner survives
    assert "Shruti R. Kapoor" in by_name
    assert "Shruti Kapoor" not in by_name
    # Nikhil Verma same pattern
    assert "Nikhil R. Verma" in by_name
    assert "Nikhil Verma" not in by_name


def test_broken_resume_new_candidate(by_name) -> None:
    # Ravi Shankar: resume_file set but file missing → sources_failed includes "resume"
    ravi = by_name["Ravi Shankar"]
    assert "resume" in ravi["_meta"]["sources_failed"]
    assert ravi["match_confidence"] == 0.5


def test_broken_github_new_candidate(by_name) -> None:
    # Preeta Subramaniam: github_url set but file missing, resume loaded OK
    preeta = by_name["Preeta Subramaniam"]
    assert "github" in preeta["_meta"]["sources_failed"]
    assert preeta["match_confidence"] == 1.0


def test_sparse_candidate_no_enrichment(by_name) -> None:
    farhan = by_name["Farhan Ali"]
    assert farhan["match_confidence"] is None
    assert farhan["skills"] == []


def test_certifications_extracted_for_enriched_candidates(by_name) -> None:
    arjun = by_name["Arjun Mehta"]
    assert len(arjun["certifications"]) >= 1
    cert_names = [c["name"] for c in arjun["certifications"]]
    assert any("AWS" in n for n in cert_names)


def test_data_quality_warnings_in_meta(by_name) -> None:
    # CSV-only candidate should have all three warnings
    farhan = by_name["Farhan Ali"]
    dq = farhan["_meta"]["data_quality"]
    assert "no_skills" in dq
    assert "no_experience" in dq
    assert "no_enrichment" in dq

    # Fully enriched candidate should have no warnings
    arjun = by_name["Arjun Mehta"]
    assert arjun["_meta"]["data_quality"] == []


def test_enriched_profile_confidence_exceeds_stub(by_name) -> None:
    arjun = by_name["Arjun Mehta"]
    farhan = by_name["Farhan Ali"]
    assert arjun["overall_confidence"] > farhan["overall_confidence"]


def test_skill_alias_normalization_new_candidates(by_name) -> None:
    # Varun Gupta: Golang->go, k8s->kubernetes, TDD, gRPC
    varun_skills = {s["name"] for s in by_name["Varun Gupta"]["skills"]}
    assert "go" in varun_skills
    assert "kubernetes" in varun_skills
    assert "golang" not in varun_skills
    assert "k8s" not in varun_skills

    # Shreya Kapoor: sklearn->scikit-learn, Pyhton->python, PowerBI->power bi
    shreya_skills = {s["name"] for s in by_name["Shreya Kapoor"]["skills"]}
    assert "scikit-learn" in shreya_skills
    assert "python" in shreya_skills
    assert "power bi" in shreya_skills
    assert "sklearn" not in shreya_skills
    assert "pyhton" not in shreya_skills

    # Tanveer Ahmed: Postgress->postgresql, TS->typescript
    tanveer_skills = {s["name"] for s in by_name["Tanveer Ahmed"]["skills"]}
    assert "postgresql" in tanveer_skills
    assert "typescript" in tanveer_skills
