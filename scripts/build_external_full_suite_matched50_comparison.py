#!/usr/bin/env python3
"""Build matched-50 external full-suite comparison artifacts (reads existing + new live CSVs)."""

from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def _mcnemar_bc(p: list[bool], c: list[bool]) -> tuple[int, int]:
    b = sum(1 for x, y in zip(p, c) if (not x) and y)
    cc = sum(1 for x, y in zip(p, c) if x and (not y))
    return b, cc


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main() -> None:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = REPO / "outputs" / f"external_full_suite_matched50_comparison_{ts}"
    out.mkdir(parents=True, exist_ok=True)

    prod_csv = sorted((REPO / "outputs").glob("production_equiv_v1_stage3_50_live_checkpoint_rerun_*/live_checkpoint_results.csv"))[
        -1
    ]
    paired_csv = REPO / "outputs/fair_core4_paired_comparison_report_20260508T181853Z/per_case_outcomes.csv"
    prior_csv = REPO / "outputs/fair_core4_vs_our_method_alignment_plan_20260508T181550Z/existing_fair_comparison.csv"
    rescored = REPO / "outputs/core4_50case_parsing_rescore_audit_20260508T181119Z/rescored_summary.json"

    sc6_csv = sorted((REPO / "outputs").glob("external_sc6_fair_50case_live_*/live_results.csv"))[-1]
    pal_csv = sorted((REPO / "outputs").glob("external_pal_pot_fair_50case_live_*/live_results.csv"))[-1]

    prod_by: dict[str, dict[str, str]] = {}
    for r in csv.DictReader(prod_csv.open(encoding="utf-8")):
        prod_by[r["case_id"]] = r
    paired_by: dict[str, dict[str, str]] = {}
    for r in csv.DictReader(open(paired_csv, encoding="utf-8")):
        paired_by[r["case_id"]] = r
    prior_by: dict[str, dict[str, str]] = {}
    for r in csv.DictReader(open(prior_csv, encoding="utf-8")):
        prior_by[r["case_id"]] = r

    sc6_by: dict[str, dict[str, str]] = {}
    for r in csv.DictReader(open(sc6_csv, encoding="utf-8")):
        sc6_by[r["case_id"]] = r
    pal_by: dict[str, dict[str, str]] = {}
    for r in csv.DictReader(open(pal_csv, encoding="utf-8")):
        pal_by[r["case_id"]] = r

    case_ids = sorted(
        prod_by.keys(),
        key=lambda x: (int(x.split("_")[-1]) if x.split("_")[-1].isdigit() else x),
    )

    def ib(b: str) -> bool:
        return int(b or 0) == 1

    outcomes: list[dict[str, Any]] = []
    scores: dict[str, int] = {}

    prod_list: list[bool] = []
    l1_list: list[bool] = []
    sc4_list: list[bool] = []
    sc6_list: list[bool] = []
    pal_list: list[bool] = []
    s1_list: list[bool] = []
    tale_list: list[bool] = []
    best_core4_list: list[bool] = []
    prior_list: list[bool] = []
    best_ind_list: list[bool] = []
    best_full_list: list[bool] = []

    for cid in case_ids:
        pr = ib(prod_by[cid]["exact_match"])
        l1 = ib(paired_by[cid]["l1_correct"])
        sc4 = ib(paired_by[cid]["sc4_correct"])
        sc6 = ib(sc6_by[cid]["exact_match"])
        pal = ib(pal_by[cid]["exact_match"])
        s1 = ib(paired_by[cid]["s1_correct"])
        tale = ib(paired_by[cid]["tale_correct"])
        b4 = ib(paired_by[cid]["best_core4_correct"])
        pif = ib(prior_by[cid]["our_correct"])

        ind_scores = [l1, sc4, sc6, pal, s1, tale]
        best_ind = any(ind_scores)
        best_full = best_ind

        prod_list.append(pr)
        l1_list.append(l1)
        sc4_list.append(sc4)
        sc6_list.append(sc6)
        pal_list.append(pal)
        s1_list.append(s1)
        tale_list.append(tale)
        best_core4_list.append(b4)
        prior_list.append(pif)
        best_ind_list.append(best_ind)
        best_full_list.append(best_full)

        outcomes.append(
            {
                "case_id": cid,
                "production_equiv_v1": int(pr),
                "external_l1_max_fair_v1": int(l1),
                "external_self_consistency_4_fair_v1": int(sc4),
                "external_self_consistency_6_fair_v1": int(sc6),
                "external_pal_pot_fair_v1": int(pal),
                "external_s1_budget_forcing_faithful_v1": int(s1),
                "external_tale_ep_prompt_budgeting_faithful_v1": int(tale),
                "best_individual_external": int(best_ind),
                "best_full_external_oracle": int(best_full),
                "best_core4_oracle": int(b4),
                "prior_patch_focused_integrated": int(pif),
            }
        )

    n = len(case_ids)
    keys = [
        "production_equiv_v1",
        "external_l1_max_fair_v1",
        "external_self_consistency_4_fair_v1",
        "external_self_consistency_6_fair_v1",
        "external_pal_pot_fair_v1",
        "external_s1_budget_forcing_faithful_v1",
        "external_tale_ep_prompt_budgeting_faithful_v1",
        "best_individual_external",
        "best_full_external_oracle",
        "best_core4_oracle",
        "prior_patch_focused_integrated",
    ]
    for k in keys:
        scores[k] = sum(int(r[k]) for r in outcomes)

    best_ind_score = max(
        scores["external_l1_max_fair_v1"],
        scores["external_self_consistency_4_fair_v1"],
        scores["external_self_consistency_6_fair_v1"],
        scores["external_pal_pot_fair_v1"],
        scores["external_s1_budget_forcing_faithful_v1"],
        scores["external_tale_ep_prompt_budgeting_faithful_v1"],
    )
    ind_methods = [
        "external_l1_max_fair_v1",
        "external_self_consistency_4_fair_v1",
        "external_self_consistency_6_fair_v1",
        "external_pal_pot_fair_v1",
        "external_s1_budget_forcing_faithful_v1",
        "external_tale_ep_prompt_budgeting_faithful_v1",
    ]
    best_ind_name = max(ind_methods, key=lambda m: scores[m])
    pe = scores["production_equiv_v1"]

    comparators: list[tuple[str, list[bool]]] = [
        ("external_l1_max_fair_v1", l1_list),
        ("external_self_consistency_4_fair_v1", sc4_list),
        ("external_self_consistency_6_fair_v1", sc6_list),
        ("external_pal_pot_fair_v1", pal_list),
        ("external_s1_budget_forcing_faithful_v1", s1_list),
        ("external_tale_ep_prompt_budgeting_faithful_v1", tale_list),
        ("best_individual_external", best_ind_list),
        ("best_full_external_oracle", best_full_list),
        ("best_core4_oracle", best_core4_list),
        ("prior_patch_focused_integrated", prior_list),
    ]

    paired_rows: list[dict[str, Any]] = []
    for name, clist in comparators:
        p_corr = sum(1 for x in prod_list if x)
        c_corr = sum(1 for x in clist if x)
        both = sum(1 for a, b in zip(prod_list, clist) if a and b)
        p_only = sum(1 for a, b in zip(prod_list, clist) if a and (not b))
        c_only = sum(1 for a, b in zip(prod_list, clist) if (not a) and b)
        bw = sum(1 for a, b in zip(prod_list, clist) if (not a) and (not b))
        mb, mc = _mcnemar_bc(prod_list, clist)
        caveat = ""
        if name in ("external_self_consistency_6_fair_v1", "external_pal_pot_fair_v1"):
            tbl = sc6_by if name == "external_self_consistency_6_fair_v1" else pal_by
            pf = sum(1 for cid in case_ids if int(tbl[cid].get("parsing_failure", 0) or 0) == 1)
            caveat = f"live_50; parsing_failures={pf}"
        elif name in ind_methods:
            rj = json.load(open(rescored, encoding="utf-8")) if Path(rescored).is_file() else {}
            unm = rj.get("unresolved_parsing_failures_by_method", {}) or {}
            pf = int(unm.get(name, 0) or 0) if name in unm else ""
            caveat = f"core4_rescored_audit_unresolved_pf={pf}" if pf != "" else "see core4 checkpoint parsing audit"
        paired_rows.append(
            {
                "comparator": name,
                "production_equiv_correct": p_corr,
                "comparator_correct": c_corr,
                "delta": p_corr - c_corr,
                "both_correct": both,
                "production_equiv_only": p_only,
                "comparator_only": c_only,
                "both_wrong": bw,
                "mcnemar_b": mb,
                "mcnemar_c": mc,
                "parsing_failure_caveat": caveat,
            }
        )

    score_rows = [{"method": k, "correct_50": scores[k]} for k in keys]

    summary = {
        "case_count": n,
        "scores_by_method": scores,
        "best_individual_external_method": best_ind_name,
        "best_individual_external_score": best_ind_score,
        "best_full_external_oracle_score": scores["best_full_external_oracle"],
        "production_equiv_score": pe,
        "production_equiv_minus_best_individual_external": pe - best_ind_score,
        "production_equiv_minus_best_full_external_oracle": pe - scores["best_full_external_oracle"],
        "production_equiv_minus_sc6": pe - scores["external_self_consistency_6_fair_v1"],
        "production_equiv_minus_pal_pot": pe - scores["external_pal_pot_fair_v1"],
        "whether_production_equiv_beats_all_individual_external_baselines": bool(
            pe > scores["external_l1_max_fair_v1"]
            and pe > scores["external_self_consistency_4_fair_v1"]
            and pe > scores["external_self_consistency_6_fair_v1"]
            and pe > scores["external_pal_pot_fair_v1"]
            and pe > scores["external_s1_budget_forcing_faithful_v1"]
            and pe > scores["external_tale_ep_prompt_budgeting_faithful_v1"]
        ),
        "whether_production_equiv_beats_best_external_oracle": bool(pe > scores["best_full_external_oracle"]),
        "whether_main_claim_needs_revision": bool(
            pe
            <= max(
                scores["external_l1_max_fair_v1"],
                scores["external_self_consistency_4_fair_v1"],
                scores["external_self_consistency_6_fair_v1"],
                scores["external_pal_pot_fair_v1"],
                scores["external_s1_budget_forcing_faithful_v1"],
                scores["external_tale_ep_prompt_budgeting_faithful_v1"],
            )
        ),
        "no_api_calls": False,
        "artifact_sources": {
            "production_equiv": str(prod_csv),
            "paired_core4": str(paired_csv),
            "prior_patch": str(prior_csv),
            "sc6_live": str(sc6_csv),
            "pal_live": str(pal_csv),
        },
    }

    _write_csv(out / "external_full_suite_scores.csv", score_rows)
    _write_csv(out / "external_full_suite_case_outcomes.csv", outcomes)
    _write_csv(out / "external_full_suite_paired_summary.csv", paired_rows)
    (out / "external_full_suite_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    report_lines = [
        "# Matched-50 full external suite",
        f"- production_equiv: **{pe}/50**",
        f"- best individual external ({best_ind_name}): **{best_ind_score}/50**",
        f"- SC6: **{scores['external_self_consistency_6_fair_v1']}/50**, PAL: **{scores['external_pal_pot_fair_v1']}/50**",
        f"- beats_all_individual_externals: **{summary['whether_production_equiv_beats_all_individual_external_baselines']}**",
    ]
    (out / "external_full_suite_report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
