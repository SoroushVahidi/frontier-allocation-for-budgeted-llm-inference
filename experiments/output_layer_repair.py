from __future__ import annotations

from collections import Counter
import math
from typing import Any

from experiments.data import extract_final_answer, normalize_answer_text
from experiments.frontier_max_support_tiebreak import (
    build_merged_support_histogram_for_tiebreak,
    normalize_answer_group_key,
    pick_answer_text_for_normalized_group,
    resolve_frontier_bias_max_support_tiebreak,
)


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


def effective_answer_raw_from_node(node: dict[str, Any], *, dataset: str) -> str | None:
    """Gold-free: best-effort answer string from a runner ``final_nodes`` row (API-free).

    Preference: explicit ``predicted_answer`` > ``trace_extracted_answer`` >
    ``extract_final_answer(reasoning_text)``. The ``dataset`` parameter is reserved for
    future dataset-aware extraction hooks.
    """
    _ = dataset  # reserved for dataset-specific extraction policy extensions
    pa = _to_text(node.get("predicted_answer"))
    if pa is not None:
        return pa
    ta = _to_text(node.get("trace_extracted_answer"))
    if ta is not None:
        return ta
    rt = _to_text(node.get("reasoning_text"))
    if rt:
        ext = _to_text(extract_final_answer(rt))
        if ext is not None:
            return ext
    nl_raw = _to_text(node.get("numeric_leaf_value"))
    nl_st = str(node.get("numeric_leaf_status") or "").strip().lower()
    if nl_raw and nl_st in {"final", "provisional", "equation_progress"}:
        return nl_raw
    return None


def augment_final_nodes_with_metadata_frontier(
    final_nodes: list[dict[str, Any]],
    metadata: dict[str, Any],
) -> list[dict[str, Any]]:
    """Append frontier-weighted nodes when the live registry snapshot omits them (gold-free).

    Sources (in order): ``selector_candidate_pool`` rows, then ``frontier_metadata.action_trace``
    expand events. Does not remove or rewrite existing registry rows.
    """
    out: list[dict[str, Any]] = list(final_nodes)
    pool_rows = metadata.get("selector_candidate_pool") or []
    has_direct_hybrid = any(
        isinstance(r, dict) and str(r.get("source_metadata") or "").strip() == "direct_hybrid_seed" for r in pool_rows
    )
    if not bool(metadata.get("frontier_executed")) and not has_direct_hybrid:
        return out
    existing: set[str] = {str(n.get("branch_id") or "") for n in out if n.get("branch_id")}

    for row in pool_rows:
        if not isinstance(row, dict):
            continue
        bid = str(row.get("branch_id") or row.get("candidate_id") or "").strip()
        if not bid or bid in existing:
            continue
        existing.add(bid)
        pred = row.get("predicted_answer")
        trace = str(row.get("reasoning_text") or row.get("trace") or "")
        sm = str(row.get("source_metadata") or "").strip()
        out.append(
            {
                "branch_id": bid,
                "predicted_answer": pred,
                "reasoning_text": trace,
                "score": float(row.get("branch_score", 0.5) or 0.5),
                "trace_extracted_answer": None,
                "expand_answer_extraction_sources": [],
                "verify_answer_extraction_sources": [],
                "source_metadata": sm if sm else "selector_candidate_pool",
            }
        )

    fm = metadata.get("frontier_metadata") or {}
    at = fm.get("action_trace") or []
    for i, ev in enumerate(at):
        if not isinstance(ev, dict):
            continue
        if str(ev.get("action") or "").strip().lower() != "expand":
            continue
        bid = str(ev.get("branch_id") or "").strip() or f"frontier_expand_{i}"
        uniq = bid
        suffix = 0
        while uniq in existing:
            suffix += 1
            uniq = f"{bid}__{suffix}"
        existing.add(uniq)
        rt = str(ev.get("response_text") or ev.get("reasoning_text") or "")
        ea = ev.get("extracted_answer")
        ea_s = str(ea).strip() if ea is not None else ""
        out.append(
            {
                "branch_id": uniq,
                "predicted_answer": ea_s if ea_s else None,
                "reasoning_text": rt,
                "score": 0.5,
                "trace_extracted_answer": ea_s if ea_s else None,
                "expand_answer_extraction_sources": [],
                "verify_answer_extraction_sources": [],
                "source_metadata": "frontier_action_trace",
            }
        )
    return out


def resolve_selected_group_hint_from_metadata(metadata: dict[str, Any], *, dataset: str) -> str | None:
    """Resolve ``selected_group_hint`` for ``choose_repair_answer`` across controller families (gold-free)."""
    _ = dataset  # reserved for future dataset-specific hint shaping
    sg = _to_text(metadata.get("selected_group"))
    if sg and sg != "__unknown__":
        return sg
    fa = _to_text(metadata.get("final_answer"))
    if fa:
        return fa
    raw = metadata.get("answer_group_support_counts") or {}
    if isinstance(raw, dict) and raw:
        best: str | None = None
        best_cnt = -1
        for k, v in raw.items():
            try:
                c = int(v)
            except Exception:
                c = 0
            ks = str(k).strip()
            if not ks or ks == "__unknown__":
                continue
            if c > best_cnt:
                best, best_cnt = ks, c
        if best is not None:
            return best
    return _to_text(metadata.get("frontier_candidate_answer"))


def gold_in_tree_from_nodes(final_nodes: list[dict[str, Any]], gold_answer: str, *, dataset: str) -> int:
    """Whether gold appears in any node's effective answer (registry + metadata-augmented)."""
    gold_can = canonicalize_answer(gold_answer, dataset=dataset)
    if gold_can is None:
        return 0
    for n in final_nodes:
        raw = effective_answer_raw_from_node(n, dataset=dataset)
        if raw and canonicalize_answer(raw, dataset=dataset) == gold_can:
            return 1
    return 0


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


def apply_controller_committed_surfacing_for_evaluation(
    metadata: dict[str, Any],
    repaired: dict[str, Any],
    *,
    dataset: str,
) -> dict[str, Any]:
    """Prefer ``metadata['final_answer']`` for evaluated surfacing when the controller committed it.

    Gold-free: uses only runtime controller metadata, never evaluation labels.
    """
    out = dict(repaired)
    repair_raw = out.get("surfaced_final_answer_raw")
    out["repair_answer_raw"] = repair_raw
    ctrl_raw = _to_text((metadata or {}).get("final_answer"))
    out["controller_final_answer_raw"] = ctrl_raw if ctrl_raw else None

    if ctrl_raw:
        can = canonicalize_answer(ctrl_raw, dataset=dataset)
        out["surfaced_final_answer_raw"] = ctrl_raw
        out["surfaced_final_answer_canonical"] = can
        out["chosen_final_node_answer_raw"] = ctrl_raw
        out["chosen_final_node_answer_canonical"] = can
        out["final_answer_source"] = "controller_metadata_final_answer"
        return out

    if _to_text(out.get("surfaced_final_answer_raw")):
        out["final_answer_source"] = "repair_layer"
    else:
        out["final_answer_source"] = "fallback"
    return out


_FINALITY_EXPAND_SOURCES = frozenset({"api_json_final_answer", "api_json_answer"})


def node_has_expand_finality_marking(node: dict[str, Any]) -> bool:
    """Gold-free: JSON field-backed extraction counts as stronger commitment than reasoning fallback."""
    for key in ("expand_answer_extraction_sources", "verify_answer_extraction_sources"):
        for s in node.get(key) or []:
            if str(s) in _FINALITY_EXPAND_SOURCES:
                return True
    return False


def _has_reliable_frontier_answer_group_counts(metadata: dict[str, Any]) -> bool:
    fg = metadata.get("frontier_answer_group_counts") or {}
    if not isinstance(fg, dict) or not fg:
        return False
    try:
        return sum(int(v or 0) for v in fg.values()) > 0
    except Exception:
        return False


def _weak_singleton_canonical(canonical: str | None) -> bool:
    return canonical is not None and str(canonical).strip() in {"0", "1"}


def _distinct_numeric_canonicals_in_nodes(final_nodes: list[dict[str, Any]], *, dataset: str) -> set[str]:
    out: set[str] = set()
    for n in final_nodes:
        raw = effective_answer_raw_from_node(n, dataset=dataset)
        if raw is None:
            continue
        ck = canonicalize_answer(raw, dataset=dataset)
        if ck is not None:
            out.add(str(ck))
    return out


def surface_answer_has_evidence(
    *,
    surfaced_raw: str | None,
    surfaced_canonical: str | None,
    metadata: dict[str, Any],
    final_nodes: list[dict[str, Any]],
    dataset: str,
) -> bool:
    """Runtime-legal support: group counts, selected_group, tiebreak group, or finality-marked node match."""
    md = metadata or {}
    if md.get("external_baseline_family"):
        return True
    nk = normalize_answer_group_key(str(surfaced_raw or surfaced_canonical or "")).strip()
    if not nk or nk == "__unknown__":
        return False
    ag = md.get("answer_group_support_counts") or {}
    if isinstance(ag, dict):
        try:
            if int(ag.get(nk, 0) or 0) >= 1:
                return True
        except Exception:
            pass
    fg = md.get("frontier_answer_group_counts") or {}
    if isinstance(fg, dict):
        try:
            if int(fg.get(nk, 0) or 0) >= 1:
                return True
        except Exception:
            pass
    sg = md.get("selected_group")
    if sg is not None and normalize_answer_group_key(str(sg)) == nk:
        return True
    if md.get("frontier_tiebreak_triggered"):
        tbg = md.get("frontier_tiebreak_selected_group")
        if tbg is not None and normalize_answer_group_key(str(tbg)) == nk:
            return True
    target_can = surfaced_canonical
    if target_can is None and surfaced_raw:
        target_can = canonicalize_answer(surfaced_raw, dataset=dataset)
    if target_can is not None:
        for n in final_nodes:
            if canonicalize_answer(effective_answer_raw_from_node(n, dataset=dataset), dataset=dataset) == target_can:
                if node_has_expand_finality_marking(n):
                    return True
    return False


def interim_total_likely_mistaken(
    *,
    surfaced_canonical: str | None,
    surfaced_raw: str | None,
    metadata: dict[str, Any],
    final_nodes: list[dict[str, Any]],
    dataset: str,
) -> bool:
    """Conservative interim detector (gold-free): singleton merged support with alternate numerics elsewhere."""
    md = metadata or {}
    if surfaced_canonical is None and surfaced_raw:
        surfaced_canonical = canonicalize_answer(surfaced_raw, dataset=dataset)
    if surfaced_canonical is None:
        return False
    nk = normalize_answer_group_key(str(surfaced_raw or surfaced_canonical or "")).strip()
    if not nk:
        return False
    for n in final_nodes:
        if canonicalize_answer(effective_answer_raw_from_node(n, dataset=dataset), dataset=dataset) == surfaced_canonical:
            if node_has_expand_finality_marking(n):
                return False
    ag = md.get("answer_group_support_counts") or {}
    direct_trace = list(md.get("direct_reserve_attempts") or [])
    final_s = md.get("final_answer")
    if final_s is not None:
        final_s = str(final_s).strip() or None
    merged = build_merged_support_histogram_for_tiebreak(
        dict(ag) if isinstance(ag, dict) else {},
        final_answer=final_s,
        direct_trace=direct_trace,
    )
    try:
        mc = int(merged.get(nk, 0) or 0)
    except Exception:
        mc = 0
    if mc != 1:
        return False
    dist = _distinct_numeric_canonicals_in_nodes(final_nodes, dataset=dataset)
    return len(dist) >= 2


def choose_completion_answer_deterministic(
    *,
    metadata: dict[str, Any],
    final_nodes: list[dict[str, Any]],
    dataset: str,
    previous_surface_key_hint: str | None,
) -> tuple[str | None, str]:
    """Highest-support group with frontier tiebreak on ties; else best scored finality-marked node."""
    md = metadata or {}
    ag = md.get("answer_group_support_counts") or {}
    direct_trace = list(md.get("direct_reserve_attempts") or [])
    final_s = md.get("final_answer")
    if final_s is not None:
        final_s = str(final_s).strip() or None
    merged: dict[str, int] = build_merged_support_histogram_for_tiebreak(
        dict(ag) if isinstance(ag, dict) else {},
        final_answer=final_s,
        direct_trace=direct_trace,
    )
    if merged:
        max_v = max(int(v) for v in merged.values())
        tied = [
            str(g).strip()
            for g, v in merged.items()
            if str(g).strip() not in {"", "__unknown__"} and int(v) == int(max_v)
        ]
        chosen_g: str | None = None
        if len(tied) == 1:
            chosen_g = tied[0]
        else:
            fg_counts = dict(md.get("frontier_answer_group_counts") or {})
            dc_counts = dict(md.get("direct_answer_group_counts") or {})
            cg, _tm = resolve_frontier_bias_max_support_tiebreak(
                merged,
                fg_counts,
                dc_counts,
                previous_group_key=str(previous_surface_key_hint or tied[0] if tied else "__unknown__"),
            )
            if cg is not None:
                chosen_g = str(cg).strip()
            elif tied:

                def _fc(g: str) -> int:
                    try:
                        return int(fg_counts.get(g, 0) or 0)
                    except Exception:
                        return 0

                def _dc(g: str) -> int:
                    try:
                        return int(dc_counts.get(g, 0) or 0)
                    except Exception:
                        return 0

                chosen_g = sorted(tied, key=lambda g: (-_fc(g), -_dc(g), g))[0]
        if chosen_g:
            da_list: list[str | None] = []
            dr = md.get("direct_reserve_answer")
            if dr is not None:
                da_list.append(str(dr))
            txt = pick_answer_text_for_normalized_group(
                chosen_g,
                direct_answers=da_list,
                incumbent_answer=str(dr).strip() if dr is not None else None,
                frontier_answer=md.get("frontier_candidate_answer"),
                frontier_metadata=dict(md.get("frontier_candidate_metadata") or md.get("frontier_metadata") or {}),
                selector_candidate_pool=list(md.get("selector_candidate_pool") or []),
            )
            if txt and str(txt).strip():
                return str(txt).strip(), "completion_histogram_or_tiebreak"

    best_raw: str | None = None
    best_score = -1e18
    for n in final_nodes:
        if not node_has_expand_finality_marking(n):
            continue
        raw = effective_answer_raw_from_node(n, dataset=dataset)
        if raw is None:
            continue
        try:
            sc = float(n.get("score", 0.0) or 0.0)
        except Exception:
            sc = 0.0
        if sc > best_score:
            best_score = sc
            best_raw = raw
    if best_raw:
        return str(best_raw).strip(), "completion_finality_marked_node"
    return None, ""


def apply_finalization_guard_surfacing(
    metadata: dict[str, Any],
    repaired: dict[str, Any],
    *,
    final_nodes: list[dict[str, Any]],
    dataset: str,
    enabled: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Post-commit surfacing guard (gold-free). Does not call APIs."""
    sidecar: dict[str, Any] = {
        "finalguard_enabled": bool(enabled),
        "finalguard_triggered": False,
        "finalguard_previous_answer": None,
        "finalguard_selected_answer": None,
        "finalguard_reason": "disabled",
        "finalguard_answer_source": "",
    }
    if not enabled:
        return dict(repaired), sidecar

    md = dict(metadata or {})
    if md.get("external_baseline_family"):
        sidecar.update(
            {
                "finalguard_triggered": False,
                "finalguard_reason": "skipped_external_baseline_family",
                "finalguard_answer_source": "skipped_external_baseline",
            }
        )
        return dict(repaired), sidecar

    out = dict(repaired)
    prev_raw = _to_text(out.get("surfaced_final_answer_raw"))
    prev_can = canonicalize_answer(prev_raw, dataset=dataset) if prev_raw else None
    sidecar["finalguard_previous_answer"] = prev_can
    src = str(out.get("final_answer_source") or "")

    ev = surface_answer_has_evidence(
        surfaced_raw=prev_raw,
        surfaced_canonical=prev_can,
        metadata=md,
        final_nodes=final_nodes,
        dataset=dataset,
    )
    weak = _weak_singleton_canonical(prev_can)
    rel_fc = _has_reliable_frontier_answer_group_counts(md)
    interim = interim_total_likely_mistaken(
        surfaced_canonical=prev_can,
        surfaced_raw=prev_raw,
        metadata=md,
        final_nodes=final_nodes,
        dataset=dataset,
    )

    should_override = False
    reason = "keep_supported_commit"
    if src == "repair_layer" and weak and not rel_fc:
        should_override = True
        reason = "repair_weak_singleton_without_frontier_counts"
    elif interim:
        should_override = True
        reason = "interim_singleton_with_alternate_numeric_leaves"
    elif not ev and prev_can is not None and (
        weak or src == "repair_layer" or src == "controller_metadata_final_answer"
    ):
        should_override = True
        reason = "unsupported_surface_completion_attempt"

    if not should_override:
        sidecar.update(
            {
                "finalguard_triggered": False,
                "finalguard_reason": reason,
                "finalguard_answer_source": "kept_original",
                "finalguard_selected_answer": prev_can,
            }
        )
        return out, sidecar

    sidecar["finalguard_triggered"] = True
    prev_key = normalize_answer_group_key(str(prev_raw or prev_can or ""))
    cand_raw, cand_src = choose_completion_answer_deterministic(
        metadata=md,
        final_nodes=final_nodes,
        dataset=dataset,
        previous_surface_key_hint=prev_key or None,
    )
    cand_can = canonicalize_answer(cand_raw, dataset=dataset) if cand_raw else None

    if cand_raw is None or not str(cand_raw).strip():
        sidecar.update(
            {
                "finalguard_reason": reason + "_no_runtime_alternative_kept_fallback",
                "finalguard_answer_source": "kept_fallback_no_alternative",
                "finalguard_selected_answer": prev_can,
            }
        )
        return out, sidecar

    if cand_can == prev_can and str(cand_raw).strip() == str(prev_raw or "").strip():
        sidecar.update(
            {
                "finalguard_reason": reason + "_completion_unchanged",
                "finalguard_answer_source": "kept_original",
                "finalguard_selected_answer": prev_can,
            }
        )
        return out, sidecar

    out["surfaced_final_answer_raw"] = cand_raw
    out["surfaced_final_answer_canonical"] = cand_can
    out["chosen_final_node_answer_raw"] = cand_raw
    out["chosen_final_node_answer_canonical"] = cand_can
    out["final_answer_source"] = "finalguard_adjusted"
    sidecar.update(
        {
            "finalguard_selected_answer": cand_can,
            "finalguard_reason": reason + "_applied_completion",
            "finalguard_answer_source": cand_src,
        }
    )
    return out, sidecar


def choose_repair_answer(
    *,
    final_nodes: list[dict[str, Any]],
    selected_group_hint: str | None,
    dataset: str,
    enable_rescue: bool = True,
    policy_mode: str = "current_selection_control",
) -> dict[str, Any]:
    done_nodes = [n for n in final_nodes if effective_answer_raw_from_node(n, dataset=dataset) is not None]
    selected_group = _to_text(selected_group_hint)

    def _group_nodes(nodes: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        out: dict[str, list[dict[str, Any]]] = {}
        for n in nodes:
            raw_eff = effective_answer_raw_from_node(n, dataset=dataset)
            ck = canonicalize_answer(raw_eff, dataset=dataset) if raw_eff is not None else None
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
            sg_can = canonicalize_answer(selected_group, dataset=dataset)
            cands = [
                n
                for n in done_nodes
                if canonicalize_answer(effective_answer_raw_from_node(n, dataset=dataset), dataset=dataset) == sg_can
            ]
            if cands:
                chosen = max(cands, key=lambda n: float(n.get("score", 0.0)))
        if chosen is None and done_nodes:
            chosen = max(done_nodes, key=lambda n: float(n.get("score", 0.0)))
            winning_group = canonicalize_answer(effective_answer_raw_from_node(chosen, dataset=dataset), dataset=dataset)

    if chosen is None and winning_group is not None:
        members = groups.get(winning_group, [])
        if members:
            chosen = max(members, key=lambda n: float(n.get("score", 0.0)))

    chosen_id = _to_text(chosen.get("branch_id")) if chosen else None
    chosen_raw = effective_answer_raw_from_node(chosen, dataset=dataset) if chosen else None
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
            ans_raw = effective_answer_raw_from_node(n, dataset=dataset)
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
