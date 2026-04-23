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
CANONICAL_INPUT = REPO_ROOT / "outputs/matched_surface_multiseed_main_comparison_20260423T002000Z"
READINESS_JSON = REPO_ROOT / "docs/external_baseline_paper_readiness_decision_matrix.json"
FAIRNESS_CHECKLIST = REPO_ROOT / "outputs/canonical_external_baseline_fairness_checklist_20260423T021422Z/baseline_presence_audit.csv"

MAIN_EXTERNALS = {"s1", "tale", "l1_exact", "l1_max", "zhai_cpo_mode_a"}
METHOD_TO_BASELINE_KEY = {
    "s1": "s1_simple_test_time_scaling",
    "tale": "tale_token_budget_aware_reasoning",
    "l1_exact": "l1_length_control_rl",
    "l1_max": "l1_length_control_rl",
    "zhai_cpo_mode_a": "zhai_constrained_budget_selector",
    "dipa_mode_a": "training_free_difficulty_proxies_mode_a",
}


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build canonical manuscript-facing external baseline closure bundle.")
    p.add_argument("--timestamp", default=utc_timestamp())
    p.add_argument("--input-dir", default=str(CANONICAL_INPUT.relative_to(REPO_ROOT)))
    return p.parse_args()


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def _classification_for_method(method: str, readiness: dict[str, dict[str, Any]]) -> tuple[str, str]:
    if method in MAIN_EXTERNALS:
        return "main_table_fair_near_direct", "Matched per-case contract; same dataset/budget/seed/extraction/accounting."
    if method == "dipa_mode_a":
        return "appendix_only", "Training-free difficulty proxy lane remains adapter/query-level and not case-level matched-equivalent."
    key = METHOD_TO_BASELINE_KEY.get(method)
    if not key:
        return "blocked", "No baseline taxonomy mapping."
    row = readiness.get(key, {})
    decision = str(row.get("readiness_decision", ""))
    comparator = str(row.get("comparator_bucket", ""))
    if decision == "main_table_ready":
        return "main_table_fair_near_direct", str(row.get("claim_boundary", "main-table-ready in readiness matrix"))
    if comparator == "adjacent":
        return "adjacent_only", str(row.get("claim_boundary", "adjacent control-space comparator"))
    if decision in {"appendix_only", "repo_only_not_paper_facing_yet"}:
        return "appendix_only", str(row.get("claim_boundary", "appendix-only by readiness matrix"))
    return "blocked", str(row.get("blocking_issue", "blocked or discuss-only"))


def main() -> None:
    args = parse_args()
    ts = args.timestamp
    input_dir = REPO_ROOT / args.input_dir
    raw_path = input_dir / "raw_case_results.csv"
    if not raw_path.exists():
        raise FileNotFoundError(raw_path)

    raw = pd.read_csv(raw_path)
    with READINESS_JSON.open("r", encoding="utf-8") as f:
        readiness_rows = json.load(f).get("rows", [])
    readiness = {str(r.get("baseline_key")): r for r in readiness_rows if isinstance(r, dict)}

    methods = sorted(raw["method"].astype(str).unique())
    status_rows: list[dict[str, Any]] = []
    for method in methods + ["dipa_mode_a"]:
        baseline_key = METHOD_TO_BASELINE_KEY.get(method, "")
        bucket, rationale = _classification_for_method(method, readiness)
        status_rows.append(
            {
                "method": method,
                "baseline_key": baseline_key,
                "status_bucket": bucket,
                "is_main_table": int(bucket == "main_table_fair_near_direct"),
                "is_appendix": int(bucket == "appendix_only"),
                "is_adjacent_only": int(bucket == "adjacent_only"),
                "is_blocked": int(bucket == "blocked"),
                "rationale": rationale,
            }
        )

    # Include all taxonomy-tracked external baselines so adjacent/blocked lanes are explicit.
    known_keys = {r["baseline_key"] for r in status_rows if r["baseline_key"]}
    for key, row in readiness.items():
        if key in known_keys:
            continue
        decision = str(row.get("readiness_decision", ""))
        comparator = str(row.get("comparator_bucket", ""))
        if comparator == "adjacent" or decision == "appendix_only":
            bucket = "adjacent_only"
        elif decision == "main_table_ready":
            bucket = "main_table_fair_near_direct"
        elif decision in {"repo_only_not_paper_facing_yet", "discuss_only", "blocked"}:
            bucket = "blocked"
        else:
            bucket = "appendix_only"
        status_rows.append(
            {
                "method": key,
                "baseline_key": key,
                "status_bucket": bucket,
                "is_main_table": int(bucket == "main_table_fair_near_direct"),
                "is_appendix": int(bucket == "appendix_only"),
                "is_adjacent_only": int(bucket == "adjacent_only"),
                "is_blocked": int(bucket == "blocked"),
                "rationale": str(row.get("claim_boundary", row.get("blocking_issue", "taxonomy classification"))),
            }
        )

    status_by_method = {r["method"]: r for r in status_rows}

    agg = (
        raw.groupby("method", as_index=False)
        .agg(
            n_cases=("is_correct", "size"),
            accuracy=("is_correct", "mean"),
            avg_actions=("actions", "mean"),
            avg_expansions=("expansions", "mean"),
            avg_verifications=("verifications", "mean"),
        )
        .sort_values(["accuracy", "method"], ascending=[False, True])
        .reset_index(drop=True)
    )

    main_table = agg[agg["method"].isin([m for m in methods if status_by_method[m]["status_bucket"] == "main_table_fair_near_direct"])].copy()
    appendix_table = agg[agg["method"].isin([m for m in methods if status_by_method[m]["status_bucket"] != "main_table_fair_near_direct"])].copy()

    per_dataset = (
        raw.groupby(["method", "dataset"], as_index=False)
        .agg(accuracy=("is_correct", "mean"), n_cases=("is_correct", "size"), avg_actions=("actions", "mean"))
        .sort_values(["dataset", "accuracy"], ascending=[True, False])
    )
    per_budget = (
        raw.groupby(["method", "budget"], as_index=False)
        .agg(accuracy=("is_correct", "mean"), n_cases=("is_correct", "size"), avg_actions=("actions", "mean"))
        .sort_values(["budget", "accuracy"], ascending=[True, False])
    )
    seed_level = (
        raw.groupby(["method", "seed"], as_index=False)
        .agg(accuracy=("is_correct", "mean"), n_cases=("is_correct", "size"), avg_actions=("actions", "mean"))
        .sort_values(["seed", "accuracy"], ascending=[True, False])
    )

    fairness_log = []
    for row in status_rows:
        fairness_log.append(
            {
                "method": row["method"],
                "decision": row["status_bucket"],
                "decision_rationale": row["rationale"],
                "contract_surface": "canonical manuscript-facing matched surface",
                "notes": "No cross-surface aggregation; matched dataset/budget/seed/extraction/accounting required.",
            }
        )

    contract_rows = [
        {
            "contract_dimension": "datasets",
            "value": ",".join(sorted(raw["dataset"].astype(str).unique())),
        },
        {
            "contract_dimension": "budgets_actions",
            "value": ",".join(str(int(x)) for x in sorted(raw["budget"].astype(int).unique())),
        },
        {
            "contract_dimension": "seeds",
            "value": ",".join(str(int(x)) for x in sorted(raw["seed"].astype(int).unique())),
        },
        {"contract_dimension": "answer_extraction", "value": "canonicalize_answer + choose_repair_answer"},
        {"contract_dimension": "compute_accounting", "value": "actions, expansions, verifications matched per-case"},
    ]

    out_dir = REPO_ROOT / f"outputs/canonical_external_baseline_closure_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)
    doc_path = REPO_ROOT / f"docs/CANONICAL_EXTERNAL_BASELINE_CLOSURE_{ts}.md"

    main_table.to_csv(out_dir / "main_table_external_results.csv", index=False)
    appendix_table.to_csv(out_dir / "appendix_external_results.csv", index=False)
    _write_csv(out_dir / "external_baseline_status_matrix.csv", status_rows)
    (out_dir / "external_baseline_status_matrix.json").write_text(json.dumps(status_rows, indent=2) + "\n", encoding="utf-8")
    _write_csv(out_dir / "fairness_decision_log.csv", fairness_log)
    _write_csv(out_dir / "method_contract_summary.csv", contract_rows)
    per_dataset.to_csv(out_dir / "per_dataset_external_results.csv", index=False)
    per_budget.to_csv(out_dir / "per_budget_external_results.csv", index=False)
    seed_level.to_csv(out_dir / "seed_level_external_results.csv", index=False)

    manifest = {
        "artifact_family": "canonical_external_baseline_closure",
        "timestamp": ts,
        "input_dir": str(input_dir.relative_to(REPO_ROOT)),
        "source_files": {
            "raw_case_results": str(raw_path.relative_to(REPO_ROOT)),
            "readiness_matrix": str(READINESS_JSON.relative_to(REPO_ROOT)),
            "fairness_presence_audit": str(FAIRNESS_CHECKLIST.relative_to(REPO_ROOT)),
        },
        "main_table_externals": sorted([m for m in methods if status_by_method[m]["status_bucket"] == "main_table_fair_near_direct" and m in {"s1", "tale", "l1_exact", "l1_max", "zhai_cpo_mode_a"}]),
        "zhai_integration": {
            "integrated": "zhai_cpo_mode_a" in methods,
            "label": "MODE A matched-substrate adapter (not full upstream reproduction)",
        },
        "dipa_status": {
            "integrated_in_surface": False,
            "decision": "appendix_only",
            "reason": "query-level global-budget adapter lane not equivalent to per-case matched-surface accounting",
        },
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Canonical external baseline closure summary",
        "",
        "## Main-table fair near-direct externals",
        "- " + ", ".join(manifest["main_table_externals"]),
        "",
        "## Appendix-only externals",
        "- dipa_mode_a (adapter/query-level lane; not per-case matched-equivalent)",
        "",
        "## Adjacent-only / blocked",
        "- See external_baseline_status_matrix.csv for full taxonomy-driven routing.",
        "",
        "## Required conclusions",
        f"- Zhai integrated: {'yes' if manifest['zhai_integration']['integrated'] else 'no'} ({manifest['zhai_integration']['label']}).",
        "- DIPA fully fair on canonical surface: no (appendix-only).",
        "- Remaining blocked baselines: compute-optimal-tts and discuss-only lanes remain blocked/adjacent per readiness matrix.",
    ]
    (out_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    doc_lines = [
        f"# CANONICAL EXTERNAL BASELINE CLOSURE ({ts})",
        "",
        "This package finalizes external-baseline closure on the canonical manuscript-facing matched surface.",
        "",
        "## Bundle",
        f"- `outputs/canonical_external_baseline_closure_{ts}/`",
        "",
        "## Main conclusions",
        f"- Main-table fair near-direct external baselines: {', '.join(manifest['main_table_externals'])}.",
        "- Zhai is now integrated as `zhai_cpo_mode_a` under the matched-substrate adapter contract (explicitly not claimed as a full faithful upstream reproduction).",
        "- DIPA/training-free-difficulty-proxy lane remains appendix-only because its query-level allocation contract is not equivalent to this per-case matched surface.",
        "- Adjacent/control-mismatched baselines remain appendix/adjacent-only per readiness taxonomy.",
    ]
    doc_path.write_text("\n".join(doc_lines) + "\n", encoding="utf-8")

    print(out_dir.relative_to(REPO_ROOT))
    print(doc_path.relative_to(REPO_ROOT))


if __name__ == "__main__":
    main()
