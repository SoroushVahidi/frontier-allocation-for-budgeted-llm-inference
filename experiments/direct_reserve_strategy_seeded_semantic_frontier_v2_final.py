"""direct_reserve_strategy_seeded_semantic_frontier_v2_final — fair pilot controller (DR-v2 backbone).

Budget-aware root strategy seeding with prompt text passed to the generator, optional early
short-circuit when the first seed is already a stable consensus, and slightly stronger inner
duplicate / repeat-family penalties (strict_f3 clone) as a deterministic allocation proxy.

Gold must never appear in prompts or non-evaluation controller decisions."""

from __future__ import annotations

import hashlib
import math
from collections import Counter
from typing import Any

from experiments.controllers import DirectReserveFrontierGateV2Controller, MethodResult, _normalize_answer
from experiments.strategy_seeded_semantic_diversity_frontier_v1 import ROOT_STRATEGY_FAMILY_SPECS

METHOD_DIRECT_RESERVE_STRATEGY_SEEDED_SEMANTIC_FRONTIER_V2_FINAL = (
    "direct_reserve_strategy_seeded_semantic_frontier_v2_final"
)


def _question_key(question: str) -> bytes:
    return hashlib.sha256(str(question or "").strip().encode("utf-8", errors="replace")).digest()


def select_strategy_spec_indices(*, max_actions: int, question: str) -> list[int]:
    """Choose root strategy spec indices: always direct_arithmetic (0) + deterministic alternates.

    Not gold-based: alternate order is keyed by SHA256(question)."""
    digest = _question_key(question)
    alts = list(range(1, len(ROOT_STRATEGY_FAMILY_SPECS)))
    alts.sort(key=lambda j: (digest[j % len(digest)], j))
    b = int(max_actions)
    if b <= 6:
        k = 1
    elif b == 8:
        k = 2
    elif b >= 10:
        k = 4
    else:
        k = 1
    k = max(0, min(k, len(alts)))
    return [0] + alts[:k]


def prompt_digest(s: str) -> str:
    return hashlib.sha256(str(s).encode("utf-8", errors="replace")).hexdigest()[:20]


class DirectReserveStrategySeededSemanticFrontierV2FinalController(DirectReserveFrontierGateV2Controller):
    """DR-v2 with budget-aware multi-prompt root seeding and stronger inner diversity pressure."""

    def __init__(
        self,
        generator: Any,
        scorer: Any,
        max_actions_per_problem: int,
        *,
        strategy_seed_min_actions: int = 2,
        min_actions_reserved_for_frontier: int = 1,
        strategy_seed_short_circuit_min_top_support: float = 0.88,
        strategy_seed_short_circuit_min_gap: float = 0.52,
        strategy_seed_short_circuit_max_norm_entropy: float = 0.38,
        method_name: str = METHOD_DIRECT_RESERVE_STRATEGY_SEEDED_SEMANTIC_FRONTIER_V2_FINAL,
        **kwargs: Any,
    ) -> None:
        super().__init__(generator, scorer, max_actions_per_problem, method_name=method_name, **kwargs)
        self.strategy_seed_min_actions = max(1, int(strategy_seed_min_actions))
        self.min_actions_reserved_for_frontier = max(0, int(min_actions_reserved_for_frontier))
        self.strategy_seed_short_circuit_min_top_support = float(strategy_seed_short_circuit_min_top_support)
        self.strategy_seed_short_circuit_min_gap = float(strategy_seed_short_circuit_min_gap)
        self.strategy_seed_short_circuit_max_norm_entropy = float(strategy_seed_short_circuit_max_norm_entropy)
        self._current_question: str = ""

    def _strategy_indices(self) -> list[int]:
        return select_strategy_spec_indices(max_actions=self.max_actions, question=self._current_question)

    def _direct_reserve_attempts(self) -> int:
        return max(1, len(self._strategy_indices()))

    def _stop_additional_direct_reserve_after_attempt(
        self,
        *,
        attempt_index: int,
        question: str,
        direct_answers: list[str | None],
        last_attempt_trace_rows: list[dict[str, Any]] | None = None,
    ) -> bool:
        if attempt_index != 0:
            return False
        rows = list(last_attempt_trace_rows or [])
        if len(rows) < 2:
            return False
        norms: list[str] = []
        for r in rows:
            if not isinstance(r, dict):
                continue
            ea = str(r.get("extracted_answer") or "").strip()
            if not ea:
                continue
            n = _normalize_answer(ea) or ""
            if n and n != "__unknown__":
                norms.append(str(n).lower())
        if len(norms) < 2:
            return False
        if len(set(norms)) != 1:
            return False
        counts = Counter((_normalize_answer(a) or "__unknown__") for a in direct_answers if a is not None)
        total = max(1, sum(counts.values()))
        sorted_v = sorted(counts.values(), reverse=True)
        top = sorted_v[0]
        second = sorted_v[1] if len(sorted_v) > 1 else 0
        top_support = top / total
        gap = (top - second) / total
        probs = [c / total for c in counts.values() if c > 0]
        ent = float(-sum(p * math.log(max(p, 1e-12)) for p in probs))
        norm_ent = float(ent / math.log(len(counts))) if len(counts) > 1 else 0.0
        return bool(
            top_support >= self.strategy_seed_short_circuit_min_top_support
            and gap >= self.strategy_seed_short_circuit_min_gap
            and norm_ent <= self.strategy_seed_short_circuit_max_norm_entropy
        )

    def _per_seed_max_actions(self, n_seeds: int, remaining_cap: int) -> int:
        budget = int(self.max_actions)
        reserve = int(self.min_actions_reserved_for_frontier)
        spendable = max(1, budget - reserve)
        n = max(1, n_seeds)
        base = max(1, spendable // n)
        if spendable >= 2 * n:
            base = max(base, min(2, self.strategy_seed_min_actions))
        return max(1, min(int(self.strategy_seed_min_actions), base, remaining_cap))

    def _run_direct_attempt(self, question: str, gold_answer: str, idx: int, max_actions: int) -> tuple[str | None, int, list[dict]]:
        indices = self._strategy_indices()
        if idx >= len(indices):
            spec_idx = 0
        else:
            spec_idx = int(indices[idx])
        fam_id, prompt_suffix = ROOT_STRATEGY_FAMILY_SPECS[spec_idx]
        n = len(indices)
        cap = self._per_seed_max_actions(n, max(1, int(max_actions)))

        branch = self.generator.init_branch(f"direct_reserve_{idx}")
        actions = 0
        trace: list[dict[str, Any]] = []
        prompt_body = f"{question}\n\n{prompt_suffix} Think for maximum {self.direct_token_budget} tokens."
        digest = prompt_digest(prompt_body)
        while actions < cap and not branch.is_done and not branch.is_pruned:
            self.generator.expand(branch, prompt_body, gold_answer)
            actions += 1
            latest = branch.trace_events[-1] if branch.trace_events else {}
            trace.append(
                {
                    "action": "expand",
                    "branch_id": branch.branch_id,
                    "root_strategy_family": fam_id,
                    "prompt_family_id": fam_id,
                    "prompt_digest": digest,
                    "action_index": actions,
                    "strategy_seed_index": idx,
                    "spec_index": spec_idx,
                    "response_from_strategy_prompt": True,
                    "prompt_text": str(latest.get("prompt_text", "")),
                    "response_text": str(latest.get("response_text", "")),
                    "reasoning_text": str(latest.get("reasoning_text", "")),
                    "extracted_answer": str(latest.get("extracted_answer", "") or ""),
                }
            )
        return branch.predicted_answer, actions, trace

    def run(self, question: str, gold_answer: str) -> MethodResult:
        self._current_question = str(question or "")
        base = super().run(question, gold_answer)
        md = dict(base.metadata or {})
        indices = self._strategy_indices()
        planned = [
            {
                "spec_index": int(indices[i]),
                "root_strategy_family": ROOT_STRATEGY_FAMILY_SPECS[int(indices[i])][0],
                "prompt_family_id": ROOT_STRATEGY_FAMILY_SPECS[int(indices[i])][0],
                "prompt_digest": prompt_digest(
                    f"{question}\n\n{ROOT_STRATEGY_FAMILY_SPECS[int(indices[i])][1]} "
                    f"Think for maximum {self.direct_token_budget} tokens."
                ),
            }
            for i in range(len(indices))
        ]
        dra = md.get("direct_reserve_attempts")
        prompt_lengths = [len(str(x.get("prompt_text", ""))) for x in dra if isinstance(x, dict)] if isinstance(dra, list) else []
        distinct_digests = sorted({str(x.get("prompt_digest", "")) for x in dra if isinstance(x, dict) and x.get("prompt_digest")})

        fm = md.get("frontier_candidate_metadata")
        inner: dict[str, Any] = fm if isinstance(fm, dict) else {}

        md["strategy_seeded_v2_final_audit"] = {
            "budget": int(self.max_actions),
            "strategy_spec_indices": [int(i) for i in indices],
            "planned_root_strategies": planned,
            "strategy_seed_min_actions": int(self.strategy_seed_min_actions),
            "min_actions_reserved_for_frontier": int(self.min_actions_reserved_for_frontier),
            "distinct_prompt_digests_in_trace": distinct_digests,
            "mean_prompt_text_len": (sum(prompt_lengths) / max(1, len(prompt_lengths))) if prompt_lengths else 0.0,
            "semantic_allocation_proxy": {
                "inner_cfg_note": (
                    "GlobalDiversityAggregationController uses strict_f3_base_cfg with boosted duplicate_penalty "
                    "and repeat_expand_family_penalty_weight vs stock DR-v2 inner config."
                ),
            },
            "semantic_gate_intervention_count": int(inner.get("gate_intervention_count", 0) or 0),
            "strategy_protection_intervention_count": int(inner.get("early_preservation_forced_steps", 0) or 0)
            + int(inner.get("early_gated_override_applied", 0) or 0),
            "redundant_strategy_expansion_avoided_count": int(inner.get("repeat_penalty_alternative_selected_count", 0) or 0),
            "underrepresented_strategy_expansion_count": int(inner.get("gate_favor_diversity_count", 0) or 0),
            "inner_counter_mapping_note": (
                "Counters are forwarded from frontier (strict_f3 inner) telemetry: gate_intervention_count→semantic_gate_intervention_count; "
                "repeat_penalty_alternative_selected_count→redundant_strategy_expansion_avoided; "
                "early_preservation_forced_steps+early_gated_override_applied→strategy_protection_intervention_count; "
                "gate_favor_diversity_count→underrepresented_strategy_expansion_count."
            ),
        }
        return MethodResult(
            method=base.method,
            prediction=base.prediction,
            is_correct=base.is_correct,
            actions_used=base.actions_used,
            expansions=base.expansions,
            verifications=base.verifications,
            avg_surviving_branches=base.avg_surviving_branches,
            budget_exhausted=base.budget_exhausted,
            metadata=md,
        )
