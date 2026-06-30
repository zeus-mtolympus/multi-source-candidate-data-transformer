from __future__ import annotations
import pytest
from pipeline.stage2.schema_validator import validate_config, validate_output


def test_validate_config_passes_valid() -> None:
    cfg = {"fields": [
        {"path": "skills", "from": "skills[].name", "type": "string[]"},
        {"path": "name", "type": "string"},
    ]}
    validate_config(cfg)


def test_validate_config_rejects_wildcard_with_scalar_type() -> None:
    cfg = {"fields": [{"path": "skills", "from": "skills[].name", "type": "string"}]}
    with pytest.raises(ValueError, match="wildcard"):
        validate_config(cfg)


def test_validate_config_rejects_wildcard_with_object_scalar() -> None:
    cfg = {"fields": [{"path": "edu", "from": "education[].institution", "type": "object"}]}
    with pytest.raises(ValueError):
        validate_config(cfg)


def test_validate_config_allows_wildcard_with_object_list() -> None:
    cfg = {"fields": [{"path": "edu", "from": "education[].institution", "type": "string[]"}]}
    validate_config(cfg)


def test_validate_output_passes_correct_types() -> None:
    cfg = {"fields": [
        {"path": "name", "type": "string"},
        {"path": "years", "type": "number"},
        {"path": "skills", "type": "string[]"},
    ], "include_confidence": False, "include_provenance": False}
    output = {"name": "Alice", "years": 5, "skills": ["python", "go"]}
    assert validate_output(output, cfg) == []


def test_validate_output_flags_wrong_type() -> None:
    cfg = {"fields": [{"path": "years", "type": "number"}],
           "include_confidence": False, "include_provenance": False}
    errors = validate_output({"years": "five"}, cfg)
    assert len(errors) == 1
    assert "years" in errors[0]


def test_validate_output_skips_null_values() -> None:
    cfg = {"fields": [{"path": "phone", "type": "string"}],
           "include_confidence": False, "include_provenance": False}
    assert validate_output({"phone": None}, cfg) == []


def test_validate_output_skips_absent_keys() -> None:
    cfg = {"fields": [{"path": "phone", "type": "string"}],
           "include_confidence": False, "include_provenance": False}
    assert validate_output({}, cfg) == []


def test_validate_output_handles_enriched_array_items() -> None:
    cfg = {"fields": [{"path": "skills", "from": "skills[].name", "type": "string[]"}],
           "include_confidence": True, "include_provenance": False}
    output = {"skills": [{"value": "python", "confidence": 0.9},
                         {"value": "go", "confidence": 0.7}]}
    assert validate_output(output, cfg) == []


def test_validate_output_flags_enriched_item_wrong_type() -> None:
    cfg = {"fields": [{"path": "skills", "from": "skills[].name", "type": "string[]"}],
           "include_confidence": True, "include_provenance": False}
    output = {"skills": [{"value": 42, "confidence": 0.9}]}
    errors = validate_output(output, cfg)
    assert len(errors) == 1
    assert "skills" in errors[0]


def test_validate_output_object_list_type() -> None:
    cfg = {"fields": [{"path": "experience", "type": "object[]"}],
           "include_confidence": False, "include_provenance": False}
    output = {"experience": [{"company": "X", "title": "Y"}]}
    assert validate_output(output, cfg) == []


def test_validate_output_nested_path() -> None:
    cfg = {"fields": [{"path": "loc.city", "type": "string"}],
           "include_confidence": False, "include_provenance": False}
    assert validate_output({"loc": {"city": "Delhi"}}, cfg) == []
    errors = validate_output({"loc": {"city": 123}}, cfg)
    assert errors
