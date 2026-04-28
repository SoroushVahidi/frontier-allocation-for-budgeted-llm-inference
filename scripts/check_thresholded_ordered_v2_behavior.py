from __future__ import annotations

import csv
import sys
from dataclasses import dataclass
from pathlib import Path
from types import MethodType
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.controllers import MethodResult
from experiments.scoring import ScoreConfig, SimpleBranchScorer
from experiments.semantic_diversity_diagnostic_strategies import build_semantic_diversity_diagnostic_strategies
from experiments.branching import SimulatedBranchGenerator
import random


@dataclass
class Scenario:
    name: str
    question: str
    gold: str
    direct_answers: list[str | None]
    challenger_answer: str | None
    family_count: int
    challenger_family_support: int


def _generator_factory() -> SimulatedBranchGenerator:
    return SimulatedBranchGenerator(rng=random.Random(1234), max_depth=6, finish_prob_base=0.18, answer_noise=0.1)


def _specs(budget: int = 6) -> dict[str, Any]:
    return build_semantic_diversity_diagnostic_strategies(
        generator_factory=_generator_factory,
        scorer=SimpleBranchScorer(ScoreConfig()),
        budget=budget,
    )


def _patch_direct_attempts(ctrl: Any, answers: list[str | None]) -> None:
    state = {"idx": 0}

    def _run_direct_attempt(self: Any, question: str, gold: str, idx: int, max_actions: int) -> tuple[str | None, int, list[dict[str, Any]]]:
        i = state["idx"]
        state["idx"] += 1
        answer = answers[i] if i < len(answers) else answers[-1]
        used = 0 if answer is None else min(1, max_actions)
        return answer, used, [{"attempt": i, "answer": answer}]

    ctrl._run_direct_attempt = MethodType(_run_direct_attempt, ctrl)


def _patch_frontier(ctrl: Any, challenger_answer: str | None, *, family_count: int, challenger_family_support: int) -> None:
    class _FrontierStub:
        def __init__(self, budget: int) -> None:
            self.budget = budget

        def run(self, question: str, gold_answer: str) -> MethodResult:
            sem_fams: dict[str, list[dict[str, Any]]] = {}
            if challenger_answer is not None:
                for i in range(max(family_count, challenger_family_support)):
                    group = challenger_answer if i < challenger_family_support else "noise"
                    sem_fams[f"family_{i}"] = [{"proxy_score": 0.7 - (0.04 * i), "features": {"answer_group_bucket": group}}]
            return MethodResult(
                method="frontier_stub",
                prediction=challenger_answer,
                is_correct=str(challenger_answer or "").strip() == str(gold_answer).strip(),
                actions_used=self.budget,
                expansions=self.budget,
                verifications=0,
                avg_surviving_branches=1.0,
                budget_exhausted=False,
                metadata={
                    "diagnostic_semantic_diversity": {
                        "semantic_family_count": int(family_count),
                        "family_redundancy_ratio": 0.65,
                        "semantic_families": sem_fams,
                    }
                },
            )

    ctrl.strict_controller_factory = lambda budget: _FrontierStub(budget)


def _row(method: str, scenario: Scenario, res: MethodResult) -> dict[str, Any]:
    meta = dict(res.metadata or {})
    direct_actions_used = int(meta.get("direct_actions_used", meta.get("direct_reserve_actions_used", 0)) or 0)
    frontier_actions_used = int(meta.get("frontier_actions_used", max(0, int(res.actions_used) - direct_actions_used)) or 0)
    return {
        "scenario": scenario.name,
        "method": method,
        "route_decision": meta.get("route_decision", ""),
        "final_source": meta.get("final_source", ""),
        "is_correct": int(res.is_correct),
        "actions_used": int(res.actions_used),
        "direct_actions_used": direct_actions_used,
        "frontier_actions_used": frontier_actions_used,
        "frontier_opened": int(meta.get("frontier_opened", 1 if frontier_actions_used > 0 else 0)),
        "continuation_value": float(meta.get("continuation_value", 0.0) or 0.0),
        "continuation_threshold": float(meta.get("continuation_threshold", 0.0) or 0.0),
        "commit_threshold": float(meta.get("commit_threshold", 0.0) or 0.0),
        "replacement_threshold": float(meta.get("replacement_threshold", 0.0) or 0.0),
        "semantic_family_count": int(meta.get("semantic_family_count", 0) or 0),
        "families_matured_count": int(meta.get("families_matured_count", 0) or 0),
    }


def main() -> None:
    scenarios = [
        Scenario("easy_direct_stop", "What is 12+13?", "25", ["25", "25"], "26", 2, 1),
        Scenario("empty_incumbent_open", "Compute 7 + 5", "12", [None, None], "12", 2, 2),
        Scenario("ambiguous_open", "What is 10+10?", "20", ["10", "20"], "20", 3, 2),
        Scenario("redundant_families", "A shop sells 3 identical packs plus 2 extras, total?", "11", ["10", "12"], "11", 6, 2),
        Scenario("weak_challenger_not_replace", "What is 12+13?", "25", ["25", "26"], "26", 1, 1),
        Scenario("parseable_challenger_replace", "Compute 7 + 5", "12", [None, None], "12", 2, 2),
    ]

    rows: list[dict[str, Any]] = []
    for scenario in scenarios:
        specs = _specs(budget=6)
        for method in ["direct_reserve_semantic_frontier_v1", "direct_reserve_semantic_frontier_v2_thresholded_ordered"]:
            ctrl = specs[method]
            _patch_direct_attempts(ctrl, scenario.direct_answers)
            _patch_frontier(
                ctrl,
                scenario.challenger_answer,
                family_count=scenario.family_count,
                challenger_family_support=scenario.challenger_family_support,
            )
            res = ctrl.run(scenario.question, scenario.gold)
            rows.append(_row(method, scenario, res))

    out_dir = Path("outputs/local_thresholded_ordered_v2_behavior")
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "behavior_summary.csv"
    md_path = out_dir / "behavior_summary.md"

    fields = list(rows[0].keys())
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    def _lookup(name: str, method: str) -> dict[str, Any]:
        return next(r for r in rows if r["scenario"] == name and r["method"] == method)

    easy_v1 = _lookup("easy_direct_stop", "direct_reserve_semantic_frontier_v1")
    easy_v2 = _lookup("easy_direct_stop", "direct_reserve_semantic_frontier_v2_thresholded_ordered")
    weak_v2 = _lookup("empty_incumbent_open", "direct_reserve_semantic_frontier_v2_thresholded_ordered")
    weak_challenger_v2 = _lookup("weak_challenger_not_replace", "direct_reserve_semantic_frontier_v2_thresholded_ordered")
    suspicious = [r for r in rows if r["method"].endswith("thresholded_ordered") and r["route_decision"] == "limited_frontier_challenge" and r["frontier_opened"] == 0]

    md = [
        "# Local behavior summary for direct_reserve_semantic_frontier_v2_thresholded_ordered",
        "",
        "## Quick answers",
        f"- Does v2 actually stop early on strong incumbent cases? **{'yes' if easy_v2['route_decision']=='stop_with_incumbent' and easy_v2['frontier_opened']==0 else 'no'}**.",
        f"- Does v2 open frontier on weak incumbent cases? **{'yes' if weak_v2['frontier_opened']==1 else 'no'}**.",
        f"- Does v2 use fewer actions than v1 in easy cases? **{'yes' if easy_v2['actions_used'] < easy_v1['actions_used'] else 'no'}** (v2={easy_v2['actions_used']}, v1={easy_v1['actions_used']}).",
        f"- Does thresholding prevent weak challengers from replacing the incumbent? **{'yes' if weak_challenger_v2['final_source']=='incumbent' else 'no'}**.",
        "- Which threshold path still looks suspicious? " + (
            "limited_frontier_challenge with frontier_opened=0 appears in "
            + ", ".join(sorted({str(r['scenario']) for r in suspicious}))
            if suspicious
            else "none obvious in this compact local diagnostic"
        )
        + ".",
        "",
        "## Table",
        "",
        "| scenario | method | route_decision | final_source | is_correct | actions_used | direct_actions_used | frontier_actions_used | frontier_opened | continuation_value | continuation_threshold | commit_threshold | replacement_threshold | semantic_family_count | families_matured_count |",
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        md.append(
            f"| {r['scenario']} | {r['method']} | {r['route_decision']} | {r['final_source']} | {r['is_correct']} | {r['actions_used']} | {r['direct_actions_used']} | {r['frontier_actions_used']} | {r['frontier_opened']} | {r['continuation_value']:.3f} | {r['continuation_threshold']:.3f} | {r['commit_threshold']:.3f} | {r['replacement_threshold']:.3f} | {r['semantic_family_count']} | {r['families_matured_count']} |"
        )

    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"wrote {csv_path}")
    print(f"wrote {md_path}")


if __name__ == "__main__":
    main()
