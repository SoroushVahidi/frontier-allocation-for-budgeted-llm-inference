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


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


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
    has_gold_reasoning = bool(case.get("has_gold_implied_reasoning", False))

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

    if source_present == 1 and gold_in_tree and selected_group and selected_group != gold:
        evidence.append("gold_present_in_tree_selected_group_differs")
        return Classification("selector_failure", evidence)

    if parse_fail or (gold_in_tree and (not final_raw or not final_canonical)) or has_gold_reasoning:
        if parse_fail:
            evidence.append("parse_extraction_failure_flag")
        if gold_in_tree and (not final_raw or not final_canonical):
            evidence.append("gold_present_but_final_answer_missing")
        if has_gold_reasoning:
            evidence.append("metadata_marks_gold_implied_reasoning")
        return Classification("extraction_or_finalization_failure", evidence)

    if source_absent == 1:
        if max_depth >= 2 and len(root_families) <= 1:
            evidence.append(f"max_depth={max_depth}")
            evidence.append(f"root_family_count={len(root_families)}")
            return Classification("continuation_focus_failure", evidence)
        if len(root_families) >= 2 and max_depth <= 1:
            evidence.append(f"root_family_count={len(root_families)}")
            evidence.append(f"max_depth={max_depth}")
            return Classification("root_diversity_failure", evidence)
        if len(root_families) <= 1 and max_depth <= 1:
            evidence.append(f"root_family_count={len(root_families)}")
            evidence.append(f"max_depth={max_depth}")
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
    rows: list[dict[str, Any]] = []
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
                w = csv.DictWriter(f, fieldnames=fieldnames)
                w.writeheader()
            return
        w = csv.DictWriter(f, fieldnames=fieldnames or list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Analyze bounded F3-vs-L1 loss trace diagnostics.")
    p.add_argument("--input-dir", required=True)
    p.add_argument("--timestamp", default="")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    in_dir = Path(args.input_dir)
    ts = args.timestamp or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    selected_rows = _read_csv(in_dir / "selected_cases.csv")
    per_example = _read_jsonl(in_dir / "per_example_records.jsonl")
    trace_index = _read_csv(in_dir / "per_case_trace_index.csv")

    traces_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for idx in trace_index:
        trace_rel = str(idx.get("trace_path", ""))
        trace_path = in_dir / trace_rel
        if not trace_path.exists():
            continue
        payload = json.loads(trace_path.read_text(encoding="utf-8"))
        top = payload.get("top_level", {})
        traces_by_key[(str(top.get("example_id")), str(top.get("method")))] = payload

    records_by_key: dict[tuple[str, int, int, str, str], dict[str, Any]] = {}
    for r in per_example:
        key = (str(r.get("example_id")), _coerce_int(r.get("seed"), -1), _coerce_int(r.get("budget"), -1), str(r.get("provider", "")), str(r.get("method", "")))
        records_by_key[key] = r

    rows: list[dict[str, Any]] = []
    absent_sub = Counter()
    present_sub = Counter()

    for base in selected_rows:
        example_id = str(base.get("example_id", ""))
        seed = _coerce_int(base.get("seed"), -1)
        budget = _coerce_int(base.get("budget"), -1)
        provider = str(base.get("provider", ""))
        f3 = records_by_key.get((example_id, seed, budget, provider, "strict_f3"), {})
        ext = records_by_key.get((example_id, seed, budget, provider, "external_l1_max"), {})
        trace = traces_by_key.get((example_id, "strict_f3"), {})
        md = dict(f3.get("result_metadata", {}) or {})

        cls_input = {
            "source_absent_from_tree": _coerce_int(base.get("source_absent_from_tree"), 0),
            "source_present_not_selected": _coerce_int(base.get("source_present_not_selected"), 0),
            "gold_answer_canonical": str(f3.get("gold_answer_canonical") or base.get("gold_answer_canonical") or ""),
            "selected_answer_group": str(md.get("selected_answer_group") or md.get("selected_group") or ""),
            "parse_extraction_failure": bool(md.get("parse_extraction_failure", False) or f3.get("parse_extraction_failure", 0) == 1),
            "final_answer_raw": str(f3.get("final_answer_raw") or ""),
            "final_answer_canonical": str(f3.get("final_answer_canonical") or ""),
            "gold_in_tree": bool(md.get("gold_in_tree", False) or f3.get("gold_in_tree", 0) == 1),
            "has_gold_implied_reasoning": bool(md.get("gold_implied_reasoning", False)),
            "answer_group_support_counts": md.get("answer_group_support_counts", {}),
            "action_trace": md.get("action_trace", []),
            "branches": trace.get("branches", []),
        }
        cls = classify_trace_failure(cls_input)

        out = {
            "provider": provider,
            "dataset": str(base.get("dataset", "")),
            "seed": seed,
            "budget": budget,
            "example_id": example_id,
            "source_loss_stratum": (
                "absent_from_tree" if _coerce_int(base.get("source_absent_from_tree"), 0) == 1 else "present_not_selected"
            ),
            "strict_f3_status": str(f3.get("status", "missing")),
            "external_l1_max_status": str(ext.get("status", "missing")),
            "strict_f3_exact_match": _coerce_int(f3.get("exact_match"), 0),
            "external_l1_max_exact_match": _coerce_int(ext.get("exact_match"), 0),
            "primary_bucket": cls.bucket,
            "evidence": " | ".join(cls.evidence),
            "problem_type": str(base.get("problem_type", "unknown")) if base.get("problem_type") else "unknown",
        }
        rows.append(out)
        if out["source_loss_stratum"] == "absent_from_tree":
            absent_sub[out["primary_bucket"]] += 1
        else:
            present_sub[out["primary_bucket"]] += 1

    out_dir = in_dir
    _write_csv(out_dir / "per_case_trace_classification.csv", rows)

    agg = Counter(r["primary_bucket"] for r in rows)
    _write_csv(
        out_dir / "aggregate_failure_breakdown.csv",
        [{"primary_bucket": b, "count": int(agg.get(b, 0))} for b in BUCKETS],
    )
    _write_csv(
        out_dir / "absent_from_tree_subtype_breakdown.csv",
        [{"primary_bucket": b, "count": int(absent_sub.get(b, 0))} for b in BUCKETS],
    )
    _write_csv(
        out_dir / "present_not_selected_breakdown.csv",
        [{"primary_bucket": b, "count": int(present_sub.get(b, 0))} for b in BUCKETS],
    )

    by_budget: dict[int, Counter[str]] = defaultdict(Counter)
    for r in rows:
        by_budget[_coerce_int(r["budget"], -1)][str(r["primary_bucket"])] += 1
    b_rows: list[dict[str, Any]] = []
    for b in sorted(by_budget):
        total = sum(by_budget[b].values())
        for bucket in BUCKETS:
            c = by_budget[b].get(bucket, 0)
            b_rows.append({"budget": b, "primary_bucket": bucket, "count": c, "share": (c / total if total else 0.0)})
    _write_csv(out_dir / "per_budget_breakdown.csv", b_rows)

    by_pt: dict[str, Counter[str]] = defaultdict(Counter)
    for r in rows:
        by_pt[str(r.get("problem_type", "unknown"))][str(r["primary_bucket"])] += 1
    pt_rows: list[dict[str, Any]] = []
    for pt in sorted(by_pt):
        total = sum(by_pt[pt].values())
        for bucket in BUCKETS:
            c = by_pt[pt].get(bucket, 0)
            pt_rows.append({"problem_type": pt, "primary_bucket": bucket, "count": c, "share": (c / total if total else 0.0)})
    _write_csv(out_dir / "per_problem_type_breakdown.csv", pt_rows)

    dominant_absent = absent_sub.most_common(1)[0][0] if absent_sub else "external_baseline_advantage_unclear"
    if dominant_absent == "root_diversity_failure":
        repair = "Prioritize root-diversity repair: add direct-reserve / root-family diversification before deep expansions."
    elif dominant_absent == "continuation_focus_failure":
        repair = "Prioritize continuation/focus repair: increase continuation score weight and anti-collapse penalties on single-family expansions."
    elif dominant_absent == "extraction_or_finalization_failure":
        repair = "Prioritize extraction repair: improve canonical answer parsing and finalization consistency checks."
    else:
        repair = "Primary signal remains ambiguous; run one follow-up micro-slice with richer trace fields before changing core algorithm."

    (out_dir / "recommended_algorithmic_repairs.md").write_text(
        "\n".join(
            [
                "# Recommended Algorithmic Repairs",
                "",
                f"- Dominant absent-from-tree subtype in this package: **{dominant_absent}**.",
                f"- Recommended next change: {repair}",
                "- Keep scope bounded: do not rerun broad sweeps until this repair is validated on this same diagnostic slice.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    doc_ts = in_dir.name.replace("f3_vs_l1_loss_trace_diagnostic_", "")
    doc_path = Path("docs") / f"F3_VS_L1_LOSS_TRACE_DIAGNOSTIC_{doc_ts}.md"
    absent_total = sum(absent_sub.values())
    present_total = sum(present_sub.values())
    report = [
        f"# F3 vs L1 Loss Trace Diagnostic ({doc_ts})",
        "",
        "## Key answers",
        f"- Among sampled absent-from-tree losses ({absent_total}), root_diversity_failure={absent_sub.get('root_diversity_failure',0)}, continuation_focus_failure={absent_sub.get('continuation_focus_failure',0)}, extraction_or_finalization_failure={absent_sub.get('extraction_or_finalization_failure',0)}.",
        f"- Main next repair direction: **{dominant_absent}**.",
        "- This package is intended as bounded decision evidence; if unclear dominates, one micro follow-up is still needed.",
        f"- Exact next algorithmic change: {repair}",
        "",
        "## Scope",
        f"- Present-not-selected sampled: {present_total}",
        f"- Total classified cases: {len(rows)}",
    ]
    doc_path.write_text("\n".join(report) + "\n", encoding="utf-8")

    manifest = {
        "analysis_timestamp": ts,
        "input_dir": str(in_dir),
        "classified_cases": len(rows),
        "bucket_labels": BUCKETS,
        "doc_report": str(doc_path),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    readme = [
        "# Analyzer outputs",
        "",
        "Generated files:",
        "- manifest.json",
        "- selected_cases.csv",
        "- per_case_trace_classification.csv",
        "- aggregate_failure_breakdown.csv",
        "- absent_from_tree_subtype_breakdown.csv",
        "- present_not_selected_breakdown.csv",
        "- per_budget_breakdown.csv",
        "- per_problem_type_breakdown.csv",
        "- recommended_algorithmic_repairs.md",
    ]
    (out_dir / "README.md").write_text("\n".join(readme) + "\n", encoding="utf-8")
    print(f"Analysis complete: {out_dir}")


if __name__ == "__main__":
    main()
