#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {}
    except json.JSONDecodeError:
        return {}


def _safe_int(v: Any) -> int:
    try:
        return int(v)
    except Exception:
        return 0


def _is_one(v: Any) -> bool:
    return str(v).strip() in {"1", "true", "True"}


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = sorted({k for row in rows for k in row})
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fields})


def inventory(roots: list[Path]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    broad_csv = Path("outputs/external_loss_casebook_broad_20260430T185500Z/loss_casebook_trace_complete.csv")
    broad_rows = _read_csv(broad_csv)
    focused_rows = [
        row
        for row in broad_rows
        if _is_one(row.get("trace_available"))
        and _is_one(row.get("gold_present_in_candidate_groups"))
        and _is_one(row.get("oracle_selector_would_fix"))
    ]
    rows.append(
        {
            "artifact": "broad_external_loss_trace_complete_casebook",
            "path": str(broad_csv),
            "artifact_level": "aggregate_casebook",
            "rows": len(broad_rows),
            "focused_rows": len(focused_rows),
            "present": broad_csv.exists(),
            "notes": "47 broad rows expected; 33 focused rows expected after selector filter.",
        }
    )

    enriched_summary = Path("outputs/focused33_trace_enriched_20260501T000906Z/focused33_trace_enrichment_summary.json")
    enriched = _read_json(enriched_summary)
    rows.append(
        {
            "artifact": "focused33_trace_enrichment_summary",
            "path": str(enriched_summary),
            "artifact_level": "trace_enriched_candidate_nodes",
            "rows": _safe_int(enriched.get("focused_input_rows")),
            "raw_records_found": _safe_int(enriched.get("raw_records_found")),
            "cases_with_candidate_nodes": _safe_int(enriched.get("cases_with_candidate_nodes_positive")),
            "cases_with_at_least_one_candidate_trace": _safe_int(enriched.get("cases_with_at_least_one_candidate_trace")),
            "cases_with_all_candidate_traces": _safe_int(enriched.get("cases_with_all_candidate_traces")),
            "total_candidate_nodes": _safe_int(enriched.get("total_candidate_nodes_extracted")),
            "traced_candidate_nodes": _safe_int(enriched.get("total_candidate_nodes_with_trace_text")),
            "trace_preserved_gold_cases": _safe_int(enriched.get("cases_gold_canonical_in_extracted_node_finals")),
            "aggregate_gold_cases": _safe_int(enriched.get("cases_gold_canonical_in_casebook_candidates_aggregate")),
            "present": enriched_summary.exists(),
            "notes": "Current input for trace-aware Cobbe-inspired selector work.",
        }
    )

    retry_summary = Path("outputs/trace_complete_external_losses_retry_20260430T204900Z/trace_complete_loss_summary.json")
    retry = _read_json(retry_summary)
    rows.append(
        {
            "artifact": "trace_complete_external_losses_retry_summary",
            "path": str(retry_summary),
            "artifact_level": "trace_complete_loss_subset",
            "rows": _safe_int(retry.get("total_trace_complete_losses_collected")),
            "gold_present_count": _safe_int(retry.get("gold_present_count")),
            "oracle_would_fix_count": _safe_int(retry.get("oracle_would_fix_count")),
            "present": retry_summary.exists(),
            "notes": "Separate 16-case trace-complete selector-failure subset; may overlap with broad casebook.",
        }
    )

    trace_index = Path(
        "outputs/trace_complete_external_losses_retry_20260430T204900Z/"
        "cohere_real_model_cost_normalized_validation_20260430T204900Z/per_case_trace_index.csv"
    )
    trace_rows = _read_csv(trace_index)
    unique_keys = {
        (
            row.get("dataset", ""),
            row.get("example_id", ""),
            row.get("seed", ""),
            row.get("budget", ""),
            row.get("method", ""),
        )
        for row in trace_rows
    }
    base_dir = trace_index.parent
    missing_paths: list[str] = []
    present_paths = 0
    for row in trace_rows:
        rel = row.get("trace_path", "")
        if not rel:
            continue
        p = base_dir / rel
        if p.exists():
            present_paths += 1
        else:
            missing_paths.append(str(p))
    rows.append(
        {
            "artifact": "per_case_trace_index",
            "path": str(trace_index),
            "artifact_level": "raw_trace_index",
            "rows": len(trace_rows),
            "unique_dataset_example_seed_budget_method": len(unique_keys),
            "trace_paths_referenced": sum(1 for row in trace_rows if row.get("trace_path")),
            "trace_paths_present": present_paths,
            "trace_paths_missing": len(missing_paths),
            "present": trace_index.exists(),
            "notes": "Raw trace index contains more traced method/example rows than the 47-row casebook.",
        }
    )

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "roots": [str(root) for root in roots],
        "broad_trace_complete_rows": len(broad_rows),
        "focused_rows": len(focused_rows),
        "focused_raw_records_found": _safe_int(enriched.get("raw_records_found")),
        "focused_candidate_nodes": _safe_int(enriched.get("total_candidate_nodes_extracted")),
        "focused_traced_candidate_nodes": _safe_int(enriched.get("total_candidate_nodes_with_trace_text")),
        "trace_preserved_gold_cases": _safe_int(enriched.get("cases_gold_canonical_in_extracted_node_finals")),
        "aggregate_gold_cases": _safe_int(enriched.get("cases_gold_canonical_in_casebook_candidates_aggregate")),
        "retry_trace_complete_losses": _safe_int(retry.get("total_trace_complete_losses_collected")),
        "per_case_trace_index_rows": len(trace_rows),
        "per_case_trace_paths_missing": len(missing_paths),
        "missing_trace_paths_sample": missing_paths[:10],
    }
    return rows, summary


def write_report(path: Path, rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    lines = [
        "# Trace Artifact Inventory",
        "",
        f"Generated: `{summary['generated_at_utc']}`",
        "",
        "## Headline counts",
        "",
        f"- Broad trace-complete casebook rows: {summary['broad_trace_complete_rows']}",
        f"- Focused rows: {summary['focused_rows']}",
        f"- Focused candidate nodes: {summary['focused_candidate_nodes']}",
        f"- Focused traced candidate nodes: {summary['focused_traced_candidate_nodes']}",
        f"- Aggregate gold cases: {summary['aggregate_gold_cases']}",
        f"- Trace-preserved gold cases: {summary['trace_preserved_gold_cases']}",
        f"- Retry trace-complete losses: {summary['retry_trace_complete_losses']}",
        f"- Raw per-case trace-index rows: {summary['per_case_trace_index_rows']}",
        f"- Missing trace paths in index: {summary['per_case_trace_paths_missing']}",
        "",
        "## Artifacts",
        "",
        "| Artifact | Level | Rows | Path | Notes |",
        "|---|---|---:|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row.get('artifact', '')} | {row.get('artifact_level', '')} | {row.get('rows', '')} | `{row.get('path', '')}` | {row.get('notes', '')} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "The 47-row broad casebook is aggregate-level. The focused33 enriched artifact is the current node-trace input for Cobbe-inspired selector work. The raw per-case trace index contains additional traced validation examples and should not be treated as the same population as the external-loss casebook.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--roots", nargs="*", default=["outputs", "archive", "logs"])
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    roots = [Path(root) for root in args.roots]
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows, summary = inventory(roots)
    _write_csv(out_dir / "trace_artifact_inventory.csv", rows)
    (out_dir / "trace_artifact_inventory.json").write_text(json.dumps({"summary": summary, "artifacts": rows}, indent=2) + "\n", encoding="utf-8")
    write_report(out_dir / "trace_artifact_inventory_report.md", rows, summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
