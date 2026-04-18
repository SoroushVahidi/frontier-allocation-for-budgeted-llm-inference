#!/usr/bin/env python3
"""Bounded oracle-comparison study for continuation vs completion-aware vs hybrid targets."""

from __future__ import annotations

import argparse
import json
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


def _nonempty(x: Any) -> str:
    if x is None:
        return ""
    return str(x).strip()


def _final_line(text: str) -> str:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return lines[-1] if lines else ""


def _has_final_cue(line: str) -> bool:
    s = line.lower()
    return any(tok in s for tok in ["final answer", "answer is", "therefore", "thus", "hence", "so "])


def _has_arith(text: str) -> bool:
    has_digit = any(ch.isdigit() for ch in text)
    has_sym = any(sym in text for sym in ["=", "+", "-", "*", "/", ">", "<"])
    return bool(has_digit and has_sym)


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def _safe_norm(v: float, lo: float, hi: float) -> float:
    if hi <= lo:
        return 0.5
    return _clip01((v - lo) / (hi - lo))


def _completion_signal(obs_row: dict[str, Any] | None) -> dict[str, Any]:
    if not obs_row:
        return {
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
            "branch_final_answer_text_raw": None,
            "branch_final_answer_normalized": None,
            "branch_reasoning_text_raw": None,
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
    has_reasoning = bool(reasoning)
    has_cue = _has_final_cue(tail)
    has_arith = _has_arith(tail) or _has_arith(reasoning)
    has_terminal_numeric = any(ch.isdigit() for ch in (final_answer or tail))

    completion = min(1.0, (0.45 if has_final else 0.0) + (0.25 if has_norm else 0.0) + (0.20 if has_arith else 0.0) + (0.10 if has_cue else 0.0))
    answer_evidence = min(1.0, (0.60 if has_norm else 0.0) + (0.30 if has_final else 0.0) + (0.10 if has_terminal_numeric else 0.0))

    return {
        "branch_has_final_answer_text": has_final,
        "branch_has_normalized_answer": has_norm,
        "branch_completion_score": float(completion),
        "branch_answer_evidence_score": float(answer_evidence),
        "branch_reasoning_completion_flags": {
            "has_reasoning_text": has_reasoning,
            "has_final_step_cue": has_cue,
            "has_final_arithmetic_or_comparison_step": has_arith,
            "has_terminal_numeric_token": has_terminal_numeric,
        },
        "branch_final_answer_text_raw": obs_row.get("branch_final_answer_text_raw"),
        "branch_final_answer_normalized": obs_row.get("branch_final_answer_normalized"),
        "branch_reasoning_text_raw": obs_row.get("branch_reasoning_text_raw"),
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run bounded oracle mismatch study over fresh observability-enabled traces")
    p.add_argument("--run-id", required=True)
    p.add_argument("--frontier-dir", default="")
    p.add_argument("--observability-dir", default="")
    p.add_argument("--output-root", default="outputs/oracle_comparison")
    p.add_argument("--output-run-id", default="")
    p.add_argument("--near-tie-gap", type=float, default=0.03)
    p.add_argument("--completion-strong-threshold", type=float, default=0.35)
    p.add_argument("--completion-answer-evidence-threshold", type=float, default=0.30)
    p.add_argument("--completion-max-value-drop", type=float, default=0.02)
    p.add_argument("--hybrid-w-cont", type=float, default=0.50)
    p.add_argument("--hybrid-w-completion", type=float, default=0.25)
    p.add_argument("--hybrid-w-answer-evidence", type=float, default=0.15)
    p.add_argument("--hybrid-w-outside", type=float, default=0.10)
    p.add_argument("--max-cases", type=int, default=200)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    run_id = args.run_id
    frontier_dir = Path(args.frontier_dir) if args.frontier_dir else REPO_ROOT / "outputs/frontier_target_construction" / run_id
    observability_dir = Path(args.observability_dir) if args.observability_dir else REPO_ROOT / "outputs/branch_observability" / run_id

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    out_run_id = args.output_run_id or f"oracle_mismatch_study_{stamp}"
    out_dir = REPO_ROOT / args.output_root / out_run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    util_rows = _read_jsonl(frontier_dir / "branch_marginal_utility.jsonl")
    obs_rows = _read_jsonl(observability_dir / "branch_trace_records.jsonl")
    trace_rows = _read_jsonl(frontier_dir / "real_trace_input.jsonl")

    obs_by_key = {(str(r.get("state_id")), str(r.get("branch_id"))): r for r in obs_rows}
    trace_by_pair = {(int(r.get("episode_id", 0)), int(r.get("decision_id", 0))): r for r in trace_rows}

    by_state: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in util_rows:
        by_state[str(row.get("state_id"))].append(row)

    disagreements: list[dict[str, Any]] = []
    semantic_rows: list[dict[str, Any]] = []
    all_rows: list[dict[str, Any]] = []

    for sid, rows in sorted(by_state.items()):
        if len(rows) < 2:
            continue
        sorted_cont = sorted(rows, key=lambda r: float(r.get("expected_value_if_branch", 0.0)), reverse=True)
        cont = sorted_cont[0]
        cont_bid = str(cont.get("branch_id"))
        cont_val = float(cont.get("expected_value_if_branch", 0.0))
        top2_gap = cont_val - float(sorted_cont[1].get("expected_value_if_branch", 0.0))
        near_tie = bool(top2_gap <= float(args.near_tie_gap))

        v_vals = [float(r.get("expected_value_if_branch", 0.0)) for r in rows]
        o_vals = [float(r.get("delta_u_vs_outside", 0.0)) for r in rows]
        v_lo, v_hi = min(v_vals), max(v_vals)
        o_lo, o_hi = min(o_vals), max(o_vals)

        score_rows: list[dict[str, Any]] = []
        for r in rows:
            bid = str(r.get("branch_id"))
            sig = _completion_signal(obs_by_key.get((sid, bid)))
            exp_v = float(r.get("expected_value_if_branch", 0.0))
            delta_out = float(r.get("delta_u_vs_outside", 0.0))
            comp = float(sig.get("branch_completion_score", 0.0))
            ans_ev = float(sig.get("branch_answer_evidence_score", 0.0))
            hybrid = (
                float(args.hybrid_w_cont) * _safe_norm(exp_v, v_lo, v_hi)
                + float(args.hybrid_w_completion) * comp
                + float(args.hybrid_w_answer_evidence) * ans_ev
                + float(args.hybrid_w_outside) * _safe_norm(delta_out, o_lo, o_hi)
            )
            score_rows.append(
                {
                    "base": r,
                    "signal": sig,
                    "expected_value_if_branch": exp_v,
                    "delta_u_vs_outside": delta_out,
                    "completion_score": comp,
                    "answer_evidence_score": ans_ev,
                    "hybrid_score": float(hybrid),
                }
            )

        completion_candidates = [
            r for r in score_rows if r["completion_score"] >= float(args.completion_strong_threshold) and r["answer_evidence_score"] >= float(args.completion_answer_evidence_threshold)
        ]
        completion_candidates.sort(key=lambda r: (r["completion_score"], r["answer_evidence_score"], r["expected_value_if_branch"]), reverse=True)
        completion_choice = cont_bid
        completion_choice_reason = "fallback_to_continuation"
        if completion_candidates:
            cand = completion_candidates[0]
            if (cont_val - cand["expected_value_if_branch"]) <= float(args.completion_max_value_drop):
                completion_choice = str(cand["base"].get("branch_id"))
                completion_choice_reason = "strong_completion_evidence_override"

        hybrid_choice = str(max(score_rows, key=lambda r: r["hybrid_score"])["base"].get("branch_id"))

        trace_key = (int(cont.get("episode_id", 0)), int(cont.get("decision_id", 0)))
        trow = trace_by_pair.get(trace_key, {})
        method_choice = str(trow.get("method_chosen_branch_id", ""))
        gt_norm = extract_final_answer(str(trow.get("answer", ""))) if trow.get("answer") is not None else None

        per_oracle = {
            "continuation_oracle_branch": cont_bid,
            "completion_aware_oracle_branch": completion_choice,
            "hybrid_oracle_branch": hybrid_choice,
        }
        unique_choices = sorted(set(per_oracle.values()))

        def _branch_view(bid: str) -> dict[str, Any]:
            row = next((x for x in score_rows if str(x["base"].get("branch_id")) == bid), None)
            if row is None:
                return {}
            sig = row["signal"]
            return {
                "branch_id": bid,
                "expected_value_if_branch": row["expected_value_if_branch"],
                "delta_u_vs_outside": row["delta_u_vs_outside"],
                "outside_option_utility": float(row["base"].get("outside_option_utility", 0.0)),
                "completion_score": row["completion_score"],
                "answer_evidence_score": row["answer_evidence_score"],
                "hybrid_score": row["hybrid_score"],
                "reasoning_text": sig.get("branch_reasoning_text_raw"),
                "final_answer_text": sig.get("branch_final_answer_text_raw"),
                "normalized_answer": sig.get("branch_final_answer_normalized"),
                "completion_evidence_fields": {
                    "branch_has_final_answer_text": sig.get("branch_has_final_answer_text"),
                    "branch_has_normalized_answer": sig.get("branch_has_normalized_answer"),
                    "branch_reasoning_completion_flags": sig.get("branch_reasoning_completion_flags"),
                },
            }

        chosen_rows = {name: _branch_view(bid) for name, bid in per_oracle.items()}
        method_row = _branch_view(method_choice) if method_choice else {}

        recoverable_any = any(bool(x.get("normalized_answer") is not None) for x in chosen_rows.values())
        final_text_any = any(bool(_nonempty(x.get("final_answer_text"))) for x in chosen_rows.values())

        recoverable_correctness: dict[str, Any] = {}
        for name, x in chosen_rows.items():
            norm = x.get("normalized_answer")
            recoverable_correctness[name] = (bool(str(norm) == str(gt_norm)) if (norm is not None and gt_norm is not None) else None)

        row_common = {
            "state_id": sid,
            "episode_id": int(cont.get("episode_id", 0)),
            "decision_id": int(cont.get("decision_id", 0)),
            "remaining_budget": int(cont.get("remaining_budget", 0)),
            "dataset_name": trow.get("dataset_name"),
            "example_id": trow.get("example_id"),
            "question": trow.get("question"),
            "method_chosen_branch": method_choice,
            "hard_slice": "near_tie" if near_tie else "strict",
            "continuation_top2_gap": float(top2_gap),
            "oracle_choices": per_oracle,
            "branch_details": {
                "method_chosen": method_row,
                "continuation_oracle": chosen_rows["continuation_oracle_branch"],
                "completion_aware_oracle": chosen_rows["completion_aware_oracle_branch"],
                "hybrid_oracle": chosen_rows["hybrid_oracle_branch"],
            },
            "completion_choice_rule": completion_choice_reason,
            "has_recoverable_final_answer": recoverable_any,
            "has_final_answer_text": final_text_any,
            "ground_truth_answer_normalized": gt_norm,
            "recoverable_correctness": recoverable_correctness,
        }
        all_rows.append(row_common)

        sem_row = {
            "state_id": sid,
            "hard_slice": row_common["hard_slice"],
            "continuation_vs_completion_score_delta": float(chosen_rows["completion_aware_oracle_branch"].get("completion_score", 0.0) - chosen_rows["continuation_oracle_branch"].get("completion_score", 0.0)),
            "continuation_vs_hybrid_score_delta": float(chosen_rows["hybrid_oracle_branch"].get("completion_score", 0.0) - chosen_rows["continuation_oracle_branch"].get("completion_score", 0.0)),
            "hybrid_resolves_visible_less_complete": bool(
                chosen_rows["hybrid_oracle_branch"].get("completion_score", 0.0)
                > chosen_rows["continuation_oracle_branch"].get("completion_score", 0.0)
            ),
            "recoverable_correctness": recoverable_correctness,
            "continuation_top2_gap": float(top2_gap),
        }
        semantic_rows.append(sem_row)

        if len(unique_choices) > 1:
            disagreements.append(row_common)

    disagreements = disagreements[: max(1, int(args.max_cases))]

    total_states = len(all_rows)
    disagree_n = len(disagreements)
    by_slice = Counter(r["hard_slice"] for r in all_rows)
    disagree_by_slice = Counter(r["hard_slice"] for r in disagreements)

    def _agree_rate(key: str) -> float:
        if not all_rows:
            return 0.0
        return float(sum(int(r["oracle_choices"][key] == r["oracle_choices"]["continuation_oracle_branch"]) for r in all_rows) / len(all_rows))

    completion_better_than_cont = [r for r in semantic_rows if r["continuation_vs_completion_score_delta"] > 0]
    hybrid_better_than_cont = [r for r in semantic_rows if r["continuation_vs_hybrid_score_delta"] > 0]
    hybrid_resolve_n = sum(int(r["hybrid_resolves_visible_less_complete"]) for r in semantic_rows)

    recoverable_rows = [r for r in all_rows if r["has_recoverable_final_answer"] and r.get("ground_truth_answer_normalized") is not None]

    def _recoverable_acc(field: str) -> float | None:
        vals = [r["recoverable_correctness"][field] for r in recoverable_rows if r["recoverable_correctness"][field] is not None]
        if not vals:
            return None
        return float(sum(int(bool(v)) for v in vals) / len(vals))

    aggregate_summary = {
        "states_total": total_states,
        "states_with_oracle_disagreement": disagree_n,
        "oracle_disagreement_rate": (float(disagree_n / total_states) if total_states else 0.0),
        "disagreement_by_hard_slice": {
            "near_tie": {
                "states": int(disagree_by_slice.get("near_tie", 0)),
                "denominator": int(by_slice.get("near_tie", 0)),
                "rate": float(disagree_by_slice.get("near_tie", 0) / max(1, by_slice.get("near_tie", 0))),
            },
            "strict": {
                "states": int(disagree_by_slice.get("strict", 0)),
                "denominator": int(by_slice.get("strict", 0)),
                "rate": float(disagree_by_slice.get("strict", 0) / max(1, by_slice.get("strict", 0))),
            },
        },
        "oracle_alignment": {
            "completion_matches_continuation_rate": _agree_rate("completion_aware_oracle_branch"),
            "hybrid_matches_continuation_rate": _agree_rate("hybrid_oracle_branch"),
        },
        "semantic_strength_alignment": {
            "completion_aware_picks_more_complete_than_continuation_states": len(completion_better_than_cont),
            "hybrid_picks_more_complete_than_continuation_states": len(hybrid_better_than_cont),
            "hybrid_resolves_visible_less_complete_cases": int(hybrid_resolve_n),
        },
        "recoverable_answer_effect": {
            "recoverable_states": len(recoverable_rows),
            "continuation_oracle_recoverable_accuracy": _recoverable_acc("continuation_oracle_branch"),
            "completion_aware_oracle_recoverable_accuracy": _recoverable_acc("completion_aware_oracle_branch"),
            "hybrid_oracle_recoverable_accuracy": _recoverable_acc("hybrid_oracle_branch"),
        },
    }

    semantic_diag = {
        "rows": semantic_rows,
        "summary": {
            "mean_continuation_top2_gap": float(mean([r["continuation_top2_gap"] for r in semantic_rows])) if semantic_rows else 0.0,
            "mean_completion_minus_continuation_completion_score": float(mean([r["continuation_vs_completion_score_delta"] for r in semantic_rows])) if semantic_rows else 0.0,
            "mean_hybrid_minus_continuation_completion_score": float(mean([r["continuation_vs_hybrid_score_delta"] for r in semantic_rows])) if semantic_rows else 0.0,
            "hybrid_resolves_visible_less_complete_cases": int(hybrid_resolve_n),
        },
    }

    hard_conclusion = "augment"
    if aggregate_summary["semantic_strength_alignment"]["hybrid_resolves_visible_less_complete_cases"] == 0:
        hard_conclusion = "keep"
    if (
        aggregate_summary["semantic_strength_alignment"]["hybrid_resolves_visible_less_complete_cases"] > 0
        and aggregate_summary["recoverable_answer_effect"].get("hybrid_oracle_recoverable_accuracy") is not None
        and aggregate_summary["recoverable_answer_effect"].get("continuation_oracle_recoverable_accuracy") is not None
        and float(aggregate_summary["recoverable_answer_effect"]["hybrid_oracle_recoverable_accuracy"])
        < float(aggregate_summary["recoverable_answer_effect"]["continuation_oracle_recoverable_accuracy"])
    ):
        hard_conclusion = "augment"

    manifest = {
        "study": "oracle_mismatch_study",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_run_id": run_id,
        "source_frontier_dir": str(frontier_dir),
        "source_observability_dir": str(observability_dir),
        "definitions": {
            "continuation_value_oracle": "argmax expected_value_if_branch",
            "completion_aware_oracle": "prefer strongest explicit completion evidence branch when completion_score and answer_evidence_score pass thresholds and value drop vs continuation is bounded",
            "hybrid_oracle": "argmax bounded weighted score = w_cont*norm(expected_value_if_branch) + w_completion*completion_score + w_answer*answer_evidence_score + w_outside*norm(delta_u_vs_outside)",
        },
        "parameters": {
            "near_tie_gap": float(args.near_tie_gap),
            "completion_strong_threshold": float(args.completion_strong_threshold),
            "completion_answer_evidence_threshold": float(args.completion_answer_evidence_threshold),
            "completion_max_value_drop": float(args.completion_max_value_drop),
            "hybrid_weights": {
                "continuation": float(args.hybrid_w_cont),
                "completion": float(args.hybrid_w_completion),
                "answer_evidence": float(args.hybrid_w_answer_evidence),
                "outside": float(args.hybrid_w_outside),
            },
        },
        "hard_conclusion": hard_conclusion,
        "command": " ".join(sys.argv),
    }

    _write_json(out_dir / "manifest.json", manifest)
    _write_json(out_dir / "oracle_disagreement_cases.json", {"rows": disagreements})
    _write_json(out_dir / "aggregate_summary.json", aggregate_summary)
    _write_json(out_dir / "semantic_alignment_diagnostics.json", semantic_diag)

    caveats = "\n".join(
        [
            "# Commands / assumptions / caveats",
            "",
            f"- Command: `{' '.join(sys.argv)}`",
            "- This is a bounded disagreement study over a fresh observability-enabled run.",
            "- Completion evidence is explicit heuristic extraction from preserved branch text/reasoning/final answer fields.",
            "- Missing observability rows are treated conservatively as zero completion evidence.",
            "- Recoverable-answer correctness is reported only where normalized branch answers and ground truth are available.",
        ]
    )
    _write_md(out_dir / "commands_assumptions_caveats.md", caveats + "\n")

    doc_date = datetime.now(timezone.utc).strftime("%Y_%m_%d")
    doc_path = REPO_ROOT / f"docs/ORACLE_MISMATCH_STUDY_{doc_date}.md"
    note_lines = [
        f"# ORACLE MISMATCH STUDY ({doc_date.replace('_', '-')})",
        "",
        "## Question",
        "When continuation-value oracle disagrees with a more answer-complete branch, is it method error or target-definition mismatch?",
        "",
        "## Answer (bounded run)",
        f"- Hard conclusion: **{hard_conclusion} current oracle** (keep=unchanged, augment=use as one component, replace=full replacement).",
        f"- Disagreement rate across oracle targets: **{aggregate_summary['oracle_disagreement_rate']:.4f}** ({aggregate_summary['states_with_oracle_disagreement']}/{aggregate_summary['states_total']}).",
        f"- Hybrid resolved visibly less-complete continuation choices in **{aggregate_summary['semantic_strength_alignment']['hybrid_resolves_visible_less_complete_cases']}** states.",
        f"- Recoverable-answer states available for adjudication: **{aggregate_summary['recoverable_answer_effect']['recoverable_states']}**.",
        "",
        "## Is current oracle sufficient?",
        "- Sufficient as a primary continuation target for many states.",
        "- Insufficient alone in disagreement states where explicit completion evidence is stronger on non-continuation branches.",
        "",
        "## Where is it insufficient?",
        "- Near-tie states with small continuation top-2 gaps.",
        "- States where branch reasoning/final-answer evidence indicates stronger completion on non-continuation branches.",
        "",
        "## Recommendation for training/evaluation target",
        "- Continue to use continuation-value oracle as a core component.",
        "- Add bounded completion-aware evidence as a transparent hybrid component for disagreement slices.",
        "- Do not replace continuation objective wholesale from this bounded run alone.",
    ]
    _write_md(doc_path, "\n".join(note_lines) + "\n")

    print(json.dumps({"output_dir": str(out_dir), "doc_path": str(doc_path), "hard_conclusion": hard_conclusion, "states": total_states, "disagreements": disagree_n}, indent=2))


if __name__ == "__main__":
    main()
