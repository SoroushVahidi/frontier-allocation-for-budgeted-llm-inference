"""Collect structured baseline-gated loss-case diagnostics from offline artifacts.

Inputs:
- group_decisions.csv emitted by compare_baseline_gated_hybrid_allocator.py
- scored candidates JSONL used for evaluation
- optional raw JSONL with richer status/trace fields

Outputs:
- loss_case_report.md
- loss_case_metrics.json
- case_diagnostics.csv
- missed_recoveries.csv
- regressions.csv
- switch_cases.csv
- oracle_recoverable_cases.csv
- manual_review_cases.csv

No provider/API calls. Offline diagnostics only.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import pathlib
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any


REQUIRED_LABELS = [
    "both_correct",
    "both_wrong",
    "baseline_correct_frontier_wrong",
    "baseline_wrong_frontier_correct",
    "gate_recovery",
    "gate_regression",
    "gate_missed_recovery",
    "gate_safe_switch",
    "gate_neutral_stay",
    "oracle_recoverable",
]

PLACEHOLDER_LABELS = [
    "candidate_pool_miss",
    "selector_miss",
    "verifier_or_gate_miss",
    "parsing_or_canonicalization_suspect",
    "unknown_needs_manual_review",
]


def _to_float(v: Any, default: float = 0.0) -> float:
    if v is None:
        return default
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if not s:
        return default
    try:
        return float(s)
    except ValueError:
        return default


def _to_int(v: Any, default: int = 0) -> int:
    if v is None:
        return default
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (int, float)):
        return int(v)
    s = str(v).strip().lower()
    if s in {"true", "t", "yes", "y"}:
        return 1
    if s in {"false", "f", "no", "n", ""}:
        return 0
    try:
        return int(float(s))
    except ValueError:
        return default


def _safe_str(v: Any) -> str:
    if v is None:
        return ""
    return str(v)


def _fmt(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, float):
        return f"{v:.6f}"
    return str(v)


def parse_feature_text(feature_text: str) -> dict[str, str]:
    out = {
        "question": "",
        "candidate_answer": "",
        "candidate_trace_short": "",
        "candidate_source": "",
    }
    if not feature_text:
        return out

    for part in feature_text.split(" | "):
        if ": " not in part:
            continue
        k, v = part.split(": ", 1)
        if k in out:
            out[k] = v
    return out


def load_group_decisions(path: pathlib.Path, split: str = "auto") -> list[dict[str, Any]]:
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        return []

    if split == "all":
        return rows

    if "split" not in rows[0]:
        return rows

    splits = {str(r.get("split", "")) for r in rows}
    if split == "auto":
        target = "validation" if "validation" in splits else None
    else:
        target = split

    if target is None:
        return rows

    filtered = [r for r in rows if str(r.get("split", "")) == target]
    return filtered if filtered else rows


def _extract_key_fields_from_row(row: dict[str, Any]) -> tuple[str, str, str, str]:
    meta = row.get("metadata", {}) or {}
    example_id = _safe_str(meta.get("example_id") or row.get("example_id"))
    budget = _safe_str(meta.get("budget") or row.get("budget"))
    method = _safe_str(meta.get("method") or row.get("method"))
    seed = _safe_str(meta.get("seed") or row.get("seed"))
    return example_id, budget, method, seed


def load_scored_index(
    path: pathlib.Path,
    *,
    score_field: str,
) -> tuple[dict[tuple[str, str, str, str], dict[str, Any]], dict[tuple[str, str], list[dict[str, Any]]]]:
    by_key: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    by_group: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)

    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            raw = json.loads(line)
            meta = raw.get("metadata", {}) or {}
            example_id = _safe_str(meta.get("example_id"))
            budget = _safe_str(meta.get("budget"))
            method = _safe_str(meta.get("method"))
            seed = _safe_str(meta.get("seed"))

            parsed = parse_feature_text(_safe_str(raw.get("feature_text", "")))

            obj = {
                "example_id": example_id,
                "budget": budget,
                "method": method,
                "seed": seed,
                "score": _to_float(raw.get(score_field), default=0.0),
                "row_index": raw.get("row_index"),
                "feature_text": _safe_str(raw.get("feature_text", "")),
                "question": parsed.get("question", ""),
                "candidate_answer": parsed.get("candidate_answer", ""),
                "candidate_trace_short": parsed.get("candidate_trace_short", ""),
                "metadata": meta,
                "raw": raw,
            }
            key = (example_id, budget, method, seed)
            by_key[key] = obj
            by_group[(example_id, budget)].append(obj)

    return by_key, by_group


def load_raw_index(path: pathlib.Path | None) -> dict[tuple[str, str, str, str], dict[str, Any]]:
    if path is None:
        return {}

    out: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            raw = json.loads(line)
            meta = raw.get("metadata", {}) or {}

            example_id = _safe_str(
                meta.get("example_id")
                or raw.get("example_id")
                or raw.get("id")
            )
            budget = _safe_str(meta.get("budget") or raw.get("budget"))
            method = _safe_str(meta.get("method") or raw.get("method"))
            seed = _safe_str(meta.get("seed") or raw.get("seed"))

            key = (example_id, budget, method, seed)
            out[key] = raw

    return out


def _extract_raw_status_fields(raw_row: dict[str, Any] | None) -> dict[str, Any]:
    if not raw_row:
        return {
            "raw_status": "",
            "raw_error": "",
            "raw_parse_status": "",
            "raw_error_type": "",
        }

    return {
        "raw_status": _safe_str(raw_row.get("status") or raw_row.get("result_status")),
        "raw_error": _safe_str(raw_row.get("error") or raw_row.get("error_message")),
        "raw_parse_status": _safe_str(raw_row.get("parse_status") or raw_row.get("parser_status")),
        "raw_error_type": _safe_str(raw_row.get("error_type") or raw_row.get("failure_type")),
    }


def _detect_parsing_suspect(raw_fields: dict[str, Any], baseline_answer: str, frontier_answer: str) -> bool:
    text = " ".join(
        _safe_str(raw_fields.get(k, "")) for k in ["raw_status", "raw_error", "raw_parse_status", "raw_error_type"]
    ).lower()
    parse_tokens = ["parse", "canonical", "normaliz", "format", "extract", "invalid"]
    if any(tok in text for tok in parse_tokens):
        return True

    # If both candidate answers are blank, parsing/canonicalization is suspect.
    if not baseline_answer and not frontier_answer:
        return True

    return False


def assign_required_labels(case: dict[str, Any]) -> list[str]:
    b = _to_int(case.get("baseline_correct"))
    f = _to_int(case.get("frontier_correct"))
    g = _to_int(case.get("gated_correct"))
    switched = _to_int(case.get("switch_flag"))

    labels: list[str] = []

    if b == 1 and f == 1:
        labels.append("both_correct")
    elif b == 0 and f == 0:
        labels.append("both_wrong")
    elif b == 1 and f == 0:
        labels.append("baseline_correct_frontier_wrong")
    elif b == 0 and f == 1:
        labels.append("baseline_wrong_frontier_correct")

    if b == 0 and switched == 1 and g == 1:
        labels.append("gate_recovery")
    if b == 1 and switched == 1 and g == 0:
        labels.append("gate_regression")
    if b == 0 and f == 1 and switched == 0:
        labels.append("gate_missed_recovery")
    if switched == 1 and g == 1:
        labels.append("gate_safe_switch")
    if switched == 0 and b == g:
        labels.append("gate_neutral_stay")
    if b == 0 and f == 1:
        labels.append("oracle_recoverable")

    return labels


def assign_placeholder_labels(case: dict[str, Any]) -> list[str]:
    b = _to_int(case.get("baseline_correct"))
    f = _to_int(case.get("frontier_correct"))
    switched = _to_int(case.get("switch_flag"))
    oracle = _to_int(case.get("oracle_correct"))
    parsing_suspect = bool(case.get("parsing_or_canonicalization_suspect"))

    labels: list[str] = []

    if b == 0 and f == 0 and oracle == 0:
        labels.append("candidate_pool_miss")

    if b == 0 and f == 1 and switched == 0:
        labels.append("selector_miss")
        labels.append("verifier_or_gate_miss")

    if parsing_suspect:
        labels.append("parsing_or_canonicalization_suspect")

    if not labels:
        # Keep review focus small: only escalate unknown when we see a loss without clear bucket.
        if _to_int(case.get("gated_correct")) == 0 and "both_wrong" not in case.get("required_labels", []):
            labels.append("unknown_needs_manual_review")

    return labels


def summarize_numeric(values: list[float]) -> dict[str, float | int | None]:
    vals = [v for v in values if not math.isnan(v)]
    if not vals:
        return {
            "count": 0,
            "min": None,
            "p25": None,
            "median": None,
            "mean": None,
            "p75": None,
            "max": None,
        }
    sv = sorted(vals)

    def pct(q: float) -> float:
        idx = (len(sv) - 1) * q
        lo = int(math.floor(idx))
        hi = int(math.ceil(idx))
        if lo == hi:
            return sv[lo]
        frac = idx - lo
        return sv[lo] * (1 - frac) + sv[hi] * frac

    return {
        "count": len(vals),
        "min": min(vals),
        "p25": pct(0.25),
        "median": statistics.median(vals),
        "mean": statistics.mean(vals),
        "p75": pct(0.75),
        "max": max(vals),
    }


def collect_cases(
    decision_rows: list[dict[str, Any]],
    *,
    scored_index: dict[tuple[str, str, str, str], dict[str, Any]],
    raw_index: dict[tuple[str, str, str, str], dict[str, Any]],
    scored_jsonl_path: pathlib.Path,
    baseline_method: str,
    frontier_method: str,
    score_field: str,
    group_id_field: str,
    budget_field: str,
    max_trace_chars: int,
) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []

    for row in decision_rows:
        example_id = _safe_str(row.get("group_id") or row.get(group_id_field))
        budget = _safe_str(row.get("budget") or row.get(budget_field))

        baseline_seed = _safe_str(row.get("external_top_seed") or row.get("baseline_top_seed"))
        frontier_seed = _safe_str(row.get("direct_top_seed") or row.get("frontier_top_seed"))

        baseline_score = _to_float(row.get("external_top_score") or row.get("baseline_top_score"), default=0.0)
        frontier_score = _to_float(row.get("direct_top_score") or row.get("frontier_top_score"), default=0.0)

        baseline_correct = _to_int(row.get("external_top_correct") or row.get("baseline_top_correct"), default=0)
        frontier_correct = _to_int(row.get("direct_top_correct") or row.get("frontier_top_correct"), default=0)
        gated_correct = _to_int(row.get("gated_correct"), default=0)
        switch_flag = _to_int(row.get("did_switch"), default=0)
        oracle_correct = _to_int(row.get("oracle_top2_correct"), default=0)

        chosen_action = _safe_str(row.get("selected_method"))
        if not chosen_action:
            chosen_action = frontier_method if switch_flag == 1 else baseline_method

        baseline_key = (example_id, budget, baseline_method, baseline_seed)
        frontier_key = (example_id, budget, frontier_method, frontier_seed)

        baseline_cand = scored_index.get(baseline_key)
        frontier_cand = scored_index.get(frontier_key)

        baseline_raw = raw_index.get(baseline_key)
        frontier_raw = raw_index.get(frontier_key)

        baseline_answer = _safe_str((baseline_cand or {}).get("candidate_answer", ""))
        frontier_answer = _safe_str((frontier_cand or {}).get("candidate_answer", ""))
        baseline_trace = _safe_str((baseline_cand or {}).get("candidate_trace_short", ""))[:max_trace_chars]
        frontier_trace = _safe_str((frontier_cand or {}).get("candidate_trace_short", ""))[:max_trace_chars]

        baseline_meta = (baseline_cand or {}).get("metadata", {}) or {}
        frontier_meta = (frontier_cand or {}).get("metadata", {}) or {}

        baseline_raw_fields = _extract_raw_status_fields(baseline_raw)
        frontier_raw_fields = _extract_raw_status_fields(frontier_raw)

        parsing_suspect = _detect_parsing_suspect(
            {
                "raw_status": baseline_raw_fields.get("raw_status", "") + " " + frontier_raw_fields.get("raw_status", ""),
                "raw_error": baseline_raw_fields.get("raw_error", "") + " " + frontier_raw_fields.get("raw_error", ""),
                "raw_parse_status": baseline_raw_fields.get("raw_parse_status", "") + " " + frontier_raw_fields.get("raw_parse_status", ""),
                "raw_error_type": baseline_raw_fields.get("raw_error_type", "") + " " + frontier_raw_fields.get("raw_error_type", ""),
            },
            baseline_answer,
            frontier_answer,
        )

        case = {
            "example_id": example_id,
            "budget": budget,
            "chosen_action": chosen_action,
            "switch_flag": switch_flag,
            "baseline_correct": baseline_correct,
            "frontier_correct": frontier_correct,
            "gated_correct": gated_correct,
            "baseline_score": baseline_score,
            "frontier_score": frontier_score,
            "score_margin": frontier_score - baseline_score,
            "baseline_seed": baseline_seed,
            "frontier_seed": frontier_seed,
            "baseline_answer": baseline_answer,
            "frontier_answer": frontier_answer,
            "baseline_trace_snippet": baseline_trace,
            "frontier_trace_snippet": frontier_trace,
            "exact_match_baseline_metadata": baseline_meta.get("exact_match_metadata"),
            "exact_match_frontier_metadata": frontier_meta.get("exact_match_metadata"),
            "gold_baseline_metadata": baseline_meta.get("gold_answer_metadata"),
            "gold_frontier_metadata": frontier_meta.get("gold_answer_metadata"),
            "baseline_row_index": (baseline_cand or {}).get("row_index"),
            "frontier_row_index": (frontier_cand or {}).get("row_index"),
            "baseline_source_pointer": f"{scored_jsonl_path}#row_index={(baseline_cand or {}).get('row_index')}",
            "frontier_source_pointer": f"{scored_jsonl_path}#row_index={(frontier_cand or {}).get('row_index')}",
            "baseline_raw_status": baseline_raw_fields.get("raw_status", ""),
            "baseline_raw_error": baseline_raw_fields.get("raw_error", ""),
            "frontier_raw_status": frontier_raw_fields.get("raw_status", ""),
            "frontier_raw_error": frontier_raw_fields.get("raw_error", ""),
            "raw_status_or_error_present": int(
                bool(baseline_raw_fields.get("raw_status") or baseline_raw_fields.get("raw_error")
                     or frontier_raw_fields.get("raw_status") or frontier_raw_fields.get("raw_error"))
            ),
            "oracle_correct": oracle_correct,
            "parsing_or_canonicalization_suspect": int(parsing_suspect),
        }

        req_labels = assign_required_labels(case)
        case["required_labels"] = req_labels
        placeholder_labels = assign_placeholder_labels(case)
        case["placeholder_labels"] = placeholder_labels

        all_labels = req_labels + placeholder_labels
        case["taxonomy_labels"] = "|".join(all_labels)

        # Primary label for simple grouping/reporting.
        if "gate_missed_recovery" in req_labels:
            primary = "gate_missed_recovery"
        elif "gate_regression" in req_labels:
            primary = "gate_regression"
        elif "gate_recovery" in req_labels:
            primary = "gate_recovery"
        elif "baseline_wrong_frontier_correct" in req_labels:
            primary = "baseline_wrong_frontier_correct"
        elif "baseline_correct_frontier_wrong" in req_labels:
            primary = "baseline_correct_frontier_wrong"
        elif "both_wrong" in req_labels:
            primary = "both_wrong"
        elif "both_correct" in req_labels:
            primary = "both_correct"
        else:
            primary = "unknown_needs_manual_review"

        case["taxonomy_label"] = primary
        case["manual_review_needed"] = int(
            "unknown_needs_manual_review" in placeholder_labels
            or "parsing_or_canonicalization_suspect" in placeholder_labels
        )

        cases.append(case)

    return cases


def compute_metrics(cases: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(cases)
    if n == 0:
        return {
            "n_groups": 0,
            "baseline_accuracy": None,
            "frontier_accuracy": None,
            "gated_accuracy": None,
            "recoveries": 0,
            "regressions": 0,
            "net_gain": 0,
            "direct_opportunities": 0,
            "captured_opportunities": 0,
            "missed_opportunities": 0,
            "taxonomy_counts": {},
            "placeholder_counts": {},
            "margin_summaries": {},
            "full_log_availability": {},
            "implications": [],
        }

    baseline_accuracy = sum(_to_int(c["baseline_correct"]) for c in cases) / n
    frontier_accuracy = sum(_to_int(c["frontier_correct"]) for c in cases) / n
    gated_accuracy = sum(_to_int(c["gated_correct"]) for c in cases) / n

    recoveries = sum(1 for c in cases if "gate_recovery" in c["required_labels"])
    regressions = sum(1 for c in cases if "gate_regression" in c["required_labels"])

    direct_opps = sum(1 for c in cases if "oracle_recoverable" in c["required_labels"])
    captured = sum(1 for c in cases if "gate_recovery" in c["required_labels"])
    missed = sum(1 for c in cases if "gate_missed_recovery" in c["required_labels"])

    taxonomy_counter = Counter()
    placeholder_counter = Counter()
    for c in cases:
        taxonomy_counter.update(c["required_labels"])
        placeholder_counter.update(c["placeholder_labels"])

    def _margins_for(label: str) -> list[float]:
        return [_to_float(c["score_margin"], default=math.nan) for c in cases if label in c["required_labels"]]

    margin_summaries = {
        "missed_recoveries": summarize_numeric(_margins_for("gate_missed_recovery")),
        "regressions": summarize_numeric(_margins_for("gate_regression")),
        "both_correct": summarize_numeric(_margins_for("both_correct")),
        "both_wrong": summarize_numeric(_margins_for("both_wrong")),
    }

    with_answer = sum(1 for c in cases if c.get("baseline_answer") or c.get("frontier_answer"))
    with_trace = sum(1 for c in cases if c.get("baseline_trace_snippet") or c.get("frontier_trace_snippet"))
    with_raw_status = sum(1 for c in cases if _to_int(c.get("raw_status_or_error_present")) == 1)

    implications = []
    if placeholder_counter.get("candidate_pool_miss", 0) > 0:
        implications.append("candidate_pool_miss_present")
    if missed > 0:
        implications.append("selector_or_gate_miss_present")
    if missed > regressions:
        implications.append("verifier_calibration_or_gate_threshold_issue_likely")
    if placeholder_counter.get("parsing_or_canonicalization_suspect", 0) > 0:
        implications.append("parsing_or_canonicalization_issue_possible")
    if frontier_accuracy < baseline_accuracy:
        implications.append("frontier_weakness_signal")

    return {
        "n_groups": n,
        "baseline_accuracy": baseline_accuracy,
        "frontier_accuracy": frontier_accuracy,
        "gated_accuracy": gated_accuracy,
        "recoveries": recoveries,
        "regressions": regressions,
        "net_gain": recoveries - regressions,
        "direct_opportunities": direct_opps,
        "captured_opportunities": captured,
        "missed_opportunities": missed,
        "taxonomy_counts": dict(sorted(taxonomy_counter.items())),
        "placeholder_counts": dict(sorted(placeholder_counter.items())),
        "margin_summaries": margin_summaries,
        "full_log_availability": {
            "with_answer_text": with_answer,
            "with_trace_snippet": with_trace,
            "with_raw_status_or_error": with_raw_status,
        },
        "implications": implications,
    }


def write_csv(path: pathlib.Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow({k: _fmt(row.get(k)) for k in fieldnames})


def write_report(path: pathlib.Path, metrics: dict[str, Any], split_used: str, baseline_method: str, frontier_method: str) -> None:
    def _pct(v: Any) -> str:
        if v is None:
            return "N/A"
        return f"{float(v):.4f} ({float(v)*100:.2f}%)"

    lines = [
        "# Baseline-Gated Loss Case Report",
        "",
        f"- Generated: {datetime.now(timezone.utc).isoformat()}",
        f"- Split analyzed: `{split_used}`",
        f"- Baseline method: `{baseline_method}`",
        f"- Frontier method: `{frontier_method}`",
        "",
        "## Overall",
        "",
        f"- n_groups: {metrics['n_groups']}",
        f"- baseline_accuracy: {_pct(metrics['baseline_accuracy'])}",
        f"- frontier_accuracy: {_pct(metrics['frontier_accuracy'])}",
        f"- gated_accuracy: {_pct(metrics['gated_accuracy'])}",
        f"- gate recoveries/regressions/net: {metrics['recoveries']}/{metrics['regressions']}/{metrics['net_gain']}",
        f"- direct/frontier opportunities: {metrics['direct_opportunities']}",
        f"- captured opportunities: {metrics['captured_opportunities']}",
        f"- missed opportunities: {metrics['missed_opportunities']}",
        "",
        "## Taxonomy Counts",
        "",
    ]

    for label in REQUIRED_LABELS:
        lines.append(f"- {label}: {metrics['taxonomy_counts'].get(label, 0)}")

    lines += ["", "## Placeholder/Derived Flags", ""]
    for label in PLACEHOLDER_LABELS:
        lines.append(f"- {label}: {metrics['placeholder_counts'].get(label, 0)}")

    lines += ["", "## Score-Margin Summaries", ""]
    for cohort in ["missed_recoveries", "regressions", "both_correct", "both_wrong"]:
        s = metrics["margin_summaries"].get(cohort, {})
        lines.append(
            f"- {cohort}: n={s.get('count',0)}, min={s.get('min')}, p25={s.get('p25')}, "
            f"median={s.get('median')}, mean={s.get('mean')}, p75={s.get('p75')}, max={s.get('max')}"
        )

    fla = metrics["full_log_availability"]
    lines += [
        "",
        "## Full-Log Availability",
        "",
        f"- cases with answer text: {fla.get('with_answer_text',0)}",
        f"- cases with trace snippets: {fla.get('with_trace_snippet',0)}",
        f"- cases with raw status/errors: {fla.get('with_raw_status_or_error',0)}",
        "",
        "## Diagnostic Implications",
        "",
    ]
    if metrics["implications"]:
        for x in metrics["implications"]:
            lines.append(f"- {x}")
    else:
        lines.append("- no clear automatic implication beyond baseline taxonomy")

    lines += [
        "",
        "## Conservative Warning",
        "",
        "- This is offline diagnostic analysis only.",
        "- Do not claim policy improvement from post-hoc loss analysis without independent validation.",
    ]

    path.write_text("\n".join(lines) + "\n")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)

    p.add_argument("--group-decisions-csv", required=True)
    p.add_argument("--scored-jsonl", required=True)
    p.add_argument("--raw-jsonl")
    p.add_argument("--output-dir", required=True)

    p.add_argument("--baseline-method", default="external_l1_max")
    p.add_argument("--frontier-method", default="direct_reserve_semantic_frontier_v2")

    p.add_argument("--score-field", default="proba_ready")
    p.add_argument("--group-id-field", default="example_id")
    p.add_argument("--budget-field", default="budget")
    p.add_argument("--max-trace-chars", type=int, default=800)

    p.add_argument("--split", default="auto", help="auto|all|<explicit split value>")

    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    group_decisions_path = pathlib.Path(args.group_decisions_csv)
    scored_path = pathlib.Path(args.scored_jsonl)
    raw_path = pathlib.Path(args.raw_jsonl) if args.raw_jsonl else None

    if not group_decisions_path.exists():
        print(f"ERROR: group-decisions CSV not found: {group_decisions_path}", file=sys.stderr)
        return 1
    if not scored_path.exists():
        print(f"ERROR: scored JSONL not found: {scored_path}", file=sys.stderr)
        return 1
    if raw_path is not None and not raw_path.exists():
        print(f"ERROR: raw JSONL not found: {raw_path}", file=sys.stderr)
        return 1

    out_dir = pathlib.Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    decision_rows = load_group_decisions(group_decisions_path, split=args.split)
    scored_index, _scored_by_group = load_scored_index(scored_path, score_field=args.score_field)
    raw_index = load_raw_index(raw_path)

    cases = collect_cases(
        decision_rows,
        scored_index=scored_index,
        raw_index=raw_index,
        scored_jsonl_path=scored_path,
        baseline_method=args.baseline_method,
        frontier_method=args.frontier_method,
        score_field=args.score_field,
        group_id_field=args.group_id_field,
        budget_field=args.budget_field,
        max_trace_chars=args.max_trace_chars,
    )

    metrics = compute_metrics(cases)

    # Subsets
    missed_recoveries = [c for c in cases if "gate_missed_recovery" in c["required_labels"]]
    regressions = [c for c in cases if "gate_regression" in c["required_labels"]]
    switch_cases = [c for c in cases if _to_int(c.get("switch_flag")) == 1]
    oracle_recoverable_cases = [c for c in cases if "oracle_recoverable" in c["required_labels"]]
    manual_review_cases = [
        c
        for c in cases
        if c.get("manual_review_needed") == 1
    ]

    fieldnames = [
        "example_id",
        "budget",
        "taxonomy_label",
        "taxonomy_labels",
        "chosen_action",
        "switch_flag",
        "baseline_correct",
        "frontier_correct",
        "gated_correct",
        "baseline_score",
        "frontier_score",
        "score_margin",
        "baseline_seed",
        "frontier_seed",
        "baseline_answer",
        "frontier_answer",
        "baseline_trace_snippet",
        "frontier_trace_snippet",
        "exact_match_baseline_metadata",
        "exact_match_frontier_metadata",
        "gold_baseline_metadata",
        "gold_frontier_metadata",
        "baseline_row_index",
        "frontier_row_index",
        "baseline_source_pointer",
        "frontier_source_pointer",
        "baseline_raw_status",
        "baseline_raw_error",
        "frontier_raw_status",
        "frontier_raw_error",
        "raw_status_or_error_present",
        "oracle_correct",
        "manual_review_needed",
    ]

    write_csv(out_dir / "case_diagnostics.csv", cases, fieldnames)
    write_csv(out_dir / "missed_recoveries.csv", missed_recoveries, fieldnames)
    write_csv(out_dir / "regressions.csv", regressions, fieldnames)
    write_csv(out_dir / "switch_cases.csv", switch_cases, fieldnames)
    write_csv(out_dir / "oracle_recoverable_cases.csv", oracle_recoverable_cases, fieldnames)
    write_csv(out_dir / "manual_review_cases.csv", manual_review_cases, fieldnames)

    metrics_obj = {
        "stamp": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "group_decisions_csv": str(group_decisions_path),
            "scored_jsonl": str(scored_path),
            "raw_jsonl": str(raw_path) if raw_path else None,
            "split": args.split,
        },
        "baseline_method": args.baseline_method,
        "frontier_method": args.frontier_method,
        "metrics": metrics,
        "n_cases": len(cases),
        "n_missed_recoveries": len(missed_recoveries),
        "n_regressions": len(regressions),
        "n_switch_cases": len(switch_cases),
        "n_oracle_recoverable_cases": len(oracle_recoverable_cases),
        "n_manual_review_cases": len(manual_review_cases),
    }

    with open(out_dir / "loss_case_metrics.json", "w") as f:
        json.dump(metrics_obj, f, indent=2)

    write_report(
        out_dir / "loss_case_report.md",
        metrics,
        split_used=args.split,
        baseline_method=args.baseline_method,
        frontier_method=args.frontier_method,
    )

    print(f"Wrote diagnostics to: {out_dir}")
    for name in [
        "loss_case_report.md",
        "loss_case_metrics.json",
        "case_diagnostics.csv",
        "missed_recoveries.csv",
        "regressions.csv",
        "switch_cases.csv",
        "oracle_recoverable_cases.csv",
        "manual_review_cases.csv",
    ]:
        print(f"  {out_dir / name}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
