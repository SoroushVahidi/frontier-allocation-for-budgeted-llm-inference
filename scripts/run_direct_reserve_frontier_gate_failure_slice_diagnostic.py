#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_DIAGNOSTIC_DIR = (
    REPO_ROOT / "outputs" / "cohere_gsm8k_strict_f3_vs_external_l1_max_diagnostic_20260425T235500Z"
)
DEFAULT_SOURCE_DIR = (
    REPO_ROOT / "outputs" / "cohere_real_model_cost_normalized_validation_20260425T133000Z_COHERE_STAGE1_MIN"
)

STRICT_METHOD = "strict_f3"
EXTERNAL_METHOD = "external_l1_max"
GATE_METHOD = "direct_reserve_frontier_gate_v1"
SUPPORT_FIELDS = ("answer_group_support_counts", "support_margin", "top2_support_gap")
MATURITY_FIELDS = ("frontier_maturity", "action_count", "actions_used", "expansions")
REQUIRED_TRACE_FIELDS = (
    "candidate_branch_table.csv",
    "answer_group_table.csv",
    "per_case_trace_index.csv",
)

PER_CASE_FIELDS = [
    "example_id",
    "gold_answer",
    "external_l1_max_prediction",
    "external_l1_max_correct",
    "strict_f3_prediction",
    "strict_f3_correct",
    "direct_reserve_frontier_gate_prediction",
    "direct_reserve_frontier_gate_correct",
    "direct_reserve_answer",
    "frontier_candidate_answer",
    "reserve_used",
    "frontier_override_triggered",
    "override_margin",
    "override_reason",
    "direct_frontier_agree",
    "helpful_override",
    "harmful_override",
    "direct_solved_preserved",
    "direct_solved_harmed",
    "dataset",
    "seed",
    "budget",
    "diagnostic_mode",
    "missing_support_or_maturity_fields",
]


def _now_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _repo_path(text: str) -> Path:
    p = Path(text)
    return p if p.is_absolute() else REPO_ROOT / p


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return [dict(r) for r in csv.DictReader(f)]


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = fieldnames or (list(rows[0].keys()) if rows else [])
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if fields:
            w.writeheader()
            for row in rows:
                w.writerow({k: row.get(k, "") for k in fields})


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _display_path(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path)


def _bool_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value)
    except Exception:
        return 0


def _pick_prediction(row: dict[str, Any]) -> str:
    for key in ("final_answer_canonical", "selected_answer_canonical", "final_answer_raw", "selected_answer_raw"):
        value = str(row.get(key, "") or "").strip()
        if value:
            return value
    return ""


def _richness(row: dict[str, Any]) -> int:
    keys = ("gold_answer", "gold_answer_canonical", "final_answer_raw", "final_answer_canonical", "question")
    return sum(1 for key in keys if row.get(key))


def _case_key(row: dict[str, Any]) -> tuple[str, int, int, str]:
    return (
        str(row.get("example_id", "")),
        _bool_int(row.get("seed")),
        _bool_int(row.get("budget")),
        str(row.get("dataset", "")),
    )


def _required_missing(source_dir: Path, diagnostic_dir: Path) -> list[str]:
    required = [
        diagnostic_dir / "manifest.json",
        diagnostic_dir / "paired_summary.csv",
        source_dir / "per_example_records.jsonl",
    ]
    return [str(p.relative_to(REPO_ROOT) if p.is_relative_to(REPO_ROOT) else p) for p in required if not p.exists()]


def _load_matched_rows(source_dir: Path) -> list[dict[str, Any]]:
    records = _read_jsonl(source_dir / "per_example_records.jsonl")
    by_key: dict[tuple[str, int, int, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in records:
        if row.get("provider") != "cohere" or row.get("dataset") != "openai/gsm8k":
            continue
        if row.get("method") not in {STRICT_METHOD, EXTERNAL_METHOD, GATE_METHOD}:
            continue
        if _bool_int(row.get("scored")) != 1:
            continue
        if _bool_int(row.get("seed")) not in {11, 23} or _bool_int(row.get("budget")) not in {4, 6, 8}:
            continue
        key = _case_key(row)
        old = by_key[key].get(str(row["method"]))
        if old is None or _richness(row) > _richness(old):
            by_key[key][str(row["method"])] = row

    matched: list[dict[str, Any]] = []
    for key, methods in sorted(by_key.items(), key=lambda item: item[0]):
        if STRICT_METHOD not in methods or EXTERNAL_METHOD not in methods:
            continue
        strict = methods[STRICT_METHOD]
        external = methods[EXTERNAL_METHOD]
        matched.append(
            {
                "example_id": key[0],
                "seed": key[1],
                "budget": key[2],
                "dataset": key[3],
                "gold_answer": strict.get("gold_answer") or external.get("gold_answer") or "",
                "strict_row": strict,
                "external_row": external,
                "gate_row": methods.get(GATE_METHOD, {}),
            }
        )
    return matched


def _support_margin(strict_row: dict[str, Any], direct_answer: str, frontier_answer: str) -> tuple[float, int, bool]:
    counts = strict_row.get("answer_group_support_counts")
    if isinstance(counts, dict) and counts:
        frontier_support = _bool_int(counts.get(frontier_answer, 0))
        direct_support = _bool_int(counts.get(direct_answer, 0))
        maturity = sum(_bool_int(v) for v in counts.values())
        return float(frontier_support - direct_support), maturity, True
    for key in ("support_margin", "top2_support_gap"):
        if str(strict_row.get(key, "")).strip():
            try:
                return float(strict_row.get(key)), _maturity(strict_row), True
            except Exception:
                pass
    return 0.0, _maturity(strict_row), False


def _maturity(row: dict[str, Any]) -> int:
    for key in MATURITY_FIELDS:
        if str(row.get(key, "")).strip():
            return _bool_int(row.get(key))
    return 0


def _field_coverage(source_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    requirements = {
        "candidate_branch_table.csv": {"example_id", "seed", "budget", "method", "branch_id", "answer_group", "branch_score"},
        "answer_group_table.csv": {"example_id", "seed", "budget", "method", "answer_group", "support_count", "maturity"},
        "per_case_trace_index.csv": {"example_id", "seed", "budget", "method", "trace_path", "trace_available"},
    }
    for filename, required in requirements.items():
        path = source_dir / filename
        table = _read_csv(path)
        present = set(table[0]) if table else set()
        missing = sorted(required - present)
        rows.append(
            {
                "field_group": filename,
                "present": int(path.exists() and bool(table)),
                "row_count": len(table),
                "missing_count": len(missing),
                "missing_fields": ";".join(missing),
                "impact": "usable" if path.exists() and table and not missing else "fallback_or_limited",
            }
        )
    return rows


def _has_usable_candidate_pool(source_dir: Path) -> bool:
    coverage = _field_coverage(source_dir)
    return all(int(row["present"]) == 1 and int(row["missing_count"]) == 0 for row in coverage)


def _trace_lookup(source_dir: Path) -> tuple[dict[tuple[str, int, int, str], list[dict[str, str]]], dict[tuple[str, int, int, str], list[dict[str, str]]]]:
    branches_by_case: dict[tuple[str, int, int, str], list[dict[str, str]]] = defaultdict(list)
    groups_by_case: dict[tuple[str, int, int, str], list[dict[str, str]]] = defaultdict(list)
    for row in _read_csv(source_dir / "candidate_branch_table.csv"):
        key = (str(row.get("example_id", "")), _bool_int(row.get("seed")), _bool_int(row.get("budget")), str(row.get("method", "")))
        branches_by_case[key].append(row)
    for row in _read_csv(source_dir / "answer_group_table.csv"):
        key = (str(row.get("example_id", "")), _bool_int(row.get("seed")), _bool_int(row.get("budget")), str(row.get("method", "")))
        groups_by_case[key].append(row)
    return branches_by_case, groups_by_case


def build_diagnostic(source_dir: Path, diagnostic_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    matched = _load_matched_rows(source_dir)
    paired_summary = _read_csv(diagnostic_dir / "paired_summary.csv")
    expected = _bool_int(paired_summary[0].get("matched_examples")) if paired_summary else 0
    field_coverage = _field_coverage(source_dir)
    mode = "paired_candidate_pool_diagnostic" if _has_usable_candidate_pool(source_dir) else "diagnostic_limited_prediction_level"
    branches_by_case, groups_by_case = _trace_lookup(source_dir) if mode == "paired_candidate_pool_diagnostic" else ({}, {})

    rows: list[dict[str, Any]] = []
    audit: list[dict[str, Any]] = []
    for cell in matched:
        strict_row = cell["strict_row"]
        external_row = cell["external_row"]
        gate_row = cell.get("gate_row") or {}
        direct_answer = _pick_prediction(external_row)
        frontier_answer = _pick_prediction(strict_row)
        external_ok = _bool_int(external_row.get("exact_match"))
        strict_ok = _bool_int(strict_row.get("exact_match"))
        actual_gate_available = bool(gate_row)
        gate_meta = gate_row.get("result_metadata") if isinstance(gate_row.get("result_metadata"), dict) else {}
        strict_trace_key = (cell["example_id"], cell["seed"], cell["budget"], STRICT_METHOD)
        external_trace_key = (cell["example_id"], cell["seed"], cell["budget"], EXTERNAL_METHOD)
        trace_groups = groups_by_case.get(strict_trace_key, [])
        trace_branches = branches_by_case.get(strict_trace_key, [])
        frontier_group_row = next((g for g in trace_groups if str(g.get("answer_group")) == str(frontier_answer)), {})
        incumbent_group_row = next((g for g in trace_groups if str(g.get("answer_group")) == str(direct_answer)), {})
        missing_support = not any(str(strict_row.get(k, "")).strip() for k in SUPPORT_FIELDS) and not trace_groups
        missing_maturity = not any(str(strict_row.get(k, "")).strip() for k in MATURITY_FIELDS) and not trace_branches
        if trace_groups:
            frontier_support_trace = _bool_int(frontier_group_row.get("support_count"))
            incumbent_support_trace = _bool_int(incumbent_group_row.get("support_count"))
            margin, maturity, support_available = (
                float(frontier_support_trace - incumbent_support_trace),
                _bool_int(frontier_group_row.get("maturity")),
                True,
            )
        else:
            margin, maturity, support_available = _support_margin(strict_row, direct_answer, frontier_answer)

        if actual_gate_available:
            override = bool(gate_meta.get("frontier_override_triggered", False))
            reason = str(gate_meta.get("override_reason", "actual_gate_metadata_unavailable"))
            gate_prediction = _pick_prediction(gate_row) or str(gate_meta.get("final_answer") or "")
            gate_ok = _bool_int(gate_row.get("exact_match"))
            margin = float(gate_meta.get("override_margin", margin) or 0.0)
            maturity = _bool_int(gate_meta.get("frontier_candidate_maturity", maturity))
        else:
            override = False
            if not frontier_answer:
                reason = "frontier_prediction_unavailable"
            elif direct_answer and direct_answer == frontier_answer:
                reason = "direct_frontier_agree"
            elif missing_support or missing_maturity or not support_available:
                reason = "missing_support_or_maturity_metadata"
            elif maturity < 2:
                reason = "frontier_not_mature"
            elif margin < 1.0:
                reason = "insufficient_support_margin"
            else:
                override = True
                reason = "frontier_support_margin_and_maturity_passed"
            gate_prediction = frontier_answer if override else direct_answer
            gate_ok = strict_ok if override else external_ok
        helpful = int(override and not external_ok and gate_ok)
        harmful = int(override and external_ok and not gate_ok)
        preserved = int(external_ok and gate_ok)
        harmed = int(external_ok and not gate_ok)
        row = {
            "example_id": cell["example_id"],
            "gold_answer": cell["gold_answer"],
            "external_l1_max_prediction": direct_answer,
            "external_l1_max_correct": external_ok,
            "strict_f3_prediction": frontier_answer,
            "strict_f3_correct": strict_ok,
            "direct_reserve_frontier_gate_prediction": gate_prediction,
            "direct_reserve_frontier_gate_correct": gate_ok,
            "direct_reserve_answer": direct_answer,
            "frontier_candidate_answer": frontier_answer,
            "reserve_used": int(not override),
            "frontier_override_triggered": int(override),
            "override_margin": margin,
            "override_reason": reason,
            "direct_frontier_agree": int(bool(direct_answer) and direct_answer == frontier_answer),
            "helpful_override": helpful,
            "harmful_override": harmful,
            "direct_solved_preserved": preserved,
            "direct_solved_harmed": harmed,
            "dataset": cell["dataset"],
            "seed": cell["seed"],
            "budget": cell["budget"],
            "diagnostic_mode": mode,
            "missing_support_or_maturity_fields": int(missing_support or missing_maturity),
        }
        rows.append(row)
        audit.append(
            {
                "example_id": cell["example_id"],
                "seed": cell["seed"],
                "budget": cell["budget"],
                "direct_reserve_answer": direct_answer,
                "frontier_candidate_answer": frontier_answer,
                "frontier_override_triggered": int(override),
                "override_margin": margin,
                "frontier_maturity": maturity,
                "override_reason": reason,
                "external_l1_max_correct": external_ok,
                "strict_f3_correct": strict_ok,
                "direct_reserve_frontier_gate_correct": gate_ok,
            }
        )

    if expected and len(rows) != expected:
        raise RuntimeError(f"matched row count mismatch: built {len(rows)} rows, paired_summary expects {expected}")
    return rows, audit, {"diagnostic_mode": mode, "expected_matched_examples": expected, "field_coverage": field_coverage}


def summarize(rows: list[dict[str, Any]], mode: str) -> dict[str, Any]:
    n = len(rows)
    total_overrides = sum(_bool_int(r["frontier_override_triggered"]) for r in rows)
    reserve = sum(_bool_int(r["reserve_used"]) for r in rows)
    return {
        "matched_examples": n,
        "external_l1_max_accuracy": sum(_bool_int(r["external_l1_max_correct"]) for r in rows) / max(1, n),
        "strict_f3_accuracy": sum(_bool_int(r["strict_f3_correct"]) for r in rows) / max(1, n),
        "direct_reserve_frontier_gate_v1_accuracy": sum(_bool_int(r["direct_reserve_frontier_gate_correct"]) for r in rows) / max(1, n),
        "paired_delta_vs_external_l1_max": (
            sum(_bool_int(r["direct_reserve_frontier_gate_correct"]) - _bool_int(r["external_l1_max_correct"]) for r in rows)
            / max(1, n)
        ),
        "paired_delta_vs_strict_f3": (
            sum(_bool_int(r["direct_reserve_frontier_gate_correct"]) - _bool_int(r["strict_f3_correct"]) for r in rows)
            / max(1, n)
        ),
        "direct_solved_cases_preserved": sum(_bool_int(r["direct_solved_preserved"]) for r in rows),
        "direct_solved_cases_harmed": sum(_bool_int(r["direct_solved_harmed"]) for r in rows),
        "helpful_overrides": sum(_bool_int(r["helpful_override"]) for r in rows),
        "harmful_overrides": sum(_bool_int(r["harmful_override"]) for r in rows),
        "total_overrides": total_overrides,
        "reserve_use_rate": reserve / max(1, n),
        "override_rate": total_overrides / max(1, n),
        "missing_support_maturity_field_count": sum(_bool_int(r["missing_support_or_maturity_fields"]) for r in rows),
        "diagnostic_type": mode,
    }


def _missing_report(rows: list[dict[str, Any]], field_coverage: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    report = [
        {
            "field_group": "support_or_maturity",
            "missing_count": sum(_bool_int(r["missing_support_or_maturity_fields"]) for r in rows),
            "total_cases": len(rows),
            "impact": "conservative_no_override_default" if rows else "not_evaluable",
        },
        {
            "field_group": "predictions_or_gold",
            "missing_count": sum(
                int(not str(r["gold_answer"]).strip() or not str(r["external_l1_max_prediction"]).strip() or not str(r["strict_f3_prediction"]).strip())
                for r in rows
            ),
            "total_cases": len(rows),
            "impact": "correctness_loaded_from_cached_exact_match_fields",
        },
    ]
    report.extend(field_coverage or [])
    return report


def _write_readme(out_dir: Path, summary: dict[str, Any]) -> None:
    text = (
        "# Direct Reserve Frontier Gate Failure Slice Diagnostic\n\n"
        "This is a cached/offline diagnostic for the Cohere GSM8K Stage-1 slice where "
        "`strict_f3` lost to `external_l1_max`.\n\n"
        f"- Diagnostic type: `{summary['diagnostic_type']}`\n"
        f"- Matched examples: {summary['matched_examples']}\n"
        f"- `external_l1_max` accuracy: {summary['external_l1_max_accuracy']:.4f}\n"
        f"- `strict_f3` accuracy: {summary['strict_f3_accuracy']:.4f}\n"
        f"- `direct_reserve_frontier_gate_v1` accuracy: {summary['direct_reserve_frontier_gate_v1_accuracy']:.4f}\n"
        f"- Total overrides: {summary['total_overrides']}\n"
        f"- Helpful overrides: {summary['helpful_overrides']}\n"
        f"- Harmful overrides: {summary['harmful_overrides']}\n\n"
        "The cached failure slice does not include candidate-pool support/maturity fields, "
        "so the fallback copies the direct reserve (`external_l1_max`) with zero overrides and "
        "does not promote this variant to canonical evidence.\n"
    )
    (out_dir / "README.md").write_text(text, encoding="utf-8")


def _write_status_doc(out_dir: Path, summary: dict[str, Any]) -> None:
    mode = str(summary["diagnostic_type"])
    if _bool_int(summary["total_overrides"]) == 0:
        interpretation = (
            "zero overrides; the variant copies `external_l1_max` on this cached slice because "
            "needed support/maturity metadata are unavailable"
        )
    elif _bool_int(summary["harmful_overrides"]) > 0:
        interpretation = "harmful overrides occurred; keep diagnostic-only"
    elif float(summary["paired_delta_vs_external_l1_max"]) > 0:
        interpretation = "accuracy improved without harmful overrides; still diagnostic-only pending broader evidence"
    else:
        interpretation = "method copies or matches external_l1_max; do not overclaim"
    text = (
        "# DIRECT_RESERVE_FRONTIER_GATE_FAILURE_SLICE_STATUS\n\n"
        f"- Output directory: `{_display_path(out_dir)}`\n"
        f"- Diagnostic type: `{mode}`\n"
        f"- Matched examples: {summary['matched_examples']}\n"
        f"- `external_l1_max` accuracy: {summary['external_l1_max_accuracy']:.4f}\n"
        f"- `strict_f3` accuracy: {summary['strict_f3_accuracy']:.4f}\n"
        f"- `direct_reserve_frontier_gate_v1` accuracy: {summary['direct_reserve_frontier_gate_v1_accuracy']:.4f}\n"
        f"- Paired delta vs `external_l1_max`: {summary['paired_delta_vs_external_l1_max']:.4f}\n"
        f"- Paired delta vs `strict_f3`: {summary['paired_delta_vs_strict_f3']:.4f}\n"
        f"- Total overrides: {summary['total_overrides']}\n"
        f"- Helpful overrides: {summary['helpful_overrides']}\n"
        f"- Harmful overrides: {summary['harmful_overrides']}\n"
        f"- Missing support/maturity field count: {summary['missing_support_maturity_field_count']}\n\n"
        f"Interpretation: {interpretation}. This remains diagnostic-only and is not canonical evidence.\n"
    )
    (REPO_ROOT / "docs" / "DIRECT_RESERVE_FRONTIER_GATE_FAILURE_SLICE_STATUS.md").write_text(text, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Cached failure-slice diagnostic for direct_reserve_frontier_gate_v1.")
    p.add_argument("--timestamp", default=_now_ts())
    p.add_argument("--source-dir", default=str(DEFAULT_SOURCE_DIR.relative_to(REPO_ROOT)))
    p.add_argument("--diagnostic-dir", default=str(DEFAULT_DIAGNOSTIC_DIR.relative_to(REPO_ROOT)))
    p.add_argument("--output-root", default="outputs")
    p.add_argument("--allow-real-api", action="store_true", help="Reserved flag; default run is strictly cached/offline.")
    p.add_argument("--skip-status-doc", action="store_true", help=argparse.SUPPRESS)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    source_dir = _repo_path(args.source_dir)
    diagnostic_dir = _repo_path(args.diagnostic_dir)
    output_root = _repo_path(args.output_root)
    out_dir = output_root / f"direct_reserve_frontier_gate_failure_slice_{args.timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    missing = _required_missing(source_dir, diagnostic_dir)
    if missing:
        status = {
            "status": "missing_required_source_artifacts",
            "missing_files": missing,
            "source_dir": str(source_dir),
            "diagnostic_dir": str(diagnostic_dir),
            "real_api_allowed": bool(args.allow_real_api),
        }
        _write_json(out_dir / "manifest.json", status)
        _write_csv(out_dir / "missing_fields_report.csv", [{"missing_file": m, "impact": "required_source_artifact_missing"} for m in missing])
        (out_dir / "README.md").write_text(
            "# Direct Reserve Frontier Gate Failure Slice Diagnostic\n\n"
            "Status: missing required source artifacts.\n\n"
            + "\n".join(f"- `{m}`" for m in missing)
            + "\n",
            encoding="utf-8",
        )
        print(f"Missing required source artifacts; wrote status report to {out_dir}", file=sys.stderr)
        return 2

    rows, audit, meta = build_diagnostic(source_dir, diagnostic_dir)
    if not rows:
        raise SystemExit("No matched rows found in cached source artifacts; refusing to invent examples.")
    summary = summarize(rows, str(meta["diagnostic_mode"]))

    _write_csv(out_dir / "per_case_results.csv", rows, PER_CASE_FIELDS)
    _write_csv(out_dir / "summary.csv", [summary])
    _write_csv(out_dir / "override_audit.csv", audit)
    _write_csv(out_dir / "missing_fields_report.csv", _missing_report(rows, list(meta.get("field_coverage", []))))
    _write_readme(out_dir, summary)
    _write_json(
        out_dir / "manifest.json",
        {
            "artifact_family": "direct_reserve_frontier_gate_failure_slice",
            "timestamp": args.timestamp,
            "source_dir": _display_path(source_dir),
            "diagnostic_dir": _display_path(diagnostic_dir),
            "real_api_allowed": bool(args.allow_real_api),
            "real_api_used": False,
            "diagnostic_type": summary["diagnostic_type"],
            "matched_examples": summary["matched_examples"],
            "outputs": [
                "manifest.json",
                "per_case_results.csv",
                "summary.csv",
                "override_audit.csv",
                "missing_fields_report.csv",
                "README.md",
            ],
        },
    )
    if not args.skip_status_doc:
        _write_status_doc(out_dir, summary)
    print(f"Wrote {summary['diagnostic_type']} to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
