#!/usr/bin/env python3
"""Bounded diagnosis + improvement pass for approximate bounded oracle-ish continuation labels."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def _latest_dir(root: Path) -> Path:
    dirs = sorted([p for p in root.glob("*") if p.is_dir()])
    if not dirs:
        raise RuntimeError(f"No run directories under {root}")
    return dirs[-1]


def _load_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        if not rows:
            f.write("")
            return
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Bounded oracle label quality improvement ablation")
    p.add_argument("--output-root", default="outputs/new_paper/oracle_label_improvement")
    p.add_argument("--run-id", default=None)
    p.add_argument("--seed", type=int, default=41)
    p.add_argument("--subset-size", type=int, default=36)
    p.add_argument("--budget", type=int, default=10)
    p.add_argument("--label-episodes", type=int, default=30)
    p.add_argument("--label-rollouts", type=int, default=4)
    p.add_argument("--proxy-ranking-episodes", type=int, default=700)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(args.output_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    base_label_root = run_dir / "oracle_labels_baseline"
    imp_label_root = run_dir / "oracle_labels_improved"

    # Baseline label generation.
    _run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/run_new_paper_oracle_branch_label_generation.py"),
            "--output-root",
            str(base_label_root),
            "--episodes",
            str(args.label_episodes),
            "--decision-budget",
            str(args.budget),
            "--rollouts-per-policy",
            str(args.label_rollouts),
            "--seed",
            str(args.seed),
            "--value-aggregation",
            "max",
            "--value-std-penalty",
            "0.0",
        ]
    )
    base_label_dir = _latest_dir(base_label_root)

    # Improved label generation (bounded robustness tweaks).
    _run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/run_new_paper_oracle_branch_label_generation.py"),
            "--output-root",
            str(imp_label_root),
            "--episodes",
            str(args.label_episodes),
            "--decision-budget",
            str(args.budget),
            "--rollouts-per-policy",
            str(args.label_rollouts),
            "--seed",
            str(args.seed),
            "--value-aggregation",
            "robust_blend",
            "--value-std-penalty",
            "0.25",
        ]
    )
    imp_label_dir = _latest_dir(imp_label_root)

    # Diagnostics.
    diag_root = run_dir / "oracle_label_diagnostics"
    _run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/run_new_paper_oracle_label_diagnostics.py"),
            "--branch-labels",
            str(base_label_dir / "branch_oracle_labels.jsonl"),
            "--pairwise",
            str(base_label_dir / "pairwise_oracle_preferences.jsonl"),
            "--output-root",
            str(diag_root),
            "--run-id",
            "baseline",
            "--compare-branch-labels",
            str(imp_label_dir / "branch_oracle_labels.jsonl"),
        ]
    )
    _run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/run_new_paper_oracle_label_diagnostics.py"),
            "--branch-labels",
            str(imp_label_dir / "branch_oracle_labels.jsonl"),
            "--pairwise",
            str(imp_label_dir / "pairwise_oracle_preferences.jsonl"),
            "--output-root",
            str(diag_root),
            "--run-id",
            "improved",
            "--compare-branch-labels",
            str(base_label_dir / "branch_oracle_labels.jsonl"),
        ]
    )

    # Supervised branch scorer ablations.
    scorer_root = run_dir / "scorer_runs"
    _run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/run_new_paper_oracle_supervised_branch_scorer.py"),
            "--output-root",
            str(scorer_root / "baseline"),
            "--oracle-label-run-dir",
            str(base_label_dir),
            "--seed",
            str(args.seed),
            "--subset-size",
            str(args.subset_size),
            "--budget",
            str(args.budget),
            "--proxy-ranking-episodes",
            str(args.proxy_ranking_episodes),
        ]
    )
    _run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/run_new_paper_oracle_supervised_branch_scorer.py"),
            "--output-root",
            str(scorer_root / "improved"),
            "--oracle-label-run-dir",
            str(imp_label_dir),
            "--seed",
            str(args.seed),
            "--subset-size",
            str(args.subset_size),
            "--budget",
            str(args.budget),
            "--proxy-ranking-episodes",
            str(args.proxy_ranking_episodes),
            "--oracle-pair-improved-calibration",
            "--oracle-pair-min-effective-margin",
            "0.35",
            "--oracle-train-min-confidence",
            "0.15",
            "--oracle-train-drop-uncertain",
        ]
    )

    baseline_score_dir = _latest_dir(scorer_root / "baseline")
    improved_score_dir = _latest_dir(scorer_root / "improved")

    baseline_metrics = _load_csv(baseline_score_dir / "method_metrics.csv")
    improved_metrics = _load_csv(improved_score_dir / "method_metrics.csv")
    baseline_comp = _load_csv(baseline_score_dir / "oracle_supervision_comparison.csv")[0]
    improved_comp = _load_csv(improved_score_dir / "oracle_supervision_comparison.csv")[0]
    baseline_label_usage = _load_csv(baseline_score_dir / "label_usage_summary.csv")
    improved_label_usage = _load_csv(improved_score_dir / "label_usage_summary.csv")

    def diag_summary(name: str) -> dict[str, Any]:
        return _load_json(diag_root / name / "oracle_label_diagnostic_summary.json")

    base_diag = diag_summary("baseline")
    imp_diag = diag_summary("improved")

    method_metrics = []
    for tag, rows in [("baseline", baseline_metrics), ("improved", improved_metrics)]:
        for r in rows:
            rr = dict(r)
            rr["label_pipeline"] = tag
            method_metrics.append(rr)

    quality_rows = [
        {
            "pipeline": "baseline",
            "decision_near_tie_rate": base_diag["decision_near_tie_rate"],
            "decision_mean_top_margin": base_diag["decision_mean_top_margin"],
            "decision_mean_value_spread": base_diag["decision_mean_value_spread"],
            "pair_tie_or_uncertain_rate": base_diag["pair_tie_or_uncertain_rate"],
            "one_feature_dominance_rate": base_diag["one_feature_dominance_rate"],
        },
        {
            "pipeline": "improved",
            "decision_near_tie_rate": imp_diag["decision_near_tie_rate"],
            "decision_mean_top_margin": imp_diag["decision_mean_top_margin"],
            "decision_mean_value_spread": imp_diag["decision_mean_value_spread"],
            "pair_tie_or_uncertain_rate": imp_diag["pair_tie_or_uncertain_rate"],
            "one_feature_dominance_rate": imp_diag["one_feature_dominance_rate"],
        },
    ]

    gap_rows = [
        {
            "pipeline": "baseline",
            "proxy_accuracy": baseline_comp["proxy_accuracy"],
            "oracleish_accuracy": baseline_comp["oracleish_accuracy"],
            "delta_accuracy_oracle_minus_proxy": baseline_comp["delta_accuracy"],
            "proxy_gap_to_oracle": baseline_comp["proxy_gap_to_oracle"],
            "oracleish_gap_to_oracle": baseline_comp["oracleish_gap_to_oracle"],
        },
        {
            "pipeline": "improved",
            "proxy_accuracy": improved_comp["proxy_accuracy"],
            "oracleish_accuracy": improved_comp["oracleish_accuracy"],
            "delta_accuracy_oracle_minus_proxy": improved_comp["delta_accuracy"],
            "proxy_gap_to_oracle": improved_comp["proxy_gap_to_oracle"],
            "oracleish_gap_to_oracle": improved_comp["oracleish_gap_to_oracle"],
        },
    ]

    label_usage_rows = []
    for tag, rows in [("baseline", baseline_label_usage), ("improved", improved_label_usage)]:
        for r in rows:
            rr = dict(r)
            rr["label_pipeline"] = tag
            label_usage_rows.append(rr)

    _write_csv(run_dir / "method_metrics.csv", method_metrics)
    _write_csv(run_dir / "oracle_label_quality_comparison.csv", quality_rows)
    _write_csv(run_dir / "oracle_gap_summary.csv", gap_rows)
    _write_csv(run_dir / "label_usage_summary.csv", label_usage_rows)

    manifest = {
        "run_id": run_id,
        "track": "new-paper",
        "label_definition": "approximate bounded oracle-ish continuation labels",
        "artifacts": {
            "method_metrics": str(run_dir / "method_metrics.csv"),
            "oracle_label_quality_comparison": str(run_dir / "oracle_label_quality_comparison.csv"),
            "oracle_gap_summary": str(run_dir / "oracle_gap_summary.csv"),
            "label_usage_summary": str(run_dir / "label_usage_summary.csv"),
            "diagnostics_root": str(diag_root),
            "baseline_label_dir": str(base_label_dir),
            "improved_label_dir": str(imp_label_dir),
            "baseline_score_dir": str(baseline_score_dir),
            "improved_score_dir": str(improved_score_dir),
        },
    }
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    interp = [
        f"# Oracle label improvement pass ({run_id})",
        "",
        "All labels here are **approximate bounded oracle-ish continuation labels**, not exact global oracle truth.",
        "",
        "## Primary diagnosis",
        f"- Baseline decision near-tie rate: {base_diag['decision_near_tie_rate']:.4f}.",
        f"- Baseline one-feature dominance rate: {base_diag['one_feature_dominance_rate']:.4f}.",
        f"- Baseline oracle top match with proxy top: {base_diag['oracle_top_match_proxy_rate']:.4f}.",
        f"- Baseline rerun/value stability signal: {base_diag.get('rerun_agreement')}.",
        "",
        "## Bounded improvements tested",
        "1) Robust rollout value aggregation (`robust_blend`) with uncertainty penalty.",
        "2) Uncertainty-aware pair conversion (`--improved-calibration`) plus low-effective-margin filtering and stricter training-pair usage.",
        "",
        "## Outcome",
        f"- Baseline oracle-ish vs proxy delta accuracy: {float(baseline_comp['delta_accuracy']):+.4f}.",
        f"- Improved oracle-ish vs proxy delta accuracy: {float(improved_comp['delta_accuracy']):+.4f}.",
        f"- Gap change (improved delta - baseline delta): {float(improved_comp['delta_accuracy']) - float(baseline_comp['delta_accuracy']):+.4f}.",
        "",
        "If improved still trails proxy, labels are still not clean enough and need additional bounded stability/coverage work before scaling training.",
    ]
    (run_dir / "interpretation.md").write_text("\n".join(interp) + "\n", encoding="utf-8")

    print(json.dumps({"run_id": run_id, "run_dir": str(run_dir)}, indent=2))


if __name__ == "__main__":
    main()
