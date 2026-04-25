#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.learned_branch_scorer_utils import as_float, as_int, entropy_from_counts, normalize_text, read_csv, write_csv, write_json


TRACE_SOURCE_TYPE_BRANCH = "trace_level_branch"
TRACE_SOURCE_TYPE_ANSWER_GROUP = "trace_level_answer_group"
PROXY_SOURCE_TYPE = "proxy_answer_group_only"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build trace-level learned branch scorer dataset from trace rerun packages.")
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    p.add_argument("--trace-dir", required=True, help="Path to outputs/ten_case_reasoning_diversity_trace_rerun_<timestamp>")
    p.add_argument("--provider", default="")
    p.add_argument("--dataset", default="")
    p.add_argument("--budgets", default="")
    p.add_argument("--seeds", default="")
    return p.parse_args()


def _norm_answer(value: Any) -> str:
    text = normalize_text(value)
    return text if text else "NA"


def _read_rows(path: Path) -> list[dict[str, str]]:
    return read_csv(path)


def _parse_int_set(text: str) -> set[int]:
    if not text:
        return set()
    return {as_int(x.strip(), -1) for x in text.split(",") if x.strip()}


def _safe_json_dict(text: Any) -> dict[str, Any]:
    if text in (None, ""):
        return {}
    if isinstance(text, dict):
        return text
    try:
        data = json.loads(str(text))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _to_float(value: Any) -> float:
    return as_float(value, 0.0)


def _to_bool_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    txt = normalize_text(value)
    if txt in {"1", "true", "yes"}:
        return 1
    return as_int(value, 0)


def main() -> None:
    args = parse_args()
    trace_dir = REPO_ROOT / args.trace_dir
    if not trace_dir.exists():
        raise SystemExit(f"Trace dir not found: {trace_dir}")

    budget_filter = _parse_int_set(args.budgets)
    seed_filter = _parse_int_set(args.seeds)

    per_case_rows = _read_rows(trace_dir / "per_case_results.csv")
    branch_rows = _read_rows(trace_dir / "branch_table.csv")
    action_rows = _read_rows(trace_dir / "action_trace.csv")
    answer_group_rows = _read_rows(trace_dir / "answer_group_table.csv")
    rd_rows = _read_rows(trace_dir / "reasoning_diversity_components.csv")
    inputs_rows = _read_rows(trace_dir / "ten_case_inputs.csv")

    if not per_case_rows:
        raise SystemExit("No per_case_results.csv rows found in trace dir.")

    gold_by_example: dict[str, str] = {
        str(r.get("example_id", "")): _norm_answer(r.get("gold_answer", "")) for r in inputs_rows
    }

    action_by_case_method: dict[tuple[str, int, int, str], list[dict[str, str]]] = defaultdict(list)
    for r in action_rows:
        key = (str(r.get("example_id", "")), as_int(r.get("seed"), -1), as_int(r.get("budget"), -1), str(r.get("method", "")))
        action_by_case_method[key].append(r)

    rd_by_branch: dict[tuple[str, int, int, str, str], dict[str, str]] = {}
    for r in rd_rows:
        key = (
            str(r.get("example_id", "")),
            as_int(r.get("seed"), -1),
            as_int(r.get("budget"), -1),
            str(r.get("method", "")),
            str(r.get("branch_id", "")),
        )
        rd_by_branch[key] = r

    # Candidate sources from branch table first.
    candidates_by_case: dict[tuple[str, int, int], list[dict[str, Any]]] = defaultdict(list)
    for b in branch_rows:
        example_id = str(b.get("example_id", ""))
        seed = as_int(b.get("seed"), -1)
        budget = as_int(b.get("budget"), -1)
        method = str(b.get("method", ""))
        key_case = (example_id, seed, budget)

        normalized_answer = _norm_answer(b.get("normalized_answer") or b.get("answer_group") or b.get("extracted_answer") or b.get("final_answer"))
        raw_answer = str(b.get("extracted_answer") or b.get("final_answer") or "")
        branch_id = str(b.get("branch_id", ""))
        parent_branch_id = str(b.get("parent_branch_id", ""))

        rd_key = (example_id, seed, budget, method, branch_id)
        rd = rd_by_branch.get(rd_key, {})

        candidates_by_case[key_case].append(
            {
                "example_id": example_id,
                "seed": seed,
                "budget": budget,
                "dataset": str(b.get("dataset", "")),
                "provider": str(b.get("provider", "")),
                "model": str(b.get("model", "")),
                "method": method,
                "branch_id": branch_id,
                "parent_branch_id": parent_branch_id,
                "branch_depth": as_int(b.get("branch_depth"), as_int(b.get("depth"), 0)),
                "action_count": as_int(b.get("actions"), 0),
                "expansion_count": as_int(b.get("expansions"), 0),
                "verification_count": as_int(b.get("verifications"), 0),
                "candidate_answer_normalized": normalized_answer,
                "raw_candidate_answer": raw_answer,
                "reasoning_text": str(b.get("reasoning_text", "")),
                "operation_sequence": str(b.get("operation_sequence_key", "")),
                "intermediate_values": str(b.get("intermediate_values", "")),
                "reasoning_role": str(b.get("reasoning_role", rd.get("reasoning_role", ""))),
                "useful_reasoning_diversity_bonus": _to_float(b.get("useful_reasoning_diversity_bonus", rd.get("useful_reasoning_diversity_bonus"))),
                "plausibility": _to_float(b.get("plausibility_score", rd.get("plausibility_score"))),
                "redundancy": _to_float(b.get("redundancy_penalty", rd.get("redundancy_penalty"))),
                "strategy_family_novelty": _to_float(b.get("strategy_family_novelty", rd.get("strategy_family_novelty"))),
                "operation_sequence_novelty": _to_float(b.get("operation_sequence_novelty", rd.get("operation_sequence_novelty"))),
                "intermediate_value_novelty": _to_float(b.get("intermediate_value_novelty", rd.get("intermediate_value_novelty"))),
                "answer_group_novelty": _to_float(b.get("answer_group_novelty", rd.get("answer_group_novelty"))),
                "reasoning_role_novelty": _to_float(b.get("reasoning_role_novelty", rd.get("reasoning_role_novelty"))),
                "branch_score": _to_float(b.get("branch_score", b.get("priority", 0.0))),
                "priority_score": _to_float(b.get("base_priority_score", 0.0)),
                "verifier_score": _to_float(b.get("verifier_score", 0.0)),
                "source_type": TRACE_SOURCE_TYPE_BRANCH,
                "is_trace_level": 1,
            }
        )

    # If no branch rows for a case, fallback to answer-group/action proxy rows.
    per_case_index: dict[tuple[str, int, int, str], dict[str, str]] = {}
    for r in per_case_rows:
        per_case_index[(str(r.get("example_id", "")), as_int(r.get("seed"), -1), as_int(r.get("budget"), -1), str(r.get("method", "")))] = r

    for ag in answer_group_rows:
        example_id = str(ag.get("example_id", ""))
        seed = as_int(ag.get("seed"), -1)
        budget = as_int(ag.get("budget"), -1)
        method = str(ag.get("method", ""))
        key_case = (example_id, seed, budget)
        if any(r.get("source_type") == TRACE_SOURCE_TYPE_BRANCH for r in candidates_by_case.get(key_case, [])):
            continue
        ag_answer = _norm_answer(ag.get("answer_group", ""))
        candidates_by_case[key_case].append(
            {
                "example_id": example_id,
                "seed": seed,
                "budget": budget,
                "dataset": str(ag.get("dataset", "")),
                "provider": str(ag.get("provider", "")),
                "model": str(ag.get("model", "")),
                "method": method,
                "branch_id": str(ag.get("branch_id", "")),
                "parent_branch_id": "",
                "branch_depth": 0,
                "action_count": 0,
                "expansion_count": 0,
                "verification_count": 0,
                "candidate_answer_normalized": ag_answer,
                "raw_candidate_answer": str(ag.get("answer_group", "")),
                "reasoning_text": "",
                "operation_sequence": "",
                "intermediate_values": "",
                "reasoning_role": "",
                "useful_reasoning_diversity_bonus": 0.0,
                "plausibility": 0.0,
                "redundancy": 0.0,
                "strategy_family_novelty": 0.0,
                "operation_sequence_novelty": 0.0,
                "intermediate_value_novelty": 0.0,
                "answer_group_novelty": 0.0,
                "reasoning_role_novelty": 0.0,
                "branch_score": 0.0,
                "priority_score": 0.0,
                "verifier_score": 0.0,
                "source_type": TRACE_SOURCE_TYPE_ANSWER_GROUP,
                "is_trace_level": 1,
            }
        )

    # Full fallback proxy mode from per_case final answer rows.
    for key, row in per_case_index.items():
        example_id, seed, budget, method = key
        case_key = (example_id, seed, budget)
        if candidates_by_case.get(case_key):
            continue
        candidates_by_case[case_key].append(
            {
                "example_id": example_id,
                "seed": seed,
                "budget": budget,
                "dataset": str(row.get("dataset", "")),
                "provider": "",
                "model": "",
                "method": method,
                "branch_id": f"proxy::{method}",
                "parent_branch_id": "",
                "branch_depth": 0,
                "action_count": as_int(row.get("actions"), 0),
                "expansion_count": as_int(row.get("expansions"), 0),
                "verification_count": as_int(row.get("verifications"), 0),
                "candidate_answer_normalized": _norm_answer(row.get("normalized_answer", "")),
                "raw_candidate_answer": str(row.get("final_answer", "")),
                "reasoning_text": "",
                "operation_sequence": "",
                "intermediate_values": "",
                "reasoning_role": "",
                "useful_reasoning_diversity_bonus": 0.0,
                "plausibility": 0.0,
                "redundancy": 0.0,
                "strategy_family_novelty": 0.0,
                "operation_sequence_novelty": 0.0,
                "intermediate_value_novelty": 0.0,
                "answer_group_novelty": 0.0,
                "reasoning_role_novelty": 0.0,
                "branch_score": 0.0,
                "priority_score": 0.0,
                "verifier_score": 0.0,
                "source_type": PROXY_SOURCE_TYPE,
                "is_trace_level": 0,
            }
        )

    examples: list[dict[str, Any]] = []
    case_coverage_rows: list[dict[str, Any]] = []

    for case_key, cands in sorted(candidates_by_case.items()):
        example_id, seed, budget = case_key
        if seed_filter and seed not in seed_filter:
            continue
        if budget_filter and budget not in budget_filter:
            continue

        # fill metadata from first candidate/any per-case result
        methods_here = [str(c.get("method", "")) for c in cands]
        pr = next((r for (e, s, b, _), r in per_case_index.items() if (e, s, b) == case_key), {})
        dataset = str(next((c.get("dataset") for c in cands if c.get("dataset")), pr.get("dataset", "")))
        provider = str(next((c.get("provider") for c in cands if c.get("provider")), ""))
        model = str(next((c.get("model") for c in cands if c.get("model")), ""))
        if args.provider and normalize_text(provider) != normalize_text(args.provider):
            continue
        if args.dataset and dataset != args.dataset:
            continue

        gold_answer = gold_by_example.get(example_id, "NA")
        selected_by_controller = _norm_answer(pr.get("normalized_answer", ""))

        answer_counts = Counter(_norm_answer(c.get("candidate_answer_normalized", "")) for c in cands)
        support_total = sum(answer_counts.values())
        sorted_groups = sorted(answer_counts.items(), key=lambda kv: (-kv[1], kv[0]))
        top_answer_group = sorted_groups[0][0] if sorted_groups else "NA"
        top_support = sorted_groups[0][1] if sorted_groups else 0
        second_support = sorted_groups[1][1] if len(sorted_groups) > 1 else 0
        group_rank = {name: i + 1 for i, (name, _) in enumerate(sorted_groups)}

        for idx, c in enumerate(cands):
            cand_norm = _norm_answer(c.get("candidate_answer_normalized", ""))
            examples.append(
                {
                    "case_id": f"{dataset}|{seed}|{budget}|{example_id}",
                    "problem_id": example_id,
                    "example_id": example_id,
                    "split_id": "",
                    "provider": provider,
                    "model": model,
                    "dataset": dataset,
                    "seed": seed,
                    "budget": budget,
                    "method": str(c.get("method", "")),
                    "branch_id": str(c.get("branch_id", f"idx_{idx}")),
                    "candidate_id": str(c.get("branch_id", f"idx_{idx}")),
                    "parent_branch_id": str(c.get("parent_branch_id", "")),
                    "parent_id": str(c.get("parent_branch_id", "")),
                    "branch_depth": as_int(c.get("branch_depth"), 0),
                    "depth": as_int(c.get("branch_depth"), 0),
                    "action_count": as_int(c.get("action_count"), 0),
                    "expansion_count": as_int(c.get("expansion_count"), 0),
                    "verification_count": as_int(c.get("verification_count"), 0),
                    "reasoning_text": str(c.get("reasoning_text", "")),
                    "raw_reasoning_text": str(c.get("reasoning_text", "")),
                    "operation_sequence": str(c.get("operation_sequence", "")),
                    "intermediate_values": str(c.get("intermediate_values", "")),
                    "reasoning_role": str(c.get("reasoning_role", "")),
                    "candidate_answer_normalized": cand_norm,
                    "normalized_answer": cand_norm,
                    "raw_candidate_answer": str(c.get("raw_candidate_answer", "")),
                    "extracted_answer": str(c.get("raw_candidate_answer", "")),
                    "selected_answer": str(pr.get("final_answer", "")),
                    "selected_answer_group": selected_by_controller,
                    "gold_answer": gold_answer,
                    "normalized_gold_answer": gold_answer,
                    "is_gold_candidate": int(cand_norm == gold_answer and gold_answer != "NA"),
                    "candidate_is_gold": int(cand_norm == gold_answer and gold_answer != "NA"),
                    "was_selected_by_current_controller": int(cand_norm == selected_by_controller and selected_by_controller != "NA"),
                    "answer_group_id": cand_norm,
                    "answer_group_support": answer_counts.get(cand_norm, 0),
                    "answer_group_rank": group_rank.get(cand_norm, 0),
                    "top_answer_group": top_answer_group,
                    "top2_support_gap": float((top_support - second_support) / max(1, support_total)),
                    "answer_entropy": float(entropy_from_counts(dict(answer_counts))),
                    "branch_score": _to_float(c.get("branch_score")),
                    "priority_score": _to_float(c.get("priority_score")),
                    "verifier_score": _to_float(c.get("verifier_score")),
                    "useful_reasoning_diversity_bonus": _to_float(c.get("useful_reasoning_diversity_bonus")),
                    "plausibility": _to_float(c.get("plausibility")),
                    "redundancy": _to_float(c.get("redundancy")),
                    "strategy_family_novelty": _to_float(c.get("strategy_family_novelty")),
                    "operation_sequence_novelty": _to_float(c.get("operation_sequence_novelty")),
                    "intermediate_value_novelty": _to_float(c.get("intermediate_value_novelty")),
                    "answer_group_novelty": _to_float(c.get("answer_group_novelty")),
                    "reasoning_role_novelty": _to_float(c.get("reasoning_role_novelty")),
                    "source_type": str(c.get("source_type", PROXY_SOURCE_TYPE)),
                    "token_count": as_int(c.get("token_count"), 0),
                    "latency_seconds": _to_float(c.get("latency_seconds", 0.0)),
                    "termination_reason": str(c.get("termination_reason", "")),
                    "data_quality_trace_available": _to_bool_int(c.get("is_trace_level", 0)),
                    "data_quality_proxy_reconstructed": int(str(c.get("source_type", "")).startswith("proxy")),
                    "data_quality_flags": "proxy_reconstructed" if int(str(c.get("source_type", "")).startswith("proxy")) else "trace_available",
                    "stratum": str(pr.get("stratum") or pr.get("failure_type") or "unknown"),
                    "label": int(cand_norm == gold_answer and gold_answer != "NA"),
                }
            )

        case_coverage_rows.append(
            {
                "case_id": f"{dataset}|{seed}|{budget}|{example_id}",
                "example_id": example_id,
                "dataset": dataset,
                "seed": seed,
                "budget": budget,
                "n_candidates": len(cands),
                "n_gold_candidates": sum(1 for c in cands if _norm_answer(c.get("candidate_answer_normalized", "")) == gold_answer and gold_answer != "NA"),
                "gold_present": int(any(_norm_answer(c.get("candidate_answer_normalized", "")) == gold_answer and gold_answer != "NA" for c in cands)),
                "selected_answer_group": selected_by_controller,
                "selected_is_gold": int(selected_by_controller == gold_answer and gold_answer != "NA"),
                "methods_present": "|".join(sorted(set(methods_here))),
                "source_types": "|".join(sorted(set(str(c.get("source_type", "")) for c in cands))),
            }
        )

    out_dir = REPO_ROOT / "outputs" / f"trace_level_learned_branch_scorer_dataset_{args.timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    write_csv(out_dir / "examples.csv", examples)
    write_csv(out_dir / "case_coverage.csv", case_coverage_rows)

    n_cases = len(case_coverage_rows)
    n_rows = len(examples)
    n_gold_rows = sum(as_int(r.get("label"), 0) for r in examples)
    summary_rows = [
        {
            "n_rows": n_rows,
            "n_cases": n_cases,
            "n_gold_rows": n_gold_rows,
            "gold_row_rate": n_gold_rows / max(1, n_rows),
            "gold_present_cases": sum(as_int(r.get("gold_present"), 0) for r in case_coverage_rows),
            "gold_present_case_rate": sum(as_int(r.get("gold_present"), 0) for r in case_coverage_rows) / max(1, n_cases),
            "trace_level_rows": sum(1 for r in examples if str(r.get("source_type")) in {TRACE_SOURCE_TYPE_BRANCH, TRACE_SOURCE_TYPE_ANSWER_GROUP}),
            "proxy_rows": sum(1 for r in examples if str(r.get("source_type")) == PROXY_SOURCE_TYPE),
        }
    ]
    write_csv(out_dir / "dataset_summary.csv", summary_rows)

    feature_schema = {
        "dataset_type": "trace_level_candidate_rows_with_proxy_fallback",
        "label_column": "label",
        "required_fields": [
            "case_id",
            "problem_id",
            "example_id",
            "split_id",
            "provider",
            "model",
            "dataset",
            "seed",
            "budget",
            "method",
            "branch_id",
            "candidate_id",
            "parent_branch_id",
            "parent_id",
            "branch_depth",
            "depth",
            "action_count",
            "expansion_count",
            "verification_count",
            "candidate_answer_normalized",
            "normalized_answer",
            "raw_candidate_answer",
            "extracted_answer",
            "selected_answer",
            "selected_answer_group",
            "gold_answer",
            "normalized_gold_answer",
            "is_gold_candidate",
            "candidate_is_gold",
            "was_selected_by_current_controller",
            "answer_group_id",
            "answer_group_support",
            "answer_group_rank",
            "top_answer_group",
            "top2_support_gap",
            "answer_entropy",
            "branch_score",
            "priority_score",
            "verifier_score",
            "operation_sequence",
            "intermediate_values",
            "reasoning_role",
            "raw_reasoning_text",
            "useful_reasoning_diversity_bonus",
            "plausibility",
            "redundancy",
            "strategy_family_novelty",
            "operation_sequence_novelty",
            "intermediate_value_novelty",
            "answer_group_novelty",
            "reasoning_role_novelty",
            "source_type",
            "token_count",
            "latency_seconds",
            "termination_reason",
            "data_quality_flags",
            "stratum",
        ],
        "source_types": [TRACE_SOURCE_TYPE_BRANCH, TRACE_SOURCE_TYPE_ANSWER_GROUP, PROXY_SOURCE_TYPE],
    }
    write_json(out_dir / "feature_schema.json", feature_schema)

    readme = "\n".join(
        [
            f"# Trace-level learned branch scorer dataset ({args.timestamp})",
            "",
            f"Input trace directory: `{args.trace_dir}`",
            "",
            "Rows are built from terminal branch/action/answer-group traces when available,",
            "with explicit proxy fallback rows when traces are missing.",
            "",
            "## Files",
            "- `examples.csv`: one row per candidate branch or reconstructed answer-group candidate",
            "- `feature_schema.json`: schema and source types",
            "- `dataset_summary.csv`: high-level counts",
            "- `case_coverage.csv`: per-case candidate/gold coverage diagnostics",
        ]
    )
    (out_dir / "README.md").write_text(readme + "\n", encoding="utf-8")

    print(f"Wrote: {out_dir}")


if __name__ == "__main__":
    main()
