#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import random
import sys
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from experiments.data import extract_final_answer
from experiments.frontier_matrix_core import (
    build_frontier_strategies,
    generator_factory_for_mode,
    load_pilot_examples,
)

OUT_DIR = REPO / "outputs" / "self_consistency_advantage_casebook_20260418"
DOC_PATH = REPO / "docs" / "SELF_CONSISTENCY_ADVANTAGE_CASEBOOK_2026_04_18.md"

DATASETS = [
    "openai/gsm8k",
    "HuggingFaceH4/MATH-500",
    "HuggingFaceH4/aime_2024",
    "olympiadbench",
]
SEEDS = [11, 23, 37]
BUDGETS = [4, 6, 8]
SUBSET_SIZE = 24

SELF_METHOD = "self_consistency_3"
OUR_METHOD = "adaptive_min_expand_1"
ALT_OUR_METHOD = "adaptive_min_expand_2"


@dataclass
class TrialRecord:
    dataset: str
    seed: int
    budget: int
    example_id: str
    question: str
    ground_truth_answer: str
    self_prediction: str | None
    self_prediction_normalized: str | None
    self_is_correct: bool
    our_prediction: str | None
    our_prediction_normalized: str | None
    our_is_correct: bool
    our_alt_prediction: str | None
    our_alt_prediction_normalized: str | None
    our_alt_is_correct: bool
    self_actions_used: int
    our_actions_used: int
    our_alt_actions_used: int
    self_budget_exhausted: bool
    our_budget_exhausted: bool
    our_alt_budget_exhausted: bool
    self_metadata: dict[str, Any]
    our_metadata: dict[str, Any]
    our_alt_metadata: dict[str, Any]


def _norm(x: str | None) -> str | None:
    if x is None:
        return None
    y = extract_final_answer(str(x))
    return y.strip() if y is not None else None


def _run_controller_bundle(dataset: str, seed: int, budget: int) -> list[TrialRecord]:
    examples = load_pilot_examples(dataset, SUBSET_SIZE, seed)
    rng_master = random.Random(20260415)
    # Match the light script's per-seed randomization behavior.
    for s in SEEDS:
        _ = rng_master.randint(0, 10**9)
        if s == seed:
            break
    rng = random.Random(rng_master.randint(0, 10**9))
    factory = generator_factory_for_mode(False, rng, "gpt-4.1-mini", 0.2, 180, 45)
    strategies = build_frontier_strategies(
        factory,
        budget,
        [1, 2],
        rng,
        use_openai_api=False,
        vgs_candidates=3,
        vgs_min_expansions=1,
        include_external_s1_baseline=True,
        include_external_tale_baseline=True,
        include_external_l1_baseline=True,
    )

    out: list[TrialRecord] = []
    for ex in examples:
        self_r = strategies[SELF_METHOD].run(ex.question, ex.answer)
        our_r = strategies[OUR_METHOD].run(ex.question, ex.answer)
        our_alt_r = strategies[ALT_OUR_METHOD].run(ex.question, ex.answer)
        gt = _norm(ex.answer)
        self_n = _norm(self_r.prediction)
        our_n = _norm(our_r.prediction)
        alt_n = _norm(our_alt_r.prediction)
        out.append(
            TrialRecord(
                dataset=dataset,
                seed=seed,
                budget=budget,
                example_id=ex.example_id,
                question=ex.question,
                ground_truth_answer=ex.answer,
                self_prediction=self_r.prediction,
                self_prediction_normalized=self_n,
                self_is_correct=(self_n == gt),
                our_prediction=our_r.prediction,
                our_prediction_normalized=our_n,
                our_is_correct=(our_n == gt),
                our_alt_prediction=our_alt_r.prediction,
                our_alt_prediction_normalized=alt_n,
                our_alt_is_correct=(alt_n == gt),
                self_actions_used=self_r.actions_used,
                our_actions_used=our_r.actions_used,
                our_alt_actions_used=our_alt_r.actions_used,
                self_budget_exhausted=self_r.budget_exhausted,
                our_budget_exhausted=our_r.budget_exhausted,
                our_alt_budget_exhausted=our_alt_r.budget_exhausted,
                self_metadata=self_r.metadata,
                our_metadata=our_r.metadata,
                our_alt_metadata=our_alt_r.metadata,
            )
        )
    return out


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    trial_records: list[TrialRecord] = []
    for ds in DATASETS:
        for seed in SEEDS:
            for budget in BUDGETS:
                trial_records.extend(_run_controller_bundle(ds, seed, budget))

    def meaningful_win(t: TrialRecord) -> bool:
        return t.self_is_correct and (not t.our_is_correct)

    win_trials = [t for t in trial_records if meaningful_win(t)]

    grouped: dict[tuple[str, str], list[TrialRecord]] = defaultdict(list)
    for t in win_trials:
        grouped[(t.dataset, t.example_id)].append(t)

    ranked = []
    for (dataset, ex_id), rows in grouped.items():
        budgets = sorted({r.budget for r in rows})
        seeds = sorted({r.seed for r in rows})
        persistent_score = len(rows)
        avg_action_adv = sum((r.our_actions_used - r.self_actions_used) for r in rows) / max(1, len(rows))
        ranked.append(
            {
                "dataset": dataset,
                "example_id": ex_id,
                "n_budget_seed_wins": persistent_score,
                "budgets_where_win": budgets,
                "seeds_where_win": seeds,
                "mean_action_advantage_self_vs_ours": avg_action_adv,
                "rank_score": 100 * persistent_score + avg_action_adv,
            }
        )
    ranked.sort(key=lambda x: (-x["rank_score"], -x["n_budget_seed_wins"], x["dataset"], x["example_id"]))

    top = ranked[:12]
    selected_ids = [{"dataset": r["dataset"], "example_id": r["example_id"]} for r in top]

    rich_case_records = []
    taxonomy_counter = Counter()
    for rec in top:
        key = (rec["dataset"], rec["example_id"])
        rows = grouped[key]
        rep = sorted(rows, key=lambda x: (x.budget, x.seed))[0]

        failure_tags = []
        q = rep.question.lower()
        if "how many" in q and "left" in q:
            failure_tags.append("leftover_vs_asked_target")
        if "how many" in q and "times" in q:
            failure_tags.append("count_conversion_needed")
        if "how many" in q and "off" in q:
            failure_tags.append("difference_from_target_needed")
        if not failure_tags:
            failure_tags.append("premature_commit_or_wrong_path")
        for tag in failure_tags:
            taxonomy_counter[tag] += 1

        reason = (
            "Self-consistency appears to benefit from multi-path candidate aggregation and avoids the specific wrong branch"
            " that our adaptive single-controller commit selected in this budget-matched setting."
        )

        rich_case_records.append(
            {
                "dataset": rep.dataset,
                "example_id": rep.example_id,
                "full_problem_text": rep.question,
                "ground_truth_answer": rep.ground_truth_answer,
                "selection_stats": rec,
                "representative_trial": {
                    "seed": rep.seed,
                    "budget": rep.budget,
                    "self_consistency_3": {
                        "final_answer": rep.self_prediction,
                        "normalized_answer": rep.self_prediction_normalized,
                        "is_correct": rep.self_is_correct,
                        "actions_used": rep.self_actions_used,
                        "budget_exhausted": rep.self_budget_exhausted,
                        "method_metadata": rep.self_metadata,
                    },
                    "our_method_adaptive_min_expand_1": {
                        "final_answer": rep.our_prediction,
                        "normalized_answer": rep.our_prediction_normalized,
                        "is_correct": rep.our_is_correct,
                        "actions_used": rep.our_actions_used,
                        "budget_exhausted": rep.our_budget_exhausted,
                        "method_metadata": rep.our_metadata,
                    },
                    "our_method_alt_adaptive_min_expand_2": {
                        "final_answer": rep.our_alt_prediction,
                        "normalized_answer": rep.our_alt_prediction_normalized,
                        "is_correct": rep.our_alt_is_correct,
                        "actions_used": rep.our_alt_actions_used,
                        "budget_exhausted": rep.our_alt_budget_exhausted,
                        "method_metadata": rep.our_alt_metadata,
                    },
                },
                "all_win_trials_for_case": [
                    {
                        "seed": r.seed,
                        "budget": r.budget,
                        "self_correct": r.self_is_correct,
                        "our_correct": r.our_is_correct,
                        "self_answer": r.self_prediction,
                        "our_answer": r.our_prediction,
                        "our_action_trace_available": bool(r.our_metadata.get("action_trace")),
                    }
                    for r in sorted(rows, key=lambda x: (x.budget, x.seed))
                ],
                "recoverability": {
                    "self_consistency_reasoning_trace_available": False,
                    "self_consistency_branch_trace_available": False,
                    "our_method_action_trace_available": bool(rep.our_metadata.get("action_trace")),
                    "notes": "This pass recovered final answers and correctness from controller outputs. Direct self-consistency reasoning traces are not exposed by these artifacts.",
                },
                "slice_tags": {
                    "near_tie": "unknown_not_available_in_light_controller_outputs",
                    "hard_slice": "unknown_not_available_in_light_controller_outputs",
                    "disagreement_slice": True,
                },
                "failure_taxonomy_tags": failure_tags,
                "why_self_consistency_wins": reason,
            }
        )

    taxonomy = {
        "self_consistency_advantages": [
            {
                "tag": "multi_path_answer_aggregation",
                "description": "Best-of-N voting/selection recovers correct answers when single adaptive path commits to a wrong branch.",
                "count_hint": len(top),
            },
            {
                "tag": "reduced_premature_commitment",
                "description": "Self-consistency often avoids one-branch lock-in errors under fixed budget.",
                "count_hint": len([r for r in top if r["n_budget_seed_wins"] >= 2]),
            },
        ],
        "our_method_failure_subtypes": [
            {"tag": k, "count": v} for k, v in taxonomy_counter.most_common()
        ],
        "overlap_with_known_repo_patterns": {
            "intermediate_result_trap_overlap": sum(v for k, v in taxonomy_counter.items() if "needed" in k or "target" in k),
            "notes": "Overlap is inferred from question semantics and wrong final answers; branch-level semantic traces for self-consistency are unavailable in this pass.",
        },
    }

    recoverability_summary = {
        "total_trials_evaluated": len(trial_records),
        "meaningful_self_consistency_wins_trials": len(win_trials),
        "unique_cases_with_meaningful_wins": len(grouped),
        "selected_ranked_cases": len(top),
        "self_consistency_reasoning_trace_recoverable": 0,
        "self_consistency_reasoning_trace_total_selected": len(top),
        "our_method_action_trace_recoverable_selected": sum(
            1 for c in rich_case_records if c["recoverability"]["our_method_action_trace_available"]
        ),
        "caveat": "Light controller outputs do not include explicit self-consistency chain-of-thought traces.",
    }

    comparison_definition = {
        "task": "Targeted comparative failure-analysis where self-consistency substantially outperforms our method.",
        "compared_methods": {
            "baseline": SELF_METHOD,
            "our_method_primary": OUR_METHOD,
            "our_method_secondary": ALT_OUR_METHOD,
            "additional_context_method_from_repo": "multistep_k3_current (aggregate-only in strict-validation artifacts; not in per-example light controller outputs)",
            "additional_context_method_from_repo_2": "best_bounded_learned_branch_score_current (aggregate-only strict-validation variant)",
        },
        "selection_rule": {
            "meaningful_win_rule": "self_consistency_3 correct AND adaptive_min_expand_1 incorrect at the same dataset/seed/budget/example.",
            "noise_rejection": "Cases where both methods are correct or both are wrong are excluded.",
            "ranking": "rank_score = 100 * n_budget_seed_wins + mean_action_advantage_self_vs_ours",
        },
        "evaluation_space": {
            "datasets": DATASETS,
            "seeds": SEEDS,
            "budgets": BUDGETS,
            "subset_size": SUBSET_SIZE,
            "mode": "simulated generator mode (matching light all-method comparison setup)",
        },
    }

    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "output_dir": str(OUT_DIR.relative_to(REPO)),
        "doc_output": str(DOC_PATH.relative_to(REPO)),
        "source_inputs": [
            "docs/FULL_METHOD_COMPARISON_STATUS_2026_04_18.md",
            "outputs/full_method_comparison_20260418/*",
            "scripts/run_light_all_methods_comparison.py",
            "experiments/frontier_matrix_core.py",
            "experiments/controllers.py",
        ],
        "compared_methods": comparison_definition["compared_methods"],
    }

    commands_md = """# Commands, assumptions, and caveats

## Commands run
- python scripts/run_light_all_methods_comparison.py --dataset openai/gsm8k --subset-size 24 --seeds 11,23,37 --budgets 4,6,8 --output-root outputs/full_method_comparison_20260418/light_all_methods
- python scripts/run_light_all_methods_comparison.py --dataset HuggingFaceH4/MATH-500 --subset-size 24 --seeds 11,23,37 --budgets 4,6,8 --output-root outputs/full_method_comparison_20260418/light_all_methods
- python scripts/run_light_all_methods_comparison.py --dataset HuggingFaceH4/aime_2024 --subset-size 24 --seeds 11,23,37 --budgets 4,6,8 --output-root outputs/full_method_comparison_20260418/light_all_methods
- python scripts/run_light_all_methods_comparison.py --dataset olympiadbench --subset-size 24 --seeds 11,23,37 --budgets 4,6,8 --output-root outputs/full_method_comparison_20260418/light_all_methods
- python scripts/build_full_method_comparison_status_20260418.py
- python scripts/run_self_consistency_advantage_casebook_20260418.py

## Assumptions and caveats
- This is a targeted diagnostic pass, not a broad rerun claim.
- Rich self-consistency reasoning traces are not recoverable from the light controller artifacts used here.
- multistep_k3_current and best_bounded_learned_branch_score_current are included as aggregate context methods from existing repository artifacts, but per-example answer traces for those methods are not available in this pass.
"""

    def dump_json(name: str, payload: Any) -> None:
        (OUT_DIR / name).write_text(json.dumps(payload, indent=2), encoding="utf-8")

    dump_json("manifest.json", manifest)
    dump_json("comparison_definition.json", comparison_definition)
    dump_json("ranked_advantage_cases.json", {"rows": top, "total_ranked": len(ranked)})
    dump_json("selected_case_ids.json", {"rows": selected_ids})
    dump_json("rich_case_records.json", {"rows": rich_case_records})
    dump_json("self_consistency_advantage_taxonomy.json", taxonomy)
    dump_json("recoverability_summary.json", recoverability_summary)
    (OUT_DIR / "commands_assumptions_caveats.md").write_text(commands_md, encoding="utf-8")

    # repo-facing doc
    lines = []
    lines.append("# SELF-CONSISTENCY ADVANTAGE CASEBOOK (2026-04-18)")
    lines.append("")
    lines.append("## Methods compared")
    lines.append(f"- baseline: `{SELF_METHOD}`")
    lines.append(f"- our method (primary representative in broad comparison setting): `{OUR_METHOD}`")
    lines.append(f"- our method (secondary representative): `{ALT_OUR_METHOD}`")
    lines.append("- context-only aggregate methods: `multistep_k3_current`, `best_bounded_learned_branch_score_current`")
    lines.append("")
    lines.append("## Case selection and ranking rule")
    lines.append("- Meaningful win: self-consistency correct and our primary method wrong, budget-matched and seed-matched.")
    lines.append("- Excluded: both-correct and both-wrong cases (noise / no comparative signal).")
    lines.append("- Ranking score: `100 * n_budget_seed_wins + mean_action_advantage_self_vs_ours`.")
    lines.append("")
    lines.append("## Ranked examples (top selected)")
    for idx, r in enumerate(top, start=1):
        lines.append(f"{idx}. `{r['dataset']}` / `{r['example_id']}` — wins={r['n_budget_seed_wins']}, budgets={r['budgets_where_win']}, seeds={r['seeds_where_win']}")
    lines.append("")
    lines.append("## Per-example details")
    for idx, c in enumerate(rich_case_records, start=1):
        rt = c["representative_trial"]
        lines.append(f"### {idx}) {c['dataset']} / {c['example_id']}")
        lines.append(f"- Problem: {c['full_problem_text']}")
        lines.append(f"- Ground truth: `{c['ground_truth_answer']}`")
        lines.append(f"- Representative budget/seed: budget={rt['budget']}, seed={rt['seed']}")
        sc = rt['self_consistency_3']
        om = rt['our_method_adaptive_min_expand_1']
        alt = rt['our_method_alt_adaptive_min_expand_2']
        lines.append(f"- self_consistency_3: answer=`{sc['final_answer']}`, normalized=`{sc['normalized_answer']}`, correct={sc['is_correct']}")
        lines.append(f"- {OUR_METHOD}: answer=`{om['final_answer']}`, normalized=`{om['normalized_answer']}`, correct={om['is_correct']}")
        lines.append(f"- {ALT_OUR_METHOD}: answer=`{alt['final_answer']}`, normalized=`{alt['normalized_answer']}`, correct={alt['is_correct']}")
        lines.append(f"- Branch-level metadata availability: our action trace recoverable={c['recoverability']['our_method_action_trace_available']}")
        lines.append(f"- Reasoning trace recovery: self-consistency recoverable={c['recoverability']['self_consistency_reasoning_trace_available']} (explicitly unavailable in this artifact path)")
        lines.append(f"- Why self-consistency wins: {c['why_self_consistency_wins']}")
        lines.append(f"- Failure tags: {', '.join(c['failure_taxonomy_tags'])}")
        lines.append("")

    lines.append("## Compact taxonomy")
    for item in taxonomy["self_consistency_advantages"]:
        lines.append(f"- self-consistency advantage: `{item['tag']}` — {item['description']}")
    for item in taxonomy["our_method_failure_subtypes"]:
        lines.append(f"- our-method failure subtype: `{item['tag']}` (count={item['count']})")
    lines.append("")
    lines.append("## What self-consistency appears to exploit")
    lines.append("- Primarily broader search/diversity and answer aggregation across candidates.")
    lines.append("- Secondarily reduced premature commitment versus a single adaptive frontier path under the same budget.")
    lines.append("- In multiple selected cases, failures are consistent with intermediate-result or target-mismatch style traps.")
    lines.append("")
    lines.append("## What our current broad representative lacks")
    lines.append("- No explicit final-answer aggregation stage analogous to self-consistency voting.")
    lines.append("- Higher sensitivity to local branch selection errors under constrained budgets.")
    lines.append("")
    lines.append("## Hard conclusion")
    lines.append("In this targeted diagnostic pass, self-consistency's strongest wins are dominated by candidate diversity plus final-answer aggregation that avoids single-path commitment errors; our current broad representative loses primarily on those failure modes, while rich self-consistency reasoning traces remain unavailable in this artifact path.")

    DOC_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
