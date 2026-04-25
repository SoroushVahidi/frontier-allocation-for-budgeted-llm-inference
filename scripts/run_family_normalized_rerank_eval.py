#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.frontier_matrix_core import build_frontier_strategies, generator_factory_for_mode
from experiments.output_layer_repair import canonicalize_answer, choose_repair_answer
from experiments.problem_type_utils import classify_problem_type

STRICT_F3_RUNTIME = (
    "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_"
    "repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth3_coverage_forced_v1"
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Diagnostic/probe family-normalized rerank evaluation.")
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    p.add_argument("--max-cases", type=int, default=0)
    p.add_argument("--resume", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--provider", default="cohere")
    p.add_argument("--cohere-model", default="command-r-plus-08-2024")
    p.add_argument("--input-package", default="outputs/detailed_loss_case_package_20260425T_WULVER_COHERE_LONG_DETAIL/")
    p.add_argument("--slice", choices=["loss150", "present_not_selected", "absent_from_tree", "all720"], default="present_not_selected")
    p.add_argument("--emit-traces", action="store_true")
    p.add_argument("--skip-real-api-if-no-key", action="store_true")
    p.add_argument("--selection-mode", default="family_normalized_full")
    p.add_argument("--selection-ablation", action="store_true")
    return p.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], *, fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        hdr = fieldnames
        if hdr is None and rows:
            hdr = list(rows[0].keys())
        if hdr is None:
            hdr = ["empty"]
        w = csv.DictWriter(f, fieldnames=hdr)
        w.writeheader()
        if rows:
            w.writerows(rows)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=True) + "\n")


def as_int(v: Any, d: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return d


def as_float(v: Any, d: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return d


def pick_slice(rows: list[dict[str, str]], sl: str) -> list[dict[str, str]]:
    if sl == "loss150":
        return [r for r in rows if str(r.get("pair_type")) == "strict_f3_wrong_external_correct"]
    if sl == "present_not_selected":
        return [r for r in rows if str(r.get("strict_f3_failure_type")) == "present_not_selected"]
    if sl == "absent_from_tree":
        return [r for r in rows if str(r.get("strict_f3_failure_type")) == "absent_from_tree"]
    return rows


def rank_map(score_by_group: dict[str, float]) -> dict[str, int]:
    ordered = sorted(score_by_group.items(), key=lambda kv: kv[1], reverse=True)
    return {k: i + 1 for i, (k, _) in enumerate(ordered)}


def parse_nested_scores(raw: dict[str, Any]) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for gk, vv in (raw or {}).items():
        if isinstance(vv, dict):
            out[str(gk)] = {str(k): as_float(v) for k, v in vv.items()}
    return out


def family_normalized_support_from_counts(family_counts: dict[str, float]) -> float:
    return float(sum(min(1.0, as_float(v, 0.0)) for v in family_counts.values()))


def family_normalized_full_score(
    *,
    normalized_support_fraction: float,
    process_score: float,
    verifier_score: float,
    diversity_score: float,
    single_family_penalty: float,
    dominant_family_penalty: float,
    support_weight: float = 1.0,
    process_weight: float = 0.5,
    verifier_weight: float = 1.0,
    diversity_weight: float = 0.4,
    single_family_penalty_weight: float = 0.5,
    dominant_family_penalty_weight: float = 0.3,
) -> float:
    return float(
        support_weight * normalized_support_fraction
        + process_weight * process_score
        + verifier_weight * verifier_score
        + diversity_weight * diversity_score
        - single_family_penalty_weight * single_family_penalty
        - dominant_family_penalty_weight * dominant_family_penalty
    )


def selection_failure_reason(
    *,
    gold_group: str,
    selected_group: str,
    support_by_group: dict[str, float],
    normalized_support_by_group: dict[str, float],
    verifier_by_group: dict[str, float],
    process_by_group: dict[str, float],
    family_counts_by_group: dict[str, int],
    family_rerank_triggered: bool,
    selection_changed_by_family_rerank: bool,
) -> str:
    if gold_group not in support_by_group:
        return "gold_group_missing_from_final_groups"
    if support_by_group.get(gold_group, 0.0) < 0.2:
        return "gold_group_low_raw_support"
    if normalized_support_by_group.get(gold_group, 0.0) < 0.2:
        return "gold_group_low_family_normalized_support"
    if verifier_by_group.get(gold_group, 0.0) < 0.45:
        return "gold_group_low_verifier_score"
    if process_by_group.get(gold_group, 0.0) < 0.45:
        return "gold_group_low_process_score"
    if family_counts_by_group.get(gold_group, 0) <= 1:
        return "gold_group_single_family_only"
    if support_by_group.get(selected_group, 0.0) > support_by_group.get(gold_group, 0.0) and family_counts_by_group.get(selected_group, 0) <= 1:
        return "wrong_group_many_same_family_votes"
    if family_counts_by_group.get(selected_group, 0) > family_counts_by_group.get(gold_group, 0):
        return "wrong_group_more_family_diverse"
    if verifier_by_group.get(selected_group, 0.0) > verifier_by_group.get(gold_group, 0.0):
        return "wrong_group_higher_verifier_score"
    if process_by_group.get(selected_group, 0.0) > process_by_group.get(gold_group, 0.0):
        return "wrong_group_higher_process_score"
    if not family_rerank_triggered:
        return "family_rerank_not_triggered"
    if family_rerank_triggered and (not selection_changed_by_family_rerank):
        return "family_rerank_triggered_but_no_change"
    return "unknown"


def run_ablation(
    *,
    support: dict[str, float],
    norm_support: dict[str, float],
    verifier: dict[str, float],
    process: dict[str, float],
    diversity: dict[str, float],
    final: dict[str, float],
    gold_group: str,
) -> list[dict[str, Any]]:
    groups = sorted(set(support) | set(norm_support) | set(verifier) | set(process) | set(diversity) | set(final))
    if not groups:
        return []

    def pick(rule: str) -> str:
        if rule == "raw_support_only":
            return max(groups, key=lambda g: support.get(g, 0.0))
        if rule == "family_normalized_support_only":
            return max(groups, key=lambda g: norm_support.get(g, 0.0))
        if rule == "verifier_only":
            return max(groups, key=lambda g: verifier.get(g, 0.0))
        if rule == "process_only":
            return max(groups, key=lambda g: process.get(g, 0.0))
        if rule == "support_plus_verifier":
            return max(groups, key=lambda g: support.get(g, 0.0) + verifier.get(g, 0.0))
        if rule == "family_normalized_support_plus_verifier":
            return max(groups, key=lambda g: norm_support.get(g, 0.0) + verifier.get(g, 0.0))
        if rule == "family_normalized_support_plus_process_plus_verifier":
            return max(groups, key=lambda g: norm_support.get(g, 0.0) + process.get(g, 0.0) + verifier.get(g, 0.0))
        if rule == "family_normalized_full":
            return max(groups, key=lambda g: final.get(g, 0.0))
        if rule == "oracle_if_gold_present":
            if gold_group in groups:
                return gold_group
            return max(groups, key=lambda g: final.get(g, 0.0))
        return max(groups, key=lambda g: final.get(g, 0.0))

    rules = [
        "raw_support_only",
        "family_normalized_support_only",
        "verifier_only",
        "process_only",
        "support_plus_verifier",
        "family_normalized_support_plus_verifier",
        "family_normalized_support_plus_process_plus_verifier",
        "family_normalized_full",
        "oracle_if_gold_present",
    ]
    out = []
    for r in rules:
        sel = pick(r)
        out.append(
            {
                "rule": r,
                "selected_group": sel,
                "gold_group": gold_group,
                "is_correct": int(sel == gold_group and gold_group != "NA"),
                "gold_present": int(gold_group in groups),
            }
        )
    return out


def main() -> None:
    args = parse_args()
    if (not args.dry_run) and args.skip_real_api_if_no_key and not os.environ.get("COHERE_API_KEY"):
        args.dry_run = True

    input_pkg = REPO_ROOT / args.input_package
    all_cases = read_csv(input_pkg / "all_paired_cases.csv")
    if not all_cases:
        raise RuntimeError("Missing all_paired_cases.csv in input package")
    all_cases = pick_slice(all_cases, args.slice)
    if args.max_cases > 0:
        all_cases = all_cases[: args.max_cases]

    out_dir = REPO_ROOT / "outputs" / f"family_normalized_rerank_eval_{args.timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    methods = [
        "strict_f3",
        "strict_f3_typed_strategy_seeded_v1",
        "strict_f3_typed_strategy_family_normalized_rerank_v1",
        "external_l1_max",
    ]
    runtime_map = {
        "strict_f3": STRICT_F3_RUNTIME,
        "strict_f3_typed_strategy_seeded_v1": "strict_f3_typed_strategy_seeded_v1",
        "strict_f3_typed_strategy_family_normalized_rerank_v1": "strict_f3_typed_strategy_family_normalized_rerank_v1",
        "external_l1_max": "external_l1_max",
    }

    budgets = sorted({as_int(r.get("budget")) for r in all_cases})
    controllers: dict[int, dict[str, Any]] = {}
    for b in budgets:
        rng = random.Random(700 + b)
        factory = generator_factory_for_mode(
            use_openai_api=not args.dry_run,
            rng=rng,
            openai_model=args.cohere_model,
            temperature=0.1,
            max_output_tokens=280,
            timeout_seconds=60,
            api_provider=args.provider,
        )
        controllers[b] = build_frontier_strategies(
            generator_factory=factory,
            budget=b,
            adaptive_min_expand_grid=[1],
            rng=rng,
            use_openai_api=not args.dry_run,
            include_broad_diversity_aggregation_methods=True,
            include_external_l1_baseline=True,
        )

    per_case: list[dict[str, Any]] = []
    per_answer_group_scores: list[dict[str, Any]] = []
    selection_ablation_per_case: list[dict[str, Any]] = []
    missing_fields: Counter[str] = Counter()

    for c in all_cases:
        question = str(c.get("question") or "")
        gold_text = str(c.get("gold_answer") or "")
        if not question or not gold_text or question == "NA" or gold_text == "NA":
            continue
        seed = as_int(c.get("seed"))
        budget = as_int(c.get("budget"))
        example_id = str(c.get("example_id"))
        problem_type = classify_problem_type(question)
        gold_group = str(canonicalize_answer(gold_text, dataset="openai/gsm8k") or "NA")
        for method in methods:
            runtime = runtime_map[method]
            ctrl = controllers[budget].get(runtime)
            if ctrl is None:
                continue
            if method == "strict_f3_typed_strategy_family_normalized_rerank_v1":
                setattr(ctrl, "_runtime_selection_mode_override", str(args.selection_mode))
            res = ctrl.run(question, gold_text)
            meta = dict(res.metadata or {})

            repaired = choose_repair_answer(
                final_nodes=list(meta.get("final_nodes") or []),
                selected_group_hint=meta.get("selected_group"),
                dataset="openai/gsm8k",
                enable_rescue=True,
            )
            pred = canonicalize_answer(repaired.get("surfaced_final_answer_raw"), dataset="openai/gsm8k")
            exact = int(pred is not None and pred == gold_group)
            if exact == 1:
                failure_type = "correct"
            elif not bool(meta.get("gold_group_ever_present", False)):
                failure_type = "absent_from_tree"
            elif bool(meta.get("gold_group_present_final", False)):
                failure_type = "output_layer_mismatch"
            else:
                failure_type = "present_not_selected"

            support_counts = {str(k): as_float(v) for k, v in dict(meta.get("answer_group_support_counts") or {}).items()}
            norm_support = {str(k): as_float(v) for k, v in dict(meta.get("family_normalized_support_by_answer_group") or {}).items()}
            verifier_scores = {str(k): as_float(v) for k, v in dict(meta.get("mean_verifier_score_by_answer_group") or {}).items()}
            process_scores = {str(k): as_float(v) for k, v in dict(meta.get("mean_process_score_by_answer_group") or {}).items()}
            final_scores = {str(k): as_float(v) for k, v in dict(meta.get("answer_group_final_scores") or {}).items()}
            family_counts_nested = parse_nested_scores(dict(meta.get("answer_group_strategy_family_counts") or {}))
            if not norm_support and family_counts_nested:
                norm_support = {
                    str(g): family_normalized_support_from_counts(fam_counts)
                    for g, fam_counts in family_counts_nested.items()
                }
            family_counts_by_group = {g: len([k for k, v in fam.items() if as_int(v) > 0]) for g, fam in family_counts_nested.items()}
            diversity_scores = {g: float(family_counts_by_group.get(g, 0)) for g in set(list(support_counts.keys()) + list(final_scores.keys()))}
            selected_group = str(meta.get("post_rerank_selected_answer_group") or meta.get("selected_group") or "NA")
            pre_group = str(meta.get("pre_rerank_selected_answer_group") or meta.get("pre_guard_selected_answer_group") or "NA")
            post_group = str(meta.get("post_rerank_selected_answer_group") or meta.get("post_guard_selected_answer_group") or selected_group)

            rank_raw = rank_map(support_counts)
            rank_norm = rank_map(norm_support)
            rank_final = rank_map(final_scores)
            rank_ver = rank_map(verifier_scores)

            reason = selection_failure_reason(
                gold_group=gold_group,
                selected_group=selected_group,
                support_by_group=support_counts,
                normalized_support_by_group=norm_support,
                verifier_by_group=verifier_scores,
                process_by_group=process_scores,
                family_counts_by_group=family_counts_by_group,
                family_rerank_triggered=bool(method == "strict_f3_typed_strategy_family_normalized_rerank_v1"),
                selection_changed_by_family_rerank=bool(meta.get("selection_changed_by_family_rerank", False)),
            )
            before_correct = int(pre_group == gold_group and gold_group != "NA")
            after_correct = int(post_group == gold_group and gold_group != "NA")
            rerank_changed = int(bool(meta.get("selection_changed_by_family_rerank", False)))
            rerank_repaired = int(method == "strict_f3_typed_strategy_family_normalized_rerank_v1" and before_correct == 0 and after_correct == 1)
            rerank_hurt = int(method == "strict_f3_typed_strategy_family_normalized_rerank_v1" and before_correct == 1 and after_correct == 0)
            row = {
                "dataset": c.get("dataset", "openai/gsm8k"),
                "seed": seed,
                "budget": budget,
                "example_id": example_id,
                "question": question,
                "gold_answer": gold_text,
                "method": method,
                "selection_mode": str(meta.get("selection_mode", "NA")),
                "prediction": pred or "NA",
                "exact_match": exact,
                "failure_type": failure_type,
                "absent_from_tree": int(failure_type == "absent_from_tree"),
                "present_not_selected": int(failure_type == "present_not_selected"),
                "output_layer_mismatch": int(failure_type == "output_layer_mismatch"),
                "problem_type_label": problem_type,
                "pre_rerank_selected_answer_group": pre_group,
                "post_rerank_selected_answer_group": post_group,
                "selection_changed_by_family_rerank": rerank_changed,
                "family_rerank_repaired_case": rerank_repaired,
                "family_rerank_hurt_case": rerank_hurt,
                "gold_answer_group": gold_group,
                "gold_group_present": int(gold_group in support_counts),
                "selected_group_before_rerank_correct": before_correct,
                "selected_group_after_rerank_correct": after_correct,
                "gold_group_rank_by_raw_support": as_int(rank_raw.get(gold_group, -1), -1),
                "gold_group_rank_by_family_normalized_score": as_int(rank_norm.get(gold_group, -1), -1),
                "gold_group_rank_by_final_rerank": as_int(rank_final.get(gold_group, -1), -1),
                "selected_group_rank_by_raw_support": as_int(rank_raw.get(selected_group, -1), -1),
                "selected_group_rank_by_family_normalized_score": as_int(rank_norm.get(selected_group, -1), -1),
                "selected_group_rank_by_final_rerank": as_int(rank_final.get(selected_group, -1), -1),
                "score_gap_selected_minus_gold": as_float(final_scores.get(selected_group, 0.0) - final_scores.get(gold_group, 0.0)),
                "support_gap_selected_minus_gold": as_float(support_counts.get(selected_group, 0.0) - support_counts.get(gold_group, 0.0)),
                "family_count_gap_selected_minus_gold": as_float(family_counts_by_group.get(selected_group, 0) - family_counts_by_group.get(gold_group, 0)),
                "verifier_gap_selected_minus_gold": as_float(verifier_scores.get(selected_group, 0.0) - verifier_scores.get(gold_group, 0.0)),
                "process_gap_selected_minus_gold": as_float(process_scores.get(selected_group, 0.0) - process_scores.get(gold_group, 0.0)),
                "selection_failure_reason": reason,
                "actions_used": int(res.actions_used),
                "expansions": int(res.expansions),
                "verifications": int(res.verifications),
                "answer_group_support_counts": json.dumps(support_counts),
                "answer_group_final_scores": json.dumps(final_scores),
                "answer_group_strategy_family_counts": json.dumps(family_counts_nested),
                "transition_from_baseline_failure_type": f"{c.get('strict_f3_failure_type','NA')} -> {failure_type}",
            }
            for k, v in row.items():
                if v in ("", None):
                    missing_fields[k] += 1
            per_case.append(row)

            for gk in sorted(set(list(support_counts.keys()) + list(final_scores.keys()) + list(norm_support.keys()))):
                fam_counts = dict(family_counts_nested.get(gk, {}))
                raw_support_count = as_int(dict(meta.get("raw_support_count_by_answer_group") or {}).get(gk, support_counts.get(gk, 0)))
                norm_fraction = as_float(norm_support.get(gk, 0.0)) / max(1e-8, sum(norm_support.values()) or 1.0)
                mean_process = as_float(process_scores.get(gk, 0.0))
                mean_verifier = as_float(verifier_scores.get(gk, 0.0))
                diversity_score = as_float(diversity_scores.get(gk, 0.0))
                single_family_penalty = 1.0 if int(family_counts_by_group.get(gk, 0)) <= 1 else 0.0
                dominant_family_penalty = as_float(dict(meta.get("dominant_family_share_by_answer_group") or {}).get(gk, 0.0))
                group_payload = {
                    "method": method,
                    "example_id": example_id,
                    "seed": seed,
                    "budget": budget,
                    "answer_group": gk,
                    "raw_support_count": raw_support_count,
                    "discounted_support": as_float(support_counts.get(gk, 0.0)),
                    "family_normalized_support": as_float(norm_support.get(gk, 0.0)),
                    "supporting_strategy_families": sorted([k for k, v in fam_counts.items() if as_int(v) > 0]),
                    "num_supporting_strategy_families": int(family_counts_by_group.get(gk, 0)),
                    "family_support_counts": fam_counts,
                    "family_best_branch_scores": dict(parse_nested_scores(dict(meta.get("family_best_branch_scores_by_answer_group") or {})).get(gk, {})),
                    "family_mean_branch_scores": dict(parse_nested_scores(dict(meta.get("family_mean_branch_scores_by_answer_group") or {})).get(gk, {})),
                    "family_best_verifier_scores": dict(parse_nested_scores(dict(meta.get("family_best_verifier_scores_by_answer_group") or {})).get(gk, {})),
                    "family_mean_verifier_scores": dict(parse_nested_scores(dict(meta.get("family_mean_verifier_scores_by_answer_group") or {})).get(gk, {})),
                    "family_representative_scores": dict(parse_nested_scores(dict(meta.get("family_representative_scores_by_answer_group") or {})).get(gk, {})),
                    "normalized_support_fraction": norm_fraction,
                    "mean_process_score": mean_process,
                    "mean_verifier_score": mean_verifier,
                    "diversity_score": diversity_score,
                    "single_family_penalty": single_family_penalty,
                    "dominant_family_penalty": dominant_family_penalty,
                    "final_rerank_score": as_float(final_scores.get(gk, 0.0)),
                    "recomputed_family_normalized_full_score": family_normalized_full_score(
                        normalized_support_fraction=norm_fraction,
                        process_score=mean_process,
                        verifier_score=mean_verifier,
                        diversity_score=diversity_score,
                        single_family_penalty=single_family_penalty,
                        dominant_family_penalty=dominant_family_penalty,
                    ),
                    "rank_by_raw_support": as_int(rank_raw.get(gk, -1), -1),
                    "rank_by_family_normalized_score": as_int(rank_norm.get(gk, -1), -1),
                    "rank_by_verifier": as_int(rank_ver.get(gk, -1), -1),
                    "rank_by_final_rerank": as_int(rank_final.get(gk, -1), -1),
                }
                per_answer_group_scores.append(group_payload)

            if args.selection_ablation and method == "strict_f3_typed_strategy_family_normalized_rerank_v1":
                for rr in run_ablation(
                    support=support_counts,
                    norm_support=norm_support,
                    verifier=verifier_scores,
                    process=process_scores,
                    diversity=diversity_scores,
                    final=final_scores,
                    gold_group=gold_group,
                ):
                    selection_ablation_per_case.append(
                        {
                            "method": method,
                            "example_id": example_id,
                            "seed": seed,
                            "budget": budget,
                            **rr,
                        }
                    )

    write_csv(out_dir / "per_case_results.csv", per_case)
    write_jsonl(out_dir / "per_answer_group_scores.jsonl", per_answer_group_scores)
    write_csv(out_dir / "gold_vs_selected_diagnostics.csv", per_case)

    by_method: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in per_case:
        by_method[str(r["method"])].append(r)

    summary = []
    for m in methods:
        rows = by_method.get(m, [])
        n = max(1, len(rows))
        summary.append(
            {
                "method": m,
                "n": len(rows),
                "accuracy": sum(as_int(r.get("exact_match")) for r in rows) / n,
                "absent_from_tree_rate": sum(as_int(r.get("absent_from_tree")) for r in rows) / n,
                "present_not_selected_rate": sum(as_int(r.get("present_not_selected")) for r in rows) / n,
                "output_layer_mismatch_rate": sum(as_int(r.get("output_layer_mismatch")) for r in rows) / n,
                "counting_combinatorics_accuracy": (
                    sum(as_int(r.get("exact_match")) for r in rows if r.get("problem_type_label") == "counting_combinatorics")
                    / max(1, sum(1 for r in rows if r.get("problem_type_label") == "counting_combinatorics"))
                ),
                "avg_actions": sum(as_float(r.get("actions_used")) for r in rows) / n,
                "avg_expansions": sum(as_float(r.get("expansions")) for r in rows) / n,
            }
        )
    write_csv(out_dir / "summary.csv", summary)
    write_csv(out_dir / "slice_summary.csv", [{"slice": args.slice, **r} for r in summary])

    write_csv(
        out_dir / "present_not_selected_repairs.csv",
        [r for r in per_case if str(r.get("method")) == "strict_f3_typed_strategy_family_normalized_rerank_v1" and "present_not_selected -> correct" in str(r.get("transition_from_baseline_failure_type"))],
    )
    write_csv(
        out_dir / "absent_from_tree_repairs.csv",
        [r for r in per_case if str(r.get("method")) == "strict_f3_typed_strategy_family_normalized_rerank_v1" and "absent_from_tree -> correct" in str(r.get("transition_from_baseline_failure_type"))],
    )
    write_csv(
        out_dir / "hurt_cases.csv",
        [r for r in per_case if as_int(r.get("family_rerank_hurt_case")) == 1],
    )
    write_csv(
        out_dir / "verifier_score_diagnostics.csv",
        [
            {
                "method": r.get("method"),
                "example_id": r.get("example_id"),
                "verifier_gap_selected_minus_gold": r.get("verifier_gap_selected_minus_gold"),
            }
            for r in per_case
        ],
    )
    write_csv(
        out_dir / "family_vote_diagnostics.csv",
        [
            {
                "method": r.get("method"),
                "example_id": r.get("example_id"),
                "family_count_gap_selected_minus_gold": r.get("family_count_gap_selected_minus_gold"),
                "support_gap_selected_minus_gold": r.get("support_gap_selected_minus_gold"),
            }
            for r in per_case
        ],
    )

    if args.selection_ablation:
        write_csv(out_dir / "selection_ablation_per_case.csv", selection_ablation_per_case)
        by_rule: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for r in selection_ablation_per_case:
            by_rule[str(r.get("rule"))].append(r)
        write_csv(
            out_dir / "selection_ablation_summary.csv",
            [
                {
                    "rule": rule,
                    "n": len(rows),
                    "accuracy": sum(as_int(x.get("is_correct")) for x in rows) / max(1, len(rows)),
                    "gold_present_rate": sum(as_int(x.get("gold_present")) for x in rows) / max(1, len(rows)),
                }
                for rule, rows in by_rule.items()
            ],
            fieldnames=["rule", "n", "accuracy", "gold_present_rate"],
        )
    else:
        write_csv(out_dir / "selection_ablation_summary.csv", [], fieldnames=["rule", "n", "accuracy", "gold_present_rate"])
        write_csv(out_dir / "selection_ablation_per_case.csv", [], fieldnames=["method", "example_id", "seed", "budget", "rule", "selected_group", "gold_group", "is_correct", "gold_present"])

    write_csv(
        out_dir / "missing_fields_report.csv",
        [{"field": k, "missing_count": int(v)} for k, v in sorted(missing_fields.items(), key=lambda kv: kv[0])],
        fieldnames=["field", "missing_count"],
    )

    readme = [
        f"# family_normalized_rerank_eval_{args.timestamp}",
        "",
        "- diagnostic/probe run",
        f"- selection_mode: {args.selection_mode}",
        f"- selection_ablation: {bool(args.selection_ablation)}",
        f"- slice: {args.slice}",
        f"- dry_run: {bool(args.dry_run)}",
        f"- real_api_validation_pending: {bool(args.dry_run)}",
        f"- input_package: `{args.input_package}`",
    ]
    (out_dir / "README.md").write_text("\n".join(readme) + "\n", encoding="utf-8")

    s = {r["method"]: r for r in summary}
    base = s.get("strict_f3_typed_strategy_seeded_v1", {})
    new = s.get("strict_f3_typed_strategy_family_normalized_rerank_v1", {})
    report = REPO_ROOT / "docs" / f"FAMILY_NORMALIZED_RERANK_EVAL_{args.timestamp}.md"
    report.write_text(
        "\n".join(
            [
                f"# FAMILY_NORMALIZED_RERANK_EVAL_{args.timestamp}",
                "",
                f"1. Did family-normalized reranking reduce present-not-selected failures? {'yes' if as_float(new.get('present_not_selected_rate',1.0)) < as_float(base.get('present_not_selected_rate',1.0)) else 'no_or_neutral'}.",
                "2. Did it repair cases where gold was present but under-scored? See present_not_selected_repairs.csv and gold_vs_selected_diagnostics.csv.",
                "3. Did it hurt cases where raw support was already correct? See hurt_cases.csv.",
                f"4. Did it improve counting/combinatorics accuracy? {'yes' if as_float(new.get('counting_combinatorics_accuracy',0.0)) > as_float(base.get('counting_combinatorics_accuracy',0.0)) else 'no_or_neutral'}.",
                "5. Was improvement from family normalization, verifier, process, or diversity? Inspect selection_ablation_summary.csv.",
                "6. In repaired cases, was gold supported by fewer raw branches but more independent families? Check family_vote_diagnostics.csv + per_answer_group_scores.jsonl.",
                "7. In unrepaired cases, why did gold still lose? Check selection_failure_reason in gold_vs_selected_diagnostics.csv.",
                "8. How many cases are theoretically fixable by oracle-if-gold-present? See selection_ablation_summary.csv.",
                "9. Is bottleneck now selection or generation? Compare gold_group_present and oracle ceilings in selection_ablation files.",
                "10. Should this be candidate method or remain diagnostic? Keep diagnostic until real-API validation and broader slices improve.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    print(json.dumps({"status": "ok", "output_dir": str(out_dir.relative_to(REPO_ROOT)), "report": str(report.relative_to(REPO_ROOT))}, indent=2))


if __name__ == "__main__":
    main()

