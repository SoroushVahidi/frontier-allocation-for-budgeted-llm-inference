#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.data import extract_final_answer
from experiments.hf_datasets import _import_hf_load_dataset
from experiments.output_layer_repair import canonicalize_answer

PAIR_TYPES = {
    (0, 1): "strict_f3_wrong_external_correct",
    (1, 0): "strict_f3_correct_external_wrong",
    (1, 1): "both_correct",
    (0, 0): "both_wrong",
}

DIAG_FIELDS_OPTIONAL = [
    "answer_group_support_counts",
    "selected_answer_group",
    "top_answer_group",
    "top2_support_gap",
    "answer_entropy",
    "branch_score",
    "commit_margin",
    "priority_score",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build detailed strict_f3-vs-external loss-case package.")
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    p.add_argument(
        "--per-example-rows",
        default="outputs/real_model_ours_vs_external_validation_20260425T_WULVER_COHERE_LONG/cohere/per_example_rows.csv",
    )
    p.add_argument(
        "--loss-bundle-dir",
        default="outputs/strict_f3_vs_external_l1_max_more_loss_cases_20260425T_WULVER_COHERE_LONG",
    )
    p.add_argument("--dataset", default="openai/gsm8k")
    p.add_argument("--split", default="test")
    p.add_argument("--config", default="main")
    return p.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
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


def as_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def as_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def parse_openai_gsm8k_index(example_id: str) -> int | None:
    m = re.fullmatch(r"openai_gsm8k_(\d+)", str(example_id).strip())
    return int(m.group(1)) if m else None


def classify_problem_type(question: str) -> str:
    q = (question or "").lower()
    if any(x in q for x in ["ways", "choose", "arrange", "permutation", "combination", "how many"]):
        return "counting_combinatorics"
    if any(x in q for x in ["percent", "%", "ratio", "fraction", "rate"]):
        return "ratio_percent"
    if any(x in q for x in ["more than", "less than", "greater than", "fewer", "difference", "compared"]):
        return "comparison"
    if any(x in q for x in ["km", "kilometer", "meter", "cm", "inch", "mile", "kg", "gram", "liter", "hour", "minute", "second"]):
        return "unit_conversion"
    if any(x in q for x in ["equation", "solve for", "variable", "x =", "x=", "y ="]):
        return "algebra_like"
    num_count = len(re.findall(r"[-+]?\d*\.?\d+", q))
    sentence_count = len([s for s in re.split(r"[.!?]+", q) if s.strip()])
    if num_count >= 3 or sentence_count >= 3:
        return "multi_step_arithmetic"
    if num_count >= 1:
        return "single_arithmetic"
    return "unknown"


def secondary_tags(question: str) -> dict[str, int]:
    q = (question or "").lower()
    return {
        "contains_how_many": int("how many" in q),
        "contains_ways_choose_arrange": int(any(x in q for x in ["ways", "choose", "arrange", "combination", "permutation"])),
        "contains_percent": int("percent" in q or "%" in q),
        "contains_rate": int("rate" in q),
        "contains_money": int(any(x in q for x in ["$", "dollar", "dollars", "cents"])),
        "contains_time": int(any(x in q for x in ["hour", "minute", "second", "day", "week", "month", "year"])),
        "contains_units": int(any(x in q for x in ["km", "kilometer", "meter", "cm", "inch", "mile", "kg", "gram", "liter"])),
        "contains_comparison_words": int(any(x in q for x in ["more than", "less than", "greater", "fewer", "difference", "compared"])),
    }


def estimate_reasoning_steps(question: str) -> int:
    q = question or ""
    num_count = len(re.findall(r"[-+]?\d*\.?\d+", q))
    sentence_count = len([s for s in re.split(r"[.!?]+", q) if s.strip()])
    op_count = len(re.findall(r"\b(then|after|before|total|left|each|per|times|minus|plus)\b", q.lower()))
    return max(1, min(8, 1 + (1 if num_count >= 3 else 0) + (1 if sentence_count >= 3 else 0) + (op_count // 2)))


def numeric_answer_features(gold: str, ours: str) -> dict[str, Any]:
    g = canonicalize_answer(gold, dataset="openai/gsm8k")
    o = canonicalize_answer(ours, dataset="openai/gsm8k")
    out = {
        "gold_numeric": 0,
        "ours_numeric": 0,
        "answer_magnitude_gold": "NA",
        "numeric_sign_diff": "NA",
        "numeric_scale_diff": "NA",
        "numeric_rounding_diff": "NA",
        "numeric_offset_diff": "NA",
    }
    try:
        gf = float(g) if g is not None else None
        out["gold_numeric"] = int(gf is not None)
    except Exception:
        gf = None
    try:
        of = float(o) if o is not None else None
        out["ours_numeric"] = int(of is not None)
    except Exception:
        of = None
    if gf is None:
        return out
    out["answer_magnitude_gold"] = abs(gf)
    if of is None:
        return out
    out["numeric_sign_diff"] = int((gf > 0 and of < 0) or (gf < 0 and of > 0))
    ratio = abs(of / gf) if gf != 0 else None
    out["numeric_scale_diff"] = int(ratio is not None and (ratio >= 10.0 or ratio <= 0.1))
    out["numeric_rounding_diff"] = int(round(gf) == round(of) and gf != of)
    out["numeric_offset_diff"] = of - gf
    return out


def load_gsm8k_index_map(dataset: str, config: str | None, split: str) -> tuple[dict[int, dict[str, str]], str]:
    try:
        load_dataset = _import_hf_load_dataset()
        if config:
            ds = load_dataset(dataset, config, split=split)
        else:
            ds = load_dataset(dataset, split=split)
        out: dict[int, dict[str, str]] = {}
        for idx, row in enumerate(ds):
            q = str(row.get("question", ""))
            ans_raw = str(row.get("answer", ""))
            out[idx] = {
                "question": q,
                "gold_answer": extract_final_answer(ans_raw),
                "gold_answer_raw": ans_raw,
            }
        return out, "index_direct_from_hf_split_order"
    except Exception as exc:  # noqa: BLE001
        return {}, f"unavailable:{type(exc).__name__}"


def pair_rows(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    by_key: dict[tuple[str, str, int, int, str], dict[str, dict[str, str]]] = defaultdict(dict)
    for r in rows:
        key = (
            str(r.get("provider", "")),
            str(r.get("dataset", "")),
            as_int(r.get("seed"), -1),
            as_int(r.get("budget"), -1),
            str(r.get("example_id", "")),
        )
        by_key[key][str(r.get("method", ""))] = r
    paired: list[dict[str, Any]] = []
    for (provider, dataset, seed, budget, example_id), cell in sorted(by_key.items()):
        if "strict_f3" not in cell or "external_l1_max" not in cell:
            continue
        s = cell["strict_f3"]
        e = cell["external_l1_max"]
        s_ok = as_int(s.get("is_correct"), 0)
        e_ok = as_int(e.get("is_correct"), 0)
        pair_type = PAIR_TYPES[(s_ok, e_ok)]
        paired.append(
            {
                "provider": provider,
                "dataset": dataset,
                "seed": seed,
                "budget": budget,
                "example_id": example_id,
                "strict_f3_correct": s_ok,
                "external_l1_max_correct": e_ok,
                "pair_type": pair_type,
                "strict_f3_failure_type": str(s.get("failure_type", "")),
                "external_l1_max_failure_type": str(e.get("failure_type", "")),
                "strict_f3_absent_from_tree": as_int(s.get("absent_from_tree")),
                "strict_f3_present_not_selected": as_int(s.get("present_not_selected")),
                "strict_f3_output_layer_mismatch": as_int(s.get("output_layer_mismatch")),
                "strict_f3_actions_used": as_int(s.get("actions_used")),
                "strict_f3_expansions": as_int(s.get("expansions")),
                "strict_f3_verifications": as_int(s.get("verifications")),
                "strict_f3_budget_exhausted": as_int(s.get("budget_exhausted")),
                "repeated_same_family_expansion_rate": s.get("repeated_same_family_expansion_rate", "NA"),
                "max_family_expansion_share": s.get("max_family_expansion_share", "NA"),
                "strict_f3_oracle_gap": s.get("oracle_gap", "NA"),
                "strict_f3_oracle_regret": s.get("oracle_regret", "NA"),
                "external_actions_used": as_int(e.get("actions_used")),
            }
        )
    return paired


def build_rows(
    paired: list[dict[str, Any]],
    gsm_map: dict[int, dict[str, str]],
    mapping_rule: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    full_rows: list[dict[str, Any]] = []
    missing: Counter[str] = Counter()
    mapping_notes: list[dict[str, Any]] = []
    for r in paired:
        example_id = str(r["example_id"])
        idx = parse_openai_gsm8k_index(example_id) if r["dataset"] == "openai/gsm8k" else None
        recovered_q = "NA"
        recovered_gold = "NA"
        recovered_gold_raw = "NA"
        mapping_status = "not_applicable"
        if idx is not None:
            if idx in gsm_map:
                recovered_q = gsm_map[idx]["question"]
                recovered_gold = gsm_map[idx]["gold_answer"]
                recovered_gold_raw = gsm_map[idx]["gold_answer_raw"]
                mapping_status = "recovered_by_index"
            else:
                mapping_status = "index_missing_in_loader"
                missing["question"] += 1
                missing["gold_answer"] += 1

        problem_type = classify_problem_type(recovered_q if recovered_q != "NA" else "")
        sec = secondary_tags(recovered_q if recovered_q != "NA" else "")
        n_tokens = len((recovered_q if recovered_q != "NA" else "").split())
        n_numbers = len(re.findall(r"[-+]?\d*\.?\d+", recovered_q if recovered_q != "NA" else ""))
        n_sent = len([s for s in re.split(r"[.!?]+", recovered_q if recovered_q != "NA" else "") if s.strip()])
        est_steps = estimate_reasoning_steps(recovered_q if recovered_q != "NA" else "")

        our_final = "NA"
        ext_final = "NA"
        for name in ("our_final_answer", "strict_f3_final_answer", "strict_f3_final_answer_raw"):
            missing[name] += 1
        for name in ("external_final_answer", "external_l1_max_final_answer", "external_l1_max_final_answer_raw"):
            missing[name] += 1
        missing["answer_group_support_counts"] += 1
        missing["selected_answer_group"] += 1
        missing["top_answer_group"] += 1
        missing["top2_support_gap"] += 1
        missing["answer_entropy"] += 1
        missing["branch_score"] += 1
        missing["commit_margin"] += 1
        missing["priority_score"] += 1

        num_feat = numeric_answer_features(recovered_gold, our_final)
        out = {
            **r,
            "question": recovered_q,
            "gold_answer": recovered_gold,
            "gold_answer_raw": recovered_gold_raw,
            "our_final_answer": our_final,
            "external_final_answer": ext_final,
            "problem_type": problem_type,
            "question_length_tokens": n_tokens,
            "number_of_numeric_quantities": n_numbers,
            "number_of_sentences": n_sent,
            "estimated_reasoning_step_count": est_steps,
            "mapping_rule": mapping_rule,
            "mapping_status": mapping_status,
            "strict_f3_present_not_selected": int(r["strict_f3_present_not_selected"] == 1),
            "strict_f3_absent_from_tree": int(r["strict_f3_absent_from_tree"] == 1),
            "external_correct_with_fewer_actions": int(
                r["pair_type"] == "strict_f3_wrong_external_correct" and r["external_actions_used"] < r["strict_f3_actions_used"]
            ),
            "loss_budget_4": int(r["budget"] == 4 and r["pair_type"] == "strict_f3_wrong_external_correct"),
            "loss_budget_6": int(r["budget"] == 6 and r["pair_type"] == "strict_f3_wrong_external_correct"),
            "loss_budget_8": int(r["budget"] == 8 and r["pair_type"] == "strict_f3_wrong_external_correct"),
            "answer_group_support_counts": "NA",
            "selected_answer_group": "NA",
            "top_answer_group": "NA",
            "top2_support_gap": "NA",
            "answer_entropy": "NA",
            "branch_score": "NA",
            "commit_margin": "NA",
            "priority_score": "NA",
            **sec,
            **num_feat,
        }
        full_rows.append(out)
        mapping_notes.append(
            {
                "dataset": r["dataset"],
                "example_id": example_id,
                "parsed_index": idx if idx is not None else "NA",
                "mapping_status": mapping_status,
            }
        )

    missing_rows = [{"field": k, "missing_count": v, "note": "NA because unavailable in per_example_rows or richer source"} for k, v in sorted(missing.items())]
    return full_rows, missing_rows, mapping_notes


def summarize_problem_types(rows: list[dict[str, Any]], label: str) -> list[dict[str, Any]]:
    ctr = Counter(str(r.get("problem_type", "unknown")) for r in rows)
    total = max(1, len(rows))
    return [{"slice": label, "problem_type": k, "count": v, "share": v / total} for k, v in sorted(ctr.items())]


def answer_diff_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fields = ["numeric_sign_diff", "numeric_scale_diff", "numeric_rounding_diff"]
    out: list[dict[str, Any]] = []
    for f in fields:
        vals = [r.get(f) for r in rows if str(r.get(f)) != "NA"]
        out.append(
            {
                "metric": f,
                "count_non_na": len(vals),
                "mean": (sum(as_float(x) for x in vals) / max(1, len(vals))),
            }
        )
    offsets = [as_float(r.get("numeric_offset_diff")) for r in rows if str(r.get("numeric_offset_diff")) != "NA"]
    out.append(
        {
            "metric": "numeric_offset_diff_mean",
            "count_non_na": len(offsets),
            "mean": (sum(offsets) / max(1, len(offsets))),
        }
    )
    return out


def build_casebook(rows: list[dict[str, Any]]) -> str:
    pns = [r for r in rows if int(r.get("strict_f3_present_not_selected", 0)) == 1]
    losses = [r for r in rows if r.get("pair_type") == "strict_f3_wrong_external_correct"][:100]
    selected = pns + [r for r in losses if r not in pns]
    lines = ["# Casebook For Manual Review", ""]
    for i, r in enumerate(selected, start=1):
        comment = "correct answer present but strict_f3 selected a different answer" if int(r.get("strict_f3_present_not_selected", 0)) == 1 else "correct answer absent from strict_f3 explored tree"
        lines.extend(
            [
                f"## Case {i}",
                f"- case_id: {r.get('provider')}|{r.get('dataset')}|{r.get('seed')}|{r.get('budget')}|{r.get('example_id')}",
                f"- dataset/seed/budget/example_id: {r.get('dataset')} / {r.get('seed')} / {r.get('budget')} / {r.get('example_id')}",
                f"- problem_statement: {r.get('question')}",
                f"- gold_answer: {r.get('gold_answer')}",
                f"- our_answer: {r.get('our_final_answer')}",
                f"- external_answer: {r.get('external_final_answer')}",
                f"- failure_type: {r.get('strict_f3_failure_type')}",
                f"- problem_type: {r.get('problem_type')}",
                f"- actions/expansions/verifications: {r.get('strict_f3_actions_used')}/{r.get('strict_f3_expansions')}/{r.get('strict_f3_verifications')}",
                f"- repeated_family_stats: rate={r.get('repeated_same_family_expansion_rate')} max_share={r.get('max_family_expansion_share')}",
                f"- diagnostic_comment: {comment}.",
                "",
            ]
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    ts = args.timestamp
    per_path = REPO_ROOT / args.per_example_rows
    rows = read_csv(per_path)
    if not rows:
        raise RuntimeError(f"No rows found at {per_path}")

    paired = pair_rows(rows)
    gsm_map, mapping_rule = load_gsm8k_index_map(args.dataset, args.config, args.split)
    full_rows, missing_rows, mapping_notes = build_rows(paired, gsm_map, mapping_rule)

    by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in full_rows:
        by_type[str(r["pair_type"])].append(r)
    present_not_selected = [r for r in full_rows if int(r.get("strict_f3_present_not_selected", 0)) == 1]
    absent_from_tree = [r for r in full_rows if int(r.get("strict_f3_absent_from_tree", 0)) == 1]

    out_dir = REPO_ROOT / "outputs" / f"detailed_loss_case_package_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(out_dir / "all_paired_cases.csv", full_rows)
    write_csv(out_dir / "strict_f3_wrong_external_correct.csv", by_type.get("strict_f3_wrong_external_correct", []))
    write_csv(out_dir / "present_not_selected_cases.csv", present_not_selected)
    write_csv(out_dir / "absent_from_tree_cases.csv", absent_from_tree)
    write_csv(out_dir / "strict_f3_correct_external_wrong.csv", by_type.get("strict_f3_correct_external_wrong", []))
    write_csv(out_dir / "both_correct_cases.csv", by_type.get("both_correct", []))
    write_csv(out_dir / "both_wrong_cases.csv", by_type.get("both_wrong", []))
    write_csv(out_dir / "problem_type_summary.csv", summarize_problem_types(full_rows, "all"))
    write_csv(
        out_dir / "present_not_selected_problem_type_summary.csv",
        summarize_problem_types(present_not_selected, "present_not_selected"),
    )
    write_csv(out_dir / "absent_from_tree_problem_type_summary.csv", summarize_problem_types(absent_from_tree, "absent_from_tree"))
    write_csv(out_dir / "answer_difference_summary.csv", answer_diff_summary(full_rows))
    write_csv(out_dir / "missing_fields_report.csv", missing_rows, fieldnames=["field", "missing_count", "note"])
    write_csv(out_dir / "mapping_verification_summary.csv", mapping_notes)
    (out_dir / "casebook_for_manual_review.md").write_text(build_casebook(full_rows), encoding="utf-8")
    (out_dir / "README.md").write_text(
        "\n".join(
            [
                f"# detailed_loss_case_package_{ts}",
                "",
                f"- Source: `{args.per_example_rows}`",
                f"- Paired cases: {len(full_rows)}",
                f"- strict_f3 losses to external_l1_max: {len(by_type.get('strict_f3_wrong_external_correct', []))}",
                f"- Mapping rule: `{mapping_rule}`",
                "- Missing unavailable fields are explicitly encoded as `NA` and listed in `missing_fields_report.csv`.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    present_pt = Counter(r.get("problem_type", "unknown") for r in present_not_selected)
    absent_pt = Counter(r.get("problem_type", "unknown") for r in absent_from_tree)
    loss_by_budget = Counter(int(r.get("budget", -1)) for r in by_type.get("strict_f3_wrong_external_correct", []))
    repeat_flags = [
        as_float(r.get("repeated_same_family_expansion_rate"), 0.0)
        for r in by_type.get("strict_f3_wrong_external_correct", [])
        if str(r.get("repeated_same_family_expansion_rate", "NA")) != "NA"
    ]
    max_share_flags = [
        as_float(r.get("max_family_expansion_share"), 0.0)
        for r in by_type.get("strict_f3_wrong_external_correct", [])
        if str(r.get("max_family_expansion_share", "NA")) != "NA"
    ]
    report_path = REPO_ROOT / "docs" / f"DETAILED_LOSS_CASE_ANALYSIS_{ts}.md"
    report_path.write_text(
        "\n".join(
            [
                f"# DETAILED_LOSS_CASE_ANALYSIS_{ts}",
                "",
                f"- Total paired cases analyzed: **{len(full_rows)}**.",
                f"- strict_f3 lost to external_l1_max: **{len(by_type.get('strict_f3_wrong_external_correct', []))}**.",
                f"- Among losses: absent-from-tree={sum(int(r.get('strict_f3_absent_from_tree', 0)) for r in by_type.get('strict_f3_wrong_external_correct', []))}, present-not-selected={sum(int(r.get('strict_f3_present_not_selected', 0)) for r in by_type.get('strict_f3_wrong_external_correct', []))}.",
                f"- Present-not-selected mostly combinatorics/counting? **{'yes' if present_pt.get('counting_combinatorics', 0) >= max(1, len(present_not_selected)//2) else 'no_or_mixed'}**.",
                f"- Top problem types among present-not-selected: {present_pt.most_common(5)}.",
                f"- Top problem types among absent-from-tree: {absent_pt.most_common(5)}.",
                f"- Loss concentration by budget: {dict(sorted(loss_by_budget.items()))}.",
                f"- Repeated same-family expansion mean (losses): {(sum(repeat_flags)/max(1,len(repeat_flags))):.4f}.",
                f"- Max-family concentration mean (losses): {(sum(max_share_flags)/max(1,len(max_share_flags))):.4f}.",
                f"- Fields still unavailable for scoring diagnosis: {[r['field'] for r in missing_rows if r['missing_count'] > 0]}.",
                "",
                f"Package: `outputs/detailed_loss_case_package_{ts}/`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "status": "ok",
                "output_dir": str(out_dir.relative_to(REPO_ROOT)),
                "report": str(report_path.relative_to(REPO_ROOT)),
                "paired_cases": len(full_rows),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

