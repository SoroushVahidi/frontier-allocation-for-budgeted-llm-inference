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
    source_family: str | None = None
    cost_norm: float = 0.0
    source_prior: float = 0.5
    metadata: dict | None = None


@dataclass(frozen=True)
class VerifierResult:
    prob_correct: float
    trace_final_consistent: bool
    answer_equivalent_if_normalized: bool | None
    major_error: bool
    short_reason: str = ""


@dataclass(frozen=True)
class AnswerGroupScore:
    normalized_answer: str
    group_score: float
    original_group_size: int
    capped_group_size: int
    max_verifier_prob: float
    mean_cost: float
    any_trace_final_consistent: bool


@dataclass(frozen=True)
class SelectorDecision:
    selected_group: str
    selected_candidate: CandidateAnswer
    group_scores: list[AnswerGroupScore]
    candidate_scores: dict[str, float]
    verifier_results: dict[str, VerifierResult]


class OutcomeVerifier(Protocol):
    def verify(self, candidate: CandidateAnswer) -> VerifierResult: ...


class DeterministicMockOutcomeVerifier:
    def __init__(self, mapping: dict[str, VerifierResult]) -> None:
        self.mapping = mapping

    def verify(self, candidate: CandidateAnswer) -> VerifierResult:
        return self.mapping[candidate.candidate_id]


def clip_prob(p: float, eps: float = 1e-4) -> float:
    return max(eps, min(1.0 - eps, float(p)))


def logit(p: float) -> float:
    q = clip_prob(p)
    return math.log(q / (1.0 - q))


def score_candidate(verifier_result: VerifierResult, source_prior: float = 0.5, cost_norm: float = 0.0) -> float:
    p = clip_prob(verifier_result.prob_correct)
    if verifier_result.major_error:
        p = min(p, 0.25)
    if not verifier_result.trace_final_consistent:
        p = min(p, 0.50)
    r = clip_prob(source_prior)
    c = float(cost_norm)
    return logit(p) + 0.5 * logit(r) - 0.1 * c


def group_candidates_by_normalized_answer(candidates: list[CandidateAnswer]) -> dict[str, list[CandidateAnswer]]:
    out: dict[str, list[CandidateAnswer]] = {}
    for c in candidates:
        key = str((c.normalized_answer or c.final_answer or "").strip() or "__empty__")
        out.setdefault(key, []).append(c)
    return out


def _logsumexp(vals: list[float]) -> float:
    if not vals:
        return float("-inf")
    m = max(vals)
    return m + math.log(sum(math.exp(v - m) for v in vals))


def score_answer_group(candidates: list[CandidateAnswer], candidate_scores: dict[str, float], tau: float = 0.25, support_bonus: float = 0.35) -> AnswerGroupScore:
    by_source: dict[str, CandidateAnswer] = {}
    for idx, c in enumerate(candidates):
        source = c.source_family if c.source_family else f"__unique__{idx}_{c.candidate_id}"
        prev = by_source.get(source)
        if prev is None or candidate_scores[c.candidate_id] > candidate_scores[prev.candidate_id]:
            by_source[source] = c
    capped = list(by_source.values())
    scaled = [candidate_scores[c.candidate_id] / max(1e-8, tau) for c in capped]
    base = tau * _logsumexp(scaled)
    total = base + support_bonus * math.log(1.0 + len(candidates))
    max_prob = max(float((c.metadata or {}).get("verifier_prob", 0.0)) for c in candidates)
    mean_cost = sum(float(c.cost_norm) for c in candidates) / max(1, len(candidates))
    any_consistent = any(bool((c.metadata or {}).get("trace_final_consistent", False)) for c in candidates)
    return AnswerGroupScore(
        normalized_answer=str(candidates[0].normalized_answer or candidates[0].final_answer),
        group_score=total,
        original_group_size=len(candidates),
        capped_group_size=len(capped),
        max_verifier_prob=max_prob,
        mean_cost=mean_cost,
        any_trace_final_consistent=any_consistent,
    )


def select_answer_group_with_outcome_verifier(candidates: list[CandidateAnswer], verifier: OutcomeVerifier, tau: float = 0.25, support_bonus: float = 0.35) -> SelectorDecision:
    vr: dict[str, VerifierResult] = {}
    scores: dict[str, float] = {}
    scored_candidates: list[CandidateAnswer] = []
    for c in candidates:
        v = verifier.verify(c)
        vr[c.candidate_id] = v
        scores[c.candidate_id] = score_candidate(v, source_prior=c.source_prior, cost_norm=c.cost_norm)
        md = dict(c.metadata or {})
        md["verifier_prob"] = v.prob_correct
        md["trace_final_consistent"] = v.trace_final_consistent
        scored_candidates.append(CandidateAnswer(**{**c.__dict__, "metadata": md}))
    groups = group_candidates_by_normalized_answer(scored_candidates)
    group_scores = [score_answer_group(g, scores, tau=tau, support_bonus=support_bonus) for g in groups.values()]
    group_scores.sort(key=lambda g: g.group_score, reverse=True)
    best = group_scores[0]
    if len(group_scores) > 1 and abs(group_scores[0].group_score - group_scores[1].group_score) <= 0.05:
        top = group_scores[:2]
        top.sort(key=lambda g: (g.max_verifier_prob, g.original_group_size, -g.mean_cost, g.any_trace_final_consistent), reverse=True)
        best = top[0]
    in_group = [c for c in scored_candidates if str(c.normalized_answer or c.final_answer) == best.normalized_answer]
    chosen = max(in_group, key=lambda c: scores[c.candidate_id])
    return SelectorDecision(best.normalized_answer, chosen, group_scores, scores, vr)


def build_outcome_verifier_prompt(candidate: CandidateAnswer) -> tuple[str, str]:
    system = "You are a strict verifier for math and word-problem solutions. Judge whether the candidate's FINAL ANSWER is correct for the given problem, using the candidate reasoning trace as evidence. Important rules: - Ignore writing style, verbosity, and fluency. - Do not reward long explanations. - Penalize any arithmetic, algebra, unit, or logical error. - If the trace contradicts the final answer, score very low. - Treat formatting differences as acceptable only if the normalized answer is equivalent. - Output JSON only."
    norm = candidate.normalized_answer if candidate.normalized_answer is not None else "null"
    user = (
        f"Problem: {candidate.problem}\n\nCandidate reasoning trace: {candidate.trace}\n\n"
        f"Candidate final answer: {candidate.final_answer}\n\n"
        f"Normalized final answer if available: {norm}\n\n"
        "Return JSON with fields: {\"prob_correct\": float, \"trace_final_consistent\": bool, \"answer_equivalent_if_normalized\": bool | null, \"major_error\": bool, \"short_reason\": string}\n"
        "Scoring rubric: 1.00 = clearly correct reasoning and correct final answer; 0.75 = likely correct; no substantive math error found; 0.50 = uncertain / insufficient evidence; 0.25 = likely wrong; 0.00 = clearly wrong. Do not reward style or length. Verify strictly."
    )
    return system, user
