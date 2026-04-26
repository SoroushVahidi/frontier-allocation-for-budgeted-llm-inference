#!/usr/bin/env python3
"""Scan direct-reserve validation / related output packages and write artifact_inventory.csv."""
from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.learned_branch_scorer_utils import as_int, read_csv
REQUIRED_V1_FILES = (
    "per_case_method_results.csv",
    "candidate_branch_table.csv",
    "answer_group_summary.csv",
    "planned_cases.csv",
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    p.add_argument(
        "--roots",
        default="outputs",
        help="Comma-separated roots to scan (default: outputs/)",
    )
    return p.parse_args()


def _relevant_name(name: str) -> bool:
    keys = (
        "cohere_direct_reserve_validation",
        "cohere_direct_reserve",
        "cohere_coverage_generation_ablation",
        "trace_level_learned_branch_scorer_dataset",
    )
    return any(k in name for k in keys)


def _iter_dirs(roots: list[Path]) -> list[Path]:
    out: list[Path] = []
    for root in roots:
        r = (REPO_ROOT / root).resolve() if not root.is_absolute() else root
        if not r.is_dir():
            continue
        for p in r.iterdir():
            if not p.is_dir() or p.name.startswith("."):
                continue
            if (p / "per_case_method_results.csv").exists() or _relevant_name(p.name):
                out.append(p)
    return sorted(out, key=lambda x: str(x))


def _summarize_package(pkg: Path) -> dict[str, Any]:
    row: dict[str, Any] = {
        "package_path": str(pkg.relative_to(REPO_ROOT)) if REPO_ROOT in pkg.parents or pkg == REPO_ROOT else str(pkg),
        "has_manifest": (pkg / "manifest.json").exists(),
    }
    for f in REQUIRED_V1_FILES:
        row[f"has_{f}"] = (pkg / f).exists()
    if not (pkg / "per_case_method_results.csv").exists():
        return {
            **row,
            "n_unique_problems": 0,
            "n_candidate_branch_rows": 0,
            "n_answer_group_rows": 0,
            "n_gold_present_problems": 0,
            "n_positive_gold_labels": 0,
            "has_reasoning_text_non_na": 0,
            "has_action_trace": (pkg / "action_trace.jsonl").exists(),
            "has_branch_states": (pkg / "final_branch_states.jsonl").exists(),
        }

    per = read_csv(pkg / "per_case_method_results.csv")
    cands = read_csv(pkg / "candidate_branch_table.csv")
    ag = read_csv(pkg / "answer_group_summary.csv")
    eids = {str(r.get("example_id", "")) for r in per if r.get("example_id")}
    gold_present = 0
    for eid in eids:
        rows = [r for r in per if str(r.get("example_id")) == eid and str(r.get("method")) == "direct_reserve_strong_plus_diverse_v1"]
        if rows and as_int(rows[0].get("gold_present", 0), 0) == 1:
            gold_present += 1
    pos = sum(1 for r in cands if as_int(r.get("is_gold_group", 0), 0) == 1)
    reason_ok = 0
    for r in cands[:2000]:
        t = str(r.get("reasoning_text", "NA") or "")
        if t and t != "NA" and len(t) > 2:
            reason_ok += 1
    return {
        **row,
        "n_unique_problems": len(eids),
        "n_candidate_branch_rows": len(cands),
        "n_answer_group_rows": len(ag),
        "n_gold_present_problems": gold_present,
        "n_positive_gold_labels": pos,
        "has_reasoning_text_non_na": 1 if reason_ok > 0 else 0,
        "has_action_trace": (pkg / "action_trace.jsonl").exists() or (pkg / "action_trace.csv").exists(),
        "has_branch_states": (pkg / "final_branch_states.jsonl").exists(),
    }


def main() -> None:
    args = parse_args()
    roots = [Path(x.strip()) for x in str(args.roots).split(",") if x.strip()]
    out_dir = REPO_ROOT / "outputs" / f"direct_reserve_learned_scorer_inventory_{args.timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for pkg in _iter_dirs(roots):
        rows.append(_summarize_package(pkg))
    if not rows:
        rows = []

    out_csv = out_dir / "artifact_inventory.csv"
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=sorted({k for r in rows for k in r.keys()}) or ["package_path"])
        w.writeheader()
        w.writerows(rows)
    (out_dir / "README.md").write_text(
        f"# direct_reserve learned scorer inventory\n\n- Timestamp: `{args.timestamp}`\n- Scanned roots: `{args.roots}`\n- Packages with inventory rows: {len(rows)}\n\nSee `artifact_inventory.csv`.\n",
        encoding="utf-8",
    )
    print(f"Wrote {out_csv}")


if __name__ == "__main__":
    main()
