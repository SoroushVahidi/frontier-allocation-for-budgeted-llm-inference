from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Protocol


@dataclass(frozen=True)
class CandidateAnswer:
    candidate_id: str
    problem: str
    trace: str
    final_answer: str
    normalized_answer: str | None = None
    source_id: str | None = None
    source_prior: float = 0.5
    cost_norm: float = 0.0


@dataclass(frozen=True)
class VerifierResult:
    prob_correct: float
    trace_final_consistent: bool
    answer_equivalent_if_normalized: bool | None
    major_error: bool
    short_reason: str


@dataclass(frozen=True)
class AnswerGroupScore:
    normalized_answer: str
    group_score: float
    original_group_size: int
    capped_group_size: int
    representative_candidate_id: str


@dataclass(frozen=True)
class SelectorDecision:
    selected_answer: str
    selected_candidate_id: str
    selected_group_score: float
    group_scores: list[AnswerGroupScore]
    verifier_results: dict[str, VerifierResult]
    candidate_scores: dict[str, float]


class OutcomeVerifier(Protocol):
    def verify(self, candidate: CandidateAnswer) -> VerifierResult: ...


class DeterministicMockOutcomeVerifier:
    """Simple deterministic verifier for tests and offline integration plumbing."""

    def verify(self, candidate: CandidateAnswer) -> VerifierResult:
        answer_text = (candidate.normalized_answer or candidate.final_answer or "").strip().lower()
        trace_text = (candidate.trace or "").strip().lower()
        if not answer_text:
            return VerifierResult(0.1, False, None, True, "empty_answer")
        is_bad = any(tok in answer_text for tok in ("wrong", "error", "invalid"))
        consistent = answer_text in trace_text if trace_text else True
        prob = 0.2 if is_bad else 0.8
        if not consistent:
            prob = min(prob, 0.5)
        return VerifierResult(
            prob_correct=prob,
            trace_final_consistent=consistent,
            answer_equivalent_if_normalized=None,
            major_error=is_bad,
            short_reason="deterministic_mock",
        )


def clip_prob(p: float, eps: float = 1e-4) -> float:
    return min(max(float(p), eps), 1.0 - eps)


def logit(p: float) -> float:
    pp = clip_prob(p)
    return math.log(pp / (1.0 - pp))


def score_candidate(verifier_result: VerifierResult, source_prior: float = 0.5, cost_norm: float = 0.0) -> float:
    p_i = verifier_result.prob_correct
    if verifier_result.major_error:
        p_i = min(p_i, 0.25)
    if not verifier_result.trace_final_consistent:
        p_i = min(p_i, 0.50)
    return logit(clip_prob(p_i)) + 0.5 * logit(clip_prob(source_prior)) - 0.1 * float(cost_norm)


def group_candidates_by_normalized_answer(candidates: list[CandidateAnswer]) -> dict[str, list[CandidateAnswer]]:
    grouped: dict[str, list[CandidateAnswer]] = {}
    for c in candidates:
        key = (c.normalized_answer or c.final_answer or "").strip()
        grouped.setdefault(key, []).append(c)
    return grouped


def score_answer_group(candidates: list[CandidateAnswer], candidate_scores: dict[str, float], tau: float = 0.25, support_bonus: float = 0.35) -> float:
    by_source: dict[str, CandidateAnswer] = {}
    for c in candidates:
        source_key = c.source_id if c.source_id else f"{c.candidate_id}"
        current = by_source.get(source_key)
        if current is None or candidate_scores[c.candidate_id] > candidate_scores[current.candidate_id]:
            by_source[source_key] = c
    capped_scores = [candidate_scores[c.candidate_id] for c in by_source.values()]
    max_scaled = max(s / tau for s in capped_scores)
    lse = max_scaled + math.log(sum(math.exp((s / tau) - max_scaled) for s in capped_scores))
    return tau * lse + support_bonus * math.log(1.0 + len(candidates))


def select_answer_group_with_outcome_verifier(candidates: list[CandidateAnswer], verifier: OutcomeVerifier, tau: float = 0.25, support_bonus: float = 0.35) -> SelectorDecision:
    verifier_results = {c.candidate_id: verifier.verify(c) for c in candidates}
    candidate_scores = {
        c.candidate_id: score_candidate(verifier_results[c.candidate_id], source_prior=c.source_prior, cost_norm=c.cost_norm)
        for c in candidates
    }
    groups = group_candidates_by_normalized_answer(candidates)
    ranked: list[tuple[AnswerGroupScore, list[CandidateAnswer]]] = []
    for answer, group_cands in groups.items():
        gs = score_answer_group(group_cands, candidate_scores, tau=tau, support_bonus=support_bonus)
        rep = max(group_cands, key=lambda c: candidate_scores[c.candidate_id])
        capped_sources = {c.source_id if c.source_id else c.candidate_id for c in group_cands}
        ranked.append((AnswerGroupScore(answer, gs, len(group_cands), len(capped_sources), rep.candidate_id), group_cands))
    ranked.sort(key=lambda x: x[0].group_score, reverse=True)

    if len(ranked) > 1 and abs(ranked[0][0].group_score - ranked[1][0].group_score) <= 0.05:
        def tie_key(item: tuple[AnswerGroupScore, list[CandidateAnswer]]) -> tuple[float, int, float, int]:
            _, gcs = item
            max_p = max(verifier_results[c.candidate_id].prob_correct for c in gcs)
            mean_cost = sum(c.cost_norm for c in gcs) / len(gcs)
            consistency = sum(1 for c in gcs if verifier_results[c.candidate_id].trace_final_consistent)
            return (max_p, len(gcs), -mean_cost, consistency)
        top_two = sorted(ranked[:2], key=tie_key, reverse=True)
        ranked = [top_two[0], top_two[1], *ranked[2:]]

    selected_group, _ = ranked[0]
    return SelectorDecision(
        selected_answer=selected_group.normalized_answer,
        selected_candidate_id=selected_group.representative_candidate_id,
        selected_group_score=selected_group.group_score,
        group_scores=[g for g, _ in ranked],
        verifier_results=verifier_results,
        candidate_scores=candidate_scores,
    )


def build_outcome_verifier_prompt(candidate: CandidateAnswer) -> tuple[str, str]:
    system_prompt = (
        "You are a strict verifier for math and word-problem solutions. "
        "Judge whether the candidate's FINAL ANSWER is correct for the given problem, using the candidate reasoning trace as evidence. "
        "Important rules: - Ignore writing style, verbosity, and fluency. - Do not reward long explanations. "
        "- Penalize any arithmetic, algebra, unit, or logical error. - If the trace contradicts the final answer, score very low. "
        "- Treat formatting differences as acceptable only if the normalized answer is equivalent. - Output JSON only."
    )
    norm = candidate.normalized_answer if candidate.normalized_answer is not None else "null"
    user_prompt = (
        f"Problem: {candidate.problem}\n\n"
        f"Candidate reasoning trace: {candidate.trace}\n\n"
        f"Candidate final answer: {candidate.final_answer}\n\n"
        f"Normalized final answer if available: {norm}\n\n"
        "Return JSON with fields: {\n"
        '  "prob_correct": float,\n'
        '  "trace_final_consistent": bool,\n'
        '  "answer_equivalent_if_normalized": bool | null,\n'
        '  "major_error": bool,\n'
        '  "short_reason": string\n'
        "}\n"
        "Scoring rubric: 1.00 = clearly correct reasoning and correct final answer 0.75 = likely correct; no substantive math error found "
        "0.50 = uncertain / insufficient evidence 0.25 = likely wrong 0.00 = clearly wrong Do not reward style or length. Verify strictly."
    )
    return system_prompt, user_prompt
