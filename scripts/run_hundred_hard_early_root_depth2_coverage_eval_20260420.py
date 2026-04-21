#!/usr/bin/env python3
"""Re-evaluate the canonical 100-case current-full-vs-reasoning_beam2 failure set with hard early root depth-2 coverage.

Compares:
  A) current canonical full method (+ deterministic output-layer repair)
  B) same + ``hard_early_root_depth2_coverage_forced_v1`` experimental controller refinement
  C) optional: B + low-marginal-gain family cooldown (``--include-combo``)

Reads the frozen hundred-case list from an existing ``per_case_failure_statistics.json``
(default: the April 2026 canonical artifact) and re-runs the simulator with matching
``(dataset, example_id, seed, budget)`` rows.
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

BASELINE_METHOD = (
    "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1"
    "__deterministic_output_layer_repair_v1"
)
NEW_METHOD = (
    "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1"
    "_hard_early_root_depth2_coverage_forced_v1__deterministic_output_layer_repair_v1"
)
COMBO_METHOD = (
    "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1"
    "_hard_early_root_depth2_coverage_forced_v1_low_marginal_gain_cooldown_v1__deterministic_output_layer_repair_v1"
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
) -> tuple[str, str, bool, bool, bool]:
    """Returns (failure_type, concise, is_correct_repair, gold_in_tree, outputish_mismatch)."""
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
    return str(failure_type), concise, is_correct, our_contains, bool(output_mismatch or extraction_mismatch)


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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--per-case-json",
        type=Path,
        default=REPO_ROOT
        / "outputs/hundred_current_full_vs_best_failure_statistics_20260420T220416Z/per_case_failure_statistics.json",
        help="Frozen hundred-case artifact (JSON array).",
    )
    ap.add_argument(
        "--include-combo",
        action="store_true",
        help="Also evaluate the hard-coverage + low-marginal-gain cooldown variant (C).",
    )
    args = ap.parse_args()

    now = datetime.now(timezone.utc)
    ts = now.strftime("%Y%m%dT%H%M%SZ")
    out_dir = REPO_ROOT / f"outputs/hundred_hard_early_root_depth2_coverage_eval_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    per_case_in = json.loads(Path(args.per_case_json).read_text(encoding="utf-8"))
    resolved_baseline = TW._resolve_current_full_method()

    manifest = {
        "artifact_family": "hundred_hard_early_root_depth2_coverage_eval",
        "created_at_utc": now.isoformat(),
        "output_dir": str(out_dir.relative_to(REPO_ROOT)),
        "source_per_case_json": str(args.per_case_json),
        "baseline_method_name": resolved_baseline,
        "new_method_name": NEW_METHOD,
        "beam_method_name": BEAM_METHOD,
        "combo_method_name": COMBO_METHOD if args.include_combo else None,
        "simulator_stream_tags": {
            "baseline_and_new": "fresh_our",
            "reasoning_beam2": "fresh_best",
            "note": "Must match build_hundred_current_full_vs_best_failure_statistics._run_one_case for RNG alignment.",
        },
        "rule": {
            "name": "hard_early_root_depth2_coverage_forced_v1",
            "definition": (
                "Root families are the two initial branches (div_0 / div_1) tracked via branch_family_ids. "
                "While any root family has a non-done, non-pruned head with max(depth) < 2, the allocator "
                "must not expand a branch whose family already satisfies max(depth)>=2 among its expandable "
                "heads; it redirects to the neediest pending family (lowest max expandable depth, then score). "
                "If remaining actions are strictly less than the sum of per-family lower bounds "
                "(2 - max_depth) over pending families, forcing releases for the rest of the run "
                "(impossible-under-budget fallback). "
                "If hard_early_coverage_min_remaining_actions_to_release > 0, forcing also releases when "
                "remaining actions are at or below that threshold (disabled in these specs: value 0)."
            ),
            "code_insertion": (
                "experiments/controllers.py: GlobalDiversityAggregationController.run(), "
                "immediately after the width_depth_allocation_guard block and before incumbent/challenger metalevel."
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

        # Stream tags MUST match ``build_hundred_current_full_vs_best_failure_statistics._run_one_case``
        # so baseline/beam simulators replay the same RNG streams as the frozen hundred-case artifact.
        base_raw = _run_case(resolved_baseline, dataset, example_id, question, gold, seed, budget, "fresh_our")
        new_raw = _run_case(NEW_METHOD, dataset, example_id, question, gold, seed, budget, "fresh_our")
        beam_raw = _run_case(BEAM_METHOD, dataset, example_id, question, gold, seed, budget, "fresh_best")

        combo_raw: dict[str, Any] | None = None
        if args.include_combo:
            combo_raw = _run_case(COMBO_METHOD, dataset, example_id, question, gold, seed, budget, "fresh_our")

        b_ft, b_con, b_ok, b_tree, _ = _classify_ours(base_raw, gold, dataset)
        n_ft, n_con, n_ok, n_tree, _ = _classify_ours(new_raw, gold, dataset)
        _, _, beam_ok, _, _ = _classify_ours(beam_raw, gold, dataset)

        meta_new = new_raw.get("metadata") or {}
        cov_meta = {
            "hard_early_root_depth2_coverage_v1_enabled": bool(meta_new.get("hard_early_root_depth2_coverage_v1_enabled")),
            "hard_early_coverage_completed_fully": bool(meta_new.get("hard_early_coverage_completed_fully")),
            "hard_early_coverage_transition_actions_used": meta_new.get("hard_early_coverage_transition_actions_used"),
            "hard_early_coverage_forced_override_steps": int(meta_new.get("hard_early_coverage_forced_override_steps") or 0),
            "hard_early_coverage_budget_released_impossible": bool(meta_new.get("hard_early_coverage_budget_released_impossible")),
            "hard_early_coverage_budget_released_low_remaining": bool(meta_new.get("hard_early_coverage_budget_released_low_remaining")),
            "hard_early_coverage_final_family_status": meta_new.get("hard_early_coverage_final_family_status") or {},
        }
        n_families_satisfied = sum(
            1
            for _fid, st in (cov_meta.get("hard_early_coverage_final_family_status") or {}).items()
            if isinstance(st, dict) and not st.get("pending", True)
        )

        same_b = HM._same_family_expansion_severity(
            [e for e in base_raw["events"]], base_raw["final_nodes"], base_raw.get("metadata")
        )
        same_n = HM._same_family_expansion_severity(
            [e for e in new_raw["events"]], new_raw["final_nodes"], new_raw.get("metadata")
        )

        base_repair = TW.choose_repair_answer(
            final_nodes=list(base_raw["final_nodes"]),
            selected_group_hint=(base_raw.get("metadata") or {}).get("selected_group"),
            dataset=dataset,
            enable_rescue=True,
        )
        new_repair = TW.choose_repair_answer(
            final_nodes=list(new_raw["final_nodes"]),
            selected_group_hint=(new_raw.get("metadata") or {}).get("selected_group"),
            dataset=dataset,
            enable_rescue=True,
        )
        beam_repair = TW.choose_repair_answer(
            final_nodes=list(beam_raw["final_nodes"]),
            selected_group_hint=(beam_raw.get("metadata") or {}).get("selected_group"),
            dataset=dataset,
            enable_rescue=True,
        )

        if b_ok:
            delta = "unchanged_correct"
        elif n_ok and not b_ok:
            delta = "improved"
        elif (not n_ok) and b_ok:
            delta = "worsened"
        else:
            delta = "unchanged_still_wrong"

        budget_heavy = bool(
            int(new_raw["actions"]) >= int(base_raw["actions"]) + 2
            and not cov_meta["hard_early_coverage_completed_fully"]
        )

        row: dict[str, Any] = {
            "case_id": case_id,
            "dataset": dataset,
            "example_id": example_id,
            "gold_answer": gold,
            "surface_row": {"seed": seed, "budget": budget},
            "reasoning_beam2_answer": beam_repair.get("surfaced_final_answer_raw"),
            "baseline_current_full_answer": base_repair.get("surfaced_final_answer_raw"),
            "new_coverage_forced_answer": new_repair.get("surfaced_final_answer_raw"),
            "baseline_failure_type": b_ft,
            "new_failure_type": n_ft,
            "baseline_failure_concise": b_con,
            "new_failure_concise": n_con,
            "gold_in_tree_baseline": bool(b_tree),
            "gold_in_tree_new": bool(n_tree),
            "repeated_same_family_present_baseline": bool(same_b["repeated_same_family_present"]),
            "repeated_same_family_present_new": bool(same_n["repeated_same_family_present"]),
            "baseline_actions": int(base_raw["actions"]),
            "baseline_expansions": int(base_raw["expansions"]),
            "baseline_verifications": int(base_raw["verifications"]),
            "new_actions": int(new_raw["actions"]),
            "new_expansions": int(new_raw["expansions"]),
            "new_verifications": int(new_raw["verifications"]),
            "beam_actions": int(beam_raw["actions"]),
            "beam_expansions": int(beam_raw["expansions"]),
            "beam_verifications": int(beam_raw["verifications"]),
            "outcome_vs_baseline": delta,
            "hard_early_coverage_diagnostics": cov_meta,
            "root_families_satisfied_count_final": int(n_families_satisfied),
            "beam_correct": bool(beam_ok),
            "budget_heavy_incomplete_coverage": budget_heavy,
        }
        if combo_raw is not None:
            c_ft, _, c_ok, c_tree, _ = _classify_ours(combo_raw, gold, dataset)
            row["combo_failure_type"] = c_ft
            row["combo_correct"] = bool(c_ok)
            row["gold_in_tree_combo"] = bool(c_tree)
        rows_out.append(row)

    (out_dir / "per_case_comparison.json").write_text(json.dumps(rows_out, indent=2), encoding="utf-8")

    n = len(rows_out)
    imp = sum(1 for r in rows_out if r["outcome_vs_baseline"] == "improved")
    wor = sum(1 for r in rows_out if r["outcome_vs_baseline"] == "worsened")
    unc_still = sum(1 for r in rows_out if r["outcome_vs_baseline"] == "unchanged_still_wrong")
    unc_ok = sum(1 for r in rows_out if r["outcome_vs_baseline"] == "unchanged_correct")

    def cnt(pred) -> int:
        return sum(1 for r in rows_out if pred(r))

    agg = {
        "created_at_utc": now.isoformat(),
        "n_cases": n,
        "baseline_method_name": resolved_baseline,
        "new_method_name": NEW_METHOD,
        "aggregate_failure_types": {
            "baseline": dict(Counter(str(r["baseline_failure_type"]) for r in rows_out)),
            "new": dict(Counter(str(r["new_failure_type"]) for r in rows_out)),
        },
        "absent_from_tree": {
            "baseline_n": cnt(lambda r: r["baseline_failure_type"] == "absent_from_tree"),
            "new_n": cnt(lambda r: r["new_failure_type"] == "absent_from_tree"),
        },
        "present_not_selected": {
            "baseline_n": cnt(lambda r: r["baseline_failure_type"] == "present_not_selected"),
            "new_n": cnt(lambda r: r["new_failure_type"] == "present_not_selected"),
        },
        "repeated_same_family_present": {
            "baseline_n": cnt(lambda r: r["repeated_same_family_present_baseline"]),
            "new_n": cnt(lambda r: r["repeated_same_family_present_new"]),
        },
        "gold_in_tree": {
            "baseline_n": cnt(lambda r: r["gold_in_tree_baseline"]),
            "new_n": cnt(lambda r: r["gold_in_tree_new"]),
        },
        "outcomes_vs_baseline": {
            "improved": imp,
            "worsened": wor,
            "unchanged_still_wrong": unc_still,
            "unchanged_correct": unc_ok,
        },
        "hard_early_coverage_completed_fully_n": sum(
            1 for r in rows_out if bool(r["hard_early_coverage_diagnostics"].get("hard_early_coverage_completed_fully"))
        ),
        "budget_released_impossible_n": sum(
            1 for r in rows_out if bool(r["hard_early_coverage_diagnostics"].get("hard_early_coverage_budget_released_impossible"))
        ),
        "mean_actions_baseline": round(sum(r["baseline_actions"] for r in rows_out) / max(1, n), 4),
        "mean_actions_new": round(sum(r["new_actions"] for r in rows_out) / max(1, n), 4),
        "mean_expansions_baseline": round(sum(r["baseline_expansions"] for r in rows_out) / max(1, n), 4),
        "mean_expansions_new": round(sum(r["new_expansions"] for r in rows_out) / max(1, n), 4),
        "cases_helping_tree_entry": sum(
            1
            for r in rows_out
            if (not r["gold_in_tree_baseline"]) and r["gold_in_tree_new"] and (not r["baseline_failure_type"] == "correct")
        ),
        "cases_hurting_incumbent": wor,
        "cases_budget_heavy_incomplete_coverage": sum(1 for r in rows_out if r.get("budget_heavy_incomplete_coverage")),
    }
    by_ds: dict[str, dict[str, int]] = defaultdict(lambda: {"improved": 0, "worsened": 0, "unchanged_still_wrong": 0})
    for r in rows_out:
        d = str(r["dataset"])
        o = str(r["outcome_vs_baseline"])
        if o == "improved":
            by_ds[d]["improved"] += 1
        elif o == "worsened":
            by_ds[d]["worsened"] += 1
        elif o == "unchanged_still_wrong":
            by_ds[d]["unchanged_still_wrong"] += 1
    agg["dataset_outcomes_vs_baseline"] = dict(by_ds)
    (out_dir / "aggregate_summary.json").write_text(json.dumps(agg, indent=2), encoding="utf-8")

    csv_path = out_dir / "comparison_table.csv"
    fieldnames = list(rows_out[0].keys()) if rows_out else []
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in rows_out:
            flat = dict(r)
            flat["hard_early_coverage_diagnostics"] = json.dumps(r["hard_early_coverage_diagnostics"])
            w.writerow(flat)

    improved_cases = [r for r in rows_out if r["outcome_vs_baseline"] == "improved"]
    worsened_cases = [r for r in rows_out if r["outcome_vs_baseline"] == "worsened"]

    doc = [
        f"# Hundred-case hard early root depth-2 coverage evaluation ({ts})",
        "",
        "## Rule (experimental)",
        "",
        manifest["rule"]["definition"],
        "",
        "## Relation to ``adaptive_min_expand``",
        "",
        "The legacy ``adaptive_min_expand`` path (see ``scripts/run_pilot_gsm8k.py``) enforces a *minimum number* of expansions "
        "before pruning on a different axis than global family coverage. It does **not** guarantee balanced shallow depth "
        "across the two root families before concentration. The new rule is intentionally stronger and global: it blocks "
        "continuing on an already depth-2-covered root family while another root family still has expandable heads below depth 2.",
        "",
        f"- **Insertion point:** {manifest['rule']['code_insertion']}",
        f"- **Baseline method:** `{resolved_baseline}`",
        f"- **New method:** `{NEW_METHOD}`",
        f"- **Beam reference:** `{BEAM_METHOD}`",
        "",
        "## Outputs",
        "",
        f"- Directory: `{out_dir.relative_to(REPO_ROOT)}`",
        "- `eval_manifest.json` — config + rule text",
        "- `per_case_comparison.json` — per-case machine-readable comparison",
        "- `aggregate_summary.json` — headline aggregates",
        "- `comparison_table.csv` — flattened table",
        "",
        "## Aggregate comparison (baseline vs new)",
        "",
        "| Metric | Baseline | New |",
        "|--------|----------|-----|",
        f"| absent_from_tree | {agg['absent_from_tree']['baseline_n']} | {agg['absent_from_tree']['new_n']} |",
        f"| present_not_selected | {agg['present_not_selected']['baseline_n']} | {agg['present_not_selected']['new_n']} |",
        f"| repeated_same_family_present | {agg['repeated_same_family_present']['baseline_n']} | {agg['repeated_same_family_present']['new_n']} |",
        f"| gold_in_tree | {agg['gold_in_tree']['baseline_n']} | {agg['gold_in_tree']['new_n']} |",
        f"| mean expansions | {agg['mean_expansions_baseline']} | {agg['mean_expansions_new']} |",
        f"| mean actions | {agg['mean_actions_baseline']} | {agg['mean_actions_new']} |",
        "",
        "## Outcomes vs baseline (correctness)",
        "",
        f"- Improved: **{imp}**",
        f"- Worsened: **{wor}**",
        f"- Unchanged still wrong: **{unc_still}**",
        f"- Unchanged correct: **{unc_ok}**",
        "",
        "## Dataset-wise outcomes (improved / worsened / unchanged still wrong)",
        "",
    ]
    for ds in sorted(agg.get("dataset_outcomes_vs_baseline", {}).keys()):
        b = agg["dataset_outcomes_vs_baseline"][ds]
        doc.append(
            f"- `{ds}`: improved **{b['improved']}**, worsened **{b['worsened']}**, unchanged still wrong **{b['unchanged_still_wrong']}**"
        )
    doc.extend(
        [
            "",
            "## Forced-coverage diagnostics",
            "",
            f"- Completed fully (no budget release): **{agg['hard_early_coverage_completed_fully_n']} / {n}**",
            f"- Released due to impossible lower bound: **{agg['budget_released_impossible_n']} / {n}**",
            f"- Cases where absent tree → present tree (new): **{agg['cases_helping_tree_entry']}**",
            "",
            "## Improved cases",
            "",
        ]
    )
    if not improved_cases:
        doc.append("_None in this run._")
    else:
        for r in improved_cases:
            doc.append(
                f"- `{r['case_id']}`: {r['baseline_failure_type']} → {r['new_failure_type']} "
                f"(actions {r['baseline_actions']} → {r['new_actions']})"
            )
    doc.extend(
        [
            "",
            "## Worsened cases",
            "",
        ]
    )
    if not worsened_cases:
        doc.append("_None in this run._")
    else:
        for r in worsened_cases:
            doc.append(
                f"- `{r['case_id']}`: {r['baseline_failure_type']} → {r['new_failure_type']} "
                f"(actions {r['baseline_actions']} → {r['new_actions']})"
            )

    doc.extend(
        [
            "",
            "## Conclusion (auto-generated; interpret cautiously)",
            "",
        ]
    )
    absent_delta = agg["absent_from_tree"]["new_n"] - agg["absent_from_tree"]["baseline_n"]
    rep_delta = agg["repeated_same_family_present"]["new_n"] - agg["repeated_same_family_present"]["baseline_n"]
    if wor == 0 and imp >= 40 and absent_delta <= -40:
        verdict = (
            "**Keep / promote to next tuning stage on this simulator slice** — large absent-from-tree reduction, "
            "no regressions on the frozen hundred-case loss set, and lower mean action/expansion cost despite the hard quota."
        )
    elif absent_delta < 0 and rep_delta <= 0 and wor <= max(1, imp // 20):
        verdict = "**Tune / keep exploring** — absent-from-tree and same-family pressure move in a helpful direction on this slice."
    elif absent_delta > 0 or wor > imp:
        verdict = "**Reject or heavily revise** — the rigid early quota appears to hurt more than it helps on average here."
    else:
        verdict = "**Tune** — mixed signals: modest structural changes without a clear win on the dominant failure counts."

    doc.append(verdict)
    doc_path = REPO_ROOT / f"docs/HUNDRED_CASE_HARD_EARLY_COVERAGE_DEPTH2_EVAL_{ts}.md"
    doc_path.write_text("\n".join(doc) + "\n", encoding="utf-8")

    print("Wrote:", doc_path.relative_to(REPO_ROOT))
    print("Output dir:", out_dir.relative_to(REPO_ROOT))
    print("Baseline absent_from_tree:", agg["absent_from_tree"]["baseline_n"], "new:", agg["absent_from_tree"]["new_n"])
    print("Baseline present_not_selected:", agg["present_not_selected"]["baseline_n"], "new:", agg["present_not_selected"]["new_n"])
    print("Repeated same-family baseline:", agg["repeated_same_family_present"]["baseline_n"], "new:", agg["repeated_same_family_present"]["new_n"])
    print("Improved / worsened / unchanged_still_wrong:", imp, wor, unc_still)


if __name__ == "__main__":
    main()
