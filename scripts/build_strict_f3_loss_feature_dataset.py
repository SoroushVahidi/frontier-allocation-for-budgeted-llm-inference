#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import sys
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.frontier_matrix_core import load_pilot_examples

OPS = {
    "ratio_percent": ["percent", "%", "ratio", "fraction", "probability", "rate"],
    "comparison": ["more than", "less than", "greater", "fewer", "difference", "compare"],
    "counting_combinatorics": ["ways", "arrange", "choose", "combination", "permutation", "how many"],
    "unit_conversion": ["km", "meter", "hour", "minute", "second", "mile", "kg", "gram", "liter", "convert"],
    "algebra_like": ["x", "equation", "solve for", "unknown", "variable"],
}


PRIMARY_FEATURES = [
    "budget",
    "question_length_tokens",
    "number_count",
    "operation_type_guess",
    "estimated_reasoning_steps_required",
    "strict_f3_gold_in_tree",
    "strict_f3_failure_tag",
    "strict_f3_num_unique_answers",
    "strict_f3_answer_diversity",
    "strict_f3_selected_answer_support",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build strict_f3 loss feature dataset vs external_l1_max")
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    p.add_argument("--diagnostic-dir", default="outputs/cohere_gsm8k_strict_f3_vs_external_l1_max_diagnostic_20260425T235500Z")
    p.add_argument("--records-path", default="outputs/cohere_real_model_cost_normalized_validation_20260425T133000Z_COHERE_STAGE1_MIN/per_example_records.jsonl")
    p.add_argument("--max-loss-cases", type=int, default=100)
    p.add_argument("--previous-timestamp", default="20260425T120000Z")
    return p.parse_args()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        with path.open("w", encoding="utf-8", newline="") as f:
            if fieldnames:
                w = csv.DictWriter(f, fieldnames=fieldnames)
                w.writeheader()
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames or list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def _count_numbers(text: str) -> int:
    return len(re.findall(r"[-+]?\d*\.?\d+", text or ""))


def _guess_operation(text: str, number_count: int) -> str:
    q = (text or "").lower()
    for label, keys in OPS.items():
        if any(k in q for k in keys):
            return label
    if number_count <= 2 and any(x in q for x in ["+", "-", "*", "times", "sum", "total"]):
        return "single_arithmetic"
    if number_count >= 3:
        return "multi_step_arithmetic"
    return "unknown"


def _estimate_steps(q_len: int, number_count: int, op: str) -> int:
    score = 1
    score += 1 if q_len > 20 else 0
    score += 1 if q_len > 35 else 0
    score += 1 if number_count >= 3 else 0
    score += 1 if op in {"multi_step_arithmetic", "counting_combinatorics", "algebra_like", "unit_conversion", "ratio_percent"} else 0
    return max(1, min(5, score))


def _build_question_lookup(dataset: str, seeds: set[int], max_index: int) -> dict[tuple[int, str], dict[str, str]]:
    lookup: dict[tuple[int, str], dict[str, str]] = {}
    for seed in sorted(seeds):
        examples = load_pilot_examples(dataset, subset_size=max_index + 1, seed=seed)
        for ex in examples:
            lookup[(seed, str(ex.example_id))] = {"question": str(ex.question), "gold_answer": str(ex.answer)}
    return lookup


def main() -> None:
    args = parse_args()
    diag_dir = REPO_ROOT / args.diagnostic_dir
    records_path = REPO_ROOT / args.records_path

    losses_raw = _read_jsonl(diag_dir / "strict_f3_loses_cases.jsonl")
    disagreements_raw = _read_jsonl(diag_dir / "per_example_disagreements.jsonl")
    recs = _read_jsonl(records_path)

    # Build matched strict_f3/external records from the underlying per-example log.
    by_case: dict[tuple[str, int, int, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for r in recs:
        if r.get("provider") != "cohere":
            continue
        if r.get("dataset") != "openai/gsm8k":
            continue
        if int(r.get("seed", -1)) not in {11, 23}:
            continue
        if int(r.get("budget", -1)) not in {4, 6, 8}:
            continue
        if r.get("method") not in {"strict_f3", "external_l1_max"}:
            continue
        if int(r.get("scored", 0)) != 1:
            continue
        key = (str(r["dataset"]), int(r["seed"]), int(r["budget"]), str(r["example_id"]))
        by_case[key][str(r["method"])] = r

    matched: list[dict[str, Any]] = []
    for (dataset, seed, budget, example_id), cell in sorted(by_case.items()):
        if "strict_f3" not in cell or "external_l1_max" not in cell:
            continue
        s = cell["strict_f3"]
        e = cell["external_l1_max"]
        matched.append(
            {
                "provider": "cohere",
                "model": s.get("model", "command-r-plus-08-2024"),
                "dataset": dataset,
                "seed": seed,
                "budget": budget,
                "example_id": example_id,
                "question": s.get("question", "") or e.get("question", ""),
                "gold_answer": s.get("gold_answer", "") or e.get("gold_answer", ""),
                "strict_f3_final_answer": s.get("final_answer_raw", ""),
                "external_l1_max_final_answer": e.get("final_answer_raw", ""),
                "strict_f3_correctness": int(s.get("exact_match", 0)),
                "external_l1_max_correctness": int(e.get("exact_match", 0)),
                "strict_f3_input_tokens": int(s.get("input_tokens", 0)),
                "strict_f3_output_tokens": int(s.get("output_tokens", 0)),
                "strict_f3_total_tokens": int(s.get("total_tokens", 0)),
                "strict_f3_latency": float(s.get("latency_seconds", 0.0)),
                "strict_f3_estimated_cost": float(s.get("estimated_cost_usd", 0.0)),
                "external_l1_max_input_tokens": int(e.get("input_tokens", 0)),
                "external_l1_max_output_tokens": int(e.get("output_tokens", 0)),
                "external_l1_max_total_tokens": int(e.get("total_tokens", 0)),
                "external_l1_max_latency": float(e.get("latency_seconds", 0.0)),
                "external_l1_max_estimated_cost": float(e.get("estimated_cost_usd", 0.0)),
                "strict_f3_gold_in_tree": int(s.get("gold_in_tree", 0)),
                "strict_f3_failure_tag": str(s.get("failure_tag", "unknown")).replace("correct answer absent from explored tree", "correct_answer_absent_from_tree").replace("correct answer present but not selected", "correct_answer_present_not_selected").replace("parse/extraction failure", "parse_extraction_failure").replace("API/runtime failure", "api_runtime_failure").replace(" ", "_").lower(),
            }
        )

    # Fill missing question/gold from loader using example_id index.
    seeds = {int(r["seed"]) for r in matched} | {11, 23}
    max_idx = 0
    for r in matched:
        try:
            max_idx = max(max_idx, int(str(r["example_id"]).split("_")[-1]))
        except Exception:
            pass
    q_lookup = _build_question_lookup("openai/gsm8k", seeds=seeds, max_index=max_idx)
    for r in matched:
        if not r["question"] or not r["gold_answer"]:
            q = q_lookup.get((int(r["seed"]), str(r["example_id"])))
            if q:
                r["question"] = q["question"]
                r["gold_answer"] = q["gold_answer"]

    losses = [r for r in matched if r["strict_f3_correctness"] == 0 and r["external_l1_max_correctness"] == 1]
    losses = losses[: args.max_loss_cases]

    for r in losses:
        q = r.get("question", "")
        q_len = len((q or "").split())
        n_num = _count_numbers(q)
        op = _guess_operation(q, n_num)
        # Answer-set metrics are unavailable in stage1-min artifacts; use conservative observable proxy.
        r["question_length_tokens"] = q_len
        r["number_count"] = n_num
        r["operation_type_guess"] = op
        r["estimated_reasoning_steps_required"] = _estimate_steps(q_len, n_num, op)
        r["strict_f3_num_unique_answers"] = 1
        r["strict_f3_answer_diversity"] = 0.0
        r["strict_f3_selected_answer_support"] = 1.0
        r["strict_f3_selected_answer_support_count"] = 1
        r["strict_f3_answer_diversity_proxy_note"] = "fallback_single_observed_answer_proxy"

    control_rows: list[dict[str, Any]] = []
    for r in matched:
        if r["strict_f3_correctness"] == 0 and r["external_l1_max_correctness"] == 1:
            ctype = "strict_f3_loss_external_win"
        elif r["strict_f3_correctness"] == 1 and r["external_l1_max_correctness"] == 0:
            ctype = "strict_f3_win_external_loss"
        elif r["strict_f3_correctness"] == 1 and r["external_l1_max_correctness"] == 1:
            ctype = "both_correct"
        else:
            ctype = "both_wrong"
        control_rows.append({
            "case_type": ctype,
            **{k: r[k] for k in [
                "provider", "model", "dataset", "seed", "budget", "example_id", "question", "gold_answer",
                "strict_f3_final_answer", "external_l1_max_final_answer", "strict_f3_correctness", "external_l1_max_correctness",
                "strict_f3_input_tokens", "strict_f3_output_tokens", "strict_f3_total_tokens", "strict_f3_latency", "strict_f3_estimated_cost",
                "external_l1_max_input_tokens", "external_l1_max_output_tokens", "external_l1_max_total_tokens", "external_l1_max_latency", "external_l1_max_estimated_cost",
            ]}
        })

    by_ftag = Counter(r["strict_f3_failure_tag"] for r in losses)
    by_budget = Counter(int(r["budget"]) for r in losses)
    by_op = Counter(r["operation_type_guess"] for r in losses)
    by_steps = Counter(int(r["estimated_reasoning_steps_required"]) for r in losses)
    by_gold_tree = Counter(int(r["strict_f3_gold_in_tree"]) for r in losses)

    feature_summary: list[dict[str, Any]] = []
    for feat, cnts in [
        ("budget", by_budget),
        ("operation_type_guess", by_op),
        ("estimated_reasoning_steps_required", by_steps),
        ("strict_f3_failure_tag", by_ftag),
        ("strict_f3_gold_in_tree", by_gold_tree),
    ]:
        total = sum(cnts.values())
        for k, v in sorted(cnts.items(), key=lambda kv: (-kv[1], str(kv[0]))):
            feature_summary.append({"feature": feat, "value": k, "count": int(v), "share": (v / total if total else 0.0)})

    top_patterns = []
    joint = Counter((r["strict_f3_failure_tag"], r["operation_type_guess"], int(r["budget"])) for r in losses)
    total_losses = max(1, len(losses))
    for (ft, op, b), c in joint.most_common(15):
        top_patterns.append({"failure_tag": ft, "operation_type_guess": op, "budget": b, "count": c, "share": c / total_losses})

    ts = args.timestamp
    out_dir = REPO_ROOT / "outputs" / f"strict_f3_loses_to_external_l1_max_feature_dataset_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    base_fields = [
        "provider", "model", "dataset", "seed", "budget", "example_id", "question", "gold_answer",
        "strict_f3_final_answer", "external_l1_max_final_answer", "strict_f3_correctness", "external_l1_max_correctness",
        "strict_f3_input_tokens", "strict_f3_output_tokens", "strict_f3_total_tokens", "strict_f3_latency", "strict_f3_estimated_cost",
        "external_l1_max_input_tokens", "external_l1_max_output_tokens", "external_l1_max_total_tokens", "external_l1_max_latency", "external_l1_max_estimated_cost",
    ]
    _write_jsonl(out_dir / "loss_cases.jsonl", [{k: r.get(k) for k in base_fields} for r in losses])
    _write_csv(out_dir / "loss_cases.csv", [{k: r.get(k) for k in base_fields} for r in losses], fieldnames=base_fields)

    feature_fields = PRIMARY_FEATURES + ["strict_f3_selected_answer_support_count", "strict_f3_answer_diversity_proxy_note", "example_id", "seed", "dataset", "provider", "model"]
    _write_csv(out_dir / "loss_case_features.csv", [{k: r.get(k) for k in feature_fields} for r in losses], fieldnames=feature_fields)
    _write_csv(out_dir / "control_cases.csv", control_rows)
    _write_csv(out_dir / "feature_summary.csv", feature_summary)
    _write_csv(out_dir / "top_failure_patterns.csv", top_patterns)

    rules = [
        "1. If strict_f3 failure risk is high from a loss-risk model over the 10 fixed features, route to external_l1_max before finalizing.",
        "2. For operation_type_guess in {ratio_percent, multi_step_arithmetic, counting_combinatorics} with estimated_reasoning_steps_required>=4, increase verification depth or defer to external_l1_max.",
        "3. When strict_f3_gold_in_tree=1 but strict_f3_failure_tag=correct_answer_present_not_selected, add a tie-break rescoring pass over candidate answers.",
        "4. When strict_f3_failure_tag=correct_answer_absent_from_tree and budget is low (4), allocate extra exploration budget before committing.",
        "5. Keep a parse/extraction guardrail: if parse_extraction_failure is detected, rerun extraction and, if unresolved, fallback to external_l1_max.",
    ]
    (out_dir / "candidate_controller_rules.md").write_text("# Candidate controller improvements\n\n" + "\n".join(f"- {r}" for r in rules) + "\n", encoding="utf-8")

    reached_100 = len(losses) >= 100
    reason = (
        "Reached target."
        if reached_100
        else (
            f"Expanded Cohere coverage yielded {len(losses)} strict_f3-loss/external-win cases from "
            f"{len(matched)} matched cases, still below the 100-case target; additional matched coverage is needed."
        )
    )

    manifest = {
        "timestamp": ts,
        "provider": "cohere",
        "model": "command-r-plus-08-2024",
        "dataset": "openai/gsm8k",
        "seeds": [11, 23],
        "budgets": [4, 6, 8],
        "comparison": {"ours": "strict_f3", "external": "external_l1_max"},
        "source_diagnostic_dir": str(diag_dir.relative_to(REPO_ROOT)),
        "source_records_path": str(records_path.relative_to(REPO_ROOT)),
        "matched_cases": len(matched),
        "strict_f3_loss_external_win_cases": len(losses),
        "target_loss_cases": 100,
        "reached_100": reached_100,
        "shortfall_reason": reason,
        "fixed_primary_features": PRIMARY_FEATURES,
        "files": [
            "manifest.json",
            "loss_cases.jsonl",
            "loss_cases.csv",
            "loss_case_features.csv",
            "control_cases.csv",
            "feature_summary.csv",
            "top_failure_patterns.csv",
            "candidate_controller_rules.md",
            "README.md",
        ],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    readme = f"""# strict_f3 loss feature dataset vs external_l1_max

- Timestamp: {ts}
- Provider/model: cohere / command-r-plus-08-2024
- Dataset: openai/gsm8k
- Seeds: 11, 23
- Budgets: 4, 6, 8
- Matched cases (strict_f3 & external_l1_max): {len(matched)}
- strict_f3 loss cases where external wins: {len(losses)}
- Target loss cases: 100
- Reached 100: {reached_100}
- Reason if not reached: {reason}

## Fixed primary features
{chr(10).join(f"{i+1}. {f}" for i, f in enumerate(PRIMARY_FEATURES))}

## Note on answer diversity/support fields
The available stage1-min artifact does not store full strict_f3 candidate-answer histograms. Therefore:
- strict_f3_num_unique_answers = 1
- strict_f3_answer_diversity = 0.0
- strict_f3_selected_answer_support = 1.0
These are explicit fallback proxies, recorded with strict_f3_answer_diversity_proxy_note.
"""
    (out_dir / "README.md").write_text(readme, encoding="utf-8")

    doc_path = REPO_ROOT / "docs" / f"STRICT_F3_LOSSES_TO_EXTERNAL_L1_MAX_FEATURE_DATASET_{ts}.md"
    prev_dir = REPO_ROOT / "outputs" / f"strict_f3_loses_to_external_l1_max_feature_dataset_{args.previous_timestamp}"
    prev_features = prev_dir / "loss_case_features.csv"
    prev_n = 0
    prev_dom_ftag = "unknown"
    prev_dom_op = "unknown"
    if prev_features.exists():
        with prev_features.open("r", encoding="utf-8", newline="") as f:
            prev_rows = list(csv.DictReader(f))
        prev_n = len(prev_rows)
        if prev_rows:
            prev_dom_ftag = Counter(str(r.get("strict_f3_failure_tag", "unknown")) for r in prev_rows).most_common(1)[0][0]
            prev_dom_op = Counter(str(r.get("operation_type_guess", "unknown")) for r in prev_rows).most_common(1)[0][0]

    cur_dom_ftag = by_ftag.most_common(1)[0][0] if by_ftag else "none"
    cur_dom_op = by_op.most_common(1)[0][0] if by_op else "none"
    feature_stability = "stable" if (cur_dom_ftag == prev_dom_ftag and cur_dom_op == prev_dom_op) else "partially_shifted"
    enough_for_controller = len(losses) >= 50
    additional_needed = 0 if len(losses) >= 100 else max(0, 100 - len(losses))
    doc_lines = [
        f"# STRICT_F3 losses-to-external_l1_max feature dataset ({ts})",
        "",
        "## Scope",
        "- Provider: cohere",
        "- Model: command-r-plus-08-2024",
        "- Dataset: openai/gsm8k",
        "- Seeds: 11, 23",
        "- Budgets: 4, 6, 8",
        "- Comparison: strict_f3 vs external_l1_max",
        "",
        "## Answers to required questions",
        f"1. Matched strict_f3/external_l1_max cases now available: **{len(matched)}**.",
        f"2. strict_f3-loss / external_l1_max-win cases found: **{len(losses)}**.",
        f"3. 100 loss cases reached: **{reached_100}**.",
        f"4. If not, why not: {reason}",
        f"5. Dominant-feature stability vs previous `{args.previous_timestamp}` report (n={prev_n}): **{feature_stability}** (failure_tag: `{prev_dom_ftag}` -> `{cur_dom_ftag}`, operation_type: `{prev_dom_op}` -> `{cur_dom_op}`).",
        f"6. Enough evidence now for feature-gated hybrid-controller design: **{enough_for_controller}** (loss-case count={len(losses)}).",
        f"7. Additional coverage needed for 100-loss target: **{additional_needed}** more strict_f3-loss/external-win cases.",
        "",
        "## Outputs",
        f"- `outputs/strict_f3_loses_to_external_l1_max_feature_dataset_{ts}/`",
        f"- `docs/STRICT_F3_LOSSES_TO_EXTERNAL_L1_MAX_FEATURE_DATASET_{ts}.md`",
    ]
    doc_path.write_text("\n".join(doc_lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
