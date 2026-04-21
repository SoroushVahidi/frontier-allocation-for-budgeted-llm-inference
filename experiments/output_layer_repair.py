from __future__ import annotations

from collections import Counter
import math
from typing import Any

from experiments.data import extract_final_answer, normalize_answer_text


def canonicalize_answer(answer_raw: str | None, *, dataset: str) -> str | None:
    """Dataset-safe canonicalization for exact-answer math datasets.

    Keeps logic deterministic and conservative: use shared normalization first,
    then apply small post-normalization numeric cleanup.
    """
    if answer_raw is None:
        return None
    norm = normalize_answer_text(str(answer_raw))
    cand = norm.get("normalized_answer")
    if cand is None:
        return None
    out = str(cand).strip()
    if not out:
        return None

    # Keep AIME answer semantics numeric but normalization-safe (e.g., 055 -> 55).
    if dataset.lower() in {"huggingfaceh4/aime_2024", "aime", "aime_2024"}:
        try:
            return str(int(float(out)))
        except ValueError:
            return out

    # For standard exact numeric datasets, normalize integer-like decimals.
    try:
        f = float(out)
        if f.is_integer():
            return str(int(f))
        return f"{f:.10g}"
    except ValueError:
        return out


def _to_text(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None


def deterministic_extract_answer(
    *,
    chosen_node_answer_raw: str | None,
    chosen_branch_reasoning_text: str | None,
) -> tuple[str | None, str]:
    """Deterministic extraction policy after node selection.

    Preference order: explicit branch-local answer > extracted-from-branch-text.
    """
    direct = _to_text(chosen_node_answer_raw)
    extracted = _to_text(extract_final_answer(chosen_branch_reasoning_text or "")) if _to_text(chosen_branch_reasoning_text) else None
    if direct is not None:
        return direct, "branch_local_answer_preferred"
    if extracted is not None:
        return extracted, "extracted_from_branch_reasoning_text"
    return None, "no_extractable_answer"


def classify_mismatch_subtype(row: dict[str, Any]) -> str:
    if row.get("canonical_answer_matches_ground_truth") and not row.get("surface_was_correct"):
        return "canonical_match_surface_mismatch"
    if row.get("chosen_node_vs_surface_mismatch"):
        return "chosen_node_vs_surface_mismatch"
    if row.get("chosen_node_vs_extraction_mismatch"):
        return "chosen_node_vs_extraction_mismatch"
    if row.get("extraction_vs_surface_mismatch"):
        return "extraction_vs_surface_mismatch"
    if row.get("canonicalization_changed_answer"):
        return "canonicalization_mismatch"
    if row.get("rescue_applied"):
        return "answer_level_rescue"
    return "unresolved_other"


def choose_repair_answer(
    *,
    final_nodes: list[dict[str, Any]],
    selected_group_hint: str | None,
    dataset: str,
    enable_rescue: bool = True,
    policy_mode: str = "current_selection_control",
) -> dict[str, Any]:
    done_nodes = [n for n in final_nodes if n.get("predicted_answer") is not None]
    selected_group = _to_text(selected_group_hint)

    def _group_nodes(nodes: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        out: dict[str, list[dict[str, Any]]] = {}
        for n in nodes:
            ck = canonicalize_answer(_to_text(n.get("predicted_answer")), dataset=dataset)
            if ck is None:
                continue
            out.setdefault(ck, []).append(n)
        return out

    def _pick_group_support_only(groups: dict[str, list[dict[str, Any]]]) -> str | None:
        if not groups:
            return None
        ranked = sorted(
            groups.items(),
            key=lambda kv: (
                len(kv[1]),
                sum(float(x.get("score", 0.0)) for x in kv[1]) / max(1, len(kv[1])),
                max(float(x.get("score", 0.0)) for x in kv[1]),
            ),
            reverse=True,
        )
        return ranked[0][0]

    def _pick_group_support_plus_score(groups: dict[str, list[dict[str, Any]]], *, calibrated: bool = False) -> str | None:
        if not groups:
            return None
        scores = [float(n.get("score", 0.0)) for members in groups.values() for n in members]
        if not scores:
            return _pick_group_support_only(groups)
        mn, mx = min(scores), max(scores)
        mean = sum(scores) / len(scores)
        var = sum((s - mean) ** 2 for s in scores) / max(1, len(scores))
        std = math.sqrt(max(var, 1e-12))

        def _norm(s: float) -> float:
            if calibrated:
                z = (s - mean) / std
                return 1.0 / (1.0 + math.exp(-z))
            if mx <= mn + 1e-12:
                return 0.5
            return (s - mn) / (mx - mn)

        total_nodes = sum(len(v) for v in groups.values())
        group_rows: list[tuple[str, float, int, float, float]] = []
        for gk, members in groups.items():
            support = len(members) / max(1, total_nodes)
            max_score = max(_norm(float(x.get("score", 0.0))) for x in members)
            mean_score = sum(_norm(float(x.get("score", 0.0))) for x in members) / max(1, len(members))
            if calibrated:
                group_score = 0.55 * support + 0.45 * mean_score
            else:
                group_score = 0.65 * support + 0.35 * max_score
            group_rows.append((gk, group_score, len(members), mean_score, max_score))
        group_rows.sort(key=lambda x: x[1], reverse=True)

        # Tie-break cleanup: near-tie prefers robust multi-branch support.
        if calibrated and len(group_rows) > 1 and abs(group_rows[0][1] - group_rows[1][1]) <= 0.03:
            top = sorted(group_rows[:2], key=lambda x: (x[2], x[3], x[4]), reverse=True)[0]
            return top[0]
        return group_rows[0][0]

    chosen: dict[str, Any] | None = None
    groups = _group_nodes(done_nodes)
    policy = str(policy_mode or "current_selection_control")
    winning_group: str | None = None
    if policy == "answer_group_support_only":
        winning_group = _pick_group_support_only(groups)
    elif policy == "answer_group_support_plus_node_score":
        winning_group = _pick_group_support_plus_score(groups, calibrated=False)
    elif policy == "answer_group_support_plus_calibrated_score":
        winning_group = _pick_group_support_plus_score(groups, calibrated=True)
    elif policy == "answer_group_support_plus_score_plus_tiebreak_cleanup":
        winning_group = _pick_group_support_plus_score(groups, calibrated=True)
    else:
        if selected_group is not None:
            cands = [
                n
                for n in done_nodes
                if canonicalize_answer(_to_text(n.get("predicted_answer")), dataset=dataset) == canonicalize_answer(selected_group, dataset=dataset)
            ]
            if cands:
                chosen = max(cands, key=lambda n: float(n.get("score", 0.0)))
        if chosen is None and done_nodes:
            chosen = max(done_nodes, key=lambda n: float(n.get("score", 0.0)))
            winning_group = canonicalize_answer(_to_text(chosen.get("predicted_answer")), dataset=dataset)

    if chosen is None and winning_group is not None:
        members = groups.get(winning_group, [])
        if members:
            chosen = max(members, key=lambda n: float(n.get("score", 0.0)))

    chosen_id = _to_text(chosen.get("branch_id")) if chosen else None
    chosen_raw = _to_text(chosen.get("predicted_answer")) if chosen else None
    chosen_canonical = canonicalize_answer(chosen_raw, dataset=dataset)
    reasoning_text = _to_text(chosen.get("reasoning_text")) if chosen else None

    extracted_raw, extraction_source = deterministic_extract_answer(
        chosen_node_answer_raw=chosen_raw,
        chosen_branch_reasoning_text=reasoning_text,
    )
    extracted_canonical = canonicalize_answer(extracted_raw, dataset=dataset)

    surfaced_raw = extracted_raw
    surfaced_canonical = extracted_canonical
    rescue_applied = False
    rescue_detail: dict[str, Any] = {"applied": False, "reason": "disabled_or_not_triggered"}

    if enable_rescue and done_nodes:
        canon_rows = []
        for n in done_nodes:
            ans_raw = _to_text(n.get("predicted_answer"))
            ans_can = canonicalize_answer(ans_raw, dataset=dataset)
            if ans_can is not None:
                canon_rows.append((ans_can, float(n.get("score", 0.0)), _to_text(n.get("branch_id"))))
        counts = Counter([c for c, _, _ in canon_rows])
        if counts:
            support_sorted = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
            top_ans, top_cnt = support_sorted[0]
            second_cnt = support_sorted[1][1] if len(support_sorted) > 1 else 0
            if top_cnt >= 2 and (top_cnt - second_cnt) >= 1:
                if surfaced_canonical != top_ans:
                    rescue_applied = True
                    surfaced_canonical = top_ans
                    surfaced_raw = top_ans
                    rescue_detail = {
                        "applied": True,
                        "reason": "high_support_canonical_consensus",
                        "top_support_count": int(top_cnt),
                        "second_support_count": int(second_cnt),
                        "candidate_supports": dict(counts),
                    }

    return {
        "selection_policy_mode": policy,
        "selected_group_hint": selected_group,
        "selected_group_after_policy": winning_group,
        "chosen_final_node_id": chosen_id,
        "chosen_final_node_answer_raw": chosen_raw,
        "chosen_final_node_answer_canonical": chosen_canonical,
        "extracted_final_answer_raw": extracted_raw,
        "extracted_final_answer_canonical": extracted_canonical,
        "surfaced_final_answer_raw": surfaced_raw,
        "surfaced_final_answer_canonical": surfaced_canonical,
        "extraction_source": extraction_source,
        "rescue_applied": rescue_applied,
        "rescue_detail": rescue_detail,
    }
