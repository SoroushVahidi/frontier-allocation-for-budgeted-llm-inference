#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import random
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.frontier_matrix_core import build_frontier_strategies, generator_factory_for_mode
from experiments.data import extract_final_answer
from experiments.hf_datasets import _import_hf_load_dataset
from experiments.output_layer_repair import canonicalize_answer
from experiments.trace_schema import build_branch_trace, write_trace_package

STRICT_F3_RUNTIME = (
    "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_"
    "repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth3_coverage_forced_v1"
)

METHOD_RUNTIME: dict[str, str] = {
    "strict_f3": STRICT_F3_RUNTIME,
    "external_l1_max": "external_l1_max",
    "direct_reserve_frontier_gate_v1": "direct_reserve_frontier_gate_v1",
}


@dataclass(frozen=True)
class SelectedCase:
    provider: str
    dataset: str
    seed: int
    budget: int
    example_id: str
    strict_f3_failure_tag: str
    source_absent_from_tree: int
    source_present_not_selected: int
    question: str
    gold_answer_raw: str
    gold_answer_canonical: str


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Bounded F3-vs-L1 loss trace diagnostic rerun.")
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    p.add_argument(
        "--source-per-example-rows",
        default="outputs/real_model_ours_vs_external_validation_20260425T_WULVER_COHERE_LONG/cohere/per_example_rows.csv",
    )
    p.add_argument("--provider", default="cohere")
    p.add_argument("--model", default="command-r-plus-08-2024")
    p.add_argument("--dataset", default="openai/gsm8k")
    p.add_argument("--split", default="test")
    p.add_argument("--config", default="main")
    p.add_argument("--absent-sample-size", type=int, default=20)
    p.add_argument("--present-sample-size", type=int, default=10)
    p.add_argument("--selection-seed", type=int, default=7)
    p.add_argument("--methods", default="strict_f3,external_l1_max")
    p.add_argument("--include-direct-reserve", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--dry-run-case-count", type=int, default=3)
    p.add_argument("--temperature", type=float, default=0.1)
    p.add_argument("--max-output-tokens", type=int, default=220)
    p.add_argument("--timeout-seconds", type=int, default=45)
    return p.parse_args()


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        if not rows:
            if fieldnames:
                w = csv.DictWriter(f, fieldnames=fieldnames)
                w.writeheader()
            return
        w = csv.DictWriter(f, fieldnames=fieldnames or list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _canonical(text: str, dataset: str) -> str:
    if not str(text).strip():
        return ""
    return str(canonicalize_answer(str(text), dataset=dataset))


def _load_gsm8k_map(dataset: str, config: str, split: str) -> dict[str, dict[str, str]]:
    load_dataset = _import_hf_load_dataset()
    ds = load_dataset(dataset, config, split=split)
    mapping: dict[str, dict[str, str]] = {}
    for idx, row in enumerate(ds):
        example_id = f"{dataset.replace('/', '_')}_{idx}"
        question = str(row.get("question", ""))
        gold_raw = str(row.get("answer", ""))
        mapping[example_id] = {
            "question": question,
            "gold_answer_raw": extract_final_answer(gold_raw),
        }
    return mapping


def _select_cases(rows: list[dict[str, str]], *, absent_n: int, present_n: int, selection_seed: int) -> list[dict[str, Any]]:
    by_key: dict[tuple[str, str, int, int, str], dict[str, dict[str, str]]] = defaultdict(dict)
    for r in rows:
        key = (str(r.get("provider", "")), str(r.get("dataset", "")), int(r.get("seed", -1)), int(r.get("budget", -1)), str(r.get("example_id", "")))
        by_key[key][str(r.get("method", ""))] = r

    losses: list[dict[str, Any]] = []
    for (provider, dataset, seed, budget, example_id), cell in sorted(by_key.items()):
        s = cell.get("strict_f3")
        e = cell.get("external_l1_max")
        if not s or not e:
            continue
        if int(s.get("is_correct", "0")) != 0:
            continue
        if int(e.get("is_correct", "0")) != 1:
            continue
        losses.append(
            {
                "provider": provider,
                "dataset": dataset,
                "seed": seed,
                "budget": budget,
                "example_id": example_id,
                "strict_f3_failure_tag": str(s.get("failure_type", "unknown")),
                "source_absent_from_tree": int(s.get("absent_from_tree", "0") or 0),
                "source_present_not_selected": int(s.get("present_not_selected", "0") or 0),
            }
        )

    absent = [r for r in losses if int(r["source_absent_from_tree"]) == 1]
    present = [r for r in losses if int(r["source_present_not_selected"]) == 1]
    rng = random.Random(selection_seed)
    rng.shuffle(absent)
    rng.shuffle(present)
    sample = absent[:absent_n] + present[:present_n]
    return sorted(sample, key=lambda r: (int(r["seed"]), int(r["budget"]), str(r["example_id"])))


def _make_selected_cases(rows: list[dict[str, Any]], dataset_map: dict[str, dict[str, str]], dataset: str) -> list[SelectedCase]:
    selected: list[SelectedCase] = []
    for row in rows:
        ex = dataset_map.get(str(row["example_id"]), {})
        question = str(ex.get("question", ""))
        gold_raw = str(ex.get("gold_answer_raw", ""))
        selected.append(
            SelectedCase(
                provider=str(row["provider"]),
                dataset=str(row["dataset"]),
                seed=int(row["seed"]),
                budget=int(row["budget"]),
                example_id=str(row["example_id"]),
                strict_f3_failure_tag=str(row["strict_f3_failure_tag"]),
                source_absent_from_tree=int(row["source_absent_from_tree"]),
                source_present_not_selected=int(row["source_present_not_selected"]),
                question=question,
                gold_answer_raw=gold_raw,
                gold_answer_canonical=_canonical(gold_raw, dataset),
            )
        )
    return selected


def main() -> None:
    args = parse_args()
    out_dir = REPO_ROOT / "outputs" / f"f3_vs_l1_loss_trace_diagnostic_{args.timestamp}"
    if out_dir.exists():
        raise SystemExit(f"Output directory already exists: {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=False)

    methods = [m.strip() for m in str(args.methods).split(",") if m.strip()]
    if args.include_direct_reserve and "direct_reserve_frontier_gate_v1" not in methods:
        methods.append("direct_reserve_frontier_gate_v1")
    unsupported = [m for m in methods if m not in METHOD_RUNTIME]
    if unsupported:
        raise SystemExit(f"Unsupported methods requested: {unsupported}")

    source_rows = _read_csv(Path(args.source_per_example_rows))
    chosen_rows = _select_cases(
        [r for r in source_rows if r.get("provider") == args.provider and r.get("dataset") == args.dataset],
        absent_n=args.absent_sample_size,
        present_n=args.present_sample_size,
        selection_seed=args.selection_seed,
    )

    dataset_map = _load_gsm8k_map(args.dataset, args.config, args.split)
    selected_cases = _make_selected_cases(chosen_rows, dataset_map, args.dataset)

    if args.dry_run:
        selected_cases = selected_cases[: max(1, args.dry_run_case_count)]

    selected_case_rows: list[dict[str, Any]] = []
    for idx, case in enumerate(selected_cases, start=1):
        selected_case_rows.append(
            {
                "case_index": idx,
                "provider": case.provider,
                "dataset": case.dataset,
                "seed": case.seed,
                "budget": case.budget,
                "example_id": case.example_id,
                "strict_f3_failure_tag": case.strict_f3_failure_tag,
                "source_absent_from_tree": case.source_absent_from_tree,
                "source_present_not_selected": case.source_present_not_selected,
                "question": case.question,
                "gold_answer_raw": case.gold_answer_raw,
                "gold_answer_canonical": case.gold_answer_canonical,
            }
        )
    _write_csv(out_dir / "selected_cases.csv", selected_case_rows)

    if not args.dry_run and args.provider == "cohere" and not os.getenv("COHERE_API_KEY", ""):
        raise SystemExit("COHERE_API_KEY is required for real reruns. Use --dry-run for synthetic package generation.")

    per_example_path = out_dir / "per_example_records.jsonl"
    raw_io_path = out_dir / "raw_prompt_response_records.jsonl"
    traces: list[dict[str, Any]] = []

    for case in selected_cases:
        for method in methods:
            runtime = METHOD_RUNTIME[method]
            status = "dry_run"
            error = ""
            exact_match = 0
            prediction = "DRY_RUN_ANSWER"
            prediction_canonical = _canonical(prediction, case.dataset)
            result_metadata: dict[str, Any] = {
                "selected_answer_group": "DRY_RUN_ANSWER",
                "answer_group_support_counts": {"DRY_RUN_ANSWER": 1},
                "action_trace": [{"action": "expand", "depth": 0, "family_id": "dry_family", "prompt": "dry prompt", "response": "dry response"}],
                "final_branch_states": [
                    {
                        "branch_id": "dry_b0",
                        "branch_depth": 0,
                        "predicted_answer": "DRY_RUN_ANSWER",
                        "score": 0.5,
                        "is_done": True,
                        "strategy_family": "dry_family",
                    }
                ],
            }
            actions_used = 1
            expansions = 1
            verifications = 0

            if not args.dry_run:
                rng = random.Random(case.seed * 10007 + case.budget)
                factory = generator_factory_for_mode(
                    use_openai_api=True,
                    rng=rng,
                    openai_model=args.model,
                    temperature=args.temperature,
                    max_output_tokens=args.max_output_tokens,
                    timeout_seconds=args.timeout_seconds,
                    api_provider=args.provider,
                )
                specs = build_frontier_strategies(
                    generator_factory=factory,
                    budget=case.budget,
                    adaptive_min_expand_grid=[1],
                    rng=rng,
                    use_openai_api=True,
                    include_broad_diversity_aggregation_methods=True,
                    include_external_l1_baseline=True,
                    include_external_s1_baseline=True,
                )
                if runtime not in specs:
                    status = "runtime_missing"
                    error = f"runtime_not_available:{runtime}"
                else:
                    try:
                        controller = specs[runtime]
                        setattr(controller, "emit_full_traces", True)
                        result = controller.run(case.question, case.gold_answer_raw)
                        prediction = str(result.prediction or "")
                        prediction_canonical = _canonical(prediction, case.dataset)
                        exact_match = int(prediction_canonical == case.gold_answer_canonical)
                        actions_used = int(getattr(result, "actions_used", 0) or 0)
                        expansions = int(getattr(result, "expansions", 0) or 0)
                        verifications = int(getattr(result, "verifications", 0) or 0)
                        result_metadata = dict(getattr(result, "metadata", {}) or {})
                        status = "scored"
                        trace = build_branch_trace(
                            result=result,
                            example_id=case.example_id,
                            dataset=case.dataset,
                            provider=case.provider,
                            model=args.model,
                            budget=case.budget,
                            seed=case.seed,
                            method=method,
                            question=case.question,
                            gold_answer=case.gold_answer_raw,
                        )
                        traces.append(trace)
                    except Exception as exc:  # noqa: BLE001
                        status = "failed"
                        error = f"{type(exc).__name__}: {str(exc)[:500]}"

            _append_jsonl(
                per_example_path,
                {
                    "provider": case.provider,
                    "model": args.model,
                    "dataset": case.dataset,
                    "seed": case.seed,
                    "budget": case.budget,
                    "example_id": case.example_id,
                    "method": method,
                    "runtime_method": runtime,
                    "status": status,
                    "error": error,
                    "question": case.question,
                    "gold_answer_raw": case.gold_answer_raw,
                    "gold_answer_canonical": case.gold_answer_canonical,
                    "final_answer_raw": prediction,
                    "final_answer_canonical": prediction_canonical,
                    "exact_match": exact_match,
                    "actions_used": actions_used,
                    "expansions": expansions,
                    "verifications": verifications,
                    "source_absent_from_tree": case.source_absent_from_tree,
                    "source_present_not_selected": case.source_present_not_selected,
                    "strict_f3_failure_tag": case.strict_f3_failure_tag,
                    "result_metadata": result_metadata,
                },
            )
            for i, ev in enumerate(list((result_metadata or {}).get("action_trace", []))):
                _append_jsonl(
                    raw_io_path,
                    {
                        "provider": case.provider,
                        "model": args.model,
                        "dataset": case.dataset,
                        "seed": case.seed,
                        "budget": case.budget,
                        "example_id": case.example_id,
                        "method": method,
                        "action_index": i,
                        "action": ev.get("action"),
                        "branch_id": ev.get("branch_id"),
                        "depth": ev.get("depth"),
                        "prompt": ev.get("prompt") or ev.get("request_prompt") or "",
                        "response": ev.get("response") or ev.get("response_text") or "",
                    },
                )

    trace_stats = write_trace_package(out_dir, traces) if traces else {"n_traces": 0, "n_branches": 0, "n_answer_groups": 0}

    manifest = {
        "run_type": "f3_vs_l1_loss_trace_diagnostic",
        "timestamp": args.timestamp,
        "provider": args.provider,
        "model": args.model,
        "dataset": args.dataset,
        "methods": methods,
        "source_per_example_rows": str(args.source_per_example_rows),
        "source_loss_counts": {
            "requested_absent": args.absent_sample_size,
            "requested_present": args.present_sample_size,
            "selected_cases": len(selected_cases),
        },
        "dry_run": bool(args.dry_run),
        "trace_stats": trace_stats,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    readme = [
        "# F3 vs L1 Loss Trace Diagnostic Package",
        "",
        f"- Timestamp: {args.timestamp}",
        f"- Dry run: {args.dry_run}",
        f"- Selected cases: {len(selected_cases)}",
        f"- Methods: {', '.join(methods)}",
        "- Artifacts: selected_cases.csv, per_example_records.jsonl, raw_prompt_response_records.jsonl, traces/",
    ]
    (out_dir / "README.md").write_text("\n".join(readme) + "\n", encoding="utf-8")
    print(f"Wrote diagnostic package: {out_dir}")


if __name__ == "__main__":
    main()
