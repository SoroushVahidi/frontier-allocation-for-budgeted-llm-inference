#!/usr/bin/env python3
"""Materialize 30-case PAL vs three external baselines pilot artifacts (post-run, no API)."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

PAL = "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal"
EXT_L1 = "external_l1_max"
EXT_TALE = "external_tale_prompt_budgeting"
EXT_S1 = "external_s1_budget_forcing"
EXT_ORDER = [EXT_L1, EXT_TALE, EXT_S1]


def _j(x: Any) -> str:
    try:
        return json.dumps(x, ensure_ascii=False)
    except Exception:
        return ""


def actions_used(md: dict[str, Any]) -> Any:
    v = md.get("actions_used")
    if v is not None:
        return v
    pe = md.get("pal_execution") or {}
    if isinstance(pe, dict) and pe.get("frontier_budget_after_pal") is not None:
        return md.get("budget_actions_used")
    return md.get("frontier_actions_used") or md.get("direct_actions_used") or ""


def budget_exhausted_flag(md: dict[str, Any], row: dict[str, Any]) -> int:
    rr = str(md.get("route_reason") or md.get("override_reason") or "")
    if "budget" in rr.lower() and "exhaust" in rr.lower():
        return 1
    if md.get("budget_error_tokens") is not None and float(md.get("budget_error_tokens") or 0) <= 0:
        pass
    return int(bool(md.get("token_budget_violation"))) if md.get("token_budget_violation") is not None else 0


def operation_hints_heuristic(question: str) -> str:
    q = (question or "").lower()
    tags: list[str] = []
    if re.search(r"\bper\b|/hour|/ day|mph|rate", q):
        tags.append("rate_ratio")
    if re.search(r"\bday\b|\bweek\b|\byear\b|before|after|ago", q):
        tags.append("temporal_change")
    if re.search(r"difference|more than|less than|remain", q):
        tags.append("difference")
    return "|".join(sorted(set(tags))) if tags else ""


def quantity_bucket(count: int) -> str:
    if count <= 1:
        return "qnum_0_1"
    if count <= 3:
        return "qnum_2_3"
    if count <= 5:
        return "qnum_4_5"
    return "qnum_6p"


def numeric_qty(question: str) -> int:
    return len(re.findall(r"\b\d+(?:\.\d+)?\b", question or ""))


def len_bucket(q: str) -> str:
    n = len((q or "").split())
    if n < 80:
        return "len_medium"
    return "len_long"


def best_external_for_case(ext: dict[str, int]) -> tuple[int, str]:
    """Return (correct_bool, method_name or ''). Preference order EXT_ORDER."""
    for m in EXT_ORDER:
        if ext.get(m):
            return 1, m
    return 0, ""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("bundle_dir", type=Path, help="Pilot output directory (contains per_example_records.jsonl)")
    ap.add_argument("--call-plan-estimate-total", type=int, default=400)
    args = ap.parse_args()
    bd: Path = args.bundle_dir.resolve()
    jsonl_path = bd / "per_example_records.jsonl"
    rows = [json.loads(x) for x in jsonl_path.read_text(encoding="utf-8").splitlines() if x.strip()]

    by_case: dict[str, dict[str, dict[str, Any]]] = {}
    for r in rows:
        if int(r.get("scored", 0)) != 1:
            continue
        eid = str(r["example_id"])
        by_case.setdefault(eid, {})[str(r["method"])] = r

    case_ids = sorted(by_case.keys())
    if len(case_ids) != 30:
        print(f"WARNING: expected 30 distinct cases, got {len(case_ids)}", file=sys.stderr)

    # --- results.jsonl ---
    results_path = bd / "results.jsonl"
    with results_path.open("w", encoding="utf-8") as out:
        for r in rows:
            if int(r.get("scored", 0)) != 1:
                continue
            md = dict(r.get("result_metadata") or {})
            ext_md = {k: md.get(k) for k in md if str(k).startswith("external_") or k in ("l1_control_mode", "final_score")}
            palx = md.get("pal_execution") or {}
            retryx = {
                "pal_empty_code_retry_ran": (md.get("pal_retry") or {}).get("pal_empty_code_retry_ran")
                if isinstance(md.get("pal_retry"), dict)
                else md.get("pal_empty_code_retry_ran"),
            }
            row_out = {
                "example_id": r.get("example_id"),
                "case_id": r.get("example_id"),
                "method": r.get("method"),
                "question": r.get("question"),
                "gold_answer": r.get("gold_answer"),
                "predicted_answer": r.get("final_answer_raw"),
                "exact_match": int(r.get("exact_match") or 0),
                "normalized_predicted_answer": r.get("final_answer_canonical"),
                "normalized_gold_answer": r.get("gold_answer_canonical"),
                "parse_extraction_failure": int(r.get("parse_extraction_failure") or 0),
                "actions_used": actions_used(md),
                "budget_exhausted": budget_exhausted_flag(md, r),
                "raw_final_output": r.get("final_answer_raw"),
                "final_nodes": r.get("final_nodes"),
                "action_trace": md.get("action_trace"),
                "final_branch_states": md.get("final_branch_states"),
                "branch_states": md.get("branch_states"),
                "direct_reserve_attempts": md.get("direct_reserve_attempts"),
                "selector_candidate_pool": md.get("selector_candidate_pool"),
                "pal_execution": palx if isinstance(palx, dict) else {},
                "pal_retry": md.get("pal_retry") if isinstance(md.get("pal_retry"), dict) else {},
                "overlay_metadata": md.get("overlay_metadata"),
                "tiebreak_metadata": {
                    "frontier_tiebreak_triggered": md.get("frontier_tiebreak_triggered"),
                    "selected_group": md.get("selected_group"),
                },
                "external_baseline_metadata": ext_md if str(r.get("method")).startswith("external_") else {},
                "cohere_logical_api_calls": int(r.get("cohere_logical_api_calls") or 0),
                "failure_tag": r.get("failure_tag"),
                "status": r.get("status"),
                "result_metadata_full": md,
            }
            out.write(json.dumps(row_out, ensure_ascii=False) + "\n")

    # --- paired_casebook.csv ---
    paired_rows: list[dict[str, Any]] = []
    for eid in case_ids:
        blk = by_case[eid]
        r0 = blk.get(PAL) or next(iter(blk.values()))
        q = str(r0.get("question") or "")
        gold = str(r0.get("gold_answer") or "")
        pal_r = blk.get(PAL, {})
        ex = {
            EXT_L1: blk.get(EXT_L1, {}),
            EXT_TALE: blk.get(EXT_TALE, {}),
            EXT_S1: blk.get(EXT_S1, {}),
        }
        pa = str(pal_r.get("final_answer_raw") or "")
        pal_ok = int(pal_r.get("exact_match") or 0)
        a1 = str(ex[EXT_L1].get("final_answer_raw") or "")
        ok1 = int(ex[EXT_L1].get("exact_match") or 0)
        a2 = str(ex[EXT_TALE].get("final_answer_raw") or "")
        ok2 = int(ex[EXT_TALE].get("exact_match") or 0)
        a3 = str(ex[EXT_S1].get("final_answer_raw") or "")
        ok3 = int(ex[EXT_S1].get("exact_match") or 0)

        wins: list[str] = []
        lose: list[str] = []
        if pal_ok:
            wins.append(PAL)
        else:
            lose.append(PAL)
        for m, ok in [(EXT_L1, ok1), (EXT_TALE, ok2), (EXT_S1, ok3)]:
            if ok:
                wins.append(m)
            else:
                lose.append(m)

        ext_any = max(ok1, ok2, ok3)
        be_ok, be_m = best_external_for_case({EXT_L1: ok1, EXT_TALE: ok2, EXT_S1: ok3})

        if pal_ok and not ext_any:
            pv = "pal_only"
        elif ext_any and not pal_ok:
            pv = "external_only"
        elif pal_ok and ext_any:
            pv = "both_correct"
        else:
            pv = "both_wrong"

        nqty = numeric_qty(q)
        hints = operation_hints_heuristic(q)
        paired_rows.append(
            {
                "case_id": eid,
                "question": q,
                "gold_answer": gold,
                "pal_answer": pa,
                "pal_correct": pal_ok,
                "external_l1_max_answer": a1,
                "external_l1_max_correct": ok1,
                "external_tale_prompt_budgeting_answer": a2,
                "external_tale_prompt_budgeting_correct": ok2,
                "external_s1_budget_forcing_answer": a3,
                "external_s1_budget_forcing_correct": ok3,
                "winning_methods": ";".join([x for x in wins if x]),
                "losing_methods": ";".join([x for x in lose if x]),
                "all_correct_count": int(pal_ok + ok1 + ok2 + ok3),
                "any_external_correct": ext_any,
                "pal_beats_all_externals": int(bool(pal_ok and not ok1 and not ok2 and not ok3)),
                "best_external_correct": be_ok,
                "best_external_method_for_case": be_m,
                "pal_vs_best_external_outcome": pv if be_ok or pal_ok else pv,
                "operation_hint_tags": hints,
                "numeric_quantity_count": nqty,
                "question_length_bucket": len_bucket(q),
                "candidate_diversity": "",
            }
        )

    # fix pal_vs_best_external_outcome column: redefine strictly vs best external correctness
    for rec in paired_rows:
        pal_ok = int(rec["pal_correct"])
        be_ok = int(rec["best_external_correct"])
        if pal_ok and be_ok:
            rec["pal_vs_best_external_outcome"] = "both_correct"
        elif pal_ok and not be_ok:
            rec["pal_vs_best_external_outcome"] = "pal_only"
        elif not pal_ok and be_ok:
            rec["pal_vs_best_external_outcome"] = "external_only"
        else:
            rec["pal_vs_best_external_outcome"] = "both_wrong"

    fields = list(paired_rows[0].keys()) if paired_rows else []
    with (bd / "paired_casebook.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(paired_rows)

    # --- method_summary.csv (user schema) ---
    def summarize_method(method_id: str) -> dict[str, Any]:
        xs = [r for r in rows if str(r.get("method")) == method_id and int(r.get("scored", 0)) == 1]
        n = len(xs)
        corr = sum(int(r.get("exact_match") or 0) for r in xs)
        md_all = [dict(r.get("result_metadata") or {}) for r in xs]
        acts: list[float] = []
        for md in md_all:
            au = actions_used(md)
            try:
                if au != "" and au is not None:
                    acts.append(float(au))
            except Exception:
                pass
        calls = [float(r.get("cohere_logical_api_calls") or 0) for r in xs]
        parse_fail = sum(int(r.get("parse_extraction_failure") or 0) for r in xs)
        bud_ex = sum(budget_exhausted_flag(dict(r.get("result_metadata") or {}), r) for r in xs)
        return {
            "method": method_id,
            "correct_count": corr,
            "total_count": n,
            "accuracy": (corr / n) if n else 0.0,
            "avg_actions_used": mean(acts) if acts else "",
            "avg_logical_calls": mean(calls) if calls else 0.0,
            "parse_failure_count": parse_fail,
            "budget_exhausted_count": bud_ex,
        }

    methods_list = [PAL, EXT_L1, EXT_TALE, EXT_S1]
    msum = [summarize_method(m) for m in methods_list]
    with (bd / "method_summary.csv").open("w", encoding="utf-8", newline="") as f:
        fn = list(msum[0].keys())
        w = csv.DictWriter(f, fieldnames=fn)
        w.writeheader()
        w.writerows(msum)

    # --- pairwise_summary.json ---

    def contingency(label_a: str, a_key: str, b_key: str) -> dict[str, Any]:
        bc = Counter()
        deltas: list[float] = []
        for rec in paired_rows:
            av = int(rec[a_key])
            bv = int(rec[b_key])
            d = float(av - bv)
            deltas.append(d)
            if av and bv:
                bc["both_correct"] += 1
            elif av and not bv:
                bc["pal_only"] += 1
            elif not av and bv:
                bc["external_only"] += 1
            else:
                bc["both_wrong"] += 1
        acc_a = mean([int(rec[a_key]) for rec in paired_rows]) if paired_rows else 0.0
        acc_b = mean([int(rec[b_key]) for rec in paired_rows]) if paired_rows else 0.0
        return {
            "label": label_a,
            "both_correct": bc["both_correct"],
            "pal_only": bc["pal_only"],
            "external_only": bc["external_only"],
            "both_wrong": bc["both_wrong"],
            "pal_minus_external_correct_count": int(sum(deltas)),
            "pal_minus_external_accuracy_pp": float((acc_a - acc_b) * 100.0),
        }

    pw: dict[str, Any] = {}
    pw["pal_vs_external_l1_max"] = contingency("pal_vs_external_l1_max", "pal_correct", "external_l1_max_correct")
    pw["pal_vs_external_tale_prompt_budgeting"] = contingency(
        "pal_vs_external_tale_prompt_budgeting", "pal_correct", "external_tale_prompt_budgeting_correct"
    )
    pw["pal_vs_external_s1_budget_forcing"] = contingency(
        "pal_vs_external_s1_budget_forcing", "pal_correct", "external_s1_budget_forcing_correct"
    )

    bc2 = Counter()
    pal_c = best_e = po = eo = bw = 0
    for rec in paired_rows:
        p = int(rec["pal_correct"])
        be = int(rec["best_external_correct"])
        pal_c += p
        best_e += be
        if p and be:
            bc2["both_correct"] += 1
        elif p and not be:
            bc2["pal_only"] += 1
        elif not p and be:
            bc2["external_only"] += 1
        else:
            bc2["both_wrong"] += 1
    pw["pal_vs_best_external"] = {
        "pal_correct_count": pal_c,
        "best_external_correct_count": best_e,
        "pal_only_count": bc2["pal_only"],
        "external_only_count": bc2["external_only"],
        "both_correct_count": bc2["both_correct"],
        "both_wrong_count": bc2["both_wrong"],
        "pal_minus_best_external_correct_count": int(sum(int(rec["pal_correct"]) - int(rec["best_external_correct"]) for rec in paired_rows)),
        "pal_minus_best_external_accuracy_pp": float(
            (mean([int(r["pal_correct"]) for r in paired_rows]) - mean([int(r["best_external_correct"]) for r in paired_rows])) * 100.0
        )
        if paired_rows
        else 0.0,
    }

    (bd / "pairwise_summary.json").write_text(json.dumps(pw, indent=2) + "\n", encoding="utf-8")

    # --- case_matrix.md ---
    lines = ["# Case correctness matrix", "", "| case_id | pal | l1 | tale | s1 |", "|---|---:|---:|---:|---:|"]
    for rec in paired_rows:
        eid = rec["case_id"]
        lines.append(
            f"| {eid} | {rec['pal_correct']} | {rec['external_l1_max_correct']} | "
            f"{rec['external_tale_prompt_budgeting_correct']} | {rec['external_s1_budget_forcing_correct']} |"
        )
    (bd / "case_matrix.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # --- failure_notes.md ---
    pal_wrong = [r["case_id"] for r in paired_rows if not int(r["pal_correct"])]
    ext_beat_pal = [
        r["case_id"]
        for r in paired_rows
        if (int(r["external_l1_max_correct"]) or int(r["external_tale_prompt_budgeting_correct"]) or int(r["external_s1_budget_forcing_correct"]))
        and not int(r["pal_correct"])
    ]
    pal_beats_all = [r["case_id"] for r in paired_rows if int(r["pal_beats_all_externals"])]
    all_fail = [r["case_id"] for r in paired_rows if not int(r["pal_correct"]) and not max(int(r["external_l1_max_correct"]), int(r["external_tale_prompt_budgeting_correct"]), int(r["external_s1_budget_forcing_correct"]))]

    notes = [
        "# Failure notes (pilot; no causal claims)",
        "",
        "## PAL wrong",
        *[f"- `{x}`" for x in pal_wrong],
        "",
        "## At least one external correct while PAL wrong",
        *[f"- `{x}`" for x in ext_beat_pal],
        "",
        "## PAL correct while all three externals wrong",
        *[f"- `{x}`" for x in pal_beats_all],
        "",
        "## All four methods wrong",
        *[f"- `{x}`" for x in all_fail],
        "",
        "## Metadata pointers",
        "- Per-method rows in `results.jsonl` include `result_metadata_full` and surfacing fields where present.",
    ]
    (bd / "failure_notes.md").write_text("\n".join(notes) + "\n", encoding="utf-8")

    # --- call_plan.json ---
    calls_by_m = Counter()
    for r in rows:
        if int(r.get("scored", 0)) == 1:
            calls_by_m[str(r.get("method"))] += int(r.get("cohere_logical_api_calls") or 0)
    total_calls = sum(calls_by_m.values())
    plan = {
        "cases_per_method": 30,
        "methods": methods_list,
        "estimated_calls_per_method_prior": {
            PAL: "~21 (from 300-case ratio scaled)",
            EXT_L1: "~21",
            EXT_TALE: "~21",
            EXT_S1: "~21",
        },
        "estimated_total_calls_prior": args.call_plan_estimate_total,
        "hard_cap_logical_calls": 900,
        "abort_conditions": [
            "Wrong method IDs or provider",
            "logical_calls_total exceeds cap",
            "unexpected incomplete slices",
        ],
        "actual_total_logical_calls_observed": total_calls,
        "actual_logical_calls_by_method": dict(calls_by_m),
    }
    (bd / "call_plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")

    print(f"Wrote paired_casebook ({len(paired_rows)} rows), results.jsonl, summaries -> {bd}")


if __name__ == "__main__":
    main()
