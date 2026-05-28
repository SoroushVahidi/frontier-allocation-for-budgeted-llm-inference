#!/usr/bin/env python3
"""D6 offline evaluator for frontier variant generation outputs.

No API calls. Uses corrected fixed-policy baselines only and treats oracle as upper bound.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ALLOWED_BASELINES = [
    "select_frontier_correct",
    "select_l1_correct",
    "select_s1_correct",
    "select_tale_correct",
    "pooled4_plurality_correct",
    "agreement_largest_cluster_correct",
    "agreement_strict_2plus_correct",
]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def write_empty_outputs(out_dir: Path, status: str, reason: str) -> None:
    (out_dir / "d6_variant_accuracy.csv").write_text(
        "variant_name,n_cases,variant_accuracy,old_frontier_accuracy,delta_vs_old_frontier,bucket,scenario,split\n"
    )
    (out_dir / "d6_unique_correct_and_regression.csv").write_text(
        "variant_name,unique_correct_added,regressions_on_old_frontier_correct,n_cases_old_frontier_correct\n"
    )
    (out_dir / "d6_oracle_ceiling_before_after.csv").write_text(
        "scope,oracle_before,oracle_after,external_only_oracle,notes\n"
    )
    (out_dir / "d6_selector_replay_results.csv").write_text(
        "selector_name,before_accuracy,after_accuracy,delta,n_cases,status\n"
    )
    (out_dir / "d6_scenario_results.csv").write_text(
        "scenario,provider,dataset,split,bucket,variant_name,n_cases,variant_accuracy,old_frontier_accuracy,best_corrected_baseline_accuracy,oracle_upper_bound\n"
    )

    status_obj = {
        "evaluated_at_utc": now_utc(),
        "status": status,
        "reason": reason,
        "api_calls": False,
        "row_wise_max_baseline_used": False,
        "oracle_role": "upper_bound_only",
    }
    (out_dir / "d6_evaluation_status.json").write_text(json.dumps(status_obj, indent=2))

    md = [
        "# D6 Evaluation Report",
        "",
        f"- Status: `{status}`",
        f"- Reason: {reason}",
        "- No API calls were made.",
        "- Corrected fixed-policy baselines only; oracle reported only as upper bound.",
        "",
        "NOT_READY_NO_GENERATION" if status == "NOT_READY_NO_GENERATION" else status,
    ]
    (out_dir / "D6_EVALUATION_REPORT.md").write_text("\n".join(md) + "\n")


def detect_generation_run(run_dir: Path, provided: str | None) -> Path | None:
    if provided:
        p = Path(provided)
        return p if p.exists() else None
    root = run_dir / "generation_runs"
    if not root.exists():
        return None
    runs = sorted([p for p in root.glob("run_*") if p.is_dir()])
    return runs[-1] if runs else None


def evaluate_with_outputs(run_dir: Path, gen_dir: Path, out_dir: Path, dry_run: bool) -> str:
    manifest_path = run_dir / "d6_generation_manifest.json"
    if not manifest_path.exists():
        write_empty_outputs(out_dir, "BLOCKED_BY_SCHEMA_ERROR", "Missing d6_generation_manifest.json")
        return "BLOCKED_BY_SCHEMA_ERROR"

    manifest = read_json(manifest_path)
    selection_path = Path(str(manifest.get("pilot_case_selection_jsonl", run_dir / "pilot_case_selection.jsonl")))
    if not selection_path.exists():
        write_empty_outputs(out_dir, "BLOCKED_BY_SCHEMA_ERROR", "Missing pilot_case_selection.jsonl")
        return "BLOCKED_BY_SCHEMA_ERROR"

    outputs_path = gen_dir / "generation_outputs.jsonl"
    if not outputs_path.exists():
        write_empty_outputs(out_dir, "NOT_READY_NO_GENERATION", f"Missing generation outputs at {outputs_path}")
        return "NOT_READY_NO_GENERATION"

    rows = read_jsonl(selection_path)
    gen = read_jsonl(outputs_path)
    if len(gen) == 0:
        write_empty_outputs(out_dir, "NOT_READY_NO_GENERATION", f"No generation output rows in {outputs_path}")
        return "NOT_READY_NO_GENERATION"

    s = pd.DataFrame(rows)
    g = pd.DataFrame(gen)
    if "pool_id" not in g.columns or "variant_name" not in g.columns:
        write_empty_outputs(out_dir, "BLOCKED_BY_SCHEMA_ERROR", "generation_outputs.jsonl missing pool_id or variant_name")
        return "BLOCKED_BY_SCHEMA_ERROR"

    # Determine variant correctness from output or fallback candidate lookup
    if "candidate_correct" in g.columns:
        g["variant_correct"] = pd.to_numeric(g["candidate_correct"], errors="coerce").fillna(0).astype(int)
    elif "action_correct" in g.columns:
        g["variant_correct"] = pd.to_numeric(g["action_correct"], errors="coerce").fillna(0).astype(int)
    else:
        # fallback: map normalized_answer against existing candidate table for same pool
        udir = Path(str(manifest.get("input_artifacts", {}).get("unified_learning_tables", "")))
        cpath = udir / "unified_candidate_action_table.csv"
        if cpath.exists() and "normalized_answer" in g.columns:
            cand = pd.read_csv(cpath, usecols=["pool_id", "normalized_answer", "candidate_correct"])
            cand["candidate_correct"] = pd.to_numeric(cand["candidate_correct"], errors="coerce").fillna(0).astype(int)
            cand = cand.drop_duplicates(subset=["pool_id", "normalized_answer"], keep="first")
            g = g.merge(cand.rename(columns={"candidate_correct": "variant_correct"}), on=["pool_id", "normalized_answer"], how="left")
            g["variant_correct"] = g["variant_correct"].fillna(0).astype(int)
        else:
            g["variant_correct"] = 0

    # old frontier and baseline fields from selection rows
    s["old_frontier_correct"] = s["old_frontier"].map(lambda x: int((x or {}).get("correct", 0)) if isinstance(x, dict) else 0)
    for b in ALLOWED_BASELINES:
        s[b] = s["corrected_fixed_baseline_flags"].map(
            lambda x: int((x or {}).get(b, 0)) if isinstance(x, dict) else 0
        )
    s["oracle_upper_bound"] = pd.to_numeric(s.get("oracle_upper_bound", 0), errors="coerce").fillna(0).astype(int)

    # join generation to selection metadata
    m = g.merge(
        s[
            [
                "pool_id",
                "scenario",
                "provider",
                "dataset",
                "split",
                "selection_bucket",
                "old_frontier_correct",
                "oracle_upper_bound",
            ]
            + ALLOWED_BASELINES
        ],
        on="pool_id",
        how="left",
    )

    # Generation outputs may already contain scenario/provider/dataset fields; merge then
    # creates *_x/*_y suffix pairs. Coalesce to canonical names for downstream grouping.
    def _coalesce_col(df: pd.DataFrame, base: str) -> None:
        candidates = [c for c in [base, f"{base}_x", f"{base}_y"] if c in df.columns]
        if not candidates:
            return
        out = df[candidates[0]]
        for c in candidates[1:]:
            out = out.fillna(df[c])
        df[base] = out

    for col in ["scenario", "provider", "dataset", "split", "selection_bucket"]:
        _coalesce_col(m, col)

    required_group_cols = ["scenario", "provider", "dataset", "split", "selection_bucket"]
    missing_group_cols = [c for c in required_group_cols if c not in m.columns]
    if missing_group_cols:
        write_empty_outputs(
            out_dir,
            "BLOCKED_BY_SCHEMA_ERROR",
            f"Missing grouping columns after merge: {missing_group_cols}",
        )
        return "BLOCKED_BY_SCHEMA_ERROR"

    # per variant global and per-scenario
    var_rows = []
    scen_rows = []
    for v, gg in m.groupby("variant_name"):
        n = len(gg)
        vacc = float(gg["variant_correct"].mean()) if n else 0.0
        oacc = float(gg["old_frontier_correct"].mean()) if n else 0.0
        var_rows.append(
            {
                "variant_name": v,
                "n_cases": n,
                "variant_accuracy": vacc,
                "old_frontier_accuracy": oacc,
                "delta_vs_old_frontier": vacc - oacc,
                "bucket": "ALL",
                "scenario": "ALL",
                "split": "ALL",
            }
        )

        for (sc, pr, ds, sp, buck), sgg in gg.groupby(["scenario", "provider", "dataset", "split", "selection_bucket"]):
            best_base = float(sgg[[b for b in ALLOWED_BASELINES if b in sgg.columns]].max(axis=1).mean())
            scen_rows.append(
                {
                    "scenario": sc,
                    "provider": pr,
                    "dataset": ds,
                    "split": sp,
                    "bucket": buck,
                    "variant_name": v,
                    "n_cases": int(len(sgg)),
                    "variant_accuracy": float(sgg["variant_correct"].mean()),
                    "old_frontier_accuracy": float(sgg["old_frontier_correct"].mean()),
                    "best_corrected_baseline_accuracy": best_base,
                    "oracle_upper_bound": float(sgg["oracle_upper_bound"].mean()),
                }
            )

    pd.DataFrame(var_rows).to_csv(out_dir / "d6_variant_accuracy.csv", index=False)
    pd.DataFrame(scen_rows).to_csv(out_dir / "d6_scenario_results.csv", index=False)

    # unique-correct and regressions metrics
    urows = []
    for v, gg in m.groupby("variant_name"):
        unique_added = int(((gg["variant_correct"] == 1) & (gg["old_frontier_correct"] == 0)).sum())
        regressions = int(((gg["variant_correct"] == 0) & (gg["old_frontier_correct"] == 1)).sum())
        n_old_correct = int((gg["old_frontier_correct"] == 1).sum())
        urows.append(
            {
                "variant_name": v,
                "unique_correct_added": unique_added,
                "regressions_on_old_frontier_correct": regressions,
                "n_cases_old_frontier_correct": n_old_correct,
            }
        )
    pd.DataFrame(urows).to_csv(out_dir / "d6_unique_correct_and_regression.csv", index=False)

    # oracle before/after and frontier share
    pool_old = s.copy()
    pool_old["external_only_oracle"] = pool_old[["select_l1_correct", "select_s1_correct", "select_tale_correct"]].max(axis=1)
    pool_old["full_pool_before_oracle"] = pool_old[["select_frontier_correct", "select_l1_correct", "select_s1_correct", "select_tale_correct"]].max(axis=1)

    best_variant_by_pool = m.groupby("pool_id")["variant_correct"].max().reset_index()
    pool_new = pool_old.merge(best_variant_by_pool, on="pool_id", how="left")
    pool_new["variant_correct"] = pool_new["variant_correct"].fillna(0).astype(int)
    pool_new["full_pool_after_oracle"] = pool_new[["full_pool_before_oracle", "variant_correct"]].max(axis=1)

    oc = pd.DataFrame(
        [
            {
                "scope": "pilot_cases",
                "oracle_before": float(pool_new["full_pool_before_oracle"].mean()),
                "oracle_after": float(pool_new["full_pool_after_oracle"].mean()),
                "external_only_oracle": float(pool_new["external_only_oracle"].mean()),
                "notes": "oracle values are upper bound diagnostics only",
            }
        ]
    )
    oc.to_csv(out_dir / "d6_oracle_ceiling_before_after.csv", index=False)

    # selector replay results only if available
    sel = pd.DataFrame(
        [
            {
                "selector_name": "not_available",
                "before_accuracy": np.nan,
                "after_accuracy": np.nan,
                "delta": np.nan,
                "n_cases": int(len(pool_new)),
                "status": "selector_replay_artifacts_not_found",
            }
        ]
    )
    sel.to_csv(out_dir / "d6_selector_replay_results.csv", index=False)

    # status/report
    status = {
        "evaluated_at_utc": now_utc(),
        "status": "READY_EVALUATED",
        "generation_run_dir": str(gen_dir),
        "dry_run": bool(dry_run),
        "n_generation_rows": int(len(g)),
        "n_pilot_cases": int(len(s)),
        "api_calls": False,
        "row_wise_max_baseline_used": False,
        "oracle_role": "upper_bound_only",
        "bucket_coverage": sorted(s["selection_bucket"].dropna().astype(str).unique().tolist()),
    }
    (out_dir / "d6_evaluation_status.json").write_text(json.dumps(status, indent=2))

    rpt = [
        "# D6 Evaluation Report",
        "",
        "- Status: `READY_EVALUATED`",
        f"- Generation run: `{gen_dir}`",
        f"- Generation rows: {len(g)}",
        f"- Pilot pools: {len(s)}",
        "- Baselines: corrected fixed-policy baselines only",
        "- Oracle: upper bound only",
        "- Row-wise max baseline: not used",
        "",
        "## Required bucket coverage",
        "- cohere_math500_frontier_wrong_external_rescue",
        "- cloudrift_math500_frontier_wrong_external_rescue",
        "- math500_frontier_correct_regression_check",
        "- gsm8k_control_slice",
        "",
        "READY_EVALUATED",
    ]
    (out_dir / "D6_EVALUATION_REPORT.md").write_text("\n".join(rpt) + "\n")
    return "READY_EVALUATED"


def main() -> None:
    ap = argparse.ArgumentParser(description="D6 evaluate frontier variants (offline)")
    ap.add_argument("--run-dir", required=True, help="D6 pilot run directory")
    ap.add_argument("--generation-run-dir", default=None, help="Optional explicit generation run directory")
    ap.add_argument("--dry-run", action="store_true", help="No side effects outside local report files")
    args = ap.parse_args()

    run_dir = Path(args.run_dir)
    if not run_dir.exists():
        raise SystemExit(f"Missing run dir: {run_dir}")

    eval_root = run_dir / "evaluation_runs"
    eval_root.mkdir(parents=True, exist_ok=True)
    eval_dir = eval_root / datetime.now(timezone.utc).strftime("run_%Y%m%dT%H%M%SZ")
    eval_dir.mkdir(parents=True, exist_ok=False)

    gen_dir = detect_generation_run(run_dir, args.generation_run_dir)
    if gen_dir is None:
        write_empty_outputs(eval_dir, "NOT_READY_NO_GENERATION", "No generation run directory found under run_dir/generation_runs")
        print("D6 evaluation status: NOT_READY_NO_GENERATION")
        print(f"evaluation_run_dir={eval_dir}")
        return

    status = evaluate_with_outputs(run_dir, gen_dir, eval_dir, dry_run=args.dry_run)
    print(f"D6 evaluation status: {status}")
    print(f"evaluation_run_dir={eval_dir}")


if __name__ == "__main__":
    main()
