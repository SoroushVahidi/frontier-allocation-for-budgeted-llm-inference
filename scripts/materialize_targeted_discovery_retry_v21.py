#!/usr/bin/env python3
"""Offline materializer for targeted discovery retry v2.1.

Only refines `quantity_ledger` scaffold into prompt_version `quantity_ledger_v2_1`.
Other scaffolds use unchanged v1 templates.
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
    classify_family_from_row,
    choose_scaffold,
    dry_run_eligible,
    provenance_risk,
    validate_prompt_no_gold,
)

from experiments.targeted_discovery_retry import classify_family_from_row


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


def _extract_quantity_ledger_ids_from_v2_pilot(v2_pilot_results: list[dict[str, str]]) -> list[str]:
    return [r["case_id"] for r in v2_pilot_results if r.get("scaffold") == "quantity_ledger"]


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
        "--v2-pilot-dir",
        type=Path,
        default=REPO / "outputs/targeted_discovery_retry_v2_cohere_pilot_20260508T013332Z",
    )
    ap.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Default: outputs/targeted_discovery_retry_v21_dry_run_<utc>",
    )
    args = ap.parse_args()

    v1_dry = args.v1_dry_run_dir.resolve()
    v1_cases_csv = v1_dry / "targeted_retry_cases.csv"
    if not v1_cases_csv.is_file():
        raise SystemExit(f"missing {v1_cases_csv}")

    v1_pilot_results = _read_csv_dicts((args.v1_pilot_dir.resolve() / "pilot_results.csv"))
    prior_v1 = _prior_status_from_v1_pilot(v1_pilot_results)

    v2_pilot_results = _read_csv_dicts((args.v2_pilot_dir.resolve() / "pilot_results.csv"))
    v2_qty_ids = _extract_quantity_ledger_ids_from_v2_pilot(v2_pilot_results)

    v1_rows = _read_csv_dicts(v1_cases_csv)
    by_id = {r["case_id"]: r for r in v1_rows}
    v1_qty_ids = [r["case_id"] for r in v1_rows if r.get("selected_scaffold") == "quantity_ledger"]

    remaining_qty = [cid for cid in v1_qty_ids if cid not in set(v2_qty_ids)]

    # Selected quantity_ledger cases: all v2 quantity_ledger + remaining from v1 not yet piloted.
    selected_case_ids: list[str] = []
    seen: set[str] = set()
    for cid in v2_qty_ids + remaining_qty:
        if cid in seen:
            continue
        if cid not in by_id:
            continue
        selected_case_ids.append(cid)
        seen.add(cid)

    # Optional single non-quantity sanity case (for report example) if we still have room.
    if len(selected_case_ids) <= 9:
        # Prefer a low-risk rate_table case.
        for r in v1_rows:
            if r.get("selected_scaffold") != "rate_table":
                continue
            cid = r["case_id"]
            if cid in seen:
                continue
            if provenance_risk(r) == "low":
                selected_case_ids.append(cid)
                seen.add(cid)
                break

    if len(selected_case_ids) > 10:
        # Trim deterministic by keeping all quantity_ledger first.
        qty_keep = [cid for cid in selected_case_ids if by_id.get(cid, {}).get("selected_scaffold") == "quantity_ledger"][:9]
        rest = [cid for cid in selected_case_ids if cid not in set(qty_keep)]
        selected_case_ids = qty_keep + rest[: max(0, 10 - len(qty_keep))]

    # Build selected rows with prompt versions
    prompts_dir_key = "prompts"
    prompt_versions_by_scaffold = {
        "quantity_ledger": "quantity_ledger_v2_1",
        "rate_table": "v1",
        "before_after_state": "v1",
        "target_difference": "v1",
    }

    selected_rows: list[dict[str, Any]] = []
    selected_count = 0
    for cid in selected_case_ids:
        row = by_id[cid]
        scaffold = row.get("selected_scaffold") or ""
        pv = prompt_versions_by_scaffold.get(scaffold, "v1")
        selected_count += 1

        problem_text = str(row.get("problem_text") or "")
        gold_answer = str(row.get("gold_answer") or "")
        prompt = build_prompt(problem_text, scaffold, prompt_version=pv)
        if not validate_prompt_no_gold(prompt, gold_answer):
            raise SystemExit(f"gold leaked into v2.1 prompt for {cid}")
        if "\\boxed" not in prompt:
            raise SystemExit(f"missing boxed final answer in v2.1 prompt for {cid}")

        source_artifacts = str(row.get("source_artifacts") or "")
        selected_rows.append(
            {
                "case_id": cid,
                "scaffold": scaffold,
                "prompt_version": pv,
                "problem_text": problem_text,
                "gold_answer": gold_answer,
                "current_pal_prediction": str(row.get("current_pal_prediction") or ""),
                "external_prediction_if_available": str(row.get("external_prediction_if_available") or ""),
                "prior_v1_pilot_status": prior_v1.get(cid, "not_piloted"),
                "source_artifacts": source_artifacts,
                "provenance_risk": provenance_risk(row),
                "prompt_path": f"{prompts_dir_key}/{cid}_{scaffold}_{pv}.txt",
            }
        )

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = args.output_dir or (REPO / "outputs" / f"targeted_discovery_retry_v21_dry_run_{ts}")
    out = out.resolve()
    prompts_dir = out / prompts_dir_key
    prompts_dir.mkdir(parents=True, exist_ok=True)

    # Materialize prompts and write cases CSV + manifest
    for r in selected_rows:
        cid = r["case_id"]
        scaffold = r["scaffold"]
        pv = r["prompt_version"]
        prompt = build_prompt(
            str(r["problem_text"]),
            scaffold,
            prompt_version=pv,
        )
        (out / r["prompt_path"]).write_text(prompt, encoding="utf-8")

    scaffold_counts = Counter(str(r["scaffold"]) for r in selected_rows)
    manifest: dict[str, Any] = {
        "timestamp": ts,
        "no_api_calls": True,
        "source_v2_dry_run_dir": str(args.v2_pilot_dir.resolve().name),
        "source_v2_pilot_dir": str(args.v2_pilot_dir.resolve()),
        "source_v1_dry_run_dir": str(v1_dry.relative_to(REPO)),
        "source_v1_pilot_dir": str(args.v1_pilot_dir.resolve()),
        "selected_case_count": len(selected_rows),
        "scaffold_counts": dict(scaffold_counts),
        "prompt_versions_by_scaffold": prompt_versions_by_scaffold,
        "selected_case_ids": [r["case_id"] for r in selected_rows],
        "estimated_live_api_calls_if_piloted": len(selected_rows),
        "gold_leak_check_passed": True,
        "selection_rules": {
            "include_all_v2_quantity_ledger_cases": True,
            "include_remaining_v1_quantity_ledger_cases_not_in_v2": True,
            "optional_single_rate_table_if_space": True,
        },
        "excluded_case_counts_by_reason": {},
    }

    (out / "targeted_retry_v21_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    fields = [
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
    _write_csv(out / "targeted_retry_v21_cases.csv", fields, selected_rows)

    # dry_run_report: show 2 examples (1 failed qty ledger, 1 non-quantity scaffold if present)
    failed_qty = [r for r in selected_rows if r["scaffold"] == "quantity_ledger" and r.get("prior_v1_pilot_status") == "failed"]
    example_qty = failed_qty[0] if failed_qty else next(r for r in selected_rows if r["scaffold"] == "quantity_ledger")
    example_non_qty = next((r for r in selected_rows if r["scaffold"] != "quantity_ledger"), None)
    if example_non_qty is None:
        example_non_qty = next(r for r in selected_rows if r["scaffold"] == "rate_table")

    p_qty = (out / example_qty["prompt_path"]).read_text(encoding="utf-8")
    p_non = (out / example_non_qty["prompt_path"]).read_text(encoding="utf-8")

    report = "\n".join(
        [
            "# Targeted discovery retry v2.1 — dry run",
            "",
            f"- Output: `{out}`",
            f"- Selected cases: {len(selected_rows)}",
            f"- Scaffold counts: `{dict(scaffold_counts)}`",
            f"- Prompt versions: `{prompt_versions_by_scaffold}`",
            "",
            "## Prompt examples (2 cases only)",
            "",
            f"### quantity_ledger v2.1 example: {example_qty['case_id']}",
            "```",
            p_qty,
            "```",
            "",
            f"### non-quantity (v1) example: {example_non_qty['case_id']} ({example_non_qty['scaffold']})",
            "```",
            p_non,
            "```",
            "",
            "## Caveats",
            "",
            "- Only `quantity_ledger` prompt is refined to v2.1. Other scaffolds use v1 templates unchanged.",
        ]
    )
    (out / "dry_run_report.md").write_text(report, encoding="utf-8")
    (out / "targeted_retry_v21_cases.csv").touch(exist_ok=True)

    print(out)


if __name__ == "__main__":
    main()

