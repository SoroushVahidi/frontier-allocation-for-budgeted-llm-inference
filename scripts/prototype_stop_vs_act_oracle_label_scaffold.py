#!/usr/bin/env python3
"""Tiny dry-run scaffold for future oracle-distilled stop-vs-act label generation.

This script does NOT run heavy oracle rollouts. It only:
1) builds a tiny lightweight stop-vs-act dataset,
2) emits schema-conformant rows with placeholder oracle fields,
3) writes a manifest and schema note to support the future heavy phase.
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

from experiments.stop_vs_act_controller import STOP_VS_ACT_FEATURE_NAMES, StopVsActLabelConfig, build_stop_vs_act_dataset


ORACLE_PLACEHOLDER_SCHEMA = {
    "row_id": "str",
    "split": "str(train|test)",
    "state": {
        "episode_id": "int",
        "decision_id": "int",
        "branch_id": "str",
    },
    "features": "dict[str,float] (stop-vs-act feature family)",
    "lightweight_proxy": {
        "label_act": "int",
        "delta_mean": "float",
        "delta_std": "float",
        "delta_sign_flip_rate": "float",
    },
    "oracle_teacher": {
        "status": "placeholder|available",
        "teacher_type": "str",
        "q_act": "float|null",
        "q_stop": "float|null",
        "oracle_action_gap": "float|null",
        "oracle_label_act": "int|null",
        "oracle_uncertainty": "float|null",
    },
    "provenance": {
        "label_source": "lightweight_proxy_scaffold",
        "anchor_target_mode": "str",
        "intended_heavy_plan": "str",
    },
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Prototype scaffold for oracle stop-vs-act labels")
    p.add_argument("--output-dir", default="outputs/stop_vs_act_oracle_label_scaffold")
    p.add_argument("--plan-path", default="configs/stop_vs_act_oracle_label_plan_v1.json")
    p.add_argument("--episodes", type=int, default=12)
    p.add_argument("--budget", type=int, default=8)
    p.add_argument("--seed", type=int, default=101)
    p.add_argument("--train-ratio", type=float, default=0.75)
    p.add_argument("--n-init-branches", type=int, default=5)
    p.add_argument("--max-depth", type=int, default=7)
    p.add_argument("--finish-prob-base", type=float, default=0.16)
    p.add_argument("--answer-noise", type=float, default=0.12)
    p.add_argument("--rollout-samples", type=int, default=6)
    p.add_argument("--max-rows", type=int, default=120)
    return p.parse_args()


def _build_tiny_proxy_rows(args: argparse.Namespace) -> list[dict[str, Any]]:
    cfg = StopVsActLabelConfig(
        target_mode="proxy_best_other_gain",
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
        label_cfg=cfg,
    )
    return rows[: max(1, int(args.max_rows))]


def _to_scaffold_row(row: dict[str, Any], *, plan_name: str) -> dict[str, Any]:
    features = {name: float(row[name]) for name in STOP_VS_ACT_FEATURE_NAMES}
    q_act = None
    q_stop = None
    oracle_gap = None

    return {
        "row_id": f"ep{int(row['episode_id'])}_d{int(row['decision_id'])}_{row['branch_id']}",
        "split": str(row["split"]),
        "state": {
            "episode_id": int(row["episode_id"]),
            "decision_id": int(row["decision_id"]),
            "branch_id": str(row["branch_id"]),
        },
        "features": features,
        "lightweight_proxy": {
            "label_act": int(row["label_act"]),
            "delta_mean": float(row["delta_mean"]),
            "delta_std": float(row["delta_std"]),
            "delta_sign_flip_rate": float(row.get("delta_sign_flip_rate", 0.0)),
        },
        "oracle_teacher": {
            "status": "placeholder",
            "teacher_type": "offline_policy_coupled_oracle_rollout",
            "q_act": q_act,
            "q_stop": q_stop,
            "oracle_action_gap": oracle_gap,
            "oracle_label_act": None,
            "oracle_uncertainty": None,
        },
        "provenance": {
            "label_source": "lightweight_proxy_scaffold",
            "anchor_target_mode": "proxy_best_other_gain",
            "intended_heavy_plan": plan_name,
        },
    }


def main() -> None:
    args = parse_args()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    plan_path = Path(args.plan_path)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))

    proxy_rows = _build_tiny_proxy_rows(args)
    scaffold_rows = [_to_scaffold_row(r, plan_name=str(plan.get("plan_name", "unknown_plan"))) for r in proxy_rows]

    jsonl_path = out_dir / "oracle_label_scaffold.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as f:
        for row in scaffold_rows:
            f.write(json.dumps(row) + "\n")

    manifest = {
        "plan_name": plan.get("plan_name"),
        "prototype_only": True,
        "heavy_oracle_generated": False,
        "rows": len(scaffold_rows),
        "feature_names": STOP_VS_ACT_FEATURE_NAMES,
        "note": "Rows include lightweight proxy labels and placeholder oracle fields only.",
        "inputs": {
            "episodes": args.episodes,
            "budget": args.budget,
            "seed": args.seed,
            "rollout_samples": args.rollout_samples,
            "max_rows": args.max_rows,
        },
    }

    (out_dir / "oracle_label_scaffold_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (out_dir / "oracle_label_scaffold_schema.json").write_text(json.dumps(ORACLE_PLACEHOLDER_SCHEMA, indent=2), encoding="utf-8")

    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
