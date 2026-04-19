#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.data import extract_final_answer
from experiments.frontier_matrix_core import build_frontier_strategies, generator_factory_for_mode, load_pilot_examples

OUR_METHOD = "broad_diversity_aggregation_strong_v1"
BASELINES = [
    "self_consistency_3",
    "adaptive_min_expand_1",
    "selective_sc_hybrid_v1",
    "broad_diversity_aggregation_v1",
    "broad_diversity_aggregation_strong_v1_diversity_needed_gate",
]


@dataclass
class ExampleMethodResult:
    dataset: str
    seed: int
    budget: int
    example_id: str
    question: str
    gold_answer: str
    method: str
    prediction: str | None
    normalized_prediction: str | None
    normalized_gold: str | None
    is_correct: bool
    actions_used: int
    expansions: int
    verifications: int
    budget_exhausted: bool
    metadata: dict[str, Any]


def _parse_int_list(raw: str) -> list[int]:
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def _norm(x: str | None) -> str | None:
    if x is None:
        return None
    y = extract_final_answer(str(x))
    if y is None:
        y = str(x)
    y = y.strip()
    return y if y else None


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _mean(xs: list[float]) -> float:
    return float(sum(xs) / len(xs)) if xs else 0.0


def _std(xs: list[float]) -> float:
    return float(statistics.pstdev(xs)) if len(xs) > 1 else 0.0


def _method_rank_by_accuracy(per_method_metrics: dict[str, dict[str, float]]) -> dict[str, int]:
    ordered = sorted(per_method_metrics.items(), key=lambda kv: kv[1]["accuracy"], reverse=True)
    return {m: idx for idx, (m, _) in enumerate(ordered)}


def _contains_numeric(s: str | None) -> bool:
    if not s:
        return False
    return any(ch.isdigit() for ch in s)


def classify_failure(our: ExampleMethodResult, winners: list[ExampleMethodResult]) -> tuple[str, str, str, str]:
    meta = our.metadata or {}
    unique_groups = _safe_int(meta.get("unique_answer_groups_seen"), 0)
    entropy = _safe_float(meta.get("answer_support_entropy"), 0.0)
    support_frac = _safe_float(meta.get("group_support_fraction"), 0.0)
    margin = _safe_float(meta.get("answer_group_margin"), 0.0)
    forced_explore_rate = _safe_float(meta.get("forced_explore_rate"), 0.0)
    commit_triggered = bool(meta.get("commit_triggered", False))
    gate_count = _safe_int(meta.get("gate_intervention_count"), 0)

    if (our.prediction is None) or (not _contains_numeric(our.prediction)):
        return (
            "incomplete_or_non_terminal",
            "verification_or_completion_gap",
            "verification",
            "better_verification",
        )

    if our.budget_exhausted or (not commit_triggered and our.actions_used >= max(1, our.budget - 1)):
        return (
            "wrong_commit_timing",
            "late_or_missed_commit",
            "commit",
            "better_commit_timing",
        )

    if unique_groups <= 1 or entropy < 0.25:
        return (
            "insufficient_diversity_realized",
            "single_or_low_diversity_answer_group",
            "expansion",
            "broader_search_coverage",
        )

    if unique_groups >= 3 and entropy >= 0.95 and support_frac < 0.6:
        return (
            "bad_diversity_realized",
            "high_entropy_low_quality_diversity",
            "expansion",
            "lower_noise_sensitivity",
        )

    if margin <= 0.20:
        return (
            "ambiguity_near_tie_failure",
            "near_tie_support_ambiguity",
            "scoring",
            "better_exploitation",
        )

    if bool(meta.get("aggregation_used", False)) and support_frac < 0.62:
        return (
            "wrong_aggregation",
            "weak_support_group_selected",
            "aggregation",
            "better_answer_agreement",
        )

    if unique_groups >= 2 and support_frac >= 0.62 and entropy >= 0.35:
        return (
            "ranking_after_diversity_failure",
            "correct_candidate_not_selected",
            "scoring",
            "better_exploitation",
        )

    if our.verifications == 0 and any(w.verifications > 0 for w in winners):
        return (
            "verification_failure",
            "winner_used_verification_signal",
            "verification",
            "better_verification",
        )

    if gate_count > 0:
        return (
            "defer_or_fallback_failure",
            "gated_or_fallback_path_instability",
            "defer_or_fallback",
            "lower_noise_sensitivity",
        )

    return (
        "wrong_final_answer",
        "incorrect_final_answer",
        "scoring",
        "better_exploitation",
    )


def _pattern_hypothesis(group: str, meta: dict[str, Any], question: str) -> str:
    q = question.lower()
    if group == "insufficient_diversity_realized":
        return "answer-group concentration too early; useful alternative branch likely never realized"
    if group == "wrong_aggregation":
        return "current aggregation may overcount correlated wrong branches"
    if group == "ranking_after_diversity_failure":
        return "correct branch likely surfaced but ranking/selection preferred wrong high-support branch"
    if group == "ambiguity_near_tie_failure":
        return "near-tie scoring ambiguity with unstable top-group margin"
    if group == "bad_diversity_realized":
        return "low-quality diversity: branch spread increased without reliable evidence"
    if "geometry" in q or "triangle" in q or "circle" in q:
        return "geometry-like alternate construction may be missing in chosen branch"
    if "how many" in q or "total" in q:
        return "hidden multi-step arithmetic/case split likely under-resolved"
    return "selection/calibration mismatch between branch quality and final answer support"


def run_eval(args: argparse.Namespace) -> dict[str, Any]:
    datasets = [d.strip() for d in args.datasets.split(",") if d.strip()]
    seeds = _parse_int_list(args.seeds)
    budgets = _parse_int_list(args.budgets)
    adaptive_grid = _parse_int_list(args.adaptive_grid)

    methods = [OUR_METHOD, *BASELINES]
    out_dir = REPO_ROOT / args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    rng_master = random.Random(args.master_seed)
    rows: list[ExampleMethodResult] = []

    for dataset in datasets:
        for seed in seeds:
            examples = load_pilot_examples(dataset, args.subset_size, seed)
            rng = random.Random(rng_master.randint(0, 10**9))
            factory = generator_factory_for_mode(False, rng, args.model, args.temperature, args.max_output_tokens, args.timeout_seconds)
            for budget in budgets:
                strategies = build_frontier_strategies(
                    factory,
                    budget,
                    adaptive_grid,
                    rng,
                    use_openai_api=False,
                    include_selective_sc_hybrid_methods=True,
                    include_broad_diversity_aggregation_methods=True,
                )
                strategies = {k: v for k, v in strategies.items() if k in methods}
                for ex in examples:
                    for method_name, controller in strategies.items():
                        r = controller.run(ex.question, ex.answer)
                        rows.append(
                            ExampleMethodResult(
                                dataset=dataset,
                                seed=seed,
                                budget=budget,
                                example_id=ex.example_id,
                                question=ex.question,
                                gold_answer=ex.answer,
                                method=method_name,
                                prediction=r.prediction,
                                normalized_prediction=_norm(r.prediction),
                                normalized_gold=_norm(ex.answer),
                                is_correct=bool(r.is_correct),
                                actions_used=int(r.actions_used),
                                expansions=int(r.expansions),
                                verifications=int(r.verifications),
                                budget_exhausted=bool(r.budget_exhausted),
                                metadata=r.metadata,
                            )
                        )

    rows_path = out_dir / "per_example_results.jsonl"
    rows_path.write_text("\n".join(json.dumps(asdict(r), ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")

    by_method: dict[str, list[ExampleMethodResult]] = defaultdict(list)
    for r in rows:
        by_method[r.method].append(r)

    per_method_metrics: dict[str, dict[str, float]] = {}
    for method in methods:
        mr = by_method.get(method, [])
        n = max(1, len(mr))
        per_method_metrics[method] = {
            "n_examples": float(len(mr)),
            "accuracy": float(sum(int(x.is_correct) for x in mr) / n),
            "avg_actions": float(sum(x.actions_used for x in mr) / n),
            "avg_expansions": float(sum(x.expansions for x in mr) / n),
            "avg_verifications": float(sum(x.verifications for x in mr) / n),
            "budget_exhaustion_rate": float(sum(int(x.budget_exhausted) for x in mr) / n),
        }

    rank = _method_rank_by_accuracy(per_method_metrics)

    # aligned by matched key
    aligned: dict[tuple[str, int, int, str], dict[str, ExampleMethodResult]] = defaultdict(dict)
    for r in rows:
        key = (r.dataset, int(r.seed), int(r.budget), r.example_id)
        aligned[key][r.method] = r

    loss_registry: list[dict[str, Any]] = []
    unchanged_or_win = 0

    for key, bucket in aligned.items():
        if OUR_METHOD not in bucket:
            continue
        our = bucket[OUR_METHOD]
        baseline_rows = [bucket[m] for m in BASELINES if m in bucket]
        winners = [b for b in baseline_rows if b.is_correct and not our.is_correct]
        if not winners:
            unchanged_or_win += 1
            continue

        winners_sorted = sorted(winners, key=lambda x: rank.get(x.method, 999))
        best_winner = winners_sorted[0]
        fg, fg_detail, pipeline_loc, advantage = classify_failure(our, winners_sorted)
        hypothesis = _pattern_hypothesis(fg, our.metadata, our.question)

        support_counts = our.metadata.get("answer_support_counts", {}) if isinstance(our.metadata, dict) else {}
        gold_key = our.normalized_gold
        surfaced_gold = bool(gold_key is not None and str(gold_key) in {str(k) for k in support_counts.keys()})

        continuing_proxy = bool(our.budget_exhausted or (our.actions_used >= max(1, our.budget - 1) and not bool(our.metadata.get("commit_triggered", False))))
        wrong_way_proxy = not continuing_proxy

        loss_registry.append(
            {
                "dataset": our.dataset,
                "seed": our.seed,
                "budget": our.budget,
                "example_id": our.example_id,
                "problem_statement": our.question,
                "gold_answer": our.gold_answer,
                "our_method": OUR_METHOD,
                "our_answer": our.prediction,
                "our_correct": our.is_correct,
                "baseline_answers": {b.method: b.prediction for b in baseline_rows},
                "baseline_correctness": {b.method: bool(b.is_correct) for b in baseline_rows},
                "winning_baselines": [w.method for w in winners_sorted],
                "best_winning_baseline": best_winner.method,
                "best_winning_baseline_answer": best_winner.prediction,
                "failure_group": fg,
                "failure_group_detail": fg_detail,
                "pipeline_failure_location": pipeline_loc,
                "best_method_advantage_type": advantage,
                "answer_attributes": {
                    "wrong_final_answer": True,
                    "incomplete_or_non_terminal": fg == "incomplete_or_non_terminal",
                    "wrong_aggregation": fg == "wrong_aggregation",
                    "wrong_commit_timing": fg == "wrong_commit_timing",
                    "low_diversity_failure": fg == "insufficient_diversity_realized",
                    "bad_diversity_failure": fg == "bad_diversity_realized",
                    "ranking_after_diversity_failure": fg == "ranking_after_diversity_failure",
                    "verification_failure": fg == "verification_failure",
                    "ambiguity_near_tie_failure": fg == "ambiguity_near_tie_failure",
                },
                "our_metadata": our.metadata,
                "best_winner_metadata": best_winner.metadata,
                "branch_support_clues": {
                    "unique_answer_groups_seen": _safe_int(our.metadata.get("unique_answer_groups_seen"), 0),
                    "answer_support_entropy": _safe_float(our.metadata.get("answer_support_entropy"), 0.0),
                    "group_support_fraction": _safe_float(our.metadata.get("group_support_fraction"), 0.0),
                    "answer_group_margin": _safe_float(our.metadata.get("answer_group_margin", 0.0), 0.0),
                    "gold_answer_surfaced_in_our_support": surfaced_gold,
                },
                "special_check": {
                    "continued_wrong_way_proxy": wrong_way_proxy,
                    "incomplete_might_improve_with_more_steps_proxy": continuing_proxy,
                },
                "pattern_hypothesis": hypothesis,
            }
        )

    loss_path = out_dir / "loss_registry.jsonl"
    loss_path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in loss_registry) + "\n", encoding="utf-8")

    # grouped summaries
    by_group = Counter(r["failure_group"] for r in loss_registry)
    by_dataset = Counter(r["dataset"] for r in loss_registry)
    by_winner = Counter(r["best_winning_baseline"] for r in loss_registry)
    by_adv = Counter(r["best_method_advantage_type"] for r in loss_registry)
    by_pipeline = Counter(r["pipeline_failure_location"] for r in loss_registry)

    group_dataset = defaultdict(Counter)
    for r in loss_registry:
        group_dataset[r["failure_group"]][r["dataset"]] += 1

    pattern_summary: dict[str, dict[str, Any]] = {}
    for group, count in by_group.items():
        group_rows = [r for r in loss_registry if r["failure_group"] == group]
        ds_counts = Counter(r["dataset"] for r in group_rows)
        winner_counts = Counter(r["best_winning_baseline"] for r in group_rows)
        surfaced_rate = _mean([1.0 if r["branch_support_clues"]["gold_answer_surfaced_in_our_support"] else 0.0 for r in group_rows])
        entropy_mean = _mean([float(r["branch_support_clues"]["answer_support_entropy"]) for r in group_rows])
        wrong_way_rate = _mean([1.0 if r["special_check"]["continued_wrong_way_proxy"] else 0.0 for r in group_rows])
        incomplete_rate = _mean([1.0 if r["special_check"]["incomplete_might_improve_with_more_steps_proxy"] else 0.0 for r in group_rows])
        pattern_summary[group] = {
            "count": int(count),
            "dataset_concentration": dict(ds_counts),
            "winning_baseline_concentration": dict(winner_counts),
            "gold_surfaced_but_not_selected_rate": float(surfaced_rate),
            "mean_answer_support_entropy": float(entropy_mean),
            "continued_wrong_way_rate_proxy": float(wrong_way_rate),
            "incomplete_might_improve_rate_proxy": float(incomplete_rate),
            "representative_pattern_hypotheses": list(dict.fromkeys([r["pattern_hypothesis"] for r in group_rows]))[:3],
        }

    # ranked subsets
    def _score_loss(r: dict[str, Any]) -> float:
        clues = r["branch_support_clues"]
        score = 0.0
        score += 2.0 * (1.0 if clues.get("gold_answer_surfaced_in_our_support") else 0.0)
        score += 1.2 * len(r.get("winning_baselines", []))
        score += 0.8 * (1.0 if r["failure_group"] in {"wrong_aggregation", "ranking_after_diversity_failure", "ambiguity_near_tie_failure"} else 0.0)
        score += min(1.0, float(clues.get("answer_support_entropy", 0.0)))
        return float(score)

    ranked_all = sorted(loss_registry, key=_score_loss, reverse=True)

    def _top_group(name: str, k: int = 10) -> list[dict[str, Any]]:
        cand = [r for r in ranked_all if r["failure_group"] == name]
        return cand[:k]

    ranked_sets = {
        "top20_informative_losses": ranked_all[:20],
        "top10_insufficient_diversity": _top_group("insufficient_diversity_realized", 10),
        "top10_aggregation_instability": _top_group("wrong_aggregation", 10),
        "top10_near_tie_ambiguity": _top_group("ambiguity_near_tie_failure", 10),
        "top10_plausible_found_but_selected_wrong": [r for r in ranked_all if r["branch_support_clues"]["gold_answer_surfaced_in_our_support"]][:10],
        "top10_diagnostic_baseline_advantage": sorted(loss_registry, key=lambda r: len(r.get("winning_baselines", [])), reverse=True)[:10],
    }

    summary = {
        "run_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "our_method": OUR_METHOD,
        "baselines": BASELINES,
        "datasets": datasets,
        "seeds": seeds,
        "budgets": budgets,
        "n_total_rows": len(rows),
        "n_matched_cells": len(aligned),
        "n_loss_cases": len(loss_registry),
        "n_non_loss_cases": int(unchanged_or_win),
        "per_method_metrics": per_method_metrics,
        "dominant_failure_group": by_group.most_common(1)[0][0] if by_group else None,
        "is_insufficient_diversity_dominant": bool(by_group.most_common(1)[0][0] == "insufficient_diversity_realized") if by_group else False,
        "is_aggregation_instability_top3": bool(any(k == "wrong_aggregation" for k, _ in by_group.most_common(3))),
        "failure_counts": dict(by_group),
        "failure_counts_by_dataset": {g: dict(c) for g, c in group_dataset.items()},
        "failure_counts_by_winning_baseline": dict(by_winner),
        "failure_counts_by_advantage_type": dict(by_adv),
        "failure_counts_by_pipeline_location": dict(by_pipeline),
    }

    (out_dir / "aggregate_comparison_metrics.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out_dir / "per_method_metrics.json").write_text(json.dumps(per_method_metrics, indent=2), encoding="utf-8")
    (out_dir / "failure_group_summary.json").write_text(
        json.dumps(
            {
                "by_failure_group": dict(by_group),
                "by_dataset": dict(by_dataset),
                "by_winning_baseline": dict(by_winner),
                "by_advantage_type": dict(by_adv),
                "by_pipeline_failure_location": dict(by_pipeline),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (out_dir / "pattern_summary_by_group.json").write_text(json.dumps(pattern_summary, indent=2), encoding="utf-8")
    (out_dir / "ranked_case_sets.json").write_text(json.dumps(ranked_sets, indent=2, ensure_ascii=False), encoding="utf-8")

    run_manifest = {
        "script": "scripts/run_refreshed_comparative_failure_casebook_20260419.py",
        "commands": [
            f"python scripts/run_refreshed_comparative_failure_casebook_20260419.py --output-dir {args.output_dir}",
        ],
        "config": vars(args),
        "artifacts": {
            "per_example_results": str((out_dir / "per_example_results.jsonl").relative_to(REPO_ROOT)),
            "loss_registry": str(loss_path.relative_to(REPO_ROOT)),
            "aggregate_comparison_metrics": str((out_dir / "aggregate_comparison_metrics.json").relative_to(REPO_ROOT)),
            "per_method_metrics": str((out_dir / "per_method_metrics.json").relative_to(REPO_ROOT)),
            "failure_group_summary": str((out_dir / "failure_group_summary.json").relative_to(REPO_ROOT)),
            "pattern_summary_by_group": str((out_dir / "pattern_summary_by_group.json").relative_to(REPO_ROOT)),
            "ranked_case_sets": str((out_dir / "ranked_case_sets.json").relative_to(REPO_ROOT)),
        },
    }
    (out_dir / "run_manifest.json").write_text(json.dumps(run_manifest, indent=2), encoding="utf-8")

    major_groups = [g for g, _ in by_group.most_common(4)]
    casebook_lines = [
        "# Refreshed Comparative Failure Casebook (2026-04-19)",
        "",
        f"- Our method: `{OUR_METHOD}`",
        f"- Baselines: {', '.join(f'`{m}`' for m in BASELINES)}",
        f"- Total loss cases: {len(loss_registry)}",
        "",
        "## Refreshed failure taxonomy",
    ]
    for g, c in by_group.most_common():
        casebook_lines.append(f"- `{g}`: {c}")
    casebook_lines.append("")
    casebook_lines.append("## Dominance checks")
    casebook_lines.append(f"- Is `insufficient_diversity_realized` dominant now? {'yes' if summary['is_insufficient_diversity_dominant'] else 'no'}.")
    casebook_lines.append(f"- Did aggregation instability become top bottleneck? {'yes (top-3)' if summary['is_aggregation_instability_top3'] else 'not top-3'}.")
    casebook_lines.append("")

    for group in major_groups:
        group_rows = [r for r in ranked_all if r["failure_group"] == group][:5]
        p = pattern_summary.get(group, {})
        casebook_lines.append(f"## Group: `{group}`")
        casebook_lines.append(f"- Count: {p.get('count', 0)}")
        casebook_lines.append(f"- Dataset concentration: {p.get('dataset_concentration', {})}")
        casebook_lines.append(f"- Winning baseline concentration: {p.get('winning_baseline_concentration', {})}")
        casebook_lines.append(
            f"- Special check (wrong-way vs incomplete proxy): {p.get('continued_wrong_way_rate_proxy', 0.0):.2f} vs {p.get('incomplete_might_improve_rate_proxy', 0.0):.2f}"
        )
        casebook_lines.append(f"- Group hypotheses: {p.get('representative_pattern_hypotheses', [])}")
        casebook_lines.append("")
        for idx, r in enumerate(group_rows, start=1):
            casebook_lines.append(f"### {group} example {idx}: `{r['dataset']} / {r['example_id']}`")
            casebook_lines.append(f"- Problem: {r['problem_statement']}")
            casebook_lines.append(f"- Gold answer: {r['gold_answer']}")
            casebook_lines.append(f"- Our answer: {r['our_answer']}")
            casebook_lines.append(f"- Best baseline winner: `{r['best_winning_baseline']}` -> {r['best_winning_baseline_answer']}")
            casebook_lines.append(f"- Failure detail: {r['failure_group_detail']}")
            casebook_lines.append(f"- Pipeline location: {r['pipeline_failure_location']}")
            casebook_lines.append(f"- Baseline advantage: {r['best_method_advantage_type']}")
            casebook_lines.append(f"- Branch/support clues: {r['branch_support_clues']}")
            casebook_lines.append(f"- Pattern hypothesis: {r['pattern_hypothesis']}")
            casebook_lines.append("")

    casebook_lines.extend(
        [
            "## Ranked sets",
            "- `top20_informative_losses`, `top10_insufficient_diversity`, `top10_aggregation_instability`,",
            "  `top10_near_tie_ambiguity`, `top10_plausible_found_but_selected_wrong`, and",
            "  `top10_diagnostic_baseline_advantage` are saved in `ranked_case_sets.json`.",
        ]
    )
    (out_dir / "RICH_FAILURE_CASEBOOK_2026_04_19.md").write_text("\n".join(casebook_lines) + "\n", encoding="utf-8")

    return summary


def main() -> None:
    p = argparse.ArgumentParser(description="Refreshed comparative failure re-audit with rich casebook")
    p.add_argument("--datasets", default="openai/gsm8k,HuggingFaceH4/MATH-500,HuggingFaceH4/aime_2024,olympiadbench")
    p.add_argument("--subset-size", type=int, default=24)
    p.add_argument("--seeds", default="11,23,37")
    p.add_argument("--budgets", default="4,6,8")
    p.add_argument("--adaptive-grid", default="1")
    p.add_argument("--model", default="gpt-4.1-mini")
    p.add_argument("--temperature", type=float, default=0.2)
    p.add_argument("--max-output-tokens", type=int, default=180)
    p.add_argument("--timeout-seconds", type=int, default=45)
    p.add_argument("--master-seed", type=int, default=20260419)
    p.add_argument("--output-dir", default="outputs/refreshed_comparative_failure_casebook_20260419")
    args = p.parse_args()
    run_eval(args)


if __name__ == "__main__":
    main()
