#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

INTERNAL_METHODS_DEFAULT = [
    "strict_f3",
    "strict_gate1_cap_k6",
    "strict_f3_anti_collapse_weak_v1",
    "direct_reserve_frontier_gate_v1",
]
EXTERNAL_METHODS_DEFAULT = ["external_l1_max", "s1", "tale"]
DATASETS_DEFAULT = ["openai/gsm8k", "natural_plan", "gpqa_diamond"]
BUDGETS_DEFAULT = [4, 6, 8]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build Cohere absent-from-tree loss diagnostics from existing artifacts.")
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    p.add_argument("--provider", default="cohere")
    p.add_argument("--output-root", default="outputs")
    return p.parse_args()


def read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
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


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def safe_int(v: Any, default: int = 0) -> int:
    try:
        if isinstance(v, str) and v.strip().upper() == "NA":
            return default
        return int(float(v))
    except Exception:
        return default


def safe_float(v: Any, default: float = 0.0) -> float:
    try:
        if isinstance(v, str) and v.strip().upper() == "NA":
            return default
        return float(v)
    except Exception:
        return default


def canonical_answer(x: Any) -> str:
    s = str(x or "").strip().lower()
    s = s.replace("\\boxed{", "").replace("}", "")
    s = re.sub(r"[^0-9a-z\.\-\+/% ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    if s.endswith("%"):
        s = s[:-1].strip()
    return s


def normalize_method_name(method: str) -> str:
    m = str(method or "").strip()
    if m in {"direct_reserve_strong_plus_diverse_margin_gated_v1", "direct_reserve_frontier_gate_v1"}:
        return "direct_reserve_frontier_gate_v1"
    if m in {"external_tale_prompt_budgeting"}:
        return "tale"
    if m in {"external_s1_budget_forcing"}:
        return "s1"
    return m


def problem_type(question: str) -> str:
    q = question.lower()
    if any(k in q for k in ["percent", "%", "probability", "ratio", "fraction"]):
        return "ratio_percent"
    if any(k in q for k in ["how many", "count", "ways", "arrange", "combination", "permutation"]):
        return "counting"
    if any(k in q for k in ["hour", "minute", "day", "week", "km", "mile", "kg", "meter"]):
        return "units_time_rate"
    if any(k in q for k in ["equation", "solve", "x", "unknown"]):
        return "algebraic"
    return "arithmetic_other"


def split_steps(text: str) -> list[str]:
    raw = re.split(r"[.\n;]+", text or "")
    out = [r.strip().lower() for r in raw if r.strip()]
    return out


def text_similarity(a: str, b: str) -> float:
    ta = set(re.findall(r"[a-z0-9]+", a.lower()))
    tb = set(re.findall(r"[a-z0-9]+", b.lower()))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(1, len(ta | tb))


def load_gsm8k_rationale_map() -> dict[str, str]:
    try:
        from datasets import load_dataset  # type: ignore
    except Exception:
        return {}
    out: dict[str, str] = {}
    for split in ("train", "test"):
        try:
            ds = load_dataset("openai/gsm8k", "main", split=split)
        except Exception:
            continue
        for row in ds:
            q = str(row.get("question", "")).strip()
            a = str(row.get("answer", "")).strip()
            if q and a and q not in out:
                out[q] = a
    return out


def build_index_key(provider: str, model: str, dataset: str, seed: int, budget: int, example_id: str, method: str) -> tuple[str, str, str, int, int, str, str]:
    return (provider, model, dataset, seed, budget, example_id, method)


def main() -> None:
    args = parse_args()
    ts = args.timestamp
    output_dir = REPO_ROOT / args.output_root / f"cohere_absent_from_tree_loss_diagnostics_{ts}"
    output_dir.mkdir(parents=True, exist_ok=True)

    provider = args.provider
    model_default = "command-r-plus-08-2024"

    records: dict[tuple[str, str, str, int, int, str, str], dict[str, Any]] = {}
    candidate_rows: dict[tuple[str, str, str, int, int, str, str], list[dict[str, Any]]] = defaultdict(list)
    source_files: list[str] = []

    # Source 1: broad real-model validation artifacts.
    for csv_path in sorted((REPO_ROOT / "outputs").glob("real_model_ours_vs_external_validation_*/cohere/per_example_rows.csv")):
        source_files.append(str(csv_path.relative_to(REPO_ROOT)))
        for r in read_csv(csv_path):
            p = str(r.get("provider", "")).lower().strip()
            if p != provider:
                continue
            dataset = str(r.get("dataset", "")).strip()
            seed = safe_int(r.get("seed", -1), -1)
            budget = safe_int(r.get("budget", -1), -1)
            method = normalize_method_name(str(r.get("method", "")).strip())
            model = str(r.get("model", model_default)).strip() or model_default
            example_id = str(r.get("example_id", "")).strip()
            if not example_id:
                continue
            k = build_index_key(provider, model, dataset, seed, budget, example_id, method)
            if k not in records:
                records[k] = {}
            records[k].update(
                {
                    "provider": provider,
                    "model": model,
                    "dataset": dataset,
                    "seed": seed,
                    "budget": budget,
                    "example_id": example_id,
                    "method": method,
                    "is_correct": safe_int(r.get("is_correct", 0)),
                    "failure_tag": str(r.get("failure_type", "unknown")),
                    "absent_from_tree_flag": safe_int(r.get("absent_from_tree", 0)),
                    "present_not_selected_flag": safe_int(r.get("present_not_selected", 0)),
                    "question": str(r.get("question", "")) if r.get("question") is not None else "",
                    "gold_answer": str(r.get("gold_answer", "")) if r.get("gold_answer") is not None else "",
                    "final_answer_raw": str(r.get("final_selected_answer", "")) if r.get("final_selected_answer") is not None else "",
                    "final_answer_canonical": canonical_answer(r.get("normalized_selected_answer", r.get("final_selected_answer", ""))),
                    "candidate_branch_count": safe_int(r.get("actions_used", 0)),
                    "answer_group_count": safe_int(r.get("expansions", 0)),
                    "top2_support_gap": safe_float(r.get("top2_support_gap", 0.0), 0.0),
                    "answer_entropy": safe_float(r.get("answer_entropy", 0.0), 0.0),
                    "token_estimate": safe_float(r.get("token_estimate", 0.0), 0.0),
                    "cost_estimate": safe_float(r.get("cost_estimate", 0.0), 0.0),
                    "latency_seconds": safe_float(r.get("latency_seconds", 0.0), 0.0),
                }
            )

    # Source 2: rich direct-reserve validation artifacts.
    for csv_path in sorted((REPO_ROOT / "outputs").glob("cohere_direct_reserve_validation_*/per_case_method_results.csv")):
        source_files.append(str(csv_path.relative_to(REPO_ROOT)))
        for r in read_csv(csv_path):
            p = str(r.get("provider", "")).lower().strip()
            if p != provider:
                continue
            dataset = str(r.get("dataset", "")).strip()
            seed = safe_int(r.get("seed", -1), -1)
            budget = safe_int(r.get("budget", -1), -1)
            method = normalize_method_name(str(r.get("method", "")).strip())
            model = str(r.get("model", model_default)).strip() or model_default
            example_id = str(r.get("example_id", "")).strip()
            if not example_id:
                continue
            k = build_index_key(provider, model, dataset, seed, budget, example_id, method)
            if k not in records:
                records[k] = {}
            records[k].update(
                {
                    "provider": provider,
                    "model": model,
                    "dataset": dataset,
                    "seed": seed,
                    "budget": budget,
                    "example_id": example_id,
                    "method": method,
                    "question": str(r.get("question", "")),
                    "gold_answer": str(r.get("gold_answer", "")),
                    "is_correct": safe_int(r.get("is_correct", 0)),
                    "failure_tag": str(r.get("failure_type", "unknown")),
                    "absent_from_tree_flag": safe_int(r.get("absent_from_pool", 0)),
                    "gold_in_tree_flag": safe_int(r.get("gold_present", 0)),
                    "gold_selected_flag": safe_int(r.get("gold_selected", 0)),
                    "present_not_selected_flag": safe_int(r.get("present_not_selected", 0)),
                    "final_answer_raw": str(r.get("final_selected_answer", "")),
                    "final_answer_canonical": canonical_answer(r.get("normalized_selected_answer", r.get("final_selected_answer", ""))),
                    "candidate_branch_count": safe_int(r.get("candidate_branch_count", 0)),
                    "answer_group_count": safe_int(r.get("answer_group_count", 0)),
                    "selected_answer_group": str(r.get("selected_answer_group", "")),
                    "top_answer_group": str(r.get("top_answer_group", "")),
                    "top2_support_gap": safe_float(r.get("top2_support_gap", 0.0), 0.0),
                    "answer_entropy": safe_float(r.get("answer_entropy", 0.0), 0.0),
                    "token_estimate": safe_float(r.get("token_estimate", 0.0), 0.0),
                    "cost_estimate": safe_float(r.get("cost_estimate", 0.0), 0.0),
                    "latency_seconds": safe_float(r.get("latency_seconds", 0.0), 0.0),
                }
            )

    for csv_path in sorted((REPO_ROOT / "outputs").glob("cohere_direct_reserve_validation_*/candidate_branch_table.csv")):
        source_files.append(str(csv_path.relative_to(REPO_ROOT)))
        for r in read_csv(csv_path):
            p = str(r.get("provider", "")).lower().strip()
            if p != provider:
                continue
            dataset = str(r.get("dataset", "")).strip()
            seed = safe_int(r.get("seed", -1), -1)
            budget = safe_int(r.get("budget", -1), -1)
            method = normalize_method_name(str(r.get("method", "")).strip())
            model = str(r.get("model", model_default)).strip() or model_default
            example_id = str(r.get("example_id", "")).strip()
            if not example_id:
                continue
            k = build_index_key(provider, model, dataset, seed, budget, example_id, method)
            candidate_rows[k].append(r)

    rationale_map = load_gsm8k_rationale_map()

    # Group by case for pairwise comparisons.
    by_case: dict[tuple[str, str, str, int, int, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for k, v in records.items():
        case_key = k[:6]
        by_case[case_key][v["method"]] = v

    internal_methods = set(INTERNAL_METHODS_DEFAULT)
    external_methods = set(EXTERNAL_METHODS_DEFAULT)
    datasets_allow = set(DATASETS_DEFAULT)
    budgets_allow = set(BUDGETS_DEFAULT)

    loss_rows: list[dict[str, Any]] = []
    matched_comparisons = 0
    wrong_vs_correct = 0
    confirmed_absent = 0
    unverified_absent = 0
    trace_available_count = 0

    for case_key, method_map in sorted(by_case.items()):
        provider_k, model_k, dataset, seed, budget, example_id = case_key
        if dataset not in datasets_allow or budget not in budgets_allow:
            continue
        int_present = [m for m in internal_methods if m in method_map]
        ext_present = [m for m in external_methods if m in method_map]
        if not int_present or not ext_present:
            continue

        for im in int_present:
            for em in ext_present:
                irow = method_map[im]
                erow = method_map[em]
                matched_comparisons += 1
                if safe_int(irow.get("is_correct", 0)) == 0 and safe_int(erow.get("is_correct", 0)) == 1:
                    wrong_vs_correct += 1
                    cands = candidate_rows.get(build_index_key(provider_k, model_k, dataset, seed, budget, example_id, im), [])
                    if cands:
                        trace_available_count += 1
                    candidate_answers = []
                    reasoning_snippets = []
                    max_depth = 0
                    branch_ids = []
                    family_ids = []
                    for c in cands:
                        p_raw = str(c.get("predicted_answer", "")).strip()
                        p_can = canonical_answer(c.get("normalized_candidate_answer", p_raw))
                        candidate_answers.append({"raw": p_raw, "canonical": p_can})
                        reasoning = str(c.get("reasoning_text", "") or c.get("raw_branch_text", "")).strip()
                        if reasoning:
                            reasoning_snippets.append(reasoning)
                        d = safe_int(c.get("branch_depth", 0), 0)
                        max_depth = max(max_depth, d)
                        branch_ids.append(str(c.get("branch_id", "")))
                        family_ids.append(str(c.get("branch_prompt_style", "")))

                    gold_raw = str(irow.get("gold_answer", "") or erow.get("gold_answer", ""))
                    gold_can = canonical_answer(gold_raw)
                    i_final_raw = str(irow.get("final_answer_raw", ""))
                    e_final_raw = str(erow.get("final_answer_raw", ""))
                    i_final_can = canonical_answer(irow.get("final_answer_canonical", i_final_raw))
                    e_final_can = canonical_answer(erow.get("final_answer_canonical", e_final_raw))

                    # strongest absent-from-tree evidence first
                    failure_tag = str(irow.get("failure_tag", "unknown"))
                    absent_confirm = False
                    absent_unverified = False
                    gold_in_tree: str | int = "unknown"

                    if "absent" in failure_tag.lower():
                        absent_confirm = True
                    if safe_int(irow.get("absent_from_tree_flag", 0), 0) == 1:
                        absent_confirm = True
                    if "gold_in_tree_flag" in irow:
                        gold_in_tree = safe_int(irow.get("gold_in_tree_flag", 0), 0)
                        if gold_in_tree == 0:
                            absent_confirm = True
                    elif candidate_answers:
                        gold_in_tree = 1 if gold_can and gold_can in {x["canonical"] for x in candidate_answers} else 0
                        if gold_in_tree == 0:
                            absent_confirm = True
                    else:
                        gold_in_tree = "unknown"
                    if not absent_confirm:
                        absent_unverified = True

                    # path-proximity diagnostics
                    question = str(irow.get("question", "") or erow.get("question", ""))
                    rationale = rationale_map.get(question.strip(), "")
                    if rationale:
                        gold_steps = split_steps(rationale)
                        scoring_method = "gsm8k_gold_rationale_step_overlap"
                    else:
                        gold_steps = split_steps(gold_raw)
                        scoring_method = "weak_gold_answer_proxy"
                    branch_texts = reasoning_snippets or [str(i_final_raw)]

                    if not branch_texts or not gold_steps:
                        gold_steps_total = 0
                        gold_steps_matched = 0
                        prefix = 0.0
                        divergence_depth = "NA"
                        nearest_text = ""
                        nearest_score = 0.0
                        nearest_branch_id = "NA"
                        nearest_branch_depth = "NA"
                        correct_region_entered = 0
                        proximity_bucket = "trace_unavailable"
                    else:
                        gold_steps_total = len(gold_steps)
                        matched_flags = []
                        for gs in gold_steps:
                            best = 0.0
                            for bt in branch_texts:
                                best = max(best, text_similarity(gs, bt))
                            matched_flags.append(1 if best >= 0.15 else 0)
                        gold_steps_matched = sum(matched_flags)
                        prefix_count = 0
                        for m in matched_flags:
                            if m == 1:
                                prefix_count += 1
                            else:
                                break
                        prefix = prefix_count / max(1, gold_steps_total)
                        divergence_depth = prefix_count if prefix_count < gold_steps_total else gold_steps_total
                        near_idx = 0
                        near_score = -1.0
                        for i_bt, bt in enumerate(branch_texts):
                            score = max(text_similarity(bt, gs) for gs in gold_steps)
                            if score > near_score:
                                near_score = score
                                near_idx = i_bt
                        nearest_text = branch_texts[near_idx][:300]
                        nearest_score = max(0.0, near_score)
                        nearest_branch_id = branch_ids[near_idx] if near_idx < len(branch_ids) else "NA"
                        nearest_branch_depth = safe_int(cands[near_idx].get("branch_depth", 0), 0) if near_idx < len(cands) else "NA"
                        correct_region_entered = 1 if gold_steps_matched > 0 else 0
                        if prefix < 0.2:
                            proximity_bucket = "immediate_miss"
                        elif prefix < 0.7:
                            proximity_bucket = "partial_progress"
                        else:
                            proximity_bucket = "near_miss_absent_final"

                    if absent_confirm:
                        confirmed_absent += 1
                    if absent_unverified:
                        unverified_absent += 1

                    loss_rows.append(
                        {
                            "provider": provider_k,
                            "model": model_k,
                            "dataset": dataset,
                            "seed": seed,
                            "budget": budget,
                            "example_id": example_id,
                            "question": question,
                            "gold_answer": gold_raw,
                            "gold_answer_canonical": gold_can,
                            "internal_method_name": im,
                            "external_baseline_name": em,
                            "internal_final_answer_raw": i_final_raw,
                            "internal_final_answer_canonical": i_final_can,
                            "external_final_answer_raw": e_final_raw,
                            "external_final_answer_canonical": e_final_can,
                            "internal_exact_match": safe_int(irow.get("is_correct", 0)),
                            "external_exact_match": safe_int(erow.get("is_correct", 0)),
                            "failure_tag": failure_tag,
                            "gold_final_answer_in_internal_tree": gold_in_tree,
                            "absent_from_tree_status": "confirmed_absent_from_tree" if absent_confirm else "absent_from_tree_unverified",
                            "all_explored_internal_candidate_answers": json.dumps(candidate_answers, ensure_ascii=False),
                            "selected_answer_group_support": str(irow.get("selected_answer_group", "")),
                            "branch_ids": json.dumps(branch_ids),
                            "family_ids": json.dumps(family_ids),
                            "branch_depths": json.dumps([safe_int(x.get("branch_depth", 0), 0) for x in cands]),
                            "max_branch_depth": max_depth,
                            "num_branches": len(cands) if cands else safe_int(irow.get("candidate_branch_count", 0), 0),
                            "num_answer_groups": safe_int(irow.get("answer_group_count", 0), 0),
                            "answer_entropy": safe_float(irow.get("answer_entropy", 0.0), 0.0),
                            "top2_gap": safe_float(irow.get("top2_support_gap", 0.0), 0.0),
                            "internal_token_count": safe_float(irow.get("token_estimate", 0.0), 0.0),
                            "external_token_count": safe_float(erow.get("token_estimate", 0.0), 0.0),
                            "internal_latency_seconds": safe_float(irow.get("latency_seconds", 0.0), 0.0),
                            "external_latency_seconds": safe_float(erow.get("latency_seconds", 0.0), 0.0),
                            "internal_estimated_cost_usd": safe_float(irow.get("cost_estimate", 0.0), 0.0),
                            "external_estimated_cost_usd": safe_float(erow.get("cost_estimate", 0.0), 0.0),
                            "gold_path_steps_total": gold_steps_total,
                            "gold_path_steps_matched_by_any_branch": gold_steps_matched,
                            "gold_path_prefix_coverage": prefix,
                            "divergence_depth": divergence_depth,
                            "nearest_branch_id": nearest_branch_id,
                            "nearest_branch_depth": nearest_branch_depth,
                            "nearest_branch_text": nearest_text,
                            "nearest_branch_similarity_score": nearest_score,
                            "correct_region_entered": correct_region_entered,
                            "path_proximity_bucket": proximity_bucket,
                            "path_scoring_method": scoring_method,
                            "problem_type": problem_type(question),
                        }
                    )

    # Writes
    write_jsonl(output_dir / "loss_cases_absent_from_tree.jsonl", loss_rows)
    write_csv(output_dir / "loss_cases_absent_from_tree.csv", loss_rows)

    def summarize_group(key: str) -> list[dict[str, Any]]:
        g: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for r in loss_rows:
            g[str(r.get(key, "unknown"))].append(r)
        out: list[dict[str, Any]] = []
        for k, rows in sorted(g.items()):
            n = len(rows)
            out.append(
                {
                    key: k,
                    "loss_cases": n,
                    "confirmed_absent": sum(1 for x in rows if x["absent_from_tree_status"] == "confirmed_absent_from_tree"),
                    "unverified_absent": sum(1 for x in rows if x["absent_from_tree_status"] == "absent_from_tree_unverified"),
                    "mean_prefix_coverage": sum(float(x["gold_path_prefix_coverage"]) for x in rows) / max(1, n),
                    "correct_region_entered_rate": sum(int(x["correct_region_entered"]) for x in rows) / max(1, n),
                }
            )
        return out

    path_counts = Counter(str(r.get("path_proximity_bucket", "trace_unavailable")) for r in loss_rows)
    path_summary = [
        {"bucket": b, "count": c, "share": c / max(1, len(loss_rows))}
        for b, c in sorted(path_counts.items(), key=lambda x: (-x[1], x[0]))
    ]
    write_csv(output_dir / "path_proximity_summary.csv", path_summary, fieldnames=["bucket", "count", "share"])
    write_csv(output_dir / "by_budget_summary.csv", summarize_group("budget"))
    write_csv(output_dir / "by_seed_summary.csv", summarize_group("seed"))
    write_csv(output_dir / "by_dataset_summary.csv", summarize_group("dataset"))
    write_csv(output_dir / "by_problem_type_summary.csv", summarize_group("problem_type"))

    cost_latency_rows = []
    for method, rows in defaultdict(list, {m: [r for r in loss_rows if r["internal_method_name"] == m] for m in sorted(set(r["internal_method_name"] for r in loss_rows))}).items():
        n = len(rows)
        if n == 0:
            continue
        cost_latency_rows.append(
            {
                "internal_method": method,
                "loss_cases": n,
                "mean_internal_tokens": sum(float(r["internal_token_count"]) for r in rows) / n,
                "mean_external_tokens": sum(float(r["external_token_count"]) for r in rows) / n,
                "mean_internal_cost": sum(float(r["internal_estimated_cost_usd"]) for r in rows) / n,
                "mean_external_cost": sum(float(r["external_estimated_cost_usd"]) for r in rows) / n,
                "mean_internal_latency": sum(float(r["internal_latency_seconds"]) for r in rows) / n,
                "mean_external_latency": sum(float(r["external_latency_seconds"]) for r in rows) / n,
                "internal_more_costly_rate": sum(1 for r in rows if float(r["internal_estimated_cost_usd"]) > float(r["external_estimated_cost_usd"])) / n,
            }
        )
    write_csv(output_dir / "cost_latency_summary.csv", cost_latency_rows)

    trace_summary = [
        {"metric": "loss_cases_total", "value": len(loss_rows)},
        {"metric": "loss_cases_with_candidate_trace_rows", "value": trace_available_count},
        {"metric": "trace_availability_rate", "value": trace_available_count / max(1, len(loss_rows))},
        {"metric": "confirmed_absent_from_tree", "value": confirmed_absent},
        {"metric": "unverified_absent_from_tree", "value": unverified_absent},
    ]
    write_csv(output_dir / "trace_availability_summary.csv", trace_summary)

    dominant_bucket = path_summary[0]["bucket"] if path_summary else "trace_unavailable"
    region_rate = (sum(int(r["correct_region_entered"]) for r in loss_rows) / max(1, len(loss_rows))) if loss_rows else 0.0
    abandoned_proxy = sum(1 for r in loss_rows if float(r["gold_path_prefix_coverage"]) >= 0.6 and str(r["path_proximity_bucket"]) == "near_miss_absent_final")
    early_commit_proxy = sum(1 for r in loss_rows if float(r["gold_path_prefix_coverage"]) >= 0.4 and safe_int(r.get("max_branch_depth", 0), 0) <= 1)

    recommendations = [
        "- Prefer delayed commit with additional continuation when prefix coverage is medium/high but final answer is absent.",
        "- Add direct-path fallback when immediate misses dominate and correct region is not entered.",
        "- Tune anti-collapse/continuation scoring to keep promising branches alive in near-miss absent-final cases.",
    ]
    if dominant_bucket == "immediate_miss":
        recommendations = [
            "- Improve initial branching diversity and early decomposition to avoid immediate misses.",
            "- Add direct-path fallback trigger for low early path overlap.",
            "- Reweight continuation score toward numeric-consistency checks before committing.",
        ]

    rec_lines = [
        "# Candidate fix recommendations",
        "",
        f"- Most absent-from-tree losses are: **{dominant_bucket}**.",
        f"- Correct reasoning region entered rate: **{region_rate:.3f}**.",
        f"- Promising-branch-abandoned proxy count: **{abandoned_proxy}** (near-miss absent-final).",
        f"- Early-commit proxy count: **{early_commit_proxy}**.",
        "- Concentration by budget/seed/dataset/problem type: see `by_budget_summary.csv`, `by_seed_summary.csv`, `by_dataset_summary.csv`, `by_problem_type_summary.csv`.",
        "- Cost inefficiency check: see `cost_latency_summary.csv` (`internal_more_costly_rate`).",
        "- Most justified controller change:",
        recommendations[0],
        "",
        "## Top 3 recommended fixes",
        recommendations[0],
        recommendations[1],
        recommendations[2],
    ]
    (output_dir / "candidate_fix_recommendations.md").write_text("\n".join(rec_lines) + "\n", encoding="utf-8")

    available_datasets = sorted(set(r["dataset"] for r in records.values()))
    missing_datasets = [d for d in DATASETS_DEFAULT if d not in available_datasets]
    missing_methods = [m for m in INTERNAL_METHODS_DEFAULT + EXTERNAL_METHODS_DEFAULT if m not in {r["method"] for r in records.values()}]
    missing_lines = [
        "# Missing data request",
        "",
        "- Existing artifacts were used only; no new expensive run was triggered.",
        f"- Missing requested datasets in available Cohere artifacts: {missing_datasets or ['none']}",
        f"- Missing requested methods in available Cohere artifacts: {missing_methods or ['none']}",
        "",
        "## Minimal additional Cohere run needed",
        "```bash",
        "python scripts/run_real_model_ours_vs_external_validation.py "
        f"--timestamp {ts}_MISSING_MIN "
        "--providers cohere "
        "--datasets openai/gsm8k,natural_plan,gpqa_diamond "
        "--subset-size 20 --seeds 11,23 --budgets 4,6,8 "
        "--methods strict_f3,strict_gate1_cap_k6,strict_f3_anti_collapse_weak_v1,external_l1_max,external_tale_prompt_budgeting,external_s1_budget_forcing "
        "--resume",
        "```",
    ]
    (output_dir / "missing_data_request.md").write_text("\n".join(missing_lines) + "\n", encoding="utf-8")

    manifest = {
        "artifact_family": "cohere_absent_from_tree_loss_diagnostics",
        "timestamp": ts,
        "provider": provider,
        "source_files": sorted(set(source_files)),
        "internal_methods_requested": INTERNAL_METHODS_DEFAULT,
        "external_methods_requested": EXTERNAL_METHODS_DEFAULT,
        "datasets_requested": DATASETS_DEFAULT,
        "budgets_requested": BUDGETS_DEFAULT,
        "matched_comparisons": matched_comparisons,
        "internal_wrong_external_correct": wrong_vs_correct,
        "confirmed_absent_from_tree": confirmed_absent,
        "unverified_absent_from_tree": unverified_absent,
        "files": [
            "loss_cases_absent_from_tree.jsonl",
            "loss_cases_absent_from_tree.csv",
            "path_proximity_summary.csv",
            "by_budget_summary.csv",
            "by_seed_summary.csv",
            "by_dataset_summary.csv",
            "by_problem_type_summary.csv",
            "cost_latency_summary.csv",
            "trace_availability_summary.csv",
            "candidate_fix_recommendations.md",
            "missing_data_request.md",
            "manifest.json",
        ],
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    doc = REPO_ROOT / "docs" / f"COHERE_ABSENT_FROM_TREE_LOSS_DIAGNOSTICS_{ts}.md"
    doc_lines = [
        f"# COHERE_ABSENT_FROM_TREE_LOSS_DIAGNOSTICS_{ts}",
        "",
        f"- Output directory: `outputs/cohere_absent_from_tree_loss_diagnostics_{ts}`",
        f"- Matched comparisons: **{matched_comparisons}**",
        f"- Internal-wrong/external-correct: **{wrong_vs_correct}**",
        f"- Confirmed absent-from-tree: **{confirmed_absent}**",
        f"- Unverified absent-from-tree: **{unverified_absent}**",
        f"- Trace availability (loss cases with branch candidates): **{trace_available_count}/{max(1, len(loss_rows))}**",
        f"- Most actionable bottleneck: **{dominant_bucket}** losses dominate.",
        "",
        "See `candidate_fix_recommendations.md` for controller-change recommendations.",
    ]
    doc.write_text("\n".join(doc_lines) + "\n", encoding="utf-8")

    print(str(output_dir.relative_to(REPO_ROOT)))
    print(f"matched_comparisons={matched_comparisons}")
    print(f"internal_wrong_external_correct={wrong_vs_correct}")
    print(f"confirmed_absent_from_tree={confirmed_absent}")
    print(f"unverified_absent_from_tree={unverified_absent}")


if __name__ == "__main__":
    main()
