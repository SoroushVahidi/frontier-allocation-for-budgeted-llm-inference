#!/usr/bin/env python3
"""Difficulty-adaptive budget allocation baseline for new-paper frontier allocation."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import re
import statistics
import sys
from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.frontier_matrix_core import (
    build_frontier_strategies,
    evaluate_strategies_on_examples,
    generator_factory_for_mode,
    load_pilot_examples,
)

FAMILIES = [
    "reasoning_greedy",
    "self_consistency_3",
    "reasoning_beam2",
    "adaptive_min_expand_0",
    "adaptive_min_expand_1",
    "adaptive_min_expand_2",
    "verifier_guided_search",
    "program_of_thought",
]
PRIMARY_METHOD = "adaptive_min_expand_1"


class ConstantDifficultyModel:
    def __init__(self, p_hard: float):
        self.p_hard = p_hard

    def predict_proba(self, questions: list[str]) -> list[float]:
        return [self.p_hard for _ in questions]


@dataclass
class DifficultyModelArtifacts:
    model: Any
    mode: str


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Difficulty-adaptive frontier allocation baseline (new-paper)")
    p.add_argument("--dataset", default="openai/gsm8k")
    p.add_argument("--subset-size", type=int, default=18)
    p.add_argument("--seed", type=int, default=29)
    p.add_argument("--budgets", default="4,6")
    p.add_argument("--calibration-ratio", type=float, default=0.5)
    p.add_argument("--adaptive-min-expand-grid", default="0,1,2")
    p.add_argument("--use-openai-api", action="store_true")
    p.add_argument("--openai-model", default="gpt-4.1-mini")
    p.add_argument("--temperature", type=float, default=0.2)
    p.add_argument("--max-output-tokens", type=int, default=180)
    p.add_argument("--timeout-seconds", type=int, default=45)
    p.add_argument("--vgs-candidates", type=int, default=3)
    p.add_argument("--vgs-min-expansions", type=int, default=1)
    p.add_argument("--output-dir", default="outputs/new_paper/difficulty_adaptive_allocation")
    return p.parse_args()


def _parse_int_list(raw: str) -> list[int]:
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def _controller_from_calib(metrics: dict[str, dict[str, float]], budget: int) -> str:
    feasible = [s for s, m in metrics.items() if float(m["avg_actions"]) <= float(budget)]
    if feasible:
        return max(feasible, key=lambda s: float(metrics[s]["accuracy"]))
    return max(metrics, key=lambda s: float(metrics[s]["accuracy"]))


def _row_index(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        out[(str(row["example_id"]), str(row["strategy"]))] = row
    return out


def _oracle_labels(rows: list[dict[str, Any]]) -> dict[str, str]:
    rank = {name: idx for idx, name in enumerate(FAMILIES)}
    by_ex: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_ex.setdefault(str(row["example_id"]), []).append(row)
    out: dict[str, str] = {}
    for ex_id, ex_rows in by_ex.items():
        best = min(
            ex_rows,
            key=lambda r: (
                0 if r["is_correct"] else 1,
                float(r["actions_used"]),
                float(r["expansions"]),
                float(r["verifications"]),
                rank.get(str(r["strategy"]), 10**9),
            ),
        )
        out[ex_id] = str(best["strategy"])
    return out


def _metrics_from_picks(picks: list[dict[str, Any]]) -> dict[str, float]:
    n = max(1, len(picks))
    acc = sum(int(bool(r["is_correct"])) for r in picks) / n
    avg_actions = sum(float(r["actions_used"]) for r in picks) / n
    avg_budget = sum(float(r["allocated_budget"]) for r in picks) / n
    unused = sum(max(0.0, float(r["allocated_budget"]) - float(r["actions_used"])) for r in picks) / n
    return {
        "accuracy": acc,
        "realized_cost": avg_actions,
        "avg_allocated_budget": avg_budget,
        "under_spend": unused,
    }


def _fit_difficulty_model(questions: list[str], hard_labels: list[int], seed: int) -> DifficultyModelArtifacts:
    pos = sum(hard_labels)
    n = max(1, len(hard_labels))
    if pos == 0 or pos == n:
        return DifficultyModelArtifacts(model=ConstantDifficultyModel(pos / n), mode="constant")
    model = make_pipeline(
        TfidfVectorizer(lowercase=True, ngram_range=(1, 2), max_features=512),
        LogisticRegression(max_iter=400, class_weight="balanced", random_state=seed),
    )
    model.fit(questions, hard_labels)
    return DifficultyModelArtifacts(model=model, mode="tfidf_logreg")


def _cheap_proxy_features(question: str) -> dict[str, float]:
    tokens = question.split()
    return {
        "char_len": float(len(question)),
        "token_len": float(len(tokens)),
        "digit_count": float(sum(ch.isdigit() for ch in question)),
        "operator_count": float(len(re.findall(r"[+\-*/=]", question))),
        "multi_step_cue": float(any(w in question.lower() for w in ["then", "after", "total", "left", "remain"])),
    }


def main() -> None:
    args = parse_args()
    rng = random.Random(args.seed)
    budgets = _parse_int_list(args.budgets)
    adaptive_grid = _parse_int_list(args.adaptive_min_expand_grid)

    examples = load_pilot_examples(args.dataset, args.subset_size, args.seed)
    split_idx = max(1, min(len(examples) - 1, int(len(examples) * args.calibration_ratio)))
    calib_examples = examples[:split_idx]
    eval_examples = examples[split_idx:]
    question_map = {str(ex.example_id): ex.question for ex in examples}

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(args.output_dir) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    gen_factory = generator_factory_for_mode(
        args.use_openai_api,
        rng,
        args.openai_model,
        args.temperature,
        args.max_output_tokens,
        args.timeout_seconds,
    )

    method_rows: list[dict[str, Any]] = []
    proxy_rows: list[dict[str, Any]] = []
    allocation_rows: list[dict[str, Any]] = []
    controller_freq_rows: list[dict[str, Any]] = []

    for budget in budgets:
        b_low = max(1, budget - 1)
        b_high = budget + 1

        per_budget: dict[int, dict[str, Any]] = {}
        for b in sorted({b_low, budget, b_high}):
            strategies_c = build_frontier_strategies(
                gen_factory,
                b,
                adaptive_grid,
                rng,
                use_openai_api=args.use_openai_api,
                vgs_candidates=args.vgs_candidates,
                vgs_min_expansions=args.vgs_min_expansions,
            )
            calib_metrics, calib_rows = evaluate_strategies_on_examples(calib_examples, strategies_c)
            strategies_e = build_frontier_strategies(
                gen_factory,
                b,
                adaptive_grid,
                rng,
                use_openai_api=args.use_openai_api,
                vgs_candidates=args.vgs_candidates,
                vgs_min_expansions=args.vgs_min_expansions,
            )
            eval_metrics, eval_rows = evaluate_strategies_on_examples(eval_examples, strategies_e)
            per_budget[b] = {
                "calib_metrics": calib_metrics,
                "calib_rows": calib_rows,
                "eval_metrics": eval_metrics,
                "eval_rows": eval_rows,
                "eval_index": _row_index(eval_rows),
                "selected": _controller_from_calib(calib_metrics, b),
            }

        base_eval_rows = per_budget[budget]["eval_rows"]
        oracle_labels = _oracle_labels(base_eval_rows)
        oracle_picks = [
            {**per_budget[budget]["eval_index"][(ex_id, strategy)], "allocated_budget": budget, "selected_controller": strategy}
            for ex_id, strategy in oracle_labels.items()
        ]
        oracle_metrics = _metrics_from_picks(oracle_picks)

        # primary method fixed budget
        primary_eval = per_budget[budget]["eval_metrics"][PRIMARY_METHOD]
        primary_metrics = {
            "accuracy": float(primary_eval["accuracy"]),
            "realized_cost": float(primary_eval["avg_actions"]),
            "avg_allocated_budget": float(budget),
            "under_spend": float(budget) - float(primary_eval["avg_actions"]),
        }

        # uniform 2-level allocation under same average budget
        eval_ids = [str(ex.example_id) for ex in eval_examples]
        n_high = len(eval_ids) // 2
        uniform_high = set(eval_ids[:n_high])

        low_controller = per_budget[b_low]["selected"]
        high_controller = per_budget[b_high]["selected"]

        uniform_picks: list[dict[str, Any]] = []
        for ex_id in eval_ids:
            alloc_b = b_high if ex_id in uniform_high else b_low
            ctrl = high_controller if alloc_b == b_high else low_controller
            row = per_budget[alloc_b]["eval_index"][(ex_id, ctrl)]
            uniform_picks.append({**row, "allocated_budget": alloc_b, "selected_controller": ctrl})

        uniform_metrics = _metrics_from_picks(uniform_picks)

        # difficulty model from calibration traces/logs at base budget
        calib_index_base = _row_index(per_budget[budget]["calib_rows"])
        calib_ids = [str(ex.example_id) for ex in calib_examples]
        calib_questions = [question_map[ex_id] for ex_id in calib_ids]
        hard_labels: list[int] = []
        for ex_id in calib_ids:
            row = calib_index_base[(ex_id, PRIMARY_METHOD)]
            hard = int((not bool(row["is_correct"])) or bool(row["budget_exhausted"]))
            hard_labels.append(hard)
            pf = _cheap_proxy_features(question_map[ex_id])
            proxy_rows.append({
                "budget": budget,
                "split": "calibration",
                "example_id": ex_id,
                **pf,
                "hard_label": hard,
                "primary_is_correct": int(bool(row["is_correct"])),
                "primary_budget_exhausted": int(bool(row["budget_exhausted"])),
                "primary_actions_used": float(row["actions_used"]),
            })

        fit = _fit_difficulty_model(calib_questions, hard_labels, seed=args.seed + budget)
        eval_questions = [question_map[str(ex.example_id)] for ex in eval_examples]
        if fit.mode == "constant":
            hard_probs = fit.model.predict_proba(eval_questions)
        else:
            hard_probs = [float(p[1]) for p in fit.model.predict_proba(eval_questions)]

        ranked = sorted(
            [(str(eval_examples[i].example_id), hard_probs[i]) for i in range(len(eval_examples))],
            key=lambda x: x[1],
            reverse=True,
        )
        diff_high = {ex_id for ex_id, _ in ranked[:n_high]}

        diff_picks: list[dict[str, Any]] = []
        for ex in eval_examples:
            ex_id = str(ex.example_id)
            alloc_b = b_high if ex_id in diff_high else b_low
            ctrl = high_controller if alloc_b == b_high else low_controller
            row = per_budget[alloc_b]["eval_index"][(ex_id, ctrl)]
            diff_picks.append({**row, "allocated_budget": alloc_b, "selected_controller": ctrl})
            pf = _cheap_proxy_features(question_map[ex_id])
            proxy_rows.append({
                "budget": budget,
                "split": "eval",
                "example_id": ex_id,
                **pf,
                "hard_label": "",
                "primary_is_correct": "",
                "primary_budget_exhausted": "",
                "primary_actions_used": "",
            })

        diff_metrics = _metrics_from_picks(diff_picks)

        for method, vals, picks in [
            ("primary_fixed", primary_metrics, [{"selected_controller": PRIMARY_METHOD}] * len(eval_examples)),
            ("uniform_two_level", uniform_metrics, uniform_picks),
            ("difficulty_adaptive_two_level", diff_metrics, diff_picks),
            ("oracle_frontier_upper", oracle_metrics, oracle_picks),
        ]:
            method_rows.append(
                {
                    "dataset": args.dataset,
                    "budget": budget,
                    "method": method,
                    "n_eval_examples": len(eval_examples),
                    "accuracy": vals["accuracy"],
                    "realized_cost": vals["realized_cost"],
                    "avg_allocated_budget": vals["avg_allocated_budget"],
                    "under_spend": vals["under_spend"],
                    "oracle_gap": oracle_metrics["accuracy"] - vals["accuracy"],
                    "difficulty_model_mode": fit.mode,
                    "selected_low_budget": low_controller,
                    "selected_high_budget": high_controller,
                }
            )
            counts: dict[str, int] = {}
            for pick in picks:
                ctrl = str(pick["selected_controller"])
                counts[ctrl] = counts.get(ctrl, 0) + 1
            for ctrl, c in sorted(counts.items()):
                controller_freq_rows.append(
                    {
                        "dataset": args.dataset,
                        "budget": budget,
                        "method": method,
                        "controller": ctrl,
                        "count": c,
                        "frequency": c / max(1, len(picks)),
                    }
                )

        for ex in eval_examples:
            ex_id = str(ex.example_id)
            allocation_rows.append(
                {
                    "dataset": args.dataset,
                    "budget": budget,
                    "example_id": ex_id,
                    "uniform_allocated_budget": b_high if ex_id in uniform_high else b_low,
                    "difficulty_allocated_budget": b_high if ex_id in diff_high else b_low,
                    "difficulty_hard_probability": next((p for i, p in ranked if i == ex_id), 0.0),
                    "uniform_selected_controller": high_controller if ex_id in uniform_high else low_controller,
                    "difficulty_selected_controller": high_controller if ex_id in diff_high else low_controller,
                }
            )

    manifest = {
        "run_id": run_id,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "dataset": args.dataset,
        "subset_size": args.subset_size,
        "seed": args.seed,
        "budgets": budgets,
        "calibration_ratio": args.calibration_ratio,
        "primary_method": PRIMARY_METHOD,
        "difficulty_proxy_rule": "hard if primary incorrect OR budget exhausted (calibration split)",
        "allocation_rule": "allocate top-half hardest queries to B+1, rest to B-1 (same average budget)",
    }
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
        if not rows:
            path.write_text("", encoding="utf-8")
            return
        with path.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)

    write_csv(run_dir / "difficulty_method_metrics.csv", method_rows)
    write_csv(run_dir / "difficulty_proxy_audit.csv", proxy_rows)
    write_csv(run_dir / "allocation_decisions.csv", allocation_rows)
    write_csv(run_dir / "selected_controller_frequencies.csv", controller_freq_rows)

    lines = [
        "# New-paper difficulty-adaptive allocation note",
        "",
        "This run adds a lightweight difficulty-adaptive budget allocator under a fixed average budget.",
        "",
        "## Difficulty proxies audited",
        "- question char/token length",
        "- digit/operator counts",
        "- simple multi-step lexical cue",
        "- calibration trace outcomes: primary correctness and budget exhaustion",
        "",
        "## Main comparison (accuracy / cost / gap / under-spend)",
    ]

    by_budget: dict[int, list[dict[str, Any]]] = {}
    for row in method_rows:
        by_budget.setdefault(int(row["budget"]), []).append(row)
    for b in sorted(by_budget):
        lines.append(f"### Budget {b}")
        for row in sorted(by_budget[b], key=lambda r: str(r["method"])):
            lines.append(
                f"- {row['method']}: acc={float(row['accuracy']):.3f}, cost={float(row['realized_cost']):.2f}, "
                f"oracle_gap={float(row['oracle_gap']):.3f}, under_spend={float(row['under_spend']):.2f}"
            )
        diff = next(r for r in by_budget[b] if r["method"] == "difficulty_adaptive_two_level")
        uni = next(r for r in by_budget[b] if r["method"] == "uniform_two_level")
        lines.append(
            f"- delta(difficulty - uniform): acc={float(diff['accuracy']) - float(uni['accuracy']):+.3f}, "
            f"under_spend={float(diff['under_spend']) - float(uni['under_spend']):+.2f}"
        )
        lines.append("")

    avg_delta = statistics.mean(
        [
            float(next(r for r in by_budget[b] if r["method"] == "difficulty_adaptive_two_level")["accuracy"])
            - float(next(r for r in by_budget[b] if r["method"] == "uniform_two_level")["accuracy"])
            for b in by_budget
        ]
    )
    lines.extend(
        [
            "## Interpretation",
            f"- Mean accuracy delta (difficulty - uniform) across budgets: {avg_delta:+.3f}.",
            "- Positive oracle gap indicates remaining frontier-allocation headroom.",
            "- Use larger splits / real API backend for stable conclusions.",
        ]
    )

    (run_dir / "difficulty_interpretation.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(str(run_dir))


if __name__ == "__main__":
    main()
