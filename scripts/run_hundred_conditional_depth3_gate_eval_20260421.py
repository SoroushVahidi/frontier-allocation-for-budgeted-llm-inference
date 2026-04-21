#!/usr/bin/env python3
"""Four-way eval: baseline vs depth-2 vs depth-3 vs conditional gated depth-3 on the frozen hundred-case loss set.

Replays the same ``(dataset, example_id, seed, budget)`` rows as
``build_hundred_current_full_vs_best_failure_statistics`` using ``fresh_our`` / ``fresh_best``.

Methods:
  A) current canonical full (+ deterministic output-layer repair)
  B) hard early root depth-2 forced
  C) hard early root depth-3 forced
  D) hard depth-2 then conditional depth-3 gate (``hard_early_root_depth2_then_conditional_depth3_v1``)

Optional ``--include-gated-combo``: gated + low-marginal-gain cooldown (extra columns only).
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.frontier_matrix_core import load_pilot_examples

HUNDRED_SUBSET_SIZE = 96

BASE_SUFFIX = (
    "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1"
)
DEPTH2_METHOD = f"{BASE_SUFFIX}_hard_early_root_depth2_coverage_forced_v1__deterministic_output_layer_repair_v1"
DEPTH3_METHOD = f"{BASE_SUFFIX}_hard_early_root_depth3_coverage_forced_v1__deterministic_output_layer_repair_v1"
GATED_METHOD = f"{BASE_SUFFIX}_hard_early_root_depth2_then_conditional_depth3_v1__deterministic_output_layer_repair_v1"
GATED_COMBO_METHOD = (
    f"{BASE_SUFFIX}_hard_early_root_depth2_then_conditional_depth3_v1_low_marginal_gain_cooldown_v1__deterministic_output_layer_repair_v1"
)
BEAM_METHOD = "reasoning_beam2"


def _load_hundred_module() -> Any:
    path = REPO_ROOT / "scripts/build_hundred_current_full_vs_best_failure_statistics.py"
    spec = importlib.util.spec_from_file_location("hundred_stats", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_twenty_module() -> Any:
    path = REPO_ROOT / "scripts/build_twenty_exact_current_full_vs_best_fresh.py"
    spec = importlib.util.spec_from_file_location("twenty_exact_bundle", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


HM = _load_hundred_module()
TW = _load_twenty_module()


def _map_failure(concise: str) -> str:
    return HM._map_failure_type(concise)


def _classify_ours(
    our_raw: dict[str, Any], gold_raw: str, dataset: str
) -> tuple[str, str, bool, bool]:
    our_repair = TW.choose_repair_answer(
        final_nodes=list(our_raw["final_nodes"]),
        selected_group_hint=(our_raw.get("metadata") or {}).get("selected_group"),
        dataset=dataset,
        enable_rescue=True,
    )
    our_answer = our_repair.get("surfaced_final_answer_raw")
    our_can = TW.canonicalize_answer(our_answer, dataset=dataset)
    gold_can = TW.canonicalize_answer(gold_raw, dataset=dataset)
    is_correct = bool(our_can == gold_can and our_can is not None)
    our_correct_ids = TW._node_ids_with_answer(our_raw["final_nodes"], gold_can)
    our_contains = bool(our_correct_ids)
    output_mismatch = bool(
        our_contains
        and (our_repair.get("chosen_final_node_answer_canonical") == gold_can)
        and (our_can != gold_can)
    )
    extraction_mismatch = bool(
        (our_repair.get("chosen_final_node_answer_canonical") != our_repair.get("extracted_final_answer_canonical"))
        or (our_repair.get("extracted_final_answer_canonical") != our_repair.get("surfaced_final_answer_canonical"))
        or (our_repair.get("chosen_final_node_answer_raw") != our_repair.get("chosen_final_node_answer_canonical"))
    )
    if not our_contains:
        concise = "absent_from_tree"
    elif output_mismatch or extraction_mismatch:
        concise = "output_layer_mismatch"
    else:
        concise = "present_not_selected" if not is_correct else "correct"
    failure_type = _map_failure(concise) if concise != "correct" else "correct"
    return str(failure_type), concise, is_correct, our_contains


def _run_case(
    method_name: str,
    dataset: str,
    example_id: str,
    question: str,
    gold: str,
    seed: int,
    budget: int,
    stream_tag: str,
) -> dict[str, Any]:
    row = {
        "dataset": dataset,
        "example_id": example_id,
        "problem_text": question,
        "ground_truth": gold,
        "seed": seed,
        "budget": budget,
    }
    return HM._run_observed_with_events(method_name, row, stream_tag)


def _lookup_example(dataset: str, example_id: str, seed: int) -> tuple[str, str] | None:
    for ex in load_pilot_examples(dataset, HUNDRED_SUBSET_SIZE, seed):
        if ex.example_id == example_id:
            return ex.question, ex.answer
    return None


def _delta_outcome(b_ok: bool, n_ok: bool) -> str:
    if b_ok:
        return "unchanged_correct" if n_ok else "worsened"
    if n_ok:
        return "improved"
    return "unchanged_still_wrong"


def _cov_diag(raw: dict[str, Any]) -> dict[str, Any]:
    m = raw.get("metadata") or {}
    return {
        "hard_early_coverage_completed_fully": bool(m.get("hard_early_coverage_completed_fully")),
        "hard_early_coverage_budget_released_impossible": bool(m.get("hard_early_coverage_budget_released_impossible")),
        "hard_early_coverage_transition_actions_used": m.get("hard_early_coverage_transition_actions_used"),
        "hard_early_root_coverage_forced_min_depth": int(m.get("hard_early_root_coverage_forced_min_depth") or 0),
        "hard_early_coverage_final_family_status": m.get("hard_early_coverage_final_family_status") or {},
    }


def _gated_diag(raw: dict[str, Any]) -> dict[str, Any]:
    m = raw.get("metadata") or {}
    gr = m.get("conditional_depth3_gate_record")
    st = str((gr or {}).get("depth3_release_status") or "")
    if st == "gated_on":
        decision = "gated_on"
    elif st == "gated_off":
        decision = "gated_off"
    elif st == "gated_on_but_released_impossible_under_budget":
        decision = "gated_on_but_released_impossible_under_budget"
    elif st == "gated_on_but_run_ended_before_depth3_forcing":
        decision = "gated_on_but_run_ended_before_depth3_forcing"
    elif st == "skipped_run_ended_before_depth2_terminal":
        decision = "skipped_run_ended_before_depth2_terminal"
    else:
        decision = st or "pending_or_unknown"
    crit = (gr or {}).get("criteria_fired") if isinstance(gr, dict) else None
    return {
        "gated_depth3_gate_decision": decision,
        "gated_depth3_gate_triggered_criteria": crit,
        "gated_depth3_forcing_completed": bool(m.get("conditional_depth3_forcing_completed")),
        "gated_release_impossible_under_budget": bool(m.get("hard_early_coverage_budget_released_impossible")),
        "conditional_coverage_phase_final": str(m.get("conditional_coverage_phase_final") or ""),
    }


def _n_families_satisfied(cov: dict[str, Any]) -> int:
    st = cov.get("hard_early_coverage_final_family_status") or {}
    return sum(1 for _k, v in st.items() if isinstance(v, dict) and not v.get("pending", True))


def _criteria_counter(rows: list[dict[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = defaultdict(int)
    for r in rows:
        crit = r.get("gated_depth3_gate_triggered_criteria")
        if not isinstance(crit, dict):
            continue
        for k, v in crit.items():
            if v:
                out[str(k)] += 1
    return dict(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--per-case-json",
        type=Path,
        default=REPO_ROOT
        / "outputs/hundred_current_full_vs_best_failure_statistics_20260420T220416Z/per_case_failure_statistics.json",
    )
    ap.add_argument("--include-gated-combo", action="store_true")
    args = ap.parse_args()

    now = datetime.now(timezone.utc)
    ts = now.strftime("%Y%m%dT%H%M%SZ")
    out_dir = REPO_ROOT / f"outputs/hundred_conditional_depth3_gate_eval_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    per_case_in = json.loads(Path(args.per_case_json).read_text(encoding="utf-8"))
    baseline_method = TW._resolve_current_full_method()

    manifest: dict[str, Any] = {
        "artifact_family": "hundred_conditional_depth3_gate_eval",
        "created_at_utc": now.isoformat(),
        "output_dir": str(out_dir.relative_to(REPO_ROOT)),
        "source_per_case_json": str(args.per_case_json),
        "baseline_method_name": baseline_method,
        "depth2_method_name": DEPTH2_METHOD,
        "depth3_method_name": DEPTH3_METHOD,
        "gated_depth3_method_name": GATED_METHOD,
        "gated_combo_method_name": GATED_COMBO_METHOD if args.include_gated_combo else None,
        "beam_method_name": BEAM_METHOD,
        "simulator_stream_tags": {"methods_abcd": "fresh_our", "reasoning_beam2": "fresh_best"},
        "conditional_depth3_gate_rule": {
            "combination": "Force depth 3 if (>=2 of criteria A–E) OR (A and B); never force depth 3 if depth-3 lower-bound is infeasible.",
            "criteria": {
                "A": "Weak answer support concentration (top share / gap vs thresholds).",
                "B": "Unresolved root-family ambiguity (active expandable families).",
                "C": "Early collapse risk (family share or consecutive same-family run).",
                "D": "No strong commit evidence (frontier score / top-group support).",
                "E": "Multiple weak answer groups with low top support.",
            },
            "code": "GlobalDiversityAggregationController._evaluate_conditional_depth3_gate",
        },
    }

    rows_out: list[dict[str, Any]] = []
    gate_thresholds_snapshot: dict[str, Any] | None = None
    for rec in per_case_in:
        dataset = str(rec["dataset"])
        example_id = str(rec["example_id"])
        seed = int(rec["surface_row"]["seed"])
        budget = int(rec["surface_row"]["budget"])
        case_id = str(rec.get("case_id") or f"{dataset}::{example_id}")
        gold = str(rec["compact_row"]["gold_answer"])
        found = _lookup_example(dataset, example_id, seed)
        if found is None:
            raise RuntimeError(f"Example not in pilot slice: {dataset} {example_id} seed={seed}")
        question, gold_ex = found
        if str(gold_ex).strip() != str(gold).strip():
            gold = str(gold_ex)

        base_raw = _run_case(baseline_method, dataset, example_id, question, gold, seed, budget, "fresh_our")
        d2_raw = _run_case(DEPTH2_METHOD, dataset, example_id, question, gold, seed, budget, "fresh_our")
        d3_raw = _run_case(DEPTH3_METHOD, dataset, example_id, question, gold, seed, budget, "fresh_our")
        g_raw = _run_case(GATED_METHOD, dataset, example_id, question, gold, seed, budget, "fresh_our")
        if gate_thresholds_snapshot is None:
            gm = g_raw.get("metadata") or {}
            gate_thresholds_snapshot = gm.get("conditional_depth3_gate_thresholds")
        beam_raw = _run_case(BEAM_METHOD, dataset, example_id, question, gold, seed, budget, "fresh_best")
        combo_raw: dict[str, Any] | None = None
        if args.include_gated_combo:
            combo_raw = _run_case(GATED_COMBO_METHOD, dataset, example_id, question, gold, seed, budget, "fresh_our")

        b_ft, _, b_ok, b_tree = _classify_ours(base_raw, gold, dataset)
        d2_ft, _, d2_ok, d2_tree = _classify_ours(d2_raw, gold, dataset)
        d3_ft, _, d3_ok, d3_tree = _classify_ours(d3_raw, gold, dataset)
        g_ft, _, g_ok, g_tree = _classify_ours(g_raw, gold, dataset)
        _, _, beam_ok, _ = _classify_ours(beam_raw, gold, dataset)

        base_rep = TW.choose_repair_answer(
            final_nodes=list(base_raw["final_nodes"]),
            selected_group_hint=(base_raw.get("metadata") or {}).get("selected_group"),
            dataset=dataset,
            enable_rescue=True,
        )
        d2_rep = TW.choose_repair_answer(
            final_nodes=list(d2_raw["final_nodes"]),
            selected_group_hint=(d2_raw.get("metadata") or {}).get("selected_group"),
            dataset=dataset,
            enable_rescue=True,
        )
        d3_rep = TW.choose_repair_answer(
            final_nodes=list(d3_raw["final_nodes"]),
            selected_group_hint=(d3_raw.get("metadata") or {}).get("selected_group"),
            dataset=dataset,
            enable_rescue=True,
        )
        g_rep = TW.choose_repair_answer(
            final_nodes=list(g_raw["final_nodes"]),
            selected_group_hint=(g_raw.get("metadata") or {}).get("selected_group"),
            dataset=dataset,
            enable_rescue=True,
        )
        beam_rep = TW.choose_repair_answer(
            final_nodes=list(beam_raw["final_nodes"]),
            selected_group_hint=(beam_raw.get("metadata") or {}).get("selected_group"),
            dataset=dataset,
            enable_rescue=True,
        )

        same_b = HM._same_family_expansion_severity(
            [e for e in base_raw["events"]], base_raw["final_nodes"], base_raw.get("metadata")
        )
        same_d2 = HM._same_family_expansion_severity(
            [e for e in d2_raw["events"]], d2_raw["final_nodes"], d2_raw.get("metadata")
        )
        same_d3 = HM._same_family_expansion_severity(
            [e for e in d3_raw["events"]], d3_raw["final_nodes"], d3_raw.get("metadata")
        )
        same_g = HM._same_family_expansion_severity(
            [e for e in g_raw["events"]], g_raw["final_nodes"], g_raw.get("metadata")
        )

        cov_d2 = _cov_diag(d2_raw)
        cov_d3 = _cov_diag(d3_raw)
        cov_g = _cov_diag(g_raw)
        gated_extra = _gated_diag(g_raw)

        d2_vs_b = _delta_outcome(b_ok, d2_ok)
        d3_vs_b = _delta_outcome(b_ok, d3_ok)
        g_vs_b = _delta_outcome(b_ok, g_ok)
        d3_vs_d2 = (
            "improved"
            if (d3_ok and not d2_ok)
            else ("worsened" if (not d3_ok and d2_ok) else ("unchanged_correct" if (d3_ok and d2_ok) else "unchanged_still_wrong"))
        )
        g_vs_d2 = (
            "improved"
            if (g_ok and not d2_ok)
            else ("worsened" if (not g_ok and d2_ok) else ("unchanged_correct" if (g_ok and d2_ok) else "unchanged_still_wrong"))
        )
        g_vs_d3 = (
            "improved"
            if (g_ok and not d3_ok)
            else ("worsened" if (not g_ok and d3_ok) else ("unchanged_correct" if (g_ok and d3_ok) else "unchanged_still_wrong"))
        )

        row: dict[str, Any] = {
            "case_id": case_id,
            "dataset": dataset,
            "example_id": example_id,
            "gold_answer": gold,
            "surface_row": {"seed": seed, "budget": budget},
            "baseline_answer": base_rep.get("surfaced_final_answer_raw"),
            "depth2_answer": d2_rep.get("surfaced_final_answer_raw"),
            "depth3_answer": d3_rep.get("surfaced_final_answer_raw"),
            "gated_depth3_answer": g_rep.get("surfaced_final_answer_raw"),
            "reasoning_beam2_answer": beam_rep.get("surfaced_final_answer_raw"),
            "baseline_failure_type": b_ft,
            "depth2_failure_type": d2_ft,
            "depth3_failure_type": d3_ft,
            "gated_depth3_failure_type": g_ft,
            "gold_in_tree_baseline": bool(b_tree),
            "gold_in_tree_depth2": bool(d2_tree),
            "gold_in_tree_depth3": bool(d3_tree),
            "gold_in_tree_gated_depth3": bool(g_tree),
            "repeated_same_family_present_baseline": bool(same_b["repeated_same_family_present"]),
            "repeated_same_family_present_depth2": bool(same_d2["repeated_same_family_present"]),
            "repeated_same_family_present_depth3": bool(same_d3["repeated_same_family_present"]),
            "repeated_same_family_present_gated_depth3": bool(same_g["repeated_same_family_present"]),
            "baseline_actions": int(base_raw["actions"]),
            "baseline_expansions": int(base_raw["expansions"]),
            "baseline_verifications": int(base_raw["verifications"]),
            "depth2_actions": int(d2_raw["actions"]),
            "depth2_expansions": int(d2_raw["expansions"]),
            "depth2_verifications": int(d2_raw["verifications"]),
            "depth3_actions": int(d3_raw["actions"]),
            "depth3_expansions": int(d3_raw["expansions"]),
            "depth3_verifications": int(d3_raw["verifications"]),
            "gated_depth3_actions": int(g_raw["actions"]),
            "gated_depth3_expansions": int(g_raw["expansions"]),
            "gated_depth3_verifications": int(g_raw["verifications"]),
            "outcome_depth2_vs_baseline": d2_vs_b,
            "outcome_depth3_vs_baseline": d3_vs_b,
            "outcome_gated_depth3_vs_baseline": g_vs_b,
            "outcome_depth3_vs_depth2": d3_vs_d2,
            "outcome_gated_depth3_vs_depth2": g_vs_d2,
            "outcome_gated_depth3_vs_depth3": g_vs_d3,
            "depth2_forced_coverage_completed_fully": cov_d2["hard_early_coverage_completed_fully"],
            "depth3_forced_coverage_completed_fully": cov_d3["hard_early_coverage_completed_fully"],
            "gated_depth3_forced_coverage_completed_fully": cov_g["hard_early_coverage_completed_fully"],
            "depth2_impossible_under_budget_release": cov_d2["hard_early_coverage_budget_released_impossible"],
            "depth3_impossible_under_budget_release": cov_d3["hard_early_coverage_budget_released_impossible"],
            "gated_depth3_impossible_under_budget_release": cov_g["hard_early_coverage_budget_released_impossible"],
            "root_families_satisfied_count_final_depth2": _n_families_satisfied(cov_d2),
            "root_families_satisfied_count_final_depth3": _n_families_satisfied(cov_d3),
            "root_families_satisfied_count_final_gated_depth3": _n_families_satisfied(cov_g),
            "gated_depth3_gate_decision": gated_extra["gated_depth3_gate_decision"],
            "gated_depth3_gate_triggered_criteria": gated_extra["gated_depth3_gate_triggered_criteria"],
            "gated_depth3_depth3_forcing_completed": gated_extra["gated_depth3_forcing_completed"],
            "gated_depth3_release_impossible_under_budget": gated_extra["gated_release_impossible_under_budget"],
            "conditional_coverage_phase_final": gated_extra["conditional_coverage_phase_final"],
            "depth2_coverage_diagnostics": cov_d2,
            "depth3_coverage_diagnostics": cov_d3,
            "gated_depth3_coverage_diagnostics": cov_g,
            "beam_correct": bool(beam_ok),
        }
        if combo_raw is not None:
            gc_ft, _, gc_ok, gc_tree = _classify_ours(combo_raw, gold, dataset)
            gc_rep = TW.choose_repair_answer(
                final_nodes=list(combo_raw["final_nodes"]),
                selected_group_hint=(combo_raw.get("metadata") or {}).get("selected_group"),
                dataset=dataset,
                enable_rescue=True,
            )
            row["gated_combo_answer"] = gc_rep.get("surfaced_final_answer_raw")
            row["gated_combo_failure_type"] = gc_ft
            row["gated_combo_correct"] = bool(gc_ok)
            row["gold_in_tree_gated_combo"] = bool(gc_tree)
        rows_out.append(row)

    manifest["conditional_depth3_gate_thresholds_snapshot"] = gate_thresholds_snapshot
    (out_dir / "eval_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    (out_dir / "per_case_comparison.json").write_text(json.dumps(rows_out, indent=2), encoding="utf-8")

    n = len(rows_out)

    def cnt(pred) -> int:
        return sum(1 for r in rows_out if pred(r))

    def ft_counts(key: str) -> dict[str, int]:
        return dict(Counter(str(r[key]) for r in rows_out))

    def outcome_counts(key: str) -> dict[str, int]:
        return dict(Counter(str(r[key]) for r in rows_out))

    agg: dict[str, Any] = {
        "created_at_utc": now.isoformat(),
        "n_cases": n,
        "baseline_method_name": baseline_method,
        "failure_type_counts": {
            "baseline": ft_counts("baseline_failure_type"),
            "depth2": ft_counts("depth2_failure_type"),
            "depth3": ft_counts("depth3_failure_type"),
            "gated_depth3": ft_counts("gated_depth3_failure_type"),
        },
        "absent_from_tree": {
            "baseline_n": cnt(lambda r: r["baseline_failure_type"] == "absent_from_tree"),
            "depth2_n": cnt(lambda r: r["depth2_failure_type"] == "absent_from_tree"),
            "depth3_n": cnt(lambda r: r["depth3_failure_type"] == "absent_from_tree"),
            "gated_n": cnt(lambda r: r["gated_depth3_failure_type"] == "absent_from_tree"),
        },
        "present_not_selected": {
            "baseline_n": cnt(lambda r: r["baseline_failure_type"] == "present_not_selected"),
            "depth2_n": cnt(lambda r: r["depth2_failure_type"] == "present_not_selected"),
            "depth3_n": cnt(lambda r: r["depth3_failure_type"] == "present_not_selected"),
            "gated_n": cnt(lambda r: r["gated_depth3_failure_type"] == "present_not_selected"),
        },
        "repeated_same_family_present": {
            "baseline_n": cnt(lambda r: r["repeated_same_family_present_baseline"]),
            "depth2_n": cnt(lambda r: r["repeated_same_family_present_depth2"]),
            "depth3_n": cnt(lambda r: r["repeated_same_family_present_depth3"]),
            "gated_n": cnt(lambda r: r["repeated_same_family_present_gated_depth3"]),
        },
        "gold_in_tree": {
            "baseline_n": cnt(lambda r: r["gold_in_tree_baseline"]),
            "depth2_n": cnt(lambda r: r["gold_in_tree_depth2"]),
            "depth3_n": cnt(lambda r: r["gold_in_tree_depth3"]),
            "gated_n": cnt(lambda r: r["gold_in_tree_gated_depth3"]),
        },
        "outcomes_vs_baseline": {
            "depth2": outcome_counts("outcome_depth2_vs_baseline"),
            "depth3": outcome_counts("outcome_depth3_vs_baseline"),
            "gated_depth3": outcome_counts("outcome_gated_depth3_vs_baseline"),
        },
        "outcome_depth3_vs_depth2": outcome_counts("outcome_depth3_vs_depth2"),
        "outcome_gated_depth3_vs_depth2": outcome_counts("outcome_gated_depth3_vs_depth2"),
        "outcome_gated_depth3_vs_depth3": outcome_counts("outcome_gated_depth3_vs_depth3"),
        "gated_gate_decision_counts": dict(Counter(str(r["gated_depth3_gate_decision"]) for r in rows_out)),
        "gated_criteria_fired_counts": _criteria_counter(rows_out),
        "gated_depth3_forcing_completed_n": cnt(lambda r: r["gated_depth3_depth3_forcing_completed"]),
        "mean_actions": {
            "baseline": round(sum(r["baseline_actions"] for r in rows_out) / n, 4),
            "depth2": round(sum(r["depth2_actions"] for r in rows_out) / n, 4),
            "depth3": round(sum(r["depth3_actions"] for r in rows_out) / n, 4),
            "gated": round(sum(r["gated_depth3_actions"] for r in rows_out) / n, 4),
        },
        "mean_expansions": {
            "baseline": round(sum(r["baseline_expansions"] for r in rows_out) / n, 4),
            "depth2": round(sum(r["depth2_expansions"] for r in rows_out) / n, 4),
            "depth3": round(sum(r["depth3_expansions"] for r in rows_out) / n, 4),
            "gated": round(sum(r["gated_depth3_expansions"] for r in rows_out) / n, 4),
        },
        "mean_verifications": {
            "baseline": round(sum(r["baseline_verifications"] for r in rows_out) / n, 4),
            "depth2": round(sum(r["depth2_verifications"] for r in rows_out) / n, 4),
            "depth3": round(sum(r["depth3_verifications"] for r in rows_out) / n, 4),
            "gated": round(sum(r["gated_depth3_verifications"] for r in rows_out) / n, 4),
        },
        "depth2_impossible_release_n": cnt(lambda r: r["depth2_impossible_under_budget_release"]),
        "depth3_impossible_release_n": cnt(lambda r: r["depth3_impossible_under_budget_release"]),
        "gated_impossible_release_n": cnt(lambda r: r["gated_depth3_impossible_under_budget_release"]),
        "gated_split_gate_on": {
            "n": cnt(lambda r: r["gated_depth3_gate_decision"] == "gated_on"),
            "mean_actions": round(
                sum(r["gated_depth3_actions"] for r in rows_out if r["gated_depth3_gate_decision"] == "gated_on")
                / max(1, cnt(lambda r: r["gated_depth3_gate_decision"] == "gated_on")),
                4,
            ),
        },
        "gated_split_gate_off": {
            "n": cnt(lambda r: r["gated_depth3_gate_decision"] == "gated_off"),
            "mean_actions": round(
                sum(r["gated_depth3_actions"] for r in rows_out if r["gated_depth3_gate_decision"] == "gated_off")
                / max(1, cnt(lambda r: r["gated_depth3_gate_decision"] == "gated_off")),
                4,
            ),
        },
    }

    by_ds: dict[str, dict[str, dict[str, int]]] = defaultdict(
        lambda: {
            "depth2": {"improved": 0, "worsened": 0, "unchanged_still_wrong": 0},
            "depth3": {"improved": 0, "worsened": 0, "unchanged_still_wrong": 0},
            "gated": {"improved": 0, "worsened": 0, "unchanged_still_wrong": 0},
        }
    )
    for r in rows_out:
        d = str(r["dataset"])
        for label, k in (
            ("depth2", "outcome_depth2_vs_baseline"),
            ("depth3", "outcome_depth3_vs_baseline"),
            ("gated", "outcome_gated_depth3_vs_baseline"),
        ):
            o = str(r[k])
            if o == "improved":
                by_ds[d][label]["improved"] += 1
            elif o == "worsened":
                by_ds[d][label]["worsened"] += 1
            elif o == "unchanged_still_wrong":
                by_ds[d][label]["unchanged_still_wrong"] += 1
    agg["dataset_outcomes_vs_baseline"] = {k: dict(v) for k, v in by_ds.items()}

    def _quad_delta(section: dict[str, int]) -> dict[str, int]:
        b0 = int(section["baseline_n"])
        t2 = int(section["depth2_n"])
        t3 = int(section["depth3_n"])
        tg = int(section["gated_n"])
        return {
            "depth2_minus_baseline": t2 - b0,
            "depth3_minus_baseline": t3 - b0,
            "gated_minus_baseline": tg - b0,
            "gated_minus_depth2": tg - t2,
            "gated_minus_depth3": tg - t3,
        }

    agg["deltas_absent_from_tree"] = _quad_delta(agg["absent_from_tree"])
    agg["deltas_present_not_selected"] = _quad_delta(agg["present_not_selected"])
    agg["deltas_repeated_same_family"] = _quad_delta(agg["repeated_same_family_present"])
    agg["deltas_gold_in_tree"] = _quad_delta(agg["gold_in_tree"])

    (out_dir / "aggregate_summary.json").write_text(json.dumps(agg, indent=2), encoding="utf-8")

    fieldnames = list(rows_out[0].keys()) if rows_out else []
    with (out_dir / "comparison_table.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in rows_out:
            flat = dict(r)
            for k in ("depth2_coverage_diagnostics", "depth3_coverage_diagnostics", "gated_depth3_coverage_diagnostics"):
                if k in flat and isinstance(flat[k], dict):
                    flat[k] = json.dumps(flat[k])
            if isinstance(flat.get("gated_depth3_gate_triggered_criteria"), dict):
                flat["gated_depth3_gate_triggered_criteria"] = json.dumps(flat["gated_depth3_gate_triggered_criteria"])
            w.writerow(flat)

    imp2 = agg["outcomes_vs_baseline"]["depth2"].get("improved", 0)
    wor2 = agg["outcomes_vs_baseline"]["depth2"].get("worsened", 0)
    imp3 = agg["outcomes_vs_baseline"]["depth3"].get("improved", 0)
    wor3 = agg["outcomes_vs_baseline"]["depth3"].get("worsened", 0)
    impg = agg["outcomes_vs_baseline"]["gated_depth3"].get("improved", 0)
    worg = agg["outcomes_vs_baseline"]["gated_depth3"].get("worsened", 0)
    g_vs_d2_imp = agg["outcome_gated_depth3_vs_depth2"].get("improved", 0)
    g_vs_d2_wor = agg["outcome_gated_depth3_vs_depth2"].get("worsened", 0)
    g_vs_d3_imp = agg["outcome_gated_depth3_vs_depth3"].get("improved", 0)
    g_vs_d3_wor = agg["outcome_gated_depth3_vs_depth3"].get("worsened", 0)

    doc = [
        f"# Hundred-case conditional depth-3 gate eval ({ts})",
        "",
        "## Gate definition (exact)",
        "",
        "- **Phase 1:** Balanced root-family coverage to **depth 2** (same mechanism as hard depth-2).",
        "- **Phase 2 (gate):** When depth-2 forcing reaches a terminal state (all satisfied, or impossible under budget, etc.), evaluate criteria **A–E** with thresholds from controller metadata ``conditional_depth3_gate_thresholds``.",
        "- **Combination rule:** Force depth 3 if **(≥2 of A–E)** OR **(A and B)**. If depth-3 lower bound is infeasible, status ``gated_on_but_released_impossible_under_budget``.",
        "- **Within-level ordering:** Unchanged — still the controller ``scored`` priorities and anti-collapse adjustments; hard coverage only **restricts eligible root families**.",
        "",
        "### Threshold snapshot (from first gated run metadata)",
        "",
        f"```json\n{json.dumps(gate_thresholds_snapshot, indent=2)}\n```",
        "",
        "## Insertion point",
        "",
        "``GlobalDiversityAggregationController.run`` immediately after ``_hard_early_root_coverage_forced_diagnostic`` and before ``_apply_hard_early_root_coverage_forced_override``; gate helper: ``_evaluate_conditional_depth3_gate``.",
        "",
        "## RNG alignment",
        "",
        "``fresh_our`` for A–D, ``fresh_best`` for ``reasoning_beam2``.",
        "",
        f"## Output directory: `{out_dir.relative_to(REPO_ROOT)}`",
        "",
        "## Aggregate comparison (baseline / depth-2 / depth-3 / gated)",
        "",
        "| Metric | Baseline | Depth-2 | Depth-3 | Gated |",
        "|--------|----------|---------|---------|-------|",
        f"| absent_from_tree | {agg['absent_from_tree']['baseline_n']} | {agg['absent_from_tree']['depth2_n']} | {agg['absent_from_tree']['depth3_n']} | {agg['absent_from_tree']['gated_n']} |",
        f"| present_not_selected | {agg['present_not_selected']['baseline_n']} | {agg['present_not_selected']['depth2_n']} | {agg['present_not_selected']['depth3_n']} | {agg['present_not_selected']['gated_n']} |",
        f"| repeated_same_family_present | {agg['repeated_same_family_present']['baseline_n']} | {agg['repeated_same_family_present']['depth2_n']} | {agg['repeated_same_family_present']['depth3_n']} | {agg['repeated_same_family_present']['gated_n']} |",
        f"| gold_in_tree | {agg['gold_in_tree']['baseline_n']} | {agg['gold_in_tree']['depth2_n']} | {agg['gold_in_tree']['depth3_n']} | {agg['gold_in_tree']['gated_n']} |",
        f"| mean actions | {agg['mean_actions']['baseline']} | {agg['mean_actions']['depth2']} | {agg['mean_actions']['depth3']} | {agg['mean_actions']['gated']} |",
        "",
        "### vs baseline (correctness)",
        "",
        f"- Depth-2: improved **{imp2}**, worsened **{wor2}**",
        f"- Depth-3: improved **{imp3}**, worsened **{wor3}**",
        f"- Gated: improved **{impg}**, worsened **{worg}**",
        "",
        "### Head-to-head",
        "",
        f"- Gated vs depth-2: improved **{g_vs_d2_imp}**, worsened **{g_vs_d2_wor}**",
        f"- Gated vs depth-3: improved **{g_vs_d3_imp}**, worsened **{g_vs_d3_wor}**",
        "",
        "### Gate",
        "",
        f"- Decision counts: {agg['gated_gate_decision_counts']}",
        f"- Criteria fired (aggregate): {agg['gated_criteria_fired_counts']}",
        f"- Depth-3 forcing completed: **{agg['gated_depth3_forcing_completed_n']}** / {n}",
        f"- release_impossible_under_budget (gated run): **{agg['gated_impossible_release_n']}**",
        "",
        "## Honest conclusion (auto)",
        "",
    ]
    abs_b, abs_2, abs_3, abs_g = (
        int(agg["absent_from_tree"]["baseline_n"]),
        int(agg["absent_from_tree"]["depth2_n"]),
        int(agg["absent_from_tree"]["depth3_n"]),
        int(agg["absent_from_tree"]["gated_n"]),
    )
    if abs_g <= abs_2 and abs_g <= abs_3 and worg <= wor2 + 1 and g_vs_d2_imp >= g_vs_d2_wor:
        verdict = (
            "**Conditional depth-3 looks like a reasonable compromise on this slice** — absent-from-tree is no worse than the better of depth-2/depth-3 "
            "and gated does not clearly multiply regressions vs baseline vs depth-2."
        )
    elif worg > wor3 or abs_g > abs_3:
        verdict = (
            "**Gated depth-3 is not clearly better than full depth-3 here** — consider keeping depth-2 as default or tuning gate thresholds."
        )
    else:
        verdict = (
            "**Mixed** — compare mean actions and gate-on rate; see per-case rows for where the gate preserved depth-3 wins without full depth-3 rigidity."
        )
    doc.append(verdict)

    doc_path = REPO_ROOT / f"docs/HUNDRED_CASE_CONDITIONAL_DEPTH3_GATE_EVAL_{ts}.md"
    doc_path.write_text("\n".join(doc) + "\n", encoding="utf-8")

    print("Wrote:", doc_path.relative_to(REPO_ROOT))
    print("Output dir:", out_dir.relative_to(REPO_ROOT))
    print(
        "absent_from_tree baseline/d2/d3/gated:",
        abs_b,
        abs_2,
        abs_3,
        abs_g,
    )
    print(
        "present_not_selected baseline/d2/d3/gated:",
        agg["present_not_selected"]["baseline_n"],
        agg["present_not_selected"]["depth2_n"],
        agg["present_not_selected"]["depth3_n"],
        agg["present_not_selected"]["gated_n"],
    )
    print(
        "repeated_same_family baseline/d2/d3/gated:",
        agg["repeated_same_family_present"]["baseline_n"],
        agg["repeated_same_family_present"]["depth2_n"],
        agg["repeated_same_family_present"]["depth3_n"],
        agg["repeated_same_family_present"]["gated_n"],
    )
    print(
        "gold_in_tree baseline/d2/d3/gated:",
        agg["gold_in_tree"]["baseline_n"],
        agg["gold_in_tree"]["depth2_n"],
        agg["gold_in_tree"]["depth3_n"],
        agg["gold_in_tree"]["gated_n"],
    )
    print("improved vs baseline d2/d3/gated:", imp2, imp3, impg)
    print("release_impossible_under_budget d2/d3/gated:", agg["depth2_impossible_release_n"], agg["depth3_impossible_release_n"], agg["gated_impossible_release_n"])
    print("gated gate decisions:", agg["gated_gate_decision_counts"])


if __name__ == "__main__":
    main()
