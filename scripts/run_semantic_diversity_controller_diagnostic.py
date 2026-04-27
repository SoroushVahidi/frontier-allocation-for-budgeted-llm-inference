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


def _loss_row_has_question_and_gold(r: dict[str, Any]) -> bool:
    """Loss JSONL sometimes omits question/gold; skip those rows for live reruns."""
    q = str(r.get("question") or "").strip()
    g = str(r.get("gold_answer") or r.get("gold_answer_canonical") or "").strip()
    return len(q) >= 12 and len(g) >= 1


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
    ga = str(r.get("gold_answer") or r.get("gold_answer_canonical") or r.get("answer") or "").strip() or "0"
    return PilotExample(
        example_id=str(r.get("example_id", "unknown")),
        question=str(r.get("question") or "").strip(),
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

    paired = []
    for r in per_case:
        if r.get("error"):
            continue
        eid, b = r.get("example_id"), r.get("budget")
        sf = next((x for x in by_method.get("strict_f3", []) if x.get("example_id") == eid and x.get("budget") == b), None)
        exl1 = next(
            (x for x in by_method.get("external_l1_max", []) if x.get("example_id") == eid and x.get("budget") == b), None
        )
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
    seed: int,
    methods: list[str],
    selection_profile: str,
    emit_full_traces: bool,
    dataset_name: str,
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

    rows = _read_jsonl(loss_jsonl)
    if selection_profile == "loss-full":
        picked = _select_live_cases_loss_full(rows, max_cases, seed)
    else:
        picked = _select_live_cases(rows, max_cases, seed)
    ex_list = [_example_from_loss_row(r) for r in picked]
    _write_jsonl(out_dir / "selected_cases.jsonl", picked)

    per_case: list[dict[str, Any]] = []
    run_exc: str | None = None
    try:
        for b in budgets:
            specs = _build_specs_for_budget(
                use_api=True,
                model=model,
                budget=b,
                selection_seed=seed,
                temperature=0.2,
                max_output_tokens=768,
                timeout_seconds=90,
            )
            for ex0, picked_row in zip(ex_list, picked, strict=True):
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
    (out_dir / "manifest.json").write_text(
        json.dumps(
            {
                "diagnostic": True,
                "selection_profile": selection_profile,
                "emit_full_traces": bool(emit_full_traces),
                "methods": methods,
                "experimental_methods": [x for x in methods if x not in ("strict_f3", "external_l1_max")],
                "readiness": "passed",
                "n_selected_cases": len(picked),
                "budgets": budgets,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
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
        choices=["standard", "loss-full"],
        default="standard",
        help="loss-full: prioritize strict_f3-wrong/external-correct + absent-from-tree (trace-complete cohort).",
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
        help="Dataset label recorded in CSV rows / manifest.",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    ts = str(args.timestamp)
    out = REPO_ROOT / f"outputs/semantic_diversity_controller_diagnostic_{ts}"
    out.mkdir(parents=True, exist_ok=True)
    budgets = [int(x) for x in str(args.budgets).split(",") if x.strip()]

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

    if args.mode == "cohere" and not args.run_live_cohere:
        (out / "cohere_api_key_issue.md").write_text(
            "# Cohere not run\n\nPass `--run-live-cohere` to enable live Cohere execution.\n", encoding="utf-8"
        )
        return 1

    mlist = resolved_methods(str(args.methods), selection_profile=str(args.selection_profile))
    ok, msg = run_cohere_live(
        out,
        max_cases=int(args.max_cases),
        allow_large=bool(args.allow_large_run),
        model=str(args.model),
        budgets=budgets,
        loss_jsonl=Path(str(args.loss_jsonl)),
        seed=int(args.selection_seed),
        methods=mlist,
        selection_profile=str(args.selection_profile),
        emit_full_traces=bool(args.emit_full_traces),
        dataset_name=str(args.dataset_name),
    )
    write_report_doc(out, ts)
    print(f"cohere_mode ok={ok} msg={msg} out_dir={out}")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
