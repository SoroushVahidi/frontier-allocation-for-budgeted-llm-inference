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

from experiments.controllers import DirectReserveFrontierGateV2Controller

METHOD_STRATEGY_SEEDED_SEMANTIC_DIVERSITY_FRONTIER_V1 = "strategy_seeded_semantic_diversity_frontier_v1"

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
