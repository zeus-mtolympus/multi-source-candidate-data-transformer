import pytest
from pipeline.stage1 import entity_resolver


def _rec(email: str, name: str = "Test"):
    return {
        "csv": {"email": email, "name": name},
        "load_failed": [],
        "extracted": {
            "emails": [{"value": email, "method": "direct", "source": "csv"}] if email else [],
            "full_name": [{"value": name, "method": "direct", "source": "csv"}],
            "phones": [], "location": [], "headline": [], "years_experience": [],
            "current_company": [], "title": [], "links": [], "skills": [], "experience": [], "education": [],
        },
    }


def test_same_email_deduped_to_one() -> None:
    recs = [_rec("alice@test.com", "Alice"), _rec("alice@test.com", "Alice")]
    result = entity_resolver.resolve(recs)
    assert len(result) == 1


def test_last_row_wins() -> None:
    r1 = _rec("dup@test.com", "Old Name")
    r2 = _rec("dup@test.com", "New Name")
    result = entity_resolver.resolve([r1, r2])
    assert result[0]["csv"]["name"] == "New Name"


def test_earlier_row_attached_as_earlier_rows() -> None:
    r1 = _rec("dup@test.com", "Old")
    r2 = _rec("dup@test.com", "New")
    result = entity_resolver.resolve([r1, r2])
    assert "_earlier_rows" in result[0]
    assert result[0]["_has_conflict"] is True


def test_different_emails_not_deduped() -> None:
    recs = [_rec("a@test.com"), _rec("b@test.com")]
    result = entity_resolver.resolve(recs)
    assert len(result) == 2


def test_no_email_not_deduped() -> None:
    r1 = _rec("")
    r2 = _rec("")
    result = entity_resolver.resolve([r1, r2])
    assert len(result) == 2


def test_email_comparison_is_case_insensitive() -> None:
    recs = [_rec("Alice@Test.COM"), _rec("alice@test.com")]
    result = entity_resolver.resolve(recs)
    assert len(result) == 1
