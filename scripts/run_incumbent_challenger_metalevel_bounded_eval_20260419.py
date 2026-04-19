#!/usr/bin/env python3
from __future__ import annotations

import argparse
import itertools
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

from experiments.frontier_matrix_core import build_frontier_strategies, generator_factory_for_mode, load_pilot_examples

BASE = "broad_diversity_aggregation_strong_v1_incumbent_challenger_commit_v1"
NEW = "broad_diversity_aggregation_strong_v1_incumbent_challenger_metalevel_v2"


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _parse_ints(raw: str) -> list[int]:
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def _parse_floats(raw: str) -> list[float]:
    return [float(x.strip()) for x in raw.split(",") if x.strip()]


def _parse_bools(raw: str) -> list[bool]:
    out: list[bool] = []
    for x in raw.split(","):
        x = x.strip().lower()
        if not x:
            continue
        out.append(x in {"1", "true", "t", "yes", "y", "on"})
    return out


def _ic_state(meta: dict[str, Any]) -> dict[str, Any]:
    checks = meta.get("incumbent_challenger_checks") or []
    return checks[-1] if checks else {}


def _failure_group(row: dict[str, Any]) -> str:
    if row["is_correct"]:
        return "correct"
    meta = row.get("metadata") or {}
    if row.get("prediction") is None:
        return "incomplete_or_non_terminal"
    if row.get("budget_exhausted") or (not bool(meta.get("commit_triggered", False)) and int(row.get("actions_used", 0)) >= int(row.get("budget", 0)) - 1):
        return "wrong_commit_timing"
    if _safe_float(meta.get("answer_group_margin", 0.0)) <= 0.20:
        return "ambiguity_near_tie"
    return "other"


def _wrong_commit_subtype(row: dict[str, Any]) -> str:
    if row.get("failure_group") != "wrong_commit_timing":
        return "not_wrong_commit_timing"
    meta = row.get("metadata") or {}
    ic = _ic_state(meta)
    risk = Counter(ic.get("wrong_commit_risk_subtypes") or [])
    if risk.get("committed_to_intermediate_result", 0) > 0:
        return "committed_to_intermediate_result"
    if risk.get("challenger_had_recoverable_upside", 0) > 0:
        return "challenger_had_recoverable_upside"
    if risk.get("committed_under_near_tie_ambiguity", 0) > 0:
        return "committed_under_near_tie_ambiguity"
    if risk.get("overcounted_weak_corroboration", 0) > 0:
        return "overcounted_weak_corroboration"
    return "wrong_commit_other"


def _load_bundle(bundle_name: str) -> list[str]:
    payload = json.loads((REPO_ROOT / "configs/dataset_experiment_readiness_bundles.json").read_text(encoding="utf-8"))
    return [str(x) for x in (((payload.get("bundles") or {}).get(bundle_name) or {}).get("datasets") or [])]


def _apply_setting(controller: Any, setting: dict[str, Any]) -> None:
    controller.challenger_upside_commit_max = float(setting["challenger_upside_commit_max"])
    controller.metalevel_delta_margin = float(setting["metalevel_delta_margin"])
    controller.near_tie_commit_margin_extra = float(setting["near_tie_commit_margin_extra"])
    controller.force_extra_explore_on_near_tie = bool(setting["force_extra_explore_on_near_tie"])
    controller.near_tie_force_upside_frac_threshold = float(setting["near_tie_force_upside_frac_threshold"])


def _run_once(
    *,
    datasets: list[str],
    seeds: list[int],
    budgets: list[int],
    adaptive_grid: list[int],
    subset_size: int,
    setting: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    rng_master = random.Random(20260419)
    for dataset in datasets:
        for seed in seeds:
            examples = load_pilot_examples(dataset, subset_size, seed)
            rng = random.Random(rng_master.randint(0, 10**9))
            factory = generator_factory_for_mode(False, rng, "gpt-4.1-mini", 0.2, 180, 45)
            for budget in budgets:
                specs = build_frontier_strategies(
                    factory,
                    budget,
                    adaptive_grid,
                    rng,
                    use_openai_api=False,
                    include_selective_sc_hybrid_methods=True,
                    include_broad_diversity_aggregation_methods=True,
                )
                specs = {k: v for k, v in specs.items() if k in {BASE, NEW}}
                _apply_setting(specs[NEW], setting)
                for ex in examples:
                    for method, ctrl in specs.items():
                        r = ctrl.run(ex.question, ex.answer)
                        row = {
                            "setting_id": str(setting["setting_id"]),
                            "setting": setting,
                            "dataset": dataset,
                            "seed": int(seed),
                            "budget": int(budget),
                            "example_id": ex.example_id,
                            "problem_statement": ex.question,
                            "gold_answer": ex.answer,
                            "method": method,
                            "prediction": r.prediction,
                            "is_correct": bool(r.is_correct),
                            "actions_used": int(r.actions_used),
                            "expansions": int(r.expansions),
                            "verifications": int(r.verifications),
                            "budget_exhausted": bool(r.budget_exhausted),
                            "metadata": r.metadata,
                        }
                        row["failure_group"] = _failure_group(row)
                        row["wrong_commit_subtype"] = _wrong_commit_subtype(row)
                        rows.append(row)
    return rows


def _harmed_subtype(base_row: dict[str, Any], cand_row: dict[str, Any]) -> str:
    cm = cand_row.get("metadata") or {}
    cic_checks = cm.get("incumbent_challenger_checks") or []
    risk_counts = Counter(
        item
        for c in cic_checks
        for item in list(c.get("wrong_commit_risk_subtypes", []))
    )
    if any(bool(c.get("intermediate_result_flags_present", False)) for c in cic_checks):
        return "intermediate_penalty_fired_but_hurt"
    if risk_counts.get("overcounted_weak_corroboration", 0) > 0:
        return "correlated_support_penalty_side_effect"
    if (not bool((cm.get("commit_triggered", False)))) and int(cand_row.get("actions_used", 0)) > int(base_row.get("actions_used", 0)) + 1:
        return "premature_extra_exploration_false_non_commit"
    expanded_branches = [a.get("branch_id") for a in (cm.get("action_trace") or []) if str(a.get("action")) == "expand"]
    if len(set(str(x) for x in expanded_branches if x is not None)) >= 3:
        return "wrong_challenger_chosen"
    return "other_harmed"


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_method: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_method[str(r["method"])].append(r)

    metrics: dict[str, dict[str, Any]] = {}
    for method in [BASE, NEW]:
        mr = by_method.get(method, [])
        n = max(1, len(mr))
        action_traces = [a for x in mr for a in ((x.get("metadata") or {}).get("action_trace") or [])]
        action_counts = Counter(str(a.get("action", "")) for a in action_traces)
        wrong_subtypes = Counter(str(x.get("wrong_commit_subtype", "")) for x in mr if x.get("failure_group") == "wrong_commit_timing")
        checks = [c for x in mr for c in ((x.get("metadata") or {}).get("incumbent_challenger_checks") or [])]
        metrics[method] = {
            "n_examples": len(mr),
            "accuracy": sum(1 for x in mr if bool(x.get("is_correct", False))) / n,
            "accepted_accuracy": sum(1 for x in mr if bool(x.get("is_correct", False))) / n,
            "wrong_commit_timing_count": sum(1 for x in mr if x.get("failure_group") == "wrong_commit_timing"),
            "commit_triggered_count": sum(1 for x in mr if bool((x.get("metadata") or {}).get("commit_triggered", False))),
            "avg_actions": sum(float(x.get("actions_used", 0)) for x in mr) / n,
            "avg_expansions": sum(float(x.get("expansions", 0)) for x in mr) / n,
            "avg_verifications": sum(float(x.get("verifications", 0)) for x in mr) / n,
            "expand_action_count": int(action_counts.get("expand", 0)),
            "verify_action_count": int(action_counts.get("verify", 0)),
            "wrong_commit_subtypes": dict(wrong_subtypes),
            "mean_near_tie_forced_steps": sum(float((x.get("metadata") or {}).get("near_tie_forced_steps_used", 0)) for x in mr) / n,
            "intermediate_flag_rate": sum(int(bool(c.get("intermediate_result_flags_present", False))) for c in checks) / max(1, len(checks)),
        }

    aligned: dict[tuple[str, int, int, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for r in rows:
        key = (str(r["dataset"]), int(r["seed"]), int(r["budget"]), str(r["example_id"]))
        aligned[key][str(r["method"])] = r

    improved: list[dict[str, Any]] = []
    harmed: list[dict[str, Any]] = []
    harmed_breakdown: Counter[str] = Counter()
    for pair in aligned.values():
        if BASE not in pair or NEW not in pair:
            continue
        b = pair[BASE]
        c = pair[NEW]
        rec = {
            "dataset": c["dataset"],
            "seed": c["seed"],
            "budget": c["budget"],
            "example_id": c["example_id"],
            "problem_statement": c["problem_statement"],
            "gold_answer": c["gold_answer"],
            "base_answer": b["prediction"],
            "candidate_answer": c["prediction"],
            "base_actions": b["actions_used"],
            "candidate_actions": c["actions_used"],
            "base_failure_group": b["failure_group"],
            "candidate_failure_group": c["failure_group"],
            "base_wrong_commit_subtype": b["wrong_commit_subtype"],
            "candidate_wrong_commit_subtype": c["wrong_commit_subtype"],
        }
        if (not b["is_correct"]) and c["is_correct"]:
            improved.append(rec)
        elif b["is_correct"] and (not c["is_correct"]):
            rec["harmed_subtype"] = _harmed_subtype(b, c)
            harmed_breakdown.update([str(rec["harmed_subtype"])])
            harmed.append(rec)

    delta = {
        "accuracy": _safe_float(metrics.get(NEW, {}).get("accuracy", 0.0)) - _safe_float(metrics.get(BASE, {}).get("accuracy", 0.0)),
        "wrong_commit_timing_count": int(metrics.get(NEW, {}).get("wrong_commit_timing_count", 0)) - int(metrics.get(BASE, {}).get("wrong_commit_timing_count", 0)),
        "commit_triggered_count": int(metrics.get(NEW, {}).get("commit_triggered_count", 0)) - int(metrics.get(BASE, {}).get("commit_triggered_count", 0)),
    }

    return {
        "metrics": metrics,
        "delta_candidate_minus_baseline": delta,
        "improved_cases": improved,
        "harmed_cases": harmed,
        "harmed_breakdown": dict(harmed_breakdown),
    }


def _setting_space(args: argparse.Namespace) -> list[dict[str, Any]]:
    space = list(
        itertools.product(
            _parse_floats(args.grid_challenger_upside_commit_max),
            _parse_floats(args.grid_metalevel_delta_margin),
            _parse_floats(args.grid_near_tie_commit_margin_extra),
            _parse_bools(args.grid_force_extra_explore_on_near_tie),
            _parse_floats(args.grid_near_tie_force_upside_frac_threshold),
        )
    )
    settings: list[dict[str, Any]] = []
    for i, (upside_max, delta_margin, near_tie_extra, force_near_tie, near_tie_upside_frac) in enumerate(space):
        settings.append(
            {
                "setting_id": f"s{i:02d}",
                "challenger_upside_commit_max": float(upside_max),
                "metalevel_delta_margin": float(delta_margin),
                "near_tie_commit_margin_extra": float(near_tie_extra),
                "force_extra_explore_on_near_tie": bool(force_near_tie),
                "near_tie_force_upside_frac_threshold": float(near_tie_upside_frac),
            }
        )
    return settings


def _best_setting_id(grid_rows: list[dict[str, Any]]) -> str:
    ranked = sorted(
        grid_rows,
        key=lambda r: (
            float(r["summary"]["metrics"][NEW]["accuracy"]),
            -int(r["summary"]["metrics"][NEW]["wrong_commit_timing_count"]),
            -int(r["summary"].get("harmed_count", 0)),
            int(r["summary"].get("improved_count", 0)),
        ),
        reverse=True,
    )
    return str(ranked[0]["setting"]["setting_id"]) if ranked else ""


def main() -> None:
    p = argparse.ArgumentParser(description="Bounded grid + confirmatory eval for metalevel ICC calibration")
    p.add_argument("--bundle", default="exact_answer_math_expansion")
    p.add_argument("--datasets", default="")
    p.add_argument("--subset-size", type=int, default=8)
    p.add_argument("--seeds", default="11")
    p.add_argument("--budgets", default="6")
    p.add_argument("--adaptive-grid", default="1")
    p.add_argument("--confirm-seeds", default="23")
    p.add_argument("--output-dir", default="outputs/incumbent_challenger_metalevel_bounded_eval_20260419")
    p.add_argument("--grid-challenger-upside-commit-max", default="0.15,0.17,0.19")
    p.add_argument("--grid-metalevel-delta-margin", default="0.00,0.01,0.02")
    p.add_argument("--grid-near-tie-commit-margin-extra", default="0.00,0.01,0.02")
    p.add_argument("--grid-force-extra-explore-on-near-tie", default="true,false")
    p.add_argument("--grid-near-tie-force-upside-frac-threshold", default="0.60,0.75")
    args = p.parse_args()

    datasets = [d.strip() for d in args.datasets.split(",") if d.strip()] if args.datasets.strip() else _load_bundle(args.bundle)
    seeds = _parse_ints(args.seeds)
    budgets = _parse_ints(args.budgets)
    adaptive_grid = _parse_ints(args.adaptive_grid)
    confirm_seeds = _parse_ints(args.confirm_seeds)

    out_dir = REPO_ROOT / args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    settings = _setting_space(args)
    grid_rows: list[dict[str, Any]] = []

    for setting in settings:
        rows = _run_once(
            datasets=datasets,
            seeds=seeds,
            budgets=budgets,
            adaptive_grid=adaptive_grid,
            subset_size=int(args.subset_size),
            setting=setting,
        )
        summary = _summarize(rows)
        summary["improved_count"] = len(summary["improved_cases"])
        summary["harmed_count"] = len(summary["harmed_cases"])
        grid_rows.append({"setting": setting, "summary": summary})

    best_id = _best_setting_id(grid_rows)
    best_item = next((x for x in grid_rows if str(x["setting"]["setting_id"]) == best_id), None)

    confirm_rows: list[dict[str, Any]] = []
    confirm_summary: dict[str, Any] = {}
    if best_item is not None:
        confirm_rows = _run_once(
            datasets=datasets,
            seeds=confirm_seeds,
            budgets=budgets,
            adaptive_grid=adaptive_grid,
            subset_size=int(args.subset_size),
            setting=best_item["setting"],
        )
        confirm_summary = _summarize(confirm_rows)
        confirm_summary["improved_count"] = len(confirm_summary["improved_cases"])
        confirm_summary["harmed_count"] = len(confirm_summary["harmed_cases"])

    artifact = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_type": "bounded_grid_and_confirmatory",
        "methods": {"baseline": BASE, "candidate": NEW},
        "datasets": datasets,
        "grid_seeds": seeds,
        "confirmatory_seeds": confirm_seeds,
        "budgets": budgets,
        "subset_size": int(args.subset_size),
        "settings_tested": [x["setting"] for x in grid_rows],
        "grid_results": [
            {
                "setting": x["setting"],
                "candidate_accuracy": x["summary"]["metrics"][NEW]["accuracy"],
                "baseline_accuracy": x["summary"]["metrics"][BASE]["accuracy"],
                "delta_accuracy": x["summary"]["delta_candidate_minus_baseline"]["accuracy"],
                "candidate_wrong_commit_timing_count": x["summary"]["metrics"][NEW]["wrong_commit_timing_count"],
                "baseline_wrong_commit_timing_count": x["summary"]["metrics"][BASE]["wrong_commit_timing_count"],
                "candidate_expand_action_count": x["summary"]["metrics"][NEW]["expand_action_count"],
                "baseline_expand_action_count": x["summary"]["metrics"][BASE]["expand_action_count"],
                "candidate_commit_triggered_count": x["summary"]["metrics"][NEW]["commit_triggered_count"],
                "baseline_commit_triggered_count": x["summary"]["metrics"][BASE]["commit_triggered_count"],
                "improved_count": x["summary"]["improved_count"],
                "harmed_count": x["summary"]["harmed_count"],
                "harmed_breakdown": x["summary"]["harmed_breakdown"],
                "intermediate_flag_rate_candidate": x["summary"]["metrics"][NEW]["intermediate_flag_rate"],
            }
            for x in grid_rows
        ],
        "best_setting_id": best_id,
        "best_setting": best_item["setting"] if best_item else None,
        "best_setting_grid_summary": best_item["summary"] if best_item else {},
        "confirmatory_summary": confirm_summary,
        "notes": [
            "Conservative bounded calibration pass; no broad-sweep claims.",
            "If best setting is still unfavorable in confirmatory run, treat as negative evidence and keep tuning local.",
        ],
    }

    (out_dir / "grid_and_confirmatory_summary.json").write_text(json.dumps(artifact, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "best_setting_grid_improved_cases.json").write_text(
        json.dumps((best_item or {"summary": {}})["summary"].get("improved_cases", []), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (out_dir / "best_setting_grid_harmed_cases.json").write_text(
        json.dumps((best_item or {"summary": {}})["summary"].get("harmed_cases", []), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (out_dir / "confirmatory_improved_cases.json").write_text(
        json.dumps(confirm_summary.get("improved_cases", []), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (out_dir / "confirmatory_harmed_cases.json").write_text(
        json.dumps(confirm_summary.get("harmed_cases", []), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(json.dumps({
        "best_setting_id": best_id,
        "best_setting": best_item["setting"] if best_item else None,
        "best_grid_delta_accuracy": ((best_item or {"summary": {"delta_candidate_minus_baseline": {"accuracy": 0.0}}})["summary"]["delta_candidate_minus_baseline"]["accuracy"] if best_item else 0.0),
        "confirmatory_delta_accuracy": _safe_float(confirm_summary.get("delta_candidate_minus_baseline", {}).get("accuracy", 0.0)),
    }, indent=2))


if __name__ == "__main__":
    main()
