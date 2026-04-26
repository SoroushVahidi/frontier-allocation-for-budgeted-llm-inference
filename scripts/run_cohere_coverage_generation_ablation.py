#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
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


def _normalize_answer(raw: Any, dataset: str = "openai/gsm8k") -> str:
    if raw in (None, "", "NA"):
        return "NA"
    try:
        return str(canonicalize_answer(str(raw), dataset=dataset))
    except Exception:
        return str(raw).strip() or "NA"


def _parse_int_list(text: str) -> list[int]:
    return [int(x.strip()) for x in str(text).split(",") if x.strip()]


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        for r in rows:
            for k in r:
                if k not in fieldnames:
                    fieldnames.append(str(k))
        fieldnames = fieldnames or ["empty"]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run tiny bounded Cohere coverage-generation ablation.")
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    p.add_argument(
        "--planned-cases",
        default="outputs/bounded_real_trace_collection_20260425T_REAL_COHERE_TINY/planned_cases.csv",
    )
    p.add_argument("--provider", default="cohere")
    p.add_argument("--model", default="command-r-plus-08-2024")
    p.add_argument(
        "--methods",
        default="strict_f3,external_l1_max,direct_reserve_strong_v1,direct_reserve_strong_plus_diverse_v1",
    )
    p.add_argument("--budgets", default="4")
    p.add_argument("--seeds", default="11")
    p.add_argument("--max-cases", type=int, default=9)
    p.add_argument("--run-real-api", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--resume", action="store_true")
    p.add_argument("--emit-full-traces", action="store_true")
    p.add_argument("--selection-seed", type=int, default=11)
    p.add_argument("--temperature", type=float, default=0.2)
    p.add_argument("--max-output-tokens", type=int, default=768)
    p.add_argument("--timeout-seconds", type=int, default=90)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    run_id = f"cohere_coverage_generation_ablation_{args.timestamp}"
    out_dir = REPO_ROOT / "outputs" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    planned_rows = _read_csv(REPO_ROOT / args.planned_cases)
    if not planned_rows:
        raise SystemExit(f"No planned cases found at: {args.planned_cases}")

    methods = [m.strip() for m in str(args.methods).split(",") if m.strip()]
    budgets = _parse_int_list(args.budgets)
    seeds = _parse_int_list(args.seeds)

    base_cases: list[dict[str, Any]] = []
    seen_case = set()
    for r in planned_rows:
        eid = str(r.get("example_id", "")).strip()
        q = str(r.get("question", "")).strip()
        graw = str(r.get("gold_answer_raw") or r.get("gold_answer") or "").strip()
        ds = str(r.get("dataset") or "openai/gsm8k").strip()
        if not eid or not q or not graw:
            continue
        key = (eid, ds)
        if key in seen_case:
            continue
        seen_case.add(key)
        base_cases.append(
            {
                "example_id": eid,
                "dataset": ds,
                "question": q,
                "gold_answer_raw": graw,
                "gold_answer": _normalize_answer(graw, dataset=ds),
                "stratum": str(r.get("stratum") or "unknown"),
            }
        )

    if args.max_cases > 0:
        random.Random(args.selection_seed).shuffle(base_cases)
        base_cases = base_cases[: args.max_cases]

    expanded: list[dict[str, Any]] = []
    case_idx = 0
    for c in base_cases:
        for s in seeds:
            for b in budgets:
                case_idx += 1
                row = dict(c)
                row.update({"case_idx": case_idx, "seed": int(s), "budget": int(b)})
                expanded.append(row)

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
        "methods": methods,
        "budgets": budgets,
        "seeds": seeds,
        "planned_cases_file": str(args.planned_cases),
        "n_base_cases": len(base_cases),
        "n_runs": len(expanded) * len(methods),
        "run_real_api_requested": bool(args.run_real_api),
        "real_api_enabled": bool(real_api_enabled),
        "dry_run": bool(effective_dry),
        "resume": bool(args.resume),
        "emit_full_traces": bool(args.emit_full_traces),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    _write_csv(out_dir / "planned_cases.csv", expanded)

    existing_rows: list[dict[str, str]] = []
    done_keys: set[tuple[str, str, int, int, str]] = set()
    if args.resume:
        existing_rows = _read_csv(out_dir / "per_case_candidates.csv")
        for r in existing_rows:
            done_keys.add(
                (
                    str(r.get("example_id", "")),
                    str(r.get("dataset", "")),
                    int(r.get("seed", -1)),
                    int(r.get("budget", -1)),
                    str(r.get("method", "")),
                )
            )

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
                api_provider=args.provider,
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

    candidates: list[dict[str, Any]] = [dict(r) for r in existing_rows]

    for row in expanded:
        for method in methods:
            run_key = (str(row["example_id"]), str(row["dataset"]), int(row["seed"]), int(row["budget"]), str(method))
            if run_key in done_keys:
                continue
            runtime_method = STRICT_F3_RUNTIME if method == "strict_f3" else method
            result = None
            metadata: dict[str, Any] = {}
            final_answer = "NA"
            is_correct = 0
            failure_type = "dry_run_trace"
            actions = expansions = verifications = 0
            if real_api_enabled:
                ctrl = controllers_by_budget.get(int(row["budget"]), {}).get(runtime_method)
                if ctrl is None:
                    failure_type = "method_not_available"
                else:
                    result = ctrl.run(str(row["question"]), str(row["gold_answer_raw"]))
                    metadata = result.metadata or {}
                    final_answer = str(result.prediction or "NA")
                    is_correct = int(bool(result.is_correct))
                    failure_type = str(
                        metadata.get("early_divergence_failure_category")
                        or metadata.get("regime_failure_category")
                        or ("correct" if is_correct else "unknown")
                    )
                    actions = int(result.actions_used)
                    expansions = int(result.expansions)
                    verifications = int(result.verifications)

            final_states = list(metadata.get("final_branch_states", [])) if metadata else []
            if not final_states and final_answer != "NA":
                final_states = [
                    {
                        "branch_id": "final_prediction",
                        "predicted_answer": final_answer,
                        "group_key": _normalize_answer(final_answer, dataset=str(row["dataset"])),
                        "selected": 1,
                        "is_terminal": 1,
                    }
                ]

            selected_answer = final_answer
            selected_group = _normalize_answer(selected_answer, dataset=str(row["dataset"]))
            gold_group = str(row["gold_answer"])
            present_any = 0
            selected_gold = 0
            group_support: Counter[str] = Counter()
            emitted = 0
            for idx, b in enumerate(final_states):
                branch_answer = str(b.get("predicted_answer") or b.get("final_answer") or b.get("answer") or "NA")
                group_key = str(b.get("group_key") or _normalize_answer(branch_answer, dataset=str(row["dataset"])))
                if group_key == "NA" and branch_answer != "NA":
                    group_key = _normalize_answer(branch_answer, dataset=str(row["dataset"]))
                is_selected = int(str(b.get("selected", "0")).strip().lower() in {"1", "true", "yes"})
                if is_selected:
                    selected_group = group_key
                    selected_answer = branch_answer
                is_gold = int(group_key == gold_group)
                present_any = max(present_any, is_gold)
                selected_gold = max(selected_gold, int(is_selected and is_gold))
                group_support[group_key] += 1
                candidates.append(
                    {
                        "case_idx": row["case_idx"],
                        "example_id": row["example_id"],
                        "dataset": row["dataset"],
                        "stratum": row.get("stratum", "unknown"),
                        "seed": row["seed"],
                        "budget": row["budget"],
                        "provider": args.provider,
                        "model": args.model,
                        "method": method,
                        "runtime_method": runtime_method,
                        "branch_index": idx,
                        "branch_id": b.get("branch_id", f"b{idx}"),
                        "predicted_answer": branch_answer,
                        "answer_group": group_key,
                        "is_selected": is_selected,
                        "is_gold_group": is_gold,
                        "gold_answer": gold_group,
                        "gold_present_case": "",
                        "selected_is_gold_case": "",
                        "absent_from_pool_case": "",
                        "present_not_selected_case": "",
                        "actions": actions,
                        "expansions": expansions,
                        "verifications": verifications,
                        "failure_type": failure_type,
                        "token_estimate": metadata.get("generated_tokens_estimate", metadata.get("token_budget_predicted", "")),
                        "cost_estimate": metadata.get("estimated_cost", ""),
                    }
                )
                emitted += 1

            if emitted == 0:
                group_key = _normalize_answer(final_answer, dataset=str(row["dataset"]))
                present_any = int(group_key == gold_group)
                selected_gold = present_any
                group_support[group_key] += 1
                candidates.append(
                    {
                        "case_idx": row["case_idx"],
                        "example_id": row["example_id"],
                        "dataset": row["dataset"],
                        "stratum": row.get("stratum", "unknown"),
                        "seed": row["seed"],
                        "budget": row["budget"],
                        "provider": args.provider,
                        "model": args.model,
                        "method": method,
                        "runtime_method": runtime_method,
                        "branch_index": 0,
                        "branch_id": "final_prediction",
                        "predicted_answer": final_answer,
                        "answer_group": group_key,
                        "is_selected": 1,
                        "is_gold_group": int(group_key == gold_group),
                        "gold_answer": gold_group,
                        "gold_present_case": "",
                        "selected_is_gold_case": "",
                        "absent_from_pool_case": "",
                        "present_not_selected_case": "",
                        "actions": actions,
                        "expansions": expansions,
                        "verifications": verifications,
                        "failure_type": failure_type,
                        "token_estimate": metadata.get("generated_tokens_estimate", metadata.get("token_budget_predicted", "")),
                        "cost_estimate": metadata.get("estimated_cost", ""),
                    }
                )

            # fill case-level labels across rows for this run_key
            for c in reversed(candidates):
                if (
                    str(c["example_id"]),
                    str(c["dataset"]),
                    int(c["seed"]),
                    int(c["budget"]),
                    str(c["method"]),
                ) != run_key:
                    continue
                c["gold_present_case"] = int(present_any)
                c["selected_is_gold_case"] = int(selected_gold)
                c["absent_from_pool_case"] = int(not present_any)
                c["present_not_selected_case"] = int(present_any and not selected_gold)
                c["selected_answer_group"] = selected_group
                c["selected_answer"] = selected_answer

    _write_csv(out_dir / "per_case_candidates.csv", candidates)

    by_case: dict[tuple[str, str, int, int, str], list[dict[str, Any]]] = defaultdict(list)
    for r in candidates:
        k = (str(r["example_id"]), str(r["dataset"]), int(r["seed"]), int(r["budget"]), str(r["method"]))
        by_case[k].append(r)

    answer_group_summary: list[dict[str, Any]] = []
    method_summary_counter: dict[str, dict[str, Any]] = defaultdict(lambda: defaultdict(float))
    stratum_summary_counter: dict[tuple[str, str], dict[str, Any]] = defaultdict(lambda: defaultdict(float))
    gold_present_cases: list[dict[str, Any]] = []
    gold_absent_cases: list[dict[str, Any]] = []

    for (_, _, _, _, method), rows in by_case.items():
        first = rows[0]
        group_counts = Counter(str(r.get("answer_group", "NA")) for r in rows)
        for g, n in group_counts.items():
            answer_group_summary.append(
                {
                    "example_id": first["example_id"],
                    "dataset": first["dataset"],
                    "stratum": first.get("stratum", "unknown"),
                    "seed": first["seed"],
                    "budget": first["budget"],
                    "method": first["method"],
                    "answer_group": g,
                    "support": n,
                    "is_gold_group": int(g == str(first.get("gold_answer", "NA"))),
                    "is_selected_group": int(g == str(first.get("selected_answer_group", ""))),
                }
            )
        ms = method_summary_counter[method]
        ms["n_cases"] += 1
        ms["n_candidate_branches"] += len(rows)
        ms["n_answer_groups"] += len(group_counts)
        ms["gold_present_count"] += int(first.get("gold_present_case", 0))
        ms["selected_gold_count"] += int(first.get("selected_is_gold_case", 0))
        ms["absent_from_pool_count"] += int(first.get("absent_from_pool_case", 0))
        ms["present_not_selected_count"] += int(first.get("present_not_selected_case", 0))
        ms["actions_sum"] += float(first.get("actions", 0) or 0)
        try:
            ms["token_estimate_sum"] += float(first.get("token_estimate", 0) or 0)
        except Exception:
            pass
        try:
            ms["cost_estimate_sum"] += float(first.get("cost_estimate", 0) or 0)
        except Exception:
            pass

        stratum = str(first.get("stratum", "unknown"))
        ss = stratum_summary_counter[(method, stratum)]
        ss["n_cases"] += 1
        ss["gold_present_count"] += int(first.get("gold_present_case", 0))
        ss["selected_gold_count"] += int(first.get("selected_is_gold_case", 0))
        ss["absent_from_pool_count"] += int(first.get("absent_from_pool_case", 0))
        ss["present_not_selected_count"] += int(first.get("present_not_selected_case", 0))

        case_record = {
            "example_id": first["example_id"],
            "dataset": first["dataset"],
            "stratum": stratum,
            "seed": first["seed"],
            "budget": first["budget"],
            "method": first["method"],
            "gold_answer": first.get("gold_answer", "NA"),
            "selected_answer": first.get("selected_answer", "NA"),
            "selected_answer_group": first.get("selected_answer_group", "NA"),
            "gold_present_case": int(first.get("gold_present_case", 0)),
            "selected_is_gold_case": int(first.get("selected_is_gold_case", 0)),
            "absent_from_pool_case": int(first.get("absent_from_pool_case", 0)),
            "present_not_selected_case": int(first.get("present_not_selected_case", 0)),
        }
        if int(first.get("gold_present_case", 0)) == 1:
            gold_present_cases.append(case_record)
        else:
            gold_absent_cases.append(case_record)

    _write_csv(out_dir / "answer_group_summary.csv", answer_group_summary)
    _write_csv(out_dir / "gold_present_cases.csv", gold_present_cases)
    _write_csv(out_dir / "gold_absent_cases.csv", gold_absent_cases)

    per_method_summary: list[dict[str, Any]] = []
    for method in methods:
        m = method_summary_counter.get(method, {})
        n_cases = int(m.get("n_cases", 0))
        per_method_summary.append(
            {
                "method": method,
                "n_cases": n_cases,
                "n_candidate_branches": int(m.get("n_candidate_branches", 0)),
                "n_answer_groups": int(m.get("n_answer_groups", 0)),
                "gold_present_count": int(m.get("gold_present_count", 0)),
                "gold_present_rate": float(m.get("gold_present_count", 0) / max(1, n_cases)),
                "selected_gold_count": int(m.get("selected_gold_count", 0)),
                "selected_gold_rate": float(m.get("selected_gold_count", 0) / max(1, n_cases)),
                "absent_from_pool_count": int(m.get("absent_from_pool_count", 0)),
                "absent_from_pool_rate": float(m.get("absent_from_pool_count", 0) / max(1, n_cases)),
                "present_not_selected_count": int(m.get("present_not_selected_count", 0)),
                "present_not_selected_rate": float(m.get("present_not_selected_count", 0) / max(1, n_cases)),
                "avg_actions": float(m.get("actions_sum", 0.0) / max(1, n_cases)),
                "token_estimate_sum": float(m.get("token_estimate_sum", 0.0)),
                "cost_estimate_sum": float(m.get("cost_estimate_sum", 0.0)),
            }
        )
    _write_csv(out_dir / "per_method_summary.csv", per_method_summary)

    per_stratum_summary: list[dict[str, Any]] = []
    for (method, stratum), s in sorted(stratum_summary_counter.items()):
        n_cases = int(s.get("n_cases", 0))
        per_stratum_summary.append(
            {
                "method": method,
                "stratum": stratum,
                "n_cases": n_cases,
                "gold_present_count": int(s.get("gold_present_count", 0)),
                "gold_present_rate": float(s.get("gold_present_count", 0) / max(1, n_cases)),
                "selected_gold_count": int(s.get("selected_gold_count", 0)),
                "selected_gold_rate": float(s.get("selected_gold_count", 0) / max(1, n_cases)),
                "absent_from_pool_count": int(s.get("absent_from_pool_count", 0)),
                "present_not_selected_count": int(s.get("present_not_selected_count", 0)),
            }
        )
    _write_csv(out_dir / "per_stratum_summary.csv", per_stratum_summary)

    coverage_summary = [
        {
            "n_cases": len(by_case),
            "n_methods": len({k[4] for k in by_case.keys()}),
            "real_api_enabled": int(real_api_enabled),
            "n_candidate_rows": len(candidates),
            "n_answer_group_rows": len(answer_group_summary),
            "n_gold_present_cases": len(gold_present_cases),
            "n_gold_absent_cases": len(gold_absent_cases),
        }
    ]
    _write_csv(out_dir / "coverage_summary.csv", coverage_summary)

    readme = "\n".join(
        [
            f"# Cohere coverage-generation ablation ({args.timestamp})",
            "",
            f"Run id: `{run_id}`",
            f"Provider/model: `{args.provider}` / `{args.model}`",
            f"Real API enabled: `{real_api_enabled}`",
            "",
            "## Files",
            "- manifest.json",
            "- planned_cases.csv",
            "- per_case_candidates.csv",
            "- answer_group_summary.csv",
            "- coverage_summary.csv",
            "- per_method_summary.csv",
            "- per_stratum_summary.csv",
            "- gold_present_cases.csv",
            "- gold_absent_cases.csv",
            "",
            "Dry-run mode writes schema-compatible artifacts without making external API calls.",
        ]
    )
    (out_dir / "README.md").write_text(readme + "\n", encoding="utf-8")
    print(f"Wrote: {out_dir}")


if __name__ == "__main__":
    main()
