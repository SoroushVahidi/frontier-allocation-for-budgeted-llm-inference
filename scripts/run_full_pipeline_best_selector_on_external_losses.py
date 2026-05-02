#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
BEST_INTERNAL_METHOD = "direct_reserve_semantic_frontier_v2"


def _norm(v: Any) -> str:
    return "" if v is None else str(v).strip()


def _to_int(v: Any, default: int = 0) -> int:
    try:
        return int(float(v))
    except Exception:
        return default


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = sorted({k for r in rows for k in r.keys()})
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fields})


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build full-pipeline+selected-selector artifacts on external-loss subset.")
    p.add_argument("--input-cases-csv", required=True)
    p.add_argument("--selected-config", required=True)
    p.add_argument("--discovery-records-jsonl", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--run-type", default="B", choices=["A", "B"])
    return p.parse_args()


def _diagnose(row: dict[str, Any]) -> str:
    if row["new_full_pipeline_selected_correct"] == 1 and row["best_external_correct"] == 1:
        return "fixed"
    if row["missing_verifier_score_indicators"] == 1:
        return "score_missing"
    if row["trace_availability"] == 0:
        return "trace_missing"
    if row["best_external_correct"] == 0:
        return "external_also_wrong"
    if row.get("selector_failure_gold_present") == 1:
        return "selector_failure"
    if row.get("discovery_failure_gold_absent") == 1:
        return "discovery_failure"
    if row["still_loses_to_best_external"] == 1 and row["gold_present_in_candidate_groups"] == 1:
        return "selector_failure"
    if row["still_loses_to_best_external"] == 1 and row["gold_present_in_candidate_groups"] == 0:
        return "discovery_failure"
    return "unknown"


def _intervention(diag: str) -> str:
    if diag == "selector_failure":
        return "improve final answer-group reranking/scoring calibration"
    if diag == "discovery_failure":
        return "improve candidate generation and frontier coverage"
    if diag == "score_missing":
        return "fill missing verifier scores and rerun selector"
    if diag == "trace_missing":
        return "rerun with trace-preserving candidate metadata"
    if diag == "external_also_wrong":
        return "case may be inherently hard/noisy; inspect manually"
    return "manual triage needed"


def main() -> int:
    args = parse_args()
    out_dir = Path(args.output_dir) if args.output_dir.startswith("/") else (REPO_ROOT / args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    input_cases = _read_csv(Path(args.input_cases_csv))
    selector_cfg = json.loads(Path(args.selected_config).read_text(encoding="utf-8"))
    score_cache_path = REPO_ROOT / selector_cfg["score_cache_path"]
    score_rows = _read_jsonl(score_cache_path)
    score_map = {(str(r.get("case_id", "")), str(r.get("candidate_id", ""))): float(r.get("verifier_score", 0.0)) for r in score_rows}

    discovery_rows = _read_jsonl(Path(args.discovery_records_jsonl))
    discovery_index = {}
    for r in discovery_rows:
        if _norm(r.get("method")) != BEST_INTERNAL_METHOD:
            continue
        key = (_norm(r.get("dataset")), _norm(r.get("example_id")), _to_int(r.get("seed")), _to_int(r.get("budget")))
        discovery_index[key] = r

    per_case: list[dict[str, Any]] = []
    missing_scores_total = 0
    fallback_due_to_missing_score_count = 0
    selected_candidate_not_in_pool_count = 0
    cache_hit_count = 0
    api_call_count = 0
    skipped: list[dict[str, Any]] = []

    for case in input_cases:
        dataset = _norm(case.get("dataset"))
        example_id = _norm(case.get("example_id"))
        seed = _to_int(case.get("seed"))
        budget = _to_int(case.get("budget"))
        key = (dataset, example_id, seed, budget)
        dr = discovery_index.get(key)
        if dr is None:
            skipped.append(
                {
                    "dataset": dataset,
                    "example_id": example_id,
                    "seed": seed,
                    "budget": budget,
                    "reason": "missing_discovery_record",
                }
            )
            continue

        case_id = f"{dataset}::{example_id}::{seed}::{budget}"
        md = dr.get("result_metadata") or {}
        pool = list(md.get("selector_candidate_pool") or [])
        api_call_count += _to_int(md.get("actions_used", dr.get("total_actions", 0)))

        best_candidate = None
        best_score = float("-inf")
        case_missing_scores = 0
        case_scored = 0
        pool_ids = set()
        score_by_candidate: dict[str, float] = {}
        for c in pool:
            cid = _norm(c.get("candidate_id"))
            pool_ids.add(cid)
            sc = score_map.get((case_id, cid))
            if sc is None:
                case_missing_scores += 1
                continue
            cache_hit_count += 1
            case_scored += 1
            score_by_candidate[cid] = sc
            has_trace = bool(_norm(c.get("trace")))
            if selector_cfg.get("require_trace_for_override", False) and not has_trace:
                continue
            if sc > best_score:
                best_score = sc
                best_candidate = c
        missing_scores_total += case_missing_scores

        old_internal_method_name = _norm(case.get("our_method_name"))
        old_internal_answer = _norm(case.get("our_final_answer"))
        best_external_answer = _norm(case.get("best_external_answer") or case.get("external_l1_max_answer"))
        best_external_correct = _to_int(case.get("best_external_correct", case.get("external_l1_max_correct", 0)))
        gold_answer = _norm(case.get("gold_answer"))

        incumbent = _norm(dr.get("selected_answer_canonical") or dr.get("final_answer_canonical") or old_internal_answer)
        if best_candidate is None:
            selected_answer = incumbent
            fallback_due_to_missing_score = int(len(pool) > 0 and case_missing_scores > 0)
            fallback_due_to_missing_score_count += fallback_due_to_missing_score
            selector_decision_reason = "fallback_to_incumbent_due_to_missing_or_unusable_scores"
            selected_candidate_id = ""
            selected_answer_group = incumbent
            selected_score = ""
        else:
            selected_candidate_id = _norm(best_candidate.get("candidate_id"))
            selected_answer_group = _norm(best_candidate.get("normalized_answer"))
            selected_answer = selected_answer_group or incumbent
            selected_score = best_score
            fallback_due_to_missing_score = 0
            selector_decision_reason = "highest_cached_verifier_score_with_selector_constraints"

        if selected_candidate_id and selected_candidate_id not in pool_ids:
            selected_candidate_not_in_pool_count += 1

        new_correct = int(selected_answer == gold_answer)
        fixed_previous = int(best_external_correct == 1 and new_correct == 1 and _to_int(case.get("our_correct", 0)) == 0)
        still_loses = int(best_external_correct == 1 and new_correct == 0)

        candidate_groups = [_norm(c.get("normalized_answer")) for c in pool if _norm(c.get("normalized_answer"))]
        gold_present_groups = int(any(g == gold_answer for g in candidate_groups))
        trace_availability = int(any(bool(_norm(c.get("trace"))) for c in pool))
        selector_failure_gold_present = _to_int(case.get("selector_failure_gold_present", 1 if (still_loses and gold_present_groups) else 0))
        discovery_failure_gold_absent = _to_int(case.get("discovery_failure_gold_absent", 1 if (still_loses and not gold_present_groups) else 0))

        row = {
            "case_id": _norm(case.get("case_id", case_id)),
            "dataset": dataset,
            "example_id": example_id,
            "seed": seed,
            "budget": budget,
            "problem_statement": _norm(case.get("problem_statement")),
            "gold_answer": gold_answer,
            "best_external_method_name": _norm(case.get("best_external_method_name", "external_l1_max")),
            "best_external_answer": best_external_answer,
            "best_external_correct": best_external_correct,
            "old_internal_method_name": old_internal_method_name,
            "old_internal_answer": old_internal_answer,
            "new_full_pipeline_selected_answer": selected_answer,
            "new_full_pipeline_selected_correct": new_correct,
            "fixed_previous_external_loss_case": fixed_previous,
            "still_loses_to_best_external": still_loses,
            "discovery_method_used": BEST_INTERNAL_METHOD,
            "selector_used": selector_cfg.get("selector_name", "outcome_verifier_answer_group_selector_v1"),
            "selector_decision_reason": selector_decision_reason,
            "selected_answer_group": selected_answer_group,
            "candidate_answer_groups": json.dumps(candidate_groups, ensure_ascii=False),
            "candidate_count": _to_int(case.get("candidate_count", len(pool))),
            "candidate_group_count": _to_int(case.get("candidate_group_count", len(set(candidate_groups)))),
            "trace_availability": trace_availability,
            "gold_present_in_candidate_groups": _to_int(case.get("gold_present_in_candidate_groups", gold_present_groups)),
            "gold_present_in_tree": _to_int(case.get("gold_present_in_tree", gold_present_groups)),
            "selector_failure_gold_present": selector_failure_gold_present,
            "discovery_failure_gold_absent": discovery_failure_gold_absent,
            "rank_of_gold_answer_group_if_present": _norm(case.get("rank_of_gold_answer_group_if_present")),
            "support_gap_selected_minus_gold_if_present": _norm(case.get("support_gap_selected_minus_gold_if_present")),
            "verifier_group_scores": json.dumps(score_by_candidate, ensure_ascii=False),
            "missing_verifier_score_indicators": int(case_missing_scores > 0),
            "fallback_due_to_missing_score": fallback_due_to_missing_score,
            "selected_candidate_not_in_pool": int(bool(selected_candidate_id) and selected_candidate_id not in pool_ids),
            "selected_candidate_id": selected_candidate_id,
            "selected_candidate_score": selected_score,
        }
        row["diagnosis"] = _diagnose(row)
        row["suggested_next_intervention"] = _intervention(row["diagnosis"])
        per_case.append(row)

    still_lost = [r for r in per_case if r["still_loses_to_best_external"] == 1]
    fixed = [r for r in per_case if r["fixed_previous_external_loss_case"] == 1]

    total_cases = len(input_cases)
    evaluated_cases = len(per_case)
    skipped_cases = len(skipped)
    correct_count = sum(r["new_full_pipeline_selected_correct"] for r in per_case)
    wrong_count = evaluated_cases - correct_count
    selector_recoverable_count = sum(_to_int(r["gold_present_in_candidate_groups"]) for r in per_case)
    discovery_failure_count = sum(_to_int(r["discovery_failure_gold_absent"]) for r in per_case)
    gold_present_but_not_selected_count = sum(_to_int(r["selector_failure_gold_present"]) for r in per_case)
    gold_absent_count = sum(1 for r in per_case if _to_int(r["gold_present_in_candidate_groups"]) == 0)

    summary = {
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_cases": total_cases,
        "evaluated_cases": evaluated_cases,
        "skipped_cases": skipped_cases,
        "correct_count": correct_count,
        "wrong_count": wrong_count,
        "accuracy_on_88": (correct_count / max(1, total_cases)),
        "fixed_previous_loss_count": len(fixed),
        "still_lost_count": len(still_lost),
        "fix_rate_on_88": (len(fixed) / max(1, total_cases)),
        "still_loss_rate_on_88": (len(still_lost) / max(1, total_cases)),
        "selector_recoverable_count": selector_recoverable_count,
        "discovery_failure_count": discovery_failure_count,
        "gold_present_but_not_selected_count": gold_present_but_not_selected_count,
        "gold_absent_count": gold_absent_count,
        "missing_score_count": missing_scores_total,
        "fallback_due_to_missing_score_count": fallback_due_to_missing_score_count,
        "selected_candidate_not_in_pool_count": selected_candidate_not_in_pool_count,
        "api_call_count": api_call_count,
        "cache_hit_count": cache_hit_count,
        "skipped_or_unusable_cases": skipped,
    }

    manifest = {
        "run_name": "full_pipeline_best_selector_on_88_external_losses",
        "run_type": args.run_type,
        "selected_full_internal_method": BEST_INTERNAL_METHOD,
        "selected_selector": selector_cfg.get("selector_name"),
        "selector_config_path": str(Path(args.selected_config)),
        "input_cases_csv": str(Path(args.input_cases_csv)),
        "discovery_records_jsonl": str(Path(args.discovery_records_jsonl)),
        "score_cache_path": selector_cfg.get("score_cache_path"),
        "gold_policy": "gold/evaluation-only fields are not used for method decisions; used only for post-prediction evaluation/diagnosis",
    }

    run_config = {
        "selector_config_snapshot": selector_cfg,
        "best_internal_method": BEST_INTERNAL_METHOD,
        "run_type": args.run_type,
    }

    _write_json(out_dir / "manifest.json", manifest)
    _write_json(out_dir / "run_config.json", run_config)
    _write_csv(out_dir / "selected_cases_input_snapshot.csv", input_cases)
    _write_jsonl(out_dir / "per_case_results.jsonl", per_case)
    _write_csv(out_dir / "per_case_results.csv", per_case)
    _write_jsonl(out_dir / "still_lost_cases.jsonl", still_lost)
    _write_csv(out_dir / "still_lost_cases.csv", still_lost)
    _write_jsonl(out_dir / "fixed_cases.jsonl", fixed)
    _write_csv(out_dir / "fixed_cases.csv", fixed)
    _write_json(out_dir / "summary.json", summary)
    _write_csv(out_dir / "summary.csv", [{"metric": k, "value": json.dumps(v) if isinstance(v, (list, dict)) else v} for k, v in summary.items()])

    report = [
        "# Full Pipeline + Best Selector on External-Loss Subset",
        "",
        f"- Run type: `{args.run_type}` (discovery rerun followed by post-hoc selected-selector application).",
        f"- Internal method: `{BEST_INTERNAL_METHOD}`.",
        f"- Selector: `{selector_cfg.get('selector_name')}` (`scorer_mode={selector_cfg.get('scorer_mode')}`).",
        f"- Total cases: {total_cases}, evaluated: {evaluated_cases}, skipped: {skipped_cases}.",
        f"- Accuracy on subset: {summary['accuracy_on_88']:.4f}.",
        f"- Fixed previous external-loss cases: {summary['fixed_previous_loss_count']}.",
        f"- Still lost cases: {summary['still_lost_count']}.",
        "",
        "## Claim Safety",
        "- This run is a selected external-loss subset evaluation, not a broad external-baseline dominance claim.",
        "- Gold is used only after prediction for evaluation/diagnosis.",
    ]
    (out_dir / "summary_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
