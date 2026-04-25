#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import random
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.data import extract_final_answer
from experiments.frontier_matrix_core import build_frontier_strategies, generator_factory_for_mode
from experiments.output_layer_repair import canonicalize_answer

STRICT_F3_RUNTIME = (
    "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_"
    "repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth3_coverage_forced_v1"
)
TRACE_FIELDS = [
    "timestamp_utc","run_id","case_id","example_id","dataset","seed","budget","provider","model","method",
    "event_type","action_index","branch_id","parent_branch_id","branch_depth","strategy_family","prompt_text",
    "response_text","reasoning_text","extracted_answer","normalized_answer","answer_group","branch_score",
    "base_priority_score","reasoning_signature_key","operation_sequence_key","reasoning_role","strategy_family_novelty",
    "operation_sequence_novelty","intermediate_value_novelty","answer_group_novelty","reasoning_role_novelty",
    "redundancy_penalty","plausibility_score","useful_reasoning_diversity_bonus","final_priority_with_reasoning_diversity",
    "selected_due_to_reasoning_diversity","selected_for_expansion","selected_final_answer","is_final_commit","is_correct",
    "failure_type","missing_fields",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Trace-enabled 10-case reasoning-diversity rerun")
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    p.add_argument("--max-cases", type=int, default=10)
    p.add_argument("--case-package", default="outputs/ten_case_loss_deep_dive_20260425T221500Z/")
    p.add_argument("--case-report", default="docs/TEN_CASE_LOSS_DEEP_DIVE_20260425T221500Z.md")
    p.add_argument("--provider", default="cohere")
    p.add_argument("--cohere-model", default="command-r-plus-08-2024")
    p.add_argument("--methods", default="strict_f3,strict_f3_reasoning_diversity_bonus_v1,external_l1_max")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--skip-real-api-if-no-key", action="store_true")
    p.add_argument("--resume", action="store_true")
    p.add_argument("--emit-full-traces", action="store_true")
    p.add_argument("--temperature", type=float, default=0.2)
    p.add_argument("--max-output-tokens", type=int, default=180)
    p.add_argument("--timeout-seconds", type=int, default=45)
    return p.parse_args()


def write_csv(path: Path, rows: list[dict[str, Any]], header: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in header})


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def normalize_answer(raw: Any, dataset: str = "openai/gsm8k") -> str:
    if raw in (None, "", "NA"):
        return "NA"
    try:
        return str(canonicalize_answer(str(raw), dataset=dataset))
    except Exception:
        return "NA"


def parse_deep_dive_report(path: Path, max_cases: int) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    case_pat = re.compile(r"## Case (\d+):\s*([^,]+),\s*seed=(\d+),\s*budget=(\d+)\n(.*?)(?=\n## Case \d+:|\Z)", re.S)
    out: list[dict[str, Any]] = []
    for m in case_pat.finditer(text):
        body = m.group(5)
        q = re.search(r"### Problem\n(.*?)\n\n### Gold answer", body, re.S)
        raw = re.search(r"### Gold answer\nRaw:\s*(.*?)\nNormalized:", body, re.S)
        norm = re.search(r"Normalized:\s*(.*?)\n", body)
        out.append(
            {
                "case_idx": int(m.group(1)),
                "example_id": m.group(2).strip(),
                "seed": int(m.group(3)),
                "budget": int(m.group(4)),
                "dataset": "openai/gsm8k",
                "question": (q.group(1).strip() if q else ""),
                "gold_answer_raw": (raw.group(1).strip() if raw else ""),
                "gold_answer": (norm.group(1).strip() if norm else extract_final_answer(raw.group(1) if raw else "")),
            }
        )
    return out[:max_cases]


def event_row(base: dict[str, Any], event_type: str, action_index: int | None = None, **kwargs: Any) -> dict[str, Any]:
    row = {k: None for k in TRACE_FIELDS}
    row.update(base)
    row["timestamp_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    row["event_type"] = event_type
    row["action_index"] = action_index
    row.update(kwargs)
    missing = [k for k, v in row.items() if k not in {"timestamp_utc", "run_id", "case_id", "event_type", "missing_fields"} and v is None]
    row["missing_fields"] = missing
    return row


def main() -> None:
    args = parse_args()
    methods = [m.strip() for m in args.methods.split(",") if m.strip()]
    run_id = f"ten_case_reasoning_diversity_trace_rerun_{args.timestamp}"
    out_dir = REPO_ROOT / "outputs" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    cases = parse_deep_dive_report(REPO_ROOT / args.case_report, args.max_cases)
    if len(cases) > args.max_cases:
        cases = cases[: args.max_cases]

    key_present = bool(os.getenv("COHERE_API_KEY"))
    real_api_enabled = (not args.dry_run) and key_present
    skipped_missing_key = (not args.dry_run) and (not key_present) and args.skip_real_api_if_no_key

    (out_dir / "run_config.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "timestamp": args.timestamp,
                "max_cases": args.max_cases,
                "provider": args.provider,
                "model": args.cohere_model,
                "methods": methods,
                "dry_run": args.dry_run,
                "real_api_enabled": real_api_enabled,
                "skipped_missing_key": skipped_missing_key,
                "diagnostic_label": "diagnostic/probe",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    if skipped_missing_key:
        (out_dir / "missing_key_report.json").write_text(json.dumps({"missing": "COHERE_API_KEY"}, indent=2), encoding="utf-8")

    write_csv(out_dir / "ten_case_inputs.csv", cases, ["case_idx","example_id","seed","budget","dataset","question","gold_answer_raw","gold_answer"])
    write_jsonl(out_dir / "ten_case_inputs.jsonl", cases)

    budgets = sorted({int(c["budget"]) for c in cases} or [4])
    controllers: dict[int, dict[str, Any]] = {}
    for b in budgets:
        rng = random.Random(1000 + b)
        factory = generator_factory_for_mode(
            use_openai_api=real_api_enabled,
            rng=rng,
            openai_model=args.cohere_model,
            temperature=args.temperature,
            max_output_tokens=args.max_output_tokens,
            timeout_seconds=args.timeout_seconds,
            api_provider=args.provider,
        )
        ctrls = build_frontier_strategies(
            generator_factory=factory,
            budget=b,
            adaptive_min_expand_grid=[1],
            rng=rng,
            use_openai_api=real_api_enabled,
            include_broad_diversity_aggregation_methods=True,
            include_external_l1_baseline=True,
        )
        for ctrl in ctrls.values():
            setattr(ctrl, "emit_full_traces", bool(args.emit_full_traces))
        controllers[b] = ctrls

    per_case: list[dict[str, Any]] = []
    traces: list[dict[str, Any]] = []
    branch_rows: list[dict[str, Any]] = []
    action_rows: list[dict[str, Any]] = []
    ag_rows: list[dict[str, Any]] = []
    rd_rows: list[dict[str, Any]] = []
    final_diag_rows: list[dict[str, Any]] = []

    for case_i, case in enumerate(cases, start=1):
        for method in methods:
            runtime = STRICT_F3_RUNTIME if method == "strict_f3" else method
            ctrl = controllers[int(case["budget"])].get(runtime)
            if ctrl is None:
                continue
            base = {
                "run_id": run_id,
                "case_id": case_i,
                "example_id": case["example_id"],
                "dataset": case["dataset"],
                "seed": case["seed"],
                "budget": case["budget"],
                "provider": args.provider,
                "model": args.cohere_model,
                "method": method,
            }
            traces.append(event_row(base, "case_start", prompt_text=case["question"], normalized_answer=normalize_answer(case["gold_answer"])))

            if args.dry_run or skipped_missing_key:
                md = {"action_trace": [], "final_branch_states": []}
                pred = "NA"
                ok = False
                acts = exps = vers = 0
                failure_type = "dry_run_trace"
            else:
                res = ctrl.run(case["question"], case["gold_answer"])
                md = res.metadata or {}
                pred = res.prediction
                ok = bool(res.is_correct)
                acts, exps, vers = int(res.actions_used), int(res.expansions), int(res.verifications)
                failure_type = str(md.get("early_divergence_failure_category") or md.get("regime_failure_category") or "")

            norm_pred = normalize_answer(pred)
            per_case.append(
                {
                    "case_idx": case_i,
                    "example_id": case["example_id"],
                    "seed": case["seed"],
                    "budget": case["budget"],
                    "method": method,
                    "runtime_method": runtime,
                    "final_answer": pred,
                    "normalized_answer": norm_pred,
                    "is_correct": int(ok),
                    "failure_type": failure_type,
                    "actions": acts,
                    "expansions": exps,
                    "verifications": vers,
                }
            )
            action_trace = list(md.get("action_trace", [])) if isinstance(md.get("action_trace", []), list) else []
            for ai, a in enumerate(action_trace):
                evt = event_row(
                    base,
                    "branch_selected_for_expansion" if a.get("action") == "expand" else "branch_scored",
                    action_index=ai,
                    branch_id=a.get("branch_id"),
                    parent_branch_id=a.get("parent_branch_id"),
                    branch_depth=a.get("branch_depth"),
                    strategy_family=a.get("strategy_family"),
                    prompt_text=a.get("prompt_text"),
                    response_text=a.get("response_text"),
                    reasoning_text=a.get("reasoning_text"),
                    extracted_answer=a.get("extracted_answer"),
                    normalized_answer=normalize_answer(a.get("extracted_answer")),
                    answer_group=a.get("group_key"),
                    branch_score=a.get("priority"),
                    base_priority_score=a.get("base_priority_score"),
                    reasoning_signature_key=a.get("reasoning_signature_key"),
                    operation_sequence_key=a.get("operation_sequence_key"),
                    reasoning_role=a.get("reasoning_role"),
                    strategy_family_novelty=a.get("strategy_family_novelty"),
                    operation_sequence_novelty=a.get("operation_sequence_novelty"),
                    intermediate_value_novelty=a.get("intermediate_value_novelty"),
                    answer_group_novelty=a.get("answer_group_novelty"),
                    reasoning_role_novelty=a.get("reasoning_role_novelty"),
                    redundancy_penalty=a.get("redundancy_penalty"),
                    plausibility_score=a.get("plausibility_score"),
                    useful_reasoning_diversity_bonus=a.get("useful_reasoning_diversity_bonus"),
                    final_priority_with_reasoning_diversity=a.get("final_priority_with_reasoning_diversity"),
                    selected_due_to_reasoning_diversity=a.get("selected_due_to_reasoning_diversity"),
                    selected_for_expansion=(a.get("action") == "expand"),
                )
                traces.append(evt)
                action_rows.append({**base, "action_index": ai, **a})
                if a.get("group_key") not in (None, ""):
                    ag_rows.append({**base, "action_index": ai, "answer_group": a.get("group_key"), "branch_id": a.get("branch_id")})
                if method == "strict_f3_reasoning_diversity_bonus_v1":
                    rd_rows.append(
                        {
                            **base,
                            "action_index": ai,
                            "branch_id": a.get("branch_id"),
                            "base_priority_score": a.get("base_priority_score"),
                            "strategy_family_novelty": a.get("strategy_family_novelty"),
                            "operation_sequence_novelty": a.get("operation_sequence_novelty"),
                            "intermediate_value_novelty": a.get("intermediate_value_novelty"),
                            "answer_group_novelty": a.get("answer_group_novelty"),
                            "reasoning_role_novelty": a.get("reasoning_role_novelty"),
                            "redundancy_penalty": a.get("redundancy_penalty"),
                            "plausibility_score": a.get("plausibility_score"),
                            "useful_reasoning_diversity_bonus": a.get("useful_reasoning_diversity_bonus"),
                            "final_priority_with_reasoning_diversity": a.get("final_priority_with_reasoning_diversity"),
                            "selected_due_to_reasoning_diversity": a.get("selected_due_to_reasoning_diversity"),
                        }
                    )

            for b in list(md.get("final_branch_states", [])) if isinstance(md.get("final_branch_states", []), list) else []:
                branch_rows.append({**base, **b})

            final_evt = event_row(
                base,
                "final_selection",
                selected_final_answer=pred,
                normalized_answer=norm_pred,
                is_correct=ok,
                failure_type=failure_type,
                is_final_commit=True,
            )
            traces.append(final_evt)
            traces.append(event_row(base, "case_end", selected_final_answer=pred, is_correct=ok, failure_type=failure_type))
            final_diag_rows.append({**base, "final_answer": pred, "normalized_answer": norm_pred, "is_correct": int(ok), "failure_type": failure_type})

    by_method: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in per_case:
        by_method[r["method"]].append(r)
    summary = []
    for m in methods:
        rows = by_method[m]
        summary.append({"method": m, "n": len(rows), "accuracy": (sum(int(r["is_correct"]) for r in rows) / max(1, len(rows)))})

    strict = {(r["example_id"], r["seed"], r["budget"]): r for r in per_case if r["method"] == "strict_f3"}
    bonus = {(r["example_id"], r["seed"], r["budget"]): r for r in per_case if r["method"] == "strict_f3_reasoning_diversity_bonus_v1"}
    repair, hurt = [], []
    for k, s in strict.items():
        b = bonus.get(k)
        if not b:
            continue
        if int(s["is_correct"]) == 0 and int(b["is_correct"]) == 1:
            repair.append({"example_id": k[0], "seed": k[1], "budget": k[2], "type": "repair"})
        if int(s["is_correct"]) == 1 and int(b["is_correct"]) == 0:
            hurt.append({"example_id": k[0], "seed": k[1], "budget": k[2], "type": "hurt"})

    miss_counter: Counter[str] = Counter()
    for t in traces:
        for k in t.get("missing_fields", []):
            miss_counter[k] += 1
    missing_rows = [{"field": k, "missing_count": v} for k, v in sorted(miss_counter.items())]

    write_csv(out_dir / "per_case_results.csv", per_case, ["case_idx","example_id","seed","budget","method","runtime_method","final_answer","normalized_answer","is_correct","failure_type","actions","expansions","verifications"])
    write_csv(out_dir / "per_method_summary.csv", summary, ["method","n","accuracy"])
    write_jsonl(out_dir / "full_trace_events.jsonl", traces)
    for m, fn in [("strict_f3","strict_f3_trace_events.jsonl"),("strict_f3_reasoning_diversity_bonus_v1","reasoning_diversity_trace_events.jsonl"),("external_l1_max","external_l1_max_trace_events.jsonl")]:
        write_jsonl(out_dir / fn, [t for t in traces if t.get("method") == m])

    write_csv(out_dir / "branch_table.csv", branch_rows, sorted({k for r in branch_rows for k in r.keys()}) or ["example_id","method","branch_id"])
    write_jsonl(out_dir / "branch_table.jsonl", branch_rows)
    write_csv(out_dir / "action_trace.csv", action_rows, sorted({k for r in action_rows for k in r.keys()}) or ["example_id","method","action"])
    write_jsonl(out_dir / "action_trace.jsonl", action_rows)
    write_csv(out_dir / "answer_group_table.csv", ag_rows, sorted({k for r in ag_rows for k in r.keys()}) or ["example_id","method","answer_group"])
    write_jsonl(out_dir / "answer_group_table.jsonl", ag_rows)
    write_csv(out_dir / "reasoning_diversity_components.csv", rd_rows, sorted({k for r in rd_rows for k in r.keys()}) or ["example_id","method","branch_id"])
    write_jsonl(out_dir / "reasoning_diversity_components.jsonl", rd_rows)
    write_csv(out_dir / "final_selection_diagnostics.csv", final_diag_rows, sorted({k for r in final_diag_rows for k in r.keys()}) or ["example_id","method","final_answer"])
    write_csv(out_dir / "repair_cases.csv", repair, ["example_id","seed","budget","type"])
    write_csv(out_dir / "hurt_cases.csv", hurt, ["example_id","seed","budget","type"])
    write_csv(out_dir / "missing_fields_report.csv", missing_rows, ["field","missing_count"])

    readme = (
        "# 10-case reasoning-diversity trace rerun (diagnostic/probe)\n\n"
        f"Run id: `{run_id}`\n\n"
        f"Dry run: `{args.dry_run}`; real API enabled: `{real_api_enabled}`; skipped missing key: `{skipped_missing_key}`.\n\n"
        "This package is diagnostic/probe-labeled and limited to exactly the ten deep-dive cases.\n"
    )
    (out_dir / "README.md").write_text(readme, encoding="utf-8")

    by_case_method = {(r["example_id"], r["method"]): r for r in per_case}
    lines = ["# Casebook: 10-case reasoning-diversity trace rerun\n"]
    for idx, c in enumerate(cases, start=1):
        lines.append(f"## Case {idx}: {c['example_id']}, seed={c['seed']}, budget={c['budget']}\n")
        lines.append("### Problem\n" + c["question"] + "\n")
        lines.append("### Gold answer\n")
        lines.append(f"Raw: {c['gold_answer_raw']}\n")
        lines.append(f"Normalized: {normalize_answer(c['gold_answer'])}\n")
        lines.append("### Method comparison\n")
        lines.append("| method | final answer | normalized answer | correct | failure type | actions | expansions | verifications |\n|---|---:|---:|---:|---|---:|---:|---:|\n")
        for m in methods:
            r = by_case_method.get((c["example_id"], m), {})
            lines.append(f"| {m} | {r.get('final_answer','NA')} | {r.get('normalized_answer','NA')} | {r.get('is_correct',0)} | {r.get('failure_type','')} | {r.get('actions',0)} | {r.get('expansions',0)} | {r.get('verifications',0)} |\n")
        lines.append("\n### strict_f3 trace summary\n- selected final answer: see table\n- answer groups: see answer_group_table.csv\n- whether gold appeared: infer from answer_group_table.csv\n- selected wrong group if any: infer from final_selection_diagnostics.csv\n- action trace summary: see action_trace.csv\n- branch table: see branch_table.csv\n")
        lines.append("\n### reasoning-diversity policy trace summary\n- selected final answer: see table\n- answer groups: see answer_group_table.csv\n- whether gold appeared: infer from answer_group_table.csv\n- selected wrong group if any: infer from final_selection_diagnostics.csv\n- diversity components that affected selection: see reasoning_diversity_components.csv\n- whether branch selection changed relative to strict_f3: compare selected_due_to_reasoning_diversity flags\n- whether final answer changed relative to strict_f3: compare method rows\n- whether it repaired or hurt the case: see repair_cases.csv / hurt_cases.csv\n")
        lines.append("\n### external_l1_max trace summary\n- final answer: see table\n- extracted answer: see action_trace.csv\n- response text summary: see action_trace.csv\n- why it was correct or incorrect if inferable: infer from traces\n")
        lines.append("\n### Diagnosis\nBased only on logged evidence in this package, classify absent-from-tree vs present-not-selected from failure_type and answer-group traces.\n\n")
    (out_dir / "casebook.md").write_text("".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
