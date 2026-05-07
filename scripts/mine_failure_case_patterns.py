#!/usr/bin/env python3
"""Offline pattern mining over failure-case corpus."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median
from typing import Any


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def _to_int(v: Any) -> int:
    try:
        return int(float(str(v)))
    except Exception:
        return 0


def _op_list(s: str) -> list[str]:
    raw = str(s or "").strip()
    if not raw:
        return ["none"]
    return [x for x in raw.split("|") if x] or ["none"]


def _build_still_failing_set(recovery_rows: list[dict[str, str]], fallback_rows: list[dict[str, str]]) -> set[str]:
    if recovery_rows and "recovery_status" in recovery_rows[0]:
        return {
            str(r.get("example_id") or "").strip()
            for r in recovery_rows
            if str(r.get("recovery_status") or "").strip() == "still_failing"
        }
    return {
        str(r.get("example_id") or "").strip()
        for r in fallback_rows
        if _to_int(r.get("our_exact")) == 0
    }


def run(
    failure_cases_jsonl: Path,
    failure_cases_csv: Path,
    output_dir: Path,
    recovery_table_csv: Path | None = None,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_rows = _read_csv(failure_cases_csv)
    jsonl_rows = _read_jsonl(failure_cases_jsonl)
    by_id = {str(r.get("example_id") or r.get("case_id") or "").strip(): r for r in jsonl_rows}
    recovery_rows = _read_csv(recovery_table_csv) if recovery_table_csv and recovery_table_csv.is_file() else []
    still_ids = _build_still_failing_set(recovery_rows, csv_rows)
    still_rows = [r for r in csv_rows if str(r.get("example_id") or "").strip() in still_ids]

    outcome_counts: Counter[str] = Counter()
    stage_counts: Counter[str] = Counter()
    op_outcome: Counter[tuple[str, str]] = Counter()
    archetypes: Counter[tuple[str, str, str]] = Counter()
    diversity_vals: list[int] = []
    gold_in_pool_count = 0
    pal_trace_count = 0
    external_trace_count = 0
    both_trace_count = 0

    row_features: dict[str, dict[str, Any]] = {}
    for r in still_rows:
        eid = str(r.get("example_id") or "").strip()
        outcome = str(r.get("outcome_bucket") or "unknown")
        stage = str(r.get("failure_stage") or "unknown")
        qbucket = str(r.get("quantity_bucket") or "unknown")
        ops = _op_list(str(r.get("operation_hints") or ""))
        div = _to_int(r.get("our_candidate_diversity"))
        diversity_vals.append(div)
        gold_in_pool = _to_int(r.get("our_gold_in_pool"))
        gold_in_pool_count += 1 if gold_in_pool == 1 else 0
        anchor_reg = _to_int(r.get("anchor_regression"))

        jr = by_id.get(eid, {})
        pal_trace = 1 if isinstance(jr.get("our_discovery_trace"), list) and len(jr.get("our_discovery_trace")) > 0 else 0
        external_trace = 1 if isinstance(jr.get("external_discovery_trace"), list) and len(jr.get("external_discovery_trace")) > 0 else 0
        pal_trace_count += pal_trace
        external_trace_count += external_trace
        both_trace_count += 1 if pal_trace and external_trace else 0

        outcome_counts[outcome] += 1
        stage_counts[stage] += 1
        for op in ops:
            op_outcome[(op, outcome)] += 1
            archetypes[(op, qbucket, stage)] += 1

        row_features[eid] = {
            "outcome": outcome,
            "stage": stage,
            "qbucket": qbucket,
            "ops": ops,
            "div": div,
            "gold_in_pool": gold_in_pool,
            "anchor_regression": anchor_reg,
            "pal_trace": pal_trace,
            "external_trace": external_trace,
            "both_trace": 1 if pal_trace and external_trace else 0,
        }

    archetype_freq = dict(archetypes)
    anchors: list[tuple[float, str]] = []
    for eid, rf in row_features.items():
        top_arch = 0
        for op in rf["ops"]:
            top_arch = max(top_arch, archetype_freq.get((op, rf["qbucket"], rf["stage"]), 0))
        score = (
            float(top_arch)
            + (5.0 if rf["stage"] == "gold_absent_everywhere_detectable" else 0.0)
            + (3.0 if rf["both_trace"] else 0.0)
            + float(rf["anchor_regression"] * 2)
        )
        anchors.append((score, eid))
    anchors.sort(key=lambda x: (-x[0], x[1]))
    top_anchor_ids = [eid for _, eid in anchors[:15]]

    arch_rows = []
    for (op, qb, st), c in archetypes.most_common():
        arch_rows.append(
            {
                "operation_hint": op,
                "quantity_bucket": qb,
                "failure_stage": st,
                "count": c,
            }
        )

    with (output_dir / "failure_archetypes.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["operation_hint", "quantity_bucket", "failure_stage", "count"])
        w.writeheader()
        w.writerows(arch_rows)

    with (output_dir / "anchor_cases.csv").open("w", encoding="utf-8", newline="") as f:
        cols = [
            "example_id",
            "score",
            "outcome_bucket",
            "failure_stage",
            "operation_hints",
            "quantity_bucket",
            "anchor_regression",
            "pal_trace_available",
            "external_trace_available",
            "both_traces_available",
        ]
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for s, eid in anchors[:15]:
            rf = row_features[eid]
            w.writerow(
                {
                    "example_id": eid,
                    "score": f"{s:.2f}",
                    "outcome_bucket": rf["outcome"],
                    "failure_stage": rf["stage"],
                    "operation_hints": "|".join(rf["ops"]),
                    "quantity_bucket": rf["qbucket"],
                    "anchor_regression": rf["anchor_regression"],
                    "pal_trace_available": rf["pal_trace"],
                    "external_trace_available": rf["external_trace"],
                    "both_traces_available": rf["both_trace"],
                }
            )

    summary = {
        "still_failing_cases_mined": len(still_rows),
        "counts_by_outcome_bucket": dict(outcome_counts),
        "counts_by_failure_stage": dict(stage_counts),
        "operation_by_outcome": [
            {"operation_hint": k[0], "outcome_bucket": k[1], "count": v}
            for k, v in sorted(op_outcome.items(), key=lambda kv: (-kv[1], kv[0]))
        ],
        "top_archetypes": [
            {
                "operation_hint": op,
                "quantity_bucket": qb,
                "failure_stage": st,
                "count": c,
            }
            for (op, qb, st), c in archetypes.most_common(15)
        ],
        "candidate_diversity_summary": {
            "count": len(diversity_vals),
            "median": float(median(diversity_vals)) if diversity_vals else 0.0,
            "mean": (sum(diversity_vals) / len(diversity_vals)) if diversity_vals else 0.0,
        },
        "gold_presence_summary": {
            "gold_in_pool_count": gold_in_pool_count,
            "gold_not_in_pool_count": max(0, len(still_rows) - gold_in_pool_count),
        },
        "trace_availability": {
            "pal_trace_available_count": pal_trace_count,
            "external_trace_available_count": external_trace_count,
            "both_trace_available_count": both_trace_count,
        },
        "top_anchor_case_ids": top_anchor_ids,
        "single_next_hypothesis": (
            "For high-frequency rate_ratio/temporal_change cases where stage is gold_absent_everywhere_detectable, "
            "improve upstream candidate-generation to produce gold-equivalent numeric leaves before selector/overlay."
        ),
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    dominant = summary["top_archetypes"][0]["count"] if summary["top_archetypes"] else 0
    total = len(still_rows) if still_rows else 1
    dominance_ratio = dominant / total
    pattern_shape = "one dominant pattern" if dominance_ratio >= 0.35 else "multiple meaningful patterns"

    report = [
        "# Failure Case Pattern Mining Report",
        "",
        f"- Still-failing cases mined: {len(still_rows)}",
        f"- Top failure archetypes: {summary['top_archetypes'][:5]}",
        f"- Pattern shape: {pattern_shape}",
        f"- PAL trace availability: {pal_trace_count}/{len(still_rows)}",
        f"- External trace availability: {external_trace_count}/{len(still_rows)}",
        "- Current 48-case corpus is enough for offline pattern design, but still small for broad claims.",
        "- More API is not needed now; use offline findings to define a single targeted hypothesis first.",
        f"- Single next hypothesis: {summary['single_next_hypothesis']}",
        "",
        "## Top 15 Anchor Cases",
    ]
    for eid in top_anchor_ids:
        rf = row_features[eid]
        report.append(
            f"- {eid} | outcome={rf['outcome']} | stage={rf['stage']} | ops={'|'.join(rf['ops'])} | qbucket={rf['qbucket']} | both_traces={rf['both_trace']}"
        )
    (output_dir / "pattern_mining_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    p = argparse.ArgumentParser(description="Mine patterns from failure-case corpus.")
    p.add_argument(
        "--failure-cases-jsonl",
        type=Path,
        default=Path("outputs/failure_case_corpus_20260507/failure_cases.jsonl"),
    )
    p.add_argument(
        "--failure-cases-csv",
        type=Path,
        default=Path("outputs/failure_case_corpus_20260507/failure_cases.csv"),
    )
    p.add_argument(
        "--recovery-table-csv",
        type=Path,
        default=Path("outputs/previous_failure_recovery_audit_20260507/case_recovery_table.csv"),
    )
    p.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/failure_case_pattern_mining_20260507"),
    )
    args = p.parse_args()
    summary = run(
        failure_cases_jsonl=args.failure_cases_jsonl,
        failure_cases_csv=args.failure_cases_csv,
        recovery_table_csv=args.recovery_table_csv if args.recovery_table_csv.is_file() else None,
        output_dir=args.output_dir,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
