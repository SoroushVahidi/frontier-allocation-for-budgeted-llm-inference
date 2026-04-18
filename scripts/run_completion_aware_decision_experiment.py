#!/usr/bin/env python3
"""Bounded completion-aware decision experiment for branch allocation mismatch analysis."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.data import extract_final_answer  # noqa: E402


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


def _nonempty_text(x: Any) -> str:
    if x is None:
        return ""
    return str(x).strip()


def _looks_like_final_line(line: str) -> bool:
    s = line.lower().strip()
    if not s:
        return False
    cues = [
        "final answer",
        "answer is",
        "therefore",
        "thus",
        "so ",
        "hence",
        "we get",
    ]
    return any(c in s for c in cues)


def _has_arithmetic_or_comparison(text: str) -> bool:
    s = text.lower()
    has_digit = bool(re.search(r"\d", s))
    has_symbol = any(tok in s for tok in ["=", "+", "-", "*", "/", ">", "<"])
    return bool(has_digit and has_symbol)


def build_completion_signal(record: dict[str, Any]) -> dict[str, Any]:
    final_answer_text = _nonempty_text(record.get("branch_final_answer_text_raw"))
    normalized = record.get("branch_final_answer_normalized")
    reasoning_text = _nonempty_text(record.get("branch_reasoning_text_raw"))
    branch_text = _nonempty_text(record.get("branch_text_raw"))
    text_for_scan = reasoning_text or branch_text

    lines = [ln.strip() for ln in text_for_scan.splitlines() if ln.strip()]
    last_line = lines[-1] if lines else ""

    has_final_answer_text = bool(final_answer_text)
    has_normalized = normalized is not None
    has_reasoning_text = bool(reasoning_text)
    has_final_step_cue = _looks_like_final_line(last_line)
    has_final_arith_or_cmp = _has_arithmetic_or_comparison(last_line) or _has_arithmetic_or_comparison(reasoning_text)
    has_terminal_numeric = bool(re.search(r"\d", final_answer_text or last_line))

    branch_completion_score = min(
        1.0,
        (
            (0.45 if has_final_answer_text else 0.0)
            + (0.25 if has_normalized else 0.0)
            + (0.20 if has_final_arith_or_cmp else 0.0)
            + (0.10 if has_final_step_cue else 0.0)
        ),
    )
    branch_answer_evidence_score = min(
        1.0,
        (0.60 if has_normalized else 0.0) + (0.30 if has_final_answer_text else 0.0) + (0.10 if has_terminal_numeric else 0.0),
    )

    return {
        "state_id": str(record.get("state_id", "")),
        "branch_id": str(record.get("branch_id", "")),
        "branch_has_final_answer_text": has_final_answer_text,
        "branch_has_normalized_answer": has_normalized,
        "branch_completion_score": float(branch_completion_score),
        "branch_answer_evidence_score": float(branch_answer_evidence_score),
        "branch_reasoning_completion_flags": {
            "has_reasoning_text": has_reasoning_text,
            "has_final_step_cue": has_final_step_cue,
            "has_final_arithmetic_or_comparison_step": has_final_arith_or_cmp,
            "has_terminal_numeric_token": has_terminal_numeric,
        },
        "completion_signal_provenance": {
            "source_fields": [
                "branch_reasoning_text_raw",
                "branch_final_answer_text_raw",
                "branch_final_answer_normalized",
                "branch_text_raw",
            ],
            "rule_set": "explicit_boolean_heuristics_v1",
        },
    }


def _state_best(rows: list[dict[str, Any]], score_field: str) -> str:
    return str(max(rows, key=lambda r: float(r.get(score_field, 0.0))).get("branch_id", ""))


def _find_branch(rows: list[dict[str, Any]], branch_id: str) -> dict[str, Any]:
    for r in rows:
        if str(r.get("branch_id")) == str(branch_id):
            return r
    return {}


def _pick_completion_bonus(rows: list[dict[str, Any]], completion: dict[tuple[str, str], dict[str, Any]], bonus: float) -> str:
    def score(r: dict[str, Any]) -> float:
        sig = completion.get((str(r.get("state_id")), str(r.get("branch_id"))), {})
        return float(r.get("expected_value_if_branch", 0.0)) + bonus * float(sig.get("branch_completion_score", 0.0))

    return str(max(rows, key=score).get("branch_id", ""))


def _pick_completion_outside_gate(
    rows: list[dict[str, Any]],
    completion: dict[tuple[str, str], dict[str, Any]],
    *,
    gate_min_completion_score: float,
    gate_min_outside_gap: float,
    gate_max_oracle_value_drop: float,
) -> str:
    oracle = max(rows, key=lambda r: float(r.get("expected_value_if_branch", 0.0)))
    oracle_bid = str(oracle.get("branch_id", ""))
    oracle_val = float(oracle.get("expected_value_if_branch", 0.0))

    ranked_by_completion = sorted(
        rows,
        key=lambda r: float(completion.get((str(r.get("state_id")), str(r.get("branch_id"))), {}).get("branch_completion_score", 0.0)),
        reverse=True,
    )
    if not ranked_by_completion:
        return oracle_bid

    cand = ranked_by_completion[0]
    cand_bid = str(cand.get("branch_id", ""))
    cand_sig = completion.get((str(cand.get("state_id")), cand_bid), {})
    cand_completion = float(cand_sig.get("branch_completion_score", 0.0))
    cand_outside = float(cand.get("delta_u_vs_outside", 0.0))
    cand_val = float(cand.get("expected_value_if_branch", 0.0))

    if (
        cand_bid != oracle_bid
        and cand_completion >= gate_min_completion_score
        and cand_outside >= gate_min_outside_gap
        and (oracle_val - cand_val) <= gate_max_oracle_value_drop
    ):
        return cand_bid
    return oracle_bid


def _pick_completion_tie_resolution(
    rows: list[dict[str, Any]], completion: dict[tuple[str, str], dict[str, Any]], *, tie_gap: float
) -> str:
    ranked = sorted(rows, key=lambda r: float(r.get("expected_value_if_branch", 0.0)), reverse=True)
    if not ranked:
        return ""
    if len(ranked) == 1:
        return str(ranked[0].get("branch_id", ""))
    top = ranked[0]
    second = ranked[1]
    gap = float(top.get("expected_value_if_branch", 0.0) - second.get("expected_value_if_branch", 0.0))
    if gap > tie_gap:
        return str(top.get("branch_id", ""))

    top_value = float(top.get("expected_value_if_branch", 0.0))
    eligible = [r for r in ranked if (top_value - float(r.get("expected_value_if_branch", 0.0))) <= tie_gap]
    return str(
        max(
            eligible,
            key=lambda r: float(completion.get((str(r.get("state_id")), str(r.get("branch_id"))), {}).get("branch_completion_score", 0.0)),
        ).get("branch_id", "")
    )


def _evaluate_policy(
    *,
    policy_name: str,
    states: dict[str, list[dict[str, Any]]],
    completion: dict[tuple[str, str], dict[str, Any]],
    method_choice: dict[str, str],
    ground_truth_norm: dict[str, str | None],
    decision_fn,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for sid, srows in sorted(states.items()):
        if len(srows) < 2:
            continue
        oracle_bid = _state_best(srows, "expected_value_if_branch")
        oracle_row = _find_branch(srows, oracle_bid)
        method_bid = str(method_choice.get(sid, ""))
        method_row = _find_branch(srows, method_bid)

        chosen_bid = str(decision_fn(sid, srows, oracle_bid, method_bid))
        chosen_row = _find_branch(srows, chosen_bid)

        oracle_sig = completion.get((sid, oracle_bid), {})
        method_sig = completion.get((sid, method_bid), {})
        chosen_sig = completion.get((sid, chosen_bid), {})

        gt = ground_truth_norm.get(sid)
        chosen_norm = _nonempty_text(chosen_sig.get("branch_normalized_answer")) if chosen_sig.get("branch_normalized_answer") is not None else None
        correct_recoverable = None
        if gt is not None and chosen_norm is not None:
            correct_recoverable = bool(chosen_norm == gt)

        rows.append(
            {
                "state_id": sid,
                "policy": policy_name,
                "oracle_preferred_branch": oracle_bid,
                "method_chosen_branch": method_bid,
                "completion_aware_chosen_branch": chosen_bid,
                "oracle_expected_value": float(oracle_row.get("expected_value_if_branch", 0.0)),
                "method_expected_value": float(method_row.get("expected_value_if_branch", 0.0)) if method_row else None,
                "chosen_expected_value": float(chosen_row.get("expected_value_if_branch", 0.0)) if chosen_row else None,
                "oracle_completion_score": float(oracle_sig.get("branch_completion_score", 0.0)),
                "method_completion_score": float(method_sig.get("branch_completion_score", 0.0)),
                "chosen_completion_score": float(chosen_sig.get("branch_completion_score", 0.0)),
                "chosen_has_stronger_completion_than_oracle": float(chosen_sig.get("branch_completion_score", 0.0)) > float(oracle_sig.get("branch_completion_score", 0.0)),
                "chosen_has_stronger_completion_than_method": float(chosen_sig.get("branch_completion_score", 0.0)) > float(method_sig.get("branch_completion_score", 0.0)),
                "target_objective_mismatch": bool(
                    float(oracle_sig.get("branch_completion_score", 0.0)) < float(method_sig.get("branch_completion_score", 0.0))
                    and oracle_bid != method_bid
                ),
                "branch_correct_when_recoverable": correct_recoverable,
                "ground_truth_answer_normalized": gt,
                "chosen_branch_normalized_answer": chosen_norm,
            }
        )

    regrets = [float(r["oracle_expected_value"]) - float(r["chosen_expected_value"]) for r in rows if r.get("chosen_expected_value") is not None]
    recoverable = [r for r in rows if r.get("branch_correct_when_recoverable") is not None]
    mismatch_rows = [r for r in rows if bool(r.get("target_objective_mismatch"))]
    corrected_mismatch = [r for r in mismatch_rows if str(r.get("completion_aware_chosen_branch")) == str(r.get("method_chosen_branch"))]

    summary = {
        "policy": policy_name,
        "states": len(rows),
        "match_oracle_rate": float(sum(int(r["completion_aware_chosen_branch"] == r["oracle_preferred_branch"]) for r in rows) / len(rows)) if rows else 0.0,
        "match_method_rate": float(sum(int(r["completion_aware_chosen_branch"] == r["method_chosen_branch"]) for r in rows) / len(rows)) if rows else 0.0,
        "mean_oracle_regret": float(mean(regrets)) if regrets else 0.0,
        "prefer_stronger_completion_vs_oracle_rate": float(sum(int(bool(r["chosen_has_stronger_completion_than_oracle"])) for r in rows) / len(rows)) if rows else 0.0,
        "prefer_stronger_completion_vs_method_rate": float(sum(int(bool(r["chosen_has_stronger_completion_than_method"])) for r in rows) / len(rows)) if rows else 0.0,
        "recoverable_answer_accuracy": float(sum(int(bool(r["branch_correct_when_recoverable"])) for r in recoverable) / len(recoverable)) if recoverable else None,
        "recoverable_answer_n": len(recoverable),
        "objective_mismatch_states": len(mismatch_rows),
        "objective_mismatch_resolved_by_policy": len(corrected_mismatch),
    }
    return rows, summary


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run bounded completion-aware decision analysis")
    p.add_argument("--run-id", default="")
    p.add_argument("--frontier-dir", default="")
    p.add_argument("--observability-dir", default="")
    p.add_argument("--output-root", default="outputs/branch_label_bruteforce_learning")
    p.add_argument("--output-run-id", default="")
    p.add_argument("--completion-bonus", type=float, default=0.03)
    p.add_argument("--completion-gate-min-score", type=float, default=0.20)
    p.add_argument("--completion-gate-min-outside-gap", type=float, default=-0.02)
    p.add_argument("--completion-gate-max-oracle-drop", type=float, default=0.02)
    p.add_argument("--tie-gap", type=float, default=0.03)
    p.add_argument("--multistep-summary", default="outputs/branch_label_bruteforce_learning/multistep_branch_utility_target_validation_eval_20260417/aggregate_comparison_summary.json")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    run_id = args.run_id
    if not run_id and not args.frontier_dir:
        raise SystemExit("Provide --run-id or explicit --frontier-dir/--observability-dir")

    if not run_id:
        run_id = Path(args.frontier_dir).name
    frontier_dir = Path(args.frontier_dir) if args.frontier_dir else REPO_ROOT / "outputs/frontier_target_construction" / run_id
    observability_dir = Path(args.observability_dir) if args.observability_dir else REPO_ROOT / "outputs/branch_observability" / run_id

    out_run_id = args.output_run_id or datetime.now(timezone.utc).strftime("completion_aware_decision_eval_%Y%m%dT%H%M%SZ")
    out_dir = REPO_ROOT / args.output_root / out_run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    util_rows = _read_jsonl(frontier_dir / "branch_marginal_utility.jsonl")
    trace_rows = _read_jsonl(frontier_dir / "real_trace_input.jsonl")
    obs_rows = _read_jsonl(observability_dir / "branch_trace_records.jsonl")

    trace_by_state: dict[str, dict[str, Any]] = {}
    for r in trace_rows:
        sid = f"s_ep{int(r.get('episode_id', 0))}_d{int(r.get('decision_id', 0))}_r{int(r.get('remaining_budget', 0))}_{str(r.get('question', ''))[:0]}"
        trace_by_state[sid] = r
    # exact state_id is stored in utility rows; map via episode+decision fallback
    trace_by_pair = {(int(r.get("episode_id", 0)), int(r.get("decision_id", 0))): r for r in trace_rows}

    states: dict[str, list[dict[str, Any]]] = defaultdict(list)
    method_choice: dict[str, str] = {}
    ground_truth_norm: dict[str, str | None] = {}
    for row in util_rows:
        sid = str(row.get("state_id", ""))
        states[sid].append(row)
        key = (int(row.get("episode_id", 0)), int(row.get("decision_id", 0)))
        tr = trace_by_pair.get(key, {})
        if tr:
            method_choice[sid] = str(tr.get("method_chosen_branch_id", ""))
            gt = extract_final_answer(str(tr.get("answer", ""))) if tr.get("answer") is not None else None
            ground_truth_norm[sid] = gt

    completion_signal_rows: list[dict[str, Any]] = []
    completion_map: dict[tuple[str, str], dict[str, Any]] = {}
    for r in obs_rows:
        sig = build_completion_signal(r)
        sig["branch_normalized_answer"] = r.get("branch_final_answer_normalized")
        completion_signal_rows.append(sig)
        completion_map[(sig["state_id"], sig["branch_id"])] = sig

    # Ensure every utility branch has an explicit conservative signal row.
    for sid, srows in states.items():
        for br in srows:
            bid = str(br.get("branch_id", ""))
            key = (sid, bid)
            if key in completion_map:
                continue
            missing_sig = {
                "state_id": sid,
                "branch_id": bid,
                "branch_has_final_answer_text": False,
                "branch_has_normalized_answer": False,
                "branch_completion_score": 0.0,
                "branch_answer_evidence_score": 0.0,
                "branch_reasoning_completion_flags": {
                    "has_reasoning_text": False,
                    "has_final_step_cue": False,
                    "has_final_arithmetic_or_comparison_step": False,
                    "has_terminal_numeric_token": False,
                },
                "completion_signal_provenance": {
                    "source_fields": ["missing_observability_record"],
                    "rule_set": "explicit_boolean_heuristics_v1",
                    "fallback_reason": "no_branch_trace_record_for_state_branch",
                },
                "branch_normalized_answer": None,
            }
            completion_signal_rows.append(missing_sig)
            completion_map[key] = missing_sig

    def _oracle_policy(_sid: str, srows: list[dict[str, Any]], _ob: str, _mb: str) -> str:
        return _state_best(srows, "expected_value_if_branch")

    def _method_policy(sid: str, srows: list[dict[str, Any]], ob: str, _mb: str) -> str:
        chosen = method_choice.get(sid)
        return chosen if chosen else ob

    def _completion_bonus_policy(_sid: str, srows: list[dict[str, Any]], _ob: str, _mb: str) -> str:
        return _pick_completion_bonus(srows, completion_map, bonus=float(args.completion_bonus))

    def _completion_gate_policy(_sid: str, srows: list[dict[str, Any]], _ob: str, _mb: str) -> str:
        return _pick_completion_outside_gate(
            srows,
            completion_map,
            gate_min_completion_score=float(args.completion_gate_min_score),
            gate_min_outside_gap=float(args.completion_gate_min_outside_gap),
            gate_max_oracle_value_drop=float(args.completion_gate_max_oracle_drop),
        )

    def _completion_tie_policy(_sid: str, srows: list[dict[str, Any]], _ob: str, _mb: str) -> str:
        return _pick_completion_tie_resolution(srows, completion_map, tie_gap=float(args.tie_gap))

    policy_defs = {
        "oracle_one_step_reference": _oracle_policy,
        "best_bounded_learned_branch_score_current": _method_policy,
        "completion_bonus": _completion_bonus_policy,
        "completion_outside_gate": _completion_gate_policy,
        "completion_tie_resolution": _completion_tie_policy,
    }

    per_policy_rows: dict[str, list[dict[str, Any]]] = {}
    per_policy_summary: list[dict[str, Any]] = []
    for name, fn in policy_defs.items():
        rows, summary = _evaluate_policy(
            policy_name=name,
            states=states,
            completion=completion_map,
            method_choice=method_choice,
            ground_truth_norm=ground_truth_norm,
            decision_fn=fn,
        )
        per_policy_rows[name] = rows
        per_policy_summary.append(summary)

    summary_by_policy = {r["policy"]: r for r in per_policy_summary}
    learned = summary_by_policy.get("best_bounded_learned_branch_score_current", {})
    completion_bonus = summary_by_policy.get("completion_bonus", {})
    completion_gate = summary_by_policy.get("completion_outside_gate", {})
    completion_tie = summary_by_policy.get("completion_tie_resolution", {})

    multistep_reference = _read_json(Path(args.multistep_summary)) if Path(args.multistep_summary).exists() else {}
    multistep_agg = (multistep_reference.get("aggregate") or {}).get("multistep_branch_utility_target_k3", {})
    if not multistep_agg:
        multistep_agg = (multistep_reference.get("aggregate") or {}).get("multistep_k3_current", {})
    if not multistep_agg:
        multistep_agg = (multistep_reference.get("aggregate") or {}).get("multistep_k3", {})

    aggregate_comparison = {
        "observability_run_policy_summary": per_policy_summary,
        "comparison_vs_best_bounded_learned": {
            "completion_bonus_delta_match_oracle_rate": float(completion_bonus.get("match_oracle_rate", 0.0) - learned.get("match_oracle_rate", 0.0)),
            "completion_bonus_delta_mean_oracle_regret": float(completion_bonus.get("mean_oracle_regret", 0.0) - learned.get("mean_oracle_regret", 0.0)),
            "completion_gate_delta_match_oracle_rate": float(completion_gate.get("match_oracle_rate", 0.0) - learned.get("match_oracle_rate", 0.0)),
            "completion_tie_delta_match_oracle_rate": float(completion_tie.get("match_oracle_rate", 0.0) - learned.get("match_oracle_rate", 0.0)),
        },
        "reference_multistep_k3_current_from_validation": {
            "source_path": str(args.multistep_summary),
            "accepted_accuracy_mean": multistep_agg.get("accepted_accuracy_mean"),
            "near_tie_accepted_accuracy_mean": multistep_agg.get("near_tie_accepted_accuracy_mean"),
            "strict_slice_accepted_accuracy_mean": multistep_agg.get("strict_slice_accepted_accuracy_mean"),
            "note": "Reference metric from canonical validation artifact; not directly re-evaluated on observability run states.",
        },
    }

    failure_diag_rows: list[dict[str, Any]] = []
    learned_rows = {r["state_id"]: r for r in per_policy_rows.get("best_bounded_learned_branch_score_current", [])}
    for policy_name in ["completion_bonus", "completion_outside_gate", "completion_tie_resolution"]:
        for r in per_policy_rows.get(policy_name, []):
            base = learned_rows.get(r["state_id"], {})
            failure_diag_rows.append(
                {
                    "state_id": r["state_id"],
                    "policy": policy_name,
                    "oracle_preferred_branch": r["oracle_preferred_branch"],
                    "method_chosen_branch": base.get("completion_aware_chosen_branch"),
                    "completion_aware_chosen_branch": r["completion_aware_chosen_branch"],
                    "policy_changed_choice_vs_method": r["completion_aware_chosen_branch"] != base.get("completion_aware_chosen_branch"),
                    "oracle_prefers_less_answer_complete_than_method": bool(
                        float(base.get("oracle_completion_score", 0.0)) < float(base.get("chosen_completion_score", 0.0))
                        and base.get("oracle_preferred_branch") != base.get("completion_aware_chosen_branch")
                    ),
                    "completion_policy_picks_more_complete_than_oracle": bool(r.get("chosen_has_stronger_completion_than_oracle")),
                    "branch_correct_when_recoverable": r.get("branch_correct_when_recoverable"),
                }
            )

    completion_alignment = {
        "rows": failure_diag_rows,
        "summary": {
            "states": len({r["state_id"] for r in failure_diag_rows}),
            "rows": len(failure_diag_rows),
            "changed_choice_rows": sum(int(bool(r["policy_changed_choice_vs_method"])) for r in failure_diag_rows),
            "oracle_prefers_less_complete_rows": sum(int(bool(r["oracle_prefers_less_answer_complete_than_method"])) for r in failure_diag_rows),
            "completion_picks_more_complete_than_oracle_rows": sum(int(bool(r["completion_policy_picks_more_complete_than_oracle"])) for r in failure_diag_rows),
        },
    }

    support = {
        "states_total": len(states),
        "state_with_method_choice": len(method_choice),
        "branch_rows": len(util_rows),
        "observability_rows": len(obs_rows),
        "completion_signal_rows": len(completion_signal_rows),
        "normalized_answers_recoverable": sum(int(bool(r.get("branch_has_normalized_answer"))) for r in completion_signal_rows),
        "final_answer_text_recoverable": sum(int(bool(r.get("branch_has_final_answer_text"))) for r in completion_signal_rows),
    }

    _write_json(
        out_dir / "config_manifest.json",
        {
            "run_id": out_run_id,
            "source_frontier_run_id": run_id,
            "source_frontier_dir": str(frontier_dir),
            "source_observability_dir": str(observability_dir),
            "policy_family": [
                "completion_bonus",
                "completion_outside_gate",
                "completion_tie_resolution",
            ],
            "completion_signal_definition": "explicit_boolean_heuristics_v1",
            "parameters": {
                "completion_bonus": float(args.completion_bonus),
                "completion_gate_min_score": float(args.completion_gate_min_score),
                "completion_gate_min_outside_gap": float(args.completion_gate_min_outside_gap),
                "completion_gate_max_oracle_drop": float(args.completion_gate_max_oracle_drop),
                "tie_gap": float(args.tie_gap),
            },
            "command": " ".join(sys.argv),
        },
    )
    _write_json(out_dir / "completion_signal_artifacts.json", {"rows": completion_signal_rows})
    _write_json(out_dir / "per_seed_summary.json", {"rows": [{"seed": int(_read_json(frontier_dir / 'config_echo.json').get('seed', 0)), "policy_summary": per_policy_summary}]})
    _write_json(out_dir / "aggregate_comparison_summary.json", aggregate_comparison)
    _write_json(out_dir / "completion_alignment_diagnostics.json", completion_alignment)
    _write_json(out_dir / "failure_case_diagnostics.json", {"rows": failure_diag_rows, "per_policy_rows": per_policy_rows})
    _write_json(out_dir / "support_diagnostics.json", support)
    (out_dir / "commands_assumptions_caveats.md").write_text(
        "\n".join(
            [
                "# Commands / assumptions / caveats",
                "",
                f"- Command: `{' '.join(sys.argv)}`",
                "- This pass is bounded to one observability-enabled worst-failure run and does not retrain canonical multistep models.",
                "- `multistep_k3_current` is included as an external reference from the canonical validation aggregate file.",
                "- Completion signal is explicit/rule-based and conservative: absent evidence defaults to zero evidence.",
                "- Correctness by branch answer is only computed when normalized branch answers are recoverable.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    print(json.dumps({"output_dir": str(out_dir), "states": len(states), "policies": list(policy_defs)}, indent=2))


if __name__ == "__main__":
    main()
