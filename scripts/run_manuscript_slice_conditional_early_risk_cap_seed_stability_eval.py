#!/usr/bin/env python3
"""Seed-stability confirmation for strict_f3_conditional_early_risk_cap_k2_v1.

Contract:
- Same manuscript-relevant replay surface contract as prior conditional-risk runs
  (datasets/budgets/subset size), while widening only seed coverage.
- Same targeted hard slice definition from anchor strict_f3:
  anchor failure + absent_from_tree + repeated_same_family_present.
"""

from __future__ import annotations

import argparse
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


HM = _load_module(
    REPO_ROOT / "scripts/build_hundred_current_full_vs_best_failure_statistics.py",
    "hm_conditional_seed_stability",
)
TW = HM.TW

SURFACE_CSV = REPO_ROOT / "outputs/canonical_full_method_ranking_20260421T212948Z/per_case_outcomes.csv"
SUBSET_SIZE = 20
ANCHOR_KEY = "anchor_strict_f3"
CANDIDATE_KEY = "conditional_baseline_k2"
METHODS: dict[str, str] = {
    ANCHOR_KEY: "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth3_coverage_forced_v1",
    CANDIDATE_KEY: "strict_f3_conditional_early_risk_cap_k2_v1",
}
DEFAULT_EXTRA_SEEDS = [37, 41]


def _seed_example_rows(dataset: str, seed: int, budgets: list[int], subset_size: int = SUBSET_SIZE) -> list[dict[str, Any]]:
    examples = load_pilot_examples(dataset, subset_size, seed)
    rows: list[dict[str, Any]] = []
    for ex in examples:
        for budget in budgets:
            rows.append(
                {
                    "dataset": str(dataset),
                    "seed": int(seed),
                    "budget": int(budget),
                    "example_id": str(ex.example_id),
                    "problem_text": str(ex.question),
                    "ground_truth": str(ex.answer),
                }
            )
    return rows


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


def _h2h_outcome(anchor_ok: bool, cur_ok: bool) -> str:
    if (not anchor_ok) and cur_ok:
        return "improved"
    if anchor_ok and (not cur_ok):
        return "worsened"
    return "unchanged"


def _aggregate(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    n = len(rows)
    acc_n = sum(1 for r in rows if r[f"{key}_correct"])
    absent_n = sum(1 for r in rows if r[f"{key}_failure"] == "absent_from_tree")
    pns_n = sum(1 for r in rows if r[f"{key}_failure"] == "present_not_selected")
    rep_n = sum(1 for r in rows if r[f"{key}_same_family_present"])
    gold_n = sum(1 for r in rows if r[f"{key}_gold_in_tree"])

    improved = worsened = unchanged = 0
    for r in rows:
        out = _h2h_outcome(bool(r[f"{ANCHOR_KEY}_correct"]), bool(r[f"{key}_correct"]))
        if out == "improved":
            improved += 1
        elif out == "worsened":
            worsened += 1
        else:
            unchanged += 1

    return {
        "method_key": key,
        "method_name": METHODS[key],
        "n_cases": int(n),
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
        "improved_vs_anchor": int(improved),
        "worsened_vs_anchor": int(worsened),
        "unchanged_vs_anchor": int(unchanged),
    }


def _stability_judgment(surface_summary: list[dict[str, Any]], target_summary: list[dict[str, Any]]) -> str:
    by_surface = {str(r["method_key"]): r for r in surface_summary}
    by_target = {str(r["method_key"]): r for r in target_summary}
    anchor_s = by_surface[ANCHOR_KEY]
    cand_s = by_surface[CANDIDATE_KEY]
    anchor_t = by_target[ANCHOR_KEY]
    cand_t = by_target[CANDIDATE_KEY]

    keep_acc = float(cand_s["accuracy"]) >= float(anchor_s["accuracy"])
    keep_absent = int(cand_s["absent_from_tree_n"]) <= int(anchor_s["absent_from_tree_n"])
    keep_repeat = int(cand_s["repeated_same_family_n"]) <= int(anchor_s["repeated_same_family_n"])
    keep_upstream = int(cand_s["gold_in_tree_n"]) >= int(anchor_s["gold_in_tree_n"])

    target_supportive = (
        float(cand_t["accuracy"]) >= float(anchor_t["accuracy"])
        and int(cand_t["absent_from_tree_n"]) <= int(anchor_t["absent_from_tree_n"])
        and int(cand_t["repeated_same_family_n"]) <= int(anchor_t["repeated_same_family_n"])
    )

    if keep_acc and keep_absent and keep_repeat and keep_upstream and target_supportive:
        return "stable_positive"
    if keep_acc and (keep_absent or keep_repeat):
        return "mixed"
    if keep_acc:
        return "fragile_positive"
    return "negative_not_confirmed"


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--extra-seeds",
        type=str,
        default=",".join(str(s) for s in DEFAULT_EXTRA_SEEDS),
        help="Comma-separated additional seeds appended to base seeds from canonical surface.",
    )
    p.add_argument(
        "--timestamp",
        type=str,
        default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        help="UTC timestamp token for output folder naming.",
    )
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    extra_seeds = [int(x.strip()) for x in args.extra_seeds.split(",") if x.strip()]

    out_dir = REPO_ROOT / f"outputs/manuscript_slice_conditional_early_risk_cap_seed_stability_eval_{args.timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    surface = pd.read_csv(SURFACE_CSV)
    strict_rows = surface[surface["method"] == "strict_f3"].copy()
    datasets = sorted({str(x) for x in strict_rows["dataset"].unique().tolist()})
    budgets = sorted({int(x) for x in strict_rows["budget"].unique().tolist()})
    base_seeds = sorted({int(x) for x in strict_rows["seed"].unique().tolist()})

    seeds = sorted({*base_seeds, *extra_seeds})

    rows_out: list[dict[str, Any]] = []
    for dataset in datasets:
        for seed in seeds:
            for case in _seed_example_rows(dataset, seed, budgets=budgets, subset_size=SUBSET_SIZE):
                row: dict[str, Any] = {
                    "dataset": str(case["dataset"]),
                    "seed": int(case["seed"]),
                    "budget": int(case["budget"]),
                    "example_id": str(case["example_id"]),
                    "is_target_slice": False,
                }

                for key, method in METHODS.items():
                    raw = HM._run_observed_with_events(
                        method,
                        {
                            "dataset": str(case["dataset"]),
                            "example_id": str(case["example_id"]),
                            "problem_text": str(case["problem_text"]),
                            "ground_truth": str(case["ground_truth"]),
                            "seed": int(case["seed"]),
                            "budget": int(case["budget"]),
                        },
                        "fresh_our",
                    )
                    failure, correct, gold_in_tree = _classify(raw, str(case["ground_truth"]), str(case["dataset"]))
                    row[f"{key}_correct"] = bool(correct)
                    row[f"{key}_failure"] = str(failure)
                    row[f"{key}_gold_in_tree"] = bool(gold_in_tree)
                    row[f"{key}_same_family_present"] = bool(_same_family_present(raw))
                    row[f"{key}_actions"] = int(raw.get("actions", 0))
                    row[f"{key}_expansions"] = int(raw.get("expansions", 0))
                    row[f"{key}_verifications"] = int(raw.get("verifications", 0))

                row["is_target_slice"] = (
                    (not bool(row[f"{ANCHOR_KEY}_correct"]))
                    and str(row[f"{ANCHOR_KEY}_failure"]) == "absent_from_tree"
                    and bool(row[f"{ANCHOR_KEY}_same_family_present"])
                )
                for key in METHODS:
                    row[f"{key}_vs_anchor"] = _h2h_outcome(bool(row[f"{ANCHOR_KEY}_correct"]), bool(row[f"{key}_correct"]))

                rows_out.append(row)

    per_case_path = out_dir / "per_case_results.csv"
    with per_case_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows_out[0].keys()))
        writer.writeheader()
        writer.writerows(rows_out)

    surface_summary = [_aggregate(rows_out, key) for key in METHODS]
    with (out_dir / "method_summary.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(surface_summary[0].keys()))
        writer.writeheader()
        writer.writerows(surface_summary)

    target_rows = [r for r in rows_out if bool(r["is_target_slice"])]
    target_summary = [_aggregate(target_rows, key) for key in METHODS]
    with (out_dir / "target_slice_method_summary.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(target_summary[0].keys()))
        writer.writeheader()
        writer.writerows(target_summary)

    per_seed_rows: list[dict[str, Any]] = []
    for seed in seeds:
        seed_rows = [r for r in rows_out if int(r["seed"]) == int(seed)]
        seed_target_rows = [r for r in seed_rows if bool(r["is_target_slice"])]
        for key in METHODS:
            full = _aggregate(seed_rows, key)
            full.update({"seed": int(seed), "slice": "full_surface"})
            per_seed_rows.append(full)
            tgt = _aggregate(seed_target_rows, key)
            tgt.update({"seed": int(seed), "slice": "target_hard_slice"})
            per_seed_rows.append(tgt)

    with (out_dir / "per_seed_summary.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(per_seed_rows[0].keys()))
        writer.writeheader()
        writer.writerows(per_seed_rows)

    judgment = _stability_judgment(surface_summary, target_summary)
    aggregate_payload = {
        "seed_contract": {
            "base_seeds_from_surface": base_seeds,
            "extra_confirmation_seeds": extra_seeds,
            "all_seeds_evaluated": seeds,
        },
        "target_slice_definition": "anchor strict_f3 failure + absent_from_tree + repeated_same_family_present",
        "n_surface_cases": len(rows_out),
        "n_target_cases": len(target_rows),
        "stability_judgment": judgment,
        "surface_summary": surface_summary,
        "target_slice_summary": target_summary,
    }
    (out_dir / "aggregate_summary.json").write_text(json.dumps(aggregate_payload, indent=2), encoding="utf-8")

    manifest = {
        "artifact_family": "manuscript_slice_conditional_early_risk_cap_seed_stability_eval",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "output_dir": str(out_dir.relative_to(REPO_ROOT)),
        "surface_csv": str(SURFACE_CSV.relative_to(REPO_ROOT)),
        "surface_contract": {
            "datasets": datasets,
            "budgets": budgets,
            "subset_size_per_seed": SUBSET_SIZE,
            "base_seeds": base_seeds,
            "extra_confirmation_seeds": extra_seeds,
            "all_seeds_evaluated": seeds,
        },
        "methods": METHODS,
        "target_slice_case_count": int(len(target_rows)),
        "stability_judgment": judgment,
        "files": {
            "per_case_results": "per_case_results.csv",
            "method_summary": "method_summary.csv",
            "target_slice_method_summary": "target_slice_method_summary.csv",
            "per_seed_summary": "per_seed_summary.csv",
            "aggregate_summary": "aggregate_summary.json",
        },
    }
    (out_dir / "eval_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(str(out_dir.relative_to(REPO_ROOT)))


if __name__ == "__main__":
    main()
