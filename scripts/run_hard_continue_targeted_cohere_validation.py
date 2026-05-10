#!/usr/bin/env python3
"""Targeted Cohere validation for the hard-continue extraction guard.

Small, case-allowlisted runner for the 12 known GSM8K final_target_mismatch /
parse-format cases. It emits only validation artifacts and enforces a logical API
call cap through APIBranchGenerator.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.branching import APIBranchGenerator, configure_logical_api_call_budget, logical_api_call_budget_snapshot
from experiments.data import normalize_answer_text
from experiments.frontier_matrix_core import (
    build_frontier_strategies,
    generator_factory_for_mode,
)
from experiments.output_layer_repair import canonicalize_answer

CASE_IDS = [
    "openai_gsm8k_1177",
    "openai_gsm8k_1180",
    "openai_gsm8k_1218",
    "openai_gsm8k_30",
    "openai_gsm8k_59",
    "openai_gsm8k_62",
    "openai_gsm8k_217",
    "openai_gsm8k_245",
    "openai_gsm8k_358",
    "openai_gsm8k_1285",
    "openai_gsm8k_228",
    "openai_gsm8k_337",
]
PRIMARY_IDS = set(CASE_IDS[:9])
DEFAULT_METHOD = "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal"
DEFAULT_POOL = "outputs/fresh_gsm8k_direct_reserve_scorer_plan_20260426T_FRESH_GSM8K_SCORER_VALIDATION/fresh_candidate_pool.csv"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Targeted hard-continue Cohere validation")
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    p.add_argument("--output-root", default="outputs")
    p.add_argument("--case-pool", default=DEFAULT_POOL)
    p.add_argument("--method", default=DEFAULT_METHOD)
    p.add_argument("--budget", type=int, default=6)
    p.add_argument("--seed", type=int, default=11)
    p.add_argument("--cohere-model", default="command-r-plus-08-2024")
    p.add_argument("--temperature", type=float, default=0.1)
    p.add_argument("--max-output-tokens", type=int, default=220)
    p.add_argument("--timeout-seconds", type=int, default=45)
    p.add_argument("--max-total-api-calls", type=int, default=120)
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args()


def norm_answer(raw: Any, *, dataset: str = "openai/gsm8k") -> str:
    txt = str(raw or "").strip()
    if not txt:
        return ""
    try:
        out = canonicalize_answer(txt, dataset=dataset)
        return str(out or "").strip()
    except Exception:
        n = normalize_answer_text(txt).get("normalized_answer")
        return str(n or txt).strip()


def load_cases(path: Path) -> list[dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    with path.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            eid = str(row.get("example_id", "")).strip()
            if eid in CASE_IDS and eid not in rows:
                rows[eid] = row
    missing = [cid for cid in CASE_IDS if cid not in rows]
    if missing:
        raise SystemExit(f"Missing case ids in {path}: {missing}")
    return [rows[cid] for cid in CASE_IDS]


def safe_action_from_response(response_text: str) -> str:
    merged = APIBranchGenerator._merge_wrapped_json_dicts(APIBranchGenerator._safe_json(response_text))
    return str(merged.get("action", "") or "").strip().lower()


def iter_trace_events(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for state in metadata.get("final_branch_states", []) if isinstance(metadata.get("final_branch_states"), list) else []:
        if not isinstance(state, dict):
            continue
        branch_id = str(state.get("branch_id", "") or "")
        state_done = bool(state.get("is_done", False) or state.get("is_terminal", False))
        state_pred = str(state.get("predicted_answer", "") or "")
        for ev in state.get("trace_events", []) if isinstance(state.get("trace_events"), list) else []:
            if isinstance(ev, dict):
                row = dict(ev)
                row.setdefault("branch_id", branch_id)
                row["state_is_done"] = state_done
                row["state_predicted_answer"] = state_pred
                events.append(row)
    for ev in metadata.get("action_trace", []) if isinstance(metadata.get("action_trace"), list) else []:
        if isinstance(ev, dict):
            row = dict(ev)
            row.setdefault("state_is_done", bool(ev.get("is_terminal", False)))
            row.setdefault("state_predicted_answer", str(ev.get("extracted_answer", "") or ""))
            events.append(row)
    return events


def selected_answer_source(metadata: dict[str, Any], final_answer: str) -> str:
    if metadata.get("pal_overlay", {}).get("pal_overlay_applied"):
        return "pal_overlay"
    if metadata.get("unit_track_overlay", {}).get("unit_track_overlay_applied"):
        return "unit_track_overlay"
    if metadata.get("decomp_eq_overlay", {}).get("decomp_eq_overlay_applied"):
        return "decomp_eq_overlay"
    if metadata.get("opcheck_overlay", {}).get("opcheck_overlay_applied"):
        return "opcheck_overlay"
    if metadata.get("frontier_tiebreak_triggered"):
        return "frontier_tiebreak"
    if metadata.get("frontier_override_triggered"):
        return "frontier_override"
    if str(metadata.get("direct_reserve_answer", "") or "").strip() == str(final_answer or "").strip():
        return "direct_reserve"
    return str(metadata.get("override_reason", "") or metadata.get("guarded_action", "") or "unknown")


def classify_failure(*, exact: bool, final_answer: str, gold: str, leakage: bool, metadata: dict[str, Any]) -> str:
    if exact:
        return "correct"
    if leakage:
        return "final_target_mismatch_continue_leakage"
    if not str(final_answer or "").strip():
        return "no_final_answer_or_parse_failure"
    support_counts = metadata.get("answer_group_support_counts", {})
    gold_norm = norm_answer(gold)
    if isinstance(support_counts, dict) and gold_norm and gold_norm not in {norm_answer(k) for k in support_counts}:
        return "gold_absent_or_not_in_answer_groups"
    return "final_target_mismatch_or_selection_error"


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fieldnames})


def main() -> None:
    args = parse_args()
    out_dir = REPO_ROOT / args.output_root / f"hard_continue_targeted_cohere_validation_{args.timestamp}"
    command = " ".join(sys.argv)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "command.sh").write_text(command + "\n", encoding="utf-8")

    cases = load_cases(REPO_ROOT / args.case_pool)
    if args.dry_run:
        print(json.dumps({"out_dir": str(out_dir), "cases": len(cases), "max_total_api_calls": args.max_total_api_calls}, indent=2))
        return

    configure_logical_api_call_budget(args.max_total_api_calls)
    rng = random.Random(args.seed)
    factory = generator_factory_for_mode(
        True,
        rng,
        args.cohere_model,
        args.temperature,
        args.max_output_tokens,
        args.timeout_seconds,
        api_provider="cohere",
    )
    specs = build_frontier_strategies(
        factory,
        args.budget,
        adaptive_min_expand_grid=[1],
        rng=rng,
        use_openai_api=True,
        include_broad_diversity_aggregation_methods=True,
    )
    if args.method not in specs:
        raise SystemExit(f"Method not available: {args.method}")
    controller = specs[args.method]
    setattr(controller, "emit_full_traces", True)

    per_case: list[dict[str, Any]] = []
    leakage_rows: list[dict[str, Any]] = []
    failures = Counter()

    for case in cases:
        case_id = case["example_id"]
        question = case["question"]
        gold = norm_answer(case.get("normalized_gold_answer") or case.get("gold_answer") or case.get("gold_answer_raw"))
        before_calls = logical_api_call_budget_snapshot()["consumed"] or 0
        result = controller.run(question, gold)
        after_calls = logical_api_call_budget_snapshot()["consumed"] or 0
        metadata = dict(result.metadata or {})
        final_answer = norm_answer(result.prediction)
        exact = bool(final_answer and gold and final_answer == gold)
        events = iter_trace_events(metadata)
        continue_events = []
        continue_contributed = False
        for i, ev in enumerate(events):
            response_text = str(ev.get("response_text", "") or "")
            parsed_action = safe_action_from_response(response_text)
            extraction_source = str(
                ev.get("expand_answer_extraction_source", "")
                or ev.get("verify_answer_extraction_source", "")
                or ""
            )
            extracted = str(ev.get("extracted_answer", "") or "").strip()
            state_done = bool(ev.get("is_terminal", False) or parsed_action == "final" or (extracted and parsed_action != "continue"))
            if parsed_action == "continue":
                contributed = bool(final_answer and extracted and norm_answer(extracted) == final_answer)
                continue_contributed = continue_contributed or contributed
                continue_events.append(
                    {
                        "case_id": case_id,
                        "event_index": i,
                        "branch_id": str(ev.get("branch_id", "") or ""),
                        "parsed_action": parsed_action,
                        "extraction_source": extraction_source,
                        "branch_is_done": int(state_done),
                        "predicted_answer": extracted,
                        "selected_final_answer": final_answer,
                        "contributed_final_answer": int(contributed),
                        "response_text_excerpt": response_text[:300].replace("\n", "\\n"),
                    }
                )
        leakage_rows.extend(continue_events)
        source = selected_answer_source(metadata, final_answer)
        family = classify_failure(exact=exact, final_answer=final_answer, gold=gold, leakage=continue_contributed, metadata=metadata)
        failures[family] += 1
        per_case.append(
            {
                "case_id": case_id,
                "case_group": "primary_final_target_mismatch" if case_id in PRIMARY_IDS else "secondary_parse_format",
                "problem_text": question,
                "gold_answer": gold,
                "selected_final_answer": final_answer,
                "exact_correct": int(exact),
                "selected_answer_source": source,
                "continue_response_count": len(continue_events),
                "continue_response_contributed_final_answer": int(continue_contributed),
                "failure_family": family,
                "logical_calls_used": int(after_calls - before_calls),
                "cumulative_logical_calls": int(after_calls),
            }
        )

    summary = {
        "timestamp": args.timestamp,
        "method": args.method,
        "model": args.cohere_model,
        "budget": args.budget,
        "seed": args.seed,
        "case_count": len(per_case),
        "primary_case_count": sum(1 for r in per_case if r["case_group"] == "primary_final_target_mismatch"),
        "secondary_case_count": sum(1 for r in per_case if r["case_group"] == "secondary_parse_format"),
        "exact_correct_count": sum(int(r["exact_correct"]) for r in per_case),
        "accuracy": sum(int(r["exact_correct"]) for r in per_case) / max(1, len(per_case)),
        "continue_response_count": sum(int(r["continue_response_count"]) for r in per_case),
        "continue_leakage_case_count": sum(int(r["continue_response_contributed_final_answer"]) for r in per_case),
        "continue_leakage_event_count": sum(int(r["contributed_final_answer"]) for r in leakage_rows),
        "failure_family_counts": dict(failures),
        "logical_api_call_budget": args.max_total_api_calls,
        "logical_api_calls_consumed": logical_api_call_budget_snapshot()["consumed"],
        "success_no_continue_response_contributed_final_answer": not any(int(r["continue_response_contributed_final_answer"]) for r in per_case),
    }

    per_fields = [
        "case_id",
        "case_group",
        "problem_text",
        "gold_answer",
        "selected_final_answer",
        "exact_correct",
        "selected_answer_source",
        "continue_response_count",
        "continue_response_contributed_final_answer",
        "failure_family",
        "logical_calls_used",
        "cumulative_logical_calls",
    ]
    leak_fields = [
        "case_id",
        "event_index",
        "branch_id",
        "parsed_action",
        "extraction_source",
        "branch_is_done",
        "predicted_answer",
        "selected_final_answer",
        "contributed_final_answer",
        "response_text_excerpt",
    ]
    write_csv(out_dir / "per_case_results.csv", per_case, per_fields)
    write_csv(out_dir / "continue_leakage_audit.csv", leakage_rows, leak_fields)
    (out_dir / "validation_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    metadata = {
        "command": command,
        "case_pool": args.case_pool,
        "case_ids": CASE_IDS,
        "outputs": ["validation_summary.json", "per_case_results.csv", "continue_leakage_audit.csv", "validation_report.md", "command.sh", "run_metadata.json"],
    }
    (out_dir / "run_metadata.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = [
        "# Hard-continue targeted Cohere validation",
        "",
        f"- Method: `{args.method}`",
        f"- Model: `{args.cohere_model}`",
        f"- Cases: {summary['case_count']} ({summary['primary_case_count']} primary, {summary['secondary_case_count']} secondary)",
        f"- Logical calls: {summary['logical_api_calls_consumed']} / {summary['logical_api_call_budget']}",
        f"- Exact: {summary['exact_correct_count']}/{summary['case_count']} = {summary['accuracy']:.3f}",
        f"- Continue responses observed: {summary['continue_response_count']}",
        f"- Continue leakage cases: {summary['continue_leakage_case_count']}",
        f"- Success criterion met: {summary['success_no_continue_response_contributed_final_answer']}",
        "",
        "## Failure families",
    ]
    for k, v in sorted(failures.items()):
        lines.append(f"- `{k}`: {v}")
    lines.extend(["", "## Per-case table", "", "| case_id | exact | selected | gold | source | continue_leak | failure_family |", "|---|---:|---:|---:|---|---:|---|"])
    for r in per_case:
        lines.append(
            f"| {r['case_id']} | {r['exact_correct']} | {r['selected_final_answer']} | {r['gold_answer']} | {r['selected_answer_source']} | {r['continue_response_contributed_final_answer']} | {r['failure_family']} |"
        )
    (out_dir / "validation_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
