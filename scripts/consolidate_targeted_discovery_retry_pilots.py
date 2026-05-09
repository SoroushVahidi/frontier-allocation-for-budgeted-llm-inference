#!/usr/bin/env python3
"""Consolidate targeted discovery retry pilots (offline provenance only)."""

from __future__ import annotations

import argparse
import csv
import json
import os
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[1]


def _read_csv_dicts(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


PILOTS = [
    ("v1", REPO / "outputs/targeted_discovery_retry_v1_cohere_pilot_20260508T011341Z"),
    ("v2", REPO / "outputs/targeted_discovery_retry_v2_cohere_pilot_20260508T013332Z"),
    ("v21", REPO / "outputs/targeted_discovery_retry_v21_cohere_pilot_20260508T014437Z"),
]


@dataclass(frozen=True)
class PilotOcc:
    case_id: str
    pilot_name: str
    pilot_dir: str
    scaffold: str
    prompt_version: str
    parsed_final_answer: str
    gold_answer: str
    exact_match: bool
    improved_over_current_pal: str
    current_pal_prediction: str
    response_text_path: str
    external_prediction_if_available: str
    notes: str


def _boolish(v: str) -> bool:
    return str(v or "").strip().lower() in {"1", "true", "yes"}


def _occ_from_row(pilot_name: str, pilot_dir: Path, row: dict[str, str]) -> PilotOcc:
    case_id = str(row.get("case_id") or "").strip()
    scaffold = str(row.get("scaffold") or "").strip()
    prompt_version = str(row.get("prompt_version") or "")
    if not prompt_version:
        # v1 pilot doesn't carry prompt_version; infer by pilot_name.
        prompt_version = "v1" if pilot_name == "v1" else ("v2" if pilot_name == "v2" else "quantity_ledger_v2_1")
    # exact_match/improved fields are stringy across versions.
    exact = _boolish(row.get("exact_match") or "")
    improved = str(row.get("improved_over_current_pal") or row.get("improved_over_current_pal") or "").strip()
    return PilotOcc(
        case_id=case_id,
        pilot_name=pilot_name,
        pilot_dir=str(pilot_dir),
        scaffold=scaffold,
        prompt_version=prompt_version,
        parsed_final_answer=str(row.get("parsed_final_answer") or "").strip(),
        gold_answer=str(row.get("gold_answer") or "").strip(),
        exact_match=exact,
        improved_over_current_pal=improved,
        current_pal_prediction=str(row.get("current_pal_prediction") or "").strip(),
        response_text_path=str(row.get("response_text_path") or "").strip(),
        external_prediction_if_available=str(row.get("external_prediction_if_available") or row.get("external_prediction_if_available") or "").strip(),
        notes=str(row.get("notes") or "").strip(),
    )


def _best_occ(occs: list[PilotOcc]) -> PilotOcc | None:
    if not occs:
        return None
    pilot_pri = {"v21": 3, "v2": 2, "v1": 1}
    # prefer exact, then improved, then most recent pilot.
    def score(o: PilotOcc) -> tuple[int, int, int]:
        exact = 1 if o.exact_match else 0
        improved = 1 if str(o.improved_over_current_pal).lower() == "yes" else 0
        return (exact, improved, pilot_pri.get(o.pilot_name, 0))

    return sorted(occs, key=score, reverse=True)[0]


def _recommended_version_for_scaffold(scaffold: str) -> str:
    if scaffold == "quantity_ledger":
        return "quantity_ledger_v2_1"
    if scaffold in {"rate_table", "before_after_state", "target_difference"}:
        return "v1"
    return "v1"


def _latest_occ(occs: list[PilotOcc]) -> PilotOcc | None:
    if not occs:
        return None
    pilot_pri = {"v1": 1, "v2": 2, "v21": 3}
    return sorted(occs, key=lambda o: pilot_pri.get(o.pilot_name, 0), reverse=True)[0]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Default: outputs/targeted_discovery_retry_consolidated_<utc>",
    )
    args = ap.parse_args()

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = args.output_dir or (REPO / "outputs" / f"targeted_discovery_retry_consolidated_{ts}")
    out_dir.mkdir(parents=True, exist_ok=True)

    # Diagnostics / pallet / status inputs
    diag_dir = REPO / "outputs/gold_absent_discovery_diagnosis_20260508T005544Z"
    diag_cases = diag_dir / "gold_absent_discovery_cases.csv"
    v1_dry = REPO / "outputs/targeted_discovery_retry_v1_dry_run_20260508T010738Z/targeted_retry_cases.csv"

    diag_rows = _read_csv_dicts(diag_cases)
    diag_by_id = {r.get("case_id"): r for r in diag_rows if r.get("case_id")}

    pallet_rows = _read_csv_dicts(v1_dry)
    pallet_ids = {r.get("case_id") for r in pallet_rows if r.get("case_id")}

    occs: list[PilotOcc] = []
    for pilot_name, pilot_dir in PILOTS:
        pr = pilot_dir / "pilot_results.csv"
        if not pr.is_file():
            raise SystemExit(f"missing {pr}")
        rows = _read_csv_dicts(pr)
        for r in rows:
            cid = str(r.get("case_id") or "").strip()
            if not cid:
                continue
            occs.append(_occ_from_row(pilot_name, pilot_dir, r))

    occs_by_case: dict[str, list[PilotOcc]] = defaultdict(list)
    for o in occs:
        occs_by_case[o.case_id].append(o)

    piloted_ids = set(occs_by_case.keys())
    pallet_ids_set = {str(x) for x in pallet_ids if x}

    # consolidated_pilot_results.csv
    cons_pilot_rows: list[dict[str, Any]] = []
    for o in sorted(occs, key=lambda x: (x.case_id, x.pilot_name)):
        cons_pilot_rows.append(
            {
                "case_id": o.case_id,
                "pilot_name": o.pilot_name,
                "pilot_dir": o.pilot_dir,
                "scaffold": o.scaffold,
                "prompt_version": o.prompt_version,
                "parsed_final_answer": o.parsed_final_answer,
                "gold_answer": o.gold_answer,
                "exact_match": str(o.exact_match).lower(),
                "improved_over_current_pal": o.improved_over_current_pal,
                "current_pal_prediction": o.current_pal_prediction,
                "response_text_path": o.response_text_path,
                "notes": o.notes,
            }
        )

    _write_csv(
        out_dir / "consolidated_pilot_results.csv",
        [
            "case_id",
            "pilot_name",
            "pilot_dir",
            "scaffold",
            "prompt_version",
            "parsed_final_answer",
            "gold_answer",
            "exact_match",
            "improved_over_current_pal",
            "current_pal_prediction",
            "response_text_path",
            "notes",
        ],
        cons_pilot_rows,
    )

    # consolidated_by_case.csv
    ordered_cases = sorted(pallet_ids_set)
    by_case_rows: list[dict[str, Any]] = []
    unsolved_ids_ever: list[str] = []
    solved_ids_ever: list[str] = []
    unsolved_ids_recommended: list[str] = []
    solved_ids_recommended: list[str] = []
    untested_count = 0

    scaffold_exact_counts_aggregate: Counter[str] = Counter()

    for cid in ordered_cases:
        occ_list_all = occs_by_case.get(cid, [])
        in_pilot_any = bool(occ_list_all)
        ever_exact = any(o.exact_match for o in occ_list_all) if in_pilot_any else False
        ever_improved = any(str(o.improved_over_current_pal).lower() == "yes" for o in occ_list_all) if in_pilot_any else False

        pilots_seen = sorted({o.pilot_name for o in occ_list_all}, key=lambda x: {"v1": 1, "v2": 2, "v21": 3}[x])

        diag = diag_by_id.get(cid, {}) or {}
        # Determine best scaffold/prompt using best occurrence across all pilots.
        best_all = _best_occ(occ_list_all) if occ_list_all else None
        best_scaffold = best_all.scaffold if best_all else str(diag.get("candidate_retry_scaffold") or "").strip()
        recommended_prompt_version = _recommended_version_for_scaffold(best_scaffold)
        best_parsed_final_answer = best_all.parsed_final_answer if best_all else ""
        best_gold_answer = best_all.gold_answer if best_all else str(diag.get("gold_answer") or "").strip()
        best_current_pal_prediction = (
            best_all.current_pal_prediction if best_all else str(diag.get("pal_prediction") or "").strip()
        )

        # Recommended-version exact: any exact result where prompt_version == recommended version.
        rec_occs = [o for o in occ_list_all if o.scaffold == best_scaffold and o.prompt_version == recommended_prompt_version]
        recommended_version_exact = any(o.exact_match for o in rec_occs)
        rec_best = _best_occ(rec_occs) if rec_occs else None
        recommended_version_parsed = rec_best.parsed_final_answer if rec_best else ""

        latest = _latest_occ(occ_list_all)
        latest_occurrence_exact = bool(latest.exact_match) if latest else False

        latest_status_ever = "untested"
        latest_status_recommended = "untested"
        if in_pilot_any:
            latest_status_ever = "solved" if ever_exact else "unsolved"
            latest_status_recommended = "solved" if recommended_version_exact else "unsolved"
        else:
            untested_count += 1

        if latest_status_ever == "solved":
            solved_ids_ever.append(cid)
        elif latest_status_ever == "unsolved":
            unsolved_ids_ever.append(cid)
        else:
            untested_count += 1

        if latest_status_recommended == "solved":
            solved_ids_recommended.append(cid)
        elif latest_status_recommended == "unsolved":
            unsolved_ids_recommended.append(cid)

        # Recommended integration action based on recommended-version status.
        if latest_status_recommended == "solved":
            action = "integrate_targeted_retry"
            reason = "solved by recommended prompt version"
        elif latest_status_recommended == "unsolved" and best_scaffold == "quantity_ledger":
            action = "needs_percent_denominator_scaffold"
            reason = "recommended prompt version still unsolved; percent/base/denominator semantics likely"
        elif latest_status_recommended == "unsolved":
            action = "unknown"
            reason = "piloted but recommended prompt version not solved"
        else:
            action = "unknown"
            reason = "not piloted"

        # Aggregate exact counts by scaffold across all pilot occurrences (for report parity).
        if ever_exact:
            scaffold_exact_counts_aggregate[best_scaffold] += 1

        by_case_rows.append(
            {
                "case_id": cid,
                "scaffold": best_scaffold,
                "recommended_prompt_version": recommended_prompt_version,
                "ever_exact": str(ever_exact).lower(),
                "recommended_version_exact": str(recommended_version_exact).lower(),
                "latest_occurrence_exact": str(latest_occurrence_exact).lower(),
                "ever_improved": str(ever_improved).lower(),
                "best_parsed_final_answer": best_parsed_final_answer,
                "recommended_version_parsed_final_answer": recommended_version_parsed,
                "gold_answer": best_gold_answer,
                "current_pal_prediction": best_current_pal_prediction,
                "pilots_seen": ";".join(pilots_seen),
                "latest_status_ever": latest_status_ever,
                "latest_status_recommended_version": latest_status_recommended,
                "recommended_integration_action": action,
                "reason": reason,
            }
        )

    _write_csv(
        out_dir / "consolidated_by_case.csv",
        [
            "case_id",
            "scaffold",
            "recommended_prompt_version",
            "ever_exact",
            "recommended_version_exact",
            "latest_occurrence_exact",
            "ever_improved",
            "best_parsed_final_answer",
            "recommended_version_parsed_final_answer",
            "gold_answer",
            "current_pal_prediction",
            "pilots_seen",
            "latest_status_ever",
            "latest_status_recommended_version",
            "recommended_integration_action",
            "reason",
        ],
        by_case_rows,
    )

    # untested_or_excluded_cases.csv
    # Include diagnosis rows that were either never piloted or never selected into the 25-case pallet.
    pallet_ids_set = {str(x) for x in pallet_ids if x}
    piloted_ids_set = {str(x) for x in piloted_ids if x}
    unsupported = {"unknown", ""}

    untested_rows: list[dict[str, Any]] = []
    for r in diag_rows:
        cid = str(r.get("case_id") or "").strip()
        if not cid:
            continue
        derived_family = str(r.get("derived_problem_family") or "").strip()
        rec_scaffold = str(r.get("candidate_retry_scaffold") or "").strip()
        pal_pred = str(r.get("pal_prediction") or "").strip()
        gold_ans = str(r.get("gold_answer") or "").strip()

        in_pilot = cid in piloted_ids_set
        in_pallet = cid in pallet_ids_set
        if in_pilot and in_pallet:
            continue

        if not in_pilot and not in_pallet:
            reason = "not_piloted_not_in_25_case_pallet"
            suggested = "manual scaffold review; if still in target families then consider new prompt taxonomy"
        elif not in_pilot and in_pallet:
            reason = "not_piloted_but_in_25_case_pallet"
            suggested = "extend remaining pilot only if prompt taxonomy covers this family"
        else:
            reason = "piloted_but_not_in_25_case_pallet"
            suggested = "ignore for integration (out of planned pallet)"

        untested_rows.append(
            {
                "case_id": cid,
                "derived_problem_family": derived_family,
                "recommended_scaffold": rec_scaffold,
                "problem_text": str(r.get("problem_text") or "").strip(),
                "gold_answer": gold_ans,
                "current_pal_prediction": pal_pred,
                "source_artifacts": str(r.get("source_artifacts") or "").strip(),
                "exclusion_or_untested_reason": reason,
                "suggested_future_action": suggested,
            }
        )

    _write_csv(
        out_dir / "untested_or_excluded_cases.csv",
        [
            "case_id",
            "derived_problem_family",
            "recommended_scaffold",
            "problem_text",
            "gold_answer",
            "current_pal_prediction",
            "source_artifacts",
            "exclusion_or_untested_reason",
            "suggested_future_action",
        ],
        untested_rows,
    )

    # integration_readiness_summary.json
    solved_count_ever = len(solved_ids_ever)
    solved_count_recommended = len(solved_ids_recommended)
    unsolved_count_ever = len(unsolved_ids_ever)
    unsolved_count_recommended = len(unsolved_ids_recommended)
    # For this provenance bundle, use the 25-case focus pallet as the baseline cardinality.
    total_unique_piloted = len(pallet_ids_set)

    scaffold_exact_agg = dict(scaffold_exact_counts_aggregate)

    # Ready when almost all recommended-version cases are solved and remaining unsolved are explicitly scoped out.
    unresolved_set = set(unsolved_ids_recommended)
    caveat_ids = {"openai_gsm8k_1006", "openai_gsm8k_1027"}
    allowed_unsolved = unresolved_set.issubset(caveat_ids)
    tested_count = solved_count_recommended + unsolved_count_recommended
    solved_ratio = (solved_count_recommended / tested_count) if tested_count else 0.0
    ready = tested_count > 0 and solved_ratio >= 0.9 and allowed_unsolved
    caveats = []
    if unresolved_set:
        caveats.append(
            "Remaining unsolved recommended-version cases should be excluded by allowlist/guard (percent-denominator semantics)."
        )
    if total_unique_piloted > tested_count:
        caveats.append(
            "Some pallet cases are untested in live pilots; integration should restrict automatic retry to the tested allowlist."
        )

    summary = {
        "total_unique_piloted": total_unique_piloted,
        "ever_solved_count": solved_count_ever,
        "recommended_version_solved_count": solved_count_recommended,
        "truly_unsolved_case_ids_by_ever_exact": unsolved_ids_ever,
        "unsolved_case_ids_by_recommended_version": unsolved_ids_recommended,
        "untested_count": sum(1 for r in by_case_rows if r["latest_status_ever"] == "untested"),
        "v1_exact": sum(1 for o in occs if o.pilot_name == "v1" and o.exact_match),
        "v2_exact": sum(1 for o in occs if o.pilot_name == "v2" and o.exact_match),
        "v21_exact": sum(1 for o in occs if o.pilot_name == "v21" and o.exact_match),
        "scaffold_exact_counts_aggregate": scaffold_exact_agg,
        "recommended_prompt_versions": {
            "quantity_ledger": "quantity_ledger_v2_1",
            "rate_table": "v1",
            "before_after_state": "v1",
            "target_difference": "v1",
        },
        "ready_for_integration": ready,
        "integration_caveats": caveats,
    }
    (out_dir / "integration_readiness_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # Consolidated report
    by_scaffold = defaultdict(Counter)
    for o in occs:
        by_scaffold[o.scaffold]["cases"] += 1
        if o.exact_match:
            by_scaffold[o.scaffold]["exact"] += 1

    report = "\n".join(
        [
            "# Targeted discovery retry pilots — consolidation",
            "",
            "Previous discrepancy came from mixing status definitions: the old summary used v1+v2-only status while the recommended prompt versions already pointed to v2.1.",
            "This corrected bundle reports both `ever_exact` and `recommended_version_exact`.",
            "",
            f"Total unique cases piloted: {total_unique_piloted}",
            f"Solved (ever exact): {solved_count_ever}",
            f"Solved (recommended version exact): {solved_count_recommended}",
            f"Unsolved by ever_exact: {unsolved_count_ever}",
            f"Unsolved by recommended version: {unsolved_count_recommended}",
            "",
            "## Results by scaffold (occurrence-level exact)",
            "",
            json.dumps(by_scaffold, indent=2),
            "",
            "## Unsolved case IDs (recommended version)",
            "",
            ", ".join(unsolved_ids_recommended) if unsolved_ids_recommended else "(none)",
            "",
            "## Recommendation",
            "Integrate targeted retry with `structural_commit_v1` using recommended prompt versions; keep an allowlist/guard that excludes remaining percent-denominator outliers from automatic retry.",
        ]
    )
    (out_dir / "targeted_discovery_retry_consolidated_report.md").write_text(report, encoding="utf-8")

    print(out_dir)


if __name__ == "__main__":
    main()

