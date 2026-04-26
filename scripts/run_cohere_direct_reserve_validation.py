#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.frontier_matrix_core import build_frontier_strategies, generator_factory_for_mode
from experiments.output_layer_repair import canonicalize_answer

STRICT_F3_RUNTIME = (
    "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_"
    "repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth3_coverage_forced_v1"
)
DEFAULT_METHODS = "strict_f3,external_l1_max,direct_reserve_strong_v1,direct_reserve_strong_plus_diverse_v1"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Small Cohere validation for direct_reserve_strong_plus_diverse_v1")
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    p.add_argument("--provider", default="cohere")
    p.add_argument("--model", default="command-r-plus-08-2024")
    p.add_argument("--dataset", default="openai/gsm8k")
    p.add_argument("--methods", default=DEFAULT_METHODS)
    p.add_argument("--budgets", default="4")
    p.add_argument("--seeds", default="23")
    p.add_argument("--absent-count", type=int, default=4)
    p.add_argument("--present-count", type=int, default=4)
    p.add_argument("--control-count", type=int, default=4)
    p.add_argument("--max-cases", type=int, default=12)
    p.add_argument("--loss-artifact-glob", default="outputs/*/per_case_results.csv")
    p.add_argument("--loss-artifact", action="append", default=[])
    p.add_argument("--exclude-previous-output", action="append", default=[])
    p.add_argument("--selection-seed", type=int, default=23)
    p.add_argument("--temperature", type=float, default=0.2)
    p.add_argument("--max-output-tokens", type=int, default=768)
    p.add_argument("--timeout-seconds", type=int, default=90)
    p.add_argument("--emit-full-traces", action="store_true")
    p.add_argument("--resume", action="store_true")
    p.add_argument("--run-real-api", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--include-method", action="append", default=[])
    p.add_argument("--reuse-planned-cases", default="")
    p.add_argument(
        "--scorer-dataset-extended",
        action="store_true",
        help="Allow up to 30 planned rows for direct-reserve scorer data collection (still budget 4 only; diagnostic).",
    )
    return p.parse_args()


def _parse_int_list(text: str) -> list[int]:
    return [int(x.strip()) for x in str(text).split(",") if x.strip()]


def _norm_answer(raw: Any, dataset: str) -> str:
    txt = str(raw or "").strip()
    if not txt:
        return "NA"
    try:
        return str(canonicalize_answer(txt, dataset=dataset))
    except Exception:
        return txt


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        for r in rows:
            for k in r:
                if k not in fieldnames:
                    fieldnames.append(str(k))
        if not fieldnames:
            fieldnames = ["empty"]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _infer_stratum(row: dict[str, str]) -> str:
    absent = str(row.get("absent_from_tree", "")).strip().lower() in {"1", "true", "yes"}
    present_not_selected = str(row.get("present_not_selected", "")).strip().lower() in {"1", "true", "yes"}
    is_correct = str(row.get("is_correct", "")).strip().lower() in {"1", "true", "yes"}
    failure_type = str(row.get("failure_type", "")).strip().lower()
    if absent or "absent" in failure_type:
        return "absent_from_tree"
    if present_not_selected or "present_not_selected" in failure_type:
        return "present_not_selected"
    if is_correct or failure_type in {"", "correct", "none", "na"}:
        return "control_correct"
    return "unknown"


def _collect_pool(paths: list[Path], dataset: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for p in paths:
        for r in _read_csv(p):
            ds = str(r.get("dataset") or dataset).strip()
            if ds != dataset:
                continue
            q = str(r.get("question") or r.get("problem") or r.get("prompt") or "").strip()
            graw = str(r.get("gold_answer") or r.get("ground_truth") or r.get("answer") or r.get("target") or "").strip()
            eid = str(r.get("example_id") or r.get("id") or r.get("problem_id") or "").strip()
            if not eid or not q or not graw:
                continue
            out.append(
                {
                    "example_id": eid,
                    "dataset": ds,
                    "question": q,
                    "gold_answer_raw": graw,
                    "gold_answer": _norm_answer(graw, ds),
                    "stratum": _infer_stratum(r),
                    "source_path": str(p),
                }
            )
    return out


def _collect_excluded_ids(paths: list[str]) -> set[str]:
    out: set[str] = set()
    for root in paths:
        rp = REPO_ROOT / root
        if not rp.exists():
            continue
        for name in ["planned_cases.csv", "per_case_method_results.csv", "per_case_candidates.csv", "ten_case_inputs.csv"]:
            f = rp / name
            for r in _read_csv(f):
                eid = str(r.get("example_id", "")).strip()
                if eid:
                    out.add(eid)
    return out


def _sample_cases(rows: list[dict[str, Any]], absent_count: int, present_count: int, control_count: int, max_cases: int, seed: int) -> tuple[list[dict[str, Any]], dict[str, int]]:
    rng = random.Random(seed)
    uniq: dict[str, dict[str, Any]] = {}
    for r in rows:
        if r["example_id"] not in uniq:
            uniq[r["example_id"]] = r
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in uniq.values():
        buckets[str(r.get("stratum", "unknown"))].append(r)
    for b in buckets.values():
        rng.shuffle(b)

    chosen: list[dict[str, Any]] = []
    for key, need in [("absent_from_tree", absent_count), ("present_not_selected", present_count), ("control_correct", control_count)]:
        chosen.extend(buckets.get(key, [])[: max(0, need)])
    selected_ids = {r["example_id"] for r in chosen}
    fallback = [r for r in uniq.values() if r["example_id"] not in selected_ids]
    rng.shuffle(fallback)
    if len(chosen) < max_cases:
        chosen.extend(fallback[: max_cases - len(chosen)])
    chosen = chosen[:max_cases]
    counts = Counter(str(r.get("stratum", "unknown")) for r in chosen)
    return chosen, dict(counts)


def _entropy(counts: list[int]) -> float:
    total = sum(counts)
    if total <= 0:
        return 0.0
    e = 0.0
    for c in counts:
        if c <= 0:
            continue
        p = c / total
        e -= p * math.log(p, 2)
    return e


def main() -> None:
    args = parse_args()
    if args.provider != "cohere":
        raise SystemExit("This script supports provider=cohere only.")
    max_allowed = 30 if args.scorer_dataset_extended else 12
    if args.max_cases > max_allowed:
        raise SystemExit(
            f"Refusing run: max-cases must be <= {max_allowed}"
            f" (use --scorer-dataset-extended to allow up to 30 for scorer data collection)"
        )

    run_id = f"cohere_direct_reserve_validation_{args.timestamp}"
    out_dir = REPO_ROOT / "outputs" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    methods = [m.strip() for m in str(args.methods).split(",") if m.strip()]
    for extra in args.include_method:
        em = str(extra).strip()
        if em and em not in methods:
            methods.append(em)
    required_base = ["strict_f3", "external_l1_max", "direct_reserve_strong_v1", "direct_reserve_strong_plus_diverse_v1"]
    for req in required_base:
        if req not in methods:
            raise SystemExit(f"Methods must include baseline set: {','.join(required_base)}")

    budgets = _parse_int_list(args.budgets)
    seeds = _parse_int_list(args.seeds)
    if budgets != [4]:
        print(f"WARN: budgets={budgets}; default bounded policy is budget 4 only.")

    loss_paths = [Path(p) for p in args.loss_artifact]
    loss_paths.extend(sorted(REPO_ROOT.glob(args.loss_artifact_glob)))
    loss_paths = [p for p in loss_paths if p.exists()]

    pool = _collect_pool(loss_paths, dataset=args.dataset)
    excluded_ids = _collect_excluded_ids(args.exclude_previous_output)
    pool_excluded = [r for r in pool if r["example_id"] not in excluded_ids]
    selected_base: list[dict[str, Any]] = []
    if str(args.reuse_planned_cases).strip():
        planned_src = Path(str(args.reuse_planned_cases))
        if not planned_src.exists():
            raise SystemExit(f"--reuse-planned-cases not found: {planned_src}")
        reused = _read_csv(planned_src)
        for i, r in enumerate(reused[: args.max_cases], start=1):
            selected_base.append(
                {
                    "example_id": str(r.get("example_id", "")).strip(),
                    "dataset": str(r.get("dataset") or args.dataset).strip(),
                    "question": str(r.get("question", "")).strip(),
                    "gold_answer_raw": str(r.get("gold_answer_raw") or r.get("gold_answer") or "").strip(),
                    "gold_answer": str(r.get("gold_answer") or _norm_answer(r.get("gold_answer_raw", ""), str(r.get("dataset") or args.dataset))),
                    "stratum": str(r.get("stratum", "unknown")).strip() or "unknown",
                    "source_path": str(planned_src),
                }
            )
        stratum_counts = dict(Counter(str(r.get("stratum", "unknown")) for r in selected_base))
    else:
        selected_base, stratum_counts = _sample_cases(
            pool_excluded if pool_excluded else pool,
            absent_count=args.absent_count,
            present_count=args.present_count,
            control_count=args.control_count,
            max_cases=args.max_cases,
            seed=args.selection_seed,
        )
    if not selected_base:
        raise SystemExit("No cases available for planning; provide loss artifacts with question and gold answers.")

    planned: list[dict[str, Any]] = []
    idx = 0
    for c in selected_base:
        for s in seeds:
            for b in budgets:
                idx += 1
                planned.append(
                    {
                        "case_idx": idx,
                        "example_id": c["example_id"],
                        "dataset": c["dataset"],
                        "question": c["question"],
                        "gold_answer_raw": c["gold_answer_raw"],
                        "gold_answer": c["gold_answer"],
                        "seed": s,
                        "budget": b,
                        "stratum": c.get("stratum", "unknown"),
                        "source_path": c.get("source_path", ""),
                        "excluded_overlap": int(c["example_id"] in excluded_ids),
                    }
                )

    key_present = bool(os.getenv("COHERE_API_KEY"))
    if args.run_real_api and not key_present:
        raise SystemExit("COHERE_API_KEY missing: refusing real API run.")
    real_api_enabled = bool(args.run_real_api and not args.dry_run and key_present)
    effective_dry = bool(args.dry_run or not real_api_enabled)

    manifest = {
        "run_id": run_id,
        "timestamp": args.timestamp,
        "provider": args.provider,
        "model": args.model,
        "dataset": args.dataset,
        "methods": methods,
        "budgets": budgets,
        "seeds": seeds,
        "max_cases": args.max_cases,
        "requested_strata": {
            "absent_from_tree": args.absent_count,
            "present_not_selected": args.present_count,
            "control_correct": args.control_count,
        },
        "planned_strata": stratum_counts,
        "n_unique_examples": len({r["example_id"] for r in planned}),
        "excluded_ids_count": len(excluded_ids),
        "loss_artifact_paths": [str(p) for p in loss_paths],
        "exclude_previous_output": args.exclude_previous_output,
        "run_real_api_requested": bool(args.run_real_api),
        "real_api_enabled": bool(real_api_enabled),
        "dry_run": bool(effective_dry),
        "emit_full_traces": bool(args.emit_full_traces),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    _write_csv(out_dir / "planned_cases.csv", planned)

    controllers_by_budget: dict[int, dict[str, Any]] = {}
    if real_api_enabled:
        for b in budgets:
            rng = random.Random(args.selection_seed + b)
            factory = generator_factory_for_mode(
                use_openai_api=True,
                rng=rng,
                openai_model=args.model,
                temperature=args.temperature,
                max_output_tokens=args.max_output_tokens,
                timeout_seconds=args.timeout_seconds,
                api_provider="cohere",
            )
            specs = build_frontier_strategies(
                generator_factory=factory,
                budget=b,
                adaptive_min_expand_grid=[1],
                rng=rng,
                use_openai_api=True,
                include_broad_diversity_aggregation_methods=True,
                include_external_l1_baseline=True,
            )
            for ctrl in specs.values():
                setattr(ctrl, "emit_full_traces", bool(args.emit_full_traces))
            controllers_by_budget[b] = specs

    per_case_method_results: list[dict[str, Any]] = []
    candidate_branch_table: list[dict[str, Any]] = []
    answer_group_summary: list[dict[str, Any]] = []
    action_trace_jsonl: list[dict[str, Any]] = []
    final_branch_states_jsonl: list[dict[str, Any]] = []
    tree_decision_jsonl: list[dict[str, Any]] = []

    by_case_method_rows: dict[tuple[str, int, int, str], list[dict[str, Any]]] = defaultdict(list)

    for row in planned:
        for method in methods:
            runtime = STRICT_F3_RUNTIME if method == "strict_f3" else method
            metadata: dict[str, Any] = {}
            final_answer = "NA"
            selected_norm = "NA"
            is_correct = 0
            actions = expansions = verifications = 0
            failure = "dry_run_trace"

            if real_api_enabled:
                ctrl = controllers_by_budget.get(int(row["budget"]), {}).get(runtime)
                if ctrl is None:
                    failure = "method_not_available"
                else:
                    res = ctrl.run(str(row["question"]), str(row["gold_answer_raw"]))
                    metadata = res.metadata or {}
                    final_answer = str(res.prediction or "NA")
                    selected_norm = _norm_answer(final_answer, dataset=str(row["dataset"]))
                    is_correct = int(bool(res.is_correct))
                    actions = int(getattr(res, "actions_used", 0) or 0)
                    expansions = int(getattr(res, "expansions", 0) or 0)
                    verifications = int(getattr(res, "verifications", 0) or 0)
                    failure = str(metadata.get("early_divergence_failure_category") or metadata.get("regime_failure_category") or ("correct" if is_correct else "unknown"))

            branches = list(metadata.get("final_branch_states", []))
            if not branches:
                branches = [{"branch_id": "final_prediction", "parent_branch_id": "", "branch_depth": 0, "predicted_answer": final_answer, "group_key": "", "selected": 1}]

            gold = str(row["gold_answer"])
            group_counts: Counter[str] = Counter()
            selected_group = "NA"
            present = 0
            selected_gold = 0
            for bi, b in enumerate(branches):
                ans_raw = str(b.get("predicted_answer") or b.get("final_answer") or b.get("answer") or "NA")
                ans_norm = _norm_answer(ans_raw, dataset=str(row["dataset"]))
                group_key = _norm_answer(b.get("group_key") or ans_raw, dataset=str(row["dataset"]))
                is_selected = int(str(b.get("selected", "0")).strip().lower() in {"1", "true", "yes"})
                if is_selected:
                    selected_group = group_key
                group_counts[group_key] += 1
                is_gold_group = int(group_key == gold)
                present = max(present, is_gold_group)
                selected_gold = max(selected_gold, int(is_selected and is_gold_group))

                cb = {
                    "case_idx": row["case_idx"],
                    "example_id": row["example_id"],
                    "dataset": row["dataset"],
                    "question": row["question"],
                    "stratum": row.get("stratum", "unknown"),
                    "seed": row["seed"],
                    "budget": row["budget"],
                    "provider": args.provider,
                    "model": args.model,
                    "method": method,
                    "runtime_method": runtime,
                    "branch_index": bi,
                    "branch_id": str(b.get("branch_id", f"b{bi}")),
                    "parent_branch_id": str(b.get("parent_branch_id", "")),
                    "branch_depth": int(b.get("branch_depth", 0) or 0),
                    "branch_prompt_style": str(b.get("strategy_family") or b.get("source") or "NA"),
                    "reasoning_text": str(b.get("reasoning_text", "NA")),
                    "raw_branch_text": str(b.get("steps", "NA")),
                    "predicted_answer": ans_raw,
                    "normalized_candidate_answer": ans_norm,
                    "answer_group": group_key,
                    "is_selected": is_selected,
                    "is_gold_group": is_gold_group,
                    "gold_answer": gold,
                    "operation_sequence": str(b.get("operation_sequence_key", "NA")),
                    "intermediate_values": str(b.get("intermediate_values", "NA")),
                    "reasoning_role": str(b.get("reasoning_role", "NA")),
                    "useful_reasoning_diversity_bonus": b.get("useful_reasoning_diversity_bonus", "NA"),
                }
                candidate_branch_table.append(cb)
                by_case_method_rows[(str(row["example_id"]), int(row["seed"]), int(row["budget"]), method)].append(cb)

            top_group, top_count = ("NA", 0)
            second_count = 0
            if group_counts:
                ordered = sorted(group_counts.items(), key=lambda kv: (-kv[1], kv[0]))
                top_group, top_count = ordered[0]
                second_count = ordered[1][1] if len(ordered) > 1 else 0
            total_groups_support = sum(group_counts.values())
            top2_support_gap = float((top_count - second_count) / max(1, total_groups_support))
            answer_entropy = _entropy(list(group_counts.values()))

            for g, s in sorted(group_counts.items(), key=lambda kv: (-kv[1], kv[0])):
                answer_group_summary.append(
                    {
                        "case_idx": row["case_idx"],
                        "example_id": row["example_id"],
                        "seed": row["seed"],
                        "budget": row["budget"],
                        "method": method,
                        "stratum": row.get("stratum", "unknown"),
                        "answer_group": g,
                        "support": s,
                        "is_gold_group": int(g == gold),
                        "is_selected_group": int(g == selected_group),
                    }
                )

            per_case_method_results.append(
                {
                    "case_idx": row["case_idx"],
                    "example_id": row["example_id"],
                    "dataset": row["dataset"],
                    "question": row["question"],
                    "stratum": row.get("stratum", "unknown"),
                    "seed": row["seed"],
                    "budget": row["budget"],
                    "provider": args.provider,
                    "model": args.model,
                    "method": method,
                    "runtime_method": runtime,
                    "gold_answer": gold,
                    "final_selected_answer": final_answer,
                    "normalized_selected_answer": selected_norm,
                    "is_correct": is_correct,
                    "gold_present": present,
                    "gold_selected": selected_gold,
                    "present_not_selected": int(present and not selected_gold),
                    "absent_from_pool": int(not present),
                    "candidate_branch_count": len(branches),
                    "answer_group_count": len(group_counts),
                    "top_answer_group": top_group,
                    "selected_answer_group": selected_group,
                    "top2_support_gap": top2_support_gap,
                    "answer_entropy": answer_entropy,
                    "action_count": actions,
                    "expansion_count": expansions,
                    "verification_count": verifications,
                    "token_estimate": metadata.get("generated_tokens_estimate", "NA"),
                    "cost_estimate": metadata.get("estimated_cost", "NA"),
                    "latency_seconds": metadata.get("latency_seconds", "NA"),
                    "margin_gate_triggered": int(bool(metadata.get("margin_gate_triggered", False))),
                    "fallback_used": int(bool(metadata.get("fallback_used", False))),
                    "fallback_source": metadata.get("fallback_source", "NA"),
                    "support_margin": metadata.get("support_margin", "NA"),
                    "num_answer_groups": metadata.get("num_answer_groups", "NA"),
                    "prompt_style_agreement": metadata.get("prompt_style_agreement", "NA"),
                    "selected_before_gate": metadata.get("selected_before_gate", "NA"),
                    "selected_after_gate": metadata.get("selected_after_gate", "NA"),
                    "gate_reason": metadata.get("gate_reason", "NA"),
                    "failure_type": failure,
                }
            )

            action_trace_jsonl.append(
                {
                    "case_idx": row["case_idx"],
                    "example_id": row["example_id"],
                    "seed": row["seed"],
                    "budget": row["budget"],
                    "method": method,
                    "action_trace": metadata.get("action_trace", []),
                }
            )
            final_branch_states_jsonl.append(
                {
                    "case_idx": row["case_idx"],
                    "example_id": row["example_id"],
                    "seed": row["seed"],
                    "budget": row["budget"],
                    "method": method,
                    "final_branch_states": branches,
                }
            )
            tree_decision_jsonl.append(
                {
                    "case_idx": row["case_idx"],
                    "example_id": row["example_id"],
                    "seed": row["seed"],
                    "budget": row["budget"],
                    "method": method,
                    "tree_of_decisions": metadata.get("decision_trace", metadata.get("action_trace", [])),
                    "selection_rationale": metadata.get("selection_rationale", "NA"),
                }
            )

    _write_csv(out_dir / "per_case_method_results.csv", per_case_method_results)
    _write_csv(out_dir / "candidate_branch_table.csv", candidate_branch_table)
    _write_csv(out_dir / "answer_group_summary.csv", answer_group_summary)
    _write_jsonl(out_dir / "action_trace.jsonl", action_trace_jsonl)
    _write_jsonl(out_dir / "final_branch_states.jsonl", final_branch_states_jsonl)
    _write_jsonl(out_dir / "tree_decision_traces.jsonl", tree_decision_jsonl)

    # summaries
    per_method_summary: list[dict[str, Any]] = []
    by_method: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in per_case_method_results:
        by_method[str(r["method"])].append(r)
    for method, rows in sorted(by_method.items()):
        n = len(rows)
        per_method_summary.append(
            {
                "method": method,
                "n_cases": n,
                "gold_present_count": sum(int(r["gold_present"]) for r in rows),
                "gold_present_rate": sum(int(r["gold_present"]) for r in rows) / max(1, n),
                "selected_gold_count": sum(int(r["gold_selected"]) for r in rows),
                "selected_gold_rate": sum(int(r["gold_selected"]) for r in rows) / max(1, n),
                "present_not_selected_count": sum(int(r["present_not_selected"]) for r in rows),
                "absent_from_pool_count": sum(int(r["absent_from_pool"]) for r in rows),
                "avg_candidate_branches": sum(float(r["candidate_branch_count"]) for r in rows) / max(1, n),
            }
        )
    _write_csv(out_dir / "per_method_summary.csv", per_method_summary)

    per_stratum_summary: list[dict[str, Any]] = []
    by_ms: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for r in per_case_method_results:
        by_ms[(str(r["method"]), str(r["stratum"]))].append(r)
    for (method, stratum), rows in sorted(by_ms.items()):
        n = len(rows)
        per_stratum_summary.append(
            {
                "method": method,
                "stratum": stratum,
                "n_cases": n,
                "gold_present_count": sum(int(r["gold_present"]) for r in rows),
                "selected_gold_count": sum(int(r["gold_selected"]) for r in rows),
                "selected_gold_rate": sum(int(r["gold_selected"]) for r in rows) / max(1, n),
                "control_degradation_count": sum(int(r["is_correct"]) == 0 and stratum == "control_correct" for r in rows),
            }
        )
    _write_csv(out_dir / "per_stratum_summary.csv", per_stratum_summary)

    coverage_summary = [
        {
            "n_unique_examples": len({r["example_id"] for r in planned}),
            "n_case_method_rows": len(per_case_method_results),
            "n_candidate_rows": len(candidate_branch_table),
            "n_answer_group_rows": len(answer_group_summary),
            "real_api_enabled": int(real_api_enabled),
            "overlap_with_excluded_previous_count": sum(1 for r in planned if int(r.get("excluded_overlap", 0)) == 1),
        }
    ]
    _write_csv(out_dir / "coverage_summary.csv", coverage_summary)

    # loss/difference cases centered on direct_reserve_strong_plus_diverse_v1
    index = {(r["example_id"], int(r["seed"]), int(r["budget"]), r["method"]): r for r in per_case_method_results}
    req_fields = [
        "problem_statement", "all_candidate_final_answers", "normalized_answer_groups", "support_counts", "branch_ids", "branch_parent_ids",
        "branch_depths", "branch_prompt_style", "raw_branch_text", "extracted_answer_per_branch", "operation_sequence", "intermediate_values",
        "reasoning_role_signature", "useful_reasoning_diversity_features", "action_trace", "final_branch_states", "tree_of_decisions", "selection_rationale_metadata", "token_cost_latency_fields"
    ]

    loss_cases: list[dict[str, Any]] = []
    diff_cases: list[dict[str, Any]] = []
    missing_counter: Counter[str] = Counter()

    for p in planned:
        key = (p["example_id"], int(p["seed"]), int(p["budget"]))
        dr = index.get((key[0], key[1], key[2], "direct_reserve_strong_plus_diverse_v1"))
        ex = index.get((key[0], key[1], key[2], "external_l1_max"))
        sf = index.get((key[0], key[1], key[2], "strict_f3"))
        if dr is None:
            continue

        cands = by_case_method_rows.get((key[0], key[1], key[2], "direct_reserve_strong_plus_diverse_v1"), [])
        support = Counter(str(c.get("answer_group", "NA")) for c in cands)
        top_group = sorted(support.items(), key=lambda kv: (-kv[1], kv[0]))[0][0] if support else "NA"
        top = sorted(support.values(), reverse=True)
        top2_gap = float((top[0] - (top[1] if len(top) > 1 else 0)) / max(1, sum(top))) if top else 0.0

        failure_type = "other"
        if int(dr.get("absent_from_pool", 0)) == 1:
            failure_type = "gold_absent"
        elif int(dr.get("present_not_selected", 0)) == 1:
            failure_type = "present_not_selected"
        elif int(dr.get("is_correct", 0)) == 0 and int(ex.get("is_correct", 0) if ex else 0) == 1:
            failure_type = "external_only_correct"
        elif int(dr.get("is_correct", 0)) == 0 and int(sf.get("is_correct", 0) if sf else 0) == 1:
            failure_type = "strict_f3_only_correct"
        elif int(dr.get("is_correct", 0)) == 0 and int(ex.get("is_correct", 0) if ex else 0) == 0 and int(sf.get("is_correct", 0) if sf else 0) == 0:
            failure_type = "all_wrong"
        elif str(p.get("stratum")) == "control_correct" and int(dr.get("is_correct", 0)) == 0:
            failure_type = "control_degradation"

        base = {
            "example_id": key[0],
            "seed": key[1],
            "budget": key[2],
            "stratum": p.get("stratum", "unknown"),
            "problem_statement": p.get("question", "NA"),
            "gold_answer": p.get("gold_answer", "NA"),
            "method_final_answer": dr.get("final_selected_answer", "NA"),
            "external_final_answer": ex.get("final_selected_answer", "NA") if ex else "NA",
            "strict_f3_final_answer": sf.get("final_selected_answer", "NA") if sf else "NA",
            "all_candidate_final_answers": json.dumps([c.get("predicted_answer", "NA") for c in cands], ensure_ascii=False),
            "normalized_answer_groups": json.dumps(sorted(support.keys()), ensure_ascii=False),
            "support_counts": json.dumps(dict(support), ensure_ascii=False),
            "top_answer_group": top_group,
            "selected_answer_group": dr.get("selected_answer_group", "NA"),
            "top2_support_gap": top2_gap,
            "answer_entropy": _entropy(list(support.values())),
            "branch_ids": json.dumps([c.get("branch_id", "NA") for c in cands], ensure_ascii=False),
            "branch_parent_ids": json.dumps([c.get("parent_branch_id", "NA") for c in cands], ensure_ascii=False),
            "branch_depths": json.dumps([c.get("branch_depth", "NA") for c in cands], ensure_ascii=False),
            "branch_prompt_style": json.dumps([c.get("branch_prompt_style", "NA") for c in cands], ensure_ascii=False),
            "raw_branch_text": json.dumps([c.get("raw_branch_text", "NA") for c in cands], ensure_ascii=False),
            "extracted_answer_per_branch": json.dumps([c.get("normalized_candidate_answer", "NA") for c in cands], ensure_ascii=False),
            "operation_sequence": json.dumps([c.get("operation_sequence", "NA") for c in cands], ensure_ascii=False),
            "intermediate_values": json.dumps([c.get("intermediate_values", "NA") for c in cands], ensure_ascii=False),
            "reasoning_role_signature": json.dumps([c.get("reasoning_role", "NA") for c in cands], ensure_ascii=False),
            "useful_reasoning_diversity_features": json.dumps([c.get("useful_reasoning_diversity_bonus", "NA") for c in cands], ensure_ascii=False),
            "action_trace": json.dumps(next((r.get("action_trace", []) for r in action_trace_jsonl if r["example_id"] == key[0] and int(r["seed"]) == key[1] and int(r["budget"]) == key[2] and r["method"] == "direct_reserve_strong_plus_diverse_v1"), []), ensure_ascii=False),
            "final_branch_states": json.dumps(next((r.get("final_branch_states", []) for r in final_branch_states_jsonl if r["example_id"] == key[0] and int(r["seed"]) == key[1] and int(r["budget"]) == key[2] and r["method"] == "direct_reserve_strong_plus_diverse_v1"), []), ensure_ascii=False),
            "tree_of_decisions": json.dumps(next((r.get("tree_of_decisions", []) for r in tree_decision_jsonl if r["example_id"] == key[0] and int(r["seed"]) == key[1] and int(r["budget"]) == key[2] and r["method"] == "direct_reserve_strong_plus_diverse_v1"), []), ensure_ascii=False),
            "selection_rationale_metadata": json.dumps(next((r.get("selection_rationale", "NA") for r in tree_decision_jsonl if r["example_id"] == key[0] and int(r["seed"]) == key[1] and int(r["budget"]) == key[2] and r["method"] == "direct_reserve_strong_plus_diverse_v1"), "NA"), ensure_ascii=False),
            "token_cost_latency_fields": json.dumps({"token_estimate": dr.get("token_estimate", "NA"), "cost_estimate": dr.get("cost_estimate", "NA"), "latency_seconds": dr.get("latency_seconds", "NA")}, ensure_ascii=False),
            "failure_type": failure_type,
        }

        differs_from_external = str(dr.get("normalized_selected_answer")) != str(ex.get("normalized_selected_answer") if ex else "NA")
        loss_condition = any(
            [
                int(dr.get("is_correct", 0)) == 0,
                int(dr.get("gold_present", 0)) == 0,
                int(dr.get("present_not_selected", 0)) == 1,
                int(ex.get("is_correct", 0) if ex else 0) > int(dr.get("is_correct", 0)),
                int(sf.get("is_correct", 0) if sf else 0) > int(dr.get("is_correct", 0)),
                differs_from_external,
            ]
        )

        if loss_condition:
            loss_cases.append(base)
        if differs_from_external:
            diff_cases.append(base)

        for fld in req_fields:
            if str(base.get(fld, "NA")).strip() in {"", "NA", "[]", "{}"}:
                missing_counter[fld] += 1

    _write_jsonl(out_dir / "loss_cases.jsonl", loss_cases)
    _write_jsonl(out_dir / "difference_cases.jsonl", diff_cases)
    _write_csv(out_dir / "loss_cases.csv", loss_cases)
    _write_csv(out_dir / "missing_fields_report.csv", [{"field": k, "missing_count": v} for k, v in sorted(missing_counter.items())])

    def _build_md(path: Path, title: str, rows: list[dict[str, Any]]) -> None:
        lines = [f"# {title}", "", f"count={len(rows)}", "", "| example_id | failure_type | method | external | strict_f3 | stratum |", "|---|---|---|---|---|---|"]
        for r in rows:
            lines.append(
                f"| {r.get('example_id','')} | {r.get('failure_type','')} | {r.get('method_final_answer','')} | {r.get('external_final_answer','')} | {r.get('strict_f3_final_answer','')} | {r.get('stratum','')} |"
            )
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    _build_md(out_dir / "loss_cases_for_manual_inspection.md", "Loss cases for manual inspection", loss_cases)
    _build_md(out_dir / "difference_cases_for_manual_inspection.md", "Difference cases for manual inspection", diff_cases)

    readme = "\n".join(
        [
            f"# Cohere direct reserve validation ({args.timestamp})",
            "",
            f"Real API enabled: `{real_api_enabled}`",
            f"Planned examples: `{len({r['example_id'] for r in planned})}`",
            "",
            "Required outputs generated:",
            "- manifest.json",
            "- planned_cases.csv",
            "- per_case_method_results.csv",
            "- per_method_summary.csv",
            "- per_stratum_summary.csv",
            "- coverage_summary.csv",
            "- answer_group_summary.csv",
            "- candidate_branch_table.csv",
            "- action_trace.jsonl",
            "- final_branch_states.jsonl",
            "- tree_decision_traces.jsonl",
            "- loss_cases.jsonl / loss_cases.csv / loss_cases_for_manual_inspection.md",
            "- difference_cases.jsonl / difference_cases_for_manual_inspection.md",
            "- missing_fields_report.csv",
        ]
    )
    (out_dir / "README.md").write_text(readme + "\n", encoding="utf-8")
    print(f"Wrote: {out_dir}")


if __name__ == "__main__":
    main()
