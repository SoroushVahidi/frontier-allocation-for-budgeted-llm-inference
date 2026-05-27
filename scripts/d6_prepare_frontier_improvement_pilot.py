#!/usr/bin/env python3
"""Prepare D6 frontier improvement pilot artifacts (no API calls).

Creates a timestamped run under outputs/job_d6_frontier_improvement_pilot_20260525/
with pilot case selection + generation manifest + evaluation plan.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

FRONTIER = "direct_reserve_semantic_frontier_v2"
L1 = "external_l1_max"
S1 = "external_s1_budget_forcing"
TALE = "external_tale_prompt_budgeting"
EXTERNALS = [L1, S1, TALE]

VARIANTS = [
    "frontier_math_extended_verify_v1",
    "frontier_math_answer_type_control_v1",
    "frontier_symbolic_check_v1",
]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def slug_now() -> str:
    return datetime.now(timezone.utc).strftime("run_%Y%m%dT%H%M%SZ")


def ensure_run_dir(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    run = root / slug_now()
    run.mkdir(parents=True, exist_ok=False)
    return run


def first_nonempty(*vals: Any) -> str:
    for v in vals:
        if pd.notna(v) and str(v) != "":
            return str(v)
    return ""


def choose_split_order(df: pd.DataFrame) -> pd.DataFrame:
    rank = {"test": 0, "validation": 1, "train": 2, "seen_dev": 3}
    out = df.copy()
    out["_split_rank"] = out["split"].map(rank).fillna(9)
    out = out.sort_values(["_split_rank", "pool_id"]).drop(columns=["_split_rank"])
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare D6 frontier improvement pilot artifacts (no API)")
    parser.add_argument("--input-dir", default="outputs/unified_learning_tables_20260525/run_20260525T184354Z")
    parser.add_argument("--corrected-baseline-dir", default="outputs/baseline_selector_definition_audit_20260525/run_20260525T194246Z")
    parser.add_argument("--corrected-eval-dir", default="outputs/corrected_d1_d2_evaluation_20260525/run_20260525T201240Z")
    parser.add_argument("--d2-dir", default="outputs/job_d2_reliability_selector_20260525/run_20260525T192302Z")
    parser.add_argument("--d3-dir", default="outputs/job_d3_conservative_override_20260525/run_20260525T203613Z")
    parser.add_argument("--d4-dir", default="outputs/job_d4_lambdamart_ranking_20260525/run_20260525T211828Z")
    parser.add_argument("--output-root", default="outputs/job_d6_frontier_improvement_pilot_20260525")
    parser.add_argument("--ledger-root", default="outputs/training_experiment_ledger_20260525")
    parser.add_argument("--cohere-math-rescue", type=int, default=40)
    parser.add_argument("--cloudrift-math-rescue", type=int, default=40)
    parser.add_argument("--math-regression", type=int, default=40)
    parser.add_argument("--gsm-control", type=int, default=40)
    args = parser.parse_args()

    in_dir = Path(args.input_dir)
    corr_base_dir = Path(args.corrected_baseline_dir)
    out_root = Path(args.output_root)
    ledger_root = Path(args.ledger_root)

    run_dir = ensure_run_dir(out_root)

    cand = pd.read_csv(
        in_dir / "unified_candidate_action_table.csv",
        usecols=[
            "pool_id",
            "scenario_id",
            "provider",
            "dataset",
            "split",
            "example_uid",
            "original_example_id",
            "question_hash",
            "method",
            "normalized_answer",
            "candidate_correct",
            "candidate_correct_exact",
            "candidate_correct_combined",
        ],
    )
    corr = pd.read_csv(corr_base_dir / "corrected_baseline_pool_decisions.csv")

    piv = (
        cand.pivot_table(
            index=["pool_id", "scenario_id", "provider", "dataset", "split", "example_uid", "original_example_id", "question_hash"],
            columns="method",
            values="candidate_correct",
            aggfunc="first",
        )
        .reset_index()
    )

    for m in [FRONTIER, L1, S1, TALE]:
        if m not in piv.columns:
            piv[m] = 0

    piv["frontier_correct"] = piv[FRONTIER].fillna(0).astype(int)
    piv["l1_correct"] = piv[L1].fillna(0).astype(int)
    piv["s1_correct"] = piv[S1].fillna(0).astype(int)
    piv["tale_correct"] = piv[TALE].fillna(0).astype(int)
    piv["any_external_correct"] = piv[["l1_correct", "s1_correct", "tale_correct"]].max(axis=1).astype(int)

    # attach frontier answer text for context
    front = cand[cand["method"] == FRONTIER][["pool_id", "normalized_answer", "candidate_correct", "candidate_correct_exact", "candidate_correct_combined"]].copy()
    front = front.rename(
        columns={
            "normalized_answer": "old_frontier_normalized_answer",
            "candidate_correct": "old_frontier_correct",
            "candidate_correct_exact": "old_frontier_correct_exact",
            "candidate_correct_combined": "old_frontier_correct_combined",
        }
    )
    piv = piv.merge(front, on="pool_id", how="left")

    # corrected baseline fields for reference only
    keep = [
        "pool_id",
        "select_frontier_correct",
        "select_l1_correct",
        "select_s1_correct",
        "select_tale_correct",
        "pooled4_plurality_correct",
        "agreement_largest_cluster_correct",
        "agreement_strict_2plus_correct",
        "oracle_correct",
    ]
    keep = [c for c in keep if c in corr.columns]
    piv = piv.merge(corr[keep].drop_duplicates("pool_id"), on="pool_id", how="left")

    # Buckets
    b1 = piv[
        (piv["scenario_id"] == "cohere_math500")
        & (piv["frontier_correct"] == 0)
        & (piv["any_external_correct"] == 1)
    ].copy()
    b1 = choose_split_order(b1).head(args.cohere_math_rescue)
    b1["selection_bucket"] = "cohere_math500_frontier_wrong_external_rescue"
    b1["selection_reason"] = "frontier wrong and at least one external source correct (offline stratification)"

    b2 = piv[
        (piv["scenario_id"] == "cloudrift_math500")
        & (piv["frontier_correct"] == 0)
        & (piv["any_external_correct"] == 1)
    ].copy()
    b2 = choose_split_order(b2).head(args.cloudrift_math_rescue)
    b2["selection_bucket"] = "cloudrift_math500_frontier_wrong_external_rescue"
    b2["selection_reason"] = "frontier wrong and at least one external source correct (offline stratification)"

    # regression set: frontier-correct math500 from both providers
    reg = piv[
        (piv["dataset"] == "math500")
        & (piv["provider"].isin(["cohere", "cloudrift"]))
        & (piv["frontier_correct"] == 1)
    ].copy()
    reg = choose_split_order(reg)
    reg_rows = []
    per_provider = max(1, args.math_regression // 2)
    for prov in ["cohere", "cloudrift"]:
        reg_rows.append(reg[reg["provider"] == prov].head(per_provider))
    b3 = pd.concat(reg_rows, ignore_index=True)
    b3 = choose_split_order(b3).head(args.math_regression)
    b3["selection_bucket"] = "math500_frontier_correct_regression_check"
    b3["selection_reason"] = "frontier currently correct; include for regression protection"

    # GSM8K control: cohere/cloudrift, prioritize test then validation
    gsm = piv[
        (piv["dataset"] == "gsm8k")
        & (piv["provider"].isin(["cohere", "cloudrift"]))
    ].copy()
    gsm = choose_split_order(gsm)
    ctrl_rows = []
    half_per_provider = max(2, args.gsm_control // 4)
    for prov in ["cohere", "cloudrift"]:
        gp = gsm[gsm["provider"] == prov]
        good = gp[gp["frontier_correct"] == 1].head(half_per_provider)
        hard = gp[(gp["frontier_correct"] == 0) & (gp["any_external_correct"] == 1)].head(half_per_provider)
        ctrl_rows.extend([good, hard])
    b4 = pd.concat(ctrl_rows, ignore_index=True)
    b4 = choose_split_order(b4).head(args.gsm_control)
    b4["selection_bucket"] = "gsm8k_control_slice"
    b4["selection_reason"] = "arithmetic control slice; includes easy frontier-correct and hard frontier-miss/external-rescue pools"

    selected = pd.concat([b1, b2, b3, b4], ignore_index=True).drop_duplicates("pool_id").reset_index(drop=True)

    selected["readiness_bucket"] = selected["split"].map(lambda s: "test_ready" if s == "test" else ("validation_ready" if s == "validation" else ("seen_dev_proxy" if s == "seen_dev" else "train_reference")))
    selected["variants_to_generate"] = json.dumps(VARIANTS)
    selected["api_call_status"] = "not_run"
    selected["leakage_safety_note"] = (
        "Selection uses local offline artifacts for stratification only. "
        "Gold/correctness labels are offline-only and must not be runtime routing features."
    )

    # jsonl records for execution planning
    records = []
    for _, r in selected.iterrows():
        rec = {
            "scenario": r["scenario_id"],
            "provider": r["provider"],
            "dataset": r["dataset"],
            "split": r["split"],
            "readiness_bucket": r["readiness_bucket"],
            "pool_id": r["pool_id"],
            "example_uid": first_nonempty(r.get("example_uid")),
            "original_example_id": first_nonempty(r.get("original_example_id"), r.get("question_hash")),
            "question_hash": first_nonempty(r.get("question_hash")),
            "old_frontier": {
                "method": FRONTIER,
                "normalized_answer": first_nonempty(r.get("old_frontier_normalized_answer")),
                "correct": int(r.get("old_frontier_correct", 0)) if pd.notna(r.get("old_frontier_correct", 0)) else 0,
                "correct_exact": int(r.get("old_frontier_correct_exact", 0)) if pd.notna(r.get("old_frontier_correct_exact", 0)) else 0,
                "correct_combined": first_nonempty(r.get("old_frontier_correct_combined")),
            },
            "external_correct_flags": {
                "select_l1_correct": int(r.get("l1_correct", 0)),
                "select_s1_correct": int(r.get("s1_correct", 0)),
                "select_tale_correct": int(r.get("tale_correct", 0)),
                "any_external_correct": int(r.get("any_external_correct", 0)),
            },
            "corrected_fixed_baseline_flags": {
                "select_frontier_correct": int(r.get("select_frontier_correct", 0)) if pd.notna(r.get("select_frontier_correct", 0)) else 0,
                "select_l1_correct": int(r.get("select_l1_correct", 0)) if pd.notna(r.get("select_l1_correct", 0)) else 0,
                "select_s1_correct": int(r.get("select_s1_correct", 0)) if pd.notna(r.get("select_s1_correct", 0)) else 0,
                "select_tale_correct": int(r.get("select_tale_correct", 0)) if pd.notna(r.get("select_tale_correct", 0)) else 0,
                "pooled4_plurality_correct": int(r.get("pooled4_plurality_correct", 0)) if pd.notna(r.get("pooled4_plurality_correct", 0)) else 0,
                "agreement_largest_cluster_correct": int(r.get("agreement_largest_cluster_correct", 0)) if pd.notna(r.get("agreement_largest_cluster_correct", 0)) else 0,
                "agreement_strict_2plus_correct": int(r.get("agreement_strict_2plus_correct", 0)) if pd.notna(r.get("agreement_strict_2plus_correct", 0)) else 0,
            },
            "oracle_upper_bound": int(r.get("oracle_correct", 0)) if pd.notna(r.get("oracle_correct", 0)) else 0,
            "reason_selected": r["selection_reason"],
            "selection_bucket": r["selection_bucket"],
            "variant_names": VARIANTS,
            "leakage_safety_note": r["leakage_safety_note"],
            "api_call_status": "not_run",
        }
        records.append(rec)

    # Write artifacts
    pilot_jsonl = run_dir / "pilot_case_selection.jsonl"
    with pilot_jsonl.open("w") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=True) + "\n")

    summary = {
        "generated_at_utc": now_utc(),
        "total_selected_cases": len(records),
        "by_bucket": selected["selection_bucket"].value_counts().to_dict(),
        "by_scenario": selected["scenario_id"].value_counts().to_dict(),
        "by_split": selected["split"].value_counts().to_dict(),
        "by_provider": selected["provider"].value_counts().to_dict(),
        "variant_names": VARIANTS,
        "api_call_status": "not_run",
    }
    (run_dir / "pilot_case_selection_summary.json").write_text(json.dumps(summary, indent=2))

    manifest = {
        "job": "D6 frontier improvement pilot",
        "prepared_at_utc": now_utc(),
        "status": "prepared_not_run",
        "api_call_status": "not_run",
        "output_run_dir": str(run_dir),
        "input_artifacts": {
            "unified_learning_tables": str(in_dir),
            "corrected_baseline_dir": str(corr_base_dir),
            "corrected_eval_dir": args.corrected_eval_dir,
            "d2_dir": args.d2_dir,
            "d3_dir": args.d3_dir,
            "d4_dir": args.d4_dir,
        },
        "selection_rules": {
            "cohere_math500_rescue": "frontier wrong && any(L1,S1,TALE correct)",
            "cloudrift_math500_rescue": "frontier wrong && any(L1,S1,TALE correct)",
            "math500_regression": "frontier correct",
            "gsm8k_control": "cohere/cloudrift mixed control",
        },
        "variant_names": VARIANTS,
        "leakage_safety": [
            "No API calls in preparation",
            "No runtime routing by gold labels",
            "Correctness labels used offline only for pilot stratification/evaluation",
        ],
        "pilot_case_selection_jsonl": str(pilot_jsonl),
        "pilot_case_selection_summary_json": str(run_dir / "pilot_case_selection_summary.json"),
        "case_count": len(records),
    }
    (run_dir / "d6_generation_manifest.json").write_text(json.dumps(manifest, indent=2))

    eval_plan = [
        "# D6 Evaluation Plan",
        "",
        "## Scope",
        "- Prepare-only run (no API generation executed).",
        "- Evaluate after generation using corrected fixed-policy baselines only.",
        "",
        "## Baselines (Allowed)",
        "- select_frontier_correct",
        "- select_l1_correct",
        "- select_s1_correct",
        "- select_tale_correct",
        "- pooled4_plurality_correct",
        "- agreement_largest_cluster_correct",
        "- agreement_strict_2plus_correct (if available)",
        "",
        "## Metrics After Generation",
        "- old frontier vs new variant raw accuracy",
        "- unique-correct additions by variant",
        "- regression rate on frontier-correct set",
        "- oracle ceiling before vs after adding variants (upper bound only)",
        "- selector accuracy after adding variants vs corrected fixed-policy baselines and D2/D3/D4",
        "- frontier contribution share before vs after",
        "- per-scenario focus: cohere_math500, cloudrift_math500",
        "- GSM8K control integrity checks",
        "",
        "## Leakage Discipline",
        "- Gold/correct labels are offline-eval only.",
        "- Runtime selection logic must remain gold-free.",
    ]
    (run_dir / "d6_eval_plan.md").write_text("\n".join(eval_plan) + "\n")

    readme = [
        "# D6 Frontier Improvement Pilot (Prepared, Not Run)",
        "",
        f"Prepared at: {now_utc()}",
        f"Run dir: `{run_dir}`",
        "",
        "This directory contains local, no-API preparation artifacts for D6.",
        "Use tmux for any later API generation step.",
    ]
    (run_dir / "README.md").write_text("\n".join(readme) + "\n")

    root_readme = [
        "# D6 Frontier Improvement Pilot Root",
        "",
        f"Latest prepared run: `{run_dir.name}`",
        "All runs are timestamped and preserved.",
    ]
    (out_root / "README.md").write_text("\n".join(root_readme) + "\n")

    # ledger update: planned-only entry
    ledger_csv = ledger_root / "training_experiment_ledger.csv"
    ledger_md = ledger_root / "training_experiment_ledger.md"

    if ledger_csv.exists():
        led = pd.read_csv(ledger_csv)
    else:
        led = pd.DataFrame()

    new_row = {
        "run_id": run_dir.name,
        "date_time_utc": now_utc(),
        "input_table_path": str(in_dir),
        "output_path": str(run_dir),
        "model_families_tried": "planned_only_no_api",
        "feature_groups_used": "pilot_case_stratification_offline",
        "reliability_features_used": "n/a",
        "complementarity_features_used": "n/a",
        "calibration_used": "n/a",
        "gpu_used": "no",
        "clean_test_wins_ties_losses": "not_run",
        "seen_dev_wins_ties_losses": "not_run",
        "macro_accuracy": "not_run",
        "worst_scenario_accuracy": "not_run",
        "biggest_losses": "not_run",
        "promotion_decision": "planned_not_run",
        "next_recommended_training": "Await explicit API approval; then run D6 generation in tmux",
    }

    led = pd.concat([led, pd.DataFrame([new_row])], ignore_index=True)
    led.to_csv(ledger_csv, index=False)

    def md_table(df: pd.DataFrame, title: str) -> str:
        lines = [f"# {title}", ""]
        if df.empty:
            lines.append("(no rows)")
            return "\n".join(lines) + "\n"
        cols = list(df.columns)
        lines.append("| " + " | ".join(cols) + " |")
        lines.append("|" + "|".join(["---"] * len(cols)) + "|")
        for _, rr in df.iterrows():
            lines.append("| " + " | ".join(str(rr[c]) for c in cols) + " |")
        return "\n".join(lines) + "\n"

    ledger_md.write_text(md_table(led, "Training Experiment Ledger"))

    # keep backlog explicitly showing D6 prepared (not run)
    backlog = [
        "# Training Backlog",
        "",
        "In progress / prepared:",
        f"- D6 frontier variant generation/inclusion (prepared only, not run): `{run_dir}`",
        "",
        "Not-yet-run planned experiments:",
        "- D5 oracle-availability head",
        "- D6 frontier variant generation/inclusion (await API approval)",
        "- D7 Fireworks/Cerebras/full MATH-500 data expansion",
        "- D8 cluster-level reliability-weighted voting",
    ]
    (ledger_root / "training_backlog.md").write_text("\n".join(backlog) + "\n")

    print(str(run_dir))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
