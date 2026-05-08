#!/usr/bin/env python3
"""Offline integrated replay: structural_commit_v1 + targeted_retry_v1 (no API)."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]

DEFAULT_STRUCTURAL_DIR = REPO / "outputs/structural_commit_v1_replay_20260508T120000Z"
DEFAULT_TARGETED_CONSOLIDATION_DIR = REPO / "outputs/targeted_discovery_retry_consolidated_20260508T015847Z"
DEFAULT_FAILURE_BANK = REPO / "outputs/latest_pal_external_loss_bank_20260508T004000Z/latest_pal_external_loss_union_by_case.csv"
METHOD_NAME = (
    "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal_"
    "structural_commit_v1_targeted_retry_v1"
)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def _mechanism(row: dict[str, str]) -> str:
    return str(row.get("gold_absent_or_present_not_selected") or "").strip() or str(row.get("known_failure_tags") or "").strip()


def run_integrated_replay(
    *,
    structural_dir: Path,
    targeted_consolidation_dir: Path,
    failure_bank_csv: Path,
    output_dir: Path,
) -> Path:
    structural_summary = json.loads((structural_dir / "structural_commit_v1_replay_summary.json").read_text(encoding="utf-8"))
    structural_rows = _read_csv(structural_dir / "structural_commit_v1_replay_cases.csv")
    targeted_summary = json.loads(
        (targeted_consolidation_dir / "integration_readiness_summary.json").read_text(encoding="utf-8")
    )
    targeted_rows = _read_csv(targeted_consolidation_dir / "consolidated_by_case.csv")
    bank_rows = _read_csv(failure_bank_csv)

    structural_by_case = {r.get("case_id", ""): r for r in structural_rows if r.get("case_id")}
    targeted_by_case = {r.get("case_id", ""): r for r in targeted_rows if r.get("case_id")}
    targeted_allowlist = {
        r["case_id"]
        for r in targeted_rows
        if str(r.get("latest_status_recommended_version") or "").strip().lower() == "solved"
    }

    rows: list[dict[str, Any]] = []
    structural_fixed = 0
    targeted_fixed_tested = 0
    overlap = 0
    integrated_fixed = 0
    untested_targeted = 0
    unknown_mechanism = 0
    outside_allowlist_or_supported = 0
    insufficient_provenance = 0
    not_fixed_estimated = 0

    for row in bank_rows:
        cid = str(row.get("case_id") or "").strip()
        mech = _mechanism(row)
        source_artifacts = str(row.get("source_artifacts") or "").strip()
        if not cid:
            continue
        structural = structural_by_case.get(cid)
        targeted = targeted_by_case.get(cid)
        structural_app = mech == "present_not_selected"
        targeted_app = mech == "gold_absent_discovery" and cid in targeted_allowlist

        structural_result = "not_applicable"
        if structural_app:
            if structural is None:
                structural_result = "unknown"
            else:
                if int(structural.get("fixed_by_structural_commit_v1") or 0) == 1:
                    structural_result = "fixed"
                elif str(structural.get("outcome_tag_structural") or "") == "abstained":
                    structural_result = "abstain"
                else:
                    structural_result = "still_wrong"

        targeted_result = "not_applicable"
        rec_prompt = ""
        if mech == "gold_absent_discovery":
            if targeted is None:
                targeted_result = "untested"
            else:
                rec_prompt = str(targeted.get("recommended_prompt_version") or "").strip()
                status = str(targeted.get("latest_status_recommended_version") or "").strip().lower()
                if cid in targeted_allowlist:
                    targeted_result = "fixed" if status == "solved" else "still_wrong"
                else:
                    targeted_result = "abstain"

        if structural_result == "fixed" and targeted_result == "fixed":
            integrated = "fixed_estimated"
            reason = "both_structural_and_targeted_supported_fix"
            overlap += 1
        elif structural_result == "fixed":
            integrated = "fixed_estimated"
            reason = "fixed_by_structural_commit_v1"
        elif targeted_result == "fixed":
            integrated = "fixed_estimated"
            reason = "fixed_by_targeted_retry_allowlisted_recommended_version"
        elif targeted_result == "untested":
            integrated = "untested_targeted_retry"
            reason = "targeted_case_not_in_tested_consolidated_allowlist"
        elif structural_result == "unknown" or (
            mech == "gold_absent_discovery" and targeted is None
        ):
            integrated = "insufficient_provenance"
            reason = "missing_replay_or_consolidation_row"
        elif mech not in {"present_not_selected", "gold_absent_discovery"}:
            integrated = "unknown_mechanism"
            reason = "mechanism_not_in_integrated_policy_scope"
        elif structural_result in {"abstain", "not_applicable"} and targeted_result in {"abstain", "not_applicable"}:
            integrated = "not_applicable"
            reason = "outside_allowlist_or_supported_scaffold_coverage"
        elif structural_result == "unknown":
            integrated = "unknown"
            reason = "missing_structural_replay_row"
        else:
            integrated = "not_fixed_estimated"
            reason = "covered_but_not_fixed_by_existing_offline_evidence"

        if structural_result == "fixed":
            structural_fixed += 1
        if targeted_result == "fixed":
            targeted_fixed_tested += 1
        if integrated == "fixed_estimated":
            integrated_fixed += 1
        elif integrated == "not_fixed_estimated":
            not_fixed_estimated += 1
        elif integrated == "untested_targeted_retry":
            untested_targeted += 1
        elif integrated == "unknown_mechanism":
            unknown_mechanism += 1
        elif integrated == "insufficient_provenance":
            insufficient_provenance += 1
        elif integrated == "not_applicable":
            outside_allowlist_or_supported += 1

        rows.append(
            {
                "case_id": cid,
                "original_mechanism": mech or "unknown",
                "source_artifacts": source_artifacts,
                "baseline_status": "wrong",
                "structural_commit_applicable": "yes" if structural_app else "no",
                "structural_commit_result": structural_result,
                "targeted_retry_applicable": "yes" if targeted_app else "no",
                "targeted_retry_result": targeted_result,
                "integrated_result": integrated,
                "integration_reason": reason,
                "recommended_prompt_version_if_any": rec_prompt,
                "notes": str(row.get("recommended_next_track") or "").strip(),
            }
        )

    summary = {
        "total_known_loss_cases": len(rows),
        "estimated_fixed_by_structural_commit": structural_fixed,
        "estimated_fixed_by_targeted_retry_tested": targeted_fixed_tested,
        "overlap_between_structural_and_targeted": overlap,
        "estimated_fixed_combined": integrated_fixed,
        "estimated_unfixed_or_not_covered_total": len(rows) - integrated_fixed,
        "untested_targeted_retry_cases": untested_targeted,
        "unknown_mechanism_cases": unknown_mechanism,
        "cases_outside_allowlist_or_supported_scaffolds": outside_allowlist_or_supported,
        "cases_with_no_replay_or_insufficient_provenance": insufficient_provenance,
        # Backward compatibility for older downstream readers.
        "remaining_covered_losses": not_fixed_estimated,
        "no_api_calls": True,
    }

    manifest = {
        "no_api_calls": True,
        "method_name": METHOD_NAME,
        "structural_commit_source": str(structural_dir),
        "targeted_retry_consolidation_source": str(targeted_consolidation_dir),
        "failure_bank_source": str(failure_bank_csv),
        "allowlist_mode": True,
        "targeted_retry_tested_solved_count": int(targeted_summary.get("recommended_version_solved_count", 0)),
        "structural_commit_fixed_count": int(structural_summary.get("targets", {}).get("fixed_by_structural_commit_v1", 0)),
        "estimated_combined_fixes_on_known_failure_bank": integrated_fixed,
        "caveats": [
            "Targeted retry stays allowlisted to tested/recommended consolidated coverage only.",
            "Integrated replay is evidence stitching from existing artifacts; no new model calls.",
            "This is an offline estimate, not a broad checkpoint comparison versus external_l1_max.",
        ],
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "integrated_replay_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    _write_csv(
        output_dir / "integrated_replay_cases.csv",
        [
            "case_id",
            "original_mechanism",
            "source_artifacts",
            "baseline_status",
            "structural_commit_applicable",
            "structural_commit_result",
            "targeted_retry_applicable",
            "targeted_retry_result",
            "integrated_result",
            "integration_reason",
            "recommended_prompt_version_if_any",
            "notes",
        ],
        rows,
    )
    (output_dir / "integrated_replay_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    report = "\n".join(
        [
            "# Integrated structural_commit_v1 + targeted_retry_v1 offline replay",
            "",
            f"- Method scaffold: `{METHOD_NAME}`",
            "- No API calls were made; this is offline provenance stitching over existing artifacts.",
            "",
            "## Estimated fixes from existing evidence",
            f"- Estimated fixed: {summary['estimated_fixed_combined']} / {summary['total_known_loss_cases']}",
            f"- structural component: {summary['estimated_fixed_by_structural_commit']}",
            f"- targeted component (tested): {summary['estimated_fixed_by_targeted_retry_tested']}",
            "",
            "## Remaining gaps",
            f"- Estimated not fixed or not covered: {summary['estimated_unfixed_or_not_covered_total']} / {summary['total_known_loss_cases']}",
            f"- untested_targeted_retry_cases: {summary['untested_targeted_retry_cases']}",
            f"- unknown_mechanism_cases: {summary['unknown_mechanism_cases']}",
            f"- cases_outside_allowlist_or_supported_scaffolds: {summary['cases_outside_allowlist_or_supported_scaffolds']}",
            f"- cases_with_no_replay_or_insufficient_provenance: {summary['cases_with_no_replay_or_insufficient_provenance']}",
            "",
            "## Recommendation",
            "This does not justify a broad checkpoint versus external_l1_max yet. Next step: "
            "(A) run a capped live integrated pilot on covered/allowlisted cases, or "
            "(B) wait for full live integration then perform a clean checkpoint comparison.",
        ]
    )
    (output_dir / "integrated_replay_report.md").write_text(report, encoding="utf-8")
    return output_dir


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--structural-dir", type=Path, default=DEFAULT_STRUCTURAL_DIR)
    ap.add_argument("--targeted-consolidation-dir", type=Path, default=DEFAULT_TARGETED_CONSOLIDATION_DIR)
    ap.add_argument("--failure-bank-csv", type=Path, default=DEFAULT_FAILURE_BANK)
    ap.add_argument("--output-dir", type=Path, default=None)
    args = ap.parse_args()

    out = args.output_dir
    if out is None:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out = REPO / "outputs" / f"integrated_structural_commit_targeted_retry_v1_replay_{ts}"
    out = out.resolve()

    run_integrated_replay(
        structural_dir=args.structural_dir.resolve(),
        targeted_consolidation_dir=args.targeted_consolidation_dir.resolve(),
        failure_bank_csv=args.failure_bank_csv.resolve(),
        output_dir=out,
    )
    print(out)


if __name__ == "__main__":
    main()

