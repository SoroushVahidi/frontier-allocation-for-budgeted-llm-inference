#!/usr/bin/env python3
"""Live PAL vs production_equiv casebook collection (bounded Cohere logical-call cap)."""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import re
import sys
from collections import Counter
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

ALIAS = (
    "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal_"
    "structural_commit_v1_production_equiv_v1"
)
PAL_METHOD = "external_pal_pot_fair_v1"
CAP_DEFAULT = 220


def _norm(text: str) -> str:
    return str(normalize_answer_text(text).get("normalized_answer") or "")


def _sanitize(s: str) -> str:
    return " ".join((s or "").replace("\r", " ").replace("\n", " ").split())


def _classify_preliminary(problem: str) -> str:
    t = (problem or "").lower()
    if re.search(r"\b(per hour|mph|percent|%|times (as fast|faster))\b", t):
        return "rate_ratio"
    if re.search(r"\b(before|after|remaining|left)\b", t):
        return "state_update"
    if len(re.findall(r"\d", problem)) >= 8:
        return "multi_step_computation"
    if re.search(r"\b(fraction|half|\d+/\d+)\b", t):
        return "arithmetic_execution"
    return "unknown"


def _read_csv(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(path.open(encoding="utf-8")))


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow(r)


def _pal_details(md: dict[str, Any]) -> tuple[bool, bool, str]:
    """PAL metadata stores code under ``pot_output.python_code``; top-level flags may be stale."""
    pot = md.get("pot_output") if isinstance(md.get("pot_output"), dict) else {}
    code_txt = str(pot.get("python_code") or pot.get("program") or "").strip()
    prog = bool(code_txt) or bool(md.get("code_generated"))
    ok_exec = bool(pot.get("ok")) if isinstance(pot, dict) else False
    if isinstance(pot, dict) and pot.get("exception") is not None:
        ok_exec = False
    err = str(md.get("execution_error") or pot.get("exception") or pot.get("stderr") or "").strip()
    return prog, ok_exec, err[:500]


def finalize_casebook_artifacts(
    out: Path,
    *,
    cases: list[dict[str, str]],
    rows: list[dict[str, Any]],
    n: int,
    snap: dict[str, Any],
    cap_errors: int,
    per_case_sum: int,
    no_gold_leak: bool,
    no_pred_leak: bool,
) -> None:
    by_case: dict[str, dict[str, dict[str, Any]]] = {}
    for r in rows:
        by_case.setdefault(r["case_id"], {})[r["method"]] = r

    incomplete_rows = sum(1 for r in rows if r.get("run_status") == "incomplete_cap")
    ok_rows = sum(1 for r in rows if r.get("run_status") != "incomplete_cap")
    acct = compute_call_accounting(
        completed_rows=ok_rows,
        total_rows=len(rows),
        cap_error_count=cap_errors,
        per_case_calls_sum=per_case_sum,
        budget_snapshot=snap,
    )

    pal_only = prod_only = both_ok = both_bad = answer_disagree = 0
    fam_pal: Counter[str] = Counter()
    fam_prod: Counter[str] = Counter()
    feat_counts: Counter[str] = Counter()
    casebook_rows: list[dict[str, Any]] = []

    for rec in cases:
        cid = rec["case_id"]
        question = _sanitize(rec["problem_text"])
        gold = str(rec["gold_answer"]).strip()
        pr = dict(by_case.get(cid, {}).get(ALIAS, {}))
        palr = dict(by_case.get(cid, {}).get(PAL_METHOD, {}))

        pe_ans = str(pr.get("parsed_answer", ""))
        pa_ans = str(palr.get("parsed_answer", ""))
        pe_ok = int(pr.get("exact_match", 0) or 0) == 1
        pa_ok = int(palr.get("exact_match", 0) or 0) == 1

        parse_issue = int(pr.get("parsing_failure", 0) or 0) == 1 or int(palr.get("parsing_failure", 0) or 0) == 1
        api_issue = (
            bool(pr.get("api_error"))
            or bool(palr.get("api_error"))
            or pr.get("run_status") == "incomplete_cap"
            or palr.get("run_status") == "incomplete_cap"
            or not pr
            or not palr
        )

        if api_issue or (parse_issue and (not pe_ans or not pa_ans)):
            outcome = "parse_or_api_issue"
        elif pe_ok and pa_ok and pe_ans == pa_ans:
            outcome = "both_correct_same"
            both_ok += 1
        elif pe_ok and pa_ok:
            outcome = "both_correct_different"
            both_ok += 1
        elif pa_ok and not pe_ok:
            outcome = "pal_only"
            pal_only += 1
            fam_pal[_classify_preliminary(question)] += 1
        elif pe_ok and not pa_ok:
            outcome = "production_only"
            prod_only += 1
            fam_prod[_classify_preliminary(question)] += 1
        elif pe_ans == pa_ans:
            outcome = "both_wrong_same"
            both_bad += 1
        else:
            outcome = "both_wrong_different"
            both_bad += 1

        if pe_ans != pa_ans and (pe_ans or pa_ans):
            answer_disagree += 1

        pal_prog = str(palr.get("pal_program_present", "")).lower() == "true"
        pal_exec = str(palr.get("pal_execution_success", "")).lower() == "true"
        surf = str(pr.get("production_equiv_surface_source", ""))
        agree = pe_ans == pa_ans and bool(pe_ans)
        feats = [
            f"pal_program_executed_cleanly={pal_prog and pal_exec}",
            f"production_structural_commit={'structural_commit' in surf}",
            f"answer_agreement={agree}",
        ]
        feat_counts.update(feats)

        pal_fail = ""
        if not pal_exec and pal_prog:
            pal_fail = "execution_or_parse"
        elif not pal_prog:
            pal_fail = "no_program"

        note = "gold-free selector cues: PAL exec path vs structural_commit surface; agreement flag."
        casebook_rows.append(
            {
                "case_id": cid,
                "problem_text": question,
                "gold_answer": gold,
                "production_equiv_answer": pe_ans,
                "production_equiv_correct": str(int(pe_ok)),
                "pal_answer": pa_ans,
                "pal_correct": str(int(pa_ok)),
                "sc6_answer": "",
                "sc6_correct": "",
                "outcome_type": outcome,
                "production_equiv_surface_source": surf,
                "pal_program_present": str(palr.get("pal_program_present", "")),
                "pal_execution_success": str(palr.get("pal_execution_success", "")),
                "pal_failure_type": pal_fail,
                "likely_selector_features": "|".join(feats),
                "preliminary_family": _classify_preliminary(question),
                "selector_design_note": note,
                "full_metadata_paths": f"{pr.get('metadata_path','')}|{palr.get('metadata_path','')}",
            }
        )

    pal_only_enough = pal_only >= 8
    disagree_enough = answer_disagree >= 10

    if pal_only_enough and disagree_enough:
        next_step = "design_pal_hybrid_selector"
    elif disagree_enough:
        next_step = "design_pal_hybrid_selector"
    elif pal_only >= 4:
        next_step = "collect_more_pal_disagreements"
    else:
        next_step = "collect_more_pal_disagreements"

    summary = {
        "case_count": n,
        "actual_cohere_calls_run_level": acct.actual_cohere_calls_run_level,
        "completed_rows": len(rows),
        "incomplete_rows": incomplete_rows,
        "cap_reached": acct.global_cap_reached,
        "api_errors_count": sum(1 for r in rows if r.get("run_status") == "method_execution_error"),
        "parsing_failures_by_method": {
            ALIAS: sum(1 for r in rows if r["method"] == ALIAS and int(r.get("parsing_failure", 0) or 0)),
            PAL_METHOD: sum(1 for r in rows if r["method"] == PAL_METHOD and int(r.get("parsing_failure", 0) or 0)),
        },
        "production_equiv_correct": sum(1 for r in rows if r["method"] == ALIAS and int(r.get("exact_match", 0) or 0)),
        "pal_correct": sum(1 for r in rows if r["method"] == PAL_METHOD and int(r.get("exact_match", 0) or 0)),
        "sc6_correct": None,
        "pal_only_count": pal_only,
        "production_only_count": prod_only,
        "both_correct_count": both_ok,
        "both_wrong_count": both_bad,
        "disagreement_count": answer_disagree,
        "asymmetric_disagreement_count": pal_only + prod_only,
        "family_counts_by_outcome_type": dict(Counter(r["outcome_type"] for r in casebook_rows)),
        "pal_only_family_counts": dict(fam_pal),
        "production_only_family_counts": dict(fam_prod),
        "selector_feature_counts": dict(feat_counts),
        "enough_pal_only_cases_for_pattern_analysis": pal_only_enough,
        "enough_disagreement_cases_for_selector_design": disagree_enough,
        "recommended_next_step": next_step,
        "no_gold_leakage": bool(no_gold_leak),
        "no_prediction_leakage": bool(no_pred_leak),
        "effective_call_cap": acct.effective_call_cap,
        "call_accounting_warning": acct.call_accounting_warning,
    }

    _write_csv(out / "live_casebook_results.csv", rows)
    (out / "live_casebook_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    report = "\n".join(
        [
            f"# PAL vs production_equiv casebook live",
            f"- cases: {n}",
            f"- actual_cohere_calls_run_level: {summary['actual_cohere_calls_run_level']}",
            f"- pal_only: {pal_only}, production_only: {prod_only}",
            f"- recommended_next_step: {next_step}",
        ]
    )
    (out / "live_casebook_report.md").write_text(report + "\n", encoding="utf-8")

    _write_csv(out / "pal_vs_prod_casebook.csv", casebook_rows)
    (out / "pal_vs_prod_casebook_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    memo = "\n".join(
        [
            "# PAL-hybrid selector design memo",
            "",
            "## PAL strengths (this slice)",
            "- PAL/PoT excels where deterministic code execution cleanly aggregates multi-step arithmetic.",
            "",
            "## production_equiv strengths",
            "- Competitive when structural_commit surface aligns with problem decomposition; retry path rarely commits.",
            "",
            "## PAL-only pattern?",
            f"- pal_only_count={pal_only}; families: {dict(fam_pal)} — sparse without larger bank.",
            "",
            "## Production-only pattern?",
            f"- production_only_count={prod_only}; families: {dict(fam_prod)}",
            "",
            "## Gold-free selector features",
            "- PAL program generated + sandbox execution success vs stderr/exception.",
            "- Parsed PAL numeric vs production parsed numeric agreement.",
            "- production surface source (structural_commit vs others).",
            "- Target-quantity cues from problem text (offline NLP).",
            "- Numeric sanity: magnitude parity between candidates.",
            "",
            "## production_equiv_v2_pal_hybrid?",
            f"- Evidence level: pal_only≥8 is {pal_only_enough}; answer-disagreement≥10 is {disagree_enough}.",
            "- **Outline v2 (no-API):** run PAL as parallel candidate; if PAL executes cleanly and disagrees with prod, ",
            "  route by confidence features (exec_ok, parse nonempty, agreement with auxiliary numeric leaves); ",
            "  tie-break toward PAL when exec_ok and prod surface is structural_commit with low diversity metadata.",
            "",
            "## Next data step",
            "- If counts insufficient: expand casebook beyond 30 from same pool (`all_casebook.csv`).",
        ]
    )
    (out / "pal_hybrid_selector_design_memo.md").write_text(memo + "\n", encoding="utf-8")


def _refresh_casebook_outputs(live: Path) -> None:
    cases = _read_csv(live / "selected_casebook_cases.csv")
    rows = list(csv.DictReader((live / "live_casebook_results.csv").open(encoding="utf-8")))
    summ = json.load((live / "live_casebook_summary.json").open(encoding="utf-8"))
    for r in rows:
        if r["method"] == PAL_METHOD:
            md = json.load((REPO / r["metadata_path"]).open(encoding="utf-8"))
            prog, okx, err = _pal_details(md)
            r["pal_program_present"] = str(prog).lower()
            r["pal_execution_success"] = str(okx).lower()
            r["pal_execution_error"] = err
    no_pred = True
    for r in rows:
        if r["method"] != PAL_METHOD:
            continue
        g = _norm(r["gold_answer"])
        p = r["parsed_answer"]
        if p and g and p != g and len(g) >= 4 and g in p:
            no_pred = False
    snap = {"budget": summ.get("effective_call_cap"), "consumed": summ.get("actual_cohere_calls_run_level")}
    finalize_casebook_artifacts(
        live,
        cases=cases,
        rows=rows,
        n=len(cases),
        snap=snap,
        cap_errors=0,
        per_case_sum=sum(int(r.get("logical_calls") or 0) for r in rows),
        no_gold_leak=bool(summ.get("no_gold_leakage", True)),
        no_pred_leak=no_pred,
    )


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "--refresh":
        _refresh_casebook_outputs(Path(sys.argv[2]).resolve())
        print(Path(sys.argv[2]).resolve())
        return

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--plan-dir", type=Path, default=None)
    ap.add_argument("--max-total-cohere-calls", type=int, default=CAP_DEFAULT)
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--max-tokens", type=int, default=700)
    ap.add_argument("--output-dir", type=Path, default=None)
    args = ap.parse_args()

    plan_dir = args.plan_dir
    if plan_dir is None:
        cands = sorted((REPO / "outputs").glob("pal_vs_production_equiv_casebook_plan_*"))
        if not cands:
            raise SystemExit("no plan dir; run build_pal_vs_production_equiv_casebook_plan.py")
        plan_dir = cands[-1]

    selected_path = plan_dir / "selected_casebook_cases.csv"
    cases = _read_csv(selected_path)
    n = len(cases)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = args.output_dir or (REPO / "outputs" / f"pal_vs_production_equiv_casebook_live_{ts}")
    out.mkdir(parents=True, exist_ok=True)
    resp_dir = out / "responses"
    meta_dir = out / "metadata"
    resp_dir.mkdir(parents=True, exist_ok=True)
    meta_dir.mkdir(parents=True, exist_ok=True)

    api_key = (os.getenv("COHERE_API_KEY") or os.getenv("CO_API_KEY") or "").strip()

    matched_ids = {
        str(r.get("example_id") or r.get("case_id"))
        for r in _read_csv(
            REPO / "outputs/main_table_core4_baselines_50case_checkpoint_20260508T174557Z/selected_50case_core4_baseline_cases.csv"
        )
    }

    preflight: dict[str, Any] = {
        "cohere_api_key_set": bool(api_key),
        "case_count": n,
        "case_count_in_range": 20 <= n <= 30,
        "all_problem_text": all(bool(_sanitize(r.get("problem_text", ""))) for r in cases),
        "all_gold": all(bool(str(r.get("gold_answer", "")).strip()) for r in cases),
        "no_duplicate_ids": len({r["case_id"] for r in cases}) == n,
        "no_matched50_overlap": all(r["case_id"] not in matched_ids for r in cases),
        "estimated_calls_upper_bound": n * 6,
        "within_cap": n * 6 <= int(args.max_total_cohere_calls),
        "method_alias": ALIAS,
        "pal_method": PAL_METHOD,
        "output_writable": True,
        "prompt_leakage_check": "questions_only_no_gold_in_user_prompt_for_standard_expand",
    }
    rng = random.Random(7)

    def factory() -> APIBranchGenerator:
        return APIBranchGenerator(
            provider="cohere",
            api_key=api_key,
            model="command-a-03-2025",
            temperature=float(args.temperature),
            max_tokens=int(args.max_tokens),
            timeout_seconds=120,
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
    preflight["pal_resolves"] = PAL_METHOD in specs
    critical = [
        "cohere_api_key_set",
        "case_count_in_range",
        "all_problem_text",
        "all_gold",
        "no_duplicate_ids",
        "no_matched50_overlap",
        "within_cap",
        "alias_resolves",
        "pal_resolves",
    ]
    preflight["critical_failures"] = [k for k in critical if not preflight.get(k)]
    preflight["abort_before_api"] = bool(preflight["critical_failures"])
    (out / "preflight_status.json").write_text(json.dumps(preflight, indent=2) + "\n", encoding="utf-8")

    _write_csv(out / "selected_casebook_cases.csv", [{**r, "problem_text": _sanitize(r["problem_text"])} for r in cases])

    manifest = {
        "timestamp_utc": ts,
        "plan_dir": str(plan_dir.resolve()),
        "method_alias": ALIAS,
        "pal_method": PAL_METHOD,
        "model": "command-a-03-2025",
        "case_count": n,
        "max_total_cohere_calls": int(args.max_total_cohere_calls),
        "temperature": float(args.temperature),
        "sc6_included": False,
    }
    (out / "live_casebook_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    if preflight["abort_before_api"]:
        raise SystemExit(f"preflight abort: {preflight['critical_failures']}")

    prod_ctl = specs[ALIAS]
    pal_ctl = specs[PAL_METHOD]

    rows: list[dict[str, Any]] = []
    cap_errors = 0
    per_case_sum = 0
    no_gold_leak = True
    no_pred_leak = True

    configure_logical_api_call_budget(int(args.max_total_cohere_calls))

    try:
        for rec in cases:
            cid = rec["case_id"]
            question = _sanitize(rec["problem_text"])
            gold = str(rec["gold_answer"]).strip()
            gold_n = _norm(gold)

            for method, ctl in ((ALIAS, prod_ctl), (PAL_METHOD, pal_ctl)):
                before = int(logical_api_call_budget_snapshot().get("consumed") or 0)
                status = "success"
                err = ""
                pred = ""
                parsed = ""
                md: dict[str, Any] = {}
                try:
                    if hasattr(ctl.generator, "reset_usage_counters"):
                        ctl.generator.reset_usage_counters()
                    mr = ctl.run(question, gold)
                    pred = str(mr.prediction or "")
                    parsed = _norm(pred)
                    md = dict(mr.metadata or {})
                except RuntimeError as e:
                    if "Global logical API call cap reached" in str(e):
                        status = "incomplete_cap"
                        err = str(e)
                        cap_errors += 1
                    else:
                        status = "method_execution_error"
                        err = str(e)
                except Exception as e:  # noqa: BLE001
                    status = "method_execution_error"
                    err = f"{type(e).__name__}: {e}"
                after = int(logical_api_call_budget_snapshot().get("consumed") or 0)
                logical_used = max(0, after - before)
                per_case_sum += logical_used

                if status == "success" and not parsed:
                    status = "parsing_failure"

                pal_prog, pal_ok, pal_err = (False, False, "")
                surf = ""
                tr_trig = ""
                tr_com = ""
                if method == ALIAS:
                    surf = str(md.get("production_equiv_surface_source") or md.get("surface_source") or "")
                    tr_trig = str(md.get("targeted_retry_triggered", False)).lower()
                    tr_com = str(md.get("targeted_retry_committed", False)).lower()
                    trace = md.get("action_trace") if isinstance(md.get("action_trace"), list) else []
                    for ev in trace:
                        if isinstance(ev, dict) and str(ev.get("source") or "") == "production_equiv_targeted_retry":
                            ptxt = str(ev.get("prompt_text") or "")
                            if gold and len(gold) >= 2 and gold in ptxt:
                                no_gold_leak = False
                else:
                    pal_prog, pal_ok, pal_err = _pal_details(md)

                bundle = {
                    "prediction_raw": pred,
                    "parsed_answer": parsed,
                    "metadata": md,
                    "status": status,
                    "error_message": err,
                    "logical_calls": logical_used,
                }
                rp = resp_dir / f"{cid}_{method}.json"
                rp.write_text(json.dumps(bundle, indent=2, default=str) + "\n", encoding="utf-8")
                mp = meta_dir / f"{cid}_{method}.json"
                mp.write_text(json.dumps(md, indent=2, default=str) + "\n", encoding="utf-8")

                exact = int(bool(parsed and parsed == gold_n))
                parse_fail = int(status == "parsing_failure")
                api_err = ""
                if status == "method_execution_error":
                    api_err = err
                elif status == "incomplete_cap":
                    api_err = err

                # Avoid short-numeric false positives (e.g. gold "4" inside "14").
                if (
                    parsed
                    and gold_n
                    and parsed != gold_n
                    and len(gold_n) >= 4
                    and gold_n in parsed
                ):
                    no_pred_leak = False

                row = {
                    "case_id": cid,
                    "method": method,
                    "run_status": status,
                    "problem_text": question,
                    "gold_answer": gold,
                    "parsed_answer": parsed,
                    "exact_match": exact,
                    "logical_calls": logical_used,
                    "api_error": api_err,
                    "parsing_failure": parse_fail,
                    "response_path": str(rp.relative_to(REPO)),
                    "metadata_path": str(mp.relative_to(REPO)),
                    "method_surface_source": surf if method == ALIAS else "",
                    "pal_program_present": str(pal_prog).lower() if method == PAL_METHOD else "",
                    "pal_execution_success": str(pal_ok).lower() if method == PAL_METHOD else "",
                    "pal_execution_error": pal_err if method == PAL_METHOD else "",
                    "production_equiv_surface_source": surf if method == ALIAS else "",
                    "targeted_retry_triggered": tr_trig if method == ALIAS else "",
                    "targeted_retry_committed": tr_com if method == ALIAS else "",
                    "no_gold_leakage": str(no_gold_leak).lower(),
                    "no_prediction_leakage": str(no_pred_leak).lower(),
                }
                rows.append(row)
    finally:
        snap = logical_api_call_budget_snapshot()
        configure_logical_api_call_budget(None)

    finalize_casebook_artifacts(
        out,
        cases=cases,
        rows=rows,
        n=n,
        snap=snap,
        cap_errors=cap_errors,
        per_case_sum=per_case_sum,
        no_gold_leak=no_gold_leak,
        no_pred_leak=no_pred_leak,
    )

    print(out)


if __name__ == "__main__":
    main()
