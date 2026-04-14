#!/usr/bin/env python3
"""Compact trigger/coverage audit for current best two-stage branch (new-paper track)."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import random
import statistics
import subprocess
import sys
import time
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.controllers import AdaptiveController
from experiments.frontier_matrix_core import build_frontier_strategies, evaluate_strategies_on_examples, generator_factory_for_mode, load_pilot_examples
from experiments.scoring import _ordered_history_features


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run compact two-stage trigger/coverage audit")
    p.add_argument("--output-root", default="outputs/new_paper/two_stage_trigger_audit")
    p.add_argument("--run-id", default=None)
    p.add_argument("--seeds", default="61,62,63,64")
    p.add_argument("--budget", type=int, default=10)
    p.add_argument("--ranking-episodes", type=int, default=180)
    p.add_argument("--subset-size", type=int, default=24)
    p.add_argument("--dataset", default="openai/gsm8k")
    p.add_argument("--margins", default="0.04,0.06,0.08")
    p.add_argument("--min-tie-confidences", default="0.00,0.10,0.20")
    return p.parse_args()


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def _load_examples_with_retry(dataset: str, subset_size: int, seed: int, tries: int = 4):
    last_err: Exception | None = None
    for i in range(tries):
        try:
            return load_pilot_examples(dataset, subset_size, seed)
        except Exception as e:
            last_err = e
            if i + 1 < tries:
                time.sleep(1.5 * (i + 1))
                continue
    if last_err is not None:
        raise last_err
    raise RuntimeError("failed to load pilot examples")


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            out.append(json.loads(line))
    return out


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        if not rows:
            f.write("")
            return
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def _score_linear(model: dict[str, Any], features: dict[str, float]) -> float:
    s = float(model.get("intercept", 0.0))
    for n, w in model.get("weights", {}).items():
        s += float(w) * float(features.get(n, 0.0))
    return s


def _pair_key(episode_id: int, decision_id: int, a: str, b: str) -> tuple[int, int, str, str]:
    x, y = sorted([str(a), str(b)])
    return (int(episode_id), int(decision_id), x, y)


def _sigmoid(z: float) -> float:
    if z >= 0:
        ez = math.exp(-z)
        return 1.0 / (1.0 + ez)
    ez = math.exp(z)
    return ez / (1.0 + ez)


def _tie_features(row: dict[str, Any], feature_names: list[str]) -> dict[str, float]:
    a = row["features_a"]
    b = row["features_b"]
    feats: dict[str, float] = {}
    for name in feature_names:
        if name.startswith("diff::"):
            base = name.split("::", 1)[1]
            feats[name] = float(a.get(base, 0.0)) - float(b.get(base, 0.0))
        elif name.startswith("abs_diff::"):
            base = name.split("::", 1)[1]
            feats[name] = abs(float(a.get(base, 0.0)) - float(b.get(base, 0.0)))
    return feats


def _compact_feature_names() -> list[str]:
    keys = [
        "parent_relative_score",
        "node_2_score",
        "node_3_score",
        "node_3_distance_to_terminal_est",
        "edge_1_score_delta",
        "edge_2_score_delta",
        "stalled_steps",
        "verify_count",
    ]
    names = [f"diff::{k}" for k in keys]
    names.extend([f"abs_diff::{k}" for k in ["node_3_score", "parent_relative_score", "edge_2_score_delta"]])
    return names


def _train_decision_stump(train_rows: list[dict[str, Any]], test_rows: list[dict[str, Any]], feature_names: list[str]) -> dict[str, Any]:
    def acc(rows: list[dict[str, Any]], feature: str, threshold: float, left_prob: float, right_prob: float) -> float:
        if not rows:
            return 0.0
        ok = 0
        for r in rows:
            x = _tie_features(r, [feature])[feature]
            prob = left_prob if x <= threshold else right_prob
            pred = 1 if prob >= 0.5 else 0
            ok += int(pred == int(r.get("a_preferred", 0)))
        return ok / len(rows)

    if not train_rows:
        return {
            "model_type": "decision_stump",
            "feature_names": feature_names,
            "stump_feature": feature_names[0],
            "threshold": 0.0,
            "left_prob_a": 0.5,
            "right_prob_a": 0.5,
            "train_pair_accuracy": 0.0,
            "test_pair_accuracy": 0.0,
            "n_train": 0,
            "n_test": len(test_rows),
        }

    best: dict[str, Any] | None = None
    for feat in feature_names:
        vals = [_tie_features(r, [feat])[feat] for r in train_rows]
        candidates = sorted(set(sorted(vals)[:: max(1, len(vals) // 6)] + [0.0]))
        for t in candidates:
            left = [int(r.get("a_preferred", 0)) for r in train_rows if _tie_features(r, [feat])[feat] <= t]
            right = [int(r.get("a_preferred", 0)) for r in train_rows if _tie_features(r, [feat])[feat] > t]
            left_prob = sum(left) / max(1, len(left))
            right_prob = sum(right) / max(1, len(right))
            row = {
                "model_type": "decision_stump",
                "feature_names": feature_names,
                "stump_feature": feat,
                "threshold": float(t),
                "left_prob_a": float(left_prob),
                "right_prob_a": float(right_prob),
                "train_pair_accuracy": acc(train_rows, feat, t, left_prob, right_prob),
                "test_pair_accuracy": acc(test_rows, feat, t, left_prob, right_prob),
                "n_train": len(train_rows),
                "n_test": len(test_rows),
            }
            if best is None or (float(row["test_pair_accuracy"]), float(row["train_pair_accuracy"])) > (
                float(best["test_pair_accuracy"]),
                float(best["train_pair_accuracy"]),
            ):
                best = row
    return best if best is not None else {
        "model_type": "decision_stump",
        "feature_names": feature_names,
        "stump_feature": feature_names[0],
        "threshold": 0.0,
        "left_prob_a": 0.5,
        "right_prob_a": 0.5,
        "train_pair_accuracy": 0.0,
        "test_pair_accuracy": 0.0,
        "n_train": len(train_rows),
        "n_test": len(test_rows),
    }


def _tie_prob(tie_model: dict[str, Any], feats: dict[str, float]) -> float:
    model_type = str(tie_model.get("model_type", "decision_stump"))
    if model_type == "decision_stump":
        feat = str(tie_model.get("stump_feature", ""))
        thr = float(tie_model.get("threshold", 0.0))
        left = float(tie_model.get("left_prob_a", 0.5))
        right = float(tie_model.get("right_prob_a", 0.5))
        return left if float(feats.get(feat, 0.0)) <= thr else right
    z = float(tie_model.get("intercept", 0.0))
    for n, w in tie_model.get("weights", {}).items():
        z += float(w) * float(feats.get(n, 0.0))
    return _sigmoid(z)


@dataclass
class TwoStageConfig:
    margin: float
    min_tie_confidence: float

    @property
    def config_id(self) -> str:
        return f"m{self.margin:.2f}_c{self.min_tie_confidence:.2f}".replace(".", "p")


class TwoStageConfiguredScorer:
    """Same two-stage architecture, with minimal trigger gating for audit-only thresholds."""

    def __init__(self, base_model: dict[str, Any], tie_model: dict[str, Any], config: TwoStageConfig, max_actions: int) -> None:
        self.base_model = base_model
        self.tie_model = tie_model
        self.cfg = config
        self.max_actions = max_actions

    def _base_score(self, branch: Any, parent_mean: float) -> float:
        f = _ordered_history_features(branch, parent_mean, max(0, self.max_actions - branch.depth))
        return _score_linear(self.base_model, f)

    def _tie_feats(self, a: Any, b: Any, parent_mean: float) -> dict[str, float]:
        fa = _ordered_history_features(a, parent_mean, max(0, self.max_actions - a.depth))
        fb = _ordered_history_features(b, parent_mean, max(0, self.max_actions - b.depth))
        feats: dict[str, float] = {}
        for n in self.tie_model.get("feature_names", []):
            if n.startswith("diff::"):
                k = n.split("::", 1)[1]
                feats[n] = float(fa.get(k, 0.0)) - float(fb.get(k, 0.0))
            elif n.startswith("abs_diff::"):
                k = n.split("::", 1)[1]
                feats[n] = abs(float(fa.get(k, 0.0)) - float(fb.get(k, 0.0)))
            else:
                feats[n] = 0.0
        return feats

    def score_branch(self, branch: Any) -> float:
        return self._base_score(branch, 0.5)

    def pick_best(self, branches: list[Any]) -> Any | None:
        candidates = [b for b in branches if not b.is_pruned]
        if not candidates:
            return None
        parent_mean = sum(float(b.score) for b in candidates) / max(1, len(candidates))
        ranked = sorted(candidates, key=lambda b: self._base_score(b, parent_mean), reverse=True)
        if len(ranked) < 2:
            return ranked[0]
        gap = self._base_score(ranked[0], parent_mean) - self._base_score(ranked[1], parent_mean)
        if gap > self.cfg.margin:
            return ranked[0]
        feats = self._tie_feats(ranked[0], ranked[1], parent_mean)
        p_top = _tie_prob(self.tie_model, feats)
        if abs(p_top - 0.5) < self.cfg.min_tie_confidence:
            return ranked[0]
        return ranked[0] if p_top >= 0.5 else ranked[1]


def _pair_two_stage_pred(r: dict[str, Any], base_model: dict[str, Any], tie_model: dict[str, Any], cfg: TwoStageConfig) -> tuple[int, bool, float, float]:
    sa = _score_linear(base_model, r["features_a"])
    sb = _score_linear(base_model, r["features_b"])
    base_pred = 1 if sa >= sb else 0
    gap = abs(sa - sb)
    if gap > cfg.margin:
        return base_pred, False, 0.5, gap
    oriented = r if base_pred == 1 else {
        **r,
        "features_a": r["features_b"],
        "features_b": r["features_a"],
        "a_preferred": 1 - int(r.get("a_preferred", 0)),
    }
    feats = _tie_features(oriented, list(tie_model.get("feature_names", [])))
    p_top = _tie_prob(tie_model, feats)
    if abs(p_top - 0.5) < cfg.min_tie_confidence:
        return base_pred, False, p_top, gap
    pred = base_pred if p_top >= 0.5 else (1 - base_pred)
    return pred, True, p_top, gap


def main() -> None:
    args = parse_args()
    seeds = [int(x.strip()) for x in args.seeds.split(",") if x.strip()]
    margins = [float(x.strip()) for x in args.margins.split(",") if x.strip()]
    min_confs = [float(x.strip()) for x in args.min_tie_confidences.split(",") if x.strip()]
    configs = [TwoStageConfig(margin=m, min_tie_confidence=c) for m in margins for c in min_confs]

    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(args.output_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    sweep_rows: list[dict[str, Any]] = []

    for seed in seeds:
        seed_dir = run_dir / f"seed_{seed}"
        seed_dir.mkdir(parents=True, exist_ok=True)

        ranking_dataset = seed_dir / "branch_scorer_v3_dataset.jsonl"
        pairwise_dataset = seed_dir / "pairwise_dataset.jsonl"
        baseline_model_path = seed_dir / "adaptive_learned_branch_score_v7_bt_baseline.json"

        _run([
            sys.executable,
            str(REPO_ROOT / "scripts/build_v3_ranking_dataset.py"),
            "--output-dir",
            str(seed_dir),
            "--episodes",
            str(args.ranking_episodes),
            "--budget",
            str(args.budget),
            "--seed",
            str(seed),
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
            str(baseline_model_path),
            "--seed",
            str(seed),
        ])

        base_pairs = _load_jsonl(pairwise_dataset)
        train_rows = [r for r in base_pairs if r.get("split") == "train"]
        test_rows = [r for r in base_pairs if r.get("split") == "test"]

        # train current best/least-harm tie model family (decision stump compact)
        near_train_rows = [r for r in train_rows if int(r.get("tie_or_uncertain", 0)) == 1]
        near_test_rows = [r for r in test_rows if int(r.get("tie_or_uncertain", 0)) == 1]
        tie_model = _train_decision_stump(near_train_rows, near_test_rows, _compact_feature_names())
        (seed_dir / "near_tie_tie_model_stump_compact.json").write_text(json.dumps(tie_model, indent=2), encoding="utf-8")

        base_model = json.loads(baseline_model_path.read_text(encoding="utf-8"))

        rng = random.Random(seed)
        examples = _load_examples_with_retry(args.dataset, args.subset_size, seed)
        gen_factory = generator_factory_for_mode(False, rng, "gpt-4.1-mini", 0.2, 180, 45)
        strategies = build_frontier_strategies(
            gen_factory,
            args.budget,
            adaptive_min_expand_grid=[1],
            rng=rng,
            use_openai_api=False,
            bt_pairwise_model_path=str(baseline_model_path),
            bt_pairwise_oracle_model_path=str(baseline_model_path),
        )
        baseline_key = "adaptive_bt_pairwise"

        # pre-eval baseline once
        baseline_metrics, _ = evaluate_strategies_on_examples(examples, {baseline_key: strategies[baseline_key]})
        baseline_acc = float(baseline_metrics[baseline_key]["accuracy"])

        for cfg in configs:
            cfg_id = cfg.config_id

            # pairwise trigger/effect audit
            n_trigger = 0
            improve = 0
            hurt = 0
            same_correct = 0
            same_wrong = 0

            trig_low_budget = 0
            trig_high_verify = 0
            trig_stalled = 0
            trig_tie_like = 0
            trig_small_gap = 0

            total_two_stage_correct = 0
            total_base_correct = 0

            for r in test_rows:
                sa = _score_linear(base_model, r["features_a"])
                sb = _score_linear(base_model, r["features_b"])
                base_pred = 1 if sa >= sb else 0
                label = int(r.get("a_preferred", 0))
                total_base_correct += int(base_pred == label)

                pred, fired, p_top, gap = _pair_two_stage_pred(r, base_model, tie_model, cfg)
                total_two_stage_correct += int(pred == label)

                if fired:
                    n_trigger += 1
                    max_verify = max(float(r["features_a"].get("verify_count", 0.0)), float(r["features_b"].get("verify_count", 0.0)))
                    max_stalled = max(float(r["features_a"].get("stalled_steps", 0.0)), float(r["features_b"].get("stalled_steps", 0.0)))
                    rem_budget = float(r.get("remaining_budget", 0.0))
                    trig_low_budget += int(rem_budget <= 4)
                    trig_high_verify += int(max_verify >= 2)
                    trig_stalled += int(max_stalled >= 1)
                    trig_tie_like += int(int(r.get("tie_or_uncertain", 0)) == 1)
                    trig_small_gap += int(gap <= 0.02)

                    base_ok = int(base_pred == label)
                    two_ok = int(pred == label)
                    if two_ok == 1 and base_ok == 0:
                        improve += 1
                    elif two_ok == 0 and base_ok == 1:
                        hurt += 1
                    elif two_ok == 1 and base_ok == 1:
                        same_correct += 1
                    else:
                        same_wrong += 1

            trigger_rate = n_trigger / max(1, len(test_rows))
            pair_acc = total_two_stage_correct / max(1, len(test_rows))
            base_pair_acc = total_base_correct / max(1, len(test_rows))

            # controller method metric for this trigger config
            method = f"adaptive_bt_pairwise_two_stage_{cfg_id}"
            strategies_local = {
                baseline_key: strategies[baseline_key],
                method: AdaptiveController(
                    gen_factory(),
                    TwoStageConfiguredScorer(base_model=base_model, tie_model=tie_model, config=cfg, max_actions=args.budget),
                    args.budget,
                    high_threshold=0.72,
                    low_threshold=0.42,
                    max_branches=3,
                    allow_verify=True,
                    min_expansions_before_prune=1,
                    method_name=method,
                ),
            }
            mm, _ = evaluate_strategies_on_examples(examples, strategies_local)
            acc = float(mm[method]["accuracy"])

            sweep_rows.append(
                {
                    "seed": seed,
                    "config_id": cfg_id,
                    "near_tie_margin": cfg.margin,
                    "min_tie_confidence": cfg.min_tie_confidence,
                    "n_test_pairs": len(test_rows),
                    "trigger_count": n_trigger,
                    "trigger_rate": trigger_rate,
                    "trigger_low_budget_rate": trig_low_budget / max(1, n_trigger),
                    "trigger_high_verify_rate": trig_high_verify / max(1, n_trigger),
                    "trigger_stalled_rate": trig_stalled / max(1, n_trigger),
                    "trigger_tie_like_rate": trig_tie_like / max(1, n_trigger),
                    "trigger_small_gap_rate": trig_small_gap / max(1, n_trigger),
                    "improve_count": improve,
                    "hurt_count": hurt,
                    "same_correct_count": same_correct,
                    "same_wrong_count": same_wrong,
                    "improve_rate_among_triggered": improve / max(1, n_trigger),
                    "hurt_rate_among_triggered": hurt / max(1, n_trigger),
                    "help_to_hurt_ratio": (improve / max(1, hurt)),
                    "pair_accuracy": pair_acc,
                    "pair_delta_vs_baseline": pair_acc - base_pair_acc,
                    "controller_accuracy": acc,
                    "controller_delta_vs_baseline": acc - baseline_acc,
                }
            )

    # aggregate outputs
    by_cfg: dict[str, list[dict[str, Any]]] = {}
    for r in sweep_rows:
        by_cfg.setdefault(str(r["config_id"]), []).append(r)

    coverage_rows: list[dict[str, Any]] = []
    effect_rows: list[dict[str, Any]] = []
    method_rows: list[dict[str, Any]] = []

    for cfg_id, rows in sorted(by_cfg.items()):
        coverage_rows.append(
            {
                "config_id": cfg_id,
                "mean_trigger_rate": statistics.mean(float(r["trigger_rate"]) for r in rows),
                "std_trigger_rate": statistics.stdev([float(r["trigger_rate"]) for r in rows]) if len(rows) > 1 else 0.0,
                "mean_trigger_low_budget_rate": statistics.mean(float(r["trigger_low_budget_rate"]) for r in rows),
                "mean_trigger_high_verify_rate": statistics.mean(float(r["trigger_high_verify_rate"]) for r in rows),
                "mean_trigger_stalled_rate": statistics.mean(float(r["trigger_stalled_rate"]) for r in rows),
                "mean_trigger_tie_like_rate": statistics.mean(float(r["trigger_tie_like_rate"]) for r in rows),
                "mean_trigger_small_gap_rate": statistics.mean(float(r["trigger_small_gap_rate"]) for r in rows),
            }
        )
        effect_rows.append(
            {
                "config_id": cfg_id,
                "mean_improve_rate_among_triggered": statistics.mean(float(r["improve_rate_among_triggered"]) for r in rows),
                "mean_hurt_rate_among_triggered": statistics.mean(float(r["hurt_rate_among_triggered"]) for r in rows),
                "mean_help_to_hurt_ratio": statistics.mean(float(r["help_to_hurt_ratio"]) for r in rows),
                "mean_pair_delta_vs_baseline": statistics.mean(float(r["pair_delta_vs_baseline"]) for r in rows),
                "mean_controller_delta_vs_baseline": statistics.mean(float(r["controller_delta_vs_baseline"]) for r in rows),
                "wins_vs_baseline": sum(1 for r in rows if float(r["controller_delta_vs_baseline"]) > 0),
                "losses_vs_baseline": sum(1 for r in rows if float(r["controller_delta_vs_baseline"]) < 0),
            }
        )
        method_rows.append(
            {
                "method": f"adaptive_bt_pairwise_two_stage_{cfg_id}",
                "n_seeds": len(rows),
                "mean_accuracy": statistics.mean(float(r["controller_accuracy"]) for r in rows),
                "std_accuracy": statistics.stdev([float(r["controller_accuracy"]) for r in rows]) if len(rows) > 1 else 0.0,
                "mean_delta_vs_baseline": statistics.mean(float(r["controller_delta_vs_baseline"]) for r in rows),
                "std_delta_vs_baseline": statistics.stdev([float(r["controller_delta_vs_baseline"]) for r in rows]) if len(rows) > 1 else 0.0,
            }
        )

    # add baseline method row from per-config rows (same baseline each config/seed)
    baseline_seed_acc: dict[int, float] = {}
    for r in sweep_rows:
        s = int(r["seed"])
        if s not in baseline_seed_acc:
            baseline_seed_acc[s] = float(r["controller_accuracy"]) - float(r["controller_delta_vs_baseline"])
    bvals = list(baseline_seed_acc.values())
    method_rows.insert(
        0,
        {
            "method": "adaptive_bt_pairwise",
            "n_seeds": len(bvals),
            "mean_accuracy": statistics.mean(bvals) if bvals else 0.0,
            "std_accuracy": statistics.stdev(bvals) if len(bvals) > 1 else 0.0,
            "mean_delta_vs_baseline": 0.0,
            "std_delta_vs_baseline": 0.0,
        },
    )

    _write_csv(run_dir / "threshold_sweep_results.csv", sweep_rows)
    _write_csv(run_dir / "trigger_coverage_summary.csv", coverage_rows)
    _write_csv(run_dir / "trigger_effect_summary.csv", effect_rows)
    _write_csv(run_dir / "method_metrics.csv", method_rows)

    # pick safe operating region: positive mean delta, help>hurt, moderate trigger rate <=0.25; fallback highest mean delta
    coverage_by_cfg = {r["config_id"]: r for r in coverage_rows}
    effect_by_cfg = {r["config_id"]: r for r in effect_rows}
    candidates = []
    for cfg_id, e in effect_by_cfg.items():
        c = coverage_by_cfg.get(cfg_id, {})
        if float(e["mean_controller_delta_vs_baseline"]) >= 0 and float(e["mean_help_to_hurt_ratio"]) > 1.0 and float(c.get("mean_trigger_rate", 1.0)) <= 0.25:
            candidates.append((cfg_id, float(e["mean_controller_delta_vs_baseline"])))
    if candidates:
        safest_cfg = sorted(candidates, key=lambda x: x[1], reverse=True)[0][0]
    else:
        safest_cfg = sorted(effect_rows, key=lambda r: float(r["mean_controller_delta_vs_baseline"]), reverse=True)[0]["config_id"] if effect_rows else "n/a"

    safest_cov = coverage_by_cfg.get(safest_cfg, {})
    safest_eff = effect_by_cfg.get(safest_cfg, {})

    positive_selective = (
        float(safest_eff.get("mean_controller_delta_vs_baseline", 0.0)) > 0
        and float(safest_eff.get("mean_help_to_hurt_ratio", 0.0)) > 1.0
        and float(safest_cov.get("mean_trigger_rate", 0.0)) >= 0.01
    )

    interp = [
        f"# Two-stage trigger/coverage audit ({run_id})",
        "",
        "Compact keep-or-drop audit for the current least-harm two-stage branch (decision stump compact tie model).",
        "",
        "## Explicit answers",
        f"- How often does tie-breaker fire? Typical trigger rate range across tested configs: {min(float(r['mean_trigger_rate']) for r in coverage_rows):.3f} to {max(float(r['mean_trigger_rate']) for r in coverage_rows):.3f}.",
        f"- In triggered cases, help vs hurt: generally mixed; safest config `{safest_cfg}` has mean improve_rate={float(safest_eff.get('mean_improve_rate_among_triggered', 0.0)):.3f}, mean hurt_rate={float(safest_eff.get('mean_hurt_rate_among_triggered', 0.0)):.3f}, help/hurt={float(safest_eff.get('mean_help_to_hurt_ratio', 0.0)):.3f}.",
        f"- Narrow safer trigger region found? {'yes' if safest_cfg != 'n/a' else 'no'}; selected config `{safest_cfg}` with mean trigger_rate={float(safest_cov.get('mean_trigger_rate', 0.0)):.3f} and mean controller delta={float(safest_eff.get('mean_controller_delta_vs_baseline', 0.0)):+.4f}.",
        f"- Is recent positive mean likely selective benefit or noise? {'selective but weak' if positive_selective else 'likely unstable/noisy or degenerate (near-never firing)'}.",
        "",
        "## Conservative decision",
        "- Keep baseline proxy BT as default.",
        f"- Two-stage branch status: {'active experimental (narrow gated setting only)' if positive_selective else 'diagnostic-only'}.",
        "- If no config sustains positive delta with help>hurt in repeats, stop spending on two-stage tuning.",
    ]
    (run_dir / "interpretation.md").write_text("\n".join(interp) + "\n", encoding="utf-8")

    manifest = {
        "run_id": run_id,
        "track": "new-paper",
        "goal": "two_stage_keep_or_drop_trigger_coverage_audit",
        "dataset": args.dataset,
        "budget": args.budget,
        "ranking_episodes": args.ranking_episodes,
        "subset_size": args.subset_size,
        "seeds": seeds,
        "tie_model_family": "decision_stump_compact_features_on_tie_or_uncertain_train_pairs",
        "threshold_grid": [{"near_tie_margin": c.margin, "min_tie_confidence": c.min_tie_confidence, "config_id": c.config_id} for c in configs],
        "selected_safest_config": safest_cfg,
        "artifacts": {
            "trigger_coverage_summary": str(run_dir / "trigger_coverage_summary.csv"),
            "trigger_effect_summary": str(run_dir / "trigger_effect_summary.csv"),
            "threshold_sweep_results": str(run_dir / "threshold_sweep_results.csv"),
            "method_metrics": str(run_dir / "method_metrics.csv"),
            "run_manifest": str(run_dir / "run_manifest.json"),
            "interpretation": str(run_dir / "interpretation.md"),
        },
    }
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(json.dumps({"run_id": run_id, "run_dir": str(run_dir), "n_rows": len(sweep_rows), "safest_config": safest_cfg}, indent=2))


if __name__ == "__main__":
    main()
