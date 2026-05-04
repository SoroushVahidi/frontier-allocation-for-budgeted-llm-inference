from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from experiments.answer_grouped_outcome_verifier import CandidateAnswer
from experiments.data import extract_final_answer

SOURCE_KEYS: tuple[str, ...] = (
    "selector_candidate_pool",
    "final_branch_states",
    "branch_states",
    "final_nodes",
    "candidate_answers",
    "answer_groups",
)


def _normalize_key(answer: str | None) -> str:
    return str(answer or "").strip().lower()


SOURCE_TRACE_DIRECT = "direct_reserve_attempts_response_text"
SOURCE_TRACE_BRANCH = "branch_state_trace_response_text"

_MAX_TRACE_EXTRACT_CHARS = 12_000


def _extract_trace(state: dict[str, Any]) -> str:
    if isinstance(state.get("trace"), str) and state.get("trace"):
        return str(state["trace"]).strip()
    frags: list[str] = []
    for key in ("trace_events", "events"):
        events = state.get(key, [])
        if isinstance(events, list):
            for ev in events:
                if isinstance(ev, dict):
                    frags.append(str(ev.get("reasoning_text", "") or ev.get("response_text", "") or ev.get("text", "")))
    steps = state.get("steps", [])
    if isinstance(steps, list):
        frags.extend(str(s) for s in steps if s is not None)
    return "\n".join(x for x in frags if str(x).strip()).strip()


def _attempt_row_text_blob(row: dict[str, Any]) -> str:
    parts: list[str] = []
    for k in ("response_text", "reasoning_text"):
        t = str(row.get(k) or "").strip()
        if t:
            parts.append(t)
    return "\n".join(parts).strip()


def _maybe_answer_from_text_blob(blob: str) -> str:
    if not blob:
        return ""
    clipped = blob if len(blob) <= _MAX_TRACE_EXTRACT_CHARS else blob[:_MAX_TRACE_EXTRACT_CHARS]
    ans = extract_final_answer(clipped).strip()
    if not ans or len(ans) > 64:
        return ""
    return ans


def _append_trace_response_candidates(
    question: str,
    metadata: dict[str, object],
    candidates: list[CandidateAnswer],
    used: list[str],
    seen: set[tuple[str, str, str, str]],
    collect_diag: bool,
    skips: Counter[str],
) -> None:
    """Recover numeric/text answers from API trace blobs when structured fields are empty."""

    rows = metadata.get("direct_reserve_attempts")
    if isinstance(rows, list):
        for i, row in enumerate(rows):
            if not isinstance(row, dict):
                if collect_diag:
                    skips["trace_harvest:direct_reserve_attempts:non_dict_row"] += 1
                continue
            blob = _attempt_row_text_blob(row)
            if not blob:
                if collect_diag:
                    skips["trace_harvest:direct_reserve_attempts:empty_text_blob"] += 1
                continue
            ans = _maybe_answer_from_text_blob(blob)
            if not ans:
                if collect_diag:
                    skips["trace_harvest:direct_reserve_attempts:extract_empty"] += 1
                continue
            cid = str(row.get("branch_id", "") or f"direct_reserve_attempt_{i}")
            trace_text = blob if len(blob) <= 2000 else blob[:2000]
            dedup_key = (cid, ans, SOURCE_TRACE_DIRECT, trace_text)
            if dedup_key in seen:
                if collect_diag:
                    skips["trace_harvest:direct_reserve_attempts:dedup_skipped"] += 1
                continue
            seen.add(dedup_key)
            candidates.append(
                CandidateAnswer(
                    cid,
                    question,
                    trace_text,
                    ans,
                    _normalize_key(ans),
                    SOURCE_TRACE_DIRECT,
                    0.45,
                    0.0,
                )
            )
            used.append(SOURCE_TRACE_DIRECT)

    for bkey in ("final_branch_states", "branch_states"):
        brows = metadata.get(bkey, [])
        if not isinstance(brows, list):
            if collect_diag:
                skips[f"trace_harvest:{bkey}:rows_not_list"] += 1
            continue
        for idx, raw in enumerate(brows):
            if not isinstance(raw, dict):
                if collect_diag:
                    skips[f"trace_harvest:{bkey}:non_dict_row"] += 1
                continue
            structured = str(
                raw.get("predicted_answer", "") or raw.get("final_answer", "") or raw.get("answer", "")
            ).strip()
            if structured:
                continue
            blob = _extract_trace(raw)
            if not blob:
                if collect_diag:
                    skips[f"trace_harvest:{bkey}:empty_trace_blob"] += 1
                continue
            ans = _maybe_answer_from_text_blob(blob)
            if not ans:
                if collect_diag:
                    skips[f"trace_harvest:{bkey}:trace_extract_empty"] += 1
                continue
            cid = str(raw.get("branch_id", "") or raw.get("candidate_id", "") or f"{bkey}_{idx}")
            trace_text = blob if len(blob) <= 2000 else blob[:2000]
            source = f"{SOURCE_TRACE_BRANCH}:{bkey}"
            dedup_key = (cid, ans, source, trace_text)
            if dedup_key in seen:
                if collect_diag:
                    skips[f"trace_harvest:{bkey}:trace_dedup_skipped"] += 1
                continue
            seen.add(dedup_key)
            candidates.append(
                CandidateAnswer(
                    cid,
                    question,
                    trace_text,
                    ans,
                    _normalize_key(ans),
                    source,
                    0.45,
                    0.0,
                )
            )
            used.append(source)


def _format_skip_counts(skips: Counter[str]) -> str:
    if not skips:
        return ""
    return "; ".join(f"{k}={v}" for k, v in sorted(skips.items()))


@dataclass(frozen=True)
class CandidateExtractionDiagnostics:
    """Read-only extraction audit; does not affect candidate selection."""

    metadata_keys_present: str
    extraction_skip_counts: str


def _build_candidates_impl(
    question: str,
    metadata: dict[str, object],
    *,
    collect_diag: bool,
) -> tuple[list[CandidateAnswer], list[str], CandidateExtractionDiagnostics]:
    candidates: list[CandidateAnswer] = []
    used: list[str] = []
    seen: set[tuple[str, str, str, str]] = set()
    skips: Counter[str] = Counter()
    meta_keys_str = ",".join(sorted(str(k) for k in metadata.keys())) if collect_diag else ""

    for key in SOURCE_KEYS:
        rows = metadata.get(key, [])
        if not isinstance(rows, list):
            if collect_diag:
                skips[f"{key}:rows_not_list"] += 1
            continue
        for idx, raw in enumerate(rows):
            if not isinstance(raw, dict):
                if collect_diag:
                    skips[f"{key}:non_dict_row"] += 1
                continue
            ans = str(raw.get("predicted_answer", "") or raw.get("final_answer", "") or raw.get("answer", "")).strip()
            if not ans:
                if collect_diag:
                    skips[f"{key}:empty_answer_field"] += 1
                continue
            cid = str(raw.get("branch_id", "") or raw.get("candidate_id", "") or f"{key}_{idx}")
            source = str(raw.get("source", "") or raw.get("source_id", "") or cid)
            try:
                prior = min(max(float(raw.get("score", raw.get("source_prior", 0.5))), 0.0), 1.0)
            except Exception:
                prior = 0.5
            try:
                if raw.get("branch_depth", None) is not None:
                    depth = float(raw.get("branch_depth", 0.0))
                    cost_norm = min(max(depth / 10.0, 0.0), 1.0)
                else:
                    cost_norm = min(max(float(raw.get("cost_norm", 0.0)), 0.0), 1.0)
            except Exception:
                cost_norm = 0.0
            trace_text = _extract_trace(raw)
            dedup_key = (cid, ans, source, trace_text)
            if dedup_key in seen:
                if collect_diag:
                    skips[f"{key}:dedup_skipped"] += 1
                continue
            seen.add(dedup_key)
            candidates.append(CandidateAnswer(cid, question, trace_text, ans, _normalize_key(ans), source, prior, cost_norm))
            used.append(key)
        if candidates:
            break
    if not candidates:
        _append_trace_response_candidates(
            question, metadata, candidates, used, seen, collect_diag, skips
        )
    if not candidates:
        ans = str(metadata.get("final_answer", "") or "").strip()
        if ans:
            candidates = [CandidateAnswer("fallback_final", question, "", ans, _normalize_key(ans), "fallback", 0.5, 0.0)]
            used = ["final_answer_fallback"]
        elif collect_diag:
            skips["no_candidates_used_final_answer_fallback_missing"] += 1

    diag = CandidateExtractionDiagnostics(
        metadata_keys_present=meta_keys_str,
        extraction_skip_counts=_format_skip_counts(skips),
    )
    return candidates, sorted(set(used)), diag


def build_candidates_from_metadata(question: str, metadata: dict[str, object]) -> tuple[list[CandidateAnswer], list[str]]:
    candidates, used, _diag = _build_candidates_impl(question, metadata, collect_diag=False)
    return candidates, used


def build_candidates_from_metadata_diagnostic(
    question: str, metadata: dict[str, object]
) -> tuple[list[CandidateAnswer], list[str], CandidateExtractionDiagnostics]:
    """Same candidates as `build_candidates_from_metadata`, plus extraction audit fields."""
    return _build_candidates_impl(question, metadata, collect_diag=True)
