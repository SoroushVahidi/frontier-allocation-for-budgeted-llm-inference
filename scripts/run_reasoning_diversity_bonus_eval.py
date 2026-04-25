#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.frontier_matrix_core import build_frontier_strategies, generator_factory_for_mode

STRICT_F3_RUNTIME = (
    "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_"
    "repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth3_coverage_forced_v1"
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Diagnostic eval for strict_f3_reasoning_diversity_bonus_v1")
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    p.add_argument("--slice", choices=["ten_case", "loss150", "present_not_selected", "absent_from_tree", "all720"], default="ten_case")
    p.add_argument("--max-cases", type=int, default=0)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--resume", action="store_true")
    p.add_argument("--emit-traces", action="store_true")
    p.add_argument("--skip-real-api-if-no-key", action="store_true")
    p.add_argument("--provider", default="cohere")
    p.add_argument("--cohere-model", default="command-r-plus-08-2024")
    return p.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], header: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in header})


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=True) + "\n")


def as_int(v: Any, d: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return d


def as_float(v: Any, d: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return d


def pick_slice(rows: list[dict[str, str]], sl: str) -> list[dict[str, str]]:
    if sl == "ten_case":
        return rows[:10]
    if sl == "loss150":
        return [r for r in rows if str(r.get("pair_type")) == "strict_f3_wrong_external_correct"][:150]
    if sl == "present_not_selected":
        return [r for r in rows if str(r.get("strict_f3_failure_type")) == "present_not_selected"]
    if sl == "absent_from_tree":
        return [r for r in rows if str(r.get("strict_f3_failure_type")) == "absent_from_tree"]
    return rows


def collapse_rate(vals: list[str]) -> float:
    if not vals:
        return 0.0
    c = Counter(vals)
    return max(c.values()) / max(1, len(vals))


def main() -> None:
    args = parse_args()
    pkg = REPO_ROOT / "outputs" / "detailed_loss_case_package_20260425T_WULVER_COHERE_LONG_DETAIL"
    cases = read_csv(pkg / "all_paired_cases.csv")
    missing: Counter[str] = Counter()
    if not cases:
        missing["all_paired_cases.csv_missing"] += 1
        cases = []

    cases = pick_slice(cases, args.slice)
    if args.max_cases > 0:
        cases = cases[: args.max_cases]

    methods = ["strict_f3", "strict_f3_reasoning_diversity_bonus_v1", "external_l1_max"]
    optional = ["strict_f3_typed_strategy_seeded_v1", "strict_f3_typed_strategy_family_normalized_rerank_v1"]

    budgets = sorted({as_int(r.get("budget"), 4) for r in cases} or [4])
    controllers: dict[int, dict[str, Any]] = {}
    for b in budgets:
        rng = random.Random(1000 + b)
        factory = generator_factory_for_mode(
            use_openai_api=False,
            rng=rng,
            openai_model=args.cohere_model,
            temperature=0.1,
            max_output_tokens=256,
            timeout_seconds=45,
            api_provider=args.provider,
        )
        controllers[b] = build_frontier_strategies(
            generator_factory=factory,
            budget=b,
            adaptive_min_expand_grid=[1],
            rng=rng,
            use_openai_api=False,
            include_broad_diversity_aggregation_methods=True,
            include_external_l1_baseline=True,
        )

    out_dir = REPO_ROOT / "outputs" / f"reasoning_diversity_bonus_eval_{args.timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    per_case: list[dict[str, Any]] = []
    per_branch_jsonl: list[dict[str, Any]] = []
    per_decision_jsonl: list[dict[str, Any]] = []

    for row in cases:
        q = str(row.get("question") or "")
        g = str(row.get("gold_answer") or "")
        if not q or not g or q == "NA" or g == "NA":
            missing["question_or_gold_missing"] += 1
            continue
        b = as_int(row.get("budget"), budgets[0])
        ctrls = controllers[b]
        run_methods = list(methods)
        run_methods.extend([m for m in optional if m in ctrls])
        for m in run_methods:
            runtime = STRICT_F3_RUNTIME if m == "strict_f3" else m
            if runtime not in ctrls:
                missing[f"method_missing:{runtime}"] += 1
                continue
            res = ctrls[runtime].run(q, g)
            md = res.metadata or {}
            action_trace = list(md.get("action_trace", [])) if isinstance(md.get("action_trace", []), list) else []
            sig_keys = [str(a.get("reasoning_signature_key", "")) for a in action_trace if str(a.get("reasoning_signature_key", ""))]
            op_keys = [str(a.get("operation_sequence_key", "")) for a in action_trace if str(a.get("operation_sequence_key", ""))]
            roles = [str(a.get("reasoning_role", "unknown")) for a in action_trace]
            answers = [str(a.get("group_key", "__unknown__")) for a in action_trace]
            per_case.append(
                {
                    "slice": args.slice,
                    "method": m,
                    "runtime_method": runtime,
                    "example_id": row.get("example_id", ""),
                    "seed": row.get("seed", ""),
                    "budget": b,
                    "prediction": res.prediction,
                    "is_correct": int(res.is_correct),
                    "actions": int(res.actions_used),
                    "expansions": int(res.expansions),
                    "verifications": int(res.verifications),
                    "absent_from_tree": int(str(md.get("early_divergence_failure_category", "")) == "absent_from_tree"),
                    "present_not_selected": int(str(md.get("early_divergence_failure_category", "")) == "present_not_selected"),
                    "output_layer_mismatch": int(str(md.get("regime_failure_category", "")) == "output_layer_mismatch"),
                    "distinct_operation_sequences": len(set(op_keys)),
                    "distinct_reasoning_roles": len(set(roles)),
                    "distinct_strategy_families": len({str(a.get("strategy_family", "")) for a in action_trace}),
                    "distinct_answer_groups": len(set(answers)),
                    "average_intermediate_value_novelty": as_float(md.get("average_intermediate_value_novelty", 0.0), 0.0),
                    "redundancy_penalty_mean": sum(as_float(a.get("redundancy_penalty", 0.0), 0.0) for a in action_trace) / max(1, len(action_trace)),
                    "dominant_reasoning_signature_share": collapse_rate(sig_keys),
                    "answer_collapse_rate": collapse_rate(answers),
                    "operation_collapse_rate": collapse_rate(op_keys),
                    "role_collapse_rate": collapse_rate(roles),
                    "selection_changed_by_reasoning_diversity": int(
                        any(bool(a.get("selected_due_to_reasoning_diversity", False)) for a in action_trace)
                    ),
                    "diagnostic_label": "diagnostic/probe",
                }
            )
            if args.emit_traces:
                for idx, a in enumerate(action_trace):
                    per_decision_jsonl.append(
                        {
                            "slice": args.slice,
                            "method": m,
                            "example_id": row.get("example_id", ""),
                            "decision_index": idx,
                            **a,
                            "diagnostic_label": "diagnostic/probe",
                        }
                    )
                    per_branch_jsonl.append(
                        {
                            "slice": args.slice,
                            "method": m,
                            "example_id": row.get("example_id", ""),
                            "branch_id": a.get("branch_id"),
                            "reasoning_signature_key": a.get("reasoning_signature_key", ""),
                            "operation_sequence_key": a.get("operation_sequence_key", ""),
                            "reasoning_role": a.get("reasoning_role", "unknown"),
                            "strategy_family": a.get("strategy_family", ""),
                            "answer_group": a.get("group_key", "__unknown__"),
                            "redundancy_penalty": a.get("redundancy_penalty", 0.0),
                            "useful_reasoning_diversity_bonus": a.get("useful_reasoning_diversity_bonus", 0.0),
                            "diagnostic_label": "diagnostic/probe",
                        }
                    )

    # summaries
    by_method = defaultdict(list)
    for r in per_case:
        by_method[r["method"]].append(r)
    summary_rows = []
    for m, rows in by_method.items():
        summary_rows.append(
            {
                "slice": args.slice,
                "method": m,
                "n": len(rows),
                "accuracy": sum(as_int(r["is_correct"]) for r in rows) / max(1, len(rows)),
                "absent_from_tree_rate": sum(as_int(r["absent_from_tree"]) for r in rows) / max(1, len(rows)),
                "present_not_selected_rate": sum(as_int(r["present_not_selected"]) for r in rows) / max(1, len(rows)),
                "output_layer_mismatch_rate": sum(as_int(r["output_layer_mismatch"]) for r in rows) / max(1, len(rows)),
                "average_actions": sum(as_float(r["actions"]) for r in rows) / max(1, len(rows)),
                "average_expansions": sum(as_float(r["expansions"]) for r in rows) / max(1, len(rows)),
                "average_verifications": sum(as_float(r["verifications"]) for r in rows) / max(1, len(rows)),
                "avg_distinct_operation_sequences": sum(as_float(r["distinct_operation_sequences"]) for r in rows) / max(1, len(rows)),
                "avg_distinct_reasoning_roles": sum(as_float(r["distinct_reasoning_roles"]) for r in rows) / max(1, len(rows)),
                "avg_distinct_strategy_families": sum(as_float(r["distinct_strategy_families"]) for r in rows) / max(1, len(rows)),
                "avg_distinct_answer_groups": sum(as_float(r["distinct_answer_groups"]) for r in rows) / max(1, len(rows)),
                "avg_intermediate_value_novelty": sum(as_float(r["average_intermediate_value_novelty"]) for r in rows) / max(1, len(rows)),
                "redundancy_penalty_mean": sum(as_float(r["redundancy_penalty_mean"]) for r in rows) / max(1, len(rows)),
                "dominant_reasoning_signature_share": sum(as_float(r["dominant_reasoning_signature_share"]) for r in rows) / max(1, len(rows)),
                "answer_collapse_rate": sum(as_float(r["answer_collapse_rate"]) for r in rows) / max(1, len(rows)),
                "operation_collapse_rate": sum(as_float(r["operation_collapse_rate"]) for r in rows) / max(1, len(rows)),
                "role_collapse_rate": sum(as_float(r["role_collapse_rate"]) for r in rows) / max(1, len(rows)),
                "diagnostic_label": "diagnostic/probe",
            }
        )

    # repair/hurt
    strict = {(r["example_id"], r["seed"], r["budget"]): r for r in per_case if r["method"] == "strict_f3"}
    bonus = {(r["example_id"], r["seed"], r["budget"]): r for r in per_case if r["method"] == "strict_f3_reasoning_diversity_bonus_v1"}
    repair_rows, hurt_rows = [], []
    for k, srow in strict.items():
        brow = bonus.get(k)
        if not brow:
            continue
        if as_int(srow["is_correct"]) == 0 and as_int(brow["is_correct"]) == 1:
            repair_rows.append({"example_id": k[0], "seed": k[1], "budget": k[2], "repair_type": "strict_f3_wrong_to_diversity_correct", "diagnostic_label": "diagnostic/probe"})
        if as_int(srow["is_correct"]) == 1 and as_int(brow["is_correct"]) == 0:
            hurt_rows.append({"example_id": k[0], "seed": k[1], "budget": k[2], "hurt_type": "strict_f3_correct_to_diversity_wrong", "diagnostic_label": "diagnostic/probe"})

    missing_rows = [{"field": k, "count": v} for k, v in sorted(missing.items())]

    write_csv(out_dir / "summary.csv", summary_rows, header=list(summary_rows[0].keys()) if summary_rows else ["slice", "method", "n", "diagnostic_label"])
    write_csv(out_dir / "slice_summary.csv", summary_rows, header=list(summary_rows[0].keys()) if summary_rows else ["slice", "method", "n", "diagnostic_label"])
    write_csv(out_dir / "per_case_results.csv", per_case, header=list(per_case[0].keys()) if per_case else ["slice", "method", "example_id", "diagnostic_label"])
    write_jsonl(out_dir / "per_branch_reasoning_diversity.jsonl", per_branch_jsonl)
    write_jsonl(out_dir / "per_decision_reasoning_diversity.jsonl", per_decision_jsonl)
    write_csv(out_dir / "reasoning_signature_summary.csv", [], header=["method", "reasoning_signature_key", "count", "diagnostic_label"])
    write_csv(out_dir / "operation_sequence_summary.csv", [], header=["method", "operation_sequence_key", "count", "diagnostic_label"])
    write_csv(out_dir / "intermediate_value_summary.csv", [], header=["method", "intermediate_value", "count", "diagnostic_label"])
    write_csv(out_dir / "answer_group_diversity_summary.csv", [], header=["method", "answer_group", "count", "diagnostic_label"])
    write_csv(out_dir / "repair_cases.csv", repair_rows, header=["example_id", "seed", "budget", "repair_type", "diagnostic_label"])
    write_csv(out_dir / "hurt_cases.csv", hurt_rows, header=["example_id", "seed", "budget", "hurt_type", "diagnostic_label"])
    write_csv(out_dir / "missing_fields_report.csv", missing_rows, header=["field", "count"])

    (out_dir / "README.md").write_text(
        "# Reasoning diversity bonus diagnostic/probe\n\n"
        f"Slice: `{args.slice}`  \nMethods: {', '.join(methods)}  \n"
        "This run is diagnostic/probe and uses local simulator-only evaluation (no real API calls).\n",
        encoding="utf-8",
    )

    doc = REPO_ROOT / "docs" / f"REASONING_DIVERSITY_BONUS_EVAL_{args.timestamp}.md"
    doc.write_text(
        "# Reasoning diversity bonus diagnostic report\n\n"
        "- Label: diagnostic/probe\n"
        f"- Slice: {args.slice}\n"
        f"- Cases evaluated: {len(per_case)} method-case rows\n\n"
        "## Answers\n"
        "1. Improvement on 10 deep-dive: see `repair_cases.csv`.\n"
        "2. Absent-from-tree reduction: compare `absent_from_tree_rate` in `summary.csv`.\n"
        "3. Present-not-selected reduction: compare `present_not_selected_rate` in `summary.csv`.\n"
        "4. Actual reasoning diversity: compare operation/role/signature and collapse metrics in `summary.csv`.\n"
        "5. Most helpful component: inspect `per_decision_reasoning_diversity.jsonl`.\n"
        "6. Hurt cases: see `hurt_cases.csv`.\n"
        "7. Missing text reliability limits: see `missing_fields_report.csv`.\n"
        "8. Candidate status: keep diagnostic/probe unless stable gains are observed across slices.\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
