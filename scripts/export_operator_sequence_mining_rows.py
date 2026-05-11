#!/usr/bin/env python3
"""Export operator-sequence mining rows from existing offline artifacts."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_INPUT = REPO_ROOT / "outputs/cohere_paired_pal_retry_vs_external_l1_300case_20260506T194114Z/per_example_records.jsonl"
PREFERRED_FILENAMES = (
    "per_example_records.jsonl",
    "action_trace.jsonl",
    "tree_decision_traces.jsonl",
    "candidate_trace_enriched.jsonl",
    "unified_candidate_trace_enriched.jsonl",
    "focused33_trace_enriched.jsonl",
    "selected_100_cases.jsonl",
    "per_method_raw_outputs.jsonl",
    "branch_traces.jsonl",
    "trace_complete_loss_cases.jsonl",
    "candidate_trace_records.jsonl",
)

from experiments.operator_sequence_mining import build_path_prefix_row  # noqa: E402


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            obj = json.loads(text)
            if isinstance(obj, dict):
                rows.append(obj)
    return rows


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _stringify(value: Any) -> str:
    return str(value).strip()


def _resolve_existing_path(raw: str) -> Path:
    candidate = Path(raw).expanduser()
    search_roots = [candidate]
    if not candidate.is_absolute():
        search_roots = [REPO_ROOT / candidate, candidate]

    for root in search_roots:
        if root.is_file():
            return root
        if root.is_dir():
            for name in PREFERRED_FILENAMES:
                direct = root / name
                if direct.is_file():
                    return direct
            for name in PREFERRED_FILENAMES:
                matches = sorted(root.rglob(name))
                if matches:
                    return matches[0]

    raise FileNotFoundError(f"Missing input artifact: {raw}")


def _extract_nested_fields(records: list[dict[str, Any]]) -> dict[str, list[str]]:
    top_level: set[str] = set()
    metadata_fields: set[str] = set()
    trace_fields: set[str] = set()
    final_node_fields: set[str] = set()

    for record in records:
        top_level.update(record.keys())
        metadata = record.get("result_metadata")
        if isinstance(metadata, dict):
            metadata_fields.update(metadata.keys())
            trace = metadata.get("action_trace")
            if isinstance(trace, list):
                for node in trace:
                    if isinstance(node, dict):
                        trace_fields.update(node.keys())
            final_states = metadata.get("final_branch_states")
            if isinstance(final_states, list):
                for node in final_states:
                    if isinstance(node, dict):
                        trace_fields.update(node.keys())
        final_nodes = record.get("final_nodes")
        if isinstance(final_nodes, list):
            for node in final_nodes:
                if isinstance(node, dict):
                    final_node_fields.update(node.keys())

    return {
        "available_top_level_fields": sorted(top_level),
        "available_result_metadata_fields": sorted(metadata_fields),
        "available_trace_fields": sorted(trace_fields),
        "available_final_node_fields": sorted(final_node_fields),
    }


def _record_trace_nodes(record: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    metadata = record.get("result_metadata")
    if isinstance(metadata, dict):
        action_trace = metadata.get("action_trace")
        if isinstance(action_trace, list) and action_trace:
            return "action_trace", [node for node in action_trace if isinstance(node, dict)]
        final_branch_states = metadata.get("final_branch_states")
        if isinstance(final_branch_states, list) and final_branch_states:
            return "final_branch_states", [node for node in final_branch_states if isinstance(node, dict)]

    final_nodes = record.get("final_nodes")
    if isinstance(final_nodes, list) and final_nodes:
        return "final_nodes", [node for node in final_nodes if isinstance(node, dict)]

    return "record_singleton", [record]


def _node_answer(node: dict[str, Any], record: dict[str, Any]) -> str:
    for key in (
        "predicted_answer_normalized",
        "normalized_answer",
        "predicted_answer",
        "final_answer_canonical",
        "selected_answer_canonical",
        "extracted_answer",
        "answer",
        "group_key",
    ):
        value = _stringify(node.get(key))
        if value:
            return value
    return _stringify(record.get("selected_answer_canonical") or record.get("final_answer_canonical"))


def _current_answer_group(node: dict[str, Any], record: dict[str, Any]) -> str:
    return _node_answer(node, record)


def _answer_group_counts(record: dict[str, Any], nodes: list[dict[str, Any]], source_kind: str) -> dict[str, int]:
    metadata = record.get("result_metadata") if isinstance(record.get("result_metadata"), dict) else {}
    for key in (
        "answer_group_support_counts",
        "direct_answer_group_counts",
        "frontier_answer_group_counts",
        "selected_answer_group_counts",
    ):
        counts = metadata.get(key) if isinstance(metadata, dict) else None
        if isinstance(counts, dict) and counts:
            out: dict[str, int] = {}
            for name, value in counts.items():
                iv = _safe_int(value, default=0)
                if iv > 0:
                    out[_stringify(name)] = iv
            if out:
                return out

    counter: Counter[str] = Counter()
    for node in nodes:
        ans = _current_answer_group(node, record)
        if ans:
            counter[ans] += 1
    if counter:
        return dict(counter)

    fallback = _current_answer_group(record, record) if source_kind == "record_singleton" else ""
    return {fallback: 1} if fallback else {}


def _normalize_operator(node: dict[str, Any], record: dict[str, Any], source_kind: str) -> str:
    text = " ".join(
        _stringify(node.get(key))
        for key in (
            "strategy_family",
            "direction_id",
            "reasoning_role",
            "action",
            "source_metadata",
            "final_answer_source",
            "branch_id",
            "reasoning_text",
            "response_text",
        )
    ).lower()

    if "uncertainty" in text and "retry" in text:
        return "uncertainty_retry"
    if node.get("uncertainty_verify_activated") in (True, 1, "1", "true"):
        return "uncertainty_retry"
    if "repair" in text or "extract" in text or "parse" in text:
        return "repair/extraction"
    if "pal" in text or "code" in text or "python" in text:
        return "PAL/code_reasoning"
    if "direct_reserve" in text or "direct_formula" in text:
        return "direct_l1_anchor"
    if source_kind == "record_singleton" and _stringify(record.get("final_answer_source")).lower() == "repair_layer":
        return "repair/extraction"
    if "equation" in text or "algebra" in text or "solve for" in text:
        return "equation_first_anchor"
    if "unit" in text or "money" in text or "ledger" in text or "currency" in text:
        return "unit_ledger_money_anchor"
    if "ratio" in text or "percent" in text or "percentage" in text:
        return "ratio_percentage_anchor"
    if "backward" in text or "check" in text or "verify" in text:
        return "backward_check_anchor"
    if "frontier" in text or "continue" in text or "expand" in text or "branch" in text or "case_split" in text:
        return "frontier_continuation"
    if "direct" in text:
        return "direct_l1_anchor"
    return "other"


def _build_rows_for_record(record: dict[str, Any], *, source_path: Path, resolved_source: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_kind, nodes = _record_trace_nodes(record)
    answer_group_counts = _answer_group_counts(record, nodes, source_kind)
    gold_answer = _stringify(record.get("gold_answer_canonical") or record.get("gold_answer"))
    record_exact_match = _safe_int(record.get("exact_match", 0), default=0)
    if not record_exact_match and gold_answer:
        record_exact_match = int(
            _stringify(record.get("selected_answer_canonical") or record.get("final_answer_canonical"))
            == gold_answer
        )
    record_gold_in_tree = _safe_int(record.get("gold_in_tree", 0), default=0)
    record_failure_tag = _stringify(record.get("failure_tag"))
    record_final_answer_source = _stringify(record.get("final_answer_source"))

    rows: list[dict[str, Any]] = []
    parent_by_node: dict[str, str] = {}
    operator_by_node: dict[str, str] = {}
    children_by_node: dict[str, list[str]] = defaultdict(list)
    terminal_quality_by_node: dict[str, float] = {}
    gold_present_by_node: dict[str, bool] = {}

    for index, node in enumerate(nodes):
        node_id = f"{_stringify(record.get('example_id') or 'example')}::{source_kind}::{index}"
        parent_id = parent_by_node.get(node_id)
        if index > 0:
            prev_node_id = f"{_stringify(record.get('example_id') or 'example')}::{source_kind}::{index - 1}"
            parent_by_node[node_id] = prev_node_id
            children_by_node[prev_node_id].append(node_id)
        else:
            parent_by_node[node_id] = ""

        operator_by_node[node_id] = _normalize_operator(node, record, source_kind)
        node_answer = _current_answer_group(node, record)
        node_is_correct = bool(gold_answer and node_answer and node_answer == gold_answer)
        terminal_quality_by_node[node_id] = 1.0 if node_is_correct else 0.0
        gold_present_by_node[node_id] = node_is_correct

        row = build_path_prefix_row(
            node_id=node_id,
            parent_by_node=parent_by_node,
            operator_by_node=operator_by_node,
            children_by_node=children_by_node,
            answer_group_counts=answer_group_counts,
            current_answer_group=node_answer or None,
            terminal_quality_by_node=terminal_quality_by_node,
            gold_present_by_node=gold_present_by_node,
            extra_feature_fields={
                "trace_index": index,
                "trace_length": len(nodes),
                "source_branch_depth": _safe_int(node.get("branch_depth"), default=index + 1),
                "source_action": _stringify(node.get("action")),
                "source_strategy_family": _stringify(node.get("strategy_family") or node.get("direction_id")),
                "source_reasoning_role": _stringify(node.get("reasoning_role")),
            },
            extra_label_fields={
                "record_exact_match": record_exact_match,
                "record_gold_in_tree": record_gold_in_tree,
                "record_failure_tag": record_failure_tag,
                "record_final_answer_source": record_final_answer_source,
                "record_final_answer_canonical": _stringify(
                    record.get("final_answer_canonical") or record.get("selected_answer_canonical") or record.get("final_answer_raw")
                ),
                "record_selected_answer_canonical": _stringify(record.get("selected_answer_canonical") or record.get("selected_answer_raw")),
                "record_gold_answer_canonical": gold_answer,
                "record_source_kind": source_kind,
            },
        )

        row.update(
            {
                "source_path": str(resolved_source),
                "source_bundle_path": str(source_path),
                "artifact_kind": source_kind,
                "example_id": _stringify(record.get("example_id")),
                "dataset": _stringify(record.get("dataset")),
                "method": _stringify(record.get("method")),
                "seed": _safe_int(record.get("seed"), default=0),
                "budget": _safe_int(record.get("budget"), default=0),
                "record_index": index,
                "record_row_kind": source_kind,
                "source_branch_id": _stringify(node.get("branch_id") or node.get("candidate_id") or node.get("node_id") or node.get("id")),
                "source_parent_branch_id": _stringify(node.get("parent_branch_id")),
                "source_source_metadata": _stringify(node.get("source_metadata")),
                "source_branch_depth": _safe_int(node.get("branch_depth"), default=index + 1),
            }
        )
        rows.append(row)

    if not rows:
        rows.append(
            build_path_prefix_row(
                node_id=f"{_stringify(record.get('example_id') or 'example')}::singleton",
                parent_by_node={},
                operator_by_node={f"{_stringify(record.get('example_id') or 'example')}::singleton": _normalize_operator(record, record, "record_singleton")},
                answer_group_counts=answer_group_counts,
                current_answer_group=_current_answer_group(record, record) or None,
                extra_feature_fields={
                    "trace_index": 0,
                    "trace_length": 1,
                    "source_branch_depth": 0,
                    "source_action": _stringify(record.get("action")),
                    "source_strategy_family": _stringify(record.get("method")),
                    "source_reasoning_role": "",
                },
                extra_label_fields={
                    "record_exact_match": record_exact_match,
                    "record_gold_in_tree": record_gold_in_tree,
                    "record_failure_tag": record_failure_tag,
                    "record_final_answer_source": record_final_answer_source,
                    "record_final_answer_canonical": _stringify(
                        record.get("final_answer_canonical") or record.get("selected_answer_canonical") or record.get("final_answer_raw")
                    ),
                    "record_selected_answer_canonical": _stringify(record.get("selected_answer_canonical") or record.get("selected_answer_raw")),
                    "record_gold_answer_canonical": gold_answer,
                    "record_source_kind": "record_singleton",
                },
            )
        )

    row_summary = {
        "example_id": _stringify(record.get("example_id")),
        "method": _stringify(record.get("method")),
        "dataset": _stringify(record.get("dataset")),
        "seed": _safe_int(record.get("seed"), default=0),
        "budget": _safe_int(record.get("budget"), default=0),
        "source_kind": source_kind,
        "trace_node_count": len(nodes),
        "row_count": len(rows),
    }
    return rows, row_summary


def _render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Operator Sequence Artifact Export",
        "",
        f"- Generated at: `{summary['generated_at_utc']}`",
        f"- Input artifacts: `{summary['input_artifact_count']}`",
        f"- Exported rows: `{summary['exported_rows']}`",
        f"- Source artifact chosen: `{summary['source_selection']['primary_source']}`",
        f"- Row type: `{summary['source_selection']['row_type']}`",
        "",
        "## Limitations",
        "",
        "- This exporter is conservative pseudo-path mining, not a full tree reconstruction.",
        "- Parent links in the chosen artifact are not reliable enough for a stable tree export, so rows are chained by trace order.",
        "- Gold-derived values appear only in `label_*` fields.",
        "",
        "## Policy",
        "",
        "- No runtime defaults were changed.",
        "- No API or model calls were made.",
        "- This is a mining artifact, not a baseline claim.",
    ]
    return "\n".join(lines) + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        nargs="+",
        default=[str(DEFAULT_INPUT)],
        help="One or more existing artifact paths, files or directories.",
    )
    parser.add_argument(
        "--output-dir",
        default="",
        help="Optional output directory. Defaults to outputs/operator_sequence_mining_rows_<timestamp>.",
    )
    parser.add_argument(
        "--timestamp",
        default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        help="UTC timestamp suffix for the default output directory.",
    )
    parser.add_argument(
        "--dry-run",
        "--validate-only",
        action="store_true",
        dest="dry_run",
        help="Validate inputs and report candidate rows without writing output.",
    )
    return parser.parse_args(argv)


def run(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)

    input_paths = [_resolve_existing_path(raw) for raw in args.input]
    all_records: list[dict[str, Any]] = []
    source_resolutions: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    row_kinds: Counter[str] = Counter()

    for source_path in input_paths:
        records = _load_jsonl(source_path)
        if not records:
            raise ValueError(f"Input artifact contains no JSONL rows: {source_path}")
        all_records.extend(records)
        fields = _extract_nested_fields(records)
        source_rows = 0
        source_row_type_counts: Counter[str] = Counter()
        for record in records:
            record_rows, row_summary = _build_rows_for_record(
                record,
                source_path=source_path,
                resolved_source=source_path,
            )
            rows.extend(record_rows)
            source_rows += len(record_rows)
            source_row_type_counts[row_summary["source_kind"]] += 1
            row_kinds[row_summary["source_kind"]] += len(record_rows)

        source_resolutions.append(
            {
                "input": str(source_path),
                "resolved": str(source_path),
                "record_count": len(records),
                "row_count": source_rows,
                "record_kind_counts": dict(source_row_type_counts),
                **fields,
            }
        )

    available_fields = {
        "available_top_level_fields": sorted({field for item in source_resolutions for field in item["available_top_level_fields"]}),
        "available_result_metadata_fields": sorted(
            {field for item in source_resolutions for field in item["available_result_metadata_fields"]}
        ),
        "available_trace_fields": sorted({field for item in source_resolutions for field in item["available_trace_fields"]}),
        "available_final_node_fields": sorted({field for item in source_resolutions for field in item["available_final_node_fields"]}),
    }
    candidate_rows = len(rows)
    output_dir = Path(args.output_dir) if args.output_dir else REPO_ROOT / "outputs" / f"operator_sequence_mining_rows_{args.timestamp}"
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_artifact_count": len(input_paths),
        "input_artifacts": [str(path) for path in input_paths],
        "source_resolutions": source_resolutions,
        "candidate_rows": candidate_rows,
        "exported_rows": candidate_rows,
        "row_kind_counts": dict(row_kinds),
        "source_selection": {
            "primary_source": str(input_paths[0]) if input_paths else "",
            "row_type": "action_trace_pseudo_path" if any(item["record_kind_counts"].get("action_trace") for item in source_resolutions) else "conservative_pseudo_path",
            "note": "Parent links were not reliable enough for stable tree mining, so rows are ordered pseudo-path chains.",
        },
        **available_fields,
    }

    if args.dry_run:
        print(json.dumps(summary, indent=2, sort_keys=True))
        return summary

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(output_dir / "path_prefix_rows.jsonl", rows)
    _write_json(output_dir / "summary.json", summary)
    (output_dir / "report.md").write_text(_render_report(summary), encoding="utf-8")
    return summary


def main() -> int:
    try:
        run()
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
