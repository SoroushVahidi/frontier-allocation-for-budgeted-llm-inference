#!/usr/bin/env python3
"""Tiny local threshold-sensitivity pass around strict_f3_conditional_early_risk_cap_k2_v1.

Contract:
- Same replay surface as prior targeted pass:
  outputs/canonical_full_method_ranking_20260421T212948Z/per_case_outcomes.csv
- Same targeted slice:
  anchor strict_f3 failures that are absent_from_tree and repeated_same_family_present.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.frontier_matrix_core import load_pilot_examples


def _load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


HM = _load_module(REPO_ROOT / "scripts/build_hundred_current_full_vs_best_failure_statistics.py", "hm_conditional_sensitivity")
TW = HM.TW

SURFACE_CSV = REPO_ROOT / "outputs/canonical_full_method_ranking_20260421T212948Z/per_case_outcomes.csv"
ANCHOR_KEY = "anchor_strict_f3"
BEST_KEY = "conditional_baseline_k2"
METHODS: dict[str, str] = {
    ANCHOR_KEY: "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth3_coverage_forced_v1",
    BEST_KEY: "strict_f3_conditional_early_risk_cap_k2_v1",
    "conditional_window5": "strict_f3_conditional_early_risk_cap_k2_window5_v1",
    "conditional_window7": "strict_f3_conditional_early_risk_cap_k2_window7_v1",
    "conditional_share55": "strict_f3_conditional_early_risk_cap_k2_share55_v1",
    "conditional_share65": "strict_f3_conditional_early_risk_cap_k2_share65_v1",
    "conditional_k3": "strict_f3_conditional_early_risk_cap_k3_v1",
}

VARIANT_NOTES: dict[str, str] = {
    BEST_KEY: "baseline successful setting: early_window=6, risk_share=0.60, risk_run=3, early_cap=2",
    "conditional_window5": "slightly smaller early window (5)",
    "conditional_window7": "slightly larger early window (7)",
    "conditional_share55": "slightly tighter share trigger (0.55)",
    "conditional_share65": "slightly looser share trigger (0.65)",
    "conditional_k3": "nearby cap setting (early cap=3 instead of 2)",
}


def _lookup_question_gold(dataset: str, seed: int, example_id: str, subset_size: int = 20) -> tuple[str, str]:
    for ex in load_pilot_examples(dataset, subset_size, seed):
        if str(ex.example_id) == str(example_id):
            return str(ex.question), str(ex.answer)
    raise RuntimeError(f"Example lookup failed: dataset={dataset} seed={seed} example_id={example_id}")


def _classify(raw: dict[str, Any], gold_raw: str, dataset: str) -> tuple[str, bool, bool]:
    rep = TW.choose_repair_answer(
        final_nodes=list(raw["final_nodes"]),
        selected_group_hint=(raw.get("metadata") or {}).get("selected_group"),
        dataset=dataset,
        enable_rescue=True,
    )
    ans_can = TW.canonicalize_answer(rep.get("surfaced_final_answer_raw"), dataset=dataset)
    gold_can = TW.canonicalize_answer(gold_raw, dataset=dataset)
    correct = bool(ans_can == gold_can and ans_can is not None)
    gold_in_tree = bool(TW._node_ids_with_answer(raw["final_nodes"], gold_can))
    if not gold_in_tree:
        return "absent_from_tree", correct, gold_in_tree
    return ("correct" if correct else "present_not_selected"), correct, gold_in_tree


def _same_family_present(raw: dict[str, Any]) -> bool:
    sev = HM._same_family_expansion_severity(
        [e for e in raw.get("events", [])], raw.get("final_nodes", []), raw.get("metadata")
    )
    return bool(sev.get("repeated_same_family_present", False))


def _h2h_outcome(ref_ok: bool, cur_ok: bool) -> str:
    if (not ref_ok) and cur_ok:
        return "improved"
    if ref_ok and (not cur_ok):
        return "worsened"
    return "unchanged"


def _aggregate(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    n = len(rows)
    acc_n = sum(1 for r in rows if r[f"{key}_correct"])
    absent_n = sum(1 for r in rows if r[f"{key}_failure"] == "absent_from_tree")
    pns_n = sum(1 for r in rows if r[f"{key}_failure"] == "present_not_selected")
    rep_n = sum(1 for r in rows if r[f"{key}_same_family_present"])
    gold_n = sum(1 for r in rows if r[f"{key}_gold_in_tree"])
    out = {
        "method_key": key,
        "method_name": METHODS[key],
        "variant_note": VARIANT_NOTES.get(key, "anchor strict_f3"),
        "n_cases": n,
        "accuracy": float(acc_n / max(1, n)),
        "accuracy_n": int(acc_n),
        "absent_from_tree_n": int(absent_n),
        "absent_from_tree_rate": float(absent_n / max(1, n)),
        "present_not_selected_n": int(pns_n),
        "present_not_selected_rate": float(pns_n / max(1, n)),
        "repeated_same_family_n": int(rep_n),
        "repeated_same_family_rate": float(rep_n / max(1, n)),
        "gold_in_tree_n": int(gold_n),
        "gold_in_tree_rate": float(gold_n / max(1, n)),
        "avg_actions": float(sum(float(r[f"{key}_actions"]) for r in rows) / max(1, n)),
        "avg_expansions": float(sum(float(r[f"{key}_expansions"]) for r in rows) / max(1, n)),
        "avg_verifications": float(sum(float(r[f"{key}_verifications"]) for r in rows) / max(1, n)),
    }

    imp_a = wor_a = unc_a = 0
    imp_b = wor_b = unc_b = 0
    for r in rows:
        out_a = _h2h_outcome(bool(r[f"{ANCHOR_KEY}_correct"]), bool(r[f"{key}_correct"]))
        if out_a == "improved":
            imp_a += 1
        elif out_a == "worsened":
            wor_a += 1
        else:
            unc_a += 1

        out_b = _h2h_outcome(bool(r[f"{BEST_KEY}_correct"]), bool(r[f"{key}_correct"]))
        if out_b == "improved":
            imp_b += 1
        elif out_b == "worsened":
            wor_b += 1
        else:
            unc_b += 1

    out.update(
        {
            "improved_vs_anchor": int(imp_a),
            "worsened_vs_anchor": int(wor_a),
            "unchanged_vs_anchor": int(unc_a),
            "improved_vs_best_conditional": int(imp_b),
            "worsened_vs_best_conditional": int(wor_b),
            "unchanged_vs_best_conditional": int(unc_b),
        }
    )
    return out


def _robustness_judgment(summary_rows: list[dict[str, Any]]) -> tuple[str, list[str]]:
    by_key = {str(r["method_key"]): r for r in summary_rows}
    base = by_key[BEST_KEY]
    candidates = [r for r in summary_rows if r["method_key"] not in (ANCHOR_KEY, BEST_KEY)]
    passing: list[str] = []
    for r in candidates:
        keep_acc = float(r["accuracy"]) >= float(base["accuracy"])
        keep_absent = int(r["absent_from_tree_n"]) <= int(base["absent_from_tree_n"])
        keep_repeat = int(r["repeated_same_family_n"]) <= int(base["repeated_same_family_n"])
        keep_upstream = int(r["gold_in_tree_n"]) >= int(base["gold_in_tree_n"])
        if keep_acc and keep_absent and keep_repeat and keep_upstream:
            passing.append(str(r["method_key"]))

    if len(passing) >= 2:
        return "stable_positive", passing
    if len(passing) == 1:
        return "mixed", passing
    return "fragile_positive", passing


def main() -> None:
    now = datetime.now(timezone.utc)
    ts = now.strftime("%Y%m%dT%H%M%SZ")
    out_dir = REPO_ROOT / f"outputs/manuscript_slice_conditional_early_risk_cap_sensitivity_eval_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    surface = pd.read_csv(SURFACE_CSV)
    strict_rows = surface[surface["method"] == "strict_f3"].copy()
    case_rows = strict_rows[["dataset", "seed", "budget", "example_id"]].drop_duplicates().sort_values(
        ["dataset", "seed", "budget", "example_id"]
    )

    baseline_slice_df = strict_rows[(strict_rows["is_correct"] == 0) & (strict_rows["absent_from_tree"] == 1) & (strict_rows["repeated_same_family_present"] == 1)]
    target_slice_keys = {
        (str(r.dataset), int(r.seed), int(r.budget), str(r.example_id))
        for r in baseline_slice_df.itertuples(index=False)
    }

    rows_out: list[dict[str, Any]] = []
    for rec in case_rows.itertuples(index=False):
        dataset = str(rec.dataset)
        seed = int(rec.seed)
        budget = int(rec.budget)
        example_id = str(rec.example_id)
        question, gold = _lookup_question_gold(dataset, seed, example_id, subset_size=20)

        row: dict[str, Any] = {
            "dataset": dataset,
            "seed": seed,
            "budget": budget,
            "example_id": example_id,
            "is_target_slice": (dataset, seed, budget, example_id) in target_slice_keys,
        }

        for key, method in METHODS.items():
            raw = HM._run_observed_with_events(
                method,
                {
                    "dataset": dataset,
                    "example_id": example_id,
                    "problem_text": question,
                    "ground_truth": gold,
                    "seed": seed,
                    "budget": budget,
                },
                "fresh_our",
            )
            failure, correct, gold_in_tree = _classify(raw, gold, dataset)
            m = raw.get("metadata") or {}
            row[f"{key}_correct"] = bool(correct)
            row[f"{key}_failure"] = str(failure)
            row[f"{key}_gold_in_tree"] = bool(gold_in_tree)
            row[f"{key}_same_family_present"] = bool(_same_family_present(raw))
            row[f"{key}_actions"] = int(raw.get("actions", 0))
            row[f"{key}_expansions"] = int(raw.get("expansions", 0))
            row[f"{key}_verifications"] = int(raw.get("verifications", 0))
            row[f"{key}_hard_cap_mode"] = str(m.get("hard_max_family_expansions_relax_mode") or "")
            row[f"{key}_hard_cap_blocks"] = int(m.get("hard_max_family_expansions_block_count") or 0)

        for key in METHODS:
            row[f"{key}_vs_anchor"] = _h2h_outcome(bool(row[f"{ANCHOR_KEY}_correct"]), bool(row[f"{key}_correct"]))
            row[f"{key}_vs_best_conditional"] = _h2h_outcome(bool(row[f"{BEST_KEY}_correct"]), bool(row[f"{key}_correct"]))
        rows_out.append(row)

    per_case_path = out_dir / "per_case_results.csv"
    with per_case_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows_out[0].keys()))
        writer.writeheader()
        writer.writerows(rows_out)

    summary_rows = [_aggregate(rows_out, key) for key in METHODS]
    summary_rows = sorted(summary_rows, key=lambda r: (str(r["method_key"]) != BEST_KEY, str(r["method_key"])))
    with (out_dir / "method_summary.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
        writer.writeheader()
        writer.writerows(summary_rows)

    target_rows = [r for r in rows_out if bool(r["is_target_slice"])]
    target_summary_rows = [_aggregate(target_rows, key) for key in METHODS]
    target_summary_rows = sorted(target_summary_rows, key=lambda r: (str(r["method_key"]) != BEST_KEY, str(r["method_key"])))
    with (out_dir / "target_slice_method_summary.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(target_summary_rows[0].keys()))
        writer.writeheader()
        writer.writerows(target_summary_rows)

    judgment, passing = _robustness_judgment(summary_rows)
    payload = {
        "target_slice_definition": "anchor strict_f3 failures + absent_from_tree + repeated_same_family_present",
        "n_surface_cases": len(rows_out),
        "n_target_cases": len(target_rows),
        "robustness_judgment": judgment,
        "promotion_gate_passing_variants": passing,
        "surface_summary": summary_rows,
        "target_slice_summary": target_summary_rows,
    }
    (out_dir / "aggregate_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    manifest = {
        "artifact_family": "manuscript_slice_conditional_early_risk_cap_sensitivity_eval",
        "created_at_utc": now.isoformat(),
        "output_dir": str(out_dir.relative_to(REPO_ROOT)),
        "surface_csv": str(SURFACE_CSV.relative_to(REPO_ROOT)),
        "surface_scope": {
            "datasets": sorted({str(x) for x in strict_rows["dataset"].unique().tolist()}),
            "budgets": sorted({int(x) for x in strict_rows["budget"].unique().tolist()}),
            "seeds": sorted({int(x) for x in strict_rows["seed"].unique().tolist()}),
            "cases": int(len(rows_out)),
        },
        "methods": METHODS,
        "variant_notes": VARIANT_NOTES,
        "target_slice_case_count": int(len(target_rows)),
        "robustness_judgment": judgment,
        "promotion_gate_passing_variants": passing,
    }
    (out_dir / "eval_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(str(out_dir.relative_to(REPO_ROOT)))


if __name__ == "__main__":
    main()
