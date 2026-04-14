#!/usr/bin/env python3
"""Lightweight diagnostic audit for BT pairwise branch-comparison limits.

No heavy training; only cheap dataset/statistical diagnostics.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import subprocess
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run lightweight pairwise diagnostic audit (new-paper track)")
    p.add_argument("--output-root", default="outputs/new_paper/pairwise_diagnostic_audit")
    p.add_argument("--seed", type=int, default=23)
    p.add_argument("--budget", type=int, default=8)
    p.add_argument("--episodes", type=int, default=220, help="Small/cheap internal ranking dataset size.")
    p.add_argument("--ranking-dataset", default="")
    p.add_argument("--pairwise-dataset", default="")
    p.add_argument("--external-run-dir", default="")
    return p.parse_args()


def _mean(xs: list[float]) -> float:
    return sum(xs) / max(1, len(xs))


def _std(xs: list[float]) -> float:
    if len(xs) <= 1:
        return 0.0
    m = _mean(xs)
    return math.sqrt(_mean([(x - m) ** 2 for x in xs]))


def _quantile(xs: list[float], q: float) -> float:
    if not xs:
        return 0.0
    ys = sorted(xs)
    idx = int(round((len(ys) - 1) * max(0.0, min(1.0, q))))
    return ys[idx]


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def _latest_external_run() -> Path | None:
    root = REPO_ROOT / "outputs/new_paper/external_warmstart_branch_scorer"
    if not root.exists():
        return None
    runs = sorted([p for p in root.iterdir() if p.is_dir()])
    return runs[-1] if runs else None


def _build_small_pairwise(run_dir: Path, episodes: int, budget: int, seed: int) -> tuple[Path, Path]:
    ranking = run_dir / "branch_scorer_v3_dataset.jsonl"
    pairwise = run_dir / "pairwise_dataset.jsonl"
    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/build_v3_ranking_dataset.py"),
            "--output-dir",
            str(run_dir),
            "--episodes",
            str(episodes),
            "--budget",
            str(budget),
            "--seed",
            str(seed),
        ],
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/build_bt_pairwise_branch_dataset.py"),
            "--ranking-dataset",
            str(ranking),
            "--output",
            str(pairwise),
        ],
        check=True,
    )
    return ranking, pairwise


def main() -> None:
    args = parse_args()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = REPO_ROOT / args.output_root / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    ranking_path = Path(args.ranking_dataset) if args.ranking_dataset else Path("")
    pairwise_path = Path(args.pairwise_dataset) if args.pairwise_dataset else Path("")
    if (not ranking_path.exists()) or (not pairwise_path.exists()) or (not ranking_path.is_file()) or (not pairwise_path.is_file()):
        ranking_path, pairwise_path = _build_small_pairwise(out_dir, args.episodes, args.budget, args.seed)

    ranking_rows = _load_jsonl(ranking_path)
    pair_rows = _load_jsonl(pairwise_path)

    train_pairs = [r for r in pair_rows if r.get("split") == "train"]
    test_pairs = [r for r in pair_rows if r.get("split") == "test"]

    confs = [float(r.get("pair_confidence", 0.0)) for r in pair_rows]
    margins = [abs(float(r.get("utility_a", 0.0)) - float(r.get("utility_b", 0.0))) for r in pair_rows]
    ties = [int(r.get("tie", 0)) for r in pair_rows]
    uncertains = [int(r.get("tie_or_uncertain", 0)) for r in pair_rows]

    a_wins = sum(int(r.get("a_preferred", 0)) for r in pair_rows)
    label_balance = a_wins / max(1, len(pair_rows))

    conf_bins = [(0.0, 0.2), (0.2, 0.5), (0.5, 0.72), (0.72, 1.01)]
    bin_rows: list[dict[str, Any]] = []
    for lo, hi in conf_bins:
        subset = [r for r in pair_rows if lo <= float(r.get("pair_confidence", 0.0)) < hi]
        if not subset:
            bin_rows.append({"diagnostic": f"conf_bin_{lo}_{hi}", "value": 0.0, "count": 0})
            continue
        proxy_agreement_bin = _mean(
            [
                float(
                    (
                        float(r.get("features_a", {}).get("node_3_score", 0.0))
                        - float(r.get("features_b", {}).get("node_3_score", 0.0))
                        >= 0
                    )
                    == bool(int(r.get("a_preferred", 0)))
                )
                for r in subset
            ]
        )
        bin_rows.append(
            {
                "diagnostic": f"node3_proxy_agreement_conf_bin_{lo}_{hi}",
                "value": proxy_agreement_bin,
                "count": len(subset),
            }
        )

    feature_keys = sorted(
        {k for row in ranking_rows for k, v in row.items() if isinstance(v, (int, float)) and k not in {"episode_id", "decision_id"}}
    )
    low_var_features: list[tuple[str, float]] = []
    for k in feature_keys:
        vals = [float(r.get(k, 0.0)) for r in ranking_rows]
        low_var_features.append((k, _std(vals)))
    low_var_features = sorted(low_var_features, key=lambda x: x[1])[:10]

    proxy_agreement = _mean(
        [
            float(
                (
                    float(r.get("features_a", {}).get("node_3_score", 0.0))
                    - float(r.get("features_b", {}).get("node_3_score", 0.0))
                    >= 0
                )
                == bool(int(r.get("a_preferred", 0)))
            )
            for r in pair_rows
        ]
    )
    progress_agreement_mean = _mean([float(r.get("rel_progress_agreement", 0.0)) for r in pair_rows])

    external_dir = Path(args.external_run_dir) if args.external_run_dir else (_latest_external_run() or Path(""))
    external_gap = None
    if external_dir and external_dir.exists():
        holdout = external_dir / "holdout_metrics.csv"
        if holdout.exists():
            lines = holdout.read_text(encoding="utf-8").strip().splitlines()
            if len(lines) >= 4:
                header = lines[0].split(",")
                idx_model = header.index("model")
                idx_acc = header.index("holdout_accuracy")
                vals = {}
                for ln in lines[1:]:
                    parts = ln.split(",")
                    vals[parts[idx_model]] = float(parts[idx_acc])
                if "internal_only" in vals and "external_warmstart_only" in vals:
                    external_gap = vals["internal_only"] - vals["external_warmstart_only"]

    diag_rows = [
        {"diagnostic": "n_ranking_rows", "value": len(ranking_rows), "count": len(ranking_rows)},
        {"diagnostic": "n_pair_rows", "value": len(pair_rows), "count": len(pair_rows)},
        {"diagnostic": "label_balance_a_preferred_rate", "value": label_balance, "count": len(pair_rows)},
        {"diagnostic": "tie_rate", "value": _mean([float(x) for x in ties]), "count": len(pair_rows)},
        {"diagnostic": "uncertain_rate", "value": _mean([float(x) for x in uncertains]), "count": len(pair_rows)},
        {"diagnostic": "pair_conf_mean", "value": _mean(confs), "count": len(confs)},
        {"diagnostic": "pair_conf_std", "value": _std(confs), "count": len(confs)},
        {"diagnostic": "pair_conf_p10", "value": _quantile(confs, 0.10), "count": len(confs)},
        {"diagnostic": "pair_conf_p50", "value": _quantile(confs, 0.50), "count": len(confs)},
        {"diagnostic": "pair_conf_p90", "value": _quantile(confs, 0.90), "count": len(confs)},
        {"diagnostic": "margin_mean", "value": _mean(margins), "count": len(margins)},
        {"diagnostic": "margin_p50", "value": _quantile(margins, 0.50), "count": len(margins)},
        {"diagnostic": "node3_score_proxy_agreement", "value": proxy_agreement, "count": len(pair_rows)},
        {"diagnostic": "rel_progress_agreement_mean", "value": progress_agreement_mean, "count": len(pair_rows)},
        {"diagnostic": "n_train_pairs", "value": len(train_pairs), "count": len(train_pairs)},
        {"diagnostic": "n_test_pairs", "value": len(test_pairs), "count": len(test_pairs)},
    ]
    if external_gap is not None:
        diag_rows.append(
            {
                "diagnostic": "external_minus_internal_holdout_gap_abs",
                "value": external_gap,
                "count": 1,
            }
        )
    diag_rows.extend(bin_rows)

    _write_csv(out_dir / "lightweight_diagnostics.csv", diag_rows)

    weakest = "label quality / uncertainty concentration"
    if _mean([float(x) for x in uncertains]) > 0.45:
        weakest = "label quality / uncertainty concentration"
    elif _std(confs) < 0.08:
        weakest = "confidence weighting low dynamic range"
    elif proxy_agreement > 0.85:
        weakest = "feature bottleneck (pair labels over-correlated with node_3_score proxy)"

    low_var_text = ", ".join([f"{k}({v:.4f})" for k, v in low_var_features[:5]])
    md = [
        f"# Pairwise diagnostic audit ({run_id})",
        "",
        "## Scope",
        "- Lightweight diagnostic only (no heavy training / no API-backed evaluation).",
        f"- Ranking rows: {len(ranking_rows)}, pair rows: {len(pair_rows)}.",
        "",
        "## Key findings",
        f"- Biggest current weakness: **{weakest}**.",
        f"- Uncertain pair rate: **{_mean([float(x) for x in uncertains]):.3f}** (ties+low-confidence flags).",
        f"- Pair-confidence spread: mean={_mean(confs):.3f}, std={_std(confs):.3f}, p10/p50/p90={_quantile(confs,0.1):.3f}/{_quantile(confs,0.5):.3f}/{_quantile(confs,0.9):.3f}.",
        f"- Label balance (`a_preferred=1`): {label_balance:.3f}.",
        f"- Crude single-proxy agreement (`node_3_score` sign vs pair label): {proxy_agreement:.3f}.",
        f"- Mean reliability component `rel_progress_agreement`: {progress_agreement_mean:.3f}.",
        f"- Lowest-variance ranking features (possible collapse): {low_var_text}.",
        "",
        "## Answers to required questions",
        f"1) Single biggest weakness: **{weakest}**.",
        "2) Main problem category: **labels + supervision mismatch first**, then confidence weighting and feature bottlenecks.",
        "3) Best next lightweight step: recalibrate pair labels by dropping/soft-targeting uncertain pairs (`tie_or_uncertain==1`) and re-audit confidence spread before any larger model changes.",
        "4) Avoid next: heavy external multitask training / large API evaluations until label quality diagnostics improve.",
        "",
        "## Notes",
        "- External warm-start path remains a partial-match signal and does not replace project-specific pair labels.",
    ]
    (out_dir / "pairwise_diagnostic_summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    payload = {
        "run_id": run_id,
        "ranking_dataset": str(ranking_path),
        "pairwise_dataset": str(pairwise_path),
        "biggest_weakness": weakest,
        "main_problem_category": "labels_and_domain_mismatch",
        "next_lightweight_step": "soft-target/drop uncertain pairs and recalibrate confidence bins",
        "avoid_next": "heavy training and large API-backed comparisons before label cleanup",
        "key_metrics": {row["diagnostic"]: row["value"] for row in diag_rows},
        "lowest_variance_features": [{"feature": k, "std": v} for k, v in low_var_features[:10]],
        "external_reference_run": str(external_dir) if external_dir and external_dir.exists() else None,
    }
    (out_dir / "pairwise_diagnostic_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(json.dumps({"run_dir": str(out_dir), "biggest_weakness": weakest}, indent=2))


if __name__ == "__main__":
    main()
