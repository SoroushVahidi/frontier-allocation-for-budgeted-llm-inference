#!/usr/bin/env python3
"""Paper-inspired MODE A adapter for
Adaptive Test-Time Compute Allocation via Training-Free Difficulty Proxies.

This is a conservative matched-substrate comparator:
- query/sample-level global budget allocation,
- one budget unit = one additional generation attempt on one unsolved instance,
- DIPA-style probabilistic allocation with dynamic difficulty updates,
- not an official reproduction.
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

DEFAULT_CONFIG = REPO_ROOT / "configs" / "training_free_difficulty_proxies_mode_a_v1.json"

POLICIES = [
    "uniform",
    "fixed_round_robin",
    "easy_to_hard_mgl",
    "hard_to_easy_mgl",
    "dipa_mgl",
]


@dataclass
class RunConfig:
    dataset: str
    subset_size: int
    seeds: list[int]
    budget_multipliers: list[float]
    output_root: Path
    lambda_scale: float
    lambda_min: float
    mgl_floor: float
    cheap_proxy_length_weight: float
    cheap_proxy_digit_weight: float


@dataclass
class AttemptRecord:
    success: bool
    generation_length: int
    generation_text: str


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
    keys: list[str] = []
    seen: set[str] = set()
    for r in rows:
        for k in r:
            if k not in seen:
                keys.append(k)
                seen.add(k)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _stable_seed(*parts: Any) -> int:
    h = hashlib.sha256("||".join(str(x) for x in parts).encode("utf-8")).hexdigest()
    return int(h[:16], 16)


def _load_config(path: Path) -> RunConfig:
    raw = _read_json(path)
    dataset = raw.get("dataset", {})
    budget = raw.get("budget", {})
    dipa = raw.get("dipa", {})
    cheap = raw.get("cheap_input_proxy", {})
    return RunConfig(
        dataset=str(dataset.get("name", "openai/gsm8k")),
        subset_size=int(dataset.get("subset_size", 24)),
        seeds=[int(s) for s in dataset.get("seeds", [11, 23])],
        budget_multipliers=[float(x) for x in budget.get("global_budget_multipliers", [1.0, 1.5, 2.0])],
        output_root=REPO_ROOT / str(raw.get("output", {}).get("root_dir", "outputs/training_free_difficulty_proxies_mode_a")),
        lambda_scale=float(dipa.get("lambda_scale", 1.0)),
        lambda_min=float(dipa.get("lambda_min", 0.25)),
        mgl_floor=float(dipa.get("mgl_floor", 1.0)),
        cheap_proxy_length_weight=float(cheap.get("length_weight", 0.8)),
        cheap_proxy_digit_weight=float(cheap.get("digit_weight", 0.2)),
    )


def cheap_input_proxy(question: str, cfg: RunConfig) -> float:
    q = question or ""
    length_term = min(1.0, len(q) / 260.0)
    digit_term = min(1.0, sum(1 for ch in q if ch.isdigit()) / 12.0)
    return max(cfg.mgl_floor, cfg.cheap_proxy_length_weight * length_term + cfg.cheap_proxy_digit_weight * digit_term)


def _simulate_attempt_record(seed: int, ex_id: str, attempt_idx: int, cheap_difficulty: float) -> AttemptRecord:
    rng = random.Random(_stable_seed("dipa_attempt", seed, ex_id, attempt_idx))
    d = max(0.0, min(1.0, cheap_difficulty))
    base = 0.18 + 0.58 * (1.0 - d)
    lift = 0.07 * max(0, attempt_idx - 1)
    p_success = max(0.03, min(0.96, base + lift))
    success = rng.random() < p_success
    mean_len = 20 + 100 * d + 8 * math.log1p(attempt_idx)
    gen_len = int(max(8, round(rng.gauss(mean_len, 7.0))))
    gen_text = "x" * gen_len
    return AttemptRecord(success=success, generation_length=gen_len, generation_text=gen_text)


def _build_attempt_bank(example_ids: list[str], cheap_diffs: list[float], seed: int, max_attempts: int) -> dict[str, list[AttemptRecord]]:
    bank: dict[str, list[AttemptRecord]] = {}
    for ex_id, d in zip(example_ids, cheap_diffs):
        bank[ex_id] = [_simulate_attempt_record(seed, ex_id, t + 1, d) for t in range(max_attempts)]
    return bank


def _mgl_from_failed_lengths(failed_lengths: list[int], fallback: float, floor: float) -> float:
    if not failed_lengths:
        return max(floor, fallback)
    return max(floor, float(sum(failed_lengths) / len(failed_lengths)))


def _choose_instance(
    policy: str,
    active_ids: list[str],
    current_m: dict[str, float],
    rr_cursor: int,
    rng: random.Random,
    lambda_t: float,
) -> tuple[str, int]:
    if policy == "uniform":
        return rng.choice(active_ids), rr_cursor
    if policy == "fixed_round_robin":
        selected = active_ids[rr_cursor % len(active_ids)]
        return selected, rr_cursor + 1
    if policy == "easy_to_hard_mgl":
        return min(active_ids, key=lambda x: (current_m[x], x)), rr_cursor
    if policy == "hard_to_easy_mgl":
        return max(active_ids, key=lambda x: (current_m[x], x)), rr_cursor
    if policy == "dipa_mgl":
        weights = [1.0 / (max(1e-6, current_m[x]) ** lambda_t) for x in active_ids]
        total = sum(weights)
        if total <= 0:
            return rng.choice(active_ids), rr_cursor
        draw = rng.random() * total
        run = 0.0
        for ex_id, w in zip(active_ids, weights):
            run += w
            if draw <= run:
                return ex_id, rr_cursor
        return active_ids[-1], rr_cursor
    raise ValueError(f"Unknown policy: {policy}")


def _run_single_policy(
    *,
    policy: str,
    example_ids: list[str],
    cheap_diffs: dict[str, float],
    bank: dict[str, list[AttemptRecord]],
    global_budget: int,
    cfg: RunConfig,
    seed: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rng = random.Random(_stable_seed("dipa_policy", policy, seed, global_budget))

    active = list(example_ids)
    solved: set[str] = set()
    failed_lengths: dict[str, list[int]] = {x: [] for x in example_ids}
    m: dict[str, float] = {x: max(cfg.mgl_floor, cheap_diffs[x]) for x in example_ids}
    pulls: dict[str, int] = {x: 0 for x in example_ids}
    rr_cursor = 0
    attempt_rows: list[dict[str, Any]] = []

    for t in range(global_budget):
        if not active:
            break
        lambda_t = max(cfg.lambda_min, cfg.lambda_scale * (len(active) / max(1, len(example_ids))))
        selected, rr_cursor = _choose_instance(policy, active, m, rr_cursor, rng, lambda_t)
        k = pulls[selected]
        rec = bank[selected][k]
        pulls[selected] += 1

        if rec.success:
            solved.add(selected)
            active = [x for x in active if x != selected]
            solved_now = True
        else:
            failed_lengths[selected].append(rec.generation_length)
            m[selected] = _mgl_from_failed_lengths(failed_lengths[selected], m[selected], cfg.mgl_floor)
            solved_now = False

        attempt_rows.append(
            {
                "policy": policy,
                "step": t + 1,
                "selected_example_id": selected,
                "active_count_before": len(active) + (0 if solved_now else 1),
                "active_count_after": len(active),
                "lambda_t": float(lambda_t),
                "attempt_index_for_selected": pulls[selected],
                "attempt_success": bool(rec.success),
                "generation_length": int(rec.generation_length),
                "updated_m_selected": float(m[selected]),
                "remaining_budget_after": int(global_budget - (t + 1)),
            }
        )

    solved_rate = len(solved) / max(1, len(example_ids))
    solved_ids = sorted(solved)
    m_vals = [m[x] for x in example_ids]
    pull_vals = [pulls[x] for x in example_ids]

    # Proxy-alignment diagnostic: pulls should inversely correlate with M in easy-first policies.
    rank_m = {x: r for r, x in enumerate(sorted(example_ids, key=lambda z: m[z]))}
    rank_p = {x: r for r, x in enumerate(sorted(example_ids, key=lambda z: pulls[z]))}
    d2 = sum((rank_m[x] - rank_p[x]) ** 2 for x in example_ids)
    n = len(example_ids)
    corr = 1.0 - (6.0 * d2 / (n * (n * n - 1))) if n > 1 else 0.0

    return (
        {
            "policy": policy,
            "global_budget": global_budget,
            "n_examples": len(example_ids),
            "n_solved": len(solved),
            "coverage": float(solved_rate),
            "total_attempts_used": int(sum(pull_vals)),
            "mean_attempts_per_example": float(sum(pull_vals) / max(1, len(pull_vals))),
            "mean_final_m": float(sum(m_vals) / max(1, len(m_vals))),
            "pull_vs_final_proxy_rank_corr": float(corr),
            "solved_example_ids": solved_ids,
        },
        attempt_rows,
    )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run training-free difficulty proxies MODE A adapter")
    p.add_argument("--config", default=str(DEFAULT_CONFIG.relative_to(REPO_ROOT)))
    p.add_argument("--run-id", default=None)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    config_path = (REPO_ROOT / args.config).resolve()
    cfg = _load_config(config_path)

    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = cfg.output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    per_seed_rows: list[dict[str, Any]] = []
    per_attempt_rows: list[dict[str, Any]] = []

    for seed in cfg.seeds:
        examples = load_pilot_examples(cfg.dataset, cfg.subset_size, seed)
        example_ids = [str(e.example_id) for e in examples]
        cheap = {str(e.example_id): cheap_input_proxy(e.question, cfg) for e in examples}

        max_budget = int(max(cfg.budget_multipliers) * len(example_ids))
        bank = _build_attempt_bank(example_ids, [cheap[eid] for eid in example_ids], seed, max_budget)

        for mult in cfg.budget_multipliers:
            budget = int(mult * len(example_ids))
            for policy in POLICIES:
                summary, attempts = _run_single_policy(
                    policy=policy,
                    example_ids=example_ids,
                    cheap_diffs=cheap,
                    bank=bank,
                    global_budget=budget,
                    cfg=cfg,
                    seed=seed,
                )
                summary.update(
                    {
                        "baseline_id": "training_free_difficulty_proxies_mode_a",
                        "dataset": cfg.dataset,
                        "seed": seed,
                        "budget_multiplier": float(mult),
                    }
                )
                per_seed_rows.append(summary)
                for row in attempts:
                    row.update(
                        {
                            "baseline_id": "training_free_difficulty_proxies_mode_a",
                            "dataset": cfg.dataset,
                            "seed": seed,
                            "budget_multiplier": float(mult),
                        }
                    )
                per_attempt_rows.extend(attempts)

    grouped: dict[tuple[float, str], list[dict[str, Any]]] = {}
    for r in per_seed_rows:
        grouped.setdefault((float(r["budget_multiplier"]), str(r["policy"])), []).append(r)

    comparison_rows: list[dict[str, Any]] = []
    for (mult, policy), rows in sorted(grouped.items()):
        covs = [float(x["coverage"]) for x in rows]
        corr = [float(x["pull_vs_final_proxy_rank_corr"]) for x in rows]
        comparison_rows.append(
            {
                "baseline_id": "training_free_difficulty_proxies_mode_a",
                "policy": policy,
                "dataset": cfg.dataset,
                "budget_multiplier": mult,
                "num_seeds": len(rows),
                "coverage": float(sum(covs) / len(covs)),
                "coverage_std": float(statistics.pstdev(covs)) if len(covs) > 1 else 0.0,
                "mean_pull_vs_final_proxy_rank_corr": float(sum(corr) / len(corr)),
                "status": "adapter_based",
                "control_equivalence": "adjacent",
                "comparability_scope": "query_level_global_budget_matched_substrate",
            }
        )

    # Diagnostics vs references.
    by_mult: dict[float, dict[str, dict[str, Any]]] = {}
    for r in comparison_rows:
        by_mult.setdefault(float(r["budget_multiplier"]), {})[str(r["policy"])] = r

    diagnostics: list[dict[str, Any]] = []
    for mult, rows in sorted(by_mult.items()):
        dipa = rows.get("dipa_mgl")
        if dipa is None:
            continue

        def delta(policy: str) -> float | None:
            other = rows.get(policy)
            return None if other is None else float(dipa["coverage"] - float(other["coverage"]))

        diagnostics.append(
            {
                "budget_multiplier": mult,
                "dipa_mgl_coverage": float(dipa["coverage"]),
                "delta_vs_uniform": delta("uniform"),
                "delta_vs_fixed_round_robin": delta("fixed_round_robin"),
                "delta_vs_easy_to_hard_mgl": delta("easy_to_hard_mgl"),
                "delta_vs_hard_to_easy_mgl": delta("hard_to_easy_mgl"),
                "dipa_adaptivity_signal": float(dipa["mean_pull_vs_final_proxy_rank_corr"]),
            }
        )

    avg_du = sum((d["delta_vs_uniform"] or 0.0) for d in diagnostics) / max(1, len(diagnostics))
    avg_df = sum((d["delta_vs_fixed_round_robin"] or 0.0) for d in diagnostics) / max(1, len(diagnostics))
    if avg_du > 0.02 and avg_df > 0.02:
        recommendation = "main_table_candidate_with_caveat"
    elif avg_du > -0.01:
        recommendation = "appendix_only"
    else:
        recommendation = "repo_only_not_paper_facing_yet"

    status = {
        "status": "ok",
        "baseline_id": "training_free_difficulty_proxies_mode_a",
        "classification": "adapter_based",
        "control_equivalence": "adjacent",
        "allocation_level": "query_level_sample_level_global_budget",
        "claim_boundary": "paper_inspired_matched_substrate_adapter_not_official_reproduction",
        "recommendation": recommendation,
        "run_id": run_id,
        "dataset": cfg.dataset,
    }

    _write_json(run_dir / "status.json", status)
    _write_csv(run_dir / "comparison_summary.csv", comparison_rows)
    _write_csv(run_dir / "per_seed_summary.csv", per_seed_rows)
    _write_jsonl(run_dir / "per_attempt_trace.jsonl", per_attempt_rows)
    _write_json(run_dir / "diagnostic_summary.json", {"diagnostics": diagnostics, "recommendation": recommendation})

    md = [
        "# training_free_difficulty_proxies_mode_a diagnostic report",
        "",
        f"Run ID: `{run_id}`",
        f"Dataset: `{cfg.dataset}`",
        "",
        "## Core question",
        "Is query-level DIPA-style adaptive allocation better than simple matched-budget references in this substrate?",
        "",
        "## Results by budget",
    ]
    for d in diagnostics:
        md.append(
            f"- budget_multiplier={d['budget_multiplier']}: dipa={d['dipa_mgl_coverage']:.4f}, "
            f"Δuniform={d['delta_vs_uniform']}, Δfixed_rr={d['delta_vs_fixed_round_robin']}, "
            f"Δeasy2hard={d['delta_vs_easy_to_hard_mgl']}, Δhard2easy={d['delta_vs_hard_to_easy_mgl']}, "
            f"adaptivity_signal={d['dipa_adaptivity_signal']:.4f}"
        )
    md.extend(
        [
            "",
            "## Interpretation",
            "- Positive delta vs uniform/fixed references indicates useful redistribution.",
            "- Comparison against easy-to-hard and hard-to-easy distinguishes pure ordering effects from probabilistic adaptive updates.",
            "- Adaptivity signal summarizes association between pull allocation and dynamically updated M proxies.",
            "",
            "## Recommendation",
            f"- `{recommendation}`",
        ]
    )
    (run_dir / "diagnostic_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    _write_json(
        run_dir / "manifest.json",
        {
            "script": "scripts/run_training_free_difficulty_proxies_mode_a.py",
            "config": str(config_path.relative_to(REPO_ROOT)),
            "outputs": [
                "status.json",
                "comparison_summary.csv",
                "per_seed_summary.csv",
                "per_attempt_trace.jsonl",
                "diagnostic_summary.json",
                "diagnostic_report.md",
                "manifest.json",
                "config_snapshot.json",
                "command_snapshot.txt",
            ],
        },
    )
    _write_json(run_dir / "config_snapshot.json", _read_json(config_path))
    (run_dir / "command_snapshot.txt").write_text(
        f"python scripts/run_training_free_difficulty_proxies_mode_a.py --config {config_path.relative_to(REPO_ROOT)} --run-id {run_id}\n",
        encoding="utf-8",
    )

    print(f"[ok] wrote artifacts to {run_dir}")


if __name__ == "__main__":
    main()
