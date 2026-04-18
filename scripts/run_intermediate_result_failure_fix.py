#!/usr/bin/env python3
"""Targeted intermediate-result trap fix evaluation for branch allocation."""

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


def _safe_norm(v: float, lo: float, hi: float) -> float:
    if hi <= lo:
        return 0.5
    return _clip01((v - lo) / (hi - lo))


def _final_line(text: str) -> str:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return lines[-1] if lines else ""


def _has_arith(text: str) -> bool:
    has_digit = any(ch.isdigit() for ch in text)
    has_sym = any(sym in text for sym in ["=", "+", "-", "*", "/", ">", "<"])
    return bool(has_digit and has_sym)


def _completion_signal(obs_row: dict[str, Any] | None) -> dict[str, Any]:
    if not obs_row:
        return {
            "branch_completion_score": 0.0,
            "branch_answer_evidence_score": 0.0,
            "branch_reasoning_text_raw": "",
            "branch_final_answer_text_raw": None,
            "branch_final_answer_normalized": None,
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


def _required_operator(question: str) -> str:
    q = question.lower()
    if "how many times" in q or "number of times" in q:
        return "division_to_count"
    if "off from" in q or "difference" in q or "how many more" in q or "how many fewer" in q or "how much more" in q:
        return "difference_from_target"
    if "give away" in q or "gave away" in q:
        return "leftover_complement"
    return "generic"


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


def _policy_completion_tie_resolution(rows: list[dict[str, Any]], tie_gap: float) -> str:
    ranked = sorted(rows, key=lambda r: float(r["expected_value_if_branch"]), reverse=True)
    if not ranked:
        return ""
    if len(ranked) == 1:
        return str(ranked[0]["branch_id"])
    top = ranked[0]
    second = ranked[1]
    gap = float(top["expected_value_if_branch"] - second["expected_value_if_branch"])
    if gap > tie_gap:
        return str(top["branch_id"])
    top_v = float(top["expected_value_if_branch"])
    eligible = [r for r in ranked if (top_v - float(r["expected_value_if_branch"])) <= tie_gap]
    return str(max(eligible, key=lambda r: float(r["branch_completion_score"]))["branch_id"])


def _policy_intermediate_trap_aware(rows: list[dict[str, Any]], *, tie_gap: float, max_value_drop: float, incompleteness_trigger: float) -> str:
    ranked = sorted(rows, key=lambda r: float(r["expected_value_if_branch"]), reverse=True)
    if not ranked:
        return ""
    top = ranked[0]
    if len(ranked) == 1:
        return str(top["branch_id"])
    top2_gap = float(top["expected_value_if_branch"] - ranked[1]["expected_value_if_branch"])
    near_tie = top2_gap <= tie_gap
    if (not near_tie) or float(top["semantic_incompleteness_score"]) < incompleteness_trigger:
        return str(top["branch_id"])

    top_v = float(top["expected_value_if_branch"])
    v_vals = [float(r["expected_value_if_branch"]) for r in rows]
    lo, hi = min(v_vals), max(v_vals)

    eligible = [r for r in rows if (top_v - float(r["expected_value_if_branch"])) <= max_value_drop]
    if not eligible:
        return str(top["branch_id"])

    def _score(r: dict[str, Any]) -> float:
        v = _safe_norm(float(r["expected_value_if_branch"]), lo, hi)
        commit = float(r["commit_quality_score"])
        incompleteness = float(r["semantic_incompleteness_score"])
        return 0.55 * v + 0.35 * commit - 0.10 * incompleteness

    return str(max(eligible, key=_score)["branch_id"])


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run targeted intermediate-result trap fix pass")
    p.add_argument("--run-id", required=True)
    p.add_argument("--frontier-dir", default="")
    p.add_argument("--observability-dir", default="")
    p.add_argument("--casebook-json", default="outputs/branch_label_bruteforce_learning/worst_real_failure_casebook_with_reasoning_20260418/rich_failure_cases_structured.json")
    p.add_argument("--multistep-summary", default="outputs/branch_label_bruteforce_learning/multistep_branch_utility_target_validation_eval_20260417/aggregate_comparison_summary.json")
    p.add_argument("--output-dir", default="outputs/intermediate_result_failure_fix_20260418")
    p.add_argument("--near-tie-gap", type=float, default=0.03)
    p.add_argument("--max-value-drop", type=float, default=0.02)
    p.add_argument("--incompleteness-trigger", type=float, default=0.45)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    frontier_dir = Path(args.frontier_dir) if args.frontier_dir else REPO_ROOT / "outputs/frontier_target_construction" / args.run_id
    observability_dir = Path(args.observability_dir) if args.observability_dir else REPO_ROOT / "outputs/branch_observability" / args.run_id
    out_dir = REPO_ROOT / args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    util_rows = _read_jsonl(frontier_dir / "branch_marginal_utility.jsonl")
    trace_rows = _read_jsonl(frontier_dir / "real_trace_input.jsonl")
    obs_rows = _read_jsonl(observability_dir / "branch_trace_records.jsonl")
    casebook_payload = _read_json(REPO_ROOT / args.casebook_json)
    casebook_cases = casebook_payload.get("cases", [])

    trace_by_pair = {(int(r.get("episode_id", 0)), int(r.get("decision_id", 0))): r for r in trace_rows}
    gt_by_state: dict[str, str | None] = {}
    method_by_state: dict[str, str] = {}
    q_by_state: dict[str, str] = {}

    states: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in util_rows:
        sid = str(r.get("state_id", ""))
        states[sid].append(r)

    obs_map = {(str(r.get("state_id")), str(r.get("branch_id"))): r for r in obs_rows}

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
            commit_quality = _clip01(0.55 * float(cs.get("branch_completion_score", 0.0)) + 0.25 * float(cs.get("branch_answer_evidence_score", 0.0)) + 0.20 * (1.0 - float(sem.get("semantic_incompleteness_score", 0.0))))
            merged = {
                "state_id": sid,
                "branch_id": bid,
                "expected_value_if_branch": float(r.get("expected_value_if_branch", 0.0)),
                "delta_u_vs_outside": float(r.get("delta_u_vs_outside", 0.0)),
                **cs,
                **sem,
                "commit_quality_score": float(commit_quality),
            }
            subtype_counter.update([str(sem.get("failure_subtype", "none"))])
            enhanced_rows.append(merged)
        branch_rows_by_state[sid] = enhanced_rows

    # Failure taxonomy from saved casebook (small targeted taxonomy only).
    taxonomy_rows: list[dict[str, Any]] = []
    for c in casebook_cases:
        question = str(c.get("question", ""))
        reasoning = _nonempty(c.get("method_branch_reasoning_text"))
        fake_sig = {
            "branch_reasoning_text_raw": reasoning,
            "branch_final_answer_normalized": c.get("method_branch_normalized_answer"),
            "branch_final_answer_text_raw": c.get("method_branch_final_answer_text"),
            "extracted_numbers": c.get("method_extracted_numbers") or [],
        }
        sem = _semantic_incompleteness_signal(question, fake_sig)
        taxonomy_rows.append(
            {
                "state_id": c.get("state_id"),
                "question": question,
                "failure_subtype": sem.get("failure_subtype"),
                "required_operator": sem.get("required_operator"),
                "one_more_operator_needed": sem.get("one_more_operator_needed"),
                "answer_matches_intermediate": sem.get("answer_matches_intermediate"),
            }
        )

    taxonomy_counts = Counter(str(r.get("failure_subtype", "none")) for r in taxonomy_rows)

    policies = {
        "continuation_oracle": lambda srows: str(max(srows, key=lambda r: float(r["expected_value_if_branch"]))["branch_id"]),
        "current_learned_branch_score": lambda srows, sid=None: method_by_state.get(str(sid), ""),
        "completion_tie_resolution_current": lambda srows: _policy_completion_tie_resolution(srows, tie_gap=float(args.near_tie_gap)),
        "intermediate_trap_aware_near_tie_v1": lambda srows: _policy_intermediate_trap_aware(
            srows,
            tie_gap=float(args.near_tie_gap),
            max_value_drop=float(args.max_value_drop),
            incompleteness_trigger=float(args.incompleteness_trigger),
        ),
    }

    per_policy_rows: dict[str, list[dict[str, Any]]] = {k: [] for k in policies}
    all_eval_rows: list[dict[str, Any]] = []

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
            if pname == "current_learned_branch_score":
                bid = str(fn(srows, sid))
                if not bid:
                    bid = oracle_bid
            else:
                bid = str(fn(srows))
                if not bid:
                    bid = oracle_bid
            chosen = by_bid.get(bid, by_bid[oracle_bid])
            gt = gt_by_state.get(sid)
            predicted_norm = _nonempty(chosen.get("branch_final_answer_normalized")) if chosen.get("branch_final_answer_normalized") is not None else None
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
            }
            per_policy_rows[pname].append(row)
            all_eval_rows.append(row)

    def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
        regrets = [float(r["oracle_regret"]) for r in rows]
        recoverable = [r for r in rows if r.get("recoverable_correct") is not None]
        trap_slice = [r for r in rows if bool(r.get("chosen_intermediate_trap_flag"))]
        return {
            "states": len(rows),
            "match_oracle_rate": float(sum(int(bool(r["match_oracle"])) for r in rows) / len(rows)) if rows else 0.0,
            "mean_oracle_regret": float(mean(regrets)) if regrets else 0.0,
            "recoverable_answer_accuracy": float(sum(int(bool(r["recoverable_correct"])) for r in recoverable) / len(recoverable)) if recoverable else None,
            "recoverable_n": len(recoverable),
            "intermediate_trap_selected_rate": float(sum(int(bool(r["chosen_intermediate_trap_flag"])) for r in rows) / len(rows)) if rows else 0.0,
            "trap_slice_mean_oracle_regret": float(mean([float(r["oracle_regret"]) for r in trap_slice])) if trap_slice else 0.0,
            "near_tie_match_oracle_rate": float(sum(int(bool(r["match_oracle"])) for r in rows if r["hard_slice"] == "near_tie") / max(1, sum(int(r["hard_slice"] == "near_tie") for r in rows))),
        }

    aggregate = {p: _summary(rows) for p, rows in per_policy_rows.items()}

    casebook_ids = {str(c.get("state_id")) for c in casebook_cases}
    targeted_results: list[dict[str, Any]] = []
    for p, rows in per_policy_rows.items():
        sub = [r for r in rows if str(r.get("state_id")) in casebook_ids]
        targeted_results.append({"policy": p, **_summary(sub), "states_in_targeted_casebook": len(sub)})

    near_tie_results: list[dict[str, Any]] = []
    for p, rows in per_policy_rows.items():
        sub = [r for r in rows if r.get("hard_slice") == "near_tie"]
        near_tie_results.append({"policy": p, **_summary(sub), "near_tie_states": len(sub)})

    oracle_alignment = {
        "reference_oracle": "continuation_oracle_expected_value_if_branch",
        "summary": [{"policy": p, "match_oracle_rate": v["match_oracle_rate"], "mean_oracle_regret": v["mean_oracle_regret"]} for p, v in aggregate.items()],
    }

    multi_ref: dict[str, Any] = {}
    mpath = REPO_ROOT / args.multistep_summary
    if mpath.exists():
        multi_ref = _read_json(mpath)

    aggregate_comparison = {
        "aggregate_policy_summary": aggregate,
        "delta_vs_current_learned_branch_score": {
            "intermediate_trap_aware_near_tie_v1": {
                "delta_match_oracle_rate": float(aggregate["intermediate_trap_aware_near_tie_v1"]["match_oracle_rate"] - aggregate["current_learned_branch_score"]["match_oracle_rate"]),
                "delta_mean_oracle_regret": float(aggregate["intermediate_trap_aware_near_tie_v1"]["mean_oracle_regret"] - aggregate["current_learned_branch_score"]["mean_oracle_regret"]),
                "delta_recoverable_answer_accuracy": None
                if aggregate["intermediate_trap_aware_near_tie_v1"]["recoverable_answer_accuracy"] is None or aggregate["current_learned_branch_score"]["recoverable_answer_accuracy"] is None
                else float(aggregate["intermediate_trap_aware_near_tie_v1"]["recoverable_answer_accuracy"] - aggregate["current_learned_branch_score"]["recoverable_answer_accuracy"]),
            }
        },
        "reference_multistep_k3_validation": (multi_ref.get("aggregate") or {}).get("multistep_branch_utility_target_k3", {}),
    }

    signal_rows = [r for rows in branch_rows_by_state.values() for r in rows]
    signal_summary = {
        "rows": len(signal_rows),
        "state_count": len(branch_rows_by_state),
        "mean_semantic_incompleteness_score": float(mean([float(r["semantic_incompleteness_score"]) for r in signal_rows])) if signal_rows else 0.0,
        "intermediate_trap_flag_rate": float(sum(int(bool(r["intermediate_trap_flag"])) for r in signal_rows) / len(signal_rows)) if signal_rows else 0.0,
        "failure_subtype_counts_all_branches": dict(subtype_counter),
        "score_formula": "0.50*one_more_operator_needed + 0.20*target_cue_missing_on_targeted_question + 0.30*answer_matches_intermediate_and_one_more_operator_needed (clipped_0_1)",
        "commit_quality_formula": "0.55*completion + 0.25*answer_evidence + 0.20*(1-semantic_incompleteness)",
        "policy_use_scope": "local_near_tie_override_only_when_top_branch_incompleteness_ge_trigger",
    }

    _write_json(
        out_dir / "manifest.json",
        {
            "run_id": args.run_id,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "frontier_dir": str(frontier_dir),
            "observability_dir": str(observability_dir),
            "casebook_json": str(REPO_ROOT / args.casebook_json),
            "command": " ".join(sys.argv),
            "parameters": {
                "near_tie_gap": float(args.near_tie_gap),
                "max_value_drop": float(args.max_value_drop),
                "incompleteness_trigger": float(args.incompleteness_trigger),
            },
        },
    )
    _write_json(
        out_dir / "failure_taxonomy.json",
        {
            "targeted_cases_n": len(taxonomy_rows),
            "taxonomy_rows": taxonomy_rows,
            "taxonomy_counts": dict(taxonomy_counts),
            "taxonomy_note": "Minimal taxonomy constrained to observed intermediate-result trap subtypes.",
        },
    )
    _write_json(out_dir / "semantic_incompleteness_signal_summary.json", signal_summary)
    _write_json(out_dir / "targeted_case_results.json", {"rows": targeted_results, "targeted_state_ids": sorted(casebook_ids)})
    _write_json(out_dir / "aggregate_comparison_summary.json", aggregate_comparison)
    _write_json(out_dir / "near_tie_slice_results.json", {"rows": near_tie_results})
    _write_json(out_dir / "oracle_alignment_results.json", oracle_alignment)
    _write_md(
        out_dir / "commands_assumptions_caveats.md",
        "\n".join(
            [
                "# Commands / assumptions / caveats",
                "",
                f"- Command: `{' '.join(sys.argv)}`",
                "- This is a bounded targeted pass on one observability-enabled run and its saved worst-case casebook.",
                "- Continuation value remains the core default score.",
                "- Intermediate-result trap signal is only used under near-tie disagreement and capped value-drop conditions.",
                "- Taxonomy is intentionally minimal and directly tied to observed failure archetypes.",
            ]
        )
        + "\n",
    )

    print(json.dumps({"output_dir": str(out_dir), "states": len(branch_rows_by_state), "targeted_cases": len(taxonomy_rows)}, indent=2))


if __name__ == "__main__":
    main()
