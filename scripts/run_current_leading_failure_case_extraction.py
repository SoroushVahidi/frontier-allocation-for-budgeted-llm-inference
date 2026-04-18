#!/usr/bin/env python3
"""Bounded failure-case extraction for the current leading multistep mode."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.linear_model import Ridge

import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.bruteforce_branch_allocator import LearningConfig, load_label_artifacts, prepare_learning_tables


RUN_ID = "current_leading_failure_case_extraction_20260418"
OUTPUT_ROOT = Path("outputs/branch_label_bruteforce_learning") / RUN_ID
MULTISTEP_RUN = Path("outputs/branch_label_bruteforce_learning/multistep_branch_utility_target_eval_20260417")
TARGETS_ROOT = Path("outputs/branch_label_bruteforce_targets/multistep_branch_utility_target_20260417")
SEEDS = [11, 29, 47]
FEATURE_SET = "v3"
NEAR_TIE_MARGIN = 0.03
MULTISTEP_FIELD = "multistep_branch_utility_target"
LEADING_MODE = "multistep_branch_utility_target_k3"
K1_MODE = "multistep_branch_utility_target_k1"
BASELINE_MODE = "canonical_pairwise_baseline"


def _write_json(path: Path, payload: dict[str, Any] | list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _fit_and_score(candidates: list[dict[str, Any]], target_field: str, seed: int) -> tuple[dict[str, Any], dict[str, float]]:
    train = [r for r in candidates if str(r.get("split")) == "train"]
    if len(train) < 8:
        return ({"status": "insufficient_train_rows", "training_rows": len(train)}, {})
    x = np.array([r["x"] for r in train], dtype=float)
    y = np.array([float(r.get(target_field, r.get("estimated_value_if_allocate_next", 0.0))) for r in train], dtype=float)
    if np.std(y) <= 1e-12:
        return ({"status": "degenerate_target", "training_rows": len(train), "target_field": target_field}, {})
    model = Ridge(alpha=1.0, random_state=seed)
    model.fit(x, y)
    scores: dict[str, float] = {}
    for r in candidates:
        if str(r.get("split")) != "test":
            continue
        key = f"{r.get('state_id')}::{r.get('branch_id')}"
        scores[key] = float(np.dot(model.coef_, np.array(r["x"], dtype=float)) + model.intercept_)
    return ({
        "status": "ok",
        "target_field": target_field,
        "training_rows": len(train),
        "weights": [float(v) for v in model.coef_],
        "intercept": float(model.intercept_),
    }, scores)


def _state_flags(pair_rows: list[dict[str, Any]]) -> dict[str, dict[str, bool]]:
    out: dict[str, dict[str, bool]] = {}
    for r in pair_rows:
        if str(r.get("split")) != "test":
            continue
        sid = str(r.get("state_id"))
        f = out.setdefault(sid, {"near_tie": False, "adjacent_rank": False, "strict_slice": False})
        near = bool(r.get("near_tie_flag", False))
        adj = str(r.get("pair_type", "")) == "adjacent_rank"
        f["near_tie"] = bool(f["near_tie"] or near)
        f["adjacent_rank"] = bool(f["adjacent_rank"] or adj)
        f["strict_slice"] = bool(f["strict_slice"] or (near and adj))
    return out


def _rank_state_rows(
    *,
    seed: int,
    state_rows: list[dict[str, Any]],
    state_flag: dict[str, bool],
    k3_scores: dict[str, float],
    k1_scores: dict[str, float],
) -> dict[str, Any]:
    sid = str(state_rows[0].get("state_id"))
    dataset = str(state_rows[0].get("dataset_name", ""))
    example_id = str(state_rows[0].get("example_id", ""))
    remaining_budget = int(state_rows[0].get("remaining_budget", 0))

    sorted_by_pred = sorted(
        state_rows,
        key=lambda r: float(k3_scores.get(f"{sid}::{r.get('branch_id')}", -1e18)),
        reverse=True,
    )
    sorted_by_k1 = sorted(
        state_rows,
        key=lambda r: float(k1_scores.get(f"{sid}::{r.get('branch_id')}", -1e18)),
        reverse=True,
    )
    sorted_by_oracle = sorted(state_rows, key=lambda r: float(r.get("estimated_value_if_allocate_next", 0.0)), reverse=True)

    chosen = sorted_by_pred[0]
    oracle_best = sorted_by_oracle[0]
    k1_best = sorted_by_k1[0]

    chosen_bid = str(chosen.get("branch_id"))
    oracle_bid = str(oracle_best.get("branch_id"))
    k1_bid = str(k1_best.get("branch_id"))

    oracle_gap = float(oracle_best.get("estimated_value_if_allocate_next", 0.0) - chosen.get("estimated_value_if_allocate_next", 0.0))
    pred_margin = 0.0
    oracle_margin = 0.0
    if len(sorted_by_pred) > 1:
        pred_margin = float(
            k3_scores.get(f"{sid}::{sorted_by_pred[0].get('branch_id')}", 0.0)
            - k3_scores.get(f"{sid}::{sorted_by_pred[1].get('branch_id')}", 0.0)
        )
    if len(sorted_by_oracle) > 1:
        oracle_margin = float(
            sorted_by_oracle[0].get("estimated_value_if_allocate_next", 0.0)
            - sorted_by_oracle[1].get("estimated_value_if_allocate_next", 0.0)
        )

    per_branch = []
    for r in sorted(state_rows, key=lambda rr: str(rr.get("branch_id"))):
        bid = str(r.get("branch_id"))
        per_branch.append(
            {
                "branch_id": bid,
                "method_score_k3": float(k3_scores.get(f"{sid}::{bid}", 0.0)),
                "method_score_k1": float(k1_scores.get(f"{sid}::{bid}", 0.0)),
                "oracle_one_step_value": float(r.get("estimated_value_if_allocate_next", 0.0)),
                "multistep_target_value": float(r.get("multistep_branch_utility_target", 0.0)),
                "multistep_delta_vs_onestep": float(r.get("multistep_branch_utility_delta_vs_onestep", 0.0)),
                "allocation_value_std": float(r.get("allocation_value_std", 0.0)),
                "branch_vs_outside_gap": float(r.get("branch_vs_outside_gap", 0.0)),
                "outside_option_value": float(r.get("outside_option_value", 0.0)),
                "best_followup_allocation": r.get("best_followup_allocation", []),
                "multistep_target_self_followup_ratio": float(r.get("multistep_target_self_followup_ratio", 0.0)),
            }
        )

    return {
        "case_id": f"seed{seed}::{sid}",
        "seed": int(seed),
        "state_id": sid,
        "dataset_name": dataset,
        "example_id": example_id,
        "remaining_budget": remaining_budget,
        "branch_count": len(state_rows),
        "method_choice_k3": chosen_bid,
        "method_choice_k1": k1_bid,
        "oracle_best_branch": oracle_bid,
        "method_matches_oracle": bool(chosen_bid == oracle_bid),
        "k1_vs_k3_disagree": bool(k1_bid != chosen_bid),
        "oracle_gap_if_choose_k3": oracle_gap,
        "k3_pred_margin_top2": pred_margin,
        "oracle_margin_top2": oracle_margin,
        "is_near_tie_state": bool(state_flag.get("near_tie", False)),
        "is_adjacent_rank_state": bool(state_flag.get("adjacent_rank", False)),
        "is_strict_slice_state": bool(state_flag.get("strict_slice", False)),
        "method_score_for_chosen_k3": float(k3_scores.get(f"{sid}::{chosen_bid}", 0.0)),
        "oracle_value_for_chosen_k3": float(chosen.get("estimated_value_if_allocate_next", 0.0)),
        "oracle_value_for_optimal": float(oracle_best.get("estimated_value_if_allocate_next", 0.0)),
        "multistep_target_for_chosen_k3": float(chosen.get("multistep_branch_utility_target", 0.0)),
        "multistep_target_for_oracle_best": float(oracle_best.get("multistep_branch_utility_target", 0.0)),
        "per_branch": per_branch,
    }


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    aggregate = json.loads((MULTISTEP_RUN / "aggregate_comparison_summary.json").read_text(encoding="utf-8"))
    leading_mode = max(
        (
            (mode, vals.get("accepted_accuracy_mean", 0.0))
            for mode, vals in aggregate.get("aggregate", {}).items()
            if str(mode).startswith("multistep_branch_utility_target_")
        ),
        key=lambda kv: kv[1],
    )[0]
    if leading_mode != LEADING_MODE:
        raise RuntimeError(f"Expected leading mode {LEADING_MODE}, found {leading_mode}")

    all_state_rows: list[dict[str, Any]] = []
    fit_status: list[dict[str, Any]] = []

    baseline_raw = load_label_artifacts(TARGETS_ROOT / "regime_all_pairs")

    for seed in SEEDS:
        cfg = LearningConfig(
            seed=int(seed),
            near_tie_margin=NEAR_TIE_MARGIN,
            feature_set=FEATURE_SET,
            train_pairwise=True,
            train_pointwise=True,
            train_outside_option=False,
            train_lightgbm_ranker=False,
            train_catboost_ranker=False,
            train_pairwise_svm=False,
        )
        baseline_tables = prepare_learning_tables(baseline_raw, cfg)
        state_flag_map = _state_flags(baseline_tables["pairwise"])

        k3_raw = load_label_artifacts(TARGETS_ROOT / "regime_multistep_branch_utility_target_k3")
        k3_tables = prepare_learning_tables(k3_raw, cfg)
        k3_fit, k3_scores = _fit_and_score(k3_tables["candidates"], MULTISTEP_FIELD, int(seed))
        fit_status.append({"seed": int(seed), "mode": LEADING_MODE, **k3_fit})

        k1_raw = load_label_artifacts(TARGETS_ROOT / "regime_multistep_branch_utility_target_k1")
        k1_tables = prepare_learning_tables(k1_raw, cfg)
        k1_fit, k1_scores = _fit_and_score(k1_tables["candidates"], MULTISTEP_FIELD, int(seed))
        fit_status.append({"seed": int(seed), "mode": K1_MODE, **k1_fit})

        test_rows = [r for r in k3_tables["candidates"] if str(r.get("split")) == "test"]
        by_state: dict[str, list[dict[str, Any]]] = {}
        for row in test_rows:
            by_state.setdefault(str(row.get("state_id")), []).append(row)

        for sid, rows in sorted(by_state.items()):
            all_state_rows.append(
                _rank_state_rows(
                    seed=int(seed),
                    state_rows=rows,
                    state_flag=state_flag_map.get(sid, {}),
                    k3_scores=k3_scores,
                    k1_scores=k1_scores,
                )
            )

    mismatches = [r for r in all_state_rows if not bool(r["method_matches_oracle"]) ]
    ranking = sorted(
        all_state_rows,
        key=lambda r: (
            1 if not bool(r["method_matches_oracle"]) else 0,
            float(r["oracle_gap_if_choose_k3"]),
            -float(r["k3_pred_margin_top2"]),
            1 if bool(r["is_near_tie_state"]) else 0,
        ),
        reverse=True,
    )
    selected = ranking[:4]

    for row in ranking:
        row["selection_bucket"] = "failure" if not bool(row["method_matches_oracle"]) else "boundary_control"

    _write_json(
        OUTPUT_ROOT / "failure_case_selection_manifest.json",
        {
            "run_id": RUN_ID,
            "source_multistep_run": str(MULTISTEP_RUN),
            "source_targets_root": str(TARGETS_ROOT),
            "seeds": SEEDS,
            "feature_set": FEATURE_SET,
            "near_tie_margin": NEAR_TIE_MARGIN,
            "leading_mode_selection_rule": "argmax accepted_accuracy_mean among multistep modes in aggregate_comparison_summary.json",
            "leading_mode": LEADING_MODE,
            "selection_rule": "Rank all test states with failures first (method choice != oracle best), then by oracle_gap_if_choose_k3 descending, then by smallest k3 predicted top-2 margin. Select top 4; if fewer than 4 strict failures exist, include boundary-control states with smallest predicted margin.",
            "selection_limit": 4,
            "total_test_states_evaluated": len(all_state_rows),
            "total_mismatches": len(mismatches),
            "selected_failure_count": sum(1 for r in selected if not bool(r["method_matches_oracle"])),
            "selected_boundary_control_count": sum(1 for r in selected if bool(r["method_matches_oracle"])),
            "fit_status": fit_status,
            "baseline_mode_reference": BASELINE_MODE,
        },
    )
    _write_json(OUTPUT_ROOT / "failure_case_ranking_table.json", {"rows": ranking})
    _write_json(OUTPUT_ROOT / "selected_failure_case_ids.json", {"case_ids": [r["case_id"] for r in selected]})
    _write_json(OUTPUT_ROOT / "selected_failure_cases_structured.json", {"cases": selected})

    caveats = (
        "# Commands, assumptions, and caveats\n\n"
        "## Commands run\n"
        "- `python scripts/run_current_leading_failure_case_extraction.py`\n\n"
        "## Assumptions\n"
        "- `estimated_value_if_allocate_next` is treated as the oracle/optimal one-step utility under the same artifacts.\n"
        "- Leading mode is selected from `aggregate_comparison_summary.json` in the latest multistep validation directory.\n"
        "- Per-seed train/test splits are reconstructed via `prepare_learning_tables` with the canonical seed and config.\n\n"
        "## Caveats\n"
        "- Support is small (21 total test states across 3 seeds), so failure rankings are diagnostic, not statistically stable.\n"
        "- Full question text and branch text are not present in these artifacts; diagnosis is state/branch-ID level only.\n"
        "- Method scores are linear model outputs fit in this extraction pass to mirror the multistep evaluation protocol.\n"
    )
    (OUTPUT_ROOT / "commands_assumptions_caveats.md").write_text(caveats, encoding="utf-8")

    print(json.dumps({
        "output_dir": str(OUTPUT_ROOT),
        "leading_mode": LEADING_MODE,
        "total_test_states": len(all_state_rows),
        "mismatch_states": len(mismatches),
        "selected_case_ids": [r["case_id"] for r in selected],
    }, indent=2))


if __name__ == "__main__":
    main()
