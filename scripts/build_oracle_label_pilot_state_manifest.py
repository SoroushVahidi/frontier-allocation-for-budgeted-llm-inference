#!/usr/bin/env python3
"""Build deterministic stratified pilot-state manifest for oracle-label generation.

This script extracts candidate stop-vs-act states from the existing default pipeline,
then performs deterministic dedupe + stratified selection. It does NOT compute oracle labels.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.stop_vs_act_controller import STOP_VS_ACT_FEATURE_NAMES, StopVsActLabelConfig, build_stop_vs_act_dataset


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _stable_hash(value: str) -> int:
    dig = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return int(dig[:16], 16)


def _is_finite_number(x: Any) -> bool:
    if not isinstance(x, (int, float)) or isinstance(x, bool):
        return False
    v = float(x)
    return math.isfinite(v)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build oracle-label pilot state manifest")
    p.add_argument("--selection-config", default="configs/stop_vs_act_oracle_pilot_state_selection_v1.json")
    p.add_argument("--output-dir", default="outputs/stop_vs_act_oracle_pilot_state_manifest")
    p.add_argument("--max-candidate-rows", type=int, default=0, help="Optional cap for debugging (0 means no cap)")
    return p.parse_args()


def _ambiguity_bucket(abs_gap: float, low_cut: float, high_cut: float) -> str:
    if abs_gap <= low_cut:
        return "high"
    if abs_gap <= high_cut:
        return "medium"
    return "low"


def _allocate_even(total: int, n_bins: int) -> list[int]:
    if n_bins <= 0:
        return []
    base = total // n_bins
    rem = total % n_bins
    return [base + (1 if i < rem else 0) for i in range(n_bins)]


def main() -> None:
    args = _parse_args()
    selection_cfg = _load_json(Path(args.selection_config))
    pilot_cfg = _load_json(Path(selection_cfg["pilot_config_path"]))

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    src_cfg = selection_cfg["source_pipeline"]
    cand_cfg = selection_cfg["candidate_generation"]
    sel_cfg = selection_cfg["selection"]
    exc_cfg = selection_cfg["exclusions"]

    seeds = [int(s) for s in pilot_cfg["pilot_grid"]["seeds"]]
    budgets = [int(b) for b in pilot_cfg["pilot_grid"]["budgets"]]
    episodes = int(cand_cfg["episodes_per_seed_budget"])
    include_splits = set(str(x) for x in cand_cfg.get("include_splits", ["train", "test"]))

    label_cfg = StopVsActLabelConfig(
        target_mode=str(src_cfg["target_mode"]),
        rollout_samples=int(src_cfg["rollout_samples"]),
    )

    candidates: list[dict[str, Any]] = []
    dropped = {"missing_core": 0, "nonfinite": 0, "split": 0}

    for budget in budgets:
        for seed in seeds:
            rows = build_stop_vs_act_dataset(
                episodes=episodes,
                budget=budget,
                seed=seed,
                train_ratio=float(src_cfg["train_ratio"]),
                n_init_branches=int(src_cfg["n_init_branches"]),
                max_depth=int(src_cfg["max_depth"]),
                finish_prob_base=float(src_cfg["finish_prob_base"]),
                answer_noise=float(src_cfg["answer_noise"]),
                label_cfg=label_cfg,
            )

            for r in rows:
                if str(r.get("split")) not in include_splits:
                    dropped["split"] += 1
                    continue

                core_fields = ["episode_id", "decision_id", "branch_id", "remaining_budget", "delta_mean", "delta_std"]
                if any(k not in r for k in core_fields):
                    dropped["missing_core"] += 1
                    continue

                numeric_fields = ["remaining_budget", "delta_mean", "delta_std", "gap_to_best_other_gain", "score_entropy"]
                if exc_cfg.get("exclude_nonfinite_numeric_fields", True):
                    if any(not _is_finite_number(r.get(k)) for k in numeric_fields):
                        dropped["nonfinite"] += 1
                        continue

                item = {
                    "source_seed": int(seed),
                    "budget": int(budget),
                    "episode_id": int(r["episode_id"]),
                    "decision_id": int(r["decision_id"]),
                    "current_branch_id": str(r["branch_id"]),
                    "split": str(r["split"]),
                    "remaining_budget": int(r["remaining_budget"]),
                    "is_uncertain": int(r.get("is_uncertain", 0)),
                    "label_act_proxy": int(r.get("label_act", 0)),
                    "delta_mean_proxy": float(r.get("delta_mean", 0.0)),
                    "delta_std_proxy": float(r.get("delta_std", 0.0)),
                    "delta_sign_flip_rate_proxy": float(r.get("delta_sign_flip_rate", 0.0)),
                    "abs_gap_to_best_other_gain": abs(float(r.get("gap_to_best_other_gain", 0.0))),
                    "score_entropy": float(r.get("score_entropy", 0.0)),
                    "features": {name: float(r[name]) for name in STOP_VS_ACT_FEATURE_NAMES if name in r},
                }
                candidates.append(item)

                if args.max_candidate_rows > 0 and len(candidates) >= int(args.max_candidate_rows):
                    break
            if args.max_candidate_rows > 0 and len(candidates) >= int(args.max_candidate_rows):
                break
        if args.max_candidate_rows > 0 and len(candidates) >= int(args.max_candidate_rows):
            break

    # Deterministic dedupe by strict key
    seen: set[tuple[int, int, int, int, str]] = set()
    deduped: list[dict[str, Any]] = []
    for c in sorted(candidates, key=lambda x: (x["source_seed"], x["budget"], x["episode_id"], x["decision_id"], x["current_branch_id"])):
        key = (c["source_seed"], c["budget"], c["episode_id"], c["decision_id"], c["current_branch_id"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(c)

    # Build ambiguity buckets per budget
    by_budget: dict[int, list[dict[str, Any]]] = {b: [] for b in budgets}
    for c in deduped:
        by_budget[int(c["budget"])].append(c)

    for b, rows_b in by_budget.items():
        gaps = sorted(float(r["abs_gap_to_best_other_gain"]) for r in rows_b)
        if not gaps:
            continue
        low_idx = int((len(gaps) - 1) * (1.0 / 3.0))
        high_idx = int((len(gaps) - 1) * (2.0 / 3.0))
        low_cut = gaps[low_idx]
        high_cut = gaps[high_idx]

        for r in rows_b:
            amb = _ambiguity_bucket(float(r["abs_gap_to_best_other_gain"]), low_cut, high_cut)
            unc = "uncertain" if int(r.get("is_uncertain", 0)) == 1 else "certain"
            r["ambiguity_bucket"] = amb
            r["uncertainty_bucket"] = unc
            r["stratum_tag"] = f"budget={b}|ambiguity={amb}|uncertainty={unc}"
            state_id = f"s{r['source_seed']}_b{r['budget']}_e{r['episode_id']}_d{r['decision_id']}_{r['current_branch_id']}"
            r["state_id"] = state_id

    # Selection quotas
    target_total = int(sel_cfg["target_states_total"])
    per_budget_targets = dict(zip(budgets, _allocate_even(target_total, len(budgets))))
    selection_seed = int(sel_cfg["selection_seed"])

    selected: list[dict[str, Any]] = []
    selection_debug: dict[str, Any] = {"budget_targets": per_budget_targets, "budget_realized": {}, "strata_realized": {}}

    for b in budgets:
        rows_b = list(by_budget.get(b, []))
        budget_target = int(per_budget_targets[b])

        strata_keys = sorted({r["stratum_tag"] for r in rows_b})
        per_stratum_target = dict(zip(strata_keys, _allocate_even(budget_target, len(strata_keys)))) if strata_keys else {}

        chosen_ids: set[str] = set()
        rows_by_stratum: dict[str, list[dict[str, Any]]] = {k: [] for k in strata_keys}
        for r in rows_b:
            rows_by_stratum[r["stratum_tag"]].append(r)

        # First pass: stratum quotas
        for sk in strata_keys:
            pool = rows_by_stratum[sk]
            pool_sorted = sorted(pool, key=lambda r: _stable_hash(f"{selection_seed}|{r['state_id']}"))
            quota = int(per_stratum_target.get(sk, 0))
            for idx, r in enumerate(pool_sorted[:quota]):
                rr = dict(r)
                rr["selection_name"] = str(selection_cfg["selection_name"])
                rr["selection_seed"] = selection_seed
                rr["selected_rank_in_stratum"] = idx
                rr["source_pipeline"] = str(src_cfg["builder"])
                selected.append(rr)
                chosen_ids.add(rr["state_id"])

        # Fill remainder within budget
        if len(chosen_ids) < budget_target:
            remain = budget_target - len(chosen_ids)
            leftovers = [r for r in rows_b if r["state_id"] not in chosen_ids]
            leftovers_sorted = sorted(leftovers, key=lambda r: _stable_hash(f"{selection_seed}|fill|{r['state_id']}"))
            for idx, r in enumerate(leftovers_sorted[:remain]):
                rr = dict(r)
                rr["selection_name"] = str(selection_cfg["selection_name"])
                rr["selection_seed"] = selection_seed
                rr["selected_rank_in_stratum"] = int(10_000 + idx)
                rr["source_pipeline"] = str(src_cfg["builder"])
                selected.append(rr)
                chosen_ids.add(rr["state_id"])

        selection_debug["budget_realized"][str(b)] = int(sum(1 for r in selected if int(r["budget"]) == b))

    # Global deterministic sort for manifest stability
    selected_sorted = sorted(selected, key=lambda r: (int(r["budget"]), r["stratum_tag"], int(r["source_seed"]), int(r["episode_id"]), int(r["decision_id"]), r["current_branch_id"]))

    # Write outputs
    manifest_path = out_dir / "pilot_state_manifest.jsonl"
    with manifest_path.open("w", encoding="utf-8") as f:
        for row in selected_sorted:
            f.write(json.dumps(row) + "\n")

    # Summaries
    stratum_counts: dict[str, int] = {}
    for r in selected_sorted:
        stratum_counts[r["stratum_tag"]] = stratum_counts.get(r["stratum_tag"], 0) + 1

    meta = {
        "selection_name": selection_cfg["selection_name"],
        "pilot_config": selection_cfg["pilot_config_path"],
        "source_builder": src_cfg["builder"],
        "target_mode": src_cfg["target_mode"],
        "candidate_rows": len(candidates),
        "deduped_rows": len(deduped),
        "selected_rows": len(selected_sorted),
        "target_states_total": target_total,
        "selection_seed": selection_seed,
        "budgets": budgets,
        "seeds": seeds,
        "dropped_counts": dropped,
        "selection_debug": selection_debug,
        "stratum_counts": stratum_counts,
        "note": "State manifest only. No oracle q_act/q_stop labels are generated here.",
    }
    (out_dir / "pilot_state_manifest_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    schema = {
        "state_id": "str",
        "selection_name": "str",
        "selection_seed": "int",
        "source_pipeline": "str",
        "source_seed": "int",
        "budget": "int",
        "episode_id": "int",
        "decision_id": "int",
        "current_branch_id": "str",
        "remaining_budget": "int",
        "split": "str",
        "ambiguity_bucket": "high|medium|low",
        "uncertainty_bucket": "uncertain|certain",
        "stratum_tag": "str",
        "label_act_proxy": "int",
        "delta_mean_proxy": "float",
        "delta_std_proxy": "float",
        "delta_sign_flip_rate_proxy": "float",
        "abs_gap_to_best_other_gain": "float",
        "score_entropy": "float",
        "features": "dict[str,float]",
        "selected_rank_in_stratum": "int",
    }
    (out_dir / "pilot_state_manifest_schema.json").write_text(json.dumps(schema, indent=2), encoding="utf-8")

    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
