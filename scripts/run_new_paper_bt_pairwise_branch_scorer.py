#!/usr/bin/env python3
"""New-paper BT pairwise branch scorer pass.

Pipeline:
1) Build ranking dataset with ordered history features.
2) Build pairwise preference dataset.
3) Train BT objective over scalar branch utility.
4) Evaluate scalar-inference controller against baselines and oracle.
"""

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

from experiments.frontier_matrix_core import build_frontier_strategies, evaluate_strategies_on_examples, generator_factory_for_mode, load_pilot_examples


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run BT pairwise branch scorer comparison (new-paper track)")
    p.add_argument("--dataset", default="openai/gsm8k")
    p.add_argument("--subset-size", type=int, default=36)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--budget", type=int, default=10)
    p.add_argument("--output-root", default="outputs/new_paper/bt_pairwise_branch_scorer")
    p.add_argument("--use-openai-api", action="store_true")
    p.add_argument("--openai-model", default="gpt-4.1-mini")
    p.add_argument("--temperature", type=float, default=0.2)
    p.add_argument("--max-output-tokens", type=int, default=180)
    p.add_argument("--timeout-seconds", type=int, default=45)
    p.add_argument("--include-prm-variants", action="store_true")
    return p.parse_args()


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow(row)


def _oracle_accuracy(rows: list[dict[str, Any]]) -> float:
    by_ex: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_ex.setdefault(str(row["example_id"]), []).append(row)
    if not by_ex:
        return 0.0
    return sum(1 for rr in by_ex.values() if any(bool(r["is_correct"]) for r in rr)) / len(by_ex)


def main() -> None:
    args = parse_args()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(args.output_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    ranking_dataset = run_dir / "branch_scorer_v3_dataset.jsonl"
    pairwise_dataset = run_dir / "pairwise_dataset.jsonl"
    model_path = run_dir / "adaptive_learned_branch_score_v7_bt.json"

    _run([
        sys.executable,
        str(REPO_ROOT / "scripts/build_v3_ranking_dataset.py"),
        "--output-dir",
        str(run_dir),
        "--episodes",
        "900",
        "--budget",
        str(args.budget),
        "--seed",
        str(args.seed),
    ])
    _run([
        sys.executable,
        str(REPO_ROOT / "scripts/build_bt_pairwise_branch_dataset.py"),
        "--ranking-dataset",
        str(ranking_dataset),
        "--output",
        str(pairwise_dataset),
    ])
    _run([
        sys.executable,
        str(REPO_ROOT / "scripts/train_bt_pairwise_branch_scorer.py"),
        "--dataset",
        str(pairwise_dataset),
        "--output",
        str(model_path),
        "--seed",
        str(args.seed),
    ])

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
        adaptive_min_expand_grid=[0, 1, 2],
        rng=rng,
        use_openai_api=args.use_openai_api,
        include_prm_variants=args.include_prm_variants,
        bt_pairwise_model_path=str(model_path),
    )
    metrics, rows = evaluate_strategies_on_examples(examples, strategies)

    selected_methods = [
        "adaptive_min_expand_1",
        "adaptive_bt_pairwise",
        "reasoning_greedy",
        "verifier_guided_search",
    ]
    if args.include_prm_variants and "adaptive_prm_partial" in metrics:
        selected_methods.append("adaptive_prm_partial")

    oracle_acc = _oracle_accuracy([r for r in rows if r["strategy"] in selected_methods])
    method_rows: list[dict[str, Any]] = []
    for m in selected_methods:
        if m not in metrics:
            continue
        method_rows.append(
            {
                "dataset": args.dataset,
                "budget": args.budget,
                "method": m,
                "accuracy": metrics[m]["accuracy"],
                "avg_actions": metrics[m]["avg_actions"],
                "gap_to_oracle": float(oracle_acc) - float(metrics[m]["accuracy"]),
            }
        )

    model = json.loads(model_path.read_text(encoding="utf-8"))
    scorer_rows = [
        {
            "metric": "bt_train_pair_accuracy",
            "value": float(model.get("train_pair_accuracy", 0.0)),
        },
        {
            "metric": "bt_test_pair_accuracy",
            "value": float(model.get("test_pair_accuracy", 0.0)),
        },
    ]
    oracle_rows = [
        {
            "dataset": args.dataset,
            "budget": args.budget,
            "oracle_accuracy": oracle_acc,
            "bt_accuracy": next((r["accuracy"] for r in method_rows if r["method"] == "adaptive_bt_pairwise"), 0.0),
            "oracle_gap_bt": next((r["gap_to_oracle"] for r in method_rows if r["method"] == "adaptive_bt_pairwise"), 0.0),
        }
    ]

    _write_csv(run_dir / "method_metrics.csv", method_rows)
    _write_csv(run_dir / "scorer_diagnostics.csv", scorer_rows)
    _write_csv(run_dir / "oracle_gap_summary.csv", oracle_rows)

    manifest = {
        "run_id": run_id,
        "dataset": args.dataset,
        "subset_size": args.subset_size,
        "budget": args.budget,
        "use_openai_api": args.use_openai_api,
        "openai_model": args.openai_model if args.use_openai_api else "simulated",
        "artifacts": {
            "pairwise_dataset": str(pairwise_dataset),
            "method_metrics": str(run_dir / "method_metrics.csv"),
            "scorer_diagnostics": str(run_dir / "scorer_diagnostics.csv"),
            "oracle_gap_summary": str(run_dir / "oracle_gap_summary.csv"),
            "model": str(model_path),
        },
    }
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    bt_acc = next((r["accuracy"] for r in method_rows if r["method"] == "adaptive_bt_pairwise"), 0.0)
    base_acc = next((r["accuracy"] for r in method_rows if r["method"] == "adaptive_min_expand_1"), 0.0)
    prm_acc = next((r["accuracy"] for r in method_rows if r["method"] == "adaptive_prm_partial"), None)

    interp = [
        f"# BT pairwise branch scorer interpretation ({run_id})",
        "",
        "- Pairwise BT training improves branch ranking iff pairwise accuracy and controller accuracy both rise versus current learned/progress baselines.",
        f"- Pairwise test accuracy (BT objective): **{float(model.get('test_pair_accuracy', 0.0)):.4f}**.",
        f"- Controller accuracy: adaptive_bt_pairwise={bt_acc:.4f}, adaptive_min_expand_1={base_acc:.4f}.",
        f"- Ordered-history encoding effect (pilot): {'positive' if bt_acc >= base_acc else 'mixed/negative'} in this run.",
        f"- Oracle gap for BT scorer: **{float(oracle_rows[0]['oracle_gap_bt']):.4f}** (smaller is better).",
        f"- Real-model-backed status: {'enabled' if args.use_openai_api else 'not run in this artifact (simulator-backed only)'}.",
        f"- Relative to PRM-style partial scoring: {'BT stronger in this run' if (prm_acc is not None and bt_acc > prm_acc) else 'no clear BT>PRM win in this run or PRM not included'}.",
        "",
        "Notes: training is pairwise, inference is scalar (one score per branch, then argmax); no O(n^2) pairwise inference path is used.",
    ]
    (run_dir / "interpretation.md").write_text("\n".join(interp) + "\n", encoding="utf-8")

    print(json.dumps({"run_dir": str(run_dir), "bt_accuracy": bt_acc, "baseline_accuracy": base_acc}, indent=2))


if __name__ == "__main__":
    main()
