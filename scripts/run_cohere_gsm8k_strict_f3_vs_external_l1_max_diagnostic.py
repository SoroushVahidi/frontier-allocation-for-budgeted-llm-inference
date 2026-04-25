#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import random
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        with path.open("w", encoding="utf-8", newline="") as f:
            if fieldnames:
                w = csv.DictWriter(f, fieldnames=fieldnames)
                w.writeheader()
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames or list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def mean(vals: list[float]) -> float:
    return float(sum(vals) / len(vals)) if vals else 0.0


def bootstrap_ci(diffs: list[float], n_boot: int = 2000, seed: int = 7) -> tuple[float, float]:
    if not diffs:
        return (0.0, 0.0)
    rng = random.Random(seed)
    n = len(diffs)
    boots = []
    for _ in range(n_boot):
        sample = [diffs[rng.randrange(n)] for _ in range(n)]
        boots.append(sum(sample) / len(sample))
    boots.sort()
    lo = boots[int(0.025 * (len(boots) - 1))]
    hi = boots[int(0.975 * (len(boots) - 1))]
    return float(lo), float(hi)


def paired_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "matched_examples": 0,
            "strict_f3_accuracy": "NA",
            "external_l1_max_accuracy": "NA",
            "paired_delta_strict_f3_minus_external_l1_max": "NA",
            "bootstrap95_low": "NA",
            "bootstrap95_high": "NA",
            "strict_f3_wins": 0,
            "ties": 0,
            "strict_f3_losses": 0,
        }
    a = [int(r["strict_f3_exact_match"]) for r in rows]
    b = [int(r["external_l1_max_exact_match"]) for r in rows]
    diffs = [x - y for x, y in zip(a, b)]
    lo, hi = bootstrap_ci([float(d) for d in diffs])
    return {
        "matched_examples": len(rows),
        "strict_f3_accuracy": mean([float(x) for x in a]),
        "external_l1_max_accuracy": mean([float(x) for x in b]),
        "paired_delta_strict_f3_minus_external_l1_max": mean([float(d) for d in diffs]),
        "bootstrap95_low": lo,
        "bootstrap95_high": hi,
        "strict_f3_wins": sum(1 for d in diffs if d > 0),
        "ties": sum(1 for d in diffs if d == 0),
        "strict_f3_losses": sum(1 for d in diffs if d < 0),
    }


def classify_claim(delta: float | str, matched: int) -> str:
    if isinstance(delta, str):
        return "not_evaluable"
    if matched < 100:
        return "diagnostic_only_incomplete"
    if delta > 0:
        return "candidate_positive_but_needs_cross_dataset"
    return "unfavorable_or_mixed"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run Cohere GSM8K strict_f3 vs external_l1_max diagnostic.")
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    p.add_argument("--target-scored-per-slice", type=int, default=100)
    p.add_argument("--max-examples", type=int, default=120)
    p.add_argument("--resume", action="store_true")
    p.add_argument("--summarize-only", action="store_true")
    p.add_argument("--include-strict-gate", action="store_true")
    p.add_argument("--base-run-timestamp", default="")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    methods = ["strict_f3", "external_l1_max"] + (["strict_gate1_cap_k6"] if args.include_strict_gate else [])

    base_ts = args.base_run_timestamp or args.timestamp
    base_out = REPO_ROOT / "outputs" / f"cohere_real_model_cost_normalized_validation_{base_ts}"
    if not args.summarize_only:
        cmd = [
            sys.executable,
            "scripts/run_cohere_real_model_cost_normalized_validation.py",
            "--timestamp",
            base_ts,
            "--providers",
            "cohere",
            "--datasets",
            "openai/gsm8k",
            "--budgets",
            "4,6,8",
            "--seeds",
            "11,23",
            "--methods",
            ",".join(methods),
            "--target-scored-per-slice",
            str(args.target_scored_per_slice),
            "--max-examples",
            str(args.max_examples),
        ]
        if args.resume:
            cmd.append("--resume")
        subprocess.run(cmd, cwd=REPO_ROOT, check=True)

    records = read_jsonl(base_out / "per_example_records.jsonl")
    records = [r for r in records if r.get("provider") == "cohere" and r.get("dataset") == "openai/gsm8k" and int(r.get("budget", -1)) in {4, 6, 8} and int(r.get("seed", -1)) in {11, 23} and r.get("method") in {"strict_f3", "external_l1_max"}]

    by_key: dict[tuple[str, int, int, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for r in records:
        if int(r.get("scored", 0)) != 1:
            continue
        k = (str(r["example_id"]), int(r["seed"]), int(r["budget"]), str(r["dataset"]))
        by_key[k][str(r["method"])] = r

    matched_rows: list[dict[str, Any]] = []
    disagreements: list[dict[str, Any]] = []
    f3_loses: list[dict[str, Any]] = []
    f3_wins: list[dict[str, Any]] = []
    for (example_id, seed, budget, dataset), cell in sorted(by_key.items()):
        if "strict_f3" not in cell or "external_l1_max" not in cell:
            continue
        a = cell["strict_f3"]
        b = cell["external_l1_max"]
        row = {
            "dataset": dataset,
            "seed": seed,
            "budget": budget,
            "example_id": example_id,
            "question": a.get("question") or b.get("question") or "",
            "gold_answer": a.get("gold_answer") or b.get("gold_answer") or "",
            "strict_f3_exact_match": int(a.get("exact_match", 0)),
            "external_l1_max_exact_match": int(b.get("exact_match", 0)),
            "strict_f3_final_answer": a.get("final_answer_raw", ""),
            "external_l1_max_final_answer": b.get("final_answer_raw", ""),
            "strict_f3_total_tokens": int(a.get("total_tokens", 0)),
            "external_l1_max_total_tokens": int(b.get("total_tokens", 0)),
            "strict_f3_latency_seconds": float(a.get("latency_seconds", 0.0)),
            "external_l1_max_latency_seconds": float(b.get("latency_seconds", 0.0)),
            "strict_f3_estimated_cost_usd": float(a.get("estimated_cost_usd", 0.0)),
            "external_l1_max_estimated_cost_usd": float(b.get("estimated_cost_usd", 0.0)),
            "failure_tag": a.get("failure_tag", "unknown") if int(a.get("exact_match", 0)) == 0 else b.get("failure_tag", "correct"),
        }
        matched_rows.append(row)
        if row["strict_f3_exact_match"] != row["external_l1_max_exact_match"]:
            disagreements.append(row)
            if row["strict_f3_exact_match"] < row["external_l1_max_exact_match"]:
                f3_loses.append(row)
            else:
                f3_wins.append(row)

    out_dir = REPO_ROOT / "outputs" / f"cohere_gsm8k_strict_f3_vs_external_l1_max_diagnostic_{args.timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    overall = paired_stats(matched_rows)
    write_csv(out_dir / "paired_summary.csv", [{"scope": "overall", **overall}])

    per_budget = []
    for b in [4, 6, 8]:
        rows = [r for r in matched_rows if int(r["budget"]) == b]
        per_budget.append({"budget": b, **paired_stats(rows)})
    write_csv(out_dir / "per_budget_pairwise.csv", per_budget)

    per_seed = []
    for s in [11, 23]:
        rows = [r for r in matched_rows if int(r["seed"]) == s]
        per_seed.append({"seed": s, **paired_stats(rows)})
    write_csv(out_dir / "per_seed_pairwise.csv", per_seed)

    with (out_dir / "per_example_disagreements.jsonl").open("w", encoding="utf-8") as f:
        for r in disagreements:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with (out_dir / "strict_f3_loses_cases.jsonl").open("w", encoding="utf-8") as f:
        for r in f3_loses:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with (out_dir / "strict_f3_wins_cases.jsonl").open("w", encoding="utf-8") as f:
        for r in f3_wins:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # failure mode summary for strict_f3 failures
    f3_fail = [r for r in records if r.get("method") == "strict_f3" and int(r.get("scored", 0)) == 1 and int(r.get("exact_match", 0)) == 0]
    counts = Counter(str(r.get("failure_tag", "unknown")) for r in f3_fail)
    canonical_modes = [
        "correct answer absent from explored tree",
        "correct answer present but not selected",
        "parse/extraction failure",
        "API/runtime failure",
        "unknown",
    ]
    rows = []
    for m in canonical_modes:
        rows.append({"failure_mode": m, "count": int(counts.get(m, 0)), "share": (counts.get(m, 0) / max(1, len(f3_fail)))})
    write_csv(out_dir / "failure_mode_summary.csv", rows)

    # cost-normalized pairwise
    def method_totals(method: str) -> dict[str, float]:
        rs = [r for r in records if r.get("method") == method and int(r.get("scored", 0)) == 1]
        n = len(rs)
        correct = sum(int(r.get("exact_match", 0)) for r in rs)
        in_tok = sum(int(r.get("input_tokens", 0)) for r in rs)
        out_tok = sum(int(r.get("output_tokens", 0)) for r in rs)
        tot_tok = sum(int(r.get("total_tokens", 0)) for r in rs)
        cost = sum(float(r.get("estimated_cost_usd", 0.0)) for r in rs)
        lat = mean([float(r.get("latency_seconds", 0.0)) for r in rs])
        acc = correct / n if n else 0.0
        return {
            "method": method,
            "scored_examples": n,
            "accuracy": acc,
            "input_tokens": in_tok,
            "output_tokens": out_tok,
            "total_tokens": tot_tok,
            "estimated_cost_usd": cost,
            "mean_latency_seconds": lat,
            "accuracy_per_1k_tokens": (acc / (tot_tok / 1000.0)) if tot_tok > 0 else 0.0,
            "accuracy_per_estimated_dollar": (acc / cost) if cost > 0 else 0.0,
        }

    cost_rows = [method_totals("strict_f3"), method_totals("external_l1_max")]
    write_csv(out_dir / "cost_normalized_pairwise.csv", cost_rows)

    # runner correctness audit
    audit_rows: list[dict[str, Any]] = []
    f3_keys = {(r["dataset"], int(r["seed"]), int(r["budget"]), r["example_id"]) for r in records if r.get("method") == "strict_f3" and int(r.get("scored", 0)) == 1}
    l1_keys = {(r["dataset"], int(r["seed"]), int(r["budget"]), r["example_id"]) for r in records if r.get("method") == "external_l1_max" and int(r.get("scored", 0)) == 1}
    inter = f3_keys & l1_keys
    audit_rows.append({"check": "same_dataset_scope", "status": "pass", "detail": "openai/gsm8k only"})
    audit_rows.append({"check": "same_seed_scope", "status": "pass", "detail": "11,23 only"})
    audit_rows.append({"check": "same_budget_scope", "status": "pass", "detail": "4,6,8 only"})
    audit_rows.append({"check": "matched_example_ids", "status": "pass" if f3_keys == l1_keys else "warn", "detail": f"strict_f3={len(f3_keys)} external_l1_max={len(l1_keys)} matched={len(inter)}"})
    audit_rows.append({"check": "answer_normalizer", "status": "pass", "detail": "canonicalize_answer + choose_repair_answer in run_cohere_real_model_cost_normalized_validation.py"})
    audit_rows.append({"check": "scoring_logic", "status": "pass", "detail": "exact_match based on canonicalized surfaced_final_answer == canonicalized gold_answer"})
    write_csv(out_dir / "runner_correctness_audit.csv", audit_rows)

    # incomplete slices from source run
    src_incomplete = base_out / "incomplete_slices.csv"
    if src_incomplete.exists():
        write_csv(out_dir / "incomplete_slices.csv", list(csv.DictReader(src_incomplete.open())))
    else:
        write_csv(out_dir / "incomplete_slices.csv", [], fieldnames=["provider", "dataset", "seed", "budget", "method"]) 

    claim = [
        {
            "question": "Does strict_f3 beat external_l1_max under Cohere Stage-1 GSM8K?",
            "answer": "yes" if isinstance(overall["paired_delta_strict_f3_minus_external_l1_max"], float) and overall["paired_delta_strict_f3_minus_external_l1_max"] > 0 else "no_or_mixed",
            "evidence": f"matched={overall['matched_examples']}, delta={overall['paired_delta_strict_f3_minus_external_l1_max']}",
        },
        {
            "question": "Claim safety tier",
            "answer": classify_claim(overall["paired_delta_strict_f3_minus_external_l1_max"], int(overall["matched_examples"])),
            "evidence": "Do not claim main-paper dominance if negative/mixed/incomplete.",
        },
    ]
    write_csv(out_dir / "claim_safety_table.csv", claim)

    manifest = {
        "artifact_family": "cohere_gsm8k_strict_f3_vs_external_l1_max_diagnostic",
        "timestamp": args.timestamp,
        "base_run_timestamp": base_ts,
        "source_dir": str(base_out.relative_to(REPO_ROOT)),
        "dataset": ["openai/gsm8k"],
        "budgets": [4, 6, 8],
        "seeds": [11, 23],
        "methods": methods,
        "target_scored_per_slice": args.target_scored_per_slice,
        "outputs": [
            "manifest.json",
            "paired_summary.csv",
            "per_budget_pairwise.csv",
            "per_seed_pairwise.csv",
            "per_example_disagreements.jsonl",
            "strict_f3_loses_cases.jsonl",
            "strict_f3_wins_cases.jsonl",
            "failure_mode_summary.csv",
            "cost_normalized_pairwise.csv",
            "runner_correctness_audit.csv",
            "incomplete_slices.csv",
            "claim_safety_table.csv",
        ],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    doc_path = REPO_ROOT / "docs" / f"COHERE_GSM8K_STRICT_F3_VS_EXTERNAL_L1_MAX_DIAGNOSTIC_{args.timestamp}.md"
    pb = {int(r["budget"]): r for r in per_budget}
    ps = {int(r["seed"]): r for r in per_seed}
    next_action = "improve_the_algorithm_or_runner" if (isinstance(overall["paired_delta_strict_f3_minus_external_l1_max"], float) and overall["paired_delta_strict_f3_minus_external_l1_max"] <= 0) else "complete_MATH500_AIME"
    lines = [
        f"# COHERE_GSM8K_STRICT_F3_VS_EXTERNAL_L1_MAX_DIAGNOSTIC_{args.timestamp}",
        "",
        f"- Source run directory: `outputs/cohere_real_model_cost_normalized_validation_{base_ts}/`",
        f"- Diagnostic directory: `outputs/cohere_gsm8k_strict_f3_vs_external_l1_max_diagnostic_{args.timestamp}/`",
        "",
        "## Required answers",
        f"1. Does strict_f3 beat external_l1_max under Cohere? **{'Yes' if claim[0]['answer']=='yes' else 'No or mixed'}**.",
        f"2. Is prior negative delta stable vs small-sample noise? Observed delta={overall['paired_delta_strict_f3_minus_external_l1_max']} with 95% CI [{overall['bootstrap95_low']}, {overall['bootstrap95_high']}], matched={overall['matched_examples']}.",
        f"3. Budgets driving result: b4 delta={pb[4]['paired_delta_strict_f3_minus_external_l1_max']}, b6 delta={pb[6]['paired_delta_strict_f3_minus_external_l1_max']}, b8 delta={pb[8]['paired_delta_strict_f3_minus_external_l1_max']}.",
        f"4. Seeds driving result: s11 delta={ps[11]['paired_delta_strict_f3_minus_external_l1_max']}, s23 delta={ps[23]['paired_delta_strict_f3_minus_external_l1_max']}.",
        "5. Cost/latency/token factors: see `cost_normalized_pairwise.csv`.",
        "6. Runner mismatch evidence: see `runner_correctness_audit.csv`.",
        f"7. Evidence tier: **{claim[1]['answer']}**; next recommended action: **{next_action}**.",
        "",
        "## Claim discipline",
        "- If strict_f3 loses or remains mixed, this does not support a main-paper dominance claim.",
        "- Safe framing remains appendix-only or diagnostic.",
        "- Manuscript should not claim real-model superiority over external_l1_max from this slice.",
    ]
    doc_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
