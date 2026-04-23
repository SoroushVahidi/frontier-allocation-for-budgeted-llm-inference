#!/usr/bin/env python3
"""Targeted follow-up: conditional early anti-collapse interventions on manuscript-relevant strict_f3 surface.

Surface contract:
- Source rows: outputs/canonical_full_method_ranking_20260421T212948Z/per_case_outcomes.csv
- Method anchor: strict_f3 runtime controller (depth-3 strict phased)
- Targeted hard slice: anchor failures that are absent-from-tree and repeated-same-family-present

Interventions:
1) strict_f3_conditional_early_risk_cap_k2_v1
2) strict_f3_conditional_early_risk_cap_k2_rival_maturation_v1
"""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
from collections import Counter
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


HM = _load_module(REPO_ROOT / "scripts/build_hundred_current_full_vs_best_failure_statistics.py", "hm_conditional_followup")
TW = HM.TW

SURFACE_CSV = REPO_ROOT / "outputs/canonical_full_method_ranking_20260421T212948Z/per_case_outcomes.csv"
ANCHOR_METHOD = (
    "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_"
    "incumbent_guard_tuned_v1_hard_early_root_depth3_coverage_forced_v1"
)
METHODS: dict[str, str] = {
    "anchor_strict_f3": ANCHOR_METHOD,
    "conditional_early_risk_cap": "strict_f3_conditional_early_risk_cap_k2_v1",
    "conditional_early_risk_cap_rival_maturation": "strict_f3_conditional_early_risk_cap_k2_rival_maturation_v1",
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
    ans = rep.get("surfaced_final_answer_raw")
    ans_can = TW.canonicalize_answer(ans, dataset=dataset)
    gold_can = TW.canonicalize_answer(gold_raw, dataset=dataset)
    correct = bool(ans_can == gold_can and ans_can is not None)
    gold_in_tree = bool(TW._node_ids_with_answer(raw["final_nodes"], gold_can))
    if not gold_in_tree:
        failure = "absent_from_tree"
    else:
        failure = "correct" if correct else "present_not_selected"
    return failure, correct, gold_in_tree


def _same_family_present(raw: dict[str, Any]) -> bool:
    sev = HM._same_family_expansion_severity(
        [e for e in raw.get("events", [])], raw.get("final_nodes", []), raw.get("metadata")
    )
    return bool(sev.get("repeated_same_family_present", False))


def _aggregate(rows: list[dict[str, Any]], key: str, anchor_key: str = "anchor_strict_f3") -> dict[str, Any]:
    improved = worsened = unchanged = 0
    for r in rows:
        base_ok = bool(r[f"{anchor_key}_correct"])
        cur_ok = bool(r[f"{key}_correct"])
        if (not base_ok) and cur_ok:
            improved += 1
        elif base_ok and (not cur_ok):
            worsened += 1
        else:
            unchanged += 1
    n = len(rows)
    return {
        "method": key,
        "n_cases": n,
        "accuracy": float(sum(1 for r in rows if r[f"{key}_correct"]) / max(1, n)),
        "absent_from_tree": int(sum(1 for r in rows if r[f"{key}_failure"] == "absent_from_tree")),
        "present_not_selected": int(sum(1 for r in rows if r[f"{key}_failure"] == "present_not_selected")),
        "repeated_same_family_present": int(sum(1 for r in rows if r[f"{key}_same_family_present"])),
        "gold_in_tree": int(sum(1 for r in rows if r[f"{key}_gold_in_tree"])),
        "avg_actions": float(sum(float(r[f"{key}_actions"]) for r in rows) / max(1, n)),
        "avg_expansions": float(sum(float(r[f"{key}_expansions"]) for r in rows) / max(1, n)),
        "avg_verifications": float(sum(float(r[f"{key}_verifications"]) for r in rows) / max(1, n)),
        "improved_vs_anchor": int(improved),
        "worsened_vs_anchor": int(worsened),
        "unchanged_vs_anchor": int(unchanged),
    }


def main() -> None:
    now = datetime.now(timezone.utc)
    ts = now.strftime("%Y%m%dT%H%M%SZ")
    out_dir = REPO_ROOT / f"outputs/manuscript_slice_conditional_early_intervention_eval_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    surface = pd.read_csv(SURFACE_CSV)
    strict_rows = surface[surface["method"] == "strict_f3"].copy()
    if strict_rows.empty:
        raise RuntimeError("No strict_f3 rows found on canonical ranking surface.")

    case_rows = strict_rows[["dataset", "seed", "budget", "example_id"]].drop_duplicates().sort_values(
        ["dataset", "seed", "budget", "example_id"]
    )

    baseline_slice_df = strict_rows[strict_rows["is_correct"] == 0]
    baseline_slice_df = baseline_slice_df[
        (baseline_slice_df["absent_from_tree"] == 1) & (baseline_slice_df["repeated_same_family_present"] == 1)
    ]
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
            row[f"{key}_method"] = method
            row[f"{key}_correct"] = bool(correct)
            row[f"{key}_failure"] = str(failure)
            row[f"{key}_gold_in_tree"] = bool(gold_in_tree)
            row[f"{key}_same_family_present"] = bool(_same_family_present(raw))
            row[f"{key}_actions"] = int(raw.get("actions", 0))
            row[f"{key}_expansions"] = int(raw.get("expansions", 0))
            row[f"{key}_verifications"] = int(raw.get("verifications", 0))
            m = raw.get("metadata") or {}
            row[f"{key}_hard_cap_blocks"] = int(m.get("hard_max_family_expansions_block_count") or 0)
            row[f"{key}_hard_cap_mode"] = str(m.get("hard_max_family_expansions_relax_mode") or "")
            row[f"{key}_hard_cap_activation_triggers"] = json.dumps(
                m.get("hard_max_family_expansions_activation_by_trigger") or {}, sort_keys=True
            )

        a_ok = bool(row["anchor_strict_f3_correct"])
        for key in METHODS:
            if key == "anchor_strict_f3":
                row[f"{key}_vs_anchor"] = "unchanged"
                continue
            n_ok = bool(row[f"{key}_correct"])
            if (not a_ok) and n_ok:
                row[f"{key}_vs_anchor"] = "improved"
            elif a_ok and (not n_ok):
                row[f"{key}_vs_anchor"] = "worsened"
            else:
                row[f"{key}_vs_anchor"] = "unchanged"

        rows_out.append(row)

    per_case_csv = out_dir / "per_case_results.csv"
    with per_case_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows_out[0].keys()))
        writer.writeheader()
        writer.writerows(rows_out)

    summary_rows = [_aggregate(rows_out, key) for key in METHODS]
    with (out_dir / "aggregate_summary.json").open("w", encoding="utf-8") as f:
        json.dump({"rows": summary_rows}, f, indent=2)

    with (out_dir / "method_summary.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
        writer.writeheader()
        writer.writerows(summary_rows)

    target_rows = [r for r in rows_out if bool(r["is_target_slice"])]
    target_summary = {
        "target_slice_definition": "anchor strict_f3 failures + absent_from_tree + repeated_same_family_present",
        "n_target_cases": len(target_rows),
        "n_surface_cases": len(rows_out),
        "per_method": [_aggregate(target_rows, key) for key in METHODS],
    }
    with (out_dir / "target_slice_summary.json").open("w", encoding="utf-8") as f:
        json.dump(target_summary, f, indent=2)

    trigger_counts: dict[str, dict[str, int]] = {}
    for key in METHODS:
        counter: Counter[str] = Counter()
        for r in rows_out:
            try:
                payload = json.loads(str(r.get(f"{key}_hard_cap_activation_triggers") or "{}"))
            except json.JSONDecodeError:
                payload = {}
            for k, v in dict(payload).items():
                counter[str(k)] += int(v)
        trigger_counts[key] = dict(counter)

    manifest = {
        "artifact_family": "manuscript_slice_conditional_early_intervention_eval",
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
        "target_slice_case_count": int(len(target_rows)),
        "hard_cap_trigger_totals": trigger_counts,
    }
    (out_dir / "eval_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(str(out_dir.relative_to(REPO_ROOT)))


if __name__ == "__main__":
    main()
