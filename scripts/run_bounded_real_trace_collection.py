#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
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
from experiments.output_layer_repair import canonicalize_answer

STRICT_F3_RUNTIME = (
    "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_"
    "repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth3_coverage_forced_v1"
)


def _parse_int_list(text: str) -> list[int]:
    values = [x.strip() for x in str(text).split(",") if x.strip()]
    return [int(v) for v in values]


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        seen: list[str] = []
        for row in rows:
            for key in row.keys():
                if str(key) not in seen:
                    seen.append(str(key))
        fieldnames = seen or ["empty"]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _normalize_answer(raw: Any, dataset: str = "openai/gsm8k") -> str:
    if raw in (None, "", "NA"):
        return "NA"
    try:
        return str(canonicalize_answer(str(raw), dataset=dataset))
    except Exception:
        return str(raw).strip() or "NA"


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _safe_read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _infer_stratum(row: dict[str, str]) -> str:
    absent = str(row.get("absent_from_tree", "")).strip().lower() in {"1", "true", "yes"}
    present_not_selected = str(row.get("present_not_selected", "")).strip().lower() in {"1", "true", "yes"}
    is_correct = str(row.get("is_correct", "")).strip().lower() in {"1", "true", "yes"}
    failure_type = str(row.get("failure_type", "")).strip().lower()
    if absent or "absent_from_tree" in failure_type:
        return "absent_from_tree"
    if present_not_selected or "present_not_selected" in failure_type:
        return "present_not_selected"
    if is_correct or failure_type in {"", "correct", "none", "na"}:
        return "control_correct"
    return "unknown"


def _extract_case_row(row: dict[str, str]) -> dict[str, Any]:
    question = str(row.get("question") or row.get("problem") or row.get("prompt") or "").strip()
    gold_raw = str(row.get("gold_answer") or row.get("answer") or row.get("target") or "").strip()
    gold_norm = _normalize_answer(gold_raw)
    return {
        "example_id": str(row.get("example_id") or row.get("id") or row.get("problem_id") or "").strip(),
        "dataset": str(row.get("dataset") or "openai/gsm8k").strip(),
        "question": question,
        "gold_answer_raw": gold_raw,
        "gold_answer": gold_norm,
        "seed": _coerce_int(row.get("seed"), -1),
        "budget": _coerce_int(row.get("budget"), -1),
        "failure_type": str(row.get("failure_type") or "").strip(),
        "stratum": _infer_stratum(row),
        "source_path": str(row.get("source_path", "")),
    }


def _collect_candidate_rows(paths: list[Path]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for path in paths:
        for row in _safe_read_csv(path):
            enriched = dict(row)
            enriched["source_path"] = str(path)
            base = _extract_case_row(enriched)
            if not base["example_id"]:
                continue
            if not base["question"] or not base["gold_answer_raw"]:
                continue
            out.append(base)
    return out


def _sample_by_stratum(
    rows: list[dict[str, Any]],
    absent_count: int,
    present_count: int,
    control_count: int,
    rng: random.Random,
) -> list[dict[str, Any]]:
    by_stratum: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen: set[tuple[str, str]] = set()
    for row in rows:
        key = (str(row.get("example_id")), str(row.get("stratum")))
        if key in seen:
            continue
        seen.add(key)
        by_stratum[str(row.get("stratum"))].append(row)

    for cell in by_stratum.values():
        rng.shuffle(cell)

    plan: list[dict[str, Any]] = []
    for stratum, need in [
        ("absent_from_tree", absent_count),
        ("present_not_selected", present_count),
        ("control_correct", control_count),
    ]:
        plan.extend(by_stratum.get(stratum, [])[: max(0, need)])
    return plan


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Bounded real trace collection for trace-level learned scorer diagnostics.")
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    p.add_argument("--loss-artifact-glob", default="outputs/*/per_case_results.csv")
    p.add_argument("--loss-artifact", action="append", default=[])
    p.add_argument("--absent-count", type=int, default=10)
    p.add_argument("--present-count", type=int, default=10)
    p.add_argument("--control-count", type=int, default=10)
    p.add_argument("--max-cases", type=int, default=30)
    p.add_argument("--provider", default="cohere")
    p.add_argument("--model", default="command-r-plus-08-2024")
    p.add_argument("--methods", default="strict_f3")
    p.add_argument("--budgets", default="4,6,8")
    p.add_argument("--seeds", default="11,23")
    p.add_argument("--run-real-api", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--resume", action="store_true")
    p.add_argument("--emit-full-traces", action="store_true")
    p.add_argument("--temperature", type=float, default=0.2)
    p.add_argument("--max-output-tokens", type=int, default=200)
    p.add_argument("--timeout-seconds", type=int, default=60)
    p.add_argument("--selection-seed", type=int, default=7)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    run_id = f"bounded_real_trace_collection_{args.timestamp}"
    out_dir = REPO_ROOT / "outputs" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    loss_paths = [Path(p) for p in args.loss_artifact]
    loss_paths.extend(sorted(REPO_ROOT.glob(args.loss_artifact_glob)))
    loss_paths = [p for p in loss_paths if p.exists()]
    candidate_rows = _collect_candidate_rows(loss_paths)
    rng = random.Random(args.selection_seed)
    planned = _sample_by_stratum(
        candidate_rows,
        absent_count=args.absent_count,
        present_count=args.present_count,
        control_count=args.control_count,
        rng=rng,
    )

    if args.max_cases > 0:
        planned = planned[: args.max_cases]

    budgets = _parse_int_list(args.budgets)
    seeds = _parse_int_list(args.seeds)
    methods = [m.strip() for m in str(args.methods).split(",") if m.strip()]

    expanded_plan: list[dict[str, Any]] = []
    case_idx = 0
    for row in planned:
        for seed in seeds:
            for budget in budgets:
                case_idx += 1
                expanded = dict(row)
                expanded["case_idx"] = case_idx
                expanded["seed"] = int(seed)
                expanded["budget"] = int(budget)
                expanded_plan.append(expanded)

    key_present = bool(os.getenv("COHERE_API_KEY"))
    real_api_enabled = bool(args.run_real_api and (not args.dry_run) and key_present)

    manifest = {
        "run_id": run_id,
        "timestamp": args.timestamp,
        "provider": args.provider,
        "model": args.model,
        "methods": methods,
        "budgets": budgets,
        "seeds": seeds,
        "run_real_api_requested": bool(args.run_real_api),
        "real_api_enabled": real_api_enabled,
        "dry_run": bool(args.dry_run or not real_api_enabled),
        "resume": bool(args.resume),
        "emit_full_traces": bool(args.emit_full_traces),
        "planned_base_cases": len(planned),
        "planned_runs": len(expanded_plan),
        "loss_artifact_paths": [str(p) for p in loss_paths],
    }
    _write_json(out_dir / "run_manifest.json", manifest)

    _write_csv(
        out_dir / "planned_cases.csv",
        expanded_plan,
        fieldnames=[
            "case_idx",
            "example_id",
            "dataset",
            "question",
            "gold_answer_raw",
            "gold_answer",
            "seed",
            "budget",
            "stratum",
            "failure_type",
            "source_path",
        ],
    )
    _write_csv(
        out_dir / "ten_case_inputs.csv",
        expanded_plan,
        fieldnames=[
            "case_idx",
            "example_id",
            "seed",
            "budget",
            "dataset",
            "question",
            "gold_answer_raw",
            "gold_answer",
        ],
    )

    per_case_results: list[dict[str, Any]] = []
    branch_rows: list[dict[str, Any]] = []
    action_rows: list[dict[str, Any]] = []
    answer_group_rows: list[dict[str, Any]] = []
    rd_rows: list[dict[str, Any]] = []

    controllers_by_budget: dict[int, dict[str, Any]] = {}
    if real_api_enabled:
        for budget in budgets:
            controller_rng = random.Random(args.selection_seed + budget)
            factory = generator_factory_for_mode(
                use_openai_api=True,
                rng=controller_rng,
                openai_model=args.model,
                temperature=args.temperature,
                max_output_tokens=args.max_output_tokens,
                timeout_seconds=args.timeout_seconds,
                api_provider=args.provider,
            )
            ctrls = build_frontier_strategies(
                generator_factory=factory,
                budget=budget,
                adaptive_min_expand_grid=[1],
                rng=controller_rng,
                use_openai_api=True,
                include_broad_diversity_aggregation_methods=True,
                include_external_l1_baseline=True,
            )
            for ctrl in ctrls.values():
                setattr(ctrl, "emit_full_traces", bool(args.emit_full_traces))
            controllers_by_budget[budget] = ctrls

    for row in expanded_plan:
        example_id = str(row["example_id"])
        for method in methods:
            runtime_method = STRICT_F3_RUNTIME if method == "strict_f3" else method
            metadata: dict[str, Any] = {"action_trace": [], "final_branch_states": []}
            final_answer = "NA"
            normalized_answer = "NA"
            is_correct = 0
            failure_type = "dry_run_trace"
            actions = expansions = verifications = 0
            if real_api_enabled:
                controller = controllers_by_budget.get(int(row["budget"]), {}).get(runtime_method)
                if controller is not None:
                    result = controller.run(str(row["question"]), str(row["gold_answer_raw"]))
                    metadata = result.metadata or {}
                    final_answer = str(result.prediction or "NA")
                    normalized_answer = _normalize_answer(final_answer, dataset=str(row["dataset"]))
                    is_correct = int(bool(result.is_correct))
                    failure_type = str(
                        metadata.get("early_divergence_failure_category")
                        or metadata.get("regime_failure_category")
                        or ("correct" if is_correct else "unknown")
                    )
                    actions = _coerce_int(result.actions_used, 0)
                    expansions = _coerce_int(result.expansions, 0)
                    verifications = _coerce_int(result.verifications, 0)

            per_case_results.append(
                {
                    "case_idx": row["case_idx"],
                    "example_id": example_id,
                    "seed": row["seed"],
                    "budget": row["budget"],
                    "method": method,
                    "runtime_method": runtime_method,
                    "final_answer": final_answer,
                    "normalized_answer": normalized_answer,
                    "is_correct": is_correct,
                    "failure_type": failure_type,
                    "actions": actions,
                    "expansions": expansions,
                    "verifications": verifications,
                    "dataset": row["dataset"],
                    "stratum": row.get("stratum", "unknown"),
                }
            )

            for ai, item in enumerate(list(metadata.get("action_trace", []))):
                action_rows.append(
                    {
                        "case_idx": row["case_idx"],
                        "example_id": example_id,
                        "seed": row["seed"],
                        "budget": row["budget"],
                        "provider": args.provider,
                        "model": args.model,
                        "dataset": row["dataset"],
                        "method": method,
                        "action_index": ai,
                        **item,
                    }
                )
                if item.get("group_key") not in (None, ""):
                    answer_group_rows.append(
                        {
                            "case_idx": row["case_idx"],
                            "example_id": example_id,
                            "seed": row["seed"],
                            "budget": row["budget"],
                            "provider": args.provider,
                            "model": args.model,
                            "dataset": row["dataset"],
                            "method": method,
                            "answer_group": item.get("group_key"),
                            "branch_id": item.get("branch_id", ""),
                        }
                    )

            for b in list(metadata.get("final_branch_states", [])):
                branch_rows.append(
                    {
                        "case_idx": row["case_idx"],
                        "example_id": example_id,
                        "seed": row["seed"],
                        "budget": row["budget"],
                        "provider": args.provider,
                        "model": args.model,
                        "dataset": row["dataset"],
                        "method": method,
                        **b,
                    }
                )

    _write_csv(out_dir / "per_case_results.csv", per_case_results)
    _write_csv(out_dir / "branch_table.csv", branch_rows)
    _write_csv(out_dir / "action_trace.csv", action_rows)
    _write_csv(out_dir / "answer_group_table.csv", answer_group_rows)
    _write_csv(out_dir / "reasoning_diversity_components.csv", rd_rows)

    by_case = Counter(str(r.get("example_id")) for r in per_case_results)
    trace_index = [
        {
            "example_id": ex,
            "n_per_case_rows": n,
            "n_branch_rows": sum(1 for r in branch_rows if str(r.get("example_id")) == ex),
            "n_action_rows": sum(1 for r in action_rows if str(r.get("example_id")) == ex),
            "n_answer_group_rows": sum(1 for r in answer_group_rows if str(r.get("example_id")) == ex),
        }
        for ex, n in sorted(by_case.items())
    ]
    _write_csv(out_dir / "per_case_trace_index.csv", trace_index)

    strat_counts = Counter(str(r.get("stratum", "unknown")) for r in expanded_plan)
    collection_summary = [
        {
            "n_planned_runs": len(expanded_plan),
            "n_unique_examples": len(set(str(r.get("example_id")) for r in expanded_plan)),
            "n_absent_from_tree": strat_counts.get("absent_from_tree", 0),
            "n_present_not_selected": strat_counts.get("present_not_selected", 0),
            "n_control_correct": strat_counts.get("control_correct", 0),
            "real_api_enabled": int(real_api_enabled),
            "n_branch_rows": len(branch_rows),
            "n_action_rows": len(action_rows),
            "n_answer_group_rows": len(answer_group_rows),
        }
    ]
    _write_csv(out_dir / "collection_summary.csv", collection_summary)

    readme = "\n".join(
        [
            f"# Bounded real trace collection ({args.timestamp})",
            "",
            f"Run id: `{run_id}`",
            f"Provider/model: `{args.provider}` / `{args.model}`",
            f"Real API enabled: `{real_api_enabled}`",
            "",
            "## Files",
            "- planned_cases.csv",
            "- run_manifest.json",
            "- per_case_trace_index.csv",
            "- collection_summary.csv",
            "- per_case_results.csv, branch_table.csv, action_trace.csv, answer_group_table.csv, reasoning_diversity_components.csv",
            "",
            "Dry-run mode writes the plan and schema-compatible trace tables without making external API calls.",
        ]
    )
    (out_dir / "README.md").write_text(readme + "\n", encoding="utf-8")

    print(f"Wrote: {out_dir}")


if __name__ == "__main__":
    main()
