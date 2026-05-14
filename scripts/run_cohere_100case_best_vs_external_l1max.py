#!/usr/bin/env python3
"""Run our best method vs external_l1_max on N GSM8K test cases via Cohere.

Usage:
  python3 scripts/run_cohere_100case_best_vs_external_l1max.py \
    --num-cases 100 --split test --seed 20260514 \
    --output-dir outputs/relation100_best_vs_external_l1max_cohere_<STAMP> \
    --provider cohere --methods best,external_l1_max --resume

Gold answers are stored only in gold_answer_metadata_only; they are never sent to any provider.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.branching import APIBranchGenerator
from experiments.data import normalize_answer_text
from experiments.frontier_matrix_core import (
    build_frontier_strategies,
    load_pilot_examples,
    resolve_api_key_for_provider,
)
from experiments.output_layer_repair import (
    apply_pal_residual_strong_integration_fix,
    augment_final_nodes_with_metadata_frontier,
    canonicalize_answer,
    choose_repair_answer,
    gold_in_tree_from_nodes,
    resolve_selected_group_hint_from_metadata,
)

DATASET = "openai/gsm8k"
DEFAULT_BUDGET = 6
DEFAULT_MODEL = "command-r-plus-08-2024"
DEFAULT_SEED = 20260514
DEFAULT_NUM_CASES = 100

BEST_RUNTIME = "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal"
EXTERNAL_RUNTIME = "external_l1_max"

METHOD_REGISTRY: dict[str, dict[str, Any]] = {
    "best": {"runtime": BEST_RUNTIME, "enable_output_repair": True, "apply_pal_fix": True},
    "external_l1_max": {"runtime": EXTERNAL_RUNTIME, "enable_output_repair": True, "apply_pal_fix": False},
}


class ObservedGenerator:
    def __init__(self, base: APIBranchGenerator) -> None:
        self.base = base
        self.registry: dict[str, Any] = {}

    def _snapshot(self, b: Any) -> dict[str, Any]:
        steps = list(getattr(b, "steps", []))
        pred = b.predicted_answer
        pred_norm_obj = normalize_answer_text(str(pred) if pred is not None else None)
        pred_norm = pred_norm_obj.get("normalized_answer") if pred_norm_obj else None
        return {
            "branch_id": b.branch_id,
            "score": float(getattr(b, "score", 0.0)),
            "depth": int(getattr(b, "depth", 0)),
            "is_done": bool(getattr(b, "is_done", False)),
            "is_pruned": bool(getattr(b, "is_pruned", False)),
            "predicted_answer": pred,
            "predicted_answer_normalized": pred_norm,
            "reasoning_text": "\n".join(str(s) for s in steps) if steps else "",
        }

    def init_branch(self, branch_id: str) -> Any:
        b = self.base.init_branch(branch_id)
        self.registry[b.branch_id] = b
        return b

    def expand(self, branch: Any, question: str, gold_answer: str) -> Any:
        return self.base.expand(branch, question, gold_answer)

    def verify(self, branch: Any, question: str) -> Any:
        return self.base.verify(branch, question)

    def prune(self, branch: Any) -> Any:
        return self.base.prune(branch)

def classify_result(
    result: Any,
    final_nodes: list[dict[str, Any]],
    gold_raw: str,
    method_cfg: dict[str, Any],
) -> dict[str, Any]:
    md = result.metadata or {}

    # Augment nodes with frontier metadata
    try:
        final_nodes = augment_final_nodes_with_metadata_frontier(final_nodes, md)
    except Exception:
        pass

    selected_group_hint = resolve_selected_group_hint_from_metadata(md, dataset=DATASET)
    repaired = choose_repair_answer(
        final_nodes=final_nodes,
        selected_group_hint=selected_group_hint,
        dataset=DATASET,
        enable_rescue=bool(method_cfg.get("enable_output_repair")),
    )

    # Apply PAL residual fix for PAL-family methods.
    # apply_pal_residual_strong_integration_fix returns (out, sidecar) where
    # out is the (possibly modified) repaired dict and sidecar is PAL tracking metadata.
    if method_cfg.get("apply_pal_fix"):
        try:
            out, _pal_sidecar = apply_pal_residual_strong_integration_fix(
                md, repaired, dataset=DATASET, enabled=True
            )
            repaired = out
        except Exception:
            pass

    surfaced_raw = repaired.get("surfaced_final_answer_raw")
    surfaced_can = canonicalize_answer(surfaced_raw, dataset=DATASET)
    gold_can = canonicalize_answer(gold_raw, dataset=DATASET)
    is_correct = bool(surfaced_can is not None and surfaced_can == gold_can)
    gold_in_tree = bool(gold_in_tree_from_nodes(final_nodes, gold_can or "", dataset=DATASET))

    if not gold_in_tree:
        failure_type = "absent_from_tree"
    elif is_correct:
        failure_type = "correct"
    elif repaired.get("chosen_final_node_answer_canonical") == gold_can:
        failure_type = "output_layer_mismatch"
    else:
        failure_type = "present_not_selected"

    # Candidate stats
    cands = [n["predicted_answer_normalized"] for n in final_nodes if n.get("predicted_answer_normalized")]
    cand_counts = Counter(c for c in cands if c)
    selected_support = cand_counts.get(surfaced_can, 0) if surfaced_can else 0
    unique_answers = len(cand_counts)

    return {
        "is_correct": int(is_correct),
        "failure_type": failure_type,
        "gold_in_tree": int(gold_in_tree),
        "surfaced_answer_raw": surfaced_raw,
        "surfaced_answer_canonical": surfaced_can,
        "selected_answer_support": selected_support,
        "unique_candidate_answers": unique_answers,
        "candidate_answers": list(cands),
        "candidate_traces": [n.get("reasoning_text", "") for n in final_nodes],
        "final_nodes": final_nodes,
        "repair_metadata": {k: v for k, v in repaired.items() if k not in ("final_nodes",)},
        "controller_metadata": md,
        "actions_used": int(getattr(result, "actions_used", 0)),
        "expansions": int(getattr(result, "expansions", 0)),
        "verifications": int(getattr(result, "verifications", 0)),
        "budget_exhausted": bool(getattr(result, "budget_exhausted", False)),
    }


def run_case(
    case_id: str,
    question: str,
    gold_raw: str,
    method_name: str,
    method_cfg: dict[str, Any],
    runtime: str,
    controller: Any,
    model: str,
    run_id: str,
    sample_index: int,
    seed: int,
) -> dict[str, Any]:
    ts = datetime.now(timezone.utc).isoformat()
    base = {
        "run_id": run_id,
        "timestamp": ts,
        "dataset_name": DATASET,
        "split": "test",
        "sample_seed": seed,
        "sample_index": sample_index,
        "case_id": case_id,
        "question": question,
        "gold_answer_metadata_only": gold_raw,
        "method_name": method_name,
        "provider": "cohere",
        "model": model,
        "runtime": runtime,
        "error": None,
        "latency_seconds": None,
    }

    # Clear the ObservedGenerator registry so this case starts fresh.
    # controller.generator is the ObservedGenerator that was passed via the factory.
    obs = getattr(controller, "generator", None)
    if isinstance(obs, ObservedGenerator):
        obs.registry.clear()
        if hasattr(obs, "base") and hasattr(obs.base, "reset_usage_counters"):
            obs.base.reset_usage_counters()

    t0 = time.monotonic()
    try:
        result = controller.run(question, gold_raw)
        latency = time.monotonic() - t0
        # Read branches captured during this run
        obs_after = getattr(controller, "generator", None)
        if isinstance(obs_after, ObservedGenerator):
            final_nodes = [obs_after._snapshot(b) for b in obs_after.registry.values()]
            token_usage = (
                obs_after.base.snapshot_usage_counters()
                if hasattr(obs_after.base, "snapshot_usage_counters")
                else {}
            )
        else:
            final_nodes = []
            token_usage = {}
        cls = classify_result(result, final_nodes, gold_raw, method_cfg)
        base.update(cls)
        base["latency_seconds"] = round(latency, 3)
        base["api_token_usage"] = token_usage
    except Exception as exc:
        latency = time.monotonic() - t0
        base["error"] = f"{type(exc).__name__}: {str(exc)[:600]}"
        base["is_correct"] = 0
        base["failure_type"] = "exception"
        base["latency_seconds"] = round(latency, 3)

    return base


def build_failure_record(row: dict[str, Any]) -> dict[str, Any]:
    final_nodes = row.get("final_nodes", [])
    cand_answers = row.get("candidate_answers", [])
    cand_traces = row.get("candidate_traces", [])
    gold_can = canonicalize_answer(row.get("gold_answer_metadata_only", ""), dataset=DATASET)

    # Trace failure hints
    surfaced = row.get("surfaced_answer_canonical")
    gold_in_tree = bool(row.get("gold_in_tree"))
    unique_answers = row.get("unique_candidate_answers", 0)

    trace_texts = " ".join(str(t) for t in cand_traces).lower()
    return {
        "case_id": row["case_id"],
        "question": row["question"],
        "gold_answer_metadata_only": row["gold_answer_metadata_only"],
        "method_name": row["method_name"],
        "selected_answer": row.get("surfaced_answer_raw"),
        "selected_answer_canonical": surfaced,
        "selected_answer_support_count": row.get("selected_answer_support", 0),
        "unique_answer_count": unique_answers,
        "all_candidate_answers": cand_answers,
        "all_candidate_traces": cand_traces,
        "gold_appeared_in_candidate_pool": gold_in_tree,
        "failure_type": row.get("failure_type"),
        "latency_seconds": row.get("latency_seconds"),
        "error": row.get("error"),
        "failure_hints": {
            "trace_is_opaque": any(
                '"action"' in str(t) and '"final"' in str(t) and len(str(t)) < 80
                for t in cand_traces
            ),
            "arithmetic_only_suspicion": (
                gold_in_tree and row.get("failure_type") == "present_not_selected"
            ),
            "selector_failure_vs_discovery_failure": (
                "selector_failure" if gold_in_tree and not row.get("is_correct")
                else "discovery_failure" if not gold_in_tree
                else "correct"
            ),
        },
        "controller_metadata": row.get("controller_metadata", {}),
        "repair_metadata": row.get("repair_metadata", {}),
        "api_token_usage": row.get("api_token_usage", {}),
        "notes": "",
    }


def load_completed(results_path: Path) -> set[tuple[str, str]]:
    done: set[tuple[str, str]] = set()
    if results_path.exists():
        for line in results_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
                if r.get("error") is None and r.get("is_correct") is not None:
                    done.add((str(r["case_id"]), str(r["method_name"])))
            except Exception:
                pass
    return done


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="100-case Cohere: best method vs external_l1_max")
    p.add_argument("--num-cases", type=int, default=DEFAULT_NUM_CASES)
    p.add_argument("--split", default="test")
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--provider", default="cohere")
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--budget", type=int, default=DEFAULT_BUDGET)
    p.add_argument("--methods", default="best,external_l1_max")
    p.add_argument("--resume", action="store_true")
    p.add_argument("--max-concurrency", type=int, default=1, help="Sequential only for now")
    p.add_argument("--dry-run", action="store_true", help="Sample cases and plan without API calls")
    p.add_argument("--temperature", type=float, default=0.1)
    p.add_argument("--max-output-tokens", type=int, default=220)
    p.add_argument("--timeout-seconds", type=int, default=60)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    failures_dir = out_dir / "failures"
    failures_dir.mkdir(parents=True, exist_ok=True)

    run_id = f"cohere_100case_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    methods = [m.strip() for m in args.methods.split(",") if m.strip()]
    invalid = [m for m in methods if m not in METHOD_REGISTRY]
    if invalid:
        print(f"ERROR: unknown methods: {invalid}. Available: {sorted(METHOD_REGISTRY)}", file=sys.stderr)
        sys.exit(1)

    # Check API key
    api_key = resolve_api_key_for_provider(args.provider)
    if not args.dry_run and not api_key:
        print(f"ERROR: COHERE_API_KEY not set", file=sys.stderr)
        sys.exit(1)
    print(f"COHERE_API_KEY present: {bool(api_key)}")
    print(f"run_id: {run_id}")
    print(f"output_dir: {out_dir}")

    # Load cases
    print(f"Loading {args.num_cases} cases from {DATASET} test split (seed={args.seed})...")
    examples = load_pilot_examples(DATASET, args.num_cases, args.seed)
    print(f"  loaded {len(examples)} examples")

    # Save sampled case IDs
    sampled_ids = [{"sample_index": i, "case_id": ex.example_id} for i, ex in enumerate(examples)]
    (out_dir / "sampled_case_ids.json").write_text(json.dumps(sampled_ids, indent=2), encoding="utf-8")

    if args.dry_run:
        plan = [
            {"sample_index": i, "case_id": ex.example_id, "method": m, "runtime": METHOD_REGISTRY[m]["runtime"]}
            for i, ex in enumerate(examples) for m in methods
        ]
        (out_dir / "dry_run_plan.jsonl").write_text(
            "\n".join(json.dumps(r) for r in plan), encoding="utf-8"
        )
        print(f"Dry-run: {len(plan)} planned calls. No API calls made.")
        return

    # Build strategies — factory wraps each APIBranchGenerator in an ObservedGenerator
    # so controllers own their observer from construction (canonical pattern from
    # run_canonical_real_model_validation.py).
    rng = random.Random(args.seed)
    print(f"Building frontier strategies (budget={args.budget})...")

    def _factory() -> ObservedGenerator:
        return ObservedGenerator(
            APIBranchGenerator(
                provider=args.provider,
                api_key=api_key,
                model=args.model,
                temperature=args.temperature,
                max_tokens=args.max_output_tokens,
                timeout_seconds=args.timeout_seconds,
            )
        )

    strategies = build_frontier_strategies(
        _factory,
        args.budget,
        [1],
        rng,
        use_openai_api=(args.provider == "openai"),
        include_broad_diversity_aggregation_methods=True,
        include_external_l1_baseline=True,
    )
    # Verify runtimes present
    for m in methods:
        runtime = METHOD_REGISTRY[m]["runtime"]
        if runtime not in strategies:
            print(f"ERROR: runtime {runtime!r} not found in strategies at budget {args.budget}", file=sys.stderr)
            sys.exit(1)
    print(f"  strategies built. Methods: {methods}")

    # Resume: find already-completed (case_id, method) pairs
    results_path = out_dir / "results_by_case.jsonl"
    done_keys: set[tuple[str, str]] = set()
    if args.resume and results_path.exists():
        done_keys = load_completed(results_path)
        print(f"  resume: {len(done_keys)} already completed")

    # Run
    all_results: list[dict[str, Any]] = []
    failure_records: list[dict[str, Any]] = []

    total_planned = len(examples) * len(methods)
    completed = len(done_keys)
    print(f"Starting run: {total_planned} planned calls, {completed} already done")

    for i, ex in enumerate(examples):
        for method_name in methods:
            key = (str(ex.example_id), method_name)
            if key in done_keys:
                continue
            method_cfg = METHOD_REGISTRY[method_name]
            runtime = method_cfg["runtime"]
            print(f"  [{i+1}/{len(examples)}] case={ex.example_id} method={method_name} ...", end=" ", flush=True)
            row = run_case(
                case_id=str(ex.example_id),
                question=ex.question,
                gold_raw=str(ex.answer),
                method_name=method_name,
                method_cfg=method_cfg,
                runtime=runtime,
                controller=strategies[runtime],
                model=args.model,
                run_id=run_id,
                sample_index=i,
                seed=args.seed,
            )
            # Strip large objects from the streaming result record
            row_clean = {k: v for k, v in row.items() if k not in ("final_nodes", "candidate_traces", "candidate_answers", "repair_metadata", "controller_metadata", "api_token_usage")}
            row_clean["candidate_answers"] = row.get("candidate_answers", [])
            row_clean["gold_appeared_in_candidate_pool"] = bool(row.get("gold_in_tree"))
            all_results.append(row_clean)
            append_jsonl(results_path, row_clean)
            status = "✓" if row.get("is_correct") else ("ERR" if row.get("error") else "✗")
            print(status)
            if row.get("is_correct") == 0 and not row.get("error"):
                fr = build_failure_record(row)
                failure_records.append(fr)
                append_jsonl(failures_dir / "full_failure_records.jsonl", fr)

    # Load all results (including resumed ones) for reporting
    all_rows: list[dict[str, Any]] = []
    if results_path.exists():
        for line in results_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    all_rows.append(json.loads(line))
                except Exception:
                    pass

    # Reload full failure records
    all_failures: list[dict[str, Any]] = []
    fr_path = failures_dir / "full_failure_records.jsonl"
    if fr_path.exists():
        for line in fr_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    all_failures.append(json.loads(line))
                except Exception:
                    pass

    # Aggregate stats
    by_method: dict[str, list[dict[str, Any]]] = {m: [] for m in methods}
    for r in all_rows:
        m = r.get("method_name", "")
        if m in by_method:
            by_method[m].append(r)

    def acc(rows: list[dict[str, Any]]) -> float:
        scored = [r for r in rows if r.get("error") is None and r.get("is_correct") is not None]
        return sum(r["is_correct"] for r in scored) / len(scored) if scored else 0.0

    def n_correct(rows: list[dict[str, Any]]) -> int:
        return sum(1 for r in rows if r.get("error") is None and r.get("is_correct") == 1)

    # Paired analysis
    m0, m1 = methods[0], methods[1] if len(methods) > 1 else methods[0]
    by_case_m0 = {r["case_id"]: r for r in by_method.get(m0, []) if r.get("error") is None}
    by_case_m1 = {r["case_id"]: r for r in by_method.get(m1, []) if r.get("error") is None}
    both_cases = set(by_case_m0) & set(by_case_m1)
    both_correct = sum(1 for c in both_cases if by_case_m0[c].get("is_correct") == 1 and by_case_m1[c].get("is_correct") == 1)
    both_wrong = sum(1 for c in both_cases if by_case_m0[c].get("is_correct") == 0 and by_case_m1[c].get("is_correct") == 0)
    m0_only = sum(1 for c in both_cases if by_case_m0[c].get("is_correct") == 1 and by_case_m1[c].get("is_correct") == 0)
    m1_only = sum(1 for c in both_cases if by_case_m0[c].get("is_correct") == 0 and by_case_m1[c].get("is_correct") == 1)

    # Write summary
    lines = [
        "# 100-Case Cohere Comparison: best vs external_l1_max",
        "",
        f"- **run_id:** `{run_id}`",
        f"- **dataset:** `{DATASET}` (test split)",
        f"- **random seed:** `{args.seed}`",
        f"- **num cases:** `{args.num_cases}`",
        f"- **budget:** `{args.budget}`",
        f"- **Cohere model:** `{args.model}`",
        f"- **methods compared:** {methods}",
        "",
        "## Accuracy",
        "",
    ]
    for m in methods:
        rows = by_method[m]
        nc = n_correct(rows)
        n = len([r for r in rows if r.get("error") is None])
        nerr = len([r for r in rows if r.get("error") is not None])
        lines.append(f"| `{m}` | {nc} / {n} | {acc(rows):.4f} | {nerr} errors |")
    lines += [
        "",
        "## Paired win/loss/tie",
        "",
        f"- **Evaluated paired cases:** {len(both_cases)}",
        f"- **Both correct:** {both_correct}",
        f"- **Both wrong:** {both_wrong}",
        f"- **`{m0}` only correct:** {m0_only}",
        f"- **`{m1}` only correct:** {m1_only}",
        "",
        "## Failure decomposition",
        "",
    ]
    for m in methods:
        fail_rows = [r for r in by_method[m] if r.get("is_correct") == 0 and r.get("error") is None]
        ft_counts = Counter(r.get("failure_type", "unknown") for r in fail_rows)
        lines.append(f"### `{m}`")
        for ft, cnt in sorted(ft_counts.items()):
            lines.append(f"- {ft}: {cnt}")
        lines.append("")
    lines += [
        "## Interpretation",
        "",
        "Results reflect a single Cohere provider run at a fixed budget. McNemar or bootstrap CI",
        "is needed before strong claims. Compare against prior 300-case evidence in",
        "`outputs/pal_retry_300case_analysis_20260506/report.md`.",
        "",
        "## Files",
        "",
        "- `results_by_case.jsonl` — one row per (case, method)",
        "- `failures/full_failure_records.jsonl` — detailed records for incorrect cases",
        "- `failures/failure_summary.md` — failure breakdown",
        "- `run_manifest.json` — run metadata",
        "- `sampled_case_ids.json` — deterministic case sample",
        "- `commands.txt` — exact CLI command",
    ]
    (out_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Failure summary
    fail_lines = [
        "# Failure Summary",
        "",
        f"Total incorrect cases across all methods: {len(all_failures)}",
        "",
        "## By method",
        "",
    ]
    by_method_fail = {m: [f for f in all_failures if f["method_name"] == m] for m in methods}
    for m in methods:
        frs = by_method_fail[m]
        fail_lines.append(f"### `{m}` — {len(frs)} failures")
        ft_counts = Counter(f.get("failure_type", "?") for f in frs)
        for ft, cnt in sorted(ft_counts.items()):
            fail_lines.append(f"- {ft}: {cnt}")
        fail_lines.append("")
    (failures_dir / "failure_summary.md").write_text("\n".join(fail_lines) + "\n", encoding="utf-8")

    # run_manifest.json
    manifest = {
        "run_id": run_id,
        "dataset": DATASET,
        "split": args.split,
        "seed": args.seed,
        "num_cases": args.num_cases,
        "budget": args.budget,
        "provider": args.provider,
        "model": args.model,
        "methods": methods,
        "method_runtimes": {m: METHOD_REGISTRY[m]["runtime"] for m in methods},
        "total_planned_calls": total_planned,
        "results_rows": len(all_rows),
        "failure_rows": len(all_failures),
    }
    (out_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # commands.txt
    cmd = (
        f"python3 scripts/run_cohere_100case_best_vs_external_l1max.py"
        f" --num-cases {args.num_cases} --split {args.split} --seed {args.seed}"
        f" --output-dir {out_dir} --provider {args.provider} --model {args.model}"
        f" --budget {args.budget} --methods {args.methods}"
        + (" --resume" if args.resume else "")
    )
    (out_dir / "commands.txt").write_text(cmd + "\n", encoding="utf-8")

    print()
    print("=" * 60)
    print(f"Run complete: {out_dir}")
    for m in methods:
        rows = by_method[m]
        print(f"  {m}: {n_correct(rows)}/{len([r for r in rows if not r.get('error')])} correct ({acc(rows):.4f})")
    print(f"  Failure records: {len(all_failures)}")
    print()
    print("✓ No gold answers were sent to any provider.")
    print("✓ No outputs staged or committed.")


if __name__ == "__main__":
    main()
