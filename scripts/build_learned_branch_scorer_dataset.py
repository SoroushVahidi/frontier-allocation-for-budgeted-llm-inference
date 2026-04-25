#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.learned_branch_scorer_utils import (
    as_float,
    as_int,
    entropy_from_counts,
    normalize_text,
    parse_support_counts,
    read_csv,
    write_csv,
    write_json,
)

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build a lightweight learned branch scorer diagnostic dataset.")
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    p.add_argument(
        "--input-per-example",
        default="outputs/real_model_ours_vs_external_validation_20260425T_WULVER_COHERE_LONG/cohere/per_example_rows.csv",
    )
    p.add_argument("--provider", default="cohere")
    p.add_argument("--dataset", default="openai/gsm8k")
    p.add_argument("--budgets", default="4,6,8")
    p.add_argument("--seeds", default="11,23")
    p.add_argument("--max-cases", type=int, default=0)
    return p.parse_args()


def _safe_first(values: list[int]) -> int:
    return values[0] if values else 0


def main() -> None:
    args = parse_args()
    budgets = {int(x.strip()) for x in str(args.budgets).split(",") if x.strip()}
    seeds = {int(x.strip()) for x in str(args.seeds).split(",") if x.strip()}

    source_rows = read_csv(REPO_ROOT / args.input_per_example)
    source_rows = [
        r
        for r in source_rows
        if normalize_text(r.get("provider")) == normalize_text(args.provider)
        and str(r.get("dataset", "")) == args.dataset
        and as_int(r.get("budget"), -1) in budgets
        and as_int(r.get("seed"), -1) in seeds
    ]

    case_keys: list[tuple[str, int, int, str]] = []
    seen_cases: set[tuple[str, int, int, str]] = set()
    for row in source_rows:
        key = (str(row.get("dataset", "")), as_int(row.get("seed"), -1), as_int(row.get("budget"), -1), str(row.get("example_id", "")))
        if key not in seen_cases:
            seen_cases.add(key)
            case_keys.append(key)
    if args.max_cases > 0:
        keep = set(case_keys[: args.max_cases])
        source_rows = [
            r
            for r in source_rows
            if (str(r.get("dataset", "")), as_int(r.get("seed"), -1), as_int(r.get("budget"), -1), str(r.get("example_id", ""))) in keep
        ]

    by_case: dict[tuple[str, int, int, str], list[dict[str, str]]] = {}
    for row in source_rows:
        key = (str(row.get("dataset", "")), as_int(row.get("seed"), -1), as_int(row.get("budget", -1)), str(row.get("example_id", "")))
        by_case.setdefault(key, []).append(row)

    examples: list[dict[str, Any]] = []
    total_proxy_only = 0
    for key, rows in by_case.items():
        dataset, seed, budget, example_id = key
        method_counts = Counter(str(r.get("method", "")) for r in rows)
        n_candidates = len(rows)
        any_correct = int(any(as_int(r.get("is_correct"), 0) == 1 for r in rows))
        strict_f3_row = next((r for r in rows if str(r.get("method")) == "strict_f3"), {})

        # Answer-group support is usually only available on diagnostic methods;
        # when absent we back off to method-level candidate proxies.
        proxy_mode = 1
        support_counts_case = parse_support_counts(strict_f3_row.get("answer_group_support_counts"))
        if support_counts_case:
            proxy_mode = 0
        if proxy_mode == 1:
            total_proxy_only += 1

        for row in rows:
            method = str(row.get("method", ""))
            support_counts = parse_support_counts(row.get("answer_group_support_counts"))
            if support_counts:
                support_values = sorted(support_counts.values(), reverse=True)
                top_support_count = int(support_values[0])
                second_support_count = int(support_values[1]) if len(support_values) > 1 else 0
                support_total = int(sum(support_values))
                answer_entropy = entropy_from_counts(support_counts)
                top_answer_group = str(row.get("top_answer_group", ""))
                selected_answer_group = str(row.get("selected_answer_group", ""))
                candidate_answer_normalized = selected_answer_group or top_answer_group or f"method::{method}"
            else:
                support_values = sorted(method_counts.values(), reverse=True)
                top_support_count = int(method_counts.get(method, 0))
                second_support_count = int(support_values[1]) if len(support_values) > 1 else 0
                support_total = max(1, n_candidates)
                answer_entropy = entropy_from_counts(dict(method_counts))
                top_answer_group = "proxy_method_group"
                selected_answer_group = f"method::{method}"
                candidate_answer_normalized = selected_answer_group

            examples.append(
                {
                    "provider": row.get("provider", ""),
                    "model": row.get("model", ""),
                    "dataset": dataset,
                    "seed": seed,
                    "budget": budget,
                    "example_id": example_id,
                    "case_id": f"{dataset}|{seed}|{budget}|{example_id}",
                    "method": method,
                    "runtime_method": row.get("runtime_method", ""),
                    "group": row.get("group", ""),
                    "candidate_answer_normalized": candidate_answer_normalized,
                    "selected_answer_group": selected_answer_group,
                    "top_answer_group": top_answer_group,
                    "action_count": as_int(row.get("actions_used"), 0),
                    "expansion_count": as_int(row.get("expansions"), 0),
                    "verification_count": as_int(row.get("verifications"), 0),
                    "answer_group_support_count": top_support_count,
                    "top2_support_gap": float((top_support_count - second_support_count) / max(1, support_total)),
                    "answer_entropy": float(answer_entropy),
                    "failure_type": row.get("failure_type", ""),
                    "absent_from_tree": as_int(row.get("absent_from_tree"), 0),
                    "present_not_selected": as_int(row.get("present_not_selected"), 0),
                    "gold_answer_present_in_candidate_pool": any_correct,
                    "direct_chain_candidate_indicator": int(method in {"external_l1_max", "strict_f3_direct_reserve_gate_rerank_v1"}),
                    "frontier_candidate_indicator": int(method in {"strict_f3", "strict_gate1_cap_k6"}),
                    "existing_priority_score": as_float(row.get("oracle_gap"), 0.0) * -1.0,
                    "existing_verifier_score": as_float(row.get("oracle_regret"), 0.0) * -1.0,
                    "label": as_int(row.get("is_correct"), 0),
                    "label_semantics": "proxy_method_selected_candidate_is_correct",
                    "proxy_answer_group_only": proxy_mode,
                }
            )

    out_dir = REPO_ROOT / "outputs" / f"learned_branch_scorer_dataset_{args.timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(out_dir / "examples.csv", examples)

    schema = {
        "dataset_type": "proxy_answer_group_case_level" if total_proxy_only > 0 else "mixed",
        "label_column": "label",
        "label_definition": "1 if candidate row corresponds to a correct method-selected candidate; 0 otherwise",
        "limitations": [
            "This dataset is primarily proxy answer-group/case-level, not full node/branch traces.",
            "Older artifacts often omit branch-level candidate pools and answer texts.",
            "Features may reflect method-level outputs rather than true per-node marginal values.",
        ],
        "feature_columns": sorted(k for k in (examples[0].keys() if examples else []) if k != "label"),
    }
    write_json(out_dir / "feature_schema.json", schema)

    summary = [
        {
            "n_rows": len(examples),
            "n_cases": len(by_case),
            "n_positive": sum(as_int(r.get("label"), 0) for r in examples),
            "positive_rate": (sum(as_int(r.get("label"), 0) for r in examples) / max(1, len(examples))),
            "proxy_case_count": total_proxy_only,
            "proxy_case_rate": total_proxy_only / max(1, len(by_case)),
        }
    ]
    write_csv(out_dir / "dataset_summary.csv", summary)

    readme = "\n".join(
        [
            f"# Learned branch scorer dataset ({args.timestamp})",
            "",
            "This package is diagnostic-only and intentionally lightweight.",
            "",
            "## Data provenance",
            f"- Source per-example rows: `{args.input_per_example}`",
            "- Candidate rows are reconstructed from method outputs.",
            "- When answer-group candidate pools are missing, the builder falls back to method-level proxy candidates.",
            "",
            "## Limitation",
            "Most rows are proxy answer-group/case-level examples rather than true branch/node-level candidate traces.",
            "",
            "## Files",
            "- `examples.csv`: supervised rows used by training/evaluation scripts",
            "- `feature_schema.json`: feature definitions and caveats",
            "- `dataset_summary.csv`: aggregate counts and positive rate",
        ]
    )
    (out_dir / "README.md").write_text(readme + "\n", encoding="utf-8")
    print(f"Wrote: {out_dir}")


if __name__ == "__main__":
    main()
