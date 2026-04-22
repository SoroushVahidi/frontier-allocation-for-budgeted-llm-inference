#!/usr/bin/env python3
"""Run an unofficial Q*-style deliberative-search adapter lane.

This lane is intentionally caveated and adapter-based:
- conceptually inspired by Q* deliberative planning,
- runnable on this repository's substrate,
- explicitly not an official Q* reproduction.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.branching import BranchState, SimulatedBranchGenerator  # noqa: E402
from experiments.controllers import MethodResult  # noqa: E402
from experiments.frontier_matrix_core import evaluate_strategies_on_examples, load_pilot_examples  # noqa: E402
from experiments.scoring import ScoreConfig, SimpleBranchScorer  # noqa: E402

DEFAULT_CONTRACT = REPO_ROOT / "configs" / "qstar_style_adapter_contract_v1.json"


@dataclass
class QStarStyleConfig:
    max_frontier_width: int
    verify_every_n_actions: int
    branch_spawn_score_threshold: float
    commit_threshold: float
    w_score: float
    w_depth_bonus: float
    w_momentum: float
    w_uncertainty_bonus: float


class QStarStyleDeliberativeSearchController:
    """Unofficial best-first/value-guided deliberative-search adapter."""

    def __init__(
        self,
        generator: SimulatedBranchGenerator,
        max_actions_per_problem: int,
        cfg: QStarStyleConfig,
    ) -> None:
        self.generator = generator
        self.max_actions = max_actions_per_problem
        self.cfg = cfg
        self.scorer = SimpleBranchScorer(ScoreConfig())

    @staticmethod
    def _answers_match(prediction: str | None, gold_answer: str) -> bool:
        if prediction is None:
            return False
        return str(prediction).strip() == str(gold_answer).strip()

    def _heuristic_value(self, branch: BranchState) -> float:
        depth_bonus = 1.0 / (1.0 + float(branch.depth))
        uncertainty_bonus = 1.0 - min(1.0, abs(float(branch.score) - 0.5) * 2.0)
        return (
            self.cfg.w_score * float(branch.score)
            + self.cfg.w_depth_bonus * depth_bonus
            + self.cfg.w_momentum * float(branch.recent_delta)
            + self.cfg.w_uncertainty_bonus * uncertainty_bonus
        )

    def run(self, question: str, gold_answer: str) -> MethodResult:
        actions = expansions = verifications = 0
        frontier: list[BranchState] = [self.generator.init_branch("qstar_style_0")]
        action_trace: list[dict[str, Any]] = []
        spawn_counter = 1

        while actions < self.max_actions and frontier:
            live = [b for b in frontier if not b.is_pruned and not b.is_done]
            if not live:
                break

            selected = max(live, key=self._heuristic_value)
            heuristic_before = self._heuristic_value(selected)
            should_verify = (
                self.cfg.verify_every_n_actions > 0
                and selected.depth > 0
                and actions > 0
                and actions % self.cfg.verify_every_n_actions == 0
            )

            if should_verify:
                self.generator.verify(selected, question)
                verifications += 1
                action = "verify"
            else:
                self.generator.expand(selected, question, gold_answer)
                expansions += 1
                action = "expand"

            actions += 1

            if (
                action == "expand"
                and actions < self.max_actions
                and len(frontier) < self.cfg.max_frontier_width
                and float(selected.score) >= self.cfg.branch_spawn_score_threshold
            ):
                sibling = self.generator.init_branch(f"qstar_style_{spawn_counter}")
                spawn_counter += 1
                frontier.append(sibling)

            ranked = sorted(frontier, key=self._heuristic_value, reverse=True)
            if len(ranked) > self.cfg.max_frontier_width:
                for stale in ranked[self.cfg.max_frontier_width :]:
                    self.generator.prune(stale)
            frontier = [b for b in ranked if not b.is_pruned]

            action_trace.append(
                {
                    "action_index": actions,
                    "action": action,
                    "selected_branch": selected.branch_id,
                    "selected_depth": selected.depth,
                    "selected_score": float(selected.score),
                    "heuristic_before": heuristic_before,
                    "frontier_size": len(frontier),
                }
            )

            done_best = max((b for b in frontier if b.is_done), key=lambda b: float(b.score), default=None)
            if done_best is not None and float(done_best.score) >= self.cfg.commit_threshold:
                break

        ranked_all = sorted(frontier, key=self._heuristic_value, reverse=True)
        best = ranked_all[0] if ranked_all else None
        prediction = best.predicted_answer if best is not None else None

        return MethodResult(
            method="qstar_style_deliberative_search",
            prediction=prediction,
            is_correct=self._answers_match(prediction, gold_answer),
            actions_used=actions,
            expansions=expansions,
            verifications=verifications,
            avg_surviving_branches=float(len(frontier)),
            budget_exhausted=actions >= self.max_actions,
            metadata={
                "unofficial": True,
                "adapter_name": "qstar_style_deliberative_search",
                "action_trace": action_trace,
                "frontier_final_size": len(frontier),
                "forbidden_claims_enforced": True,
            },
        )


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
    fields = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run unofficial Q*-style adapter lane")
    p.add_argument("--contract-config", default=str(DEFAULT_CONTRACT))
    p.add_argument("--output-root", default=None)
    p.add_argument("--run-id", default=None)
    p.add_argument("--seed", type=int, default=20260422)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    contract_path = Path(args.contract_config).resolve()
    if not contract_path.exists():
        raise FileNotFoundError(f"Missing contract config: {contract_path}")

    contract = _read_json(contract_path)
    artifact_root = contract.get("artifact_requirements", {}).get("output_root", "outputs/qstar_style_adapter")
    output_root = Path(args.output_root).resolve() if args.output_root else (REPO_ROOT / artifact_root)

    run_id = args.run_id or _utc_run_id()
    run_dir = output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    benchmark = contract.get("benchmark_contract", {})
    dataset = str(benchmark.get("dataset", "")).strip()
    seeds = [int(x) for x in benchmark.get("seeds", [])]
    budgets = [int(x) for x in benchmark.get("budgets", [])]
    subset_size = int(benchmark.get("subset_size", 0))

    if not dataset or not seeds or not budgets or subset_size <= 0:
        raise ValueError("Contract benchmark_contract is incomplete: dataset/seeds/budgets/subset_size required")

    algo = contract.get("adapter_approximation", {}).get("algorithm_defaults", {})
    weights = algo.get("heuristic_weights", {})
    adapter_cfg = QStarStyleConfig(
        max_frontier_width=int(algo.get("max_frontier_width", 3)),
        verify_every_n_actions=int(algo.get("verify_every_n_actions", 2)),
        branch_spawn_score_threshold=float(algo.get("branch_spawn_score_threshold", 0.66)),
        commit_threshold=float(algo.get("commit_threshold", 0.86)),
        w_score=float(weights.get("score", 0.62)),
        w_depth_bonus=float(weights.get("depth_bonus", 0.16)),
        w_momentum=float(weights.get("momentum", 0.12)),
        w_uncertainty_bonus=float(weights.get("uncertainty_bonus", 0.10)),
    )

    rng_master = random.Random(args.seed)
    per_example_rows: list[dict[str, Any]] = []
    comparison_rows: list[dict[str, Any]] = []

    for seed in seeds:
        examples = load_pilot_examples(dataset, subset_size, seed)
        for budget in budgets:
            rng = random.Random(rng_master.randint(0, 10**9))
            strategies = {
                "qstar_style_deliberative_search": QStarStyleDeliberativeSearchController(
                    generator=SimulatedBranchGenerator(rng=rng, max_depth=7, finish_prob_base=0.16, answer_noise=0.12),
                    max_actions_per_problem=budget,
                    cfg=adapter_cfg,
                ),
            }
            metrics, rows = evaluate_strategies_on_examples(examples, strategies)
            summary = metrics["qstar_style_deliberative_search"]
            comparison_rows.append(
                {
                    "baseline_id": "qstar_style_adapter",
                    "method": "qstar_style_deliberative_search",
                    "dataset": dataset,
                    "seed": seed,
                    "budget_actions": budget,
                    "n_examples": int(summary["n_examples"]),
                    "accuracy": float(summary["accuracy"]),
                    "avg_actions": float(summary["avg_actions"]),
                    "avg_expansions": float(summary["avg_expansions"]),
                    "avg_verifications": float(summary["avg_verifications"]),
                    "budget_exhaustion_rate": float(summary["budget_exhaustion_rate"]),
                    "comparability_scope": "unofficial_caveated_adapter_only",
                }
            )
            for row in rows:
                per_example_rows.append(
                    {
                        "dataset": dataset,
                        "seed": seed,
                        "budget_actions": budget,
                        "example_id": row["example_id"],
                        "is_correct": bool(row["is_correct"]),
                        "actions_used": int(row["actions_used"]),
                        "expansions": int(row["expansions"]),
                        "verifications": int(row["verifications"]),
                        "budget_exhausted": bool(row["budget_exhausted"]),
                        "metadata": row["metadata"],
                    }
                )

    avg_accuracy = sum(float(r["accuracy"]) for r in comparison_rows) / max(1, len(comparison_rows))
    status = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "baseline_id": "qstar_style_adapter",
        "classification": "unofficial_adapter_caveated",
        "control_equivalence": "direct_family_caveated",
        "conceptual_source": contract.get("conceptual_source", {}),
        "allowed_claims": contract.get("allowed_claims", []),
        "forbidden_claims": contract.get("forbidden_claims", []),
        "official_reproduction_claim": False,
        "ready": bool(comparison_rows),
    }

    summary = {
        "run_id": run_id,
        "baseline_id": "qstar_style_adapter",
        "dataset": dataset,
        "num_seed_budget_cells": len(comparison_rows),
        "mean_accuracy": avg_accuracy,
        "output_dir": str(run_dir.relative_to(REPO_ROOT)),
    }

    summary_md = "\n".join(
        [
            "# Q*-style adapter summary (unofficial)",
            "",
            f"- Run ID: `{run_id}`",
            "- Adapter lane: `qstar_style_adapter`",
            "- Method: `qstar_style_deliberative_search`",
            f"- Dataset slice: `{dataset}` (`subset_size={subset_size}`)",
            f"- Evaluated seed/budget cells: `{len(comparison_rows)}`",
            f"- Mean accuracy across cells: `{avg_accuracy:.4f}`",
            "",
            "## Caveat guardrail",
            "",
            "- This is an **unofficial, caveated Q*-style adapter**.",
            "- It is inspired by the Q* paper's deliberative-search perspective but is **not** an official reproduction.",
            "- Do not merge these results into tables that imply official Q* reproduction.",
        ]
    ) + "\n"

    commands = [
        "python scripts/run_qstar_style_adapter.py "
        f"--contract-config {contract_path.relative_to(REPO_ROOT)} --run-id {run_id}"
    ]

    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "script": "scripts/run_qstar_style_adapter.py",
        "output_dir": str(run_dir.relative_to(REPO_ROOT)),
        "commands": commands,
        "artifacts": contract.get("artifact_requirements", {}).get("required_outputs", []),
    }

    config_snapshot = {
        "contract_config_path": str(contract_path.relative_to(REPO_ROOT)),
        "contract": contract,
        "args": {
            "seed": args.seed,
            "output_root": str(output_root),
        },
    }

    _write_json(run_dir / "status.json", status)
    _write_json(run_dir / "summary.json", summary)
    (run_dir / "summary.md").write_text(summary_md, encoding="utf-8")
    _write_json(run_dir / "manifest.json", manifest)
    _write_json(run_dir / "config_snapshot.json", config_snapshot)
    (run_dir / "commands_snapshot.txt").write_text("\n".join(commands) + "\n", encoding="utf-8")
    _write_csv(run_dir / "comparison_summary.csv", comparison_rows)
    _write_json(run_dir / "per_example_rows.json", per_example_rows)

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
