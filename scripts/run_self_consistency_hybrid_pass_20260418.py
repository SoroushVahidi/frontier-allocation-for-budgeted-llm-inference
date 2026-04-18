#!/usr/bin/env python3
"""Targeted selective self-consistency hybrid pass.

Bounded design:
- keep continuation value as default expansion signal,
- activate local diversity + answer aggregation only in hard close-call slices,
- use answer support as a bounded commit/selection modifier (not a global replacement).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.data import extract_final_answer  # noqa: E402
from experiments.objective_function_stack import (  # noqa: E402
    BranchSurrogates,
    compute_answer_support,
    compute_commit_quality,
    compute_process_quality,
    compute_target_completion,
    metalevel_expand_commit_decision,
)

NUM_RE = re.compile(r"[-+]?\d*\.?\d+")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_md(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def _nonempty(x: Any) -> str:
    if x is None:
        return ""
    return str(x).strip()


def _final_line(text: str) -> str:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return lines[-1] if lines else ""


def _has_arith(text: str) -> bool:
    has_digit = any(ch.isdigit() for ch in text)
    has_sym = any(sym in text for sym in ["=", "+", "-", "*", "/", ">", "<"])
    return bool(has_digit and has_sym)


def _floatish(x: Any) -> float | None:
    if x is None:
        return None
    s = _nonempty(x)
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _extract_numbers(text: str) -> list[float]:
    vals: list[float] = []
    for m in NUM_RE.findall(text):
        try:
            vals.append(float(m))
        except ValueError:
            continue
    return vals


def _required_operator(question: str) -> str:
    q = question.lower()
    if "how many times" in q or "number of times" in q:
        return "division_to_count"
    if "off from" in q or "difference" in q or "how many more" in q or "how many fewer" in q or "how much more" in q:
        return "difference_from_target"
    if "give away" in q or "gave away" in q:
        return "leftover_complement"
    return "generic"


def _completion_signal(obs_row: dict[str, Any] | None) -> dict[str, Any]:
    if not obs_row:
        return {
            "branch_completion_score": 0.0,
            "branch_answer_evidence_score": 0.0,
            "branch_reasoning_text_raw": "",
            "branch_final_answer_text_raw": None,
            "branch_final_answer_normalized": None,
            "extracted_numbers": [],
            "fallback_reason": "missing_observability_record",
        }

    reasoning = _nonempty(obs_row.get("branch_reasoning_text_raw"))
    branch_text = _nonempty(obs_row.get("branch_text_raw"))
    final_answer = _nonempty(obs_row.get("branch_final_answer_text_raw"))
    normalized = obs_row.get("branch_final_answer_normalized")
    scan = reasoning or branch_text
    tail = _final_line(scan)

    has_final = bool(final_answer)
    has_norm = normalized is not None
    has_cue = any(tok in tail.lower() for tok in ["final answer", "answer is", "therefore", "thus", "hence", "so "])
    has_arith = _has_arith(tail) or _has_arith(reasoning)
    has_terminal_numeric = any(ch.isdigit() for ch in (final_answer or tail))

    completion = min(1.0, (0.45 if has_final else 0.0) + (0.25 if has_norm else 0.0) + (0.20 if has_arith else 0.0) + (0.10 if has_cue else 0.0))
    answer_evidence = min(1.0, (0.60 if has_norm else 0.0) + (0.30 if has_final else 0.0) + (0.10 if has_terminal_numeric else 0.0))

    return {
        "branch_completion_score": float(completion),
        "branch_answer_evidence_score": float(answer_evidence),
        "branch_reasoning_text_raw": reasoning,
        "branch_final_answer_text_raw": obs_row.get("branch_final_answer_text_raw"),
        "branch_final_answer_normalized": obs_row.get("branch_final_answer_normalized"),
        "extracted_numbers": obs_row.get("extracted_numbers") or [],
    }


def _semantic_incompleteness_signal(question: str, branch_sig: dict[str, Any]) -> dict[str, Any]:
    reasoning = _nonempty(branch_sig.get("branch_reasoning_text_raw"))
    final_answer_norm = _floatish(branch_sig.get("branch_final_answer_normalized"))
    if final_answer_norm is None:
        final_answer_norm = _floatish(branch_sig.get("branch_final_answer_text_raw"))
    required = _required_operator(question)

    text = reasoning.lower()
    has_sub = "-" in text or "subtract" in text or "difference" in text
    has_div = "/" in text or "divide" in text or "per" in text or "each" in text
    has_left = "left" in text or "remain" in text
    has_give = "gave" in text or "give away" in text
    has_target_word = any(tok in text for tok in ["off", "target", "times", "sessions", "gave", "give away"])

    numbers = branch_sig.get("extracted_numbers") if isinstance(branch_sig.get("extracted_numbers"), list) else []
    num_list = [float(x) for x in numbers if isinstance(x, (int, float))]
    if not num_list:
        num_list = _extract_numbers(reasoning)

    one_more_needed = False
    if required == "difference_from_target":
        one_more_needed = not has_sub
    elif required == "division_to_count":
        one_more_needed = not has_div
    elif required == "leftover_complement":
        one_more_needed = bool(has_left and not has_sub and not has_give)

    answer_matches_intermediate = False
    if final_answer_norm is not None and num_list:
        rounded = {round(abs(v), 6) for v in num_list}
        answer_matches_intermediate = round(abs(final_answer_norm), 6) in rounded

    trap = bool(one_more_needed and answer_matches_intermediate)

    score = 0.0
    score += 0.50 if one_more_needed else 0.0
    score += 0.20 if (required != "generic" and not has_target_word) else 0.0
    score += 0.30 if trap else 0.0
    score = _clip01(score)

    subtype = "none"
    if required == "difference_from_target" and trap:
        subtype = "subtotal_vs_final_difference"
    elif required == "division_to_count" and trap:
        subtype = "resource_total_vs_action_count"
    elif required == "leftover_complement" and trap:
        subtype = "leftover_vs_given_away"
    elif one_more_needed:
        subtype = "one_more_operator_needed"

    return {
        "required_operator": required,
        "one_more_operator_needed": one_more_needed,
        "answer_matches_intermediate": answer_matches_intermediate,
        "intermediate_trap_flag": trap,
        "target_variable_cue_present": has_target_word,
        "semantic_incompleteness_score": float(score),
        "failure_subtype": subtype,
    }


def _normalize_answer(x: Any) -> str | None:
    if x is None:
        return None
    s = extract_final_answer(str(x))
    return s.strip() if s else None


def _policy_intermediate_trap_aware(rows: list[dict[str, Any]], *, tie_gap: float, max_value_drop: float, incompleteness_trigger: float) -> tuple[str, str, dict[str, Any]]:
    ranked = sorted(rows, key=lambda r: float(r["expected_value_if_branch"]), reverse=True)
    if not ranked:
        return "", "empty_state", {}
    top = ranked[0]
    surrogate_rows = [
        BranchSurrogates(
            branch_id=str(r["branch_id"]),
            continuation_value=float(r["expected_value_if_branch"]),
            process_quality=float(r["process_quality"]),
            target_completion=float(r["target_completion"]),
            semantic_incompleteness=float(r["semantic_incompleteness_score"]),
        )
        for r in rows
    ]
    decision = metalevel_expand_commit_decision(
        surrogate_rows,
        near_tie_gap=float(tie_gap),
        max_value_drop_for_local_override=float(max_value_drop),
        low_completion_trigger=max(0.0, 1.0 - float(incompleteness_trigger)),
    )
    return str(decision.branch_id or top["branch_id"]), decision.rationale, {"action": decision.action}


def _policy_selective_sc_hybrid(
    rows: list[dict[str, Any]],
    *,
    near_tie_gap: float,
    max_value_drop: float,
    low_completion_trigger: float,
    disagreement_trigger: float,
    diversity_top_k: int,
    min_consensus_support: float,
) -> tuple[str, str, dict[str, Any]]:
    ranked = sorted(rows, key=lambda r: float(r["expected_value_if_branch"]), reverse=True)
    if not ranked:
        return "", "empty_state", {}
    top = ranked[0]
    second = ranked[1] if len(ranked) > 1 else ranked[0]

    top_gap = float(top["expected_value_if_branch"] - second["expected_value_if_branch"])
    near_tie = bool(top_gap <= float(near_tie_gap))

    top_completion = float(top["target_completion"])
    low_top_completion = bool(top_completion <= float(low_completion_trigger))

    best_completion = max(rows, key=lambda r: float(r["target_completion"]))
    continuation_completion_disagree = (
        str(best_completion["branch_id"]) != str(top["branch_id"])
        and (float(best_completion["target_completion"]) - float(top["target_completion"])) >= float(disagreement_trigger)
    )

    top_trap = bool(top.get("intermediate_trap_flag"))
    hard_case_active = bool(near_tie or low_top_completion or continuation_completion_disagree or top_trap)

    if not hard_case_active:
        return str(top["branch_id"]), "default_continuation_value", {
            "hard_case_active": False,
            "near_tie": near_tie,
            "low_top_completion": low_top_completion,
            "continuation_completion_disagree": continuation_completion_disagree,
            "top_intermediate_trap": top_trap,
        }

    top_value = float(top["expected_value_if_branch"])
    eligible = [r for r in ranked if (top_value - float(r["expected_value_if_branch"])) <= float(max_value_drop)]
    diversity_set = eligible[: max(1, int(diversity_top_k))]

    answer_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in diversity_set:
        ans = _normalize_answer(r.get("branch_final_answer_normalized") or r.get("branch_final_answer_text_raw"))
        if ans is None:
            continue
        answer_groups[ans].append(r)

    if not answer_groups:
        return str(top["branch_id"]), "hard_case_no_recoverable_answers_default_continuation", {
            "hard_case_active": True,
            "near_tie": near_tie,
            "low_top_completion": low_top_completion,
            "continuation_completion_disagree": continuation_completion_disagree,
            "top_intermediate_trap": top_trap,
            "diversity_branch_count": len(diversity_set),
            "recoverable_answer_groups": 0,
        }

    def _group_stats(items: list[dict[str, Any]]) -> tuple[float, float, float]:
        support_fraction = float(len(items) / max(1, len(diversity_set)))
        weighted_cont = float(mean(float(x["expected_value_if_branch"]) for x in items))
        support_weighted_value = _clip01(weighted_cont / max(1e-8, top_value)) if top_value > 0 else 0.0
        score = compute_answer_support(
            support_fraction=support_fraction,
            support_weighted_value=support_weighted_value,
        )
        return score, support_fraction, weighted_cont

    grouped_scored: list[tuple[str, float, float, float, list[dict[str, Any]]]] = []
    for ans, items in answer_groups.items():
        score, frac, weighted_cont = _group_stats(items)
        grouped_scored.append((ans, score, frac, weighted_cont, items))

    grouped_scored.sort(key=lambda x: (x[1], x[2], x[3]), reverse=True)
    best_answer, best_support_score, best_support_fraction, _, supporters = grouped_scored[0]

    top_answer = _normalize_answer(top.get("branch_final_answer_normalized") or top.get("branch_final_answer_text_raw"))
    consensus_ready = bool(best_support_score >= float(min_consensus_support))
    consensus_disagrees_top = bool(top_answer is None or best_answer != top_answer)

    if consensus_ready and consensus_disagrees_top:
        selected = max(
            supporters,
            key=lambda r: (
                float(r["expected_value_if_branch"]),
                float(r["target_completion"]),
                float(r["process_quality"]),
            ),
        )
        return str(selected["branch_id"]), "hard_case_selective_sc_consensus_override", {
            "hard_case_active": True,
            "near_tie": near_tie,
            "low_top_completion": low_top_completion,
            "continuation_completion_disagree": continuation_completion_disagree,
            "top_intermediate_trap": top_trap,
            "diversity_branch_count": len(diversity_set),
            "recoverable_answer_groups": len(answer_groups),
            "top_answer": top_answer,
            "consensus_answer": best_answer,
            "consensus_support_score": float(best_support_score),
            "consensus_support_fraction": float(best_support_fraction),
        }

    return str(top["branch_id"]), "hard_case_consensus_insufficient_keep_continuation", {
        "hard_case_active": True,
        "near_tie": near_tie,
        "low_top_completion": low_top_completion,
        "continuation_completion_disagree": continuation_completion_disagree,
        "top_intermediate_trap": top_trap,
        "diversity_branch_count": len(diversity_set),
        "recoverable_answer_groups": len(answer_groups),
        "top_answer": top_answer,
        "best_consensus_answer": best_answer,
        "consensus_support_score": float(best_support_score),
        "consensus_support_fraction": float(best_support_fraction),
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run selective self-consistency-inspired hybrid pass")
    p.add_argument("--run-id", required=True)
    p.add_argument("--frontier-dir", default="")
    p.add_argument("--observability-dir", default="")
    p.add_argument("--sc-casebook-json", default="outputs/self_consistency_advantage_casebook_20260418/rich_case_records.json")
    p.add_argument("--sc-taxonomy-json", default="outputs/self_consistency_advantage_casebook_20260418/self_consistency_advantage_taxonomy.json")
    p.add_argument("--failure-casebook-json", default="outputs/branch_label_bruteforce_learning/worst_real_failure_casebook_with_reasoning_20260418/rich_failure_cases_structured.json")
    p.add_argument("--intermediate-fix-summary", default="outputs/intermediate_result_failure_fix_20260418/aggregate_comparison_summary.json")
    p.add_argument("--full-comparison-summary", default="outputs/branch_label_bruteforce_learning/completion_aware_decision_eval_20260418/aggregate_comparison_summary.json")
    p.add_argument("--output-dir", default="outputs/self_consistency_hybrid_pass_20260418")

    p.add_argument("--near-tie-gap", type=float, default=0.03)
    p.add_argument("--max-value-drop", type=float, default=0.03)
    p.add_argument("--low-completion-trigger", type=float, default=0.45)
    p.add_argument("--disagreement-trigger", type=float, default=0.12)
    p.add_argument("--diversity-top-k", type=int, default=3)
    p.add_argument("--min-consensus-support", type=float, default=0.56)
    return p.parse_args()


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    regrets = [float(r["oracle_regret"]) for r in rows]
    recoverable = [r for r in rows if r.get("recoverable_correct") is not None]
    hard_cases = [r for r in rows if bool(r.get("hard_case_active"))]
    overrides = [r for r in rows if bool(r.get("consensus_override"))]
    trap_slice = [r for r in rows if bool(r.get("chosen_intermediate_trap_flag"))]
    near_tie_rows = [r for r in rows if r.get("hard_slice") == "near_tie"]

    return {
        "states": len(rows),
        "match_oracle_rate": float(sum(int(bool(r["match_oracle"])) for r in rows) / len(rows)) if rows else 0.0,
        "mean_oracle_regret": float(mean(regrets)) if regrets else 0.0,
        "recoverable_answer_accuracy": float(sum(int(bool(r["recoverable_correct"])) for r in recoverable) / len(recoverable)) if recoverable else None,
        "recoverable_n": len(recoverable),
        "hard_case_activation_rate": float(len(hard_cases) / len(rows)) if rows else 0.0,
        "consensus_override_rate": float(len(overrides) / len(rows)) if rows else 0.0,
        "near_tie_match_oracle_rate": float(sum(int(bool(r["match_oracle"])) for r in near_tie_rows) / len(near_tie_rows)) if near_tie_rows else 0.0,
        "intermediate_trap_selected_rate": float(sum(int(bool(r["chosen_intermediate_trap_flag"])) for r in rows) / len(rows)) if rows else 0.0,
        "trap_slice_mean_oracle_regret": float(mean([float(r["oracle_regret"]) for r in trap_slice])) if trap_slice else 0.0,
    }


def main() -> None:
    args = parse_args()
    frontier_dir = Path(args.frontier_dir) if args.frontier_dir else REPO_ROOT / "outputs/frontier_target_construction" / args.run_id
    observability_dir = Path(args.observability_dir) if args.observability_dir else REPO_ROOT / "outputs/branch_observability" / args.run_id
    out_dir = REPO_ROOT / args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    util_rows = _read_jsonl(frontier_dir / "branch_marginal_utility.jsonl")
    trace_rows = _read_jsonl(frontier_dir / "real_trace_input.jsonl")
    obs_rows = _read_jsonl(observability_dir / "branch_trace_records.jsonl")

    sc_casebook = _read_json(REPO_ROOT / args.sc_casebook_json)
    sc_taxonomy = _read_json(REPO_ROOT / args.sc_taxonomy_json)
    worst_casebook = _read_json(REPO_ROOT / args.failure_casebook_json)

    trace_by_pair = {(int(r.get("episode_id", 0)), int(r.get("decision_id", 0))): r for r in trace_rows}
    states: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in util_rows:
        states[str(r.get("state_id", ""))].append(r)

    obs_map = {(str(r.get("state_id")), str(r.get("branch_id"))): r for r in obs_rows}

    gt_by_state: dict[str, str | None] = {}
    q_by_state: dict[str, str] = {}
    method_by_state: dict[str, str] = {}
    branch_rows_by_state: dict[str, list[dict[str, Any]]] = {}
    subtype_counter: Counter[str] = Counter()

    for sid, rows in states.items():
        any_row = rows[0]
        key = (int(any_row.get("episode_id", 0)), int(any_row.get("decision_id", 0)))
        tr = trace_by_pair.get(key, {})
        q = str(tr.get("question", ""))
        q_by_state[sid] = q
        method_by_state[sid] = str(tr.get("method_chosen_branch_id", ""))
        gt_by_state[sid] = extract_final_answer(str(tr.get("answer", ""))) if tr.get("answer") is not None else None

        enhanced_rows: list[dict[str, Any]] = []
        for r in rows:
            bid = str(r.get("branch_id", ""))
            cs = _completion_signal(obs_map.get((sid, bid)))
            sem = _semantic_incompleteness_signal(q, cs)

            process_quality = compute_process_quality(
                completion_score=float(cs.get("branch_completion_score", 0.0)),
                answer_evidence_score=float(cs.get("branch_answer_evidence_score", 0.0)),
                semantic_incompleteness=float(sem.get("semantic_incompleteness_score", 0.0)),
            )
            target_completion = compute_target_completion(
                completion_score=float(cs.get("branch_completion_score", 0.0)),
                answer_evidence_score=float(cs.get("branch_answer_evidence_score", 0.0)),
                semantic_incompleteness=float(sem.get("semantic_incompleteness_score", 0.0)),
            )
            commit_quality = compute_commit_quality(
                process_quality=float(process_quality),
                target_completion=float(target_completion),
            )
            merged = {
                "state_id": sid,
                "branch_id": bid,
                "expected_value_if_branch": float(r.get("expected_value_if_branch", 0.0)),
                "delta_u_vs_outside": float(r.get("delta_u_vs_outside", 0.0)),
                **cs,
                **sem,
                "process_quality": float(process_quality),
                "target_completion": float(target_completion),
                "continuation_value": float(r.get("expected_value_if_branch", 0.0)),
                "commit_quality_score": float(commit_quality),
            }
            subtype_counter.update([str(sem.get("failure_subtype", "none"))])
            enhanced_rows.append(merged)
        branch_rows_by_state[sid] = enhanced_rows

    policies = {
        "continuation_oracle": lambda srows, sid=None: (
            str(max(srows, key=lambda r: float(r["expected_value_if_branch"]))["branch_id"]),
            "oracle_reference",
            {},
        ),
        "current_learned_branch_score": lambda srows, sid=None: (
            str(method_by_state.get(str(sid), "") or max(srows, key=lambda r: float(r["expected_value_if_branch"]))["branch_id"]),
            "current_method_trace_choice",
            {},
        ),
        "intermediate_trap_aware_near_tie_v1": lambda srows, sid=None: _policy_intermediate_trap_aware(
            srows,
            tie_gap=float(args.near_tie_gap),
            max_value_drop=float(args.max_value_drop),
            incompleteness_trigger=float(args.low_completion_trigger),
        ),
        "selective_sc_hybrid_v1": lambda srows, sid=None: _policy_selective_sc_hybrid(
            srows,
            near_tie_gap=float(args.near_tie_gap),
            max_value_drop=float(args.max_value_drop),
            low_completion_trigger=float(args.low_completion_trigger),
            disagreement_trigger=float(args.disagreement_trigger),
            diversity_top_k=int(args.diversity_top_k),
            min_consensus_support=float(args.min_consensus_support),
        ),
    }

    per_policy_rows: dict[str, list[dict[str, Any]]] = {k: [] for k in policies}
    for sid, srows in sorted(branch_rows_by_state.items()):
        if len(srows) < 2:
            continue
        sorted_v = sorted(srows, key=lambda r: float(r["expected_value_if_branch"]), reverse=True)
        top2_gap = float(sorted_v[0]["expected_value_if_branch"] - sorted_v[1]["expected_value_if_branch"])
        hard_slice = "near_tie" if top2_gap <= float(args.near_tie_gap) else "strict"
        oracle_bid = str(sorted_v[0]["branch_id"])
        oracle_value = float(sorted_v[0]["expected_value_if_branch"])
        by_bid = {str(r["branch_id"]): r for r in srows}

        for pname, fn in policies.items():
            bid, rationale, extra = fn(srows, sid)
            bid = str(bid or oracle_bid)
            chosen = by_bid.get(bid, by_bid[oracle_bid])

            gt = gt_by_state.get(sid)
            predicted_norm = _normalize_answer(chosen.get("branch_final_answer_normalized") or chosen.get("branch_final_answer_text_raw"))
            correct = None
            if gt is not None and predicted_norm is not None:
                correct = bool(str(predicted_norm) == str(gt))

            row = {
                "state_id": sid,
                "policy": pname,
                "chosen_branch": bid,
                "oracle_branch": oracle_bid,
                "match_oracle": bool(bid == oracle_bid),
                "oracle_regret": float(oracle_value - float(chosen["expected_value_if_branch"])),
                "hard_slice": hard_slice,
                "top2_gap": top2_gap,
                "question": q_by_state.get(sid, ""),
                "chosen_expected_value": float(chosen["expected_value_if_branch"]),
                "chosen_commit_quality_score": float(chosen["commit_quality_score"]),
                "chosen_semantic_incompleteness_score": float(chosen["semantic_incompleteness_score"]),
                "chosen_intermediate_trap_flag": bool(chosen["intermediate_trap_flag"]),
                "chosen_failure_subtype": chosen["failure_subtype"],
                "ground_truth_normalized": gt,
                "chosen_branch_normalized_answer": predicted_norm,
                "recoverable_correct": correct,
                "decision_rationale": rationale,
                "hard_case_active": bool(extra.get("hard_case_active", False)),
                "consensus_override": bool(rationale == "hard_case_selective_sc_consensus_override"),
                "consensus_support_score": float(extra.get("consensus_support_score", 0.0)),
                "consensus_support_fraction": float(extra.get("consensus_support_fraction", 0.0)),
                "diversity_branch_count": int(extra.get("diversity_branch_count", 0)),
            }
            per_policy_rows[pname].append(row)

    aggregate = {p: _summary(rows) for p, rows in per_policy_rows.items()}

    # Targeted evaluation slices.
    near_tie_rows = {p: [r for r in rows if r["hard_slice"] == "near_tie"] for p, rows in per_policy_rows.items()}
    trap_rows = {
        p: [r for r in rows if (r["chosen_failure_subtype"] != "none" or bool(r["chosen_intermediate_trap_flag"]))]
        for p, rows in per_policy_rows.items()
    }

    sc_case_records = sc_casebook.get("rows") or sc_casebook.get("rich_case_records") or []
    if not sc_case_records and isinstance(sc_casebook, list):
        sc_case_records = sc_casebook
    sc_reason_counter: Counter[str] = Counter()
    for rec in sc_case_records:
        tags = (rec.get("failure_analysis") or {}).get("our_method_failure_tags") or []
        if not tags:
            tags = ((rec.get("failure_analysis") or {}).get("failure_tags") or rec.get("failure_tags") or rec.get("failure_taxonomy_tags") or [])
        for t in tags:
            sc_reason_counter.update([str(t)])

    sc_tax = sc_taxonomy.get("taxonomy") or sc_taxonomy

    targeted_case_results = {
        "self_consistency_advantage_casebook_audit": {
            "selected_cases": len(sc_case_records),
            "our_failure_tag_counts": dict(sc_reason_counter),
            "reported_advantage_taxonomy": sc_tax,
            "imported_hybrid_intent": {
                "targets_multi_path_answer_aggregation": True,
                "targets_reduced_premature_commitment": True,
                "bounded_not_global": True,
            },
        },
        "observability_targeted_slice": {
            "worst_real_failure_case_count": len((worst_casebook.get("cases") or [])),
            "policy_summary": [{"policy": p, **_summary(rows)} for p, rows in per_policy_rows.items()],
            "near_tie_policy_summary": [{"policy": p, **_summary(rows)} for p, rows in near_tie_rows.items()],
            "intermediate_trap_policy_summary": [{"policy": p, **_summary(rows)} for p, rows in trap_rows.items()],
        },
    }

    # Optional reference summaries.
    intermediate_fix = {}
    fp = REPO_ROOT / args.intermediate_fix_summary
    if fp.exists():
        intermediate_fix = _read_json(fp)

    full_comp = {}
    cp = REPO_ROOT / args.full_comparison_summary
    if cp.exists():
        full_comp = _read_json(cp)

    base = aggregate.get("current_learned_branch_score", {})
    hybrid = aggregate.get("selective_sc_hybrid_v1", {})

    gap_reduction = {
        "baseline_policy": "current_learned_branch_score",
        "hybrid_policy": "selective_sc_hybrid_v1",
        "delta_match_oracle_rate": float(hybrid.get("match_oracle_rate", 0.0) - base.get("match_oracle_rate", 0.0)),
        "delta_mean_oracle_regret": float(hybrid.get("mean_oracle_regret", 0.0) - base.get("mean_oracle_regret", 0.0)),
        "delta_near_tie_match_oracle_rate": float(hybrid.get("near_tie_match_oracle_rate", 0.0) - base.get("near_tie_match_oracle_rate", 0.0)),
        "delta_hard_case_activation_rate": float(hybrid.get("hard_case_activation_rate", 0.0) - base.get("hard_case_activation_rate", 0.0)),
        "delta_consensus_override_rate": float(hybrid.get("consensus_override_rate", 0.0) - base.get("consensus_override_rate", 0.0)),
        "material_gap_reduction_flag": bool((hybrid.get("match_oracle_rate", 0.0) - base.get("match_oracle_rate", 0.0)) >= 0.10),
    }

    taxonomy_shift = {
        "state_count": sum(len(v) for v in per_policy_rows.values()) // max(1, len(per_policy_rows)),
        "selected_failure_subtype_counts_all_branches": dict(subtype_counter),
        "selected_policy_rows_failure_counts": {
            p: dict(Counter(str(r.get("chosen_failure_subtype", "none")) for r in rows)) for p, rows in per_policy_rows.items()
        },
        "premature_commit_proxy": {
            "definition": "policy chooses non-oracle branch in near-tie or intermediate-trap slices",
            "by_policy": {
                p: {
                    "count": int(sum(1 for r in rows if (r["hard_slice"] == "near_tie" or bool(r["chosen_intermediate_trap_flag"])) and not bool(r["match_oracle"]))),
                    "rate": float(
                        sum(1 for r in rows if (r["hard_slice"] == "near_tie" or bool(r["chosen_intermediate_trap_flag"])) and not bool(r["match_oracle"]))
                        / max(1, sum(1 for r in rows if (r["hard_slice"] == "near_tie" or bool(r["chosen_intermediate_trap_flag"]))))
                    ),
                }
                for p, rows in per_policy_rows.items()
            },
        },
    }

    activation_rule = {
        "name": "selective_sc_hard_case_activation_v1",
        "default_mode": "continuation_value_default",
        "hard_case_mode_activation_any": [
            f"top2_gap <= {float(args.near_tie_gap)}",
            f"top_target_completion <= {float(args.low_completion_trigger)}",
            f"continuation_vs_completion_disagreement >= {float(args.disagreement_trigger)}",
            "top_branch_intermediate_trap_flag == true",
        ],
        "scope": "local_per_state_only",
        "guardrail": "do_not_replace_global_continuation_value_objective",
    }

    diversity_budget = {
        "name": "local_diversity_budget_v1",
        "max_branches": int(args.diversity_top_k),
        "selection": "top continuation branches within bounded value drop",
        "value_drop_cap": float(args.max_value_drop),
        "global_budget_expansion": "none",
        "intent": "bounded_local_diversity_only_in_hard_case_mode",
    }

    aggregation_schema = {
        "name": "answer_aggregation_v1",
        "normalization": "extract_final_answer string normalization",
        "group_key": "normalized_answer",
        "support_measures": {
            "support_fraction": "supporters_for_answer / diversity_branches",
            "support_weighted_value": "mean_continuation_value(answer_group) scaled by top continuation",
            "answer_support_score": "0.70*support_fraction + 0.30*support_weighted_value",
        },
        "override_condition": {
            "consensus_support_min": float(args.min_consensus_support),
            "consensus_answer_disagrees_with_top": True,
            "hard_case_mode": True,
        },
        "role": "bounded_hard_case_commit_modifier_not_global_replacement",
    }

    aggregate_comparison_summary = {
        "aggregate_policy_summary": aggregate,
        "near_tie_policy_summary": {p: _summary(rows) for p, rows in near_tie_rows.items()},
        "intermediate_trap_policy_summary": {p: _summary(rows) for p, rows in trap_rows.items()},
        "delta_vs_current_learned_branch_score": {
            "intermediate_trap_aware_near_tie_v1": {
                "delta_match_oracle_rate": float(aggregate.get("intermediate_trap_aware_near_tie_v1", {}).get("match_oracle_rate", 0.0) - base.get("match_oracle_rate", 0.0)),
                "delta_mean_oracle_regret": float(aggregate.get("intermediate_trap_aware_near_tie_v1", {}).get("mean_oracle_regret", 0.0) - base.get("mean_oracle_regret", 0.0)),
            },
            "selective_sc_hybrid_v1": {
                "delta_match_oracle_rate": gap_reduction["delta_match_oracle_rate"],
                "delta_mean_oracle_regret": gap_reduction["delta_mean_oracle_regret"],
                "delta_near_tie_match_oracle_rate": gap_reduction["delta_near_tie_match_oracle_rate"],
            },
        },
        "reference_intermediate_fix_summary": intermediate_fix,
        "reference_completion_aware_comparison": full_comp,
    }

    _write_json(
        out_dir / "manifest.json",
        {
            "run_id": args.run_id,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "frontier_dir": str(frontier_dir),
            "observability_dir": str(observability_dir),
            "sc_casebook_json": str(REPO_ROOT / args.sc_casebook_json),
            "sc_taxonomy_json": str(REPO_ROOT / args.sc_taxonomy_json),
            "failure_casebook_json": str(REPO_ROOT / args.failure_casebook_json),
            "command": " ".join(sys.argv),
            "parameters": {
                "near_tie_gap": float(args.near_tie_gap),
                "max_value_drop": float(args.max_value_drop),
                "low_completion_trigger": float(args.low_completion_trigger),
                "disagreement_trigger": float(args.disagreement_trigger),
                "diversity_top_k": int(args.diversity_top_k),
                "min_consensus_support": float(args.min_consensus_support),
            },
        },
    )
    _write_json(out_dir / "activation_rule_definition.json", activation_rule)
    _write_json(out_dir / "local_diversity_budget_definition.json", diversity_budget)
    _write_json(out_dir / "answer_aggregation_schema.json", aggregation_schema)
    _write_json(out_dir / "targeted_case_results.json", targeted_case_results)
    _write_json(out_dir / "aggregate_comparison_summary.json", aggregate_comparison_summary)
    _write_json(out_dir / "self_consistency_gap_reduction_summary.json", gap_reduction)
    _write_json(out_dir / "failure_taxonomy_shift.json", taxonomy_shift)
    _write_md(
        out_dir / "commands_assumptions_caveats.md",
        "\n".join(
            [
                "# Commands / assumptions / caveats",
                "",
                f"- Command: `{' '.join(sys.argv)}`",
                "- This is a bounded targeted pass and not a global replacement with self-consistency.",
                "- Continuation value remains the default ranking signal.",
                "- Selective self-consistency activation is local to hard states only.",
                "- Local diversity budget is capped and does not trigger broad sample-everything behavior.",
                "- Answer aggregation is only used as a bounded commit/selection aid in hard-case mode.",
                "- Material gap conclusions should be interpreted against this bounded observability-enabled run and saved casebooks.",
            ]
        )
        + "\n",
    )

    print(
        json.dumps(
            {
                "output_dir": str(out_dir),
                "states": len(branch_rows_by_state),
                "policy_states": {k: len(v) for k, v in per_policy_rows.items()},
                "hybrid_delta_match_oracle": gap_reduction["delta_match_oracle_rate"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
