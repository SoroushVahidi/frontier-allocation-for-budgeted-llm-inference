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
from experiments.output_layer_repair import canonicalize_answer, choose_repair_answer
from experiments.problem_type_utils import classify_problem_type

STRICT_F3_RUNTIME = (
    "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_"
    "repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth3_coverage_forced_v1"
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Evaluate strict_f3_typed_strategy_seeded_v1 diagnostics.")
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    p.add_argument("--max-cases", type=int, default=0)
    p.add_argument("--resume", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--provider", default="cohere")
    p.add_argument("--cohere-model", default="command-r-plus-08-2024")
    p.add_argument("--input-package", default="outputs/detailed_loss_case_package_20260425T_WULVER_COHERE_LONG_DETAIL/")
    p.add_argument("--slice", choices=["loss150", "present_not_selected", "absent_from_tree", "all720"], default="loss150")
    p.add_argument("--emit-traces", action="store_true")
    p.add_argument("--skip-real-api-if-no-key", action="store_true")
    return p.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        if not rows:
            w = csv.DictWriter(f, fieldnames=fieldnames or ["empty"])
            w.writeheader()
            return
        w = csv.DictWriter(f, fieldnames=fieldnames or list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


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
    if sl == "loss150":
        return [r for r in rows if str(r.get("pair_type")) == "strict_f3_wrong_external_correct"]
    if sl == "present_not_selected":
        return [r for r in rows if str(r.get("strict_f3_failure_type")) == "present_not_selected"]
    if sl == "absent_from_tree":
        return [r for r in rows if str(r.get("strict_f3_failure_type")) == "absent_from_tree"]
    return rows


def main() -> None:
    args = parse_args()
    all_cases = read_csv(REPO_ROOT / args.input_package / "all_paired_cases.csv")
    if not all_cases:
        raise RuntimeError("Missing all_paired_cases.csv in input package")
    all_cases = pick_slice(all_cases, args.slice)
    if args.max_cases > 0:
        all_cases = all_cases[: args.max_cases]

    out_dir = REPO_ROOT / "outputs" / f"typed_strategy_seeded_eval_{args.timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    existing = read_csv(out_dir / "per_case_results.csv") if args.resume else []
    done = {(r["method"], r["example_id"], as_int(r["seed"]), as_int(r["budget"])) for r in existing}
    per_case = list(existing)
    per_case_strategy_metadata: list[dict[str, Any]] = []
    per_branch_strategy_traces: list[dict[str, Any]] = []
    missing_fields: Counter[str] = Counter()

    methods = [
        "strict_f3",
        "strict_f3_direction_combinatorics_guard_v1",
        "strict_f3_typed_strategy_seeded_v1",
        "external_l1_max",
    ]
    runtime_map = {
        "strict_f3": STRICT_F3_RUNTIME,
        "strict_f3_direction_combinatorics_guard_v1": "strict_f3_direction_combinatorics_guard_v1",
        "strict_f3_typed_strategy_seeded_v1": "strict_f3_typed_strategy_seeded_v1",
        "external_l1_max": "external_l1_max",
    }
    budgets = sorted({as_int(r.get("budget")) for r in all_cases})
    controllers: dict[int, dict[str, Any]] = {}
    for b in budgets:
        rng = random.Random(300 + b)
        factory = generator_factory_for_mode(
            use_openai_api=not args.dry_run,
            rng=rng,
            openai_model=args.cohere_model,
            temperature=0.1,
            max_output_tokens=280,
            timeout_seconds=60,
            api_provider=args.provider,
        )
        controllers[b] = build_frontier_strategies(
            generator_factory=factory,
            budget=b,
            adaptive_min_expand_grid=[1],
            rng=rng,
            use_openai_api=not args.dry_run,
            include_broad_diversity_aggregation_methods=True,
            include_external_l1_baseline=True,
        )

    for c in all_cases:
        q = str(c.get("question") or "")
        g = str(c.get("gold_answer") or "")
        if not q or not g or q == "NA" or g == "NA":
            continue
        seed, budget, example_id = as_int(c.get("seed")), as_int(c.get("budget")), str(c.get("example_id"))
        problem_type = classify_problem_type(q)
        for m in methods:
            key = (m, example_id, seed, budget)
            if key in done:
                continue
            specs = controllers[budget]
            runtime_name = runtime_map[m]
            if runtime_name not in specs:
                continue
            res = specs[runtime_name].run(q, g)
            meta = res.metadata or {}
            repaired = choose_repair_answer(
                final_nodes=list(meta.get("final_nodes") or []),
                selected_group_hint=meta.get("selected_group"),
                dataset="openai/gsm8k",
                enable_rescue=True,
            )
            pred = canonicalize_answer(repaired.get("surfaced_final_answer_raw"), dataset="openai/gsm8k")
            gold = canonicalize_answer(g, dataset="openai/gsm8k")
            exact = int(pred is not None and pred == gold)
            failure_type = "correct"
            if exact == 0:
                if not bool(meta.get("gold_group_ever_present", False)):
                    failure_type = "absent_from_tree"
                elif bool(meta.get("gold_group_present_final", False)):
                    failure_type = "output_layer_mismatch"
                else:
                    failure_type = "present_not_selected"
            answer_counts = dict(meta.get("answer_group_support_counts") or {})
            answer_entropy = as_float(meta.get("answer_entropy", 0.0))
            top2_gap = as_float(meta.get("top2_support_gap", 0.0))
            distinct_groups = len(answer_counts)
            all_same_group = distinct_groups <= 1
            row = {
                "dataset": c.get("dataset", "openai/gsm8k"),
                "seed": seed,
                "budget": budget,
                "example_id": example_id,
                "question": q,
                "gold_answer": g,
                "method": m,
                "prediction": pred or "NA",
                "exact_match": exact,
                "failure_type": failure_type,
                "absent_from_tree": int(failure_type == "absent_from_tree"),
                "present_not_selected": int(failure_type == "present_not_selected"),
                "output_layer_mismatch": int(failure_type == "output_layer_mismatch"),
                "problem_type_label": problem_type,
                "num_typed_strategy_branches_seeded": as_int(meta.get("num_typed_strategy_branches_seeded", 0)),
                "typed_strategy_families_seeded": json.dumps(meta.get("typed_strategy_families_seeded", [])),
                "typed_strategy_families_seen": json.dumps(meta.get("typed_strategy_families_seen", [])),
                "typed_strategy_family_expansion_counts": json.dumps(meta.get("typed_strategy_family_expansion_counts", {})),
                "typed_strategy_family_action_counts": json.dumps(meta.get("typed_strategy_family_action_counts", {})),
                "typed_strategy_family_answer_groups": json.dumps(meta.get("typed_strategy_family_answer_groups", {})),
                "dominant_typed_strategy_family": meta.get("dominant_typed_strategy_family", "NA"),
                "dominant_typed_strategy_family_share": as_float(meta.get("dominant_typed_strategy_family_share", 0.0)),
                "typed_strategy_min_coverage_satisfied": int(bool(meta.get("typed_strategy_min_coverage_satisfied", False))),
                "typed_strategy_forced_expansion_count": as_int(meta.get("typed_strategy_forced_expansion_count", 0)),
                "typed_strategy_cap_block_count": as_int(meta.get("typed_strategy_cap_block_count", 0)),
                "typed_strategy_redundancy_detected": int(bool(meta.get("typed_strategy_redundancy_detected", False))),
                "prompt_diversity_family_count": len(set(meta.get("typed_strategy_families_seeded", []))),
                "prompt_diversity_prompt_count": as_int(meta.get("num_typed_strategy_branches_seeded", 0)),
                "answer_diversity_group_count": distinct_groups,
                "answer_entropy": answer_entropy,
                "top2_support_gap": top2_gap,
                "answer_groups_by_strategy_family": json.dumps(meta.get("typed_strategy_family_answer_groups", {})),
                "pairwise_trace_lexical_similarity": "NA",
                "pairwise_answer_group_diversity": 0.0 if all_same_group else 1.0,
                "distinct_first_step_rationales": "NA",
                "all_branches_collapsed_same_answer_group": int(all_same_group),
                "direction_count": len(set(meta.get("typed_strategy_families_seen", []))) or len(set(meta.get("typed_strategy_families_seeded", []))),
                "dominant_direction_share": as_float(meta.get("dominant_typed_strategy_family_share", 0.0)),
                "commit_guard_triggered": int(bool(meta.get("commit_guard_triggered", False))),
                "commit_guard_reason": meta.get("commit_guard_reason", "NA"),
                "budget_available_for_verifier": int(bool(meta.get("budget_available_for_verifier", False))),
                "verifier_used_real_call": int(bool(meta.get("verifier_used_real_call", False))),
                "verifier_used_heuristic": int(bool(meta.get("verifier_used_heuristic", False))),
                "verifier_scores_by_answer_group": json.dumps(meta.get("verifier_scores_by_answer_group", {})),
                "verifier_verdicts_by_answer_group": json.dumps(meta.get("verifier_verdicts_by_answer_group", {})),
                "verifier_reason_by_answer_group": json.dumps(meta.get("verifier_reason_by_answer_group", {})),
                "pre_guard_selected_answer_group": meta.get("pre_guard_selected_answer_group", "NA"),
                "post_guard_selected_answer_group": meta.get("post_guard_selected_answer_group", "NA"),
                "selected_answer_strategy_families": json.dumps(meta.get("selected_answer_strategy_families", [])),
                "correct_answer_strategy_families": json.dumps(meta.get("correct_answer_strategy_families", [])),
                "selection_changed_by_guard": int(bool(meta.get("selection_changed_by_guard", False))),
                "guard_repaired_case": int(bool(meta.get("guard_repaired_case", False))),
                "guard_hurt_case": int(bool(meta.get("guard_hurt_case", False))),
                "actions_used": int(res.actions_used),
                "expansions": int(res.expansions),
                "verifications": int(res.verifications),
                "token_cost": "NA",
                "dollar_cost": "NA",
                "latency_ms": "NA",
                "transition_from_baseline_failure_type": f"{c.get('strict_f3_failure_type','NA')} -> {failure_type}",
            }
            for k, v in row.items():
                if v in ("", None):
                    missing_fields[k] += 1
            per_case.append(row)
            per_case_strategy_metadata.append(
                {
                    "method": m,
                    "example_id": example_id,
                    "seed": seed,
                    "budget": budget,
                    "problem_type_label": problem_type,
                    "typed_strategy_branch_metadata": meta.get("typed_strategy_branch_metadata", []),
                }
            )
            if args.emit_traces:
                for t in list(meta.get("action_trace") or []):
                    per_branch_strategy_traces.append(
                        {"method": m, "example_id": example_id, "seed": seed, "budget": budget, **dict(t)}
                    )
            done.add(key)

    write_csv(out_dir / "per_case_results.csv", per_case)
    write_jsonl(out_dir / "per_case_strategy_metadata.jsonl", per_case_strategy_metadata)
    write_jsonl(out_dir / "per_branch_strategy_traces.jsonl", per_branch_strategy_traces)

    by_method: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in per_case:
        by_method[str(r["method"])].append(r)

    summary = []
    for m in methods:
        rows = by_method.get(m, [])
        n = max(1, len(rows))
        summary.append(
            {
                "method": m,
                "n": len(rows),
                "accuracy": sum(as_int(r["exact_match"]) for r in rows) / n,
                "absent_from_tree_rate": sum(as_int(r["absent_from_tree"]) for r in rows) / n,
                "present_not_selected_rate": sum(as_int(r["present_not_selected"]) for r in rows) / n,
                "output_layer_mismatch_rate": sum(as_int(r["output_layer_mismatch"]) for r in rows) / n,
                "counting_combinatorics_accuracy": (
                    sum(as_int(r["exact_match"]) for r in rows if r.get("problem_type_label") == "counting_combinatorics")
                    / max(1, sum(1 for r in rows if r.get("problem_type_label") == "counting_combinatorics"))
                ),
                "avg_actions": sum(as_float(r["actions_used"]) for r in rows) / n,
                "avg_expansions": sum(as_float(r["expansions"]) for r in rows) / n,
            }
        )
    write_csv(out_dir / "summary.csv", summary)
    write_csv(out_dir / "slice_summary.csv", [{"slice": args.slice, **x} for x in summary])
    write_csv(
        out_dir / "typed_strategy_diversity_summary.csv",
        [
            {
                "method": m,
                "avg_prompt_diversity_family_count": sum(as_float(r["prompt_diversity_family_count"]) for r in by_method.get(m, []))
                / max(1, len(by_method.get(m, []))),
                "avg_answer_diversity_group_count": sum(as_float(r["answer_diversity_group_count"]) for r in by_method.get(m, []))
                / max(1, len(by_method.get(m, []))),
                "collapse_rate": sum(as_int(r["all_branches_collapsed_same_answer_group"]) for r in by_method.get(m, []))
                / max(1, len(by_method.get(m, []))),
            }
            for m in methods
        ],
    )
    write_csv(
        out_dir / "answer_group_by_strategy_summary.csv",
        [{"method": r["method"], "example_id": r["example_id"], "answer_groups_by_strategy_family": r["answer_groups_by_strategy_family"]} for r in per_case],
    )
    write_csv(
        out_dir / "transition_summary.csv",
        [{"method": r["method"], "transition": r["transition_from_baseline_failure_type"], "count": 1} for r in per_case],
    )
    write_csv(
        out_dir / "commit_guard_summary.csv",
        [{"method": m, "trigger_rate": sum(as_int(r["commit_guard_triggered"]) for r in by_method.get(m, [])) / max(1, len(by_method.get(m, [])))} for m in methods],
    )
    write_csv(
        out_dir / "verifier_diagnostics.csv",
        [{"method": r["method"], "example_id": r["example_id"], "verifier_used_heuristic": r["verifier_used_heuristic"], "verifier_used_real_call": r["verifier_used_real_call"]} for r in per_case],
    )
    write_csv(out_dir / "present_not_selected_repairs.csv", [r for r in per_case if "present_not_selected -> correct" in r["transition_from_baseline_failure_type"]])
    write_csv(out_dir / "absent_from_tree_repairs.csv", [r for r in per_case if "absent_from_tree -> correct" in r["transition_from_baseline_failure_type"]])
    write_csv(out_dir / "hurt_cases.csv", [r for r in per_case if as_int(r["guard_hurt_case"]) == 1])
    write_csv(
        out_dir / "missing_fields_report.csv",
        [{"field": k, "missing_count": int(v)} for k, v in sorted(missing_fields.items(), key=lambda kv: kv[0])],
        fieldnames=["field", "missing_count"],
    )

    readme = [
        f"# typed_strategy_seeded_eval_{args.timestamp}",
        "",
        "- diagnostic/probe run",
        f"- slice: {args.slice}",
        f"- dry_run: {bool(args.dry_run)}",
        f"- emit_traces: {bool(args.emit_traces)}",
        f"- input_package: `{args.input_package}`",
    ]
    (out_dir / "README.md").write_text("\n".join(readme) + "\n", encoding="utf-8")

    s = {r["method"]: r for r in summary}
    b = s.get("strict_f3", {})
    t = s.get("strict_f3_typed_strategy_seeded_v1", {})
    report = REPO_ROOT / "docs" / f"TYPED_STRATEGY_SEEDED_EVAL_{args.timestamp}.md"
    report.write_text(
        "\n".join(
            [
                f"# TYPED_STRATEGY_SEEDED_EVAL_{args.timestamp}",
                "",
                f"1. Did typed strategy seeding reduce absent-from-tree failures on the 150 loss cases? {'yes' if as_float(t.get('absent_from_tree_rate',1.0)) < as_float(b.get('absent_from_tree_rate',1.0)) else 'no_or_neutral'}.",
                f"2. Did it reduce present-not-selected failures? {'yes' if as_float(t.get('present_not_selected_rate',1.0)) < as_float(b.get('present_not_selected_rate',1.0)) else 'no_or_neutral'}.",
                f"3. Did it improve counting/combinatorics accuracy? {'yes' if as_float(t.get('counting_combinatorics_accuracy',0.0)) > as_float(b.get('counting_combinatorics_accuracy',0.0)) else 'no_or_neutral'}.",
                "4. Did it create genuinely different reasoning paths, or did branches still collapse to the same answer/direction? Check typed_strategy_diversity_summary.csv.",
                "5. Which strategy family most often discovered the correct answer? Check answer_group_by_strategy_summary.csv and per_case_strategy_metadata.jsonl.",
                "6. Which strategy family most often caused wrong high-confidence answers? Check answer_group_by_strategy_summary.csv + per_case_results.csv.",
                "7. Did the commit guard repair any present-not-selected cases? Check present_not_selected_repairs.csv.",
                "8. Did the commit guard hurt any cases? Check hurt_cases.csv.",
                f"9. Did typed seeding increase actions/cost/latency? avg_actions strict_f3={as_float(b.get('avg_actions',0.0)):.3f}, typed={as_float(t.get('avg_actions',0.0)):.3f}.",
                "10. Should this become a real candidate method, or remain diagnostic? Diagnostic unless gains hold in real API runs.",
                "11. What fields are still missing for deeper scoring diagnosis? See missing_fields_report.csv.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    print(json.dumps({"status": "ok", "output_dir": str(out_dir.relative_to(REPO_ROOT)), "report": str(report.relative_to(REPO_ROOT))}, indent=2))


if __name__ == "__main__":
    main()

