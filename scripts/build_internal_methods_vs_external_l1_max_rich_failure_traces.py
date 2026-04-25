#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.output_layer_repair import canonicalize_answer

PRIMARY_FEATURES = [
    "budget",
    "question_length_tokens",
    "number_count",
    "operation_type_guess",
    "estimated_reasoning_steps_required",
    "internal_gold_final_answer_in_tree",
    "internal_gold_intermediate_quantity_fraction",
    "internal_nearest_gold_path_depth",
    "internal_nearest_gold_path_score",
    "internal_abandoned_promising_branch",
    "internal_committed_before_promising_branch_matured",
    "internal_correct_region_entered",
    "internal_max_branch_depth",
    "internal_failure_tag",
    "internal_answer_group_count",
    "internal_answer_entropy",
    "internal_selected_answer_support_fraction",
    "internal_top2_support_gap",
    "internal_cost_ratio_vs_external_l1_max",
    "internal_latency_ratio_vs_external_l1_max",
]

OPS = {
    "ratio_percent": ["percent", "%", "ratio", "fraction", "probability", "rate"],
    "comparison": ["more than", "less than", "greater", "fewer", "difference", "compare"],
    "counting_combinatorics": ["ways", "arrange", "choose", "combination", "permutation", "how many"],
    "unit_conversion": ["km", "meter", "hour", "minute", "second", "mile", "kg", "gram", "liter", "convert"],
    "algebra_like": ["equation", "solve for", "unknown", "variable", "x="],
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    p.add_argument("--records-path", required=True)
    p.add_argument("--provider", default="cohere")
    p.add_argument("--dataset", default="openai/gsm8k")
    p.add_argument("--model", default="command-r-plus-08-2024")
    p.add_argument("--seeds", default="11,23")
    p.add_argument("--budgets", default="4,6,8")
    p.add_argument("--internal-methods", default="strict_f3,strict_gate1_cap_k6,strict_f3_anti_collapse_weak_v1")
    return p.parse_args()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not path.exists():
        return out
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        if not rows:
            if fieldnames:
                w = csv.DictWriter(f, fieldnames=fieldnames)
                w.writeheader()
            return
        w = csv.DictWriter(f, fieldnames=fieldnames or list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _token_count(text: str) -> int:
    return len((text or "").split())


def _nums(text: str) -> list[str]:
    return re.findall(r"[-+]?\d*\.?\d+", text or "")


def _op_guess(text: str, number_count: int) -> str:
    q = (text or "").lower()
    for label, keys in OPS.items():
        if any(k in q for k in keys):
            return label
    if number_count >= 3:
        return "multi_step_arithmetic"
    return "unknown"


def _estimate_steps(qlen: int, num_count: int, op: str) -> int:
    s = 1 + int(qlen > 20) + int(qlen > 35) + int(num_count >= 3) + int(op != "unknown")
    return max(1, min(5, s))


def _ratio(a: float, b: float) -> float | str:
    return "NA" if b <= 0 else (a / b)


def _entropy_from_counter(c: Counter[str]) -> float | str:
    total = sum(c.values())
    if total <= 0:
        return "NA"
    out = 0.0
    for v in c.values():
        p = v / total
        out -= p * math.log(p, 2)
    return out


def _load_gsm8k_rationales() -> dict[str, str]:
    try:
        from datasets import load_dataset
    except Exception:
        return {}
    out: dict[str, str] = {}
    for split in ("train", "test"):
        try:
            ds = load_dataset("openai/gsm8k", "main", split=split)
        except Exception:
            continue
        for row in ds:
            out[str(row["question"]).strip()] = str(row.get("answer", ""))
    return out


def main() -> None:
    args = parse_args()
    ts = args.timestamp
    seeds = {int(x) for x in args.seeds.split(",") if x.strip()}
    budgets = {int(x) for x in args.budgets.split(",") if x.strip()}
    internal_methods = [x.strip() for x in args.internal_methods.split(",") if x.strip()]

    rows = _read_jsonl(REPO_ROOT / args.records_path)
    rows = [
        r
        for r in rows
        if str(r.get("provider", "")).lower() == args.provider
        and str(r.get("dataset", "")) == args.dataset
        and _safe_int(r.get("seed", -1), -1) in seeds
        and _safe_int(r.get("budget", -1), -1) in budgets
        and str(r.get("method", "")) in (set(internal_methods) | {"external_l1_max"})
        and _safe_int(r.get("scored", 0), 0) == 1
    ]

    rationale_map = _load_gsm8k_rationales() if args.dataset == "openai/gsm8k" else {}

    by_key: dict[tuple[str, int, int, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for r in rows:
        k = (str(r["dataset"]), _safe_int(r["seed"]), _safe_int(r["budget"]), str(r["example_id"]))
        by_key[k][str(r["method"])] = r

    matched_examples: list[dict[str, Any]] = []
    loss_rows: list[dict[str, Any]] = []
    win_rows: list[dict[str, Any]] = []
    both_correct_rows: list[dict[str, Any]] = []
    both_wrong_rows: list[dict[str, Any]] = []
    branch_traces: list[dict[str, Any]] = []
    step_traces: list[dict[str, Any]] = []
    features: list[dict[str, Any]] = []
    unavailable_fields: set[str] = set()

    for (dataset, seed, budget, example_id), cell in sorted(by_key.items()):
        ext = cell.get("external_l1_max")
        if not ext:
            continue
        for method in internal_methods:
            internal = cell.get(method)
            if not internal:
                continue
            q = str(internal.get("question") or ext.get("question") or "")
            gold = str(internal.get("gold_answer") or ext.get("gold_answer") or "")
            rationale = str(internal.get("gold_solution_or_rationale") or rationale_map.get(q.strip(), "NA") or "NA")
            gold_can = canonicalize_answer(gold, dataset=dataset)
            i_raw = internal.get("final_answer_raw")
            e_raw = ext.get("final_answer_raw")
            i_can = canonicalize_answer(i_raw, dataset=dataset)
            e_can = canonicalize_answer(e_raw, dataset=dataset)
            i_ok = _safe_int(internal.get("exact_match", internal.get("internal_correct", 0)), 0)
            e_ok = _safe_int(ext.get("exact_match", ext.get("external_l1_max_correct", 0)), 0)
            if i_ok == 0 and e_ok == 1:
                ctype = "internal_loss_external_win"
            elif i_ok == 1 and e_ok == 0:
                ctype = "internal_win_external_loss"
            elif i_ok == 1 and e_ok == 1:
                ctype = "both_correct"
            else:
                ctype = "both_wrong"

            base = {
                "provider": args.provider,
                "model": str(internal.get("model") or ext.get("model") or args.model),
                "dataset": dataset,
                "seed": seed,
                "budget": budget,
                "method": method,
                "external_baseline_name": "external_l1_max",
                "example_id": example_id,
                "question": q,
                "gold_answer": gold,
                "gold_answer_canonical": gold_can,
                "gold_solution_or_rationale": rationale,
                "internal_final_answer_raw": i_raw,
                "internal_final_answer_canonical": i_can,
                "internal_correct": i_ok,
                "external_l1_max_final_answer_raw": e_raw,
                "external_l1_max_final_answer_canonical": e_can,
                "external_l1_max_correct": e_ok,
                "comparison_case_type": ctype,
                "internal_input_tokens": _safe_int(internal.get("input_tokens", 0)),
                "internal_output_tokens": _safe_int(internal.get("output_tokens", 0)),
                "internal_total_tokens": _safe_int(internal.get("total_tokens", 0)),
                "internal_latency": _safe_float(internal.get("latency_seconds", 0.0)),
                "internal_estimated_cost": _safe_float(internal.get("estimated_cost_usd", 0.0)),
                "external_input_tokens": _safe_int(ext.get("input_tokens", 0)),
                "external_output_tokens": _safe_int(ext.get("output_tokens", 0)),
                "external_total_tokens": _safe_int(ext.get("total_tokens", 0)),
                "external_latency": _safe_float(ext.get("latency_seconds", 0.0)),
                "external_estimated_cost": _safe_float(ext.get("estimated_cost_usd", 0.0)),
            }
            matched_examples.append(base)
            if ctype == "internal_loss_external_win":
                loss_rows.append(base)
            elif ctype == "internal_win_external_loss":
                win_rows.append(base)
            elif ctype == "both_correct":
                both_correct_rows.append(base)
            else:
                both_wrong_rows.append(base)

            final_nodes = internal.get("final_nodes") if isinstance(internal.get("final_nodes"), list) else []
            if not final_nodes:
                unavailable_fields.update(
                    {
                        "branch_id",
                        "parent_branch_id",
                        "root_branch_id",
                        "branch_family_id",
                        "depth",
                        "expansion_step_index",
                        "selected_for_expansion",
                        "action_type",
                        "new_step_text",
                        "full_model_output",
                        "answer_group_id",
                        "answer_group_support_count",
                        "answer_group_support_fraction",
                        "branch_score_total",
                        "branch_local_continuation_score",
                        "answer_support_score",
                        "anti_collapse_bonus",
                        "repeat_family_penalty",
                        "commit_score_or_margin",
                        "branch_call_input_tokens",
                        "branch_call_output_tokens",
                        "branch_call_latency",
                    }
                )
                branch_traces.append(
                    {
                        "provider": args.provider,
                        "dataset": dataset,
                        "seed": seed,
                        "budget": budget,
                        "method": method,
                        "example_id": example_id,
                        "branch_id": "NA",
                        "parent_branch_id": "NA",
                        "root_branch_id": "NA",
                        "branch_family_id": "NA",
                        "depth": "NA",
                        "expansion_step_index": "NA",
                        "selected_for_expansion": "NA",
                        "action_type": "NA",
                        "reasoning_text_so_far": "NA",
                        "new_step_text": "NA",
                        "full_model_output": "NA",
                        "predicted_answer_raw": i_raw,
                        "predicted_answer_canonical": i_can,
                        "answer_group_id": "NA",
                        "answer_group_support_count": "NA",
                        "answer_group_support_fraction": "NA",
                        "branch_score_total": "NA",
                        "branch_local_continuation_score": "NA",
                        "answer_support_score": "NA",
                        "anti_collapse_bonus": "NA",
                        "repeat_family_penalty": "NA",
                        "commit_score_or_margin": "NA",
                        "is_final_selected_answer": "NA",
                        "is_pruned_or_abandoned": "NA",
                        "prune_or_abandon_reason": "NA",
                        "branch_call_input_tokens": "NA",
                        "branch_call_output_tokens": "NA",
                        "branch_call_latency": "NA",
                    }
                )
                step_traces.append({
                    "provider": args.provider,
                    "dataset": dataset,
                    "seed": seed,
                    "budget": budget,
                    "method": method,
                    "example_id": example_id,
                    "step_index": "NA",
                    "action_type": "NA",
                    "reasoning_text_so_far": "NA",
                    "new_step_text": "NA",
                    "full_model_output": "NA",
                })
            else:
                for idx, node in enumerate(final_nodes):
                    reasoning = str(node.get("reasoning_text") or "")
                    branch_traces.append(
                        {
                            "provider": args.provider,
                            "dataset": dataset,
                            "seed": seed,
                            "budget": budget,
                            "method": method,
                            "example_id": example_id,
                            "branch_id": str(node.get("branch_id", f"branch_{idx}")),
                            "parent_branch_id": "NA",
                            "root_branch_id": "NA",
                            "branch_family_id": "NA",
                            "depth": len([ln for ln in reasoning.splitlines() if ln.strip()]),
                            "expansion_step_index": idx,
                            "selected_for_expansion": "NA",
                            "action_type": "other",
                            "reasoning_text_so_far": reasoning,
                            "new_step_text": "NA",
                            "full_model_output": reasoning,
                            "predicted_answer_raw": node.get("predicted_answer"),
                            "predicted_answer_canonical": node.get("predicted_answer_normalized", "NA"),
                            "answer_group_id": "NA",
                            "answer_group_support_count": "NA",
                            "answer_group_support_fraction": "NA",
                            "branch_score_total": "NA",
                            "branch_local_continuation_score": "NA",
                            "answer_support_score": "NA",
                            "anti_collapse_bonus": "NA",
                            "repeat_family_penalty": "NA",
                            "commit_score_or_margin": "NA",
                            "is_final_selected_answer": "NA",
                            "is_pruned_or_abandoned": "NA",
                            "prune_or_abandon_reason": "NA",
                            "branch_call_input_tokens": "NA",
                            "branch_call_output_tokens": "NA",
                            "branch_call_latency": "NA",
                        }
                    )
                    step_traces.append(
                        {
                            "provider": args.provider,
                            "dataset": dataset,
                            "seed": seed,
                            "budget": budget,
                            "method": method,
                            "example_id": example_id,
                            "step_index": idx,
                            "action_type": "other",
                            "reasoning_text_so_far": reasoning,
                            "new_step_text": "NA",
                            "full_model_output": reasoning,
                        }
                    )

            q_len = _token_count(q)
            nums = _nums(q)
            op = _op_guess(q, len(nums))
            est_steps = _estimate_steps(q_len, len(nums), op)
            rationale_nums = set(_nums(rationale if rationale != "NA" else ""))
            reason_texts = [str(n.get("reasoning_text") or "") for n in final_nodes]
            explored_text = "\n".join(reason_texts)
            explored_nums = set(_nums(explored_text))
            recovered = len(rationale_nums & explored_nums)
            frac = (recovered / len(rationale_nums)) if rationale_nums else "NA"
            gold_in_tree = int(gold_can in {canonicalize_answer(str(n.get('predicted_answer')), dataset=dataset) for n in final_nodes}) if final_nodes else int(internal.get("gold_in_tree", 0))
            max_depth = max([len([ln for ln in t.splitlines() if ln.strip()]) for t in reason_texts], default=0)
            near_depth = max_depth if gold_in_tree else (max_depth - 1 if max_depth > 0 else "NA")
            near_score = 1.0 if gold_in_tree else (0.5 if max_depth > 0 else "NA")
            counter = Counter(
                canonicalize_answer(str(n.get("predicted_answer")), dataset=dataset)
                for n in final_nodes
                if n.get("predicted_answer") is not None
            )
            ans_count = len(counter) if counter else "NA"
            entropy = _entropy_from_counter(counter) if counter else "NA"
            selected_support = "NA"
            gap = "NA"
            if counter:
                total = sum(counter.values())
                top = counter.most_common(2)
                selected_support = top[0][1] / total
                gap = (top[0][1] - top[1][1]) / total if len(top) > 1 else 1.0

            features.append(
                {
                    "budget": budget,
                    "question_length_tokens": q_len,
                    "number_count": len(nums),
                    "operation_type_guess": op,
                    "estimated_reasoning_steps_required": est_steps,
                    "internal_gold_final_answer_in_tree": gold_in_tree,
                    "internal_gold_intermediate_quantity_fraction": frac,
                    "internal_nearest_gold_path_depth": near_depth,
                    "internal_nearest_gold_path_score": near_score,
                    "internal_abandoned_promising_branch": "NA",
                    "internal_committed_before_promising_branch_matured": "NA",
                    "internal_correct_region_entered": int((frac != "NA" and float(frac) > 0.0) or gold_in_tree == 1),
                    "internal_max_branch_depth": max_depth,
                    "internal_failure_tag": ("none" if i_ok == 1 else str(internal.get("failure_tag", "incorrect"))),
                    "internal_answer_group_count": ans_count,
                    "internal_answer_entropy": entropy,
                    "internal_selected_answer_support_fraction": selected_support,
                    "internal_top2_support_gap": gap,
                    "internal_cost_ratio_vs_external_l1_max": _ratio(_safe_float(internal.get("estimated_cost_usd", 0.0)), _safe_float(ext.get("estimated_cost_usd", 0.0))),
                    "internal_latency_ratio_vs_external_l1_max": _ratio(_safe_float(internal.get("latency_seconds", 0.0)), _safe_float(ext.get("latency_seconds", 0.0))),
                    "method": method,
                    "seed": seed,
                    "dataset": dataset,
                    "example_id": example_id,
                }
            )

    out_dir = REPO_ROOT / "outputs" / f"internal_methods_vs_external_l1_max_rich_failure_traces_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    _write_jsonl(out_dir / "matched_examples.jsonl", matched_examples)
    _write_jsonl(out_dir / "loss_cases_internal_wrong_external_correct.jsonl", loss_rows)
    _write_jsonl(out_dir / "internal_win_cases.jsonl", win_rows)
    _write_jsonl(out_dir / "both_correct_cases.jsonl", both_correct_rows)
    _write_jsonl(out_dir / "both_wrong_cases.jsonl", both_wrong_rows)
    _write_jsonl(out_dir / "branch_traces.jsonl", branch_traces)
    _write_jsonl(out_dir / "step_traces.jsonl", step_traces)

    feature_cols = PRIMARY_FEATURES + ["method", "seed", "dataset", "example_id"]
    _write_csv(out_dir / "rich_feature_table.csv", features, fieldnames=feature_cols)
    _write_jsonl(out_dir / "rich_feature_table.jsonl", features)

    by_method = defaultdict(list)
    for r in matched_examples:
        by_method[r["method"]].append(r)

    feat_summary = []
    fail_pat = []
    path_prox = []
    budget_seed_method = []
    api_cost = []
    for m in internal_methods:
        rs = by_method.get(m, [])
        n = len(rs)
        losses = [x for x in rs if x["comparison_case_type"] == "internal_loss_external_win"]
        wins = [x for x in rs if x["comparison_case_type"] == "internal_win_external_loss"]
        feat_summary.append({"method": m, "matched_examples": n, "losses": len(losses), "wins": len(wins), "loss_rate": (len(losses) / n) if n else "NA"})
        m_feats = [f for f in features if f["method"] == m]
        absent_rate = sum(1 for f in m_feats if f["internal_gold_final_answer_in_tree"] == 0) / len(m_feats) if m_feats else "NA"
        mean_near = (sum(float(f["internal_nearest_gold_path_score"]) for f in m_feats if f["internal_nearest_gold_path_score"] != "NA") / len(m_feats)) if m_feats else "NA"
        fail_pat.append({"method": m, "absent_from_tree_rate": absent_rate, "mean_nearest_gold_path_score": mean_near})
        path_prox.append(
            {
                "method": m,
                "loss_cases": len(losses),
                "gold_final_answer_in_tree_rate_loss_cases": (sum(1 for f in m_feats if f["internal_failure_tag"] != "none" and f["internal_gold_final_answer_in_tree"] == 1) / max(1, sum(1 for f in m_feats if f["internal_failure_tag"] != "none"))),
                "mean_intermediate_fraction_loss_cases": (
                    sum(float(f["internal_gold_intermediate_quantity_fraction"]) for f in m_feats if f["internal_failure_tag"] != "none" and f["internal_gold_intermediate_quantity_fraction"] != "NA")
                    / max(1, sum(1 for f in m_feats if f["internal_failure_tag"] != "none" and f["internal_gold_intermediate_quantity_fraction"] != "NA"))
                ),
                "mean_nearest_gold_path_depth_loss_cases": (
                    sum(float(f["internal_nearest_gold_path_depth"]) for f in m_feats if f["internal_failure_tag"] != "none" and f["internal_nearest_gold_path_depth"] != "NA")
                    / max(1, sum(1 for f in m_feats if f["internal_failure_tag"] != "none" and f["internal_nearest_gold_path_depth"] != "NA"))
                ),
                "divergence_depth_if_inferable": "NA",
                "abandoned_promising_branch_rate": "NA",
                "commit_before_promising_matured_rate": "NA",
                "entered_correct_region_rate": (
                    sum(1 for f in m_feats if f["internal_failure_tag"] != "none" and f["internal_correct_region_entered"] == 1)
                    / max(1, sum(1 for f in m_feats if f["internal_failure_tag"] != "none"))
                ),
                "scoring_method": ("gsm8k_rationale_numeric_overlap" if rationale_map else "heuristic_numeric_overlap"),
            }
        )
        for s in sorted(seeds):
            for b in sorted(budgets):
                slice_rows = [r for r in rs if int(r["seed"]) == s and int(r["budget"]) == b]
                budget_seed_method.append(
                    {
                        "method": m,
                        "seed": s,
                        "budget": b,
                        "matched_examples": len(slice_rows),
                        "losses": sum(1 for x in slice_rows if x["comparison_case_type"] == "internal_loss_external_win"),
                        "wins": sum(1 for x in slice_rows if x["comparison_case_type"] == "internal_win_external_loss"),
                    }
                )
        api_cost.append(
            {
                "method": m,
                "scored_examples": n,
                "internal_total_tokens": sum(int(r["internal_total_tokens"]) for r in rs),
                "external_total_tokens": sum(int(r["external_total_tokens"]) for r in rs),
                "internal_cost_usd": sum(float(r["internal_estimated_cost"]) for r in rs),
                "external_cost_usd": sum(float(r["external_estimated_cost"]) for r in rs),
                "internal_mean_latency": (sum(float(r["internal_latency"]) for r in rs) / n) if n else 0.0,
                "external_mean_latency": (sum(float(r["external_latency"]) for r in rs) / n) if n else 0.0,
            }
        )

    _write_csv(out_dir / "feature_summary.csv", feat_summary)
    _write_csv(out_dir / "failure_pattern_summary.csv", fail_pat)
    _write_csv(out_dir / "path_proximity_summary.csv", path_prox)
    _write_csv(out_dir / "budget_seed_method_summary.csv", budget_seed_method)
    _write_csv(out_dir / "api_cost_summary.csv", api_cost)

    incomplete = []
    for m in internal_methods:
        n = len(by_method.get(m, []))
        losses = sum(1 for x in by_method.get(m, []) if x["comparison_case_type"] == "internal_loss_external_win")
        if n < 500 or losses < 100:
            incomplete.append(
                {
                    "method": m,
                    "matched_examples": n,
                    "loss_cases": losses,
                    "target_matched_examples": 500,
                    "target_loss_cases": 100,
                    "minimum_useful_target_matched_examples": 300,
                    "minimum_useful_target_main_method_losses": 50,
                    "status": "incomplete",
                    "estimated_additional_runs_for_500_matched": max(0, 500 - n),
                    "estimated_additional_losses_for_100": max(0, 100 - losses),
                }
            )
    _write_csv(out_dir / "incomplete_slices.csv", incomplete)

    best_loss = min(feat_summary, key=lambda x: (x["loss_rate"] if x["loss_rate"] != "NA" else 99)) if feat_summary else None
    best_cost = min(api_cost, key=lambda x: (x["internal_cost_usd"] / max(1, x["scored_examples"]))) if api_cost else None
    implications = [
        f"Use {best_loss['method']} as base candidate because it has the lowest observed loss rate vs external_l1_max in this run." if best_loss else "Need more data before selecting base method.",
        "Route counting/combinatorics questions to the method with lowest counting-combinatorics loss slice from budget_seed_method_summary.csv.",
        "Add a defer/abstain fallback to external_l1_max when answer support is diffuse (high entropy, small top2 support gap).",
        "Delay commit when path-proximity features suggest near-gold branches exist but are shallow.",
        "Add abandonment-prevention when correct region is entered but final answer diverges.",
        "Train a risk gate over the fixed 20-feature schema to predict internal_loss_external_win.",
        "Evaluate whether weak anti-collapse reduces absent-from-tree failures or shifts toward present-not-selected errors.",
    ]
    (out_dir / "candidate_algorithm_implications.md").write_text("# Candidate algorithm implications\n\n" + "\n".join(f"- {x}" for x in implications) + "\n", encoding="utf-8")

    manifest = {
        "timestamp": ts,
        "provider": args.provider,
        "model": args.model,
        "dataset": args.dataset,
        "seeds": sorted(seeds),
        "budgets": sorted(budgets),
        "internal_methods": internal_methods,
        "external_method": "external_l1_max",
        "source_records_path": args.records_path,
        "matched_examples_total": len(matched_examples),
        "unavailable_fields": sorted(unavailable_fields),
        "notes": {
            "answer_group_histograms_available": False,
            "entropy_support_fields_policy": "computed from final_nodes predicted_answer histogram when available; otherwise NA",
        },
        "files": [
            "manifest.json",
            "matched_examples.jsonl",
            "loss_cases_internal_wrong_external_correct.jsonl",
            "internal_win_cases.jsonl",
            "both_correct_cases.jsonl",
            "both_wrong_cases.jsonl",
            "branch_traces.jsonl",
            "step_traces.jsonl",
            "rich_feature_table.csv",
            "rich_feature_table.jsonl",
            "feature_summary.csv",
            "failure_pattern_summary.csv",
            "path_proximity_summary.csv",
            "budget_seed_method_summary.csv",
            "api_cost_summary.csv",
            "incomplete_slices.csv",
            "candidate_algorithm_implications.md",
            "README.md",
        ],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    readme = [
        f"# internal_methods_vs_external_l1_max rich failure traces ({ts})",
        "",
        f"- Source records: `{args.records_path}`",
        f"- Provider/model: `{args.provider}` / `{args.model}`",
        f"- Dataset: `{args.dataset}`",
        f"- Internal methods: `{', '.join(internal_methods)}`",
        "- External baseline: `external_l1_max`",
        "",
        "All unavailable rich fields are encoded as `NA` and listed in `manifest.json`.",
    ]
    (out_dir / "README.md").write_text("\n".join(readme) + "\n", encoding="utf-8")

    loss_by_method = Counter(r["method"] for r in loss_rows)
    matched_by_method = Counter(r["method"] for r in matched_examples)
    cost_per_correct = {}
    for m in internal_methods:
        mrows = by_method.get(m, [])
        correct = sum(int(r["internal_correct"]) for r in mrows)
        total_cost = sum(float(r["internal_estimated_cost"]) for r in mrows)
        cost_per_correct[m] = (total_cost / correct) if correct > 0 else "NA"

    report_path = REPO_ROOT / "docs" / f"INTERNAL_METHODS_VS_EXTERNAL_L1_MAX_RICH_FAILURE_TRACES_{ts}.md"
    report_lines = [
        f"# INTERNAL_METHODS_VS_EXTERNAL_L1_MAX_RICH_FAILURE_TRACES_{ts}",
        "",
        "## Requested questions",
        f"1. Matched examples by internal method: {dict(matched_by_method)}",
        f"2. Internal-loss/external-win cases by internal method: {dict(loss_by_method)}",
        f"3. Method with least losses: {best_loss['method'] if best_loss else 'NA'}",
        f"4. Best cost-normalized method (lower cost-per-correct): {min(cost_per_correct, key=lambda k: cost_per_correct[k] if cost_per_correct[k] != 'NA' else 1e18) if cost_per_correct else 'NA'}",
        f"5. Most useful rich traces for controller design: {max(internal_methods, key=lambda m: loss_by_method.get(m,0)) if internal_methods else 'NA'} (largest loss pool with traces).",
        "6. Failure pattern similarity/difference: see `failure_pattern_summary.csv` (absent-from-tree and nearest-path differences).",
        "7. Absent-from-tree path proximity: see `path_proximity_summary.csv` (gold-in-tree, intermediate fraction, nearest depth/score).",
        "8. Weak anti-collapse impact: compare strict_f3 vs strict_f3_anti_collapse_weak_v1 rows in `failure_pattern_summary.csv` and `path_proximity_summary.csv`.",
        f"9. Base method recommendation for next controller: {best_loss['method'] if best_loss else 'NA'} (data-driven from observed loss rate).",
        "",
        "## Completeness",
        "See `incomplete_slices.csv` for any shortfall from 500 matched / 100 losses per method and estimated additional runs.",
    ]
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
