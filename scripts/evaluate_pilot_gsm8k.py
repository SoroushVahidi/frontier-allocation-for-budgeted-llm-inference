#!/usr/bin/env python3
"""Evaluate a pilot run directory and summarize method-level metrics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate pilot GSM8K run outputs")
    parser.add_argument("run_dir", help="Run directory under outputs/pilot/<run_id>")
    return parser.parse_args()


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    return rows


def summarize(rows: list[dict]) -> dict:
    n = len(rows)
    if n == 0:
        return {
            "n_examples": 0,
            "accuracy": 0.0,
            "avg_actions": 0.0,
            "avg_expansions": 0.0,
            "avg_verifications": 0.0,
            "avg_surviving_branches": 0.0,
            "budget_exhaustion_rate": 0.0,
        }

    return {
        "n_examples": n,
        "accuracy": sum(1 for r in rows if r["is_correct"]) / n,
        "avg_actions": sum(r["actions_used"] for r in rows) / n,
        "avg_expansions": sum(r["expansions"] for r in rows) / n,
        "avg_verifications": sum(r["verifications"] for r in rows) / n,
        "avg_surviving_branches": sum(r["avg_surviving_branches"] for r in rows) / n,
        "budget_exhaustion_rate": sum(1 for r in rows if r["budget_exhausted"]) / n,
    }


def main() -> None:
    args = parse_args()
    run_dir = Path(args.run_dir)

    method_files = sorted(p for p in run_dir.glob("*.jsonl") if p.name != "summary.json")
    if not method_files:
        raise FileNotFoundError(f"No method jsonl files found in {run_dir}")

    summary = {}
    for path in method_files:
        rows = read_jsonl(path)
        summary[path.stem] = summarize(rows)

    summary_path = run_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(json.dumps(summary, indent=2))
    print(f"Saved summary to: {summary_path}")


if __name__ == "__main__":
    main()
