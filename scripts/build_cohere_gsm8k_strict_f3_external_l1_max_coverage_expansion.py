#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build Cohere coverage-expansion summary for strict_f3 vs external_l1_max")
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    p.add_argument("--records-path", default="outputs/cohere_real_model_cost_normalized_validation_20260425T183000Z_COVERAGE/per_example_records.jsonl")
    p.add_argument("--target-scored-per-slice", type=int, default=100)
    return p.parse_args()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not path.exists():
        return out
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


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


def main() -> None:
    args = parse_args()
    records_path = REPO_ROOT / args.records_path
    rows = read_jsonl(records_path)
    rows = [
        r
        for r in rows
        if r.get("provider") == "cohere"
        and r.get("dataset") == "openai/gsm8k"
        and int(r.get("seed", -1)) in {11, 23}
        and int(r.get("budget", -1)) in {4, 6, 8}
        and r.get("method") in {"strict_f3", "external_l1_max"}
        and int(r.get("scored", 0)) == 1
    ]

    expected = [(s, b, m) for s in [11, 23] for b in [4, 6, 8] for m in ["strict_f3", "external_l1_max"]]
    by_slice_method: dict[tuple[int, int, str], list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_slice_method[(int(r["seed"]), int(r["budget"]), str(r["method"]))].append(r)

    coverage_rows: list[dict[str, Any]] = []
    incomplete_rows: list[dict[str, Any]] = []
    for s, b, m in expected:
        rs = by_slice_method.get((s, b, m), [])
        scored = len(rs)
        acc = sum(int(r.get("exact_match", 0)) for r in rs) / scored if scored else 0.0
        total_tokens = sum(int(r.get("total_tokens", 0)) for r in rs)
        cost = sum(float(r.get("estimated_cost_usd", 0.0)) for r in rs)
        mean_latency = (sum(float(r.get("latency_seconds", 0.0)) for r in rs) / scored) if scored else 0.0
        rec = {
            "provider": "cohere",
            "dataset": "openai/gsm8k",
            "seed": s,
            "budget": b,
            "method": m,
            "scored_examples": scored,
            "target_scored_examples": args.target_scored_per_slice,
            "coverage_ratio_vs_target": (scored / args.target_scored_per_slice) if args.target_scored_per_slice else 0.0,
            "accuracy": acc,
            "total_tokens": total_tokens,
            "estimated_cost_usd": cost,
            "mean_latency_seconds": mean_latency,
            "is_incomplete": int(scored < args.target_scored_per_slice),
        }
        coverage_rows.append(rec)
        if scored < args.target_scored_per_slice:
            incomplete_rows.append(rec)

    by_case: dict[tuple[int, int, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for r in rows:
        k = (int(r["seed"]), int(r["budget"]), str(r["example_id"]))
        by_case[k][str(r["method"])] = r

    matched_rows: list[dict[str, Any]] = []
    for (seed, budget, example_id), cell in sorted(by_case.items()):
        if "strict_f3" not in cell or "external_l1_max" not in cell:
            continue
        s = int(cell["strict_f3"].get("exact_match", 0))
        e = int(cell["external_l1_max"].get("exact_match", 0))
        if s == 0 and e == 1:
            case_type = "strict_f3_loss_external_win"
        elif s == 1 and e == 0:
            case_type = "strict_f3_win_external_loss"
        elif s == 1 and e == 1:
            case_type = "both_correct"
        else:
            case_type = "both_wrong"
        matched_rows.append(
            {
                "seed": seed,
                "budget": budget,
                "example_id": example_id,
                "strict_f3_correctness": s,
                "external_l1_max_correctness": e,
                "case_type": case_type,
            }
        )

    matched_summary = []
    all_counts = Counter(r["case_type"] for r in matched_rows)
    total_matched = len(matched_rows)
    matched_summary.append(
        {
            "scope": "overall",
            "matched_cases": total_matched,
            "strict_f3_loss_external_win": all_counts.get("strict_f3_loss_external_win", 0),
            "strict_f3_win_external_loss": all_counts.get("strict_f3_win_external_loss", 0),
            "both_correct": all_counts.get("both_correct", 0),
            "both_wrong": all_counts.get("both_wrong", 0),
            "loss_rate_over_matched": (all_counts.get("strict_f3_loss_external_win", 0) / total_matched) if total_matched else 0.0,
        }
    )
    for s in [11, 23]:
        for b in [4, 6, 8]:
            rs = [r for r in matched_rows if r["seed"] == s and r["budget"] == b]
            c = Counter(r["case_type"] for r in rs)
            n = len(rs)
            matched_summary.append(
                {
                    "scope": f"seed_{s}_budget_{b}",
                    "matched_cases": n,
                    "strict_f3_loss_external_win": c.get("strict_f3_loss_external_win", 0),
                    "strict_f3_win_external_loss": c.get("strict_f3_win_external_loss", 0),
                    "both_correct": c.get("both_correct", 0),
                    "both_wrong": c.get("both_wrong", 0),
                    "loss_rate_over_matched": (c.get("strict_f3_loss_external_win", 0) / n) if n else 0.0,
                }
            )

    loss_count_rows = []
    for s in [11, 23]:
        for b in [4, 6, 8]:
            rs = [r for r in matched_rows if r["seed"] == s and r["budget"] == b and r["case_type"] == "strict_f3_loss_external_win"]
            loss_count_rows.append({"seed": s, "budget": b, "loss_case_count": len(rs)})

    api_cost_summary = []
    for m in ["strict_f3", "external_l1_max"]:
        rs = [r for r in rows if r["method"] == m]
        api_cost_summary.append(
            {
                "method": m,
                "scored_examples": len(rs),
                "total_input_tokens": sum(int(r.get("input_tokens", 0)) for r in rs),
                "total_output_tokens": sum(int(r.get("output_tokens", 0)) for r in rs),
                "total_tokens": sum(int(r.get("total_tokens", 0)) for r in rs),
                "estimated_cost_usd": sum(float(r.get("estimated_cost_usd", 0.0)) for r in rs),
                "mean_latency_seconds": (sum(float(r.get("latency_seconds", 0.0)) for r in rs) / len(rs)) if rs else 0.0,
            }
        )
    api_cost_summary.append(
        {
            "method": "combined",
            "scored_examples": len(rows),
            "total_input_tokens": sum(int(r.get("input_tokens", 0)) for r in rows),
            "total_output_tokens": sum(int(r.get("output_tokens", 0)) for r in rows),
            "total_tokens": sum(int(r.get("total_tokens", 0)) for r in rows),
            "estimated_cost_usd": sum(float(r.get("estimated_cost_usd", 0.0)) for r in rows),
            "mean_latency_seconds": (sum(float(r.get("latency_seconds", 0.0)) for r in rows) / len(rows)) if rows else 0.0,
        }
    )

    ts = args.timestamp
    out_dir = REPO_ROOT / "outputs" / f"cohere_gsm8k_strict_f3_external_l1_max_coverage_expansion_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    write_csv(out_dir / "coverage_summary.csv", coverage_rows)
    write_csv(out_dir / "matched_case_summary.csv", matched_summary)
    write_csv(out_dir / "loss_case_count_by_budget_seed.csv", loss_count_rows)
    write_csv(out_dir / "api_cost_summary.csv", api_cost_summary)
    write_csv(out_dir / "incomplete_slices.csv", incomplete_rows)

    manifest = {
        "timestamp": ts,
        "provider": "cohere",
        "model": "command-r-plus-08-2024",
        "dataset": "openai/gsm8k",
        "methods": ["strict_f3", "external_l1_max"],
        "seeds": [11, 23],
        "budgets": [4, 6, 8],
        "target_scored_per_slice": args.target_scored_per_slice,
        "source_records_path": str(records_path.relative_to(REPO_ROOT)),
        "scored_rows_total": len(rows),
        "matched_cases_total": total_matched,
        "strict_f3_loss_external_win_cases": all_counts.get("strict_f3_loss_external_win", 0),
        "reached_100_losses": all_counts.get("strict_f3_loss_external_win", 0) >= 100,
        "files": [
            "manifest.json",
            "coverage_summary.csv",
            "matched_case_summary.csv",
            "loss_case_count_by_budget_seed.csv",
            "api_cost_summary.csv",
            "incomplete_slices.csv",
        ],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
