from __future__ import annotations

from typing import Any

from experiments.answer_grouped_outcome_verifier import CandidateAnswer


def _normalize_key(answer: str | None) -> str:
    return str(answer or "").strip().lower()


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


def build_candidates_from_metadata(question: str, metadata: dict[str, object]) -> tuple[list[CandidateAnswer], list[str]]:
    source_keys = ["selector_candidate_pool", "final_branch_states", "branch_states", "final_nodes", "candidate_answers", "answer_groups"]
    candidates: list[CandidateAnswer] = []
    used: list[str] = []
    seen: set[tuple[str, str, str, str]] = set()
    for key in source_keys:
        rows = metadata.get(key, [])
        if not isinstance(rows, list):
            continue
        for idx, raw in enumerate(rows):
            if not isinstance(raw, dict):
                continue
            ans = str(raw.get("predicted_answer", "") or raw.get("final_answer", "") or raw.get("answer", "")).strip()
            if not ans:
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
                continue
            seen.add(dedup_key)
            candidates.append(CandidateAnswer(cid, question, trace_text, ans, _normalize_key(ans), source, prior, cost_norm))
            used.append(key)
        if candidates:
            break
    if not candidates:
        ans = str(metadata.get("final_answer", "") or "").strip()
        if ans:
            candidates = [CandidateAnswer("fallback_final", question, "", ans, _normalize_key(ans), "fallback", 0.5, 0.0)]
            used = ["final_answer_fallback"]
    return candidates, sorted(set(used))
