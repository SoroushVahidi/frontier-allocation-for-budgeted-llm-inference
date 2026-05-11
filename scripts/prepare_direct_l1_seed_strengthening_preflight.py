#!/usr/bin/env python3
"""Prepare a no-API preflight for a stronger direct-L1 seed experiment."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import build_pal_unresolved_pattern_taxonomy as taxonomy_builder

DEFAULT_FULL_FAILURE_CSV = REPO_ROOT / "docs/project_handoff_20260510/exhaustive_failure_audit/full_latest_method_failures.csv"
DEFAULT_GOLD_ABSENT_CSV = REPO_ROOT / "docs/project_handoff_20260510/exhaustive_failure_audit/gold_absent_subpattern_analysis_20260510.csv"
DEFAULT_ANCHOR_EFFECT_CSV = REPO_ROOT / "docs/project_handoff_20260510/exhaustive_failure_audit/direct_l1_anchor_patch_effect_20260510.csv"
DEFAULT_COVERAGE_DETAILS_CSV = ""
DEFAULT_TAXONOMY_OUTPUT_DIR = ""
DEFAULT_OUTPUT_PREFIX = "direct_l1_seed_strengthening_preflight_"
DEFAULT_OUTPUTS_ROOT = REPO_ROOT / "outputs"
DEFAULT_EXACT_REPLAY_30_JSONL = REPO_ROOT / "docs/project_handoff_20260510/exact_case_replay/failure_recovery_30case_exact_cases_20260510.jsonl"
DEFAULT_EXACT_REPLAY_50_JSONL = REPO_ROOT / "docs/project_handoff_20260510/exact_case_replay/failure_recovery_50case_exact_cases_20260510.jsonl"
DEFAULT_METHOD = taxonomy_builder.DEFAULT_METHOD
SUGGESTED_DIAGNOSTIC_CASE_IDS = (
    "openai_gsm8k_297",
    "openai_gsm8k_168",
    "openai_gsm8k_180",
    "openai_gsm8k_190",
    "openai_gsm8k_197",
    "openai_gsm8k_213",
    "openai_gsm8k_264",
    "openai_gsm8k_347",
    "openai_gsm8k_367",
    "openai_gsm8k_376",
    "openai_gsm8k_391",
    "openai_gsm8k_204",
    "openai_gsm8k_228",
    "openai_gsm8k_233",
    "openai_gsm8k_354",
)
PROPOSED_METHOD_ID = (
    "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_direct_l1_strong_seed_v1"
)

TRUE_TOKENS = {"1", "true", "t", "yes", "y"}


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        text = _stringify(value)
        if not text:
            return default
        return float(text)
    except Exception:
        return default


def _is_truthy(value: Any) -> bool:
    text = _stringify(value).lower()
    if not text:
        return False
    if text in TRUE_TOKENS:
        return True
    if text in {"0", "false", "f", "no", "n", "0.0", "0.00", "none", "nan"}:
        return False
    return bool(text)


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _read_case_ids_from_jsonl(path: Path) -> list[str]:
    ids: list[str] = []
    if not path.is_file():
        return ids
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            case_id = _stringify(payload.get("example_id") or payload.get("case_id"))
            if case_id:
                ids.append(case_id)
    return ids


def _sorted_counter(counter: Counter[str]) -> dict[str, int]:
    return dict(sorted(counter.items(), key=lambda item: (-item[1], item[0])))


def _render_table(rows: list[dict[str, Any]], headers: list[str]) -> str:
    if not rows:
        return "_No rows._"
    widths = {header: len(header) for header in headers}
    for row in rows:
        for header in headers:
            widths[header] = max(widths[header], len(_stringify(row.get(header, ""))))
    header_line = " | ".join(header.ljust(widths[header]) for header in headers)
    divider = " | ".join("-" * widths[header] for header in headers)
    body = "\n".join(
        " | ".join(_stringify(row.get(header, "")).ljust(widths[header]) for header in headers) for row in rows
    )
    return f"{header_line}\n{divider}\n{body}"


def _resolve_taxonomy_rows(
    *,
    taxonomy_output_dir: Path | None,
    failure_csv: Path,
    gold_absent_csv: Path,
    coverage_details_csv: Path,
    anchor_effect_csv: Path,
    outputs_root: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any], str]:
    if taxonomy_output_dir is not None:
        cases_csv = taxonomy_output_dir / "pal_unresolved_cases.csv"
        summary_json = taxonomy_output_dir / "summary.json"
        if cases_csv.is_file():
            rows = [dict(row) for row in _read_csv_rows(cases_csv)]
            summary: dict[str, Any] = {}
            if summary_json.is_file():
                try:
                    summary = json.loads(summary_json.read_text(encoding="utf-8"))
                except Exception:
                    summary = {}
            return rows, summary, "taxonomy_output_dir"

    if not coverage_details_csv.is_file():
        coverage_details_csv = taxonomy_builder._latest_case_coverage_csv(outputs_root)  # type: ignore[attr-defined]
    if coverage_details_csv is None or not coverage_details_csv.is_file():
        raise FileNotFoundError(
            f"Missing coverage-details CSV: supply --coverage-details-csv or place case_coverage_details.csv under {outputs_root}"
        )

    summary = taxonomy_builder._summarize(
        method=DEFAULT_METHOD,
        failure_csv=failure_csv,
        gold_absent_csv=gold_absent_csv,
        coverage_details_csv=coverage_details_csv,
        anchor_effect_csv=anchor_effect_csv,
        outputs_root=outputs_root,
    )
    return list(summary["case_rows"]), summary, "recomputed_from_source_csvs"


def _row_case_id(row: dict[str, Any]) -> str:
    return _stringify(row.get("case_id") or row.get("example_id"))


def _row_score(row: dict[str, Any]) -> float:
    score = _safe_float(row.get("score"), default=float("-inf"))
    if score != float("-inf"):
        return score
    score = 0.0
    if _is_truthy(row.get("direct_l1_anchor_potential")):
        score += 50.0
    if _is_truthy(row.get("wrong_supported_consensus")):
        score += 30.0
    if _is_truthy(row.get("frontier_collapse_low_diversity")):
        score += 20.0
    if _is_truthy(row.get("premature_intermediate_answer")):
        score += 45.0
    if _is_truthy(row.get("counting_grouping_off_by_factor")):
        score += 40.0
    if _is_truthy(row.get("structured_extraction_failure")):
        score += 35.0
    if _is_truthy(row.get("external_l1_exact")):
        score += 10.0
    if _is_truthy(row.get("anchor_matches_l1_max")):
        score += 5.0
    domain_label = _stringify(row.get("domain_label"))
    if domain_label in {
        "domain_money_cost_revenue",
        "domain_ratio_proportion_percentage",
        "domain_multi_step_arithmetic",
    }:
        score += 2.0
    return score


def _selection_source(row: dict[str, Any], *, selected_order: int | None, suggested: bool) -> str:
    if suggested:
        return "suggested_preserved"
    if selected_order is None:
        return "ranked_fill"
    return f"ranked_fill_{selected_order:02d}"


def _build_anchor_potential_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    anchor_rows = [row for row in rows if _is_truthy(row.get("direct_l1_anchor_potential"))]
    for row in anchor_rows:
        row["case_id"] = _row_case_id(row)
        row["score"] = f"{_row_score(row):.1f}"
    anchor_rows.sort(key=lambda row: (-_row_score(row), _stringify(row.get("domain_label")), _row_case_id(row)))
    return anchor_rows


def _select_diagnostic_rows(anchor_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    anchor_by_id = {_row_case_id(row): row for row in anchor_rows}
    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    missing: list[str] = []

    for case_id in SUGGESTED_DIAGNOSTIC_CASE_IDS:
        row = anchor_by_id.get(case_id)
        if row is None:
            missing.append(case_id)
            continue
        selected.append(
            {
                **row,
                "selection_source": _selection_source(row, selected_order=None, suggested=True),
                "selection_rank": len(selected) + 1,
            }
        )
        selected_ids.add(case_id)

    fill_candidates = [row for row in anchor_rows if _row_case_id(row) not in selected_ids]
    fill_candidates.sort(key=lambda row: (-_row_score(row), _stringify(row.get("domain_label")), _row_case_id(row)))
    for fill_index, row in enumerate(fill_candidates, start=1):
        if len(selected) >= len(SUGGESTED_DIAGNOSTIC_CASE_IDS):
            break
        selected.append(
            {
                **row,
                "selection_source": _selection_source(row, selected_order=fill_index, suggested=False),
                "selection_rank": len(selected) + 1,
            }
        )
        selected_ids.add(_row_case_id(row))

    return selected, missing


def _load_selected_exact_ids(path: Path) -> list[str]:
    return _read_case_ids_from_jsonl(path)


def _build_summary(
    *,
    rows: list[dict[str, Any]],
    failure_csv: Path,
    gold_absent_csv: Path,
    taxonomy_source_mode: str,
    taxonomy_output_dir: Path | None,
    exact_30_ids: list[str],
    exact_50_ids: list[str],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    anchor_rows = _build_anchor_potential_rows(rows)
    anchor_ids = {_row_case_id(row) for row in anchor_rows}
    strong_rows = [row for row in anchor_rows if _is_truthy(row.get("anchor_matches_l1_max"))]
    selected_rows, missing_suggested_case_ids = _select_diagnostic_rows(anchor_rows)
    selected_ids = [_row_case_id(row) for row in selected_rows]
    selected_id_set = set(selected_ids)
    exact_30_set = set(exact_30_ids)
    exact_50_set = set(exact_50_ids)

    domain_counts = Counter(_stringify(row.get("domain_label")) for row in anchor_rows)
    exact_overlap = {
        "exact_replay_30_count": len(anchor_id_set := anchor_ids & exact_30_set),
        "exact_replay_50_count": len(anchor_ids & exact_50_set),
        "exact_replay_30_case_ids": sorted(anchor_id_set),
        "exact_replay_50_case_ids": sorted(anchor_ids & exact_50_set),
        "selected_15_overlap_30_count": len(selected_id_set & exact_30_set),
        "selected_15_overlap_50_count": len(selected_id_set & exact_50_set),
        "selected_15_overlap_30_case_ids": sorted(selected_id_set & exact_30_set),
        "selected_15_overlap_50_case_ids": sorted(selected_id_set & exact_50_set),
        "strong_overlap_30_count": len({ _row_case_id(row) for row in strong_rows } & exact_30_set),
        "strong_overlap_50_count": len({ _row_case_id(row) for row in strong_rows } & exact_50_set),
    }

    failure_rows = _read_csv_rows(failure_csv)
    gold_rows = _read_csv_rows(gold_absent_csv)
    summary: dict[str, Any] = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_mode": taxonomy_source_mode,
        "taxonomy_output_dir": str(taxonomy_output_dir) if taxonomy_output_dir else "",
        "failure_corpus_rows": len(failure_rows),
        "unique_failure_ids": len({_row_case_id(row) for row in failure_rows if _row_case_id(row)}),
        "gold_absent_rows": len(gold_rows),
        "gold_absent_case_ids": len({_row_case_id(row) for row in gold_rows if _row_case_id(row)}),
        "unresolved_cases_count": len(rows),
        "anchor_potential_count": len(anchor_rows),
        "strong_patch_effect_count": len(strong_rows),
        "domain_counts": _sorted_counter(domain_counts),
        "anchor_potential_case_ids": [_row_case_id(row) for row in anchor_rows],
        "strong_patch_effect_case_ids": [_row_case_id(row) for row in strong_rows],
        "selected_diagnostic_case_ids": selected_ids,
        "missing_suggested_case_ids": missing_suggested_case_ids,
        "exact_replay_overlap": exact_overlap,
        "current_direct_l1_behavior": [
            "direct_l1_anchor is the direct-hybrid seed record with prompt style direct_l1_max_budget and source family direct_l1_anchor.",
            "Direct hybrid seed is opt-in behind enable_direct_hybrid_seed, which defaults to False in the controller constructor.",
            "Diverse prompt anchors are opt-in behind enable_diverse_prompt_anchors, which also defaults to False.",
            "When diverse anchors are off, the controller still synthesizes a direct_l1_anchor record from the hybrid seed answer for candidate-pool accounting.",
            "When diverse anchors are on, the direct_l1 anchor is special-cased so the hybrid seed does not silently double-spend budget.",
        ],
        "candidate_stronger_seed_designs": [
            "Stronger direct extraction of the target variable and final numeric answer.",
            "Equation skeleton first, then direct solve.",
            "Direct answer plus independent arithmetic/unit self-check.",
            "Direct answer plus anti-premature-intermediate-answer instruction.",
            "Direct answer plus forced final 'what is being asked?' check.",
        ],
        "recommended_design": "Direct answer plus independent arithmetic/unit self-check.",
        "proposed_method_id": PROPOSED_METHOD_ID,
        "validation_plan": [
            "Run a no-API method registry check first to confirm the proposed method ID is still opt-in and not wired into the controller defaults.",
            "Validate the exact 15-case diagnostic loader against the anchor-potential slice.",
            "Run a dry-run/call-plan pass before any paid run.",
            "Only after explicit approval, run a live 15-case diagnostic.",
        ],
        "claim_boundaries": [
            "No external-baseline claim.",
            "No current accuracy claim.",
            "This is only preflight/design.",
            "No runtime default change.",
            "No paid/model API calls.",
        ],
        "recommended_rationale": (
            "The current bottleneck is discovery, not selector polish, so the next implementation should stay on the seed path. "
            f"The anchor-potential slice has {len(anchor_rows)} cases and the strongest patch-effect subset has {len(strong_rows)} cases."
        ),
    }
    return summary, anchor_rows, strong_rows, selected_rows


def _render_report(summary: dict[str, Any], anchor_rows: list[dict[str, Any]], strong_rows: list[dict[str, Any]], selected_rows: list[dict[str, Any]]) -> str:
    domain_rows = [
        {
            "domain_label": domain,
            "count": count,
            "share_of_anchor_potential": round(count / max(1, len(anchor_rows)), 6),
        }
        for domain, count in summary["domain_counts"].items()
    ]
    exact_overlap = summary["exact_replay_overlap"]
    overlap_rows = [
        {
            "slice": "anchor_potential",
            "exact_replay_30": exact_overlap["exact_replay_30_count"],
            "exact_replay_50": exact_overlap["exact_replay_50_count"],
        },
        {
            "slice": "strong_patch_effect",
            "exact_replay_30": exact_overlap["strong_overlap_30_count"],
            "exact_replay_50": exact_overlap["strong_overlap_50_count"],
        },
        {
            "slice": "selected_15",
            "exact_replay_30": exact_overlap["selected_15_overlap_30_count"],
            "exact_replay_50": exact_overlap["selected_15_overlap_50_count"],
        },
    ]
    selected_rows_render = [
        {
            "selection_rank": row["selection_rank"],
            "case_id": row["case_id"],
            "selection_source": row["selection_source"],
            "domain_label": row.get("domain_label", ""),
            "score": row.get("score", ""),
            "anchor_matches_l1_max": int(_is_truthy(row.get("anchor_matches_l1_max"))),
            "external_l1_exact": int(_is_truthy(row.get("external_l1_exact"))),
        }
        for row in selected_rows
    ]
    missing = summary["missing_suggested_case_ids"]
    lines = [
        "# Direct L1 Seed Strengthening Preflight",
        "",
        "## Observed Facts",
        "",
        f"- Full failure corpus rows: `{summary['failure_corpus_rows']}`",
        f"- Unique fully tracked failure IDs: `{summary['unique_failure_ids']}`",
        f"- Gold-absent rows: `{summary['gold_absent_rows']}`",
        f"- Gold-absent case IDs: `{summary['gold_absent_case_ids']}`",
        f"- Unresolved PAL cases: `{summary['unresolved_cases_count']}`",
        f"- Anchor-potential cases: `{summary['anchor_potential_count']}`",
        f"- Strong patch-effect cases: `{summary['strong_patch_effect_count']}`",
        f"- Suggested 15-case slice size: `{len(selected_rows)}`",
        f"- Missing suggested case IDs: `{', '.join(missing) if missing else 'none'}`",
        "",
        "### Domain Distribution",
        "",
        _render_table(domain_rows, ["domain_label", "count", "share_of_anchor_potential"]),
        "",
        "### Exact-Replay Overlap",
        "",
        _render_table(overlap_rows, ["slice", "exact_replay_30", "exact_replay_50"]),
        "",
        "## Current Direct L1 Anchor Behavior",
        "",
    ]
    for item in summary["current_direct_l1_behavior"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Candidate Stronger-Seed Designs",
            "",
        ]
    )
    for item in summary["candidate_stronger_seed_designs"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Recommended Design",
            "",
            f"- {summary['recommended_design']}",
            f"- Rationale: {summary['recommended_rationale']}",
            "",
            "## Proposed Opt-In Method ID",
            "",
            f"`{summary['proposed_method_id']}`",
            "",
            "## Exact Next Validation Plan",
            "",
        ]
    )
    for idx, item in enumerate(summary["validation_plan"], start=1):
        lines.append(f"{idx}. {item}")
    lines.extend(
        [
            "",
            "## Selected 15-Case Slice",
            "",
            _render_table(selected_rows_render, ["selection_rank", "case_id", "selection_source", "domain_label", "score", "anchor_matches_l1_max", "external_l1_exact"]),
            "",
            "## Why Not Another Selector Patch",
            "",
            "- The main loss is discovery: if the gold answer never enters the pool, selector tweaks cannot recover it.",
            "- The 43 anchor-potential cases are the smallest high-signal slice with explicit direct-L1 evidence, so they are the right first target for a stronger seed.",
            "- The 15-case slice is only a diagnostic starter set, not proof of improvement.",
            "",
            "## Claim Boundaries",
            "",
        ]
    )
    for item in summary["claim_boundaries"]:
        lines.append(f"- {item}")
    return "\n".join(lines).rstrip() + "\n"


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--taxonomy-output-dir",
        default=DEFAULT_TAXONOMY_OUTPUT_DIR,
        help="Optional precomputed taxonomy output directory. If present and it contains pal_unresolved_cases.csv, the script reuses it.",
    )
    parser.add_argument(
        "--full-failure-csv",
        default=str(DEFAULT_FULL_FAILURE_CSV),
        help="Fully tracked latest-method failure corpus CSV.",
    )
    parser.add_argument(
        "--gold-absent-csv",
        default=str(DEFAULT_GOLD_ABSENT_CSV),
        help="Gold-absent subpattern CSV.",
    )
    parser.add_argument(
        "--anchor-effect-csv",
        default=str(DEFAULT_ANCHOR_EFFECT_CSV),
        help="Direct L1 anchor patch-effect CSV.",
    )
    parser.add_argument(
        "--coverage-details-csv",
        default=DEFAULT_COVERAGE_DETAILS_CSV,
        help="Coverage details CSV from the recovery audit. If omitted, the newest outputs/latest_failure_recovery_coverage_*/case_coverage_details.csv is used when recomputing.",
    )
    parser.add_argument(
        "--outputs-root",
        default=str(DEFAULT_OUTPUTS_ROOT),
        help="Root directory used when auto-discovering the latest coverage audit output.",
    )
    parser.add_argument(
        "--exact-replay-30-jsonl",
        default=str(DEFAULT_EXACT_REPLAY_30_JSONL),
        help="Exact 30-case replay slice JSONL used for overlap detection.",
    )
    parser.add_argument(
        "--exact-replay-50-jsonl",
        default=str(DEFAULT_EXACT_REPLAY_50_JSONL),
        help="Exact 50-case replay slice JSONL used for overlap detection.",
    )
    parser.add_argument(
        "--output-dir",
        default="",
        help="Optional output directory. Defaults to outputs/direct_l1_seed_strengthening_preflight_<timestamp>.",
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
        help="Validate inputs and print a compact summary without writing files.",
    )
    return parser.parse_args(argv)


def run(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    failure_csv = Path(args.full_failure_csv).expanduser()
    gold_absent_csv = Path(args.gold_absent_csv).expanduser()
    anchor_effect_csv = Path(args.anchor_effect_csv).expanduser()
    outputs_root = Path(args.outputs_root).expanduser()
    taxonomy_output_dir = Path(args.taxonomy_output_dir).expanduser() if args.taxonomy_output_dir else None
    exact_30_jsonl = Path(args.exact_replay_30_jsonl).expanduser()
    exact_50_jsonl = Path(args.exact_replay_50_jsonl).expanduser()

    if not failure_csv.is_file():
        raise FileNotFoundError(f"Missing failure corpus CSV: {failure_csv}")
    if not gold_absent_csv.is_file():
        raise FileNotFoundError(f"Missing gold-absent CSV: {gold_absent_csv}")
    if not anchor_effect_csv.is_file():
        raise FileNotFoundError(f"Missing anchor-effect CSV: {anchor_effect_csv}")

    if taxonomy_output_dir is not None and not taxonomy_output_dir.exists():
        raise FileNotFoundError(f"Missing taxonomy output directory: {taxonomy_output_dir}")

    coverage_details_csv = Path(args.coverage_details_csv).expanduser() if args.coverage_details_csv else Path()
    rows, taxonomy_summary, taxonomy_source_mode = _resolve_taxonomy_rows(
        taxonomy_output_dir=taxonomy_output_dir,
        failure_csv=failure_csv,
        gold_absent_csv=gold_absent_csv,
        coverage_details_csv=coverage_details_csv,
        anchor_effect_csv=anchor_effect_csv,
        outputs_root=outputs_root,
    )

    exact_30_ids = _load_selected_exact_ids(exact_30_jsonl)
    exact_50_ids = _load_selected_exact_ids(exact_50_jsonl)

    summary, anchor_rows, strong_rows, selected_rows = _build_summary(
        rows=rows,
        failure_csv=failure_csv,
        gold_absent_csv=gold_absent_csv,
        taxonomy_source_mode=taxonomy_source_mode,
        taxonomy_output_dir=taxonomy_output_dir,
        exact_30_ids=exact_30_ids,
        exact_50_ids=exact_50_ids,
    )
    if taxonomy_summary:
        summary["taxonomy_output_summary_present"] = True
        summary["taxonomy_output_dir_loaded"] = str(taxonomy_output_dir) if taxonomy_output_dir else ""
    summary["selected_15_case_rows"] = selected_rows
    summary["anchor_potential_case_rows"] = anchor_rows
    summary["strong_patch_effect_case_rows"] = strong_rows
    summary_output = {k: v for k, v in summary.items() if k not in {"selected_15_case_rows", "anchor_potential_case_rows", "strong_patch_effect_case_rows"}}

    if not args.dry_run:
        output_dir = Path(args.output_dir).expanduser() if args.output_dir else REPO_ROOT / "outputs" / f"{DEFAULT_OUTPUT_PREFIX}{args.timestamp}"
        output_dir.mkdir(parents=True, exist_ok=True)
        anchor_fields = [
            "case_id",
            "score",
            "question_type",
            "domain_label",
            "error_type",
            "failure_family",
            "anchor_matches_l1_max",
            "external_l1_exact",
            "gold_recovered",
            "direct_l1_anchor_potential",
            "pattern_labels",
            "selection_source",
            "in_exact_replay_30",
            "in_exact_replay_50",
        ]
        diag_fields = [
            "selection_rank",
            "case_id",
            "selection_source",
            "score",
            "question_type",
            "domain_label",
            "error_type",
            "failure_family",
            "anchor_matches_l1_max",
            "external_l1_exact",
            "gold_recovered",
            "direct_l1_anchor_potential",
            "pattern_labels",
            "in_exact_replay_30",
            "in_exact_replay_50",
        ]
        anchor_rows_out: list[dict[str, Any]] = []
        selected_rows_out: list[dict[str, Any]] = []
        anchor_selected_ids = set(summary_output["selected_diagnostic_case_ids"])
        exact_30_set = set(exact_30_ids)
        exact_50_set = set(exact_50_ids)
        for row in anchor_rows:
            case_id = _row_case_id(row)
            anchor_rows_out.append(
                {
                    **row,
                    "in_exact_replay_30": int(case_id in exact_30_set),
                    "in_exact_replay_50": int(case_id in exact_50_set),
                    "selection_source": "selected_15" if case_id in anchor_selected_ids else "",
                }
            )
        for row in selected_rows:
            case_id = _row_case_id(row)
            selected_rows_out.append(
                {
                    **row,
                    "in_exact_replay_30": int(case_id in exact_30_set),
                    "in_exact_replay_50": int(case_id in exact_50_set),
                }
            )
        _write_csv(output_dir / "direct_l1_anchor_potential_cases.csv", anchor_rows_out, anchor_fields)
        _write_csv(output_dir / "direct_l1_seed_diagnostic_15case.csv", selected_rows_out, diag_fields)
        (output_dir / "summary.json").write_text(json.dumps(summary_output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (output_dir / "direct_l1_seed_strengthening_preflight_report.md").write_text(
            _render_report(summary_output, anchor_rows, strong_rows, selected_rows),
            encoding="utf-8",
        )
    else:
        print(json.dumps(summary_output, indent=2, sort_keys=True))

    return summary_output


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
