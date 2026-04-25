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

from experiments.frontier_matrix_core import (
    build_frontier_strategies,
    generator_factory_for_mode,
    load_pilot_examples,
)
from experiments.output_layer_repair import canonicalize_answer, choose_repair_answer

STRICT_F3_RUNTIME_DEFAULT = (
    "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_"
    "repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth3_coverage_forced_v1"
)
METHOD_RUNTIME = {
    "strict_f3": STRICT_F3_RUNTIME_DEFAULT,
    "strict_f3_exhaustive_depth2_probe": "strict_f3_exhaustive_depth2_probe",
    "strict_f3_exhaustive_depth3_probe": "strict_f3_exhaustive_depth3_probe",
}


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        with path.open("w", encoding="utf-8", newline="") as f:
            if fieldnames:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames or list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run strict_f3 shallow exhaustive probe diagnostics on loss cases.")
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    p.add_argument(
        "--loss-cases-csv",
        default=(
            "outputs/strict_f3_vs_external_l1_max_more_loss_cases_20260425T_WULVER_COHERE_LONG/"
            "loss_cases_strict_f3_wrong_external_correct.csv"
        ),
    )
    p.add_argument(
        "--run-config-json",
        default="outputs/real_model_ours_vs_external_validation_20260425T_WULVER_COHERE_LONG/run_config.json",
    )
    p.add_argument("--output-root", default="outputs")
    p.add_argument("--docs-root", default="docs")
    p.add_argument("--provider", default="cohere")
    p.add_argument("--model", default="command-r-plus-08-2024")
    p.add_argument("--temperature", type=float, default=0.1)
    p.add_argument("--max-output-tokens", type=int, default=220)
    p.add_argument("--timeout-seconds", type=int, default=45)
    p.add_argument("--resume", action="store_true")
    p.add_argument("--dry-run", action="store_true", help="Offline plumbing validation without external API calls.")
    p.add_argument("--max-cases", type=int, default=0, help="Optional cap for smoke tests; 0 runs all.")
    return p.parse_args()


def load_subset_size(run_config_path: Path) -> int:
    if not run_config_path.exists():
        return 120
    try:
        data = json.loads(run_config_path.read_text(encoding="utf-8"))
    except Exception:
        return 120
    return int(data.get("subset_size", 120))


def normalize_failure_category(
    *,
    exact_match: int,
    gold_ever_present: bool,
    gold_present_final: bool,
) -> str:
    if int(exact_match) == 1:
        return "correct"
    if not bool(gold_ever_present):
        return "absent_from_tree"
    if bool(gold_present_final):
        return "output_layer_mismatch"
    return "present_not_selected"


def safe_int(x: Any, default: int = 0) -> int:
    try:
        if x is None or x == "":
            return default
        return int(x)
    except Exception:
        return default


def safe_float(x: Any, default: float = 0.0) -> float:
    try:
        if x is None or x == "":
            return default
        return float(x)
    except Exception:
        return default


def main() -> None:
    args = parse_args()
    loss_csv = REPO_ROOT / args.loss_cases_csv
    run_cfg = REPO_ROOT / args.run_config_json
    out_dir = REPO_ROOT / args.output_root / f"shallow_exhaustive_probe_{args.timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    docs_path = REPO_ROOT / args.docs_root / f"SHALLOW_EXHAUSTIVE_PROBE_REPORT_{args.timestamp}.md"

    loss_rows = read_csv_rows(loss_csv)
    if not loss_rows:
        raise RuntimeError(f"No loss-case rows found at {loss_csv}")

    strict_f3_runtime = next(
        (str(r.get("strict_f3_runtime_method", "")).strip() for r in loss_rows if r.get("strict_f3_runtime_method")),
        STRICT_F3_RUNTIME_DEFAULT,
    )
    METHOD_RUNTIME["strict_f3"] = strict_f3_runtime

    subset_size = load_subset_size(run_cfg)
    seeds = sorted({safe_int(r.get("seed")) for r in loss_rows})
    budgets = sorted({safe_int(r.get("budget")) for r in loss_rows})
    dataset_names = sorted({str(r.get("dataset") or "openai/gsm8k") for r in loss_rows})
    if dataset_names != ["openai/gsm8k"]:
        raise RuntimeError(f"Expected openai/gsm8k-only slice, got datasets={dataset_names}")

    # Build (seed, example_id) -> (question, answer).
    example_lookup: dict[tuple[int, str], tuple[str, str]] = {}
    for seed in seeds:
        examples = load_pilot_examples("openai/gsm8k", subset_size=subset_size, seed=seed)
        for ex in examples:
            example_lookup[(seed, str(ex.example_id))] = (str(ex.question), str(ex.answer))

    cases: list[dict[str, Any]] = []
    for r in loss_rows:
        seed = safe_int(r.get("seed"))
        budget = safe_int(r.get("budget"))
        example_id = str(r.get("example_id") or "")
        qa = example_lookup.get((seed, example_id))
        if qa is None:
            raise RuntimeError(f"Missing question reconstruction for seed={seed} example_id={example_id}")
        question, gold_answer = qa
        cases.append(
            {
                "dataset": "openai/gsm8k",
                "seed": seed,
                "budget": budget,
                "example_id": example_id,
                "question": question,
                "gold_answer": gold_answer,
                "strict_f3_failure_type_baseline": str(r.get("strict_f3_failure_type") or ""),
                "strict_f3_actions_used_baseline": safe_int(r.get("strict_f3_actions_used")),
                "strict_f3_expansions_baseline": safe_int(r.get("strict_f3_expansions")),
                "strict_f3_verifications_baseline": safe_int(r.get("strict_f3_verifications")),
            }
        )

    if args.max_cases > 0:
        cases = cases[: args.max_cases]

    methods = ["strict_f3", "strict_f3_exhaustive_depth2_probe", "strict_f3_exhaustive_depth3_probe"]

    existing_rows: list[dict[str, Any]] = []
    per_case_path = out_dir / "per_case_probe_results.csv"
    if args.resume and per_case_path.exists():
        existing_rows = read_csv_rows(per_case_path)
    done_keys = {
        (str(r.get("method")), str(r.get("example_id")), safe_int(r.get("seed")), safe_int(r.get("budget")))
        for r in existing_rows
    }

    controllers_by_budget: dict[int, dict[str, Any]] = {}
    for budget in budgets:
        rng = random.Random(1000 + budget)
        factory = generator_factory_for_mode(
            use_openai_api=not args.dry_run,
            rng=rng,
            openai_model=args.model,
            temperature=args.temperature,
            max_output_tokens=args.max_output_tokens,
            timeout_seconds=args.timeout_seconds,
            api_provider=args.provider,
        )
        specs = build_frontier_strategies(
            generator_factory=factory,
            budget=budget,
            adaptive_min_expand_grid=[1],
            rng=rng,
            use_openai_api=not args.dry_run,
            include_broad_diversity_aggregation_methods=True,
            include_external_l1_baseline=False,
        )
        controllers_by_budget[budget] = specs

    rows = list(existing_rows)
    for case in cases:
        budget = int(case["budget"])
        question = str(case["question"])
        gold_answer = str(case["gold_answer"])
        seed = int(case["seed"])
        example_id = str(case["example_id"])
        for method in methods:
            key = (method, example_id, seed, budget)
            if key in done_keys:
                continue
            runtime_name = METHOD_RUNTIME[method]
            specs = controllers_by_budget[budget]
            if runtime_name not in specs:
                raise RuntimeError(f"Missing runtime `{runtime_name}` for method `{method}` and budget={budget}")
            result = specs[runtime_name].run(question, gold_answer)
            meta = result.metadata or {}
            final_nodes = list(meta.get("final_nodes") or [])
            repaired = choose_repair_answer(
                final_nodes=final_nodes,
                selected_group_hint=meta.get("selected_group"),
                dataset="openai/gsm8k",
                enable_rescue=True,
            )
            surfaced = canonicalize_answer(repaired.get("surfaced_final_answer_raw"), dataset="openai/gsm8k")
            gold_can = canonicalize_answer(gold_answer, dataset="openai/gsm8k")
            exact = int(bool(surfaced == gold_can and surfaced is not None))
            gold_ever_present = bool(meta.get("gold_group_ever_present", False))
            gold_present_final = bool(meta.get("gold_group_present_final", False))
            failure_type = normalize_failure_category(
                exact_match=exact,
                gold_ever_present=gold_ever_present,
                gold_present_final=gold_present_final,
            )
            first_present_step = meta.get("gold_group_first_present_step")
            transition_step = meta.get("exhaustive_probe_transition_actions_used")
            first_after_forced_d2 = int(
                method == "strict_f3_exhaustive_depth2_probe"
                and first_present_step is not None
                and transition_step is not None
                and safe_int(first_present_step, -1) > safe_int(transition_step, 10**9)
            )
            first_after_forced_d3 = int(
                method == "strict_f3_exhaustive_depth3_probe"
                and first_present_step is not None
                and transition_step is not None
                and safe_int(first_present_step, -1) > safe_int(transition_step, 10**9)
            )
            rows.append(
                {
                    "dataset": case["dataset"],
                    "seed": seed,
                    "budget": budget,
                    "example_id": example_id,
                    "method": method,
                    "runtime_method": runtime_name,
                    "is_correct": exact,
                    "failure_type": failure_type,
                    "absent_from_tree": int(failure_type == "absent_from_tree"),
                    "present_not_selected": int(failure_type == "present_not_selected"),
                    "output_layer_mismatch": int(failure_type == "output_layer_mismatch"),
                    "actions_used": int(result.actions_used),
                    "expansions": int(result.expansions),
                    "verifications": int(result.verifications),
                    "budget_exhausted": int(bool(result.budget_exhausted)),
                    "exhaustive_probe_budget_truncated": int(bool(meta.get("exhaustive_probe_budget_truncated", False))),
                    "exhaustive_probe_planned_shallow_nodes_unexpanded": safe_int(
                        meta.get("exhaustive_probe_planned_shallow_nodes_unexpanded")
                    ),
                    "hard_early_root_coverage_forced_min_depth": safe_int(meta.get("hard_early_root_coverage_forced_min_depth")),
                    "hard_early_coverage_transition_actions_used": (
                        "" if transition_step is None else safe_int(transition_step)
                    ),
                    "gold_group_first_present_step": (
                        "" if first_present_step is None else safe_int(first_present_step)
                    ),
                    "gold_group_ever_present": int(gold_ever_present),
                    "gold_group_present_final": int(gold_present_final),
                    "first_correct_appearance_after_forced_depth2": int(first_after_forced_d2),
                    "first_correct_appearance_after_forced_depth3": int(first_after_forced_d3),
                    "strict_f3_failure_type_baseline": case["strict_f3_failure_type_baseline"],
                }
            )
            done_keys.add(key)

    write_csv(per_case_path, rows)

    rows_by_method: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        rows_by_method[str(r["method"])].append(r)

    summary_rows: list[dict[str, Any]] = []
    for method in methods:
        mr = rows_by_method.get(method, [])
        n = max(1, len(mr))
        summary_rows.append(
            {
                "method": method,
                "n_cases": len(mr),
                "accuracy": sum(safe_int(r.get("is_correct")) for r in mr) / n,
                "absent_from_tree_rate": sum(safe_int(r.get("absent_from_tree")) for r in mr) / n,
                "present_not_selected_rate": sum(safe_int(r.get("present_not_selected")) for r in mr) / n,
                "output_layer_mismatch_rate": sum(safe_int(r.get("output_layer_mismatch")) for r in mr) / n,
                "avg_actions_used": sum(safe_float(r.get("actions_used")) for r in mr) / n,
                "avg_expansions": sum(safe_float(r.get("expansions")) for r in mr) / n,
                "avg_verifications": sum(safe_float(r.get("verifications")) for r in mr) / n,
                "budget_truncation_rate": sum(safe_int(r.get("exhaustive_probe_budget_truncated")) for r in mr) / n,
                "first_appearance_after_forced_depth2_count": sum(
                    safe_int(r.get("first_correct_appearance_after_forced_depth2")) for r in mr
                ),
                "first_appearance_after_forced_depth2_share": sum(
                    safe_int(r.get("first_correct_appearance_after_forced_depth2")) for r in mr
                )
                / n,
                "first_appearance_after_forced_depth3_count": sum(
                    safe_int(r.get("first_correct_appearance_after_forced_depth3")) for r in mr
                ),
                "first_appearance_after_forced_depth3_share": sum(
                    safe_int(r.get("first_correct_appearance_after_forced_depth3")) for r in mr
                )
                / n,
            }
        )
    write_csv(out_dir / "summary.csv", summary_rows)

    transition_targets = [
        "absent_from_tree -> correct",
        "absent_from_tree -> present_not_selected",
        "absent_from_tree -> absent_from_tree",
        "present_not_selected -> correct",
        "present_not_selected -> still_present_not_selected",
    ]
    paired_rows: list[dict[str, Any]] = []
    for method in ["strict_f3_exhaustive_depth2_probe", "strict_f3_exhaustive_depth3_probe"]:
        tr_counts: Counter[str] = Counter()
        mr = rows_by_method.get(method, [])
        for r in mr:
            before = str(r.get("strict_f3_failure_type_baseline") or "")
            after = str(r.get("failure_type") or "")
            if before == "absent_from_tree" and after == "correct":
                tr_counts["absent_from_tree -> correct"] += 1
            elif before == "absent_from_tree" and after == "present_not_selected":
                tr_counts["absent_from_tree -> present_not_selected"] += 1
            elif before == "absent_from_tree" and after == "absent_from_tree":
                tr_counts["absent_from_tree -> absent_from_tree"] += 1
            elif before == "present_not_selected" and after == "correct":
                tr_counts["present_not_selected -> correct"] += 1
            elif before == "present_not_selected" and after == "present_not_selected":
                tr_counts["present_not_selected -> still_present_not_selected"] += 1
        denom = max(1, len(mr))
        for label in transition_targets:
            paired_rows.append(
                {
                    "probe_method": method,
                    "transition": label,
                    "count": int(tr_counts.get(label, 0)),
                    "share_over_150": float(tr_counts.get(label, 0) / denom),
                }
            )
    write_csv(out_dir / "paired_transition_summary.csv", paired_rows)

    coverage_rows: list[dict[str, Any]] = []
    for method in methods:
        mr = rows_by_method.get(method, [])
        n = max(1, len(mr))
        coverage_rows.append(
            {
                "method": method,
                "n_cases": len(mr),
                "mean_forced_min_depth": sum(
                    safe_int(r.get("hard_early_root_coverage_forced_min_depth")) for r in mr
                )
                / n,
                "transition_observed_rate": sum(
                    1 for r in mr if str(r.get("hard_early_coverage_transition_actions_used", "")).strip() != ""
                )
                / n,
                "mean_transition_action": sum(
                    safe_int(r.get("hard_early_coverage_transition_actions_used"))
                    for r in mr
                    if str(r.get("hard_early_coverage_transition_actions_used", "")).strip() != ""
                )
                / max(
                    1,
                    sum(
                        1
                        for r in mr
                        if str(r.get("hard_early_coverage_transition_actions_used", "")).strip() != ""
                    ),
                ),
            }
        )
    write_csv(out_dir / "coverage_depth_summary.csv", coverage_rows)

    trunc_rows: list[dict[str, Any]] = []
    for method in methods:
        for budget in budgets:
            br = [r for r in rows_by_method.get(method, []) if safe_int(r.get("budget")) == budget]
            n = max(1, len(br))
            trunc_rows.append(
                {
                    "method": method,
                    "budget": budget,
                    "n_cases": len(br),
                    "truncated_count": sum(safe_int(r.get("exhaustive_probe_budget_truncated")) for r in br),
                    "truncated_share": sum(safe_int(r.get("exhaustive_probe_budget_truncated")) for r in br) / n,
                    "mean_planned_shallow_nodes_unexpanded": sum(
                        safe_int(r.get("exhaustive_probe_planned_shallow_nodes_unexpanded")) for r in br
                    )
                    / n,
                }
            )
    write_csv(out_dir / "budget_truncation_summary.csv", trunc_rows)

    readme_lines = [
        f"# shallow_exhaustive_probe_{args.timestamp}",
        "",
        "Diagnostic-only probe run. Not a candidate production method.",
        "",
        "Files:",
        "- `summary.csv`",
        "- `paired_transition_summary.csv`",
        "- `per_case_probe_results.csv`",
        "- `coverage_depth_summary.csv`",
        "- `budget_truncation_summary.csv`",
        "",
        f"Run mode: `{'dry-run (offline simulated generator)' if args.dry_run else 'real API run'}`",
        f"Cases evaluated: `{len(cases)}`",
        f"Budgets: `{budgets}`",
    ]
    (out_dir / "README.md").write_text("\n".join(readme_lines) + "\n", encoding="utf-8")

    sum_map = {str(r["method"]): r for r in summary_rows}
    d2 = sum_map.get("strict_f3_exhaustive_depth2_probe", {})
    d3 = sum_map.get("strict_f3_exhaustive_depth3_probe", {})
    s0 = sum_map.get("strict_f3", {})
    d2_abs = safe_float(s0.get("absent_from_tree_rate")) - safe_float(d2.get("absent_from_tree_rate"))
    d3_abs = safe_float(s0.get("absent_from_tree_rate")) - safe_float(d3.get("absent_from_tree_rate"))

    report_lines = [
        f"# SHALLOW_EXHAUSTIVE_PROBE_REPORT_{args.timestamp}",
        "",
        f"- Output directory: `outputs/shallow_exhaustive_probe_{args.timestamp}/`",
        f"- Dataset slice: strict_f3-loss cases where external_l1_max was correct (n={len(cases)}).",
        f"- Mode: `{'dry-run (offline)' if args.dry_run else 'real API (cohere command-r-plus-08-2024)'}`",
        "",
        "## Explicit answers",
        f"1. Did exhaustive depth-2 exploration reduce absent-from-tree failures? **{'Yes' if d2_abs > 0 else 'No or neutral'}** (delta={d2_abs:+.4f}).",
        f"2. Did exhaustive depth-3 exploration reduce absent-from-tree failures? **{'Yes' if d3_abs > 0 else 'No or neutral'}** (delta={d3_abs:+.4f}).",
        "3. Did the correct answer usually appear shallowly once breadth was forced, or remain absent?",
        f"   - Depth-2 first-appearance-after-forced-depth2 share: {safe_float(d2.get('first_appearance_after_forced_depth2_share')):.4f}",
        f"   - Depth-3 first-appearance-after-forced-depth3 share: {safe_float(d3.get('first_appearance_after_forced_depth3_share')):.4f}",
        "4. Was the main limitation root diversity, depth-2 sibling coverage, depth-3 continuation, or final selection?",
        "   - Use `paired_transition_summary.csv`, `coverage_depth_summary.csv`, and `budget_truncation_summary.csv` for this decomposition.",
        "5. Should this become a new method, or remain only a diagnostic?",
        "   - Recommendation: keep as **diagnostic-only** pending broader cross-dataset and cross-provider validation.",
        "",
        "## Notes",
        "- Budgets remain fixed at 4/6/8 (no budget inflation).",
        "- Truncation is logged via `exhaustive_probe_budget_truncated` and unexpanded shallow-node lower bound.",
    ]
    docs_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "status": "ok",
                "output_dir": str(out_dir.relative_to(REPO_ROOT)),
                "report": str(docs_path.relative_to(REPO_ROOT)),
                "n_cases": len(cases),
                "dry_run": bool(args.dry_run),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

