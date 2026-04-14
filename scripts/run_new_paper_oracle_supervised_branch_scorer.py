#!/usr/bin/env python3
"""Train/evaluate branch scorers with approximate bounded oracle-ish continuation labels."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import subprocess
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.frontier_matrix_core import (  # noqa: E402
    build_frontier_strategies,
    evaluate_strategies_on_examples,
    generator_factory_for_mode,
    load_pilot_examples,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="New-paper oracle-supervised branch scorer comparison")
    p.add_argument("--dataset", default="openai/gsm8k")
    p.add_argument("--subset-size", type=int, default=36)
    p.add_argument("--seed", type=int, default=41)
    p.add_argument("--budget", type=int, default=10)
    p.add_argument("--output-root", default="outputs/new_paper/oracle_supervised_branch_scorer")
    p.add_argument("--oracle-label-run-dir", default=None, help="Use existing oracle label run dir if provided.")
    p.add_argument("--oracle-label-episodes", type=int, default=30)
    p.add_argument("--oracle-label-decision-budget", type=int, default=10)
    p.add_argument("--oracle-label-rollouts-per-policy", type=int, default=4)
    p.add_argument("--oracle-pair-tie-margin", type=float, default=0.02)
    p.add_argument("--oracle-pair-improved-calibration", action="store_true")
    p.add_argument("--oracle-pair-uncertainty-scale", type=float, default=1.0)
    p.add_argument("--oracle-pair-min-effective-margin", type=float, default=0.0)
    p.add_argument("--oracle-train-min-confidence", type=float, default=0.0)
    p.add_argument("--oracle-train-drop-uncertain", action="store_true")
    p.add_argument("--oracle-label-value-aggregation", choices=["max", "robust_blend"], default="max")
    p.add_argument("--oracle-label-value-std-penalty", type=float, default=0.0)
    p.add_argument("--proxy-ranking-episodes", type=int, default=700)
    p.add_argument("--use-openai-api", action="store_true")
    p.add_argument("--openai-model", default="gpt-4.1-mini")
    p.add_argument("--temperature", type=float, default=0.2)
    p.add_argument("--max-output-tokens", type=int, default=180)
    p.add_argument("--timeout-seconds", type=int, default=45)
    return p.parse_args()


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            out.append(json.loads(line))
    return out


def _oracle_accuracy(rows: list[dict[str, Any]]) -> float:
    by_ex: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_ex.setdefault(str(row["example_id"]), []).append(row)
    if not by_ex:
        return 0.0
    return sum(1 for rr in by_ex.values() if any(bool(r["is_correct"]) for r in rr)) / len(by_ex)


def _resolve_oracle_label_dir(args: argparse.Namespace, run_dir: Path) -> Path:
    if args.oracle_label_run_dir:
        return Path(args.oracle_label_run_dir)
    _run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/run_new_paper_oracle_branch_label_generation.py"),
            "--output-root",
            str(run_dir / "oracle_label_runs"),
            "--episodes",
            str(args.oracle_label_episodes),
            "--decision-budget",
            str(args.oracle_label_decision_budget),
            "--rollouts-per-policy",
            str(args.oracle_label_rollouts_per_policy),
            "--seed",
            str(args.seed),
        ]
    )
    # Single run generated in temporary root.
    generated = sorted((run_dir / "oracle_label_runs").glob("*"))
    if not generated:
        raise RuntimeError("Oracle label generation did not produce a run directory.")
    return generated[-1]


def main() -> None:
    args = parse_args()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(args.output_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    oracle_label_dir = _resolve_oracle_label_dir(args, run_dir)
    oracle_branch_labels = oracle_label_dir / "branch_oracle_labels.jsonl"

    oracle_pairwise_dataset = run_dir / "oracle_pairwise_dataset.jsonl"
    proxy_ranking_dataset = run_dir / "proxy_branch_scorer_v3_dataset.jsonl"
    proxy_pairwise_dataset = run_dir / "proxy_pairwise_dataset.jsonl"
    proxy_model_path = run_dir / "adaptive_learned_branch_score_v7_bt_proxy.json"
    oracle_model_path = run_dir / "adaptive_learned_branch_score_v7_bt_oracleish.json"

    oracle_pair_cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts/build_oracle_pairwise_branch_dataset.py"),
        "--branch-labels",
        str(oracle_branch_labels),
        "--output",
        str(oracle_pairwise_dataset),
        "--tie-margin",
        str(args.oracle_pair_tie_margin),
        "--uncertainty-scale",
        str(args.oracle_pair_uncertainty_scale),
        "--min-effective-margin",
        str(args.oracle_pair_min_effective_margin),
    ]
    if args.oracle_pair_improved_calibration:
        oracle_pair_cmd.append("--improved-calibration")
    _run(oracle_pair_cmd)

    _run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/build_v3_ranking_dataset.py"),
            "--output-dir",
            str(run_dir),
            "--episodes",
            str(args.proxy_ranking_episodes),
            "--budget",
            str(args.budget),
            "--seed",
            str(args.seed),
        ]
    )

    generated_proxy_ranking = run_dir / "branch_scorer_v3_dataset.jsonl"
    if generated_proxy_ranking.exists():
        generated_proxy_ranking.replace(proxy_ranking_dataset)

    _run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/build_bt_pairwise_branch_dataset.py"),
            "--ranking-dataset",
            str(proxy_ranking_dataset),
            "--output",
            str(proxy_pairwise_dataset),
        ]
    )

    _run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/train_bt_pairwise_branch_scorer.py"),
            "--dataset",
            str(proxy_pairwise_dataset),
            "--output",
            str(proxy_model_path),
            "--seed",
            str(args.seed),
        ]
    )
    oracle_train_cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts/train_bt_pairwise_branch_scorer.py"),
        "--dataset",
        str(oracle_pairwise_dataset),
        "--output",
        str(oracle_model_path),
        "--seed",
        str(args.seed),
        "--weighting",
        "confidence",
        "--soft-uncertain-target",
        "--min-confidence",
        str(args.oracle_train_min_confidence),
    ]
    if args.oracle_train_drop_uncertain:
        oracle_train_cmd.append("--drop-uncertain")
    _run(oracle_train_cmd)

    rng = random.Random(args.seed)
    examples = load_pilot_examples(args.dataset, args.subset_size, args.seed)
    gen_factory = generator_factory_for_mode(
        args.use_openai_api,
        rng,
        args.openai_model,
        args.temperature,
        args.max_output_tokens,
        args.timeout_seconds,
    )
    strategies = build_frontier_strategies(
        gen_factory,
        args.budget,
        adaptive_min_expand_grid=[1],
        rng=rng,
        use_openai_api=args.use_openai_api,
        bt_pairwise_model_path=str(proxy_model_path),
        bt_pairwise_oracle_model_path=str(oracle_model_path),
    )
    metrics, rows = evaluate_strategies_on_examples(examples, strategies)

    selected = ["adaptive_min_expand_1", "adaptive_bt_pairwise", "adaptive_bt_pairwise_oracle", "reasoning_greedy"]
    eval_rows = [r for r in rows if r["strategy"] in selected]
    oracle_acc = _oracle_accuracy(eval_rows)

    method_metrics: list[dict[str, Any]] = []
    for m in selected:
        if m not in metrics:
            continue
        method_metrics.append(
            {
                "dataset": args.dataset,
                "budget": args.budget,
                "method": m,
                "accuracy": float(metrics[m]["accuracy"]),
                "avg_actions": float(metrics[m]["avg_actions"]),
                "gap_to_oracle": float(oracle_acc) - float(metrics[m]["accuracy"]),
            }
        )

    method_by_name = {r["method"]: r for r in method_metrics}
    proxy_acc = float(method_by_name.get("adaptive_bt_pairwise", {}).get("accuracy", 0.0))
    oracleish_acc = float(method_by_name.get("adaptive_bt_pairwise_oracle", {}).get("accuracy", 0.0))
    proxy_gap = float(method_by_name.get("adaptive_bt_pairwise", {}).get("gap_to_oracle", 0.0))
    oracleish_gap = float(method_by_name.get("adaptive_bt_pairwise_oracle", {}).get("gap_to_oracle", 0.0))

    comparison_rows = [
        {
            "comparison": "oracleish_supervised_vs_proxy_supervised",
            "proxy_accuracy": proxy_acc,
            "oracleish_accuracy": oracleish_acc,
            "delta_accuracy": oracleish_acc - proxy_acc,
            "proxy_gap_to_oracle": proxy_gap,
            "oracleish_gap_to_oracle": oracleish_gap,
            "delta_gap_to_oracle": oracleish_gap - proxy_gap,
            "improves_over_proxy": int(oracleish_acc > proxy_acc),
        }
    ]

    proxy_pair_rows = _load_jsonl(proxy_pairwise_dataset)
    oracle_pair_rows = _load_jsonl(oracle_pairwise_dataset)
    oracle_branch_rows = _load_jsonl(oracle_branch_labels)

    label_usage_rows = [
        {
            "label_set": "proxy_pairwise",
            "n_pairs": len(proxy_pair_rows),
            "n_train_pairs": sum(1 for r in proxy_pair_rows if r.get("split") == "train"),
            "n_test_pairs": sum(1 for r in proxy_pair_rows if r.get("split") == "test"),
            "mean_pair_confidence": sum(float(r.get("pair_confidence", 1.0)) for r in proxy_pair_rows) / max(1, len(proxy_pair_rows)),
            "tie_or_uncertain_rate": sum(int(r.get("tie_or_uncertain", 0)) for r in proxy_pair_rows) / max(1, len(proxy_pair_rows)),
            "label_caveat": "proxy target from logged future outcomes, not continuation search",
        },
        {
            "label_set": "oracleish_pairwise",
            "n_pairs": len(oracle_pair_rows),
            "n_train_pairs": sum(1 for r in oracle_pair_rows if r.get("split") == "train"),
            "n_test_pairs": sum(1 for r in oracle_pair_rows if r.get("split") == "test"),
            "mean_pair_confidence": sum(float(r.get("pair_confidence", 1.0)) for r in oracle_pair_rows) / max(1, len(oracle_pair_rows)),
            "tie_or_uncertain_rate": sum(int(r.get("tie_or_uncertain", 0)) for r in oracle_pair_rows) / max(1, len(oracle_pair_rows)),
            "label_caveat": "approximate bounded oracle-ish continuation labels, not exact oracle truth",
        },
        {
            "label_set": "oracleish_branch_scalar",
            "n_pairs": 0,
            "n_train_pairs": 0,
            "n_test_pairs": 0,
            "mean_pair_confidence": 0.0,
            "tie_or_uncertain_rate": 0.0,
            "label_caveat": (
                "branch labels available as approx_oracle_continuation_value for scalar/regression follow-up "
                f"(rows={len(oracle_branch_rows)})"
            ),
        },
    ]

    gap_rows = [
        {
            "dataset": args.dataset,
            "budget": args.budget,
            "oracle_accuracy": oracle_acc,
            "proxy_supervised_accuracy": proxy_acc,
            "oracleish_supervised_accuracy": oracleish_acc,
            "proxy_gap_to_oracle": proxy_gap,
            "oracleish_gap_to_oracle": oracleish_gap,
        }
    ]

    _write_csv(run_dir / "method_metrics.csv", method_metrics)
    _write_csv(run_dir / "oracle_supervision_comparison.csv", comparison_rows)
    _write_csv(run_dir / "oracle_gap_summary.csv", gap_rows)
    _write_csv(run_dir / "label_usage_summary.csv", label_usage_rows)

    manifest = {
        "run_id": run_id,
        "track": "new-paper",
        "dataset": args.dataset,
        "subset_size": args.subset_size,
        "budget": args.budget,
        "use_openai_api": args.use_openai_api,
        "openai_model": args.openai_model if args.use_openai_api else "simulated",
        "oracleish_label_definition": "approximate bounded oracle-ish continuation labels",
        "artifacts": {
            "method_metrics": str(run_dir / "method_metrics.csv"),
            "oracle_supervision_comparison": str(run_dir / "oracle_supervision_comparison.csv"),
            "oracle_gap_summary": str(run_dir / "oracle_gap_summary.csv"),
            "label_usage_summary": str(run_dir / "label_usage_summary.csv"),
            "run_manifest": str(run_dir / "run_manifest.json"),
            "interpretation": str(run_dir / "interpretation.md"),
            "proxy_model": str(proxy_model_path),
            "oracleish_model": str(oracle_model_path),
            "oracle_label_dir": str(oracle_label_dir),
        },
        "comparison": comparison_rows[0],
    }
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    interpretation = [
        f"# Oracle-supervised branch scorer comparison ({run_id})",
        "",
        "- Supervision type is **approximate bounded oracle-ish continuation labels** (not exact global oracle).",
        "- Training path uses pairwise BT objective for both proxy and oracle-ish datasets, with scalar argmax inference at test time.",
        f"- Proxy-supervised adaptive_bt_pairwise accuracy: **{proxy_acc:.4f}**.",
        f"- Oracle-ish-supervised adaptive_bt_pairwise_oracle accuracy: **{oracleish_acc:.4f}**.",
        f"- Delta accuracy (oracle-ish - proxy): **{oracleish_acc - proxy_acc:+.4f}**.",
        f"- Proxy gap to oracle: **{proxy_gap:.4f}**.",
        f"- Oracle-ish gap to oracle: **{oracleish_gap:.4f}**.",
        f"- Delta oracle gap (oracle-ish - proxy): **{oracleish_gap - proxy_gap:+.4f}** (negative is better).",
        f"- Real-model status: {'enabled' if args.use_openai_api else 'simulator-backed only in this run'}.",
        "",
        "Recommendation rule-of-thumb:",
        "- If accuracy improves and oracle gap shrinks, expand oracle-ish label generation as the next supervision path.",
        "- If mixed/flat, keep oracle-ish labels as a complementary source and expand depth/budget coverage first.",
    ]
    (run_dir / "interpretation.md").write_text("\n".join(interpretation) + "\n", encoding="utf-8")

    print(json.dumps({"run_dir": str(run_dir), "comparison": comparison_rows[0]}, indent=2))


if __name__ == "__main__":
    main()
