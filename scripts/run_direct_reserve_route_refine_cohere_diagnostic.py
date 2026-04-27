#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import random
import re
import subprocess
import sys
import time
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
SOURCE_LOSS_PATH = (
    REPO_ROOT
    / "outputs"
    / "cohere_absent_from_tree_loss_diagnostics_20260427T171917Z"
    / "loss_cases_absent_from_tree.jsonl"
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Run diagnostic direct_reserve_route_refine_v1 on Cohere with readiness checks "
            "and max-cases safety cap."
        )
    )
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    p.add_argument("--provider", default="cohere")
    p.add_argument("--model", default="command-r-plus-08-2024")
    p.add_argument("--dataset", default="openai/gsm8k")
    p.add_argument("--budget", type=int, default=4)
    p.add_argument("--seed", type=int, default=23)
    p.add_argument("--max-cases", type=int, default=4)
    p.add_argument("--source-loss-jsonl", default=str(SOURCE_LOSS_PATH))
    p.add_argument("--temperature", type=float, default=0.2)
    p.add_argument("--max-output-tokens", type=int, default=768)
    p.add_argument("--timeout-seconds", type=int, default=90)
    p.add_argument("--smoke-timeout-seconds", type=int, default=45)
    p.add_argument("--run-live-rerun", action="store_true")
    return p.parse_args()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not path.exists():
        return out
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
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


def safe_float(v: Any, default: float = 0.0) -> float:
    try:
        if isinstance(v, str) and v.strip().upper() == "NA":
            return default
        return float(v)
    except Exception:
        return default


def safe_int(v: Any, default: int = 0) -> int:
    try:
        if isinstance(v, str) and v.strip().upper() == "NA":
            return default
        return int(float(v))
    except Exception:
        return default


def detect_runtime_context() -> str:
    if os.getenv("SLURM_JOB_ID"):
        return "slurm"
    if os.getenv("SSH_CONNECTION") or os.getenv("SSH_CLIENT"):
        return "ssh"
    if os.getenv("CURSOR_TRACE_ID") or os.getenv("CURSOR_AGENT") or os.getenv("CURSOR_IDE"):
        return "cursor"
    return "local"


def classify_failure(text: str) -> str:
    t = (text or "").lower()
    if "missing cohere_api_key" in t or "cohere_api_key is missing" in t:
        return "missing_env_var"
    if "401" in t or "unauthorized" in t or "invalid api key" in t:
        return "authentication_failed"
    if "403" in t or "forbidden" in t or ("model" in t and ("not found" in t or "unavailable" in t or "access" in t)):
        return "permission_or_model_access_denied"
    if "quota" in t or "billing" in t or "insufficient" in t or "credit" in t or "429" in t:
        return "quota_or_billing_limit"
    if "timeout" in t or "timed out" in t or "network" in t or "connection" in t or "dns" in t:
        return "network_or_timeout"
    if "module" in t or "import" in t or "no module named" in t or "pip" in t:
        return "package_or_import_error"
    return "unknown_api_error"


def fix_for_failure(failure_class: str) -> str:
    mapping = {
        "missing_env_var": "Set/export COHERE_API_KEY in the same shell/session where Cursor runs this command.",
        "authentication_failed": "Verify the key is correct and active in Cohere dashboard.",
        "permission_or_model_access_denied": "Check access to command-r-plus-08-2024 or switch to an available Cohere model.",
        "quota_or_billing_limit": "Check Cohere usage/quota/billing.",
        "network_or_timeout": "Retry from a networked environment or cluster node with outbound access.",
        "package_or_import_error": "Install/upgrade the Cohere SDK dependency used by the repo.",
        "unknown_api_error": "Inspect sanitized error output and retry with verified key/model/network.",
    }
    return mapping.get(failure_class, mapping["unknown_api_error"])


def write_issue_report(
    *,
    out_dir: Path,
    timestamp: str,
    model: str,
    key_present: bool,
    failure_class: str,
    error_message: str,
    rerun_command: str,
) -> None:
    runtime_context = detect_runtime_context()
    sanitized = error_message
    key = os.getenv("COHERE_API_KEY", "")
    if key:
        sanitized = sanitized.replace(key, "[REDACTED]")
    lines = [
        "# Cohere API key issue report",
        "",
        f"- Timestamp (UTC): {timestamp}",
        f"- Runtime context (detected): `{runtime_context}`",
        f"- Model: `{model}`",
        f"- `COHERE_API_KEY` presence: `{'present' if key_present else 'absent'}`",
        f"- Failure class: `{failure_class}`",
        "",
        "## What happened",
        (
            "- `COHERE_API_KEY` is missing from the current process environment."
            if failure_class == "missing_env_var"
            else "- Cohere readiness/smoke test failed before rerun."
        ),
        "",
        "## How to fix",
        f"- {fix_for_failure(failure_class)}",
        "- Set key format (placeholder only):",
        "```bash",
        'export COHERE_API_KEY="..."',
        "```",
        "",
        "## Exact rerun command",
        "```bash",
        rerun_command,
        "```",
        "",
        "## Sanitized error",
        "```text",
        sanitized[:2000] if sanitized else "N/A",
        "```",
    ]
    (out_dir / "cohere_api_key_issue.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_readiness_check(*, model: str, smoke_timeout_seconds: int) -> tuple[bool, str, dict[str, Any]]:
    key_present = bool(os.getenv("COHERE_API_KEY"))
    print(f"COHERE_API_KEY: {'present' if key_present else 'absent'}")
    if not key_present:
        return False, "missing_env_var", {"status": "missing key"}
    cmd = [
        sys.executable,
        "-c",
        (
            "import os,json,cohere;"
            "c=cohere.ClientV2(api_key=os.environ['COHERE_API_KEY']);"
            f"r=c.chat(model='{model}',messages=[{{'role':'user','content':'OK'}}],max_tokens=2);"
            "p=r.model_dump() if hasattr(r,'model_dump') else (r if isinstance(r,dict) else {});"
            "u=(p.get('usage',{}) if isinstance(p,dict) else {});"
            "t=(u.get('tokens',{}) if isinstance(u,dict) else {});"
            "print(json.dumps({'status':'success','model':'" + model + "','tokens':t}))"
        ),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=smoke_timeout_seconds)
    except subprocess.TimeoutExpired:
        return False, "network_or_timeout", {"status": "failure", "model": model, "error": f"smoke test timed out after {smoke_timeout_seconds}s"}
    if proc.returncode != 0:
        msg = (proc.stderr or proc.stdout or "unknown smoke failure").strip()
        failure_class = classify_failure(msg)
        print(f"smoke_test: failure model={model} class={failure_class}")
        return False, failure_class, {"status": "failure", "model": model, "error": msg}
    payload: dict[str, Any] = {"status": "success", "model": model, "tokens": {}}
    try:
        payload = json.loads(proc.stdout.strip().splitlines()[-1])
    except Exception:
        payload = {"status": "success", "model": model, "tokens": {}}
    print(f"smoke_test: success model={model}")
    print(f"smoke_tokens: {json.dumps(payload.get('tokens', {}), sort_keys=True)}")
    return True, "ok", payload


def choose_cases(rows: list[dict[str, Any]], dataset: str, max_cases: int, seed: int) -> list[dict[str, Any]]:
    # Focus: strict_f3 loses while external_l1_max wins (same as motivation).
    filtered = [
        r
        for r in rows
        if str(r.get("dataset")) == dataset
        and str(r.get("internal_method_name")) == "strict_f3"
        and str(r.get("external_baseline_name")) == "external_l1_max"
    ]
    if not filtered:
        return []
    rng = random.Random(seed)
    filtered.sort(
        key=lambda r: (
            0 if str(r.get("absent_from_tree_status")) == "confirmed_absent_from_tree" else 1,
            {"immediate_miss": 0, "partial_progress": 1, "near_miss_absent_final": 2}.get(str(r.get("path_proximity_bucket")), 9),
            int(r.get("seed", 999)),
            int(r.get("budget", 999)),
        )
    )
    # Keep distinct ids first for breadth.
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for r in filtered:
        eid = str(r.get("example_id", ""))
        if not eid or eid in seen:
            continue
        selected.append(r)
        seen.add(eid)
        if len(selected) >= max_cases:
            break
    if len(selected) < max_cases:
        rest = [r for r in filtered if str(r.get("example_id", "")) not in seen]
        rng.shuffle(rest)
        selected.extend(rest[: max_cases - len(selected)])
    return selected[:max_cases]


def canonical(ans: Any, dataset: str) -> str:
    return str(canonicalize_answer(str(ans or ""), dataset=dataset))


def number_count(text: str) -> int:
    return len(re.findall(r"[-+]?\d+(?:\.\d+)?", text or ""))


def build_specs(*, budget: int, model: str, temperature: float, max_output_tokens: int, timeout_seconds: int, seed: int) -> dict[str, Any]:
    rng = random.Random(seed)
    factory = generator_factory_for_mode(
        use_openai_api=True,
        rng=rng,
        openai_model=model,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        timeout_seconds=timeout_seconds,
        api_provider="cohere",
    )
    return build_frontier_strategies(
        generator_factory=factory,
        budget=budget,
        adaptive_min_expand_grid=[1],
        rng=rng,
        use_openai_api=True,
        include_broad_diversity_aggregation_methods=True,
        include_external_l1_baseline=True,
    )


def main() -> None:
    args = parse_args()
    if args.provider != "cohere":
        raise SystemExit("This diagnostic currently supports --provider cohere only.")
    if args.max_cases > 30:
        raise SystemExit("Refusing run: --max-cases must be <= 30.")

    ts = args.timestamp
    out_dir = REPO_ROOT / "outputs" / f"direct_reserve_route_refine_cohere_diagnostic_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)
    rerun_command = (
        f'python scripts/run_direct_reserve_route_refine_cohere_diagnostic.py --timestamp {ts} --provider cohere '
        f'--dataset {args.dataset} --model "{args.model}" --max-cases {args.max_cases} --run-live-rerun'
    )

    if not args.run_live_rerun:
        (out_dir / "candidate_next_changes.md").write_text(
            "# Candidate next changes\n\n- Live run not executed. Re-run with `--run-live-rerun`.\n",
            encoding="utf-8",
        )
        (out_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "artifact_family": "direct_reserve_route_refine_cohere_diagnostic",
                    "timestamp": ts,
                    "provider": args.provider,
                    "model": args.model,
                    "run_live_rerun": False,
                    "note": "Selection-only mode for safety.",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(str(out_dir.relative_to(REPO_ROOT)))
        print("cohere_api_key_present=not_checked")
        print("smoke_test_passed=not_run")
        print("selected_cases=0")
        return

    readiness_ok, failure_class, smoke = run_readiness_check(model=args.model, smoke_timeout_seconds=args.smoke_timeout_seconds)
    if not readiness_ok:
        write_issue_report(
            out_dir=out_dir,
            timestamp=ts,
            model=args.model,
            key_present=bool(os.getenv("COHERE_API_KEY")),
            failure_class=failure_class,
            error_message=str(smoke.get("error", smoke.get("status", ""))),
            rerun_command=rerun_command,
        )
        raise SystemExit(f"Cohere readiness failed ({failure_class}); see {out_dir}/cohere_api_key_issue.md")

    source_rows = read_jsonl(Path(args.source_loss_jsonl))
    selected = choose_cases(source_rows, args.dataset, args.max_cases, args.seed)
    if not selected:
        raise SystemExit("No eligible cases found in source loss JSONL.")

    specs = build_specs(
        budget=args.budget,
        model=args.model,
        temperature=args.temperature,
        max_output_tokens=args.max_output_tokens,
        timeout_seconds=args.timeout_seconds,
        seed=args.seed,
    )
    if "external_l1_max" not in specs or STRICT_F3_RUNTIME not in specs:
        raise SystemExit("Required runtime methods unavailable in built strategy specs.")

    per_case: list[dict[str, Any]] = []
    paired_rows: list[dict[str, Any]] = []
    route_counter = Counter()
    fail_counter = Counter()
    total_trace_complete = 0
    for i, case in enumerate(selected, start=1):
        q = str(case.get("question", ""))
        gold_raw = str(case.get("gold_answer", ""))
        gold_can = canonical(gold_raw, args.dataset)
        if not q:
            continue

        # 1) Direct reserve incumbent.
        t0 = time.perf_counter()
        incumbent_res = specs["external_l1_max"].run(q, gold_raw)
        incumbent_latency = time.perf_counter() - t0
        incumbent_answer_raw = str(incumbent_res.prediction or "")
        incumbent_answer_can = canonical(incumbent_answer_raw, args.dataset)
        incumbent_parsed = 0 if incumbent_answer_can in {"", "None", "NA"} else 1
        incumbent_tokens = safe_float((incumbent_res.metadata or {}).get("generated_tokens_estimate", 0.0), 0.0)
        incumbent_cost = safe_float((incumbent_res.metadata or {}).get("estimated_cost", 0.0), 0.0)

        # 2) Cheap uncertainty gate (deterministic).
        q_len = len(q)
        n_count = number_count(q)
        appears_multistep = int(n_count >= 4 or q_len >= 180 or any(x in q.lower() for x in ["then", "after", "total", "remaining", "difference"]))
        incumbent_len = len(incumbent_answer_raw)
        unstable_or_unparseable = int((not incumbent_parsed) or incumbent_len > 24)
        answer_confidence_proxy = 1.0 if incumbent_parsed else 0.0
        disagreement = 0  # no extra cheap sample in smoke mode.

        if unstable_or_unparseable:
            route_decision = "frontier_search_challenger"
            route_reason = "incumbent_unparseable_or_unstable"
        elif appears_multistep and args.budget >= 4:
            route_decision = "frontier_search_challenger"
            route_reason = "multistep_question_risk"
        elif disagreement:
            route_decision = "longer_direct_continuation"
            route_reason = "direct_disagreement_detected"
        elif q_len >= 120:
            route_decision = "longer_direct_continuation"
            route_reason = "long_question_direct_continuation"
        else:
            route_decision = "stop_with_incumbent"
            route_reason = "high_confidence_direct"
        route_counter[route_decision] += 1

        challenger_answer_raw = ""
        challenger_answer_can = ""
        challenger_support = 0.0
        challenger_tokens = 0.0
        challenger_cost = 0.0
        challenger_latency = 0.0
        challenger_meta: dict[str, Any] = {}
        trace_complete = 0

        if route_decision == "frontier_search_challenger":
            t1 = time.perf_counter()
            challenger_res = specs[STRICT_F3_RUNTIME].run(q, gold_raw)
            challenger_latency = time.perf_counter() - t1
            challenger_answer_raw = str(challenger_res.prediction or "")
            challenger_answer_can = canonical(challenger_answer_raw, args.dataset)
            challenger_meta = dict(challenger_res.metadata or {})
            support_map = challenger_meta.get("answer_group_support_counts", {})
            if isinstance(support_map, dict):
                challenger_support = max([safe_float(v, 0.0) for v in support_map.values()] or [0.0])
            else:
                challenger_support = 0.0
            challenger_tokens = safe_float(challenger_meta.get("generated_tokens_estimate", 0.0), 0.0)
            challenger_cost = safe_float(challenger_meta.get("estimated_cost", 0.0), 0.0)
            trace_complete = int(bool(challenger_meta.get("final_branch_states")))
        elif route_decision == "longer_direct_continuation" and "direct_reserve_frontier_gate_v1" in specs:
            t1 = time.perf_counter()
            challenger_res = specs["direct_reserve_frontier_gate_v1"].run(q, gold_raw)
            challenger_latency = time.perf_counter() - t1
            challenger_answer_raw = str(challenger_res.prediction or "")
            challenger_answer_can = canonical(challenger_answer_raw, args.dataset)
            challenger_meta = dict(challenger_res.metadata or {})
            challenger_support = safe_float(challenger_meta.get("frontier_support", 0.0), 0.0)
            challenger_tokens = safe_float(challenger_meta.get("generated_tokens_estimate", 0.0), 0.0)
            challenger_cost = safe_float(challenger_meta.get("estimated_cost", 0.0), 0.0)
            trace_complete = int(bool(challenger_meta.get("final_branch_states")))

        # 3) Guarded commit: challenger replaces only on deterministic conditions.
        incumbent_support = 1.0
        replace_incumbent = False
        replace_reason = "preserve_incumbent"
        if route_decision != "stop_with_incumbent" and challenger_answer_can not in {"", "None", "NA"}:
            if unstable_or_unparseable:
                replace_incumbent = True
                replace_reason = "incumbent_unparseable"
            elif challenger_support >= (incumbent_support + 1.0):
                replace_incumbent = True
                replace_reason = "stronger_answer_support"
            elif appears_multistep and challenger_answer_can != incumbent_answer_can:
                replace_incumbent = True
                replace_reason = "resolved_multistep_uncertainty"

        final_raw = challenger_answer_raw if replace_incumbent else incumbent_answer_raw
        final_can = challenger_answer_can if replace_incumbent else incumbent_answer_can
        direct_path_preserved = int(not replace_incumbent)
        final_correct = int(final_can == gold_can and final_can not in {"", "None", "NA"})

        # failure bucket proxy against source absent-from-tree labels.
        src_bucket = str(case.get("path_proximity_bucket", "trace_unavailable"))
        if final_correct:
            failure_mode = "resolved"
        elif src_bucket == "immediate_miss":
            failure_mode = "immediate_miss"
        elif src_bucket == "partial_progress":
            failure_mode = "partial_progress"
        elif src_bucket == "near_miss_absent_final":
            failure_mode = "near_miss_absent_final"
        elif safe_int(case.get("gold_final_answer_in_internal_tree", 0), 0) == 1:
            failure_mode = "present_but_misselected"
        else:
            failure_mode = "trace_unavailable"
        fail_counter[failure_mode] += 1

        if trace_complete:
            total_trace_complete += 1

        rec = {
            "case_idx": i,
            "example_id": str(case.get("example_id", "")),
            "dataset": args.dataset,
            "seed": args.seed,
            "budget": args.budget,
            "method": "direct_reserve_route_refine_v1",
            "question": q,
            "gold_answer_raw": gold_raw,
            "gold_answer_canonical": gold_can,
            "route_decision": route_decision,
            "route_reason": route_reason,
            "incumbent_answer": incumbent_answer_raw,
            "incumbent_canonical": incumbent_answer_can,
            "incumbent_tokens": incumbent_tokens,
            "incumbent_latency_seconds": round(incumbent_latency, 6),
            "incumbent_cost": incumbent_cost,
            "answer_parsed": incumbent_parsed,
            "answer_confidence_proxy": answer_confidence_proxy,
            "direct_answer_length": incumbent_len,
            "self_consistency_disagreement": disagreement,
            "number_count": n_count,
            "question_length": q_len,
            "appears_multistep": appears_multistep,
            "incumbent_unstable_or_unparseable": unstable_or_unparseable,
            "challenger_answers": [challenger_answer_raw] if challenger_answer_raw else [],
            "challenger_support": challenger_support,
            "challenger_tokens": challenger_tokens,
            "challenger_latency_seconds": round(challenger_latency, 6),
            "challenger_cost": challenger_cost,
            "incumbent_replaced": int(replace_incumbent),
            "replace_reason": replace_reason,
            "direct_path_preserved": direct_path_preserved,
            "final_answer_raw": final_raw,
            "final_answer_canonical": final_can,
            "is_correct": final_correct,
            "source_path_bucket": src_bucket,
            "trace_complete": trace_complete,
            "challenger_branch_traces": challenger_meta.get("final_branch_states", []),
            "challenger_action_trace": challenger_meta.get("action_trace", []),
        }
        per_case.append(rec)

        paired_rows.extend(
            [
                {
                    "example_id": rec["example_id"],
                    "dataset": args.dataset,
                    "seed": args.seed,
                    "budget": args.budget,
                    "method": "external_l1_max",
                    "is_correct": safe_int(case.get("external_exact_match", 0), 0),
                    "final_answer_canonical": str(case.get("external_final_answer_canonical", "")),
                },
                {
                    "example_id": rec["example_id"],
                    "dataset": args.dataset,
                    "seed": args.seed,
                    "budget": args.budget,
                    "method": "strict_f3",
                    "is_correct": safe_int(case.get("internal_exact_match", 0), 0),
                    "final_answer_canonical": str(case.get("internal_final_answer_canonical", "")),
                },
                {
                    "example_id": rec["example_id"],
                    "dataset": args.dataset,
                    "seed": args.seed,
                    "budget": args.budget,
                    "method": "direct_reserve_route_refine_v1",
                    "is_correct": final_correct,
                    "final_answer_canonical": final_can,
                },
            ]
        )

    write_jsonl(out_dir / "per_case_decisions.jsonl", per_case)
    write_csv(out_dir / "paired_summary.csv", paired_rows)

    route_rows = [{"route_decision": k, "count": v, "share": v / max(1, len(per_case))} for k, v in sorted(route_counter.items())]
    write_csv(out_dir / "route_decision_summary.csv", route_rows, fieldnames=["route_decision", "count", "share"])

    by_method_metrics = defaultdict(lambda: {"n": 0, "tokens": 0.0, "cost": 0.0, "lat": 0.0})
    for r in per_case:
        by_method_metrics["direct_reserve_route_refine_v1"]["n"] += 1
        by_method_metrics["direct_reserve_route_refine_v1"]["tokens"] += safe_float(r["incumbent_tokens"]) + safe_float(r["challenger_tokens"])
        by_method_metrics["direct_reserve_route_refine_v1"]["cost"] += safe_float(r["incumbent_cost"]) + safe_float(r["challenger_cost"])
        by_method_metrics["direct_reserve_route_refine_v1"]["lat"] += safe_float(r["incumbent_latency_seconds"]) + safe_float(r["challenger_latency_seconds"])
    for r in paired_rows:
        if r["method"] in {"external_l1_max", "strict_f3"}:
            by_method_metrics[r["method"]]["n"] += 1
    token_rows = []
    for method, m in sorted(by_method_metrics.items()):
        n = max(1, m["n"])
        token_rows.append(
            {
                "method": method,
                "n_rows": m["n"],
                "mean_token_estimate": m["tokens"] / n,
                "mean_estimated_cost_usd": m["cost"] / n,
                "mean_latency_seconds": m["lat"] / n,
            }
        )
    write_csv(out_dir / "token_cost_latency_summary.csv", token_rows)

    failure_rows = [{"failure_mode": k, "count": v, "share": v / max(1, len(per_case))} for k, v in sorted(fail_counter.items())]
    write_csv(out_dir / "failure_mode_summary.csv", failure_rows, fieldnames=["failure_mode", "count", "share"])

    # Evaluation comparisons
    eval_by_method = Counter()
    denom = Counter()
    for r in paired_rows:
        denom[r["method"]] += 1
        eval_by_method[r["method"]] += int(r["is_correct"])
    acc = {m: (eval_by_method[m] / max(1, denom[m])) for m in denom}
    preserve_rate = 0.0
    if per_case:
        preserve_rate = sum(
            1
            for r in per_case
            if safe_int(next((x["is_correct"] for x in paired_rows if x["example_id"] == r["example_id"] and x["method"] == "external_l1_max"), 0), 0) == 1
            and r["is_correct"] == 1
        ) / max(1, sum(1 for x in paired_rows if x["method"] == "external_l1_max" and x["is_correct"] == 1))

    next_changes = [
        "# Candidate next changes",
        "",
        f"- Cases run: {len(per_case)}",
        f"- Route mix: {dict(route_counter)}",
        f"- Accuracy: external_l1_max={acc.get('external_l1_max', 0.0):.3f}, strict_f3={acc.get('strict_f3', 0.0):.3f}, direct_reserve_route_refine_v1={acc.get('direct_reserve_route_refine_v1', 0.0):.3f}",
        "",
        "## Top recommendations",
        "- Increase frontier-search trigger for multi-step numeric questions when incumbent answer length is short but unstable.",
        "- Add one extra low-cost direct sample for uncertainty estimation before stopping with incumbent.",
        "- Tighten challenger replacement to require both support margin and consistency with independent continuation.",
    ]
    (out_dir / "candidate_next_changes.md").write_text("\n".join(next_changes) + "\n", encoding="utf-8")

    manifest = {
        "artifact_family": "direct_reserve_route_refine_cohere_diagnostic",
        "timestamp": ts,
        "provider": args.provider,
        "model": args.model,
        "method": "direct_reserve_route_refine_v1",
        "cohere_api_key_present": True,
        "smoke_test_passed": True,
        "selected_cases": len(per_case),
        "completed_trace_cases": total_trace_complete,
        "files": [
            "paired_summary.csv",
            "per_case_decisions.jsonl",
            "route_decision_summary.csv",
            "token_cost_latency_summary.csv",
            "failure_mode_summary.csv",
            "candidate_next_changes.md",
            "manifest.json",
        ],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    # Final report doc with mandatory answers.
    immediate = fail_counter.get("immediate_miss", 0)
    immediate_total = max(1, sum(1 for r in per_case if r.get("source_path_bucket") == "immediate_miss"))
    immediate_reduced = "yes" if immediate < immediate_total else "no"
    beat_strict = "yes" if acc.get("direct_reserve_route_refine_v1", 0.0) > acc.get("strict_f3", 0.0) else "no"
    approach_external = "yes" if acc.get("direct_reserve_route_refine_v1", 0.0) >= (acc.get("external_l1_max", 0.0) - 0.10) else "no"
    run_30_next = "yes" if (len(per_case) >= 4 and acc.get("direct_reserve_route_refine_v1", 0.0) >= acc.get("strict_f3", 0.0)) else "no"

    doc_lines = [
        f"# DIRECT_RESERVE_ROUTE_REFINE_COHERE_DIAGNOSTIC_{ts}",
        "",
        "- Prototype status: diagnostic only; not paper-ready.",
        f"- Cohere readiness: passed (`COHERE_API_KEY` present, smoke test ok).",
        f"- Output directory: `outputs/direct_reserve_route_refine_cohere_diagnostic_{ts}`",
        "",
        "## Required answers",
        f"1. Preserve cases solved by external/direct reasoning: **{'yes' if preserve_rate >= 0.5 else 'partially'}** (preserve_rate={preserve_rate:.3f}).",
        f"2. Reduce immediate_miss absent-from-tree failures: **{immediate_reduced}**.",
        f"3. Beat strict_f3: **{beat_strict}** (route_refine={acc.get('direct_reserve_route_refine_v1', 0.0):.3f}, strict_f3={acc.get('strict_f3', 0.0):.3f}).",
        f"4. Beat or approach external_l1_max: **{approach_external}** (external_l1_max={acc.get('external_l1_max', 0.0):.3f}).",
        "5. Token/cost/latency tradeoff: see `token_cost_latency_summary.csv` (hybrid adds challenger cost only on routed cases).",
        f"6. Run 30-case version next: **{run_30_next}**.",
        "",
        "## Controller behavior",
        f"- Route decisions: {dict(route_counter)}",
        f"- Failure modes: {dict(fail_counter)}",
        f"- Completed trace-bearing challenger runs: {total_trace_complete}/{len(per_case)}",
    ]
    doc_path = REPO_ROOT / "docs" / f"DIRECT_RESERVE_ROUTE_REFINE_COHERE_DIAGNOSTIC_{ts}.md"
    doc_path.write_text("\n".join(doc_lines) + "\n", encoding="utf-8")

    print(str(out_dir.relative_to(REPO_ROOT)))
    print("cohere_api_key_present=present")
    print("smoke_test_passed=yes")
    print(f"selected_cases={len(per_case)}")
    print(f"completed_trace_cases={total_trace_complete}")


if __name__ == "__main__":
    main()
