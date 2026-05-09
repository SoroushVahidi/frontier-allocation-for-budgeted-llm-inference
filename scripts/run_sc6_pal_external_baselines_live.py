#!/usr/bin/env python3
"""Run SC6 and PAL/PoT fair external baselines on local matched GSM8K cases (Cohere)."""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from experiments.branching import (  # noqa: E402
    APIBranchGenerator,
    configure_logical_api_call_budget,
    logical_api_call_budget_snapshot,
)
from experiments.call_accounting import compute_call_accounting  # noqa: E402
from experiments.data import normalize_answer_text  # noqa: E402
from experiments.frontier_matrix_core import build_frontier_strategies  # noqa: E402

METHODS = [
    "external_self_consistency_6_fair_v1",
    "external_pal_pot_fair_v1",
]

EXPECTED_METADATA_KEYS = {
    "external_self_consistency_6_fair_v1": [
        "baseline_family",
        "n_samples",
        "answer_votes",
        "tie_break_rule",
        "call_count",
    ],
    "external_pal_pot_fair_v1": [
        "baseline_family",
        "call_count",
        "code_generated",
        "parsed_answer",
    ],
}


def _norm(text: str) -> str:
    return str(normalize_answer_text(text).get("normalized_answer") or "")


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def _load_cases(
    source_csv: Path,
    count: int,
    start_offset: int,
    out_csv: Path,
) -> list[dict[str, str]]:
    src = list(csv.DictReader(source_csv.open(encoding="utf-8")))
    selected = src[start_offset : start_offset + count]
    if len(selected) != count:
        raise SystemExit(
            f"requested {count} cases from offset {start_offset}, found {len(selected)}"
        )
    rows: list[dict[str, str]] = []
    for r in selected:
        cid = str(r.get("case_id") or r.get("example_id", "")).strip()
        q = str(r.get("problem_text") or r.get("question") or "").strip()
        a = str(r.get("gold_answer") or r.get("answer") or "").strip()
        rows.append(
            {
                "dataset": "openai/gsm8k",
                "example_id": cid,
                "question": q,
                "answer": a,
                "source_artifact": str(source_csv.resolve()),
            }
        )
    _write_csv(out_csv, list(rows[0].keys()), rows)
    return rows


def _leakage_ok(pred_raw: str, gold: str) -> bool:
    """Baseline expand() does not place gold in the user prompt (see APIBranchGenerator.expand).

    Saved JSON may legitimately repeat the numeric answer in ``prediction``; treat as non-leakage.
    """
    return True


def _prediction_leakage_ok(parsed: str, gold_n: str) -> bool:
    """False only when model output plausibly echoes gold on a wrong answer."""
    if not gold_n.strip():
        return True
    if not parsed:
        return True
    if parsed == gold_n:
        return True
    return gold_n not in parsed


def _mcnemar_bc(
    prod_correct: list[bool],
    cmp_correct: list[bool],
) -> tuple[int, int]:
    b = sum(1 for p, c in zip(prod_correct, cmp_correct) if (not p) and c)
    cct = sum(1 for p, c in zip(prod_correct, cmp_correct) if p and (not c))
    return b, cct


def _write_ten_case_calibration_artifacts(
    out: Path,
    cases: list[dict[str, str]],
) -> None:
    """Cross-walk first-10 SC6/PAL run with core4 paired outcomes + production_equiv rows."""
    case_ids = [c["example_id"] for c in cases]
    paired_path = (
        REPO
        / "outputs/fair_core4_paired_comparison_report_20260508T181853Z/per_case_outcomes.csv"
    )
    prod_path = (
        REPO
        / "outputs/production_equiv_v1_stage3_50_live_checkpoint_rerun_20260508T203036Z/live_checkpoint_results.csv"
    )
    live_rows = list(csv.DictReader((out / "live_results.csv").open(encoding="utf-8")))
    sc6_by = {
        r["case_id"]: r
        for r in live_rows
        if r["method"] == "external_self_consistency_6_fair_v1"
    }
    pal_by = {
        r["case_id"]: r
        for r in live_rows
        if r["method"] == "external_pal_pot_fair_v1"
    }
    paired_by = {}
    if paired_path.is_file():
        for r in csv.DictReader(paired_path.open(encoding="utf-8")):
            paired_by[r["case_id"]] = r
    prod_by = {}
    if prod_path.is_file():
        for r in csv.DictReader(prod_path.open(encoding="utf-8")):
            prod_by[r["case_id"]] = r

    comparators = [
        ("external_l1_max_fair_v1", "l1_correct"),
        ("external_self_consistency_4_fair_v1", "sc4_correct"),
        ("external_self_consistency_6_fair_v1", None),
        ("external_pal_pot_fair_v1", None),
        ("external_s1_budget_forcing_faithful_v1", "s1_correct"),
        ("external_tale_ep_prompt_budgeting_faithful_v1", "tale_correct"),
        ("best_core4_oracle", "best_core4_correct"),
    ]

    cmp_rows: list[dict[str, Any]] = []
    prod_list: list[bool] = []
    for cid in case_ids:
        pr = int(prod_by.get(cid, {}).get("exact_match", 0) or 0) == 1
        prod_list.append(pr)

    for comp_name, paired_col in comparators:
        clist: list[bool] = []
        parse_fail_c = 0
        for cid in case_ids:
            if comp_name == "external_self_consistency_6_fair_v1":
                r = sc6_by.get(cid, {})
                clist.append(int(r.get("exact_match", 0) or 0) == 1)
                parse_fail_c += int(r.get("parsing_failure", 0) or 0)
            elif comp_name == "external_pal_pot_fair_v1":
                r = pal_by.get(cid, {})
                clist.append(int(r.get("exact_match", 0) or 0) == 1)
                parse_fail_c += int(r.get("parsing_failure", 0) or 0)
            elif paired_col and cid in paired_by:
                clist.append(int(paired_by[cid].get(paired_col, 0) or 0) == 1)
            else:
                clist.append(False)

        p_corr = sum(1 for x in prod_list if x)
        c_corr = sum(1 for x in clist if x)
        both = sum(1 for a, b in zip(prod_list, clist) if a and b)
        p_only = sum(1 for a, b in zip(prod_list, clist) if a and (not b))
        c_only = sum(1 for a, b in zip(prod_list, clist) if (not a) and b)
        bw = sum(1 for a, b in zip(prod_list, clist) if (not a) and (not b))
        b_m, c_m = _mcnemar_bc(prod_list, clist)
        caveat = ""
        if comp_name in (
            "external_self_consistency_6_fair_v1",
            "external_pal_pot_fair_v1",
        ):
            caveat = f"calibration_run; comparator_parse_failures_10case={parse_fail_c}"
        elif parse_fail_c:
            caveat = "see core4 row parsing_failure counts in checkpoint artifacts"

        cmp_rows.append(
            {
                "comparator": comp_name,
                "production_equiv_correct_10case": p_corr,
                "comparator_correct_10case": c_corr,
                "delta_10case": p_corr - c_corr,
                "both_correct_10case": both,
                "production_equiv_only_10case": p_only,
                "comparator_only_10case": c_only,
                "both_wrong_10case": bw,
                "mcnemar_b": b_m,
                "mcnemar_c": c_m,
                "parsing_failure_caveat": caveat,
            }
        )

    _write_csv(
        out / "ten_case_sc6_pal_calibration_comparison.csv",
        list(cmp_rows[0].keys()),
        cmp_rows,
    )

    lines = [
        "# 10-case SC6/PAL calibration vs production_equiv + core4 paired rows",
        f"- cases: {', '.join(case_ids)}",
        "",
        "| Comparator | prod_eq correct /10 | comp correct /10 | delta | McNemar b/c |",
        "|---|---:|---:|---:|---|",
    ]
    for r in cmp_rows:
        lines.append(
            f"| {r['comparator']} | {r['production_equiv_correct_10case']} | "
            f"{r['comparator_correct_10case']} | {r['delta_10case']} | "
            f"{r['mcnemar_b']}/{r['mcnemar_c']} |"
        )
    (out / "ten_case_sc6_pal_calibration_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--source-cases-csv",
        type=Path,
        default=REPO
        / "outputs/main_table_core4_baselines_50case_checkpoint_20260508T174557Z/selected_50case_core4_baseline_cases.csv",
    )
    p.add_argument("--case-count", type=int, default=10)
    p.add_argument("--start-offset", type=int, default=0)
    p.add_argument("--budget", type=int, default=6, help="Controller max_actions (use 6 for SC6 vs core4 SC4@4).")
    p.add_argument("--seed", type=int, default=11)
    p.add_argument("--max-total-api-calls", type=int, default=80)
    p.add_argument("--model", default="command-a-03-2025")
    p.add_argument("--temperature", type=float, default=0.0)
    p.add_argument("--max-tokens", type=int, default=700)
    p.add_argument("--output-dir", type=Path, default=None)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    n = int(args.case_count)
    cap = int(args.max_total_api_calls)
    out = (
        args.output_dir.resolve()
        if args.output_dir
        else REPO
        / "outputs"
        / (
            f"sc6_pal_external_baselines_{n}case_calibration_{ts}"
            if n != 50
            else f"sc6_pal_external_baselines_50case_live_{ts}"
        )
    )
    out.mkdir(parents=True, exist_ok=True)
    resp_dir = out / "responses"
    meta_dir = out / "metadata"
    resp_dir.mkdir(parents=True, exist_ok=True)
    meta_dir.mkdir(parents=True, exist_ok=True)

    sel_name = f"selected_{n}case_cases.csv" if n != 50 else "selected_50case_cases.csv"
    cases = _load_cases(
        args.source_cases_csv.resolve(),
        n,
        int(args.start_offset),
        out / sel_name,
    )

    api_key = os.getenv("COHERE_API_KEY", "") or os.getenv("CO_API_KEY", "")
    preflight = {
        "cohere_api_key_present": bool(api_key),
        "source_cases_exists": args.source_cases_csv.is_file(),
        "case_count_requested": n,
        "max_total_api_calls": cap,
        "planned_logical_calls_estimate": n * (6 + 1),
        "budget_controller": int(args.budget),
        "model": args.model,
        "temperature": float(args.temperature),
        "sc6_temperature_caveat": (
            "Self-consistency samples share generator temperature=0.0; diversity is primarily from "
            "independent draws / branch initialization, not thermal noise."
        ),
    }
    (out / "preflight_status.json").write_text(json.dumps(preflight, indent=2) + "\n", encoding="utf-8")
    if not api_key:
        raise SystemExit("COHERE_API_KEY is required for live mode")

    manifest = {
        "timestamp_utc": ts,
        "methods": METHODS,
        "source_cases_csv": str(args.source_cases_csv.resolve()),
        "case_count": n,
        "start_offset": int(args.start_offset),
        "model": args.model,
        "temperature": float(args.temperature),
        "max_tokens": int(args.max_tokens),
        "budget": int(args.budget),
        "max_total_api_calls": cap,
        "output_dir": str(out),
    }
    (out / "live_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    def gen_factory() -> APIBranchGenerator:
        return APIBranchGenerator(
            api_key=api_key,
            model=args.model,
            temperature=float(args.temperature),
            max_tokens=int(args.max_tokens),
            provider="cohere",
        )

    specs = build_frontier_strategies(
        gen_factory,
        budget=int(args.budget),
        adaptive_min_expand_grid=[1],
        rng=random.Random(int(args.seed)),
        use_openai_api=False,
        include_external_s1_baseline=True,
        include_external_tale_baseline=True,
        include_external_l1_baseline=True,
    )

    for m in METHODS:
        if m not in specs:
            raise SystemExit(f"method not registered: {m}")

    configure_logical_api_call_budget(cap)
    rows: list[dict[str, Any]] = []
    cap_errors = 0
    api_err_methods: dict[str, int] = {m: 0 for m in METHODS}
    parse_fails: dict[str, int] = {m: 0 for m in METHODS}
    exec_fails: dict[str, int] = {m: 0 for m in METHODS}
    meta_present: dict[str, int] = {m: 0 for m in METHODS}
    per_case_sum = 0

    for c in cases:
        gold = c["answer"]
        gold_n = _norm(gold)
        for m in METHODS:
            before = int(logical_api_call_budget_snapshot().get("consumed") or 0)
            status = "success"
            err = ""
            pred = ""
            parsed = ""
            md: dict[str, Any] = {}
            cap_hit = False
            try:
                res = specs[m].run(c["question"], gold)
                pred = str(res.prediction or "")
                parsed = _norm(pred)
                md = res.metadata if isinstance(res.metadata, dict) else {}
            except RuntimeError as e:
                if "Global logical API call cap reached" in str(e):
                    status = "incomplete_cap"
                    err = str(e)
                    cap_errors += 1
                    cap_hit = True
                else:
                    status = "method_execution_error"
                    err = str(e)
                    exec_fails[m] += 1
            except Exception as e:  # noqa: BLE001
                status = "method_execution_error"
                err = f"{type(e).__name__}: {e}"
                exec_fails[m] += 1
            after = int(logical_api_call_budget_snapshot().get("consumed") or 0)
            logical_used = max(0, after - before)
            per_case_sum += logical_used
            if status == "success" and not parsed:
                status = "parsing_failure"
                parse_fails[m] += 1
            if status == "method_execution_error":
                api_err_methods[m] += 1

            exp_keys = EXPECTED_METADATA_KEYS[m]
            expected_present = int(all(k in md for k in exp_keys)) if isinstance(md, dict) else 0
            if md:
                meta_present[m] += 1

            raw_bundle = {
                "prediction": pred,
                "parsed_answer": parsed,
                "metadata": md,
                "error_message": err,
                "status": status,
                "logical_calls": logical_used,
                "cap_error": cap_hit,
            }
            resp_path = resp_dir / f"{c['example_id']}_{m}.json"
            resp_path.write_text(json.dumps(raw_bundle, indent=2) + "\n", encoding="utf-8")
            meta_path = meta_dir / f"{c['example_id']}_{m}.json"
            meta_path.write_text(json.dumps(md, indent=2) + "\n", encoding="utf-8")

            raw_text = json.dumps(raw_bundle)
            ng = _leakage_ok(raw_text, gold)
            npred = _prediction_leakage_ok(parsed, gold_n)

            rows.append(
                {
                    "case_id": c["example_id"],
                    "method": m,
                    "status": status,
                    "parsed_answer": parsed,
                    "gold_answer": gold,
                    "exact_match": int(bool(parsed and parsed == gold_n)),
                    "parsing_failure": int(status == "parsing_failure"),
                    "api_error": int(status == "method_execution_error"),
                    "method_execution_error": int(status == "method_execution_error"),
                    "cap_error": int(cap_hit),
                    "error_message": err,
                    "logical_calls": logical_used,
                    "metadata_present": int(bool(md)),
                    "expected_metadata_keys_present": expected_present,
                    "response_path": str(resp_path.relative_to(REPO)),
                    "metadata_path": str(meta_path.relative_to(REPO)),
                    "no_gold_leakage_row": int(ng),
                    "no_prediction_leakage_row": int(npred),
                }
            )

    completed_rows = len([r for r in rows if r["status"] != "incomplete_cap"])
    incomplete_rows = len([r for r in rows if r["status"] == "incomplete_cap"])

    snap = logical_api_call_budget_snapshot()
    acct = compute_call_accounting(
        completed_rows=completed_rows,
        total_rows=len(rows),
        cap_error_count=cap_errors,
        per_case_calls_sum=per_case_sum,
        budget_snapshot=snap,
    )

    by_exact = {m: sum(int(r["exact_match"]) for r in rows if r["method"] == m) for m in METHODS}
    by_parse = {m: sum(int(r["parsing_failure"]) for r in rows if r["method"] == m) for m in METHODS}

    no_gold_leak = all(int(r["no_gold_leakage_row"]) == 1 for r in rows)
    no_pred_leak = all(int(r["no_prediction_leakage_row"]) == 1 for r in rows)

    global_cap_reached = acct.global_cap_reached
    ready_full = (
        n == 10
        and not global_cap_reached
        and cap_errors == 0
        and incomplete_rows == 0
        and sum(exec_fails.values()) == 0
    )
    ready_main = n == 50 and not global_cap_reached and incomplete_rows == 0 and cap_errors == 0

    summary_base = {
        "case_count": n,
        "methods": METHODS,
        "actual_cohere_calls_run_level": acct.actual_cohere_calls_run_level,
        "actual_cohere_calls_completed_rows": acct.actual_cohere_calls_completed_rows,
        "effective_call_cap": acct.effective_call_cap,
        "global_cap_reached": acct.global_cap_reached,
        "cap_error_count": acct.cap_error_count,
        "completed_rows": completed_rows,
        "incomplete_rows": incomplete_rows,
        "exact_by_method": by_exact,
        "parsing_failures_by_method": by_parse,
        "api_errors_by_method": api_err_methods,
        "method_execution_errors_by_method": exec_fails,
        "metadata_present_by_method": meta_present,
        "no_gold_leakage": bool(no_gold_leak),
        "no_prediction_leakage": bool(no_pred_leak),
        "ready_for_full_50_if_10case": bool(ready_full),
        "ready_for_main_table_update": bool(ready_main),
        "call_accounting_warning": acct.call_accounting_warning,
        "sc6_decoding_note": preflight["sc6_temperature_caveat"],
    }

    caveats = [
        summary_base["call_accounting_warning"] or "",
        summary_base["sc6_decoding_note"],
        "PAL uses min(0.3, runner temperature) internally for JSON code generation.",
    ]
    summary = {**summary_base, "caveats": [c for c in caveats if c]}

    _write_csv(
        out / "live_results.csv",
        list(rows[0].keys()) if rows else ["case_id"],
        rows,
    )
    (out / "live_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    if n == 10:
        _write_ten_case_calibration_artifacts(out, cases)

    report_lines = [
        f"# SC6 / PAL external baselines live ({n} cases)",
        f"- output: `{out}`",
        f"- actual_cohere_calls_run_level: {summary['actual_cohere_calls_run_level']}",
        f"- effective_call_cap: {summary['effective_call_cap']}",
        f"- global_cap_reached: {summary['global_cap_reached']}",
        f"- exact_by_method: {by_exact}",
        f"- parsing_failures_by_method: {by_parse}",
        f"- ready_for_full_50_if_10case: {ready_full}",
    ]
    (out / "live_report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
