#!/usr/bin/env python3
"""Load one shuffled example per dataset key (no raw data committed)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.hf_datasets import resolve_dataset_spec, sample_hf_examples


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Smoke sample one example per dataset key")
    p.add_argument(
        "--datasets",
        default="openai/gsm8k,hendrycks/competition_math,Idavidrein/gpqa,HuggingFaceH4/aime_2024,Hothan/OlympiadBench",
    )
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--output-dir", default="outputs/dataset_smoke")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    names = [x.strip() for x in args.datasets.split(",") if x.strip()]
    rows_out: list[dict[str, object]] = []
    for name in names:
        try:
            spec = resolve_dataset_spec(name)
            sample = sample_hf_examples(name, pilot_size=1, seed=args.seed)
            rows_out.append(
                {
                    "requested_name": name,
                    "resolved_key": spec.key,
                    "provenance_note": spec.provenance_note,
                    "example": sample[0] if sample else None,
                }
            )
        except Exception as exc:  # noqa: BLE001
            rows_out.append({"requested_name": name, "ok": False, "error": f"{type(exc).__name__}: {exc}"})

    (out / "smoke_summary.json").write_text(json.dumps(rows_out, indent=2), encoding="utf-8")
    print(out / "smoke_summary.json")


if __name__ == "__main__":
    main()
