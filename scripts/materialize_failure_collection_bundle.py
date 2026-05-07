#!/usr/bin/env python3
"""Post-process cohere_collect_pal_failure_cases bundle: CSVs, JSONL, reports (no API)."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

_SPEC = importlib.util.spec_from_file_location(
    "p4bundle", REPO_ROOT / "scripts" / "materialize_cohere_4way_pilot_bundle.py"
)
assert _SPEC and _SPEC.loader
p4 = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(p4)  # type: ignore

actions_used = p4.actions_used
budget_exhausted_flag = p4.budget_exhausted_flag
PAL = p4.PAL
EXT_L1 = p4.EXT_L1
EXT_TALE = p4.EXT_TALE
EXT_S1 = p4.EXT_S1
EXT_ORDER = p4.EXT_ORDER

METHOD_LIST = [PAL, EXT_L1, EXT_TALE, EXT_S1]

RANGE_300 = {f"openai_gsm8k_{i}" for i in range(772, 1072)}
RANGE_30 = {f"openai_gsm8k_{i}" for i in range(50, 80)}


def load_corpus(repo: Path) -> set[str]:
    p = repo / "outputs" / "failure_case_corpus_20260507" / "failure_cases.csv"
    if not p.exists():
        return set()
    with p.open(encoding="utf-8") as f:
        return {str(r["example_id"]) for r in csv.DictReader(f) if r.get("example_id")}


def best_external_for_case(ext: dict[str, int]) -> tuple[int, str]:
    for m in EXT_ORDER:
        if ext.get(m):
            return 1, m
    return 0, ""


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


def numeric_qty(question: str) -> int:
    return len(re.findall(r"\b\d+(?:\.\d+)?\b", question or ""))


def len_bucket(q: str) -> str:
    n = len((q or "").split())
    if n < 80:
        return "len_medium"
    return "len_long"


def richness_score(pal_row: dict[str, Any]) -> int:
    md = dict(pal_row.get("result_metadata") or {})
    n = 0
    if md.get("action_trace"):
        n += 3
    if md.get("selector_candidate_pool"):
        n += 2
    if md.get("final_branch_states") or md.get("branch_states"):
        n += 1
    pe = md.get("pal_execution")
    if isinstance(pe, dict) and len(json.dumps(pe, default=str)) > 300:
        n += 2
    if md.get("direct_reserve_attempts"):
        n += 1
    return n


def map_row_to_all_results(r: dict[str, Any]) -> dict[str, Any]:
    md = dict(r.get("result_metadata") or {})
    ext_md = {k: md.get(k) for k in md if str(k).startswith("external_") or k in ("l1_control_mode", "final_score")}
    palx = md.get("pal_execution") or {}
    scored = int(r.get("scored", 0))
    row_out: dict[str, Any] = {
        "example_id": r.get("example_id"),
        "case_id": r.get("example_id"),
        "method": r.get("method"),
        "question": r.get("question"),
        "gold_answer": r.get("gold_answer"),
        "predicted_answer": r.get("final_answer_raw"),
        "exact_match": int(r.get("exact_match") or 0),
        "correct": bool(int(r.get("exact_match") or 0)),
        "normalized_predicted_answer": r.get("final_answer_canonical"),
        "normalized_gold_answer": r.get("gold_answer_canonical"),
        "parse_extraction_failure": int(r.get("parse_extraction_failure") or 0),
        "parse_surfacing_ok": int(scored == 1 and int(r.get("parse_extraction_failure") or 0) == 0),
        "actions_used": actions_used(md) if scored else "",
        "budget_exhausted": budget_exhausted_flag(md, r) if scored else 0,
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
        "external_baseline_metadata": ext_md if str(r.get("method", "")).startswith("external_") else {},
        "cohere_logical_api_calls": int(r.get("cohere_logical_api_calls") or 0),
        "failure_tag": r.get("failure_tag"),
        "status": r.get("status"),
        "scored": scored,
        "result_metadata_full": md if scored else {},
        "error": r.get("error", ""),
    }
    return row_out


def contingency(label: str, paired: list[dict[str, Any]], ak: str, bk: str) -> dict[str, Any]:
    bc = Counter()
    for rec in paired:
        av = int(rec[ak])
        bv = int(rec[bk])
        if av and bv:
            bc["both_correct"] += 1
        elif av and not bv:
            bc["pal_only"] += 1
        elif not av and bv:
            bc["external_only"] += 1
        else:
            bc["both_wrong"] += 1
    acc_a = mean([int(rec[ak]) for rec in paired]) if paired else 0.0
    acc_b = mean([int(rec[bk]) for rec in paired]) if paired else 0.0
    return {
        "label": label,
        "both_correct": bc["both_correct"],
        "pal_only": bc["pal_only"],
        "external_only": bc["external_only"],
        "both_wrong": bc["both_wrong"],
        "pal_accuracy": acc_a,
        "external_accuracy": acc_b,
        "pal_minus_external_accuracy_pp": float((acc_a - acc_b) * 100.0),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("bundle_dir", type=Path)
    args = ap.parse_args()
    bd: Path = args.bundle_dir.resolve()
    repo = REPO_ROOT

    inner = None
    for c in sorted(bd.glob("cohere_real_model_cost_normalized_validation_*")):
        if c.is_dir():
            inner = c
            break
    if inner is None:
        print("No cohere_real_model_cost_normalized_validation_* under bundle", file=sys.stderr)
        raise SystemExit(1)

    per_path = inner / "per_example_records.jsonl"
    if not per_path.exists():
        print("Missing per_example_records.jsonl", per_path, file=sys.stderr)
        raise SystemExit(1)

    raw_rows = [json.loads(x) for x in per_path.read_text(encoding="utf-8").splitlines() if x.strip()]

    all_res_path = bd / "all_results.jsonl"
    with all_res_path.open("w", encoding="utf-8") as out:
        for r in raw_rows:
            out.write(json.dumps(map_row_to_all_results(r), ensure_ascii=False) + "\n")

    by_case: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    failed_rows = 0
    for r in raw_rows:
        if int(r.get("scored", 0)) != 1:
            failed_rows += 1
            continue
        by_case[str(r["example_id"])][str(r["method"])] = r

    case_ids_sorted = sorted(by_case.keys(), key=lambda x: int(str(x).rsplit("_", 1)[-1]))

    incomplete_cases = [cid for cid in case_ids_sorted if len(by_case[cid]) < 4]

    paired_rows: list[dict[str, Any]] = []
    for eid in case_ids_sorted:
        blk = by_case[eid]
        if len(blk) < 4:
            continue
        r0 = blk.get(PAL) or next(iter(blk.values()))
        q = str(r0.get("question") or "")
        gold = str(r0.get("gold_answer") or "")
        pal_r = blk.get(PAL, {})
        ex = {EXT_L1: blk.get(EXT_L1, {}), EXT_TALE: blk.get(EXT_TALE, {}), EXT_S1: blk.get(EXT_S1, {})}
        pa = str(pal_r.get("final_answer_raw") or "")
        pal_ok = int(pal_r.get("exact_match") or 0)
        ok1 = int(ex[EXT_L1].get("exact_match") or 0)
        ok2 = int(ex[EXT_TALE].get("exact_match") or 0)
        ok3 = int(ex[EXT_S1].get("exact_match") or 0)
        ext_any = max(ok1, ok2, ok3)
        ext_all = min(ok1, ok2, ok3)
        be_ok, be_m = best_external_for_case({EXT_L1: ok1, EXT_TALE: ok2, EXT_S1: ok3})

        wins = [m for m, ok in [(PAL, pal_ok), (EXT_L1, ok1), (EXT_TALE, ok2), (EXT_S1, ok3)] if ok]
        loses = [m for m, ok in [(PAL, pal_ok), (EXT_L1, ok1), (EXT_TALE, ok2), (EXT_S1, ok3)] if not ok]

        if pal_ok and ext_all:
            bucket = "all_correct"
        elif pal_ok and not ext_any:
            bucket = "pal_correct_all_external_wrong"
        elif not pal_ok and ext_any:
            bucket = "pal_wrong_external_correct"
        elif not pal_ok and not ext_any:
            bucket = "pal_wrong_all_external_wrong"
        else:
            bucket = "mixed_other"

        pal_md = dict(pal_r.get("result_metadata") or {})
        cand_div = str(pal_md.get("selector_candidate_diversity") or pal_md.get("candidate_diversity") or "")
        ext_tree = int(bool(pal_md.get("external_tree_available") or pal_md.get("l1_tree_available")))

        paired_rows.append(
            {
                "case_id": eid,
                "question": q,
                "gold_answer": gold,
                "pal_answer": pa,
                "pal_correct": pal_ok,
                "external_l1_max_answer": str(ex[EXT_L1].get("final_answer_raw") or ""),
                "external_l1_max_correct": ok1,
                "external_tale_prompt_budgeting_answer": str(ex[EXT_TALE].get("final_answer_raw") or ""),
                "external_tale_prompt_budgeting_correct": ok2,
                "external_s1_budget_forcing_answer": str(ex[EXT_S1].get("final_answer_raw") or ""),
                "external_s1_budget_forcing_correct": ok3,
                "best_external_correct": be_ok,
                "best_external_methods": be_m,
                "outcome_bucket": bucket,
                "winning_methods": ";".join(wins),
                "losing_methods": ";".join(loses),
                "operation_hint_tags": operation_hints_heuristic(q),
                "numeric_quantity_count": numeric_qty(q),
                "question_length_bucket": len_bucket(q),
                "candidate_diversity": cand_div,
                "gold_in_trace_detectable": int(bool(pal_md.get("gold_in_tree"))),
                "external_tree_available": ext_tree,
                "trace_rich_pal": int(richness_score(pal_r) >= 3),
            }
        )

    if paired_rows:
        fn = list(paired_rows[0].keys())
        with (bd / "all_casebook.csv").open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fn)
            w.writeheader()
            w.writerows(paired_rows)

    corpus_ids = load_corpus(repo)
    overlap = {
        "prior_300_case_band_openai_gsm8k_772_1071": sorted(set(case_ids_sorted) & RANGE_300),
        "prior_30_case_pilot_openai_gsm8k_50_79": sorted(set(case_ids_sorted) & RANGE_30),
        "failure_case_corpus_20260507": sorted(set(case_ids_sorted) & corpus_ids),
    }
    (bd / "case_overlap_report.json").write_text(json.dumps(overlap, indent=2) + "\n", encoding="utf-8")

    pal_wrong_cases = [r for r in paired_rows if not int(r["pal_correct"])]
    preferred_list: list[dict[str, Any]] = []
    secondary_candidates: list[dict[str, Any]] = []
    for rec in pal_wrong_cases:
        ext_any = max(int(rec["external_l1_max_correct"]), int(rec["external_tale_prompt_budgeting_correct"]), int(rec["external_s1_budget_forcing_correct"]))
        if ext_any:
            preferred_list.append(rec)
        else:
            secondary_candidates.append(rec)

    secondary_candidates.sort(key=lambda r: (-int(r["trace_rich_pal"]), richness_score(by_case[r["case_id"]][PAL])))

    selected: list[tuple[str, str]] = []
    seen_sel: set[str] = set()
    for rec in preferred_list:
        cid = rec["case_id"]
        if cid not in seen_sel and len(selected) < 45:
            selected.append((cid, "preferred"))
            seen_sel.add(cid)
    for rec in secondary_candidates:
        cid = rec["case_id"]
        if cid not in seen_sel and len(selected) < 45:
            selected.append((cid, "secondary"))
            seen_sel.add(cid)

    preferred_sel = [cid for cid, t in selected if t == "preferred"]
    secondary_sel = [cid for cid, t in selected if t == "secondary"]

    with (bd / "selected_failure_cases.jsonl").open("w", encoding="utf-8") as out:
        for cid, tier in selected:
            blk = by_case[cid]
            pal_row = blk[PAL]
            out.write(
                json.dumps(
                    {
                        "case_id": cid,
                        "failure_tier": tier,
                        "question": str(pal_row.get("question") or ""),
                        "gold_answer": str(pal_row.get("gold_answer") or ""),
                        "method_records": {m: blk.get(m, {}) for m in METHOD_LIST},
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    sel_csv_rows: list[dict[str, Any]] = []
    for cid, tier in selected:
        rec = next((x for x in paired_rows if x["case_id"] == cid), None)
        if rec:
            sel_csv_rows.append({**rec, "failure_tier": tier})
    if sel_csv_rows:
        sf = list(sel_csv_rows[0].keys())
        with (bd / "selected_failure_cases.csv").open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=sf)
            w.writeheader()
            w.writerows(sel_csv_rows)

    pal_ext_win = [
        r
        for r in paired_rows
        if not int(r["pal_correct"])
        and max(int(r["external_l1_max_correct"]), int(r["external_tale_prompt_budgeting_correct"]), int(r["external_s1_budget_forcing_correct"]))
    ]
    pal_all_ext_wrong = [
        r
        for r in paired_rows
        if not int(r["pal_correct"])
        and not max(int(r["external_l1_max_correct"]), int(r["external_tale_prompt_budgeting_correct"]), int(r["external_s1_budget_forcing_correct"]))
    ]

    if pal_ext_win:
        pf = list(pal_ext_win[0].keys())
        with (bd / "pal_loss_external_win_cases.csv").open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=pf)
            w.writeheader()
            w.writerows(pal_ext_win)
    else:
        (bd / "pal_loss_external_win_cases.csv").write_text("", encoding="utf-8")

    if pal_all_ext_wrong:
        pf = list(pal_all_ext_wrong[0].keys())
        with (bd / "pal_wrong_all_external_wrong_cases.csv").open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=pf)
            w.writeheader()
            w.writerows(pal_all_ext_wrong)
    else:
        (bd / "pal_wrong_all_external_wrong_cases.csv").write_text("", encoding="utf-8")

    calls_by_m: Counter[str] = Counter()
    correct_by_m: Counter[str] = Counter()
    total_by_m: Counter[str] = Counter()
    for r in raw_rows:
        if int(r.get("scored", 0)) != 1:
            continue
        m = str(r.get("method"))
        total_by_m[m] += 1
        correct_by_m[m] += int(r.get("exact_match") or 0)
        calls_by_m[m] += int(r.get("cohere_logical_api_calls") or 0)
    total_calls = sum(calls_by_m.values())
    cap = 3000
    try:
        cp = json.loads((bd / "call_plan.json").read_text(encoding="utf-8"))
        cap = int(cp.get("hard_cap_logical_calls", 3000))
    except Exception:
        pass

    bc2 = Counter()
    for rec in paired_rows:
        p = int(rec["pal_correct"])
        be = int(rec["best_external_correct"])
        if p and be:
            bc2["both_correct"] += 1
        elif p and not be:
            bc2["pal_only"] += 1
        elif not p and be:
            bc2["external_only"] += 1
        else:
            bc2["both_wrong"] += 1

    per_window_yield: list[dict[str, Any]] = []
    for aw in sorted(bd.glob("allowlist_window_*.jsonl")):
        wids = sorted({json.loads(ln)["example_id"] for ln in aw.read_text(encoding="utf-8").splitlines() if ln.strip()})
        pref_n = sum(1 for cid in wids if cid in preferred_sel)
        sec_n = sum(1 for cid in wids if cid in secondary_sel)
        per_window_yield.append(
            {"allowlist_file": aw.name, "cases_in_window": len(set(wids)), "preferred_failures_in_selected_corpus": pref_n, "secondary_in_selected_corpus": sec_n}
        )

    summary = {
        "evaluated_case_count": len(case_ids_sorted),
        "evaluated_complete_4way_case_count": len(paired_rows),
        "incomplete_case_ids": incomplete_cases,
        "method_rows_count": len([r for r in raw_rows if int(r.get("scored", 0)) == 1]),
        "failed_skipped_row_count": failed_rows,
        "preferred_failures_in_pool_pal_wrong_external_correct": len(preferred_list),
        "secondary_failures_in_pool_pal_wrong_all_external_wrong": len(secondary_candidates),
        "preferred_failures_selected": len(preferred_sel),
        "secondary_failures_selected": len(secondary_sel),
        "selected_failure_count": len(selected),
        "per_method_accuracy": {
            m: {"correct": correct_by_m[m], "total": total_by_m[m], "accuracy": (correct_by_m[m] / total_by_m[m]) if total_by_m[m] else 0.0}
            for m in METHOD_LIST
        },
        "call_usage_per_method": dict(calls_by_m),
        "total_logical_calls": total_calls,
        "hard_cap_logical_calls": cap,
        "cap_respected": total_calls <= cap,
        "pal_vs_best_external_counts": dict(bc2),
        "per_window_failure_yield": per_window_yield,
    }
    (bd / "failure_collection_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    lines = ["# Failure case matrix (selected corpus)", "", "| case_id | tier | PAL | L1 | TALE | S1 | pal_ans | gold |", "|---|---|--:|--:|--:|--:|---|---|"]
    sel_set = set(cid for cid, _ in selected)
    for rec in paired_rows:
        if rec["case_id"] not in sel_set:
            continue
        tier = next((t for c, t in selected if c == rec["case_id"]), "")
        lines.append(
            f"| {rec['case_id']} | {tier} | {rec['pal_correct']} | {rec['external_l1_max_correct']} | "
            f"{rec['external_tale_prompt_budgeting_correct']} | {rec['external_s1_budget_forcing_correct']} | "
            f"{str(rec['pal_answer'])[:40]} | {str(rec['gold_answer'])[:20]} |"
        )
    (bd / "failure_case_matrix.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    pw1 = contingency("pal_vs_external_l1_max", paired_rows, "pal_correct", "external_l1_max_correct")
    pw2 = contingency("pal_vs_external_tale_prompt_budgeting", paired_rows, "pal_correct", "external_tale_prompt_budgeting_correct")
    pw3 = contingency("pal_vs_external_s1_budget_forcing", paired_rows, "pal_correct", "external_s1_budget_forcing_correct")
    acc_pal = mean([int(r["pal_correct"]) for r in paired_rows]) if paired_rows else 0.0
    acc_be = mean([int(r["best_external_correct"]) for r in paired_rows]) if paired_rows else 0.0

    report = [
        "# PAL + retry failure collection (vs three externals)",
        "",
        "## What ran",
        "- Bundle directory contains `cohere_real_model_cost_normalized_validation_*` run artifacts and allowlists.",
        "- Materialization is offline from `per_example_records.jsonl`.",
        "",
        "## Scale",
        f"- Evaluated cases (any rows): **{len(case_ids_sorted)}**",
        f"- Complete 4-method rows: **{len(paired_rows)}**",
        f"- Selected failure corpus size: **{len(selected)}** (target 45 preferred-first, padded with secondary rich-trace cases if needed)",
        f"- Preferred failures in pool: **{len(preferred_list)}**; secondary (PAL wrong, all externals wrong): **{len(secondary_candidates)}**",
        f"- Logical Cohere calls (sum of row counters): **{total_calls}** (cap {cap})",
        "",
        "## Selected failure case IDs",
        *[f"- `{cid}` ({tier})" for cid, tier in selected],
        "",
        "## Per-method accuracy (evaluated pool, scored rows)",
        *[f"- `{m}`: {correct_by_m[m]}/{total_by_m[m]} = {((correct_by_m[m]/total_by_m[m]) if total_by_m[m] else 0):.4f}" for m in METHOD_LIST],
        "",
        "## PAL vs each external (pairwise)",
        f"- vs L1: external_only={pw1['external_only']} pal_only={pw1['pal_only']} both_wrong={pw1['both_wrong']} both_correct={pw1['both_correct']}",
        f"- vs TALE: external_only={pw2['external_only']} pal_only={pw2['pal_only']} both_wrong={pw2['both_wrong']} both_correct={pw2['both_correct']}",
        f"- vs S1: external_only={pw3['external_only']} pal_only={pw3['pal_only']} both_wrong={pw3['both_wrong']} both_correct={pw3['both_correct']}",
        "",
        "## PAL vs best external",
        f"- PAL accuracy: {acc_pal:.4f}; best-external accuracy: {acc_be:.4f}",
        f"- Counts: {dict(bc2)}",
        "",
        "## Dominant failure patterns (heuristic tags, selected PAL-wrong cases)",
    ]
    tag_c = Counter()
    for rec in paired_rows:
        if rec["case_id"] in sel_set and not int(rec["pal_correct"]):
            for t in (rec.get("operation_hint_tags") or "").split("|"):
                if t:
                    tag_c[t] += 1
    report.extend([f"- `{k}`: {v}" for k, v in tag_c.most_common(12)])
    report.extend(
        [
            "",
            "## Caveats",
            "- Exact-match scoring only; no claim of statistical superiority.",
            "- Incomplete slices (missing method rows) are listed in `failure_collection_summary.json`.",
            "",
            "## More collection needed?",
            "- If `preferred_failures_selected` < 45 and API budget remains, additional windows can be run with the orchestrator.",
            "",
        ]
    )
    (bd / "failure_collection_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")

    try:
        commit = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
        branch = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "--abbrev-ref", "HEAD"], text=True).strip()
    except Exception:
        commit, branch = "", ""
    env_detected = [k for k in ("COHERE_API_KEY", "CO_API_KEY", "HF_TOKEN", "HUGGINGFACE_HUB_TOKEN") if os.getenv(k)]
    coll_state: dict[str, Any] = {}
    stp = bd / "collection_state.json"
    if stp.exists():
        try:
            coll_state = json.loads(stp.read_text(encoding="utf-8"))
        except Exception:
            pass
    manifest = {
        "timestamp": inner.name.replace("cohere_real_model_cost_normalized_validation_", ""),
        "git_commit": commit,
        "git_branch": branch,
        "dataset": "openai/gsm8k",
        "provider": "cohere",
        "model": "command-r-plus-08-2024",
        "primary_method_id": PAL,
        "external_baseline_ids": [EXT_L1, EXT_TALE, EXT_S1],
        "target_failure_count": 45,
        "case_selection_policy": "Deterministic GSM8K ids openai_gsm8k_1072..1318 excluding failure_case_corpus_20260507; excludes prior 300-case band 772-1071 and 30-case pilot 50-79 by construction.",
        "evaluated_case_ids_sorted": case_ids_sorted,
        "selected_failure_case_ids": [cid for cid, _ in selected],
        "preferred_selected_ids": preferred_sel,
        "secondary_selected_ids": secondary_sel,
        "overlap_report_file": "case_overlap_report.json",
        "call_cap": cap,
        "actual_logical_calls": total_calls,
        "environment_variables_detected_names_only": env_detected,
        "commands_run": coll_state.get("commands", []),
        "inner_validation_dir": str(inner.relative_to(repo)),
    }
    (bd / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    cp_path = bd / "call_plan.json"
    if cp_path.exists():
        cp_obj = json.loads(cp_path.read_text(encoding="utf-8"))
        cp_obj["actual_total_logical_calls"] = total_calls
        cp_obj["actual_logical_calls_by_method"] = dict(calls_by_m)
        cp_obj["evaluated_cases"] = len(case_ids_sorted)
        cp_path.write_text(json.dumps(cp_obj, indent=2) + "\n", encoding="utf-8")

    print(f"Materialized bundle -> {bd}")


if __name__ == "__main__":
    main()
