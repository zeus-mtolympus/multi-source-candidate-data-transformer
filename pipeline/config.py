from __future__ import annotations

# Source loader
CSV_FILENAME: str = "recruiter_data.csv"
RESUME_DIR: str = "resume"
GITHUB_DIR: str = "github"
RESUME_SUFFIX: str = "_resume.txt"
GITHUB_SUFFIX: str = "_github.json"

# Phone normalisation — BCP-47 region used when a number has no country-code prefix
PHONE_DEFAULT_REGION: str = "IN"

# Confidence base scores per (source, extraction-method) pair
BASE_SCORES: dict[tuple[str, str], float] = {
    ("csv", "direct"):               0.90,
    ("github", "direct"):            0.70,
    ("github", "language_inferred"): 0.50,
    ("resume", "regex_extracted"):   0.65,
    ("resume", "section_heuristic"): 0.55,
    ("csv_duplicate", "direct"):     0.90,
}

# Per-field weights used in overall_confidence weighted average.
# ALL fields always contribute to the denominator (missing = 0.0 score),
# so enriched profiles correctly score higher than sparse CSV-only stubs.
FIELD_WEIGHTS: dict[str, float] = {
    "full_name":        0.20,
    "emails":           0.20,
    "phones":           0.08,
    "location":         0.07,
    "headline":         0.07,
    "years_experience": 0.08,
    "skills":           0.10,
    "experience":       0.12,
    "education":        0.08,
}

# Added to base score for each additional source that corroborates the same value
CORROBORATION_BONUS: float = 0.10
