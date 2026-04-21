#!/usr/bin/env python3
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
BASE = "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_then_gate_v1_optimistic_collapse_first_hard_max_family_expansions_cap_k6_v1"
VARIANTS = {
    "fixed_k6_control": f"{BASE}_fixed_k6_control__deterministic_output_layer_repair_v1",
    "relax_on_cross_family_coverage_complete": f"{BASE}_relax_on_cross_family_coverage_complete__deterministic_output_layer_repair_v1",
    "relax_on_low_marginal_gain_absence_false": f"{BASE}_relax_on_low_marginal_gain_absence_false__deterministic_output_layer_repair_v1",
    "relax_on_multi_family_maturity": f"{BASE}_relax_on_multi_family_maturity__deterministic_output_layer_repair_v1",
    "relax_on_high_confidence_incumbent_but_no_challenger_gap": f"{BASE}_relax_on_high_confidence_incumbent_but_no_challenger_gap__deterministic_output_layer_repair_v1",
}


def _load(path: Path, mod_name: str) -> Any:
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


HM = _load(REPO_ROOT / "scripts/build_hundred_current_full_vs_best_failure_statistics.py", "hundred_stats")
TW = _load(REPO_ROOT / "scripts/build_twenty_exact_current_full_vs_best_fresh.py", "twenty_exact")


def _lookup_example(dataset: str, example_id: str, seed: int) -> tuple[str, str] | None:
    for ex in load_pilot_examples(dataset, HUNDRED_SUBSET_SIZE, seed):
        if ex.example_id == example_id:
            return ex.question, ex.answer
    return None


def _classify(raw: dict[str, Any], gold: str, dataset: str) -> tuple[str, bool]:
    rep = TW.choose_repair_answer(
        final_nodes=list(raw["final_nodes"]),
        selected_group_hint=(raw.get("metadata") or {}).get("selected_group"),
        dataset=dataset,
        enable_rescue=True,
    )
    pred = rep.get("surfaced_final_answer_raw")
    pred_can = TW.canonicalize_answer(pred, dataset=dataset)
    gold_can = TW.canonicalize_answer(gold, dataset=dataset)
    is_correct = bool(pred_can == gold_can and pred_can is not None)
    correct_ids = TW._node_ids_with_answer(raw["final_nodes"], gold_can)
    in_tree = bool(correct_ids)
    if not in_tree:
        return "absent_from_tree", is_correct
    if not is_correct:
        return "present_not_selected", is_correct
    return "correct", is_correct


def _run_case(method: str, dataset: str, example_id: str, q: str, gold: str, seed: int, budget: int) -> dict[str, Any]:
    row = {"dataset": dataset, "example_id": example_id, "problem_text": q, "ground_truth": gold, "seed": seed, "budget": budget}
    return HM._run_observed_with_events(method, row, "fresh_our")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--per-case-json",
        type=Path,
        default=REPO_ROOT / "outputs/hundred_current_full_vs_best_failure_statistics_20260420T220416Z/per_case_failure_statistics.json",
    )
    args = ap.parse_args()
    now = datetime.now(timezone.utc)
    ts = now.strftime("%Y%m%dT%H%M%SZ")
    out_dir = REPO_ROOT / f"outputs/conditional_k_relaxation_eval_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    surface = json.loads(args.per_case_json.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for rec in surface:
        dataset = str(rec["dataset"])
        example_id = str(rec["example_id"])
        seed = int(rec["surface_row"]["seed"])
        budget = int(rec["surface_row"]["budget"])
        gold = str(rec["compact_row"]["gold_answer"])
        qg = _lookup_example(dataset, example_id, seed)
        if qg is None:
            raise RuntimeError(f"missing example {dataset} {example_id} seed={seed}")
        q, gold_ex = qg
        if str(gold_ex).strip() != str(gold).strip():
            gold = str(gold_ex)
        case = {"case_id": str(rec.get("case_id") or f"{dataset}::{example_id}"), "dataset": dataset, "example_id": example_id, "seed": seed, "budget": budget}
        control_ok = False
        for label, method in VARIANTS.items():
            raw = _run_case(method, dataset, example_id, q, gold, seed, budget)
            ft, ok = _classify(raw, gold, dataset)
            if label == "fixed_k6_control":
                control_ok = ok
            same = HM._same_family_expansion_severity(raw["events"], raw["final_nodes"], raw.get("metadata"))
            meta = raw.get("metadata") or {}
            act = int(meta.get("hard_max_family_expansions_relax_activation_count", 0))
            case.update(
                {
                    f"{label}_failure_type": ft,
                    f"{label}_correct": bool(ok),
                    f"{label}_actions": int(raw["actions"]),
                    f"{label}_expansions": int(raw["expansions"]),
                    f"{label}_verifications": int(raw["verifications"]),
                    f"{label}_repeated_same_family_present": bool(same["repeated_same_family_present"]),
                    f"{label}_longest_same_family_run": int(same["longest_consecutive_same_family_run"]),
                    f"{label}_max_family_share": float(same["max_family_share_of_expansions"] or 0.0),
                    f"{label}_relax_activation_count": act,
                    f"{label}_relax_activation_rate": float(meta.get("hard_max_family_expansions_relax_activation_rate", 0.0)),
                    f"{label}_relax_mean_delta": float(meta.get("hard_max_family_expansions_mean_relax_delta_on_activation", 0.0)),
                    f"{label}_relax_activation_by_trigger": meta.get("hard_max_family_expansions_activation_by_trigger") or {},
                }
            )
        for label in VARIANTS:
            ok = bool(case[f"{label}_correct"])
            case[f"{label}_outcome_vs_control"] = "improved" if (ok and not control_ok) else ("worsened" if ((not ok) and control_ok) else "unchanged")
        rows.append(case)

    def _metric_for(label: str) -> dict[str, Any]:
        n = len(rows)
        return {
            "n": n,
            "accuracy": sum(1 for r in rows if r[f"{label}_correct"]) / max(1, n),
            "absent_from_tree": sum(1 for r in rows if r[f"{label}_failure_type"] == "absent_from_tree"),
            "present_not_selected": sum(1 for r in rows if r[f"{label}_failure_type"] == "present_not_selected"),
            "repeated_same_family_present": sum(1 for r in rows if r[f"{label}_repeated_same_family_present"]),
            "longest_same_family_run_mean": sum(float(r[f"{label}_longest_same_family_run"]) for r in rows) / max(1, n),
            "max_family_share_mean": sum(float(r[f"{label}_max_family_share"]) for r in rows) / max(1, n),
            "avg_actions": sum(float(r[f"{label}_actions"]) for r in rows) / max(1, n),
            "avg_expansions": sum(float(r[f"{label}_expansions"]) for r in rows) / max(1, n),
            "avg_verifications": sum(float(r[f"{label}_verifications"]) for r in rows) / max(1, n),
            "relax_activation_count": sum(int(r[f"{label}_relax_activation_count"]) for r in rows),
            "relax_activation_case_rate": sum(1 for r in rows if int(r[f"{label}_relax_activation_count"]) > 0) / max(1, n),
            "accuracy_when_activated": (
                sum(1 for r in rows if int(r[f"{label}_relax_activation_count"]) > 0 and r[f"{label}_correct"])
                / max(1, sum(1 for r in rows if int(r[f"{label}_relax_activation_count"]) > 0))
            ),
            "accuracy_when_not_activated": (
                sum(1 for r in rows if int(r[f"{label}_relax_activation_count"]) == 0 and r[f"{label}_correct"])
                / max(1, sum(1 for r in rows if int(r[f"{label}_relax_activation_count"]) == 0))
            ),
        }

    aggregate = {label: _metric_for(label) for label in VARIANTS}
    h2h = {
        label: dict(Counter(str(r[f"{label}_outcome_vs_control"]) for r in rows))
        for label in VARIANTS
        if label != "fixed_k6_control"
    }
    per_budget: dict[str, dict[str, Any]] = {}
    for b in sorted({int(r["budget"]) for r in rows}):
        sub = [r for r in rows if int(r["budget"]) == b]
        per_budget[str(b)] = {label: sum(1 for r in sub if r[f"{label}_correct"]) / max(1, len(sub)) for label in VARIANTS}
    per_dataset: dict[str, dict[str, Any]] = {}
    for ds in sorted({str(r["dataset"]) for r in rows}):
        sub = [r for r in rows if str(r["dataset"]) == ds]
        per_dataset[ds] = {label: sum(1 for r in sub if r[f"{label}_correct"]) / max(1, len(sub)) for label in VARIANTS}
    activation_summary: dict[str, Any] = {}
    for label in VARIANTS:
        trig = Counter()
        for r in rows:
            for k, v in (r.get(f"{label}_relax_activation_by_trigger") or {}).items():
                trig[str(k)] += int(v)
        activation_summary[label] = {"trigger_counts": dict(trig), "activated_cases": sum(1 for r in rows if int(r[f"{label}_relax_activation_count"]) > 0)}

    best_label = max(VARIANTS.keys(), key=lambda k: aggregate[k]["accuracy"])
    best_non_control = max((k for k in VARIANTS if k != "fixed_k6_control"), key=lambda k: aggregate[k]["accuracy"])
    rec = {
        "winner_overall": best_label,
        "best_non_control_variant": best_non_control,
        "best_non_control_beats_fixed_k6": bool(aggregate[best_non_control]["accuracy"] > aggregate["fixed_k6_control"]["accuracy"]),
        "recommendation": (
            "keep_fixed_k6_control"
            if aggregate[best_non_control]["accuracy"] <= aggregate["fixed_k6_control"]["accuracy"]
            else "promote_best_conditional_variant"
        ),
    }

    (out_dir / "eval_manifest.json").write_text(
        json.dumps(
            {
                "artifact_family": "conditional_k_relaxation_eval",
                "created_at_utc": now.isoformat(),
                "source_per_case_json": str(args.per_case_json),
                "variants": VARIANTS,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (out_dir / "per_case_comparison.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    (out_dir / "aggregate_summary.json").write_text(json.dumps(aggregate, indent=2), encoding="utf-8")
    (out_dir / "head_to_head_vs_fixed_k6.json").write_text(json.dumps(h2h, indent=2), encoding="utf-8")
    (out_dir / "per_budget_summary.json").write_text(json.dumps(per_budget, indent=2), encoding="utf-8")
    (out_dir / "per_dataset_summary.json").write_text(json.dumps(per_dataset, indent=2), encoding="utf-8")
    (out_dir / "relaxation_activation_summary.json").write_text(json.dumps(activation_summary, indent=2), encoding="utf-8")
    (out_dir / "recommended_policy.json").write_text(json.dumps(rec, indent=2), encoding="utf-8")

    with (out_dir / "comparison_table.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        writer.writeheader()
        writer.writerows(rows)

    doc = REPO_ROOT / f"docs/CONDITIONAL_K_RELAXATION_EVAL_{ts}.md"
    lines = [
        f"# Conditional K relaxation eval ({ts})",
        "",
        f"- Output folder: `{out_dir.relative_to(REPO_ROOT)}`",
        "- Surface: matched hundred-case canonical failure-statistics rows (mixed budgets, mixed datasets).",
        "",
        "## Aggregate accuracy",
    ]
    for label in VARIANTS:
        lines.append(f"- `{label}`: {aggregate[label]['accuracy']:.4f}")
    lines.extend(
        [
            "",
            "## Head-to-head vs fixed_k6_control",
            *(f"- `{k}`: {v}" for k, v in h2h.items()),
            "",
            "## Interpretation",
            f"- Overall winner: `{rec['winner_overall']}`.",
            f"- Best non-control beats fixed K=6: `{rec['best_non_control_beats_fixed_k6']}`.",
            "- Claims apply only to this evaluated surface and current strict-phased repo state.",
        ]
    )
    doc.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Wrote", doc.relative_to(REPO_ROOT))
    print("Output", out_dir.relative_to(REPO_ROOT))


if __name__ == "__main__":
    main()
