import pytest
from pipeline.stage1 import normalizer


def test_normalize_date_month_year() -> None:
    assert normalizer.normalize_date("Jan 2022") == "2022-01"
    assert normalizer.normalize_date("March 2019") == "2019-03"
    assert normalizer.normalize_date("Dec 2021") == "2021-12"


def test_normalize_date_year_only() -> None:
    assert normalizer.normalize_date("2021") == "2021-01"


def test_normalize_date_unparseable_returns_none() -> None:
    assert normalizer.normalize_date("Present") is None
    assert normalizer.normalize_date("garbage") is None
    assert normalizer.normalize_date(None) is None


def test_normalize_phone_indian() -> None:
    result = normalizer.normalize_phone("+91 98765 43210")
    assert result == "+919876543210"


def test_normalize_phone_us() -> None:
    result = normalizer.normalize_phone("+1 (415) 555-0123")
    assert result == "+14155550123"


def test_normalize_phone_invalid_dropped() -> None:
    assert normalizer.normalize_phone("not a phone") is None
    assert normalizer.normalize_phone("123") is None
    assert normalizer.normalize_phone(None) is None


def test_normalize_country_india() -> None:
    assert normalizer.normalize_country("India") == "IN"


def test_normalize_country_unknown_returns_none() -> None:
    assert normalizer.normalize_country("Nowhere Land") is None
    assert normalizer.normalize_country(None) is None


def test_normalize_skill_alias() -> None:
    assert normalizer.normalize_skill("JS") == "javascript"
    assert normalizer.normalize_skill("Postgres") == "postgresql"
    assert normalizer.normalize_skill("ML") == "machine learning"


def test_normalize_skill_typo_via_rapidfuzz() -> None:
    result = normalizer.normalize_skill("Pyhton")
    assert result == "python"


def test_normalize_skill_canonical_passthrough() -> None:
    assert normalizer.normalize_skill("Python") == "python"
    assert normalizer.normalize_skill("docker") == "docker"


def test_normalize_skill_unknown_kept_as_lowercase() -> None:
    result = normalizer.normalize_skill("Leadership")
    assert result == "leadership"


def test_normalize_skill_none() -> None:
    assert normalizer.normalize_skill(None) is None


def test_normalize_url_adds_https() -> None:
    assert normalizer.normalize_url("linkedin.com/in/alice") == "https://linkedin.com/in/alice"
    assert normalizer.normalize_url("github.com/alice") == "https://github.com/alice"


def test_normalize_url_preserves_existing_scheme() -> None:
    assert normalizer.normalize_url("https://alice.dev") == "https://alice.dev"
    assert normalizer.normalize_url("http://alice.dev") == "http://alice.dev"


def test_normalize_url_none_returns_none() -> None:
    assert normalizer.normalize_url(None) is None
    assert normalizer.normalize_url("") is None
