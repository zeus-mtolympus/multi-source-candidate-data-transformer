import pytest
from pipeline.stage1 import parser


def _rec(resume_raw=None, github_raw=None):
    return {"csv": {}, "resume_raw": resume_raw, "github_raw": github_raw, "load_failed": []}


def test_valid_json_parsed(tmp_path) -> None:
    rec = _rec(github_raw='{"login": "u", "name": "Test", "repos": []}')
    result = parser.parse([rec])[0]
    assert result["github_parsed"]["name"] == "Test"


def test_invalid_json_records_failure() -> None:
    rec = _rec(github_raw="NOT JSON {{{")
    result = parser.parse([rec])[0]
    assert result["github_parsed"] is None
    assert "github" in result["load_failed"]


def test_no_github_leaves_parsed_none() -> None:
    rec = _rec(github_raw=None)
    result = parser.parse([rec])[0]
    assert result["github_parsed"] is None
    assert result["load_failed"] == []


def test_resume_raw_passed_through() -> None:
    rec = _rec(resume_raw="Alice\nalice@test.com")
    result = parser.parse([rec])[0]
    assert result["resume_raw"] == "Alice\nalice@test.com"
