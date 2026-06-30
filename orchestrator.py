from __future__ import annotations
import argparse
from pathlib import Path

# ── Pipeline Settings ─────────────────────────────────────────────────────────
# All tuneable values live here. Edit this block when switching datasets.

import pipeline.config as cfg

# Input file/directory layout
cfg.CSV_FILENAME  = "recruiter_data.csv"   # CSV inside DATA_ROOT
cfg.RESUME_DIR    = "resume"               # sub-folder for resume .txt files
cfg.GITHUB_DIR    = "github"               # sub-folder for GitHub .json files
cfg.RESUME_SUFFIX = "_resume.txt"          # appended to candidate name
cfg.GITHUB_SUFFIX = "_github.json"         # appended to candidate name

# Phone normalisation: BCP-47 region for numbers without a country-code prefix.
# Common values: "IN" India, "US" United States, "GB" United Kingdom.
cfg.PHONE_DEFAULT_REGION = "IN"

# Confidence base scores — how much to trust each (source, extraction-method) pair.
cfg.BASE_SCORES = {
    ("csv",            "direct"):               0.90,
    ("github",         "direct"):               0.70,
    ("github",         "language_inferred"):    0.50,
    ("resume",         "regex_extracted"):       0.65,
    ("resume",         "section_heuristic"):     0.55,
    ("csv_duplicate",  "direct"):               0.90,
}

# Weight of each field in the overall_confidence weighted average.
# Fields absent from a profile are excluded from the average automatically.
cfg.FIELD_WEIGHTS = {
    "full_name":        0.25,
    "emails":           0.25,
    "phones":           0.10,
    "location":         0.10,
    "headline":         0.10,
    "years_experience": 0.10,
    "skills":           0.10,
}

# Added to the base score for each additional source that corroborates a value.
cfg.CORROBORATION_BONUS = 0.10

# ─────────────────────────────────────────────────────────────────────────────

DATA_ROOT = Path(__file__).parent


def stage1() -> None:
    from pipeline.stage1.stage1 import run
    run(DATA_ROOT)


def stage2(config_path: Path, input_path: Path | None = None) -> None:
    from pipeline.stage2.stage2 import run
    run(DATA_ROOT, config_path, input_path or (DATA_ROOT / "canonical_profiles.json"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=["stage1", "stage2", "all"], required=True)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--input", type=Path)
    args = parser.parse_args()

    if args.stage == "stage1":
        stage1()
    elif args.stage == "stage2":
        if not args.config:
            parser.error("--config is required for stage2")
        stage2(args.config, args.input)
    elif args.stage == "all":
        stage1()
        if args.config:
            stage2(args.config, args.input)
        else:
            print("Skipping stage2: --config required for stage2")


if __name__ == "__main__":
    main()
