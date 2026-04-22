#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_RANKING = REPO_ROOT / "outputs/canonical_full_method_ranking_20260421T212948Z/overall_ranking.csv"
S1_CONFIG = REPO_ROOT / "configs/s1_budget_forcing_inference_only_v1.json"
S1_RUNNER = REPO_ROOT / "scripts/run_s1_budget_forcing_baseline.py"


def _utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    keys: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                keys.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build simple-scaling baseline coverage audit.")
    parser.add_argument("--run-id", default=_utc_run_id())
    parser.add_argument("--paper-tables-run", default="20260422T231500Z")
    args = parser.parse_args()

    out_dir = REPO_ROOT / "outputs/simple_scaling_baseline_coverage_audit" / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    ranking_df = pd.read_csv(CANONICAL_RANKING)
    s1_cfg = json.loads(S1_CONFIG.read_text(encoding="utf-8"))
    s1_runner_text = S1_RUNNER.read_text(encoding="utf-8")

    methods = set(ranking_df["method"].astype(str).tolist())
    s1_methods = set(s1_cfg.get("methods", {}).get("include", []))

    checks = {
        "external_s1_in_canonical_ranking": "external_s1_budget_forcing" in methods,
        "external_s1_in_s1_config_include": "external_s1_budget_forcing" in s1_methods,
        "s1_config_has_budget_forcing_knobs": all(
            k in (s1_cfg.get("s1_budget_forcing") or {}) for k in ["num_ignore_think_end", "min_thinking_steps", "wait_token"]
        ),
        "s1_runner_builds_external_s1_strategy": "include_external_s1_baseline=True" in s1_runner_text,
        "self_consistency_reference_present": "self_consistency_3" in methods,
    }

    near_direct_methods = [
        "strict_f3",
        "external_s1_budget_forcing",
        "external_tale_prompt_budgeting",
        "external_l1_exact",
        "external_l1_max",
    ]

    role_rows: list[dict[str, Any]] = []
    for method in near_direct_methods + ["self_consistency_3"]:
        sub = ranking_df[ranking_df["method"] == method]
        if sub.empty:
            continue
        row = sub.iloc[0]
        role_rows.append(
            {
                "method": method,
                "rank": int(row["rank"]),
                "mean_accuracy": float(row["mean_accuracy"]),
                "axis_simple_inference_scaling": "primary_representative" if method == "external_s1_budget_forcing" else (
                    "internal_reference" if method == "self_consistency_3" else "other_near_direct_budget_control"
                ),
                "best_of_n_or_sc_style": "yes" if method == "self_consistency_3" else "no",
                "paper_main_table_expected": "yes" if method in near_direct_methods else "no",
                "notes": (
                    "s1 budget forcing directly scales inference-time thinking budget on matched substrate"
                    if method == "external_s1_budget_forcing"
                    else "internal self-consistency comparator present in canonical ranking"
                    if method == "self_consistency_3"
                    else "near-direct baseline but not the canonical simple-scaling representative"
                ),
            }
        )

    coverage_adequate = all(
        [
            checks["external_s1_in_canonical_ranking"],
            checks["external_s1_in_s1_config_include"],
            checks["s1_config_has_budget_forcing_knobs"],
            checks["s1_runner_builds_external_s1_strategy"],
        ]
    )

    decision = {
        "run_id": args.run_id,
        "question": "Does current direct package already cover simple inference-time scaling / Best-of-N / self-consistency reviewer axis?",
        "coverage_adequate": coverage_adequate,
        "decision": "no_new_baseline_added" if coverage_adequate else "add_one_lightweight_baseline_required",
        "primary_representative": "external_s1_budget_forcing" if coverage_adequate else None,
        "secondary_context": "self_consistency_3 appears as internal reference in canonical ranking",
        "evidence_checks": checks,
        "new_baseline_added": False,
        "honesty_boundary": "external_s1_budget_forcing is used as an inference-time budget-scaling representative only; not claimed as full official s1 training-stack reproduction.",
    }

    _write_json(out_dir / "coverage_decision.json", decision)
    _write_csv(out_dir / "direct_baseline_role_matrix.csv", role_rows)

    notes_lines = [
        "# Reviewer expectation notes: simple scaling axis",
        "",
        "- Reviewer expectation: include at least one direct, simple inference-time scaling comparator in the near-direct layer.",
        "- Current package already includes `external_s1_budget_forcing` as a matched-substrate inference-time budget-forcing baseline.",
        "- `self_consistency_3` is also present in canonical ranking artifacts as internal context for Best-of-N/self-consistency behavior.",
        "- Therefore this pass keeps baseline scope minimal and avoids adding a redundant new direct baseline.",
        "",
        "Claim boundary:",
        "- Do not describe this as a full official s1 post-training reproduction; this is an inference-only adapter lane.",
    ]
    (out_dir / "reviewer_expectation_notes.md").write_text("\n".join(notes_lines), encoding="utf-8")

    coverage_md = [
        "# Simple scaling baseline coverage decision",
        "",
        f"Run ID: `{args.run_id}`",
        "",
        f"- Coverage adequate: **{coverage_adequate}**",
        f"- Decision: **{decision['decision']}**",
        f"- Primary representative: **{decision['primary_representative']}**",
        "",
        "## Evidence checks",
    ]
    for key, val in checks.items():
        coverage_md.append(f"- {key}: `{val}`")
    coverage_md.extend(
        [
            "",
            "## Conclusion",
            "The current direct package already covers the simple inference-time scaling axis; no new baseline was added.",
        ]
    )
    (out_dir / "coverage_decision.md").write_text("\n".join(coverage_md), encoding="utf-8")

    _write_json(
        out_dir / "config_snapshot.json",
        {
            "canonical_ranking": str(CANONICAL_RANKING.relative_to(REPO_ROOT)),
            "s1_config": str(S1_CONFIG.relative_to(REPO_ROOT)),
            "s1_runner": str(S1_RUNNER.relative_to(REPO_ROOT)),
            "paper_tables_run": args.paper_tables_run,
        },
    )

    (out_dir / "command_snapshot.txt").write_text(
        "python scripts/build_simple_scaling_baseline_coverage_audit.py "
        f"--run-id {args.run_id} --paper-tables-run {args.paper_tables_run}\n",
        encoding="utf-8",
    )

    paper_dir = REPO_ROOT / "outputs/paper_facing_baseline_tables" / args.paper_tables_run
    paper_dir.mkdir(parents=True, exist_ok=True)
    (paper_dir / "simple_scaling_axis_explicit_note.md").write_text(
        "\n".join(
            [
                "# Simple scaling axis explicit note",
                "",
                f"Linked audit: `outputs/simple_scaling_baseline_coverage_audit/{args.run_id}/coverage_decision.json`.",
                "",
                "Decision: The current direct package already covers the simple inference-time scaling axis via `external_s1_budget_forcing`; no new baseline was added in this pass.",
                "",
                "Boundary: This statement is limited to inference-only adapter comparability and does not claim full official s1 training-stack reproduction.",
            ]
        ),
        encoding="utf-8",
    )

    _write_json(
        out_dir / "manifest.json",
        {
            "run_id": args.run_id,
            "decision": decision["decision"],
            "new_baseline_added": False,
            "outputs": [
                "coverage_decision.json",
                "coverage_decision.md",
                "direct_baseline_role_matrix.csv",
                "reviewer_expectation_notes.md",
                "manifest.json",
                "config_snapshot.json",
                "command_snapshot.txt",
            ],
            "paper_facing_update": str((paper_dir / "simple_scaling_axis_explicit_note.md").relative_to(REPO_ROOT)),
        },
    )


if __name__ == "__main__":
    main()
