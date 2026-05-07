#!/usr/bin/env python3
"""Offline PAL discovery-deficit atlas (no API)."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from experiments.output_layer_repair import canonicalize_answer
from experiments.frontier_max_support_tiebreak import normalize_answer_group_key
from experiments.pal_executor import extract_pal_stdout_numeric_candidate


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def _index_pal(path: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in _iter_jsonl(path):
        eid = str(row.get("example_id") or row.get("case_id") or "").strip()
        if eid:
            out[eid] = row
    return out


def _to_int(v: Any) -> int:
    try:
        return int(float(str(v)))
    except Exception:
        return 0


def _norm(v: Any) -> str:
    return str(v if v is not None else "").strip()


def _as_list(v: Any) -> list[Any]:
    return v if isinstance(v, list) else []


def _extract_answers_from_row(row: Any) -> list[str]:
    out: list[str] = []
    if not isinstance(row, dict):
        return out
    for k in (
        "predicted_answer",
        "extracted_answer",
        "answer",
        "final_answer",
        "trace_extracted_answer",
        "pal_answer_raw",
        "pal_answer_normalized",
    ):
        s = _norm(row.get(k))
        if s:
            out.append(s)
    return out


def _match_gold(ans: str, gcan: str) -> bool:
    if not ans or not gcan:
        return False
    return canonicalize_answer(ans, dataset="openai/gsm8k") == gcan


def _bucket_regret(row: dict[str, str]) -> str:
    ext = _to_int(row.get("external_exact") or row.get("external_l1_max_exact"))
    pal = _to_int(row.get("pal_exact"))
    if ext and not pal:
        return "external_only"
    if (not ext) and (not pal):
        return "both_wrong"
    if ext and pal:
        return "both_correct"
    return "pal_only"


def _quantity_bucket(question: str) -> str:
    nums = re.findall(r"[-+]?\d+(?:\.\d+)?", question.replace(",", ""))
    n = len(nums)
    if n <= 1:
        return "qnum_0_1"
    if n <= 3:
        return "qnum_2_3"
    if n <= 5:
        return "qnum_4_5"
    return "qnum_6p"


def _question_len_bucket(question: str) -> str:
    w = len([x for x in question.split() if x.strip()])
    if w <= 12:
        return "len_short"
    if w <= 24:
        return "len_medium"
    return "len_long"


def _operation_hints(question: str) -> list[str]:
    q = question.lower()
    hints: list[str] = []
    if re.search(r"\b(per|each|rate|ratio)\b", q):
        hints.append("rate_ratio")
    if re.search(r"\b(percent|percentage|%|discount|interest)\b", q):
        hints.append("percent")
    if re.search(r"\b(total|sum|altogether|in all)\b", q):
        hints.append("total_sum")
    if re.search(r"\b(left|remain|difference|more than|less than|fewer)\b", q):
        hints.append("difference")
    if re.search(r"\b(times|product|multiplied|double|triple)\b", q):
        hints.append("product")
    if re.search(r"\b(divide|split|share|average|quotient|equal parts)\b", q):
        hints.append("division_share")
    if re.search(r"\b(after|before|then|next|now|later|increased|decreased|change)\b", q):
        hints.append("temporal_change")
    return hints or ["none"]


def _diversity_bucket(selector_pool: list[str]) -> str:
    groups = {normalize_answer_group_key(_norm(x)) or "__unknown__" for x in selector_pool if _norm(x)}
    n = len(groups)
    if n <= 1:
        return "div_low"
    if n == 2:
        return "div_mid"
    return "div_high"


def _extract_stage_flags(md: dict[str, Any], gcan: str) -> dict[str, int]:
    selector_pool_vals: list[str] = []
    for r in _as_list(md.get("selector_candidate_pool")):
        selector_pool_vals.extend(_extract_answers_from_row(r))

    direct_vals: list[str] = []
    for r in _as_list(md.get("direct_reserve_attempts")):
        direct_vals.extend(_extract_answers_from_row(r))

    trace_vals: list[str] = []
    for r in _as_list(md.get("action_trace")):
        trace_vals.extend(_extract_answers_from_row(r))
    fm = md.get("frontier_metadata")
    if isinstance(fm, dict):
        for r in _as_list(fm.get("action_trace")):
            trace_vals.extend(_extract_answers_from_row(r))

    branch_vals: list[str] = []
    for k in ("final_branch_states", "branch_states"):
        for r in _as_list(md.get(k)):
            branch_vals.extend(_extract_answers_from_row(r))

    exec_vals: list[str] = []
    px = md.get("pal_execution")
    if isinstance(px, dict):
        exec_vals.extend(_extract_answers_from_row(px))
        er = px.get("pal_execution_result")
        if isinstance(er, dict):
            exec_vals.extend(_extract_answers_from_row(er))
            sn = extract_pal_stdout_numeric_candidate(_norm(er.get("pal_stdout")))
            if sn:
                exec_vals.append(sn)

    gold_in_direct = int(any(_match_gold(x, gcan) for x in direct_vals))
    gold_in_trace = int(any(_match_gold(x, gcan) for x in (trace_vals + branch_vals)))
    gold_in_pool = int(any(_match_gold(x, gcan) for x in selector_pool_vals))
    gold_in_exec = int(any(_match_gold(x, gcan) for x in exec_vals))

    any_detectable = bool(
        selector_pool_vals or direct_vals or trace_vals or branch_vals or exec_vals
    )
    return {
        "gold_in_direct_attempts": gold_in_direct,
        "gold_in_trace_but_not_pool": int(gold_in_trace == 1 and gold_in_pool == 0),
        "gold_in_execution_only": int(gold_in_exec == 1 and gold_in_pool == 0 and gold_in_trace == 0 and gold_in_direct == 0),
        "gold_absent_all_detectable": int(any_detectable and not (gold_in_pool or gold_in_direct or gold_in_trace or gold_in_exec)),
        "insufficient_metadata": int(not any_detectable),
        "selector_pool_values": selector_pool_vals,
    }


def _stage_label(flags: dict[str, int]) -> str:
    for k in (
        "gold_in_direct_attempts",
        "gold_in_trace_but_not_pool",
        "gold_in_execution_only",
        "gold_absent_all_detectable",
        "insufficient_metadata",
    ):
        if flags.get(k):
            return k
    return "gold_absent_all_detectable"


def run_atlas(casebook_path: Path, pal_results_path: Path, output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    cb_rows = _read_csv_rows(casebook_path)
    pal_by_id = _index_pal(pal_results_path)

    coverage_rows: list[dict[str, Any]] = []
    archetypes: Counter[tuple[str, str, str, str]] = Counter()
    operation_counts: Counter[str] = Counter()
    quantity_counts: Counter[str] = Counter()
    anchors_by_arch: defaultdict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)

    for cb in cb_rows:
        bucket = _bucket_regret(cb)
        if bucket not in {"external_only", "both_wrong"}:
            continue
        eid = _norm(cb.get("example_id") or cb.get("case_id"))
        pal_row = pal_by_id.get(eid, {})
        md = pal_row.get("result_metadata")
        if not isinstance(md, dict):
            md = {}
        question = _norm(cb.get("question") or pal_row.get("question"))
        gold = _norm(cb.get("gold_answer") or pal_row.get("gold_answer"))
        gcan = canonicalize_answer(gold, dataset="openai/gsm8k") if gold else ""

        flags = _extract_stage_flags(md, gcan)
        stage = _stage_label(flags)
        q_bucket = _quantity_bucket(question)
        hints = _operation_hints(question)
        op = hints[0]
        div_bucket = _diversity_bucket(flags["selector_pool_values"])
        len_bucket = _question_len_bucket(question)

        arch = (stage, op, q_bucket, div_bucket)
        archetypes[arch] += 1
        operation_counts[op] += 1
        quantity_counts[q_bucket] += 1

        row = {
            "example_id": eid,
            "bucket": bucket,
            "stage": stage,
            "operation_hint": op,
            "quantity_bucket": q_bucket,
            "length_bucket": len_bucket,
            "diversity_bucket": div_bucket,
            "gold_in_direct_attempts": flags["gold_in_direct_attempts"],
            "gold_in_trace_but_not_pool": flags["gold_in_trace_but_not_pool"],
            "gold_in_execution_only": flags["gold_in_execution_only"],
            "gold_absent_all_detectable": flags["gold_absent_all_detectable"],
            "insufficient_metadata": flags["insufficient_metadata"],
        }
        coverage_rows.append(row)
        if len(anchors_by_arch[arch]) < 5:
            anchors_by_arch[arch].append(row)

    top_arch = archetypes.most_common(20)
    summary = {
        "meta": {
            "casebook_path": str(casebook_path.resolve()),
            "pal_results_path": str(pal_results_path.resolve()),
            "output_dir": str(output_dir.resolve()),
            "api_calls": "none",
        },
        "focus_rows": len(coverage_rows),
        "stage_counts": dict(Counter(r["stage"] for r in coverage_rows)),
        "operation_counts": dict(operation_counts),
        "quantity_bucket_counts": dict(quantity_counts),
        "top_archetypes": [
            {
                "stage": a[0],
                "operation_hint": a[1],
                "quantity_bucket": a[2],
                "diversity_bucket": a[3],
                "count": n,
            }
            for a, n in top_arch
        ],
    }

    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with (output_dir / "deficit_archetype_table.csv").open("w", encoding="utf-8", newline="") as f:
        fields = ["stage", "operation_hint", "quantity_bucket", "diversity_bucket", "count"]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for a, n in top_arch:
            w.writerow(
                {
                    "stage": a[0],
                    "operation_hint": a[1],
                    "quantity_bucket": a[2],
                    "diversity_bucket": a[3],
                    "count": n,
                }
            )

    anchor_rows: list[dict[str, Any]] = []
    for a, _ in top_arch[:10]:
        anchor_rows.extend(anchors_by_arch[a])
    with (output_dir / "anchor_cases.csv").open("w", encoding="utf-8", newline="") as f:
        fields = list(anchor_rows[0].keys()) if anchor_rows else ["example_id"]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        if anchor_rows:
            w.writerows(anchor_rows)

    lines = [
        "# Offline PAL discovery deficit atlas",
        "",
        f"- Focus rows: **{summary['focus_rows']}**",
        f"- Stage counts: `{summary['stage_counts']}`",
        f"- Top operation hints: `{dict(operation_counts.most_common(6))}`",
        f"- Quantity buckets: `{dict(quantity_counts)}`",
        "- API calls: none",
        "",
        "## Top archetypes",
    ]
    for item in summary["top_archetypes"][:10]:
        lines.append(
            f"- {item['stage']} | {item['operation_hint']} | {item['quantity_bucket']} | {item['diversity_bucket']} -> {item['count']}"
        )
    (output_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    repo = Path.cwd()
    default_dir = repo / "outputs" / "cohere_paired_pal_retry_vs_external_l1_300case_20260506T194114Z"
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--casebook", type=Path, default=default_dir / "paired_casebook.csv")
    p.add_argument("--pal-results", type=Path, dest="pal_results", default=default_dir / "pal_results.jsonl")
    p.add_argument(
        "--coverage-table",
        type=Path,
        default=repo / "outputs" / "offline_pal_path_coverage_counterfactual_20260506" / "coverage_table.csv",
        help="Optional existing coverage table (currently unused but accepted for workflow compatibility).",
    )
    p.add_argument(
        "--output-dir",
        type=Path,
        default=repo / "outputs" / "offline_pal_discovery_deficit_atlas_20260506",
    )
    args = p.parse_args()
    _ = args.coverage_table
    out = run_atlas(args.casebook, args.pal_results, args.output_dir)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
