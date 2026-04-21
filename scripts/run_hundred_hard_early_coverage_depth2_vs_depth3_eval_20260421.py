#!/usr/bin/env python3
"""Three-way eval: baseline vs hard early root depth-2 vs depth-3 on the frozen 100-case loss set.

Replays the same ``(dataset, example_id, seed, budget)`` rows as
``build_hundred_current_full_vs_best_failure_statistics`` using stream tags
``fresh_our`` / ``fresh_best`` for RNG alignment.

Methods:
  A) current canonical full (+ deterministic output-layer repair)
  B) A + ``hard_early_root_depth2_coverage_forced_v1`` (``hard_early_root_coverage_forced_min_depth=2``)
  C) A + ``hard_early_root_depth3_coverage_forced_v1`` (``hard_early_root_coverage_forced_min_depth=3``)

Optional ``--include-combo-depth3``: also run depth-3 + low-marginal-gain cooldown (not in main aggregates).
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

DEPTH2_METHOD = (
    "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1"
    "_hard_early_root_depth2_coverage_forced_v1__deterministic_output_layer_repair_v1"
)
DEPTH3_METHOD = (
    "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1"
    "_hard_early_root_depth3_coverage_forced_v1__deterministic_output_layer_repair_v1"
)
DEPTH3_COMBO_METHOD = (
    "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1"
    "_hard_early_root_depth3_coverage_forced_v1_low_marginal_gain_cooldown_v1__deterministic_output_layer_repair_v1"
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


def _n_families_satisfied(cov: dict[str, Any]) -> int:
    st = cov.get("hard_early_coverage_final_family_status") or {}
    return sum(1 for _k, v in st.items() if isinstance(v, dict) and not v.get("pending", True))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--per-case-json",
        type=Path,
        default=REPO_ROOT
        / "outputs/hundred_current_full_vs_best_failure_statistics_20260420T220416Z/per_case_failure_statistics.json",
    )
    ap.add_argument("--include-combo-depth3", action="store_true")
    args = ap.parse_args()

    now = datetime.now(timezone.utc)
    ts = now.strftime("%Y%m%dT%H%M%SZ")
    out_dir = REPO_ROOT / f"outputs/hundred_hard_early_coverage_depth2_vs_depth3_eval_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    per_case_in = json.loads(Path(args.per_case_json).read_text(encoding="utf-8"))
    baseline_method = TW._resolve_current_full_method()

    manifest: dict[str, Any] = {
        "artifact_family": "hundred_hard_early_coverage_depth2_vs_depth3_eval",
        "created_at_utc": now.isoformat(),
        "output_dir": str(out_dir.relative_to(REPO_ROOT)),
        "source_per_case_json": str(args.per_case_json),
        "baseline_method_name": baseline_method,
        "depth2_method_name": DEPTH2_METHOD,
        "depth3_method_name": DEPTH3_METHOD,
        "beam_method_name": BEAM_METHOD,
        "depth3_combo_method_name": DEPTH3_COMBO_METHOD if args.include_combo_depth3 else None,
        "simulator_stream_tags": {
            "baseline_depth2_depth3": "fresh_our",
            "reasoning_beam2": "fresh_best",
        },
        "rule_depth3": {
            "name": "hard_early_root_depth3_coverage_forced_v1",
            "parameter": "hard_early_root_coverage_forced_min_depth=3",
            "difference_from_depth2": (
                "Same mechanism as depth-2, but each root family must reach max(expandable depth) >= 3 before "
                "another root family that is still below 3 may be ignored for cross-family expansion priority. "
                "Within each pending family, branch choice still follows the normal scored ordering (not fixed BFS)."
            ),
        },
    }
    (out_dir / "eval_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    rows_out: list[dict[str, Any]] = []
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
        beam_raw = _run_case(BEAM_METHOD, dataset, example_id, question, gold, seed, budget, "fresh_best")
        combo_raw: dict[str, Any] | None = None
        if args.include_combo_depth3:
            combo_raw = _run_case(DEPTH3_COMBO_METHOD, dataset, example_id, question, gold, seed, budget, "fresh_our")

        b_ft, _, b_ok, b_tree = _classify_ours(base_raw, gold, dataset)
        d2_ft, _, d2_ok, d2_tree = _classify_ours(d2_raw, gold, dataset)
        d3_ft, _, d3_ok, d3_tree = _classify_ours(d3_raw, gold, dataset)
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

        cov_d2 = _cov_diag(d2_raw)
        cov_d3 = _cov_diag(d3_raw)

        d2_vs_b = _delta_outcome(b_ok, d2_ok)
        d3_vs_b = _delta_outcome(b_ok, d3_ok)
        d3_vs_d2 = "improved" if (d3_ok and not d2_ok) else ("worsened" if (not d3_ok and d2_ok) else ("unchanged_correct" if (d3_ok and d2_ok) else "unchanged_still_wrong"))

        earlier_gold_d2 = bool((not b_tree) and d2_tree)
        earlier_gold_d3 = bool((not b_tree) and d3_tree)
        earlier_gold_d3_vs_d2 = bool((not d2_tree) and d3_tree)

        budget_heavy_d3 = bool(
            int(d3_raw["actions"]) >= int(d2_raw["actions"]) + 2
            and not cov_d3["hard_early_coverage_completed_fully"]
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
            "reasoning_beam2_answer": beam_rep.get("surfaced_final_answer_raw"),
            "baseline_failure_type": b_ft,
            "depth2_failure_type": d2_ft,
            "depth3_failure_type": d3_ft,
            "gold_in_tree_baseline": bool(b_tree),
            "gold_in_tree_depth2": bool(d2_tree),
            "gold_in_tree_depth3": bool(d3_tree),
            "repeated_same_family_present_baseline": bool(same_b["repeated_same_family_present"]),
            "repeated_same_family_present_depth2": bool(same_d2["repeated_same_family_present"]),
            "repeated_same_family_present_depth3": bool(same_d3["repeated_same_family_present"]),
            "baseline_actions": int(base_raw["actions"]),
            "baseline_expansions": int(base_raw["expansions"]),
            "baseline_verifications": int(base_raw["verifications"]),
            "depth2_actions": int(d2_raw["actions"]),
            "depth2_expansions": int(d2_raw["expansions"]),
            "depth2_verifications": int(d2_raw["verifications"]),
            "depth3_actions": int(d3_raw["actions"]),
            "depth3_expansions": int(d3_raw["expansions"]),
            "depth3_verifications": int(d3_raw["verifications"]),
            "outcome_depth2_vs_baseline": d2_vs_b,
            "outcome_depth3_vs_baseline": d3_vs_b,
            "outcome_depth3_vs_depth2": d3_vs_d2,
            "depth2_forced_coverage_completed_fully": cov_d2["hard_early_coverage_completed_fully"],
            "depth3_forced_coverage_completed_fully": cov_d3["hard_early_coverage_completed_fully"],
            "depth2_impossible_under_budget_release": cov_d2["hard_early_coverage_budget_released_impossible"],
            "depth3_impossible_under_budget_release": cov_d3["hard_early_coverage_budget_released_impossible"],
            "root_families_satisfied_count_final_depth2": _n_families_satisfied(cov_d2),
            "root_families_satisfied_count_final_depth3": _n_families_satisfied(cov_d3),
            "depth2_coverage_diagnostics": cov_d2,
            "depth3_coverage_diagnostics": cov_d3,
            "earlier_gold_entry_depth2_vs_baseline": earlier_gold_d2,
            "earlier_gold_entry_depth3_vs_baseline": earlier_gold_d3,
            "earlier_gold_entry_depth3_vs_depth2": earlier_gold_d3_vs_d2,
            "depth3_budget_heavy_incomplete_coverage": budget_heavy_d3,
            "beam_correct": bool(beam_ok),
        }
        if combo_raw is not None:
            c_ft, _, c_ok, c_tree = _classify_ours(combo_raw, gold, dataset)
            row["depth3_combo_failure_type"] = c_ft
            row["depth3_combo_correct"] = bool(c_ok)
            row["gold_in_tree_depth3_combo"] = bool(c_tree)
        rows_out.append(row)

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
        },
        "absent_from_tree": {
            "baseline_n": cnt(lambda r: r["baseline_failure_type"] == "absent_from_tree"),
            "depth2_n": cnt(lambda r: r["depth2_failure_type"] == "absent_from_tree"),
            "depth3_n": cnt(lambda r: r["depth3_failure_type"] == "absent_from_tree"),
        },
        "present_not_selected": {
            "baseline_n": cnt(lambda r: r["baseline_failure_type"] == "present_not_selected"),
            "depth2_n": cnt(lambda r: r["depth2_failure_type"] == "present_not_selected"),
            "depth3_n": cnt(lambda r: r["depth3_failure_type"] == "present_not_selected"),
        },
        "repeated_same_family_present": {
            "baseline_n": cnt(lambda r: r["repeated_same_family_present_baseline"]),
            "depth2_n": cnt(lambda r: r["repeated_same_family_present_depth2"]),
            "depth3_n": cnt(lambda r: r["repeated_same_family_present_depth3"]),
        },
        "gold_in_tree": {
            "baseline_n": cnt(lambda r: r["gold_in_tree_baseline"]),
            "depth2_n": cnt(lambda r: r["gold_in_tree_depth2"]),
            "depth3_n": cnt(lambda r: r["gold_in_tree_depth3"]),
        },
        "outcomes_vs_baseline": {
            "depth2": outcome_counts("outcome_depth2_vs_baseline"),
            "depth3": outcome_counts("outcome_depth3_vs_baseline"),
        },
        "outcome_depth3_vs_depth2": outcome_counts("outcome_depth3_vs_depth2"),
        "mean_actions": {
            "baseline": round(sum(r["baseline_actions"] for r in rows_out) / n, 4),
            "depth2": round(sum(r["depth2_actions"] for r in rows_out) / n, 4),
            "depth3": round(sum(r["depth3_actions"] for r in rows_out) / n, 4),
        },
        "mean_expansions": {
            "baseline": round(sum(r["baseline_expansions"] for r in rows_out) / n, 4),
            "depth2": round(sum(r["depth2_expansions"] for r in rows_out) / n, 4),
            "depth3": round(sum(r["depth3_expansions"] for r in rows_out) / n, 4),
        },
        "mean_verifications": {
            "baseline": round(sum(r["baseline_verifications"] for r in rows_out) / n, 4),
            "depth2": round(sum(r["depth2_verifications"] for r in rows_out) / n, 4),
            "depth3": round(sum(r["depth3_verifications"] for r in rows_out) / n, 4),
        },
        "depth2_forced_coverage_completed_fully_n": cnt(lambda r: r["depth2_forced_coverage_completed_fully"]),
        "depth3_forced_coverage_completed_fully_n": cnt(lambda r: r["depth3_forced_coverage_completed_fully"]),
        "depth2_impossible_release_n": cnt(lambda r: r["depth2_impossible_under_budget_release"]),
        "depth3_impossible_release_n": cnt(lambda r: r["depth3_impossible_under_budget_release"]),
        "cases_depth3_correct_depth2_wrong": cnt(lambda r: r["outcome_depth3_vs_depth2"] == "improved"),
        "cases_depth2_correct_depth3_wrong": cnt(lambda r: r["outcome_depth3_vs_depth2"] == "worsened"),
        "cases_depth3_budget_heavy_incomplete": cnt(lambda r: r["depth3_budget_heavy_incomplete_coverage"]),
        "cases_earlier_gold_depth3_vs_depth2": cnt(lambda r: r["earlier_gold_entry_depth3_vs_depth2"]),
    }

    by_ds: dict[str, dict[str, dict[str, int]]] = defaultdict(
        lambda: {
            "depth2": {"improved": 0, "worsened": 0, "unchanged_still_wrong": 0},
            "depth3": {"improved": 0, "worsened": 0, "unchanged_still_wrong": 0},
        }
    )
    for r in rows_out:
        d = str(r["dataset"])
        for label, k in (("depth2", "outcome_depth2_vs_baseline"), ("depth3", "outcome_depth3_vs_baseline")):
            o = str(r[k])
            if o == "improved":
                by_ds[d][label]["improved"] += 1
            elif o == "worsened":
                by_ds[d][label]["worsened"] += 1
            elif o == "unchanged_still_wrong":
                by_ds[d][label]["unchanged_still_wrong"] += 1
    agg["dataset_outcomes_vs_baseline"] = {k: dict(v) for k, v in by_ds.items()}

    def _triple_delta(section: dict[str, int]) -> dict[str, int]:
        b0, t2, t3 = int(section["baseline_n"]), int(section["depth2_n"]), int(section["depth3_n"])
        return {"depth2_minus_baseline": t2 - b0, "depth3_minus_baseline": t3 - b0, "depth3_minus_depth2": t3 - t2}

    agg["deltas_absent_from_tree"] = _triple_delta(agg["absent_from_tree"])
    agg["deltas_present_not_selected"] = _triple_delta(agg["present_not_selected"])
    agg["deltas_repeated_same_family"] = _triple_delta(agg["repeated_same_family_present"])
    agg["deltas_gold_in_tree"] = _triple_delta(agg["gold_in_tree"])

    (out_dir / "aggregate_summary.json").write_text(json.dumps(agg, indent=2), encoding="utf-8")

    fieldnames = list(rows_out[0].keys()) if rows_out else []
    with (out_dir / "comparison_table.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in rows_out:
            flat = dict(r)
            flat["depth2_coverage_diagnostics"] = json.dumps(r["depth2_coverage_diagnostics"])
            flat["depth3_coverage_diagnostics"] = json.dumps(r["depth3_coverage_diagnostics"])
            w.writerow(flat)

    imp2 = agg["outcomes_vs_baseline"]["depth2"].get("improved", 0)
    wor2 = agg["outcomes_vs_baseline"]["depth2"].get("worsened", 0)
    unc2 = agg["outcomes_vs_baseline"]["depth2"].get("unchanged_still_wrong", 0)
    imp3 = agg["outcomes_vs_baseline"]["depth3"].get("improved", 0)
    wor3 = agg["outcomes_vs_baseline"]["depth3"].get("worsened", 0)
    unc3 = agg["outcomes_vs_baseline"]["depth3"].get("unchanged_still_wrong", 0)
    d3_vs_d2_imp = agg["outcome_depth3_vs_depth2"].get("improved", 0)
    d3_vs_d2_wor = agg["outcome_depth3_vs_depth2"].get("worsened", 0)

    doc = [
        f"# Hundred-case hard early coverage: depth-2 vs depth-3 ({ts})",
        "",
        "## Depth-3 rule",
        "",
        manifest["rule_depth3"]["difference_from_depth2"],
        "",
        "Same-level ordering inside the eligible pending families is still determined by the existing "
        "``scored`` priorities and anti-collapse stack; the hard rule only **filters which root families are eligible** when cross-family imbalance would violate the minimum depth quota.",
        "",
        f"- **Controller parameter:** ``{manifest['rule_depth3']['parameter']}``",
        f"- **Code:** ``GlobalDiversityAggregationController._hard_early_root_coverage_forced_diagnostic`` / "
        "``_apply_hard_early_root_coverage_forced_override`` inserted after the width-depth guard and before metalevel.",
        "",
        "## RNG alignment",
        "",
        "Uses ``fresh_our`` for baseline / depth-2 / depth-3 and ``fresh_best`` for ``reasoning_beam2``, matching the hundred-case builder.",
        "",
        "## Outputs",
        "",
        f"- ``{out_dir.relative_to(REPO_ROOT)}``",
        "",
        "## Aggregate (100 cases)",
        "",
        "| Metric | Baseline | Depth-2 | Depth-3 |",
        "|--------|----------|---------|---------|",
        f"| absent_from_tree | {agg['absent_from_tree']['baseline_n']} | {agg['absent_from_tree']['depth2_n']} | {agg['absent_from_tree']['depth3_n']} |",
        f"| present_not_selected | {agg['present_not_selected']['baseline_n']} | {agg['present_not_selected']['depth2_n']} | {agg['present_not_selected']['depth3_n']} |",
        f"| repeated_same_family_present | {agg['repeated_same_family_present']['baseline_n']} | {agg['repeated_same_family_present']['depth2_n']} | {agg['repeated_same_family_present']['depth3_n']} |",
        f"| gold_in_tree | {agg['gold_in_tree']['baseline_n']} | {agg['gold_in_tree']['depth2_n']} | {agg['gold_in_tree']['depth3_n']} |",
        f"| mean actions | {agg['mean_actions']['baseline']} | {agg['mean_actions']['depth2']} | {agg['mean_actions']['depth3']} |",
        f"| mean expansions | {agg['mean_expansions']['baseline']} | {agg['mean_expansions']['depth2']} | {agg['mean_expansions']['depth3']} |",
        "",
        "### vs baseline (correctness)",
        "",
        f"- Depth-2: improved **{imp2}**, worsened **{wor2}**, unchanged still wrong **{unc2}**",
        f"- Depth-3: improved **{imp3}**, worsened **{wor3}**, unchanged still wrong **{unc3}**",
        "",
        "### Depth-3 vs depth-2 (strict correctness)",
        "",
        f"- Depth-3 correct & depth-2 wrong: **{d3_vs_d2_imp}**",
        f"- Depth-2 correct & depth-3 wrong: **{d3_vs_d2_wor}**",
        f"- Impossible-under-budget release: depth-2 **{agg['depth2_impossible_release_n']}**, depth-3 **{agg['depth3_impossible_release_n']}**",
        f"- Depth-3 budget-heavy incomplete coverage heuristic: **{agg['cases_depth3_budget_heavy_incomplete']}**",
        "",
        "## Dataset-wise (improved / worsened / unchanged still wrong vs baseline)",
        "",
    ]
    for ds in sorted(agg["dataset_outcomes_vs_baseline"].keys()):
        x = agg["dataset_outcomes_vs_baseline"][ds]
        doc.append(
            f"- `{ds}` — depth2: improved {x['depth2']['improved']}, worsened {x['depth2']['worsened']}, "
            f"unchanged still wrong {x['depth2']['unchanged_still_wrong']}; "
            f"depth3: improved {x['depth3']['improved']}, worsened {x['depth3']['worsened']}, "
            f"unchanged still wrong {x['depth3']['unchanged_still_wrong']}"
        )

    imp3_list = [r for r in rows_out if r["outcome_depth3_vs_baseline"] == "improved"]
    wor3_list = [r for r in rows_out if r["outcome_depth3_vs_baseline"] == "worsened"]
    d3_beats_d2 = [r for r in rows_out if r["outcome_depth3_vs_depth2"] == "improved"]
    d2_beats_d3 = [r for r in rows_out if r["outcome_depth3_vs_depth2"] == "worsened"]
    budget_loss = [r for r in rows_out if r["depth3_budget_heavy_incomplete_coverage"]]

    doc.extend(["", "## Depth-3 vs baseline: improved cases", ""])
    if not imp3_list:
        doc.append("_None._")
    else:
        for r in imp3_list[:35]:
            doc.append(
                f"- `{r['case_id']}`: {r['baseline_failure_type']} → {r['depth3_failure_type']} "
                f"(actions {r['baseline_actions']} → {r['depth3_actions']})"
            )
        if len(imp3_list) > 35:
            doc.append(f"- _…and {len(imp3_list) - 35} more._")

    doc.extend(["", "## Depth-3 vs baseline: worsened cases", ""])
    if not wor3_list:
        doc.append("_None._")
    else:
        for r in wor3_list:
            doc.append(
                f"- `{r['case_id']}`: {r['baseline_failure_type']} → {r['depth3_failure_type']} "
                f"(actions {r['baseline_actions']} → {r['depth3_actions']})"
            )

    doc.extend(["", "## Depth-3 vs depth-2 (strict): depth-3 wins", ""])
    if not d3_beats_d2:
        doc.append("_None._")
    else:
        for r in d3_beats_d2:
            doc.append(f"- `{r['case_id']}` (actions d2→d3: {r['depth2_actions']} → {r['depth3_actions']})")

    doc.extend(["", "## Depth-3 vs depth-2 (strict): depth-2 wins", ""])
    if not d2_beats_d3:
        doc.append("_None._")
    else:
        for r in d2_beats_d3:
            doc.append(f"- `{r['case_id']}` (actions d2→d3: {r['depth2_actions']} → {r['depth3_actions']})")

    doc.extend(["", "## Depth-3 budget-heavy incomplete coverage heuristic", ""])
    if not budget_loss:
        doc.append("_None flagged._")
    else:
        for r in budget_loss[:20]:
            doc.append(
                f"- `{r['case_id']}`: actions d2→d3 {r['depth2_actions']} → {r['depth3_actions']}, "
                f"completed_fully={r['depth3_forced_coverage_completed_fully']}"
            )

    doc.extend(
        [
            "",
            "## Conclusion (auto-generated)",
            "",
        ]
    )
    abs2, abs3 = int(agg["absent_from_tree"]["depth2_n"]), int(agg["absent_from_tree"]["depth3_n"])
    rel2, rel3 = int(agg["depth2_impossible_release_n"]), int(agg["depth3_impossible_release_n"])
    if wor3 > wor2 or (abs3 > abs2 and imp3 < imp2):
        verdict = (
            "**Depth-3 is not clearly worth it vs depth-2 on this slice** — headline failure counts regress vs depth-2 "
            "and/or depth-3 introduces more regressions vs baseline."
        )
    elif (
        wor3 == 0
        and imp3 >= imp2
        and abs3 <= abs2
        and d3_vs_d2_imp > d3_vs_d2_wor
        and rel3 <= rel2 + 25
    ):
        verdict = (
            "**Depth-3 modestly improves on depth-2 here** — vs baseline, depth-3 fixes at least as many cases as depth-2 "
            "and further reduces `absent_from_tree`; strict depth-3 vs depth-2 correctness favors depth-3. Tradeoff: "
            "more `release_impossible_under_budget` events when the quota is tight, so monitor real budgets carefully."
        )
    elif d3_vs_d2_imp > d3_vs_d2_wor and abs3 <= abs2:
        verdict = (
            "**Depth-3 is mixed but slightly favorable vs depth-2** — strict head-to-head wins vs depth-2 outweigh losses, "
            "and absent-from-tree does not regress vs the depth-2 intervention."
        )
    else:
        verdict = (
            "**Depth-3 is broadly comparable to depth-2 with a rigidity / release-rate tradeoff** — keep depth-2 as the "
            "default experimental hard coverage unless follow-up work shows depth-3 wins on a targeted subset."
        )
    doc.append(verdict)
    if args.include_combo_depth3:
        doc.append("")
        doc.append("_(Depth-3 + low-marginal-gain combo was run per ``--include-combo-depth3``; see per-row optional columns.)_")

    doc_path = REPO_ROOT / f"docs/HUNDRED_CASE_HARD_EARLY_COVERAGE_DEPTH3_EVAL_{ts}.md"
    doc_path.write_text("\n".join(doc) + "\n", encoding="utf-8")

    print("Wrote:", doc_path.relative_to(REPO_ROOT))
    print("Output dir:", out_dir.relative_to(REPO_ROOT))
    print(
        "absent_from_tree baseline/d2/d3:",
        agg["absent_from_tree"]["baseline_n"],
        agg["absent_from_tree"]["depth2_n"],
        agg["absent_from_tree"]["depth3_n"],
    )
    print(
        "present_not_selected baseline/d2/d3:",
        agg["present_not_selected"]["baseline_n"],
        agg["present_not_selected"]["depth2_n"],
        agg["present_not_selected"]["depth3_n"],
    )
    print(
        "repeated_same_family baseline/d2/d3:",
        agg["repeated_same_family_present"]["baseline_n"],
        agg["repeated_same_family_present"]["depth2_n"],
        agg["repeated_same_family_present"]["depth3_n"],
    )
    print(
        "gold_in_tree baseline/d2/d3:",
        agg["gold_in_tree"]["baseline_n"],
        agg["gold_in_tree"]["depth2_n"],
        agg["gold_in_tree"]["depth3_n"],
    )
    print("improved vs baseline d2/d3:", imp2, imp3)
    print("depth3 vs depth2 strict improved/worsened:", d3_vs_d2_imp, d3_vs_d2_wor)


if __name__ == "__main__":
    main()
