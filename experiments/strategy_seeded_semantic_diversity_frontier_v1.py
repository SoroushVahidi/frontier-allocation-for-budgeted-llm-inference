"""strategy_seeded_semantic_diversity_frontier_v1 — DR-v2-style gate + explicit math root strategies.

Diagnostic / pilot method: forces distinct **prompt-conditioned** decomposition families at the
direct-reserve/root stage before the semantic aggregation frontier activates.

Proxy-only semantic tagging (keyword buckets on reasoning text): not a neural classifier.
Gold must never influence controller decisions — only downstream evaluation compares to gold."""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

from experiments.controllers import (
    DirectReserveFrontierGateV2Controller,
    GlobalDiversityAggregationController,
    MethodResult,
)

METHOD_STRATEGY_SEEDED_SEMANTIC_DIVERSITY_FRONTIER_V1 = "strategy_seeded_semantic_diversity_frontier_v1"
METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1 = "direct_reserve_diverse_root_frontier_v1"

# Canonical root strategy identifiers (orthogonal to MECHANICAL answer-group churn).
ROOT_STRATEGY_FAMILY_SPECS: list[tuple[str, str]] = [
    (
        "direct_arithmetic",
        "Solve directly using arithmetic: keep quantities explicit and check each intermediate computation. "
        "Then output only the final numeric answer in \\boxed{}.",
    ),
    (
        "algebra_equation",
        "Set up algebraic equations representing the quantities in the word problem before you compute final numbers; "
        "solve symbolically-first where helpful. Output only the final numeric answer in \\boxed{}.",
    ),
    (
        "quantity_table_units",
        "Build a compact table listing each quantity with units row-by-row, then reconcile subtotals. "
        "Output only the final numeric answer in \\boxed{}.",
    ),
    (
        "constraint_decomposition",
        "Decompose into explicit numeric constraints/equations and satisfy them stepwise in a dependency order "
        "(no skipping intermediate unknowns when needed). Output only the final numeric answer in \\boxed{}.",
    ),
    (
        "backward_check_or_inverse_reasoning",
        "Use backward chaining or sanity checks: test candidate totals against partial constraints before locking an answer "
        "(still derive the answer honestly from the narrative). Output only the final numeric answer in \\boxed{}.",
    ),
]

_SEM_BUCKET_PATTERNS: list[tuple[str, list[re.Pattern[str]]]] = [
    (
        "algebra_like",
        [re.compile(p, re.I) for p in (r"\blet\b", r"\bx\b", r"equation", r"=", r"solve\s+for")],
    ),
    (
        "table_units_like",
        [re.compile(p, re.I) for p in (r"\|", r"\btable\b", r"\bunits?\b", r"row", r"column")],
    ),
    (
        "constraint_like",
        [re.compile(p, re.I) for p in (r"\bconstraints?\b", r"\bsubgoal", r"satisf")],
    ),
    (
        "backward_like",
        [re.compile(p, re.I) for p in (r"\bbackward", r"\breverse", r"\bcheck\b", r"\bverify\b", r"\binverse\b")],
    ),
    (
        "arithmetic_like",
        [re.compile(p, re.I) for p in (r"\+", r"\*", r"\d+\s*[×x]\s*\d+", r"subtract", r"multiply", r"divide")],
    ),
]


def build_strategy_prompt_styles_semantic_frontier_v1() -> list[str]:
    return [suffix for (_, suffix) in ROOT_STRATEGY_FAMILY_SPECS]


_GUARDED_K3_FINAL_NUDGE = (
    " If you already have the final numeric result, respond with action='final' and put it in the answer field."
)


def build_strategy_prompt_styles_semantic_frontier_v1_guarded_k3() -> list[str]:
    """Root prompts for guarded K=3 live variant: same families as v1, plus a compact final-answer nudge."""
    return [suffix + _GUARDED_K3_FINAL_NUDGE for (_, suffix) in ROOT_STRATEGY_FAMILY_SPECS]


def infer_semantic_family_proxy(*, reasoning_text: str, root_strategy_family: str) -> str:
    """Cheap deterministic buckets; overlaps possible — prioritize first match after root fallback."""
    t = str(reasoning_text or "")
    for bucket, patterns in _SEM_BUCKET_PATTERNS:
        if any(p.search(t) for p in patterns):
            return bucket
    return f"root_proxy::{root_strategy_family}"


def shannon_entropy_from_counts(counts: Counter[str]) -> float:
    tot = sum(int(v) for v in counts.values() if int(v) > 0)
    if tot <= 0:
        return 0.0
    probs = [int(v) / tot for v in counts.values() if int(v) > 0]
    if len(probs) <= 1:
        return 0.0
    return float(-sum(p * math.log(max(1e-12, p)) for p in probs) / math.log(len(probs)))


class StrategySeededSemanticDiversityFrontierV1Controller(DirectReserveFrontierGateV2Controller):
    """Adds per-seed caps + trace tags; inherits DR-v2 incumbent guard semantics."""

    def __init__(
        self,
        generator: Any,
        scorer: Any,
        max_actions_per_problem: int,
        *,
        strategy_seed_max_actions: int = 1,
        method_name: str = METHOD_STRATEGY_SEEDED_SEMANTIC_DIVERSITY_FRONTIER_V1,
        **kwargs: Any,
    ) -> None:
        if "strict_controller_factory" not in kwargs:
            kwargs["strict_controller_factory"] = lambda remaining_budget: GlobalDiversityAggregationController(
                generator,
                scorer,
                int(remaining_budget),
            )
        super().__init__(generator, scorer, max_actions_per_problem, method_name=method_name, **kwargs)
        self.strategy_seed_max_actions = max(1, int(strategy_seed_max_actions))

    def _run_direct_attempt(self, question: str, gold_answer: str, idx: int, max_actions: int) -> tuple[str | None, int, list[dict]]:
        capped = min(int(max_actions), int(self.strategy_seed_max_actions))
        fam_id = ROOT_STRATEGY_FAMILY_SPECS[idx % len(ROOT_STRATEGY_FAMILY_SPECS)][0]
        ans, used, trace = super()._run_direct_attempt(question, gold_answer, idx, capped)
        for row in trace:
            row["root_strategy_family"] = fam_id
            row["strategy_family"] = fam_id
        return ans, used, trace


class DirectReserveDiverseRootFrontierV1Controller(DirectReserveFrontierGateV2Controller):
    """Direct reserve with diverse root strategies frontier (v1).

    Variant that ensures diverse root decomposition approaches are explored
    at the direct-reserve stage before frontier aggregation.
    """

    def __init__(
        self,
        generator: Any,
        scorer: Any,
        max_actions_per_problem: int,
        *,
        strategy_seed_max_actions: int = 1,
        method_name: str = METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1,
        **kwargs: Any,
    ) -> None:
        if "strict_controller_factory" not in kwargs:
            kwargs["strict_controller_factory"] = lambda remaining_budget: GlobalDiversityAggregationController(
                generator,
                scorer,
                int(remaining_budget),
            )
        super().__init__(generator, scorer, max_actions_per_problem, method_name=method_name, **kwargs)
        self.strategy_seed_max_actions = max(1, int(strategy_seed_max_actions))

    def _run_direct_attempt(self, question: str, gold_answer: str, idx: int, max_actions: int) -> tuple[str | None, int, list[dict]]:
        capped = min(int(max_actions), int(self.strategy_seed_max_actions))
        fam_id = ROOT_STRATEGY_FAMILY_SPECS[idx % len(ROOT_STRATEGY_FAMILY_SPECS)][0]
        ans, used, trace = super()._run_direct_attempt(question, gold_answer, idx, capped)
        for row in trace:
            row["root_strategy_family"] = fam_id
            row["strategy_family"] = fam_id
        return ans, used, trace


METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED = "direct_reserve_diverse_root_frontier_v1_guarded"
METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K3 = "direct_reserve_diverse_root_frontier_v1_guarded_k3"
METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K2_FRONTIER2 = (
    "direct_reserve_diverse_root_frontier_v1_guarded_k2_frontier2"
)
METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4 = (
    "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4"
)
METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4_FRONTIER_TIEBREAK = (
    "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak"
)
# PAL-labeled alias: same guarded K1/frontier4 + frontier tiebreak controller/settings as the non-_pal ID,
# but distinct method_name string for paired bundles / provenance (PR #357).
METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4_FRONTIER_TIEBREAK_PAL = (
    "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal"
)
METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4_FRONTIER_TIEBREAK_PAL_TRACK_B_COMMITMENT_V1 = (
    "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal_track_b_commitment_v1"
)
METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4_FRONTIER_TIEBREAK_PAL_STRUCTURAL_COMMIT_V1 = (
    "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal_structural_commit_v1"
)
METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4_FRONTIER_TIEBREAK_PAL_STRUCTURAL_COMMIT_V1_TARGETED_RETRY_V1 = (
    "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal_structural_commit_v1_targeted_retry_v1"
)
METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4_FRONTIER_TIEBREAK_PAL_STRUCTURAL_COMMIT_V1_ADAPTIVE_ROUTER_V3_FINAL_TARGET_VERIFIER_V1 = (
    "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal_structural_commit_v1_adaptive_router_v3_final_target_verifier_v1"
)
METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4_FRONTIER_TIEBREAK_PAL_STRUCTURAL_COMMIT_V1_PRODUCTION_EQUIV_V1 = (
    "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal_structural_commit_v1_production_equiv_v1"
)
METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4_FRONTIER_TIEBREAK_FINALGUARD = (
    "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_finalguard"
)
METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4_FRONTIER_TIEBREAK_NUMERIC_LEAF = (
    "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_numeric_leaf"
)
METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4_FRONTIER_TIEBREAK_UNIT_TRACK = (
    "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_unit_track"
)
METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4_FRONTIER_TIEBREAK_DECOMP_EQ = (
    "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_decomp_eq"
)
METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4_FRONTIER_TIEBREAK_OPCHECK = (
    "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_opcheck"
)
# K1 tiebreak + optional L1-style hybrid seed (extra expand before frontier when gate-unstable).
METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4_FRONTIER_TIEBREAK_DIRECT_HYBRID = (
    "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_direct_hybrid"
)
METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4_FRONTIER_TIEBREAK_DIVERSE_ANCHOR = (
    "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_diverse_anchor"
)

_NUMERIC_LEAF_DR_APPEND = (
    " Emit numeric_leaf_status and numeric_leaf_value in branch JSON on each expand (see expand prompt); "
    "label provisional totals explicitly before advancing."
)


def build_strategy_prompt_styles_semantic_frontier_v1_guarded_k1_frontier4_numeric_leaf() -> list[str]:
    """K1 frontier4 + numeric-leaf contract nudge (full JSON schema is in APIBranchGenerator expand prompt)."""
    return [s + _NUMERIC_LEAF_DR_APPEND for s in build_strategy_prompt_styles_semantic_frontier_v1_guarded_k1_frontier4()]


def build_strategy_prompt_styles_semantic_frontier_v1_guarded_k2_frontier2() -> list[str]:
    """K=2 + reserved frontier budget: reuse K3 nudged family prompts (only first two roots run)."""
    return build_strategy_prompt_styles_semantic_frontier_v1_guarded_k3()


def build_strategy_prompt_styles_semantic_frontier_v1_guarded_k1_frontier4() -> list[str]:
    """K=1 + four-action frontier reserve: first K3 nudged family prompt only."""
    return build_strategy_prompt_styles_semantic_frontier_v1_guarded_k3()[:1]


class DirectReserveDiverseRootFrontierV1GuardedController(DirectReserveDiverseRootFrontierV1Controller):
    """Guarded variant of diverse root frontier v1.

    Extends v1 with a guard: falls back to the baseline (v2_final style) answer
    when the baseline has strong frontier support (i.e., multiple answer groups in candidates).

    Decision logic is gold-agnostic: only checks frontier evidence strength, never gold.
    This reduces regressions while preserving recoveries from v1.
    """

    def __init__(
        self,
        generator: Any,
        scorer: Any,
        max_actions_per_problem: int,
        *,
        strategy_seed_max_actions: int = 1,
        enable_diverse_anchor_regression_guard: bool = False,
        method_name: str = METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            generator,
            scorer,
            max_actions_per_problem,
            strategy_seed_max_actions=strategy_seed_max_actions,
            method_name=method_name,
            **kwargs,
        )
        self.enable_diverse_anchor_regression_guard = bool(enable_diverse_anchor_regression_guard)

    def run(self, question: str, gold_answer: str) -> MethodResult:
        """Run v1, then apply fallback guard based on frontier support."""
        result = super().run(question, gold_answer)
        metadata = dict(result.metadata or {})

        support_source = metadata.get("frontier_answer_group_counts")
        if not isinstance(support_source, dict) or not support_source:
            support_source = metadata.get("answer_group_support_counts", {})

        if not isinstance(support_source, dict):
            support_source = {}

        support_count = len([k for k, v in support_source.items() if int(v or 0) > 0])
        has_strong_frontier_support = support_count > 1

        direct_reserve_answer = metadata.get("direct_reserve_answer")

        guard_applied = has_strong_frontier_support and direct_reserve_answer is not None

        metadata["guarded_frontier_support_count"] = support_count
        metadata["guarded_has_strong_support"] = has_strong_frontier_support
        metadata["guarded_direct_reserve_answer"] = direct_reserve_answer
        metadata["guarded_override_blocked"] = guard_applied
        metadata["guarded_override_reason"] = (
            "strong_frontier_support_with_direct_answer" if guard_applied else "no_override"
        )

        if not guard_applied:
            metadata["guarded_action"] = "accept_v1_override"
            return MethodResult(
                method=self.method_name,
                prediction=result.prediction,
                is_correct=result.is_correct,
                actions_used=result.actions_used,
                expansions=result.expansions,
                verifications=result.verifications,
                avg_surviving_branches=result.avg_surviving_branches,
                budget_exhausted=result.budget_exhausted,
                metadata=metadata,
            )

        metadata["guarded_action"] = "fallback_to_direct_reserve"
        return MethodResult(
            method=self.method_name,
            prediction=direct_reserve_answer,
            is_correct=self._answers_match(direct_reserve_answer, gold_answer),
            actions_used=result.actions_used,
            expansions=result.expansions,
            verifications=result.verifications,
            avg_surviving_branches=result.avg_surviving_branches,
            budget_exhausted=result.budget_exhausted,
            metadata=metadata,
        )
