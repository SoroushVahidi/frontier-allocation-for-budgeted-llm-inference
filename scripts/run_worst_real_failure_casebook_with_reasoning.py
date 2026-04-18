#!/usr/bin/env python3
"""Bounded real trace-backed worst-failure casebook with branch observability."""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import random
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.branching import APIBranchGenerator, BranchState, SimulatedBranchGenerator
from experiments.data import extract_final_answer
from experiments.frontier_target_construction import FrontierTargetConstructionConfig, run_frontier_target_construction
from experiments.hf_datasets import sample_hf_examples
from experiments.scoring import LearnedBranchScorerV3


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


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


def _safe_score(scorer: LearnedBranchScorerV3, branch: BranchState) -> float:
    return float(scorer.score_branch(branch))


def _snapshot_branch(branch: BranchState, *, provider: str) -> dict[str, Any]:
    reasoning = "\n".join(branch.steps).strip() if branch.steps else None
    final_answer = str(branch.predicted_answer).strip() if branch.predicted_answer is not None else None
    text_raw = None
    if reasoning and final_answer:
        text_raw = f"{reasoning}\nFinal answer: {final_answer}"
    elif reasoning:
        text_raw = reasoning
    elif final_answer:
        text_raw = f"Final answer: {final_answer}"
    return {
        "branch_id": branch.branch_id,
        "score": float(branch.score),
        "depth": int(branch.depth),
        "verify_count": int(branch.verify_count),
        "stalled_steps": int(branch.stalled_steps),
        "recent_delta": float(branch.recent_delta),
        "branch_age": int(branch.branch_age),
        "is_done": int(branch.is_done),
        "is_pruned": int(branch.is_pruned),
        "action_history": list(branch.action_history),
        "score_history": [float(x) for x in branch.score_history],
        "depth_history": [int(x) for x in branch.depth_history],
        "parent_relative_score": 0.0,
        "branch_text_raw": text_raw,
        "branch_reasoning_text_raw": reasoning,
        "branch_final_answer_text_raw": final_answer,
        "generation_metadata": {
            "generator_provider": provider,
            "predicted_answer_present": final_answer is not None,
        },
    }


def _top2_margin(score_map: dict[str, float]) -> float:
    if len(score_map) < 2:
        return 1.0
    vals = sorted(score_map.values(), reverse=True)
    return float(vals[0] - vals[1])


def _run_real_trace(
    *,
    rows: list[dict[str, str]],
    seed: int,
    budget: int,
    init_branches: int,
    max_branches: int,
    provider: str,
    model: str,
    temperature: float,
    max_tokens: int,
    learned_model_path: Path,
    allow_sim_fallback: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rng = random.Random(seed)
    scorer = LearnedBranchScorerV3(str(learned_model_path))
    trace_rows: list[dict[str, Any]] = []
    provider_used = provider
    provider_key_map = {
        "openai": "OPENAI_API_KEY",
        "groq": "GROQ_API_KEY",
        "gemini": "GEMINI_API_KEY",
    }
    api_key = os.getenv(provider_key_map.get(provider, "OPENAI_API_KEY"))

    for ep_idx, row in enumerate(rows):
        question = str(row["question"])
        answer = extract_final_answer(str(row["answer"]))
        example_id = str(row["example_id"])
        branches: list[BranchState] = []
        try:
            for bidx in range(init_branches):
                gen = APIBranchGenerator(
                    api_key=api_key,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    provider=provider,
                )
                branches.append(gen.init_branch(f"b{bidx}"))
            generator = APIBranchGenerator(
                api_key=api_key,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                provider=provider,
            )
        except Exception:
            if not allow_sim_fallback:
                raise
            provider_used = "simulated_fallback"
            generator = SimulatedBranchGenerator(
                rng=random.Random(seed + ep_idx * 17),
                max_depth=7,
                finish_prob_base=0.16,
                answer_noise=0.12,
            )
            branches = [generator.init_branch(f"b{bidx}") for bidx in range(init_branches)]

        for branch in branches:
            try:
                generator.expand(branch, question, answer)
            except Exception:
                if not allow_sim_fallback:
                    raise
                sf_boot = SimulatedBranchGenerator(
                    rng=random.Random(seed + ep_idx * 41 + int(branch.branch_id.replace("b", ""))),
                    max_depth=7,
                    finish_prob_base=0.16,
                    answer_noise=0.12,
                )
                sf_boot.expand(branch, question, answer)

        for decision_id in range(budget):
            active = [b for b in branches if not b.is_done and not b.is_pruned]
            if len(active) < 2:
                break
            for b in active:
                b.branch_age += 1
            score_map = {b.branch_id: _safe_score(scorer, b) for b in active}
            method_branch_id = max(active, key=lambda b: score_map[b.branch_id]).branch_id
            method_margin = _top2_margin(score_map)

            snapshots = [_snapshot_branch(b, provider=provider_used) for b in active[:max_branches]]
            parent_mean = sum(float(x["score"]) for x in snapshots) / max(1, len(snapshots))
            for snap in snapshots:
                snap["parent_relative_score"] = float(snap["score"] - parent_mean)

            trace_rows.append(
                {
                    "episode_id": ep_idx,
                    "decision_id": decision_id,
                    "remaining_budget": budget - decision_id,
                    "split": "test",
                    "dataset_name": "openai/gsm8k",
                    "example_id": example_id,
                    "question": question,
                    "answer": answer,
                    "method_name": "adaptive_learned_branch_score_v3",
                    "method_chosen_branch_id": method_branch_id,
                    "method_score_margin_top2": method_margin,
                    "active_branches": snapshots,
                }
            )

            chosen = next(b for b in active if b.branch_id == method_branch_id)
            try:
                generator.expand(chosen, question, answer)
            except Exception:
                if not allow_sim_fallback:
                    raise
                sf = SimulatedBranchGenerator(
                    rng=random.Random(seed + ep_idx * 97 + decision_id),
                    max_depth=7,
                    finish_prob_base=0.16,
                    answer_noise=0.12,
                )
                sf.expand(chosen, question, answer)

            if (not chosen.is_done) and len(branches) < max_branches and rng.random() < 0.35:
                child = generator.init_branch(f"b{len(branches)}")
                child.score = 0.5 * child.score + 0.5 * chosen.score
                branches.append(child)

    return trace_rows, {"provider_used": provider_used, "trace_rows": len(trace_rows)}


def _build_casebook(
    *,
    run_id: str,
    trace_rows: list[dict[str, Any]],
    frontier_dir: Path,
    observability_dir: Path,
    out_dir: Path,
    top_k: int,
) -> dict[str, Any]:
    frontier_states = _read_jsonl(frontier_dir / "frontier_states.jsonl")
    util_rows = _read_jsonl(frontier_dir / "branch_marginal_utility.jsonl")
    obs_rows = _read_jsonl(observability_dir / "branch_trace_records.jsonl")

    trace_idx = {(int(r["episode_id"]), int(r["decision_id"])): r for r in trace_rows}
    obs_idx = {(str(r["state_id"]), str(r["branch_id"])): r for r in obs_rows}

    by_state: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in util_rows:
        by_state[str(row["state_id"])].append(row)

    ranking_rows: list[dict[str, Any]] = []
    structured_cases: list[dict[str, Any]] = []
    for srow in frontier_states:
        state_id = str(srow["state_id"])
        ep = int(srow["episode_id"])
        did = int(srow["decision_id"])
        source = trace_idx.get((ep, did), {})
        method_id = str(source.get("method_chosen_branch_id", ""))
        if not method_id:
            continue
        candidates = by_state.get(state_id, [])
        if len(candidates) < 2:
            continue
        oracle_row = max(candidates, key=lambda r: float(r.get("expected_value_if_branch", 0.0)))
        oracle_id = str(oracle_row["branch_id"])
        if oracle_id == method_id:
            continue
        method_row = next((r for r in candidates if str(r["branch_id"]) == method_id), None)
        if method_row is None:
            continue

        method_obs = obs_idx.get((state_id, method_id), {})
        oracle_obs = obs_idx.get((state_id, oracle_id), {})
        gt = extract_final_answer(str(source.get("answer", ""))) if source.get("answer") else None
        method_norm = method_obs.get("branch_final_answer_normalized")
        oracle_norm = oracle_obs.get("branch_final_answer_normalized")
        method_correct = (method_norm == gt) if (method_norm is not None and gt is not None) else None
        oracle_correct = (oracle_norm == gt) if (oracle_norm is not None and gt is not None) else None

        oracle_regret = float(oracle_row["expected_value_if_branch"]) - float(method_row["expected_value_if_branch"])
        margin = float(source.get("method_score_margin_top2", 0.0))
        values = sorted([float(r["expected_value_if_branch"]) for r in candidates], reverse=True)
        oracle_top2_gap = float(values[0] - values[1]) if len(values) > 1 else 0.0
        hard_slice = "near_tie" if oracle_top2_gap <= 0.03 else "strict"
        wrong_and_oracle_right = int(method_correct is False and oracle_correct is True)
        ranking_score = float(oracle_regret + 0.35 * margin + 0.25 * wrong_and_oracle_right + (0.1 if hard_slice == "near_tie" else 0.0))
        ranking_rows.append(
            {
                "state_id": state_id,
                "episode_id": ep,
                "decision_id": did,
                "dataset_name": source.get("dataset_name"),
                "example_id": source.get("example_id"),
                "method_name": source.get("method_name"),
                "method_branch_id": method_id,
                "oracle_branch_id": oracle_id,
                "oracle_regret": oracle_regret,
                "method_score_margin_top2": margin,
                "oracle_top2_gap": oracle_top2_gap,
                "hard_slice": hard_slice,
                "method_correct": method_correct,
                "oracle_correct": oracle_correct,
                "ranking_score": ranking_score,
            }
        )

    ranking_rows = sorted(ranking_rows, key=lambda r: float(r["ranking_score"]), reverse=True)
    selected = ranking_rows[:top_k]

    for row in selected:
        sid = str(row["state_id"])
        method_id = str(row["method_branch_id"])
        oracle_id = str(row["oracle_branch_id"])
        source = trace_idx.get((int(row["episode_id"]), int(row["decision_id"])), {})
        method_obs = obs_idx.get((sid, method_id), {})
        oracle_obs = obs_idx.get((sid, oracle_id), {})
        structured_cases.append(
            {
                **row,
                "question": source.get("question"),
                "ground_truth_answer": source.get("answer"),
                "method_branch_reasoning_text": method_obs.get("branch_reasoning_text_raw"),
                "oracle_branch_reasoning_text": oracle_obs.get("branch_reasoning_text_raw"),
                "method_branch_final_answer_text": method_obs.get("branch_final_answer_text_raw"),
                "oracle_branch_final_answer_text": oracle_obs.get("branch_final_answer_text_raw"),
                "method_branch_normalized_answer": method_obs.get("branch_final_answer_normalized"),
                "oracle_branch_normalized_answer": oracle_obs.get("branch_final_answer_normalized"),
                "method_extracted_numbers": method_obs.get("extracted_numbers"),
                "oracle_extracted_numbers": oracle_obs.get("extracted_numbers"),
                "method_branch_role_summary": method_obs.get("branch_role_summary"),
                "oracle_branch_role_summary": oracle_obs.get("branch_role_summary"),
                "method_provenance": method_obs.get("provenance_source"),
                "oracle_provenance": oracle_obs.get("provenance_source"),
                "method_recoverability": method_obs.get("recoverability_flags"),
                "oracle_recoverability": oracle_obs.get("recoverability_flags"),
                "inference_notes": {
                    "branch_role_summary": "inferred_from_branch_metadata",
                    "ranking_score": "computed_from_oracle_regret_margin_and_correctness",
                },
            }
        )

    rec_reason = 0
    rec_final_pair = 0
    for c in structured_cases:
        mr = bool((c.get("method_recoverability") or {}).get("branch_reasoning_text_raw", {}).get("recoverable"))
        orr = bool((c.get("oracle_recoverability") or {}).get("branch_reasoning_text_raw", {}).get("recoverable"))
        mf = bool((c.get("method_recoverability") or {}).get("branch_final_answer_text_raw", {}).get("recoverable"))
        of = bool((c.get("oracle_recoverability") or {}).get("branch_final_answer_text_raw", {}).get("recoverable"))
        if mr and orr:
            rec_reason += 1
        if mf and of:
            rec_final_pair += 1

    recoverability_summary = {
        "selected_cases": len(structured_cases),
        "direct_reasoning_recovery_both_method_and_oracle": rec_reason,
        "direct_final_answer_recovery_both_method_and_oracle": rec_final_pair,
    }

    _write_json(out_dir / "manifest.json", {
        "run_id": run_id,
        "frontier_dir": str(frontier_dir),
        "observability_dir": str(observability_dir),
        "selection_rule": "ranking_score = oracle_regret + 0.35*method_score_margin_top2 + 0.25*wrong_and_oracle_right + near_tie_bonus",
        "top_k": top_k,
    })
    _write_json(out_dir / "selected_case_ids.json", {"case_ids": [str(c["state_id"]) for c in structured_cases]})
    _write_json(out_dir / "worst_failure_ranking_table.json", {"rows": ranking_rows})
    _write_json(out_dir / "rich_failure_cases_structured.json", {"cases": structured_cases})
    _write_json(out_dir / "recoverability_summary.json", recoverability_summary)
    (out_dir / "commands_assumptions_caveats.md").write_text(
        "\n".join(
            [
                "# Commands / assumptions / caveats",
                "",
                "- This casebook is built from a fresh bounded trace-backed run.",
                "- Direct branch text/final answers are used when recoverable from observability bundle.",
                "- Missing fields are left null and interpreted conservatively.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    return {
        "structured_cases": structured_cases,
        "recoverability_summary": recoverability_summary,
        "ranking_rows": ranking_rows,
    }


def _write_markdown_casebook(doc_path: Path, payload: dict[str, Any], *, run_id: str) -> None:
    cases = payload["structured_cases"]
    lines = [
        f"# WORST REAL FAILURE CASEBOOK WITH REASONING ({datetime.now(timezone.utc).strftime('%Y-%m-%d')})",
        "",
        f"- Run ID: `{run_id}`",
        f"- Selected worst failures: `{len(cases)}`",
        "- Canonical framing: fixed-budget branch allocation for next-step compute.",
        "",
        "## Recoverability summary",
        f"- Direct reasoning recovery (method+oracle): {payload['recoverability_summary']['direct_reasoning_recovery_both_method_and_oracle']}/{len(cases)}",
        f"- Direct final-answer recovery (method+oracle): {payload['recoverability_summary']['direct_final_answer_recovery_both_method_and_oracle']}/{len(cases)}",
        "",
    ]
    for idx, case in enumerate(cases, start=1):
        lines.extend(
            [
                f"## Case {idx}: `{case['state_id']}`",
                f"- dataset/example: `{case.get('dataset_name')}` / `{case.get('example_id')}`",
                f"- method: `{case.get('method_name')}` chose `{case.get('method_branch_id')}`; oracle-best `{case.get('oracle_branch_id')}`",
                f"- oracle_regret={case.get('oracle_regret'):.6f}, method_margin_top2={case.get('method_score_margin_top2'):.6f}, hard_slice={case.get('hard_slice')}",
                f"- Full problem: {case.get('question')}",
                f"- Ground truth answer: `{case.get('ground_truth_answer')}`",
                f"- Method branch final answer text (direct): `{case.get('method_branch_final_answer_text')}`",
                f"- Oracle branch final answer text (direct): `{case.get('oracle_branch_final_answer_text')}`",
                f"- Method normalized answer: `{case.get('method_branch_normalized_answer')}`",
                f"- Oracle normalized answer: `{case.get('oracle_branch_normalized_answer')}`",
                f"- Method reasoning text (direct): {case.get('method_branch_reasoning_text')}",
                f"- Oracle reasoning text (direct): {case.get('oracle_branch_reasoning_text')}",
                f"- Method extracted numbers: `{case.get('method_extracted_numbers')}`",
                f"- Oracle extracted numbers: `{case.get('oracle_extracted_numbers')}`",
                f"- Divergence: method selected `{case.get('method_branch_id')}` under higher learned margin while oracle rollout target preferred `{case.get('oracle_branch_id')}` with higher expected value.",
                f"- Design lesson: penalize high-confidence selection when branch-level answer evidence is weak or lagging against oracle-immediate value.",
                "",
            ]
        )
    doc_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run bounded worst real failure casebook with observability")
    p.add_argument("--dataset-name", default="openai/gsm8k")
    p.add_argument("--dataset-split", default="test")
    p.add_argument("--subset-size", type=int, default=6)
    p.add_argument("--seed", type=int, default=19)
    p.add_argument("--budget", type=int, default=5)
    p.add_argument("--init-branches", type=int, default=3)
    p.add_argument("--max-branches", type=int, default=4)
    p.add_argument("--provider", default="openai")
    p.add_argument("--model", default="gpt-4.1-mini")
    p.add_argument("--temperature", type=float, default=0.2)
    p.add_argument("--max-output-tokens", type=int, default=220)
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument("--allow-sim-fallback", action="store_true")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    date_tag = datetime.now(timezone.utc).strftime("%Y%m%d")
    run_id = datetime.now(timezone.utc).strftime(f"worst_real_failure_observability_{date_tag}T%H%M%SZ")

    rows = sample_hf_examples(
        dataset_name=args.dataset_name,
        pilot_size=args.subset_size,
        seed=args.seed,
        split=args.dataset_split,
        config_name="main",
    )

    learned_model_path = REPO_ROOT / "outputs/branch_scorer_v3_final_eval/selected_best_learned_model.json"
    trace_rows, trace_meta = _run_real_trace(
        rows=rows,
        seed=args.seed,
        budget=args.budget,
        init_branches=args.init_branches,
        max_branches=args.max_branches,
        provider=args.provider,
        model=args.model,
        temperature=args.temperature,
        max_tokens=args.max_output_tokens,
        learned_model_path=learned_model_path,
        allow_sim_fallback=bool(args.allow_sim_fallback),
    )
    if not trace_rows:
        raise SystemExit("No trace rows were captured; cannot continue.")

    frontier_out = REPO_ROOT / "outputs/frontier_target_construction" / run_id
    trace_path = frontier_out / "real_trace_input.jsonl"
    _write_jsonl(trace_path, trace_rows)
    cfg = FrontierTargetConstructionConfig(
        episodes=max(1, args.subset_size),
        decision_budget=args.budget,
        n_init_branches=args.init_branches,
        max_branches_per_state=args.max_branches,
        rollouts_per_branch=6,
        seed=args.seed,
        train_ratio=0.0,
    )
    result = run_frontier_target_construction(cfg, output_dir=frontier_out, trace_jsonl=trace_path)

    observability_dir = REPO_ROOT / "outputs/branch_observability" / run_id
    casebook_out = REPO_ROOT / f"outputs/branch_label_bruteforce_learning/worst_real_failure_casebook_with_reasoning_{date_tag}"
    payload = _build_casebook(
        run_id=run_id,
        trace_rows=trace_rows,
        frontier_dir=frontier_out,
        observability_dir=observability_dir,
        out_dir=casebook_out,
        top_k=args.top_k,
    )

    doc_path = REPO_ROOT / f"docs/WORST_REAL_FAILURE_CASEBOOK_WITH_REASONING_{date_tag}.md"
    _write_markdown_casebook(doc_path, payload, run_id=run_id)
    _write_json(casebook_out / "run_summary.json", {
        "run_id": run_id,
        "frontier_output_dir": str(frontier_out),
        "observability_output_dir": str(observability_dir),
        "casebook_output_dir": str(casebook_out),
        "trace_meta": trace_meta,
        "frontier_summary": result["summary"],
        "recoverability_summary": payload["recoverability_summary"],
    })
    print(json.dumps({
        "run_id": run_id,
        "frontier_output_dir": str(frontier_out),
        "observability_output_dir": str(observability_dir),
        "casebook_output_dir": str(casebook_out),
        "doc_path": str(doc_path),
        "recoverability_summary": payload["recoverability_summary"],
    }, indent=2))


if __name__ == "__main__":
    main()
