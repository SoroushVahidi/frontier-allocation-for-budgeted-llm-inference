#!/usr/bin/env python3
"""Paper-inspired MODE A adapter for Conformal Thinking (arXiv:2602.03814).

This script implements a conservative matched-substrate early-exit baseline with:
- upper-threshold stopping (confidence-like signal),
- optional dual-threshold stopping (confidence + low-progress threshold),
- validation-set calibration with plus-one finite-sample correction,
- explicit per-query max-budget accounting.

Claim boundary: adapter-based adjacent comparator only, not official reproduction.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import random
import statistics
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.frontier_matrix_core import load_pilot_examples  # noqa: E402

DEFAULT_CONFIG = REPO_ROOT / "configs" / "conformal_thinking_mode_a_v1.json"

POLICIES = [
    "full_budget_baseline",
    "fixed_budget_truncation_baseline",
    "naive_upper_threshold_stopping",
    "conformal_thinking_mode_a_upper",
    "conformal_thinking_mode_a_dual",
]


@dataclass
class RunConfig:
    dataset: str
    subset_size: int
    seeds: list[int]
    calibration_fraction: float
    max_steps_per_query: int
    fixed_truncation_steps: int
    step_token_cost: int
    confidence_smoothing: float
    progress_window: int
    difficulty_length_weight: float
    difficulty_digit_weight: float
    difficulty_symbol_weight: float
    risk_target_upper: float
    risk_target_lower: float
    threshold_grid_points: int
    allow_dual_threshold: bool
    output_root: Path


@dataclass
class ExampleTrajectory:
    example_id: str
    difficulty: float
    solve_step: int | None
    conf: list[float]
    progress: list[float]
    correct_by_step: list[bool]


def _stable_seed(*parts: Any) -> int:
    h = hashlib.sha256("||".join(str(x) for x in parts).encode("utf-8")).hexdigest()
    return int(h[:16], 16)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for k in row:
            if k not in seen:
                seen.add(k)
                fields.append(k)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _load_config(path: Path) -> RunConfig:
    raw = _read_json(path)
    d = raw.get("dataset", {})
    b = raw.get("budget", {})
    s = raw.get("signals", {})
    c = raw.get("calibration", {})
    return RunConfig(
        dataset=str(d.get("name", "openai/gsm8k")),
        subset_size=int(d.get("subset_size", 36)),
        seeds=[int(x) for x in d.get("seeds", [11, 23, 37])],
        calibration_fraction=float(d.get("calibration_fraction", 0.5)),
        max_steps_per_query=max(2, int(b.get("max_steps_per_query", 10))),
        fixed_truncation_steps=max(1, int(b.get("fixed_truncation_steps", 6))),
        step_token_cost=max(1, int(b.get("step_token_cost", 64))),
        confidence_smoothing=min(0.95, max(0.0, float(s.get("confidence_smoothing", 0.35)))),
        progress_window=max(1, int(s.get("progress_window", 2))),
        difficulty_length_weight=float(s.get("difficulty_length_weight", 0.55)),
        difficulty_digit_weight=float(s.get("difficulty_digit_weight", 0.25)),
        difficulty_symbol_weight=float(s.get("difficulty_symbol_weight", 0.2)),
        risk_target_upper=float(c.get("risk_target_upper", 0.2)),
        risk_target_lower=float(c.get("risk_target_lower", 0.25)),
        threshold_grid_points=max(5, int(c.get("threshold_grid_points", 41))),
        allow_dual_threshold=bool(c.get("allow_dual_threshold", True)),
        output_root=REPO_ROOT / str(raw.get("output", {}).get("root_dir", "outputs/conformal_thinking_mode_a")),
    )


def difficulty_score(question: str, cfg: RunConfig) -> float:
    q = question or ""
    length_term = min(1.0, len(q) / 260.0)
    digit_term = min(1.0, sum(1 for ch in q if ch.isdigit()) / 14.0)
    symbol_term = min(1.0, sum(1 for ch in q if ch in "+-*/%=<>") / 10.0)
    score = (
        cfg.difficulty_length_weight * length_term
        + cfg.difficulty_digit_weight * digit_term
        + cfg.difficulty_symbol_weight * symbol_term
    )
    return max(0.0, min(1.0, score))


def _simulate_trajectory(example_id: str, difficulty: float, cfg: RunConfig, seed: int) -> ExampleTrajectory:
    rng = random.Random(_stable_seed("ctraj", example_id, seed))
    max_t = cfg.max_steps_per_query

    solve_step: int | None
    p_solvable = max(0.12, min(0.9, 0.88 - 0.72 * difficulty))
    if rng.random() < p_solvable:
        raw = 2 + int(round((max_t - 2) * (0.20 + 0.75 * difficulty)))
        solve_step = max(1, min(max_t, raw + rng.choice([-1, 0, 1])))
    else:
        solve_step = None

    conf: list[float] = []
    progress: list[float] = []
    correct_by_step: list[bool] = []

    prev = 0.08 + 0.12 * (1.0 - difficulty)
    for t in range(1, max_t + 1):
        target = 0.35 + 0.60 * (1.0 - difficulty)
        if solve_step is not None and t >= solve_step:
            target = min(0.99, 0.80 + 0.17 * (1.0 - 0.3 * difficulty))
        slope = 0.05 + (0.07 if solve_step is not None and t <= solve_step else 0.02)
        noise = rng.uniform(-0.06, 0.06)
        raw = prev + slope * (target - prev) + noise
        smoothed = cfg.confidence_smoothing * prev + (1 - cfg.confidence_smoothing) * raw
        prev = max(0.0, min(1.0, smoothed))
        conf.append(prev)

        if t == 1:
            progress.append(conf[0])
        else:
            window_start = max(0, t - cfg.progress_window - 1)
            gain = conf[t - 1] - conf[window_start]
            progress.append(max(-1.0, min(1.0, gain)))

        correct = solve_step is not None and t >= solve_step
        correct_by_step.append(correct)

    return ExampleTrajectory(
        example_id=example_id,
        difficulty=difficulty,
        solve_step=solve_step,
        conf=conf,
        progress=progress,
        correct_by_step=correct_by_step,
    )


def finite_sample_upper_risk(errors: int, n: int) -> float:
    if n <= 0:
        return 0.0
    return (errors + 1) / (n + 1)


def finite_sample_lower_risk(false_negatives: int, n: int) -> float:
    if n <= 0:
        return 0.0
    return (false_negatives + 1) / (n + 1)


def split_calibration_eval(example_ids: list[str], frac: float, seed: int) -> tuple[set[str], set[str]]:
    rng = random.Random(_stable_seed("csplit", seed, len(example_ids)))
    ids = list(example_ids)
    rng.shuffle(ids)
    k = max(1, min(len(ids) - 1, int(round(len(ids) * frac))))
    calib = set(ids[:k])
    eval_ids = set(ids[k:])
    return calib, eval_ids


def _pick_exit_time(conf: list[float], progress: list[float], upper: float | None, lower: float | None) -> tuple[int, str]:
    max_t = len(conf)
    for idx in range(max_t):
        t = idx + 1
        if upper is not None and conf[idx] >= upper:
            return t, "upper"
        if lower is not None and progress[idx] <= lower:
            return t, "lower"
    return max_t, "budget"


def calibrate_upper_threshold(
    calib: list[ExampleTrajectory],
    risk_target: float,
    grid_points: int,
    corrected: bool,
) -> dict[str, Any]:
    thresholds = [i / (grid_points - 1) for i in range(grid_points)]
    feasible: list[dict[str, Any]] = []
    for th in thresholds:
        exits = 0
        errors = 0
        mean_steps = 0.0
        for tr in calib:
            t, _ = _pick_exit_time(tr.conf, tr.progress, upper=th, lower=None)
            exits += 1
            mean_steps += t
            if not tr.correct_by_step[t - 1]:
                errors += 1
        risk = finite_sample_upper_risk(errors, exits) if corrected else (errors / exits if exits else 0.0)
        feasible.append(
            {
                "threshold": th,
                "upper_risk": risk,
                "raw_error_rate": errors / exits if exits else 0.0,
                "mean_steps": mean_steps / max(1, exits),
                "feasible": risk <= risk_target,
            }
        )
    candidates = [r for r in feasible if r["feasible"]]
    if candidates:
        chosen = min(candidates, key=lambda r: (r["mean_steps"], -r["threshold"]))
    else:
        chosen = min(feasible, key=lambda r: (r["upper_risk"], r["mean_steps"]))
    return {"rows": feasible, "chosen": chosen, "corrected": corrected}


def calibrate_dual_threshold(
    calib: list[ExampleTrajectory],
    upper_threshold: float,
    risk_target_lower: float,
    grid_points: int,
    corrected: bool,
) -> dict[str, Any]:
    low_grid = [(-0.25 + 0.55 * i / (grid_points - 1)) for i in range(grid_points)]
    rows: list[dict[str, Any]] = []
    for low in low_grid:
        lower_stops = 0
        false_neg = 0
        mean_steps = 0.0
        for tr in calib:
            t, reason = _pick_exit_time(tr.conf, tr.progress, upper=upper_threshold, lower=low)
            mean_steps += t
            if reason == "lower":
                lower_stops += 1
                can_solve_later = any(tr.correct_by_step[t - 1 :])
                if can_solve_later:
                    false_neg += 1
        risk = finite_sample_lower_risk(false_neg, lower_stops) if corrected else (false_neg / lower_stops if lower_stops else 0.0)
        rows.append(
            {
                "lower_threshold": low,
                "lower_risk": risk,
                "raw_false_negative_rate": false_neg / lower_stops if lower_stops else 0.0,
                "lower_stop_rate": lower_stops / max(1, len(calib)),
                "mean_steps": mean_steps / max(1, len(calib)),
                "feasible": risk <= risk_target_lower,
            }
        )
    feasible = [r for r in rows if r["feasible"]]
    if feasible:
        chosen = min(feasible, key=lambda r: (r["mean_steps"], r["lower_risk"]))
    else:
        chosen = min(rows, key=lambda r: (r["lower_risk"], r["mean_steps"]))
    return {"rows": rows, "chosen": chosen, "corrected": corrected}


def evaluate_policy(
    policy: str,
    trajectories: list[ExampleTrajectory],
    upper: float | None,
    lower: float | None,
    fixed_steps: int,
    max_steps: int,
    step_token_cost: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    per_ex: list[dict[str, Any]] = []
    for tr in trajectories:
        if policy == "full_budget_baseline":
            stop_t, reason = max_steps, "budget"
        elif policy == "fixed_budget_truncation_baseline":
            stop_t, reason = min(max_steps, fixed_steps), "fixed_truncation"
        else:
            stop_t, reason = _pick_exit_time(tr.conf[:max_steps], tr.progress[:max_steps], upper=upper, lower=lower)

        correct = tr.correct_by_step[stop_t - 1]
        per_ex.append(
            {
                "baseline_id": policy,
                "example_id": tr.example_id,
                "difficulty": tr.difficulty,
                "solve_step": tr.solve_step,
                "stop_step": stop_t,
                "stop_reason": reason,
                "is_correct": bool(correct),
                "confidence_at_stop": tr.conf[stop_t - 1],
                "progress_at_stop": tr.progress[stop_t - 1],
                "tokens_used": stop_t * step_token_cost,
                "max_tokens": max_steps * step_token_cost,
            }
        )

    acc = sum(1 for r in per_ex if r["is_correct"]) / max(1, len(per_ex))
    mean_steps = statistics.mean([r["stop_step"] for r in per_ex]) if per_ex else 0.0
    mean_tokens = statistics.mean([r["tokens_used"] for r in per_ex]) if per_ex else 0.0
    savings = 1.0 - (mean_steps / max_steps) if max_steps > 0 else 0.0
    stop_reasons = {k: 0 for k in ["upper", "lower", "budget", "fixed_truncation"]}
    for r in per_ex:
        stop_reasons[r["stop_reason"]] = stop_reasons.get(r["stop_reason"], 0) + 1
    adaptivity_std = statistics.pstdev([r["stop_step"] for r in per_ex]) if len(per_ex) > 1 else 0.0
    diff = [r["difficulty"] for r in per_ex]
    steps = [r["stop_step"] for r in per_ex]
    corr = 0.0
    if len(per_ex) > 1:
        mean_x = statistics.mean(diff)
        mean_y = statistics.mean(steps)
        num = sum((x - mean_x) * (y - mean_y) for x, y in zip(diff, steps))
        den = math.sqrt(sum((x - mean_x) ** 2 for x in diff) * sum((y - mean_y) ** 2 for y in steps))
        corr = float(num / den) if den > 0 else 0.0

    summary = {
        "baseline_id": policy,
        "accuracy": float(acc),
        "mean_steps": float(mean_steps),
        "mean_tokens": float(mean_tokens),
        "compute_savings_vs_full_budget": float(savings),
        "adaptive_stop_std": float(adaptivity_std),
        "difficulty_vs_stop_step_corr": float(corr),
        "n": len(per_ex),
        "stop_reason_upper": stop_reasons.get("upper", 0),
        "stop_reason_lower": stop_reasons.get("lower", 0),
        "stop_reason_budget": stop_reasons.get("budget", 0),
    }
    return summary, per_ex


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run conformal-thinking MODE A matched-substrate adapter")
    p.add_argument("--config", default=str(DEFAULT_CONFIG.relative_to(REPO_ROOT)))
    p.add_argument("--run-id", default=None)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    config_path = (REPO_ROOT / args.config).resolve()
    cfg = _load_config(config_path)

    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = cfg.output_root / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    all_seed_summary: list[dict[str, Any]] = []
    all_example_rows: list[dict[str, Any]] = []
    calibration_rows: list[dict[str, Any]] = []

    for seed in cfg.seeds:
        examples = load_pilot_examples(cfg.dataset, cfg.subset_size, seed)
        ids = [str(getattr(e, "example_id", f"ex_{i}")) for i, e in enumerate(examples)]
        trajectories: list[ExampleTrajectory] = []
        for e, eid in zip(examples, ids):
            diff = difficulty_score(str(getattr(e, "question", "")), cfg)
            trajectories.append(_simulate_trajectory(eid, diff, cfg, seed))

        calib_ids, eval_ids = split_calibration_eval(ids, cfg.calibration_fraction, seed)
        calib = [t for t in trajectories if t.example_id in calib_ids]
        eval_trajs = [t for t in trajectories if t.example_id in eval_ids]

        naive_cal = calibrate_upper_threshold(calib, cfg.risk_target_upper, cfg.threshold_grid_points, corrected=False)
        conf_cal = calibrate_upper_threshold(calib, cfg.risk_target_upper, cfg.threshold_grid_points, corrected=True)
        dual_cal = None
        if cfg.allow_dual_threshold:
            dual_cal = calibrate_dual_threshold(
                calib,
                upper_threshold=float(conf_cal["chosen"]["threshold"]),
                risk_target_lower=cfg.risk_target_lower,
                grid_points=cfg.threshold_grid_points,
                corrected=True,
            )

        policy_to_thresholds: dict[str, tuple[float | None, float | None]] = {
            "full_budget_baseline": (None, None),
            "fixed_budget_truncation_baseline": (None, None),
            "naive_upper_threshold_stopping": (float(naive_cal["chosen"]["threshold"]), None),
            "conformal_thinking_mode_a_upper": (float(conf_cal["chosen"]["threshold"]), None),
            "conformal_thinking_mode_a_dual": (
                float(conf_cal["chosen"]["threshold"]),
                float(dual_cal["chosen"]["lower_threshold"]) if dual_cal else None,
            ),
        }

        for policy in POLICIES:
            if policy == "conformal_thinking_mode_a_dual" and not cfg.allow_dual_threshold:
                continue
            upper, lower = policy_to_thresholds[policy]
            summary, rows = evaluate_policy(
                policy=policy,
                trajectories=eval_trajs,
                upper=upper,
                lower=lower,
                fixed_steps=cfg.fixed_truncation_steps,
                max_steps=cfg.max_steps_per_query,
                step_token_cost=cfg.step_token_cost,
            )
            summary.update(
                {
                    "seed": seed,
                    "calibration_size": len(calib),
                    "eval_size": len(eval_trajs),
                    "upper_threshold": upper,
                    "lower_threshold": lower,
                    "calibration_upper_target": cfg.risk_target_upper,
                    "calibration_lower_target": cfg.risk_target_lower,
                }
            )
            all_seed_summary.append(summary)
            all_example_rows.extend([{**r, "seed": seed} for r in rows])

        calibration_rows.append(
            {
                "seed": seed,
                "naive_upper_threshold": naive_cal["chosen"]["threshold"],
                "naive_upper_risk_estimate": naive_cal["chosen"]["upper_risk"],
                "conformal_upper_threshold": conf_cal["chosen"]["threshold"],
                "conformal_upper_risk_estimate": conf_cal["chosen"]["upper_risk"],
                "conformal_dual_lower_threshold": None if dual_cal is None else dual_cal["chosen"]["lower_threshold"],
                "conformal_dual_lower_risk_estimate": None if dual_cal is None else dual_cal["chosen"]["lower_risk"],
                "calibration_size": len(calib),
            }
        )

    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in all_seed_summary:
        grouped.setdefault(row["baseline_id"], []).append(row)

    comp_rows: list[dict[str, Any]] = []
    for baseline, rows in grouped.items():
        comp_rows.append(
            {
                "baseline_id": baseline,
                "accuracy": statistics.mean([float(r["accuracy"]) for r in rows]),
                "mean_steps": statistics.mean([float(r["mean_steps"]) for r in rows]),
                "mean_tokens": statistics.mean([float(r["mean_tokens"]) for r in rows]),
                "compute_savings_vs_full_budget": statistics.mean([float(r["compute_savings_vs_full_budget"]) for r in rows]),
                "adaptive_stop_std": statistics.mean([float(r["adaptive_stop_std"]) for r in rows]),
                "difficulty_vs_stop_step_corr": statistics.mean([float(r["difficulty_vs_stop_step_corr"]) for r in rows]),
                "n_rows": len(rows),
            }
        )

    comp_rows.sort(key=lambda x: (x["accuracy"], -x["mean_steps"]), reverse=True)

    by_name = {r["baseline_id"]: r for r in comp_rows}
    full = by_name.get("full_budget_baseline")
    conf_upper = by_name.get("conformal_thinking_mode_a_upper")
    conf_dual = by_name.get("conformal_thinking_mode_a_dual")

    recommendation = "repo_only_not_paper_facing_yet"
    if conf_upper and full and conf_upper["accuracy"] >= (full["accuracy"] - 0.03) and conf_upper["compute_savings_vs_full_budget"] >= 0.08:
        recommendation = "appendix_only"

    diagnostic_summary = {
        "baseline_id": "conformal_thinking_mode_a",
        "classification": "adapter_based",
        "control_equivalence": "adjacent",
        "paper_identity_source": "arXiv_2602.03814",
        "official_reproduction_claim": False,
        "adaptive_behavior_evidence": {
            "upper_adaptive_stop_std": None if conf_upper is None else conf_upper["adaptive_stop_std"],
            "upper_difficulty_corr": None if conf_upper is None else conf_upper["difficulty_vs_stop_step_corr"],
        },
        "calibration_effect": {
            "mean_naive_upper_threshold": statistics.mean([float(r["naive_upper_threshold"]) for r in calibration_rows]),
            "mean_conformal_upper_threshold": statistics.mean([float(r["conformal_upper_threshold"]) for r in calibration_rows]),
            "mean_naive_upper_risk_estimate": statistics.mean([float(r["naive_upper_risk_estimate"]) for r in calibration_rows]),
            "mean_conformal_upper_risk_estimate": statistics.mean([float(r["conformal_upper_risk_estimate"]) for r in calibration_rows]),
        },
        "compute_savings_real": {
            "upper_vs_full_budget": None if conf_upper is None else conf_upper["compute_savings_vs_full_budget"],
            "dual_vs_full_budget": None if conf_dual is None else conf_dual["compute_savings_vs_full_budget"],
            "accounting_basis": "per_query_steps * step_token_cost with shared max_steps_per_query",
        },
        "help_vs_hurt": {
            "upper_accuracy_delta_vs_full": None if conf_upper is None or full is None else conf_upper["accuracy"] - full["accuracy"],
            "dual_accuracy_delta_vs_full": None if conf_dual is None or full is None else conf_dual["accuracy"] - full["accuracy"],
        },
        "recommendation": recommendation,
        "claim_boundary": "paper-inspired matched-substrate risk-controlled early-exit baseline; not branch-level control-equivalent and not official reproduction",
    }

    status = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "baseline_id": "conformal_thinking_mode_a",
        "status": "adapter_based",
        "control_equivalence": "adjacent",
        "comparability_scope": "matched_substrate_mode_a_sanity_bundle",
        "official_reproduction_claim": False,
        "paper_source": {
            "arxiv_abs": "https://arxiv.org/abs/2602.03814",
            "arxiv_pdf": "https://arxiv.org/pdf/2602.03814.pdf",
            "official_public_repo_verified": False,
        },
        "recommendation": recommendation,
    }

    _write_csv(out_dir / "comparison_summary.csv", comp_rows)
    _write_csv(out_dir / "per_seed_summary.csv", all_seed_summary)
    _write_jsonl(out_dir / "per_example_results.jsonl", all_example_rows)
    _write_json(out_dir / "calibration_summary.json", {"rows": calibration_rows})
    _write_json(out_dir / "diagnostic_summary.json", diagnostic_summary)
    _write_json(out_dir / "status.json", status)

    lines = [
        "# conformal_thinking_mode_a diagnostic report",
        "",
        "This run is a paper-inspired MODE A adapter baseline and not an official reproduction.",
        "",
        "## Sanity bundle policies",
        "- full_budget_baseline",
        "- fixed_budget_truncation_baseline",
        "- naive_upper_threshold_stopping",
        "- conformal_thinking_mode_a_upper",
        "- conformal_thinking_mode_a_dual",
        "",
        "## Calibration findings",
        f"- mean naive upper risk estimate: {diagnostic_summary['calibration_effect']['mean_naive_upper_risk_estimate']:.4f}",
        f"- mean conformal upper risk estimate: {diagnostic_summary['calibration_effect']['mean_conformal_upper_risk_estimate']:.4f}",
        "",
        "## Compute and quality",
    ]
    if full and conf_upper:
        lines.append(
            f"- upper: accuracy delta vs full = {conf_upper['accuracy'] - full['accuracy']:+.4f}, compute savings = {conf_upper['compute_savings_vs_full_budget']:.4f}"
        )
    if full and conf_dual:
        lines.append(
            f"- dual: accuracy delta vs full = {conf_dual['accuracy'] - full['accuracy']:+.4f}, compute savings = {conf_dual['compute_savings_vs_full_budget']:.4f}"
        )
    lines.extend(
        [
            "",
            "## Paper-facing recommendation",
            f"- {recommendation}",
            "- claim boundary: risk-controlled early-exit adapter, adjacent control space, non-official reproduction.",
        ]
    )
    (out_dir / "diagnostic_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    manifest = {
        "run_id": run_id,
        "script": "scripts/run_conformal_thinking_mode_a.py",
        "config": str(config_path.relative_to(REPO_ROOT)),
        "outputs": [
            "status.json",
            "comparison_summary.csv",
            "per_seed_summary.csv",
            "per_example_results.jsonl",
            "calibration_summary.json",
            "diagnostic_summary.json",
            "diagnostic_report.md",
            "manifest.json",
            "config_snapshot.json",
            "command_snapshot.txt",
        ],
    }
    _write_json(out_dir / "manifest.json", manifest)
    _write_json(
        out_dir / "config_snapshot.json",
        {
            "dataset": cfg.dataset,
            "subset_size": cfg.subset_size,
            "seeds": cfg.seeds,
            "max_steps_per_query": cfg.max_steps_per_query,
            "fixed_truncation_steps": cfg.fixed_truncation_steps,
            "risk_target_upper": cfg.risk_target_upper,
            "risk_target_lower": cfg.risk_target_lower,
        },
    )
    (out_dir / "command_snapshot.txt").write_text(
        f"python scripts/run_conformal_thinking_mode_a.py --config {config_path.relative_to(REPO_ROOT)} --run-id {run_id}\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
