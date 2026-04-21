#!/usr/bin/env python3
"""Six-way strict-phased eval on frozen 100-case current-full-vs-reasoning_beam2 failures.

Compares:
A) baseline current canonical full
B) strict phased forced F2
C) strict phased forced F3
D) strict phased Gate Design 1
E) strict phased Gate Design 2
F) strict phased Gate Design 3
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
GATE1_METHOD = f"{BASE_SUFFIX}_hard_early_root_depth2_then_gate_v1_optimistic_collapse_first__deterministic_output_layer_repair_v1"
GATE2_METHOD = f"{BASE_SUFFIX}_hard_early_root_depth2_then_gate_v2_budget_aware_rescue__deterministic_output_layer_repair_v1"
GATE3_METHOD = f"{BASE_SUFFIX}_hard_early_root_depth2_then_gate_v3_ambiguity_after_depth2__deterministic_output_layer_repair_v1"
BEAM_METHOD = "reasoning_beam2"


def _load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


HM = _load_module(REPO_ROOT / "scripts/build_hundred_current_full_vs_best_failure_statistics.py", "hundred_stats")
TW = _load_module(REPO_ROOT / "scripts/build_twenty_exact_current_full_vs_best_fresh.py", "twenty_exact_bundle")


def _lookup_example(dataset: str, example_id: str, seed: int) -> tuple[str, str] | None:
    for ex in load_pilot_examples(dataset, HUNDRED_SUBSET_SIZE, seed):
        if ex.example_id == example_id:
            return ex.question, ex.answer
    return None


def _classify_ours(our_raw: dict[str, Any], gold_raw: str, dataset: str) -> tuple[str, bool, bool, str]:
    rep = TW.choose_repair_answer(
        final_nodes=list(our_raw["final_nodes"]),
        selected_group_hint=(our_raw.get("metadata") or {}).get("selected_group"),
        dataset=dataset,
        enable_rescue=True,
    )
    our_answer = rep.get("surfaced_final_answer_raw")
    our_can = TW.canonicalize_answer(our_answer, dataset=dataset)
    gold_can = TW.canonicalize_answer(gold_raw, dataset=dataset)
    is_correct = bool(our_can == gold_can and our_can is not None)
    contains = bool(TW._node_ids_with_answer(our_raw["final_nodes"], gold_can))
    output_mismatch = bool(
        contains
        and (rep.get("chosen_final_node_answer_canonical") == gold_can)
        and (our_can != gold_can)
    )
    extraction_mismatch = bool(
        (rep.get("chosen_final_node_answer_canonical") != rep.get("extracted_final_answer_canonical"))
        or (rep.get("extracted_final_answer_canonical") != rep.get("surfaced_final_answer_canonical"))
        or (rep.get("chosen_final_node_answer_raw") != rep.get("chosen_final_node_answer_canonical"))
    )
    if not contains:
        concise = "absent_from_tree"
    elif output_mismatch or extraction_mismatch:
        concise = "output_layer_mismatch"
    else:
        concise = "present_not_selected" if not is_correct else "correct"
    ft = HM._map_failure_type(concise) if concise != "correct" else "correct"
    return str(ft), is_correct, contains, str(our_answer)


def _delta(base_ok: bool, new_ok: bool) -> str:
    if base_ok:
        return "unchanged_correct" if new_ok else "worsened"
    if new_ok:
        return "improved"
    return "unchanged_still_wrong"


def _same_family(raw: dict[str, Any]) -> bool:
    m = raw.get("metadata") or {}
    return bool(float(m.get("repeated_same_family_expansion_rate", 0.0)) > 0.0)


def _gate_diag(raw: dict[str, Any], prefix: str) -> dict[str, Any]:
    m = raw.get("metadata") or {}
    gr = m.get("conditional_depth3_gate_record") or {}
    return {
        f"{prefix}_gate_decision": str(gr.get("depth3_release_status") or ""),
        f"{prefix}_gate_triggered_criteria": gr.get("criteria_fired") if isinstance(gr, dict) else {},
        f"{prefix}_depth3_forcing_happened": bool(m.get("conditional_depth3_forcing_completed")),
        f"{prefix}_release_impossible_under_budget": bool(m.get("hard_early_coverage_budget_released_impossible")),
        f"{prefix}_run_ended_before_full_gate_resolution": str(gr.get("depth3_release_status") or "").endswith(
            "run_ended_before_depth3_forcing"
        )
        or str(gr.get("depth3_release_status") or "") == "skipped_run_ended_before_depth2_terminal",
    }


def _phase_trace(raw: dict[str, Any]) -> dict[str, Any]:
    m = raw.get("metadata") or {}
    phase_log = list(m.get("hard_early_coverage_phase_transition_log") or [])
    release_phase = None
    for ev in reversed(phase_log):
        if str(ev.get("reason") or "").startswith("release_"):
            release_phase = str(ev.get("from_phase") or ev.get("to_phase") or "")
            break
    return {
        "phase_trace_summary": [str(ev.get("to_phase") or "") for ev in phase_log],
        "release_impossible_under_budget": bool(m.get("hard_early_coverage_budget_released_impossible")),
        "release_phase": release_phase,
    }


def _criteria_counts(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    out: dict[str, int] = defaultdict(int)
    for r in rows:
        crit = r.get(field)
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
    args = ap.parse_args()

    now = datetime.now(timezone.utc)
    ts = now.strftime("%Y%m%dT%H%M%SZ")
    out_dir = REPO_ROOT / f"outputs/hundred_three_gate_design_eval_strict_phased_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    baseline_method = TW._resolve_current_full_method()
    methods = {
        "baseline": baseline_method,
        "strict_f2": DEPTH2_METHOD,
        "strict_f3": DEPTH3_METHOD,
        "strict_gate1": GATE1_METHOD,
        "strict_gate2": GATE2_METHOD,
        "strict_gate3": GATE3_METHOD,
    }

    per_case_in = json.loads(Path(args.per_case_json).read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    gate_thresholds_snapshot: dict[str, Any] = {}

    for rec in per_case_in:
        dataset = str(rec["dataset"])
        example_id = str(rec["example_id"])
        seed = int(rec["surface_row"]["seed"])
        budget = int(rec["surface_row"]["budget"])
        gold = str(rec["compact_row"]["gold_answer"])
        found = _lookup_example(dataset, example_id, seed)
        if found is None:
            raise RuntimeError(f"example not found: {dataset} {example_id}")
        question, gold_ex = found
        if gold_ex.strip() != gold.strip():
            gold = str(gold_ex)

        raw_runs: dict[str, Any] = {}
        cls: dict[str, Any] = {}
        for key, method_name in methods.items():
            raw = HM._run_observed_with_events(
                method_name,
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
            raw_runs[key] = raw
            ft, ok, contains, answer = _classify_ours(raw, gold, dataset)
            cls[key] = {"failure_type": ft, "correct": ok, "gold_in_tree": contains, "answer": answer}

        beam_raw = HM._run_observed_with_events(BEAM_METHOD, {
            "dataset": dataset,
            "example_id": example_id,
            "problem_text": question,
            "ground_truth": gold,
            "seed": seed,
            "budget": budget,
        }, "fresh_best")
        beam_rep = TW.choose_repair_answer(final_nodes=list(beam_raw["final_nodes"]), selected_group_hint=(beam_raw.get("metadata") or {}).get("selected_group"), dataset=dataset, enable_rescue=True)

        if not gate_thresholds_snapshot:
            gate_thresholds_snapshot = {
                "strict_gate1": (raw_runs["strict_gate1"].get("metadata") or {}).get("conditional_depth3_gate_thresholds"),
                "strict_gate2": (raw_runs["strict_gate2"].get("metadata") or {}).get("conditional_depth3_gate_thresholds"),
                "strict_gate3": (raw_runs["strict_gate3"].get("metadata") or {}).get("conditional_depth3_gate_thresholds"),
            }

        row = {
            "dataset": dataset,
            "example_id": example_id,
            "gold_answer": gold,
            "reasoning_beam2_answer": beam_rep.get("surfaced_final_answer_raw"),
            **{f"{k}_answer": cls[k]["answer"] for k in methods},
            **{f"{k}_failure_type": cls[k]["failure_type"] for k in methods},
            **{f"gold_in_tree_{k}": cls[k]["gold_in_tree"] for k in methods},
            **{f"repeated_same_family_present_{k}": _same_family(raw_runs[k]) for k in methods},
            **{f"{k}_actions": int(raw_runs[k]["actions"]) for k in methods},
            **{f"{k}_expansions": int(raw_runs[k]["expansions"]) for k in methods},
            **{f"{k}_verifications": int(raw_runs[k]["verifications"]) for k in methods},
            "strict_f2_release_impossible_under_budget": bool(
                (raw_runs["strict_f2"].get("metadata") or {}).get("hard_early_coverage_budget_released_impossible")
            ),
            "strict_f3_release_impossible_under_budget": bool(
                (raw_runs["strict_f3"].get("metadata") or {}).get("hard_early_coverage_budget_released_impossible")
            ),
            "outcome_strict_f2_vs_baseline": _delta(cls["baseline"]["correct"], cls["strict_f2"]["correct"]),
            "outcome_strict_f3_vs_baseline": _delta(cls["baseline"]["correct"], cls["strict_f3"]["correct"]),
            "outcome_strict_gate1_vs_baseline": _delta(cls["baseline"]["correct"], cls["strict_gate1"]["correct"]),
            "outcome_strict_gate2_vs_baseline": _delta(cls["baseline"]["correct"], cls["strict_gate2"]["correct"]),
            "outcome_strict_gate3_vs_baseline": _delta(cls["baseline"]["correct"], cls["strict_gate3"]["correct"]),
            "outcome_strict_f3_vs_strict_f2": _delta(cls["strict_f2"]["correct"], cls["strict_f3"]["correct"]),
            "outcome_strict_gate1_vs_strict_f2": _delta(cls["strict_f2"]["correct"], cls["strict_gate1"]["correct"]),
            "outcome_strict_gate1_vs_strict_f3": _delta(cls["strict_f3"]["correct"], cls["strict_gate1"]["correct"]),
            "outcome_strict_gate2_vs_strict_f2": _delta(cls["strict_f2"]["correct"], cls["strict_gate2"]["correct"]),
            "outcome_strict_gate2_vs_strict_f3": _delta(cls["strict_f3"]["correct"], cls["strict_gate2"]["correct"]),
            "outcome_strict_gate3_vs_strict_f2": _delta(cls["strict_f2"]["correct"], cls["strict_gate3"]["correct"]),
            "outcome_strict_gate3_vs_strict_f3": _delta(cls["strict_f3"]["correct"], cls["strict_gate3"]["correct"]),
            "outcome_strict_gate1_vs_strict_gate2": _delta(cls["strict_gate2"]["correct"], cls["strict_gate1"]["correct"]),
            "outcome_strict_gate1_vs_strict_gate3": _delta(cls["strict_gate3"]["correct"], cls["strict_gate1"]["correct"]),
            "outcome_strict_gate2_vs_strict_gate3": _delta(cls["strict_gate3"]["correct"], cls["strict_gate2"]["correct"]),
        }
        for k in ("strict_f2", "strict_f3", "strict_gate1", "strict_gate2", "strict_gate3"):
            p = _phase_trace(raw_runs[k])
            row[f"{k}_phase_trace_summary"] = p["phase_trace_summary"]
            row[f"{k}_release_impossible_under_budget"] = p["release_impossible_under_budget"]
            row[f"{k}_release_phase"] = p["release_phase"]
        row.update(_gate_diag(raw_runs["strict_gate1"], "strict_gate1"))
        row.update(_gate_diag(raw_runs["strict_gate2"], "strict_gate2"))
        row.update(_gate_diag(raw_runs["strict_gate3"], "strict_gate3"))
        rows.append(row)

    def cnt(fn: Any) -> int:
        return int(sum(1 for r in rows if fn(r)))

    def ocount(key: str) -> dict[str, int]:
        return dict(Counter(str(r.get(key, "")) for r in rows))

    by_dataset: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in rows:
        d = str(r["dataset"])
        by_dataset[d]["n"] += 1
        for m in ("baseline", "strict_f2", "strict_f3", "strict_gate1", "strict_gate2", "strict_gate3"):
            if r[f"{m}_failure_type"] == "absent_from_tree":
                by_dataset[d][f"absent_from_tree_{m}"] += 1
            if r[f"gold_in_tree_{m}"]:
                by_dataset[d][f"gold_in_tree_{m}"] += 1

    aggregate = {
        "n_cases": len(rows),
        "methods": methods,
        "thresholds": gate_thresholds_snapshot,
        "absent_from_tree": {m: cnt(lambda r, mm=m: r[f"{mm}_failure_type"] == "absent_from_tree") for m in methods},
        "present_not_selected": {m: cnt(lambda r, mm=m: r[f"{mm}_failure_type"] == "present_not_selected") for m in methods},
        "repeated_same_family_present": {m: cnt(lambda r, mm=m: r[f"repeated_same_family_present_{mm}"]) for m in methods},
        "gold_in_tree": {m: cnt(lambda r, mm=m: r[f"gold_in_tree_{mm}"]) for m in methods},
        "release_impossible_under_budget": {
            "baseline": cnt(lambda r: False),
            "strict_f2": cnt(lambda r: r["strict_f2_release_impossible_under_budget"]),
            "strict_f3": cnt(lambda r: r["strict_f3_release_impossible_under_budget"]),
            "strict_gate1": cnt(lambda r: r["strict_gate1_release_impossible_under_budget"]),
            "strict_gate2": cnt(lambda r: r["strict_gate2_release_impossible_under_budget"]),
            "strict_gate3": cnt(lambda r: r["strict_gate3_release_impossible_under_budget"]),
        },
        "outcomes_vs_baseline": {m: ocount(f"outcome_{m}_vs_baseline") for m in ("strict_f2", "strict_f3", "strict_gate1", "strict_gate2", "strict_gate3")},
        "head_to_head": {
            "strict_f3_vs_strict_f2": ocount("outcome_strict_f3_vs_strict_f2"),
            "strict_gate1_vs_strict_f2": ocount("outcome_strict_gate1_vs_strict_f2"),
            "strict_gate1_vs_strict_f3": ocount("outcome_strict_gate1_vs_strict_f3"),
            "strict_gate2_vs_strict_f2": ocount("outcome_strict_gate2_vs_strict_f2"),
            "strict_gate2_vs_strict_f3": ocount("outcome_strict_gate2_vs_strict_f3"),
            "strict_gate3_vs_strict_f2": ocount("outcome_strict_gate3_vs_strict_f2"),
            "strict_gate3_vs_strict_f3": ocount("outcome_strict_gate3_vs_strict_f3"),
            "strict_gate1_vs_strict_gate2": ocount("outcome_strict_gate1_vs_strict_gate2"),
            "strict_gate1_vs_strict_gate3": ocount("outcome_strict_gate1_vs_strict_gate3"),
            "strict_gate2_vs_strict_gate3": ocount("outcome_strict_gate2_vs_strict_gate3"),
        },
        "gate_decisions": {
            "strict_gate1": ocount("strict_gate1_gate_decision"),
            "strict_gate2": ocount("strict_gate2_gate_decision"),
            "strict_gate3": ocount("strict_gate3_gate_decision"),
        },
        "gate_forces_depth3": {
            "strict_gate1": cnt(lambda r: r["strict_gate1_depth3_forcing_happened"]),
            "strict_gate2": cnt(lambda r: r["strict_gate2_depth3_forcing_happened"]),
            "strict_gate3": cnt(lambda r: r["strict_gate3_depth3_forcing_happened"]),
        },
        "gate_stops_after_depth2": {
            "strict_gate1": cnt(lambda r: (not r["strict_gate1_depth3_forcing_happened"])),
            "strict_gate2": cnt(lambda r: (not r["strict_gate2_depth3_forcing_happened"])),
            "strict_gate3": cnt(lambda r: (not r["strict_gate3_depth3_forcing_happened"])),
        },
        "gate_criteria_fired_counts": {
            "strict_gate1": _criteria_counts(rows, "strict_gate1_gate_triggered_criteria"),
            "strict_gate2": _criteria_counts(rows, "strict_gate2_gate_triggered_criteria"),
            "strict_gate3": _criteria_counts(rows, "strict_gate3_gate_triggered_criteria"),
        },
        "dataset_breakdown": {k: dict(v) for k, v in by_dataset.items()},
        "cases_gate_retains_depth3_gains_with_lower_budget_stress": [
            {"dataset": r["dataset"], "example_id": r["example_id"]}
            for r in rows
            if r["outcome_strict_f3_vs_baseline"] == "improved"
            and any(r[f"outcome_{g}_vs_baseline"] == "improved" and r[f"{g}_actions"] <= r["strict_f3_actions"] for g in ("strict_gate1", "strict_gate2", "strict_gate3"))
        ],
        "cases_clearly_wrong_gate_decisions": [
            {
                "dataset": r["dataset"],
                "example_id": r["example_id"],
                "strict_gate1": r["outcome_strict_gate1_vs_strict_f3"],
                "strict_gate2": r["outcome_strict_gate2_vs_strict_f3"],
                "strict_gate3": r["outcome_strict_gate3_vs_strict_f3"],
            }
            for r in rows
            if any(r[f"outcome_{g}_vs_strict_f3"] == "worsened" for g in ("strict_gate1", "strict_gate2", "strict_gate3"))
        ],
    }

    manifest = {
        "artifact_family": "hundred_three_gate_design_eval_strict_phased",
        "created_at_utc": now.isoformat(),
        "output_dir": str(out_dir.relative_to(REPO_ROOT)),
        "source_per_case_json": str(args.per_case_json),
        "methods": methods,
        "beam_method": BEAM_METHOD,
        "gate_designs": {
            "gate1": "v1_optimistic_collapse_first",
            "gate2": "v2_budget_aware_rescue",
            "gate3": "v3_ambiguity_after_depth2",
        },
        "invariant": "same-level ordering remains controller-driven by scores/anti-collapse tie-breaks (no rigid BFS)",
        "gate_thresholds_snapshot": gate_thresholds_snapshot,
    }

    (out_dir / "eval_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (out_dir / "per_case_comparison.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    (out_dir / "aggregate_summary.json").write_text(json.dumps(aggregate, indent=2), encoding="utf-8")

    with (out_dir / "comparison_table.csv").open("w", newline="", encoding="utf-8") as f:
        if rows:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            for r in rows:
                rr = dict(r)
                for k in list(rr.keys()):
                    if isinstance(rr[k], (dict, list)):
                        rr[k] = json.dumps(rr[k], sort_keys=True)
                writer.writerow(rr)

    report = REPO_ROOT / f"docs/HUNDRED_THREE_GATE_DESIGN_COMPARISON_STRICT_PHASED_{ts}.md"
    table_lines = [
        "| Metric | baseline | strict_f2 | strict_f3 | strict_gate1 | strict_gate2 | strict_gate3 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for metric in ("absent_from_tree", "present_not_selected", "repeated_same_family_present", "gold_in_tree"):
        m = aggregate[metric]
        table_lines.append(
            f"| {metric} | {m['baseline']} | {m['strict_f2']} | {m['strict_f3']} | {m['strict_gate1']} | {m['strict_gate2']} | {m['strict_gate3']} |"
        )
    md = [
        f"# Hundred-case three-gate design comparison under strict phased law ({ts})",
        "",
        "Strict phased law: finish F1 completely, then F2 completely, then (optional) F3 completely before phase_normal.",
        "No gate evaluates depth-3 decisions before F2 is terminal for all required root families.",
        "Within each level, ordering is controller-driven by normal scores/anti-collapse priorities/tie-breaks (no BFS replacement).",
        "",
        "## Gate definitions and thresholds",
        "```json",
        json.dumps(gate_thresholds_snapshot, indent=2),
        "```",
        "",
        "## Six-way aggregate table",
        *table_lines,
        "",
        "## Head-to-head summary",
        f"- strict_f3 vs strict_f2: {aggregate['head_to_head']['strict_f3_vs_strict_f2']}",
        f"- strict_gate1 vs strict_f2: {aggregate['head_to_head']['strict_gate1_vs_strict_f2']}",
        f"- strict_gate1 vs strict_f3: {aggregate['head_to_head']['strict_gate1_vs_strict_f3']}",
        f"- strict_gate2 vs strict_f2: {aggregate['head_to_head']['strict_gate2_vs_strict_f2']}",
        f"- strict_gate2 vs strict_f3: {aggregate['head_to_head']['strict_gate2_vs_strict_f3']}",
        f"- strict_gate3 vs strict_f2: {aggregate['head_to_head']['strict_gate3_vs_strict_f2']}",
        f"- strict_gate3 vs strict_f3: {aggregate['head_to_head']['strict_gate3_vs_strict_f3']}",
        f"- strict_gate1 vs strict_gate2: {aggregate['head_to_head']['strict_gate1_vs_strict_gate2']}",
        f"- strict_gate1 vs strict_gate3: {aggregate['head_to_head']['strict_gate1_vs_strict_gate3']}",
        f"- strict_gate2 vs strict_gate3: {aggregate['head_to_head']['strict_gate2_vs_strict_gate3']}",
        "",
        "## Representative wins/losses",
        f"- cases retaining depth3 gains with lower budget stress: {len(aggregate['cases_gate_retains_depth3_gains_with_lower_budget_stress'])}",
        f"- clearly wrong gate decisions count: {len(aggregate['cases_clearly_wrong_gate_decisions'])}",
        "",
        "## Honest conclusion",
        "Use aggregate_summary.json head-to-head + outcomes_vs_baseline to decide best compromise.",
        "If all gates trail fixed depth-2 or depth-3, prefer fixed-force baseline (as required).",
    ]
    report.write_text("\n".join(md), encoding="utf-8")

    print(f"output_dir={out_dir.relative_to(REPO_ROOT)}")
    print("six_way_absent_from_tree", aggregate["absent_from_tree"])


if __name__ == "__main__":
    main()
