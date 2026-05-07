#!/usr/bin/env python3
"""Offline diagnostics for still-failing rate_ratio missing-leaf cases."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _to_int(v: Any) -> int:
    try:
        return int(float(str(v)))
    except Exception:
        return 0


def _to_float(v: Any) -> float | None:
    try:
        return float(str(v))
    except Exception:
        return None


def _listify(v: Any) -> list[Any]:
    return v if isinstance(v, list) else []


def _is_still_failing(
    row: dict[str, Any],
    recovery_status_by_id: dict[str, str],
) -> bool:
    eid = str(row.get("example_id") or row.get("case_id") or "").strip()
    current_correct = row.get("current_correct")
    if current_correct is not None:
        return _to_int(current_correct) == 0
    if eid in recovery_status_by_id:
        return recovery_status_by_id[eid] == "still_failing"
    return _to_int(row.get("our_exact")) == 0


def _feature_tags(row: dict[str, Any]) -> dict[str, Any]:
    ft = row.get("feature_tags")
    return ft if isinstance(ft, dict) else {}


def _operation_hints(row: dict[str, Any]) -> list[str]:
    ft = _feature_tags(row)
    ops = ft.get("operation_hints")
    if isinstance(ops, list):
        return [str(x) for x in ops if str(x)]
    raw = str(row.get("operation_hints") or "")
    return [x for x in raw.split("|") if x]


def _failure_stage(row: dict[str, Any]) -> str:
    ft = _feature_tags(row)
    return str(ft.get("failure_stage_classification") or row.get("failure_stage") or "")


def _tags_for_case(
    question: str,
    our_answer: Any,
    gold_answer: Any,
    operation_hints: list[str],
    candidate_diversity: int,
    pool_size: int,
    pal_trace_available: int,
    external_trace_available: int,
) -> list[str]:
    q = question.lower()
    tags: list[str] = []
    if ("per " in q) or re.search(r"\beach\b|\bper\b|\bmonthly\b|\bdaily\b|\bhour\b|\bminute\b", q):
        tags.append("unit_rate_missing")
    if re.search(r"\bpercent\b|%|\bhalf\b|\bquarter\b|\bthird\b|\bfraction\b", q):
        tags.append("percent_or_fraction_conversion")
    if re.search(r"\bthen\b|\bafter\b|\bbefore\b|\bfirst\b|\bsecond\b|\bthird\b|\bfinally\b", q):
        tags.append("multi_step_quantity_tracking")
    if re.search(r"\bremaining\b|\bleft\b|\bout of\b|\btotal\b|\bbase\b|\bdozen\b", q):
        tags.append("denominator_or_base_quantity_missing")

    oa = _to_float(our_answer)
    ga = _to_float(gold_answer)
    if oa is not None and ga not in (None, 0.0):
        reciprocal_gap = abs(oa - (1.0 / ga))
        scaled_reciprocal_gap = abs(oa - (100.0 / ga))
        if reciprocal_gap < 0.1 or scaled_reciprocal_gap < 0.5:
            tags.append("ratio_inversion_possible")

    if candidate_diversity <= 1 or pool_size <= 1:
        tags.append("candidate_generation_empty_or_low_diversity")
    if pal_trace_available == 0 and external_trace_available == 0:
        tags.append("insufficient_trace_data")
    if "rate_ratio" not in operation_hints:
        tags.append("wrong_operation_family")
    if not tags:
        tags.append("wrong_operation_family")
    # preserve order, remove duplicates
    return list(dict.fromkeys(tags))


def run(
    failure_cases_jsonl: Path,
    output_dir: Path,
    anchor_cases_csv: Path | None = None,
    recovery_table_csv: Path | None = None,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = _read_jsonl(failure_cases_jsonl)
    anchor_rows = _read_csv(anchor_cases_csv) if anchor_cases_csv and anchor_cases_csv.is_file() else []
    recovery_rows = _read_csv(recovery_table_csv) if recovery_table_csv and recovery_table_csv.is_file() else []
    recovery_status_by_id = {
        str(r.get("example_id") or "").strip(): str(r.get("recovery_status") or "").strip()
        for r in recovery_rows
    }

    selected: list[dict[str, Any]] = []
    for row in rows:
        eid = str(row.get("example_id") or row.get("case_id") or "").strip()
        ft = _feature_tags(row)
        ops = _operation_hints(row)
        stage = _failure_stage(row)
        if not _is_still_failing(row, recovery_status_by_id):
            continue
        if "rate_ratio" not in ops:
            continue
        if "gold_absent_everywhere_detectable" not in stage:
            continue

        pool = _listify(row.get("our_candidate_pool"))
        pool_size = len(pool)
        pool_answers = [str(c.get("normalized_answer") or c.get("predicted_answer") or "") for c in pool[:5]]
        pool_summary = f"size={pool_size}; top_answers={pool_answers}"
        pal_trace = _listify(row.get("our_discovery_trace"))
        ext_trace = _listify(row.get("external_discovery_trace"))
        pal_trace_available = 1 if pal_trace else 0
        ext_trace_available = 1 if ext_trace else 0
        direct_reserve_attempts = _listify(row.get("direct_reserve_attempts"))
        branch_states = _listify(row.get("our_final_branch_states"))
        trace_snippets = []
        if pal_trace:
            trace_snippets.append(str(pal_trace[0])[:180])
        if direct_reserve_attempts:
            trace_snippets.append(str(direct_reserve_attempts[0])[:180])
        if branch_states:
            trace_snippets.append(str(branch_states[0])[:180])
        trace_snippet = " || ".join(trace_snippets) if trace_snippets else ""

        question = str(row.get("question") or "")
        candidate_diversity = _to_int(ft.get("our_candidate_diversity", row.get("our_candidate_diversity")))
        tags = _tags_for_case(
            question=question,
            our_answer=row.get("our_answer"),
            gold_answer=row.get("gold_answer"),
            operation_hints=ops,
            candidate_diversity=candidate_diversity,
            pool_size=pool_size,
            pal_trace_available=pal_trace_available,
            external_trace_available=ext_trace_available,
        )

        selected.append(
            {
                "example_id": eid,
                "question": question,
                "gold_answer": row.get("gold_answer"),
                "pal_answer": row.get("our_answer"),
                "external_answer": row.get("external_answer"),
                "outcome_bucket": row.get("outcome_bucket"),
                "quantity_count": ft.get("numeric_quantity_count", row.get("quantity_count", "")),
                "quantity_bucket": ft.get("quantity_bucket", row.get("quantity_bucket")),
                "candidate_diversity": candidate_diversity,
                "pal_selector_candidate_pool_summary": pool_summary,
                "pal_trace_available": pal_trace_available,
                "external_action_trace_available": ext_trace_available,
                "pal_trace_snippets": trace_snippet,
                "direct_reserve_attempts_count": len(direct_reserve_attempts),
                "final_branch_states_count": len(branch_states),
                "missing_leaf_root_cause_tags": "|".join(tags),
            }
        )

    with (output_dir / "case_diagnosis.csv").open("w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "example_id",
            "question",
            "gold_answer",
            "pal_answer",
            "external_answer",
            "outcome_bucket",
            "quantity_count",
            "quantity_bucket",
            "candidate_diversity",
            "pal_selector_candidate_pool_summary",
            "pal_trace_available",
            "external_action_trace_available",
            "pal_trace_snippets",
            "direct_reserve_attempts_count",
            "final_branch_states_count",
            "missing_leaf_root_cause_tags",
        ]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(selected)

    tag_counter: Counter[str] = Counter()
    for row in selected:
        for t in str(row["missing_leaf_root_cause_tags"]).split("|"):
            if t:
                tag_counter[t] += 1

    root_rows = [{"root_cause_tag": k, "count": v} for k, v in tag_counter.most_common()]
    with (output_dir / "root_cause_table.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["root_cause_tag", "count"])
        w.writeheader()
        w.writerows(root_rows)

    recovered_rate_ratio_reference_cases = []
    for r in recovery_rows:
        memb = str(r.get("original_bucket_membership") or "")
        if str(r.get("recovery_status") or "") != "corrected_now":
            continue
        if "rate_ratio" not in memb:
            continue
        recovered_rate_ratio_reference_cases.append(
            {
                "example_id": str(r.get("example_id") or ""),
                "original_bucket_membership": memb,
                "current_output_source": str(r.get("current_output_source") or ""),
            }
        )

    requested_anchor_ids = {
        "openai_gsm8k_812",
        "openai_gsm8k_953",
        "openai_gsm8k_814",
        "openai_gsm8k_979",
        "openai_gsm8k_1069",
    }
    anchor_priority = [str(r.get("example_id") or "") for r in anchor_rows]
    selected_by_id = {r["example_id"]: r for r in selected}
    anchor_focus_ids = [eid for eid in anchor_priority if eid in requested_anchor_ids and eid in selected_by_id]
    for eid in requested_anchor_ids:
        if eid in selected_by_id and eid not in anchor_focus_ids:
            anchor_focus_ids.append(eid)

    anchor_md = ["# Anchor Review (rate_ratio + gold_absent)", ""]
    for eid in anchor_focus_ids:
        row = selected_by_id[eid]
        anchor_md.extend(
            [
                f"## {eid}",
                f"- outcome: {row['outcome_bucket']}",
                f"- quantity_bucket: {row['quantity_bucket']}",
                f"- candidate_diversity: {row['candidate_diversity']}",
                f"- root_cause_tags: {row['missing_leaf_root_cause_tags']}",
                f"- trace_data: pal={row['pal_trace_available']} external={row['external_action_trace_available']}",
                "",
            ]
        )
    (output_dir / "anchor_review.md").write_text("\n".join(anchor_md) + "\n", encoding="utf-8")

    summary = {
        "selected_case_count": len(selected),
        "selection_rule": "still_failing AND operation_hints contains rate_ratio AND failure_stage contains gold_absent_everywhere_detectable",
        "still_failing_inference_rule": "use current_correct if present, else recovery_table.recovery_status, else our_exact==0",
        "top_root_cause_tags": root_rows[:10],
        "trace_data_summary": {
            "pal_trace_available_count": sum(_to_int(r["pal_trace_available"]) for r in selected),
            "external_action_trace_available_count": sum(_to_int(r["external_action_trace_available"]) for r in selected),
        },
        "anchor_focus_case_ids": anchor_focus_ids,
        "recovered_rate_ratio_reference_cases": recovered_rate_ratio_reference_cases,
        "api_pilot_recommendation": (
            "No API pilot yet; continue offline root-cause inspection first. "
            "Run capped Cohere pilot only after an offline fix yields clearer tag reduction and no regression against recovered references."
        ),
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    p = argparse.ArgumentParser(description="Diagnose still-failing rate_ratio missing-leaf cases (offline).")
    p.add_argument(
        "--failure-cases-jsonl",
        type=Path,
        default=Path("outputs/failure_case_corpus_20260507/failure_cases.jsonl"),
    )
    p.add_argument(
        "--anchor-cases-csv",
        type=Path,
        default=Path("outputs/failure_case_pattern_mining_20260507/anchor_cases.csv"),
    )
    p.add_argument(
        "--recovery-table-csv",
        type=Path,
        default=Path("outputs/previous_failure_recovery_audit_20260507/case_recovery_table.csv"),
    )
    p.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/rate_ratio_missing_leaf_diagnosis_20260507"),
    )
    args = p.parse_args()
    summary = run(
        failure_cases_jsonl=args.failure_cases_jsonl,
        anchor_cases_csv=args.anchor_cases_csv if args.anchor_cases_csv.is_file() else None,
        recovery_table_csv=args.recovery_table_csv if args.recovery_table_csv.is_file() else None,
        output_dir=args.output_dir,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
