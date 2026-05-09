#!/usr/bin/env python3
"""Offline materializer for targeted discovery retry v2.

Only refines the `quantity_ledger` scaffold into v2; all other scaffolds remain v1.
No Cohere calls, no HF downloads.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Ensure repo root is importable when executed with system `python3`.
import sys

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from experiments.targeted_discovery_retry import (
    build_prompt,
    choose_scaffold,
    classify_family_from_row,
    provenance_risk,
    validate_prompt_no_gold,
)


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


def _prior_status_from_v1_pilot(v1_pilot_results: list[dict[str, str]]) -> dict[str, str]:
    """Return case_id -> prior_v1_pilot_status in {exact, improved, failed, not_piloted}."""
    out: dict[str, str] = {}
    for r in v1_pilot_results:
        cid = str(r.get("case_id") or "").strip()
        if not cid:
            continue
        exact = str(r.get("exact_match") or "").strip().lower() == "true"
        improved = str(r.get("improved_over_current_pal") or "").strip().lower() == "yes"
        if exact:
            out[cid] = "exact"
        elif improved:
            out[cid] = "improved"
        else:
            out[cid] = "failed"
    return out


def _select_v2_cases(
    v1_dry_run_rows: list[dict[str, str]],
    v1_pilot_prior: dict[str, str],
) -> tuple[list[dict[str, str]], dict[str, int]]:
    """Select <= 15 cases total, returning (selected_rows, scaffold_counts)."""
    # v2 includes all failed quantity_ledger cases from v1 pilot.
    failed_qty = [r for r in v1_dry_run_rows if r["selected_scaffold"] == "quantity_ledger" and v1_pilot_prior.get(r["case_id"]) == "failed"]

    # Choose remaining quantity_ledger to reach exactly 6 total if available.
    target_qty_total = 6
    qty_selected = list(failed_qty)
    qty_needed = max(0, target_qty_total - len(qty_selected))
    qty_candidates = [
        r
        for r in v1_dry_run_rows
        if r["selected_scaffold"] == "quantity_ledger" and v1_pilot_prior.get(r["case_id"]) == "not_piloted"
    ]
    # Prefer low risk first.
    qty_candidates.sort(key=lambda r: (provenance_risk(r) == "high", provenance_risk(r), r["case_id"]))
    for r in qty_candidates:
        if qty_needed <= 0:
            break
        if provenance_risk(r) == "high":
            continue
        qty_selected.append(r)
        qty_needed -= 1

    # If still short, allow medium (rare).
    if qty_needed > 0:
        qty_candidates.sort(key=lambda r: (provenance_risk(r) == "high", provenance_risk(r), r["case_id"]))
        for r in qty_candidates:
            if qty_needed <= 0:
                break
            if r in qty_selected:
                continue
            qty_selected.append(r)
            qty_needed -= 1

    if len(qty_selected) > target_qty_total:
        qty_selected = qty_selected[:target_qty_total]

    # Successful scaffolds: pick balanced validation set.
    def _pick_first(scaffold: str, n: int) -> list[dict[str, str]]:
        rows = [r for r in v1_dry_run_rows if r["selected_scaffold"] == scaffold]
        # Prefer not-high risk and cases with gold/pal/external if available (heuristic: nonempty external).
        def key(r: dict[str, str]) -> tuple[int, int, str]:
            risk_is_high = 1 if provenance_risk(r) == "high" else 0
            ext_ok = 0 if (str(r.get("external_prediction_if_available") or "").strip()) else 1
            prior = v1_pilot_prior.get(r["case_id"], "not_piloted")
            prior_score = {"exact": 0, "improved": 1, "failed": 2, "not_piloted": 3}.get(prior, 3)
            return (risk_is_high, ext_ok, prior_score, r["case_id"])

        rows.sort(key=key)
        picked: list[dict[str, str]] = []
        for r in rows:
            if len(picked) >= n:
                break
            # Exclude high risk unless necessary for the scaffold count.
            if provenance_risk(r) == "high" and picked:
                continue
            picked.append(r)
        return picked

    rate_selected = _pick_first("rate_table", 3)
    before_after_selected = _pick_first("before_after_state", 3)
    target_diff_selected = _pick_first("target_difference", 3)

    selected = qty_selected + rate_selected + before_after_selected + target_diff_selected

    # Remove duplicates by case_id (should not happen, but be safe).
    seen: set[str] = set()
    uniq: list[dict[str, str]] = []
    for r in selected:
        cid = r["case_id"]
        if cid in seen:
            continue
        uniq.append(r)
        seen.add(cid)

    # If too many, trim deterministically with the scaffold priorities.
    if len(uniq) > 15:
        pri = {"quantity_ledger": 0, "rate_table": 1, "before_after_state": 2, "target_difference": 3}
        uniq.sort(key=lambda r: (pri.get(r["selected_scaffold"], 9), r["case_id"]))
        uniq = uniq[:15]

    scaffold_counts = Counter(str(r.get("selected_scaffold") or "") for r in uniq)
    return uniq, dict(scaffold_counts)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--v1-dry-run-dir",
        type=Path,
        default=REPO / "outputs/targeted_discovery_retry_v1_dry_run_20260508T010738Z",
    )
    ap.add_argument(
        "--v1-pilot-dir",
        type=Path,
        default=REPO / "outputs/targeted_discovery_retry_v1_cohere_pilot_20260508T011341Z",
    )
    ap.add_argument(
        "--v1-diagnosis-dir",
        type=Path,
        default=REPO / "outputs/gold_absent_discovery_diagnosis_20260508T005544Z",
    )
    ap.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Default: outputs/targeted_discovery_retry_v2_dry_run_<utc>",
    )
    args = ap.parse_args()

    v1_dry = args.v1_dry_run_dir.resolve()
    v1_cases_csv = v1_dry / "targeted_retry_cases.csv"
    if not v1_cases_csv.is_file():
        raise SystemExit(f"missing {v1_cases_csv}")
    v1_pilot = args.v1_pilot_dir.resolve()
    v1_pilot_results = v1_pilot / "pilot_results.csv"
    if not v1_pilot_results.is_file():
        raise SystemExit(f"missing {v1_pilot_results}")

    v1_dry_rows = _read_csv_dicts(v1_cases_csv)
    v1_pilot_prior = _prior_status_from_v1_pilot(_read_csv_dicts(v1_pilot_results))

    # Default any missing pilot case ids to not_piloted.
    for r in v1_dry_rows:
        v1_pilot_prior.setdefault(r["case_id"], "not_piloted")

    selected, scaffold_counts = _select_v2_cases(v1_dry_rows, v1_pilot_prior)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = args.output_dir or (REPO / f"outputs/targeted_discovery_retry_v2_dry_run_{ts}")
    out = out.resolve()

    prompts_dir = out / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)

    # Prompt versions: only quantity_ledger differs.
    prompt_versions_by_scaffold = {
        "quantity_ledger": "v2",
        "rate_table": "v1",
        "before_after_state": "v1",
        "target_difference": "v1",
    }

    selected_rows: list[dict[str, Any]] = []
    scaffold_for_case: dict[str, str] = {}
    prompt_paths: dict[str, str] = {}

    for r in selected:
        cid = r["case_id"]
        scaffold = r["selected_scaffold"]
        prompt_version = prompt_versions_by_scaffold.get(scaffold, "v1")
        problem_text = r["problem_text"]
        gold_answer = str(r.get("gold_answer") or "").strip()

        prompt = build_prompt(problem_text, scaffold, prompt_version=prompt_version)
        if not validate_prompt_no_gold(prompt, gold_answer if gold_answer else None):
            raise SystemExit(f"gold leak detected in v2 prompt for {cid}")
        if "\\boxed" not in prompt:
            raise SystemExit(f"missing boxed final-answer instruction for {cid}")

        prompt_path = prompts_dir / f"{cid}_{scaffold}_{prompt_version}.txt"
        prompt_path.write_text(prompt, encoding="utf-8")
        prompt_paths[cid] = str(prompt_path.relative_to(out)).replace("\\", "/")

        prior_status = v1_pilot_prior.get(cid, "not_piloted")
        selected_rows.append(
            {
                "case_id": cid,
                "scaffold": scaffold,
                "prompt_version": prompt_version,
                "problem_text": problem_text,
                "gold_answer": gold_answer,
                "current_pal_prediction": r.get("current_pal_prediction") or "",
                "external_prediction_if_available": r.get("external_prediction_if_available") or "",
                "prior_v1_pilot_status": prior_status,
                "source_artifacts": r.get("source_artifacts") or "",
                "provenance_risk": provenance_risk(r),
                "prompt_path": prompt_paths[cid],
            }
        )
        scaffold_for_case[cid] = scaffold

    # v2 manifest
    excluded_case_counts_by_reason: dict[str, int] = {}
    manifest = {
        "no_api_calls": True,
        "source_v1_dry_run_dir": str(v1_dry.relative_to(REPO)),
        "source_v1_pilot_dir": str(v1_pilot.relative_to(REPO)),
        "selected_case_count": len(selected_rows),
        "scaffold_counts": scaffold_counts,
        "prompt_versions_by_scaffold": prompt_versions_by_scaffold,
        "selected_case_ids": [r["case_id"] for r in selected_rows],
        "estimated_live_api_calls_if_piloted": len(selected_rows),
        "gold_leak_check_passed": True,
        "selection_rules": {
            "quantity_ledger_failed_v1_cases_included": True,
            "quantity_ledger_total_target": 6,
            "validation_scaffolds": {
                "rate_table": 3,
                "before_after_state": 3,
                "target_difference": 3,
            },
            "exclude_high_provenance_risk_unless_needed": True,
        },
        "excluded_case_counts_by_reason": excluded_case_counts_by_reason,
    }

    out.mkdir(parents=True, exist_ok=True)
    (out / "targeted_retry_v2_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # v2 cases csv
    cases_fieldnames = [
        "case_id",
        "scaffold",
        "prompt_version",
        "problem_text",
        "gold_answer",
        "current_pal_prediction",
        "external_prediction_if_available",
        "prior_v1_pilot_status",
        "source_artifacts",
        "provenance_risk",
        "prompt_path",
    ]
    _write_csv(out / "targeted_retry_v2_cases.csv", cases_fieldnames, selected_rows)

    # dry_run_report with only 2 prompt examples
    failed_qty_cases = [r for r in selected_rows if r["scaffold"] == "quantity_ledger" and r["prior_v1_pilot_status"] == "failed"]
    example_failed = failed_qty_cases[0] if failed_qty_cases else selected_rows[0]
    example_non_qty = None
    for sc in ("rate_table", "before_after_state", "target_difference"):
        for r in selected_rows:
            if r["scaffold"] == sc:
                example_non_qty = r
                break
        if example_non_qty:
            break
    if example_non_qty is None:
        example_non_qty = selected_rows[0]

    def _read_prompt(r: dict[str, Any]) -> str:
        pp = out / r["prompt_path"]
        return pp.read_text(encoding="utf-8")

    ex1 = example_failed
    ex2 = example_non_qty
    p1 = _read_prompt(ex1)
    p2 = _read_prompt(ex2)

    report = "\n".join(
        [
            "# Targeted discovery retry v2 dry run",
            "",
            f"- Output: `{out}`",
            f"- Selected cases: {len(selected_rows)}",
            f"- Scaffold counts: `{scaffold_counts}`",
            f"- Prompt versions: `{prompt_versions_by_scaffold}`",
            "",
            "## Selected case IDs (up to first 15 in scaffold order)",
            ", ".join([r["case_id"] for r in selected_rows]),
            "",
            "## Prompt examples (exact; 2 cases only)",
            "",
            f"### Quantity ledger v2 example: {ex1['case_id']}",
            "",
            "```",
            p1,
            "```",
            "",
            f"### Non-quantity (unchanged v1) example: {ex2['case_id']} ({ex2['scaffold']})",
            "",
            "```",
            p2,
            "```",
            "",
            "## Caveats",
            "",
            "- Only `quantity_ledger` template changed; other scaffolds reuse v1 wording.",
            "- Prompts are gold-free; offline scoring uses gold only after generation.",
        ]
    )
    (out / "dry_run_report.md").write_text(report, encoding="utf-8")

    print(out)


if __name__ == "__main__":
    main()

