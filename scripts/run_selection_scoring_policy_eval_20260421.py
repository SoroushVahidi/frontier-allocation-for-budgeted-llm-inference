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
from experiments.output_layer_repair import canonicalize_answer, choose_repair_answer

HUNDRED_SUBSET_SIZE = 96
CONTROL_METHOD = (
    "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_"
    "hard_early_root_depth2_then_gate_v1_optimistic_collapse_first_hard_max_family_expansions_cap_k6_v1_fixed_k6_control__deterministic_output_layer_repair_v1"
)
POLICIES = [
    "current_selection_control",
    "answer_group_support_only",
    "answer_group_support_plus_node_score",
    "answer_group_support_plus_calibrated_score",
    "answer_group_support_plus_score_plus_tiebreak_cleanup",
]


def _load(path: Path, mod_name: str) -> Any:
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


HM = _load(REPO_ROOT / "scripts/build_hundred_current_full_vs_best_failure_statistics.py", "hundred_stats_selection_policy")


def _lookup_example(dataset: str, example_id: str, seed: int) -> tuple[str, str] | None:
    for ex in load_pilot_examples(dataset, HUNDRED_SUBSET_SIZE, seed):
        if ex.example_id == example_id:
            return ex.question, ex.answer
    return None


def _node_ids_with_answer(final_nodes: list[dict[str, Any]], gold_can: str | None, dataset: str) -> list[str]:
    if gold_can is None:
        return []
    out = []
    for n in final_nodes:
        pred_can = canonicalize_answer(str(n.get("predicted_answer")) if n.get("predicted_answer") is not None else None, dataset=dataset)
        if pred_can == gold_can:
            out.append(str(n.get("branch_id") or ""))
    return [x for x in out if x]


def _same_family_expansion_severity(events: list[dict[str, Any]], final_nodes: list[dict[str, Any]], metadata: dict[str, Any] | None) -> dict[str, Any]:
    by_id = {str(n.get("branch_id") or ""): n for n in final_nodes}
    fam_seq: list[str] = []
    for e in events:
        if str(e.get("action")) != "expand":
            continue
        bid = str(e.get("branch_id") or "")
        node = by_id.get(bid, {})
        fam = str(node.get("branch_family_id") or bid.split("_child_")[0] or bid or "__unknown__")
        fam_seq.append(fam)
    if not fam_seq:
        return {
            "repeated_same_family_present": False,
            "max_family_share_of_expansions": 0.0,
            "longest_consecutive_same_family_run": 0,
            "num_families_expanded": 0,
        }
    counts = Counter(fam_seq)
    longest = 1
    cur = 1
    for i in range(1, len(fam_seq)):
        if fam_seq[i] == fam_seq[i - 1]:
            cur += 1
            longest = max(longest, cur)
        else:
            cur = 1
    repeated = longest >= 2 or any(v >= 2 for v in counts.values())
    max_share = max(counts.values()) / max(1, len(fam_seq))
    return {
        "repeated_same_family_present": bool(repeated),
        "max_family_share_of_expansions": float(max_share),
        "longest_consecutive_same_family_run": int(longest),
        "num_families_expanded": int(len(counts)),
    }


def _classify(pred_can: str | None, gold_can: str | None, in_tree: bool) -> tuple[str, bool]:
    is_correct = bool(pred_can is not None and gold_can is not None and pred_can == gold_can)
    if not in_tree:
        return "absent_from_tree", is_correct
    if not is_correct:
        return "present_not_selected", is_correct
    return "correct", is_correct


def _gold_group_size(final_nodes: list[dict[str, Any]], gold_can: str | None, dataset: str) -> int:
    if gold_can is None:
        return 0
    cnt = 0
    for n in final_nodes:
        pred_can = canonicalize_answer(str(n.get("predicted_answer")) if n.get("predicted_answer") is not None else None, dataset=dataset)
        if pred_can == gold_can:
            cnt += 1
    return cnt


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--per-case-json",
        type=Path,
        default=REPO_ROOT / "outputs/canonical_hundred_strict_gate1_cap_k6_vs_best_failure_statistics_20260421T160120Z/per_case_failure_statistics.json",
    )
    args = ap.parse_args()

    now = datetime.now(timezone.utc)
    ts = now.strftime("%Y%m%dT%H%M%SZ")
    out_dir = REPO_ROOT / f"outputs/selection_scoring_policy_eval_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    surface = json.loads(args.per_case_json.read_text(encoding="utf-8"))
    per_case: list[dict[str, Any]] = []
    for rec in surface:
        dataset = str(rec["dataset"])
        example_id = str(rec["example_id"])
        seed = int(rec["surface_row"]["seed"])
        budget = int(rec["surface_row"]["budget"])
        qg = _lookup_example(dataset, example_id, seed)
        if qg is None:
            raise RuntimeError(f"missing example {dataset} {example_id} seed={seed}")
        q, gold = qg
        gold_can = canonicalize_answer(gold, dataset=dataset)
        row = {
            "dataset": dataset,
            "example_id": example_id,
            "problem_text": q,
            "ground_truth": gold,
            "seed": seed,
            "budget": budget,
        }
        raw = HM._run_observed_with_events(CONTROL_METHOD, row, "fresh_our")
        final_nodes = list(raw.get("final_nodes") or [])
        metadata = raw.get("metadata") or {}
        selected_hint = metadata.get("selected_group")
        correct_node_ids = _node_ids_with_answer(final_nodes, gold_can, dataset)
        in_tree = bool(correct_node_ids)
        same = _same_family_expansion_severity(list(raw.get("events") or []), final_nodes, metadata)
        gold_group_size = _gold_group_size(final_nodes, gold_can, dataset)

        case = {
            "case_id": str(rec.get("case_id") or f"{dataset}::{example_id}"),
            "dataset": dataset,
            "example_id": example_id,
            "seed": seed,
            "budget": budget,
            "gold_answer": gold,
            "gold_answer_canonical": gold_can,
            "gold_in_tree": in_tree,
            "gold_group_size": int(gold_group_size),
            "gold_group_type": ("multi_branch" if gold_group_size >= 2 else ("singleton" if gold_group_size == 1 else "absent")),
            "control_actions": int(raw.get("actions") or 0),
            "control_expansions": int(raw.get("expansions") or 0),
            "control_verifications": int(raw.get("verifications") or 0),
            "repeated_same_family_present": bool(same["repeated_same_family_present"]),
            "longest_same_family_run": int(same["longest_consecutive_same_family_run"]),
            "max_family_share": float(same["max_family_share_of_expansions"]),
        }

        for policy in POLICIES:
            rep = choose_repair_answer(
                final_nodes=final_nodes,
                selected_group_hint=selected_hint,
                dataset=dataset,
                enable_rescue=True,
                policy_mode=policy,
            )
            pred_raw = rep.get("surfaced_final_answer_raw")
            pred_can = canonicalize_answer(str(pred_raw) if pred_raw is not None else None, dataset=dataset)
            failure_type, is_correct = _classify(pred_can, gold_can, in_tree)
            case[f"{policy}_prediction_raw"] = pred_raw
            case[f"{policy}_prediction_canonical"] = pred_can
            case[f"{policy}_correct"] = bool(is_correct)
            case[f"{policy}_failure_type"] = failure_type
            case[f"{policy}_selected_group"] = rep.get("selected_group_after_policy")
            case[f"{policy}_rescue_applied"] = bool(rep.get("rescue_applied", False))

        control_ok = bool(case["current_selection_control_correct"])
        for policy in POLICIES:
            ok = bool(case[f"{policy}_correct"])
            case[f"{policy}_outcome_vs_control"] = (
                "improved" if (ok and not control_ok) else ("worsened" if ((not ok) and control_ok) else "unchanged")
            )
        per_case.append(case)

    def _aggregate(policy: str) -> dict[str, Any]:
        n = len(per_case)
        gold_in_tree_cases = [r for r in per_case if bool(r["gold_in_tree"])]
        control_present_not_selected = [
            r for r in per_case if str(r["current_selection_control_failure_type"]) == "present_not_selected"
        ]
        recovered = [
            r
            for r in control_present_not_selected
            if bool(r[f"{policy}_correct"]) and not bool(r["current_selection_control_correct"])
        ]
        return {
            "n_cases": n,
            "overall_accuracy": sum(1 for r in per_case if bool(r[f"{policy}_correct"])) / max(1, n),
            "absent_from_tree": sum(1 for r in per_case if str(r[f"{policy}_failure_type"]) == "absent_from_tree"),
            "present_not_selected": sum(1 for r in per_case if str(r[f"{policy}_failure_type"]) == "present_not_selected"),
            "recovered_present_not_selected_cases": len(recovered),
            "accuracy_when_gold_in_tree": (
                sum(1 for r in gold_in_tree_cases if bool(r[f"{policy}_correct"])) / max(1, len(gold_in_tree_cases))
            ),
            "head_to_head_vs_control": dict(Counter(str(r[f"{policy}_outcome_vs_control"]) for r in per_case)),
            "avg_actions": sum(float(r["control_actions"]) for r in per_case) / max(1, n),
            "avg_expansions": sum(float(r["control_expansions"]) for r in per_case) / max(1, n),
            "avg_verifications": sum(float(r["control_verifications"]) for r in per_case) / max(1, n),
        }

    aggregate = {p: _aggregate(p) for p in POLICIES}

    control_pns = [r for r in per_case if str(r["current_selection_control_failure_type"]) == "present_not_selected"]
    pns_summary: dict[str, Any] = {
        "control_present_not_selected_cases": len(control_pns),
        "recovery_by_policy": {},
        "recovery_mechanism_counts": defaultdict(int),
        "gold_group_type_distribution_in_control_present_not_selected": dict(
            Counter(str(r["gold_group_type"]) for r in control_pns)
        ),
    }
    for policy in POLICIES:
        recovered = [
            r
            for r in control_pns
            if bool(r[f"{policy}_correct"]) and not bool(r["current_selection_control_correct"])
        ]
        pns_summary["recovery_by_policy"][policy] = {
            "recovered_count": len(recovered),
            "recovered_rate_over_control_present_not_selected": len(recovered) / max(1, len(control_pns)),
            "recovered_gold_group_type_distribution": dict(Counter(str(r["gold_group_type"]) for r in recovered)),
        }
        if policy == "answer_group_support_only":
            pns_summary["recovery_mechanism_counts"]["support_aggregation"] += len(recovered)
        elif policy == "answer_group_support_plus_node_score":
            pns_summary["recovery_mechanism_counts"]["support_plus_node_score"] += len(recovered)
        elif policy == "answer_group_support_plus_calibrated_score":
            pns_summary["recovery_mechanism_counts"]["calibration_or_normalization"] += len(recovered)
        elif policy == "answer_group_support_plus_score_plus_tiebreak_cleanup":
            pns_summary["recovery_mechanism_counts"]["tiebreak_or_surfacing_cleanup"] += len(recovered)
    pns_summary["recovery_mechanism_counts"] = dict(pns_summary["recovery_mechanism_counts"])

    per_dataset: dict[str, dict[str, Any]] = {}
    for ds in sorted({str(r["dataset"]) for r in per_case}):
        subset = [r for r in per_case if str(r["dataset"]) == ds]
        per_dataset[ds] = {}
        for policy in POLICIES:
            per_dataset[ds][policy] = {
                "accuracy": sum(1 for r in subset if bool(r[f"{policy}_correct"])) / max(1, len(subset)),
                "present_not_selected": sum(1 for r in subset if str(r[f"{policy}_failure_type"]) == "present_not_selected"),
            }

    best_overall = max(POLICIES, key=lambda p: aggregate[p]["overall_accuracy"])
    best_pns = max(POLICIES, key=lambda p: pns_summary["recovery_by_policy"][p]["recovered_count"])
    recommendation = {
        "best_variant_overall": best_overall,
        "best_variant_for_present_not_selected_recovery": best_pns,
        "beats_control_overall": bool(
            aggregate[best_overall]["overall_accuracy"] > aggregate["current_selection_control"]["overall_accuracy"]
        ),
        "beats_control_on_present_not_selected_recovery": bool(
            pns_summary["recovery_by_policy"][best_pns]["recovered_count"] > 0
        ),
        "recommended_policy": (
            best_overall
            if (
                aggregate[best_overall]["overall_accuracy"] > aggregate["current_selection_control"]["overall_accuracy"]
                and pns_summary["recovery_by_policy"][best_overall]["recovered_count"] > 0
            )
            else "current_selection_control"
        ),
    }

    (out_dir / "eval_manifest.json").write_text(
        json.dumps(
            {
                "artifact_family": "selection_scoring_policy_eval",
                "created_at_utc": now.isoformat(),
                "source_per_case_json": str(args.per_case_json),
                "control_method": CONTROL_METHOD,
                "policies": POLICIES,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (out_dir / "per_case_comparison.json").write_text(json.dumps(per_case, indent=2), encoding="utf-8")
    (out_dir / "aggregate_summary.json").write_text(json.dumps(aggregate, indent=2), encoding="utf-8")
    (out_dir / "per_policy_comparison_summary.json").write_text(json.dumps(aggregate, indent=2), encoding="utf-8")
    (out_dir / "head_to_head_vs_control.json").write_text(
        json.dumps({p: aggregate[p]["head_to_head_vs_control"] for p in POLICIES if p != "current_selection_control"}, indent=2),
        encoding="utf-8",
    )
    (out_dir / "present_not_selected_improvement_summary.json").write_text(json.dumps(pns_summary, indent=2), encoding="utf-8")
    (out_dir / "per_dataset_summary.json").write_text(json.dumps(per_dataset, indent=2), encoding="utf-8")
    (out_dir / "recommended_policy.json").write_text(json.dumps(recommendation, indent=2), encoding="utf-8")

    with (out_dir / "comparison_table.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(per_case[0].keys()) if per_case else [])
        writer.writeheader()
        writer.writerows(per_case)

    doc = REPO_ROOT / f"docs/SELECTION_SCORING_POLICY_EVAL_{ts}.md"
    lines = [
        f"# Selection scoring policy eval ({ts})",
        "",
        f"- Output folder: `{out_dir.relative_to(REPO_ROOT)}`",
        f"- Control method: `{CONTROL_METHOD}`",
        "- Surface: canonical hundred strict_gate1_cap_k6-vs-best failure-statistics slice.",
        "- Claims are restricted to this current evaluated repository phase and this selection-layer experiment.",
        "",
        "## Aggregate metrics",
    ]
    for p in POLICIES:
        m = aggregate[p]
        lines.append(
            f"- `{p}`: accuracy={m['overall_accuracy']:.4f}, absent_from_tree={m['absent_from_tree']}, "
            f"present_not_selected={m['present_not_selected']}, recovered_present_not_selected={m['recovered_present_not_selected_cases']}, "
            f"accuracy_when_gold_in_tree={m['accuracy_when_gold_in_tree']:.4f}"
        )
    lines.extend(
        [
            "",
            "## Target failure mode (present_not_selected)",
            f"- Control present_not_selected count: {pns_summary['control_present_not_selected_cases']}",
        ]
    )
    for p in POLICIES:
        rr = pns_summary["recovery_by_policy"][p]
        lines.append(
            f"- `{p}` recovered {rr['recovered_count']} "
            f"({rr['recovered_rate_over_control_present_not_selected']:.3f} of control present_not_selected)"
        )
    lines.extend(
        [
            "",
            "## Best variants",
            f"- Best overall: `{recommendation['best_variant_overall']}`",
            f"- Best for present_not_selected recovery: `{recommendation['best_variant_for_present_not_selected_recovery']}`",
            f"- Recommended policy for this evaluated slice: `{recommendation['recommended_policy']}`",
        ]
    )
    doc.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Wrote", doc.relative_to(REPO_ROOT))
    print("Output", out_dir.relative_to(REPO_ROOT))


if __name__ == "__main__":
    main()
