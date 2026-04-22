#!/usr/bin/env python3
"""Run a conservative MODE A adapter baseline for
"Learning How Hard to Think: Input-Adaptive Allocation of LM Computation".

This runner provides a paper-usable sanity bundle under matched substrate:
- learning_how_hard_to_think_mode_a (paper-inspired adaptive best-of-k allocator),
- uniform matched-compute allocator,
- fixed-k allocator,
- easy-to-hard redistribution,
- hard-to-easy redistribution.

Claim boundary: adapter-based comparator only; not an official reproduction.
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

from experiments.controllers import BestOfNController  # noqa: E402
from experiments.frontier_matrix_core import generator_factory_for_mode, load_pilot_examples  # noqa: E402
from experiments.scoring import ScoreConfig, SimpleBranchScorer  # noqa: E402

DEFAULT_CONFIG = REPO_ROOT / "configs" / "learning_how_hard_to_think_mode_a_v1.json"

POLICIES = [
    "learning_how_hard_to_think_mode_a",
    "uniform_matched_compute",
    "fixed_k_matched_compute",
    "easy_to_hard_ordering",
    "hard_to_easy_ordering",
]


@dataclass
class AdapterConfig:
    dataset: str
    subset_size: int
    seeds: list[int]
    budgets: list[int]
    use_openai_api: bool
    api_provider: str
    model: str
    temperature: float
    max_output_tokens: int
    timeout_seconds: int
    candidate_action_cap: int
    min_k: int
    max_k: int
    difficulty_length_weight: float
    difficulty_digit_weight: float
    difficulty_symbol_weight: float
    difficulty_multi_step_weight: float
    weighted_temp: float
    weighted_alpha: float
    output_root: Path


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
    cols: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row.keys():
            if key not in seen:
                cols.append(key)
                seen.add(key)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        writer.writerows(rows)


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _stable_seed(*parts: Any) -> int:
    h = hashlib.sha256("||".join(str(x) for x in parts).encode("utf-8")).hexdigest()
    return int(h[:16], 16)


def _load_config(path: Path) -> AdapterConfig:
    raw = _read_json(path)
    dataset = raw.get("dataset", {})
    model = raw.get("model", {})
    budget = raw.get("budget", {})
    adapter = raw.get("adapter", {})
    diff = adapter.get("difficulty_estimator", {})
    weighted = adapter.get("weighted_allocator", {})
    return AdapterConfig(
        dataset=str(dataset.get("name", "openai/gsm8k")),
        subset_size=int(dataset.get("subset_size", 32)),
        seeds=[int(s) for s in dataset.get("seeds", [11, 23])],
        budgets=[int(b) for b in budget.get("grid", [4, 6])],
        use_openai_api=bool(model.get("use_openai_api", False)),
        api_provider=str(model.get("provider", "openai")),
        model=str(model.get("name", "gpt-4.1-mini")),
        temperature=float(model.get("temperature", 0.2)),
        max_output_tokens=int(model.get("max_output_tokens", 180)),
        timeout_seconds=int(model.get("timeout_seconds", 45)),
        candidate_action_cap=max(1, int(adapter.get("candidate_action_cap", 2))),
        min_k=max(1, int(adapter.get("min_k", 1))),
        max_k=max(1, int(adapter.get("max_k", 4))),
        difficulty_length_weight=float(diff.get("length_weight", 0.55)),
        difficulty_digit_weight=float(diff.get("digit_weight", 0.20)),
        difficulty_symbol_weight=float(diff.get("symbol_weight", 0.15)),
        difficulty_multi_step_weight=float(diff.get("multi_step_weight", 0.10)),
        weighted_temp=max(0.05, float(weighted.get("temperature", 0.7))),
        weighted_alpha=max(0.0, float(weighted.get("mix_alpha", 0.75))),
        output_root=REPO_ROOT / str(raw.get("output", {}).get("root_dir", "outputs/learning_how_hard_to_think_mode_a")),
    )


def difficulty_score(question: str, cfg: AdapterConfig) -> float:
    text = question or ""
    length_term = min(1.0, len(text) / 240.0)
    digit_term = min(1.0, sum(1 for ch in text if ch.isdigit()) / 12.0)
    symbol_term = min(1.0, sum(1 for ch in text if ch in "+-*/%=<>") / 8.0)
    multistep_markers = [" then ", " after ", " each ", " total ", " remaining ", " twice ", " difference "]
    multi_step_hits = sum(1 for token in multistep_markers if token in text.lower())
    multi_step_term = min(1.0, multi_step_hits / 4.0)
    score = (
        cfg.difficulty_length_weight * length_term
        + cfg.difficulty_digit_weight * digit_term
        + cfg.difficulty_symbol_weight * symbol_term
        + cfg.difficulty_multi_step_weight * multi_step_term
    )
    return float(max(0.0, min(1.0, score)))


def _weighted_round_robin(weights: list[float], extra_slots: int, caps_remaining: list[int]) -> list[int]:
    n = len(weights)
    give = [0] * n
    for _ in range(extra_slots):
        feasible = [i for i in range(n) if caps_remaining[i] > 0]
        if not feasible:
            break
        idx = max(feasible, key=lambda i: (weights[i] / (1 + give[i]), weights[i], -i))
        give[idx] += 1
        caps_remaining[idx] -= 1
    return give


def allocate_candidate_slots(
    policy: str,
    hardness: list[float],
    budget_actions_per_example: int,
    cfg: AdapterConfig,
) -> tuple[list[int], dict[str, Any]]:
    n = len(hardness)
    target_total_actions = n * budget_actions_per_example
    target_total_slots = target_total_actions // cfg.candidate_action_cap
    action_slack = target_total_actions - target_total_slots * cfg.candidate_action_cap

    if target_total_slots < n * cfg.min_k:
        raise ValueError("Budget too small for configured min_k under candidate_action_cap.")

    base = [cfg.min_k] * n
    extra_slots = target_total_slots - sum(base)
    caps_remaining = [max(0, cfg.max_k - cfg.min_k) for _ in range(n)]

    if policy == "fixed_k_matched_compute":
        # Strict fixed-k: choose largest uniform k that fits all; keep remaining slots unspent.
        k = min(cfg.max_k, target_total_slots // n)
        slots = [k] * n
    elif policy == "uniform_matched_compute":
        slots = base[:]
        idx = 0
        while extra_slots > 0:
            j = idx % n
            if slots[j] < cfg.max_k:
                slots[j] += 1
                extra_slots -= 1
            idx += 1
            if idx > n * cfg.max_k * 3:
                break
    elif policy in {"easy_to_hard_ordering", "hard_to_easy_ordering"}:
        reverse = policy == "hard_to_easy_ordering"
        order = sorted(range(n), key=lambda i: (hardness[i], -i), reverse=reverse)
        slots = base[:]
        idx = 0
        while extra_slots > 0 and order:
            j = order[idx % n]
            if slots[j] < cfg.max_k:
                slots[j] += 1
                extra_slots -= 1
            idx += 1
            if idx > n * cfg.max_k * 3:
                break
    elif policy == "learning_how_hard_to_think_mode_a":
        slots = base[:]
        centered = [max(1e-6, h) for h in hardness]
        max_h = max(centered) if centered else 1.0
        normalized = [h / max_h for h in centered]
        soft = [math.exp(v / cfg.weighted_temp) for v in normalized]
        mix = [(cfg.weighted_alpha * s) + ((1.0 - cfg.weighted_alpha) * nrm) for s, nrm in zip(soft, normalized)]
        add = _weighted_round_robin(mix, extra_slots, caps_remaining)
        slots = [s + a for s, a in zip(slots, add)]
    else:
        raise ValueError(f"Unknown policy: {policy}")

    planned_total_slots = sum(slots)
    planned_total_actions = planned_total_slots * cfg.candidate_action_cap
    return slots, {
        "policy": policy,
        "target_total_actions": target_total_actions,
        "target_total_slots": target_total_slots,
        "action_slack_from_unit_conversion": action_slack,
        "planned_total_slots": planned_total_slots,
        "planned_total_actions": planned_total_actions,
        "effective_unspent_actions": target_total_actions - planned_total_actions,
        "mean_k": float(sum(slots) / max(1, n)),
        "max_k": int(max(slots) if slots else 0),
        "min_k": int(min(slots) if slots else 0),
    }


def _spearman_like_rank_corr(x: list[float], y: list[float]) -> float:
    if len(x) != len(y) or len(x) < 2:
        return 0.0
    x_rank = {i: r for r, i in enumerate(sorted(range(len(x)), key=lambda k: x[k]))}
    y_rank = {i: r for r, i in enumerate(sorted(range(len(y)), key=lambda k: y[k]))}
    d2 = sum((x_rank[i] - y_rank[i]) ** 2 for i in range(len(x)))
    n = len(x)
    denom = n * (n * n - 1)
    return float(1 - (6 * d2 / denom)) if denom else 0.0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run Learning-How-Hard-To-Think MODE A adapter sanity bundle")
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

    scorer = SimpleBranchScorer(ScoreConfig())

    per_example_rows: list[dict[str, Any]] = []
    per_seed_rows: list[dict[str, Any]] = []

    for seed in cfg.seeds:
        examples = load_pilot_examples(cfg.dataset, cfg.subset_size, seed)
        hardness = [difficulty_score(ex.question, cfg) for ex in examples]

        for budget in cfg.budgets:
            for policy in POLICIES:
                slots, alloc_meta = allocate_candidate_slots(policy, hardness, budget, cfg)
                correct = 0
                actions_used: list[int] = []
                for i, ex in enumerate(examples):
                    k_i = int(max(cfg.min_k, min(cfg.max_k, slots[i])))
                    max_actions = k_i * cfg.candidate_action_cap

                    ex_seed = _stable_seed("lhh2", seed, budget, ex.example_id)
                    ex_rng = random.Random(ex_seed)
                    generator = generator_factory_for_mode(
                        cfg.use_openai_api,
                        ex_rng,
                        cfg.model,
                        cfg.temperature,
                        cfg.max_output_tokens,
                        cfg.timeout_seconds,
                        cfg.api_provider,
                    )()

                    controller = BestOfNController(generator, scorer, max_actions_per_problem=max_actions, n_candidates=k_i)
                    result = controller.run(ex.question, ex.answer)
                    correct += int(result.is_correct)
                    actions_used.append(int(result.actions_used))

                    per_example_rows.append(
                        {
                            "baseline_id": "learning_how_hard_to_think_mode_a",
                            "policy": policy,
                            "dataset": cfg.dataset,
                            "seed": seed,
                            "budget_actions_per_example": budget,
                            "example_id": ex.example_id,
                            "question_length": len(ex.question),
                            "difficulty_score": hardness[i],
                            "allocated_k": k_i,
                            "planned_actions": max_actions,
                            "actions_used": int(result.actions_used),
                            "is_correct": bool(result.is_correct),
                        }
                    )

                n = len(examples)
                acc = float(correct / max(1, n))
                per_seed_rows.append(
                    {
                        "baseline_id": "learning_how_hard_to_think_mode_a",
                        "policy": policy,
                        "dataset": cfg.dataset,
                        "seed": seed,
                        "budget_actions_per_example": budget,
                        "n_examples": n,
                        "accuracy": acc,
                        "mean_allocated_k": float(sum(slots) / max(1, n)),
                        "mean_actions_used": float(sum(actions_used) / max(1, len(actions_used))),
                        "planned_total_actions": int(alloc_meta["planned_total_actions"]),
                        "target_total_actions": int(alloc_meta["target_total_actions"]),
                        "effective_unspent_actions": int(alloc_meta["effective_unspent_actions"]),
                        "alloc_hardness_rank_corr": _spearman_like_rank_corr(hardness, [float(v) for v in slots]),
                    }
                )

    grouped: dict[tuple[int, str], list[dict[str, Any]]] = {}
    for row in per_seed_rows:
        grouped.setdefault((int(row["budget_actions_per_example"]), str(row["policy"])), []).append(row)

    comparison_rows: list[dict[str, Any]] = []
    for (budget, policy), rows in sorted(grouped.items()):
        accs = [float(r["accuracy"]) for r in rows]
        ks = [float(r["mean_allocated_k"]) for r in rows]
        acts = [float(r["mean_actions_used"]) for r in rows]
        rankcorr = [float(r["alloc_hardness_rank_corr"]) for r in rows]
        unspent = [float(r["effective_unspent_actions"]) for r in rows]
        comparison_rows.append(
            {
                "baseline_id": "learning_how_hard_to_think_mode_a",
                "policy": policy,
                "dataset": cfg.dataset,
                "budget_actions_per_example": budget,
                "num_seeds": len(rows),
                "accuracy": float(sum(accs) / len(accs)),
                "accuracy_std": float(statistics.pstdev(accs)) if len(accs) > 1 else 0.0,
                "mean_allocated_k": float(sum(ks) / len(ks)),
                "mean_actions_used": float(sum(acts) / len(acts)),
                "mean_alloc_hardness_rank_corr": float(sum(rankcorr) / len(rankcorr)),
                "mean_effective_unspent_actions": float(sum(unspent) / len(unspent)),
                "status": "adapter_based",
                "control_equivalence": "adjacent",
                "comparability_scope": "matched_substrate_mode_a_sanity_bundle",
            }
        )

    by_budget = {}
    for row in comparison_rows:
        by_budget.setdefault(int(row["budget_actions_per_example"]), {})[str(row["policy"])] = row

    diagnostics: list[dict[str, Any]] = []
    for budget, rows in sorted(by_budget.items()):
        main_row = rows.get("learning_how_hard_to_think_mode_a")
        if main_row is None:
            continue
        def delta(other: str) -> float | None:
            r = rows.get(other)
            return None if r is None else float(main_row["accuracy"] - float(r["accuracy"]))

        diagnostics.append(
            {
                "budget_actions_per_example": budget,
                "mode_a_accuracy": float(main_row["accuracy"]),
                "delta_vs_uniform": delta("uniform_matched_compute"),
                "delta_vs_fixed_k": delta("fixed_k_matched_compute"),
                "delta_vs_easy_to_hard": delta("easy_to_hard_ordering"),
                "delta_vs_hard_to_easy": delta("hard_to_easy_ordering"),
                "mode_a_alloc_hardness_rank_corr": float(main_row["mean_alloc_hardness_rank_corr"]),
                "mode_a_unspent_actions": float(main_row["mean_effective_unspent_actions"]),
                "interpretation": (
                    "If mode_a beats hard_to_easy and easy_to_hard consistently, gains likely involve weighted redistribution details, "
                    "not just monotone sorting."
                ),
            }
        )

    overall_status = "ok"
    recommendation = "appendix_only"
    if diagnostics:
        avg_delta_uniform = sum((d["delta_vs_uniform"] or 0.0) for d in diagnostics) / len(diagnostics)
        avg_delta_fixed = sum((d["delta_vs_fixed_k"] or 0.0) for d in diagnostics) / len(diagnostics)
        if avg_delta_uniform > 0.01 and avg_delta_fixed > 0.01:
            recommendation = "main_table_candidate_with_caveat"
        elif avg_delta_uniform > -0.01:
            recommendation = "appendix_only"
        else:
            recommendation = "repo_only_not_paper_facing_yet"

    status = {
        "status": overall_status,
        "baseline_id": "learning_how_hard_to_think_mode_a",
        "classification": "adapter_based",
        "control_equivalence": "adjacent",
        "claim_boundary": "paper_inspired_matched_substrate_comparator_not_official_reproduction",
        "run_id": run_id,
        "dataset": cfg.dataset,
        "policies": POLICIES,
        "recommendation": recommendation,
    }

    _write_json(run_dir / "status.json", status)
    _write_csv(run_dir / "comparison_summary.csv", comparison_rows)
    _write_csv(run_dir / "per_seed_summary.csv", per_seed_rows)
    _write_jsonl(run_dir / "per_example_results.jsonl", per_example_rows)
    _write_json(run_dir / "diagnostic_summary.json", {"diagnostics": diagnostics, "recommendation": recommendation})

    report_lines = [
        "# Learning How Hard to Think MODE A sanity diagnostic report",
        "",
        f"Run ID: `{run_id}`",
        f"Dataset: `{cfg.dataset}`",
        "",
        "## Comparator policies",
        "- learning_how_hard_to_think_mode_a",
        "- uniform_matched_compute",
        "- fixed_k_matched_compute",
        "- easy_to_hard_ordering",
        "- hard_to_easy_ordering",
        "",
        "## Diagnostic answers",
    ]
    for d in diagnostics:
        report_lines.append(
            f"- budget={d['budget_actions_per_example']}: mode_a={d['mode_a_accuracy']:.4f}, "
            f"Δuniform={d['delta_vs_uniform']}, Δfixed_k={d['delta_vs_fixed_k']}, "
            f"Δeasy2hard={d['delta_vs_easy_to_hard']}, Δhard2easy={d['delta_vs_hard_to_easy']}, "
            f"alloc_corr={d['mode_a_alloc_hardness_rank_corr']:.4f}"
        )
    report_lines.extend(
        [
            "",
            "## Candid recommendation",
            f"- `{recommendation}`",
            "",
            "Interpretation key:",
            "- Gains/losses vs uniform/fixed-k indicate whether adaptive redistribution helps under matched substrate.",
            "- easy-to-hard vs hard-to-easy contrasts directionality sensitivity.",
            "- allocation-hardness rank correlation checks whether policy truly reallocates toward predicted harder items.",
        ]
    )
    (run_dir / "diagnostic_report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    _write_json(
        run_dir / "manifest.json",
        {
            "script": "scripts/run_learning_how_hard_to_think_mode_a.py",
            "config": str(config_path.relative_to(REPO_ROOT)),
            "outputs": [
                "status.json",
                "comparison_summary.csv",
                "per_seed_summary.csv",
                "per_example_results.jsonl",
                "diagnostic_summary.json",
                "diagnostic_report.md",
                "manifest.json",
                "config_snapshot.json",
                "command_snapshot.txt",
            ],
            "caveat": "Adapter-based MODE A comparator only; no official method reproduction claim.",
        },
    )
    _write_json(run_dir / "config_snapshot.json", _read_json(config_path))
    (run_dir / "command_snapshot.txt").write_text(
        f"python scripts/run_learning_how_hard_to_think_mode_a.py --config {config_path.relative_to(REPO_ROOT)} --run-id {run_id}\n",
        encoding="utf-8",
    )
    print(f"[ok] wrote MODE A sanity bundle artifacts to {run_dir}")


if __name__ == "__main__":
    main()
