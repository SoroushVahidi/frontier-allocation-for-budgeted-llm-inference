#!/usr/bin/env python3
"""Hundred-case failure statistics: canonical full method vs reasoning_beam2.

Extends the methodology in ``build_twenty_exact_current_full_vs_best_fresh.py`` with:
- deterministic fair merge across datasets for broader coverage,
- richer per-case diagnostics (10 analysis features),
- machine-readable aggregates and a paper-facing markdown report.

Best method is fixed to ``reasoning_beam2`` per the April 2026 canonical comparison surface.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import math
import random
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _load_twenty_bundle_module():
    path = REPO_ROOT / "scripts/build_twenty_exact_current_full_vs_best_fresh.py"
    spec = importlib.util.spec_from_file_location("twenty_exact_bundle", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


TW = _load_twenty_bundle_module()

BEST_METHOD_FIXED = "reasoning_beam2"
TARGET_N = 100
# Larger simulator slice than the 20-case note so 100 exact verified losses remain feasible.
HUNDRED_SURFACE_SUBSET_SIZE = 96
HUNDRED_EXTRA_SEEDS: tuple[int, ...] = (101, 113, 137)
HUNDRED_EXTRA_BUDGETS: tuple[int, ...] = (14, 16)


def _run_observed_with_events(
    method_name: str, row: dict[str, Any], stream_tag: str
) -> dict[str, Any]:
    """Same as ``TW._run_observed`` but retains raw generator events for family-expansion analytics."""
    from experiments.branching import SimulatedBranchGenerator
    from experiments.frontier_matrix_core import build_frontier_strategies

    budget = int(row["budget"])
    seed = int(row["seed"])
    dataset = str(row["dataset"])
    example_id = str(row["example_id"])
    question = str(row["problem_text"])
    gold = str(row["ground_truth"])

    run_seed = TW._stable_seed(stream_tag, method_name, dataset, example_id, seed, budget)
    rng = random.Random(run_seed)
    observed = TW.ObservedGenerator(
        SimulatedBranchGenerator(rng=rng, max_depth=7, finish_prob_base=0.16, answer_noise=0.12)
    )

    def factory() -> Any:
        return observed

    strategies = build_frontier_strategies(
        factory,
        budget,
        TW.ADAPTIVE_GRID,
        rng,
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
    )
    result = strategies[TW._runtime_method(method_name)].run(question, gold)

    for i, ev in enumerate(observed.decision_events):
        ev.remaining_budget_before = max(0, budget - i)

    parent_map: dict[str, str | None] = {}
    last_actor: str | None = None
    for e in observed.events:
        if e["event"] in {"expand", "verify"}:
            last_actor = str(e["branch_id"])
        elif e["event"] == "init_branch":
            bid = str(e["branch_id"])
            if bid not in parent_map:
                if bid.startswith("div_child") and last_actor is not None:
                    parent_map[bid] = last_actor
                else:
                    parent_map[bid] = None

    final_nodes: list[dict[str, Any]] = []
    for bid, b in sorted(observed.registry.items(), key=lambda kv: kv[0]):
        snap = observed._snapshot(b)
        snap["parent_branch_id"] = parent_map.get(bid)
        fam = bid
        cur = bid
        seen: set[str] = set()
        while parent_map.get(cur) is not None and cur not in seen:
            seen.add(cur)
            cur = str(parent_map[cur])
            fam = cur
        snap["branch_family_id"] = fam
        final_nodes.append(snap)

    return {
        "method": method_name,
        "run_seed": run_seed,
        "budget": budget,
        "prediction": result.prediction,
        "is_correct": bool(result.is_correct),
        "actions": int(result.actions_used),
        "expansions": int(result.expansions),
        "verifications": int(result.verifications),
        "metadata": result.metadata,
        "final_nodes": final_nodes,
        "events": observed.events,
    }


def _collect_excluded_case_ids_extended() -> set[str]:
    excluded = TW._collect_excluded_case_ids()
    fresh_root = REPO_ROOT / "outputs/twenty_exact_current_full_vs_best_fresh_20260420"
    if fresh_root.is_dir():
        for p in fresh_root.glob("*/selected_case_manifest.json"):
            if not p.is_file():
                continue
            data = json.loads(p.read_text(encoding="utf-8"))
            for c in data.get("cases", []):
                if "case_id" in c:
                    excluded.add(str(c["case_id"]))
                elif "dataset" in c and "example_id" in c:
                    excluded.add(TW._case_id(str(c["dataset"]), str(c["example_id"])))
    return excluded


def _build_eval_surface_hundred(current_method: str, best_method: str) -> list[dict[str, Any]]:
    """Same grid as the 20-case builder with a wider per-seed subset and mild seed/budget expansion."""
    old_subset = TW.SUBSET_SIZE
    old_seeds = list(TW.SEEDS)
    old_budgets = list(TW.BUDGETS)
    try:
        TW.SUBSET_SIZE = int(HUNDRED_SURFACE_SUBSET_SIZE)
        TW.SEEDS = sorted(set(old_seeds) | set(HUNDRED_EXTRA_SEEDS))
        TW.BUDGETS = sorted(set(old_budgets) | set(HUNDRED_EXTRA_BUDGETS))
        return TW._build_eval_surface(current_method, best_method)
    finally:
        TW.SUBSET_SIZE = old_subset
        TW.SEEDS = old_seeds
        TW.BUDGETS = old_budgets


def _enrich_ranked_with_group_rows(
    ranked: list[dict[str, Any]], all_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    eligible = [r for r in all_rows if (not r["our_correct"]) and r["best_correct"]]
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for r in eligible:
        grouped[(str(r["dataset"]), str(r["example_id"]))].append(r)
    enriched: list[dict[str, Any]] = []
    for pick in ranked:
        key = (str(pick["dataset"]), str(pick["example_id"]))
        grows = grouped.get(key, [])
        group_rows = sorted(grows, key=lambda r: (-int(r["budget"]), -int(r["seed"])))
        enriched.append({**pick, "group_rows": group_rows})
    return enriched


def _fair_merge_by_dataset(ranked_global: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Preserve within-dataset order from *ranked_global*, merge buckets round-robin (lexicographic dataset)."""
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for rec in ranked_global:
        buckets[str(rec["dataset"])].append(rec)
    ds_order = sorted(buckets.keys())
    idx = {d: 0 for d in ds_order}
    total = sum(len(buckets[d]) for d in ds_order)
    out: list[dict[str, Any]] = []
    while len(out) < total:
        for d in ds_order:
            j = idx[d]
            if j < len(buckets[d]):
                out.append(buckets[d][j])
                idx[d] += 1
    return out


def _parent_and_family_maps(
    events: list[dict[str, Any]], final_nodes: list[dict[str, Any]]
) -> tuple[dict[str, str | None], dict[str, str]]:
    parent_map: dict[str, str | None] = {}
    last_actor: str | None = None
    for e in events:
        if e["event"] in {"expand", "verify"}:
            last_actor = str(e["branch_id"])
        elif e["event"] == "init_branch":
            bid = str(e["branch_id"])
            if bid not in parent_map:
                if bid.startswith("div_child") and last_actor is not None:
                    parent_map[bid] = last_actor
                else:
                    parent_map[bid] = None

    def family_of(bid: str) -> str:
        fam = bid
        cur = bid
        seen: set[str] = set()
        while parent_map.get(cur) is not None and cur not in seen:
            seen.add(cur)
            cur = str(parent_map[cur])
            fam = cur
        return fam

    fam_map = {str(n["branch_id"]): str(n.get("branch_family_id")) for n in final_nodes}
    # Ensure all branch ids in events resolve
    all_ids = {str(e.get("branch_id")) for e in events if e.get("branch_id")}
    for bid in all_ids:
        if bid not in fam_map:
            fam_map[bid] = family_of(bid)
    return parent_map, fam_map


def _expansion_family_sequence(events: list[dict[str, Any]], fam_map: dict[str, str]) -> list[str]:
    out: list[str] = []
    for e in events:
        if e.get("event") != "expand":
            continue
        bid = str(e.get("branch_id", ""))
        out.append(fam_map.get(bid, bid))
    return out


def _same_family_expansion_severity(
    events: list[dict[str, Any]], final_nodes: list[dict[str, Any]], metadata: dict[str, Any] | None
) -> dict[str, Any]:
    _, fam_map = _parent_and_family_maps(events, final_nodes)
    seq = _expansion_family_sequence(events, fam_map)
    if not seq:
        meta_ct = int((metadata or {}).get("repeated_same_family_expansion_count", 0))
        return {
            "repeated_same_family_present": bool(meta_ct > 0),
            "max_family_share_of_expansions": None,
            "longest_consecutive_same_family_run": 0,
            "num_families_expanded": 0,
            "expansion_family_sequence_length": 0,
        }
    ctr = Counter(seq)
    top_cnt = ctr.most_common(1)[0][1]
    max_share = float(top_cnt / len(seq))
    longest = 1
    cur = 1
    for i in range(1, len(seq)):
        if seq[i] == seq[i - 1]:
            cur += 1
            longest = max(longest, cur)
        else:
            cur = 1
    n_fam = len(set(seq))
    meta_ct = int((metadata or {}).get("repeated_same_family_expansion_count", 0))
    # Conservative: a single expand always yields max_share==1.0; require repetition or broadened concentration.
    repeated = bool(meta_ct > 0 or longest >= 2 or (len(seq) >= 4 and max_share >= 0.55))
    return {
        "repeated_same_family_present": repeated,
        "max_family_share_of_expansions": round(max_share, 6),
        "longest_consecutive_same_family_run": int(longest),
        "num_families_expanded": int(n_fam),
        "expansion_family_sequence_length": int(len(seq)),
    }


def _answer_group_profile(
    final_nodes: list[dict[str, Any]], dataset: str, metadata: dict[str, Any] | None
) -> dict[str, Any]:
    support: dict[str, list[str]] = defaultdict(list)
    for n in final_nodes:
        raw = n.get("predicted_answer")
        if raw is None:
            continue
        can = TW.canonicalize_answer(str(raw), dataset=dataset)
        if can is not None:
            support[can].append(str(n.get("branch_id")))
    counts = {k: len(v) for k, v in support.items()}
    total = sum(counts.values())
    dom_share = float(max(counts.values()) / total) if total else 0.0
    meta_groups = (metadata or {}).get("unique_answer_groups_seen")
    monopolized = bool(len(counts) >= 2 and dom_share >= 0.75)
    starved = bool(
        len(counts) >= 2 and dom_share >= 0.6 and meta_groups is not None and int(meta_groups) <= 2
    )
    return {
        "num_answer_groups": int(len(counts)),
        "answer_group_support": counts,
        "answer_group_node_ids": {k: v for k, v in support.items()},
        "dominant_answer_group_share": round(dom_share, 6),
        "one_answer_group_monopolized_tree": monopolized,
        "plausible_alternatives_starved_heuristic": starved,
    }


def _dominant_wrong_family_depth_profile(
    final_nodes: list[dict[str, Any]], gold_can: str | None, chosen_id: str | None, dataset: str
) -> dict[str, Any]:
    wrong_done = [
        n
        for n in final_nodes
        if n.get("predicted_answer") is not None
        and TW.canonicalize_answer(str(n.get("predicted_answer")), dataset=dataset) != gold_can
    ]
    if not wrong_done:
        return {"profile": None, "reason": "no_wrong_done_nodes"}
    # choose dominant wrong answer by count then score
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for n in wrong_done:
        can = TW.canonicalize_answer(str(n.get("predicted_answer")), dataset=dataset)
        if can:
            buckets[can].append(n)
    dom_ans = max(
        buckets.keys(),
        key=lambda a: (len(buckets[a]), max(float(x.get("score", 0.0)) for x in buckets[a])),
    )
    nodes = buckets[dom_ans]
    depths = [int(n.get("depth", 0)) for n in nodes]
    return {
        "dominant_wrong_answer": dom_ans,
        "min_depth": min(depths) if depths else None,
        "max_depth": max(depths) if depths else None,
        "mean_depth": round(float(statistics.mean(depths)), 4) if depths else None,
        "n_nodes": len(nodes),
        "chosen_in_this_family": bool(
            chosen_id and any(str(n.get("branch_id")) == str(chosen_id) for n in nodes)
        ),
    }


def _correct_depth_maturity(
    final_nodes: list[dict[str, Any]],
    correct_ids: list[str],
    chosen_id: str | None,
    dataset: str,
) -> dict[str, Any]:
    if not correct_ids:
        return {"status": "absent"}
    id_to_node = {str(n.get("branch_id")): n for n in final_nodes}
    depths = []
    for cid in correct_ids:
        n = id_to_node.get(str(cid))
        if n is not None:
            depths.append(int(n.get("depth", 0)))
    if not depths:
        return {"status": "present_ids_not_in_final_snapshot"}
    cmin, cmax = min(depths), max(depths)
    ch_depth = None
    if chosen_id and str(chosen_id) in id_to_node:
        ch_depth = int(id_to_node[str(chosen_id)].get("depth", 0))
    early_late = None
    if ch_depth is not None:
        if cmin < ch_depth:
            early_late = "correct_earlier_than_chosen"
        elif cmin == ch_depth:
            early_late = "correct_same_depth_as_chosen_min"
        else:
            early_late = "correct_only_deeper_than_chosen"
    return {
        "status": "present",
        "min_depth_correct": cmin,
        "max_depth_correct": cmax,
        "chosen_depth": ch_depth,
        "correct_vs_chosen_depth_relation": early_late,
    }


def _score_gap_profile(
    final_nodes: list[dict[str, Any]],
    correct_ids: list[str],
    chosen_id: str | None,
    gold_can: str | None,
) -> dict[str, Any]:
    id_to_node = {str(n.get("branch_id")): n for n in final_nodes}
    chosen_score = (
        float(id_to_node[str(chosen_id)]["score"])
        if chosen_id and str(chosen_id) in id_to_node
        else None
    )
    if not correct_ids:
        return {
            "chosen_score": chosen_score,
            "best_correct_score": None,
            "score_gap_chosen_minus_best_correct": None,
            "gap_magnitude": None,
        }
    scores = []
    for cid in correct_ids:
        n = id_to_node.get(str(cid))
        if n is not None:
            scores.append(float(n.get("score", 0.0)))
    if not scores:
        return {
            "chosen_score": chosen_score,
            "best_correct_score": None,
            "score_gap_chosen_minus_best_correct": None,
            "gap_magnitude": None,
        }
    best_c = max(scores)
    gap = None if chosen_score is None else float(chosen_score - best_c)
    mag = None
    if gap is not None:
        ag = abs(gap)
        if ag < 0.05:
            mag = "near_tie"
        elif ag < 0.15:
            mag = "moderate"
        else:
            mag = "large"
    return {
        "chosen_score": chosen_score,
        "best_correct_score": best_c,
        "score_gap_chosen_minus_best_correct": gap,
        "gap_magnitude": mag,
    }


def _problem_regime_label(problem: str, dataset: str) -> str:
    t = problem.lower()
    ds = dataset.lower()
    if "openai/gsm8k" in ds:
        return "gsm8k_style_word_arithmetic"
    if any(
        k in t
        for k in (
            "triangle",
            "circle",
            "angle",
            "polygon",
            "rectangle",
            "degree",
            "cyclic quadrilateral",
        )
    ):
        return "geometry"
    if any(k in t for k in ("\\sum", "sum_", "infinite", "fibonacci", "series")):
        return "symbolic_series_or_formula"
    if any(k in t for k in (" gcd ", "lcm", "mod ", " remainder", "divisible", "prime")):
        return "number_theory"
    if any(k in t for k in ("choose", "combin", "permut", "ways to", "how many")) and (
        "graph" not in t
    ):
        return "counting_combinatorics"
    if any(k in t for k in ("solve", "equation", "polynomial", "quadratic", "variable")):
        return "algebraic_manipulation"
    return "other"


def _error_geometry(
    our_answer_raw: str | None, gold: str, problem: str, dataset: str
) -> dict[str, Any]:
    labels: list[str] = []
    detail: dict[str, Any] = {}
    oc = TW.canonicalize_answer(our_answer_raw, dataset=dataset)
    gc = TW.canonicalize_answer(gold, dataset=dataset)
    detail["our_canonical"] = oc
    detail["gold_canonical"] = gc
    if oc is None or gc is None:
        return {"labels": ["other"], "detail": detail}
    if oc == gc:
        return {"labels": ["other"], "detail": detail}

    def _try_float(x: str) -> float | None:
        try:
            return float(x)
        except ValueError:
            return None

    of, gf = _try_float(str(oc)), _try_float(str(gc))
    if of is not None and gf is not None:
        diff = abs(of - gf)
        detail["numeric_distance"] = diff
        scale = max(abs(gf), 1e-9)
        rel = diff / scale
        if diff <= 1.0 or rel <= 0.02:
            labels.append("near_miss")
        elif rel <= 0.12:
            labels.append("wrong_local_neighborhood")
        if of * gf < 0 and abs(of) > 1e-6 and abs(gf) > 1e-6:
            labels.append("sign_or_parity_error")
        if (
            diff == round(diff)
            and diff > 0
            and diff < 25
            and any(k in problem.lower() for k in ("+", "-", "*", "/"))
        ):
            labels.append("arithmetic_slip")
        if "how many" in problem.lower() and diff == round(diff):
            labels.append("counting_error")
    if not labels:
        if len(str(oc)) > 1 and (str(oc) in str(gc) or str(gc) in str(oc)):
            labels.append("wrong_reasoning_path")
        else:
            labels.append("other")
    # de-dupe preserving order
    seen: set[str] = set()
    uniq = []
    for x in labels:
        if x not in seen:
            seen.add(x)
            uniq.append(x)
    return {"labels": uniq, "detail": detail}


def _best_method_advantage_types(
    our: dict[str, Any],
    best: dict[str, Any],
    our_correct_ids: list[str],
    best_correct_ids: list[str],
    same_ours: dict[str, Any],
    same_best: dict[str, Any],
    failure_type: str,
) -> list[str]:
    tags: list[str] = []
    od = _correct_depth_maturity(
        our["final_nodes"], our_correct_ids, our.get("repair", {}).get("chosen_final_node_id"), ""
    )
    bd = _correct_depth_maturity(
        best["final_nodes"],
        best_correct_ids,
        best.get("repair", {}).get("chosen_final_node_id"),
        "",
    )
    if failure_type == "absent_from_tree" and best_correct_ids:
        if bd.get("min_depth_correct") is not None:
            tags.append("earlier_correct_entry")
        if len(best_correct_ids) >= 2:
            tags.append("multiple_correct_beams")
    if failure_type == "present_not_selected":
        tags.append("better_selection")
        if bd.get("min_depth_correct") is not None and od.get("min_depth_correct") is not None:
            if int(bd["min_depth_correct"]) < int(od["min_depth_correct"]):
                tags.append("earlier_correct_entry")
    if failure_type == "output_or_extraction_mismatch":
        tags.append("better_selection")
    max_ours = float(same_ours.get("max_family_share_of_expansions") or 0.0)
    max_best = float(same_best.get("max_family_share_of_expansions") or 0.0)
    if max_ours - max_best >= 0.15 and longest_run_ge(same_ours, same_best):
        tags.append("less_collapse")
    if int(best["actions"]) <= int(our["actions"]) - 2 and best.get("is_correct"):
        tags.append("better_budget_efficiency")
    if not tags:
        tags.append("other")
    # uniq
    out: list[str] = []
    for t in tags:
        if t not in out:
            out.append(t)
    return out


def longest_run_ge(same_ours: dict[str, Any], same_best: dict[str, Any]) -> bool:
    a = int(same_ours.get("longest_consecutive_same_family_run") or 0)
    b = int(same_best.get("longest_consecutive_same_family_run") or 0)
    return a >= max(2, b + 1)


def _budget_profile(our: dict[str, Any], best: dict[str, Any], budget: int) -> dict[str, Any]:
    def _util(row: dict[str, Any]) -> float | None:
        if budget <= 0:
            return None
        return round(float(row["actions"]) / budget, 6)

    return {
        "budget": budget,
        "ours": {
            "actions": int(our["actions"]),
            "expansions": int(our["expansions"]),
            "verifications": int(our["verifications"]),
            "budget_utilization_ratio": _util(our),
        },
        "best": {
            "actions": int(best["actions"]),
            "expansions": int(best["expansions"]),
            "verifications": int(best["verifications"]),
            "budget_utilization_ratio": _util(best),
        },
        "action_gap_ours_minus_best": int(our["actions"]) - int(best["actions"]),
    }


def _map_failure_type(concise: str) -> str:
    if concise == "absent_from_tree":
        return "absent_from_tree"
    if concise == "present_not_selected":
        return "present_not_selected"
    if concise == "output_layer_mismatch":
        return "output_or_extraction_mismatch"
    return "other"


def _percentile(sorted_vals: list[float], q: float) -> float | None:
    if not sorted_vals:
        return None
    k = (len(sorted_vals) - 1) * q
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(sorted_vals[int(k)])
    return float(sorted_vals[f] * (c - k) + sorted_vals[c] * (k - f))


def _distribution_summary(values: list[float | int | None]) -> dict[str, Any]:
    xs = sorted(float(x) for x in values if x is not None)
    if not xs:
        return {"n": 0, "missing": sum(1 for x in values if x is None)}
    return {
        "n": len(xs),
        "missing": sum(1 for x in values if x is None),
        "min": xs[0],
        "mean": round(statistics.mean(xs), 6),
        "p50": _percentile(xs, 0.5),
        "p90": _percentile(xs, 0.9),
        "max": xs[-1],
    }


def _cross_tab(rows: list[dict[str, Any]], key_a: str, key_b: str) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in rows:
        a = str(r.get(key_a, "missing"))
        b = str(r.get(key_b, "missing"))
        out[a][b] += 1
    return {ka: dict(vb) for ka, vb in out.items()}


def _run_one_case(
    pick: dict[str, Any],
    row: dict[str, Any],
    current_method: str,
) -> dict[str, Any] | None:
    case_id = str(pick["case_id"])
    dataset = str(row["dataset"])
    gold_raw = str(row["ground_truth"])
    gold_can = TW.canonicalize_answer(gold_raw, dataset=dataset)

    # Stream tags must match ``build_twenty_exact_current_full_vs_best_fresh.py`` so trajectories align.
    our_raw = _run_observed_with_events(current_method, row, "fresh_our")
    best_raw = _run_observed_with_events(BEST_METHOD_FIXED, row, "fresh_best")

    our_repair = TW.choose_repair_answer(
        final_nodes=list(our_raw["final_nodes"]),
        selected_group_hint=(our_raw.get("metadata") or {}).get("selected_group"),
        dataset=dataset,
        enable_rescue=True,
    )
    best_repair = TW.choose_repair_answer(
        final_nodes=list(best_raw["final_nodes"]),
        selected_group_hint=(best_raw.get("metadata") or {}).get("selected_group"),
        dataset=dataset,
        enable_rescue=True,
    )

    our_answer = our_repair.get("surfaced_final_answer_raw")
    best_answer = best_repair.get("surfaced_final_answer_raw")
    our_can = TW.canonicalize_answer(our_answer, dataset=dataset)
    best_can = TW.canonicalize_answer(best_answer, dataset=dataset)

    if not (our_can != gold_can and best_can == gold_can):
        return None

    our_correct_ids = TW._node_ids_with_answer(our_raw["final_nodes"], gold_can)
    best_correct_ids = TW._node_ids_with_answer(best_raw["final_nodes"], gold_can)
    our_contains = bool(our_correct_ids)

    output_mismatch = bool(
        our_contains
        and (our_repair.get("chosen_final_node_answer_canonical") == gold_can)
        and (our_can != gold_can)
    )
    extraction_mismatch = bool(
        (
            our_repair.get("chosen_final_node_answer_canonical")
            != our_repair.get("extracted_final_answer_canonical")
        )
        or (
            our_repair.get("extracted_final_answer_canonical")
            != our_repair.get("surfaced_final_answer_canonical")
        )
        or (
            our_repair.get("chosen_final_node_answer_raw")
            != our_repair.get("chosen_final_node_answer_canonical")
        )
    )

    if not our_contains:
        concise = "absent_from_tree"
    elif output_mismatch or extraction_mismatch:
        concise = "output_layer_mismatch"
    else:
        concise = "present_not_selected"

    failure_type = _map_failure_type(concise)

    cov_status = "none"
    if len(our_correct_ids) == 1:
        cov_status = "single"
    elif len(our_correct_ids) > 1:
        cov_status = "multiple"

    same_ours = _same_family_expansion_severity(
        [e for e in our_raw["events"]], our_raw["final_nodes"], our_raw.get("metadata")
    )
    same_best = _same_family_expansion_severity(
        [e for e in best_raw["events"]], best_raw["final_nodes"], best_raw.get("metadata")
    )

    ag_ours = _answer_group_profile(our_raw["final_nodes"], dataset, our_raw.get("metadata"))

    c_depth = _correct_depth_maturity(
        our_raw["final_nodes"], our_correct_ids, our_repair.get("chosen_final_node_id"), dataset
    )
    if failure_type == "absent_from_tree":
        c_depth = {
            **c_depth,
            "dominant_wrong_family": _dominant_wrong_family_depth_profile(
                our_raw["final_nodes"], gold_can, our_repair.get("chosen_final_node_id"), dataset
            ),
        }

    sgap = _score_gap_profile(
        our_raw["final_nodes"], our_correct_ids, our_repair.get("chosen_final_node_id"), gold_can
    )

    bud = _budget_profile(our_raw, best_raw, int(row["budget"]))

    err_geo = _error_geometry(our_answer, gold_raw, str(row["problem_text"]), dataset)

    regime = _problem_regime_label(str(row["problem_text"]), dataset)

    adv = _best_method_advantage_types(
        {**our_raw, "repair": our_repair, "is_correct": False},
        {**best_raw, "repair": best_repair, "is_correct": True},
        our_correct_ids,
        best_correct_ids,
        same_ours,
        same_best,
        failure_type,
    )

    compact_row = {
        "case_id": case_id,
        "dataset": dataset,
        "example_id": str(row["example_id"]),
        "gold_answer": gold_raw,
        "our_answer": our_answer,
        "best_answer": best_answer,
        "failure_type": failure_type,
        "same_family_expansion_present": same_ours["repeated_same_family_present"],
        "max_family_share": same_ours.get("max_family_share_of_expansions"),
        "longest_consecutive_family_run": same_ours.get("longest_consecutive_same_family_run"),
        "num_families_expanded": same_ours.get("num_families_expanded"),
        "correct_answer_coverage_status": cov_status,
        "correct_node_ids": ";".join(our_correct_ids),
        "chosen_node_id": our_repair.get("chosen_final_node_id"),
        "chosen_score": sgap.get("chosen_score"),
        "best_correct_score": sgap.get("best_correct_score"),
        "score_gap": sgap.get("score_gap_chosen_minus_best_correct"),
        "actions_ours": bud["ours"]["actions"],
        "expansions_ours": bud["ours"]["expansions"],
        "verifications_ours": bud["ours"]["verifications"],
        "actions_best": bud["best"]["actions"],
        "expansions_best": bud["best"]["expansions"],
        "verifications_best": bud["best"]["verifications"],
        "num_answer_groups": ag_ours["num_answer_groups"],
        "dominant_answer_group_share": ag_ours["dominant_answer_group_share"],
        "error_geometry": "|".join(err_geo["labels"]),
        "best_method_advantage_type": "|".join(adv),
        "problem_regime_label": regime,
    }

    return {
        "case_id": case_id,
        "dataset": dataset,
        "example_id": str(row["example_id"]),
        "selection_rank_fields": {
            "loss_support_count": int(pick["loss_support_count"]),
            "max_budget_with_loss": int(pick["max_budget_with_loss"]),
            "observability_priority": int(pick["observability_priority"]),
        },
        "surface_row": {"seed": int(row["seed"]), "budget": int(row["budget"])},
        "failure_type": failure_type,
        "same_family_expansion_severity": same_ours,
        "correct_answer_coverage_status": cov_status,
        "correct_node_ids": our_correct_ids,
        "correct_branch_depth_and_maturity": c_depth,
        "chosen_vs_correct_score_gap": sgap,
        "budget_usage_profile": bud,
        "alternative_answer_group_count_and_maturity": ag_ours,
        "error_geometry": err_geo,
        "best_method_advantage_type": adv,
        "problem_regime_label": regime,
        "compact_row": compact_row,
        "artifacts": {
            "our_discovered_tree_compact": TW._to_text_tree(our_raw["final_nodes"]),
            "best_discovered_tree_compact": TW._to_text_tree(best_raw["final_nodes"]),
        },
    }


def main() -> None:
    now = datetime.now(timezone.utc)
    ts = now.strftime("%Y%m%dT%H%M%SZ")
    out_dir = REPO_ROOT / f"outputs/hundred_current_full_vs_best_failure_statistics_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    current_method = TW._resolve_current_full_method()

    excluded = _collect_excluded_case_ids_extended()
    rows = _build_eval_surface_hundred(current_method, BEST_METHOD_FIXED)
    ranked, selection_policy = TW._select_candidates(rows, excluded)
    ranked = _enrich_ranked_with_group_rows(ranked, rows)
    merged = _fair_merge_by_dataset(ranked)

    selection_policy = {
        **selection_policy,
        "target_count": TARGET_N,
        "best_method_fixed": BEST_METHOD_FIXED,
        "surface_expansion": {
            "subset_size": HUNDRED_SURFACE_SUBSET_SIZE,
            "extra_seeds": list(HUNDRED_EXTRA_SEEDS),
            "extra_budgets": list(HUNDRED_EXTRA_BUDGETS),
        },
        "dataset_fair_merge": "within-dataset global rank preserved; round-robin across datasets in lexicographic order",
        "verification_search": "within each (dataset, example_id), try group_rows sorted by (-budget,-seed) until repair-consistent exact loss holds",
    }

    per_case: list[dict[str, Any]] = []
    tried_groups = 0
    for pick in merged:
        if len(per_case) >= TARGET_N:
            break
        tried_groups += 1
        for row in pick.get("group_rows") or [pick["representative"]]:
            built = _run_one_case(pick, row, current_method)
            if built is not None:
                per_case.append(built)
                break

    if len(per_case) < TARGET_N:
        raise RuntimeError(
            f"Only collected {len(per_case)}/{TARGET_N} verified cases after {tried_groups} fair-merge groups; "
            "relax exclusions or expand eval surface."
        )

    # --- aggregates ---
    flat_rows = [p["compact_row"] for p in per_case]

    def pct(n: int, d: int) -> str:
        return f"{n} ({100.0 * n / max(1, d):.1f}%)"

    n = len(per_case)
    ft_counts = Counter(str(p["failure_type"]) for p in per_case)
    ds_counts = Counter(str(p["dataset"]) for p in per_case)
    reg_counts = Counter(str(p["problem_regime_label"]) for p in per_case)

    err_flat: list[str] = []
    for p in per_case:
        err_flat.extend(p["error_geometry"]["labels"])
    err_counts = Counter(err_flat)

    adv_flat: list[str] = []
    for p in per_case:
        for t in p["best_method_advantage_type"]:
            adv_flat.append(t)
    adv_counts = Counter(adv_flat)

    cov_counts = Counter(str(p["correct_answer_coverage_status"]) for p in per_case)

    def _collect_num(key: str) -> list[float | None]:
        out: list[float | None] = []
        for r in flat_rows:
            v = r.get(key)
            out.append(float(v) if v is not None else None)
        return out

    aggregate = {
        "created_at_utc": now.isoformat(),
        "current_full_method_name": current_method,
        "best_method_name": BEST_METHOD_FIXED,
        "target_n": TARGET_N,
        "selection_policy": selection_policy,
        "exclusion_case_count": len(excluded),
        "failure_type_counts": {
            k: {"n": ft_counts[k], "pct": 100.0 * ft_counts[k] / n}
            for k in sorted(ft_counts.keys())
        },
        "dataset_counts": {
            k: {"n": ds_counts[k], "pct": 100.0 * ds_counts[k] / n}
            for k in sorted(ds_counts.keys())
        },
        "problem_regime_counts": {
            k: {"n": reg_counts[k], "pct": 100.0 * reg_counts[k] / n}
            for k in sorted(reg_counts.keys())
        },
        "error_geometry_counts": {
            k: {"n": err_counts[k], "pct": 100.0 * err_counts[k] / n}
            for k in sorted(err_counts.keys())
        },
        "best_method_advantage_counts": {
            k: {"n": adv_counts[k], "pct": 100.0 * adv_counts[k] / n}
            for k in sorted(adv_counts.keys())
        },
        "correct_coverage_counts": {
            k: {"n": cov_counts[k], "pct": 100.0 * cov_counts[k] / n}
            for k in sorted(cov_counts.keys())
        },
        "repeated_same_family_present_n": sum(
            1
            for p in per_case
            if p["same_family_expansion_severity"]["repeated_same_family_present"]
        ),
        "distributions": {
            "actions_ours": _distribution_summary([r["actions_ours"] for r in flat_rows]),
            "expansions_ours": _distribution_summary([r["expansions_ours"] for r in flat_rows]),
            "verifications_ours": _distribution_summary(
                [r["verifications_ours"] for r in flat_rows]
            ),
            "action_gap_ours_minus_best": _distribution_summary(
                [float(r["actions_ours"] - r["actions_best"]) for r in flat_rows]
            ),
            "score_gap": _distribution_summary(_collect_num("score_gap")),
            "longest_consecutive_family_run": _distribution_summary(
                [
                    float(
                        p["same_family_expansion_severity"].get(
                            "longest_consecutive_same_family_run"
                        )
                        or 0
                    )
                    for p in per_case
                ]
            ),
            "max_family_share": _distribution_summary(_collect_num("max_family_share")),
            "num_answer_groups": _distribution_summary(
                [float(r["num_answer_groups"]) for r in flat_rows]
            ),
        },
        "cross_tabs": {
            "failure_type_x_dataset": _cross_tab(flat_rows, "failure_type", "dataset"),
            "failure_type_x_error_geometry_primary": _cross_tab(
                [
                    {
                        **r,
                        "error_geometry_primary": (r.get("error_geometry") or "other").split("|")[
                            0
                        ],
                    }
                    for r in flat_rows
                ],
                "failure_type",
                "error_geometry_primary",
            ),
            "failure_type_x_same_family": _cross_tab(
                [
                    {**r, "same_family_expansion_present": str(r["same_family_expansion_present"])}
                    for r in flat_rows
                ],
                "failure_type",
                "same_family_expansion_present",
            ),
            "failure_type_x_problem_regime": _cross_tab(
                flat_rows, "failure_type", "problem_regime_label"
            ),
        },
        "missingness_notes": {
            "max_family_share_null_when_no_expands": "max_family_share may be null if no expand events were observed",
            "score_gap_null_when_no_correct_node": "score_gap null when correct nodes absent or scores unavailable",
        },
    }

    manifest = {
        "artifact_family": "hundred_current_full_vs_best_failure_statistics",
        "created_at_utc": now.isoformat(),
        "output_dir": str(out_dir.relative_to(REPO_ROOT)),
        "current_full_method_name": current_method,
        "best_method_name": BEST_METHOD_FIXED,
        "selection_policy": selection_policy,
        "cases": [
            {"case_id": p["case_id"], "dataset": p["dataset"], "example_id": p["example_id"]}
            for p in per_case
        ],
        "fair_merge_groups_scanned_to_reach_target": tried_groups,
    }

    (out_dir / "selection_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    (out_dir / "per_case_failure_statistics.json").write_text(
        json.dumps(per_case, indent=2) + "\n", encoding="utf-8"
    )
    (out_dir / "aggregate_failure_statistics.json").write_text(
        json.dumps(aggregate, indent=2) + "\n", encoding="utf-8"
    )

    csv_path = out_dir / "failure_statistics_table.csv"
    if flat_rows:
        with csv_path.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(flat_rows[0].keys()))
            w.writeheader()
            w.writerows(flat_rows)

    by_ft: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for p in per_case:
        by_ft[str(p["failure_type"])].append(p)
    rep_examples: list[dict[str, Any]] = []
    for ft in sorted(by_ft.keys()):
        for p in by_ft[ft][:4]:
            rep_examples.append(p)
    rep_examples = rep_examples[:14]

    doc_path = REPO_ROOT / f"docs/HUNDRED_CURRENT_FULL_VS_BEST_FAILURE_STATISTICS_{ts}.md"
    top_err = err_counts.most_common(3)
    top_adv = adv_counts.most_common(3)
    absent_n = ft_counts.get("absent_from_tree", 0)
    pns_n = ft_counts.get("present_not_selected", 0)
    om_n = ft_counts.get("output_or_extraction_mismatch", 0)
    rep_same_n = aggregate["repeated_same_family_present_n"]

    conclusion = (
        "Most losses are still driven by absent gold in our search tree (coverage) rather than output-layer errors, "
        "with repeated same-family expansion pressure remaining a common companion pattern."
    )
    if absent_n < pns_n:
        conclusion = "Selection and scoring errors dominate on this 100-case slice once gold is present; coverage gaps are still material but secondary."

    lines: list[str] = []
    lines.append("# Hundred-case failure statistics: current full method vs reasoning_beam2")
    lines.append("")
    lines.append(f"- Generated (UTC): `{now.isoformat()}`")
    lines.append(f"- Output directory: `{out_dir.relative_to(REPO_ROOT)}`")
    lines.append("")
    lines.append("## Method resolution")
    lines.append(f"- **Current full method**: `{current_method}`")
    lines.append(f"- **Best method (fixed for this report)**: `{BEST_METHOD_FIXED}`")
    lines.append("")
    lines.append("## Selection rule for the 100 cases")
    lines.append(
        "0. **Simulator surface (expanded, documented in `selection_manifest.json`)**: same benchmark mix as the 20-case "
        "builder, with per-seed subset size 96 (vs 40) and additional seeds `{101,113,137}` plus budgets `{14,16}` to "
        "ensure 100 repair-consistent exact-loss cases exist under current exclusions."
    )
    lines.append(
        "1. **Eligibility**: On that grid, keep rows where the current full method is incorrect and `reasoning_beam2` is correct."
    )
    lines.append(
        "2. **De-duplication**: Group by `(dataset, example_id)`; score groups by support across the grid "
        "(loss_support_count, max_budget_with_loss, observability_priority, lexical id) exactly as the 20-case builder."
    )
    lines.append(
        "3. **Exclusions**: Union of the repo’s prior exact-failure manifests (see `selection_manifest.json`) plus any "
        "checked-in `twenty_exact_current_full_vs_best_fresh_20260420/*/selected_case_manifest.json` if present."
    )
    lines.append(
        "4. **Coverage-aware ordering**: Within each dataset, preserve the global rank order; merge datasets in "
        "**round-robin** (lexicographic dataset name) so early picks span benchmarks before going deeper in one dataset."
    )
    lines.append(
        "5. **Exact verification**: For each candidate group, try `(seed, budget)` rows in descending budget/seed order "
        "until a pair passes full observed-tree replay with deterministic output-layer repair where canonical grading "
        "still shows **ours wrong / beam2 correct** (stream tags `fresh_our` / `fresh_best` match the 20-case builder)."
    )
    lines.append("")
    lines.append("## Output files")
    lines.append(f"- `{out_dir.relative_to(REPO_ROOT)}/per_case_failure_statistics.json`")
    lines.append(f"- `{out_dir.relative_to(REPO_ROOT)}/aggregate_failure_statistics.json`")
    lines.append(f"- `{out_dir.relative_to(REPO_ROOT)}/failure_statistics_table.csv`")
    lines.append(f"- `{out_dir.relative_to(REPO_ROOT)}/selection_manifest.json`")
    lines.append("")
    lines.append("## Aggregate: failure_type")
    for k in sorted(ft_counts.keys()):
        lines.append(f"- `{k}`: {pct(ft_counts[k], n)}")
    lines.append("")
    lines.append("## Aggregate: dataset")
    for k in sorted(ds_counts.keys()):
        lines.append(f"- `{k}`: {pct(ds_counts[k], n)}")
    lines.append("")
    lines.append("## Aggregate: problem_regime_label")
    for k in sorted(reg_counts.keys()):
        lines.append(f"- `{k}`: {pct(reg_counts[k], n)}")
    lines.append("")
    lines.append("## Aggregate: error_geometry (multi-label; counts sum >100%)")
    for k, c in err_counts.most_common():
        lines.append(f"- `{k}`: {c} ({100.0 * c / n:.1f}% of cases carry this tag)")
    lines.append("")
    lines.append("## Aggregate: best_method_advantage_type (multi-label)")
    for k, c in adv_counts.most_common():
        lines.append(f"- `{k}`: {c} ({100.0 * c / n:.1f}% of cases carry this tag)")
    lines.append("")
    lines.append("## Correct-answer coverage (in our tree)")
    for k in sorted(cov_counts.keys()):
        lines.append(f"- `{k}`: {pct(cov_counts[k], n)}")
    lines.append("")
    lines.append("## Same-family expansion severity (ours)")
    lines.append(
        f"- repeated_same_family_present: **{rep_same_n} / {n}** ({100.0 * rep_same_n / n:.1f}%)"
    )
    lines.append(
        "- distribution summaries: see `aggregate_failure_statistics.json` under `distributions`"
    )
    lines.append("")
    lines.append("## Answer-group maturity (ours)")
    lines.append(
        "- See `alternative_answer_group_count_and_maturity` per case and `distributions.num_answer_groups` / "
        "`dominant_answer_group_share` in the table."
    )
    lines.append("")
    lines.append("## Cross-tabs (excerpt)")
    lines.append("- Full tables in `aggregate_failure_statistics.json` under `cross_tabs`.")
    lines.append("")
    lines.append("## Representative examples")
    for p in rep_examples:
        surf = p["surface_row"]
        prow = next(
            (
                r
                for r in rows
                if str(r["dataset"]) == p["dataset"]
                and str(r["example_id"]) == p["example_id"]
                and int(r["seed"]) == surf["seed"]
                and int(r["budget"]) == surf["budget"]
            ),
            None,
        )
        preview = (prow or {}).get("problem_text", "")
        lines.append(
            f"- `{p['case_id']}` — **{p['failure_type']}** — error_geometry: `{', '.join(p['error_geometry']['labels'])}` — "
            f"best_method_advantage: `{', '.join(p['best_method_advantage_type'])}`"
        )
        lines.append(f"  - preview: {str(preview)[:240]!r}")
    lines.append("")
    lines.append("## Conclusions")
    lines.append(f"- {conclusion}")
    lines.append("")

    doc_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("OUTPUT_DIR", out_dir)
    print("DOC", doc_path)
    print("ABSENT_FROM_TREE", absent_n)
    print("PRESENT_NOT_SELECTED", pns_n)
    print("OUTPUT_OR_EXTRACTION_MISMATCH", om_n)
    print("REPEATED_SAME_FAMILY", rep_same_n)
    print("TOP_ERROR_GEOM", top_err)
    print("TOP_ADV", top_adv)


if __name__ == "__main__":
    main()
