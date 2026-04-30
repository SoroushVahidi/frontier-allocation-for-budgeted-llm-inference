#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

INTERNAL_METHOD_ALIASES = {
    "direct_reserve_semantic_frontier_v2": "direct_reserve_semantic_frontier_v2",
    "dr_v2": "direct_reserve_semantic_frontier_v2",
    "strict_f3": "strict_f3",
    "strict_gate1_cap_k6": "strict_gate1_cap_k6",
    "strict_f3_anti_collapse_weak_v1": "strict_f3_anti_collapse_weak_v1",
}
EXTERNAL_METHOD_ALIASES = {
    "external_l1_max": "external_l1_max",
    "l1_max": "external_l1_max",
    "l1-max": "external_l1_max",
    "external_l1_exact": "external_l1_exact",
    "l1_exact": "external_l1_exact",
    "external_tale_prompt_budgeting": "external_tale_prompt_budgeting",
    "tale": "external_tale_prompt_budgeting",
    "external_s1_budget_forcing": "external_s1_budget_forcing",
    "s1": "external_s1_budget_forcing",
    "tot_beam_matched_budget": "tot_beam_matched_budget",
    "tot_bfs_matched_budget": "tot_bfs_matched_budget",
    "tot_dfs_matched_budget": "tot_dfs_matched_budget",
}
INTERNAL_PRIORITY = [
    "direct_reserve_semantic_frontier_v2",
    "strict_f3",
    "strict_gate1_cap_k6",
    "strict_f3_anti_collapse_weak_v1",
]
EXTERNAL_PRIORITY = [
    "external_l1_max",
    "external_l1_exact",
    "external_tale_prompt_budgeting",
    "external_s1_budget_forcing",
    "tot_beam_matched_budget",
    "tot_bfs_matched_budget",
    "tot_dfs_matched_budget",
]


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _norm(v: Any) -> str:
    return str(v or "").strip()


def _canon_method(method: str) -> tuple[str, str]:
    m = _norm(method).lower()
    if m in INTERNAL_METHOD_ALIASES:
        return "internal", INTERNAL_METHOD_ALIASES[m]
    if m in EXTERNAL_METHOD_ALIASES:
        return "external", EXTERNAL_METHOD_ALIASES[m]
    return "other", _norm(method)


def _read_csv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))
    except csv.Error:
        raw = path.read_bytes().replace(b"\x00", b"")
        return list(csv.DictReader(raw.decode("utf-8", errors="ignore").splitlines()))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def _load_table_like(path: Path) -> tuple[list[dict[str, Any]], str]:
    ext = path.suffix.lower()
    if ext == ".csv":
        return _read_csv(path), "csv"
    if ext == ".tsv":
        with path.open("r", encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f, delimiter="\t")), "tsv"
    if ext == ".jsonl":
        return _read_jsonl(path), "jsonl"
    if ext == ".json":
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(obj, list):
                return [x for x in obj if isinstance(x, dict)], "json_array"
            if isinstance(obj, dict):
                for k in ("rows", "data", "records"):
                    if isinstance(obj.get(k), list):
                        return [x for x in obj[k] if isinstance(x, dict)], "json_wrapped"
        except Exception:
            pass
        return [], "json"
    if ext == ".parquet":
        try:
            import pandas as pd

            return pd.read_parquet(path).to_dict(orient="records"), "parquet"
        except Exception:
            return [], "parquet_unreadable"
    return [], "unknown"


def _discover_artifact_dirs(roots: list[Path]) -> list[Path]:
    found: set[Path] = set()
    for root in roots:
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if p.is_file() and p.suffix.lower() in {".csv", ".json", ".jsonl", ".tsv", ".parquet"}:
                found.add(p.parent)
    return sorted(found)


def _extract_method_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for r in rows:
        m = _norm(r.get("method"))
        if not m:
            continue
        kind, canon = _canon_method(m)
        if kind == "other":
            continue
        out.append({**r, "_method_kind": kind, "_method_canon": canon})
    return out


def _pick_internal(methods: set[str]) -> str:
    for m in INTERNAL_PRIORITY:
        if m in methods:
            return m
    return ""


def _pick_best_external(mm: dict[str, dict[str, Any]]) -> tuple[str, int, dict[str, Any]] | None:
    cand = []
    for m, row in mm.items():
        if m not in EXTERNAL_PRIORITY:
            continue
        ok = _safe_int(row.get("is_correct", row.get("exact_match", 0)))
        cand.append((m, ok, row))
    if not cand:
        return None
    cand.sort(key=lambda x: (x[1], x[0] == "external_l1_max", -EXTERNAL_PRIORITY.index(x[0])), reverse=True)
    return cand[0]


def _collect_groups(rows: list[dict[str, Any]], case_key: tuple[str, str, int, int]) -> list[dict[str, Any]]:
    out = []
    for r in rows:
        rk = (_norm(r.get("dataset")), _norm(r.get("example_id")), _safe_int(r.get("seed")), _safe_int(r.get("budget")))
        if rk != case_key:
            continue
        if _norm(r.get("answer_group")) or _norm(r.get("normalized_answer")):
            out.append(
                {
                    "answer": _norm(r.get("answer_group", r.get("normalized_answer"))),
                    "support": _safe_int(r.get("support", r.get("support_count", 0))),
                    "method": _norm(r.get("method")),
                }
            )
    return out


def _collect_branches(rows: list[dict[str, Any]], case_key: tuple[str, str, int, int]) -> list[dict[str, Any]]:
    out = []
    for r in rows:
        rk = (_norm(r.get("dataset")), _norm(r.get("example_id")), _safe_int(r.get("seed")), _safe_int(r.get("budget")))
        if rk != case_key:
            continue
        if any(k in r for k in ("branch_depth", "depth", "action_index", "action_count", "normalized_candidate_answer", "selector_candidate_pool")):
            out.append(r)
    return out


def is_trace_complete(row: dict[str, Any], groups: list[dict[str, Any]], branches: list[dict[str, Any]]) -> bool:
    if groups or branches:
        return True
    md = row.get("result_metadata") if isinstance(row.get("result_metadata"), dict) else {}
    return isinstance(md.get("selector_candidate_pool"), list) and bool(md.get("selector_candidate_pool"))


def _scan_artifact_dir(artifact_dir: Path, dataset_filter: str, budgets: set[int], seeds: set[int]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    files = [p for p in artifact_dir.iterdir() if p.is_file() and p.suffix.lower() in {".csv", ".jsonl", ".json", ".tsv", ".parquet"}]
    # Restrict to known method/trace tables; this prevents OOM on unrelated large blobs.
    method_like = {
        "per_case_method_results",
        "per_example_records",
        "answer_group_summary",
        "answer_group_table",
        "candidate_branch_table",
        "final_branch_states",
        "selector_tournament",
    }
    files = [p for p in files if any(k in p.name for k in method_like)]
    all_rows: list[dict[str, Any]] = []
    scan_rows: list[dict[str, Any]] = []
    for p in files:
        rows, schema = _load_table_like(p)
        if len(rows) > 200000:
            rows = rows[:200000]
        all_rows.extend(rows)
        scan_rows.append(
            {
                "artifact_path": str(p),
                "file_type": p.suffix.lower().lstrip("."),
                "schema_detected": schema,
                "row_count": len(rows),
                "datasets_found": "|".join(sorted({_norm(r.get("dataset")) for r in rows if _norm(r.get("dataset"))})),
                "methods_found": "",
                "paired_internal_external_exists": 0,
                "candidate_loss_cases": 0,
                "trace_complete_loss_cases": 0,
                "rejection_reason": "empty_or_unreadable" if not rows else "",
            }
        )

    method_rows = _extract_method_rows(all_rows)
    by_case: dict[tuple[str, str, int, int], dict[str, dict[str, Any]]] = defaultdict(dict)
    for r in method_rows:
        key = (_norm(r.get("dataset")), _norm(r.get("example_id")), _safe_int(r.get("seed")), _safe_int(r.get("budget")))
        if dataset_filter and dataset_filter not in key[0].lower():
            continue
        if budgets and key[3] not in budgets:
            continue
        if seeds and key[2] not in seeds:
            continue
        by_case[key][r["_method_canon"]] = r

    losses: list[dict[str, Any]] = []
    candidate_losses = 0
    trace_losses = 0
    paired = 0
    methods_found = sorted({m for mm in by_case.values() for m in mm.keys()})

    for case_key, mm in by_case.items():
        our_method = _pick_internal(set(mm.keys()))
        if not our_method:
            continue
        ext_pick = _pick_best_external(mm)
        if ext_pick is None:
            continue
        paired += 1
        ext_method, ext_ok, ext_row = ext_pick
        our_row = mm[our_method]
        our_ok = _safe_int(our_row.get("is_correct", our_row.get("exact_match", 0)))
        if ext_ok != 1 or our_ok == 1:
            continue
        candidate_losses += 1
        groups = _collect_groups(all_rows, case_key)
        branches = _collect_branches(all_rows, case_key)
        if not is_trace_complete(our_row, groups, branches):
            continue
        trace_losses += 1
        ds, ex, seed, budget = case_key
        gold = _norm(our_row.get("gold_answer", our_row.get("gold_answer_canonical")))
        q = _norm(our_row.get("question", our_row.get("question_raw")))
        if not q or not gold:
            continue
        our_ans = _norm(our_row.get("normalized_selected_answer", our_row.get("final_selected_answer", our_row.get("final_answer_canonical"))))
        ext_ans = _norm(ext_row.get("normalized_selected_answer", ext_row.get("final_selected_answer", ext_row.get("final_answer_canonical"))))
        unique_answers = sorted({g["answer"] for g in groups if g.get("answer")})
        gold_present = int(gold in unique_answers)
        depths = [_safe_int(b.get("branch_depth", b.get("depth", 0))) for b in branches]
        support_vals = sorted([_safe_int(g.get("support", 0)) for g in groups], reverse=True)
        top1 = support_vals[0] if support_vals else 0
        top2 = support_vals[1] if len(support_vals) > 1 else 0
        losses.append(
            {
                "case_id": f"{ds}::{ex}::{seed}::{budget}::{our_method}::{ext_method}",
                "dataset": ds,
                "example_id": ex,
                "seed": seed,
                "budget": budget,
                "internal_method": our_method,
                "best_external_method": ext_method,
                "problem_statement_short": q[:220],
                "gold_answer": gold,
                "our_final_answer": our_ans,
                "external_final_answer": ext_ans,
                "gold_present": gold_present,
                "oracle_would_fix": int(gold_present == 1),
                "candidate_group_count": len(unique_answers),
                "branch_count": len(branches),
                "max_depth": max(depths) if depths else 0,
                "answer_entropy": _safe_float(our_row.get("answer_entropy", 0.0)),
                "top1_support": top1,
                "top2_support": top2,
                "top2_support_gap": top1 - top2,
                "failure_mode": "selector_failure" if gold_present else "discovery_failure",
                "source_artifact": str(artifact_dir),
                "generated_new_or_existing": "existing",
                "all_available_external_methods": "|".join(sorted([m for m in mm.keys() if m in EXTERNAL_PRIORITY])),
                "l1_correct_but_ours_gold_absent": int(ext_method == "external_l1_max" and gold_present == 0),
                "trace_available": 1,
            }
        )

    for r in scan_rows:
        r["methods_found"] = "|".join(methods_found)
        r["paired_internal_external_exists"] = int(paired > 0)
        r["candidate_loss_cases"] = candidate_losses
        r["trace_complete_loss_cases"] = trace_losses
        if not methods_found:
            r["rejection_reason"] = r["rejection_reason"] or "no_method_rows"
        elif candidate_losses == 0:
            r["rejection_reason"] = r["rejection_reason"] or "no_external_correct_internal_wrong_losses"
        elif trace_losses == 0:
            r["rejection_reason"] = r["rejection_reason"] or "no_trace_complete_losses"
    return losses, scan_rows


def dedupe_cases(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, int, int, str, str]] = set()
    out = []
    for r in rows:
        k = (_norm(r["dataset"]), _norm(r["example_id"]), _safe_int(r["seed"]), _safe_int(r["budget"]), _norm(r["internal_method"]), _norm(r["best_external_method"]))
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields: list[str] = []
    for r in rows:
        for k in r.keys():
            if k not in fields:
                fields.append(k)
    if not fields:
        fields = ["case_id", "dataset", "example_id", "seed", "budget", "internal_method", "best_external_method"]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--target-trace-losses", type=int, default=200)
    p.add_argument("--dataset", default="gsm8k")
    p.add_argument("--budgets", nargs="+", type=int, default=[4, 6, 8])
    p.add_argument("--seeds", nargs="+", type=int, default=[11, 23, 37, 41, 53, 67])
    p.add_argument("--search-roots", nargs="+", default=["outputs", "archive", "logs", "results"])
    p.add_argument("--output-dir", required=True)
    p.add_argument("--provider", default="cohere")
    p.add_argument("--cohere-model", default="command-r-plus")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--smoke-generate", action="store_true")
    p.add_argument("--smoke-limit", type=int, default=3)
    p.add_argument("--max-generation-calls", type=int, default=2000)
    p.add_argument("--max-annotation-calls", type=int, default=200)
    return p.parse_args()


def resolve_cohere_model(model: str) -> str:
    # command-r-plus alias is stale for this repository's runner; pin to known-valid model.
    if _norm(model) == "command-r-plus":
        return "command-r-plus-08-2024"
    return _norm(model)


def short_error_excerpt(stderr_text: str, stdout_text: str, limit: int = 280) -> str:
    merged = (stderr_text or "").strip() or (stdout_text or "").strip()
    if not merged:
        return "no stderr/stdout captured"
    one_line = " | ".join([x.strip() for x in merged.splitlines() if x.strip()][:3])
    return one_line[:limit]


def count_generated_trace_artifacts(output_root: Path) -> dict[str, int]:
    per_example = list(output_root.rglob("per_example_records.jsonl"))
    branch_states = list(output_root.rglob("final_branch_states.jsonl"))
    candidate_groups = list(output_root.rglob("answer_group_summary.csv")) + list(output_root.rglob("answer_group_table.csv"))
    return {
        "generated_per_example_records_files": len(per_example),
        "generated_branch_state_files": len(branch_states),
        "generated_candidate_group_files": len(candidate_groups),
    }


def main() -> None:
    args = parse_args()
    out_dir = Path(args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    roots = sorted(set([(REPO_ROOT / r).resolve() for r in args.search_roots]))
    effective_model = resolve_cohere_model(args.cohere_model)

    budgets_for_generation = list(args.budgets)
    seeds_for_generation = list(args.seeds)
    if args.smoke_generate:
        budgets_for_generation = [4]
        seeds_for_generation = [11]

    artifact_dirs = _discover_artifact_dirs(roots)
    all_cases: list[dict[str, Any]] = []
    scan_rows: list[dict[str, Any]] = []
    for d in artifact_dirs:
        cases, sr = _scan_artifact_dir(d, args.dataset.lower(), set(args.budgets), set(args.seeds))
        all_cases.extend(cases)
        scan_rows.extend(sr)
    all_cases = dedupe_cases(all_cases)
    selected = all_cases[: args.target_trace_losses]

    existing_count = len(all_cases)
    needed = max(0, args.target_trace_losses - existing_count)
    planned_examples = needed * 4
    if args.smoke_generate:
        planned_examples = min(args.smoke_limit, max(1, planned_examples))
    expected_generation_calls = min(args.max_generation_calls, planned_examples)
    expected_annotation_calls = min(args.max_annotation_calls, args.target_trace_losses if not args.smoke_generate else args.smoke_limit)

    generation_plan = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "existing_trace_complete_losses_found": existing_count,
        "additional_trace_complete_losses_needed": needed,
        "target_trace_losses": args.target_trace_losses,
        "planned_dataset": args.dataset,
        "planned_budgets": budgets_for_generation,
        "planned_seeds": seeds_for_generation,
        "planned_internal_methods": ["direct_reserve_semantic_frontier_v2", "strict_f3"],
        "planned_external_methods": ["external_l1_max"],
        "planned_examples_to_evaluate": planned_examples,
        "expected_cohere_generation_calls": expected_generation_calls,
        "expected_cohere_diagnostic_annotation_calls": expected_annotation_calls,
        "cohere_generation_cache_path": str(out_dir / "cohere_generation_cache.jsonl"),
        "cohere_annotation_cache_path": str(out_dir / "cohere_annotation_cache.jsonl"),
        "output_dir": str(out_dir),
        "model_name": effective_model,
        "safety_cap_generation_calls": args.max_generation_calls,
        "safety_cap_annotation_calls": args.max_annotation_calls,
        "smoke_generate": bool(args.smoke_generate),
        "smoke_limit": args.smoke_limit,
    }
    print(json.dumps(generation_plan, indent=2))

    generation_started = False
    generation_error = ""
    generation_return_code: int | None = None
    runner_cmd_path = out_dir / "generation_runner_command.txt"
    runner_stdout_path = out_dir / "generation_runner_stdout.log"
    runner_stderr_path = out_dir / "generation_runner_stderr.log"
    if needed > 0 and not args.dry_run and args.provider == "cohere" and os.environ.get("COHERE_API_KEY"):
        if expected_generation_calls <= args.max_generation_calls and expected_annotation_calls <= args.max_annotation_calls:
            generation_started = True
            # Reuse existing runner with explicit bounded settings.
            ts = out_dir.name.split("_")[-1]
            cmd = [
                "python",
                "scripts/run_cohere_real_model_cost_normalized_validation.py",
                "--timestamp",
                ts,
                "--providers",
                "cohere",
                "--cohere-model",
                effective_model,
                "--datasets",
                "openai/gsm8k",
                "--budgets",
                ",".join(str(x) for x in budgets_for_generation),
                "--seeds",
                ",".join(str(x) for x in seeds_for_generation),
                "--methods",
                "direct_reserve_semantic_frontier_v2,external_l1_max",
                "--target-scored-per-slice",
                str(max(1, planned_examples // max(1, len(budgets_for_generation) * len(seeds_for_generation)))),
                "--max-examples",
                str(planned_examples if args.smoke_generate else 0),
                "--output-root",
                str(out_dir),
                "--save-branch-traces",
                "--emit-trace-audit",
            ]
            runner_cmd_path.write_text(" ".join(cmd) + "\n", encoding="utf-8")
            r = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, check=False)
            generation_return_code = r.returncode
            runner_stdout_path.write_text(r.stdout or "", encoding="utf-8")
            runner_stderr_path.write_text(r.stderr or "", encoding="utf-8")
            if r.returncode != 0:
                generation_error = f"generation_runner_failed:{r.returncode}::{short_error_excerpt(r.stderr, r.stdout)}"
        else:
            generation_error = "generation_plan_exceeds_safety_cap"
    elif needed > 0 and not args.dry_run:
        generation_error = "generation_not_started_missing_key_or_provider"

    generated_trace_counts = count_generated_trace_artifacts(out_dir)
    if args.smoke_generate and generation_started and not generation_error:
        if generated_trace_counts["generated_per_example_records_files"] == 0:
            generation_error = "smoke_generation_no_per_example_records"

    # Stage A scan again after possible generation run.
    if generation_started and not generation_error:
        all_cases = []
        scan_rows = []
        artifact_dirs = _discover_artifact_dirs(roots + [out_dir])
        for d in artifact_dirs:
            cases, sr = _scan_artifact_dir(d, args.dataset.lower(), set(args.budgets), set(args.seeds))
            all_cases.extend(cases)
            scan_rows.extend(sr)
        all_cases = dedupe_cases(all_cases)
        selected = all_cases[: args.target_trace_losses]

    # Outputs
    _write_csv(out_dir / "artifact_scan.csv", scan_rows)
    (out_dir / "artifact_scan_report.md").write_text(
        "\n".join(
            [
                "# Trace-Complete External Loss Artifact Scan",
                "",
                f"- artifact_directories_scanned: {len(artifact_dirs)}",
                f"- candidate_rows_scanned: {len(scan_rows)}",
                f"- trace_complete_losses_found: {len(all_cases)}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (out_dir / "generation_plan.json").write_text(json.dumps(generation_plan, indent=2) + "\n", encoding="utf-8")
    (out_dir / "generation_plan.md").write_text(
        "\n".join(
            [
                "# Trace-Complete Generation Plan",
                "",
                f"- existing_trace_complete_losses_found: {generation_plan['existing_trace_complete_losses_found']}",
                f"- additional_trace_complete_losses_needed: {generation_plan['additional_trace_complete_losses_needed']}",
                f"- expected_cohere_generation_calls: {generation_plan['expected_cohere_generation_calls']}",
                f"- expected_cohere_diagnostic_annotation_calls: {generation_plan['expected_cohere_diagnostic_annotation_calls']}",
                f"- model: {generation_plan['model_name']}",
                f"- output_dir: `{generation_plan['output_dir']}`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    # Required raw outputs (ignored by policy).
    with (out_dir / "trace_complete_loss_cases.jsonl").open("w", encoding="utf-8") as f:
        for r in selected:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    push_rows = []
    for r in selected:
        push_rows.append(
            {
                "case_id": r["case_id"],
                "dataset": r["dataset"],
                "example_id": r["example_id"],
                "seed": r["seed"],
                "budget": r["budget"],
                "internal_method": r["internal_method"],
                "best_external_method": r["best_external_method"],
                "problem_statement_short": r["problem_statement_short"],
                "gold_answer": r["gold_answer"],
                "our_final_answer": r["our_final_answer"],
                "external_final_answer": r["external_final_answer"],
                "gold_present": r["gold_present"],
                "oracle_would_fix": r["oracle_would_fix"],
                "candidate_group_count": r["candidate_group_count"],
                "branch_count": r["branch_count"],
                "max_depth": r["max_depth"],
                "answer_entropy": r["answer_entropy"],
                "top1_support": r["top1_support"],
                "top2_support": r["top2_support"],
                "top2_support_gap": r["top2_support_gap"],
                "failure_mode": r["failure_mode"],
                "source_artifact": r["source_artifact"],
                "generated_new_or_existing": r["generated_new_or_existing"],
            }
        )
    _write_csv(out_dir / "trace_complete_loss_cases.csv", push_rows)

    by_dataset = Counter(r["dataset"] for r in selected)
    by_budget = Counter(str(r["budget"]) for r in selected)
    by_seed = Counter(str(r["seed"]) for r in selected)
    by_internal = Counter(r["internal_method"] for r in selected)
    by_external = Counter(r["best_external_method"] for r in selected)
    gold_present = sum(int(r["gold_present"]) for r in selected)
    oracle_fix = sum(int(r["oracle_would_fix"]) for r in selected)
    l1_abs = sum(int(r["l1_correct_but_ours_gold_absent"]) for r in selected)
    failure_modes = Counter(r["failure_mode"] for r in selected)
    summary = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "existing_trace_complete_losses_found": existing_count,
        "newly_generated_trace_complete_losses": max(0, len(all_cases) - existing_count),
        "total_trace_complete_losses_collected": len(all_cases),
        "selected_for_casebook": len(selected),
        "target_trace_losses": args.target_trace_losses,
        "breakdown_by_dataset": dict(by_dataset),
        "breakdown_by_budget": dict(by_budget),
        "breakdown_by_seed": dict(by_seed),
        "breakdown_by_internal_method": dict(by_internal),
        "breakdown_by_best_external_method": dict(by_external),
        "gold_present_count": gold_present,
        "gold_present_fraction": (gold_present / len(selected)) if selected else 0.0,
        "gold_absent_count": len(selected) - gold_present,
        "gold_absent_fraction": ((len(selected) - gold_present) / len(selected)) if selected else 0.0,
        "oracle_would_fix_count": oracle_fix,
        "oracle_would_fix_fraction": (oracle_fix / len(selected)) if selected else 0.0,
        "l1_correct_but_ours_gold_absent_count": l1_abs,
        "l1_correct_but_ours_gold_absent_fraction": (l1_abs / len(selected)) if selected else 0.0,
        "most_common_failure_modes": dict(failure_modes),
        "average_candidate_group_count": mean([_safe_int(r["candidate_group_count"]) for r in selected]) if selected else 0.0,
        "average_branch_count": mean([_safe_int(r["branch_count"]) for r in selected]) if selected else 0.0,
        "average_max_depth": mean([_safe_int(r["max_depth"]) for r in selected]) if selected else 0.0,
        "primary_regime": (
            "selector_failures"
            if failure_modes.get("selector_failure", 0) > failure_modes.get("discovery_failure", 0)
            else ("discovery_failures" if failure_modes else "none")
        ),
        "recommended_next_experiment": (
            "focus on selector diagnostics for gold-present losses"
            if failure_modes.get("selector_failure", 0) > failure_modes.get("discovery_failure", 0)
            else "focus on discovery/coverage repair and branch diversity"
        ),
        "expected_cohere_generation_calls": expected_generation_calls,
        "expected_annotation_calls": expected_annotation_calls,
        "generation_started": generation_started,
        "generation_error": generation_error,
        "generation_runner_return_code": generation_return_code,
        "generation_runner_command_path": str(runner_cmd_path) if runner_cmd_path.exists() else "",
        "generation_runner_stdout_path": str(runner_stdout_path) if runner_stdout_path.exists() else "",
        "generation_runner_stderr_path": str(runner_stderr_path) if runner_stderr_path.exists() else "",
        "generation_model_used": effective_model,
        **generated_trace_counts,
    }
    (out_dir / "trace_complete_loss_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (out_dir / "trace_complete_loss_summary.md").write_text(
        "\n".join(
            [
                "# Trace-Complete External Loss Summary",
                "",
                f"- existing_trace_complete_losses_found: {summary['existing_trace_complete_losses_found']}",
                f"- newly_generated_trace_complete_losses: {summary['newly_generated_trace_complete_losses']}",
                f"- total_trace_complete_losses_collected: {summary['total_trace_complete_losses_collected']}",
                f"- selected_for_casebook: {summary['selected_for_casebook']}",
                f"- gold_present_fraction: {summary['gold_present_fraction']:.3f}",
                f"- oracle_would_fix_fraction: {summary['oracle_would_fix_fraction']:.3f}",
                f"- primary_regime: {summary['primary_regime']}",
                f"- recommended_next_experiment: {summary['recommended_next_experiment']}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (out_dir / "trace_collection_report.md").write_text(
        "\n".join(
            [
                "# Trace Collection Report",
                "",
                f"- output_dir: `{out_dir}`",
                f"- dry_run: {args.dry_run}",
                f"- smoke_generate: {args.smoke_generate}",
                f"- generation_started: {generation_started}",
                f"- generation_error: {generation_error or 'none'}",
                f"- generation_runner_return_code: {generation_return_code}",
                f"- generation_runner_command_path: `{runner_cmd_path if runner_cmd_path.exists() else ''}`",
                f"- generation_runner_stdout_path: `{runner_stdout_path if runner_stdout_path.exists() else ''}`",
                f"- generation_runner_stderr_path: `{runner_stderr_path if runner_stderr_path.exists() else ''}`",
                f"- paired_cases_collected: {len(all_cases)}",
                f"- trace_losses_selected: {len(selected)}",
                f"- generated_per_example_records_files: {summary['generated_per_example_records_files']}",
                f"- generated_branch_state_files: {summary['generated_branch_state_files']}",
                f"- generated_candidate_group_files: {summary['generated_candidate_group_files']}",
                f"- avg_candidate_groups: {summary['average_candidate_group_count']:.3f}",
                f"- avg_branch_states: {summary['average_branch_count']:.3f}",
                "- Gold labels are used only for post-hoc analysis/diagnosis and not for deployable decisions.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"output_dir": str(out_dir), "selected_trace_complete_cases": len(selected), "existing_trace_complete_found": existing_count}, indent=2))


if __name__ == "__main__":
    main()
