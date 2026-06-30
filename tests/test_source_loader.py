import csv
import pytest
from pathlib import Path
from pipeline.stage1 import source_loader


def _make_data(tmp_path: Path, rows: list[dict], resumes: dict[str, str] = {}, githubs: dict[str, str] = {}) -> Path:
    (tmp_path / "resume").mkdir(exist_ok=True)
    (tmp_path / "github").mkdir(exist_ok=True)
    fields = ["name", "email", "phone", "current_company", "title", "location_city",
              "location_region", "location_country", "linkedin_url", "github_url",
              "portfolio_url", "headline", "years_experience", "resume_file"]
    with open(tmp_path / "recruiter_data.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fields})
    for name, content in resumes.items():
        (tmp_path / "resume" / f"{name}_resume.txt").write_text(content, encoding="utf-8")
    for name, content in githubs.items():
        (tmp_path / "github" / f"{name}_github.json").write_text(content, encoding="utf-8")
    return tmp_path


def test_loads_resume_when_file_exists(tmp_path: Path) -> None:
    root = _make_data(
        tmp_path,
        [{"name": "Alice Smith", "email": "alice@example.com", "resume_file": "alice_resume.txt"}],
        resumes={"Alice Smith": "Alice Smith\nalice@example.com"},
    )
    records = source_loader.load(root)
    assert records[0]["resume_raw"] is not None
    assert records[0]["load_failed"] == []


def test_load_failed_when_resume_missing(tmp_path: Path) -> None:
    root = _make_data(
        tmp_path,
        [{"name": "Bob Jones", "email": "bob@example.com", "resume_file": "bob_resume.txt"}],
    )
    records = source_loader.load(root)
    assert records[0]["resume_raw"] is None
    assert "resume" in records[0]["load_failed"]


def test_load_failed_when_github_missing(tmp_path: Path) -> None:
    root = _make_data(
        tmp_path,
        [{"name": "Carol Lee", "email": "carol@example.com", "github_url": "https://github.com/carollee"}],
    )
    records = source_loader.load(root)
    assert records[0]["github_raw"] is None
    assert "github" in records[0]["load_failed"]


def test_continues_after_missing_file(tmp_path: Path) -> None:
    root = _make_data(
        tmp_path,
        [
            {"name": "Alice Smith", "email": "alice@example.com", "resume_file": "x"},
            {"name": "Bob Jones", "email": "bob@example.com"},
        ],
    )
    records = source_loader.load(root)
    assert len(records) == 2
    assert "resume" in records[0]["load_failed"]
    assert records[1]["load_failed"] == []


def test_sparse_row_no_crash(tmp_path: Path) -> None:
    root = _make_data(
        tmp_path,
        [{"name": "Min Imum", "email": "min@example.com"}],
    )
    records = source_loader.load(root)
    assert len(records) == 1
    assert records[0]["load_failed"] == []
