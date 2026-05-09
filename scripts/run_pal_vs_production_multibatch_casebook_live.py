#!/usr/bin/env python3
"""Multi-batch live collection: PAL screen then production_equiv follow-up (bounded logical Cohere calls)."""

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
CAP = 900
SCREEN_BATCH = 50
FOLLOWUP_CAP = 25
TARGET_PAL_ONLY = 30
TARGET_DISAGREEMENT = 50
TARGET_USEFUL = 50
MAX_SCREENED = 300
EST_BATCH_MAX = SCREEN_BATCH + FOLLOWUP_CAP * 4

CASEBOOK_COLS = [
    "case_id",
    "batch_id",
    "problem_text",
    "gold_answer",
    "pal_answer",
    "pal_correct",
    "pal_parsing_failure",
    "pal_api_error",
    "pal_program_present",
    "pal_execution_success",
    "pal_execution_error",
    "production_equiv_answer",
    "production_equiv_correct",
    "production_equiv_parsing_failure",
    "production_equiv_api_error",
    "production_equiv_surface_source",
    "production_equiv_logical_calls",
    "targeted_retry_triggered",
    "targeted_retry_committed",
    "outcome_type",
    "answer_agreement",
    "useful_selector_case",
    "preliminary_family",
    "selector_feature_candidates",
    "response_paths",
    "metadata_paths",
    "notes",
]


def _norm(text: str) -> str:
    return str(normalize_answer_text(text).get("normalized_answer") or "")


def _sanitize(s: str) -> str:
    return " ".join((s or "").replace("\r", " ").replace("\n", " ").split())


def _classify_preliminary(problem: str, pe_ans: str, pa_ans: str, surf: str) -> str:
    t = (problem or "").lower()
    if not pe_ans or not pa_ans:
        return "parse_format"
    if "structural_commit" in (surf or "").lower() and pe_ans != pa_ans:
        return "final_target_mismatch"
    if re.search(r"\b(per hour|mph|percent|%|times (as fast|faster))\b", t):
        return "rate_ratio"
    if re.search(r"\b(before|after|remaining|left)\b", t):
        return "state_update"
    if len(re.findall(r"\d", problem)) >= 8:
        return "multi_step_computation"
    if re.search(r"\b(fraction|half|\d+/\d+)\b", t):
        return "arithmetic_execution"
    return "unknown"


def _pal_details(md: dict[str, Any]) -> tuple[bool, bool, str]:
    pot = md.get("pot_output") if isinstance(md.get("pot_output"), dict) else {}
    code_txt = str(pot.get("python_code") or pot.get("program") or "").strip()
    prog = bool(code_txt) or bool(md.get("code_generated"))
    ok_exec = bool(pot.get("ok")) if isinstance(pot, dict) else False
    if isinstance(pot, dict) and pot.get("exception") is not None:
        ok_exec = False
    err = str(md.get("execution_error") or pot.get("exception") or pot.get("stderr") or "").strip()
    return prog, ok_exec, err[:500]


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def _run_one(
    *,
    cid: str,
    method: str,
    ctl: Any,
    question: str,
    gold: str,
    gold_n: str,
    resp_root: Path,
    meta_root: Path,
) -> dict[str, Any]:
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
        else:
            status = "method_execution_error"
            err = str(e)
    except Exception as e:  # noqa: BLE001
        status = "method_execution_error"
        err = f"{type(e).__name__}: {e}"
    after = int(logical_api_call_budget_snapshot().get("consumed") or 0)
    logical_used = max(0, after - before)
    if status == "success" and not parsed:
        status = "parsing_failure"

    rp = resp_root / f"{cid}.json"
    mp = meta_root / f"{cid}.json"
    bundle = {
        "prediction_raw": pred,
        "parsed_answer": parsed,
        "metadata": md,
        "status": status,
        "error_message": err,
        "logical_calls": logical_used,
    }
    rp.write_text(json.dumps(bundle, indent=2, default=str) + "\n", encoding="utf-8")
    mp.write_text(json.dumps(md, indent=2, default=str) + "\n", encoding="utf-8")

    exact = int(bool(parsed and parsed == gold_n))
    parse_fail = int(status == "parsing_failure")
    api_err = err if status in ("method_execution_error", "incomplete_cap") else ""

    pal_prog, pal_ok, pal_err = (False, False, "")
    surf = ""
    tr_trig = ""
    tr_com = ""
    if method == ALIAS:
        surf = str(md.get("production_equiv_surface_source") or md.get("surface_source") or "")
        tr_trig = str(md.get("targeted_retry_triggered", False)).lower()
        tr_com = str(md.get("targeted_retry_committed", False)).lower()
    elif method == PAL_METHOD:
        pal_prog, pal_ok, pal_err = _pal_details(md)

    return {
        "case_id": cid,
        "method": method,
        "run_status": status,
        "parsed_answer": parsed,
        "exact_match": exact,
        "logical_calls": logical_used,
        "api_error": api_err,
        "parsing_failure": parse_fail,
        "response_path": str(rp.relative_to(REPO)),
        "metadata_path": str(mp.relative_to(REPO)),
        "production_equiv_surface_source": surf if method == ALIAS else "",
        "pal_program_present": str(pal_prog).lower() if method == PAL_METHOD else "",
        "pal_execution_success": str(pal_ok).lower() if method == PAL_METHOD else "",
        "pal_execution_error": pal_err if method == PAL_METHOD else "",
        "targeted_retry_triggered": tr_trig if method == ALIAS else "",
        "targeted_retry_committed": tr_com if method == ALIAS else "",
    }


def _pick_followup(pal_results: list[dict[str, Any]], cap: int) -> list[str]:
    ok_clean: list[str] = []
    bad_clean: list[str] = []
    for r in pal_results:
        cid = r["case_id"]
        if r.get("run_status") != "success":
            continue
        parse_fail = int(r.get("parsing_failure", 0) or 0) == 1
        if parse_fail:
            continue
        ex = int(r.get("exact_match", 0) or 0) == 1
        prog = str(r.get("pal_program_present", "")).lower() == "true"
        okx = str(r.get("pal_execution_success", "")).lower() == "true"
        clean = prog and okx
        if ex and clean:
            ok_clean.append(cid)
        elif not ex and clean:
            bad_clean.append(cid)
    out: list[str] = []
    for cid in ok_clean:
        if len(out) >= cap:
            break
        out.append(cid)
    for cid in bad_clean:
        if len(out) >= cap:
            break
        if cid not in out:
            out.append(cid)
    return out


def _build_cumulative_row(
    *,
    batch_id: int,
    rec: dict[str, str],
    pal_r: dict[str, Any],
    pr: dict[str, Any],
    no_gold_note: str,
) -> dict[str, Any]:
    question = _sanitize(rec["problem_text"])
    gold = str(rec["gold_answer"]).strip()
    gold_n = _norm(gold)
    pa = str(pal_r.get("parsed_answer", ""))
    pe = str(pr.get("parsed_answer", ""))
    pa_ok = int(pal_r.get("exact_match", 0) or 0) == 1
    pe_ok = int(pr.get("exact_match", 0) or 0) == 1
    pal_parse_fail = int(pal_r.get("parsing_failure", 0) or 0) == 1
    pe_parse_fail = int(pr.get("parsing_failure", 0) or 0) == 1
    pal_api = str(pal_r.get("api_error") or "")
    pe_api = str(pr.get("api_error") or "")
    if pal_r.get("run_status") == "incomplete_cap":
        pal_api = pal_api or "cap"
    if pr.get("run_status") == "incomplete_cap":
        pe_api = pe_api or "cap"

    api_issue = bool(pal_api) or bool(pe_api) or pal_r.get("run_status") != "success" or pr.get("run_status") != "success"
    parse_issue = (pal_parse_fail or pe_parse_fail) and (not pa or not pe)

    if api_issue or parse_issue:
        outcome = "parse_or_api_issue"
    elif pe_ok and pa_ok and pe == pa:
        outcome = "both_correct_same"
    elif pe_ok and pa_ok:
        outcome = "both_correct_different"
    elif pa_ok and not pe_ok:
        outcome = "pal_only"
    elif pe_ok and not pa_ok:
        outcome = "production_only"
    elif pe == pa:
        outcome = "both_wrong_same"
    else:
        outcome = "both_wrong_different"

    agree = bool(pa == pe and pa)
    pal_clean = (
        pal_r.get("run_status") == "success"
        and not pal_parse_fail
        and str(pal_r.get("pal_program_present", "")).lower() == "true"
        and str(pal_r.get("pal_execution_success", "")).lower() == "true"
    )
    pe_clean = pr.get("run_status") == "success" and not pe_parse_fail and bool(pe)

    useful = outcome in ("pal_only", "production_only") or (outcome == "both_wrong_different" and pal_clean and pe_clean)

    surf = str(pr.get("production_equiv_surface_source", ""))
    fam = _classify_preliminary(question, pe, pa, surf)

    feats: list[str] = []
    if pal_clean:
        feats.append("pal_clean_execution")
    if pal_r.get("run_status") == "success" and pa and not pal_parse_fail:
        feats.append("pal_parse_confident")
    if "structural_commit" in surf:
        feats.append("production_structural_commit")
    if agree:
        feats.append("answer_agreement")
    if pa.isdigit() and pe.isdigit() and pa != pe:
        feats.append("numeric_outlier")
    if re.search(r"\b(how many|total|left|remaining)\b", question.lower()):
        feats.append("target_quantity_cue")

    return {
        "case_id": rec["case_id"],
        "batch_id": str(batch_id),
        "problem_text": question,
        "gold_answer": gold,
        "pal_answer": pa,
        "pal_correct": str(int(pa_ok)),
        "pal_parsing_failure": str(int(pal_parse_fail)),
        "pal_api_error": pal_api,
        "pal_program_present": str(pal_r.get("pal_program_present", "")),
        "pal_execution_success": str(pal_r.get("pal_execution_success", "")),
        "pal_execution_error": str(pal_r.get("pal_execution_error", "")),
        "production_equiv_answer": pe,
        "production_equiv_correct": str(int(pe_ok)),
        "production_equiv_parsing_failure": str(int(pe_parse_fail)),
        "production_equiv_api_error": pe_api,
        "production_equiv_surface_source": surf,
        "production_equiv_logical_calls": str(pr.get("logical_calls", "")),
        "targeted_retry_triggered": str(pr.get("targeted_retry_triggered", "")),
        "targeted_retry_committed": str(pr.get("targeted_retry_committed", "")),
        "outcome_type": outcome,
        "answer_agreement": str(agree).lower(),
        "useful_selector_case": str(useful).lower(),
        "preliminary_family": fam,
        "selector_feature_candidates": "|".join(feats),
        "response_paths": f"{pal_r.get('response_path','')}|{pr.get('response_path','')}",
        "metadata_paths": f"{pal_r.get('metadata_path','')}|{pr.get('metadata_path','')}",
        "notes": no_gold_note,
    }


def _summarize(
    cumulative: list[dict[str, Any]],
    screened: int,
    pal_screen_rows: list[dict[str, Any]],
    snap: dict[str, Any],
    cap_errors: int,
    per_case_sum: int,
    stop_reason: str,
    eligible_remaining: int,
    no_gold: bool,
    no_pred: bool,
) -> dict[str, Any]:
    pal_only = sum(1 for r in cumulative if r["outcome_type"] == "pal_only")
    prod_only = sum(1 for r in cumulative if r["outcome_type"] == "production_only")
    disagree = sum(
        1
        for r in cumulative
        if r["pal_answer"] != r["production_equiv_answer"] and (r["pal_answer"] or r["production_equiv_answer"])
    )
    useful = sum(1 for r in cumulative if r.get("useful_selector_case") == "true")
    both_ok = sum(1 for r in cumulative if r["outcome_type"] in ("both_correct_same", "both_correct_different"))
    both_bad = sum(1 for r in cumulative if r["outcome_type"] in ("both_wrong_same", "both_wrong_different"))
    both_wrong_diff = sum(1 for r in cumulative if r["outcome_type"] == "both_wrong_different")

    fam_pal = Counter(r["preliminary_family"] for r in cumulative if r["outcome_type"] == "pal_only")
    fam_prod = Counter(r["preliminary_family"] for r in cumulative if r["outcome_type"] == "production_only")
    fam_dis = Counter(
        r["preliminary_family"]
        for r in cumulative
        if r["pal_answer"] != r["production_equiv_answer"] and (r["pal_answer"] or r["production_equiv_answer"])
    )
    feat_c: Counter[str] = Counter()
    for r in cumulative:
        for p in (r.get("selector_feature_candidates") or "").split("|"):
            if p:
                feat_c[p] += 1

    pal_scr_ok = sum(1 for r in pal_screen_rows if int(r.get("exact_match", 0) or 0) == 1)
    pal_scr_clean = sum(
        1
        for r in pal_screen_rows
        if r.get("run_status") == "success"
        and str(r.get("pal_execution_success", "")).lower() == "true"
        and str(r.get("pal_program_present", "")).lower() == "true"
    )
    pe_follow_ok = sum(1 for r in cumulative if r["production_equiv_correct"] == "1")
    pal_follow_ok = sum(1 for r in cumulative if r["pal_correct"] == "1")

    acct = compute_call_accounting(
        completed_rows=len([r for r in pal_screen_rows if r.get("run_status") == "success"])
        + len([r for r in cumulative if r]),
        total_rows=len(pal_screen_rows) + len(cumulative) * 2,
        cap_error_count=cap_errors,
        per_case_calls_sum=per_case_sum,
        budget_snapshot=snap,
    )
    calls = int(acct.actual_cohere_calls_run_level)

    enough_pal = pal_only >= TARGET_PAL_ONLY
    enough_dis = disagree >= TARGET_DISAGREEMENT
    enough_useful = useful >= TARGET_USEFUL

    if enough_pal and enough_dis:
        rec_next = "design_pal_hybrid_selector"
    elif screened >= MAX_SCREENED and not enough_dis:
        rec_next = "stop_if_no_pattern_after_300_screened"
    elif eligible_remaining < SCREEN_BATCH and not enough_dis:
        rec_next = "relax_sampling_strategy"
    elif not enough_pal and not enough_dis:
        rec_next = "continue_collection"
    else:
        rec_next = "continue_collection"

    return {
        "screened_cases": screened,
        "followup_cases": len(cumulative),
        "actual_cohere_calls_run_level": calls,
        "effective_call_cap": CAP,
        "cap_reached": bool(snap.get("budget") is not None and calls >= int(snap.get("budget") or CAP)),
        "eligible_cases_remaining": eligible_remaining,
        "pal_screen_correct_count": pal_scr_ok,
        "pal_screen_clean_execution_count": pal_scr_clean,
        "production_equiv_correct_on_followup": pe_follow_ok,
        "pal_correct_on_followup": pal_follow_ok,
        "pal_only_count": pal_only,
        "production_only_count": prod_only,
        "both_correct_count": both_ok,
        "both_wrong_count": both_bad,
        "both_wrong_different_count": both_wrong_diff,
        "disagreement_count": disagree,
        "useful_selector_case_count": useful,
        "pal_only_family_counts": dict(fam_pal),
        "production_only_family_counts": dict(fam_prod),
        "disagreement_family_counts": dict(fam_dis),
        "selector_feature_counts": dict(feat_c),
        "external_oracle_style_advantage_count": 0,
        "external_oracle_style_advantage_derivable_without_extra_methods": False,
        "enough_pal_only_cases_for_pattern_analysis": enough_pal,
        "enough_disagreement_cases_for_selector_design": enough_dis,
        "enough_useful_selector_cases": enough_useful,
        "stop_reason": stop_reason,
        "recommended_next_step": rec_next,
        "no_gold_leakage": bool(no_gold),
        "no_prediction_leakage": bool(no_pred),
        "call_accounting_warning": acct.call_accounting_warning,
    }


def finalize_from_csv(out: Path, *, plan_dir: Path, stop_reason: str = "finalize_after_crash") -> int:
    """Rebuild summary / memos / reports from CSVs (e.g. after a crash post-collection)."""
    pal_all = list(csv.DictReader((out / "pal_screen_results_all.csv").open(encoding="utf-8")))
    prod_all = list(csv.DictReader((out / "production_followup_results_all.csv").open(encoding="utf-8")))
    cumulative = list(csv.DictReader((out / "cumulative_pal_vs_prod_casebook.csv").open(encoding="utf-8")))
    by_cumulative = {r["case_id"]: r for r in cumulative}
    screened_ids = {r["case_id"] for r in pal_all}
    pool_path = plan_dir / "candidate_pool_inventory.csv"
    pool = [r for r in csv.DictReader(pool_path.open(encoding="utf-8")) if r.get("eligible_for_multibatch_loop") == "yes"]
    pool_by_id = {r["case_id"]: r for r in pool}
    ordered = sorted(pool_by_id.keys(), key=lambda x: (int(x.split("_")[-1]) if x.split("_")[-1].isdigit() else 0, x))
    eligible_rem = len([i for i in ordered if i not in screened_ids])
    eff_stop = stop_reason
    if stop_reason == "finalize_after_crash" and eligible_rem == 0 and len(screened_ids) > 0:
        eff_stop = "no_eligible_cases_remain"
    per_sum = sum(int(r.get("logical_calls") or 0) for r in pal_all) + sum(int(r.get("logical_calls") or 0) for r in prod_all)
    consumed = max(per_sum, int(logical_api_call_budget_snapshot().get("consumed") or 0))
    snap = {"budget": CAP, "consumed": consumed}
    no_gold = True
    no_pred = True
    for pr in prod_all:
        if pr.get("run_status") != "success":
            continue
        mp = REPO / pr["metadata_path"]
        if not mp.is_file():
            continue
        md = json.load(mp.open(encoding="utf-8"))
        cid = pr["case_id"]
        rec = by_cumulative.get(cid, {})
        gold = str(rec.get("gold_answer", "")).strip()
        trace = md.get("action_trace") if isinstance(md.get("action_trace"), list) else []
        for ev in trace:
            if isinstance(ev, dict) and str(ev.get("source") or "") == "production_equiv_targeted_retry":
                ptxt = str(ev.get("prompt_text") or "")
                if gold and len(gold) >= 2 and gold in ptxt:
                    no_gold = False
        pe = str(pr.get("parsed_answer", ""))
        gold_n = _norm(gold)
        if pe and gold_n and pe != gold_n and len(gold_n) >= 4 and gold_n in pe:
            no_pred = False

    summary = _summarize(
        cumulative,
        screened=len(screened_ids),
        pal_screen_rows=pal_all,
        snap=snap,
        cap_errors=0,
        per_case_sum=per_sum,
        stop_reason=eff_stop,
        eligible_remaining=eligible_rem,
        no_gold=no_gold,
        no_pred=no_pred,
    )
    (out / "cumulative_casebook_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    report = "\n".join(
        [
            "# PAL vs production_equiv multi-batch live loop (finalized from CSV)",
            f"- stop_reason: **{eff_stop}**",
            f"- screened_cases: **{summary['screened_cases']}**",
            f"- followup_cases: **{summary['followup_cases']}**",
            f"- actual_cohere_calls_run_level: **{summary['actual_cohere_calls_run_level']}** / {CAP}",
            f"- pal_only: **{summary['pal_only_count']}**; disagreement: **{summary['disagreement_count']}**",
            f"- recommended_next_step: **{summary['recommended_next_step']}**",
        ]
    )
    (out / "live_loop_report.md").write_text(report + "\n", encoding="utf-8")
    memo = "\n".join(
        [
            "# PAL-hybrid selector — data collection memo",
            "",
            f"- **PAL-only:** {summary['pal_only_count']} (target {TARGET_PAL_ONLY})",
            f"- **Production-only:** {summary['production_only_count']}",
            f"- **Disagreements (parsed answer differ):** {summary['disagreement_count']} (target {TARGET_DISAGREEMENT})",
            f"- **Useful selector cases:** {summary['useful_selector_case_count']}",
            f"- **Thresholds reached:** pal_only={summary['enough_pal_only_cases_for_pattern_analysis']}, "
            f"disagreement={summary['enough_disagreement_cases_for_selector_design']}, "
            f"useful={summary['enough_useful_selector_cases']}",
            "",
            "## Note",
            "- This directory was **finalized from disk** after an interrupted run; call totals are reconstructed from per-row `logical_calls` sums.",
        ]
    )
    (out / "pal_hybrid_selector_data_memo.md").write_text(memo + "\n", encoding="utf-8")
    print(out)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--plan-dir", type=Path, default=None)
    ap.add_argument("--output-dir", type=Path, default=None)
    ap.add_argument(
        "--finalize-only",
        action="store_true",
        help="Rebuild summary/report/memo from existing CSVs in --output-dir (no API).",
    )
    args = ap.parse_args()

    if args.finalize_only:
        if not args.output_dir:
            raise SystemExit("--output-dir required with --finalize-only")
        plan_dir = args.plan_dir
        if plan_dir is None:
            cands = sorted((REPO / "outputs").glob("pal_vs_production_multibatch_casebook_plan_*"))
            if not cands:
                raise SystemExit("no plan dir for finalize-only")
            plan_dir = cands[-1]
        return finalize_from_csv(args.output_dir.resolve(), plan_dir=plan_dir.resolve())

    plan_dir = args.plan_dir
    if plan_dir is None:
        cands = sorted((REPO / "outputs").glob("pal_vs_production_multibatch_casebook_plan_*"))
        if not cands:
            raise SystemExit("no multibatch plan dir; run build_pal_vs_production_multibatch_casebook_plan.py")
        plan_dir = cands[-1]

    pool_path = plan_dir / "candidate_pool_inventory.csv"
    if not pool_path.is_file():
        raise SystemExit(f"missing {pool_path}")

    pool = [r for r in csv.DictReader(pool_path.open(encoding="utf-8")) if r.get("eligible_for_multibatch_loop") == "yes"]
    pool_by_id = {r["case_id"]: r for r in pool}
    ordered = sorted(pool_by_id.keys(), key=lambda x: (int(x.split("_")[-1]) if x.split("_")[-1].isdigit() else 0, x))

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = args.output_dir or (REPO / "outputs" / f"pal_vs_production_multibatch_casebook_live_{ts}")
    out.mkdir(parents=True, exist_ok=True)
    (out / "responses" / "pal").mkdir(parents=True, exist_ok=True)
    (out / "metadata" / "pal").mkdir(parents=True, exist_ok=True)
    (out / "responses" / "production_equiv").mkdir(parents=True, exist_ok=True)
    (out / "metadata" / "production_equiv").mkdir(parents=True, exist_ok=True)

    api_key = (os.getenv("COHERE_API_KEY") or os.getenv("CO_API_KEY") or "").strip()
    manifest_plan = json.load((plan_dir / "multibatch_plan_manifest.json").open(encoding="utf-8"))
    pool_size = int(manifest_plan.get("candidate_pool_size") or len(ordered))

    preflight: dict[str, Any] = {
        "cohere_api_key_set": bool(api_key),
        "candidate_pool_size": pool_size,
        "pool_eligible_loaded": len(ordered),
        "all_problem_text": all(bool(_sanitize(pool_by_id[i].get("problem_text", ""))) for i in ordered),
        "all_gold": all(bool(str(pool_by_id[i].get("gold_answer", "")).strip()) for i in ordered),
        "no_duplicate_ids": len(ordered) == len(set(ordered)),
        "estimated_first_batch_calls_upper_bound": EST_BATCH_MAX,
        "first_batch_within_200": EST_BATCH_MAX <= 200,
        "method_alias_resolves": False,
        "pal_method_resolves": False,
        "output_writable": True,
        "planned_max_actual_calls": CAP,
    }

    rng = random.Random(11)

    def factory() -> APIBranchGenerator:
        return APIBranchGenerator(
            provider="cohere",
            api_key=api_key,
            model="command-a-03-2025",
            temperature=0.0,
            max_tokens=700,
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
    preflight["method_alias_resolves"] = ALIAS in specs
    preflight["pal_method_resolves"] = PAL_METHOD in specs
    critical = [
        "cohere_api_key_set",
        "all_problem_text",
        "all_gold",
        "no_duplicate_ids",
        "first_batch_within_200",
        "method_alias_resolves",
        "pal_method_resolves",
    ]
    preflight["pool_size_ok"] = len(ordered) >= 30
    if not preflight["pool_size_ok"]:
        critical.append("pool_size_ok")

    preflight["critical_failures"] = [k for k in critical if not preflight.get(k)]
    preflight["abort_before_api"] = bool(preflight["critical_failures"])
    (out / "preflight_status.json").write_text(json.dumps(preflight, indent=2) + "\n", encoding="utf-8")

    (out / "live_loop_manifest.json").write_text(
        json.dumps(
            {
                "timestamp_utc": ts,
                "plan_dir": str(plan_dir.resolve()),
                "method_alias": ALIAS,
                "pal_method": PAL_METHOD,
                "cap": CAP,
                "screen_batch": SCREEN_BATCH,
                "followup_cap": FOLLOWUP_CAP,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    batch_log: list[dict[str, Any]] = []
    pal_all: list[dict[str, Any]] = []
    prod_all: list[dict[str, Any]] = []
    cumulative: list[dict[str, Any]] = []

    if preflight["abort_before_api"]:
        summary = _summarize(
            cumulative,
            screened=0,
            pal_screen_rows=[],
            snap={"budget": CAP, "consumed": 0},
            cap_errors=0,
            per_case_sum=0,
            stop_reason="preflight_abort",
            eligible_remaining=len(ordered),
            no_gold=True,
            no_pred=True,
        )
        summary["recommended_next_step"] = "fix_preflight_then_rerun"
        _write_csv(out / "batch_log.csv", batch_log, ["batch_id", "pal_screened", "followup_n", "calls_end", "notes"])
        _write_csv(out / "pal_screen_results_all.csv", pal_all, ["case_id"])
        _write_csv(out / "production_followup_results_all.csv", prod_all, ["case_id"])
        _write_csv(out / "cumulative_pal_vs_prod_casebook.csv", cumulative, CASEBOOK_COLS)
        (out / "cumulative_casebook_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        (out / "live_loop_report.md").write_text("# Aborted at preflight\n", encoding="utf-8")
        (out / "pal_hybrid_selector_data_memo.md").write_text("# No live data (preflight abort)\n", encoding="utf-8")
        print(out)
        return 1

    prod_ctl = specs[ALIAS]
    pal_ctl = specs[PAL_METHOD]
    screened_ids: set[str] = set()
    no_gold_leak = True
    no_pred_leak = True
    cap_errors = 0
    per_case_sum = 0
    stop_reason = "running"
    configure_logical_api_call_budget(CAP)
    snap: dict[str, Any] = {}
    batch_id = 0

    try:
        while True:
            batch_id += 1
            calls_before = int(logical_api_call_budget_snapshot().get("consumed") or 0)
            remaining_ids = [i for i in ordered if i not in screened_ids]
            eligible_remaining = len(remaining_ids)
            if eligible_remaining == 0:
                stop_reason = "no_eligible_cases_remain"
                break
            if calls_before + EST_BATCH_MAX > CAP:
                stop_reason = "would_exceed_cap_before_next_batch"
                break

            take = min(SCREEN_BATCH, len(remaining_ids), MAX_SCREENED - len(screened_ids))
            if take <= 0:
                stop_reason = "max_screened_cases"
                break

            batch_ids = remaining_ids[:take]
            pal_batch_results: list[dict[str, Any]] = []

            cap_hit = False
            for cid in batch_ids:
                rec = pool_by_id[cid]
                question = _sanitize(rec["problem_text"])
                gold = str(rec["gold_answer"]).strip()
                gold_n = _norm(gold)
                pal_r = _run_one(
                    cid=cid,
                    method=PAL_METHOD,
                    ctl=pal_ctl,
                    question=question,
                    gold=gold,
                    gold_n=gold_n,
                    resp_root=out / "responses" / "pal",
                    meta_root=out / "metadata" / "pal",
                )
                pal_r["batch_id"] = str(batch_id)
                pal_batch_results.append(pal_r)
                pal_all.append(pal_r)
                per_case_sum += int(pal_r.get("logical_calls") or 0)
                screened_ids.add(cid)

                md_path = REPO / pal_r["metadata_path"]
                if md_path.is_file():
                    md = json.load(md_path.open(encoding="utf-8"))
                    prog, okx, _e = _pal_details(md)
                    pal_r["pal_program_present"] = str(prog).lower()
                    pal_r["pal_execution_success"] = str(okx).lower()
                    pal_r["pal_execution_error"] = _e
                if pal_r.get("run_status") == "incomplete_cap":
                    cap_hit = True
                    cap_errors += 1
                    break
            if cap_hit:
                stop_reason = "max_actual_calls"
                break

            screened_total = len(screened_ids)
            follow_ids = _pick_followup(pal_batch_results, FOLLOWUP_CAP)

            cap_hit_prod = False
            for cid in follow_ids:
                rec = pool_by_id[cid]
                question = _sanitize(rec["problem_text"])
                gold = str(rec["gold_answer"]).strip()
                gold_n = _norm(gold)
                pal_r = next(x for x in pal_batch_results if x["case_id"] == cid)
                pr = _run_one(
                    cid=cid,
                    method=ALIAS,
                    ctl=prod_ctl,
                    question=question,
                    gold=gold,
                    gold_n=gold_n,
                    resp_root=out / "responses" / "production_equiv",
                    meta_root=out / "metadata" / "production_equiv",
                )
                pr["batch_id"] = str(batch_id)
                prod_all.append(pr)
                per_case_sum += int(pr.get("logical_calls") or 0)
                if pr.get("run_status") == "incomplete_cap":
                    cap_hit_prod = True
                    cap_errors += 1
                    break

                if pr.get("run_status") == "success":
                    md = json.load((REPO / pr["metadata_path"]).open(encoding="utf-8"))
                    trace = md.get("action_trace") if isinstance(md.get("action_trace"), list) else []
                    for ev in trace:
                        if isinstance(ev, dict) and str(ev.get("source") or "") == "production_equiv_targeted_retry":
                            ptxt = str(ev.get("prompt_text") or "")
                            if gold and len(gold) >= 2 and gold in ptxt:
                                no_gold_leak = False
                pe = str(pr.get("parsed_answer", ""))
                pa = str(pal_r.get("parsed_answer", ""))
                if pe and gold_n and pe != gold_n and len(gold_n) >= 4 and gold_n in pe:
                    no_pred_leak = False

                row = _build_cumulative_row(
                    batch_id=batch_id,
                    rec=rec,
                    pal_r=pal_r,
                    pr=pr,
                    no_gold_note="gold-free prompts: question-only to standard expand; gold used only for scoring.",
                )
                cumulative.append(row)
            if cap_hit_prod:
                stop_reason = "max_actual_calls"
                break

            calls_after = int(logical_api_call_budget_snapshot().get("consumed") or 0)
            batch_log.append(
                {
                    "batch_id": str(batch_id),
                    "pal_screened": str(len(batch_ids)),
                    "followup_n": str(len(follow_ids)),
                    "calls_end": str(calls_after),
                    "notes": f"screened_total={screened_total}",
                }
            )

            pal_only = sum(1 for r in cumulative if r["outcome_type"] == "pal_only")
            disagree = sum(
                1
                for r in cumulative
                if r["pal_answer"] != r["production_equiv_answer"] and (r["pal_answer"] or r["production_equiv_answer"])
            )
            useful = sum(1 for r in cumulative if r.get("useful_selector_case") == "true")
            calls_now = calls_after

            if pal_only >= TARGET_PAL_ONLY:
                stop_reason = "pal_only_threshold"
                break
            if disagree >= TARGET_DISAGREEMENT:
                stop_reason = "disagreement_threshold"
                break
            if useful >= TARGET_USEFUL:
                stop_reason = "useful_selector_case_threshold"
                break
            if screened_total >= MAX_SCREENED:
                stop_reason = "max_screened_cases"
                break
            if calls_now >= CAP:
                stop_reason = "max_actual_calls"
                break
            if len([i for i in ordered if i not in screened_ids]) == 0:
                stop_reason = "no_eligible_cases_remain"
                break

    finally:
        snap = logical_api_call_budget_snapshot()
        configure_logical_api_call_budget(None)

    _write_csv(out / "batch_log.csv", batch_log, list(batch_log[0].keys()) if batch_log else ["batch_id"])
    pal_fields = sorted({k for r in pal_all for k in r}) if pal_all else ["case_id", "method", "run_status"]
    _write_csv(out / "pal_screen_results_all.csv", pal_all, pal_fields)
    prod_fields = sorted({k for r in prod_all for k in r}) if prod_all else pal_fields
    _write_csv(out / "production_followup_results_all.csv", prod_all, prod_fields)
    _write_csv(out / "cumulative_pal_vs_prod_casebook.csv", cumulative, CASEBOOK_COLS)

    eligible_rem = len([i for i in ordered if i not in screened_ids])
    summary = _summarize(
        cumulative,
        screened=len(screened_ids),
        pal_screen_rows=pal_all,
        snap={"budget": CAP, "consumed": int(snap.get("consumed") or 0)},
        cap_errors=cap_errors,
        per_case_sum=per_case_sum,
        stop_reason=stop_reason,
        eligible_remaining=eligible_rem,
        no_gold=no_gold_leak,
        no_pred=no_pred_leak,
    )
    (out / "cumulative_casebook_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    report = "\n".join(
        [
            "# PAL vs production_equiv multi-batch live loop",
            f"- stop_reason: **{stop_reason}**",
            f"- screened_cases: **{summary['screened_cases']}**",
            f"- followup_cases: **{summary['followup_cases']}**",
            f"- actual_cohere_calls_run_level: **{summary['actual_cohere_calls_run_level']}** / {CAP}",
            f"- pal_only: **{summary['pal_only_count']}**; disagreement: **{summary['disagreement_count']}**",
            f"- recommended_next_step: **{summary['recommended_next_step']}**",
        ]
    )
    (out / "live_loop_report.md").write_text(report + "\n", encoding="utf-8")

    memo = "\n".join(
        [
            "# PAL-hybrid selector — data collection memo",
            "",
            f"- **PAL-only:** {summary['pal_only_count']} (target {TARGET_PAL_ONLY})",
            f"- **Production-only:** {summary['production_only_count']}",
            f"- **Disagreements (parsed answer differ):** {summary['disagreement_count']} (target {TARGET_DISAGREEMENT})",
            f"- **Useful selector cases:** {summary['useful_selector_case_count']}",
            f"- **Thresholds reached:** pal_only={summary['enough_pal_only_cases_for_pattern_analysis']}, "
            f"disagreement={summary['enough_disagreement_cases_for_selector_design']}, "
            f"useful={summary['enough_useful_selector_cases']}",
            "",
            "## PAL strengths (early read)",
            "- Clean code execution + numeric extraction on arithmetic-heavy word problems.",
            "",
            "## production_equiv strengths",
            "- Wins when structural_commit surface aligns; contrast rows in production_only families.",
            "",
            "## Gold-free selector features",
            "- `selector_feature_candidates` column lists offline-usable cues (exec success, agreement, structural_commit).",
            "",
            "## Enough for production_equiv_v2_pal_hybrid?",
            f"- Pattern-analysis gate (pal_only≥30): **{summary['enough_pal_only_cases_for_pattern_analysis']}**",
            f"- Selector-design gate (disagreement≥50): **{summary['enough_disagreement_cases_for_selector_design']}**",
            "",
            "## If insufficient",
            "- Relax exclusions only with explicit overlap report; widen pool beyond `all_casebook.csv` second tranche; increase SCREEN_BATCH only after cap review.",
            "",
            "## Caveats",
            "- Biased by GSM8K-style pool and sequential ID ordering; API cost scales with screened×PAL + followup×production logical calls.",
        ]
    )
    (out / "pal_hybrid_selector_data_memo.md").write_text(memo + "\n", encoding="utf-8")

    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
