#!/usr/bin/env python3
"""Reliability-weighted BT branch scorer run (new-paper track).

Pairwise supervision + scalar inference, with confidence-weighted BT ablations.
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
    p = argparse.ArgumentParser(description="Run reliability-weighted BT branch scorer")
    p.add_argument("--dataset", default="openai/gsm8k")
    p.add_argument("--subset-size", type=int, default=36)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--budget", type=int, default=10)
    p.add_argument("--output-root", default="outputs/new_paper/bt_reliability_weighted_branch_scorer")
    p.add_argument("--use-openai-api", action="store_true")
    p.add_argument("--openai-model", default="gpt-4.1-mini")
    p.add_argument("--temperature", type=float, default=0.2)
    p.add_argument("--max-output-tokens", type=int, default=180)
    p.add_argument("--timeout-seconds", type=int, default=45)
    p.add_argument("--include-prm-variants", action="store_true")
    p.add_argument("--min-confidence", type=float, default=0.20)
    return p.parse_args()


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
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


def _confidence_summary(pair_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not pair_rows:
        return []
    confs = [float(r.get("pair_confidence", 0.0)) for r in pair_rows]
    low = sum(1 for c in confs if c < 0.2)
    mid = sum(1 for c in confs if 0.2 <= c < 0.5)
    high = sum(1 for c in confs if c >= 0.5)
    uncertain = sum(1 for r in pair_rows if int(r.get("tie_or_uncertain", 0)) == 1)
    n = len(pair_rows)
    rel_keys = [
        "rel_margin_confidence",
        "rel_progress_agreement",
        "rel_distance_trend_clarity",
        "rel_value_stability",
        "rel_delta_consistency",
        "rel_budget_fit",
    ]
    rel_means = {k: sum(float(r.get(k, 0.0)) for r in pair_rows) / n for k in rel_keys}
    return [
        {"metric": "pair_rows", "value": float(n)},
        {"metric": "mean_pair_confidence", "value": sum(confs) / n},
        {"metric": "low_confidence_share_lt_0.2", "value": low / n},
        {"metric": "mid_confidence_share_0.2_to_0.5", "value": mid / n},
        {"metric": "high_confidence_share_ge_0.5", "value": high / n},
        {"metric": "tie_or_uncertain_share", "value": uncertain / n},
        *({"metric": f"mean_{k}", "value": v} for k, v in rel_means.items()),
    ]


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    return rows


def main() -> None:
    args = parse_args()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(args.output_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    ranking_dataset = run_dir / "branch_scorer_v3_dataset.jsonl"
    pair_dataset = run_dir / "pairwise_dataset_with_confidence.jsonl"
    plain_model = run_dir / "adaptive_learned_branch_score_v7_bt_plain.json"
    weighted_model = run_dir / "adaptive_learned_branch_score_v7_bt_reliability.json"
    weighted_filt_model = run_dir / "adaptive_learned_branch_score_v7_bt_reliability_filtered.json"

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
        str(pair_dataset),
    ])
    _run([
        sys.executable,
        str(REPO_ROOT / "scripts/train_bt_pairwise_branch_scorer.py"),
        "--dataset",
        str(pair_dataset),
        "--output",
        str(plain_model),
        "--weighting",
        "none",
        "--seed",
        str(args.seed),
    ])
    _run([
        sys.executable,
        str(REPO_ROOT / "scripts/train_bt_pairwise_branch_scorer.py"),
        "--dataset",
        str(pair_dataset),
        "--output",
        str(weighted_model),
        "--weighting",
        "confidence",
        "--seed",
        str(args.seed),
    ])
    _run([
        sys.executable,
        str(REPO_ROOT / "scripts/train_bt_pairwise_branch_scorer.py"),
        "--dataset",
        str(pair_dataset),
        "--output",
        str(weighted_filt_model),
        "--weighting",
        "confidence",
        "--min-confidence",
        str(args.min_confidence),
        "--drop-uncertain",
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
        bt_pairwise_model_path=str(plain_model),
        bt_pairwise_reliability_model_path=str(weighted_model),
    )
    # Keep filtered variant as scalar scorer comparison via same strategy family name pattern.
    strategies["adaptive_bt_pairwise_reliability_filtered"] = build_frontier_strategies(
        gen_factory,
        args.budget,
        adaptive_min_expand_grid=[1],
        rng=rng,
        use_openai_api=args.use_openai_api,
        bt_pairwise_reliability_model_path=str(weighted_filt_model),
    )["adaptive_bt_pairwise_reliability"]

    metrics, rows = evaluate_strategies_on_examples(examples, strategies)

    selected = [
        "adaptive_min_expand_1",
        "adaptive_bt_pairwise",
        "adaptive_bt_pairwise_reliability",
        "adaptive_bt_pairwise_reliability_filtered",
    ]
    if args.include_prm_variants and "adaptive_prm_partial" in metrics:
        selected.append("adaptive_prm_partial")

    oracle = _oracle_accuracy([r for r in rows if r["strategy"] in selected])
    method_rows = []
    for name in selected:
        if name not in metrics:
            continue
        method_rows.append(
            {
                "dataset": args.dataset,
                "budget": args.budget,
                "method": name,
                "accuracy": metrics[name]["accuracy"],
                "avg_actions": metrics[name]["avg_actions"],
                "gap_to_oracle": oracle - float(metrics[name]["accuracy"]),
            }
        )
    method_rows.append(
        {
            "dataset": args.dataset,
            "budget": args.budget,
            "method": "oracle_upper_bound",
            "accuracy": oracle,
            "avg_actions": float(args.budget),
            "gap_to_oracle": 0.0,
        }
    )

    plain = json.loads(plain_model.read_text(encoding="utf-8"))
    weighted = json.loads(weighted_model.read_text(encoding="utf-8"))
    filtered = json.loads(weighted_filt_model.read_text(encoding="utf-8"))
    scorer_diag = [
        {
            "variant": "plain_bt",
            "test_pair_accuracy": float(plain.get("test_pair_accuracy", 0.0)),
            "test_pair_accuracy_low_conf_lt_0.2": float(plain.get("test_pair_accuracy_low_conf_lt_0.2", 0.0)),
            "test_pair_accuracy_mid_conf_0.2_0.5": float(plain.get("test_pair_accuracy_mid_conf_0.2_0.5", 0.0)),
            "test_pair_accuracy_high_conf_ge_0.5": float(plain.get("test_pair_accuracy_high_conf_ge_0.5", 0.0)),
            "n_train_total": int(plain.get("n_train_total", 0)),
            "n_train_used": int(plain.get("n_train_used", 0)),
            "n_train_dropped_low_conf": int(plain.get("n_train_dropped_low_conf", 0)),
            "n_train_dropped_uncertain": int(plain.get("n_train_dropped_uncertain", 0)),
        },
        {
            "variant": "weighted_bt",
            "test_pair_accuracy": float(weighted.get("test_pair_accuracy", 0.0)),
            "test_pair_accuracy_low_conf_lt_0.2": float(weighted.get("test_pair_accuracy_low_conf_lt_0.2", 0.0)),
            "test_pair_accuracy_mid_conf_0.2_0.5": float(weighted.get("test_pair_accuracy_mid_conf_0.2_0.5", 0.0)),
            "test_pair_accuracy_high_conf_ge_0.5": float(weighted.get("test_pair_accuracy_high_conf_ge_0.5", 0.0)),
            "n_train_total": int(weighted.get("n_train_total", 0)),
            "n_train_used": int(weighted.get("n_train_used", 0)),
            "n_train_dropped_low_conf": int(weighted.get("n_train_dropped_low_conf", 0)),
            "n_train_dropped_uncertain": int(weighted.get("n_train_dropped_uncertain", 0)),
        },
        {
            "variant": "weighted_bt_filtered",
            "test_pair_accuracy": float(filtered.get("test_pair_accuracy", 0.0)),
            "test_pair_accuracy_low_conf_lt_0.2": float(filtered.get("test_pair_accuracy_low_conf_lt_0.2", 0.0)),
            "test_pair_accuracy_mid_conf_0.2_0.5": float(filtered.get("test_pair_accuracy_mid_conf_0.2_0.5", 0.0)),
            "test_pair_accuracy_high_conf_ge_0.5": float(filtered.get("test_pair_accuracy_high_conf_ge_0.5", 0.0)),
            "n_train_total": int(filtered.get("n_train_total", 0)),
            "n_train_used": int(filtered.get("n_train_used", 0)),
            "n_train_dropped_low_conf": int(filtered.get("n_train_dropped_low_conf", 0)),
            "n_train_dropped_uncertain": int(filtered.get("n_train_dropped_uncertain", 0)),
        },
    ]
    oracle_rows = [
        {
            "dataset": args.dataset,
            "budget": args.budget,
            "oracle_accuracy": oracle,
            "plain_bt_gap": next((r["gap_to_oracle"] for r in method_rows if r["method"] == "adaptive_bt_pairwise"), 0.0),
            "reliability_bt_gap": next((r["gap_to_oracle"] for r in method_rows if r["method"] == "adaptive_bt_pairwise_reliability"), 0.0),
            "reliability_filtered_bt_gap": next((r["gap_to_oracle"] for r in method_rows if r["method"] == "adaptive_bt_pairwise_reliability_filtered"), 0.0),
        }
    ]

    pair_rows = _load_jsonl(pair_dataset)
    conf_rows = _confidence_summary(pair_rows)

    _write_csv(run_dir / "method_metrics.csv", method_rows)
    _write_csv(run_dir / "scorer_diagnostics.csv", scorer_diag)
    _write_csv(run_dir / "oracle_gap_summary.csv", oracle_rows)
    _write_csv(run_dir / "pair_confidence_summary.csv", conf_rows)

    manifest = {
        "run_id": run_id,
        "dataset": args.dataset,
        "subset_size": args.subset_size,
        "budget": args.budget,
        "use_openai_api": args.use_openai_api,
        "artifacts": {
            "pairwise_dataset_with_confidence": str(pair_dataset),
            "method_metrics": str(run_dir / "method_metrics.csv"),
            "scorer_diagnostics": str(run_dir / "scorer_diagnostics.csv"),
            "oracle_gap_summary": str(run_dir / "oracle_gap_summary.csv"),
            "pair_confidence_summary": str(run_dir / "pair_confidence_summary.csv"),
            "plain_model": str(plain_model),
            "reliability_model": str(weighted_model),
            "reliability_filtered_model": str(weighted_filt_model),
        },
    }
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    plain_acc = next((r["accuracy"] for r in method_rows if r["method"] == "adaptive_bt_pairwise"), 0.0)
    rel_acc = next((r["accuracy"] for r in method_rows if r["method"] == "adaptive_bt_pairwise_reliability"), 0.0)
    relf_acc = next((r["accuracy"] for r in method_rows if r["method"] == "adaptive_bt_pairwise_reliability_filtered"), 0.0)
    interp = [
        f"# Reliability-weighted BT interpretation ({run_id})",
        "",
        f"- Plain BT accuracy: {plain_acc:.4f}",
        f"- Reliability-weighted BT accuracy: {rel_acc:.4f}",
        f"- Reliability-weighted + filtered BT accuracy: {relf_acc:.4f}",
        f"- Confidence weighting improves over plain BT: {'yes' if rel_acc > plain_acc else 'no/mixed'}.",
        f"- Filtering uncertain pairs helps: {'yes' if relf_acc > rel_acc else 'no/mixed'}.",
        f"- Oracle-gap improvement beyond plain BT: {'yes' if oracle_rows[0]['reliability_bt_gap'] < oracle_rows[0]['plain_bt_gap'] else 'no/mixed'}.",
        (
            "- Low-confidence pairs appear harmful to pairwise fitting: "
            f"{'yes/mixed evidence' if float(weighted.get('test_pair_accuracy_high_conf_ge_0.5', 0.0)) > float(weighted.get('test_pair_accuracy_low_conf_lt_0.2', 0.0)) else 'no clear evidence'}."
        ),
        (
            "- Filtered training data volume: "
            f"{int(filtered.get('n_train_used', 0))}/{int(filtered.get('n_train_total', 0))} pairs used "
            f"(dropped_low_conf={int(filtered.get('n_train_dropped_low_conf', 0))}, "
            f"dropped_uncertain={int(filtered.get('n_train_dropped_uncertain', 0))})."
        ),
        f"- Real-model-backed status: {'enabled' if args.use_openai_api else 'simulator-backed only in this run'}.",
        "- Reliability signals are weak confidence heuristics, not ground-truth label quality.",
        "- Inference remains scalar: one score per branch, argmax; no pairwise inference matrix.",
    ]
    (run_dir / "interpretation.md").write_text("\n".join(interp) + "\n", encoding="utf-8")

    print(json.dumps({"run_dir": str(run_dir), "plain_bt": plain_acc, "rel_bt": rel_acc, "relf_bt": relf_acc}, indent=2))


if __name__ == "__main__":
    main()
