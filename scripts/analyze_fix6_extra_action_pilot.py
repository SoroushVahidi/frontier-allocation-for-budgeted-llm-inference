#!/usr/bin/env python3
"""Analyze FIX-6 extra-action pilot outputs into LoVEC training/evaluation artifacts.

Safety contract:
- Offline-only analysis over existing artifacts.
- No provider/API calls.
- Graceful readiness-mode output when pilot rows are missing/incomplete.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EXPECTED_METHODS = {
    "direct_reserve_semantic_frontier_v2",
    "external_tale_prompt_budgeting",
}
EXPECTED_ROWS = 80
EXPECTED_EXAMPLES = 40
EXPECTED_SEED = 53
EXPECTED_BUDGET = 6


@dataclass
class ValidationSummary:
    row_count: int
    complete: bool
    reasons: list[str]
    status_counts: dict[str, int]
    method_counts: dict[str, int]
    unique_examples: int
    duplicate_count: int
    promotion_review_record_coverage: dict[str, int]
    promotion_review_validation_coverage: dict[str, int]
    enough_for_promotion_review_counts: dict[str, int]
    seed_mismatch_count: int
    budget_mismatch_count: int
    method_mismatch_count: int
    leakage_hits: list[dict[str, Any]]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        s = value.strip().lower()
        if s in {"1", "true", "yes", "y"}:
            return True
        if s in {"0", "false", "no", "n", ""}:
            return False
    return None


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open() as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _load_csv(path: Path) -> list[dict[str, Any]]:
    with path.open() as f:
        return list(csv.DictReader(f))


def _write_json(path: Path, obj: Any) -> None:
    with path.open("w") as f:
        json.dump(obj, f, indent=2)


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    if fieldnames is None:
        keys: set[str] = set()
        for row in rows:
            keys.update(str(k) for k in row.keys())
        fieldnames = sorted(keys)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _to_int(value: Any, default: int | None = None) -> int | None:
    try:
        if value is None or value == "":
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _row_key(row: dict[str, Any]) -> tuple[str, str, str, str, str]:
    return (
        str(row.get("example_id") or ""),
        str(row.get("dataset") or ""),
        str(row.get("method") or ""),
        str(row.get("seed") or ""),
        str(row.get("budget") or ""),
    )


def _example_key(row: dict[str, Any]) -> tuple[str, str]:
    return (str(row.get("example_id") or ""), str(row.get("dataset") or ""))


def _extract_answer(row: dict[str, Any]) -> str | None:
    for key in ("final_answer_canonical", "selected_answer_canonical", "final_answer_raw", "selected_answer_raw"):
        v = row.get(key)
        if v is not None and str(v).strip() != "":
            return str(v).strip()
    return None


def _extract_correct(row: dict[str, Any]) -> bool | None:
    em = _norm_bool(row.get("exact_match"))
    if em is not None:
        return em
    ans = _extract_answer(row)
    gold = row.get("gold_answer_canonical") or row.get("gold_answer")
    if ans is None or gold is None:
        return None
    return str(ans).strip() == str(gold).strip()


def _deep_items(obj: Any, prefix: str = ""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            k_str = str(k)
            path = f"{prefix}.{k_str}" if prefix else k_str
            yield from _deep_items(v, path)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            path = f"{prefix}[{i}]"
            yield from _deep_items(v, path)
    else:
        yield prefix, obj


def _scan_leakage(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    needle_terms = ("gold", "exact")
    for idx, row in enumerate(rows):
        for path, value in _deep_items(row):
            p = path.lower()
            if "prompt" not in p and "feature" not in p:
                continue
            if not isinstance(value, str):
                continue
            lowered = value.lower()
            if any(term in lowered for term in needle_terms):
                hits.append(
                    {
                        "row_index": idx,
                        "example_id": row.get("example_id"),
                        "dataset": row.get("dataset"),
                        "method": row.get("method"),
                        "path": path,
                        "value_excerpt": value[:200],
                    }
                )
    return hits


def _coverage_counter(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    counts = Counter()
    for row in rows:
        value = row.get(field)
        if value is None:
            rm = row.get("result_metadata")
            if isinstance(rm, dict):
                value = rm.get(field)
        if value is None:
            counts["missing"] += 1
        elif isinstance(value, dict) and value:
            counts["present"] += 1
        elif isinstance(value, dict):
            counts["empty"] += 1
        elif str(value).strip() == "":
            counts["empty"] += 1
        else:
            counts["present"] += 1
    return dict(counts)


def validate_pilot_rows(
    rows: list[dict[str, Any]],
    *,
    expected_rows: int = EXPECTED_ROWS,
    expected_examples: int = EXPECTED_EXAMPLES,
) -> ValidationSummary:
    reasons: list[str] = []
    status_counts = Counter(str(r.get("status") or "unknown") for r in rows)
    method_counts = Counter(str(r.get("method") or "unknown") for r in rows)
    unique_examples = len({_example_key(r) for r in rows})

    seen = set()
    duplicate_count = 0
    for row in rows:
        k = _row_key(row)
        if k in seen:
            duplicate_count += 1
        seen.add(k)

    seed_mismatch_count = sum(1 for r in rows if _to_int(r.get("seed")) != EXPECTED_SEED)
    budget_mismatch_count = sum(1 for r in rows if _to_int(r.get("budget")) != EXPECTED_BUDGET)
    method_mismatch_count = sum(1 for r in rows if str(r.get("method") or "") not in EXPECTED_METHODS)

    if len(rows) != expected_rows:
        reasons.append(f"row_count_mismatch: expected={expected_rows}, found={len(rows)}")
    if unique_examples != expected_examples:
        reasons.append(f"example_count_mismatch: expected={expected_examples}, found={unique_examples}")
    if set(method_counts.keys()) - EXPECTED_METHODS:
        reasons.append("unexpected_methods_present")
    if seed_mismatch_count:
        reasons.append(f"seed_mismatch_count={seed_mismatch_count}")
    if budget_mismatch_count:
        reasons.append(f"budget_mismatch_count={budget_mismatch_count}")
    if duplicate_count:
        reasons.append(f"duplicate_rows={duplicate_count}")

    pr_record_cov = _coverage_counter(rows, "promotion_review_record")
    pr_validation_cov = _coverage_counter(rows, "promotion_review_validation")

    enough_counts = Counter()
    for row in rows:
        value = row.get("enough_for_promotion_review")
        if value is None:
            rm = row.get("result_metadata")
            if isinstance(rm, dict):
                value = rm.get("enough_for_promotion_review")
        if value is None:
            enough_counts["missing"] += 1
            continue
        s = str(value).strip().lower()
        if s in {"yes", "true", "1"}:
            enough_counts["yes"] += 1
        elif s in {"partial", "partially"}:
            enough_counts["partial"] += 1
        elif s in {"no", "false", "0"}:
            enough_counts["no"] += 1
        else:
            enough_counts[s or "unknown"] += 1

    leakage_hits = _scan_leakage(rows)
    if leakage_hits:
        reasons.append(f"leakage_hits={len(leakage_hits)}")

    complete = len(reasons) == 0
    return ValidationSummary(
        row_count=len(rows),
        complete=complete,
        reasons=reasons,
        status_counts=dict(status_counts),
        method_counts=dict(method_counts),
        unique_examples=unique_examples,
        duplicate_count=duplicate_count,
        promotion_review_record_coverage=pr_record_cov,
        promotion_review_validation_coverage=pr_validation_cov,
        enough_for_promotion_review_counts=dict(enough_counts),
        seed_mismatch_count=seed_mismatch_count,
        budget_mismatch_count=budget_mismatch_count,
        method_mismatch_count=method_mismatch_count,
        leakage_hits=leakage_hits,
    )


def _load_pre_action_tables(fix6_root: Path) -> dict[str, list[dict[str, Any]]]:
    return {
        "state": _load_csv(fix6_root / "fix6_state_feature_table.csv"),
        "residual": _load_csv(fix6_root / "fix6_residual_failure_cases.csv"),
        "availability": _load_csv(fix6_root / "fix6_action_availability.csv"),
        "oracle": _load_csv(fix6_root / "fix6_oracle_action_table.csv"),
    }


def _index_rows(rows: list[dict[str, Any]], *, include_seed_budget: bool = False) -> dict[tuple[Any, ...], dict[str, Any]]:
    out: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        key: tuple[Any, ...]
        if include_seed_budget:
            key = (
                str(row.get("example_id") or ""),
                str(row.get("dataset") or ""),
                str(row.get("seed") or ""),
                str(row.get("budget") or ""),
            )
        else:
            key = (str(row.get("example_id") or ""), str(row.get("dataset") or ""))
        if key not in out:
            out[key] = row
    return out


def _find_candidate_row(
    index_seed_budget: dict[tuple[Any, ...], dict[str, Any]],
    index_example: dict[tuple[Any, ...], dict[str, Any]],
    example_id: str,
    dataset: str,
    seed_parent: Any,
    budget_parent: Any,
) -> dict[str, Any] | None:
    seed = "" if seed_parent is None else str(seed_parent)
    budget = "" if budget_parent is None else str(budget_parent)
    key_sb = (str(example_id), str(dataset), seed, budget)
    if key_sb in index_seed_budget:
        return index_seed_budget[key_sb]
    key_ex = (str(example_id), str(dataset))
    return index_example.get(key_ex)


def _choose_recommendation(summary_rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not summary_rows:
        return {
            "recommended_action": "run_larger_pilot",
            "reason": "no_action_rows_available",
        }
    by_action = {r["action_type"]: r for r in summary_rows}
    frontier_gain = by_action.get("extra_frontier", {}).get("mean_delta_vs_fix24", 0.0)
    tale_gain = by_action.get("extra_tale_retry", {}).get("mean_delta_vs_fix24", 0.0)

    if frontier_gain <= 0 and tale_gain <= 0:
        rec = "abandon_extra_actions"
    elif frontier_gain > 0 and tale_gain > 0:
        rec = "implement_lovec_policy_now"
    elif frontier_gain > 0:
        rec = "use_only_frontier_extra"
    elif tale_gain > 0:
        rec = "use_only_tale_retry"
    else:
        rec = "run_larger_pilot"

    return {
        "recommended_action": rec,
        "mean_delta_vs_fix24": {
            "extra_frontier": frontier_gain,
            "extra_tale_retry": tale_gain,
        },
        "considerations": [
            "offline_only_diagnostic",
            "requires_disjoint_followup_for_promotion_claims",
        ],
    }


def analyze_complete_pilot(
    *,
    selected_cases: list[dict[str, Any]],
    extra_action_plan: list[dict[str, Any]],
    pilot_rows: list[dict[str, Any]],
    fix6_tables: dict[str, list[dict[str, Any]]],
    expected_rows: int,
) -> dict[str, Any]:
    selected_idx = _index_rows(selected_cases)

    state_rows = fix6_tables["state"]
    residual_rows = fix6_tables["residual"]
    availability_rows = fix6_tables["availability"]

    state_idx_sb = _index_rows(state_rows, include_seed_budget=True)
    state_idx = _index_rows(state_rows)
    residual_idx_sb = _index_rows(residual_rows, include_seed_budget=True)
    residual_idx = _index_rows(residual_rows)
    availability_idx_sb = _index_rows(availability_rows, include_seed_budget=True)
    availability_idx = _index_rows(availability_rows)

    grouped: dict[tuple[str, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in pilot_rows:
        grouped[_example_key(row)][str(row.get("method") or "")] = row

    outcomes: list[dict[str, Any]] = []
    training_rows: list[dict[str, Any]] = []

    for (example_id, dataset), mm in sorted(grouped.items()):
        if not EXPECTED_METHODS.issubset(mm.keys()):
            continue

        sel = selected_idx.get((example_id, dataset), {})
        offline_labels = sel.get("offline_labels") if isinstance(sel.get("offline_labels"), dict) else {}
        seed_parent = sel.get("seed_parent")
        budget_parent = sel.get("budget_parent")

        state = _find_candidate_row(state_idx_sb, state_idx, example_id, dataset, seed_parent, budget_parent) or {}
        residual = _find_candidate_row(residual_idx_sb, residual_idx, example_id, dataset, seed_parent, budget_parent) or {}
        avail = _find_candidate_row(availability_idx_sb, availability_idx, example_id, dataset, seed_parent, budget_parent) or {}

        fix24_correct = _norm_bool(offline_labels.get("fix24_correct"))
        tale_correct = _norm_bool(offline_labels.get("tale_correct"))
        if fix24_correct is None:
            fix24_correct = _norm_bool(residual.get("fix24_correct"))
        if tale_correct is None:
            tale_correct = _norm_bool(residual.get("tale_correct"))

        fix24_correct = bool(fix24_correct)
        tale_correct = bool(tale_correct)

        frontier_row = mm["direct_reserve_semantic_frontier_v2"]
        tale_row = mm["external_tale_prompt_budgeting"]

        frontier_correct = bool(_extract_correct(frontier_row))
        tale_retry_correct = bool(_extract_correct(tale_row))

        frontier_answer = _extract_answer(frontier_row)
        tale_retry_answer = _extract_answer(tale_row)

        prior_answers = {
            str(sel.get("fix24_answer_canonical") or ""),
            str(sel.get("tale_answer_canonical") or ""),
            str(sel.get("frontier_answer_canonical") or ""),
            str(sel.get("l1_answer_canonical") or ""),
            str(sel.get("s1_answer_canonical") or ""),
        }
        prior_answers = {a for a in prior_answers if a}

        delta_frontier_vs_fix24 = int(frontier_correct) - int(fix24_correct)
        delta_tale_vs_fix24 = int(tale_retry_correct) - int(fix24_correct)
        delta_frontier_vs_tale = int(frontier_correct) - int(tale_correct)
        delta_tale_vs_tale = int(tale_retry_correct) - int(tale_correct)

        def _label(delta: int) -> str:
            if delta > 0:
                return "recovery"
            if delta < 0:
                return "regression"
            return "no_change"

        common = {
            "example_id": example_id,
            "dataset": dataset,
            "pilot_seed": EXPECTED_SEED,
            "pilot_budget": EXPECTED_BUDGET,
            "parent_seed": seed_parent,
            "parent_budget": budget_parent,
            "residual_category": sel.get("residual_category") or residual.get("root_cause_label"),
            "low_depth_flag": _norm_bool(state.get("low_depth_flag")),
            "external_agreement_signature": state.get("external_agreement_signature"),
            "candidate_count": _to_int(state.get("candidate_count")),
            "answer_diversity_cluster_count": _to_int(state.get("answer_diversity_cluster_count")),
            "avail_logged_frontier_alternative_proxy": _norm_bool(avail.get("avail_logged_frontier_alternative_proxy")),
            "avail_logged_external_alternative_proxy": _norm_bool(avail.get("avail_logged_external_alternative_proxy")),
            "fix24_correct": fix24_correct,
            "tale_correct": tale_correct,
        }

        frontier_outcome = {
            **common,
            "action_type": "extra_frontier",
            "pilot_method": "direct_reserve_semantic_frontier_v2",
            "extra_answer_canonical": frontier_answer,
            "extra_correct": frontier_correct,
            "delta_vs_fix24": delta_frontier_vs_fix24,
            "delta_vs_tale": delta_frontier_vs_tale,
            "delta_label_vs_fix24": _label(delta_frontier_vs_fix24),
            "delta_label_vs_tale": _label(delta_frontier_vs_tale),
            "new_answer_not_in_prior": bool(frontier_answer and frontier_answer not in prior_answers),
        }
        tale_outcome = {
            **common,
            "action_type": "extra_tale_retry",
            "pilot_method": "external_tale_prompt_budgeting",
            "extra_answer_canonical": tale_retry_answer,
            "extra_correct": tale_retry_correct,
            "delta_vs_fix24": delta_tale_vs_fix24,
            "delta_vs_tale": delta_tale_vs_tale,
            "delta_label_vs_fix24": _label(delta_tale_vs_fix24),
            "delta_label_vs_tale": _label(delta_tale_vs_tale),
            "new_answer_not_in_prior": bool(tale_retry_answer and tale_retry_answer not in prior_answers),
        }

        outcomes.extend([frontier_outcome, tale_outcome])

        runtime_feature_exclusions = ("gold", "exact", "correct")
        runtime_features = {
            f"state_{k}": v
            for k, v in state.items()
            if not any(term in str(k).lower() for term in runtime_feature_exclusions)
            and str(k) not in {"example_id", "dataset", "budget", "seed", "artifact", "split_kind"}
        }

        training_rows.append(
            {
                "example_id": example_id,
                "dataset": dataset,
                "parent_seed": seed_parent,
                "parent_budget": budget_parent,
                "action_type": "extra_frontier",
                "action_cost_proxy": _to_float(frontier_row.get("estimated_cost_usd"), 1.0),
                "target_delta_correctness_vs_fix24": delta_frontier_vs_fix24,
                "target_delta_correctness_vs_tale": delta_frontier_vs_tale,
                **runtime_features,
            }
        )
        training_rows.append(
            {
                "example_id": example_id,
                "dataset": dataset,
                "parent_seed": seed_parent,
                "parent_budget": budget_parent,
                "action_type": "extra_tale_retry",
                "action_cost_proxy": _to_float(tale_row.get("estimated_cost_usd"), 1.0),
                "target_delta_correctness_vs_fix24": delta_tale_vs_fix24,
                "target_delta_correctness_vs_tale": delta_tale_vs_tale,
                **runtime_features,
            }
        )

    action_summary: list[dict[str, Any]] = []
    by_action = defaultdict(list)
    for row in outcomes:
        by_action[row["action_type"]].append(row)

    for action_type, rows in sorted(by_action.items()):
        n = len(rows)
        action_summary.append(
            {
                "action_type": action_type,
                "n": n,
                "mean_delta_vs_fix24": round(sum(r["delta_vs_fix24"] for r in rows) / n, 6) if n else 0.0,
                "mean_delta_vs_tale": round(sum(r["delta_vs_tale"] for r in rows) / n, 6) if n else 0.0,
                "recoveries_vs_fix24": sum(1 for r in rows if r["delta_vs_fix24"] > 0),
                "regressions_vs_fix24": sum(1 for r in rows if r["delta_vs_fix24"] < 0),
                "recoveries_vs_tale": sum(1 for r in rows if r["delta_vs_tale"] > 0),
                "regressions_vs_tale": sum(1 for r in rows if r["delta_vs_tale"] < 0),
            }
        )

    by_residual: list[dict[str, Any]] = []
    by_action_resid = defaultdict(list)
    for row in outcomes:
        by_action_resid[(row["action_type"], str(row.get("residual_category") or "unknown"))].append(row)
    for (action_type, residual_category), rows in sorted(by_action_resid.items()):
        n = len(rows)
        by_residual.append(
            {
                "action_type": action_type,
                "residual_category": residual_category,
                "n": n,
                "mean_delta_vs_fix24": round(sum(r["delta_vs_fix24"] for r in rows) / n, 6),
                "recoveries_vs_fix24": sum(1 for r in rows if r["delta_vs_fix24"] > 0),
                "regressions_vs_fix24": sum(1 for r in rows if r["delta_vs_fix24"] < 0),
            }
        )

    by_bins: list[dict[str, Any]] = []

    def _bin_candidate_count(v: Any) -> str:
        n = _to_int(v)
        if n is None:
            return "unknown"
        if n <= 2:
            return "le2"
        if n <= 5:
            return "3to5"
        return "gt5"

    def _bin_bool(v: Any) -> str:
        b = _norm_bool(v)
        if b is None:
            return "unknown"
        return "true" if b else "false"

    grouped_bins = defaultdict(list)
    for row in outcomes:
        grouped_bins[(row["action_type"], "low_depth_flag", _bin_bool(row.get("low_depth_flag")))].append(row)
        grouped_bins[(row["action_type"], "external_agreement_signature", str(row.get("external_agreement_signature") or "unknown"))].append(row)
        grouped_bins[(row["action_type"], "candidate_count_bin", _bin_candidate_count(row.get("candidate_count")))].append(row)
        grouped_bins[(row["action_type"], "frontier_alt_available", _bin_bool(row.get("avail_logged_frontier_alternative_proxy")))].append(row)
        grouped_bins[(row["action_type"], "external_alt_available", _bin_bool(row.get("avail_logged_external_alternative_proxy")))].append(row)

    for (action_type, feature_name, feature_bin), rows in sorted(grouped_bins.items()):
        n = len(rows)
        by_bins.append(
            {
                "action_type": action_type,
                "feature_name": feature_name,
                "feature_bin": feature_bin,
                "n": n,
                "mean_delta_vs_fix24": round(sum(r["delta_vs_fix24"] for r in rows) / n, 6),
                "recoveries_vs_fix24": sum(1 for r in rows if r["delta_vs_fix24"] > 0),
                "regressions_vs_fix24": sum(1 for r in rows if r["delta_vs_fix24"] < 0),
            }
        )

    regressions = [r for r in outcomes if r["delta_vs_fix24"] < 0]
    recoveries = [r for r in outcomes if r["delta_vs_fix24"] > 0]

    recommendation = _choose_recommendation(action_summary)

    metrics = {
        "generated_at": _now_iso(),
        "expected_rows": expected_rows,
        "pilot_rows_loaded": len(pilot_rows),
        "selected_cases": len(selected_cases),
        "extra_action_plan_rows": len(extra_action_plan),
        "outcome_rows": len(outcomes),
        "training_rows": len(training_rows),
        "action_summary": action_summary,
        "recommendation": recommendation,
        "safety": {
            "offline_only": True,
            "no_provider_api_calls": True,
            "gold_offline_only": True,
        },
    }

    report_lines = [
        "# FIX-6 Extra-Action Pilot Analysis",
        "",
        f"Generated: {_now_iso()}",
        f"Selected cases: {len(selected_cases)}",
        f"Pilot rows loaded: {len(pilot_rows)}",
        "",
        "## Headline (offline diagnostic)",
    ]
    for row in action_summary:
        report_lines.append(
            f"- {row['action_type']}: mean delta vs FIX-2+FIX-4 = {row['mean_delta_vs_fix24']:+.3f} "
            f"(recoveries/regressions {row['recoveries_vs_fix24']}/{row['regressions_vs_fix24']}, n={row['n']})"
        )
    report_lines.extend(
        [
            "",
            "## Recommendation",
            f"- {recommendation['recommended_action']}",
            "- Offline signal only; do not promote runtime policy without independent confirmation.",
        ]
    )

    return {
        "outcomes": outcomes,
        "training_rows": training_rows,
        "action_summary": action_summary,
        "by_residual": by_residual,
        "by_bins": by_bins,
        "regressions": regressions,
        "recoveries": recoveries,
        "recommendation": recommendation,
        "metrics": metrics,
        "report_markdown": "\n".join(report_lines) + "\n",
    }


def _discover_pilot_jsonl_paths(pilot_root: Path) -> list[Path]:
    return sorted(pilot_root.glob("runner_output/**/per_example_records.jsonl"))


def run_analysis(
    *,
    pilot_root: Path,
    fix6_root: Path,
    main_postrun_root: Path,
    output_root: Path,
    expected_rows: int = EXPECTED_ROWS,
    expected_examples: int = EXPECTED_EXAMPLES,
) -> dict[str, Any]:
    del main_postrun_root  # kept for CLI/API stability and future extension.

    output_root.mkdir(parents=True, exist_ok=False)

    selected_cases = _load_jsonl(pilot_root / "selected_cases.jsonl")
    extra_action_plan = _load_csv(pilot_root / "extra_action_plan.csv")

    selected_cases_summary_path = pilot_root / "selected_cases_summary.csv"
    selected_cases_summary_present = selected_cases_summary_path.exists()

    fix6_tables = _load_pre_action_tables(fix6_root)
    per_example_paths = _discover_pilot_jsonl_paths(pilot_root)

    pilot_rows: list[dict[str, Any]] = []
    for p in per_example_paths:
        pilot_rows.extend(_load_jsonl(p))

    validation = validate_pilot_rows(
        pilot_rows,
        expected_rows=expected_rows,
        expected_examples=expected_examples,
    )

    readiness_metrics = {
        "generated_at": _now_iso(),
        "pilot_root": str(pilot_root),
        "fix6_root": str(fix6_root),
        "selected_cases_count": len(selected_cases),
        "extra_action_plan_count": len(extra_action_plan),
        "selected_cases_summary_present": selected_cases_summary_present,
        "discovered_per_example_paths": [str(p) for p in per_example_paths],
        "validation": {
            "row_count": validation.row_count,
            "complete": validation.complete,
            "reasons": validation.reasons,
            "status_counts": validation.status_counts,
            "method_counts": validation.method_counts,
            "unique_examples": validation.unique_examples,
            "duplicate_count": validation.duplicate_count,
            "promotion_review_record_coverage": validation.promotion_review_record_coverage,
            "promotion_review_validation_coverage": validation.promotion_review_validation_coverage,
            "enough_for_promotion_review_counts": validation.enough_for_promotion_review_counts,
            "seed_mismatch_count": validation.seed_mismatch_count,
            "budget_mismatch_count": validation.budget_mismatch_count,
            "method_mismatch_count": validation.method_mismatch_count,
            "leakage_hits_count": len(validation.leakage_hits),
        },
    }

    if not validation.complete:
        missing_items: list[str] = []
        if not per_example_paths:
            missing_items.append("runner_output/**/per_example_records.jsonl")
        if validation.row_count != expected_rows:
            missing_items.append(f"expected_rows={expected_rows} (found={validation.row_count})")
        if validation.unique_examples != expected_examples:
            missing_items.append(
                f"expected_examples={expected_examples} (found={validation.unique_examples})"
            )

        lines = [
            "# FIX-6 Extra-Action Pilot Readiness Report",
            "",
            f"Generated: {_now_iso()}",
            "",
            "## Status",
            "- Pilot rows are not complete yet; analysis outputs were not generated.",
            f"- Rows loaded: {validation.row_count} / {expected_rows}",
            f"- Unique examples: {validation.unique_examples} / {expected_examples}",
            "",
            "## Missing / Blocking",
        ]
        for item in missing_items or ["none"]:
            lines.append(f"- {item}")
        lines.extend(
            [
                "",
                "## Validation Notes",
            ]
        )
        for reason in validation.reasons or ["none"]:
            lines.append(f"- {reason}")

        (output_root / "pilot_readiness_report.md").write_text("\n".join(lines) + "\n")
        _write_json(output_root / "pilot_readiness_metrics.json", readiness_metrics)
        return {
            "mode": "readiness",
            "output_root": str(output_root),
            "metrics": readiness_metrics,
        }

    analysis = analyze_complete_pilot(
        selected_cases=selected_cases,
        extra_action_plan=extra_action_plan,
        pilot_rows=pilot_rows,
        fix6_tables=fix6_tables,
        expected_rows=expected_rows,
    )

    (output_root / "pilot_analysis_report.md").write_text(analysis["report_markdown"])
    _write_json(output_root / "pilot_analysis_metrics.json", analysis["metrics"])
    _write_csv(output_root / "extra_action_outcomes.csv", analysis["outcomes"])
    _write_jsonl(output_root / "extra_action_outcomes.jsonl", analysis["outcomes"])
    _write_csv(output_root / "lovec_training_rows.csv", analysis["training_rows"])
    _write_csv(output_root / "action_value_summary.csv", analysis["action_summary"])
    _write_csv(output_root / "action_value_by_residual_category.csv", analysis["by_residual"])
    _write_csv(output_root / "action_value_by_state_feature_bins.csv", analysis["by_bins"])
    _write_jsonl(output_root / "pilot_regression_cases.jsonl", analysis["regressions"])
    _write_jsonl(output_root / "pilot_recovery_cases.jsonl", analysis["recoveries"])
    _write_json(output_root / "recommended_lovec_policy.json", analysis["recommendation"])

    return {
        "mode": "complete",
        "output_root": str(output_root),
        "metrics": analysis["metrics"],
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot-root", type=Path, required=True)
    parser.add_argument("--fix6-root", type=Path, required=True)
    parser.add_argument("--main-postrun-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--expected-rows", type=int, default=EXPECTED_ROWS)
    parser.add_argument("--expected-examples", type=int, default=EXPECTED_EXAMPLES)
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    run_analysis(
        pilot_root=args.pilot_root,
        fix6_root=args.fix6_root,
        main_postrun_root=args.main_postrun_root,
        output_root=args.output_root,
        expected_rows=args.expected_rows,
        expected_examples=args.expected_examples,
    )


if __name__ == "__main__":
    main()
