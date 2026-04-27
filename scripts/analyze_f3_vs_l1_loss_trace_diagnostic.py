#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BUCKETS = [
    "root_diversity_failure",
    "continuation_focus_failure",
    "selector_failure",
    "extraction_or_finalization_failure",
    "external_baseline_advantage_unclear",
]


@dataclass
class Classification:
    bucket: str
    evidence: list[str]


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def classify_trace_failure(case: dict[str, Any]) -> Classification:
    evidence: list[str] = []
    source_absent = _coerce_int(case.get("source_absent_from_tree"), 0)
    source_present = _coerce_int(case.get("source_present_not_selected"), 0)
    gold = str(case.get("gold_answer_canonical") or "").strip()
    selected_group = str(case.get("selected_answer_group") or "").strip()
    parse_fail = bool(case.get("parse_extraction_failure", False))
    final_raw = str(case.get("final_answer_raw") or "").strip()
    final_canonical = str(case.get("final_answer_canonical") or "").strip()
    gold_in_tree = bool(case.get("gold_in_tree", False))

    answer_support = case.get("answer_group_support_counts") if isinstance(case.get("answer_group_support_counts"), dict) else {}
    action_trace = case.get("action_trace") if isinstance(case.get("action_trace"), list) else []
    branches = case.get("branches") if isinstance(case.get("branches"), list) else []

    root_families = {
        str((ev or {}).get("family_id") or (ev or {}).get("strategy_family") or "")
        for ev in action_trace
        if _coerce_int((ev or {}).get("depth"), 0) <= 1
    }
    root_families = {x for x in root_families if x}
    max_depth = max([_coerce_int((b or {}).get("depth"), 0) for b in branches] + [0])

    if source_present == 1 and gold and gold in answer_support and selected_group and selected_group != gold:
        evidence.append("gold_answer_group_present_but_not_selected")
        return Classification("selector_failure", evidence)

    if parse_fail or (gold_in_tree and (not final_raw or not final_canonical)):
        if parse_fail:
            evidence.append("parse_extraction_failure_flag")
        if gold_in_tree and (not final_raw or not final_canonical):
            evidence.append("gold_present_but_final_answer_missing")
        return Classification("extraction_or_finalization_failure", evidence)

    if source_absent == 1:
        if max_depth >= 2 and len(root_families) <= 1:
            evidence.extend([f"max_depth={max_depth}", f"root_family_count={len(root_families)}"])
            return Classification("continuation_focus_failure", evidence)
        if len(root_families) <= 1 and max_depth <= 1:
            evidence.extend([f"max_depth={max_depth}", f"root_family_count={len(root_families)}"])
            return Classification("root_diversity_failure", evidence)

    evidence.append("heuristics_ambiguous")
    return Classification("external_baseline_advantage_unclear", evidence)


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        if not rows:
            if fieldnames:
                csv.DictWriter(f, fieldnames=fieldnames).writeheader()
            return
        w = csv.DictWriter(f, fieldnames=fieldnames or list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def _trace_key_from_top(top: dict[str, Any]) -> tuple[str, str, int, int, str, str]:
    return (
        str(top.get("provider", "")),
        str(top.get("dataset", "")),
        _coerce_int(top.get("seed"), -1),
        _coerce_int(top.get("budget"), -1),
        str(top.get("example_id", "")),
        str(top.get("method", "")),
    )


def _record_key(row: dict[str, Any]) -> tuple[str, str, int, int, str, str]:
    return (
        str(row.get("provider", "")),
        str(row.get("dataset", "")),
        _coerce_int(row.get("seed"), -1),
        _coerce_int(row.get("budget"), -1),
        str(row.get("example_id", "")),
        str(row.get("method", "")),
    )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Analyze bounded F3-vs-L1 loss trace diagnostics.")
    p.add_argument("--input-dir", required=True)
    p.add_argument("--timestamp", default="")
    p.add_argument("--report-path", default="")
    return p.parse_args()


def analyze_input_dir(input_dir: Path, timestamp: str = "", report_path: str = "") -> Path:
    ts = timestamp or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    selected_rows = _read_csv(input_dir / "selected_cases.csv")
    per_example = _read_jsonl(input_dir / "per_example_records.jsonl")
    trace_index = _read_csv(input_dir / "per_case_trace_index.csv")
    runner_manifest = {}
    if (input_dir / "manifest.json").exists():
        runner_manifest = json.loads((input_dir / "manifest.json").read_text(encoding="utf-8"))

    traces_by_key: dict[tuple[str, str, int, int, str, str], dict[str, Any]] = {}
    for idx in trace_index:
        rel = str(idx.get("trace_path", ""))
        path = input_dir / rel
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        key = _trace_key_from_top(dict(payload.get("top_level", {})))
        traces_by_key[key] = payload

    records_by_key = {_record_key(r): r for r in per_example}

    rows: list[dict[str, Any]] = []
    absent_sub = Counter()
    present_sub = Counter()

    for base in selected_rows:
        provider = str(base.get("provider", ""))
        dataset = str(base.get("dataset", ""))
        seed = _coerce_int(base.get("seed"), -1)
        budget = _coerce_int(base.get("budget"), -1)
        example_id = str(base.get("example_id", ""))

        f3_key = (provider, dataset, seed, budget, example_id, "strict_f3")
        ext_key = (provider, dataset, seed, budget, example_id, "external_l1_max")
        f3 = records_by_key.get(f3_key, {})
        ext = records_by_key.get(ext_key, {})
        trace = traces_by_key.get(f3_key, {})
        md = dict(f3.get("result_metadata", {}) or {})

        cls = classify_trace_failure(
            {
                "source_absent_from_tree": _coerce_int(base.get("source_absent_from_tree"), 0),
                "source_present_not_selected": _coerce_int(base.get("source_present_not_selected"), 0),
                "gold_answer_canonical": str(f3.get("gold_answer_canonical") or base.get("gold_answer_canonical") or ""),
                "selected_answer_group": str(md.get("selected_answer_group") or md.get("selected_group") or ""),
                "parse_extraction_failure": bool(md.get("parse_extraction_failure", False) or f3.get("parse_extraction_failure", 0) == 1),
                "final_answer_raw": str(f3.get("final_answer_raw") or ""),
                "final_answer_canonical": str(f3.get("final_answer_canonical") or ""),
                "gold_in_tree": bool(md.get("gold_in_tree", False) or f3.get("gold_in_tree", 0) == 1),
                "answer_group_support_counts": md.get("answer_group_support_counts", {}),
                "action_trace": md.get("action_trace", []),
                "branches": trace.get("branches", []),
            }
        )

        row = {
            "provider": provider,
            "dataset": dataset,
            "seed": seed,
            "budget": budget,
            "example_id": example_id,
            "source_loss_stratum": "absent_from_tree" if _coerce_int(base.get("source_absent_from_tree"), 0) == 1 else "present_not_selected",
            "strict_f3_status": str(f3.get("status", "missing")),
            "external_l1_max_status": str(ext.get("status", "missing")),
            "strict_f3_exact_match": _coerce_int(f3.get("exact_match"), 0),
            "external_l1_max_exact_match": _coerce_int(ext.get("exact_match"), 0),
            "primary_bucket": cls.bucket,
            "evidence": " | ".join(cls.evidence),
            "problem_type": str(base.get("problem_type", "unknown") or "unknown"),
            "trace_key": str(f3_key),
        }
        rows.append(row)
        if row["source_loss_stratum"] == "absent_from_tree":
            absent_sub[row["primary_bucket"]] += 1
        else:
            present_sub[row["primary_bucket"]] += 1

    _write_csv(input_dir / "per_case_trace_classification.csv", rows)
    agg = Counter(r["primary_bucket"] for r in rows)
    _write_csv(input_dir / "aggregate_failure_breakdown.csv", [{"primary_bucket": b, "count": int(agg.get(b, 0))} for b in BUCKETS])
    _write_csv(input_dir / "absent_from_tree_subtype_breakdown.csv", [{"primary_bucket": b, "count": int(absent_sub.get(b, 0))} for b in BUCKETS])
    _write_csv(input_dir / "present_not_selected_breakdown.csv", [{"primary_bucket": b, "count": int(present_sub.get(b, 0))} for b in BUCKETS])

    by_budget: dict[int, Counter[str]] = defaultdict(Counter)
    for r in rows:
        by_budget[_coerce_int(r["budget"], -1)][str(r["primary_bucket"])] += 1
    pb_rows = []
    for b in sorted(by_budget):
        tot = sum(by_budget[b].values())
        for bucket in BUCKETS:
            c = by_budget[b].get(bucket, 0)
            pb_rows.append({"budget": b, "primary_bucket": bucket, "count": c, "share": (c / tot if tot else 0.0)})
    _write_csv(input_dir / "per_budget_breakdown.csv", pb_rows)

    by_pt: dict[str, Counter[str]] = defaultdict(Counter)
    for r in rows:
        by_pt[str(r.get("problem_type", "unknown"))][str(r["primary_bucket"])] += 1
    pt_rows = []
    for pt in sorted(by_pt):
        tot = sum(by_pt[pt].values())
        for bucket in BUCKETS:
            c = by_pt[pt].get(bucket, 0)
            pt_rows.append({"problem_type": pt, "primary_bucket": bucket, "count": c, "share": (c / tot if tot else 0.0)})
    _write_csv(input_dir / "per_problem_type_breakdown.csv", pt_rows)

    is_dry = bool(runner_manifest.get("dry_run", False))
    dominant_absent = absent_sub.most_common(1)[0][0] if absent_sub else "external_baseline_advantage_unclear"
    repair = "Synthetic placeholder only." if is_dry else f"Prioritize next repair track: {dominant_absent}."
    (input_dir / "recommended_algorithmic_repairs.md").write_text(
        "\n".join([
            "# Recommended Algorithmic Repairs",
            "",
            ("**This is a dry-run artifact for schema validation only. It must not be used as scientific or empirical evidence.**" if is_dry else ""),
            f"- Dominant absent-from-tree subtype: **{dominant_absent}**.",
            f"- Recommendation: {repair}",
        ])
        + "\n",
        encoding="utf-8",
    )

    report = Path(report_path) if report_path else Path("docs") / f"F3_VS_L1_LOSS_TRACE_DIAGNOSTIC_{input_dir.name.replace('f3_vs_l1_loss_trace_diagnostic_', '')}.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report_lines = [
        f"# F3 vs L1 Loss Trace Diagnostic ({input_dir.name.replace('f3_vs_l1_loss_trace_diagnostic_', '')})",
        "",
        ("**This is a dry-run artifact for schema validation only. It must not be used as scientific or empirical evidence.**" if is_dry else ""),
        "## Key answers",
        f"- Among sampled absent-from-tree losses ({sum(absent_sub.values())}), root_diversity_failure={absent_sub.get('root_diversity_failure',0)}, continuation_focus_failure={absent_sub.get('continuation_focus_failure',0)}, extraction_or_finalization_failure={absent_sub.get('extraction_or_finalization_failure',0)}.",
        f"- Main next repair direction: **{('synthetic_placeholder' if is_dry else dominant_absent)}**.",
        f"- Exact next algorithmic change: {repair}",
        "",
        "## Scope",
        f"- Present-not-selected sampled: {sum(present_sub.values())}",
        f"- Total classified cases: {len(rows)}",
    ]
    report.write_text("\n".join([x for x in report_lines if x is not None]) + "\n", encoding="utf-8")

    analysis_manifest = {
        "analysis_timestamp": ts,
        "input_dir": str(input_dir),
        "classified_cases": len(rows),
        "bucket_labels": BUCKETS,
        "doc_report": str(report),
    }
    merged_manifest = dict(runner_manifest or {})
    merged_manifest["analysis"] = analysis_manifest
    (input_dir / "manifest.json").write_text(json.dumps(merged_manifest, indent=2) + "\n", encoding="utf-8")
    (input_dir / "README.md").write_text(
        "\n".join(
            [
                "# Analyzer outputs",
                "",
                "Generated files: manifest.json, selected_cases.csv, per_case_trace_classification.csv, aggregate_failure_breakdown.csv, absent_from_tree_subtype_breakdown.csv, present_not_selected_breakdown.csv, per_budget_breakdown.csv, per_problem_type_breakdown.csv, recommended_algorithmic_repairs.md.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return report


def main() -> None:
    args = parse_args()
    analyze_input_dir(Path(args.input_dir), timestamp=args.timestamp, report_path=args.report_path)
    print(f"Analysis complete: {args.input_dir}")


if __name__ == "__main__":
    main()
