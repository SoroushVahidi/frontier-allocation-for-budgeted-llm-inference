#!/usr/bin/env python3
"""Build paired pilot artifacts (CSV/JSON/MD) from per_example_records.jsonl (no API)."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any

from experiments.output_layer_repair import augment_final_nodes_with_metadata_frontier, canonicalize_answer  # noqa: E402
from experiments.frontier_max_support_tiebreak import normalize_answer_group_key  # noqa: E402

PAL_METHOD = "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal"
EXT_METHOD = "external_l1_max"


def _j(x: Any) -> str:
    try:
        return json.dumps(x, ensure_ascii=False)
    except Exception:
        return ""


def _to_int(val: Any) -> int:
    try:
        return int(val)
    except (TypeError, ValueError):
        return 0


def _external_candidate_answers(md: dict[str, Any]) -> str:
    fbs = md.get("final_branch_states")
    if isinstance(fbs, list):
        out = []
        for b in fbs:
            if isinstance(b, dict):
                pa = b.get("predicted_answer")
                if pa is not None and str(pa).strip():
                    out.append(str(pa).strip())
        if out:
            return _j(out)
    at = md.get("action_trace")
    if isinstance(at, list):
        out2 = []
        for ev in at:
            if isinstance(ev, dict):
                ext = ev.get("extracted_answer") or ev.get("answer")
                if ext is not None and str(ext).strip():
                    out2.append(str(ext).strip())
        if out2:
            return _j(out2)
    return ""


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("bundle_dir", type=Path)
    args = p.parse_args()
    bd: Path = args.bundle_dir.resolve()

    jsonl = bd / "per_example_records.jsonl"
    rows = [json.loads(x) for x in jsonl.read_text(encoding="utf-8").splitlines() if x.strip()]

    ext_rows = [r for r in rows if r.get("method") == EXT_METHOD and int(r.get("scored", 0)) == 1]
    pal_rows_list = [r for r in rows if r.get("method") == PAL_METHOD and int(r.get("scored", 0)) == 1]
    em = {str(r["example_id"]): r for r in ext_rows}
    pm = {str(r["example_id"]): r for r in pal_rows_list}
    common = sorted(set(em.keys()) & set(pm.keys()))
    n = len(common)

    paired: list[dict[str, Any]] = []

    def pal_wrong_failure_tag(eid: str, ee: int) -> str:
        pr = pm[eid]
        md = dict(pr.get("result_metadata") or {})
        px = md.get("pal_execution") or {}
        if ee == 0:
            return "external_also_wrong"
        gcan = canonicalize_answer(str(pr.get("gold_answer") or ""), dataset="openai/gsm8k")
        fn = list(pr.get("final_nodes") or [])
        aug = augment_final_nodes_with_metadata_frontier(fn, md)
        in_tree = False
        if gcan:
            for node in aug:
                ra = node.get("predicted_answer")
                if ra is not None and canonicalize_answer(str(ra), dataset="openai/gsm8k") == gcan:
                    in_tree = True
                    break
        if not str(px.get("pal_code") or "").strip():
            return "code_absent"
        if isinstance(px, dict) and int(px.get("pal_safety_ok") or 0) == 0:
            return "unsafe_code"
        if isinstance(px, dict) and int(px.get("pal_exec_ok") or 0) == 0:
            return "exec_failed"
        if in_tree:
            return "pal_candidate_correct_but_not_selected"
        return "exec_succeeded_but_wrong_or_gold_absent"

    tax_counter: Counter[str] = Counter()

    for eid in common:
        e, p = em[eid], pm[eid]
        q = str(e.get("question") or p.get("question") or "")
        gold = str(e.get("gold_answer") or p.get("gold_answer") or "")
        ext_ans = str(e.get("final_answer_raw") or "")
        pal_ans = str(p.get("final_answer_raw") or "")
        ex_exact = int(e.get("exact_match") or 0)
        pal_exact = int(p.get("exact_match") or 0)
        if ex_exact and pal_exact:
            outcome = "both_correct"
        elif ex_exact and not pal_exact:
            outcome = "external_correct_pal_wrong"
        elif pal_exact and not ex_exact:
            outcome = "pal_correct_external_wrong"
        else:
            outcome = "both_wrong"

        if pal_exact == 0:
            tax_counter[pal_wrong_failure_tag(eid, ex_exact)] += 1

        emd, pmd = dict(e.get("result_metadata") or {}), dict(p.get("result_metadata") or {})
        fn = list(p.get("final_nodes") or [])
        aug = augment_final_nodes_with_metadata_frontier(fn, pmd)
        gcan = canonicalize_answer(gold, dataset="openai/gsm8k")
        git = 0
        if gcan:
            for node in aug:
                ra = node.get("predicted_answer")
                if ra is not None and canonicalize_answer(str(ra), dataset="openai/gsm8k") == gcan:
                    git = 1
                    break
        cand_norms: list[str] = []
        for node in aug:
            for k in ("predicted_answer_normalized", "predicted_answer"):
                v = node.get(k)
                if v is not None and str(v).strip():
                    cand_norms.append(str(v).strip())
        cand_cans = {canonicalize_answer(x, dataset="openai/gsm8k") for x in cand_norms}
        d3 = int(gcan is not None and gcan in cand_cans)
        uniq = len({normalize_answer_group_key(str(x)) for x in cand_norms if str(x).strip()})
        px = pmd.get("pal_execution") or {}
        pal_integ = pmd.get("pal_integration_evaluator") or {}
        pool = pmd.get("selector_candidate_pool") or []
        pool_ans = _j([r.get("predicted_answer") for r in pool if isinstance(r, dict)])

        pal_present_not_selected = int(git == 1 and pal_exact == 0)
        pal_gold_absent = int(git == 0 and d3 == 0)

        row = {
            "example_id": eid,
            "question": q,
            "gold_answer": gold,
            "external_final_answer": ext_ans,
            "external_exact": ex_exact,
            "external_l1_max_final_answer": ext_ans,
            "external_l1_max_exact": ex_exact,
            "pal_final_answer": pal_ans,
            "pal_exact": pal_exact,
            "pair_outcome": outcome,
            "both_correct": int(outcome == "both_correct"),
            "external_correct_pal_wrong": int(outcome == "external_correct_pal_wrong"),
            "pal_correct_external_wrong": int(outcome == "pal_correct_external_wrong"),
            "both_wrong": int(outcome == "both_wrong"),
            "external_l1_max_candidate_answers_json": _external_candidate_answers(emd),
            "external_l1_max_discovery3": "unavailable",
            "pal_corrected_gold_in_tree": git,
            "pal_discovery3": d3,
            "pal_discovery3_candidate_gold_present": d3,
            "pal_present_not_selected": pal_present_not_selected,
            "pal_gold_absent": pal_gold_absent,
            "pal_final_answer_source": p.get("final_answer_source") or "",
            "pal_selected_group": str(pmd.get("selected_group") or ""),
            "pal_frontier_tiebreak_triggered": int(bool(pmd.get("frontier_tiebreak_triggered"))),
            "pal_seed_ran": int(px.get("pal_seed_ran") or 0) if isinstance(px, dict) else "",
            "pal_budget_cost_observed": int(px.get("pal_budget_cost_observed") or 0) if isinstance(px, dict) else "",
            "pal_code_present": (
                int(px.get("pal_code_present"))
                if isinstance(px, dict) and px.get("pal_code_present") is not None
                else int(bool(str(px.get("pal_code") or "").strip()))
                if isinstance(px, dict)
                else ""
            ),
            "pal_json_answer_present": int(bool(str(px.get("pal_json_answer") or "").strip())) if isinstance(px, dict) else "",
            "pal_confidence_present": int(bool(px.get("pal_confidence") is not None)) if isinstance(px, dict) else "",
            "pal_parse_ok": int(px.get("pal_parse_ok") or 0) if isinstance(px, dict) else "",
            "pal_safety_ok": int(px.get("pal_safety_ok") or 0) if isinstance(px, dict) else "",
            "pal_exec_ok": int(px.get("pal_exec_ok") or 0) if isinstance(px, dict) else "",
            "pal_stdout_present": int(
                bool(str((px.get("pal_execution_result") or {}).get("pal_stdout") or "").strip())
            )
            if isinstance(px, dict)
            else "",
            "pal_answer_raw": str((px.get("pal_execution_result") or {}).get("pal_answer_raw") or "") if isinstance(px, dict) else "",
            "pal_answer_normalized": str((px.get("pal_execution_result") or {}).get("pal_answer_normalized") or "")
            if isinstance(px, dict)
            else "",
            "pal_error_type": str((px.get("pal_execution_result") or {}).get("pal_error_type") or "") if isinstance(px, dict) else "",
            "pal_candidate_strong": int(px.get("pal_candidate_is_strong") or 0) if isinstance(px, dict) else "",
            "pal_overlay_triggered": int(bool((pmd.get("pal_overlay") or {}).get("pal_overlay_applied")))
            if isinstance(pmd.get("pal_overlay"), dict)
            else 0,
            "pal_integration_fix_triggered": int(bool(pal_integ.get("pal_integration_fix_triggered")))
            if isinstance(pal_integ, dict)
            else "",
            "pal_direct_candidate_answers_json": _j(pmd.get("direct_reserve_attempts")),
            "pal_frontier_candidate_answers_json": _j((pmd.get("frontier_metadata") or {}).get("action_trace")),
            "pal_final_nodes_normalized_answers_json": _j(cand_norms),
            "pal_selector_candidate_pool_json": pool_ans,
            "pal_answer_group_support_counts_json": _j(pmd.get("answer_group_support_counts")),
            "pal_frontier_answer_group_counts_json": _j(pmd.get("frontier_answer_group_counts")),
            "pal_direct_answer_group_counts_json": _j(pmd.get("direct_answer_group_counts")),
            "pal_parse_extraction_failure": int(p.get("parse_extraction_failure") or 0),
            "unique_normalized_answer_count": uniq,
            "low_diversity_flag": int(uniq <= 1),
            "fallback_like_final_answer_flag": int(str(pal_ans).strip() in {"", "0", "1", "__unknown__"}),
        }
        paired.append(row)

    ext_acc = mean([float(em[i]["exact_match"]) for i in common]) if common else 0.0
    pal_acc = mean([float(pm[i]["exact_match"]) for i in common]) if common else 0.0
    gap_pp = round(100.0 * (ext_acc - pal_acc), 2)
    outcomes = Counter(r["pair_outcome"] for r in paired)

    total_calls_per_example_sum = sum(int(r.get("cohere_logical_api_calls") or 0) for r in rows)
    cap_hit: list[str] = []
    cap_consumed_vals: list[int] = []
    for r in rows:
        err = str(r.get("error") or "")
        m = re.search(r"Global logical API call cap reached \(\s*(\d+)", err)
        if m:
            cap_hit.append(str(r.get("example_id")))
            cap_consumed_vals.append(int(m.group(1)))
    inferred_global_budget = max(cap_consumed_vals) if cap_consumed_vals else None
    by_method: Counter[str] = Counter()
    for r in rows:
        by_method[str(r.get("method"))] += int(r.get("cohere_logical_api_calls") or 0)

    pal_sub = [pm[i] for i in common]
    exec_ok_n = sum(1 for r in pal_sub if int((r.get("result_metadata") or {}).get("pal_execution", {}).get("pal_exec_ok") or 0) == 1)
    strong_n = sum(
        1
        for r in pal_sub
        if int((r.get("result_metadata") or {}).get("pal_execution", {}).get("pal_candidate_is_strong") or 0) == 1
    )
    ex_ok_exact = sum(
        int(r.get("exact_match") or 0)
        for r in pal_sub
        if int((r.get("result_metadata") or {}).get("pal_execution", {}).get("pal_exec_ok") or 0) == 1
    )
    strong_exact = sum(
        int(r.get("exact_match") or 0)
        for r in pal_sub
        if int((r.get("result_metadata") or {}).get("pal_execution", {}).get("pal_candidate_is_strong") or 0) == 1
    )
    git_n = sum(int(r["pal_corrected_gold_in_tree"]) for r in paired)
    d3_n = sum(int(r["pal_discovery3_candidate_gold_present"]) for r in paired)
    pns = sum(1 for r in paired if int(r["pal_corrected_gold_in_tree"]) == 1 and int(r["pal_exact"]) == 0)
    gabs = sum(1 for r in paired if int(r["pal_corrected_gold_in_tree"]) == 0 and int(r["pal_discovery3_candidate_gold_present"]) == 0)

    def pal_rate(fname: str) -> float | None:
        if not n:
            return None
        return float(sum(_to_int(r.get(fname)) for r in paired)) / float(n)

    summary = {
        "selected_fresh_example_ids": sorted(common),
        "cohort_design_note": (
            "~120 paired rows is not feasible under a strict 360 logical-call cap "
            "(empirically ~3 calls/method/example ⇒ ~6/pair ⇒ ~54–56 full pairs)."
        ),
        "paired_examples_completed": n,
        "total_cohere_logical_api_calls": int(total_calls_per_example_sum),
        "logical_api_budget_cap_consumed_estimate": inferred_global_budget,
        "logical_calls_accounting_note": (
            "`total_cohere_logical_api_calls` sums per-example `cohere_logical_api_calls` counters (reset each example); "
            "the global branching cap consumed can exceed this sum mid-trajectory. When cap errors appear, "
            "`logical_api_budget_cap_consumed_estimate` records the inferred global budget from the RuntimeError "
            "(authoritative enforcement), while the row-sum remains useful for comparative per-example cost."
        ),
        "first_example_id_logical_cap_failure": cap_hit[0] if cap_hit else None,
        "calls_by_method_sum_per_completed_rows_only": dict(by_method),
        "failed_rows": int(sum(1 for r in rows if int(r.get("failed", 0)) == 1)),
        "skipped_or_unscored_rows": int(sum(1 for r in rows if int(r.get("scored", 0)) == 0)),
        "external_l1_max_exact_rate": ext_acc,
        "pal_exact_rate": pal_acc,
        "gap_external_minus_pal_percentage_points": gap_pp,
        "pair_outcomes": dict(outcomes),
        "pair_outcome_breakdown_counts": {
            "both_correct": int(outcomes.get("both_correct", 0)),
            "external_correct_pal_wrong": int(outcomes.get("external_correct_pal_wrong", 0)),
            "pal_correct_external_wrong": int(outcomes.get("pal_correct_external_wrong", 0)),
            "both_wrong": int(outcomes.get("both_wrong", 0)),
        },
        "pal_corrected_gold_in_tree_num": int(git_n),
        "pal_corrected_gold_in_tree_rate": float(git_n / n) if n else 0.0,
        "pal_discovery3_gold_present_num": int(d3_n),
        "pal_discovery3_gold_present_rate": float(d3_n / n) if n else 0.0,
        "pal_present_not_selected_num": int(pns),
        "pal_present_not_selected_rate": float(pns / n) if n else 0.0,
        "pal_gold_absent_num": int(gabs),
        "pal_gold_absent_rate": float(gabs / n) if n else 0.0,
        "pal_seed_ran_fraction": pal_rate("pal_seed_ran"),
        "pal_code_present_fraction": pal_rate("pal_code_present"),
        "pal_json_answer_present_fraction": pal_rate("pal_json_answer_present"),
        "pal_confidence_present_fraction": pal_rate("pal_confidence_present"),
        "pal_parse_ok_fraction": pal_rate("pal_parse_ok"),
        "pal_safety_ok_fraction": pal_rate("pal_safety_ok"),
        "pal_exec_ok_fraction": float(exec_ok_n / n) if n else 0.0,
        "pal_stdout_present_fraction": pal_rate("pal_stdout_present"),
        "pal_candidate_strong_fraction": float(strong_n / n) if n else 0.0,
        "pal_overlay_triggered_fraction": pal_rate("pal_overlay_triggered"),
        "pal_integration_fix_triggered_fraction": pal_rate("pal_integration_fix_triggered"),
        "pal_exact_given_exec_ok": float(ex_ok_exact / exec_ok_n) if exec_ok_n else None,
        "pal_exact_given_candidate_strong": float(strong_exact / strong_n) if strong_n else None,
        "pal_failure_taxonomy_on_pal_errors": dict(tax_counter),
        "interpretation_competitive_abs_gap_at_most_5pp": bool(abs(ext_acc - pal_acc) <= 0.05),
        "interpretation_pal_matches_or_beats_external_exact_rate": bool(pal_acc + 1e-9 >= ext_acc),
        "interpretation_more_paired_sampling_justified": bool(n < 80),
    }

    def _fmt_rate(rv: float | None) -> str:
        if rv is None:
            return "n/a"
        return f"{100.0 * rv:.1f}% of paired rows"

    subsystem_rate_lines = [
        ("pal_seed_ran_fraction", "pal_seed_ran"),
        ("pal_code_present_fraction", "pal_code_present"),
        ("pal_json_answer_present_fraction", "pal_json_answer_present"),
        ("pal_confidence_present_fraction", "pal_confidence_present"),
        ("pal_parse_ok_fraction", "pal_parse_ok"),
        ("pal_safety_ok_fraction", "pal_safety_ok"),
        ("pal_exec_ok_fraction", "pal_exec_ok"),
        ("pal_stdout_present_fraction", "pal_stdout_present"),
        ("pal_candidate_strong_fraction", "pal_candidate_strong"),
        ("pal_overlay_triggered_fraction", "pal_overlay_triggered"),
        ("pal_integration_fix_triggered_fraction", "pal_integration_fix_triggered"),
    ]

    (bd / "paired_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    manifest = {
        "bundle_dir": str(bd),
        "paired_methods": [EXT_METHOD, PAL_METHOD],
        "paired_examples_completed": n,
        "selected_fresh_example_ids": sorted(common),
        "rows_in_per_example_jsonl": len(rows),
        "logical_api_calls_cap_requested": 360,
        "paired_batch_completion_note": (
            "When `--max-total-api-calls 360` is hit mid-trajectory, later queue items fail fast; "
            "paired rows in this bundle are defined by intersections of scored PAL and scored external rows "
            "(orphan singleton rows remain in split CSV/JSON but are omitted from pairing)."
            + (
                f" First cap-hit row: `{summary['first_example_id_logical_cap_failure']}`."
                if summary.get("first_example_id_logical_cap_failure")
                else ""
            )
        ),
        "cohort_note": summary["cohort_design_note"],
        "paired_summary_digest": {
            "total_cohere_logical_api_calls_row_sum": int(total_calls_per_example_sum),
            "logical_api_budget_cap_consumed_estimate": inferred_global_budget,
            "external_exact_rate": ext_acc,
            "pal_exact_rate": pal_acc,
            "gap_external_minus_pal_pp": gap_pp,
            "failures_logged": summary["failed_rows"],
        },
    }
    (bd / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    with (bd / "selected_cases.csv").open("w", encoding="utf-8", newline="") as sf:
        ww = csv.DictWriter(sf, fieldnames=["example_id", "question", "gold_answer"])
        ww.writeheader()
        for r in paired:
            ww.writerow({"example_id": r["example_id"], "question": r["question"], "gold_answer": r["gold_answer"]})

    if paired:
        fieldnames = list(paired[0].keys())
        with (bd / "paired_casebook.csv").open("w", encoding="utf-8", newline="") as cf:
            w = csv.DictWriter(cf, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(paired)

        exec_fields = [
            "example_id",
            "pal_seed_ran",
            "pal_budget_cost_observed",
            "pal_code_present",
            "pal_json_answer_present",
            "pal_confidence_present",
            "pal_parse_ok",
            "pal_safety_ok",
            "pal_exec_ok",
            "pal_stdout_present",
            "pal_answer_raw",
            "pal_answer_normalized",
            "pal_error_type",
            "pal_candidate_strong",
            "pal_overlay_triggered",
            "pal_integration_fix_triggered",
            "pal_exact",
        ]
        with (bd / "pal_execution_audit.csv").open("w", encoding="utf-8", newline="") as ef:
            ww = csv.DictWriter(ef, fieldnames=exec_fields)
            ww.writeheader()
            for r in paired:
                ww.writerow({k: r.get(k, "") for k in exec_fields})

        disc_fields = [
            "example_id",
            "pal_corrected_gold_in_tree",
            "pal_discovery3_candidate_gold_present",
            "pal_final_nodes_normalized_answers_json",
            "pal_selector_candidate_pool_json",
        ]
        with (bd / "pal_discovery3_audit.csv").open("w", encoding="utf-8", newline="") as df:
            ww = csv.DictWriter(df, fieldnames=disc_fields)
            ww.writeheader()
            for r in paired:
                ww.writerow({k: r.get(k, "") for k in disc_fields})

    for method, name in [(EXT_METHOD, "external_l1"), (PAL_METHOD, "pal")]:
        sub = [r for r in rows if r.get("method") == method]
        if not sub:
            continue
        (bd / f"{name}_results.jsonl").write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in sub) + "\n", encoding="utf-8"
        )
        keys = sorted({k for r in sub for k in r.keys()})
        with (bd / f"{name}_results.csv").open("w", encoding="utf-8", newline="") as cf:
            ww = csv.DictWriter(cf, fieldnames=keys)
            ww.writeheader()
            for r in sub:
                flat = {k: _j(r[k]) if isinstance(r.get(k), (dict, list)) else r.get(k, "") for k in keys}
                ww.writerow(flat)

    failed = [r for r in rows if int(r.get("failed", 0)) == 1]
    (bd / "failed_or_skipped_calls.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in failed) + ("\n" if failed else ""),
        encoding="utf-8",
    )
    (bd / "call_usage_summary.json").write_text(
        json.dumps(
            {
                "total_logical_calls_row_sum": int(total_calls_per_example_sum),
                "logical_api_budget_cap_consumed_estimate": inferred_global_budget,
                "calls_by_method_row_sum_all_rows": dict(by_method),
                "rows_n": len(rows),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    competitive = bool(summary["interpretation_competitive_abs_gap_at_most_5pp"])
    more_sampling = bool(summary["interpretation_more_paired_sampling_justified"])
    lines = [
        "# Paired pilot: external_l1_max vs PAL (fresh allowlist)",
        "",
        f"- Planned allowlist cohort: larger than `{n}` pairs; finalized **full pairs `{n}`** after global logical-call cap behavior (see manifest / `paired_summary.json`).",
        "",
        f"- Paired rows: **{n}**",
        f"- External exact: **{ext_acc:.3f}**",
        f"- PAL exact: **{pal_acc:.3f}**",
        f"- Gap (external − PAL, percentage points): **{gap_pp}**",
        f"- Total logical API calls (sum of `cohere_logical_api_calls`, per-example counters): **{total_calls_per_example_sum}**",
        f"- Logical API budget cap consumed (infer from RuntimeError): **{inferred_global_budget!s}**",
        "",
        "## Pair outcomes",
    ]
    for k, v in sorted(outcomes.items()):
        lines.append(f"- {k}: **{v}**")
    lines += [
        "",
        "## PAL quality",
        f"- gold_in_tree: **{git_n}/{n}**",
        f"- discovery3 gold in augmented norms: **{d3_n}/{n}**",
        f"- present-not-selected: **{pns}/{n}**",
        f"- gold-absent proxy: **{gabs}/{n}**",
        "",
        "### PAL subsystem rates",
    ]
    for sk, lbl in subsystem_rate_lines:
        fr = summary.get(sk)
        lines.append(f"- {lbl}: **{_fmt_rate(float(fr)) if isinstance(fr, (int, float)) else 'n/a'}**")
    pal_exok = summary.get("pal_exact_given_exec_ok")
    pal_str = summary.get("pal_exact_given_candidate_strong")
    lines += [
        f"- PAL exact | exec_ok: **{('%.3f' % pal_exok if isinstance(pal_exok, float) else 'n/a')}**",
        f"- PAL exact | candidate_strong: **{('%.3f' % pal_str if isinstance(pal_str, float) else 'n/a')}**",
        "",
        "## Interpretation",
        f"- **PAL matches/beats external exact rate?** {summary['interpretation_pal_matches_or_beats_external_exact_rate']}",
        f"- **Head-to-head “close race” |gap|≤5pp?** {competitive}",
        f"- **More paired sampling justified (narrow remaining uncertainty)?** {more_sampling}",
        (
            "- Proposed next logical-call cap if tightening head-to-head mass (≈≥80 pairs feasible): **720**."
            if more_sampling
            else "- Proposed next cap: **≥360** remains optional for confirmation only; larger caps only if widening evaluation."
        ),
        "",
        "- External `discovery3` column is **unavailable** (no PAL-style augmented pool in external metadata).",
    ]
    (bd / "paired_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
