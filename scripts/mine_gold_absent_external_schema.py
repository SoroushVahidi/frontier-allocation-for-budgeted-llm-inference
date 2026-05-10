#!/usr/bin/env python3
"""Offline schema mining for gold-absent PAL failures vs external success (no API, no controllers)."""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

BUNDLE = REPO_ROOT / "outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z"
PAL_METHOD = "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal"

EX_SPECS: tuple[tuple[str, str, str], ...] = (
    ("external_l1_max", "external_l1_max_answer", "external_l1_max_correct"),
    ("external_tale_prompt_budgeting", "external_tale_prompt_budgeting_answer", "external_tale_prompt_budgeting_correct"),
    ("external_s1_budget_forcing", "external_s1_budget_forcing_answer", "external_s1_budget_forcing_correct"),
)

OUT_DIR = REPO_ROOT / "outputs/gold_absent_external_success_schema_mining_20260507"

# Hand-structured labels (problem → schema vs PAL vs external trace), per task spec.
MANUAL: dict[str, dict[str, Any]] = {
    "openai_gsm8k_1099": {
        "required_schemas": "target_mapping_error|aggregation_total|multi_step_chain",
        "pal_failure_modes": "wrong_target_variable",
        "external_success_signals": "used_aggregation_over_groups|directly_answered_target_variable",
        "analyst_notes": "PAL summed cobra+mamba spots correctly but never divided by 2 for 'half the total'.",
    },
    "openai_gsm8k_1125": {
        "required_schemas": "rate_equation|temporal_state_update|multi_step_chain",
        "pal_failure_modes": "wrong_operator|missing_intermediate_state",
        "external_success_signals": "used_rate_times_duration|explicitly_used_missing_quantity",
        "analyst_notes": "PAL multiplied foot-rates instead of adding taps/min per phase then × minutes.",
    },
    "openai_gsm8k_1155": {
        "required_schemas": "unit_conversion|product_grouping",
        "pal_failure_modes": "wrong_operator|arithmetic_from_wrong_relation",
        "external_success_signals": "explicitly_used_missing_quantity",
        "analyst_notes": "PAL mixed inches-as-feet; external uses feet spacing 111/1.5 then buys 57 plants.",
    },
    "openai_gsm8k_1166": {
        "required_schemas": "multi_step_chain|rate_equation",
        "pal_failure_modes": "failed_code_or_empty_code",
        "external_success_signals": "used_state_table_or_before_after_update|directly_answered_target_variable",
        "analyst_notes": "April halves (15+15 days), 15x+30x=1125; need second-half daily (2x). PAL code empty.",
    },
    "openai_gsm8k_1187": {
        "required_schemas": "difference_comparison|multi_step_chain",
        "pal_failure_modes": "arithmetic_from_wrong_relation",
        "external_success_signals": "explicitly_used_missing_quantity|directly_answered_target_variable",
        "analyst_notes": "PAL mis-solved Camden/Sarah split (30,12); external sets C+S=30, C=S+12, 2A+30=56.",
    },
    "openai_gsm8k_1198": {
        "required_schemas": "temporal_state_update|multi_step_chain",
        "pal_failure_modes": "overcompressed_one_expression|missing_intermediate_state",
        "external_success_signals": "used_state_table_or_before_after_update",
        "analyst_notes": "Multi-day chalk decay until <2in; PAL only 20% of initial chunk.",
    },
    "openai_gsm8k_1215": {
        "required_schemas": "difference_comparison|multi_step_chain",
        "pal_failure_modes": "failed_code_or_empty_code",
        "external_success_signals": "explicitly_used_missing_quantity|directly_answered_target_variable",
        "analyst_notes": "PAL references undefined james_run; external equates James total to Jon+10.",
    },
    "openai_gsm8k_1230": {
        "required_schemas": "aggregation_total|proportional_scaling",
        "pal_failure_modes": "wrong_target_variable",
        "external_success_signals": "used_aggregation_over_groups|directly_answered_target_variable",
        "analyst_notes": "PAL summed geometric levels but question asks average (divide by 4).",
    },
    "openai_gsm8k_1244": {
        "required_schemas": "unit_conversion|multi_step_chain",
        "pal_failure_modes": "wrong_target_variable",
        "external_success_signals": "directly_answered_target_variable|used_rate_times_duration",
        "analyst_notes": "PAL stops at days; need weeks (÷7).",
    },
    "openai_gsm8k_1248": {
        "required_schemas": "target_mapping_error|multi_step_chain",
        "pal_failure_modes": "arithmetic_from_wrong_relation",
        "external_success_signals": "explicitly_used_missing_quantity|used_aggregation_over_groups",
        "analyst_notes": "Infer box size (8) from Jam; combine pencils; PAL mis-boxes Meg.",
    },
    "openai_gsm8k_1281": {
        "required_schemas": "multi_step_chain|aggregation_total",
        "pal_failure_modes": "omitted_quantity|arithmetic_from_wrong_relation",
        "external_success_signals": "explicitly_used_missing_quantity|used_aggregation_over_groups",
        "analyst_notes": "Scene line counts + fractions; PAL undercounts scene1 Sean lines (needs full 108×2 then /3).",
    },
    # Secondary: gold_absent + both externals wrong — longest S1 trace used for comparison.
    "openai_gsm8k_1081": {
        "required_schemas": "temporal_state_update|rate_equation|multi_step_chain",
        "pal_failure_modes": "wrong_operator|arithmetic_from_wrong_relation",
        "external_success_signals": "other",
        "analyst_notes": "Compounding annual salary from monthly base; PAL used single 600*1.1**3; externals also confused.",
        "selection_tier": "secondary_both_wrong",
    },
    "openai_gsm8k_1112": {
        "required_schemas": "aggregation_total|difference_comparison",
        "pal_failure_modes": "failed_code_or_empty_code",
        "external_success_signals": "other",
        "analyst_notes": "PAL truncates mid-expense expression; S1 computes costs then profit but still fails later.",
        "selection_tier": "secondary_both_wrong",
    },
    "openai_gsm8k_1115": {
        "required_schemas": "temporal_state_update|multi_step_chain",
        "pal_failure_modes": "wrong_operator",
        "external_success_signals": "used_aggregation_over_groups",
        "analyst_notes": "Sequential land sales: remaining area then $/m²; PAL adds headline prices only.",
        "selection_tier": "secondary_both_wrong",
    },
    "openai_gsm8k_1132": {
        "required_schemas": "aggregation_total|product_grouping",
        "pal_failure_modes": "wrong_operator|arithmetic_from_wrong_relation",
        "external_success_signals": "used_aggregation_over_groups",
        "analyst_notes": "Room-type candle counts + flashlight story; PAL double-counts flashlights pattern.",
        "selection_tier": "secondary_both_wrong",
    },
    "openai_gsm8k_1137": {
        "required_schemas": "temporal_state_update|multi_step_chain",
        "pal_failure_modes": "wrong_operator",
        "external_success_signals": "used_state_table_or_before_after_update",
        "analyst_notes": "Toy demand tracks dog count over arrivals/departures; PAL linear 4+8+8+3.",
        "selection_tier": "secondary_both_wrong",
    },
    "openai_gsm8k_1139": {
        "required_schemas": "difference_comparison|multi_step_chain",
        "pal_failure_modes": "wrong_operator",
        "external_success_signals": "explicitly_used_missing_quantity",
        "analyst_notes": "Baseline 4×8 plus extra weeks; PAL subtracts exceptions instead of replacing baseline.",
        "selection_tier": "secondary_both_wrong",
    },
    "openai_gsm8k_1144": {
        "required_schemas": "multi_step_chain|aggregation_total",
        "pal_failure_modes": "failed_code_or_empty_code",
        "external_success_signals": "explicitly_used_missing_quantity",
        "analyst_notes": "500-apple family equation; PAL code incomplete; S1 sets up linear sum.",
        "selection_tier": "secondary_both_wrong",
    },
    "openai_gsm8k_1147": {
        "required_schemas": "target_mapping_error|multi_step_chain",
        "pal_failure_modes": "wrong_target_variable",
        "external_success_signals": "other",
        "analyst_notes": "Q asks meditation time only; PAL adds yoga hours; S1 also conflates.",
        "selection_tier": "secondary_both_wrong",
    },
    "openai_gsm8k_1158": {
        "required_schemas": "aggregation_total|difference_comparison",
        "pal_failure_modes": "wrong_operator|arithmetic_from_wrong_relation",
        "external_success_signals": "used_aggregation_over_groups",
        "analyst_notes": "PAL sums raw deltas+amounts; need sequential 'more than' reconstruction of each girl's total.",
        "selection_tier": "secondary_both_wrong",
    },
    "openai_gsm8k_1162": {
        "required_schemas": "multi_step_chain|rate_equation",
        "pal_failure_modes": "wrong_target_variable|arithmetic_from_wrong_relation",
        "external_success_signals": "other",
        "analyst_notes": "Weekly spend split across toy types; PAL/S1 disagree on final count interpretation.",
        "selection_tier": "secondary_both_wrong",
    },
}


def _load_cb() -> dict[str, dict[str, str]]:
    with (BUNDLE / "all_casebook.csv").open(encoding="utf-8", newline="") as f:
        return {r["case_id"]: r for r in csv.DictReader(f) if r.get("case_id")}


def _load_ga() -> set[str]:
    out: set[str] = set()
    with (BUNDLE / "failure_cluster_summary.csv").open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("failure_type") == "gold_absent_discovery":
                out.add(row["case_id"])
    return out


def _load_selected() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    with (BUNDLE / "selected_failure_cases.jsonl").open(encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            cid = str(d.get("case_id") or "")
            if cid:
                out[cid] = d
    return out


def _load_pal_results(ga: set[str]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    with (BUNDLE / "all_results.jsonl").open(encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            if d.get("method") != PAL_METHOD:
                continue
            cid = str(d.get("case_id") or "")
            if cid in ga:
                out[cid] = d
    return out


def _nodes_reasoning(fn: Any) -> str:
    if not isinstance(fn, list):
        return ""
    parts: list[str] = []
    for n in fn:
        if isinstance(n, dict):
            t = str(n.get("reasoning_text") or "").strip()
            if t:
                parts.append(t)
    return "\n".join(parts)


def _pick_external_trace(
    cb: dict[str, str],
    sel: dict[str, Any],
    *,
    require_correct: bool,
) -> tuple[str, str, str, str]:
    """Return (method_name, answer, correctness_0_1, reasoning_concat)."""
    mr_all = sel.get("method_records") or {}
    if not isinstance(mr_all, dict):
        return "", "", "", ""

    best: tuple[int, str, str, str, str] = (-1, "", "", "", "")

    for mname, acol, ccol in EX_SPECS:
        mr = mr_all.get(mname)
        if not isinstance(mr, dict):
            continue
        corr = cb.get(ccol) == "1"
        if require_correct and not corr:
            continue
        if not require_correct and corr:
            continue
        txt = _nodes_reasoning(mr.get("final_nodes"))
        ln = len(txt)
        if ln > best[0]:
            best = (ln, mname, str(cb.get(acol) or ""), "1" if corr else "0", txt)

    if best[0] <= 0 and not require_correct:
        for mname, acol, ccol in EX_SPECS:
            mr = mr_all.get(mname)
            if not isinstance(mr, dict):
                continue
            txt = _nodes_reasoning(mr.get("final_nodes"))
            ln = len(txt)
            if ln > best[0]:
                best = (ln, mname, str(cb.get(acol) or ""), "1" if cb.get(ccol) == "1" else "0", txt)

    if best[0] <= 0:
        return "", "", "", ""
    return best[1], best[2], best[3], best[4]


def _static_row(audit_csv: Path, cid: str) -> dict[str, str] | None:
    if not audit_csv.is_file():
        return None
    with audit_csv.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("case_id") != cid:
                continue
            if row.get("bundle_slug") != BUNDLE.name:
                continue
            if row.get("audit_cohort") != "gold_absent_discovery":
                continue
            return row
    return None


def _pal_exec(pal: dict[str, Any]) -> dict[str, Any]:
    px = pal.get("pal_execution")
    return px if isinstance(px, dict) else {}


def main() -> None:
    cb = _load_cb()
    ga = _load_ga()
    sel = _load_selected()
    pal_by = _load_pal_results(ga)
    audit_path = (
        REPO_ROOT
        / "outputs/gsm8k_structural_validator_eval_20260507/pal_code_static_audit_scaled/pal_code_static_audit_scaled.csv"
    )

    rows_out: list[dict[str, Any]] = []
    primary_ids = sorted(
        cid
        for cid in ga
        if cb[cid]["pal_correct"] != "1" and cb[cid]["best_external_correct"] == "1"
    )
    secondary_ids = sorted(
        cid for cid in ga if cb[cid]["pal_correct"] != "1" and cb[cid]["best_external_correct"] != "1"
    )

    def ingest(cid: str, tier: str) -> None:
        cbrow = cb[cid]
        srow = sel[cid]
        require_correct = tier == "primary_external_correct"
        em, eans, ecok, etext = _pick_external_trace(cbrow, srow, require_correct=require_correct)
        pal = pal_by.get(cid, {})
        px = _pal_exec(pal)
        er = px.get("pal_execution_result") if isinstance(px.get("pal_execution_result"), dict) else {}
        st = _static_row(audit_path, cid)
        trig_bits = []
        if st:
            for col in (
                "temporal_cue_required",
                "rate_cue_required",
                "syntax_ok",
                "exec_ok",
                "pal_code_empty",
                "opaque_one_expression_heuristic",
                "quantity_coverage_validator",
                "n_unused_salient_quantities",
            ):
                if col in st:
                    trig_bits.append(f"{col}={st[col]}")
        man = MANUAL[cid]
        rows_out.append(
            {
                "case_id": cid,
                "selection_tier": man.get("selection_tier", tier),
                "problem_text": cbrow.get("question", ""),
                "gold_answer": cbrow.get("gold_answer", ""),
                "pal_answer": cbrow.get("pal_answer", ""),
                "pal_code": px.get("pal_code", ""),
                "pal_stdout_preview": str(er.get("pal_stdout", "") or "")[:500],
                "pal_exec_ok": str(er.get("pal_exec_ok", "")),
                "external_method_with_trace": em,
                "external_answer_shown": eans,
                "external_correct_0_1": ecok,
                "external_reasoning_excerpt": etext[:2000],
                "operation_hint_tags": cbrow.get("operation_hint_tags", ""),
                "static_audit_row_present": "1" if st else "0",
                "static_audit_snapshot": "; ".join(trig_bits[:12]),
                "required_schemas": man["required_schemas"],
                "pal_failure_modes": man["pal_failure_modes"],
                "external_success_signals": man["external_success_signals"],
                "analyst_notes": man["analyst_notes"],
            }
        )

    for cid in primary_ids:
        ingest(cid, "primary_external_correct")
    for cid in secondary_ids:
        ingest(cid, "secondary_both_wrong")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fields = list(rows_out[0].keys()) if rows_out else []
    with (OUT_DIR / "schema_mining_cases.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in sorted(rows_out, key=lambda x: (x["selection_tier"].startswith("secondary"), x["case_id"])):
            w.writerow(r)

    def explode_pipe(s: str) -> list[str]:
        return [x.strip() for x in s.split("|") if x.strip()]

    pri = [r for r in rows_out if r["selection_tier"] == "primary_external_correct"]
    sec = [r for r in rows_out if r["selection_tier"] == "secondary_both_wrong"]

    schema_c = Counter()
    fail_c = Counter()
    ext_c = Counter()
    cross: defaultdict[str, Counter[str]] = defaultdict(Counter)
    for r in rows_out:
        for a in explode_pipe(r["required_schemas"]):
            schema_c[a] += 1
        for a in explode_pipe(r["pal_failure_modes"]):
            fail_c[a] += 1
        for a in explode_pipe(r["external_success_signals"]):
            ext_c[a] += 1
        dom_schema = explode_pipe(r["required_schemas"])[0] if r["required_schemas"] else "other"
        for fm in explode_pipe(r["pal_failure_modes"]):
            cross[dom_schema][fm] += 1

    top_schema = schema_c.most_common(5)

    rep_pick = [
        "openai_gsm8k_1099",
        "openai_gsm8k_1125",
        "openai_gsm8k_1155",
        "openai_gsm8k_1187",
        "openai_gsm8k_1198",
    ]
    top5_rep: list[dict[str, str]] = []
    for cid in rep_pick:
        for r in rows_out:
            if r["case_id"] == cid:
                top5_rep.append(
                    {
                        "case_id": cid,
                        "required_schemas": r["required_schemas"],
                        "pal_failure_modes": r["pal_failure_modes"],
                        "external_method_with_trace": r["external_method_with_trace"],
                    }
                )
                break

    retry_ideas = [
        {
            "idea": "state_table_temporal_retry",
            "targets_schema": ["temporal_state_update"],
            "approx_cases_primary": sum(1 for r in pri if "temporal_state_update" in r["required_schemas"]),
            "approx_cases_all": sum(1 for r in rows_out if "temporal_state_update" in r["required_schemas"]),
            "clear_trigger": "medium",
            "guardrail_risk": "high_if_misdetects_multiplicative_rate_problems",
            "needs_api_now": False,
            "offline_testable": True,
        },
        {
            "idea": "rate_equation_retry",
            "targets_schema": ["rate_equation"],
            "approx_cases_primary": sum(1 for r in pri if "rate_equation" in r["required_schemas"]),
            "approx_cases_all": sum(1 for r in rows_out if "rate_equation" in r["required_schemas"]),
            "clear_trigger": "low",
            "guardrail_risk": "high",
            "needs_api_now": False,
            "offline_testable": True,
        },
        {
            "idea": "aggregation_total_retry",
            "targets_schema": ["aggregation_total"],
            "approx_cases_primary": sum(1 for r in pri if "aggregation_total" in r["required_schemas"]),
            "approx_cases_all": sum(1 for r in rows_out if "aggregation_total" in r["required_schemas"]),
            "clear_trigger": "low",
            "guardrail_risk": "medium",
            "needs_api_now": False,
            "offline_testable": True,
        },
        {
            "idea": "target_variable_rewrite_retry",
            "targets_schema": ["target_mapping_error"],
            "approx_cases_primary": sum(1 for r in pri if "target_mapping_error" in r["required_schemas"]),
            "approx_cases_all": sum(1 for r in rows_out if "target_mapping_error" in r["required_schemas"]),
            "clear_trigger": "low_without_NLU",
            "guardrail_risk": "medium",
            "needs_api_now": False,
            "offline_testable": "partial_keyword_checks_only",
        },
        {
            "idea": "quantity_grounding_retry",
            "targets_schema": ["unit_conversion", "product_grouping"],
            "approx_cases_primary": sum(
                1
                for r in pri
                if "unit_conversion" in r["required_schemas"] or "product_grouping" in r["required_schemas"]
            ),
            "approx_cases_all": sum(
                1
                for r in rows_out
                if "unit_conversion" in r["required_schemas"] or "product_grouping" in r["required_schemas"]
            ),
            "clear_trigger": "medium_for_unit_mismatch_heuristics",
            "guardrail_risk": "medium",
            "needs_api_now": False,
            "offline_testable": True,
        },
    ]

    summary = {
        "bundle": str(BUNDLE),
        "gold_absent_discovery_total": len(ga),
        "primary_external_correct_n": len(primary_ids),
        "secondary_both_wrong_n": len(secondary_ids),
        "cases_documented": len(rows_out),
        "schema_counts_all": dict(schema_c),
        "pal_failure_mode_counts_all": dict(fail_c),
        "external_success_signal_counts_all": dict(ext_c),
        "schema_x_pal_failure_cross": {k: dict(v) for k, v in sorted(cross.items())},
        "top_repeated_schemas": top_schema,
        "top_5_representative_primary_cases": top5_rep,
        "primary_cases_for_manual_review": [r["case_id"] for r in pri],
        "retry_idea_estimates": retry_ideas,
        "verdict": {
            "strongest_repeated_schema": top_schema[0][0] if top_schema else None,
            "recommended_next_step": (
                "Targeted prompting for multi_step_chain + explicit final target restatement "
                "(addresses wrong_target_variable and many relation errors) before narrow rate/table triggers."
            ),
            "algorithmic_path_clarity": (
                "Moderate: recurring PAL errors cluster on target mis-read, staged totals, and unit/phase modeling — "
                "but n=11 primary successes limits trigger design; scale labeled failures before implementation."
            ),
        },
    }

    (OUT_DIR / "schema_mining_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    def md_table(rows: list[dict[str, Any]], cols: list[str]) -> str:
        header = "| " + " | ".join(cols) + " |"
        sep = "| " + " | ".join("---" for _ in cols) + " |"
        lines = [header, sep]
        for r in rows:
            lines.append("| " + " | ".join(str(r.get(c, ""))[:120].replace("\n", " ") for c in cols) + " |")
        return "\n".join(lines)

    compact = [
        {
            "case_id": r["case_id"],
            "tier": r["selection_tier"],
            "schemas": r["required_schemas"],
            "pal_fail": r["pal_failure_modes"],
            "ext_ok": r["external_correct_0_1"],
        }
        for r in sorted(rows_out, key=lambda x: x["case_id"])
    ]

    report = "\n".join(
        [
            "# Gold-absent schema mining (external-correct vs PAL-wrong)",
            "",
            "## A. Why validator-trigger implementation is paused",
            "",
            "Scaled PAL-code static triggers did not meet the **promising** usefulness band "
            "(high recall on `gold_absent_discovery` with low guardrail FPs) in "
            "`outputs/gsm8k_structural_validator_eval_20260507/pal_code_static_audit_scaled/`. "
            "Automating retries from those signals alone would add noise.",
            "",
            "## B. Case selection",
            "",
            f"- **Gold-absent pool:** {len(ga)} cases (`failure_cluster_summary.csv`).",
            f"- **Primary:** PAL wrong ∧ **any external correct** ∧ `final_nodes` reasoning text from a correct external "
            f"→ **{len(primary_ids)}** cases.",
            f"- **Secondary:** both PAL and best external wrong — included for contrast using **longest** "
            f"`external_s1_budget_forcing` trace when available → **{len(secondary_ids)}** cases.",
            "",
            md_table(compact, ["case_id", "tier", "schemas", "pal_fail", "ext_ok"]),
            "",
            "## C. Schema / failure-mode table (full rows)",
            "",
            "See `schema_mining_cases.csv` for problem text, PAL code, stdout, full external reasoning excerpts, "
            "operation tags, and static-audit snapshots.",
            "",
            "## D. External-success comparison",
            "",
            "Externals often succeed by (1) **staged arithmetic** (remainders, halves, multi-day updates), "
            "(2) **explicit target restatement** (average vs sum, weeks vs days), "
            "(3) **additive rate×time** instead of multiplying incompatible rates.",
            "",
            "### Top 5 representative primary cases (hand-picked diversity)",
            "",
            "```json",
            json.dumps(top5_rep, indent=2),
            "```",
            "",
            "## E. Top repeated missing schemas (counts over all 21)",
            "",
            "```json",
            json.dumps(dict(schema_c.most_common()), indent=2),
            "```",
            "",
            "### Schema × dominant PAL failure (first schema token cross fail-modes)",
            "",
            "```json",
            json.dumps({k: dict(v) for k, v in sorted(cross.items())}, indent=2),
            "```",
            "",
            "## F. Candidate targeted retry ideas",
            "",
            "```json",
            json.dumps(retry_ideas, indent=2),
            "```",
            "",
            "## G. Which idea to implement next",
            "",
            summary["verdict"]["recommended_next_step"],
            "",
            f"**Dominant counted schema:** `{summary['verdict']['strongest_repeated_schema']}`.",
            "",
            "## H. API needed now?",
            "",
            "**No.** This analysis uses archived traces and code only.",
            "",
            "## I. Exact next query",
            "",
            "> Prototype **offline** a *target-restatement + staged checklist* PAL retry template on "
            f"**{len(primary_ids)}** primary cases: force explicit “quantity asked” / units / final transform "
            "(half, average, weeks) before codegen; benchmark precision on expanded gold-absent CSV before any API.",
            "",
        ]
    )
    (OUT_DIR / "schema_mining_report.md").write_text(report, encoding="utf-8")
    print(f"Wrote {OUT_DIR}")


if __name__ == "__main__":
    main()
