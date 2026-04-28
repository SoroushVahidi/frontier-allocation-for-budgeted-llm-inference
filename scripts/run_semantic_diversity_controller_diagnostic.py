#!/usr/bin/env python3
"""Offline and live Cohere diagnostics for semantic-diversity experimental controllers."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import os
import random
import re
import subprocess
import sys
import traceback
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.data import PilotExample, extract_final_answer
from experiments.frontier_matrix_core import (
    build_frontier_strategies,
    build_semantic_diversity_diagnostic_registry,
    generator_factory_for_mode,
    load_pilot_examples,
)
from experiments.scoring import SimpleBranchScorer, ScoreConfig

STRICT_F3_RUNTIME = (
    "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_"
    "repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth3_coverage_forced_v1"
)

METHODS_COMPARE = [
    "external_l1_max",
    "strict_f3",
    "semantic_minimum_maturation_frontier_v1_d2",
    "semantic_minimum_maturation_frontier_v1_d3",
    "direct_reserve_semantic_frontier_v1",
    "branching_necessity_gate_v1",
    "semantic_minimum_maturation_plus_direct_reserve_v1",
]

# trace-complete loss diagnostic: omit underperforming d2; keep branching_necessity (cheap flag layer)
METHODS_LOSS_FULL = [
    "external_l1_max",
    "strict_f3",
    "semantic_minimum_maturation_frontier_v1_d3",
    "direct_reserve_semantic_frontier_v1",
    "branching_necessity_gate_v1",
    "semantic_minimum_maturation_plus_direct_reserve_v1",
]

# Cost-focused expanded-pool live run (user-curated; re-check with --methods to add e.g. branching_necessity_gate_v1)
METHODS_EXPANDED_POOL = [
    "external_l1_max",
    "strict_f3",
    "direct_reserve_semantic_frontier_v1",
    "semantic_minimum_maturation_plus_direct_reserve_v1",
]

EXPANDED_INTERNAL_METHODS = {
    "strict_f3",
    "strict_gate1_cap_k6",
    "strict_f3_anti_collapse_weak_v1",
    "direct_reserve_frontier_gate_v1",
}

DEFAULT_LOSS_JSONL = (
    REPO_ROOT
    / "outputs"
    / "cohere_absent_from_tree_loss_diagnostics_20260427T171917Z"
    / "loss_cases_absent_from_tree.jsonl"
)


def _load_readiness():
    p = REPO_ROOT / "scripts" / "run_cohere_trace_complete_loss_subset.py"
    spec = importlib.util.spec_from_file_location("cohere_tr_read", p)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        if fieldnames:
            with path.open("w", encoding="utf-8", newline="") as f:
                csv.DictWriter(f, fieldnames=fieldnames).writeheader()
        return
    fn = fieldnames or list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fn)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fn})


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def _method_runtime_key(method: str) -> str:
    return STRICT_F3_RUNTIME if method == "strict_f3" else method


def resolved_methods(methods_csv: str, *, selection_profile: str) -> list[str]:
    if methods_csv.strip():
        return [m.strip() for m in methods_csv.split(",") if m.strip()]
    if selection_profile == "loss-full":
        return list(METHODS_LOSS_FULL)
    if selection_profile == "expanded-loss-pool":
        return list(METHODS_EXPANDED_POOL)
    return list(METHODS_COMPARE)


def _safe_int(r: dict[str, Any], key: str, default: int = 0) -> int:
    try:
        return int(float(str(r.get(key, default)).strip()))
    except (TypeError, ValueError):
        return default


def _select_live_cases_loss_full(
    loss_rows: list[dict[str, Any]],
    max_cases: int,
    seed: int,
) -> list[dict[str, Any]]:
    """Prioritize internal-wrong/external-correct, confirmed absent-from-tree; diversify problem_type."""
    rng = random.Random(seed + 7919)
    pool = [
        r
        for r in loss_rows
        if str(r.get("internal_method_name", "")) == "strict_f3" and _loss_row_has_question_and_gold(r)
    ]
    iw_ec = [
        r
        for r in pool
        if _safe_int(r, "internal_exact_match", -1) == 0 and _safe_int(r, "external_exact_match", -1) == 1
    ]
    primary_pool = iw_ec if iw_ec else pool
    tier_a = [r for r in primary_pool if str(r.get("absent_from_tree_status", "")) == "confirmed_absent_from_tree"]
    tier_b = [r for r in primary_pool if r not in tier_a]

    def enrich(rr: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rng.shuffle(rr)
        by_pt: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rr:
            by_pt[str(row.get("problem_type") or "unknown")].append(row)
        picked: list[dict[str, Any]] = []
        keys = list(by_pt.keys())
        rng.shuffle(keys)
        while any(by_pt.values()) and len(picked) < max_cases:
            progressed = False
            for k in keys:
                if len(picked) >= max_cases:
                    break
                if by_pt[k]:
                    picked.append(by_pt[k].pop())
                    progressed = True
            if not progressed:
                break
        return picked

    candidates = enrich(tier_a) + enrich(tier_b)
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for r in candidates:
        eid = str(r.get("example_id", "")).strip()
        if not eid or eid in seen:
            continue
        seen.add(eid)
        unique.append(r)
        if len(unique) >= max_cases:
            break
    if len(unique) < max_cases:
        remainder = enrich([r for r in pool if str(r.get("example_id")) not in seen])
        for r in remainder:
            eid = str(r.get("example_id", "")).strip()
            if not eid or eid in seen:
                continue
            seen.add(eid)
            unique.append(r)
            if len(unique) >= max_cases:
                break
    return unique[:max_cases]


def _sanitize_method_tag(method: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in method)[:120]


def _estimate_tokens_latency_cost(meta: dict[str, Any], *, actions_used: int) -> tuple[float, float, float, float]:
    """Extract token-ish sums from trace_events where present; rough cost USD proxy."""
    traces = meta.get("action_trace") or []
    if not isinstance(traces, list):
        traces = []
    in_sum = out_sum = 0.0
    lat_sum = 0.0
    lat_n = 0
    for ev in traces:
        if not isinstance(ev, dict):
            continue
        llm = ev.get("llm_usage") or {}
        if isinstance(llm, dict):
            in_sum += float(llm.get("input_tokens") or llm.get("prompt_tokens") or 0)
            out_sum += float(llm.get("output_tokens") or llm.get("completion_tokens") or 0)
        ti = ev.get("latency_seconds") or ev.get("wall_time_seconds")
        if ti is not None:
            try:
                lat_sum += float(ti)
                lat_n += 1
            except (TypeError, ValueError):
                pass
        te = ev.get("trace_events")
        if isinstance(te, dict):
            tok = te.get("tokens") or {}
            if isinstance(tok, dict):
                in_sum += float(tok.get("input_tokens") or 0)
                out_sum += float(tok.get("output_tokens") or 0)
    if in_sum == 0 and out_sum == 0:
        rough = float(actions_used) * 64.0 * 3.0
        in_sum = rough * 0.65
        out_sum = rough * 0.35
    latency = lat_sum / max(1, lat_n) if lat_n else float("nan")
    cost_proxy = (in_sum + out_sum) * 1e-6 * 0.5
    return float(in_sum), float(out_sum), latency, float(cost_proxy)


def _taxonomy_from_meta(meta: dict[str, Any], *, method: str, trace_len: int) -> str:
    if trace_len <= 1 and method not in {"external_l1_max"}:
        return "trace_sparse_or_truncated"
    rf = str(meta.get("regime_failure_category") or "").strip()
    ef = str(meta.get("early_divergence_failure_category") or "").strip()
    base = rf or ef or ""
    if not base:
        return "unknown_unclassified"
    mapping = {
        "correct_answer_group_absent": "bad_seeding_absent_answer_group",
        "repeated_same_branch_expansion_dominated_budget": "bad_allocation_budget_domination",
        "correct_group_preserved_but_insufficiently_matured": "bad_maturation",
        "final_commit_lost_despite_viable_alternative": "bad_selection_repair",
        "generated_but_underweighted": "bad_selection_underweight",
        "generated_but_committed_away_from_later": "bad_selection_early_commit",
    }
    return mapping.get(base, base)


def _write_full_trace_json(
    out_dir: Path,
    *,
    example_id: str,
    budget: int,
    method: str,
    meta: dict[str, Any],
) -> str:
    rel = Path("full_traces") / f"{example_id}_b{budget}_{_sanitize_method_tag(method)}.json"
    path = out_dir / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    dsem = meta.get("diagnostic_semantic_diversity") or {}
    fm = meta.get("frontier_metadata") or {}
    payload = {
        "action_trace": meta.get("action_trace", []),
        "final_branch_states": meta.get("final_branch_states", []),
        "diagnostic_semantic_diversity": dsem,
        "frontier_diagnostic_semantic": (fm.get("diagnostic_semantic_diversity") if isinstance(fm, dict) else {}) or {},
        "regime_failure_category": meta.get("regime_failure_category"),
        "early_divergence_failure_category": meta.get("early_divergence_failure_category"),
        "gold_group_ever_present": meta.get("gold_group_ever_present"),
        "gold_group_present_final": meta.get("gold_group_present_final"),
        "immediate_miss_proxy": meta.get("gold_group_present_after_first_split"),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, default=str), encoding="utf-8")
    return str(rel.as_posix())


def _cohere_build_row(
    *,
    picked_row: dict[str, Any],
    ex0: PilotExample,
    budget: int,
    method: str,
    model: str,
    dataset: str,
    res: Any,
    meta: dict[str, Any],
    emit_full_traces: bool,
    trace_rel: str,
    cohort_slot: int | None = None,
) -> dict[str, Any]:
    dsem = meta.get("diagnostic_semantic_diversity") or {}
    fmeta = (meta.get("frontier_metadata") or {}) if isinstance(meta.get("frontier_metadata"), dict) else {}
    dsem2 = (fmeta.get("diagnostic_semantic_diversity") if isinstance(fmeta.get("diagnostic_semantic_diversity"), dict) else {}) or {}
    cand = meta.get("candidate_group_support") or meta.get("answer_support_counts") or {}
    traces = meta.get("action_trace") or []
    trace_len = len(traces) if isinstance(traces, list) else 0
    mat_audit = (dsem or {}).get("maturation_phase_audit") or []
    f2l = dsem.get("families_reaching_depth_ge_2")
    f3l = dsem.get("families_reaching_depth_ge_3")
    ft2: int | str = len(f2l) if isinstance(f2l, list) else ""
    ft3: int | str = len(f3l) if isinstance(f3l, list) else ""
    in_tok, out_tok, latency, cost_p = _estimate_tokens_latency_cost(meta, actions_used=int(res.actions_used))
    ent = float(meta.get("answer_support_entropy") or 0.0)
    grp = meta.get("answer_support_counts") or {}
    gap = 0.0
    if isinstance(grp, dict) and grp:
        vals = sorted((float(v) for v in grp.values()), reverse=True)
        total = sum(vals) or 1.0
        gap = float((vals[0] - (vals[1] if len(vals) > 1 else 0)) / total)

    gold_tree_flag = meta.get("gold_answer_present_in_candidate_pool")
    if gold_tree_flag is None or gold_tree_flag == "":
        gold_tree_flag = meta.get("gold_present_in_candidate_pool")
    if gold_tree_flag is None or gold_tree_flag == "":
        gold_tree_flag = picked_row.get("gold_final_answer_in_internal_tree")

    try:
        absent_flag = int(float(str(meta.get("absent_from_tree", 0) or 0)))
    except (TypeError, ValueError):
        absent_flag = 0
    pns = 0
    if str(gold_tree_flag) in {"1", "true", "True"} or gold_tree_flag == 1:
        try:
            pns = int(bool(meta.get("present_not_selected"))) if meta.get("present_not_selected") is not None else 0
        except (TypeError, ValueError):
            pns = 0

    tox = _taxonomy_from_meta(meta, method=method, trace_len=trace_len)

    try:
        sfc_denom = float(str(dsem.get("semantic_family_count") or dsem2.get("semantic_family_count") or "1").strip() or "1")
    except (TypeError, ValueError):
        sfc_denom = 1.0

    return {
        "mode": "cohere",
        "provider": str(picked_row.get("provider") or "cohere"),
        "model": model,
        "dataset": dataset,
        "seed": picked_row.get("seed", ""),
        "budget": budget,
        "example_id": ex0.example_id,
        "question": ex0.question[:2000],
        "gold_answer": str(ex0.answer),
        "problem_type_loss_row": picked_row.get("problem_type", ""),
        "selection_absent_from_tree_status": picked_row.get("absent_from_tree_status", ""),
        "method": method,
        "is_correct": int(bool(res.is_correct)),
        "prediction_raw": str(res.prediction or ""),
        "prediction_normalized": _normalize_live_answer(res.prediction),
        "gold_normalized": _normalize_live_answer(ex0.answer),
        "exact_match": int(bool(res.is_correct)),
        "candidate_answer_groups_json": json.dumps(dict(cand), ensure_ascii=False)[:12000]
        if isinstance(cand, dict)
        else str(cand)[:12000],
        "gold_answer_in_tree_best_effort": gold_tree_flag if gold_tree_flag is not None else "",
        "absent_from_tree_meta": absent_flag,
        "present_not_selected_meta": meta.get("present_not_selected"),
        "present_not_selected_infer": pns,
        "actions_used": res.actions_used,
        "expansions": res.expansions,
        "verifications": res.verifications,
        "budget_exhausted": int(res.budget_exhausted),
        "semantic_family_count": dsem.get("semantic_family_count", "") or dsem2.get("semantic_family_count", ""),
        "semantic_family_ids_json": json.dumps(dsem.get("semantic_family_id_by_branch"), ensure_ascii=False)
        if dsem.get("semantic_family_id_by_branch")
        else "",
        "semantic_family_features_json": (
            json.dumps(dsem.get("semantic_families"), ensure_ascii=False)[:12000]
            if dsem.get("semantic_families")
            else json.dumps(dsem.get("semantic_family_id_by_branch"), ensure_ascii=False)[:8000]
            if dsem.get("semantic_family_id_by_branch")
            else ""
        ),
        "root_branch_count": dsem.get("root_branch_count", ""),
        "family_redundancy_ratio": dsem.get("family_redundancy_ratio", "") or dsem2.get("family_redundancy_ratio", ""),
        "family_entropy_answer_support": ent,
        "top2_gap_answer_support": gap,
        "num_families_depth_ge_2": ft2 if ft2 != "" else "",
        "num_families_depth_ge_3": ft3 if ft3 != "" else "",
        "share_families_depth_ge_2": (
            round(float(ft2) / max(1.0, sfc_denom), 4) if isinstance(ft2, int) else ""
        ),
        "share_families_depth_ge_3": (
            round(float(ft3) / max(1.0, sfc_denom), 4) if isinstance(ft3, int) else ""
        ),
        "adaptive_phase_len_proxy": max(0, trace_len - len(mat_audit)),
        "maturation_phase_audit_len": len(mat_audit),
        "maturation_phase_audit_json": json.dumps(mat_audit[:400], ensure_ascii=False)[:8000],
        "branching_necessity_last": dsem.get("branching_necessity_score", "") or dsem2.get("branching_necessity_score", ""),
        "branching_necessity_decision_last": dsem.get("branching_necessity_decision", ""),
        "direct_incumbent_pool_size": meta.get("direct_reserve_attempts_executed", ""),
        "incumbent_replaced": meta.get("incumbent_replaced", ""),
        "replacement_reason": str(meta.get("incumbent_replacement_reason", "")),
        "commit_reason_regime": str(meta.get("regime_failure_category", "")),
        "commit_reason_early_div": str(meta.get("early_divergence_failure_category", "")),
        "answer_entropy": ent,
        "estimated_input_tokens": round(in_tok, 2),
        "estimated_output_tokens": round(out_tok, 2),
        "estimated_latency_seconds": latency,
        "estimated_cost_usd_proxy": round(cost_p, 8),
        "failure_taxonomy": tox,
        "gold_group_ever_present": meta.get("gold_group_ever_present"),
        "gold_group_present_final": meta.get("gold_group_present_final"),
        "immediate_miss_proxy": meta.get("gold_group_present_after_first_split"),
        "emit_full_traces": int(bool(emit_full_traces)),
        "trace_json_path": trace_rel if emit_full_traces else "",
        "action_trace_len": trace_len,
        "branch_trace_len": len(meta.get("final_branch_states") or []) if isinstance(meta.get("final_branch_states"), list) else 0,
        "cohort_slot": cohort_slot if cohort_slot is not None else "",
        "selection_phase": picked_row.get("_selection_phase", ""),
        "loss_row_seed": picked_row.get("seed", ""),
        "loss_row_budget_observed": picked_row.get("budget", ""),
    }


def _normalize_live_answer(pred: Any) -> str:
    if pred is None:
        return ""
    s = str(pred).strip()
    nums = re.findall(r"[-+]?\d+(?:\.\d+)?", s.replace(",", ""))
    if nums:
        v = nums[-1]
        return v[:-2] if v.endswith(".0") else v
    return s.lower()


def _build_specs_for_budget(
    *,
    use_api: bool,
    model: str,
    budget: int,
    selection_seed: int,
    temperature: float,
    max_output_tokens: int,
    timeout_seconds: int,
) -> dict[str, Any]:
    rng = random.Random(selection_seed + budget)
    factory = generator_factory_for_mode(
        use_openai_api=use_api,
        rng=rng,
        openai_model=model,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        timeout_seconds=timeout_seconds,
        api_provider="cohere" if use_api else None,
    )
    specs = build_frontier_strategies(
        generator_factory=factory,
        budget=budget,
        adaptive_min_expand_grid=[1],
        rng=rng,
        use_openai_api=use_api,
        include_broad_diversity_aggregation_methods=True,
        include_external_l1_baseline=True,
    )
    diag = build_semantic_diversity_diagnostic_registry(factory, SimpleBranchScorer(ScoreConfig()), budget)
    merged = {**specs, **diag}
    return merged


def _extract_semantic_row(meta: dict[str, Any]) -> dict[str, Any]:
    d = meta.get("diagnostic_semantic_diversity") or {}
    if not d and "global_diversity_aggregation" in str(meta.get("method_family", "")):
        d = {k: v for k, v in meta.items() if k in {"semantic_family_count", "family_redundancy_ratio"}}
    return {
        "semantic_family_count": d.get("semantic_family_count", ""),
        "family_redundancy_ratio": d.get("family_redundancy_ratio", ""),
        "root_branch_count": d.get("root_branch_count", ""),
        "branching_necessity_score": d.get("branching_necessity_score", ""),
    }


def _loss_row_question_text(r: dict[str, Any]) -> str:
    return str(r.get("question") or r.get("problem_statement") or "").strip()


def _loss_row_gold_text(r: dict[str, Any]) -> str:
    return str(r.get("gold_answer") or r.get("gold_answer_canonical") or "").strip()


def _loss_row_has_question_and_gold(r: dict[str, Any]) -> bool:
    """Loss JSONL sometimes omits question/gold; skip those rows for live reruns."""
    q = _loss_row_question_text(r)
    g = _loss_row_gold_text(r)
    return len(q) >= 12 and len(g) >= 1


def _merge_loss_jsonl_files(paths: list[Path]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (unique rows by (file, line), per_line metadata for pool audit)."""
    rows: list[dict[str, Any]] = []
    meta: list[dict[str, Any]] = []
    for p in paths:
        if not p.exists():
            continue
        for i, r in enumerate(_read_jsonl(p)):
            rr = dict(r)
            rp = Path(p).resolve()
            try:
                rr.setdefault("source_file", str(rp.relative_to(REPO_ROOT.resolve())))
            except ValueError:
                rr.setdefault("source_file", str(p))
            rr.setdefault("source_line_index", i)
            rows.append(rr)
            meta.append({"source_file": rr.get("source_file"), "source_line_index": i})
    return rows, meta


def _row_external_is_any_correct(r: dict[str, Any]) -> bool:
    """external_exact_match==1 for row baseline (typically external_l1_max)."""
    return _safe_int(r, "external_exact_match", -1) == 1


def _expanded_eligible_row(r: dict[str, Any]) -> bool:
    """expanded-loss-pool: allowed internals lose vs external baseline row."""
    if not _loss_row_has_question_and_gold(r):
        return False
    im = str(r.get("internal_method_name") or "").strip()
    if im not in EXPANDED_INTERNAL_METHODS:
        return False
    if _safe_int(r, "internal_exact_match", -1) != 0:
        return False
    if _safe_int(r, "external_exact_match", -1) != 1:
        return False
    eb = str(r.get("external_baseline_name") or "").strip()
    valid_ext = {
        "external_l1_max",
        "s1",
        "tale",
        "external_s1_budget_forcing",
        "external_tale_prompt_budgeting",
    }
    return eb in valid_ext


def _internal_sort_rank(name: str) -> int:
    order = [
        "strict_f3",
        "strict_gate1_cap_k6",
        "strict_f3_anti_collapse_weak_v1",
        "direct_reserve_frontier_gate_v1",
    ]
    try:
        return order.index(str(name))
    except ValueError:
        return len(order)


def _absent_rank(status: str) -> int:
    s = str(status or "").strip()
    if s == "confirmed_absent_from_tree":
        return 0
    if s == "absent_from_tree_unverified":
        return 1
    return 2


def _dataset_matches_gsm8k_filter(row_dataset: str, *, gsm8k_only: bool) -> bool:
    if not gsm8k_only:
        return True
    ds = str(row_dataset or "").lower()
    return "gsm8k" in ds


def _select_live_cases_expanded_loss_pool(
    loss_rows: list[dict[str, Any]],
    *,
    max_cases: int,
    seed: int,
    allow_duplicate_example_fallback: bool,
    gsm8k_only: bool,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, Any],
]:
    """Broader internal methods + iw/ec + audits + duplicate fallback."""
    rng = random.Random(seed + 424242)

    candidates_inspected = len(loss_rows)
    rejected_empty = 0
    rejected_ineligible = 0
    rejected_dataset = 0
    pool_audit: list[dict[str, Any]] = []

    eligible: list[dict[str, Any]] = []
    for r in loss_rows:
        if not _dataset_matches_gsm8k_filter(str(r.get("dataset") or ""), gsm8k_only=gsm8k_only):
            pool_audit.append(
                {
                    "example_id": r.get("example_id"),
                    "seed": r.get("seed"),
                    "budget_source_row": r.get("budget"),
                    "internal_method_name": r.get("internal_method_name"),
                    "outcome": "rejected_dataset_filter",
                    "detail": "gsm8k_only_filter",
                    "stratum": "",
                    "selection_reason": "",
                }
            )
            rejected_dataset += 1
            continue
        if not _loss_row_has_question_and_gold(r):
            rejected_empty += 1
            pool_audit.append(
                {
                    "example_id": r.get("example_id"),
                    "seed": r.get("seed"),
                    "budget_source_row": r.get("budget"),
                    "internal_method_name": r.get("internal_method_name"),
                    "outcome": "rejected_empty_question_or_gold",
                    "detail": "",
                    "stratum": "",
                    "selection_reason": "",
                }
            )
            continue
        if not _expanded_eligible_row(r):
            rejected_ineligible += 1
            pool_audit.append(
                {
                    "example_id": r.get("example_id"),
                    "seed": r.get("seed"),
                    "budget_source_row": r.get("budget"),
                    "internal_method_name": r.get("internal_method_name"),
                    "outcome": "rejected_ineligible_loss_pattern",
                    "detail": "",
                    "stratum": "",
                    "selection_reason": "",
                }
            )
            continue
        eligible.append(r)

    def sort_key(rr: dict[str, Any]) -> tuple[int, int, int, float]:
        ar = _absent_rank(str(rr.get("absent_from_tree_status")))
        ir = _internal_sort_rank(str(rr.get("internal_method_name")))
        tie = rng.random()
        return (ar, ir, _safe_int(rr, "budget", 999), tie)

    eligible_sorted = sorted(eligible, key=sort_key)

    picked: list[dict[str, Any]] = []
    seen_example_ids: set[str] = set()
    seen_triples: set[tuple[str, str, str]] = set()

    # Phase 1: at most one row per example_id (best priority first via sort interleaved by problem_type)
    by_pt: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for rr in eligible_sorted:
        by_pt[str(rr.get("problem_type") or "unknown")].append(rr)
    for k in by_pt:
        by_pt[k] = sorted(by_pt[k], key=sort_key)
    pt_keys = sorted(by_pt.keys(), key=lambda k: k)
    rng.shuffle(pt_keys)

    def rr_take_unique(max_n: int) -> None:
        nonlocal picked
        idx_map = {k: 0 for k in pt_keys}
        while len(picked) < max_n:
            progressed = False
            for k in pt_keys:
                if len(picked) >= max_n:
                    break
                lst = by_pt[k]
                while idx_map[k] < len(lst):
                    cand_row = lst[idx_map[k]]
                    idx_map[k] += 1
                    eid = str(cand_row.get("example_id") or "").strip()
                    if not eid or eid in seen_example_ids:
                        continue
                    seen_example_ids.add(eid)
                    trip = (
                        eid,
                        str(cand_row.get("seed", "")),
                        str(cand_row.get("budget", "")),
                    )
                    seen_triples.add(trip)
                    cand_row = dict(cand_row)
                    cand_row["_selection_phase"] = "unique_example_id_round_robin_problem_type"
                    cand_row["_selection_reason"] = "first_unique_example_id_stratum_priority"
                    picked.append(cand_row)
                    progressed = True
                    break
                if len(picked) >= max_n:
                    break
            if not progressed:
                break

    rr_take_unique(max_cases)

    # Phase 2: allow duplicate example_id with distinct (seed,budget) triple
    if len(picked) < max_cases and allow_duplicate_example_fallback:
        for rr in eligible_sorted:
            if len(picked) >= max_cases:
                break
            trip = (
                str(rr.get("example_id") or ""),
                str(rr.get("seed", "")),
                str(rr.get("budget", "")),
            )
            if trip in seen_triples:
                continue
            if not str(trip[0]).strip():
                continue
            seen_triples.add(trip)
            c2 = dict(rr)
            c2["_selection_phase"] = "duplicate_example_id_distinct_seed_or_budget"
            c2["_selection_reason"] = "fallback_pool_not_enough_unique_ids"
            picked.append(c2)

    # Phase 3: cycle to max_cases (wrap) with explicit flag
    if len(picked) < max_cases and allow_duplicate_example_fallback and eligible_sorted:
        i = 0
        while len(picked) < max_cases:
            base = eligible_sorted[i % len(eligible_sorted)]
            i += 1
            c3 = dict(base)
            c3["_selection_phase"] = "cycled_pool_row"
            c3["_selection_reason"] = f"pool_exhausted_wrap_index={i-1}"
            picked.append(c3)

    for r in picked:
        pool_audit.append(
            {
                "example_id": r.get("example_id"),
                "seed": r.get("seed"),
                "budget_source_row": r.get("budget"),
                "internal_method_name": r.get("internal_method_name"),
                "outcome": "selected",
                "detail": str(r.get("_selection_phase", "")),
                "stratum": str(r.get("absent_from_tree_status", "")),
                "selection_reason": str(r.get("_selection_reason", "")),
            }
        )

    uids = {str(r.get("example_id")) for r in picked if str(r.get("example_id") or "").strip()}
    fb_dup = sum(
        1
        for r in picked
        if "duplicate" in str(r.get("_selection_phase", "")) or "cycled" in str(r.get("_selection_phase", ""))
    )
    exp = {
        "candidates_inspected": candidates_inspected,
        "rejected_empty_question_or_gold": rejected_empty,
        "rejected_dataset_filter": rejected_dataset,
        "rejected_ineligible_loss_pattern": rejected_ineligible,
        "eligible_after_filters": len(eligible),
        "unique_example_ids_in_eligible_pool": len({str(r.get("example_id")) for r in eligible if r.get("example_id")}),
        "selected_rows": len(picked),
        "unique_example_ids_selected": len(uids),
        "n_fallback_duplicate_or_cycle_rows": fb_dup,
        "max_cases_requested": max_cases,
        "dataset_filter_gsm8k_only": gsm8k_only,
        "strata_note": "prioritize absent-from-tree confirmed > unverified; internal priority strict_f3 > gate > anti-collapse > dr_gate",
    }

    return picked, pool_audit, exp


def _normalize_loss_row_for_example(r: dict[str, Any]) -> None:
    """Ensure `question` is populated for downstream."""
    if not str(r.get("question") or "").strip() and str(r.get("problem_statement") or "").strip():
        r["question"] = str(r.get("problem_statement")).strip()


def _select_live_cases(
    loss_rows: list[dict[str, Any]],
    max_cases: int,
    seed: int,
) -> list[dict[str, Any]]:
    """Prefer internal-wrong external-correct, confirmed absent-from-tree."""
    rng = random.Random(seed)
    pool = [
        r
        for r in loss_rows
        if str(r.get("internal_method_name", "")) == "strict_f3" and _loss_row_has_question_and_gold(r)
    ]
    scored: list[tuple[tuple[int, int, int], dict[str, Any]]] = []
    for r in pool:
        strict_ok = str(r.get("strict_f3_is_correct", r.get("internal_is_correct", ""))).lower() in {"1", "true", "yes"}
        ext_ok = str(r.get("external_l1_max_is_correct", r.get("external_is_correct", ""))).lower() in {
            "1",
            "true",
            "yes",
        }
        conf = 0 if str(r.get("absent_from_tree_status", "")) == "confirmed_absent_from_tree" else 1
        miss = 0 if "wrong" in str(r.get("strict_f3_is_correct", "")).lower() and ext_ok else 1
        pri = (miss, conf, 0)
        scored.append((pri, r))
    scored.sort(key=lambda x: (x[0], rng.random()))
    out = [r for _, r in scored[: max_cases * 3]]
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for r in out:
        eid = str(r.get("example_id", ""))
        if not eid or eid in seen:
            continue
        seen.add(eid)
        unique.append(r)
        if len(unique) >= max_cases:
            break
    return unique


def _examples_for_offline(n: int, seed: int) -> list[PilotExample]:
    return load_pilot_examples("openai/gsm8k", subset_size=n, seed=seed)


def _example_from_loss_row(r: dict[str, Any]) -> PilotExample:
    _normalize_loss_row_for_example(r)
    ga = str(r.get("gold_answer") or r.get("gold_answer_canonical") or r.get("answer") or "").strip() or "0"
    return PilotExample(
        example_id=str(r.get("example_id", "unknown")),
        question=_loss_row_question_text(r),
        answer=extract_final_answer(ga),
    )


def run_offline(
    out_dir: Path, *, max_examples: int, seed: int, budgets: list[int], methods: list[str] | None = None
) -> None:
    mlist = methods or list(METHODS_COMPARE)
    missing = out_dir / "missing_data_report.md"
    ex = _examples_for_offline(max_examples, seed)
    if not ex:
        missing.write_text(
            "# Missing data (offline)\n\nCould not load HF pilot examples. "
            "Check network and `openai/gsm8k` availability, or re-run in an environment with dataset access.\n",
            encoding="utf-8",
        )
        return
    if len(ex) < 4:
        missing.write_text(
            "# Missing data (offline)\n\nToo few examples for a meaningful multi-method comparison. "
            "Increase subset or check dataset access.\n",
            encoding="utf-8",
        )

    per_case: list[dict[str, Any]] = []
    for b in budgets:
        specs = _build_specs_for_budget(
            use_api=False,
            model="command-r-plus-08-2024",
            budget=b,
            selection_seed=seed,
            temperature=0.2,
            max_output_tokens=512,
            timeout_seconds=60,
        )
        for ex0 in ex:
            for m in mlist:
                key = _method_runtime_key(m)
                ctrl = specs.get(key)
                if ctrl is None:
                    per_case.append(
                        {
                            "mode": "offline",
                            "example_id": ex0.example_id,
                            "budget": b,
                            "method": m,
                            "error": "method_not_in_specs",
                        }
                    )
                    continue
                try:
                    res = ctrl.run(ex0.question, ex0.answer)
                    meta = res.metadata or {}
                    ds = _extract_semantic_row(meta)
                    ddiv = meta.get("diagnostic_semantic_diversity") or {}
                    per_case.append(
                        {
                            "mode": "offline",
                            "example_id": ex0.example_id,
                            "budget": b,
                            "method": m,
                            "is_correct": int(bool(res.is_correct)),
                            "prediction": str(res.prediction or ""),
                            "actions_used": res.actions_used,
                            "expansions": res.expansions,
                            "verifications": res.verifications,
                            "budget_exhausted": int(res.budget_exhausted),
                            "immediate_miss": int(
                                not bool(meta.get("gold_group_present_after_first_split", True)) and not bool(res.is_correct)
                            ),
                            "maturation_phase_len": len(ddiv.get("maturation_phase_audit", []) or []),
                            "commit_reason": str(meta.get("regime_failure_category", meta.get("early_divergence_failure_category", ""))),
                            "incumbent_replaced": meta.get("incumbent_replaced", ""),
                            "replacement_reason": str(meta.get("incumbent_replacement_reason", "")),
                            **ds,
                        }
                    )
                except Exception as e:  # noqa: BLE001
                    per_case.append(
                        {
                            "mode": "offline",
                            "example_id": ex0.example_id,
                            "budget": b,
                            "method": m,
                            "error": str(e)[:500],
                        }
                    )
    _write_csv(out_dir / "per_case_results.csv", per_case)
    _write_summaries(out_dir, per_case, mode="offline")


def _write_summaries(out_dir: Path, per_case: list[dict[str, Any]], *, mode: str) -> None:
    by_method: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in per_case:
        if r.get("error"):
            continue
        by_method[str(r.get("method", ""))].append(r)
    acc_rows = []
    for m, rows in by_method.items():
        n = max(1, len(rows))
        acc_rows.append(
            {
                "method": m,
                "n": len(rows),
                "accuracy": sum(int(x.get("is_correct", 0) or 0) for x in rows) / n,
                "avg_actions": sum(float(x.get("actions_used", 0) or 0) for x in rows) / n,
            }
        )
    _write_csv(out_dir / "method_accuracy_summary.csv", acc_rows)

    def _paired_lookup(rows: list[dict[str, Any]], r: dict[str, Any]) -> dict[str, Any] | None:
        eid, b = r.get("example_id"), r.get("budget")
        cs = r.get("cohort_slot")
        for x in rows:
            if str(x.get("budget") or "") != str(b or ""):
                continue
            if str(cs or "") not in {"", "None"}:
                if str(x.get("cohort_slot") or "") == str(cs or ""):
                    return x
            else:
                if str(x.get("example_id") or "") == str(eid or ""):
                    return x
        return None

    paired = []
    for r in per_case:
        if r.get("error"):
            continue
        eid, b = r.get("example_id"), r.get("budget")
        sf = _paired_lookup(by_method.get("strict_f3", []), r)
        exl1 = _paired_lookup(by_method.get("external_l1_max", []), r)
        if sf and r.get("method") not in {"strict_f3", "external_l1_max"}:
            paired.append(
                {
                    "example_id": eid,
                    "budget": b,
                    "method": r.get("method"),
                    "delta_vs_strict_f3": int(r.get("is_correct", 0)) - int(sf.get("is_correct", 0)),
                    "delta_vs_external_l1_max": int(r.get("is_correct", 0)) - int(exl1.get("is_correct", 0)) if exl1 else "",
                }
            )
    _write_csv(out_dir / "paired_summary.csv", paired)

    # Semantic / audits (simplified)
    sem = [
        {**_extract_semantic_row({"diagnostic_semantic_diversity": r}), "method": r.get("method"), "example_id": r.get("example_id")}
        for r in per_case
        if not r.get("error")
    ]
    _write_csv(out_dir / "semantic_family_summary.csv", sem)
    _write_csv(
        out_dir / "maturation_phase_audit.csv",
        [
            {
                "example_id": r.get("example_id"),
                "budget": r.get("budget"),
                "method": r.get("method"),
                "maturation_phase_audit_len": r.get("maturation_phase_audit_len", r.get("maturation_phase_len", "")),
                "maturation_phase_audit_json": str(r.get("maturation_phase_audit_json", ""))[:4000],
            }
            for r in per_case
            if not r.get("error")
        ],
    )
    _write_csv(
        out_dir / "branching_necessity_audit.csv",
        [
            {
                "example_id": r.get("example_id"),
                "budget": r.get("budget"),
                "method": r.get("method"),
                "branching_necessity_score": r.get("branching_necessity_score", r.get("branching_necessity_last", "")),
                "branching_necessity_decision": r.get("branching_necessity_decision_last", ""),
            }
            for r in per_case
            if not r.get("error")
        ],
    )
    _write_csv(
        out_dir / "incumbent_replacement_audit.csv",
        [
            {
                "example_id": r.get("example_id"),
                "budget": r.get("budget"),
                "method": r.get("method"),
                "incumbent_replaced": r.get("incumbent_replaced", ""),
                "replacement_reason": r.get("replacement_reason", ""),
            }
            for r in per_case
            if not r.get("error")
        ],
    )


def run_cohere_live(
    out_dir: Path,
    *,
    max_cases: int,
    allow_large: bool,
    model: str,
    budgets: list[int],
    loss_jsonl: Path,
    extra_loss_jsonl: list[Path],
    seed: int,
    methods: list[str],
    selection_profile: str,
    emit_full_traces: bool,
    dataset_name: str,
    run_timestamp: str,
    allow_duplicate_example_fallback: bool,
    loss_pool_gsm8k_only: bool,
) -> tuple[bool, str]:
    if max_cases > 30 and not allow_large:
        return False, "refuse: max-cases>30 without --allow-large-run"
    rmod = _load_readiness()
    ok, fclass, _sm = rmod.run_readiness_check(model=model, smoke_timeout_seconds=45)
    if not ok:
        rmod.write_issue_report(
            out_dir=out_dir,
            timestamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
            model=model,
            key_present=bool(os.getenv("COHERE_API_KEY")),
            failure_class=fclass,
            error_message=str(_sm.get("error", "")),
            rerun_command="python scripts/run_semantic_diversity_controller_diagnostic.py --mode cohere --run-live-cohere",
        )
        return False, f"readiness:{fclass}"

    if selection_profile == "expanded-loss-pool":
        paths_merged = [loss_jsonl] + list(extra_loss_jsonl)
        rows, _ = _merge_loss_jsonl_files(paths_merged)
        picked, pool_audit_rows, exp_summary = _select_live_cases_expanded_loss_pool(
            rows,
            max_cases=max_cases,
            seed=seed,
            allow_duplicate_example_fallback=allow_duplicate_example_fallback,
            gsm8k_only=loss_pool_gsm8k_only,
        )
        _write_csv(
            out_dir / "selected_case_pool_audit.csv",
            pool_audit_rows,
            fieldnames=[
                "example_id",
                "seed",
                "budget_source_row",
                "internal_method_name",
                "outcome",
                "detail",
                "stratum",
                "selection_reason",
            ],
        )
        _write_csv(out_dir / "case_pool_expansion_audit.csv", [exp_summary])
    else:
        rows = _read_jsonl(loss_jsonl)
        if selection_profile == "loss-full":
            picked = _select_live_cases_loss_full(rows, max_cases, seed)
        else:
            picked = _select_live_cases(rows, max_cases, seed)
        _write_csv(out_dir / "selected_case_pool_audit.csv", [])
        _write_csv(
            out_dir / "case_pool_expansion_audit.csv",
            [{"note": f"selection_profile={selection_profile}", "loss_jsonl": str(loss_jsonl)}],
        )

    for pr in picked:
        _normalize_loss_row_for_example(pr)
    ex_list = [_example_from_loss_row(r) for r in picked]
    _write_jsonl(out_dir / "selected_cases.jsonl", picked)

    per_case: list[dict[str, Any]] = []
    run_exc: str | None = None
    try:
        for case_index, (picked_row, ex0) in enumerate(zip(picked, ex_list, strict=True)):
            row_seed = int(seed)
            try:
                row_seed = int(float(str(picked_row.get("seed", seed))))
            except (TypeError, ValueError):
                row_seed = int(seed)
            for b in budgets:
                specs = _build_specs_for_budget(
                    use_api=True,
                    model=model,
                    budget=b,
                    selection_seed=row_seed * 1009 + b * 13,
                    temperature=0.2,
                    max_output_tokens=768,
                    timeout_seconds=90,
                )
                for m in methods:
                    key = _method_runtime_key(m)
                    ctrl = specs.get(key)
                    if ctrl is None:
                        per_case.append(
                            {
                                "mode": "cohere",
                                "example_id": ex0.example_id,
                                "budget": b,
                                "method": m,
                                "error": "method_not_in_specs",
                            }
                        )
                        continue
                    setattr(ctrl, "emit_full_traces", bool(emit_full_traces))
                    res = ctrl.run(ex0.question, ex0.answer)
                    meta = dict(res.metadata or {})
                    trace_rel = ""
                    if emit_full_traces:
                        trace_rel = _write_full_trace_json(
                            out_dir,
                            example_id=ex0.example_id,
                            budget=b,
                            method=m,
                            meta=meta,
                        )
                    row = _cohere_build_row(
                        picked_row=picked_row,
                        ex0=ex0,
                        budget=b,
                        method=m,
                        model=model,
                        dataset=dataset_name,
                        res=res,
                        meta=meta,
                        emit_full_traces=emit_full_traces,
                        trace_rel=trace_rel,
                        cohort_slot=case_index,
                    )
                    row["branching_necessity_score"] = row.get("branching_necessity_last", "")
                    row["maturation_phase_len"] = row.get("maturation_phase_audit_len", "")
                    per_case.append(row)
    except Exception as e:  # noqa: BLE001
        run_exc = traceback.format_exc()
        (out_dir / "run_failure_issue.md").write_text(
            f"# Run failure (post-readiness)\n\n```text\n{run_exc[:8000]}\n```\n", encoding="utf-8"
        )
        return False, "post_readiness_failure"

    _write_csv(out_dir / "per_case_results.csv", per_case)
    _write_summaries(out_dir, per_case, mode="cohere")
    tax = Counter(str(r.get("failure_taxonomy") or "unknown") for r in per_case if not r.get("error"))
    _write_csv(out_dir / "failure_taxonomy.csv", [{"category": k, "count": v} for k, v in sorted(tax.items())])
    resc: list[dict[str, Any]] = []
    for r in per_case:
        if r.get("error"):
            continue
        prior = str(r.get("selection_absent_from_tree_status") or "")
        rescue = int(
            prior == "confirmed_absent_from_tree"
            and int(r.get("absent_from_tree_meta") or 1) == 0
            and int(r.get("is_correct") or 0) == 1
        )
        resc.append(
            {
                "example_id": r.get("example_id"),
                "budget": r.get("budget"),
                "method": r.get("method"),
                "confirmed_absent_prior": prior,
                "absent_from_tree_now": r.get("absent_from_tree_meta"),
                "is_correct": r.get("is_correct"),
                "absent_from_tree_rescue": rescue,
            }
        )
    _write_csv(out_dir / "absent_from_tree_rescue_audit.csv", resc)
    tok_rows = []
    for r in per_case:
        if r.get("error"):
            continue
        tok_rows.append(
            {
                "example_id": r.get("example_id"),
                "budget": r.get("budget"),
                "method": r.get("method"),
                "estimated_input_tokens": r.get("estimated_input_tokens", ""),
                "estimated_output_tokens": r.get("estimated_output_tokens", ""),
                "estimated_latency_seconds": r.get("estimated_latency_seconds", ""),
                "estimated_cost_usd_proxy": r.get("estimated_cost_usd_proxy", ""),
                "actions_used": r.get("actions_used", ""),
            }
        )
    _write_csv(out_dir / "token_cost_latency_summary.csv", tok_rows)

    nxt = out_dir / "candidate_next_steps.md"
    nxt.write_text(
        "# Candidate next steps\n\n"
        "- **Diagnostic only** — not manuscript-grade evidence.\n"
        "- Review `failure_taxonomy.csv`, `full_traces/`, and `paired_summary.csv` before scaling.\n"
        "- Runs beyond `--max-cases 30` require explicit approval.\n",
        encoding="utf-8",
    )
    u_eid = len({str(p.get("example_id", "")).strip() for p in picked if str(p.get("example_id", "")).strip()})
    exp_rows = _read_csv_rows(out_dir / "case_pool_expansion_audit.csv")
    exp0: dict[str, Any] = exp_rows[0] if exp_rows else {}
    man: dict[str, Any] = {
        "diagnostic": True,
        "selection_profile": selection_profile,
        "emit_full_traces": bool(emit_full_traces),
        "methods": methods,
        "experimental_methods": [x for x in methods if x not in ("strict_f3", "external_l1_max")],
        "readiness": "passed",
        "n_selected_cases": len(picked),
        "n_unique_example_ids": u_eid,
        "budgets": budgets,
        "run_timestamp": run_timestamp,
    }
    for k, v in exp0.items():
        if k and not k.startswith("note"):
            man[f"case_pool_{k}"] = v
    (out_dir / "manifest.json").write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")

    try:
        ac = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "analyze_semantic_diversity_diagnostic_run.py"),
                "--timestamp",
                run_timestamp,
            ],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        if ac.returncode != 0:
            (out_dir / "postprocess_analyzer_note.md").write_text(
                f"# Postprocess analyzer (non-fatal)\n\nexit={ac.returncode}\n\n{ac.stderr[:4000]}\n",
                encoding="utf-8",
            )
    except Exception as e:  # noqa: BLE001
        (out_dir / "postprocess_analyzer_note.md").write_text(
            f"# Postprocess analyzer skipped\n\n{str(e)[:2000]}\n", encoding="utf-8"
        )
    return True, "ok"


def _read_csv_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        rdr = csv.DictReader(f)
        for row in rdr:
            rows.append(dict(row))
    return rows


def _diagnostic_report_body(out_dir: Path, ts: str) -> str:
    manifest: dict[str, Any] = {}
    mp = out_dir / "manifest.json"
    if mp.exists():
        try:
            manifest = json.loads(mp.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            manifest = {}

    per_case = _read_csv_rows(out_dir / "per_case_results.csv")
    acc = _read_csv_rows(out_dir / "method_accuracy_summary.csv")
    paired = _read_csv_rows(out_dir / "paired_summary.csv")
    tax = _read_csv_rows(out_dir / "failure_taxonomy.csv")
    tok = _read_csv_rows(out_dir / "token_cost_latency_summary.csv")

    n_cases = int(manifest.get("n_selected_cases") or 0)
    if not n_cases and per_case:
        n_cases = len({str(r.get("example_id")) for r in per_case if not r.get("error")})

    best_m, best_acc = "", -1.0
    for r in acc:
        try:
            a = float(r.get("accuracy") or 0)
        except (TypeError, ValueError):
            a = 0.0
        if a > best_acc:
            best_acc = a
            best_m = str(r.get("method") or "")

    avg_actions_by_m: dict[str, list[float]] = defaultdict(list)
    for r in per_case:
        if r.get("error"):
            continue
        try:
            avg_actions_by_m[str(r.get("method"))].append(float(r.get("actions_used") or 0))
        except (TypeError, ValueError):
            pass
    action_penalty = {
        m: sum(v) / max(1, len(v)) for m, v in avg_actions_by_m.items()
    }

    deltas_sf = [
        int(r.get("delta_vs_strict_f3") or 0)
        for r in paired
        if str(r.get("delta_vs_strict_f3") or "").strip() != ""
    ]
    beats_strict = sum(1 for x in deltas_sf if x > 0)
    any_beat_strict = beats_strict > 0

    deltas_ex = []
    for r in paired:
        dx = r.get("delta_vs_external_l1_max")
        if dx is None or str(dx).strip() == "":
            continue
        try:
            deltas_ex.append(int(dx))
        except (TypeError, ValueError):
            pass
    beats_ext = sum(1 for x in deltas_ex if x > 0)
    approaches_ext = sum(1 for x in deltas_ex if x >= 0)

    dom_tax = ""
    dom_n = -1
    for r in tax:
        try:
            c = int(float(str(r.get("count") or 0)))
        except (TypeError, ValueError):
            c = 0
        if c > dom_n:
            dom_n = c
            dom_tax = str(r.get("category") or "")

    rescue_rows = _read_csv_rows(out_dir / "absent_from_tree_rescue_audit.csv")
    rescue_hits = sum(
        1
        for r in rescue_rows
        if str(r.get("absent_from_tree_rescue") or "") in {"1", "true", "True"}
    )

    lines = [
        f"# Semantic diversity controller diagnostic ({ts})",
        "",
        "## Status",
        "",
        "Experimental / diagnostic only — **not** manuscript-grade evidence unless replicated and reviewed.",
        "",
        "## Case volume",
        "",
        f"- **Loss / selected cases evaluated (unique example_ids in manifest):** {n_cases or '(see per_case_results.csv)'}",
        f"- **Per-method rows in per_case_results.csv:** {len([r for r in per_case if not r.get('error')])}",
        "",
        "## Headline comparisons",
        "",
        f"- **Best accuracy (method_accuracy_summary.csv):** `{best_m}` at {best_acc:.4f}" if acc else "- **Accuracy summary:** (missing method_accuracy_summary.csv)",
        "",
        "### vs strict_f3",
        "",
        f"- **Paired rows with delta > 0 vs strict_f3:** {beats_strict} (non-experimental methods excluded from paired_summary)",
        f"- **Any experimental method beat strict_f3 on at least one paired row:** {'yes' if any_beat_strict else 'no'}",
        "",
        "### vs external_l1_max",
        "",
        f"- **Paired deltas ≥ 0 vs external_l1_max:** {approaches_ext} rows with numeric delta",
        f"- **Paired deltas > 0 vs external_l1_max:** {beats_ext}",
        "",
        "### Direct reserve / semantic maturation (directional)",
        "",
        "- **Did direct reserve help?** Compare `direct_reserve_semantic_frontier_v1` vs `strict_f3` in `paired_summary.csv` and `method_accuracy_summary.csv`.",
        "- **Did semantic minimum maturation help?** Compare `semantic_minimum_maturation_frontier_v1_d3` vs `strict_f3`.",
        "- **Did combined semantic maturation + direct reserve help?** Compare `semantic_minimum_maturation_plus_direct_reserve_v1` vs baselines.",
        "",
        "### Cost / action penalty",
        "",
        "Mean actions_used by method (from per_case_results, diagnostic only):",
        "",
        *(f"- `{m}`: {v:.2f}" for m, v in sorted(action_penalty.items())),
        "",
        "### Absent-from-tree / rescue",
        "",
        f"- **absent_from_tree_rescue_audit rows flagged as rescue:** {rescue_hits}",
        "- Review `failure_taxonomy.csv` and `absent_from_tree_rescue_audit.csv` for bad seeding vs selection vs trace gaps.",
        "",
        "### Failure taxonomy (post hoc)",
        "",
        f"- **Dominant category:** `{dom_tax}` (count {dom_n})" if dom_tax else "- **Dominant category:** (empty failure_taxonomy.csv)",
        "",
        "### Token / latency / cost proxy",
        "",
        f"- **Rows in token_cost_latency_summary.csv:** {len(tok)}",
        "",
        "## Artifacts",
        "",
        f"- Output directory: `{out_dir.relative_to(REPO_ROOT)}`",
        "- Key files: `selected_cases.jsonl`, `per_case_results.csv`, `paired_summary.csv`, `method_accuracy_summary.csv`, "
        "`token_cost_latency_summary.csv`, `semantic_family_summary.csv`, `*_audit.csv`, `failure_taxonomy.csv`, "
        "`full_traces/` (if emitted), `manifest.json`, `candidate_next_steps.md`.",
        "",
        "## Scale-up judgment",
        "",
        "- **Larger run justified?** Only if paired deltas and taxonomy show a consistent, interpretable pattern; "
        "runs beyond 30 cases require explicit approval.",
        "- **Manuscript change warranted?** Default **no** unless evidence is strong and reproducible.",
        "",
    ]
    return "\n".join(lines) + "\n"


def write_report_doc(out_dir: Path, ts: str) -> None:
    doc = REPO_ROOT / f"docs/SEMANTIC_DIVERSITY_CONTROLLER_DIAGNOSTIC_{ts}.md"
    doc.write_text(_diagnostic_report_body(out_dir, ts), encoding="utf-8")


def run_dry_selection(
    out_dir: Path,
    *,
    max_cases: int,
    seed: int,
    selection_profile: str,
    loss_jsonl: Path,
    extra_loss_jsonl: list[Path],
    allow_duplicate_example_fallback: bool,
    loss_pool_gsm8k_only: bool,
    methods: list[str],
    budgets: list[int],
    run_timestamp: str,
) -> tuple[int, dict[str, Any]]:
    """Selection only; no Cohere / no readiness. Writes pool audits + selected_cases + stub manifest."""
    out_dir.mkdir(parents=True, exist_ok=True)
    if selection_profile != "expanded-loss-pool":
        (out_dir / "dry_run_note.md").write_text(
            "Dry-run selection with full audits is implemented for `--selection-profile expanded-loss-pool` only.\n",
            encoding="utf-8",
        )
        return 2, {"error": "unsupported_profile_for_dry_selection"}

    paths_merged = [loss_jsonl] + list(extra_loss_jsonl)
    rows, _ = _merge_loss_jsonl_files(paths_merged)
    picked, pool_audit_rows, exp_summary = _select_live_cases_expanded_loss_pool(
        rows,
        max_cases=max_cases,
        seed=seed,
        allow_duplicate_example_fallback=allow_duplicate_example_fallback,
        gsm8k_only=loss_pool_gsm8k_only,
    )
    for pr in picked:
        _normalize_loss_row_for_example(pr)
    _write_csv(
        out_dir / "selected_case_pool_audit.csv",
        pool_audit_rows,
        fieldnames=[
            "example_id",
            "seed",
            "budget_source_row",
            "internal_method_name",
            "outcome",
            "detail",
            "stratum",
            "selection_reason",
        ],
    )
    _write_csv(out_dir / "case_pool_expansion_audit.csv", [exp_summary])
    _write_jsonl(out_dir / "selected_cases.jsonl", picked)
    u_eid = len({str(p.get("example_id", "")).strip() for p in picked if str(p.get("example_id", "")).strip()})
    (out_dir / "manifest.json").write_text(
        json.dumps(
            {
                "dry_run_selection": True,
                "selection_profile": selection_profile,
                "methods": methods,
                "budgets": budgets,
                "n_selected_cases": len(picked),
                "n_unique_example_ids": u_eid,
                "run_timestamp": run_timestamp,
                **{f"case_pool_{k}": v for k, v in exp_summary.items()},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"dry_selection_summary": exp_summary, "n_picked": len(picked)}, indent=2))
    if len(picked) < 20:
        return 3, exp_summary
    return 0, exp_summary


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    p.add_argument("--mode", choices=["offline", "cohere"], default="offline")
    p.add_argument("--run-live-cohere", action="store_true", help="Required for real API in cohere mode.")
    p.add_argument("--max-cases", type=int, default=10)
    p.add_argument("--allow-large-run", action="store_true")
    p.add_argument("--selection-seed", type=int, default=31)
    p.add_argument("--model", default="command-r-plus-08-2024")
    p.add_argument("--budgets", default="4,6,8")
    p.add_argument("--loss-jsonl", default=str(DEFAULT_LOSS_JSONL))
    p.add_argument("--offline-examples", type=int, default=8)
    p.add_argument(
        "--selection-profile",
        choices=["standard", "loss-full", "expanded-loss-pool"],
        default="standard",
        help=(
            "loss-full: strict_f3-centric absent-from-tree cohort. "
            "expanded-loss-pool: merge extra loss JSONL, more internal methods, audit files, optional duplicate-ID fallback."
        ),
    )
    p.add_argument(
        "--methods",
        default="",
        help="Comma-separated methods; empty uses METHODS_COMPARE or METHODS_LOSS_FULL per selection-profile.",
    )
    p.add_argument(
        "--emit-full-traces",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Write per-run JSON under full_traces/ (default: true).",
    )
    p.add_argument(
        "--dataset-name",
        default="openai/gsm8k",
        help="Dataset label for result rows. Comma-separated is not supported for live expanded-pool runs (GSM8K-only).",
    )
    p.add_argument(
        "--extra-loss-jsonl",
        action="append",
        default=None,
        help="Additional loss JSONL files merged for expanded-loss-pool (repeatable).",
    )
    p.add_argument(
        "--allow-duplicate-example-fallback",
        action="store_true",
        help="If unique example_id count is low, allow second pass (distinct seed/budget) and cycling to fill max-cases.",
    )
    p.add_argument(
        "--loss-pool-gsm8k-only",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="For expanded-loss-pool: keep only rows whose dataset field mentions gsm8k (default: true).",
    )
    p.add_argument(
        "--dry-run-selection",
        action="store_true",
        help="cohere mode: only run case selection + pool audits; no API / no readiness check.",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    ts = str(args.timestamp)
    base_ts = ts.replace("_DRY", "")
    extra_loss: list[Path] = [Path(p) for p in (args.extra_loss_jsonl or [])]
    out = REPO_ROOT / f"outputs/semantic_diversity_controller_diagnostic_{ts}"
    out.mkdir(parents=True, exist_ok=True)
    budgets = [int(x) for x in str(args.budgets).split(",") if x.strip()]

    if (
        args.mode == "cohere"
        and "," in str(args.dataset_name)
        and args.selection_profile == "expanded-loss-pool"
        and args.run_live_cohere
        and not args.dry_run_selection
    ):
        doc = REPO_ROOT / f"docs/SEMANTIC_DIVERSITY_EXPANDED_POOL_MULTIDATASET_UNSUPPORTED_{base_ts}.md"
        doc.write_text(
            "# Multi-dataset live run not enabled\n\n"
            "Comma-separated `--dataset-name` is not supported for safe live scoring with expanded-loss-pool in this runner. "
            "Keep `--dataset-name openai/gsm8k` and widen the loss JSONL inputs instead.\n",
            encoding="utf-8",
        )
        return 2

    if args.mode == "offline":
        run_offline(out, max_examples=int(args.offline_examples), seed=int(args.selection_seed), budgets=budgets)
        (out / "missing_data_report.md").write_text(
            "# Offline data availability\n\n"
            "Offline mode uses the **local simulator** and freshly sampled GSM8K examples; it does not replay historical "
            "Cohere logs. Comparing new variants against archived Cohere runs requires a **live** `--mode cohere` re-run on "
            "the same `example_id` set (see `selected_cases.jsonl` in live mode).\n",
            encoding="utf-8",
        )
        _write_csv(out / "token_cost_latency_summary.csv", [{"mode": "offline", "note": "Simulated: no real API tokens"}])
        (out / "manifest.json").write_text(
            json.dumps({"mode": "offline", "diagnostic": True, "budgets": budgets}, indent=2) + "\n", encoding="utf-8"
        )
        (out / "selected_cases.jsonl").write_text("", encoding="utf-8")
        write_report_doc(out, ts)
        print(f"offline_ok out_dir={out}")
        return 0

    mlist = resolved_methods(str(args.methods), selection_profile=str(args.selection_profile))

    if args.mode == "cohere" and args.dry_run_selection:
        code, summ = run_dry_selection(
            out,
            max_cases=int(args.max_cases),
            seed=int(args.selection_seed),
            selection_profile=str(args.selection_profile),
            loss_jsonl=Path(str(args.loss_jsonl)),
            extra_loss_jsonl=extra_loss,
            allow_duplicate_example_fallback=bool(args.allow_duplicate_example_fallback),
            loss_pool_gsm8k_only=bool(args.loss_pool_gsm8k_only),
            methods=mlist,
            budgets=budgets,
            run_timestamp=base_ts,
        )
        if code == 3:
            ins = REPO_ROOT / f"docs/SEMANTIC_DIVERSITY_EXPANDED_POOL_SELECTION_INSUFFICIENT_{base_ts}.md"
            ins.write_text(
                f"# Expanded pool dry selection insufficient (<20 rows)\n\n"
                f"- Timestamp token: `{base_ts}`\n"
                f"- Selection summary: `{summ}`\n\n"
                "**Remediation:** regenerate `loss_cases_absent_from_tree.jsonl` via "
                "`scripts/build_cohere_absent_from_tree_loss_diagnostics.py` after broader validation CSV coverage, "
                "or add `--extra-loss-jsonl` paths with compatible rows.\n",
                encoding="utf-8",
            )
            print(f"dry_selection_insufficient doc={ins}")
        print(f"dry_selection_exit_code={code} out_dir={out}")
        return int(code)

    if args.mode == "cohere" and not args.run_live_cohere:
        (out / "cohere_api_key_issue.md").write_text(
            "# Cohere not run\n\nPass `--run-live-cohere` for API execution or `--dry-run-selection` for pool selection only.\n",
            encoding="utf-8",
        )
        return 1

    ok, msg = run_cohere_live(
        out,
        max_cases=int(args.max_cases),
        allow_large=bool(args.allow_large_run),
        model=str(args.model),
        budgets=budgets,
        loss_jsonl=Path(str(args.loss_jsonl)),
        extra_loss_jsonl=extra_loss,
        seed=int(args.selection_seed),
        methods=mlist,
        selection_profile=str(args.selection_profile),
        emit_full_traces=bool(args.emit_full_traces),
        dataset_name=str(args.dataset_name),
        run_timestamp=base_ts,
        allow_duplicate_example_fallback=bool(args.allow_duplicate_example_fallback),
        loss_pool_gsm8k_only=bool(args.loss_pool_gsm8k_only),
    )
    write_report_doc(out, ts)
    print(f"cohere_mode ok={ok} msg={msg} out_dir={out}")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
