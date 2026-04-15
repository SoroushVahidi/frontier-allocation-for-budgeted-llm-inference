#!/usr/bin/env python3
"""Build stop-vs-act dataset for fixed-budget branch allocation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.stop_vs_act_controller import STOP_VS_ACT_FEATURE_NAMES, StopVsActLabelConfig, build_stop_vs_act_dataset


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build stop-vs-act dataset")
    parser.add_argument("--output-dir", default="outputs/stop_vs_act_controller")
    parser.add_argument("--episodes", type=int, default=1200)
    parser.add_argument("--budget", type=int, default=14)
    parser.add_argument("--seed", type=int, default=31)
    parser.add_argument("--train-ratio", type=float, default=0.8)
    parser.add_argument("--n-init-branches", type=int, default=5)
    parser.add_argument("--max-depth", type=int, default=7)
    parser.add_argument("--finish-prob-base", type=float, default=0.16)
    parser.add_argument("--answer-noise", type=float, default=0.12)
    parser.add_argument("--gain-margin", type=float, default=0.015)
    parser.add_argument("--uncertainty-band", type=float, default=0.03)
    parser.add_argument("--instability-std-threshold", type=float, default=0.045)
    parser.add_argument(
        "--instability-guard-band",
        type=float,
        default=None,
        help="If set, instability contributes to uncertainty only when |delta_mean| <= this band.",
    )
    parser.add_argument("--rollout-samples", type=int, default=6)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    label_cfg = StopVsActLabelConfig(
        gain_margin=args.gain_margin,
        uncertainty_band=args.uncertainty_band,
        instability_std_threshold=args.instability_std_threshold,
        instability_guard_band=args.instability_guard_band,
        rollout_samples=args.rollout_samples,
    )
    rows = build_stop_vs_act_dataset(
        episodes=args.episodes,
        budget=args.budget,
        seed=args.seed,
        train_ratio=args.train_ratio,
        n_init_branches=args.n_init_branches,
        max_depth=args.max_depth,
        finish_prob_base=args.finish_prob_base,
        answer_noise=args.answer_noise,
        label_cfg=label_cfg,
    )

    dataset_path = out_dir / "stop_vs_act_dataset.jsonl"
    with dataset_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")

    uncertain_count = sum(int(bool(r["is_uncertain"])) for r in rows)
    pos = sum(int(r["label_act"]) for r in rows)
    meta = {
        "rows": len(rows),
        "train_rows": sum(1 for r in rows if r["split"] == "train"),
        "test_rows": sum(1 for r in rows if r["split"] == "test"),
        "positive_rate": pos / max(1, len(rows)),
        "uncertain_rate": uncertain_count / max(1, len(rows)),
        "feature_names": STOP_VS_ACT_FEATURE_NAMES,
        "label_rule": {
            "target": "ACT(1) if estimated +1-action gain delta is larger than gain_margin; else STOP(0)",
            "delta_definition": "delta = E[utility_after_one_more_action_here - current_utility] - best_other_expected_next_gain",
            "utility": "0.72*score + 0.20*done_and_correct + 0.08*done_bonus",
            "rollout": f"bounded rollout with {args.rollout_samples} local samples",
            "gain_margin": args.gain_margin,
        },
        "uncertainty_rule": {
            "uncertain_if": (
                "abs(delta_mean) <= uncertainty_band OR "
                "((delta_std >= instability_std_threshold) AND (|delta_mean| <= instability_guard_band if provided else True))"
            ),
            "uncertainty_band": args.uncertainty_band,
            "instability_std_threshold": args.instability_std_threshold,
            "instability_guard_band": args.instability_guard_band,
            "weighting": "sample_weight reduced for uncertain examples (near-zero:0.35, unstable:0.50, both:0.20)",
        },
    }
    (out_dir / "dataset_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
