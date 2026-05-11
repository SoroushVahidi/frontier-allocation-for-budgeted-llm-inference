#!/usr/bin/env python3
"""Audit recovery coverage for the fully tracked latest-method failure corpus."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FAILURE_CSV = REPO_ROOT / "docs/project_handoff_20260510/exhaustive_failure_audit/full_latest_method_failures.csv"
DEFAULT_GOLD_ABSENT_CSV = REPO_ROOT / "docs/project_handoff_20260510/exhaustive_failure_audit/gold_absent_subpattern_analysis_20260510.csv"
DEFAULT_OUTPUTS_ROOT = REPO_ROOT / "outputs"
DEFAULT_METHODS = (
    "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_uncertainty_retry_v1",
    "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_diverse_anchor",
    "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal",
)

TRUE_TOKENS = {"1", "true", "t", "yes", "y"}
FALSE_TOKENS = {"0", "false", "f", "no", "n"}
CORRECTNESS_TRUE_FIELDS = (
    "is_correct",
    "exact_match",
    "exact",
    "correct",
    "production_equiv_correct",
    "pal_correct",
    "exact_match_raw_runner",
)
CORRECTNESS_FALSE_FIELDS = tuple(CORRECTNESS_TRUE_FIELDS)
ID_FIELDS = ("case_id", "example_id", "id")
METHOD_FIELDS = ("method", "method_id", "method_name")
PREDICTION_FIELDS = (
    "prediction",
    "predicted_answer",
    "selected_answer",
    "final_answer",
    "final_answer_canonical",
    "production_equiv_answer",
    "pal_answer",
    "normalized_answer",
)
GOLD_FIELDS = (
    "gold",
    "gold_answer",
    "gold_answer_canonical",
    "answer",
    "selected_failure_gold",
)
VALIDITY_FALSE_FIELDS = (
    "valid_for_primary_question",
    "valid_for_selected_failure_case",
)
VALIDITY_FALSE_TOKENS = FALSE_TOKENS | {"invalid", "false", "0"}
TIMESTAMP_RE = re.compile(r"(?P<stamp>\d{8}T\d{6}Z)")


@dataclass(frozen=True)
class FailureCase:
    case_id: str
    method_ids: tuple[str, ...]
    failure_family: str
    gold_answer: str
    is_gold_absent: bool
    source_rows: tuple[dict[str, str], ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ArtifactMatch:
    case_id: str
    method: str
    source_path: str
    row_index: int
    row: dict[str, str]
    validity: str
    correctness_status: str
    correctness_field: str
    prediction: str
    gold: str
    status_text: str
    evidence_score: int
    time_key: str


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_case_id(value: Any) -> str:
    text = _stringify(value)
    if not text:
        return ""
    return text


def _normalize_method(value: Any) -> str:
    return _stringify(value)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except Exception:
        return default


def _safe_bool_text(value: Any) -> bool | None:
    text = _stringify(value).lower()
    if not text:
        return None
    if text in TRUE_TOKENS:
        return True
    if text in FALSE_TOKENS:
        return False
    return None


def _normalize_numberish(text: str) -> str:
    raw = _stringify(text)
    if not raw:
        return ""
    cleaned = raw.replace(",", "").strip()
    try:
        value = float(cleaned)
    except Exception:
        return cleaned
    if value.is_integer():
        return str(int(value))
    return ("%f" % value).rstrip("0").rstrip(".")


def _load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader]


def _load_jsonl_rows(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            obj = json.loads(text)
            if isinstance(obj, dict):
                rows.append({str(k): "" if v is None else str(v) for k, v in obj.items()})
    return rows


def _iter_failure_rows(path: Path) -> list[dict[str, str]]:
    if path.suffix == ".csv":
        return _load_csv_rows(path)
    raise ValueError(f"Unsupported failure corpus format: {path}")


def _load_failure_cases(path: Path, gold_absent_ids: set[str]) -> dict[str, FailureCase]:
    rows = _iter_failure_rows(path)
    cases: dict[str, FailureCase] = {}
    grouped_rows: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        case_id = _normalize_case_id(row.get("case_id"))
        if not case_id:
            continue
        grouped_rows[case_id].append(row)

    for case_id, case_rows in grouped_rows.items():
        method_ids = tuple(sorted({_normalize_method(r.get("method_id")) for r in case_rows if _normalize_method(r.get("method_id"))}))
        failure_family = next((r.get("failure_family", "") for r in case_rows if _stringify(r.get("failure_family"))), "")
        gold_answer = next((_stringify(r.get("gold_answer")) for r in case_rows if _stringify(r.get("gold_answer"))), "")
        cases[case_id] = FailureCase(
            case_id=case_id,
            method_ids=method_ids,
            failure_family=_stringify(failure_family),
            gold_answer=gold_answer,
            is_gold_absent=case_id in gold_absent_ids,
            source_rows=tuple(case_rows),
        )
    return cases


def _load_gold_absent_ids(path: Path) -> set[str]:
    rows = _iter_failure_rows(path)
    case_ids = {_normalize_case_id(row.get("case_id")) for row in rows if _normalize_case_id(row.get("case_id"))}
    return case_ids


def _extract_case_id(row: dict[str, str]) -> str:
    for field in ID_FIELDS:
        value = _normalize_case_id(row.get(field))
        if value:
            return value
    return ""


def _extract_method(row: dict[str, str]) -> str:
    for field in METHOD_FIELDS:
        value = _normalize_method(row.get(field))
        if value:
            return value
    return ""


def _extract_prediction(row: dict[str, str]) -> str:
    for field in PREDICTION_FIELDS:
        value = _stringify(row.get(field))
        if value:
            return value
    return ""


def _extract_gold(row: dict[str, str]) -> str:
    for field in GOLD_FIELDS:
        value = _stringify(row.get(field))
        if value:
            return value
    return ""


def _extract_validity(row: dict[str, str]) -> str:
    for field in VALIDITY_FALSE_FIELDS:
        raw = _safe_bool_text(row.get(field))
        if raw is False:
            return "invalid"
        if _stringify(row.get(field)).lower() in VALIDITY_FALSE_TOKENS:
            return "invalid"
    if _stringify(row.get("run_status")).lower().startswith("invalid"):
        return "invalid"
    if _stringify(row.get("status")).lower().startswith("invalid"):
        return "invalid"
    return "valid"


def _extract_time_key(path: Path) -> str:
    matches = [m.group("stamp") for m in TIMESTAMP_RE.finditer(str(path))]
    if not matches:
        return ""
    return max(matches)


def _field_count(row: dict[str, str], fields: Iterable[str]) -> int:
    return sum(1 for field in fields if _stringify(row.get(field)))


def _infer_correctness(row: dict[str, str]) -> tuple[str, str]:
    for field in CORRECTNESS_TRUE_FIELDS:
        raw = row.get(field)
        if raw is None or _stringify(raw) == "":
            continue
        bool_value = _safe_bool_text(raw)
        if bool_value is True:
            return "resolved", field
        if bool_value is False:
            return "still_fails", field
        if field in {"exact_match", "exact", "correct", "production_equiv_correct", "pal_correct", "exact_match_raw_runner"}:
            numeric = _safe_int(raw, default=-1)
            if numeric == 1:
                return "resolved", field
            if numeric == 0:
                return "still_fails", field

    prediction = _normalize_numberish(_extract_prediction(row))
    gold = _normalize_numberish(_extract_gold(row))
    if prediction and gold:
        return ("resolved", "prediction==gold") if prediction == gold else ("still_fails", "prediction!=gold")

    if _stringify(row.get("status")).lower() in {"scored", "completed", "complete", "done"}:
        return "unknown", "status_only"

    return "unknown", ""


def _artifact_rows(path: Path) -> list[dict[str, str]]:
    if path.suffix == ".csv":
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                return []
            fieldset = {field for field in reader.fieldnames if field}
            if not (fieldset.intersection(ID_FIELDS) and fieldset.intersection(METHOD_FIELDS)):
                return []
            return [dict(row) for row in reader]
    if path.suffix == ".jsonl":
        rows = _load_jsonl_rows(path)
        if not rows:
            return []
        fieldset = set(rows[0].keys())
        if not (fieldset.intersection(ID_FIELDS) and fieldset.intersection(METHOD_FIELDS)):
            return []
        return rows
    return []


def _scan_artifacts(
    outputs_root: Path, requested_methods: set[str]
) -> tuple[list[ArtifactMatch], dict[str, int]]:
    matches: list[ArtifactMatch] = []
    invalidated_methods: dict[str, int] = defaultdict(int)
    for path in sorted(outputs_root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix not in {".csv", ".jsonl"}:
            continue
        try:
            rows = _artifact_rows(path)
        except Exception:
            continue
        if not rows:
            continue
        time_key = _extract_time_key(path)
        for row_index, row in enumerate(rows):
            case_id = _extract_case_id(row)
            method = _extract_method(row)
            if not case_id or not method or method not in requested_methods:
                continue
            validity = _extract_validity(row)
            if validity != "valid":
                invalidated_methods[method] += 1
                continue
            correctness_status, correctness_field = _infer_correctness(row)
            prediction = _extract_prediction(row)
            gold = _extract_gold(row)
            matches.append(
                ArtifactMatch(
                    case_id=case_id,
                    method=method,
                    source_path=str(path.relative_to(REPO_ROOT)) if path.is_relative_to(REPO_ROOT) else str(path),
                    row_index=row_index,
                    row=row,
                    validity=validity,
                    correctness_status=correctness_status,
                    correctness_field=correctness_field,
                    prediction=prediction,
                    gold=gold,
                    status_text=_stringify(row.get("status")),
                    evidence_score=_field_count(
                        row,
                        (
                            *ID_FIELDS,
                            *METHOD_FIELDS,
                            *PREDICTION_FIELDS,
                            *GOLD_FIELDS,
                            "status",
                            "failure_tag",
                            "result_metadata",
                            "gold_in_tree",
                            "parse_extraction_failure",
                            "final_answer_source",
                        ),
                    ),
                    time_key=time_key,
                )
            )
    return matches, invalidated_methods


def _choose_match(candidates: list[ArtifactMatch]) -> ArtifactMatch:
    def _rank(item: ArtifactMatch) -> tuple[str, int, int, str, int]:
        correctness_rank = {"resolved": 2, "still_fails": 1, "unknown": 0}.get(item.correctness_status, 0)
        return (item.time_key, correctness_rank, item.evidence_score, item.source_path, item.row_index)

    return sorted(candidates, key=_rank, reverse=True)[0]


def _summarize_matches(
    failure_cases: dict[str, FailureCase],
    requested_methods: list[str],
    matches: list[ArtifactMatch],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    grouped: dict[tuple[str, str], list[ArtifactMatch]] = defaultdict(list)
    for match in matches:
        grouped[(match.case_id, match.method)].append(match)

    details: list[dict[str, Any]] = []
    per_method_summary: dict[str, dict[str, Any]] = {}

    for method in requested_methods:
        per_method_summary[method] = {
            "method": method,
            "total_unique_failure_ids": len(failure_cases),
            "covered_cases": 0,
            "resolved_cases": 0,
            "still_fails_cases": 0,
            "unknown_cases": 0,
            "not_covered_cases": 0,
            "gold_absent_total": sum(1 for case in failure_cases.values() if case.is_gold_absent),
            "gold_absent_covered": 0,
            "gold_absent_resolved": 0,
            "gold_absent_still_fails": 0,
            "gold_absent_unknown": 0,
            "gold_absent_not_covered": 0,
            "matched_rows": 0,
            "matched_case_ids": 0,
            "candidate_rows": 0,
        }

    for case_id, case in failure_cases.items():
        for method in requested_methods:
            candidates = grouped.get((case_id, method), [])
            summary = per_method_summary[method]
            if not candidates:
                details.append(
                    {
                        "case_id": case_id,
                        "failure_method_ids": "|".join(case.method_ids),
                        "failure_family": case.failure_family,
                        "gold_absent": int(case.is_gold_absent),
                        "method": method,
                        "coverage_status": "not_covered",
                        "selected_source_path": "",
                        "selected_time_key": "",
                        "selected_correctness_status": "",
                        "selected_correctness_field": "",
                        "selected_prediction": "",
                        "selected_gold": case.gold_answer,
                        "selected_status": "",
                        "candidate_count": 0,
                        "candidate_sources": "",
                        "candidate_statuses": "",
                        "candidate_correctness_fields": "",
                        "selected_note": "No exact method/case match found in scanned artifacts.",
                    }
                )
                summary["not_covered_cases"] += 1
                if case.is_gold_absent:
                    summary["gold_absent_not_covered"] += 1
                continue

            summary["covered_cases"] += 1
            summary["matched_rows"] += len(candidates)
            summary["matched_case_ids"] += 1
            summary["candidate_rows"] += len(candidates)
            chosen = _choose_match(candidates)
            summary[chosen.correctness_status + "_cases"] += 1
            if case.is_gold_absent:
                summary[f"gold_absent_{chosen.correctness_status}"] += 1

            candidate_sources = "|".join(sorted({c.source_path for c in candidates}))
            candidate_statuses = "|".join(sorted({c.correctness_status for c in candidates}))
            candidate_fields = "|".join(sorted({c.correctness_field for c in candidates if c.correctness_field}))
            details.append(
                {
                    "case_id": case_id,
                    "failure_method_ids": "|".join(case.method_ids),
                    "failure_family": case.failure_family,
                    "gold_absent": int(case.is_gold_absent),
                    "method": method,
                    "coverage_status": chosen.correctness_status,
                    "selected_source_path": chosen.source_path,
                    "selected_time_key": chosen.time_key,
                    "selected_correctness_status": chosen.correctness_status,
                    "selected_correctness_field": chosen.correctness_field,
                    "selected_prediction": chosen.prediction,
                    "selected_gold": chosen.gold or case.gold_answer,
                    "selected_status": chosen.status_text,
                    "candidate_count": len(candidates),
                    "candidate_sources": candidate_sources,
                    "candidate_statuses": candidate_statuses,
                    "candidate_correctness_fields": candidate_fields,
                    "selected_note": "",
                }
            )

    for method, summary in per_method_summary.items():
        summary["resolved_cases"] = sum(1 for row in details if row["method"] == method and row["coverage_status"] == "resolved")
        summary["still_fails_cases"] = sum(1 for row in details if row["method"] == method and row["coverage_status"] == "still_fails")
        summary["unknown_cases"] = sum(1 for row in details if row["method"] == method and row["coverage_status"] == "unknown")
        summary["not_covered_cases"] = sum(1 for row in details if row["method"] == method and row["coverage_status"] == "not_covered")
        summary["gold_absent_covered"] = sum(
            1
            for row in details
            if row["method"] == method and row["gold_absent"] and row["coverage_status"] in {"resolved", "still_fails", "unknown"}
        )
        summary["gold_absent_resolved"] = sum(
            1 for row in details if row["method"] == method and row["gold_absent"] and row["coverage_status"] == "resolved"
        )
        summary["gold_absent_still_fails"] = sum(
            1 for row in details if row["method"] == method and row["gold_absent"] and row["coverage_status"] == "still_fails"
        )
        summary["gold_absent_unknown"] = sum(
            1 for row in details if row["method"] == method and row["gold_absent"] and row["coverage_status"] == "unknown"
        )

    return details, per_method_summary


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row.keys()}) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


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


def _render_report(summary: dict[str, Any]) -> str:
    method_rows = summary.get("coverage_by_method", [])
    lines = [
        "# Latest Failure Recovery Coverage Audit",
        "",
        f"- Generated at: `{summary['generated_at_utc']}`",
        f"- Failure corpus rows: `{summary['failure_corpus_rows']}`",
        f"- Unique fully tracked failure IDs: `{summary['unique_failure_ids']}`",
        f"- Gold-absent subset IDs: `{summary['gold_absent_ids']}`",
        f"- Outputs scanned: `{summary['outputs_scanned']}`",
        f"- Candidate rows matched: `{summary['candidate_rows_matched']}`",
        "",
        "## Coverage By Method",
        "",
        _render_table(
            method_rows,
            [
                "method",
                "covered_cases",
                "resolved_cases",
                "still_fails_cases",
                "unknown_cases",
                "not_covered_cases",
                "gold_absent_covered",
            ],
        ),
        "",
        "## Gold-Absent Subset",
        "",
        _render_table(
            method_rows,
            [
                "method",
                "gold_absent_total",
                "gold_absent_covered",
                "gold_absent_resolved",
                "gold_absent_still_fails",
                "gold_absent_unknown",
                "gold_absent_not_covered",
            ],
        ),
        "",
        "## Method Notes",
        "",
    ]
    for note in summary.get("method_notes", []):
        lines.append(f"- {note}")

    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            summary.get("recommended_next_step", ""),
            "",
            "## Limits",
            "",
            "- Missing coverage is reported as `not_covered`; it is not treated as a failure.",
            "- This is an existing-artifact audit only.",
            "- No runtime behavior change was made.",
            "- No paid/model API calls were made.",
            "- No external-baseline claim is made.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--failure-csv",
        default=str(DEFAULT_FAILURE_CSV),
        help="Fully tracked latest-method failure corpus CSV.",
    )
    parser.add_argument(
        "--gold-absent-csv",
        default=str(DEFAULT_GOLD_ABSENT_CSV),
        help="Optional gold-absent subset CSV.",
    )
    parser.add_argument(
        "--outputs-root",
        default=str(DEFAULT_OUTPUTS_ROOT),
        help="Root directory containing existing artifacts to scan.",
    )
    parser.add_argument(
        "--method",
        action="append",
        default=[],
        help="Exact method ID to audit. May be repeated.",
    )
    parser.add_argument(
        "--output-dir",
        default="",
        help="Optional output directory. Defaults to outputs/latest_failure_recovery_coverage_<timestamp>.",
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
        help="Validate inputs and print summary without writing output files.",
    )
    return parser.parse_args(argv)


def analyze(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    failure_csv = Path(args.failure_csv).expanduser()
    gold_absent_csv = Path(args.gold_absent_csv).expanduser() if args.gold_absent_csv else None
    outputs_root = Path(args.outputs_root).expanduser()

    if not failure_csv.is_file():
        raise FileNotFoundError(f"Missing failure corpus CSV: {failure_csv}")
    if gold_absent_csv is not None and not gold_absent_csv.is_file():
        raise FileNotFoundError(f"Missing gold-absent CSV: {gold_absent_csv}")
    if not outputs_root.exists():
        raise FileNotFoundError(f"Missing outputs root: {outputs_root}")

    requested_methods = list(dict.fromkeys(args.method or list(DEFAULT_METHODS)))
    gold_absent_ids = _load_gold_absent_ids(gold_absent_csv) if gold_absent_csv else set()
    failure_cases = _load_failure_cases(failure_csv, gold_absent_ids)
    matches, invalidated_methods = _scan_artifacts(outputs_root, set(requested_methods))
    details, per_method_summary = _summarize_matches(failure_cases, requested_methods, matches)

    coverage_rows = []
    for method in requested_methods:
        summary = per_method_summary[method]
        coverage_rows.append(
            {
                **summary,
                "covered_plus_not_covered": summary["covered_cases"] + summary["not_covered_cases"],
                "coverage_fraction": float(summary["covered_cases"] / max(1, summary["total_unique_failure_ids"])),
            }
        )

    unresolved_rows = [
        row for row in details if row["coverage_status"] in {"still_fails", "unknown"} and row["method"] in requested_methods
    ]
    resolved_rows = [row for row in details if row["coverage_status"] == "resolved"]
    not_covered_rows = [row for row in details if row["coverage_status"] == "not_covered"]

    total_unique_failure_ids = len(failure_cases)
    gold_absent_total = sum(1 for case in failure_cases.values() if case.is_gold_absent)

    total_unresolved_covered = sum(1 for row in unresolved_rows if row["coverage_status"] in {"still_fails", "unknown"})
    recommended_next_step = (
        "Unresolved covered cases are large enough for pattern mining."
        if total_unresolved_covered >= 30
        else "Current unresolved covered cases are too small for robust pattern mining; use the full corpus with coverage labels, or collect a larger current-method run first."
    )
    if total_unresolved_covered < 30:
        recommended_case_list = "full 174-case failure corpus with coverage status attached"
    else:
        recommended_case_list = "all unresolved covered cases"

    method_notes = []
    for method in requested_methods:
        summary = per_method_summary[method]
        if summary["covered_cases"] == 0:
            method_notes.append(f"{method}: no exact method/case matches found in scanned artifacts.")
        if method.endswith("uncertainty_retry_v1") and summary["covered_cases"] == 0:
            method_notes.append(f"{method}: no scored artifact coverage was found in existing outputs.")
        if method.endswith("diverse_anchor") and invalidated_methods.get(method, 0) > 0 and summary["covered_cases"] == 0:
            method_notes.append(
                f"{method}: only invalidated recovery artifacts were found, so they were excluded from coverage."
            )

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "failure_corpus_rows": len(_iter_failure_rows(failure_csv)),
        "unique_failure_ids": total_unique_failure_ids,
        "gold_absent_ids": gold_absent_total,
        "outputs_scanned": len(matches),
        "candidate_rows_matched": len(matches),
        "methods": requested_methods,
        "coverage_by_method": coverage_rows,
        "case_coverage_details": details,
        "resolved_cases": resolved_rows,
        "unresolved_cases": unresolved_rows,
        "not_covered_cases": not_covered_rows,
        "recommended_next_step": recommended_next_step,
        "recommended_case_list": recommended_case_list,
        "method_notes": method_notes,
    }

    output_dir = Path(args.output_dir) if args.output_dir else REPO_ROOT / "outputs" / f"latest_failure_recovery_coverage_{args.timestamp}"
    if not args.dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)
        _write_csv(output_dir / "coverage_by_method.csv", coverage_rows)
        _write_csv(output_dir / "case_coverage_details.csv", details)
        _write_csv(output_dir / "resolved_cases.csv", resolved_rows)
        _write_csv(output_dir / "unresolved_cases.csv", unresolved_rows)
        _write_csv(output_dir / "not_covered_cases.csv", not_covered_rows)
        (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (output_dir / "recovery_coverage_report.md").write_text(_render_report(summary), encoding="utf-8")
    else:
        print(json.dumps(summary, indent=2, sort_keys=True))

    return summary


def main() -> int:
    try:
        analyze()
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
