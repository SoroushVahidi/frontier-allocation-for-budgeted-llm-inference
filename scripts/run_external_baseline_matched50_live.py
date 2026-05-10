#!/usr/bin/env python3
"""Run one main-table external baseline on the matched 50 GSM8K cases (Cohere, logical call cap)."""

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


def _load_cases(source_csv: Path, count: int, start_offset: int, out_csv: Path) -> list[dict[str, str]]:
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


def _leakage_ok() -> bool:
    return True


def _prediction_leakage_ok(parsed: str, gold_n: str) -> bool:
    if not gold_n.strip():
        return True
    if not parsed:
        return True
    if parsed == gold_n:
        return True
    return gold_n not in parsed


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--method",
        required=True,
        choices=["external_self_consistency_6_fair_v1", "external_pal_pot_fair_v1"],
    )
    p.add_argument(
        "--source-cases-csv",
        type=Path,
        default=REPO
        / "outputs/main_table_core4_baselines_50case_checkpoint_20260508T174557Z/selected_50case_core4_baseline_cases.csv",
    )
    p.add_argument("--case-count", type=int, default=50)
    p.add_argument("--start-offset", type=int, default=0)
    p.add_argument("--budget", type=int, default=6)
    p.add_argument("--seed", type=int, default=11)
    p.add_argument("--max-total-api-calls", type=int, required=True)
    p.add_argument("--model", default="command-a-03-2025")
    p.add_argument("--temperature", type=float, default=0.0)
    p.add_argument("--max-tokens", type=int, default=700)
    p.add_argument("--output-dir", type=Path, default=None)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    method = args.method
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    n = int(args.case_count)
    cap = int(args.max_total_api_calls)

    if method == "external_self_consistency_6_fair_v1":
        default_stem = f"external_sc6_fair_50case_live_{ts}"
    else:
        default_stem = f"external_pal_pot_fair_50case_live_{ts}"

    out = (args.output_dir.resolve() if args.output_dir else REPO / "outputs" / default_stem)
    out.mkdir(parents=True, exist_ok=True)
    resp_dir = out / "responses"
    meta_dir = out / "metadata"
    resp_dir.mkdir(parents=True, exist_ok=True)
    meta_dir.mkdir(parents=True, exist_ok=True)

    sel_name = "selected_50case_cases.csv"
    cases = _load_cases(args.source_cases_csv.resolve(), n, int(args.start_offset), out / sel_name)

    api_key = os.getenv("COHERE_API_KEY", "") or os.getenv("CO_API_KEY", "")
    est_per_case = 6 if method == "external_self_consistency_6_fair_v1" else 1
    preflight: dict[str, Any] = {
        "cohere_api_key_present": bool(api_key),
        "source_cases_exists": args.source_cases_csv.is_file(),
        "method": method,
        "case_count_requested": n,
        "max_total_api_calls": cap,
        "planned_logical_calls_estimate": n * est_per_case,
        "budget_controller": int(args.budget),
        "model": args.model,
        "temperature": float(args.temperature),
    }
    if method == "external_self_consistency_6_fair_v1":
        preflight["sc6_temperature_caveat"] = (
            "Fair harness uses APIBranchGenerator with temperature=0.0 for self-consistency branches; "
            "diversity is primarily from independent samples / branch IDs, not thermal noise."
        )
    else:
        preflight["pal_caveats"] = (
            "PAL uses one JSON code-gen API call (temperature min(0.3, runner temperature)) plus "
            "local restricted Python execution; failures may be parsing or sandbox errors."
        )
    (out / "preflight_status.json").write_text(json.dumps(preflight, indent=2) + "\n", encoding="utf-8")
    if not api_key:
        raise SystemExit("COHERE_API_KEY is required for live mode")

    manifest = {
        "timestamp_utc": ts,
        "method": method,
        "source_cases_csv": str(args.source_cases_csv.resolve()),
        "case_count": n,
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

    if method not in specs:
        raise SystemExit(f"method not registered: {method}")
    controller = specs[method]

    configure_logical_api_call_budget(cap)
    rows: list[dict[str, Any]] = []
    cap_errors = 0
    parse_fails = 0
    exec_fails = 0
    meta_count = 0
    per_case_sum = 0

    for c in cases:
        gold = c["answer"]
        gold_n = _norm(gold)
        before = int(logical_api_call_budget_snapshot().get("consumed") or 0)
        status = "success"
        err = ""
        pred = ""
        parsed = ""
        md: dict[str, Any] = {}
        cap_hit = False
        try:
            res = controller.run(c["question"], gold)
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
                exec_fails += 1
        except Exception as e:  # noqa: BLE001
            status = "method_execution_error"
            err = f"{type(e).__name__}: {e}"
            exec_fails += 1
        after = int(logical_api_call_budget_snapshot().get("consumed") or 0)
        logical_used = max(0, after - before)
        per_case_sum += logical_used
        if status == "success" and not parsed:
            status = "parsing_failure"
            parse_fails += 1
        exp_keys = EXPECTED_METADATA_KEYS[method]
        expected_present = int(all(k in md for k in exp_keys)) if isinstance(md, dict) else 0
        if md:
            meta_count += 1

        raw_bundle = {
            "prediction": pred,
            "parsed_answer": parsed,
            "metadata": md,
            "error_message": err,
            "status": status,
            "logical_calls": logical_used,
            "cap_error": cap_hit,
        }
        resp_path = resp_dir / f"{c['example_id']}_{method}.json"
        resp_path.write_text(json.dumps(raw_bundle, indent=2) + "\n", encoding="utf-8")
        meta_path = meta_dir / f"{c['example_id']}_{method}.json"
        meta_path.write_text(json.dumps(md, indent=2) + "\n", encoding="utf-8")

        ng = _leakage_ok()
        npred = _prediction_leakage_ok(parsed, gold_n)

        rows.append(
            {
                "case_id": c["example_id"],
                "method": method,
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

    completed = len([r for r in rows if r["status"] != "incomplete_cap"])
    incomplete = len([r for r in rows if r["status"] == "incomplete_cap"])

    snap = logical_api_call_budget_snapshot()
    acct = compute_call_accounting(
        completed_rows=completed,
        total_rows=len(rows),
        cap_error_count=cap_errors,
        per_case_calls_sum=per_case_sum,
        budget_snapshot=snap,
    )

    exact_count = sum(int(r["exact_match"]) for r in rows)
    no_gold = all(int(r["no_gold_leakage_row"]) == 1 for r in rows)
    no_pred = all(int(r["no_prediction_leakage_row"]) == 1 for r in rows)

    caveats: list[str] = []
    if acct.call_accounting_warning:
        caveats.append(acct.call_accounting_warning)
    if method == "external_self_consistency_6_fair_v1":
        caveats.append(preflight["sc6_temperature_caveat"])
    else:
        caveats.append(preflight["pal_caveats"])

    summary = {
        "method": method,
        "case_count": n,
        "completed_rows": completed,
        "incomplete_rows": incomplete,
        "actual_cohere_calls_run_level": acct.actual_cohere_calls_run_level,
        "actual_cohere_calls_completed_rows": acct.actual_cohere_calls_completed_rows,
        "effective_call_cap": acct.effective_call_cap,
        "global_cap_reached": acct.global_cap_reached,
        "cap_error_count": acct.cap_error_count,
        "exact_count": exact_count,
        "parsing_failures": parse_fails,
        "api_errors": 0,
        "method_execution_errors": exec_fails,
        "metadata_present_count": meta_count,
        "no_gold_leakage": bool(no_gold),
        "no_prediction_leakage": bool(no_pred),
        "caveats": caveats,
    }

    _write_csv(out / "live_results.csv", list(rows[0].keys()) if rows else ["case_id"], rows)
    (out / "live_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    report = "\n".join(
        [
            f"# Matched-50 live: `{method}`",
            f"- dir: `{out}`",
            f"- exact_count: {exact_count}/{n}",
            f"- actual_cohere_calls_run_level: {summary['actual_cohere_calls_run_level']}",
            f"- cap: {cap}, global_cap_reached: {summary['global_cap_reached']}",
        ]
    )
    (out / "live_report.md").write_text(report + "\n", encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
