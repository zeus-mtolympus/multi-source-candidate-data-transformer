from __future__ import annotations
import argparse
from pathlib import Path

# Tuneable values (file layout, base scores, field weights) live in
# pipeline/config.py — that's the single source of truth. Edit there when
# switching datasets, not here.

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
