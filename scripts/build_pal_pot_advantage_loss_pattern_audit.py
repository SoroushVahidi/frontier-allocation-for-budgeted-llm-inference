#!/usr/bin/env python3
"""No-API PAL advantage + external-oracle loss-pattern audit (writes outputs/)."""

from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


EXT_KEYS = [
    "external_l1_max_fair_v1",
    "external_self_consistency_4_fair_v1",
    "external_self_consistency_6_fair_v1",
    "external_pal_pot_fair_v1",
    "external_s1_budget_forcing_faithful_v1",
    "external_tale_ep_prompt_budgeting_faithful_v1",
]


def ib(x: str | int | None) -> bool:
    return int(x or 0) == 1


def _sanitize_cell(text: str) -> str:
    return " ".join((text or "").replace("\r", " ").replace("\n", " ").split())


def classify_family(problem: str, prod_row: dict[str, str]) -> tuple[str, str]:
    if ib(prod_row.get("parsing_failure")):
        return "production_parse_failure", "production_equiv parsing_failure=1"
    t = (problem or "").lower()
    if re.search(r"\b(per hour|mph|meters per second|times (as fast|faster)|ratio|percent|%)\b", t):
        return "rate_ratio_arithmetic", "rate/ratio/percent cues"
    if re.search(r"\b(before|after|remaining|left|starts with|had \d+)\b", t):
        return "state_update_arithmetic", "before/after/state-update cues"
    if len(re.findall(r"\d", problem)) >= 8:
        return "multi_step_computation", "high numeric density"
    if re.search(r"\b(fraction|half|third|quarter|\d+/\d+)\b", t):
        return "arithmetic_execution", "fraction cues"
    if len(re.findall(r"\d", problem)) >= 5:
        return "multi_step_computation", "moderate numeric density"
    return "unknown", "no strong heuristic hit"


def main() -> None:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = REPO / "outputs" / f"pal_pot_advantage_loss_pattern_audit_{ts}"
    out.mkdir(parents=True, exist_ok=True)

    suite = REPO / "outputs/external_full_suite_matched50_comparison_20260508T222631Z/external_full_suite_case_outcomes.csv"
    prod_csv = sorted(
        (REPO / "outputs").glob("production_equiv_v1_stage3_50_live_checkpoint_rerun_*/live_checkpoint_results.csv")
    )[-1]
    pal_csv = REPO / "outputs/external_pal_pot_fair_50case_live_20260508T222348Z/live_results.csv"
    sc6_csv = REPO / "outputs/external_sc6_fair_50case_live_20260508T221625Z/live_results.csv"

    outcomes = list(csv.DictReader(open(suite, encoding="utf-8")))
    prod_by = {r["case_id"]: r for r in csv.DictReader(open(prod_csv, encoding="utf-8"))}
    pal_by = {r["case_id"]: r for r in csv.DictReader(open(pal_csv, encoding="utf-8"))}

    pal_adv_rows: list[dict[str, str]] = []
    oracle_rows: list[dict[str, str]] = []

    pal_fam = Counter()
    ora_fam = Counter()

    for row in outcomes:
        cid = row["case_id"]
        pe = ib(row["production_equiv_v1"])
        pal_ok = ib(row["external_pal_pot_fair_v1"])
        pr = prod_by[cid]
        pal_r = pal_by[cid]
        sc6_ok = ib(row["external_self_consistency_6_fair_v1"])
        sc4_ok = ib(row["external_self_consistency_4_fair_v1"])
        tale_ok = ib(row["external_tale_ep_prompt_budgeting_faithful_v1"])
        s1_ok = ib(row["external_s1_budget_forcing_faithful_v1"])
        l1_ok = ib(row["external_l1_max_fair_v1"])

        winners = [k for k in EXT_KEYS if ib(row[k])]
        any_ext = bool(winners)

        if not pe and pal_ok:
            fam, note = classify_family(pr.get("problem_text", ""), pr)
            pal_fam[fam] += 1
            pal_adv_rows.append(
                {
                    "case_id": cid,
                    "problem_text": _sanitize_cell(pr.get("problem_text", "")),
                    "gold_answer": pr.get("gold_answer", ""),
                    "production_equiv_answer": pr.get("production_equiv_answer", ""),
                    "pal_pot_answer": pal_r.get("parsed_answer", ""),
                    "production_equiv_surface_source": pr.get("production_equiv_surface_source", ""),
                    "production_equiv_parsing_failure": str(pr.get("parsing_failure", "")),
                    "pal_pot_parsing_failure": str(pal_r.get("parsing_failure", "")),
                    "production_equiv_metadata_path": pr.get("metadata_path", ""),
                    "pal_pot_metadata_path": pal_r.get("metadata_path", ""),
                    "whether_sc6_correct": str(int(sc6_ok)),
                    "whether_sc4_correct": str(int(sc4_ok)),
                    "whether_tale_correct": str(int(tale_ok)),
                    "whether_s1_correct": str(int(s1_ok)),
                    "whether_l1_correct": str(int(l1_ok)),
                    "likely_pal_advantage_family": fam,
                    "notes": note,
                }
            )

        if not pe and any_ext:
            pal_only = winners == ["external_pal_pot_fair_v1"]
            multi = len(winners) > 1
            fam2, n2 = classify_family(pr.get("problem_text", ""), pr)
            ora_fam[fam2] += 1
            oracle_rows.append(
                {
                    "case_id": cid,
                    "winning_external_methods": ";".join(winners),
                    "gold_answer": pr.get("gold_answer", ""),
                    "production_equiv_answer": pr.get("production_equiv_answer", ""),
                    "likely_family": fam2,
                    "is_pal_only_win": str(pal_only).lower(),
                    "is_multi_external_win": str(multi).lower(),
                    "actionable_pattern_candidate": "yes" if fam2 not in ("unknown", "production_parse_failure") else "no",
                    "notes": n2 + ("; multi_external" if multi else ""),
                }
            )

    prod_corr = sum(ib(r["production_equiv_v1"]) for r in outcomes)
    pal_corr = sum(ib(r["external_pal_pot_fair_v1"]) for r in outcomes)
    oracle_corr = sum(ib(r["best_full_external_oracle"]) for r in outcomes)
    prod_wrong_oracle_right = sum((not ib(r["production_equiv_v1"])) and ib(r["best_full_external_oracle"]) for r in outcomes)

    pe_adv_over_pal = sum(ib(r["production_equiv_v1"]) and not ib(r["external_pal_pot_fair_v1"]) for r in outcomes)

    recurring = [f for f, c in pal_fam.items() if c >= 3]
    weak = [f for f, c in pal_fam.items() if 1 <= c <= 2]

    actionable_found = bool(recurring)

    mechanism = ""
    if actionable_found:
        mechanism = (
            "offline_design for targeted numeric/code-adjacent scaffolding on dominant families: "
            + ", ".join(recurring)
            + " (no patch in this step)."
        )
    no_pattern_action = (
        "Reframe claims; PAL wins are heterogeneous keyword buckets—no >=3-case recurring family "
        "beyond coarse buckets; defer improvement until larger failure bank or budget framing study."
    )

    summary = {
        "production_equiv_correct": prod_corr,
        "pal_pot_correct": pal_corr,
        "best_external_oracle_correct": oracle_corr,
        "pal_pot_advantage_count": len(pal_adv_rows),
        "production_equiv_advantage_over_pal_count": pe_adv_over_pal,
        "external_oracle_advantage_count": len(oracle_rows),
        "production_equiv_wrong_best_external_oracle_correct_count": prod_wrong_oracle_right,
        "family_counts_for_pal_advantage": dict(pal_fam),
        "family_counts_for_external_oracle_advantage": dict(ora_fam),
        "recurring_actionable_families": recurring,
        "weak_families": weak,
        "whether_actionable_pattern_found": actionable_found,
        "if_actionable_pattern_found_recommended_mechanism": mechanism or None,
        "if_no_actionable_pattern_recommended_action": no_pattern_action if not actionable_found else None,
        "no_api_calls": True,
    }

    decision = {}
    if len(pal_adv_rows) < 4:
        decision = {"decision": "collect_more_pal_advantage_cases", "reason": "few PAL-only wins on matched-50"}
    elif actionable_found:
        decision = {
            "decision": "improve_against_pal_pattern",
            "reason": f"recurring families (>={3}) in PAL advantage set: {recurring}",
        }
    else:
        decision = {
            "decision": "stop_improvement_and_reframe_claims",
            "reason": "PAL advantage families are sparse/heuristic-only (no family >=3); heterogeneous arithmetic wins",
        }

    fields_pal = list(pal_adv_rows[0].keys()) if pal_adv_rows else [
        "case_id",
        "problem_text",
        "gold_answer",
        "production_equiv_answer",
        "pal_pot_answer",
        "production_equiv_surface_source",
        "production_equiv_parsing_failure",
        "pal_pot_parsing_failure",
        "production_equiv_metadata_path",
        "pal_pot_metadata_path",
        "whether_sc6_correct",
        "whether_sc4_correct",
        "whether_tale_correct",
        "whether_s1_correct",
        "whether_l1_correct",
        "likely_pal_advantage_family",
        "notes",
    ]
    with (out / "pal_pot_advantage_cases.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields_pal)
        w.writeheader()
        for r in pal_adv_rows:
            w.writerow(r)

    fields_o = list(oracle_rows[0].keys()) if oracle_rows else [
        "case_id",
        "winning_external_methods",
        "gold_answer",
        "production_equiv_answer",
        "likely_family",
        "is_pal_only_win",
        "is_multi_external_win",
        "actionable_pattern_candidate",
        "notes",
    ]
    with (out / "external_oracle_advantage_cases.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields_o)
        w.writeheader()
        for r in oracle_rows:
            w.writerow(r)

    (out / "pal_pot_advantage_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    claim_md = "\n".join(
        [
            "# Claim revision note (matched-50)",
            "",
            "## Why “beats all external baselines” is unsafe",
            "- PAL/PoT fair reaches **40/50** vs production_equiv **36/50** on the same cases.",
            "- Best six-way external oracle is **43/50**, strictly above production_equiv.",
            "",
            "## Safer claims",
            "- Production-equiv **beats** L1/SC4/S1/TALE-EP and **ties SC6** (**36** each) but **trails PAL/PoT** by **4** on this slice.",
            "- Production-equiv is **competitive** among budgeted narrative methods; **PAL/PoT is the strongest single external** baseline here.",
            "- **Best external oracle** is an **upper bound** over heterogeneous single-method runs, not one deployable policy.",
            "",
            "## Evidence needed for a stronger claim",
            "- Repeated, validated failure families where PAL wins and production-equiv loses, with ablations showing fix lifts **without** hurting PAL-regression cases.",
            "- Larger slices / robustness (not done here).",
            "",
            "## Main table",
            "- **Yes**: promote PAL/PoT (and SC6) to the **main comparison table** alongside core4 for transparency.",
        ]
    )
    (out / "claim_revision_note.md").write_text(claim_md + "\n", encoding="utf-8")

    (out / "next_research_decision.json").write_text(json.dumps(decision, indent=2) + "\n", encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
