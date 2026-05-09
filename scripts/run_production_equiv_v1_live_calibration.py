#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import random
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from experiments.branching import (
    APIBranchGenerator,
    configure_logical_api_call_budget,
    logical_api_call_budget_snapshot,
)
from experiments.call_accounting import compute_call_accounting
from experiments.frontier_matrix_core import build_frontier_strategies

ALIAS = (
    "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal_"
    "structural_commit_v1_production_equiv_v1"
)
MATCHED_50 = REPO / "outputs/main_table_core4_baselines_50case_checkpoint_20260508T174557Z/selected_50case_core4_baseline_cases.csv"
CASE_SOURCE = REPO / "outputs/stage3_tale_s1_pilot_readiness_20260508T032919Z/stage3_pilot_cases.csv"
FAIR_PER_CASE = REPO / "outputs/fair_core4_paired_comparison_report_20260508T181853Z/per_case_outcomes.csv"
PRIOR_PER_CASE = REPO / "outputs/fair_core4_vs_our_method_alignment_plan_20260508T181550Z/existing_fair_comparison.csv"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run production_equiv_v1 10-case live calibration.")
    p.add_argument("--case-count", type=int, default=10)
    p.add_argument("--max-total-cohere-calls", type=int, default=50)
    p.add_argument("--temperature", type=float, default=0.0)
    p.add_argument("--max-tokens", type=int, default=700)
    p.add_argument("--output-dir", type=Path, default=None)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = (
        args.output_dir.resolve()
        if args.output_dir
        else REPO / "outputs" / f"production_equiv_v1_10case_live_calibration_{ts}"
    )
    (out / "responses").mkdir(parents=True, exist_ok=True)
    (out / "metadata").mkdir(parents=True, exist_ok=True)

    selected_50 = _read_csv(MATCHED_50)
    selected = selected_50[: args.case_count]
    selected_ids = [r.get("example_id") or r.get("case_id") for r in selected]
    selected_ids = [x for x in selected_ids if x]
    case_map = {
        (r.get("case_id") or r.get("example_id")): r
        for r in _read_csv(CASE_SOURCE)
    }

    api_key = (os.getenv("COHERE_API_KEY") or os.getenv("CO_API_KEY") or "").strip()
    preflight = {
        "cohere_api_key_set": bool(api_key),
        "selected_case_count": len(selected_ids),
        "selected_case_ids_in_matched_50": len(selected_ids) == args.case_count,
        "method_alias": ALIAS,
        "discovery3_excluded": True,
        "percent_base_enabled": False,
        "effective_call_cap": int(args.max_total_cohere_calls),
        "output_dir_ready": out.exists(),
    }

    rng = random.Random(7)

    def factory() -> APIBranchGenerator:
        return APIBranchGenerator(
            provider="cohere",
            api_key=api_key,
            model="command-a-03-2025",
            temperature=float(args.temperature),
            max_tokens=int(args.max_tokens),
            timeout_seconds=60,
        )

    specs = build_frontier_strategies(
        factory,
        budget=4,
        adaptive_min_expand_grid=[1],
        rng=rng,
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
        include_external_l1_baseline=True,
        include_external_s1_baseline=True,
        include_external_tale_baseline=True,
    )
    preflight["alias_resolves"] = ALIAS in specs
    preflight["abort_reasons"] = [
        k
        for k in ("cohere_api_key_set", "selected_case_ids_in_matched_50", "alias_resolves")
        if not preflight[k]
    ]
    preflight["abort"] = bool(preflight["abort_reasons"])
    (out / "preflight_status.json").write_text(json.dumps(preflight, indent=2) + "\n", encoding="utf-8")

    _write_csv(out / "selected_10case_cases.csv", list(selected[0].keys()), selected)
    manifest = {
        "method_alias": ALIAS,
        "model": "command-a-03-2025",
        "temperature": float(args.temperature),
        "max_tokens": int(args.max_tokens),
        "case_count": len(selected_ids),
        "max_total_cohere_calls": int(args.max_total_cohere_calls),
        "selected_case_source": str(MATCHED_50),
        "discovery3_excluded": True,
        "percent_base_enabled": False,
    }
    (out / "live_calibration_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    if preflight["abort"]:
        raise SystemExit(f"preflight failed: {preflight['abort_reasons']}")

    controller = specs[ALIAS]
    results: list[dict[str, object]] = []
    api_errors: list[str] = []
    surface_counts: Counter[str] = Counter()
    retry_triggered = 0
    retry_committed = 0
    metadata_present = 0
    parsing_failures = 0
    exact_count = 0
    per_case_calls_sum = 0
    no_gold_leakage = True
    no_prediction_leakage = True
    cap_error_count = 0

    configure_logical_api_call_budget(int(args.max_total_cohere_calls))
    try:
        for cid in selected_ids:
            case = case_map[cid]
            question = case.get("question") or case.get("problem_text") or ""
            gold = str(case.get("answer") or case.get("gold_answer") or "")
            if hasattr(controller.generator, "reset_usage_counters"):
                controller.generator.reset_usage_counters()
            try:
                mr = controller.run(question, gold)
                md = dict(mr.metadata or {})
                prediction = str(mr.prediction or "")
                normalized = prediction.replace(",", "").strip()
                exact = int(bool(normalized and normalized == gold.replace(",", "").strip()))
                parse_fail = int(not normalized)
                calls = int((controller.generator.snapshot_usage_counters() or {}).get("api_calls", 0))
                per_case_calls_sum += calls
                api_error = ""
                trace = md.get("action_trace") if isinstance(md.get("action_trace"), list) else []
                for ev in trace:
                    if isinstance(ev, dict) and str(ev.get("source") or "") == "production_equiv_targeted_retry":
                        ptxt = str(ev.get("prompt_text") or "")
                        if gold and len(gold) >= 2 and gold in ptxt:
                            no_gold_leakage = False
                        if any(t in ptxt.lower() for t in ("external_l1", "best_core4", "our_correct", "prediction")):
                            no_prediction_leakage = False
                response_text = "(no targeted retry response captured)"
                for ev in reversed(trace):
                    if isinstance(ev, dict) and str(ev.get("source") or "") == "production_equiv_targeted_retry":
                        response_text = str(ev.get("response_text") or ev.get("reasoning_text") or response_text)
                        break
                rp = out / "responses" / f"{cid}.txt"
                mp = out / "metadata" / f"{cid}.json"
                rp.write_text(response_text, encoding="utf-8")
                mp.write_text(json.dumps(md, indent=2) + "\n", encoding="utf-8")
                source = str(md.get("production_equiv_surface_source") or "")
                surface_counts[source] += 1
                tr = bool(md.get("targeted_retry_triggered", False))
                tc = bool(md.get("targeted_retry_committed", False))
                retry_triggered += int(tr)
                retry_committed += int(tc)
                metadata_present += 1
                parsing_failures += parse_fail
                exact_count += exact
                results.append(
                    {
                        "case_id": cid,
                        "problem_text": question,
                        "gold_answer": gold,
                        "production_equiv_answer": prediction,
                        "normalized_answer": normalized,
                        "exact_match": exact,
                        "logical_calls": calls,
                        "api_error": api_error,
                        "parsing_failure": parse_fail,
                        "response_path": str(rp.relative_to(REPO)),
                        "metadata_path": str(mp.relative_to(REPO)),
                        "production_equiv_surface_source": source,
                        "production_equiv_surface_reason": str(md.get("production_equiv_surface_reason") or ""),
                        "targeted_retry_triggered": tr,
                        "targeted_retry_scaffold": str(md.get("targeted_retry_scaffold") or ""),
                        "targeted_retry_extra_calls_used": int(md.get("targeted_retry_extra_calls_used", 0) or 0),
                        "targeted_retry_answer_parsed": str(md.get("targeted_retry_answer_parsed") or ""),
                        "targeted_retry_committed": tc,
                        "targeted_retry_rejection_reason": str(md.get("targeted_retry_rejection_reason") or ""),
                        "discovery3_excluded": True,
                        "percent_base_enabled": False,
                    }
                )
            except Exception as exc:
                msg = f"{type(exc).__name__}: {exc}"
                api_errors.append(f"{cid}: {msg}")
                if "Global logical API call cap reached" in msg:
                    cap_error_count += 1
                results.append(
                    {
                        "case_id": cid,
                        "problem_text": question,
                        "gold_answer": gold,
                        "production_equiv_answer": "",
                        "normalized_answer": "",
                        "exact_match": 0,
                        "logical_calls": 0,
                        "api_error": msg,
                        "parsing_failure": 1,
                        "response_path": "",
                        "metadata_path": "",
                        "production_equiv_surface_source": "",
                        "production_equiv_surface_reason": "",
                        "targeted_retry_triggered": False,
                        "targeted_retry_scaffold": "",
                        "targeted_retry_extra_calls_used": 0,
                        "targeted_retry_answer_parsed": "",
                        "targeted_retry_committed": False,
                        "targeted_retry_rejection_reason": "exception",
                        "discovery3_excluded": True,
                        "percent_base_enabled": False,
                    }
                )
                parsing_failures += 1
    finally:
        snap = logical_api_call_budget_snapshot()
        configure_logical_api_call_budget(None)

    completed_rows = sum(1 for r in results if not str(r["api_error"]).strip())
    acct = compute_call_accounting(
        completed_rows=completed_rows,
        total_rows=len(results),
        cap_error_count=cap_error_count,
        per_case_calls_sum=per_case_calls_sum,
        budget_snapshot=snap,
        inferred_from_errors=(int(args.max_total_cohere_calls) if cap_error_count > 0 else None),
    )
    _write_csv(out / "live_calibration_results.csv", list(results[0].keys()), results)

    fair = {r["case_id"]: r for r in _read_csv(FAIR_PER_CASE)}
    prior = {r["case_id"]: r for r in _read_csv(PRIOR_PER_CASE)}
    comparators = [
        ("prior_patch_focused_integrated_method", "our_correct"),
        ("external_l1_max_fair_v1", "l1_correct"),
        ("external_self_consistency_4_fair_v1", "sc4_correct"),
        ("external_s1_budget_forcing_faithful_v1", "s1_correct"),
        ("external_tale_ep_prompt_budgeting_faithful_v1", "tale_correct"),
        ("best_core4_oracle", "best_core4_correct"),
    ]
    our_map = {r["case_id"]: int(r["exact_match"]) for r in results}
    comp_rows = []
    pair_rows = []
    for name, key in comparators:
        both = ours = comp = wrong = b = c = 0
        for cid in selected_ids:
            ov = our_map.get(cid, 0)
            cv = int((prior if name == "prior_patch_focused_integrated_method" else fair).get(cid, {}).get(key, 0) or 0)
            if ov and cv:
                both += 1
            elif ov and not cv:
                ours += 1
                b += 1
            elif (not ov) and cv:
                comp += 1
                c += 1
            else:
                wrong += 1
        comp_rows.append(
            {
                "comparator": name,
                "production_equiv_correct": both + ours,
                "comparator_correct": both + comp,
                "delta": (both + ours) - (both + comp),
                "both_correct": both,
                "production_equiv_only": ours,
                "comparator_only": comp,
                "both_wrong": wrong,
                "mcnemar_b": b,
                "mcnemar_c": c,
            }
        )
        pair_rows.append(
            {
                "comparator": name,
                "production_equiv_only": ours,
                "comparator_only": comp,
                "both_correct": both,
                "both_wrong": wrong,
                "mcnemar_b": b,
                "mcnemar_c": c,
            }
        )
    _write_csv(out / "ten_case_subset_comparison.csv", list(comp_rows[0].keys()), comp_rows)
    _write_csv(out / "ten_case_paired_summary.csv", list(pair_rows[0].keys()), pair_rows)

    recommended_full_50_cap = max(132, int(round((acct.actual_cohere_calls_completed_rows / max(completed_rows, 1)) * 50 + 30)))
    summary = {
        "case_count": len(results),
        "completed_rows": acct.completed_rows,
        "incomplete_rows": acct.incomplete_rows,
        "actual_cohere_calls": acct.actual_cohere_calls_completed_rows,
        "actual_cohere_calls_completed_rows": acct.actual_cohere_calls_completed_rows,
        "actual_cohere_calls_run_level": acct.actual_cohere_calls_run_level,
        "effective_call_cap": acct.effective_call_cap,
        "global_cap_reached": acct.global_cap_reached,
        "cap_error_count": acct.cap_error_count,
        "call_accounting_source": acct.call_accounting_source,
        "call_accounting_warning": acct.call_accounting_warning,
        "production_equiv_correct_count": exact_count,
        "parsing_failures": parsing_failures,
        "api_errors": api_errors,
        "metadata_present_count": metadata_present,
        "targeted_retry_triggered_count": retry_triggered,
        "targeted_retry_committed_count": retry_committed,
        "surface_source_counts": dict(surface_counts),
        "no_gold_leakage": bool(no_gold_leakage),
        "no_prediction_leakage": bool(no_prediction_leakage),
        "ready_for_full_50_rerun": bool(
            acct.completed_rows == len(results)
            and not acct.global_cap_reached
            and acct.cap_error_count == 0
            and metadata_present == len(results)
            and acct.actual_cohere_calls_run_level <= int(args.max_total_cohere_calls)
            and no_gold_leakage
            and no_prediction_leakage
        ),
        "recommended_full_50_cap": recommended_full_50_cap,
    }
    (out / "live_calibration_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    report = [
        "# production_equiv_v1 10-case live calibration",
        f"- case_count: {summary['case_count']}",
        f"- completed_rows: {summary['completed_rows']}",
        f"- incomplete_rows: {summary['incomplete_rows']}",
        f"- actual_cohere_calls_completed_rows: {summary['actual_cohere_calls_completed_rows']}",
        f"- actual_cohere_calls_run_level: {summary['actual_cohere_calls_run_level']}",
        f"- effective_call_cap: {summary['effective_call_cap']}",
        f"- global_cap_reached: {summary['global_cap_reached']}",
        f"- cap_error_count: {summary['cap_error_count']}",
        f"- call_accounting_source: {summary['call_accounting_source']}",
        f"- call_accounting_warning: {summary['call_accounting_warning']}",
        f"- production_equiv_correct_count: {summary['production_equiv_correct_count']}",
        f"- parsing_failures: {summary['parsing_failures']}",
        f"- metadata_present_count: {summary['metadata_present_count']}",
        f"- targeted_retry_triggered_count: {summary['targeted_retry_triggered_count']}",
        f"- targeted_retry_committed_count: {summary['targeted_retry_committed_count']}",
        f"- surface_source_counts: {summary['surface_source_counts']}",
        f"- no_gold_leakage: {summary['no_gold_leakage']}",
        f"- no_prediction_leakage: {summary['no_prediction_leakage']}",
        f"- ready_for_full_50_rerun: {summary['ready_for_full_50_rerun']}",
        f"- recommended_full_50_cap: {summary['recommended_full_50_cap']}",
    ]
    (out / "live_calibration_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
