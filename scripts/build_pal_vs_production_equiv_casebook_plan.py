#!/usr/bin/env python3
"""No-API plan for PAL vs production_equiv casebook collection."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

MATCHED_50 = REPO / "outputs/main_table_core4_baselines_50case_checkpoint_20260508T174557Z/selected_50case_core4_baseline_cases.csv"
NONOVERLAP_30 = REPO / "outputs/nonoverlap_our_method_discovery3_live_20260508T185859Z/selected_nonoverlap_cases.csv"
CASEBOOK_SOURCE = REPO / "outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z/all_casebook.csv"
CASEBOOK_FALLBACK = REPO / "outputs/stage3_tale_s1_pilot_readiness_20260508T032919Z/stage3_pilot_cases.csv"
CAP = 220
MAX_CASES = 30
MIN_CASES = 20
METHODS = ["production_equiv_v1", "external_pal_pot_fair_v1"]
PLANNED_CALLS_PE = 5
PLANNED_CALLS_PAL = 1


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--case-target", type=int, default=30)
    p.add_argument("--output-dir", type=Path, default=None)
    args = p.parse_args()

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = args.output_dir or (REPO / "outputs" / f"pal_vs_production_equiv_casebook_plan_{ts}")
    out.mkdir(parents=True, exist_ok=True)

    matched = {
        str(r.get("example_id") or r.get("case_id"))
        for r in csv.DictReader(open(MATCHED_50, encoding="utf-8"))
    }

    nonoverlap_ids = set()
    if NONOVERLAP_30.is_file():
        nonoverlap_ids = {r["case_id"] for r in csv.DictReader(open(NONOVERLAP_30, encoding="utf-8"))}

    book_rows = list(csv.DictReader(open(CASEBOOK_SOURCE, encoding="utf-8")))

    def valid_book_row(r: dict[str, str]) -> bool:
        cid = r.get("case_id", "").strip()
        q = (r.get("question") or "").strip()
        g = str(r.get("gold_answer", "") or "").strip()
        return bool(cid and q and g)

    strict = [
        r
        for r in book_rows
        if valid_book_row(r) and r["case_id"] not in matched and r["case_id"] not in nonoverlap_ids
    ]
    excluded_nonoverlap = True
    if len(strict) < MIN_CASES:
        strict = [
            r
            for r in book_rows
            if valid_book_row(r) and r["case_id"] not in matched
        ]
        excluded_nonoverlap = False

    strict.sort(key=lambda r: int(r["case_id"].split("_")[-1]) if r["case_id"].split("_")[-1].isdigit() else r["case_id"])
    n = min(MAX_CASES, max(MIN_CASES, min(args.case_target, len(strict))), len(strict))

    selected = strict[:n]
    sel_rows = []
    for r in selected:
        sel_rows.append(
            {
                "case_id": r["case_id"],
                "problem_text": r["question"].replace("\n", " ").replace("\r", " ").strip(),
                "gold_answer": str(r["gold_answer"]).strip(),
                "source_artifact": str(CASEBOOK_SOURCE.resolve()),
            }
        )

    fields = list(sel_rows[0].keys())
    with (out / "selected_casebook_cases.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(sel_rows)

    plan_rows = []
    for s in sel_rows:
        plan_rows.append(
            {
                "case_id": s["case_id"],
                "method": "production_equiv_v1",
                "planned_logical_calls_estimate": PLANNED_CALLS_PE,
            }
        )
        plan_rows.append(
            {
                "case_id": s["case_id"],
                "method": "external_pal_pot_fair_v1",
                "planned_logical_calls_estimate": PLANNED_CALLS_PAL,
            }
        )
    with (out / "pal_vs_prod_call_plan.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(plan_rows[0].keys()))
        w.writeheader()
        w.writerows(plan_rows)

    est_total = n * (PLANNED_CALLS_PE + PLANNED_CALLS_PAL)
    all_have_text = all(bool(r["problem_text"]) for r in sel_rows)
    all_have_gold = all(bool(r["gold_answer"]) for r in sel_rows)
    ids = [r["case_id"] for r in sel_rows]
    no_dup = len(ids) == len(set(ids))

    manifest = {
        "selected_case_count": n,
        "planned_methods": METHODS,
        "planned_calls_by_method": {"production_equiv_v1": PLANNED_CALLS_PE, "external_pal_pot_fair_v1": PLANNED_CALLS_PAL},
        "estimated_total_calls": est_total,
        "excluded_case_sources": [
            str(MATCHED_50.resolve()),
            str(NONOVERLAP_30.resolve()) if excluded_nonoverlap else "(relaxed: included prior nonoverlap pool)",
        ],
        "primary_case_pool": str(CASEBOOK_SOURCE.resolve()),
        "all_cases_have_problem_text": all_have_text,
        "all_cases_have_gold": all_have_gold,
        "no_duplicate_case_ids": no_dup,
        "no_overlap_with_matched50": all(cid not in matched for cid in ids),
        "no_overlap_with_prior_nonoverlap30": excluded_nonoverlap and all(cid not in nonoverlap_ids for cid in ids),
        "ready_for_live_collection": bool(
            MIN_CASES <= n <= MAX_CASES and est_total <= CAP and all_have_text and all_have_gold and no_dup
        ),
        "logical_call_cap": CAP,
    }
    (out / "casebook_plan_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    report = "\n".join(
        [
            "# PAL vs production_equiv casebook plan",
            f"- selected_case_count: **{n}**",
            f"- estimated_total_calls: **{est_total}** (cap {CAP})",
            f"- methods: {', '.join(METHODS)} (SC6 omitted to stay under cap)",
            f"- ready_for_live_collection: **{manifest['ready_for_live_collection']}**",
            f"- excluded_nonoverlap30_strict: **{excluded_nonoverlap}**",
        ]
    )
    (out / "casebook_plan_report.md").write_text(report + "\n", encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
