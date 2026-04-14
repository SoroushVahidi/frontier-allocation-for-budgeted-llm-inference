#!/usr/bin/env python3
"""Build auditable pairwise branch-preference dataset for BT training.

Each row compares branch A vs B from the same (episode_id, decision_id),
with deterministic tie handling and scalar-inference compatible supervision.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.branch_scorer_v3 import V7_FEATURE_NAMES


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _mean(xs: list[float]) -> float:
    return sum(xs) / max(1, len(xs))


def _std(xs: list[float]) -> float:
    if len(xs) <= 1:
        return 0.0
    m = _mean(xs)
    return (_mean([(x - m) ** 2 for x in xs])) ** 0.5


def _branch_recent_trend(feat: dict[str, float]) -> float:
    # Positive means estimated distance-to-terminal is shrinking over path window.
    start = float(feat.get("node_0_distance_to_terminal_est", 0.0))
    end = float(feat.get("node_3_distance_to_terminal_est", start))
    return max(-1.0, min(1.0, (start - end) / max(1.0, start)))


def _branch_value_stability(feat: dict[str, float]) -> float:
    vals = [float(feat.get(f"node_{i}_future_value_est", 0.0)) for i in range(4)]
    masks = [float(feat.get(f"node_{i}_mask", 0.0)) for i in range(4)]
    kept = [v for v, m in zip(vals, masks) if m > 0.5]
    if not kept:
        return 0.0
    return _clip01(1.0 - (_std(kept) / 0.25))


def _branch_delta_consistency(feat: dict[str, float]) -> float:
    deltas = [float(feat.get(f"edge_{i}_score_delta", 0.0)) for i in range(3)]
    pos = sum(1 for d in deltas if d > 0)
    neg = sum(1 for d in deltas if d < 0)
    return max(pos, neg) / 3.0


def _progress_signal(feat: dict[str, float]) -> float:
    return float(feat.get("node_3_future_value_est", 0.0)) - 0.15 * float(feat.get("node_3_distance_to_terminal_est", 0.0))


def _pair_reliability(
    a_feat: dict[str, float],
    b_feat: dict[str, float],
    utility_diff: float,
    margin_scale: float,
    uncertain_margin: float,
) -> dict[str, float]:
    margin = abs(utility_diff)
    margin_conf = _clip01(margin / max(1e-9, margin_scale))
    progress_agreement = 1.0 if (_progress_signal(a_feat) - _progress_signal(b_feat)) * utility_diff > 0 else 0.0
    trend_a = _branch_recent_trend(a_feat)
    trend_b = _branch_recent_trend(b_feat)
    trend_clarity = _clip01(abs(trend_a - trend_b))
    stability = _clip01(0.5 * (_branch_value_stability(a_feat) + _branch_value_stability(b_feat)))
    delta_consistency = _clip01(0.5 * (_branch_delta_consistency(a_feat) + _branch_delta_consistency(b_feat)))
    rem_budget = float(a_feat.get("remaining_budget", 0.0))
    mean_distance = 0.5 * (
        float(a_feat.get("node_3_distance_to_terminal_est", 1.0)) + float(b_feat.get("node_3_distance_to_terminal_est", 1.0))
    )
    budget_fit = _clip01(rem_budget / max(1.0, mean_distance))
    pair_conf = (
        0.35 * margin_conf
        + 0.15 * progress_agreement
        + 0.15 * trend_clarity
        + 0.15 * stability
        + 0.10 * delta_consistency
        + 0.10 * budget_fit
    )
    # Conservative uncertain flag: either tiny margin or low-to-mid aggregate confidence.
    tie_or_uncertain = 1 if (margin <= uncertain_margin or pair_conf < 0.72) else 0
    return {
        "preference_margin": margin,
        "pair_confidence": _clip01(pair_conf),
        "tie_or_uncertain": tie_or_uncertain,
        "rel_margin_confidence": margin_conf,
        "rel_progress_agreement": progress_agreement,
        "rel_distance_trend_clarity": trend_clarity,
        "rel_value_stability": stability,
        "rel_delta_consistency": delta_consistency,
        "rel_budget_fit": budget_fit,
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build pairwise BT branch scorer dataset")
    p.add_argument("--ranking-dataset", default="outputs/branch_scorer_v3/branch_scorer_v3_dataset.jsonl")
    p.add_argument("--output", default="outputs/branch_scorer_v3/bt_pairwise_dataset.jsonl")
    p.add_argument("--tie-epsilon", type=float, default=1e-9)
    p.add_argument("--margin-scale", type=float, default=0.20, help="Scale for margin->confidence normalization.")
    p.add_argument("--uncertain-margin", type=float, default=0.03)
    return p.parse_args()


def _load_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    return rows


def main() -> None:
    args = parse_args()
    rows = _load_rows(Path(args.ranking_dataset))

    grouped: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault((int(row["episode_id"]), int(row["decision_id"])), []).append(row)

    output_rows: list[dict[str, Any]] = []
    ties = 0
    for (episode_id, decision_id), group in grouped.items():
        if len(group) < 2:
            continue
        remaining_budget = int(group[0].get("remaining_budget", 0))
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a = group[i]
                b = group[j]
                ua = float(a["v6_target_pairwise_groupwise"])
                ub = float(b["v6_target_pairwise_groupwise"])
                diff = ua - ub
                tie = abs(diff) <= args.tie_epsilon
                if tie:
                    ties += 1
                    # Deterministic tie rule for reproducibility.
                    a_preferred = str(a["branch_id"]) <= str(b["branch_id"])
                else:
                    a_preferred = diff > 0.0
                reliability = _pair_reliability(
                    a_feat={k: float(a[k]) for k in V7_FEATURE_NAMES},
                    b_feat={k: float(b[k]) for k in V7_FEATURE_NAMES},
                    utility_diff=diff,
                    margin_scale=float(args.margin_scale),
                    uncertain_margin=float(args.uncertain_margin),
                )

                output_rows.append(
                    {
                        "episode_id": episode_id,
                        "decision_id": decision_id,
                        "split": a["split"],
                        "remaining_budget": remaining_budget,
                        "branch_a_id": a["branch_id"],
                        "branch_b_id": b["branch_id"],
                        "a_preferred": int(a_preferred),
                        "preference_label": int(a_preferred),
                        "tie": int(tie),
                        "label_source": "v6_target_pairwise_groupwise",
                        "utility_a": ua,
                        "utility_b": ub,
                        "features_a": {k: float(a[k]) for k in V7_FEATURE_NAMES},
                        "features_b": {k: float(b[k]) for k in V7_FEATURE_NAMES},
                        **reliability,
                    }
                )

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for row in output_rows:
            f.write(json.dumps(row) + "\n")

    meta = {
        "ranking_dataset": str(Path(args.ranking_dataset)),
        "pair_rows": len(output_rows),
        "tie_rows": ties,
        "feature_family": "v7_ordered_history",
        "bt_label": "a_preferred uses deterministic tie-break by branch_id when utilities tie",
        "confidence_signals": [
            "preference_margin",
            "pair_confidence",
            "tie_or_uncertain",
            "rel_margin_confidence",
            "rel_progress_agreement",
            "rel_distance_trend_clarity",
            "rel_value_stability",
            "rel_delta_consistency",
            "rel_budget_fit",
        ],
    }
    out_path.with_name(out_path.stem + "_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
