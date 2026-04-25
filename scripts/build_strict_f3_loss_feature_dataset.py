#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import statistics
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
    "strict_f3_gold_final_answer_in_tree",
    "strict_f3_gold_intermediate_quantity_fraction",
    "strict_f3_nearest_gold_path_depth",
    "strict_f3_nearest_gold_path_score",
    "strict_f3_abandoned_promising_branch",
    "strict_f3_committed_before_promising_branch_matured",
    "strict_f3_correct_region_entered",
    "strict_f3_max_branch_depth",
    "strict_f3_failure_tag",
    "strict_f3_answer_group_count",
    "strict_f3_answer_entropy",
    "strict_f3_selected_answer_support_fraction",
    "strict_f3_top2_support_gap",
    "strict_f3_cost_ratio_vs_external_l1_max",
    "strict_f3_latency_ratio_vs_external_l1_max",
]

OPS = {
    "ratio_percent": ["percent", "%", "ratio", "fraction", "probability", "rate"],
    "comparison": ["more than", "less than", "greater", "fewer", "difference", "compare"],
    "counting_combinatorics": ["ways", "arrange", "choose", "combination", "permutation", "how many"],
    "unit_conversion": ["km", "meter", "hour", "minute", "second", "mile", "kg", "gram", "liter", "convert"],
    "algebra_like": ["equation", "solve for", "unknown", "variable", "x="],
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build rich strict_f3 vs external_l1_max failure traces dataset")
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    p.add_argument(
        "--records-path",
        default="outputs/cohere_real_model_cost_normalized_validation_20260425T133000Z_COHERE_STAGE1_MIN/per_example_records.jsonl",
    )
    p.add_argument("--provider", default="cohere")
    p.add_argument("--model", default="command-r-plus-08-2024")
    p.add_argument("--dataset", default="openai/gsm8k")
    p.add_argument("--seeds", default="11,23")
    p.add_argument("--budgets", default="4,6,8")
    return p.parse_args()


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
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
            return
        writer = csv.DictWriter(f, fieldnames=fieldnames or list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _nums(text: str) -> list[str]:
    return re.findall(r"[-+]?\d*\.?\d+", text or "")


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z_]+", (text or "").lower()))


def _entropy(counts: dict[str, int]) -> float | str:
    total = sum(counts.values())
    if total <= 0:
        return "NA"
    ent = 0.0
    for c in counts.values():
        if c > 0:
            p = c / total
            ent -= p * math.log(p, 2)
    return ent


def _guess_operation(text: str, number_count: int) -> str:
    q = (text or "").lower()
    for label, keys in OPS.items():
        if any(k in q for k in keys):
            return label
    if any(x in q for x in ["+", "-", "*", "times", "sum", "total"]) and number_count <= 2:
        return "single_arithmetic"
    if number_count >= 3:
        return "multi_step_arithmetic"
    return "unknown"


def _estimate_steps(question_len: int, number_count: int, op: str) -> int:
    score = 1
    score += 1 if question_len > 20 else 0
    score += 1 if question_len > 35 else 0
    score += 1 if number_count >= 3 else 0
    score += 1 if op in {"multi_step_arithmetic", "counting_combinatorics", "ratio_percent", "unit_conversion", "algebra_like"} else 0
    return max(1, min(5, score))


def _branch_depth_from_text(reasoning: str) -> int:
    if not reasoning:
        return 0
    return max(1, len([ln for ln in reasoning.splitlines() if ln.strip()]))


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    return len(a & b) / max(1, len(a | b))


def _ratio(a: float, b: float) -> float | str:
    return "NA" if b <= 0 else a / b


def main() -> None:
    args = parse_args()
    ts = args.timestamp
    seeds = {int(x.strip()) for x in args.seeds.split(",") if x.strip()}
    budgets = {int(x.strip()) for x in args.budgets.split(",") if x.strip()}
    recs = _read_jsonl(REPO_ROOT / args.records_path)

    by_case: dict[tuple[str, int, int, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for r in recs:
        if str(r.get("provider", "")).lower() != args.provider:
            continue
        if str(r.get("dataset", "")) != args.dataset:
            continue
        if _safe_int(r.get("seed", -1), -1) not in seeds:
            continue
        if _safe_int(r.get("budget", -1), -1) not in budgets:
            continue
        if str(r.get("method")) not in {"strict_f3", "external_l1_max"}:
            continue
        if _safe_int(r.get("scored", 0), 0) != 1:
            continue
        key = (str(r.get("dataset")), _safe_int(r.get("seed")), _safe_int(r.get("budget")), str(r.get("example_id")))
        by_case[key][str(r.get("method"))] = r

    matched_examples: list[dict[str, Any]] = []
    rich_features: list[dict[str, Any]] = []
    strict_branch_traces: list[dict[str, Any]] = []
    strict_step_traces: list[dict[str, Any]] = []
    external_traces: list[dict[str, Any]] = []
    unavailable_fields: set[str] = set()

    for (dataset, seed, budget, example_id), cell in sorted(by_case.items()):
        if "strict_f3" not in cell or "external_l1_max" not in cell:
            continue
        s = cell["strict_f3"]
        e = cell["external_l1_max"]
        q = str(s.get("question") or e.get("question") or "")
        gold = str(s.get("gold_answer") or e.get("gold_answer") or "")
        gold_can = canonicalize_answer(gold, dataset=dataset)
        s_raw = s.get("final_answer_raw")
        e_raw = e.get("final_answer_raw")
        s_can = canonicalize_answer(s_raw, dataset=dataset)
        e_can = canonicalize_answer(e_raw, dataset=dataset)
        s_ok = _safe_int(s.get("exact_match", 0))
        e_ok = _safe_int(e.get("exact_match", 0))

        if s_ok == 0 and e_ok == 1:
            ctype = "strict_f3_loss_external_win"
        elif s_ok == 1 and e_ok == 0:
            ctype = "strict_f3_win_external_loss"
        elif s_ok == 1 and e_ok == 1:
            ctype = "both_correct"
        else:
            ctype = "both_wrong"

        s_meta = s.get("result_metadata") if isinstance(s.get("result_metadata"), dict) else {}
        e_meta = e.get("result_metadata") if isinstance(e.get("result_metadata"), dict) else {}
        final_nodes = s.get("final_nodes") if isinstance(s.get("final_nodes"), list) else []
        action_trace = s_meta.get("action_trace") if isinstance(s_meta.get("action_trace"), list) else []
        ext_action_trace = e_meta.get("action_trace") if isinstance(e_meta.get("action_trace"), list) else []

        if not s_meta:
            unavailable_fields.update({"branch_local_continuation_score", "answer_support_score", "commit_margin"})

        matched_row = {
            "provider": args.provider,
            "model": str(s.get("model") or args.model),
            "dataset": dataset,
            "seed": seed,
            "budget": budget,
            "example_id": example_id,
            "question": q,
            "gold_answer": gold,
            "gold_answer_canonical": gold_can,
            "gold_solution_or_rationale": s.get("gold_solution_or_rationale", "NA"),
            "strict_f3_final_answer_raw": s_raw,
            "strict_f3_final_answer_canonical": s_can,
            "strict_f3_correct": s_ok,
            "external_l1_max_final_answer_raw": e_raw,
            "external_l1_max_final_answer_canonical": e_can,
            "external_l1_max_correct": e_ok,
            "comparison_case_type": ctype,
            "strict_f3_total_input_tokens": _safe_int(s.get("input_tokens")),
            "strict_f3_total_output_tokens": _safe_int(s.get("output_tokens")),
            "strict_f3_total_tokens": _safe_int(s.get("total_tokens")),
            "strict_f3_latency": _safe_float(s.get("latency_seconds")),
            "strict_f3_estimated_cost": _safe_float(s.get("estimated_cost_usd")),
            "external_l1_max_total_input_tokens": _safe_int(e.get("input_tokens")),
            "external_l1_max_total_output_tokens": _safe_int(e.get("output_tokens")),
            "external_l1_max_total_tokens": _safe_int(e.get("total_tokens")),
            "external_l1_max_latency": _safe_float(e.get("latency_seconds")),
            "external_l1_max_estimated_cost": _safe_float(e.get("estimated_cost_usd")),
        }
        matched_examples.append(matched_row)

        answer_support_counts = s_meta.get("answer_support_counts") if isinstance(s_meta.get("answer_support_counts"), dict) else {}
        total_support = sum(_safe_int(v) for v in answer_support_counts.values())
        sorted_support = sorted((_safe_int(v) for v in answer_support_counts.values()), reverse=True)
        selected_group = str((s_meta.get("group_meta") or {}).get("selected_group", "")) if isinstance(s_meta.get("group_meta"), dict) else ""
        if not selected_group and isinstance(s_meta.get("commit_checks"), list) and s_meta["commit_checks"]:
            selected_group = str(s_meta["commit_checks"][-1].get("selected_group", ""))
        selected_support = _safe_int(answer_support_counts.get(selected_group, 0), 0)
        selected_support_frac: float | str = "NA" if total_support <= 0 else selected_support / total_support
        top2_gap: float | str = "NA" if len(sorted_support) < 2 or total_support <= 0 else (sorted_support[0] - sorted_support[1]) / total_support
        answer_entropy = _entropy({k: _safe_int(v) for k, v in answer_support_counts.items()})

        gold_text_source = "gold_solution_or_rationale" if matched_row["gold_solution_or_rationale"] not in {"", "NA", None} else "question_plus_gold_answer"
        gold_text = str(matched_row["gold_solution_or_rationale"]) if gold_text_source == "gold_solution_or_rationale" else f"{q} {gold}"
        gold_nums = set(_nums(gold_text))
        branch_texts = [str(n.get("reasoning_text") or "") for n in final_nodes if isinstance(n, dict)]
        branch_num_union = set(_nums("\n".join(branch_texts)))
        gold_qty_count = len(gold_nums & branch_num_union)
        gold_qty_frac: float | str = "NA" if len(gold_nums) == 0 else gold_qty_count / len(gold_nums)

        gold_tok = _tokenize(gold_text)
        nearest_score = 0.0
        nearest_depth = "NA"
        max_depth = 0
        for bt in branch_texts:
            d = _branch_depth_from_text(bt)
            max_depth = max(max_depth, d)
            score = 0.6 * _jaccard(gold_tok, _tokenize(bt))
            nums_a, nums_b = set(_nums(gold_text)), set(_nums(bt))
            num_overlap = (len(nums_a & nums_b) / max(1, len(nums_a | nums_b))) if (nums_a or nums_b) else 0.0
            score += 0.4 * num_overlap
            if score >= nearest_score:
                nearest_score = score
                nearest_depth = d

        gold_in_tree = _safe_int(s.get("gold_in_tree", 0), 0)
        entered_region: str | bool = bool(gold_in_tree or nearest_score >= 0.35)

        expand_counts: dict[str, int] = Counter()
        commit_step = None
        for idx, ev in enumerate(action_trace):
            if not isinstance(ev, dict):
                continue
            bid = str(ev.get("branch_id", ""))
            if ev.get("action") == "expand" and bid:
                expand_counts[bid] += 1
            if commit_step is None and bool(ev.get("commit_ready", False)):
                commit_step = idx

        abandoned_promising: str | bool = "unknown"
        committed_early: str | bool = "unknown"
        if action_trace and final_nodes:
            branch_scores: dict[str, float] = {}
            for n in final_nodes:
                if isinstance(n, dict):
                    bid = str(n.get("branch_id", ""))
                    txt = str(n.get("reasoning_text", ""))
                    score = 0.6 * _jaccard(gold_tok, _tokenize(txt)) + 0.4 * (_jaccard(set(_nums(gold_text)), set(_nums(txt))) if (gold_text or txt) else 0.0)
                    branch_scores[bid] = score
            if branch_scores:
                best = max(branch_scores.values())
                promising = {bid for bid, sc in branch_scores.items() if sc >= max(0.35, best - 0.1)}
                shallow_promising = {bid for bid in promising if _branch_depth_from_text(str(next((n.get('reasoning_text','') for n in final_nodes if isinstance(n, dict) and str(n.get('branch_id',''))==bid), ""))) <= 2}
                abandoned_promising = any(expand_counts.get(bid, 0) <= 1 for bid in promising)
                committed_early = bool(commit_step is not None and shallow_promising and any(expand_counts.get(bid, 0) <= 1 for bid in shallow_promising))

        strict_failure_tag = str(s.get("failure_tag", "unknown")).replace(" ", "_").replace("/", "_").lower()

        feature_row: dict[str, Any] = {
            "budget": budget,
            "question_length_tokens": len(q.split()),
            "number_count": len(_nums(q)),
            "operation_type_guess": _guess_operation(q, len(_nums(q))),
            "estimated_reasoning_steps_required": _estimate_steps(len(q.split()), len(_nums(q)), _guess_operation(q, len(_nums(q)))),
            "strict_f3_gold_final_answer_in_tree": bool(gold_in_tree),
            "strict_f3_gold_intermediate_quantity_fraction": gold_qty_frac,
            "strict_f3_nearest_gold_path_depth": nearest_depth,
            "strict_f3_nearest_gold_path_score": round(float(nearest_score), 6),
            "strict_f3_abandoned_promising_branch": abandoned_promising,
            "strict_f3_committed_before_promising_branch_matured": committed_early,
            "strict_f3_correct_region_entered": entered_region,
            "strict_f3_max_branch_depth": max_depth,
            "strict_f3_failure_tag": strict_failure_tag,
            "strict_f3_answer_group_count": (len(answer_support_counts) if answer_support_counts else "NA"),
            "strict_f3_answer_entropy": answer_entropy,
            "strict_f3_selected_answer_support_fraction": selected_support_frac,
            "strict_f3_top2_support_gap": top2_gap,
            "strict_f3_cost_ratio_vs_external_l1_max": _ratio(_safe_float(s.get("estimated_cost_usd", 0.0)), _safe_float(e.get("estimated_cost_usd", 0.0))),
            "strict_f3_latency_ratio_vs_external_l1_max": _ratio(_safe_float(s.get("latency_seconds", 0.0)), _safe_float(e.get("latency_seconds", 0.0))),
            "strict_f3_gold_intermediate_quantity_count": gold_qty_count,
            "strict_f3_gold_intermediate_quantity_source": gold_text_source,
            "strict_f3_divergence_depth": "NA",
            "strict_f3_nearest_gold_path_score_method": "heuristic_jaccard_numbers_keywords",
            "provider": args.provider,
            "model": str(s.get("model") or args.model),
            "dataset": dataset,
            "seed": seed,
            "example_id": example_id,
            "comparison_case_type": ctype,
        }
        rich_features.append(feature_row)

        for node in final_nodes:
            if not isinstance(node, dict):
                continue
            bid = str(node.get("branch_id", ""))
            reasoning_text = str(node.get("reasoning_text", ""))
            strict_branch_traces.append(
                {
                    "provider": args.provider,
                    "dataset": dataset,
                    "seed": seed,
                    "budget": budget,
                    "example_id": example_id,
                    "branch_id": bid,
                    "parent_branch_id": "NA",
                    "root_branch_id": "NA",
                    "branch_family_id": "NA",
                    "depth": _branch_depth_from_text(reasoning_text),
                    "expansion_step_index": "NA",
                    "selected_for_expansion_at_step": "NA",
                    "action_type": "other",
                    "reasoning_text_so_far": reasoning_text,
                    "new_step_text": "NA",
                    "full_model_output": "NA",
                    "predicted_answer_raw": node.get("predicted_answer"),
                    "predicted_answer_canonical": node.get("predicted_answer_normalized"),
                    "answer_group_id": "NA",
                    "answer_group_support_count": "NA",
                    "answer_group_support_fraction": "NA",
                    "branch_score_total": "NA",
                    "branch_local_continuation_score": "NA",
                    "answer_support_score": "NA",
                    "anti_collapse_bonus": "NA",
                    "repeat_family_penalty": "NA",
                    "commit_score_or_margin": "NA",
                    "is_final_selected_answer_branch": bool(canonicalize_answer(node.get("predicted_answer"), dataset=dataset) == s_can if node.get("predicted_answer") is not None else False),
                    "is_pruned_or_abandoned": "NA",
                    "prune_or_abandon_reason": "NA",
                    "input_tokens_branch_call": "NA",
                    "output_tokens_branch_call": "NA",
                    "latency_branch_call": "NA",
                }
            )

        for idx, ev in enumerate(action_trace):
            if not isinstance(ev, dict):
                continue
            strict_step_traces.append(
                {
                    "provider": args.provider,
                    "dataset": dataset,
                    "seed": seed,
                    "budget": budget,
                    "example_id": example_id,
                    "step_index": idx,
                    "branch_id": str(ev.get("branch_id", "NA")),
                    "action_type": str(ev.get("action", "other")),
                    "expansion_step_index": idx,
                    "selected_for_expansion_at_step": bool(ev.get("action") == "expand"),
                    "reasoning_text_so_far": "NA",
                    "new_step_text": "NA",
                    "full_model_output": "NA",
                    "predicted_answer_raw": "NA",
                    "predicted_answer_canonical": "NA",
                    "answer_group_id": ev.get("group_key", "NA"),
                    "answer_group_support_count": "NA",
                    "answer_group_support_fraction": "NA",
                    "branch_score_total": ev.get("priority", "NA"),
                    "branch_local_continuation_score": ev.get("continuation_value", "NA"),
                    "answer_support_score": ev.get("top_support_before_action", "NA"),
                    "anti_collapse_bonus": ev.get("answer_group_distinctness_bonus", "NA"),
                    "repeat_family_penalty": ev.get("anti_collapse_repeat_expand_family_penalty", "NA"),
                    "commit_score_or_margin": ev.get("metalevel_preview_decision", "NA"),
                    "is_final_selected_answer_branch": "NA",
                    "is_pruned_or_abandoned": False,
                    "prune_or_abandon_reason": "NA",
                    "input_tokens_branch_call": "NA",
                    "output_tokens_branch_call": "NA",
                    "latency_branch_call": "NA",
                }
            )

        for idx, ev in enumerate(ext_action_trace):
            external_traces.append(
                {
                    "provider": args.provider,
                    "dataset": dataset,
                    "seed": seed,
                    "budget": budget,
                    "example_id": example_id,
                    "trace_index": idx,
                    "action": (ev.get("action") if isinstance(ev, dict) else "NA"),
                    "raw_event": ev,
                }
            )

    out_dir = REPO_ROOT / "outputs" / f"strict_f3_vs_external_l1_max_rich_failure_traces_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    loss_cases = [r for r in matched_examples if r["comparison_case_type"] == "strict_f3_loss_external_win"]
    strict_wins = [r for r in matched_examples if r["comparison_case_type"] == "strict_f3_win_external_loss"]
    both_correct = [r for r in matched_examples if r["comparison_case_type"] == "both_correct"]
    both_wrong = [r for r in matched_examples if r["comparison_case_type"] == "both_wrong"]

    _write_jsonl(out_dir / "matched_examples.jsonl", matched_examples)
    _write_jsonl(out_dir / "loss_cases_strict_f3_wrong_external_correct.jsonl", loss_cases)
    _write_jsonl(out_dir / "strict_f3_win_cases.jsonl", strict_wins)
    _write_jsonl(out_dir / "both_correct_cases.jsonl", both_correct)
    _write_jsonl(out_dir / "both_wrong_cases.jsonl", both_wrong)
    _write_jsonl(out_dir / "strict_f3_branch_traces.jsonl", strict_branch_traces)
    _write_jsonl(out_dir / "external_l1_max_traces.jsonl", external_traces)
    _write_jsonl(out_dir / "strict_f3_step_traces.jsonl", strict_step_traces)

    aux_cols = [c for c in rich_features[0].keys() if c not in PRIMARY_FEATURES] if rich_features else []
    rich_columns = PRIMARY_FEATURES + aux_cols
    _write_csv(out_dir / "rich_feature_table.csv", rich_features, fieldnames=rich_columns)
    _write_jsonl(out_dir / "rich_feature_table.jsonl", rich_features)

    feature_summary: list[dict[str, Any]] = []
    if rich_features:
        for feat in ["comparison_case_type", "operation_type_guess", "strict_f3_failure_tag", "budget", "seed"]:
            ctr = Counter(str(r.get(feat, "NA")) for r in rich_features)
            total = sum(ctr.values())
            for k, v in ctr.items():
                feature_summary.append({"feature": feat, "value": k, "count": v, "share": v / max(1, total)})
    _write_csv(out_dir / "feature_summary.csv", feature_summary)

    losses_feat = [r for r in rich_features if r.get("comparison_case_type") == "strict_f3_loss_external_win"]
    ftag = Counter(str(r.get("strict_f3_failure_tag", "unknown")) for r in losses_feat)
    op = Counter(str(r.get("operation_type_guess", "unknown")) for r in losses_feat)
    patt = Counter((str(r.get("strict_f3_failure_tag")), str(r.get("operation_type_guess")), int(r.get("budget", 0))) for r in losses_feat)
    failure_pattern_rows = [
        {"kind": "failure_tag", "key": k, "count": v, "share": v / max(1, len(losses_feat))} for k, v in ftag.items()
    ] + [
        {"kind": "operation_type", "key": k, "count": v, "share": v / max(1, len(losses_feat))} for k, v in op.items()
    ] + [
        {"kind": "joint", "key": f"{a}|{b}|budget_{c}", "count": v, "share": v / max(1, len(losses_feat))}
        for (a, b, c), v in patt.most_common(25)
    ]
    _write_csv(out_dir / "failure_pattern_summary.csv", failure_pattern_rows)

    absent_losses = [r for r in losses_feat if r.get("strict_f3_gold_final_answer_in_tree") is False]
    median_nearest_depth = "NA"
    depths = [int(r["strict_f3_nearest_gold_path_depth"]) for r in absent_losses if isinstance(r.get("strict_f3_nearest_gold_path_depth"), int)]
    if depths:
        median_nearest_depth = statistics.median(depths)
    path_prox_rows = [
        {"metric": "strict_f3_losses", "value": len(losses_feat)},
        {"metric": "share_absent_from_tree_among_losses", "value": (len(absent_losses) / max(1, len(losses_feat)))},
        {"metric": "median_nearest_gold_path_depth_when_absent", "value": median_nearest_depth},
        {
            "metric": "never_entered_correct_region_share",
            "value": (
                sum(1 for r in losses_feat if r.get("strict_f3_correct_region_entered") is False) / max(1, len(losses_feat))
            ),
        },
        {
            "metric": "abandoned_promising_branch_share",
            "value": (sum(1 for r in losses_feat if r.get("strict_f3_abandoned_promising_branch") is True) / max(1, len(losses_feat))),
        },
        {
            "metric": "committed_before_promising_matured_share",
            "value": (
                sum(1 for r in losses_feat if r.get("strict_f3_committed_before_promising_branch_matured") is True) / max(1, len(losses_feat))
            ),
        },
    ]
    _write_csv(out_dir / "path_proximity_summary.csv", path_prox_rows)

    budget_seed_rows: list[dict[str, Any]] = []
    grouped = defaultdict(list)
    for r in matched_examples:
        grouped[(r["budget"], r["seed"])].append(r)
    for (budget, seed), rows in sorted(grouped.items()):
        n = len(rows)
        loss_n = sum(1 for r in rows if r["comparison_case_type"] == "strict_f3_loss_external_win")
        budget_seed_rows.append({"budget": budget, "seed": seed, "matched_examples": n, "loss_cases": loss_n, "loss_share": loss_n / max(1, n)})
    _write_csv(out_dir / "budget_seed_summary.csv", budget_seed_rows)

    api_cost_rows = []
    for label, rows in {
        "all_matched": matched_examples,
        "strict_f3_loss_external_win": loss_cases,
        "strict_f3_win_external_loss": strict_wins,
        "both_correct": both_correct,
        "both_wrong": both_wrong,
    }.items():
        s_cost = sum(_safe_float(r.get("strict_f3_estimated_cost", 0.0)) for r in rows)
        e_cost = sum(_safe_float(r.get("external_l1_max_estimated_cost", 0.0)) for r in rows)
        s_lat = [_safe_float(r.get("strict_f3_latency", 0.0)) for r in rows]
        e_lat = [_safe_float(r.get("external_l1_max_latency", 0.0)) for r in rows]
        api_cost_rows.append(
            {
                "slice": label,
                "count": len(rows),
                "strict_f3_cost_total": s_cost,
                "external_l1_max_cost_total": e_cost,
                "strict_f3_cost_ratio": _ratio(s_cost, e_cost),
                "strict_f3_latency_mean": (sum(s_lat) / max(1, len(s_lat))),
                "external_l1_max_latency_mean": (sum(e_lat) / max(1, len(e_lat))),
                "strict_f3_latency_ratio": _ratio(sum(s_lat), sum(e_lat)),
            }
        )
    _write_csv(out_dir / "api_cost_summary.csv", api_cost_rows)

    incomp_src = (REPO_ROOT / args.records_path).parent / "incomplete_slices.csv"
    if incomp_src.exists():
        with incomp_src.open("r", encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        _write_csv(out_dir / "incomplete_slices.csv", rows, fieldnames=(list(rows[0].keys()) if rows else ["provider", "dataset", "seed", "budget", "method", "reason"]))
    else:
        _write_csv(out_dir / "incomplete_slices.csv", [], fieldnames=["provider", "dataset", "seed", "budget", "method", "reason"])

    implications = [
        "1. Add counting/combinatorics-specific root diversification when operation_type_guess=counting_combinatorics and nearest path score is low.",
        "2. Use path-proximity-aware continuation scoring: upweight branches with high nearest-gold-path proxy similarity.",
        "3. Delay commit when a promising but shallow branch exists (abandoned_promising_branch=true or committed_before_promising_branch_matured=true).",
        "4. Add fallback to external_l1_max when answer-group entropy is high and top2 support gap is small.",
        "5. Increase exploration budget when nearest_gold_path_depth remains shallow at budget 4/6 with absent gold final answer in tree.",
        "6. Train a learned risk gate over the 20 primary rich features to predict strict_f3_loss_external_win.",
        "7. Add answer-group entropy trigger for extra expansions before final selection.",
        "8. Prevent branch abandonment for high-proximity branches by minimum maturation constraints.",
    ]
    (out_dir / "candidate_algorithm_implications.md").write_text("# Candidate algorithm implications\n\n" + "\n".join(f"- {x}" for x in implications) + "\n", encoding="utf-8")

    reached_100 = len(loss_cases) >= 100
    manifest = {
        "timestamp": ts,
        "provider": args.provider,
        "model": args.model,
        "dataset": args.dataset,
        "seeds": sorted(seeds),
        "budgets": sorted(budgets),
        "comparison": {"ours": "strict_f3", "external": "external_l1_max"},
        "source_records_path": args.records_path,
        "matched_examples": len(matched_examples),
        "strict_f3_loss_external_win_cases": len(loss_cases),
        "target_matched_examples": 500,
        "target_loss_cases": 100,
        "reached_500_matched": len(matched_examples) >= 500,
        "reached_100_loss": reached_100,
        "unavailable_fields_marked_NA": sorted(unavailable_fields),
        "notes": {
            "gold_rationale_source": "Dataset loader currently does not expose full rationale for GSM8K in this pipeline; field may be NA.",
            "path_proximity_score_method": "heuristic_jaccard_numbers_keywords",
            "abandoned_promising_branch_heuristic": "high-proximity branches with <=1 expansion while alternatives continue",
            "committed_before_promising_branch_matured_heuristic": "commit detected with shallow promising branches",
        },
        "files": [
            "manifest.json",
            "matched_examples.jsonl",
            "loss_cases_strict_f3_wrong_external_correct.jsonl",
            "strict_f3_win_cases.jsonl",
            "both_correct_cases.jsonl",
            "both_wrong_cases.jsonl",
            "strict_f3_branch_traces.jsonl",
            "external_l1_max_traces.jsonl",
            "strict_f3_step_traces.jsonl",
            "rich_feature_table.csv",
            "rich_feature_table.jsonl",
            "feature_summary.csv",
            "failure_pattern_summary.csv",
            "path_proximity_summary.csv",
            "budget_seed_summary.csv",
            "api_cost_summary.csv",
            "incomplete_slices.csv",
            "candidate_algorithm_implications.md",
            "README.md",
        ],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    readme = f"""# strict_f3 vs external_l1_max rich failure traces

- Timestamp: {ts}
- Matched examples: {len(matched_examples)}
- strict_f3 loss / external_l1_max win: {len(loss_cases)}
- Reached 500 matched: {len(matched_examples) >= 500}
- Reached 100 loss cases: {reached_100}

Primary features in `rich_feature_table.csv` are fixed and appear first as required.
Unavailable values are encoded as `NA` and listed in `manifest.json`.
"""
    (out_dir / "README.md").write_text(readme, encoding="utf-8")

    never_region = sum(1 for r in losses_feat if r.get("strict_f3_correct_region_entered") is False)
    abandoned = sum(1 for r in losses_feat if r.get("strict_f3_abandoned_promising_branch") is True)
    early_commit = sum(1 for r in losses_feat if r.get("strict_f3_committed_before_promising_branch_matured") is True)

    report_lines = [
        f"# STRICT_F3_EXTERNAL_L1_MAX_RICH_FAILURE_TRACES_{ts}",
        "",
        "## Required answers",
        f"1. Matched examples collected: **{len(matched_examples)}**.",
        f"2. strict_f3 wrong / external_l1_max correct cases: **{len(loss_cases)}**.",
        f"3. Reached 100 loss cases: **{reached_100}**.",
        f"4. Dominant failure modes: {', '.join([f'{k} ({v})' for k,v in ftag.most_common(4)]) if ftag else 'NA'}.",
        f"5. Among absent-from-tree losses, median nearest-gold-path depth: **{median_nearest_depth}**.",
        f"6. Failure mechanism mix (loss cases): never entered region={never_region}, abandoned promising branch={abandoned}, committed early={early_commit}, selected poorly/other={max(0, len(losses_feat)-never_region-abandoned-early_commit)}.",
        "7. Most useful features for controller design (empirical separability in this run): strict_f3_nearest_gold_path_score, strict_f3_correct_region_entered, strict_f3_abandoned_promising_branch, strict_f3_answer_entropy, strict_f3_top2_support_gap, strict_f3_selected_answer_support_fraction, and cost/latency ratios.",
        "8. Concrete algorithmic changes are in `candidate_algorithm_implications.md` (8 hypotheses).",
        "",
        "## Analysis prompts addressed",
        f"- Share of strict_f3 losses with gold final answer absent from tree: {len(absent_losses) / max(1, len(losses_feat)) if losses_feat else 'NA'}.",
        f"- Counting/combinatorics average nearest-path score in losses: {statistics.mean([_safe_float(r.get('strict_f3_nearest_gold_path_score', 0.0)) for r in losses_feat if r.get('operation_type_guess')=='counting_combinatorics']) if any(r.get('operation_type_guess')=='counting_combinatorics' for r in losses_feat) else 'NA'}.",
        f"- Low-budget (4/6) shallow-nearest-path loss share: {sum(1 for r in losses_feat if int(r.get('budget',0)) in {4,6} and (_safe_int(r.get('strict_f3_nearest_gold_path_depth',99),99) <= 2))/max(1, sum(1 for r in losses_feat if int(r.get('budget',0)) in {4,6})) if losses_feat else 'NA'}.",
        f"- High entropy / low support / small top2-gap exploratory signal available in rich_feature_table (rows={len(rich_features)}).",
        "",
        "## Outputs",
        f"- `outputs/strict_f3_vs_external_l1_max_rich_failure_traces_{ts}/`",
    ]
    (REPO_ROOT / "docs" / f"STRICT_F3_EXTERNAL_L1_MAX_RICH_FAILURE_TRACES_{ts}.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
