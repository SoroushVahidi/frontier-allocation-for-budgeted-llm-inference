"""Deterministic helpers for gold-absent path-gap proxy diagnostics (not ground-truth paths)."""

from __future__ import annotations

import json
import math
from typing import Any

INTERNAL_METHOD_DEFAULT = "direct_reserve_semantic_frontier_v2"


def parse_case_id(case_id: str) -> tuple[str, str, int, int] | None:
    parts = (case_id or "").split("::")
    if len(parts) != 4:
        return None
    ds, ex, sd, bd = parts
    try:
        return ds.strip(), ex.strip(), int(sd), int(bd)
    except ValueError:
        return None


def _as_tri(v: Any) -> int | None:
    if v is None:
        return None
    s = str(v).strip()
    if s == "":
        return None
    try:
        return int(float(s))
    except ValueError:
        return None


def row_matches_gold_absent_focus(r: dict[str, Any]) -> bool:
    """OR of user conditions: discovery flag, gold absent from groups, gold absent from tree."""
    if _as_tri(r.get("discovery_failure_gold_absent")) == 1:
        return True
    if _as_tri(r.get("gold_present_in_candidate_groups")) == 0:
        return True
    if _as_tri(r.get("gold_present_in_tree")) == 0:
        return True
    return False


def load_per_example_index(
    paths: list[Any],
    *,
    methods: set[str] | None = None,
) -> dict[tuple[str, str, int, int, str], dict[str, Any]]:
    idx: dict[tuple[str, str, int, int, str], dict[str, Any]] = {}
    for p in paths:
        path = p if hasattr(p, "read_text") else __import__("pathlib").Path(p)
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                o = json.loads(line)
            except json.JSONDecodeError:
                continue
            m = str(o.get("method") or "").strip()
            if methods is not None and m not in methods:
                continue
            ds = str(o.get("dataset") or "").strip()
            ex = str(o.get("example_id") or "").strip()
            try:
                sd = int(o.get("seed"))
                bd = int(o.get("budget"))
            except (TypeError, ValueError):
                continue
            idx[(ds, ex, sd, bd, m)] = o
    return idx


def _max_branch_depth(action_trace: list[Any] | None) -> int | None:
    if not isinstance(action_trace, list):
        return None
    depths = []
    for t in action_trace:
        if not isinstance(t, dict):
            continue
        d = t.get("branch_depth")
        if isinstance(d, (int, float)) and not math.isnan(float(d)):
            depths.append(int(d))
    return max(depths) if depths else None


def _count_trace_actions(action_trace: list[Any] | None) -> int | None:
    if not isinstance(action_trace, list):
        return None
    return len(action_trace)


def extract_trace_stats_from_record(rec: dict[str, Any] | None) -> dict[str, Any]:
    out: dict[str, Any] = {
        "trace_available": 0,
        "max_depth_from_trace": "",
        "action_count_from_trace": "",
        "parse_extraction_failure": "",
        "gold_in_record": "",
        "failure_tag": "",
        "exact_match": "",
        "candidate_pool_size": "",
        "max_actions_used_in_pool": "",
    }
    if not rec:
        return out
    out["trace_available"] = 1
    rm = rec.get("result_metadata")
    rm = rm if isinstance(rm, dict) else {}
    at = rm.get("action_trace")
    if isinstance(at, list):
        md = _max_branch_depth(at)
        if md is not None:
            out["max_depth_from_trace"] = md
        ac = _count_trace_actions(at)
        if ac is not None:
            out["action_count_from_trace"] = ac
    pool = rm.get("selector_candidate_pool")
    if isinstance(pool, list) and pool:
        actions_used = []
        for c in pool:
            if isinstance(c, dict) and isinstance(c.get("actions_used"), (int, float)):
                actions_used.append(int(c["actions_used"]))
        if actions_used:
            out["max_actions_used_in_pool"] = max(actions_used)
        out["candidate_pool_size"] = len(pool)
    dra = rm.get("direct_reserve_attempts")
    if isinstance(dra, list) and out["action_count_from_trace"] == "":
        out["action_count_from_trace"] = len(dra)
    pe = rec.get("parse_extraction_failure")
    if pe is not None:
        out["parse_extraction_failure"] = int(pe) if str(pe).isdigit() else pe
    if rec.get("gold_in_tree") is not None:
        out["gold_in_record"] = rec.get("gold_in_tree")
    if rec.get("failure_tag") is not None:
        out["failure_tag"] = rec.get("failure_tag")
    if rec.get("exact_match") is not None:
        out["exact_match"] = rec.get("exact_match")
    return out


def numeric_or_string_distance(gold: str, cand: str) -> tuple[str, Any]:
    """Return ('numeric', abs_err) or ('string', lev_proxy_len_diff)."""
    g = str(gold or "").strip()
    c = str(cand or "").strip()
    if not g or not c:
        return ("string", "")
    try:
        gf = float(g.replace(",", "").replace("$", ""))
        cf = float(c.replace(",", "").replace("$", ""))
        return ("numeric", abs(cf - gf))
    except ValueError:
        return ("string", abs(len(c) - len(g)))


def closest_candidate_answer_to_gold(
    pool: list[dict[str, Any]] | None, gold_answer: str
) -> tuple[str | None, Any, Any, int | None]:
    """normalized_answer predicted, distance, distance_kind, branch_depth if any."""
    if not isinstance(pool, list) or not pool:
        return None, "", "", None
    best: tuple[float | int, str, str] | None = None
    best_depth = None
    gold = str(gold_answer or "").strip()
    for c in pool:
        if not isinstance(c, dict):
            continue
        pa = c.get("predicted_answer")
        na = c.get("normalized_answer")
        use = str(na if na is not None else pa or "").strip()
        if not use:
            continue
        kind, dist = numeric_or_string_distance(gold, use)
        key: float | int
        if kind == "numeric" and isinstance(dist, (int, float)):
            key = float(dist)
        elif isinstance(dist, int):
            key = dist
        else:
            key = 1e9
        if best is None or key < best[0]:
            best = (key, use, kind)
            bd = c.get("branch_depth")
            if isinstance(bd, (int, float)):
                best_depth = int(bd)
            else:
                best_depth = None
    if best is None:
        return None, "", "", None
    return best[1], best[0], best[2], best_depth


def infer_failure_mode_proxy(
    *,
    internal: dict[str, Any],
    external: dict[str, Any],
    casebook: dict[str, Any],
    est_depth_src: str,
    est_act_src: str,
) -> tuple[str, str, str, str]:
    """likely_failure_mode, reason, intervention, confidence (low/medium)."""
    reasons: list[str] = []
    if internal.get("trace_available") != 1:
        return (
            "trace_missing_or_unclassifiable",
            "No matching internal per_example_record for (dataset, example_id, seed, budget).",
            "Regenerate or link discovery JSONL for this slice.",
            "low",
        )
    if str(internal.get("parse_extraction_failure")) in ("1", "1.0", 1, True):
        return (
            "answer_extraction_or_canonicalization_issue",
            "Internal record reports parse_extraction_failure.",
            "Improve JSON step parsing / final answer extraction for DR-v2.",
            "medium",
        )
    if external.get("trace_available") != 1:
        reasons.append("external trace unavailable for matched key; path-gap proxy limited.")

    be = str(casebook.get("budget_exhausted_or_early_commit") or "").lower()
    prem = str(casebook.get("premature_commitment") or "").strip() in ("1", "1.0", 1, True)
    rpt_fam = int(float(str(casebook.get("repeated_same_family_expansion_count") or 0) or 0))
    rpt_ans = int(float(str(casebook.get("repeated_same_answer_expansion_count") or 0) or 0))
    bfc = int(float(str(casebook.get("branch_family_count") or 0) or 0))
    insuf_root = str(casebook.get("insufficient_root_diversity") or "").strip() in ("1", "1.0", 1, True)

    if insuf_root or bfc <= 1:
        return (
            "root_seeding_or_insufficient_branch_diversity",
            f"Low branch_family_count={bfc}, insufficient_root_diversity={insuf_root}.",
            "Increase early root diversity / reduce early collapse.",
            "low",
        )
    if rpt_fam >= 8 or rpt_ans >= 10:
        return (
            "repeated_same_family_overexpansion",
            f"High repeated expansions fam={rpt_fam}, ans={rpt_ans}.",
            "Tune anti-collapse / repetition penalties.",
            "low",
        )
    if prem or "early_commit" in be:
        return (
            "premature_commit",
            f"budget_exhausted_or_early_commit={be}, premature_commitment={prem}.",
            "Defer commitment; strengthen challenger maturation gates.",
            "low",
        )
    if est_depth_src.startswith("external") and isinstance(internal.get("max_depth_from_trace"), int):
        return (
            "insufficient_depth_or_pruning_under_budget",
            "External trace depth/action count exceeds internal proxy; gold path not in tree.",
            "Relax pruning or increase effective depth/search under same budget accounting.",
            "low",
        )
    if "unavailable" in est_depth_src:
        return (
            "estimate_unavailable",
            "; ".join(reasons) or "Insufficient fields for depth/action proxy.",
            "Collect aligned external JSONL per (seed,budget,example) or fuller traces.",
            "low",
        )
    return (
        "unknown_or_mixed",
        "Heuristic inconclusive; see per-field stats.",
        "Inspect action_trace and casebook manually.",
        "low",
    )


def compute_path_gap_estimates(
    *,
    internal_depth: int | None,
    internal_actions: int | None,
    closest_branch_depth: int | None,
    external_depth: int | None,
    external_actions: int | None,
) -> tuple[Any, Any, str]:
    """estimated_missing_depth, estimated_missing_actions, missing_edges_estimate_source."""
    est_d = ""
    est_a = ""
    src_d = ""

    if (
        isinstance(external_depth, int)
        and isinstance(closest_branch_depth, int)
        and external_depth >= 0
        and closest_branch_depth >= 0
    ):
        est_d = max(0, external_depth - closest_branch_depth)
        src_d = "external_trace_minus_closest_internal_branch"
    elif isinstance(external_depth, int) and isinstance(internal_depth, int):
        est_d = max(0, external_depth - internal_depth)
        src_d = "external_trace_minus_internal_max_depth"

    src_a = ""
    if isinstance(external_actions, int) and isinstance(internal_actions, int):
        est_a = max(0, external_actions - internal_actions)
        src_a = "external_action_minus_internal_actions"

    if src_d and src_a:
        return est_d, est_a, f"{src_d};{src_a}"
    if src_d:
        return est_d, est_a if est_a != "" else "", src_d
    if src_a:
        return "", est_a, src_a
    if external_depth is None and external_actions is None:
        return "", "", "unavailable_no_external_trace"
    if internal_depth is None and closest_branch_depth is None and internal_actions is None:
        return "", "", "unavailable_no_internal_trace"
    return "", "", "unavailable_no_depth_fields"
