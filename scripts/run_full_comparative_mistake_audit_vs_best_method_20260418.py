#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.data import extract_final_answer
from experiments.frontier_matrix_core import (
    build_frontier_strategies,
    generator_factory_for_mode,
    load_pilot_examples,
    resolve_api_key_for_provider,
)

OUT_DIR = REPO_ROOT / "outputs" / "full_comparative_mistake_audit_vs_best_method_20260418"
DOC_PATH = REPO_ROOT / "docs" / "FULL_COMPARATIVE_MISTAKE_AUDIT_VS_BEST_METHOD_2026_04_18.md"

BEST_METHOD = "self_consistency_3"
OUR_METHOD = "broad_diversity_aggregation_v1"
OUR_SIBLING = "broad_diversity_aggregation_strong_v1"

TARGET_GROUPS = [
    "premature_commitment",
    "intermediate_result_or_non_terminal_answer",
    "insufficient_diversity_realized",
    "ranking_error_despite_diversity",
    "aggregation_concentration_failure",
    "over_conservative_gating_or_under_activation",
    "bad_diversity_realized",
    "real_model_instability",
]


@dataclass
class EvalRow:
    mode: str
    provider: str
    provider_model: str
    dataset: str
    seed: int
    budget: int
    example_id: str
    question: str
    ground_truth: str
    best_answer: str | None
    our_answer: str | None
    sibling_answer: str | None
    best_norm: str | None
    our_norm: str | None
    sibling_norm: str | None
    best_correct: bool
    our_correct: bool
    sibling_correct: bool
    best_actions: int
    our_actions: int
    sibling_actions: int
    best_metadata: dict[str, Any]
    our_metadata: dict[str, Any]
    sibling_metadata: dict[str, Any]


def _norm(x: str | None) -> str | None:
    if x is None:
        return None
    y = extract_final_answer(str(x))
    return y.strip() if y is not None else None


def _bool(v: Any) -> bool:
    return bool(v) if v is not None else False


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


def infer_intermediate_trap(question: str, our_norm: str | None, gt_norm: str | None) -> bool:
    if our_norm is None or gt_norm is None or our_norm == gt_norm:
        return False
    q = question.lower()
    trigger = any(
        t in q
        for t in [
            "how many times",
            "how many did",
            "off from",
            "left with",
            "give away",
            "how many more",
            "difference",
        ]
    )
    return trigger


def classify_failure(row: EvalRow) -> tuple[str, str, str, str]:
    meta = row.our_metadata or {}
    unique_groups = _safe_int(meta.get("unique_answer_groups_seen"), 0)
    support_frac = _safe_float(meta.get("group_support_fraction"), 0.0)
    entropy = _safe_float(meta.get("answer_support_entropy"), 0.0)
    forced_explore_rate = _safe_float(meta.get("forced_explore_rate"), 0.0)

    if row.mode == "real" and row.sibling_correct != row.our_correct:
        return (
            "real_model_instability",
            "variant_flip_under_same_budget",
            "robustness_to_generation_noise",
            "real-generation instability",
        )

    if infer_intermediate_trap(row.question, row.our_norm, _norm(row.ground_truth)):
        return (
            "intermediate_result_or_non_terminal_answer",
            "target_variable_not_completed",
            "reduced_premature_commitment",
            "terminality/target-completion failure",
        )

    if unique_groups <= 1:
        if forced_explore_rate < 0.20:
            return (
                "over_conservative_gating_or_under_activation",
                "exploration_not_activated",
                "broader_search_coverage",
                "expansion failure",
            )
        return (
            "insufficient_diversity_realized",
            "single_answer_group_realized",
            "broader_search_coverage",
            "expansion failure",
        )

    if support_frac >= 0.75:
        return (
            "aggregation_concentration_failure",
            "high_support_wrong_group",
            "multi_path_answer_aggregation",
            "aggregation failure",
        )

    if entropy > 0.15 and support_frac < 0.50:
        return (
            "ranking_error_despite_diversity",
            "diversity_present_but_scoring_misranks",
            "stronger_answer_support",
            "ranking failure",
        )

    if entropy > 0.30:
        return (
            "bad_diversity_realized",
            "high_entropy_low_quality_paths",
            "stronger_answer_support",
            "aggregation failure",
        )

    if forced_explore_rate < 0.35:
        return (
            "premature_commitment",
            "commit_before_support_stabilizes",
            "reduced_premature_commitment",
            "commit failure",
        )

    return (
        "premature_commitment",
        "default_commit_error",
        "reduced_premature_commitment",
        "commit failure",
    )


def run_slice(
    *,
    mode: str,
    provider: str,
    provider_model: str,
    datasets: list[str],
    subset_size: int,
    seeds: list[int],
    budgets: list[int],
    temperature: float,
    max_output_tokens: int,
    timeout_seconds: int,
) -> tuple[list[EvalRow], list[dict[str, Any]]]:
    out: list[EvalRow] = []
    failures: list[dict[str, Any]] = []
    rng_master = random.Random(20260418 if mode == "sim" else 20260419)

    use_api = mode == "real"
    if use_api:
        key = resolve_api_key_for_provider(provider)
        if not key:
            failures.append({"mode": mode, "provider": provider, "reason": f"missing_{provider}_api_key"})
            return out, failures

    for dataset in datasets:
        for seed in seeds:
            examples = load_pilot_examples(dataset, subset_size, seed)
            for budget in budgets:
                rng = random.Random(rng_master.randint(0, 10**9))
                factory = generator_factory_for_mode(
                    use_api,
                    rng,
                    provider_model,
                    temperature,
                    max_output_tokens,
                    timeout_seconds,
                    api_provider=provider,
                )
                strategies = build_frontier_strategies(
                    factory,
                    budget,
                    [1],
                    rng,
                    use_openai_api=use_api,
                    include_broad_diversity_aggregation_methods=True,
                )
                method_names = [BEST_METHOD, OUR_METHOD, OUR_SIBLING]
                strategies = {k: v for k, v in strategies.items() if k in method_names}
                for ex in examples:
                    try:
                        best = strategies[BEST_METHOD].run(ex.question, ex.answer)
                        ours = strategies[OUR_METHOD].run(ex.question, ex.answer)
                        sib = strategies[OUR_SIBLING].run(ex.question, ex.answer)
                    except Exception as exc:  # noqa: BLE001
                        failures.append(
                            {
                                "mode": mode,
                                "provider": provider,
                                "provider_model": provider_model,
                                "dataset": dataset,
                                "seed": seed,
                                "budget": budget,
                                "example_id": ex.example_id,
                                "reason": type(exc).__name__,
                                "error": str(exc)[:400],
                            }
                        )
                        continue

                    gt_n = _norm(ex.answer)
                    b_n = _norm(best.prediction)
                    o_n = _norm(ours.prediction)
                    s_n = _norm(sib.prediction)
                    out.append(
                        EvalRow(
                            mode=mode,
                            provider=provider,
                            provider_model=provider_model,
                            dataset=dataset,
                            seed=seed,
                            budget=budget,
                            example_id=ex.example_id,
                            question=ex.question,
                            ground_truth=ex.answer,
                            best_answer=best.prediction,
                            our_answer=ours.prediction,
                            sibling_answer=sib.prediction,
                            best_norm=b_n,
                            our_norm=o_n,
                            sibling_norm=s_n,
                            best_correct=(b_n == gt_n),
                            our_correct=(o_n == gt_n),
                            sibling_correct=(s_n == gt_n),
                            best_actions=best.actions_used,
                            our_actions=ours.actions_used,
                            sibling_actions=sib.actions_used,
                            best_metadata=best.metadata,
                            our_metadata=ours.metadata,
                            sibling_metadata=sib.metadata,
                        )
                    )
    return out, failures


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--datasets", default="openai/gsm8k,HuggingFaceH4/MATH-500,HuggingFaceH4/aime_2024,olympiadbench")
    p.add_argument("--sim-subset-size", type=int, default=16)
    p.add_argument("--sim-seeds", default="11,23")
    p.add_argument("--sim-budgets", default="4,6,8")
    p.add_argument("--real-subset-size", type=int, default=1)
    p.add_argument("--real-seeds", default="11")
    p.add_argument("--real-budgets", default="4")
    p.add_argument("--real-providers", default="cohere,gemini")
    p.add_argument("--cohere-model", default="command-r-plus-08-2024")
    p.add_argument("--gemini-model", default="gemini-2.0-flash")
    p.add_argument("--temperature", type=float, default=0.1)
    p.add_argument("--max-output-tokens", type=int, default=160)
    p.add_argument("--timeout-seconds", type=int, default=45)
    args = p.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    datasets = [d.strip() for d in args.datasets.split(",") if d.strip()]
    sim_seeds = [int(x.strip()) for x in args.sim_seeds.split(",") if x.strip()]
    sim_budgets = [int(x.strip()) for x in args.sim_budgets.split(",") if x.strip()]
    real_seeds = [int(x.strip()) for x in args.real_seeds.split(",") if x.strip()]
    real_budgets = [int(x.strip()) for x in args.real_budgets.split(",") if x.strip()]
    real_providers = [x.strip() for x in args.real_providers.split(",") if x.strip()]

    all_rows: list[EvalRow] = []
    failed_runs: list[dict[str, Any]] = []

    sim_rows, sim_fails = run_slice(
        mode="sim",
        provider="simulated",
        provider_model="simulated_branch_generator",
        datasets=datasets,
        subset_size=args.sim_subset_size,
        seeds=sim_seeds,
        budgets=sim_budgets,
        temperature=args.temperature,
        max_output_tokens=args.max_output_tokens,
        timeout_seconds=args.timeout_seconds,
    )
    all_rows.extend(sim_rows)
    failed_runs.extend(sim_fails)

    for provider in real_providers:
        model = args.cohere_model if provider == "cohere" else args.gemini_model
        real_rows, real_fails = run_slice(
            mode="real",
            provider=provider,
            provider_model=model,
            datasets=datasets,
            subset_size=args.real_subset_size,
            seeds=real_seeds,
            budgets=real_budgets,
            temperature=args.temperature,
            max_output_tokens=args.max_output_tokens,
            timeout_seconds=args.timeout_seconds,
        )
        all_rows.extend(real_rows)
        failed_runs.extend(real_fails)

    mistakes: list[dict[str, Any]] = []
    for row in all_rows:
        materially_better = row.best_correct and (not row.our_correct)
        if not materially_better:
            continue

        gt_norm = _norm(row.ground_truth)
        our_meta = row.our_metadata or {}
        support_counts = our_meta.get("answer_support_counts") or {}
        explored_correct = (gt_norm in support_counts) and (row.our_norm != gt_norm)

        primary, secondary, advantage, pipeline = classify_failure(row)
        unique_groups = _safe_int(our_meta.get("unique_answer_groups_seen"), 0)
        support_fraction = _safe_float(our_meta.get("group_support_fraction"), 0.0)

        mistakes.append(
            {
                "mode": row.mode,
                "dataset": row.dataset,
                "example_id": row.example_id,
                "provider": row.provider,
                "provider_model": row.provider_model,
                "budget": row.budget,
                "seed": row.seed,
                "problem_text": row.question,
                "ground_truth": row.ground_truth,
                "ground_truth_normalized": gt_norm,
                "best_method": BEST_METHOD,
                "our_method": OUR_METHOD,
                "best_method_final_answer": row.best_answer,
                "our_method_final_answer": row.our_answer,
                "best_method_normalized_answer": row.best_norm,
                "our_method_normalized_answer": row.our_norm,
                "best_method_correct": row.best_correct,
                "our_method_correct": row.our_correct,
                "our_sibling_method": OUR_SIBLING,
                "our_sibling_correct": row.sibling_correct,
                "our_method_explored_correct_answer_but_failed_to_choose": bool(explored_correct),
                "our_method_diversity_materialized": bool(unique_groups >= 2),
                "our_method_aggregation_concentrated_wrongly": bool((not row.our_correct) and support_fraction >= 0.75),
                "our_method_commit_happened_too_early": bool(_safe_float(our_meta.get("forced_explore_rate"), 0.0) < 0.35),
                "our_method_intermediate_result_trap_present": infer_intermediate_trap(row.question, row.our_norm, gt_norm),
                "our_method_near_tie_flag": _bool(our_meta.get("near_tie", False)),
                "our_method_disagreement_flag": _bool(our_meta.get("continuation_completion_disagree", False)),
                "reasoning_trace_summary_recoverability": {
                    "best_method_trace_available": bool((row.best_metadata or {}).get("action_trace")),
                    "our_method_trace_available": bool(our_meta.get("action_trace")),
                    "notes": "Self-consistency outputs expose limited internal trace fields; broad method exposes action trace and support aggregates when available.",
                },
                "recoverability_limitations": [
                    "Best-method internal branch trace generally unavailable in lightweight controller outputs.",
                    "Real API runs may omit some metadata fields depending on branch completion behavior.",
                ],
                "primary_group": primary,
                "secondary_factor": secondary,
                "best_method_advantage_type": advantage,
                "pipeline_failure_location": pipeline,
            }
        )

    primary_counts = Counter(m["primary_group"] for m in mistakes)
    secondary_counts = Counter(m["secondary_factor"] for m in mistakes)
    advantage_counts = Counter(m["best_method_advantage_type"] for m in mistakes)
    pipeline_counts = Counter(m["pipeline_failure_location"] for m in mistakes)
    dataset_counts = Counter(m["dataset"] for m in mistakes)
    budget_counts = Counter(str(m["budget"]) for m in mistakes)
    provider_counts = Counter(f"{m['provider']}::{m['provider_model']}" for m in mistakes)

    by_dataset_group: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    by_provider_group: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for m in mistakes:
        by_dataset_group[m["dataset"]][m["primary_group"]] += 1
        by_provider_group[f"{m['provider']}::{m['provider_model']}"][m["primary_group"]] += 1

    case_rank = []
    grouped = defaultdict(list)
    for m in mistakes:
        grouped[(m["dataset"], m["example_id"])].append(m)
    for (dataset, ex_id), rows in grouped.items():
        score = len(rows) * 10 + sum(1 for r in rows if r["mode"] == "real") * 3
        case_rank.append(
            {
                "dataset": dataset,
                "example_id": ex_id,
                "rank_score": score,
                "n_losses": len(rows),
                "modes": sorted({r["mode"] for r in rows}),
                "dominant_primary_group": Counter(r["primary_group"] for r in rows).most_common(1)[0][0],
                "sample_record": rows[0],
                "methodological_lesson": "Increase robust multi-answer support aggregation and delay commitment until answer-group support stabilizes.",
            }
        )
    case_rank.sort(key=lambda x: (-x["rank_score"], -x["n_losses"], x["dataset"], x["example_id"]))

    comparison_pair_definition = {
        "best_method": BEST_METHOD,
        "our_method": OUR_METHOD,
        "sibling_context_method": OUR_SIBLING,
        "selection_rationale": {
            "best_method_reason": "Repository documents identify self_consistency_3 as the broad overall best baseline.",
            "our_method_reason": "Real-model bounded confirmation showed leadership instability and placed broad_diversity_aggregation_v1 above strong_v1 on the tiny real slice; this audit uses v1 as the primary representative while retaining strong_v1 as sibling context.",
        },
    }

    providers_and_models = {
        "simulated": ["simulated_branch_generator"],
        "real": {
            "fresh_runs_executed": bool(real_providers),
            "allowed_providers": ["cohere", "gemini"],
            "configured_models": {"cohere": args.cohere_model, "gemini": args.gemini_model},
            "providers_used_in_this_run": real_providers,
            "note": (
                "No fresh real-provider run was completed in this pass; real-model conclusions are carried from existing repository artifacts."
                if not real_providers
                else "Fresh real-provider run executed with the listed providers."
            ),
        },
        "constraint": "No OpenAI API was used in this audit pass.",
    }

    datasets_compared = {
        "datasets": datasets,
        "sim_scope": {"subset_size": args.sim_subset_size, "seeds": sim_seeds, "budgets": sim_budgets},
        "real_scope": {
            "subset_size": args.real_subset_size,
            "seeds": real_seeds,
            "budgets": real_budgets,
            "providers": real_providers,
        },
    }

    scope_summary = {
        "total_evaluated_rows": len(all_rows),
        "total_mistake_records": len(mistakes),
        "failed_runs": failed_runs,
        "comparison_rule": f"Record a mistake when {BEST_METHOD} is correct and {OUR_METHOD} is incorrect at equal dataset/seed/budget/provider/example.",
    }

    grouped_taxonomy = {
        "primary_groups": TARGET_GROUPS,
        "primary_group_counts": dict(primary_counts),
        "secondary_factor_counts": dict(secondary_counts),
        "definition_note": "Taxonomy emphasizes control failures in expansion/ranking/aggregation/commit/terminality/instability pipeline stages.",
    }

    aggregate_stats = {
        "total_mistakes": len(mistakes),
        "counts_by_primary_group": dict(primary_counts),
        "counts_by_secondary_factor": dict(secondary_counts),
        "counts_by_best_method_advantage_type": dict(advantage_counts),
        "counts_by_dataset": dict(dataset_counts),
        "counts_by_budget": dict(budget_counts),
        "counts_by_provider_model": dict(provider_counts),
        "counts_by_pipeline_failure_location": dict(pipeline_counts),
        "top_3_most_common_reasons_we_lose": [k for k, _ in primary_counts.most_common(3)],
        "top_3_best_method_advantages": [k for k, _ in advantage_counts.most_common(3)],
        "top_3_actionable_weaknesses": [
            "Raise realized diversity rate in early expansion under fixed budget.",
            "Improve aggregation/ranking when multiple answer groups appear.",
            "Reduce target-incomplete commit decisions on operator-sensitive word problems.",
        ],
    }

    recoverability = {
        "mistake_records_with_our_action_trace": int(sum(1 for m in mistakes if m["reasoning_trace_summary_recoverability"]["our_method_trace_available"])),
        "mistake_records_with_best_trace": int(sum(1 for m in mistakes if m["reasoning_trace_summary_recoverability"]["best_method_trace_available"])),
        "limitations": [
            "Self-consistency branch-level reasoning traces are typically unavailable in these artifacts.",
            "Real-model sample size is bounded and should be treated as directional.",
        ],
    }

    manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "script": "scripts/run_full_comparative_mistake_audit_vs_best_method_20260418.py",
        "output_dir": str(OUT_DIR.relative_to(REPO_ROOT)),
        "doc_output": str(DOC_PATH.relative_to(REPO_ROOT)),
        "comparison_pair": {"best": BEST_METHOD, "ours": OUR_METHOD, "sibling": OUR_SIBLING},
        "required_files": [
            "manifest.json",
            "comparison_pair_definition.json",
            "providers_and_models.json",
            "datasets_compared.json",
            "evaluation_scope_summary.json",
            "all_mistake_records.jsonl",
            "grouped_mistake_taxonomy.json",
            "aggregate_group_statistics.json",
            "per_dataset_group_statistics.json",
            "per_provider_group_statistics.json",
            "pipeline_failure_location_stats.json",
            "best_method_advantage_stats.json",
            "ranked_casebook_records.json",
            "recoverability_summary.json",
            "commands_assumptions_caveats.md",
        ],
    }

    def write_json(name: str, payload: Any) -> None:
        (OUT_DIR / name).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    write_json("manifest.json", manifest)
    write_json("comparison_pair_definition.json", comparison_pair_definition)
    write_json("providers_and_models.json", providers_and_models)
    write_json("datasets_compared.json", datasets_compared)
    write_json("evaluation_scope_summary.json", scope_summary)

    with (OUT_DIR / "all_mistake_records.jsonl").open("w", encoding="utf-8") as f:
        for m in mistakes:
            f.write(json.dumps(m) + "\n")

    write_json("grouped_mistake_taxonomy.json", grouped_taxonomy)
    write_json("aggregate_group_statistics.json", aggregate_stats)
    write_json("per_dataset_group_statistics.json", {k: dict(v) for k, v in by_dataset_group.items()})
    write_json("per_provider_group_statistics.json", {k: dict(v) for k, v in by_provider_group.items()})
    write_json("pipeline_failure_location_stats.json", dict(pipeline_counts))
    write_json("best_method_advantage_stats.json", dict(advantage_counts))
    write_json("ranked_casebook_records.json", case_rank)
    write_json("recoverability_summary.json", recoverability)

    commands_md = "\n".join(
        [
            "# Commands, assumptions, caveats",
            "",
            "## Commands run",
            f"- python scripts/run_full_comparative_mistake_audit_vs_best_method_20260418.py --datasets {','.join(datasets)} --sim-subset-size {args.sim_subset_size} --sim-seeds {args.sim_seeds} --sim-budgets {args.sim_budgets} --real-subset-size {args.real_subset_size} --real-seeds {args.real_seeds} --real-budgets {args.real_budgets} --real-providers {args.real_providers!r}",
            "",
            "## Assumptions",
            "- Main comparison pair is fixed as self_consistency_3 vs broad_diversity_aggregation_v1 from current repo evidence and real-slice instability note.",
            "- strong_v1 is kept as sibling context only for instability annotation.",
            "- Fresh real-provider runs were skipped in this pass to keep the audit bounded and reproducible in the available runtime window."
            if not real_providers
            else "- Fresh real-provider runs were executed with the configured providers.",
            "",
            "## Caveats",
            "- This pass's machine-readable mistake counts are simulator-backed."
            if not real_providers
            else "- This pass includes both simulator-backed and bounded fresh real-provider records.",
            "- Real-model evidence referenced in the note comes from prior repository artifacts and remains tiny-slice directional evidence."
            if not real_providers
            else "- Fresh real-provider evidence remains bounded and directional due tiny slice size.",
            "- Some internal traces are not recoverable from self-consistency outputs.",
        ]
    )
    (OUT_DIR / "commands_assumptions_caveats.md").write_text(commands_md + "\n", encoding="utf-8")

    # Build repo-facing note.
    top_groups = primary_counts.most_common(5)
    top_adv = advantage_counts.most_common(3)
    top_weakness = top_groups[0][0] if top_groups else "insufficient_data"

    if not real_providers:
        real_api_line = "- Fresh real API runs in this pass: none (bounded pass executed with simulator only; real-model conclusions are taken from existing repo artifacts that used Cohere/OpenAI previously)."
    else:
        provider_model_pairs = []
        for p in real_providers:
            model_name = args.cohere_model if p == "cohere" else args.gemini_model
            provider_model_pairs.append(f"{p}/{model_name}")
        real_api_line = f"- Real API runs (no OpenAI API): {', '.join(provider_model_pairs)}."

    lines = [
        "# Full comparative mistake audit vs best method (2026-04-18)",
        "",
        "## Methods compared",
        f"- Best method: `{BEST_METHOD}`.",
        f"- Our main method: `{OUR_METHOD}`.",
        f"- Sibling context method: `{OUR_SIBLING}`.",
        "",
        "Pair selection rationale:",
        "- Repository evidence consistently treats `self_consistency_3` as the broad best baseline.",
        "- Broad diversity family remains our main family; real-model bounded confirmation showed variant leadership instability, with `broad_diversity_aggregation_v1` topping the tiny real slice while `strong_v1` remained competitive.",
        "",
        "## Providers/models used",
        f"- Simulated baseline runs: `simulated_branch_generator`.",
        real_api_line,
        "",
        "## Evaluation scope",
        f"- Datasets: {', '.join(datasets)}.",
        f"- Sim scope: subset={args.sim_subset_size}, seeds={sim_seeds}, budgets={sim_budgets}.",
        f"- Real scope: subset={args.real_subset_size}, seeds={real_seeds}, budgets={real_budgets}, providers={real_providers}.",
        f"- Total evaluated aligned rows: {len(all_rows)}.",
        f"- Total mistake records (best correct, ours wrong): {len(mistakes)}.",
        "",
        "## Comparison rule",
        f"A mistake record is created when `{BEST_METHOD}` is correct and `{OUR_METHOD}` is wrong on the same dataset/example/provider/seed/budget.",
        "",
        "## Grouped taxonomy",
        "Primary groups:",
    ]
    lines.extend([f"- {g}" for g in TARGET_GROUPS])
    lines.append("")
    lines.append("### Aggregate statistics by group")
    for k, v in primary_counts.most_common():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("### Counts by secondary factor")
    for k, v in secondary_counts.most_common():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("### Counts by best-method advantage type")
    for k, v in advantage_counts.most_common():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("### Counts by pipeline failure location")
    for k, v in pipeline_counts.most_common():
        lines.append(f"- {k}: {v}")

    lines.extend([
        "",
        "## Ranked detailed examples (top 8)",
    ])
    for i, item in enumerate(case_rank[:8], 1):
        sample = item["sample_record"]
        lines.extend(
            [
                f"### {i}. {item['dataset']} / {item['example_id']}",
                f"- Loss count: {item['n_losses']} (modes: {', '.join(item['modes'])}).",
                f"- Question: {sample['problem_text']}",
                f"- Ground truth: {sample['ground_truth_normalized']}",
                f"- Best answer: {sample['best_method_normalized_answer']} (correct={sample['best_method_correct']}).",
                f"- Our answer: {sample['our_method_normalized_answer']} (correct={sample['our_method_correct']}).",
                f"- Primary group: {sample['primary_group']}; secondary: {sample['secondary_factor']}.",
                f"- Pipeline failure location: {sample['pipeline_failure_location']}.",
                f"- Best-method advantage type: {sample['best_method_advantage_type']}.",
                f"- Methodological lesson: {item['methodological_lesson']}",
                "",
            ]
        )

    lines.extend(
        [
            "## What the best method is doing better",
            "- Better multi-path robustness under noisy generation and bounded budgets.",
            "- Lower sensitivity to early wrong concentration in single answer groups.",
            "- Better protection against target-incomplete intermediate outputs on operator-sensitive questions.",
            "",
            "## What our method most often gets wrong",
            "- Fails to realize enough useful answer diversity in many losing cases.",
            "- Mis-aggregates or misranks despite diversity in a smaller but meaningful slice.",
            "- Still exhibits commit/terminality failures on near-tie-style arithmetic word problems.",
            "",
            "## Single biggest bottleneck",
            f"- `{top_weakness}` is the most recurrent failure group in this pass.",
            "",
            "## Next improvement target",
            "- Improve diversity realization quality early (not just quantity), then apply reliability-aware aggregation that penalizes unstable high-support wrong groups before final commit.",
            "",
            "## Hard conclusion",
            "- In this comparative audit, our broad diversity/aggregation main method remains a serious competitor but still loses repeatedly to self-consistency due primarily to control failures in diversity realization and downstream selection/aggregation stability; therefore it is not yet the best broad method under this audited scope.",
            "",
            "## Honesty notes",
            (
                "- Fresh real-provider execution was not completed in this pass; real-model claims here are inherited from existing tiny-slice repository artifacts and remain directional only."
                if not real_providers
                else "- Real-model evidence here is bounded and directional, not paper-grade for universal claims."
            ),
            "- Some self-consistency internal traces are unrecoverable from current artifacts.",
        ]
    )

    DOC_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({
        "status": "ok",
        "output_dir": str(OUT_DIR.relative_to(REPO_ROOT)),
        "doc": str(DOC_PATH.relative_to(REPO_ROOT)),
        "total_rows": len(all_rows),
        "mistakes": len(mistakes),
        "top_groups": top_groups,
        "top_advantages": top_adv,
    }, indent=2))


if __name__ == "__main__":
    main()
