#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.answer_grouped_outcome_verifier import CandidateAnswer, CohereOutcomeVerifier
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
    out: list[dict[str, Any]] = []
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        out.append(json.loads(line))
    return out


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
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


def _build_case_id(dataset: str, example_id: str, seed: int, budget: int) -> str:
    return f"{dataset}::{example_id}::{seed}::{budget}"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Complete verifier-score coverage and rerun selected selector on 88-case external-loss subset.")
    p.add_argument("--previous-output-dir", required=True)
    p.add_argument("--selected-cases-csv", required=True)
    p.add_argument("--selected-config", required=True)
    p.add_argument("--discovery-records-jsonl", required=True)
    p.add_argument("--score-completion-output-dir", required=True)
    p.add_argument("--final-output-dir", required=True)
    p.add_argument("--verifier-model", default="command-a-03-2025")
    p.add_argument("--plan-only", action="store_true")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    prev_dir = Path(args.previous_output_dir)
    score_dir = Path(args.score_completion_output_dir)
    final_dir = Path(args.final_output_dir)
    score_dir.mkdir(parents=True, exist_ok=True)
    final_dir.mkdir(parents=True, exist_ok=True)

    selected_cases = _read_csv(Path(args.selected_cases_csv))
    prev_per_case = _read_jsonl(prev_dir / "per_case_results.jsonl")
    prev_per_case_idx = {_norm(r.get("case_id")): r for r in prev_per_case}
    prev_missing_count = sum(_to_int(r.get("missing_verifier_score_indicators", 0)) for r in prev_per_case)
    prev_fallback_count = sum(_to_int(r.get("fallback_due_to_missing_score", 0)) for r in prev_per_case)

    selector_cfg = json.loads(Path(args.selected_config).read_text(encoding="utf-8"))
    base_score_cache = Path(REPO_ROOT / selector_cfg["score_cache_path"])
    base_scores = _read_jsonl(base_score_cache)
    base_score_map = {(_norm(r.get("case_id")), _norm(r.get("candidate_id"))): float(r.get("verifier_score", 0.0)) for r in base_scores}

    discovery_rows = _read_jsonl(Path(args.discovery_records_jsonl))
    discovery_index: dict[tuple[str, str, int, int], dict[str, Any]] = {}
    for r in discovery_rows:
        if _norm(r.get("method")) != BEST_INTERNAL_METHOD:
            continue
        k = (_norm(r.get("dataset")), _norm(r.get("example_id")), _to_int(r.get("seed")), _to_int(r.get("budget")))
        discovery_index[k] = r

    missing_items: list[dict[str, Any]] = []
    missing_keys = set()
    fallback_case_ids: list[str] = []
    invalid_plan_items = 0
    for c in selected_cases:
        dataset = _norm(c.get("dataset"))
        example_id = _norm(c.get("example_id"))
        seed = _to_int(c.get("seed"))
        budget = _to_int(c.get("budget"))
        case_id = _norm(c.get("case_id")) or _build_case_id(dataset, example_id, seed, budget)
        d = discovery_index.get((dataset, example_id, seed, budget))
        if d is None:
            continue
        pool = ((d.get("result_metadata") or {}).get("selector_candidate_pool") or [])
        case_had_missing = False
        for i, cand in enumerate(pool):
            cid = _norm(cand.get("candidate_id")) or f"cand_{i}"
            key = (case_id, cid)
            if key in base_score_map or key in missing_keys:
                continue
            item = {
                "case_id": case_id,
                "dataset": dataset,
                "example_id": example_id,
                "seed": seed,
                "budget": budget,
                "candidate_id": cid,
                "problem_statement": _norm(cand.get("problem_statement")) or _norm(c.get("problem_statement")) or _norm(d.get("question")),
                "final_answer": _norm(cand.get("predicted_answer")) or _norm(cand.get("normalized_answer")),
                "normalized_answer": _norm(cand.get("normalized_answer")),
                "trace_text": _norm(cand.get("trace")),
                "source_family": _norm(cand.get("source_family")),
            }
            if not item["problem_statement"] or not item["final_answer"] or not item["trace_text"]:
                item["missing_required_fields"] = True
                invalid_plan_items += 1
            else:
                item["missing_required_fields"] = False
            missing_items.append(item)
            missing_keys.add(key)
            case_had_missing = True
        if case_had_missing:
            fallback_case_ids.append(case_id)

    call_plan_path = score_dir / "missing_score_call_plan.jsonl"
    _write_jsonl(call_plan_path, missing_items)
    call_plan_summary = {
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_missing_items_to_score": len(missing_items),
        "unique_case_count": len(set(_norm(x["case_id"]) for x in missing_items)),
        "expected_api_calls": len(missing_items),
        "scorer_backend": "cohere",
        "scorer_model": args.verifier_model,
        "input_source_paths": {
            "selected_cases_csv": str(Path(args.selected_cases_csv)),
            "discovery_records_jsonl": str(Path(args.discovery_records_jsonl)),
            "base_score_cache": str(base_score_cache),
        },
        "previous_output_dir": str(prev_dir),
        "items_missing_required_fields": invalid_plan_items,
        "previous_missing_score_count": prev_missing_count,
        "previous_fallback_due_to_missing_score_count": prev_fallback_count,
        "fallback_case_count_previous": len(set(fallback_case_ids)),
    }
    _write_json(score_dir / "missing_score_call_plan_summary.json", call_plan_summary)

    if args.plan_only:
        print(json.dumps(call_plan_summary, indent=2))
        return 0

    verifier = CohereOutcomeVerifier(model=args.verifier_model)
    new_scores: list[dict[str, Any]] = []
    parse_error_count = 0
    api_error_count = 0
    for item in missing_items:
        if item["missing_required_fields"]:
            continue
        cand = CandidateAnswer(
            candidate_id=item["candidate_id"],
            problem=item["problem_statement"],
            trace=item["trace_text"],
            final_answer=item["final_answer"],
            normalized_answer=item["normalized_answer"] or None,
            source_id=item["source_family"] or None,
            source_prior=0.5,
            cost_norm=0.0,
        )
        vr = verifier.verify(cand)
        if "cohere_json_parse_failed" in vr.short_reason:
            parse_error_count += 1
        if "cohere_verify_error:" in vr.short_reason:
            api_error_count += 1
        new_scores.append(
            {
                "case_id": item["case_id"],
                "candidate_id": item["candidate_id"],
                "verifier_score": vr.prob_correct,
                "verifier_backend": "cohere",
                "verifier_model": args.verifier_model,
                "short_reason": vr.short_reason,
            }
        )

    _write_jsonl(final_dir / "new_verifier_scores_only.jsonl", new_scores)

    merged = list(base_scores)
    merged_map = dict(base_score_map)
    duplicate_score_count = 0
    duplicate_conflict_count = 0
    for r in new_scores:
        k = (_norm(r["case_id"]), _norm(r["candidate_id"]))
        if k in merged_map:
            duplicate_score_count += 1
            if float(merged_map[k]) != float(r["verifier_score"]):
                duplicate_conflict_count += 1
            continue
        merged_map[k] = float(r["verifier_score"])
        merged.append(r)
    _write_jsonl(final_dir / "completed_verifier_scores.jsonl", merged)

    still_missing_after_merge = 0
    per_case: list[dict[str, Any]] = []
    still_lost: list[dict[str, Any]] = []
    fixed: list[dict[str, Any]] = []
    selected_candidate_not_in_pool_count = 0
    fallback_due_to_missing = 0
    cache_hit_count = 0

    for c in selected_cases:
        dataset = _norm(c.get("dataset"))
        example_id = _norm(c.get("example_id"))
        seed = _to_int(c.get("seed"))
        budget = _to_int(c.get("budget"))
        case_id = _norm(c.get("case_id")) or _build_case_id(dataset, example_id, seed, budget)
        d = discovery_index.get((dataset, example_id, seed, budget))
        if d is None:
            continue
        pool = ((d.get("result_metadata") or {}).get("selector_candidate_pool") or [])
        best = None
        best_score = float("-inf")
        score_map_case: dict[str, float] = {}
        case_missing = 0
        for i, cand in enumerate(pool):
            cid = _norm(cand.get("candidate_id")) or f"cand_{i}"
            sc = merged_map.get((case_id, cid))
            if sc is None:
                case_missing += 1
                continue
            cache_hit_count += 1
            score_map_case[cid] = float(sc)
            if selector_cfg.get("require_trace_for_override", True) and not _norm(cand.get("trace")):
                continue
            if float(sc) > best_score:
                best_score = float(sc)
                best = cand
        still_missing_after_merge += case_missing

        old = prev_per_case_idx.get(case_id, {})
        incumbent = _norm(d.get("selected_answer_canonical") or d.get("final_answer_canonical") or old.get("old_internal_answer"))
        if best is None:
            selected_answer = incumbent
            selected_answer_group = incumbent
            selected_candidate_id = ""
            selected_candidate_score = ""
            decision_reason = "fallback_to_incumbent_due_to_missing_or_unusable_scores"
            fallback = int(len(pool) > 0 and case_missing > 0)
            fallback_due_to_missing += fallback
        else:
            selected_answer_group = _norm(best.get("normalized_answer")) or incumbent
            selected_answer = selected_answer_group
            selected_candidate_id = _norm(best.get("candidate_id"))
            selected_candidate_score = best_score
            decision_reason = "highest_cached_verifier_score_with_selector_constraints"
            fallback = 0
        pool_ids = {_norm(x.get("candidate_id")) for x in pool}
        sel_not_pool = int(bool(selected_candidate_id) and selected_candidate_id not in pool_ids)
        selected_candidate_not_in_pool_count += sel_not_pool

        gold = _norm(c.get("gold_answer"))
        best_external_correct = _to_int(c.get("best_external_correct", c.get("external_l1_max_correct", 0)))
        new_correct = int(selected_answer == gold)
        fixed_prev_loss = int(best_external_correct == 1 and new_correct == 1 and _to_int(c.get("our_correct", 0)) == 0)
        still_loses = int(best_external_correct == 1 and new_correct == 0)
        candidate_groups = [_norm(x.get("normalized_answer")) for x in pool if _norm(x.get("normalized_answer"))]
        gold_present = int(any(x == gold for x in candidate_groups))
        row = {
            "case_id": case_id,
            "dataset": dataset,
            "example_id": example_id,
            "seed": seed,
            "budget": budget,
            "problem_statement": _norm(c.get("problem_statement")),
            "gold_answer": gold,
            "best_external_method_name": _norm(c.get("best_external_method_name", "external_l1_max")),
            "best_external_answer": _norm(c.get("best_external_answer") or c.get("external_l1_max_answer")),
            "best_external_correct": best_external_correct,
            "old_internal_method_name": _norm(c.get("our_method_name")),
            "old_internal_answer": _norm(c.get("our_final_answer")),
            "previous_selected_answer": _norm(old.get("new_full_pipeline_selected_answer")),
            "previous_selector_decision_reason": _norm(old.get("selector_decision_reason")),
            "new_full_pipeline_selected_answer": selected_answer,
            "new_full_pipeline_selected_correct": new_correct,
            "fixed_previous_external_loss_case": fixed_prev_loss,
            "still_loses_to_best_external": still_loses,
            "discovery_method_used": BEST_INTERNAL_METHOD,
            "selector_used": selector_cfg.get("selector_name"),
            "selector_decision_reason": decision_reason,
            "selected_answer_group": selected_answer_group,
            "candidate_answer_groups": json.dumps(candidate_groups, ensure_ascii=False),
            "candidate_count": _to_int(c.get("candidate_count", len(pool))),
            "candidate_group_count": _to_int(c.get("candidate_group_count", len(set(candidate_groups)))),
            "trace_availability": int(any(_norm(x.get("trace")) for x in pool)),
            "gold_present_in_candidate_groups": _to_int(c.get("gold_present_in_candidate_groups", gold_present)),
            "gold_present_in_tree": _to_int(c.get("gold_present_in_tree", gold_present)),
            "selector_failure_gold_present": _to_int(c.get("selector_failure_gold_present", int(still_loses and gold_present))),
            "discovery_failure_gold_absent": _to_int(c.get("discovery_failure_gold_absent", int(still_loses and not gold_present))),
            "rank_of_gold_answer_group_if_present": _norm(c.get("rank_of_gold_answer_group_if_present")),
            "support_gap_selected_minus_gold_if_present": _norm(c.get("support_gap_selected_minus_gold_if_present")),
            "verifier_group_scores": json.dumps(score_map_case, ensure_ascii=False),
            "missing_verifier_score_indicators": int(case_missing > 0),
            "fallback_due_to_missing_score": fallback,
            "selected_candidate_not_in_pool": sel_not_pool,
            "selected_candidate_id": selected_candidate_id,
            "selected_candidate_score": selected_candidate_score,
            "change_caused_by_new_verifier_scores": int(_norm(old.get("new_full_pipeline_selected_answer")) != selected_answer),
        }
        if still_loses and row["selector_failure_gold_present"] == 1:
            row["diagnosis"] = "selector failure"
            row["suggested_next_intervention"] = "improve answer-group score calibration / tie-breaks"
        elif still_loses and row["discovery_failure_gold_absent"] == 1:
            row["diagnosis"] = "discovery failure"
            row["suggested_next_intervention"] = "improve candidate generation/frontier coverage"
        elif still_loses and row["trace_availability"] == 0:
            row["diagnosis"] = "trace missing"
            row["suggested_next_intervention"] = "rerun with trace-preserving candidates"
        elif still_loses and row["missing_verifier_score_indicators"] == 1:
            row["diagnosis"] = "parse/API issue"
            row["suggested_next_intervention"] = "resolve verifier scoring errors and rerun"
        elif fixed_prev_loss:
            row["diagnosis"] = "fixed"
            row["suggested_next_intervention"] = "none"
        elif best_external_correct == 0:
            row["diagnosis"] = "external also wrong"
            row["suggested_next_intervention"] = "manual review"
        else:
            row["diagnosis"] = "unknown"
            row["suggested_next_intervention"] = "manual triage"

        per_case.append(row)
        if row["still_loses_to_best_external"] == 1:
            still_lost.append(row)
        if row["fixed_previous_external_loss_case"] == 1:
            fixed.append(row)

    total_cases = len(selected_cases)
    evaluated_cases = len(per_case)
    correct_count = sum(_to_int(r["new_full_pipeline_selected_correct"]) for r in per_case)
    wrong_count = evaluated_cases - correct_count
    selector_recoverable_count = sum(_to_int(r["gold_present_in_candidate_groups"]) for r in per_case)
    discovery_failure_count = sum(_to_int(r["discovery_failure_gold_absent"]) for r in per_case)
    summary = {
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_cases": total_cases,
        "evaluated_cases": evaluated_cases,
        "skipped_cases": total_cases - evaluated_cases,
        "correct_count": correct_count,
        "wrong_count": wrong_count,
        "accuracy_on_88": correct_count / max(1, total_cases),
        "fixed_previous_loss_count": len(fixed),
        "still_lost_count": len(still_lost),
        "fix_rate_on_88": len(fixed) / max(1, total_cases),
        "still_loss_rate_on_88": len(still_lost) / max(1, total_cases),
        "selector_recoverable_count": selector_recoverable_count,
        "discovery_failure_count": discovery_failure_count,
        "gold_present_but_not_selected_count": sum(_to_int(r["selector_failure_gold_present"]) for r in per_case),
        "gold_absent_count": sum(1 for r in per_case if _to_int(r["gold_present_in_candidate_groups"]) == 0),
        "missing_score_count": still_missing_after_merge,
        "fallback_due_to_missing_score_count": fallback_due_to_missing,
        "selected_candidate_not_in_pool_count": selected_candidate_not_in_pool_count,
        "previous_missing_score_count": prev_missing_count,
        "previous_fallback_due_to_missing_score_count": prev_fallback_count,
        "new_scores_added_count": len(new_scores),
        "expected_api_calls": len(missing_items),
        "actual_api_calls": len([x for x in missing_items if not x["missing_required_fields"]]),
        "cache_hit_count": cache_hit_count,
        "api_error_count": api_error_count,
        "parse_error_count": parse_error_count,
    }

    score_merge_report = {
        "previous_score_count": len(base_scores),
        "new_score_count": len(new_scores),
        "duplicate_score_count": duplicate_score_count,
        "total_completed_score_count": len(merged),
        "missing_after_merge_count": still_missing_after_merge,
        "parse_error_count": parse_error_count,
        "api_error_count": api_error_count,
        "duplicate_conflict_count": duplicate_conflict_count,
    }

    _write_json(final_dir / "score_merge_report.json", score_merge_report)
    (final_dir / "score_merge_report.md").write_text(
        "\n".join(
            [
                "# Score Merge Report",
                "",
                *[f"- {k}: {v}" for k, v in score_merge_report.items()],
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    comparison_rows = []
    newly_fixed = 0
    became_wrong = 0
    unchanged = 0
    for r in per_case:
        cid = _norm(r["case_id"])
        old = prev_per_case_idx.get(cid, {})
        old_correct = _to_int(old.get("new_full_pipeline_selected_correct", 0))
        new_correct = _to_int(r["new_full_pipeline_selected_correct"])
        if old_correct == 0 and new_correct == 1:
            newly_fixed += 1
        elif old_correct == 1 and new_correct == 0:
            became_wrong += 1
        else:
            unchanged += 1
        comparison_rows.append(
            {
                "case_id": cid,
                "previous_selected_answer": _norm(old.get("new_full_pipeline_selected_answer")),
                "new_selected_answer": _norm(r.get("new_full_pipeline_selected_answer")),
                "previous_decision_reason": _norm(old.get("selector_decision_reason")),
                "new_decision_reason": _norm(r.get("selector_decision_reason")),
                "changed": int(_norm(old.get("new_full_pipeline_selected_answer")) != _norm(r.get("new_full_pipeline_selected_answer"))),
                "change_caused_by_now_available_verifier_scores": _to_int(r["change_caused_by_new_verifier_scores"]),
            }
        )
    comparison = {
        "previous_correct_count": sum(_to_int(x.get("new_full_pipeline_selected_correct", 0)) for x in prev_per_case),
        "new_correct_count": correct_count,
        "previous_still_lost_count": sum(_to_int(x.get("still_loses_to_best_external", 0)) for x in prev_per_case),
        "new_still_lost_count": len(still_lost),
        "cases_newly_fixed_after_score_completion": newly_fixed,
        "cases_became_wrong_after_score_completion": became_wrong,
        "cases_unchanged": unchanged,
    }
    _write_json(final_dir / "comparison_vs_previous_run.json", comparison)
    (final_dir / "comparison_vs_previous_run.md").write_text(
        "\n".join(
            [
                "# Comparison vs Previous Run",
                "",
                *[f"- {k}: {v}" for k, v in comparison.items()],
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    manifest = {
        "run_name": "full_score_completed_best_selector_on_88_external_losses",
        "selected_full_internal_method": BEST_INTERNAL_METHOD,
        "selected_selector": selector_cfg.get("selector_name"),
        "selected_config_path": str(Path(args.selected_config)),
        "previous_output_dir": str(prev_dir),
        "score_completion_output_dir": str(score_dir),
        "run_type": "B",
    }
    run_config = {
        "selector_config_snapshot": selector_cfg,
        "verifier_backend": "cohere",
        "verifier_model": args.verifier_model,
        "expected_api_calls": len(missing_items),
    }

    _write_json(final_dir / "manifest.json", manifest)
    _write_json(final_dir / "run_config.json", run_config)
    _write_csv(final_dir / "selected_cases_input_snapshot.csv", selected_cases)
    _write_jsonl(final_dir / "per_case_results.jsonl", per_case)
    _write_csv(final_dir / "per_case_results.csv", per_case)
    _write_jsonl(final_dir / "still_lost_cases.jsonl", still_lost)
    _write_csv(final_dir / "still_lost_cases.csv", still_lost)
    _write_jsonl(final_dir / "fixed_cases.jsonl", fixed)
    _write_csv(final_dir / "fixed_cases.csv", fixed)
    _write_json(final_dir / "summary.json", summary)
    _write_csv(final_dir / "summary.csv", [{"metric": k, "value": json.dumps(v) if isinstance(v, (list, dict)) else v} for k, v in summary.items()])
    (final_dir / "summary_report.md").write_text(
        "\n".join(
            [
                "# Full Score-Completed Selector Rerun",
                "",
                f"- Total cases: {summary['total_cases']}",
                f"- Correct: {summary['correct_count']}",
                f"- Wrong: {summary['wrong_count']}",
                f"- Missing scores after merge: {summary['missing_score_count']}",
                f"- Fallback due to missing score: {summary['fallback_due_to_missing_score_count']}",
                f"- Selected candidate not in pool: {summary['selected_candidate_not_in_pool_count']}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    # requested also in score-completion output dir
    _write_jsonl(score_dir / "new_verifier_scores_only.jsonl", new_scores)
    _write_jsonl(score_dir / "completed_verifier_scores.jsonl", merged)
    _write_json(score_dir / "score_merge_report.json", score_merge_report)
    (score_dir / "score_merge_report.md").write_text((final_dir / "score_merge_report.md").read_text(encoding="utf-8"), encoding="utf-8")

    print(json.dumps({"expected_api_calls": len(missing_items), "missing_after_merge_count": still_missing_after_merge}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
