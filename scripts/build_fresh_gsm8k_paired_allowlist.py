#!/usr/bin/env python3
"""Emit JSONL allowlist for paired Cohere runs (two methods, identical example_id sets)."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path


def collect_excluded_ids(repo: Path) -> set[str]:
    ex: set[str] = set()

    def ingest_text(t: str) -> None:
        for m in re.finditer(r"\bopenai_gsm8k_\d+\b", t):
            ex.add(m.group(0))

    scan_dirs = [
        repo / "outputs/cohere_pal_quality_15case_20260505T213437Z",
        repo / "outputs/cohere_pal_stratified_quality_15case_20260505T214725Z",
        repo / "outputs/pal_consolidated_28case_report_20260505",
        repo / "outputs/cohere_l1_loss_casebook_cache_expansion_20260505T183346Z",
        repo / "outputs/cohere_l1_loss_casebook_50_losses_20260505T142227Z",
    ]

    suffix_globs = (".csv", ".jsonl", ".md", ".json", ".txt")
    for sd in scan_dirs:
        if not sd.exists():
            continue
        for p in sd.rglob("*"):
            if not p.is_file():
                continue
            if p.suffix.lower() not in suffix_globs:
                continue
            try:
                ingest_text(p.read_text(encoding="utf-8", errors="ignore"))
            except OSError:
                continue

    for p in repo.glob("outputs/cohere_fair_external_l1_vs_best_current_*/per_example_records.jsonl"):
        try:
            ingest_text(p.read_text(encoding="utf-8", errors="ignore"))
        except OSError:
            continue
    for p in repo.glob("outputs/cohere_real_model_cost_normalized_validation_*/per_example_records.jsonl"):
        try:
            ingest_text(p.read_text(encoding="utf-8", errors="ignore"))
        except OSError:
            continue

    return ex


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument("--out-jsonl", type=Path, required=True)
    ap.add_argument("--pair-count", type=int, default=56)
    ap.add_argument("--subset-size", type=int, default=2048)
    ap.add_argument("--dataset", type=str, default="openai/gsm8k")
    ap.add_argument("--seed", type=int, default=20260501)
    ap.add_argument("--budget", type=int, default=6)
    ap.add_argument(
        "--method-a",
        type=str,
        default="external_l1_max",
    )
    ap.add_argument(
        "--method-b",
        type=str,
        default="direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal",
    )
    args = ap.parse_args()
    repo: Path = args.repo_root.resolve()

    excluded = collect_excluded_ids(repo)

    if str(repo) not in sys.path:
        sys.path.insert(0, str(repo))
    from experiments.frontier_matrix_core import load_pilot_examples  # noqa: E402

    examples = load_pilot_examples(args.dataset, subset_size=args.subset_size, seed=args.seed)
    picked: list[str] = []
    for ex in examples:
        eid = str(ex.example_id)
        if eid in excluded:
            continue
        picked.append(eid)
        if len(picked) >= args.pair_count:
            break

    if len(picked) < args.pair_count:
        raise SystemExit(f"Insufficient fresh IDs after exclusions: wanted {args.pair_count}, got {len(picked)}")

    args.out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with args.out_jsonl.open("w", encoding="utf-8") as f:
        for eid in picked:
            for meth in (args.method_a, args.method_b):
                f.write(
                    json.dumps(
                        {
                            "dataset": args.dataset,
                            "seed": args.seed,
                            "budget": args.budget,
                            "method": meth,
                            "example_id": eid,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )

    with args.out_jsonl.with_name("fresh_pool_note.csv").open("w", encoding="utf-8", newline="") as cf:
        w = csv.writer(cf)
        w.writerow(["excluded_pool_ids_count", len(excluded)])
        w.writerow(["picked_pair_count_target", args.pair_count])
        w.writerow(["picked_ids_concat", " ".join(picked)])


if __name__ == "__main__":
    main()
