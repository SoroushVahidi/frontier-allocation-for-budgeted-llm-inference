#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import random
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.data import extract_final_answer
from experiments.frontier_matrix_core import build_frontier_strategies, generator_factory_for_mode
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
    problem_type: str


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
    p.add_argument("--dry-run-from-source", action="store_true")
    p.add_argument("--dry-run-case-count", type=int, default=0)
    p.add_argument("--allow-smaller-sample", action="store_true")
    p.add_argument("--temperature", type=float, default=0.1)
    p.add_argument("--max-output-tokens", type=int, default=220)
    p.add_argument("--timeout-seconds", type=int, default=45)
    return p.parse_args()


def classify_problem_type(question: str) -> str:
    q = (question or "").lower()
    if any(x in q for x in ["ways", "choose", "arrange", "permutation", "combination", "how many"]):
        return "counting_combinatorics"
    if any(x in q for x in ["percent", "%", "ratio", "fraction", "rate"]):
        return "ratio_percent"
    if any(x in q for x in ["more than", "less than", "greater than", "fewer", "difference", "compared"]):
        return "comparison"
    if any(x in q for x in ["km", "kilometer", "meter", "cm", "inch", "mile", "kg", "gram", "liter", "hour", "minute", "second"]):
        return "unit_conversion"
    if any(x in q for x in ["equation", "solve for", "variable", "x =", "x=", "y ="]):
        return "algebra_like"
    num_count = len([x for x in q.split() if any(c.isdigit() for c in x)])
    sentence_count = len([s for s in q.replace("?", ".").replace("!", ".").split(".") if s.strip()])
    if num_count >= 3 or sentence_count >= 3:
        return "multi_step_arithmetic"
    if num_count >= 1:
        return "single_arithmetic"
    return "unknown"


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
                csv.DictWriter(f, fieldnames=fieldnames).writeheader()
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


def _get_git_snapshot() -> dict[str, Any]:
    def _run(cmd: list[str]) -> str:
        try:
            return subprocess.check_output(cmd, cwd=REPO_ROOT, text=True).strip()
        except Exception:
            return "NA"

    commit = _run(["git", "rev-parse", "HEAD"])
    branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    dirty = "NA"
    try:
        dirty = "clean" if subprocess.run(["git", "diff", "--quiet"], cwd=REPO_ROOT, check=False).returncode == 0 else "dirty"
    except Exception:
        pass
    return {"git_commit_hash": commit or "NA", "git_branch": branch or "NA", "git_dirty_state": dirty}


def _environment_summary() -> dict[str, Any]:
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "python_version": sys.version,
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "system": platform.system(),
        "machine": platform.machine(),
    }


def _load_gsm8k_map(dataset: str, config: str, split: str) -> dict[str, dict[str, str]]:
    load_dataset = _import_hf_load_dataset()
    ds = load_dataset(dataset, config, split=split)
    mapping: dict[str, dict[str, str]] = {}
    for idx, row in enumerate(ds):
        ex_id = f"{dataset.replace('/', '_')}_{idx}"
        q = str(row.get("question", ""))
        gold_raw = extract_final_answer(str(row.get("answer", "")))
        mapping[ex_id] = {"question": q, "gold_answer_raw": gold_raw, "problem_type": classify_problem_type(q)}
    return mapping


def _select_cases(rows: list[dict[str, str]], absent_n: int, present_n: int, selection_seed: int) -> tuple[list[dict[str, Any]], dict[str, int]]:
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
        if int(s.get("is_correct", "0")) != 0 or int(e.get("is_correct", "0")) != 1:
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
    selected = absent[:absent_n] + present[:present_n]
    selected = sorted(selected, key=lambda r: (int(r["seed"]), int(r["budget"]), str(r["example_id"])))
    return selected, {"available_absent": len(absent), "available_present": len(present)}


def _synthetic_cases(args: argparse.Namespace) -> list[SelectedCase]:
    cases: list[SelectedCase] = []
    absent_n = max(1, int(args.absent_sample_size))
    present_n = max(1, int(args.present_sample_size))
    if int(args.dry_run_case_count) > 0:
        total_target = int(args.dry_run_case_count)
        absent_n = max(1, min(absent_n, total_target - 1 if total_target > 1 else 1))
        present_n = max(1, total_target - absent_n)
    for i in range(absent_n):
        cases.append(
            SelectedCase(
                args.provider,
                args.dataset,
                11 if i % 2 == 0 else 23,
                4 if i % 3 == 0 else (6 if i % 3 == 1 else 8),
                f"synthetic_absent_{i}",
                "absent_from_tree",
                1,
                0,
                f"How many ways can we arrange {i+3} books?",
                str((i + 3) * 2),
                str((i + 3) * 2),
                "counting_combinatorics",
            )
        )
    for i in range(present_n):
        cases.append(
            SelectedCase(
                args.provider,
                args.dataset,
                11 if i % 2 == 0 else 23,
                4 if i % 3 == 0 else (6 if i % 3 == 1 else 8),
                f"synthetic_present_{i}",
                "present_not_selected",
                0,
                1,
                f"What percent of {50+i} is {10+i}?",
                "20",
                "20",
                "ratio_percent",
            )
        )
    return cases


def _selected_to_rows(cases: list[SelectedCase]) -> list[dict[str, Any]]:
    rows = []
    for i, c in enumerate(cases, start=1):
        row = asdict(c)
        row["case_index"] = i
        rows.append({
            "case_index": row["case_index"],
            "provider": row["provider"],
            "dataset": row["dataset"],
            "seed": row["seed"],
            "budget": row["budget"],
            "example_id": row["example_id"],
            "strict_f3_failure_tag": row["strict_f3_failure_tag"],
            "source_absent_from_tree": row["source_absent_from_tree"],
            "source_present_not_selected": row["source_present_not_selected"],
            "problem_type": row["problem_type"],
            "question": row["question"],
            "gold_answer_raw": row["gold_answer_raw"],
            "gold_answer_canonical": row["gold_answer_canonical"],
        })
    return rows


def main() -> None:
    args = parse_args()
    out_dir = REPO_ROOT / "outputs" / f"f3_vs_l1_loss_trace_diagnostic_{args.timestamp}"
    if out_dir.exists():
        raise SystemExit(f"Output directory already exists: {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=False)

    invoked_cmd = " ".join([sys.executable, *sys.argv])
    analyzer_cmd = f"python scripts/analyze_f3_vs_l1_loss_trace_diagnostic.py --input-dir {out_dir}"
    wulver_cmd = (
        "python scripts/run_f3_vs_l1_loss_trace_diagnostic.py --timestamp REAL_F3_L1_TRACE_DIAG_<TS> "
        "--provider cohere --model command-r-plus-08-2024 --dataset openai/gsm8k --absent-sample-size 20 "
        "--present-sample-size 10 --methods strict_f3,external_l1_max"
    )
    (out_dir / "command_log.txt").write_text(
        "\n".join([
            f"invoked_command={invoked_cmd}",
            f"analyzer_command={analyzer_cmd}",
            f"wulver_ready_real_run_command={wulver_cmd}",
        ]) + "\n",
        encoding="utf-8",
    )

    methods = [m.strip() for m in str(args.methods).split(",") if m.strip()]
    if args.include_direct_reserve and "direct_reserve_frontier_gate_v1" not in methods:
        methods.append("direct_reserve_frontier_gate_v1")
    unsupported = [m for m in methods if m not in METHOD_RUNTIME]
    if unsupported:
        raise SystemExit(f"Unsupported methods requested: {unsupported}")

    git_snapshot = _get_git_snapshot()
    env_summary = _environment_summary()
    (out_dir / "git_snapshot.json").write_text(json.dumps(git_snapshot, indent=2) + "\n", encoding="utf-8")
    (out_dir / "environment_summary.json").write_text(json.dumps(env_summary, indent=2) + "\n", encoding="utf-8")

    selected_cases: list[SelectedCase]
    source_row_count = "NA"
    available_absent = "NA"
    available_present = "NA"
    shortfall_reason = "NA"

    if args.dry_run and not args.dry_run_from_source:
        selected_cases = _synthetic_cases(args)
    else:
        source_rows = _read_csv(Path(args.source_per_example_rows))
        source_row_count = len(source_rows)
        selected_raw, avail = _select_cases(
            [r for r in source_rows if r.get("provider") == args.provider and r.get("dataset") == args.dataset],
            args.absent_sample_size,
            args.present_sample_size,
            args.selection_seed,
        )
        available_absent = avail["available_absent"]
        available_present = avail["available_present"]

        dataset_map = _load_gsm8k_map(args.dataset, args.config, args.split)
        selected_cases = []
        for row in selected_raw:
            ex = dataset_map.get(str(row["example_id"]), {})
            q = str(ex.get("question", ""))
            g = str(ex.get("gold_answer_raw", ""))
            selected_cases.append(
                SelectedCase(
                    provider=str(row["provider"]),
                    dataset=str(row["dataset"]),
                    seed=int(row["seed"]),
                    budget=int(row["budget"]),
                    example_id=str(row["example_id"]),
                    strict_f3_failure_tag=str(row["strict_f3_failure_tag"]),
                    source_absent_from_tree=int(row["source_absent_from_tree"]),
                    source_present_not_selected=int(row["source_present_not_selected"]),
                    question=q,
                    gold_answer_raw=g,
                    gold_answer_canonical=_canonical(g, args.dataset),
                    problem_type=str(ex.get("problem_type", classify_problem_type(q))),
                )
            )

    selected_absent = sum(int(c.source_absent_from_tree) for c in selected_cases)
    selected_present = sum(int(c.source_present_not_selected) for c in selected_cases)
    diagnostic_complete = True
    if selected_absent < args.absent_sample_size or selected_present < args.present_sample_size:
        diagnostic_complete = False
        shortfall_reason = (
            f"requested absent={args.absent_sample_size}, present={args.present_sample_size}; "
            f"selected absent={selected_absent}, present={selected_present}"
        )

    selected_rows = _selected_to_rows(selected_cases)
    _write_csv(out_dir / "selected_cases.csv", selected_rows)

    expected_api_calls = len(selected_cases) * len(methods) if not args.dry_run else 0
    config_snapshot = {
        "timestamp": args.timestamp,
        "invoked_command": invoked_cmd,
        "provider": args.provider,
        "model": args.model,
        "dataset": args.dataset,
        "config": args.config,
        "split": args.split,
        "source_per_example_rows": str(args.source_per_example_rows),
        "source_row_count": source_row_count,
        "available_absent_sample_size": available_absent,
        "available_present_sample_size": available_present,
        "requested_absent_sample_size": args.absent_sample_size,
        "selected_absent_sample_size": selected_absent,
        "requested_present_sample_size": args.present_sample_size,
        "selected_present_sample_size": selected_present,
        "diagnostic_complete": diagnostic_complete,
        "shortfall_reason": shortfall_reason,
        "allow_smaller_sample": bool(args.allow_smaller_sample),
        "methods": methods,
        "selected_example_ids": [c.example_id for c in selected_cases],
        "represented_budgets": sorted({c.budget for c in selected_cases}),
        "represented_seeds": sorted({c.seed for c in selected_cases}),
        "dry_run": bool(args.dry_run),
        "dry_run_from_source": bool(args.dry_run_from_source),
        "expected_api_call_count": expected_api_calls,
        "analyzer_command": analyzer_cmd,
        "wulver_ready_real_run_command": wulver_cmd,
    }
    (out_dir / "config_snapshot.json").write_text(json.dumps(config_snapshot, indent=2) + "\n", encoding="utf-8")

    if not diagnostic_complete and not args.allow_smaller_sample:
        manifest = {
            "timestamp": args.timestamp,
            "diagnostic_complete": False,
            "shortfall_reason": shortfall_reason,
            "status": "failed_due_to_sample_shortfall",
            "completed_call_count": 0,
            "scored_call_count": 0,
            "failed_call_count": 0,
            "failure_reasons": [shortfall_reason],
            "dry_run": bool(args.dry_run),
            "expected_api_call_count": expected_api_calls,
        }
        (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        (out_dir / "README.md").write_text("# Incomplete diagnostic package\n\nSample shortfall prevented run completion.\n", encoding="utf-8")
        raise SystemExit(f"Sample shortfall: {shortfall_reason}. Use --allow-smaller-sample to proceed.")

    if not args.dry_run and args.provider == "cohere" and not os.getenv("COHERE_API_KEY", ""):
        raise SystemExit("COHERE_API_KEY is required for real reruns. Use --dry-run for offline schema validation.")

    per_example_path = out_dir / "per_example_records.jsonl"
    raw_io_path = out_dir / "raw_prompt_response_records.jsonl"
    traces: list[dict[str, Any]] = []
    status_counter = Counter()
    failure_reasons: Counter[str] = Counter()

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
                "final_branch_states": [{"branch_id": "dry_b0", "branch_depth": 0, "predicted_answer": "DRY_RUN_ANSWER", "score": 0.5, "is_done": True, "strategy_family": "dry_family"}],
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
                        traces.append(
                            build_branch_trace(
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
                        )
                    except Exception as exc:  # noqa: BLE001
                        status = "failed"
                        error = f"{type(exc).__name__}: {str(exc)[:500]}"
            else:
                traces.append(
                    {
                        "schema_version": "branch_trace_v1",
                        "top_level": {
                            "example_id": case.example_id,
                            "dataset": case.dataset,
                            "provider": case.provider,
                            "model": args.model,
                            "budget": case.budget,
                            "seed": case.seed,
                            "method": method,
                            "question_hash": "dry_hash",
                            "gold_answer": case.gold_answer_raw,
                            "final_answer": prediction,
                            "final_correct": False,
                            "actions_used": actions_used,
                            "expansions": expansions,
                            "verifications": verifications,
                            "trace_available": True,
                        },
                        "answer_groups": {
                            "answer_group_support_counts": {"DRY_RUN_ANSWER": 1},
                            "answer_group_maturity": {"DRY_RUN_ANSWER": 1},
                            "answer_group_family_counts": {"DRY_RUN_ANSWER": {"dry_family": 1}},
                            "answer_group_depth_stats": {"DRY_RUN_ANSWER": {"depth_max": 0, "depth_mean": 0.0}},
                            "answer_group_best_branch_score": {"DRY_RUN_ANSWER": 0.5},
                            "answer_group_branch_ids": {"DRY_RUN_ANSWER": ["dry_b0"]},
                        },
                        "branches": [
                            {
                                "branch_id": "dry_b0",
                                "parent_id": "",
                                "depth": (2 if case.source_absent_from_tree and case.budget >= 6 else 0),
                                "family_id": "dry_family",
                                "parsed_answer": prediction,
                                "answer_group": "DRY_RUN_ANSWER",
                                "is_resolved": True,
                                "is_selected": True,
                                "is_expanded": True,
                                "branch_score": 0.5,
                                "V": None,
                                "A": None,
                                "C": None,
                                "R": None,
                                "I": None,
                                "text_hash": "dry_text_hash",
                                "metadata": {},
                            }
                        ],
                        "direct_reserve": {},
                        "frontier_candidate": {},
                        "override_gating": {},
                        "raw_metadata": result_metadata,
                    }
                )

            status_counter[status] += 1
            if error:
                failure_reasons[error] += 1
            row = {
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
                "problem_type": case.problem_type,
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
            }
            _append_jsonl(per_example_path, row)
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
        "diagnostic_complete": diagnostic_complete,
        "shortfall_reason": shortfall_reason,
        "provider": args.provider,
        "model": args.model,
        "dataset": args.dataset,
        "config": args.config,
        "split": args.split,
        "methods": methods,
        "selected_example_ids": [c.example_id for c in selected_cases],
        "represented_budgets": sorted({c.budget for c in selected_cases}),
        "represented_seeds": sorted({c.seed for c in selected_cases}),
        "dry_run": bool(args.dry_run),
        "expected_api_call_count": expected_api_calls,
        "completed_call_count": int(sum(status_counter.values())),
        "scored_call_count": int(status_counter.get("scored", 0)),
        "failed_call_count": int(status_counter.get("failed", 0)),
        "failure_reasons": dict(failure_reasons) or {"NA": 0},
        "trace_stats": trace_stats,
        "next_analyzer_command": analyzer_cmd,
        "wulver_ready_real_run_command": wulver_cmd,
        **git_snapshot,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    readme = [
        "# F3 vs L1 Loss Trace Diagnostic Package",
        "",
        f"- Timestamp: {args.timestamp}",
        f"- Dry run: {args.dry_run}",
        f"- Diagnostic complete: {diagnostic_complete}",
        f"- Selected cases: {len(selected_cases)}",
        f"- Methods: {', '.join(methods)}",
        f"- Expected API calls: {expected_api_calls}",
        f"- Completed/scored/failed: {manifest['completed_call_count']}/{manifest['scored_call_count']}/{manifest['failed_call_count']}",
        "- Required persistence artifacts are in this directory (manifest/config/git/env/command log/records).",
    ]
    (out_dir / "README.md").write_text("\n".join(readme) + "\n", encoding="utf-8")
    print(f"Wrote diagnostic package: {out_dir}")


if __name__ == "__main__":
    main()
