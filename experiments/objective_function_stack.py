"""Canonical objective/function stack for fixed-budget branch allocation.

Top-level objective (unique): maximize expected final correctness/utility under a
fixed compute budget.

This module keeps surrogate quantities explicit:
- process_quality(b)
- target_completion(b)
- continuation_value(b)

and defines a bounded metalevel decision template over:
- expand(i)
- expand(j)
- commit_now
"""

from __future__ import annotations

from dataclasses import dataclass


CANONICAL_OBJECTIVE_ID = "maximize_expected_final_utility_under_fixed_budget"
CANONICAL_OBJECTIVE_TEXT = (
    "Maximize expected final task correctness/utility under a fixed compute budget "
    "by allocating each next compute unit to the branch with highest expected "
    "marginal value, unless commit-now has higher bounded local utility."
)


@dataclass(frozen=True)
class BranchSurrogates:
    branch_id: str
    continuation_value: float
    process_quality: float
    target_completion: float
    semantic_incompleteness: float = 0.0


@dataclass(frozen=True)
class MetalevelDecision:
    action: str  # expand | commit_now
    branch_id: str | None
    rationale: str


def clip01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def compute_process_quality(*, completion_score: float, answer_evidence_score: float, semantic_incompleteness: float = 0.0) -> float:
    """Local reasoning quality signal; not commit-readiness on its own."""
    return clip01(0.50 * float(completion_score) + 0.35 * float(answer_evidence_score) + 0.15 * (1.0 - float(semantic_incompleteness)))


def compute_target_completion(*, completion_score: float, answer_evidence_score: float, semantic_incompleteness: float) -> float:
    """Target-variable completion/readiness signal with trap penalty."""
    raw = 0.60 * float(completion_score) + 0.25 * float(answer_evidence_score) - 0.35 * float(semantic_incompleteness)
    return clip01(raw)


def compute_commit_quality(*, process_quality: float, target_completion: float) -> float:
    """Incumbent quality proxy for commit-now comparison."""
    return clip01(0.40 * float(process_quality) + 0.60 * float(target_completion))


def metalevel_expand_commit_decision(
    branches: list[BranchSurrogates],
    *,
    near_tie_gap: float = 0.03,
    max_value_drop_for_local_override: float = 0.02,
    commit_margin: float = 0.02,
    low_completion_trigger: float = 0.35,
) -> MetalevelDecision:
    """Bounded local decision rule.

    Default: expand branch with highest continuation_value.
    Local correction: in near ties, prefer higher target_completion if value-drop is bounded.
    Commit option: if best branch has strong commit-quality and continuation advantage is low.
    """
    if not branches:
        return MetalevelDecision(action="commit_now", branch_id=None, rationale="no_active_branches")

    ranked = sorted(branches, key=lambda b: float(b.continuation_value), reverse=True)
    top = ranked[0]
    second = ranked[1] if len(ranked) > 1 else None
    top_gap = float(top.continuation_value - second.continuation_value) if second is not None else 1.0
    near_tie = bool(top_gap <= float(near_tie_gap))

    chosen = top
    rationale = "default_continuation_value"

    if near_tie:
        eligible = [b for b in ranked if (float(top.continuation_value) - float(b.continuation_value)) <= float(max_value_drop_for_local_override)]
        better_completion = max(eligible, key=lambda b: (float(b.target_completion), float(b.process_quality)))
        if (better_completion.branch_id != top.branch_id) and (float(top.target_completion) <= float(low_completion_trigger)):
            chosen = better_completion
            rationale = "near_tie_local_completion_correction"

    chosen_commit = compute_commit_quality(process_quality=float(chosen.process_quality), target_completion=float(chosen.target_completion))
    if (chosen_commit - float(chosen.continuation_value)) >= float(commit_margin):
        return MetalevelDecision(action="commit_now", branch_id=chosen.branch_id, rationale=f"commit_quality_dominates:{rationale}")

    return MetalevelDecision(action="expand", branch_id=chosen.branch_id, rationale=rationale)
