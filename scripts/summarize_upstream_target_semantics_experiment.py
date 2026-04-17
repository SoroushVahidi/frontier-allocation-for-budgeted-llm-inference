#!/usr/bin/env python3
"""Summarize upstream target-semantics strict-validation outputs by regime.

Produces machine-readable aggregate/per-seed/delta summaries and weight diagnostics.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _mean(xs: list[float]) -> float:
    return float(sum(xs) / len(xs)) if xs else 0.0


def _pct(vals: list[float], q: float) -> float:
    if not vals:
        return 0.0
    vv = sorted(vals)
    idx = min(len(vv) - 1, max(0, int(round(q * (len(vv) - 1)))))
    return float(vv[idx])


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _weight_diagnostics(regime_dir: Path) -> dict[str, Any]:
    pair_path = regime_dir / "pairwise_labels.jsonl"
    if not pair_path.exists():
        return {"status": "missing_pairwise_labels"}
    rows = _read_jsonl(pair_path)
    weights = [float(r.get("opportunity_intensity_weight_final", r.get("opportunity_intensity_weight", 1.0))) for r in rows]
    near = [float(r.get("opportunity_intensity_weight_final", r.get("opportunity_intensity_weight", 1.0))) for r in rows if bool(r.get("near_tie_flag", False))]
    not_near = [float(r.get("opportunity_intensity_weight_final", r.get("opportunity_intensity_weight", 1.0))) for r in rows if (not bool(r.get("near_tie_flag", False)))]
    adj = [float(r.get("opportunity_intensity_weight_final", r.get("opportunity_intensity_weight", 1.0))) for r in rows if str(r.get("pair_type", "")) == "adjacent_rank"]
    non_adj = [float(r.get("opportunity_intensity_weight_final", r.get("opportunity_intensity_weight", 1.0))) for r in rows if str(r.get("pair_type", "")) != "adjacent_rank"]
    return {
        "status": "ok",
        "rows": len(rows),
        "mean_weight": _mean(weights),
        "mean_weight_near_tie": _mean(near),
        "mean_weight_non_near_tie": _mean(not_near),
        "mean_weight_adjacent": _mean(adj),
        "mean_weight_non_adjacent": _mean(non_adj),
        "weight_percentiles": {
            "p05": _pct(weights, 0.05),
            "p25": _pct(weights, 0.25),
            "p50": _pct(weights, 0.50),
            "p75": _pct(weights, 0.75),
            "p95": _pct(weights, 0.95),
        },
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Summarize upstream target-semantics strict-validation run")
    p.add_argument("--strict-results", required=True, help="Path to strict_validation_results.json")
    p.add_argument("--targets-root", required=True)
    p.add_argument("--baseline-regime", default="all_pairs_approx")
    p.add_argument("--output-dir", required=True)
    p.add_argument("--run-id", required=True)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    strict = _load_json(Path(args.strict_results))
    rows = strict.get("rows", [])
    by_regime: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        by_regime.setdefault(str(r.get("regime", "unknown")), []).append(r)

    per_seed_summary: list[dict[str, Any]] = []
    aggregate_summary: dict[str, Any] = {}
    for regime, items in sorted(by_regime.items()):
        for item in items:
            full = item.get("variant_metrics", {}).get("full_method", {})
            pairwise = item.get("pairwise_binary_baseline", {})
            per_seed_summary.append(
                {
                    "regime": regime,
                    "seed": int(item.get("seed", 0)),
                    "accepted_pair_accuracy": float(full.get("accepted_pair_accuracy", 0.0)),
                    "coverage": float(full.get("coverage", 0.0)),
                    "defer_rate": float(full.get("defer_rate", 0.0)),
                    "near_tie_accepted_pair_accuracy": float(full.get("near_tie_accepted_pair_accuracy", 0.0)),
                    "adjacent_rank_accepted_pair_accuracy": float(full.get("adjacent_rank_accepted_pair_accuracy", 0.0)),
                    "accepted_mean_true_value_gap": float(full.get("accepted_mean_true_value_gap", 0.0)),
                    "deferred_mean_true_value_gap": float(full.get("deferred_mean_true_value_gap", 0.0)),
                    "pairwise_binary_accuracy": float(pairwise.get("accepted_pair_accuracy", 0.0)),
                    "pairwise_binary_near_tie_accuracy": float(pairwise.get("near_tie_accepted_pair_accuracy", 0.0)),
                    "pairwise_binary_adjacent_accuracy": float(pairwise.get("adjacent_rank_accepted_pair_accuracy", 0.0)),
                }
            )
        aggregate_summary[regime] = {
            "accepted_pair_accuracy": _mean([float(x.get("variant_metrics", {}).get("full_method", {}).get("accepted_pair_accuracy", 0.0)) for x in items]),
            "coverage": _mean([float(x.get("variant_metrics", {}).get("full_method", {}).get("coverage", 0.0)) for x in items]),
            "defer_rate": _mean([float(x.get("variant_metrics", {}).get("full_method", {}).get("defer_rate", 0.0)) for x in items]),
            "near_tie_accepted_pair_accuracy": _mean([float(x.get("variant_metrics", {}).get("full_method", {}).get("near_tie_accepted_pair_accuracy", 0.0)) for x in items]),
            "adjacent_rank_accepted_pair_accuracy": _mean([float(x.get("variant_metrics", {}).get("full_method", {}).get("adjacent_rank_accepted_pair_accuracy", 0.0)) for x in items]),
            "accepted_mean_true_value_gap": _mean([float(x.get("variant_metrics", {}).get("full_method", {}).get("accepted_mean_true_value_gap", 0.0)) for x in items]),
            "deferred_mean_true_value_gap": _mean([float(x.get("variant_metrics", {}).get("full_method", {}).get("deferred_mean_true_value_gap", 0.0)) for x in items]),
            "pairwise_binary_accuracy": _mean([float(x.get("pairwise_binary_baseline", {}).get("accepted_pair_accuracy", 0.0)) for x in items]),
            "pairwise_binary_near_tie_accuracy": _mean([float(x.get("pairwise_binary_baseline", {}).get("near_tie_accepted_pair_accuracy", 0.0)) for x in items]),
            "pairwise_binary_adjacent_accuracy": _mean([float(x.get("pairwise_binary_baseline", {}).get("adjacent_rank_accepted_pair_accuracy", 0.0)) for x in items]),
        }

    baseline = aggregate_summary.get(str(args.baseline_regime), {})
    deltas_vs_baseline: dict[str, Any] = {}
    for regime, metrics in aggregate_summary.items():
        deltas_vs_baseline[regime] = {
            f"delta_{k}": float(metrics.get(k, 0.0)) - float(baseline.get(k, 0.0)) for k in [
                "accepted_pair_accuracy",
                "coverage",
                "defer_rate",
                "near_tie_accepted_pair_accuracy",
                "adjacent_rank_accepted_pair_accuracy",
                "accepted_mean_true_value_gap",
                "deferred_mean_true_value_gap",
                "pairwise_binary_accuracy",
                "pairwise_binary_near_tie_accuracy",
                "pairwise_binary_adjacent_accuracy",
            ]
        }

    weight_diag: dict[str, Any] = {}
    targets_root = Path(args.targets_root)
    for regime in sorted(by_regime.keys()):
        weight_diag[regime] = _weight_diagnostics(targets_root / f"regime_{regime}")

    payload = {
        "run_id": args.run_id,
        "strict_results": str(args.strict_results),
        "targets_root": str(args.targets_root),
        "baseline_regime": args.baseline_regime,
        "aggregate_summary_by_regime": aggregate_summary,
        "deltas_vs_baseline": deltas_vs_baseline,
        "per_seed_summary": per_seed_summary,
        "weight_diagnostics_by_regime": weight_diag,
    }

    (out_dir / "upstream_target_semantics_summary.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (out_dir / "upstream_target_semantics_per_seed_summary.json").write_text(json.dumps(per_seed_summary, indent=2) + "\n", encoding="utf-8")
    (out_dir / "upstream_target_semantics_aggregate_comparison.json").write_text(json.dumps({
        "aggregate_summary_by_regime": aggregate_summary,
        "deltas_vs_baseline": deltas_vs_baseline,
    }, indent=2) + "\n", encoding="utf-8")
    (out_dir / "upstream_target_semantics_weight_diagnostics.json").write_text(json.dumps(weight_diag, indent=2) + "\n", encoding="utf-8")
    (out_dir / "upstream_target_semantics_manifest.json").write_text(json.dumps({
        "run_id": args.run_id,
        "artifacts": [
            "upstream_target_semantics_summary.json",
            "upstream_target_semantics_per_seed_summary.json",
            "upstream_target_semantics_aggregate_comparison.json",
            "upstream_target_semantics_weight_diagnostics.json",
            "upstream_target_semantics_manifest.json",
        ],
    }, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({"output_dir": str(out_dir), "regimes": sorted(by_regime.keys())}, indent=2))


if __name__ == "__main__":
    main()
