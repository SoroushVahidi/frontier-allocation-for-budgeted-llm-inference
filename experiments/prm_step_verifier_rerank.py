"""PRM-style step-level verifier reranking over DR-v2 candidate traces."""

from __future__ import annotations

import json
import math
import os
import re
from dataclasses import dataclass
from typing import Any, Protocol

from experiments.answer_grouped_outcome_verifier import CandidateAnswer, build_candidates_from_dr_v2_metadata


@dataclass(frozen=True)
class StepVerifierResult:
    validity_score: float
    progress_score: float | None
    major_error: bool
    short_reason: str
    parse_fallback: bool = False


@dataclass(frozen=True)
class TraceStepScore:
    step_index: int
    validity_score: float
    progress_score: float | None
    major_error: bool
    short_reason: str
    parse_fallback: bool


@dataclass(frozen=True)
class PRMAnswerGroupScore:
    normalized_answer: str
    group_score: float
    original_group_size: int
    representative_candidate_id: str


@dataclass(frozen=True)
class PRMSelectorDecision:
    selected_answer: str
    selected_candidate_id: str
    selected_group_score: float
    group_scores: list[PRMAnswerGroupScore]
    trace_scores: dict[str, float]
    step_scores: dict[str, list[dict[str, Any]]]
    verifier_calls: int
    verifier_backend: str
    verifier_model: str


class StepVerifier(Protocol):
    def verify_step(self, problem: str, prefix_steps: list[str], current_step: str, final_answer: str) -> StepVerifierResult: ...


_MIN_MERGE_LEN = 8
_LAMBDA_TRACE = 0.7
_BETA_PROGRESS = 0.7


def split_trace_into_steps(trace: str) -> list[str]:
    text = str(trace or "").strip()
    if not text:
        return []

    # 1) Numbered steps like "1." "2." at line starts
    numbered = re.split(r"(?m)(?=^\s*\d+\.\s+)", text)
    numbered = [re.sub(r"^\s*\d+\.\s+", "", seg).strip() for seg in numbered if seg.strip()]
    if len(numbered) > 1:
        steps = numbered
    else:
        # 2) Line breaks
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if len(lines) > 1:
            steps = lines
        else:
            # 3) Discourse markers
            parts = re.split(
                r"(?i)(?<=\s)(First|Then|Next|Therefore|Thus|Hence|So)(?=\s)",
                text,
            )
            steps = [p.strip() for p in parts if p and p.strip()]

    if not steps:
        steps = [text]

    # Merge extremely short fragments into previous (or next if first)
    merged: list[str] = []
    for seg in steps:
        seg = seg.strip()
        if not seg:
            continue
        if len(seg) < _MIN_MERGE_LEN and merged:
            merged[-1] = (merged[-1] + " " + seg).strip()
        elif len(seg) < _MIN_MERGE_LEN and not merged:
            merged.append(seg)
        else:
            merged.append(seg)

    return merged if merged else [text]


def _clip01(x: float) -> float:
    return min(max(float(x), 0.0), 1.0)


def aggregate_trace_score(step_results: list[StepVerifierResult]) -> float:
    if not step_results:
        return 0.0
    c_t = [_clip01(s.validity_score) for s in step_results]
    mean_validity = sum(c_t) / len(c_t)
    min_validity = min(c_t)
    q_i = _LAMBDA_TRACE * mean_validity + (1.0 - _LAMBDA_TRACE) * min_validity
    prog_vals = [s.progress_score for s in step_results if s.progress_score is not None]
    if prog_vals:
        mean_progress = sum(float(p) for p in prog_vals) / len(prog_vals)
        mean_progress = _clip01(mean_progress)
        u_i = _BETA_PROGRESS * q_i + (1.0 - _BETA_PROGRESS) * mean_progress
    else:
        u_i = q_i
    if any(s.major_error for s in step_results):
        u_i = min(u_i, 0.25)
    return float(u_i)


def _norm_answer_key(c: CandidateAnswer) -> str:
    return (c.normalized_answer or c.final_answer or "").strip().lower()


def select_answer_group_with_prm_step_verifier(
    candidates: list[CandidateAnswer],
    verifier: StepVerifier,
    *,
    verifier_backend: str = "mock",
    verifier_model: str = "command-r-plus-08-2024",
) -> PRMSelectorDecision:
    trace_scores: dict[str, float] = {}
    step_payload: dict[str, list[dict[str, Any]]] = {}
    calls = 0

    for c in candidates:
        steps = split_trace_into_steps(c.trace)
        if not steps:
            steps = [c.final_answer or "empty"]
        prefix: list[str] = []
        step_results: list[StepVerifierResult] = []
        frags: list[dict[str, Any]] = []
        for idx, step in enumerate(steps):
            res = verifier.verify_step(c.problem, list(prefix), step, c.final_answer)
            calls += 1
            step_results.append(res)
            frags.append(
                {
                    "step_index": idx,
                    "validity_score": float(res.validity_score),
                    "progress_score": res.progress_score,
                    "major_error": bool(res.major_error),
                    "short_reason": str(res.short_reason),
                    "parse_fallback": bool(res.parse_fallback),
                }
            )
            prefix.append(step)
        u_i = aggregate_trace_score(step_results)
        trace_scores[c.candidate_id] = u_i
        step_payload[c.candidate_id] = frags

    # Group by normalized answer
    groups: dict[str, list[CandidateAnswer]] = {}
    for c in candidates:
        k = _norm_answer_key(c) or "__unknown__"
        groups.setdefault(k, []).append(c)

    ranked: list[tuple[PRMAnswerGroupScore, list[CandidateAnswer]]] = []
    for ans, gcs in groups.items():
        s_sum = sum(trace_scores.get(x.candidate_id, 0.0) for x in gcs)
        rep = max(gcs, key=lambda x: trace_scores.get(x.candidate_id, 0.0))
        ranked.append((PRMAnswerGroupScore(ans, s_sum, len(gcs), rep.candidate_id), gcs))

    ranked.sort(key=lambda x: x[0].group_score, reverse=True)
    top = ranked[0][0]
    best_cand = max(ranked[0][1], key=lambda x: trace_scores.get(x.candidate_id, 0.0))

    return PRMSelectorDecision(
        selected_answer=top.normalized_answer,
        selected_candidate_id=best_cand.candidate_id,
        selected_group_score=float(top.group_score),
        group_scores=[g for g, _ in ranked],
        trace_scores=trace_scores,
        step_scores=step_payload,
        verifier_calls=calls,
        verifier_backend=str(verifier_backend).strip().lower(),
        verifier_model=str(verifier_model).strip(),
    )


class DeterministicMockStepVerifier:
    """Deterministic step verifier for tests and offline plumbing (no API)."""

    def verify_step(self, problem: str, prefix_steps: list[str], current_step: str, final_answer: str) -> StepVerifierResult:  # noqa: ARG002
        st = current_step.lower()
        if not st.strip():
            return StepVerifierResult(0.1, None, True, "empty_step", False)
        if any(tok in st for tok in ("wrong", "error", "contradict", "invalid")):
            return StepVerifierResult(0.15, 0.1, True, "marker_bad", False)
        base_v = 0.85
        prog = _clip01(0.45 + 0.02 * len(prefix_steps))
        if final_answer and str(final_answer).strip().lower() in st:
            base_v = min(1.0, base_v + 0.05)
        return StepVerifierResult(base_v, prog, False, "deterministic_mock_step", False)


class CohereStepVerifier:
    """Cohere-backed strict JSON step verifier with conservative fallback."""

    def __init__(
        self,
        *,
        model: str = "command-r-plus-08-2024",
        api_key: str | None = None,
        timeout_seconds: int = 45,
        client: object | None = None,
    ) -> None:
        self.model = model
        self.timeout_seconds = int(timeout_seconds)
        self._api_key = api_key if api_key is not None else os.getenv("COHERE_API_KEY", "")
        self._client = client

    def _ensure_client(self) -> object:
        if self._client is not None:
            return self._client
        if not self._api_key:
            raise RuntimeError("COHERE_API_KEY missing for CohereStepVerifier")
        import cohere  # type: ignore

        self._client = cohere.ClientV2(api_key=self._api_key, timeout=self.timeout_seconds)
        return self._client

    @staticmethod
    def _extract_json_obj(text: str) -> dict[str, object] | None:
        raw = str(text or "").strip()
        if not raw:
            return None
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            pass
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            snippet = raw[start : end + 1]
            try:
                parsed = json.loads(snippet)
                return parsed if isinstance(parsed, dict) else None
            except Exception:
                return None
        return None

    @staticmethod
    def _coerce(payload: dict[str, object]) -> StepVerifierResult:
        try:
            v = float(payload.get("validity_score", 0.5))
        except Exception:
            v = 0.5
        v = _clip01(v)
        pg = payload.get("progress_score", None)
        prog: float | None
        if pg is None:
            prog = None
        else:
            try:
                prog = _clip01(float(pg))
            except Exception:
                prog = None
        return StepVerifierResult(
            validity_score=v,
            progress_score=prog,
            major_error=bool(payload.get("major_error", False)),
            short_reason=str(payload.get("short_reason", "cohere_parsed"))[:300],
            parse_fallback=False,
        )

    def verify_step(self, problem: str, prefix_steps: list[str], current_step: str, final_answer: str) -> StepVerifierResult:
        system_prompt, user_prompt = build_prm_step_verifier_prompt(problem, prefix_steps, current_step, final_answer)
        try:
            cli = self._ensure_client()
            response = cli.chat(  # type: ignore[attr-defined]
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.0,
                max_tokens=160,
            )
            text = ""
            msg = getattr(response, "message", None)
            if msg is not None and getattr(msg, "content", None):
                for part in getattr(msg, "content"):
                    t = getattr(part, "text", "")
                    if t:
                        text += str(t)
            payload = self._extract_json_obj(text)
            if payload is None:
                return StepVerifierResult(0.5, None, False, "cohere_json_parse_failed", True)
            return self._coerce(payload)
        except Exception as exc:  # noqa: BLE001
            return StepVerifierResult(0.5, None, False, f"cohere_verify_error:{type(exc).__name__}", True)


def build_prm_step_verifier_prompt(
    problem: str,
    prefix_steps: list[str],
    current_step: str,
    final_answer: str,
) -> tuple[str, str]:
    system_prompt = (
        "You are a strict process verifier for math/word-problem reasoning. "
        "Given prior reasoning steps and the CURRENT step only, judge whether the current step is logically valid "
        "and whether it makes progress toward the candidate final answer. "
        "Penalize arithmetic/algebra/unit errors and contradictions with earlier steps. "
        "Do not use any ground-truth or reference solution text. Output JSON only."
    )
    prior = "\n".join(f"- {s}" for s in prefix_steps) if prefix_steps else "(none)"
    user_prompt = (
        f"Problem:\n{problem}\n\n"
        f"Prior reasoning steps:\n{prior}\n\n"
        f"Current step:\n{current_step}\n\n"
        f"Candidate final answer (for progress judgment only, not as ground truth):\n{final_answer}\n\n"
        "Return JSON with fields:\n"
        "{\n"
        '  "validity_score": float in [0,1],\n'
        '  "progress_score": float in [0,1] or null if not applicable,\n'
        '  "major_error": bool,\n'
        '  "short_reason": string\n'
        "}\n"
    )
    return system_prompt, user_prompt


def build_prm_candidates_from_dr_v2_metadata(question: str, metadata: dict[str, object]) -> list[CandidateAnswer]:
    """Reuse DR-v2 candidate extraction (same surface as outcome-verifier rerank)."""
    return build_candidates_from_dr_v2_metadata(question, metadata)
