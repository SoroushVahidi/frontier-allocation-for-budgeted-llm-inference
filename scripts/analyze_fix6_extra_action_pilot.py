#!/usr/bin/env python3
"""Offline analyzer for FIX-6 extra-action pilot outputs.

Safe-by-default behavior:
- If pilot rows are missing/incomplete, emit readiness outputs and exit 0.
- Never mutates live pilot output directory.
- Uses gold/exact only as offline labels for diagnostics/targets.
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


FRONTIER_METHOD = "direct_reserve_semantic_frontier_v2"
TALE_METHOD = "external_tale_prompt_budgeting"
REQUIRED_METHODS = {FRONTIER_METHOD, TALE_METHOD}

FORBIDDEN_FEATURE_TOKENS = ("gold", "exact_match", "exact match", "correct")


def _norm_answer(v: Any) -> str | None:
    s = str(v or "").strip()
    if not s or s.lower() in {"none", "__unknown__"}:
        return None
    return s


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open() as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open() as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow(row)


def _write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, indent=2))


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def _scan_for_label_leakage(row: dict[str, Any]) -> list[dict[str, Any]]:
    """Scan prompt/feature-like fields for gold/exact-match label tokens."""
    hits: list[dict[str, Any]] = []

    def scan_obj(obj: Any, path: str) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                scan_obj(v, f"{path}.{k}" if path else str(k))
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                scan_obj(v, f"{path}[{i}]")
        elif isinstance(obj, str):
            low = obj.lower()
            if any(tok in low for tok in ("gold_answer", "gold_answer_canonical", "exact_match", "exact match")):
                hits.append({"field": path, "snippet": obj[:220]})

    feature_fields = {
        "question": row.get("question"),
        "result_metadata": row.get("result_metadata"),
    }
    pr = row.get("promotion_review_record")
    if isinstance(pr, dict):
        for k in (
            "prompt_text",
            "candidate_trace",
            "gate_features",
            "policy_thresholds",
            "prune_or_selection_reasons",
            "candidate_pool_summary",
            "discovery_tree",
        ):
            feature_fields[f"promotion_review_record.{k}"] = pr.get(k)

    for k, v in feature_fields.items():
        scan_obj(v, k)
    return hits


@dataclass
class PilotReadiness:
    ready: bool
    reason: str
    metrics: dict[str, Any]


def _discover_pilot_jsonl(pilot_root: Path) -> Path | None:
    paths = sorted(pilot_root.glob("runner_output/**/per_example_records.jsonl"))
    if not paths:
        return None
    # Choose largest row file to avoid stale partial alternates.
    best = None
    best_size = -1
    for p in paths:
        try:
            size = p.stat().st_size
        except Exception:
            size = -1
        if size > best_size:
            best = p
            best_size = size
    return best


def _parse_bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    return s in {"1", "true", "yes", "y"}


def _feature_columns_from_state(state_row: dict[str, Any]) -> dict[str, Any]:
    feature_cols: dict[str, Any] = {}
    for k, v in state_row.items():
        lk = k.lower()
        if k in {"artifact", "split_kind", "example_id", "dataset", "seed", "budget"}:
            continue
        if any(tok in lk for tok in FORBIDDEN_FEATURE_TOKENS):
            continue
        feature_cols[f"f_{k}"] = v
    return feature_cols


def _group_pilot_rows(rows: list[dict[str, Any]]) -> dict[tuple[str, Any, Any, str], dict[str, dict[str, Any]]]:
    grouped: dict[tuple[str, Any, Any, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        key = (
            str(row.get("example_id")),
            row.get("seed"),
            row.get("budget"),
            str(row.get("dataset") or ""),
        )
        grouped[key][str(row.get("method") or "")] = row
    return grouped


def _build_readiness(
    pilot_root: Path,
    selected_cases: list[dict[str, Any]],
    pilot_rows: list[dict[str, Any]] | None,
    expected_rows: int,
    expected_cases: int,
) -> PilotReadiness:
    if pilot_rows is None:
        return PilotReadiness(
            ready=False,
            reason="pilot_rows_missing",
            metrics={
                "selected_case_count": len(selected_cases),
                "expected_case_count": expected_cases,
                "expected_rows": expected_rows,
                "pilot_rows_found": 0,
                "ready": False,
            },
        )

    method_counts = Counter(str(r.get("method") or "") for r in pilot_rows)
    status_counts = Counter(str(r.get("status") or "") for r in pilot_rows)
    unique_examples = {str(r.get("example_id") or "") for r in pilot_rows}
    seeds = {r.get("seed") for r in pilot_rows}
    budgets = {r.get("budget") for r in pilot_rows}

    dup_key = Counter(
        (
            r.get("provider"),
            r.get("dataset"),
            r.get("seed"),
            r.get("budget"),
            r.get("method"),
            r.get("example_id"),
        )
        for r in pilot_rows
    )
    duplicate_count = sum(c - 1 for c in dup_key.values() if c > 1)

    ready = True
    reason = "ready"
    if len(pilot_rows) < expected_rows:
        ready = False
        reason = "pilot_rows_incomplete"
    elif duplicate_count != 0:
        ready = False
        reason = "duplicate_rows_detected"
    elif set(method_counts.keys()) != REQUIRED_METHODS:
        ready = False
        reason = "methods_incomplete"
    elif seeds != {53}:
        ready = False
        reason = "unexpected_seed"
    elif budgets != {6}:
        ready = False
        reason = "unexpected_budget"
    elif len(unique_examples) < min(expected_cases, len(selected_cases)):
        ready = False
        reason = "selected_examples_incomplete"

    metrics = {
        "selected_case_count": len(selected_cases),
        "expected_case_count": expected_cases,
        "expected_rows": expected_rows,
        "pilot_rows_found": len(pilot_rows),
        "pilot_unique_examples": len(unique_examples),
        "method_counts": dict(method_counts),
        "status_counts": dict(status_counts),
        "seeds": sorted(seeds),
        "budgets": sorted(budgets),
        "duplicate_count": duplicate_count,
        "ready": ready,
        "reason": reason,
    }
    return PilotReadiness(ready=ready, reason=reason, metrics=metrics)


def run_analysis(
    pilot_root: Path,
    fix6_root: Path,
    main_postrun_root: Path,
    output_root: Path,
    expected_rows: int,
    expected_cases: int,
) -> None:
    output_root.mkdir(parents=True, exist_ok=False)

    selected_cases_path = pilot_root / "selected_cases.jsonl"
    extra_action_plan_path = pilot_root / "extra_action_plan.csv"

    if not selected_cases_path.exists() or not extra_action_plan_path.exists():
        metrics = {
            "ready": False,
            "reason": "missing_selection_inputs",
            "selected_cases_jsonl_exists": selected_cases_path.exists(),
            "extra_action_plan_csv_exists": extra_action_plan_path.exists(),
        }
        _write_json(output_root / "pilot_readiness_metrics.json", metrics)
        (output_root / "pilot_readiness_report.md").write_text(
            "# Pilot Readiness Report\n\n"
            "Missing required pilot selection inputs.\n"
            f"- selected_cases.jsonl exists: `{selected_cases_path.exists()}`\n"
            f"- extra_action_plan.csv exists: `{extra_action_plan_path.exists()}`\n"
        )
        return

    selected_cases = _read_jsonl(selected_cases_path)
    extra_action_plan = _read_csv(extra_action_plan_path)

    pilot_jsonl = _discover_pilot_jsonl(pilot_root)
    pilot_rows = _read_jsonl(pilot_jsonl) if pilot_jsonl else None

    readiness = _build_readiness(
        pilot_root=pilot_root,
        selected_cases=selected_cases,
        pilot_rows=pilot_rows,
        expected_rows=expected_rows,
        expected_cases=expected_cases,
    )

    if not readiness.ready:
        _write_json(output_root / "pilot_readiness_metrics.json", readiness.metrics)
        (output_root / "pilot_readiness_report.md").write_text(
            "# Pilot Readiness Report\n\n"
            f"- ready: `{readiness.ready}`\n"
            f"- reason: `{readiness.reason}`\n"
            f"- pilot root: `{pilot_root}`\n"
            f"- discovered per_example_records: `{str(pilot_jsonl) if pilot_jsonl else 'missing'}`\n"
            f"- selected cases: `{len(selected_cases)}`\n"
            f"- expected rows: `{expected_rows}`\n"
            f"- rows found: `{readiness.metrics.get('pilot_rows_found', 0)}`\n"
            "\nReadiness metrics are in `pilot_readiness_metrics.json`.\n"
        )
        return

    assert pilot_rows is not None  # guarded by readiness

    # Load FIX-6 offline tables.
    state_rows = _read_csv(fix6_root / "fix6_state_feature_table.csv")
    residual_rows = _read_csv(fix6_root / "fix6_residual_failure_cases.csv")
    action_availability_rows = _read_csv(fix6_root / "fix6_action_availability.csv")
    oracle_rows = _read_csv(fix6_root / "fix6_oracle_action_table.csv")

    # Build quick maps.
    state_map = {
        str(r.get("example_id")): r
        for r in state_rows
        if str(r.get("artifact")) == "overnight_300_unbiased"
    }
    residual_map = {
        str(r.get("example_id")): r
        for r in residual_rows
        if str(r.get("artifact")) == "overnight_300_unbiased"
    }
    action_avail_map = {
        str(r.get("example_id")): r
        for r in action_availability_rows
        if str(r.get("artifact")) == "overnight_300_unbiased"
    }
    oracle_map = {
        str(r.get("example_id")): r
        for r in oracle_rows
        if str(r.get("artifact")) == "overnight_300_unbiased"
    }

    # Pilot row grouping.
    grouped = _group_pilot_rows(pilot_rows)
    by_example: dict[str, dict[str, Any]] = {}
    for (_, _, _, _), mm in grouped.items():
        frontier = mm.get(FRONTIER_METHOD)
        tale = mm.get(TALE_METHOD)
        if not frontier and not tale:
            continue
        eid = str((frontier or tale).get("example_id") or "")
        by_example[eid] = {"frontier": frontier, "tale": tale}

    # Validate promotion review coverage + leakage.
    pr_rec = 0
    pr_val = 0
    enough_counter = Counter()
    runtime_counter = Counter()
    leakage_hits: list[dict[str, Any]] = []

    for r in pilot_rows:
        if isinstance(r.get("promotion_review_record"), dict):
            pr_rec += 1
        pv = r.get("promotion_review_validation")
        if isinstance(pv, dict):
            pr_val += 1
            enough_counter[str(pv.get("enough_for_promotion_review", "missing"))] += 1
            runtime_counter[str(pv.get("runtime_failure_reviewable", "missing"))] += 1
        for h in _scan_for_label_leakage(r):
            h2 = dict(h)
            h2["example_id"] = r.get("example_id")
            h2["method"] = r.get("method")
            leakage_hits.append(h2)

    # Build outcomes per selected case.
    outcomes: list[dict[str, Any]] = []
    recovery_rows: list[dict[str, Any]] = []
    regression_rows: list[dict[str, Any]] = []
    training_rows: list[dict[str, Any]] = []

    for case in selected_cases:
        eid = str(case.get("example_id") or "")
        p = by_example.get(eid, {})
        frow = p.get("frontier")
        trow = p.get("tale")

        rrow = residual_map.get(eid, {})
        srow = state_map.get(eid, {})
        arow = action_avail_map.get(eid, {})
        orow = oracle_map.get(eid, {})

        fix24_correct = _parse_bool((case.get("offline_labels") or {}).get("fix24_correct", rrow.get("fix24_correct")))
        tale_correct_base = _parse_bool((case.get("offline_labels") or {}).get("tale_correct", rrow.get("tale_correct")))

        frontier_ans = _norm_answer((frow or {}).get("final_answer_canonical") or (frow or {}).get("selected_answer_canonical"))
        tale_retry_ans = _norm_answer((trow or {}).get("final_answer_canonical") or (trow or {}).get("selected_answer_canonical"))

        frontier_correct = bool((frow or {}).get("exact_match")) if frow else None
        tale_retry_correct = bool((trow or {}).get("exact_match")) if trow else None

        prior_answers = {
            _norm_answer(case.get("fix24_answer_canonical")),
            _norm_answer(case.get("tale_answer_canonical")),
            _norm_answer(case.get("l1_answer_canonical")),
            _norm_answer(case.get("s1_answer_canonical")),
            _norm_answer(case.get("frontier_answer_canonical")),
        }
        prior_answers.discard(None)

        frontier_new_answer = bool(frontier_ans and frontier_ans not in prior_answers)
        tale_retry_new_answer = bool(tale_retry_ans and tale_retry_ans not in prior_answers)

        def classify(cur: bool, nxt: bool | None) -> str:
            if nxt is None:
                return "missing"
            if (not cur) and nxt:
                return "recovery"
            if cur and (not nxt):
                return "regression"
            return "no_change"

        frontier_label = classify(fix24_correct, frontier_correct)
        tale_retry_label = classify(fix24_correct, tale_retry_correct)

        row = {
            "example_id": eid,
            "dataset": case.get("dataset"),
            "tier": case.get("tier"),
            "residual_category": case.get("residual_category") or rrow.get("root_cause_label"),
            "fix24_correct": fix24_correct,
            "tale_correct_base": tale_correct_base,
            "extra_frontier_answer": frontier_ans,
            "extra_frontier_correct": frontier_correct,
            "extra_tale_retry_answer": tale_retry_ans,
            "extra_tale_retry_correct": tale_retry_correct,
            "delta_frontier_vs_fix24": (int(frontier_correct) - int(fix24_correct)) if frontier_correct is not None else None,
            "delta_tale_retry_vs_fix24": (int(tale_retry_correct) - int(fix24_correct)) if tale_retry_correct is not None else None,
            "delta_frontier_vs_tale": (int(frontier_correct) - int(tale_correct_base)) if frontier_correct is not None else None,
            "delta_tale_retry_vs_tale": (int(tale_retry_correct) - int(tale_correct_base)) if tale_retry_correct is not None else None,
            "frontier_effect_label": frontier_label,
            "tale_retry_effect_label": tale_retry_label,
            "frontier_new_answer_not_in_prior": frontier_new_answer,
            "tale_retry_new_answer_not_in_prior": tale_retry_new_answer,
            "low_depth_flag": _parse_bool(srow.get("low_depth_flag")),
            "weak_search_flag": _parse_bool(srow.get("weak_search_flag")),
            "external_agreement_signature": srow.get("external_agreement_signature"),
            "avail_logged_frontier_alt": _parse_bool(arow.get("avail_logged_frontier_alternative_proxy")),
            "avail_logged_external_alt": _parse_bool(arow.get("avail_logged_external_alternative_proxy")),
            "oracle_observable_action": orow.get("oracle_observable_action"),
            "oracle_observable_correct": _parse_bool(orow.get("oracle_observable_correct")),
        }
        outcomes.append(row)

        if frontier_label == "recovery":
            recovery_rows.append({"action_type": "extra_frontier_proxy", **row})
        if tale_retry_label == "recovery":
            recovery_rows.append({"action_type": "extra_tale_retry_proxy", **row})
        if frontier_label == "regression":
            regression_rows.append({"action_type": "extra_frontier_proxy", **row})
        if tale_retry_label == "regression":
            regression_rows.append({"action_type": "extra_tale_retry_proxy", **row})

        feature_cols = _feature_columns_from_state(srow)

        if frow is not None:
            training_rows.append(
                {
                    "example_id": eid,
                    "dataset": case.get("dataset"),
                    "seed": frow.get("seed"),
                    "budget": frow.get("budget"),
                    "residual_category": row["residual_category"],
                    "action_type": "extra_frontier_proxy",
                    "action_answer": frontier_ans,
                    "action_correct_offline": frontier_correct,
                    "current_fix24_correct_offline": fix24_correct,
                    "current_tale_correct_offline": tale_correct_base,
                    "delta_vs_fix24": row["delta_frontier_vs_fix24"],
                    "delta_vs_tale": row["delta_frontier_vs_tale"],
                    "action_cost_total_tokens": frow.get("total_tokens"),
                    "action_cost_api_calls": frow.get("cohere_logical_api_calls"),
                    "action_latency_seconds": frow.get("latency_seconds"),
                    **feature_cols,
                }
            )

        if trow is not None:
            training_rows.append(
                {
                    "example_id": eid,
                    "dataset": case.get("dataset"),
                    "seed": trow.get("seed"),
                    "budget": trow.get("budget"),
                    "residual_category": row["residual_category"],
                    "action_type": "extra_tale_retry_proxy",
                    "action_answer": tale_retry_ans,
                    "action_correct_offline": tale_retry_correct,
                    "current_fix24_correct_offline": fix24_correct,
                    "current_tale_correct_offline": tale_correct_base,
                    "delta_vs_fix24": row["delta_tale_retry_vs_fix24"],
                    "delta_vs_tale": row["delta_tale_retry_vs_tale"],
                    "action_cost_total_tokens": trow.get("total_tokens"),
                    "action_cost_api_calls": trow.get("cohere_logical_api_calls"),
                    "action_latency_seconds": trow.get("latency_seconds"),
                    **feature_cols,
                }
            )

    # Aggregates.
    action_summary: list[dict[str, Any]] = []
    by_action = defaultdict(list)
    for tr in training_rows:
        by_action[str(tr.get("action_type"))].append(tr)

    for action_type, rows in sorted(by_action.items()):
        n = len(rows)
        delta_fix24 = [r.get("delta_vs_fix24") for r in rows if r.get("delta_vs_fix24") is not None]
        delta_tale = [r.get("delta_vs_tale") for r in rows if r.get("delta_vs_tale") is not None]
        regressions = sum(1 for r in rows if r.get("delta_vs_fix24") == -1)
        recoveries = sum(1 for r in rows if r.get("delta_vs_fix24") == 1)
        action_summary.append(
            {
                "action_type": action_type,
                "n_rows": n,
                "mean_delta_vs_fix24": (sum(delta_fix24) / len(delta_fix24)) if delta_fix24 else 0.0,
                "mean_delta_vs_tale": (sum(delta_tale) / len(delta_tale)) if delta_tale else 0.0,
                "recoveries": recoveries,
                "regressions": regressions,
                "recovery_rate": (recoveries / n) if n else 0.0,
                "regression_rate": (regressions / n) if n else 0.0,
            }
        )

    by_residual: list[dict[str, Any]] = []
    by_state_bins: list[dict[str, Any]] = []

    def add_group(rows: list[dict[str, Any]], group_name: str, group_value: str) -> None:
        if not rows:
            return
        by_state_bins.append(
            {
                "group_name": group_name,
                "group_value": group_value,
                "n_rows": len(rows),
                "mean_delta_vs_fix24": sum(r["delta_vs_fix24"] for r in rows if r["delta_vs_fix24"] is not None) / max(1, len([r for r in rows if r["delta_vs_fix24"] is not None])),
                "mean_delta_vs_tale": sum(r["delta_vs_tale"] for r in rows if r["delta_vs_tale"] is not None) / max(1, len([r for r in rows if r["delta_vs_tale"] is not None])),
            }
        )

    for action_type, rows in sorted(by_action.items()):
        cat_map = defaultdict(list)
        for r in rows:
            cat_map[str(r.get("residual_category"))].append(r)
        for cat, sub in sorted(cat_map.items()):
            by_residual.append(
                {
                    "action_type": action_type,
                    "residual_category": cat,
                    "n_rows": len(sub),
                    "mean_delta_vs_fix24": sum(x["delta_vs_fix24"] for x in sub if x["delta_vs_fix24"] is not None) / max(1, len([x for x in sub if x["delta_vs_fix24"] is not None])),
                    "mean_delta_vs_tale": sum(x["delta_vs_tale"] for x in sub if x["delta_vs_tale"] is not None) / max(1, len([x for x in sub if x["delta_vs_tale"] is not None])),
                    "recoveries": sum(1 for x in sub if x["delta_vs_fix24"] == 1),
                    "regressions": sum(1 for x in sub if x["delta_vs_fix24"] == -1),
                }
            )

        for flag in ("True", "False"):
            sub = [r for r in rows if str(r.get("f_low_depth_flag")) == flag]
            add_group(sub, f"{action_type}:low_depth_flag", flag)
        for sig in sorted({str(r.get("f_external_agreement_signature")) for r in rows}):
            sub = [r for r in rows if str(r.get("f_external_agreement_signature")) == sig]
            add_group(sub, f"{action_type}:external_agreement_signature", sig)

    # Recommendation heuristic.
    action_gain = {r["action_type"]: r["mean_delta_vs_fix24"] for r in action_summary}
    frontier_gain = action_gain.get("extra_frontier_proxy", 0.0)
    tale_gain = action_gain.get("extra_tale_retry_proxy", 0.0)
    frontier_reg = next((r["regression_rate"] for r in action_summary if r["action_type"] == "extra_frontier_proxy"), 0.0)
    tale_reg = next((r["regression_rate"] for r in action_summary if r["action_type"] == "extra_tale_retry_proxy"), 0.0)

    if max(frontier_gain, tale_gain) >= 0.03 and min(frontier_reg, tale_reg) <= 0.1:
        recommendation = "A"
        rec_reason = "Strong pilot signal with manageable regression risk."
    elif max(frontier_gain, tale_gain) > 0.0:
        recommendation = "B"
        rec_reason = "Signal positive but underpowered for immediate policy lock-in."
    elif frontier_gain > tale_gain:
        recommendation = "C"
        rec_reason = "Frontier extra action dominates TALE retry in pilot."
    elif tale_gain > frontier_gain:
        recommendation = "D"
        rec_reason = "TALE retry dominates frontier extra action in pilot."
    else:
        recommendation = "E"
        rec_reason = "No positive action-value signal over baseline."

    recommended_policy = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "recommendation": recommendation,
        "reason": rec_reason,
        "frontier_mean_delta_vs_fix24": frontier_gain,
        "tale_retry_mean_delta_vs_fix24": tale_gain,
        "frontier_regression_rate": frontier_reg,
        "tale_retry_regression_rate": tale_reg,
        "notes": [
            "Offline pilot proxy analysis only.",
            "No gold/exact features were used in lovec_training_rows feature columns.",
        ],
    }

    # Write required outputs.
    _write_csv(
        output_root / "extra_action_outcomes.csv",
        outcomes,
        sorted({k for r in outcomes for k in r.keys()}),
    )
    _write_jsonl(output_root / "extra_action_outcomes.jsonl", outcomes)
    _write_csv(
        output_root / "lovec_training_rows.csv",
        training_rows,
        sorted({k for r in training_rows for k in r.keys()}),
    )
    _write_csv(
        output_root / "action_value_summary.csv",
        action_summary,
        [
            "action_type",
            "n_rows",
            "mean_delta_vs_fix24",
            "mean_delta_vs_tale",
            "recoveries",
            "regressions",
            "recovery_rate",
            "regression_rate",
        ],
    )
    _write_csv(
        output_root / "action_value_by_residual_category.csv",
        by_residual,
        [
            "action_type",
            "residual_category",
            "n_rows",
            "mean_delta_vs_fix24",
            "mean_delta_vs_tale",
            "recoveries",
            "regressions",
        ],
    )
    _write_csv(
        output_root / "action_value_by_state_feature_bins.csv",
        by_state_bins,
        ["group_name", "group_value", "n_rows", "mean_delta_vs_fix24", "mean_delta_vs_tale"],
    )
    _write_jsonl(output_root / "pilot_regression_cases.jsonl", regression_rows)
    _write_jsonl(output_root / "pilot_recovery_cases.jsonl", recovery_rows)
    _write_json(output_root / "recommended_lovec_policy.json", recommended_policy)

    leakage_report = {
        "scan_scope": "prompt_and_feature_fields_only",
        "patterns": ["gold_answer", "gold_answer_canonical", "exact_match", "exact match"],
        "total_rows_scanned": len(pilot_rows),
        "hit_count": len(leakage_hits),
        "sample_hits": leakage_hits[:40],
    }
    _write_json(output_root / "pilot_leakage_scan_report.json", leakage_report)

    metrics = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pilot_root": str(pilot_root),
        "fix6_root": str(fix6_root),
        "main_postrun_root": str(main_postrun_root),
        "pilot_rows": len(pilot_rows),
        "selected_cases": len(selected_cases),
        "expected_rows": expected_rows,
        "method_counts": readiness.metrics.get("method_counts", {}),
        "status_counts": readiness.metrics.get("status_counts", {}),
        "duplicate_count": readiness.metrics.get("duplicate_count", 0),
        "promotion_review_record_coverage": pr_rec / len(pilot_rows) if pilot_rows else 0.0,
        "promotion_review_validation_coverage": pr_val / len(pilot_rows) if pilot_rows else 0.0,
        "enough_for_promotion_review": dict(enough_counter),
        "runtime_failure_reviewable": dict(runtime_counter),
        "leakage_hit_count": len(leakage_hits),
        "action_summary": action_summary,
        "recommended_lovec_action": recommended_policy,
    }
    _write_json(output_root / "pilot_analysis_metrics.json", metrics)

    lines = [
        "# FIX-6 Extra-Action Pilot Analysis",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Pilot root: `{pilot_root}`",
        f"Pilot rows: `{len(pilot_rows)}` / expected `{expected_rows}`",
        f"Selected cases: `{len(selected_cases)}`",
        "",
        "## Integrity",
        f"- Methods: `{readiness.metrics.get('method_counts', {})}`",
        f"- Status counts: `{readiness.metrics.get('status_counts', {})}`",
        f"- Duplicate count: `{readiness.metrics.get('duplicate_count', 0)}`",
        f"- Promotion review record coverage: `{metrics['promotion_review_record_coverage']:.3f}`",
        f"- Promotion review validation coverage: `{metrics['promotion_review_validation_coverage']:.3f}`",
        f"- Leakage hits (prompt/feature fields): `{len(leakage_hits)}`",
        "",
        "## Action Value Summary",
    ]
    for r in action_summary:
        lines.append(
            f"- {r['action_type']}: n={r['n_rows']}, mean ΔvsFIX24={r['mean_delta_vs_fix24']:+.4f}, "
            f"recoveries={r['recoveries']}, regressions={r['regressions']}"
        )
    lines.extend(
        [
            "",
            "## Recommendation",
            f"- Next action: `{recommended_policy['recommendation']}`",
            f"- Reason: {recommended_policy['reason']}",
        ]
    )
    (output_root / "pilot_analysis_report.md").write_text("\n".join(lines))


def _default_output_root(repo_root: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return repo_root / f"outputs/fix6_extra_action_pilot_analysis_PREP_{stamp}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze FIX-6 extra-action pilot outputs safely.")
    parser.add_argument("--pilot-root", type=Path, required=True)
    parser.add_argument("--fix6-root", type=Path, required=True)
    parser.add_argument("--main-postrun-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--expected-rows", type=int, default=80)
    parser.add_argument("--expected-cases", type=int, default=40)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    out = args.output_root or _default_output_root(repo_root)

    run_analysis(
        pilot_root=args.pilot_root,
        fix6_root=args.fix6_root,
        main_postrun_root=args.main_postrun_root,
        output_root=out,
        expected_rows=args.expected_rows,
        expected_cases=args.expected_cases,
    )
    print(out)


if __name__ == "__main__":
    main()
