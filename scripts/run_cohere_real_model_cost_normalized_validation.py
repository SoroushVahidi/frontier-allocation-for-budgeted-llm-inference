#!/usr/bin/env python3
from __future__ import annotations

import argparse
import atexit
import csv
import hashlib
import json
import os
import random
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.branching import APIBranchGenerator, configure_logical_api_call_budget
from experiments.data import PilotExample, normalize_answer_text
from experiments.frontier_matrix_core import ScoreConfig, SimpleBranchScorer, build_frontier_strategies, build_semantic_diversity_diagnostic_registry, load_pilot_examples
from experiments.output_layer_repair import (
    apply_controller_committed_surfacing_for_evaluation,
    apply_finalization_guard_surfacing,
    apply_pal_residual_strong_integration_fix,
    augment_final_nodes_with_metadata_frontier,
    canonicalize_answer,
    choose_repair_answer,
    gold_in_tree_from_nodes,
    resolve_selected_group_hint_from_metadata,
)
from experiments.trace_schema import build_branch_trace, write_trace_package
from scripts.compute_cohere_validation_disjointness import compute_disjointness
from scripts.failure_case_logging_schema import (
    EXPLICIT_NOT_SCORED_YET_MARKER,
    EXPLICIT_UNAVAILABLE_MARKER,
    EXPLICIT_UNAVAILABLE_NOT_RECORDED_MARKER,
    build_promotion_review_record,
    validate_promotion_review_record,
)

STRICT_F3 = "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth3_coverage_forced_v1"
STRICT_GATE1_CAP_K6 = "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_then_gate_v1_optimistic_collapse_first_hard_max_family_expansions_cap_k6_v1_fixed_k6_control"
STRICT_F2 = "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_coverage_forced_v1"
TARGET_STAGED_PAL_FRONTIER_RUNTIME = (
    "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal_structural_commit_v1_targeted_retry_v1"
)

METHODS: dict[str, dict[str, Any]] = {
    "strict_f3": {"runtime": STRICT_F3, "enable_output_repair": True},
    "strict_gate1_cap_k6": {"runtime": STRICT_GATE1_CAP_K6, "enable_output_repair": True},
    "strict_f3_anti_collapse_weak_v1": {"runtime": "strict_f3_anti_collapse_weak_v1", "enable_output_repair": True},
    "strict_f2": {"runtime": STRICT_F2, "enable_output_repair": True},
    "external_l1_max": {"runtime": "external_l1_max", "enable_output_repair": True},
    "external_l1_max_fair_v1": {"runtime": "external_l1_max_fair_v1", "enable_output_repair": True},
    "external_self_consistency_4_fair_v1": {"runtime": "external_self_consistency_4_fair_v1", "enable_output_repair": True},
    "external_self_consistency_6_fair_v1": {"runtime": "external_self_consistency_6_fair_v1", "enable_output_repair": True},
    "external_pal_pot_fair_v1": {"runtime": "external_pal_pot_fair_v1", "enable_output_repair": True},
    "direct_reserve_semantic_frontier_v1": {"runtime": "direct_reserve_frontier_gate_v1", "enable_output_repair": True},
    "direct_reserve_semantic_frontier_v2": {"runtime": "direct_reserve_frontier_gate_v2", "enable_output_repair": True},
    "direct_reserve_semantic_frontier_v2_selection_fix_v1": {"runtime": "direct_reserve_semantic_frontier_v2_selection_fix_v1", "enable_output_repair": True},
    "direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1": {
        "runtime": "direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1",
        "enable_output_repair": True,
    },
    "direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1": {
        "runtime": "direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1",
        "enable_output_repair": True,
    },
    "direct_reserve_semantic_frontier_v2_l1_direct_injection_v1": {
        "runtime": "direct_reserve_semantic_frontier_v2_l1_direct_injection_v1",
        "enable_output_repair": True,
    },
    "direct_reserve_semantic_frontier_v2_thresholded_ordered": {"runtime": "direct_reserve_semantic_frontier_v2_thresholded_ordered", "enable_output_repair": True},
    "direct_reserve_diverse_root_frontier_v1": {"runtime": "direct_reserve_diverse_root_frontier_v1", "enable_output_repair": True},
    "direct_reserve_diverse_root_frontier_v1_guarded": {"runtime": "direct_reserve_diverse_root_frontier_v1_guarded", "enable_output_repair": True},
    "direct_reserve_diverse_root_frontier_v1_guarded_k3": {
        "runtime": "direct_reserve_diverse_root_frontier_v1_guarded_k3",
        "enable_output_repair": True,
    },
    "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_diverse_anchor": {
        "runtime": "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_diverse_anchor",
        "enable_output_repair": True,
    },
    "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_stability_redundant_anchor_v1": {
        "runtime": "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_stability_redundant_anchor_v1",
        "enable_output_repair": True,
    },
    "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_uncertainty_retry_v1": {
        "runtime": "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_uncertainty_retry_v1",
        "enable_output_repair": True,
    },
    "direct_reserve_diverse_root_frontier_v1_guarded_k2_frontier2": {
        "runtime": "direct_reserve_diverse_root_frontier_v1_guarded_k2_frontier2",
        "enable_output_repair": True,
    },
    "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4": {
        "runtime": "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4",
        "enable_output_repair": True,
    },
    "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak": {
        "runtime": "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak",
        "enable_output_repair": True,
    },
    "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal": {
        "runtime": "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal",
        "enable_output_repair": True,
    },
    "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal_track_b_commitment_v1": {
        "runtime": "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal_track_b_commitment_v1",
        "enable_output_repair": True,
    },
    "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal_structural_commit_v1": {
        "runtime": "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal_structural_commit_v1",
        "enable_output_repair": True,
    },
    "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal_structural_commit_v1_targeted_retry_v1": {
        "runtime": "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal_structural_commit_v1_targeted_retry_v1",
        "enable_output_repair": True,
    },
    # Opt-in target-staged scaffold alias: keep the live runner on the existing PAL structural targeted-retry runtime.
    "target_staged_pal_frontier_v1": {
        "runtime": TARGET_STAGED_PAL_FRONTIER_RUNTIME,
        "enable_output_repair": True,
    },
    "ts_pal_frontier_v1": {
        "runtime": TARGET_STAGED_PAL_FRONTIER_RUNTIME,
        "enable_output_repair": True,
    },
    "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal_structural_commit_v1_adaptive_router_v3_final_target_verifier_v1": {
        "runtime": "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal_structural_commit_v1_adaptive_router_v3_final_target_verifier_v1",
        "enable_output_repair": True,
    },
    "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal_structural_commit_v1_production_equiv_v1": {
        "runtime": "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal_structural_commit_v1_production_equiv_v1",
        "enable_output_repair": True,
    },
    "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_finalguard": {
        "runtime": "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_finalguard",
        "enable_output_repair": True,
        "enable_finalization_guard": True,
    },
    "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_numeric_leaf": {
        "runtime": "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_numeric_leaf",
        "enable_output_repair": True,
    },
    "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_unit_track": {
        "runtime": "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_unit_track",
        "enable_output_repair": True,
    },
    "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_direct_hybrid": {
        "runtime": "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_direct_hybrid",
        "enable_output_repair": True,
    },
    "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_direct_l1_strong_seed_v1": {
        "runtime": "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_direct_l1_strong_seed_v1",
        "enable_output_repair": True,
    },
    "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_diverse_anchor": {
        "runtime": "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_diverse_anchor",
        "enable_output_repair": True,
    },
    "direct_reserve_frontier_gate_v1": {"runtime": "direct_reserve_frontier_gate_v1", "enable_output_repair": True},
    "near_direct_reserve_frontier_gate_v1": {"runtime": "near_direct_reserve_frontier_gate_v1", "enable_output_repair": True},
    "calibrated_near_direct_frontier_gate_v1": {"runtime": "calibrated_near_direct_frontier_gate_v1", "enable_output_repair": True},
    "tale": {"runtime": "external_tale_prompt_budgeting", "enable_output_repair": True},
    "external_tale_prompt_budgeting": {"runtime": "external_tale_prompt_budgeting", "enable_output_repair": True},
    "external_tale_ep_prompt_budgeting_faithful_v1": {
        "runtime": "external_tale_ep_prompt_budgeting_faithful_v1",
        "enable_output_repair": True,
    },
    "s1": {"runtime": "external_s1_budget_forcing", "enable_output_repair": True},
    "external_s1_budget_forcing": {"runtime": "external_s1_budget_forcing", "enable_output_repair": True},
    "external_s1_budget_forcing_faithful_v1": {
        "runtime": "external_s1_budget_forcing_faithful_v1",
        "enable_output_repair": True,
    },
    "self_consistency_3": {"runtime": "self_consistency_3", "enable_output_repair": True},
    # Explicit root strategy seeding + semantic maturation frontier (diagnostic; see docs in experiment module).
    "strategy_seeded_semantic_diversity_frontier_v1": {
        "runtime": "strategy_seeded_semantic_diversity_frontier_v1",
        "enable_output_repair": True,
    },
    "direct_reserve_strategy_seeded_semantic_frontier_v2_final": {
        "runtime": "direct_reserve_strategy_seeded_semantic_frontier_v2_final",
        "enable_output_repair": True,
    },
}

DEFAULT_PROVIDERS = "cohere"
DEFAULT_DATASETS = "openai/gsm8k,HuggingFaceH4/MATH-500,HuggingFaceH4/aime_2024"
DEFAULT_METHODS = "strict_f3,strict_gate1_cap_k6,strict_f2,external_l1_max,self_consistency_3"
DEFAULT_BUDGETS = "4,6,8"
DEFAULT_SEEDS = "11,23"


@dataclass(frozen=True)
class CaseKey:
    dataset: str
    seed: int
    budget: int
    method: str
    example_id: str


class ObservedGenerator:
    def __init__(self, base: APIBranchGenerator) -> None:
        self.base = base
        self.registry: dict[str, Any] = {}

    def init_branch(self, branch_id: str) -> Any:
        b = self.base.init_branch(branch_id)
        self.registry[b.branch_id] = b
        return b

    def expand(self, branch: Any, question: str, gold_answer: str) -> Any:
        return self.base.expand(branch, question, gold_answer)

    def verify(self, branch: Any, question: str) -> Any:
        return self.base.verify(branch, question)

    def prune(self, branch: Any) -> Any:
        return self.base.prune(branch)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Real-model cost-normalized validation (provider-aware, resumable)")
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    p.add_argument("--providers", default=DEFAULT_PROVIDERS)
    p.add_argument("--provider", default="", help="Deprecated alias for single-provider runs.")
    p.add_argument("--cohere-model", default="command-r-plus-08-2024")
    p.add_argument("--openai-model", default="gpt-4o-mini")
    p.add_argument("--datasets", default=DEFAULT_DATASETS)
    p.add_argument("--budgets", default=DEFAULT_BUDGETS)
    p.add_argument("--seeds", default=DEFAULT_SEEDS)
    p.add_argument("--methods", default=DEFAULT_METHODS)
    p.add_argument("--target-scored-per-slice", type=int, default=100)
    p.add_argument("--max-examples", type=int, default=0, help="Max attempted examples per dataset/seed/budget/method slice; 0=use target")
    p.add_argument("--temperature", type=float, default=0.1)
    p.add_argument("--max-output-tokens", type=int, default=220)
    p.add_argument("--timeout-seconds", type=int, default=45)
    p.add_argument("--input-cost-per-1k", type=float, default=0.003)
    p.add_argument("--output-cost-per-1k", type=float, default=0.015)
    p.add_argument("--resume", action="store_true")
    p.add_argument("--summarize-only", action="store_true", help="Skip new API calls and only recompute aggregate artifacts from existing records.")
    p.add_argument("--output-root", default="outputs")
    p.add_argument("--save-branch-traces", action="store_true")
    p.add_argument("--emit-trace-audit", action="store_true", help="Emit compact per-case DR-v2 vs external_l1_max trace-audit CSV.")
    p.add_argument("--validate-methods-only", action="store_true", help="Validate requested method IDs resolve to runnable strategy specs and exit without API calls.")
    p.add_argument("--allowed-example-ids-file", default="", help="Optional JSONL file containing rows with example_id (and optional dataset/seed/budget/method) to hard-filter runs.")
    p.add_argument("--exact-cases-jsonl", default="", help="Optional exact-case JSONL with example_id, question/problem_text, and gold answer; bypasses shuffled dataset loading.")
    p.add_argument(
        "--disjointness-prior-jsonl",
        action="append",
        default=[],
        help="Optional prior JSONL artifact to compare against exact cases for overlap (repeatable).",
    )
    p.add_argument(
        "--disjointness-prior-label",
        action="append",
        default=[],
        help="Optional labels aligned with --disjointness-prior-jsonl order.",
    )
    p.add_argument(
        "--disjointness-proof-json",
        default="",
        help="Optional explicit output path for disjointness_proof.json (default: <run_output_root>/disjointness_proof.json).",
    )
    p.add_argument(
        "--allow-disjointness-overlap",
        action="store_true",
        help="Allow overlaps in disjointness preflight (default is fail on overlap).",
    )
    p.add_argument("--validate-exact-cases-only", action="store_true", help="Validate exact-case JSONL and method resolution without API calls, then exit.")
    p.add_argument("--expected-exact-case-count", type=int, default=0, help="Optional expected number of cases for --validate-exact-cases-only.")
    p.add_argument("--dry-run-call-plan", action="store_true", help="Emit planned case count after filtering and exit without API calls.")
    p.add_argument(
        "--max-total-api-calls",
        type=int,
        default=0,
        help="Optional global cap on logical APIBranchGenerator calls (0=unlimited). Enforced across the whole run.",
    )
    p.add_argument(
        "--pal-residual-strong-integration-fix",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Apply evaluator-time PAL residual strong-integration replay on *_tiebreak_pal-method rows.",
    )
    return p.parse_args()


def validate_methods_only(args: argparse.Namespace, providers: list[str], budgets: list[int], methods: list[str]) -> Path:
    rows: list[dict[str, Any]] = []
    for m in methods:
        if m not in METHODS:
            rows.append({"provider": "all", "budget": "all", "method": m, "runtime": "", "status": "unknown_method", "detail": "method missing from METHODS registry"})
    for provider in providers:
        for budget in budgets:
            rng = random.Random(1000003 * 11 + 97 * budget + len("openai/gsm8k"))
            runner_specs = build_frontier_strategies(
                lambda: None,
                budget,
                [1],
                rng,
                use_openai_api=(provider == "openai"),
                include_broad_diversity_aggregation_methods=True,
                include_external_l1_baseline=True,
                include_external_s1_baseline=True,
                include_external_tale_baseline=True,
            )
            diagnostic_specs = build_semantic_diversity_diagnostic_registry(lambda: None, SimpleBranchScorer(ScoreConfig()), budget)
            for m in methods:
                runtime = METHODS.get(m, {}).get("runtime", "")
                registered = m in METHODS
                runtime_in_runner = bool(runtime and runtime in runner_specs)
                runtime_in_diag = bool(runtime and runtime in diagnostic_specs)
                if not registered:
                    status = "excluded"
                    reason = "method missing from METHODS registry"
                elif runtime_in_runner:
                    status = "runnable"
                    reason = "runtime present in runner build_frontier_strategies specs"
                elif runtime_in_diag:
                    status = "diagnostic_only"
                    reason = "runtime only present in semantic diversity diagnostic registry, not in runner specs"
                else:
                    status = "runtime_missing"
                    reason = "runtime not found in runner specs"
                rows.append(
                    {
                        "provider": provider,
                        "budget": budget,
                        "method_id": m,
                        "registered_in_METHODS": "yes" if registered else "no",
                        "runtime_id": runtime,
                        "runtime_present_in_build_frontier_strategies": "yes" if runtime_in_runner else "no",
                        "validation_status": status,
                        "reason": reason,
                    }
                )
    out_dir = REPO_ROOT / args.output_root / f"cohere_real_model_cost_normalized_validation_{args.timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "method_validation_report.csv"
    write_csv(report_path, rows, fieldnames=["provider", "budget", "method_id", "registered_in_METHODS", "runtime_id", "runtime_present_in_build_frontier_strategies", "validation_status", "reason"])
    bad = [r for r in rows if r["validation_status"] != "runnable"]
    print(f"validate-methods-only report: {report_path}")
    print(f"validated_rows={len(rows)} bad_rows={len(bad)}")
    if bad:
        raise SystemExit(2)
    raise SystemExit(0)


def parse_csv_list(text: str) -> list[str]:
    return [x.strip() for x in text.split(",") if x.strip()]


def parse_csv_ints(text: str) -> list[int]:
    return [int(x.strip()) for x in text.split(",") if x.strip()]


def write_csv(path: Path, rows: list[dict[str, Any]], *, fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        with path.open("w", encoding="utf-8", newline="") as f:
            if fieldnames:
                w = csv.DictWriter(f, fieldnames=fieldnames)
                w.writeheader()
            else:
                f.write("")
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames or list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def mean(vals: list[float]) -> float:
    return float(sum(vals) / len(vals)) if vals else 0.0


def _is_dr_v2_method(method: str) -> bool:
    return method.strip() == "direct_reserve_semantic_frontier_v2"


def _is_external_l1_method(method: str) -> bool:
    return method.strip() == "external_l1_max"


def classify_failure(error_text: str) -> str:
    t = error_text.lower()
    if "401" in t or "unauthorized" in t or "invalid api" in t:
        return "authentication failure"
    if "quota" in t or "insufficient" in t:
        return "quota failure"
    if "429" in t or "rate" in t:
        return "rate limit"
    if "timed out" in t or "network" in t or "temporary failure" in t:
        return "network error"
    if "model" in t and ("not found" in t or "unavailable" in t):
        return "model unavailable"
    return "other"


def normalize_providers(args: argparse.Namespace) -> list[str]:
    if args.provider:
        providers = [args.provider]
    else:
        providers = parse_csv_list(args.providers)
    normed = [p.strip().lower() for p in providers if p.strip()]
    allowed = {"cohere", "openai"}
    bad = [p for p in normed if p not in allowed]
    if bad:
        raise ValueError(f"Unsupported provider(s): {bad}; allowed={sorted(allowed)}")
    if not normed:
        raise ValueError("At least one provider is required.")
    return normed


def load_allowed_case_filter(path_text: str) -> dict[tuple[str, int, int, str], dict[str, dict[str, Any]]]:
    if not path_text:
        return {}
    path = Path(path_text)
    rows = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    allow: dict[tuple[str, int, int, str], dict[str, dict[str, Any]]] = {}
    for r in rows:
        dataset = str(r.get("dataset", "openai/gsm8k"))
        seed = int(r.get("seed", 11))
        budget = int(r.get("budget", 4))
        method = str(r.get("our_method_name", r.get("method", "direct_reserve_semantic_frontier_v2")))
        example_id = str(r.get("example_id"))
        allow.setdefault((dataset, seed, budget, method), {})[example_id] = dict(r)
    return allow


def _normalize_exact_question(text: str) -> str:
    return " ".join(str(text or "").split())


def load_exact_case_rows(path_text: str, *, dataset: str = "openai/gsm8k") -> list[dict[str, Any]]:
    """Load exact replay cases from JSONL without shuffling or external dataset access."""
    if not path_text:
        return []
    path = Path(path_text)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        example_id = str(row.get("example_id") or row.get("case_id") or "").strip()
        question = str(row.get("question") or row.get("problem_text") or "").strip()
        gold_raw = row.get("gold_answer_canonical", row.get("gold_canonical", row.get("gold_answer", row.get("gold"))))
        if not example_id:
            raise ValueError(f"{path}:{line_no}: missing example_id/case_id")
        if example_id in seen:
            raise ValueError(f"{path}:{line_no}: duplicate example_id {example_id!r}")
        if not question:
            raise ValueError(f"{path}:{line_no}: missing question/problem_text for {example_id}")
        if gold_raw is None or str(gold_raw).strip() == "":
            raise ValueError(f"{path}:{line_no}: missing gold answer for {example_id}")
        gold_can = canonicalize_answer(str(gold_raw), dataset=dataset)
        if gold_can is None:
            raise ValueError(f"{path}:{line_no}: could not canonicalize gold answer for {example_id}: {gold_raw!r}")
        out = dict(row)
        out["example_id"] = example_id
        out["question"] = question
        out["gold_answer_canonical"] = str(gold_can)
        out.setdefault("dataset", dataset)
        out["question_normalized_for_replay"] = _normalize_exact_question(question)
        rows.append(out)
        seen.add(example_id)
    return rows


def exact_case_rows_to_examples(rows: list[dict[str, Any]]) -> list[PilotExample]:
    return [PilotExample(example_id=str(r["example_id"]), question=str(r["question"]), answer=str(r["gold_answer_canonical"])) for r in rows]


def validate_exact_case_examples(rows: list[dict[str, Any]], examples: list[PilotExample], *, dataset: str = "openai/gsm8k") -> list[dict[str, Any]]:
    """Return mismatch rows; an empty list means exact replay cases match the runner examples."""
    mismatches: list[dict[str, Any]] = []
    if len(rows) != len(examples):
        mismatches.append({"type": "count_mismatch", "expected_rows": len(rows), "runner_examples": len(examples)})
    for idx, (row, ex) in enumerate(zip(rows, examples)):
        expected_answer = canonicalize_answer(str(row.get("gold_answer_canonical") or row.get("gold_answer") or row.get("gold")), dataset=dataset)
        actual_answer = canonicalize_answer(str(ex.answer), dataset=dataset)
        expected_question_norm = _normalize_exact_question(str(row.get("question") or row.get("problem_text") or ""))
        actual_question_norm = _normalize_exact_question(ex.question)
        if str(row.get("example_id")) != str(ex.example_id):
            mismatches.append({"type": "example_id_mismatch", "index": idx, "expected": row.get("example_id"), "actual": ex.example_id})
        if expected_question_norm != actual_question_norm:
            mismatches.append({"type": "question_mismatch", "index": idx, "example_id": row.get("example_id"), "expected": expected_question_norm, "actual": actual_question_norm})
        if expected_answer != actual_answer:
            mismatches.append({"type": "gold_mismatch", "index": idx, "example_id": row.get("example_id"), "expected": expected_answer, "actual": actual_answer})
    return mismatches


def resolve_examples_for_dataset(dataset: str, *, subset_size: int, seed: int, exact_case_rows: list[dict[str, Any]] | None = None) -> list[PilotExample]:
    if exact_case_rows is not None:
        filtered = [r for r in exact_case_rows if str(r.get("dataset", dataset)) == dataset]
        return exact_case_rows_to_examples(filtered)
    return load_pilot_examples(dataset, subset_size=subset_size, seed=seed)


def validate_exact_cases_only(args: argparse.Namespace, providers: list[str], datasets: list[str], budgets: list[int], methods: list[str]) -> None:
    if not args.exact_cases_jsonl:
        raise SystemExit("--validate-exact-cases-only requires --exact-cases-jsonl")
    out_dir = REPO_ROOT / args.output_root / f"cohere_real_model_cost_normalized_validation_{args.timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    all_rows: list[dict[str, Any]] = []
    all_mismatches: list[dict[str, Any]] = []
    per_dataset: list[dict[str, Any]] = []
    for dataset in datasets:
        rows = load_exact_case_rows(args.exact_cases_jsonl, dataset=dataset)
        examples = resolve_examples_for_dataset(dataset, subset_size=len(rows), seed=0, exact_case_rows=rows)
        mismatches = validate_exact_case_examples(rows, examples, dataset=dataset)
        all_rows.extend(rows)
        all_mismatches.extend(mismatches)
        per_dataset.append({"dataset": dataset, "case_count": len(rows), "mismatch_count": len(mismatches)})
    method_rows: list[dict[str, Any]] = []
    for provider in providers:
        for budget in budgets:
            rng = random.Random(1000003 * 11 + 97 * budget + len(datasets[0] if datasets else ""))
            runner_specs = build_frontier_strategies(
                lambda: None,
                budget,
                [1],
                rng,
                use_openai_api=(provider == "openai"),
                include_broad_diversity_aggregation_methods=True,
                include_external_l1_baseline=True,
                include_external_s1_baseline=True,
                include_external_tale_baseline=True,
            )
            for method in methods:
                runtime = METHODS.get(method, {}).get("runtime", "")
                ok = bool(runtime and runtime in runner_specs)
                method_rows.append({"provider": provider, "budget": budget, "method_id": method, "runtime_id": runtime, "runnable_without_api": ok})
                if not ok:
                    all_mismatches.append({"type": "method_not_runnable", "provider": provider, "budget": budget, "method_id": method, "runtime_id": runtime})
    if args.expected_exact_case_count and len(all_rows) != args.expected_exact_case_count:
        all_mismatches.append({"type": "expected_case_count_mismatch", "expected": args.expected_exact_case_count, "actual": len(all_rows)})
    report = {
        "exact_cases_jsonl": args.exact_cases_jsonl,
        "case_count": len(all_rows),
        "expected_case_count": args.expected_exact_case_count or None,
        "datasets": per_dataset,
        "methods": method_rows,
        "mismatch_count": len(all_mismatches),
        "mismatches": all_mismatches,
        "api_calls_made": 0,
        "shuffled_loader_used": False,
    }
    report_path = out_dir / "exact_case_validation_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"exact-case validation report: {report_path}")
    print(f"exact_case_count={len(all_rows)} mismatch_count={len(all_mismatches)} api_calls_made=0 shuffled_loader_used=false")
    if all_mismatches:
        raise SystemExit(2)
    raise SystemExit(0)


def maybe_compute_disjointness_preflight(
    *,
    args: argparse.Namespace,
    out_dir: Path,
) -> Path | None:
    """Optionally compute hardened disjointness proof and enforce overlap policy.

    Runs only when both exact cases and one or more prior artifacts are provided.
    """
    if not args.exact_cases_jsonl or not args.disjointness_prior_jsonl:
        return None

    prior_paths = [Path(p) for p in args.disjointness_prior_jsonl]
    missing = [str(p) for p in prior_paths if not p.exists()]
    if missing:
        raise FileNotFoundError(
            "Missing --disjointness-prior-jsonl file(s): " + ", ".join(missing)
        )

    labels = args.disjointness_prior_label or None
    if labels is not None and len(labels) > 0 and len(labels) != len(prior_paths):
        raise ValueError(
            "--disjointness-prior-label count must match --disjointness-prior-jsonl count"
        )

    selected_cases_path = Path(args.exact_cases_jsonl)
    proof = compute_disjointness(
        selected_cases_jsonl=selected_cases_path,
        prior_jsonls=prior_paths,
        source_labels=labels,
    )

    proof_path = Path(args.disjointness_proof_json) if args.disjointness_proof_json else (out_dir / "disjointness_proof.json")
    proof_path.parent.mkdir(parents=True, exist_ok=True)
    proof_path.write_text(json.dumps(proof, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        "disjointness preflight:"
        f" selected={proof['selected_count']}"
        f" overlap_ids={proof['overlap_example_ids_with_prior']}"
        f" overlap_questions={proof['overlap_questions_with_prior']}"
        f" proof={proof_path}"
    )

    if (not args.allow_disjointness_overlap) and int(proof.get("overlap_example_ids_with_prior", 0)) > 0:
        raise RuntimeError(
            "Disjointness preflight failed: overlap detected with prior artifacts "
            f"({proof.get('overlap_example_ids_with_prior', 0)} overlapping example_ids). "
            "Pass --allow-disjointness-overlap to bypass intentionally."
        )

    return proof_path


def ensure_cohere_readiness(*, model: str, timestamp: str) -> tuple[bool, str]:
    key = os.getenv("COHERE_API_KEY", "") or os.getenv("CO_API_KEY", "")
    checked = ["COHERE_API_KEY", "CO_API_KEY"]
    status = "present" if key else "missing_or_empty"
    if not key:
        err = "Neither COHERE_API_KEY nor CO_API_KEY is set"
        report_path = write_readiness_failure_report(
            timestamp=timestamp,
            checked_envs=checked,
            env_state={"COHERE_API_KEY": status},
            failure_type="missing key",
            command_attempted="python scripts/run_cohere_real_model_cost_normalized_validation.py ...",
            error_message=err,
            remediation="Set COHERE_API_KEY to a valid Cohere API key and rerun.",
        )
        print("Cohere experiment cancelled before execution because Cohere API access was not usable.")
        print(f"Failure report: {report_path}")
        return False, err

    try:
        import cohere  # type: ignore
    except ModuleNotFoundError:
        install_cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "cohere"]
        subprocess.run(install_cmd, check=False)
        try:
            import cohere  # type: ignore # noqa: F401
        except Exception as exc:  # noqa: BLE001
            err = f"Module import failed after installation attempt: {type(exc).__name__}: {str(exc)[:500]}"
            report_path = write_readiness_failure_report(
                timestamp=timestamp,
                checked_envs=checked,
                env_state={"COHERE_API_KEY": status},
                failure_type="SDK/import problem",
                command_attempted="python -m pip install --upgrade cohere && tiny cohere chat request",
                error_message=err,
                remediation="Ensure pip install succeeds in this runtime and rerun readiness.",
            )
            print("Cohere experiment cancelled before execution because Cohere API access was not usable.")
            print(f"Failure report: {report_path}")
            return False, err

    cmd = [
        sys.executable,
        "-c",
        (
            "import os,cohere;"
            "c=cohere.ClientV2(api_key=os.environ['COHERE_API_KEY']);"
            f"r=c.chat(model='{model}',messages=[{{'role':'user','content':'Reply with exactly: OK'}}],max_tokens=4);"
            "print('READINESS_OK',bool(r))"
        ),
    ]
    probe_env = {**os.environ, "COHERE_API_KEY": key}
    try:
        probe = subprocess.run(cmd, capture_output=True, text=True, timeout=90, env=probe_env)
    except subprocess.TimeoutExpired:
        err = "cohere readiness probe timed out after 90s"
        report_path = write_readiness_failure_report(
            timestamp=timestamp,
            checked_envs=checked,
            env_state={"COHERE_API_KEY": status},
            failure_type="network timeout",
            command_attempted=" ".join(cmd),
            error_message=err,
            remediation="Retry; if persistent, verify Cohere network reachability from this environment.",
        )
        print("Cohere experiment cancelled before execution because Cohere API access was not usable.")
        print(f"Failure report: {report_path}")
        return False, err
    if probe.returncode != 0:
        err = (probe.stderr or probe.stdout or "unknown readiness failure")[:1000]
        report_path = write_readiness_failure_report(
            timestamp=timestamp,
            checked_envs=checked,
            env_state={"COHERE_API_KEY": status},
            failure_type=classify_failure(err),
            command_attempted=" ".join(cmd),
            error_message=err,
            remediation="Verify key validity/permissions/quota/network/model availability and rerun.",
        )
        print("Cohere experiment cancelled before execution because Cohere API access was not usable.")
        print(f"Failure report: {report_path}")
        return False, err
    print("Cohere readiness check passed: tiny authenticated request succeeded.")
    return True, "ok"


def ensure_openai_readiness(*, timestamp: str) -> tuple[bool, str]:
    key = os.getenv("OPENAI_API_KEY", "")
    if not key:
        return False, "OPENAI_API_KEY is missing or empty"
    cmd = [
        sys.executable,
        "-c",
        "import os; assert os.environ.get('OPENAI_API_KEY'); print('READINESS_OK', True)",
    ]
    probe = subprocess.run(cmd, capture_output=True, text=True)
    if probe.returncode != 0:
        err = (probe.stderr or probe.stdout or "unknown readiness failure")[:1000]
        return False, err
    return True, "ok"


def write_readiness_failure_report(
    *,
    timestamp: str,
    checked_envs: list[str],
    env_state: dict[str, str],
    failure_type: str,
    command_attempted: str,
    error_message: str,
    remediation: str,
) -> str:
    docs = REPO_ROOT / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    path = docs / f"COHERE_API_READINESS_FAILURE_{timestamp}.md"
    lines = [
        "# Cohere API Readiness Failure Report",
        "",
        f"- Timestamp (UTC): {timestamp}",
        "",
        "## 1) Environment variables checked (names only)",
        *[f"- `{x}`" for x in checked_envs],
        "",
        "## 2) Presence status",
        *[f"- `{k}`: {v}" for k, v in env_state.items()],
        "",
        "## 3) Failure type",
        f"- {failure_type}",
        "",
        "## 4) Exact command attempted",
        "```bash",
        command_attempted,
        "```",
        "",
        "## 5) Sanitized exception/error message",
        "```text",
        error_message.replace(os.getenv("COHERE_API_KEY", ""), "[REDACTED]") if os.getenv("COHERE_API_KEY") else error_message,
        "```",
        "",
        "## 6) What must be fixed before rerunning",
        f"- {remediation}",
        "",
        "## 7) Cancellation line",
        "**Cohere experiment cancelled before execution because Cohere API access was not usable.**",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path.relative_to(REPO_ROOT))


def to_case_key(row: dict[str, Any]) -> CaseKey:
    provider = str(row.get("provider", "cohere"))
    method = str(row["method"])
    scoped_method = method if method.startswith(f"{provider}:") else f"{provider}:{method}"
    return CaseKey(
        dataset=str(row["dataset"]),
        seed=int(row["seed"]),
        budget=int(row["budget"]),
        method=scoped_method,
        example_id=str(row["example_id"]),
    )


def load_existing_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def append_progress(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _error_type_from_text(error_text: str) -> str:
    text = str(error_text or "").strip()
    if not text:
        return ""
    head = text.split(":", 1)[0].strip()
    return head if head and " " not in head else ""


def _runtime_cap_reached(error_text: str) -> bool:
    t = str(error_text or "").lower()
    return "logical api call cap reached" in t


def _candidate_trace_from_nodes(
    nodes: list[dict[str, Any]],
    *,
    selected_answer_raw: Any,
    selected_answer_canonical: Any,
) -> str:
    sel_raw = str(selected_answer_raw or "").strip()
    sel_can = str(selected_answer_canonical or "").strip()
    fallback = ""
    for node in nodes:
        trace = str(node.get("reasoning_text") or node.get("trace") or "").strip()
        if not trace:
            continue
        if not fallback:
            fallback = trace
        node_raw = str(node.get("predicted_answer") or "").strip()
        node_can = str(node.get("predicted_answer_normalized") or "").strip()
        if sel_can and node_can and sel_can == node_can:
            return trace
        if sel_raw and node_raw and sel_raw == node_raw:
            return trace
    return fallback


def _selected_node_id_from_nodes(
    nodes: list[dict[str, Any]],
    *,
    selected_answer_raw: Any,
    selected_answer_canonical: Any,
) -> str:
    sel_raw = str(selected_answer_raw or "").strip()
    sel_can = str(selected_answer_canonical or "").strip()
    for node in nodes:
        node_raw = str(node.get("predicted_answer") or "").strip()
        node_can = str(node.get("predicted_answer_normalized") or "").strip()
        if (sel_can and node_can and sel_can == node_can) or (sel_raw and node_raw and sel_raw == node_raw):
            return str(node.get("branch_id") or "")
    return ""


def _node_expansion_order_from_metadata(md: dict[str, Any]) -> list[Any]:
    action_trace = md.get("action_trace")
    if not isinstance(action_trace, list):
        return []
    order: list[Any] = []
    for ev in action_trace:
        if not isinstance(ev, dict):
            continue
        if str(ev.get("action") or "") != "expand":
            continue
        order.append(ev.get("branch_id") or ev.get("node_id") or ev.get("family_id") or dict(ev))
    return order


def _prune_or_selection_reasons_from_metadata(md: dict[str, Any]) -> list[dict[str, Any]]:
    action_trace = md.get("action_trace")
    out: list[dict[str, Any]] = []
    if isinstance(action_trace, list):
        for ev in action_trace:
            if not isinstance(ev, dict):
                continue
            action = str(ev.get("action") or "")
            if action in {"prune", "select", "selection", "commit"}:
                out.append(
                    {
                        "action": action,
                        "branch_id": ev.get("branch_id"),
                        "reason": ev.get("reason") or ev.get("prune_reason") or ev.get("selection_reason"),
                    }
                )
    if out:
        return out
    selected_group = md.get("selected_group") or md.get("final_answer_group")
    selection_reason = md.get("selection_reason")
    if selected_group or selection_reason:
        return [{"action": "selection", "selected_group": selected_group, "reason": selection_reason}]
    return []


def _prompt_hash_from_row(row: dict[str, Any]) -> str:
    question = str(row.get("question") or "").strip()
    if not question:
        return ""
    return "question_sha256:" + hashlib.sha256(question.encode("utf-8")).hexdigest()


def build_promotion_review_fields_for_record(
    row: dict[str, Any],
    *,
    run_id: str,
    artifact_label: str,
) -> dict[str, Any]:
    md = dict(row.get("result_metadata", {}) or {})
    final_nodes = list(row.get("final_nodes", []) or [])
    selected_answer_raw = row.get("selected_answer_raw") or row.get("final_answer_raw")
    selected_answer_canonical = row.get("selected_answer_canonical") or row.get("final_answer_canonical")
    status = str(row.get("status") or "")
    status_lower = status.strip().lower()
    err_text = str(row.get("error") or "")
    runtime_cap_reached = _runtime_cap_reached(err_text)
    is_runtime_failure = runtime_cap_reached or status_lower in {"failed", "runtime_cap", "timeout", "parse_failed"}

    candidate_trace = _candidate_trace_from_nodes(
        final_nodes,
        selected_answer_raw=selected_answer_raw,
        selected_answer_canonical=selected_answer_canonical,
    )
    selected_node_id = _selected_node_id_from_nodes(
        final_nodes,
        selected_answer_raw=selected_answer_raw,
        selected_answer_canonical=selected_answer_canonical,
    )
    prompt_hash = _prompt_hash_from_row(row)
    prune_or_selection_reasons = _prune_or_selection_reasons_from_metadata(md)
    if not prune_or_selection_reasons:
        prune_or_selection_reasons = (
            EXPLICIT_UNAVAILABLE_MARKER if is_runtime_failure else EXPLICIT_UNAVAILABLE_NOT_RECORDED_MARKER
        )
    verifier_scores = (
        md.get("verifier_scores")
        or md.get("outcome_verifier_scores")
        or md.get("prm_step_scores")
    )
    verifier_scores_pointer: Any = None
    if not verifier_scores:
        verifier_scores_pointer = EXPLICIT_NOT_SCORED_YET_MARKER
    raw_proba_ready = md.get("raw_proba_ready")
    calibrated_percentile = md.get("calibrated_percentile")
    if raw_proba_ready is None and calibrated_percentile is None:
        raw_proba_ready = EXPLICIT_NOT_SCORED_YET_MARKER
    candidate_pool_summary = (
        md.get("answer_group_support_counts")
        or md.get("candidate_pool_summary")
        or {"final_nodes_count": len(final_nodes)}
    )

    promotion_source = {
        "run_id": run_id,
        "artifact_label": artifact_label,
        "example_id": row.get("example_id"),
        "problem_id": row.get("example_id"),
        "dataset": row.get("dataset"),
        "provider": row.get("provider"),
        "model": row.get("model"),
        "method": row.get("method"),
        "budget": row.get("budget"),
        "seed": row.get("seed"),
        "problem_text": row.get("question"),
        "question": row.get("question"),
        "prompt_hash": prompt_hash,
        "candidate_answer": selected_answer_raw,
        "candidate_trace": candidate_trace,
        "candidate_answer_canonical": selected_answer_canonical,
        "parse_success": int(not bool(row.get("parse_extraction_failure"))),
        "parser_status": "ok" if not bool(row.get("parse_extraction_failure")) else "parse_failed",
        "parser_error": "",
        "status": status,
        "runtime_cap_reached": runtime_cap_reached,
        "error_type": _error_type_from_text(err_text),
        "error_message": err_text,
        "partial_answer_present": bool(str(selected_answer_raw or "").strip()),
        "partial_trace_present": bool(str(candidate_trace).strip()),
        "discovery_tree": final_nodes,
        "node_expansion_order": _node_expansion_order_from_metadata(md),
        "final_nodes": final_nodes,
        "selected_node_id": selected_node_id,
        "prune_or_selection_reasons": prune_or_selection_reasons,
        "candidate_pool_summary": candidate_pool_summary,
        "call_count": row.get("cohere_logical_api_calls"),
        "prompt_tokens": row.get("input_tokens"),
        "completion_tokens": row.get("output_tokens"),
        "total_tokens": row.get("total_tokens"),
        "estimated_cost": row.get("estimated_cost_usd"),
        "latency_seconds": row.get("latency_seconds"),
        "verifier_scores": verifier_scores or {},
        "verifier_scores_pointer": verifier_scores_pointer,
        "raw_proba_ready": raw_proba_ready,
        "calibrated_percentile": calibrated_percentile,
        "gate_features": md.get("gate_features") or {},
        "gate_decision": md.get("gate_decision") or ("scored" if status == "scored" else "failed_runtime"),
        "policy_family": md.get("policy_family") or "unknown",
        "policy_thresholds": md.get("policy_thresholds") or {},
        "exact_match": row.get("exact_match"),
        "gold_answer": row.get("gold_answer"),
        "offline_eval_only": True,
    }
    promotion_review_record = build_promotion_review_record(
        promotion_source, fill_explicit_failure_state=True
    )
    promotion_review_validation = validate_promotion_review_record(promotion_review_record)
    return {
        "promotion_review_record": promotion_review_record,
        "promotion_review_validation": promotion_review_validation,
    }


def evaluate_example(
    result: Any,
    dataset: str,
    gold_answer: str,
    final_nodes: list[dict[str, Any]],
    enable_output_repair: bool,
    *,
    enable_finalization_guard: bool = False,
    enable_pal_residual_strong_integration_fix: bool = False,
) -> int:
    md = result.metadata or {}
    hint = resolve_selected_group_hint_from_metadata(md, dataset=dataset) or md.get("selected_group")
    repaired = choose_repair_answer(
        final_nodes=final_nodes,
        selected_group_hint=hint,
        dataset=dataset,
        enable_rescue=bool(enable_output_repair),
    )
    repaired = apply_controller_committed_surfacing_for_evaluation(md, repaired, dataset=dataset)
    repaired, _pal_integration = apply_pal_residual_strong_integration_fix(
        md,
        repaired,
        dataset=dataset,
        enabled=bool(enable_pal_residual_strong_integration_fix),
    )
    repaired, _fg = apply_finalization_guard_surfacing(
        md, repaired, final_nodes=final_nodes, dataset=dataset, enabled=bool(enable_finalization_guard)
    )
    surfaced_can = canonicalize_answer(repaired.get("surfaced_final_answer_raw"), dataset=dataset)
    gold_can = canonicalize_answer(gold_answer, dataset=dataset)
    return int(bool(surfaced_can == gold_can and surfaced_can is not None))


def evaluate_with_diagnostics(
    result: Any,
    dataset: str,
    gold_answer: str,
    final_nodes: list[dict[str, Any]],
    enable_output_repair: bool,
    *,
    enable_finalization_guard: bool = False,
    enable_pal_residual_strong_integration_fix: bool = False,
) -> dict[str, Any]:
    md = result.metadata or {}
    hint = resolve_selected_group_hint_from_metadata(md, dataset=dataset) or md.get("selected_group")
    repaired = choose_repair_answer(
        final_nodes=final_nodes,
        selected_group_hint=hint,
        dataset=dataset,
        enable_rescue=bool(enable_output_repair),
    )
    repaired = apply_controller_committed_surfacing_for_evaluation(md, repaired, dataset=dataset)
    repaired, pal_integration_sidecar = apply_pal_residual_strong_integration_fix(
        md,
        repaired,
        dataset=dataset,
        enabled=bool(enable_pal_residual_strong_integration_fix),
    )
    repaired, fg_sidecar = apply_finalization_guard_surfacing(
        md, repaired, final_nodes=final_nodes, dataset=dataset, enabled=bool(enable_finalization_guard)
    )
    surfaced_raw = repaired.get("surfaced_final_answer_raw")
    surfaced_can = canonicalize_answer(surfaced_raw, dataset=dataset)
    gold_can = canonicalize_answer(gold_answer, dataset=dataset)
    exact_match = int(bool(surfaced_can == gold_can and surfaced_can is not None))
    gold_in_tree = int(gold_in_tree_from_nodes(final_nodes, gold_answer, dataset=dataset) == 1)
    parse_failure = int(not exact_match and surfaced_can is None)
    if exact_match:
        failure_tag = "correct"
    elif parse_failure:
        failure_tag = "parse/extraction failure"
    elif not gold_in_tree:
        failure_tag = "correct answer absent from explored tree"
    elif gold_in_tree:
        failure_tag = "correct answer present but not selected"
    else:
        failure_tag = "unknown"
    out = {
        "exact_match": exact_match,
        "gold_answer_canonical": gold_can,
        "surfaced_final_answer_raw": surfaced_raw,
        "surfaced_final_answer_canonical": surfaced_can,
        "chosen_final_node_answer_raw": repaired.get("chosen_final_node_answer_raw"),
        "chosen_final_node_answer_canonical": repaired.get("chosen_final_node_answer_canonical"),
        "gold_in_tree": gold_in_tree,
        "parse_extraction_failure": parse_failure,
        "failure_tag": failure_tag,
        "final_answer_source": repaired.get("final_answer_source"),
        "repair_answer_raw": repaired.get("repair_answer_raw"),
        "controller_final_answer_raw": repaired.get("controller_final_answer_raw"),
        "pal_integration": dict(pal_integration_sidecar),
    }
    out.update(fg_sidecar)
    return out


def bootstrap_paired_ci(diffs: list[float], n_boot: int = 1000, seed: int = 7) -> tuple[float, float]:
    if not diffs:
        return (0.0, 0.0)
    rng = random.Random(seed)
    n = len(diffs)
    boots = []
    for _ in range(n_boot):
        sample = [diffs[rng.randrange(n)] for _ in range(n)]
        boots.append(sum(sample) / len(sample))
    boots.sort()
    lo = boots[int(0.025 * (len(boots) - 1))]
    hi = boots[int(0.975 * (len(boots) - 1))]
    return (float(lo), float(hi))


def main() -> None:
    args = parse_args()
    providers = normalize_providers(args)
    datasets = parse_csv_list(args.datasets)
    budgets = parse_csv_ints(args.budgets)
    seeds = parse_csv_ints(args.seeds)
    methods = parse_csv_list(args.methods)
    allowed_case_filter = load_allowed_case_filter(args.allowed_example_ids_file)
    for m in methods:
        if m not in METHODS:
            raise ValueError(f"Unknown method: {m}")
    if args.validate_methods_only:
        validate_methods_only(args, providers, budgets, methods)
    if args.validate_exact_cases_only:
        validate_exact_cases_only(args, providers, datasets, budgets, methods)

    out_dir = REPO_ROOT / args.output_root / f"cohere_real_model_cost_normalized_validation_{args.timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    exact_case_rows_by_dataset = {d: load_exact_case_rows(args.exact_cases_jsonl, dataset=d) for d in datasets} if args.exact_cases_jsonl else {}
    exact_case_meta_by_dataset: dict[str, dict[str, dict[str, Any]]] = {}
    if exact_case_rows_by_dataset:
        for _d, _rows in exact_case_rows_by_dataset.items():
            if not isinstance(_rows, list):
                continue
            exact_case_meta_by_dataset[_d] = {
                str(r.get("example_id")): r for r in _rows if isinstance(r, dict) and str(r.get("example_id") or "").strip()
            }

    maybe_compute_disjointness_preflight(args=args, out_dir=out_dir)

    model_by_provider = {
        "cohere": args.cohere_model,
        "openai": args.openai_model,
    }
    provider_status: dict[str, dict[str, str]] = {}
    if args.summarize_only:
        provider_status = {p: {"ready": "1", "reason": "summarize_only"} for p in providers}
    else:
        for provider in providers:
            if provider == "cohere":
                ok, reason = ensure_cohere_readiness(model=model_by_provider["cohere"], timestamp=args.timestamp)
            else:
                ok, reason = ensure_openai_readiness(timestamp=args.timestamp)
            provider_status[provider] = {"ready": "1" if ok else "0", "reason": reason}

    if (not args.summarize_only) and all(s["ready"] != "1" for s in provider_status.values()):
        print("No configured provider is ready; exiting without API execution.")
        raise SystemExit(1)
    raw_dir = out_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    per_example_path = out_dir / "per_example_records.jsonl"
    progress_path = out_dir / "progress_heartbeat.jsonl"

    existing = load_existing_records(per_example_path) if (args.resume or args.summarize_only) else []
    seen = {to_case_key(r) for r in existing}
    records = list(existing)

    api_keys = {
        "cohere": os.getenv("COHERE_API_KEY", "") or os.getenv("CO_API_KEY", ""),
        "openai": os.getenv("OPENAI_API_KEY", ""),
    }
    ov_verifier_env = {
        "DR_V2_OV_RERANK_VERIFIER_BACKEND": os.getenv("DR_V2_OV_RERANK_VERIFIER_BACKEND", ""),
        "DR_V2_OV_RERANK_COHERE_MODEL": os.getenv("DR_V2_OV_RERANK_COHERE_MODEL", ""),
        "COHERE_API_KEY_present": "yes" if bool(api_keys.get("cohere")) else "no",
    }
    prm_step_verifier_env = {
        "DR_V2_PRM_STEP_VERIFIER_BACKEND": os.getenv("DR_V2_PRM_STEP_VERIFIER_BACKEND", ""),
        "DR_V2_PRM_STEP_VERIFIER_COHERE_MODEL": os.getenv("DR_V2_PRM_STEP_VERIFIER_COHERE_MODEL", ""),
        "COHERE_API_KEY_present": "yes" if bool(api_keys.get("cohere")) else "no",
    }
    dataset_load_failures: dict[tuple[str, str, int], str] = {}
    runtime_missing: set[tuple[str, str, int, int, str]] = set()
    branch_traces: list[dict[str, Any]] = []

    if int(getattr(args, "max_total_api_calls", 0) or 0) > 0:
        configure_logical_api_call_budget(int(args.max_total_api_calls))
        atexit.register(lambda: configure_logical_api_call_budget(None))
    else:
        configure_logical_api_call_budget(None)

    if not args.summarize_only:
        for provider in providers:
            if provider_status[provider]["ready"] != "1":
                continue
            for dataset in datasets:
                for seed in seeds:
                    target_n = args.target_scored_per_slice
                    max_attempt = args.max_examples if args.max_examples > 0 else target_n
                    pool_n = max(max_attempt, target_n)
                    if allowed_case_filter:
                        filtered_counts = [len(v) for (d, s, _b, _m), v in allowed_case_filter.items() if d == dataset and s == seed]
                        if filtered_counts:
                            # GSM8K test split is ~1319 rows; small multipliers can drop tail IDs from the shuffled pool.
                            pool_n = max(pool_n, max(filtered_counts) * 400)
                        # Pilot example_ids are sample-local indices (`..._{idx}` in sample_hf_examples); an ID like
                        # `openai_gsm8k_800` requires subset_size > 800 regardless of allowlist row count.
                        max_suffix = 0
                        for (d, s, _b, _m), ids in allowed_case_filter.items():
                            if d != dataset or s != seed:
                                continue
                            for eid in ids:
                                tail = str(eid).rsplit("_", 1)[-1]
                                if tail.isdigit():
                                    max_suffix = max(max_suffix, int(tail))
                        if max_suffix > 0:
                            pool_n = max(pool_n, max_suffix + 1)
                    try:
                        exact_rows = exact_case_rows_by_dataset.get(dataset) if exact_case_rows_by_dataset else None
                        examples = resolve_examples_for_dataset(dataset, subset_size=pool_n, seed=seed, exact_case_rows=exact_rows)
                        if exact_rows is not None:
                            mismatches = validate_exact_case_examples(exact_rows, examples, dataset=dataset)
                            if mismatches:
                                raise RuntimeError(f"exact-case validation failed before API execution: {mismatches[:3]}")
                    except Exception as exc:  # noqa: BLE001
                        dataset_load_failures[(provider, dataset, seed)] = f"{type(exc).__name__}: {str(exc)[:500]}"
                        continue
                    for budget in budgets:
                        rng = random.Random(1000003 * seed + 97 * budget + len(dataset))

                        def factory() -> Any:
                            return ObservedGenerator(
                                APIBranchGenerator(
                                    provider=provider,
                                    api_key=api_keys[provider],
                                    model=model_by_provider[provider],
                                    temperature=args.temperature,
                                    max_tokens=args.max_output_tokens,
                                    timeout_seconds=args.timeout_seconds,
                                    expand_prompt_variant="default",
                                )
                            )

                        def factory_numeric_leaf() -> Any:
                            return ObservedGenerator(
                                APIBranchGenerator(
                                    provider=provider,
                                    api_key=api_keys[provider],
                                    model=model_by_provider[provider],
                                    temperature=args.temperature,
                                    max_tokens=args.max_output_tokens,
                                    timeout_seconds=args.timeout_seconds,
                                    expand_prompt_variant="numeric_leaf",
                                )
                            )

                        specs = build_frontier_strategies(
                            factory,
                            budget,
                            [1],
                            rng,
                            use_openai_api=(provider == "openai"),
                            include_broad_diversity_aggregation_methods=True,
                            include_external_l1_baseline=True,
                            include_external_s1_baseline=True,
                            include_external_tale_baseline=True,
                            generator_factory_numeric_leaf=factory_numeric_leaf,
                        )

                        for method in methods:
                            method_allowed_cases = allowed_case_filter.get((dataset, seed, budget, method))
                            method_allowed_ids = set(method_allowed_cases or {})
                            if allowed_case_filter and not method_allowed_ids:
                                continue
                            runtime = METHODS[method]["runtime"]
                            enable_repair = bool(METHODS[method]["enable_output_repair"])
                            enable_finalguard = bool(METHODS[method].get("enable_finalization_guard", False))
                            if runtime not in specs:
                                runtime_missing.add((provider, dataset, seed, budget, method))
                                continue
                            attempted = 0
                            scored = 0
                            planned_case_count = len(method_allowed_ids) if method_allowed_cases is not None else len(examples)
                            if args.dry_run_call_plan:
                                append_progress(
                                    progress_path,
                                    {
                                        "event": "dry_run_plan",
                                        "provider": provider,
                                        "dataset": dataset,
                                        "seed": seed,
                                        "budget": budget,
                                        "method": method,
                                        "planned_cases": planned_case_count,
                                    },
                                )
                                continue
                            for ex in examples:
                                if method_allowed_cases is not None and str(ex.example_id) not in method_allowed_ids:
                                    continue
                                if method_allowed_cases is not None:
                                    allowed_meta = method_allowed_cases.get(str(ex.example_id), {})
                                    expected_gold = allowed_meta.get("gold_answer_canonical") or allowed_meta.get("gold_answer")
                                    expected_question = str(allowed_meta.get("question") or allowed_meta.get("problem_text") or "").strip()
                                    if expected_gold is not None:
                                        expected_can = canonicalize_answer(str(expected_gold), dataset=dataset)
                                        actual_can = canonicalize_answer(str(ex.answer), dataset=dataset)
                                        if expected_can is not None and actual_can != expected_can:
                                            raise RuntimeError(
                                                "allowed-example-id gold mismatch for "
                                                f"{ex.example_id}: expected {expected_can!r} from allowlist, "
                                                f"loaded {actual_can!r}; refusing API run because example_id is not stable for this dataset loader"
                                            )
                                    if expected_question and str(ex.question).strip() != expected_question:
                                        raise RuntimeError(
                                            "allowed-example-id question mismatch for "
                                            f"{ex.example_id}; refusing API run because example_id is not stable for this dataset loader"
                                        )
                                if attempted >= max_attempt or scored >= target_n:
                                    break
                                ck = CaseKey(dataset=dataset, seed=seed, budget=budget, method=f"{provider}:{method}", example_id=str(ex.example_id))
                                if ck in seen:
                                    continue
                                attempted += 1
                                append_progress(
                                    progress_path,
                                    {
                                        "event": "example_start",
                                        "timestamp": datetime.now(timezone.utc).isoformat(),
                                        "provider": provider,
                                        "dataset": dataset,
                                        "seed": seed,
                                        "budget": budget,
                                        "method": method,
                                        "example_id": str(ex.example_id),
                                        "attempted_so_far": attempted,
                                        "scored_so_far": scored,
                                        "target_scored": target_n,
                                    },
                                )
                                t0 = time.perf_counter()
                                controller = specs[runtime]
                                if args.save_branch_traces:
                                    setattr(controller, "emit_full_traces", True)
                                # If running exact-case JSONL mode, attach per-example metadata so downstream
                                # diagnostics (e.g. domain-aware anchor prioritization) can use explicit labels.
                                if args.exact_cases_jsonl and dataset in exact_case_meta_by_dataset:
                                    try:
                                        row_meta = exact_case_meta_by_dataset.get(dataset, {}).get(str(ex.example_id), {})
                                        setattr(controller, "current_example_id", str(ex.example_id))
                                        setattr(controller, "current_exact_case_metadata", dict(row_meta) if isinstance(row_meta, dict) else {})
                                    except Exception:
                                        # Best-effort only: never block the run on metadata plumbing.
                                        setattr(controller, "current_example_id", str(ex.example_id))
                                        setattr(controller, "current_exact_case_metadata", {})
                                if hasattr(controller, "generator") and hasattr(controller.generator, "base") and hasattr(controller.generator.base, "reset_usage_counters"):
                                    controller.generator.base.reset_usage_counters()
                                status = "scored"
                                err_text = ""
                                retry_attempts = 0
                                in_tok = 0
                                out_tok = 0
                                total_tok = 0
                                logical_api_calls_local = 0
                                exact_match = 0
                                eval_diag: dict[str, Any] = {}
                                result_metadata: dict[str, Any] = {}
                                final_nodes: list[dict[str, Any]] = []
                                merged_nodes: list[dict[str, Any]] = []
                                try:
                                    result = controller.run(ex.question, ex.answer)
                                    latency = time.perf_counter() - t0
                                    obs = controller.generator
                                    result_metadata = dict(getattr(result, "metadata", {}) or {})
                                    if hasattr(obs, "registry"):
                                        for _, b in sorted(obs.registry.items(), key=lambda kv: kv[0]):
                                            reasoning_text = "\n".join(str(x) for x in getattr(b, "steps", [])) if getattr(b, "steps", None) else ""
                                            pred = b.predicted_answer
                                            pred_norm = normalize_answer_text(str(pred) if pred is not None else None).get("normalized_answer")
                                            evs = getattr(b, "trace_events", None) or []
                                            expand_sources = [
                                                str(ev.get("expand_answer_extraction_source") or "")
                                                for ev in evs
                                                if isinstance(ev, dict) and ev.get("action") == "expand"
                                            ]
                                            verify_sources = [
                                                str(ev.get("verify_answer_extraction_source") or "")
                                                for ev in evs
                                                if isinstance(ev, dict) and ev.get("action") == "verify"
                                            ]
                                            nl_status: Any = None
                                            nl_value: Any = None
                                            nl_src: Any = None
                                            for ev in reversed(evs):
                                                if isinstance(ev, dict) and ev.get("action") == "expand":
                                                    nl_status = ev.get("numeric_leaf_status")
                                                    nl_value = ev.get("numeric_leaf_value")
                                                    nl_src = ev.get("numeric_leaf_source")
                                                    break
                                            final_nodes.append(
                                                {
                                                    "branch_id": b.branch_id,
                                                    "reasoning_text": reasoning_text,
                                                    "predicted_answer": pred,
                                                    "predicted_answer_normalized": pred_norm,
                                                    "expand_answer_extraction_sources": expand_sources,
                                                    "verify_answer_extraction_sources": verify_sources,
                                                    "numeric_leaf_status": nl_status,
                                                    "numeric_leaf_value": nl_value,
                                                    "numeric_leaf_source": nl_src,
                                                }
                                            )
                                    merged_nodes = augment_final_nodes_with_metadata_frontier(final_nodes, result_metadata)
                                    pal_residual = bool(
                                        getattr(args, "pal_residual_strong_integration_fix", False)
                                        and ("tiebreak_pal" in str(method))
                                    )
                                    eval_diag = evaluate_with_diagnostics(
                                        result,
                                        dataset,
                                        str(ex.answer),
                                        merged_nodes,
                                        enable_repair,
                                        enable_finalization_guard=enable_finalguard,
                                        enable_pal_residual_strong_integration_fix=pal_residual,
                                    )
                                    exact_match = int(eval_diag["exact_match"])
                                    for _gk, _gv in eval_diag.items():
                                        if str(_gk).startswith("finalguard_"):
                                            result_metadata[_gk] = _gv
                                    if isinstance(eval_diag.get("pal_integration"), dict):
                                        result_metadata["pal_integration_evaluator"] = dict(eval_diag["pal_integration"])
                                    if args.save_branch_traces:
                                        branch_traces.append(
                                            build_branch_trace(
                                                result=result,
                                                example_id=str(ex.example_id),
                                                dataset=dataset,
                                                provider=provider,
                                                model=model_by_provider[provider],
                                                budget=budget,
                                                seed=seed,
                                                method=method,
                                                question=str(ex.question),
                                                gold_answer=str(ex.answer),
                                            )
                                        )
                                    scored += 1
                                    if hasattr(controller, "generator") and hasattr(controller.generator, "base") and hasattr(controller.generator.base, "snapshot_usage_counters"):
                                        usage = controller.generator.base.snapshot_usage_counters()
                                        in_tok = int(usage.get("input_tokens", 0))
                                        out_tok = int(usage.get("output_tokens", 0))
                                        total_tok = int(usage.get("total_tokens", in_tok + out_tok))
                                        retry_attempts = int(usage.get("retry_attempts", 0))
                                        logical_api_calls_local = int(usage.get("api_calls", 0))
                                except Exception as exc:  # noqa: BLE001
                                    latency = time.perf_counter() - t0
                                    status = "failed"
                                    err_text = f"{type(exc).__name__}: {str(exc)[:800]}"

                                cost = (in_tok / 1000.0) * args.input_cost_per_1k + (out_tok / 1000.0) * args.output_cost_per_1k
                                row = {
                                    "provider": provider,
                                    "model": model_by_provider[provider],
                                    "dataset": dataset,
                                    "seed": seed,
                                    "budget": budget,
                                    "method": method,
                                    "example_id": str(ex.example_id),
                                    "status": status,
                                    "error": err_text,
                                    "exact_match": int(exact_match),
                                    "question": str(ex.question),
                                    "gold_answer": str(ex.answer),
                                    "gold_answer_canonical": eval_diag.get("gold_answer_canonical"),
                                    "final_answer_raw": eval_diag.get("surfaced_final_answer_raw"),
                                    "final_answer_canonical": eval_diag.get("surfaced_final_answer_canonical"),
                                    "selected_answer_raw": eval_diag.get("chosen_final_node_answer_raw"),
                                    "selected_answer_canonical": eval_diag.get("chosen_final_node_answer_canonical"),
                                    "gold_in_tree": int(eval_diag.get("gold_in_tree", 0)),
                                    "parse_extraction_failure": int(eval_diag.get("parse_extraction_failure", 0)),
                                    "failure_tag": (eval_diag.get("failure_tag") if status == "scored" else "API/runtime failure"),
                                    "final_answer_source": eval_diag.get("final_answer_source"),
                                    "repair_answer_raw": eval_diag.get("repair_answer_raw"),
                                    "controller_final_answer_raw": eval_diag.get("controller_final_answer_raw"),
                                    "result_metadata": result_metadata if status == "scored" else {},
                                    "final_nodes": merged_nodes if status == "scored" else [],
                                    "attempted": 1,
                                    "scored": int(status == "scored"),
                                    "failed": int(status == "failed"),
                                    "skipped": 0,
                                    "retry_attempts": int(retry_attempts),
                                    "cohere_logical_api_calls": int(logical_api_calls_local),
                                    "input_tokens": int(in_tok),
                                    "output_tokens": int(out_tok),
                                    "total_tokens": int(total_tok),
                                    "latency_seconds": float(round(latency, 6)),
                                    "estimated_cost_usd": float(cost),
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                    "ov_verifier_backend_env": ov_verifier_env["DR_V2_OV_RERANK_VERIFIER_BACKEND"] or "unset",
                                    "ov_verifier_model_env": ov_verifier_env["DR_V2_OV_RERANK_COHERE_MODEL"] or "unset",
                                    "prm_step_verifier_backend_env": prm_step_verifier_env["DR_V2_PRM_STEP_VERIFIER_BACKEND"] or "unset",
                                    "prm_step_verifier_model_env": prm_step_verifier_env["DR_V2_PRM_STEP_VERIFIER_COHERE_MODEL"] or "unset",
                                    "cohere_api_key_present": ov_verifier_env["COHERE_API_KEY_present"],
                                }
                                try:
                                    row.update(
                                        build_promotion_review_fields_for_record(
                                            row,
                                            run_id=str(args.timestamp),
                                            artifact_label=out_dir.name,
                                        )
                                    )
                                except Exception as exc:  # noqa: BLE001
                                    row["promotion_review_record"] = {}
                                    row["promotion_review_validation"] = {
                                        "enough_for_promotion_review": "no",
                                        "runtime_failure_reviewable": "no",
                                        "missing_required_fields": ["promotion_review_build_exception"],
                                        "missing_critical_fields": ["promotion_review_build_exception"],
                                        "notes": [f"promotion_review_build_exception:{type(exc).__name__}"],
                                    }
                                append_jsonl(per_example_path, row)
                                records.append(row)
                                seen.add(ck)
                                append_progress(
                                    progress_path,
                                    {
                                        "event": "example_end",
                                        "timestamp": datetime.now(timezone.utc).isoformat(),
                                        "provider": provider,
                                        "dataset": dataset,
                                        "seed": seed,
                                        "budget": budget,
                                        "method": method,
                                        "example_id": str(ex.example_id),
                                        "status": status,
                                        "latency_seconds": float(round(latency, 6)),
                                        "attempted_so_far": attempted,
                                        "scored_so_far": scored,
                                        "target_scored": target_n,
                                    },
                                )
                                print(
                                    f"[progress] provider={provider} dataset={dataset} seed={seed} "
                                    f"budget={budget} method={method} attempted={attempted} "
                                    f"scored={scored} status={status} example_id={ex.example_id}",
                                    flush=True,
                                )
                                if status == "failed":
                                    append_jsonl(raw_dir / "failures.jsonl", row)
    if args.dry_run_call_plan:
        print(f"dry-run-call-plan written: {progress_path}")
        raise SystemExit(0)

    slices: dict[tuple[str, str, int, int, str], list[dict[str, Any]]] = {}
    for r in records:
        key = (str(r.get("provider", "cohere")), str(r["dataset"]), int(r["seed"]), int(r["budget"]), str(r["method"]))
        slices.setdefault(key, []).append(r)

    expected_slices = [(p, d, s, b, m) for p in providers for d in datasets for s in seeds for b in budgets for m in methods]
    slice_rows: list[dict[str, Any]] = []
    incomplete_rows: list[dict[str, Any]] = []
    for (provider, dataset, seed, budget, method) in expected_slices:
        rows = slices.get((provider, dataset, seed, budget, method), [])
        attempted = sum(int(x.get("attempted", 0)) for x in rows)
        scored = sum(int(x.get("scored", 0)) for x in rows)
        failed = sum(int(x.get("failed", 0)) for x in rows)
        skipped = sum(int(x.get("skipped", 0)) for x in rows)
        retries = sum(int(x.get("retry_attempts", 0)) for x in rows)
        acc_float = mean([float(x.get("exact_match", 0)) for x in rows if int(x.get("scored", 0)) == 1])
        in_tok = sum(int(x.get("input_tokens", 0)) for x in rows)
        out_tok = sum(int(x.get("output_tokens", 0)) for x in rows)
        tot_tok = sum(int(x.get("total_tokens", 0)) for x in rows)
        lat = sum(float(x.get("latency_seconds", 0.0)) for x in rows)
        cost = sum(float(x.get("estimated_cost_usd", 0.0)) for x in rows)
        target_n = args.target_scored_per_slice
        incomplete = scored < target_n
        if provider_status[provider]["ready"] != "1":
            reason = "provider_unavailable"
        elif (provider, dataset, seed) in dataset_load_failures:
            reason = "dataset_loading_failure"
        elif (provider, dataset, seed, budget, method) in runtime_missing:
            reason = "runtime_missing"
        elif not rows:
            reason = "missing_slice_zero_records"
        elif failed > 0 and scored == 0:
            reason = "api_failures"
        elif incomplete:
            reason = "insufficient_scored_examples"
        else:
            reason = "target_reached"
        row = {
            "provider": provider,
            "model": model_by_provider[provider],
            "dataset": dataset,
            "seed": seed,
            "budget": budget,
            "method": method,
            "attempted_examples": attempted,
            "successfully_scored_examples": scored,
            "skipped_examples": skipped,
            "failed_examples": failed,
            "retry_counts": retries,
            "accuracy": ("NA" if scored == 0 else acc_float),
            "exact_match": ("NA" if scored == 0 else acc_float),
            "total_input_tokens": in_tok,
            "total_output_tokens": out_tok,
            "total_tokens": tot_tok,
            "mean_input_tokens_per_scored_example": (in_tok / scored) if scored else 0.0,
            "mean_output_tokens_per_scored_example": (out_tok / scored) if scored else 0.0,
            "mean_total_tokens_per_scored_example": (tot_tok / scored) if scored else 0.0,
            "total_latency_seconds": lat,
            "mean_latency_seconds_per_scored_example": (lat / scored) if scored else 0.0,
            "estimated_dollar_cost": cost,
            "accuracy_per_1k_tokens": (acc_float / (tot_tok / 1000.0)) if tot_tok > 0 and scored > 0 else 0.0,
            "accuracy_per_estimated_dollar": (acc_float / cost) if cost > 0 and scored > 0 else 0.0,
            "incomplete_slice": int(incomplete),
            "incomplete_reason": reason,
        }
        slice_rows.append(row)
        if incomplete or reason != "target_reached":
            incomplete_rows.append(row)

    write_csv(out_dir / "slice_summary.csv", slice_rows)

    by_method: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for r in slice_rows:
        by_method.setdefault((str(r["provider"]), str(r["method"])), []).append(r)
    method_rows = []
    cost_rows = []
    for (provider, m), rows in sorted(by_method.items()):
        scored = sum(int(x["successfully_scored_examples"]) for x in rows)
        tot_tok = sum(float(x["total_tokens"]) for x in rows)
        total_cost = sum(float(x["estimated_dollar_cost"]) for x in rows)
        avg_acc = mean([float(x["accuracy"]) for x in rows if str(x["accuracy"]) != "NA"])
        method_rows.append(
            {
                "provider": provider,
                "method": m,
                "n_slices": len(rows),
                "total_scored_examples": scored,
                "mean_accuracy_across_slices": avg_acc,
                "mean_total_tokens_per_scored_example": (tot_tok / scored) if scored else 0.0,
                "mean_latency_seconds_per_scored_example": mean([float(x["mean_latency_seconds_per_scored_example"]) for x in rows]),
                "estimated_total_cost_usd": total_cost,
            }
        )
        cost_rows.append(
            {
                "provider": provider,
                "method": m,
                "mean_accuracy": avg_acc,
                "accuracy_per_1k_tokens": (avg_acc / (tot_tok / 1000.0)) if tot_tok > 0 else 0.0,
                "accuracy_per_estimated_dollar": (avg_acc / total_cost) if total_cost > 0 else 0.0,
                "total_tokens": tot_tok,
                "estimated_total_cost_usd": total_cost,
            }
        )

    write_csv(out_dir / "method_summary.csv", method_rows)
    write_csv(out_dir / "cost_normalized_summary.csv", cost_rows)
    write_csv(out_dir / "incomplete_slices.csv", incomplete_rows, fieldnames=list(slice_rows[0].keys()) if slice_rows else None)

    per_group: dict[tuple[str, str, int, int, str], dict[str, int]] = {}
    for r in records:
        if int(r.get("scored", 0)) != 1:
            continue
        k = (str(r["provider"]), str(r["dataset"]), int(r["seed"]), int(r["budget"]), str(r["example_id"]))
        per_group.setdefault(k, {})[str(r["method"])] = int(r["exact_match"])

    def paired_rows(provider: str, a: str, b: str, label: str) -> list[dict[str, Any]]:
        diffs = []
        wins_a = 0
        wins_b = 0
        ties = 0
        for (p, _, _, _, _), m in per_group.items():
            if p != provider:
                continue
            if a in m and b in m:
                d = m[a] - m[b]
                diffs.append(float(d))
                if d > 0:
                    wins_a += 1
                elif d < 0:
                    wins_b += 1
                else:
                    ties += 1
        mdiff = mean(diffs)
        lo, hi = bootstrap_paired_ci(diffs)
        status = "evaluable" if diffs else "not_evaluable_zero_matched_examples"
        return [
            {
                "provider": provider,
                "comparison": label,
                "method_a": a,
                "method_b": b,
                "matched_examples": len(diffs),
                "mean_accuracy_delta_a_minus_b": ("NA" if not diffs else mdiff),
                "bootstrap95_low": ("NA" if not diffs else lo),
                "bootstrap95_high": ("NA" if not diffs else hi),
                "wins_a": wins_a,
                "wins_b": wins_b,
                "ties": ties,
                "comparison_status": status,
            }
        ]

    pairwise = []
    for provider in providers:
        pairwise.extend(paired_rows(provider, "strict_f3", "external_l1_max", "strict_f3_vs_external_l1_max"))
        pairwise.extend(paired_rows(provider, "strict_f3", "strict_gate1_cap_k6", "strict_f3_vs_strict_gate1_cap_k6"))
        fa_methods = [m for m in ["strict_f3", "strict_gate1_cap_k6", "strict_f2"] if (provider, m) in by_method]
        if fa_methods:
            best_fa = max(
                fa_methods,
                key=lambda m: mean([float(x["accuracy"]) for x in by_method[(provider, m)] if str(x["accuracy"]) != "NA"]),
            )
            pairwise.extend(paired_rows(provider, best_fa, "external_l1_max", "best_frontier_vs_external_l1_max"))
            if (provider, "self_consistency_3") in by_method:
                pairwise.extend(paired_rows(provider, best_fa, "self_consistency_3", "frontier_family_best_vs_self_consistency_3"))
    write_csv(out_dir / "pairwise_comparisons.csv", pairwise)
    if args.emit_trace_audit:
        scored_records = [r for r in records if int(r.get("scored", 0)) == 1]
        by_key_method: dict[tuple[str, str, int, int, str], dict[str, dict[str, Any]]] = {}
        for r in scored_records:
            k = (str(r.get("provider", "cohere")), str(r.get("dataset", "")), int(r.get("seed", 0)), int(r.get("budget", 0)), str(r.get("example_id", "")))
            by_key_method.setdefault(k, {})[str(r.get("method", ""))] = r
        trace_rows: list[dict[str, Any]] = []
        for (_, dataset, seed, budget, example_id), method_map in sorted(by_key_method.items()):
            dr = method_map.get("direct_reserve_semantic_frontier_v2")
            l1 = method_map.get("external_l1_max")
            if not dr:
                continue
            md = dict(dr.get("result_metadata", {}) or {})
            final_nodes = list(dr.get("final_nodes", []) or [])
            candidate_answers_raw = [n.get("predicted_answer") for n in final_nodes if n.get("predicted_answer") is not None]
            candidate_answers_norm = [n.get("predicted_answer_normalized") for n in final_nodes if n.get("predicted_answer_normalized")]
            selected_group = str(md.get("selected_group") or md.get("final_answer_group") or "")
            gold_group = str(dr.get("gold_answer_canonical") or "")
            present_gold = int(bool(gold_group and gold_group in set(candidate_answers_norm)))
            selected_gold = int(bool(gold_group and selected_group and gold_group == selected_group))
            raw_final = dr.get("final_answer_raw")
            norm_final = dr.get("final_answer_canonical")
            trace_rows.append(
                {
                    "dataset": dataset, "example_id": example_id, "seed": seed, "budget": budget, "method": "direct_reserve_semantic_frontier_v2",
                    "gold_answer": dr.get("gold_answer"), "raw_final_answer": raw_final, "normalized_final_answer": norm_final,
                    "exact_match": int(dr.get("exact_match", 0)), "action_count": int(md.get("actions_used", dr.get("budget", 0)) or 0),
                    "output_tokens": int(dr.get("output_tokens", 0)), "total_tokens": int(dr.get("total_tokens", 0)),
                    "latency_seconds": dr.get("latency_seconds", ""), "estimated_cost": dr.get("estimated_cost_usd", ""),
                    "dr_v2_candidate_answers_raw": json.dumps(candidate_answers_raw, ensure_ascii=False),
                    "dr_v2_candidate_answers_normalized": json.dumps(candidate_answers_norm, ensure_ascii=False),
                    "dr_v2_candidate_answer_groups": json.dumps(sorted(set(candidate_answers_norm)), ensure_ascii=False),
                    "dr_v2_selected_answer_group": selected_group,
                    "dr_v2_gold_answer_group_present": present_gold,
                    "dr_v2_gold_answer_present_in_candidates": present_gold,
                    "dr_v2_selected_gold_answer_group": selected_gold,
                    "dr_v2_present_not_selected": int(bool(present_gold and not selected_gold and not int(dr.get("exact_match", 0)))),
                    "dr_v2_absent_from_frontier": int(bool((not present_gold) and (not int(dr.get("exact_match", 0))))),
                    "dr_v2_extraction_suspected": int(bool(raw_final and not norm_final and not int(dr.get("exact_match", 0)))),
                    "dr_v2_commit_source": md.get("override_reason", ""),
                    "dr_v2_frontier_actions_used": md.get("frontier_actions_used", ""),
                    "dr_v2_direct_actions_used": md.get("direct_actions_used", ""),
                    "dr_v2_stop_reason": md.get("route_reason", md.get("override_reason", "")),
                    "dr_v2_trace_available": int(bool(final_nodes or md.get("action_trace"))),
                    "external_l1_raw_answer": "" if not l1 else l1.get("final_answer_raw", ""),
                    "external_l1_normalized_answer": "" if not l1 else l1.get("final_answer_canonical", ""),
                    "external_l1_exact_match": "" if not l1 else int(l1.get("exact_match", 0)),
                    "external_l1_tokens": "" if not l1 else int(l1.get("total_tokens", 0)),
                    "external_l1_latency_seconds": "" if not l1 else l1.get("latency_seconds", ""),
                    "external_l1_estimated_cost": "" if not l1 else l1.get("estimated_cost_usd", ""),
                }
            )
        write_csv(out_dir / "trace_audit_per_case.csv", trace_rows)

    pmap = {(r["provider"], r["comparison"]): r for r in pairwise}
    cohere_row = pmap.get(("cohere", "strict_f3_vs_external_l1_max"), {})
    cohere_evaluable = cohere_row.get("comparison_status") == "evaluable"
    cohere_delta = cohere_row.get("mean_accuracy_delta_a_minus_b", "NA")
    mixed = False
    for r in pairwise:
        if "external" not in str(r.get("comparison", "")) or r.get("comparison_status") != "evaluable":
            continue
        mixed = mixed or float(r.get("mean_accuracy_delta_a_minus_b", 0.0)) <= 0

    provider_answers = []
    for provider in providers:
        row = pmap.get((provider, "strict_f3_vs_external_l1_max"), {})
        if row.get("comparison_status") != "evaluable":
            verdict = "not_evaluable_zero_matched_examples"
            evidence = f"matched={int(row.get('matched_examples', 0))}"
        else:
            delta = float(row["mean_accuracy_delta_a_minus_b"])
            verdict = "yes" if delta > 0 else "no_or_mixed"
            evidence = f"delta={delta:+.4f}, matched={int(row['matched_examples'])}"
        provider_answers.append({"question": f"Under provider={provider}, does strict_f3 beat external_l1_max?", "answer": verdict, "evidence": evidence})

    claim_rows = [
        {
            "question": "Did Cohere produce an evaluable strict_f3 vs external_l1_max comparison?",
            "answer": "yes" if cohere_evaluable else "no",
            "evidence": f"matched={int(cohere_row.get('matched_examples', 0))}",
        },
        {
            "question": "If not, why not?",
            "answer": ("na_evaluable" if cohere_evaluable else str(cohere_row.get("comparison_status", "not_evaluable_zero_matched_examples"))),
            "evidence": f"delta={cohere_delta}",
        },
        {
            "question": "Was OpenAI fallback used?",
            "answer": "yes" if ("openai" in providers and provider_status.get("openai", {}).get("ready") == "1") else "no",
            "evidence": provider_status.get("openai", {}).get("reason", "not_requested"),
        },
        {
            "question": "Is the evidence still appendix-only, or strong enough for main-paper use?",
            "answer": "yes" if (not mixed and len(incomplete_rows) == 0) else "no_appendix_only",
            "evidence": f"incomplete_slices={len(incomplete_rows)}, mixed={mixed}",
        },
    ]
    claim_rows.extend(provider_answers)
    write_csv(out_dir / "claim_safety_table.csv", claim_rows)
    trace_stats = {"n_traces": 0, "n_branches": 0, "n_answer_groups": 0}
    if args.save_branch_traces and branch_traces:
        trace_stats = write_trace_package(out_dir, branch_traces)

    manifest = {
        "artifact_family": "cohere_real_model_cost_normalized_validation",
        "timestamp": args.timestamp,
        "providers": providers,
        "models": model_by_provider,
        "datasets": datasets,
        "budgets": budgets,
        "seeds": seeds,
        "methods": methods,
        "target_scored_per_slice": args.target_scored_per_slice,
        "max_examples": args.max_examples,
        "provider_status": provider_status,
        "pricing": {"input_cost_per_1k": args.input_cost_per_1k, "output_cost_per_1k": args.output_cost_per_1k},
        "save_branch_traces": bool(args.save_branch_traces),
        "ov_verifier_environment": {
            "DR_V2_OV_RERANK_VERIFIER_BACKEND": ov_verifier_env["DR_V2_OV_RERANK_VERIFIER_BACKEND"] or "unset",
            "DR_V2_OV_RERANK_COHERE_MODEL": ov_verifier_env["DR_V2_OV_RERANK_COHERE_MODEL"] or "unset",
            "COHERE_API_KEY_present": ov_verifier_env["COHERE_API_KEY_present"],
        },
        "prm_step_verifier_environment": {
            "DR_V2_PRM_STEP_VERIFIER_BACKEND": prm_step_verifier_env["DR_V2_PRM_STEP_VERIFIER_BACKEND"] or "unset",
            "DR_V2_PRM_STEP_VERIFIER_COHERE_MODEL": prm_step_verifier_env["DR_V2_PRM_STEP_VERIFIER_COHERE_MODEL"] or "unset",
            "COHERE_API_KEY_present": prm_step_verifier_env["COHERE_API_KEY_present"],
        },
        "branch_trace_stats": trace_stats,
        "max_total_api_calls": int(getattr(args, "max_total_api_calls", 0) or 0),
        "outputs": [
            "manifest.json",
            "slice_summary.csv",
            "method_summary.csv",
            "cost_normalized_summary.csv",
            "pairwise_comparisons.csv",
            "incomplete_slices.csv",
            "claim_safety_table.csv",
            "per_example_records.jsonl",
            "progress_heartbeat.jsonl",
            "raw/failures.jsonl",
            "candidate_branch_table.csv",
            "answer_group_table.csv",
            "per_case_trace_index.csv",
            "traces/",
        ],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    doc_path = REPO_ROOT / "docs" / f"COHERE_REAL_MODEL_COST_NORMALIZED_VALIDATION_{args.timestamp}.md"
    total_expected = len(expected_slices)
    completed = sum(1 for r in slice_rows if int(r["incomplete_slice"]) == 0)
    zero_records = sum(1 for r in slice_rows if int(r["attempted_examples"]) == 0)
    by_provider_counts = {p: {"completed": 0, "expected": 0} for p in providers}
    by_method_counts = {m: {"completed": 0, "expected": 0} for m in methods}
    by_dataset_counts = {d: {"completed": 0, "expected": 0} for d in datasets}
    for r in slice_rows:
        by_provider_counts[str(r["provider"])]["expected"] += 1
        by_method_counts[str(r["method"])]["expected"] += 1
        by_dataset_counts[str(r["dataset"])]["expected"] += 1
        if int(r["incomplete_slice"]) == 0:
            by_provider_counts[str(r["provider"])]["completed"] += 1
            by_method_counts[str(r["method"])]["completed"] += 1
            by_dataset_counts[str(r["dataset"])]["completed"] += 1
    acc_table = "\n".join(
        [
            f"- provider={r['provider']} method={r['method']}: mean_accuracy={float(r['mean_accuracy_across_slices']):.4f}, total_scored={int(r['total_scored_examples'])}"
            for r in method_rows
        ]
    )
    tok_table = "\n".join(
        [
            f"- provider={r['provider']} method={r['method']}: total_tokens={int(float(r['total_tokens']))}, estimated_total_cost_usd={float(r['estimated_total_cost_usd']):.6f}"
            for r in cost_rows
        ]
    )
    pair_table = "\n".join(
        [
            (
                f"- provider={r['provider']} {r['comparison']}: status={r['comparison_status']}, "
                f"delta={r['mean_accuracy_delta_a_minus_b']}, matched={int(r['matched_examples'])}"
            )
            for r in pairwise
        ]
    )
    claim_lines = "\n".join([f"- {r['question']} **{r['answer']}** ({r['evidence']})" for r in claim_rows])
    doc_lines = [
        "# COHERE_REAL_MODEL_COST_NORMALIZED_VALIDATION",
        "",
        f"- Timestamp: `{args.timestamp}`",
        f"- Exact command: `python scripts/run_cohere_real_model_cost_normalized_validation.py --timestamp {args.timestamp} --resume --max-examples {args.max_examples} --target-scored-per-slice {args.target_scored_per_slice}`",
        f"- Providers: `{providers}`",
        f"- Provider models: `{model_by_provider}`",
        f"- Datasets: `{datasets}`",
        f"- Budgets: `{budgets}`",
        f"- Seeds: `{seeds}`",
        f"- Methods: `{methods}`",
        f"- Sample-size target per slice: `{args.target_scored_per_slice}` (max-examples cap `{args.max_examples}`)",
        "",
        "## Completion status",
        f"- Total expected slices: `{total_expected}`",
        f"- Completed slices: `{completed}`",
        f"- Incomplete slices: `{total_expected - completed}`",
        f"- Zero-record slices: `{zero_records}`",
        "- Per-provider completion counts:",
        *[f"  - {p}: {c['completed']}/{c['expected']}" for p, c in sorted(by_provider_counts.items())],
        "- Per-method completion counts:",
        *[f"  - {m}: {c['completed']}/{c['expected']}" for m, c in sorted(by_method_counts.items())],
        "- Per-dataset completion counts:",
        *[f"  - {d}: {c['completed']}/{c['expected']}" for d, c in sorted(by_dataset_counts.items())],
        "",
        "## Staged status",
        f"- Stage 1 (GSM8K): {by_dataset_counts.get('openai/gsm8k', {}).get('completed', 0)}/{by_dataset_counts.get('openai/gsm8k', {}).get('expected', 0)} slices completed.",
        f"- Stage 2 (MATH-500): {by_dataset_counts.get('HuggingFaceH4/MATH-500', {}).get('completed', 0)}/{by_dataset_counts.get('HuggingFaceH4/MATH-500', {}).get('expected', 0)} slices completed.",
        f"- Stage 3 (AIME 2024): {by_dataset_counts.get('HuggingFaceH4/aime_2024', {}).get('completed', 0)}/{by_dataset_counts.get('HuggingFaceH4/aime_2024', {}).get('expected', 0)} slices completed.",
        f"- Provider status: {provider_status}",
        "",
        "## Main accuracy table",
        acc_table or "- (no rows)",
        "",
        "## Token/latency/cost table",
        tok_table or "- (no rows)",
        "",
        "## Cost-normalized performance table",
        "- See `cost_normalized_summary.csv` in artifact directory.",
        "",
        "## Paired comparison table",
        pair_table or "- (no pairwise rows)",
        "",
        "## Clear answers",
        claim_lines,
        "",
        "## Manuscript-safe wording",
        "- Treat Cohere evidence as bounded external-validity evidence under this matched setup.",
        "- If slices are incomplete or mixed, keep appendix-only / competitive-non-dominant framing.",
        "",
        "## Forbidden overclaim wording",
        "- Do not claim universal dominance across providers/datasets/budgets from this single Cohere run.",
        "",
        f"## Artifact directory\n- `outputs/cohere_real_model_cost_normalized_validation_{args.timestamp}/`",
    ]
    doc_path.write_text("\n".join(doc_lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
