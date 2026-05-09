#!/usr/bin/env python3
"""Dry-run: materialize targeted discovery retry prompts (no API)."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from experiments.targeted_discovery_retry import (
    FIRST_COHORT_FAMILIES,
    build_prompt,
    choose_scaffold,
    classify_family_from_row,
    dry_run_eligible,
    order_selected_rows,
    provenance_risk,
    validate_prompt_no_gold,
)

REPO = Path(__file__).resolve().parents[1]

FUTURE_METHOD = (
    "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_"
    "pal_structural_commit_v1_targeted_retry_v1"
)


def parse_anchor_order(anchor_md: Path) -> list[str]:
    if not anchor_md.is_file():
        return []
    text = anchor_md.read_text(encoding="utf-8")
    return re.findall(r"^## (openai_gsm8k_\d+)\s*$", text, re.M)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--diagnosis-dir",
        type=Path,
        default=REPO / "outputs/gold_absent_discovery_diagnosis_20260508T005544Z",
    )
    ap.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Default: outputs/targeted_discovery_retry_v1_dry_run_<utc>",
    )
    args = ap.parse_args()
    diag = args.diagnosis_dir.resolve()
    cases_csv = diag / "gold_absent_discovery_cases.csv"
    anchor_md = diag / "anchor_cases.md"

    if not cases_csv.is_file():
        raise SystemExit(f"missing {cases_csv}")

    with cases_csv.open(encoding="utf-8") as f:
        all_rows = list(csv.DictReader(f))

    anchor_order = parse_anchor_order(anchor_md)
    anchor_ids = frozenset(anchor_order)

    exclusions: Counter[str] = Counter()
    eligible: list[dict[str, str]] = []
    for row in all_rows:
        ok, reason = dry_run_eligible(row, anchor_ids=anchor_ids)
        if not ok:
            exclusions[reason or "unknown"] += 1
        else:
            eligible.append(dict(row))

    ordered = order_selected_rows(eligible, anchor_order)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = args.output_dir or (REPO / "outputs" / f"targeted_discovery_retry_v1_dry_run_{ts}")
    out = out.resolve()
    prompts_dir = out / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)

    scaffold_counts = Counter()
    csv_rows_out: list[dict[str, str]] = []

    for row in ordered:
        cid = row["case_id"]
        fam = classify_family_from_row(row)
        sc = choose_scaffold(row)
        scaffold_counts[sc] += 1
        problem = str(row.get("problem_text") or "").strip()
        prompt = build_prompt(problem, sc)
        if not validate_prompt_no_gold(prompt, row.get("gold_answer")):
            raise SystemExit(f"gold leaked into prompt for {cid}")
        rel = Path("prompts") / f"{cid}_{sc}.txt"
        (out / rel).write_text(prompt, encoding="utf-8")
        ext_pred = str(row.get("external_l1_prediction") or "").strip() or str(
            row.get("best_external_prediction") or ""
        ).strip()
        sel_reason_parts = [f"family={fam}", f"scaffold={sc}"]
        if cid in anchor_ids:
            sel_reason_parts.append("anchor_priority")
        if provenance_risk(row) == "medium":
            sel_reason_parts.append("external_winner_non_l1_ok")
        csv_rows_out.append(
            {
                "case_id": cid,
                "derived_problem_family": fam,
                "selected_scaffold": sc,
                "problem_text": problem,
                "gold_answer": str(row.get("gold_answer") or ""),
                "current_pal_prediction": str(row.get("pal_prediction") or ""),
                "external_prediction_if_available": ext_pred,
                "source_artifacts": str(row.get("source_artifacts") or ""),
                "selection_reason": "; ".join(sel_reason_parts),
                "provenance_risk": provenance_risk(row),
                "prompt_path": str(rel).replace("\\", "/"),
            }
        )

    manifest = {
        "timestamp": ts,
        "no_api_calls": True,
        "source_diagnosis_dir": str(diag.relative_to(REPO)),
        "selected_case_count": len(ordered),
        "scaffold_counts": dict(scaffold_counts),
        "selection_rules": {
            "cohort": "gold_absent_tagged_only",
            "families": sorted(FIRST_COHORT_FAMILIES),
            "scaffold_map": {
                "money_budget": "quantity_ledger",
                "rate_ratio": "rate_table",
                "temporal_change": "before_after_state",
                "difference_comparison": "target_difference",
                "fallback": "quantity_ledger (unused when family filtered)",
            },
            "anchor_priority_source": str((diag / "anchor_cases.md").relative_to(REPO)),
            "exclude_high_provenance_unless_anchor": True,
        },
        "excluded_case_counts_by_reason": dict(exclusions),
        "future_method_name": FUTURE_METHOD,
        "estimated_live_api_calls_if_piloted": len(ordered),
        "budget6_schedule_proposed": "Schedule A — conservative single targeted retry slot for eligible gold-absent cohort",
        "api_required_for_next_step": True,
    }
    (out / "targeted_retry_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    fields = [
        "case_id",
        "derived_problem_family",
        "selected_scaffold",
        "problem_text",
        "gold_answer",
        "current_pal_prediction",
        "external_prediction_if_available",
        "source_artifacts",
        "selection_reason",
        "provenance_risk",
        "prompt_path",
    ]
    with (out / "targeted_retry_cases.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in csv_rows_out:
            w.writerow(r)

    anchor_10 = [cid for cid in anchor_order if any(r["case_id"] == cid for r in csv_rows_out)][:10]
    example_ids = anchor_10[:2] if len(anchor_10) >= 2 else [r["case_id"] for r in csv_rows_out[:2]]
    examples_md = []
    for eid in example_ids:
        pr = next(r for r in csv_rows_out if r["case_id"] == eid)
        ptext = (out / pr["prompt_path"]).read_text(encoding="utf-8")
        examples_md.append(f"### {eid} ({pr['selected_scaffold']})\n\n```\n{ptext}\n```\n")

    report = "\n".join(
        [
            "# Targeted discovery retry v1 — dry run",
            "",
            f"- **Output:** `{out.relative_to(REPO)}`",
            f"- **Selected cases:** {len(ordered)}",
            f"- **Scaffold counts:** `{dict(scaffold_counts)}`",
            "",
            "## Cohort summary",
            "",
            "First implementation cohort: `money_budget`, `rate_ratio`, `temporal_change`, `difference_comparison` "
            "from gold-absent diagnosis, `gold_absent_tagged` only. High provenance risk excluded unless listed in "
            "`anchor_cases.md` (anchors with unknown family still fail the family filter).",
            "",
            "## Ten anchor IDs (in `anchor_cases.md` order, intersecting selected set)",
            "",
            ", ".join(anchor_10) if anchor_10 else "(none)",
            "",
            "## Example prompts (2 cases only)",
            "",
            *examples_md,
            "## Next live pilot",
            "",
            "Run **10–15** cases from the anchor intersection with Cohere on frozen prompts; "
            "compare exact match vs baseline PAL; keep structural-commit guardrail replay at 0 regressions.",
            "",
            "## Caveats",
            "",
            "- Prompts are **gold-free** by construction; CSV still carries gold for offline scoring only.",
            "- `external_prediction_if_available` may contain non-numeric artifact text from sources.",
            "",
        ]
    )
    (out / "dry_run_report.md").write_text(report, encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
