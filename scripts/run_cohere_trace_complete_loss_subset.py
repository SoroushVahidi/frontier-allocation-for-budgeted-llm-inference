#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

SOURCE_LOSS_PATH = (
    REPO_ROOT
    / "outputs"
    / "cohere_absent_from_tree_loss_diagnostics_20260427T171917Z"
    / "loss_cases_absent_from_tree.jsonl"
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Focused trace-complete Cohere rerun for absent-from-tree loss subset.")
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    p.add_argument("--model", default="command-r-plus-08-2024")
    p.add_argument("--max-cases", type=int, default=30)
    p.add_argument("--selection-seed", type=int, default=27)
    p.add_argument("--source-loss-jsonl", default=str(SOURCE_LOSS_PATH))
    p.add_argument("--timeout-seconds", type=int, default=90)
    p.add_argument("--smoke-timeout-seconds", type=int, default=45)
    p.add_argument("--rerun-timeout-seconds", type=int, default=3600)
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


def choose_cases(rows: list[dict[str, Any]], max_cases: int) -> list[dict[str, Any]]:
    # Prefer strict_f3 vs external_l1_max.
    rows = [r for r in rows if str(r.get("internal_method_name")) == "strict_f3" and str(r.get("external_baseline_name")) == "external_l1_max"]
    if not rows:
        return []
    # Confirmed first, then unverified.
    rows.sort(
        key=lambda r: (
            0 if str(r.get("absent_from_tree_status")) == "confirmed_absent_from_tree" else 1,
            {"immediate_miss": 0, "partial_progress": 1, "near_miss_absent_final": 2}.get(str(r.get("path_proximity_bucket")), 9),
            int(r.get("budget", 999)),
            int(r.get("seed", 999)),
        )
    )
    by_bucket: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_bucket[str(r.get("path_proximity_bucket", "trace_unavailable"))].append(r)

    desired_buckets = ["immediate_miss", "partial_progress", "near_miss_absent_final"]
    selected: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, int, int]] = set()

    # Balanced seed for each desired bucket and budgets 4/6/8 where available.
    for bucket in desired_buckets:
        candidates = by_bucket.get(bucket, [])
        for b in (4, 6, 8):
            for r in candidates:
                key = (str(r.get("example_id")), int(r.get("seed", -1)), int(r.get("budget", -1)))
                if int(r.get("budget", -1)) != b or key in seen_keys:
                    continue
                selected.append(r)
                seen_keys.add(key)
                break

    # Fill remainder with best-ranked unique rows.
    for r in rows:
        if len(selected) >= max_cases:
            break
        key = (str(r.get("example_id")), int(r.get("seed", -1)), int(r.get("budget", -1)))
        if key in seen_keys:
            continue
        selected.append(r)
        seen_keys.add(key)
    return selected[:max_cases]


def load_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def main() -> None:
    args = parse_args()
    if args.max_cases > 30:
        raise SystemExit("Refusing run: --max-cases must be <= 30.")

    ts = args.timestamp
    out_dir = REPO_ROOT / "outputs" / f"cohere_trace_complete_loss_subset_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)
    rerun_command = (
        f'python scripts/run_cohere_trace_complete_loss_subset.py --timestamp {ts} --model "{args.model}" --max-cases {args.max_cases}'
    )

    # 1) Explicit readiness check
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
        doc_path = REPO_ROOT / "docs" / f"COHERE_TRACE_COMPLETE_LOSS_SUBSET_{ts}.md"
        doc_path.write_text(
            "\n".join(
                [
                    f"# COHERE_TRACE_COMPLETE_LOSS_SUBSET_{ts}",
                    "",
                    "- Cohere API readiness: **failed**",
                    f"- Failure class: **{failure_class}**",
                    f"- Recommended fix: {fix_for_failure(failure_class)}",
                    f"- See `outputs/cohere_trace_complete_loss_subset_{ts}/cohere_api_key_issue.md`",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        print(str(out_dir.relative_to(REPO_ROOT)))
        print("cohere_api_key_present=absent" if not os.getenv("COHERE_API_KEY") else "cohere_api_key_present=present")
        print("smoke_test_passed=no")
        print(f"failure_class={failure_class}")
        return

    # 2) Select up to 30 loss cases
    source_rows = read_jsonl(Path(args.source_loss_jsonl))
    if not source_rows:
        raise SystemExit(f"Source loss JSONL not found or empty: {args.source_loss_jsonl}")
    selected = choose_cases(source_rows, args.max_cases)
    if not selected:
        raise SystemExit("No eligible strict_f3 vs external_l1_max rows found in source loss dataset.")

    selected_cases = []
    planned_rows = []
    for i, r in enumerate(selected, start=1):
        selected_cases.append(
            {
                "case_idx": i,
                "example_id": r["example_id"],
                "dataset": r["dataset"],
                "seed": int(r["seed"]),
                "budget": int(r["budget"]),
                "stratum": r.get("absent_from_tree_status", "unknown"),
                "path_proximity_bucket": r.get("path_proximity_bucket", "trace_unavailable"),
                "question": r.get("question", ""),
                "gold_answer_raw": r.get("gold_answer", ""),
                "gold_answer": r.get("gold_answer_canonical", ""),
            }
        )
        planned_rows.append(
            {
                "example_id": r["example_id"],
                "dataset": r["dataset"],
                "question": r.get("question", ""),
                "gold_answer_raw": r.get("gold_answer", ""),
                "gold_answer": r.get("gold_answer_canonical", ""),
                "stratum": r.get("path_proximity_bucket", "unknown"),
            }
        )
    write_jsonl(out_dir / "selected_cases.jsonl", selected_cases)
    write_csv(out_dir / "selected_cases.csv", planned_rows)

    # 3) Live rerun through existing trace-capable runner.
    inner_ts = f"TRACE_SUBSET_{ts}"
    reuse_file = out_dir / "selected_cases.csv"
    methods = ",".join(
        [
            "strict_f3",
            "external_l1_max",
            "strict_f3_anti_collapse_weak_v1",
            "direct_reserve_strong_plus_diverse_margin_gated_v1",
            "direct_reserve_strong_v1",
            "direct_reserve_strong_plus_diverse_v1",
        ]
    )
    budgets = sorted({int(r["budget"]) for r in selected_cases})
    seeds = sorted({int(r["seed"]) for r in selected_cases})
    cmd = [
        sys.executable,
        "scripts/run_cohere_direct_reserve_validation.py",
        "--timestamp",
        inner_ts,
        "--provider",
        "cohere",
        "--model",
        args.model,
        "--dataset",
        "openai/gsm8k",
        "--methods",
        methods,
        "--budgets",
        ",".join(str(b) for b in budgets),
        "--seeds",
        ",".join(str(s) for s in seeds),
        "--max-cases",
        str(min(args.max_cases, len(selected_cases))),
        "--scorer-dataset-extended",
        "--emit-full-traces",
        "--run-real-api",
        "--reuse-planned-cases",
        str(reuse_file),
        "--timeout-seconds",
        str(args.timeout_seconds),
    ]
    try:
        proc = subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=args.rerun_timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        fc = "network_or_timeout"
        write_issue_report(
            out_dir=out_dir,
            timestamp=ts,
            model=args.model,
            key_present=bool(os.getenv("COHERE_API_KEY")),
            failure_class=fc,
            error_message=f"focused rerun timed out after {args.rerun_timeout_seconds}s",
            rerun_command=rerun_command,
        )
        raise SystemExit(
            f"Trace subset rerun timed out. See outputs/cohere_trace_complete_loss_subset_{ts}/cohere_api_key_issue.md"
        )
    if proc.returncode != 0:
        fc = classify_failure((proc.stderr or "") + "\n" + (proc.stdout or ""))
        write_issue_report(
            out_dir=out_dir,
            timestamp=ts,
            model=args.model,
            key_present=bool(os.getenv("COHERE_API_KEY")),
            failure_class=fc,
            error_message=(proc.stderr or proc.stdout or "unknown rerun failure")[:3000],
            rerun_command=rerun_command,
        )
        raise SystemExit(
            f"Trace subset rerun failed. See outputs/cohere_trace_complete_loss_subset_{ts}/cohere_api_key_issue.md"
        )

    # 4) Convert artifacts to required files.
    src_dir = REPO_ROOT / "outputs" / f"cohere_direct_reserve_validation_{inner_ts}"
    per_case = load_csv(src_dir / "per_case_method_results.csv")
    branch_table = load_csv(src_dir / "candidate_branch_table.csv")
    action_trace_rows = read_jsonl(src_dir / "action_trace.jsonl")

    per_example_trace_records = per_case
    branch_traces = branch_table
    step_traces: list[dict[str, Any]] = []
    for row in action_trace_rows:
        for i, step in enumerate(row.get("action_trace", []) if isinstance(row, dict) else []):
            step_traces.append(
                {
                    "example_id": row.get("example_id"),
                    "seed": row.get("seed"),
                    "budget": row.get("budget"),
                    "method": row.get("method"),
                    "step_index": i,
                    "step": step,
                }
            )

    write_jsonl(out_dir / "per_example_trace_records.jsonl", per_example_trace_records)
    write_jsonl(out_dir / "branch_traces.jsonl", branch_traces)
    write_jsonl(out_dir / "step_traces.jsonl", step_traces)

    # 5) Summary/audit files.
    by_case: dict[tuple[str, int, int], list[dict[str, Any]]] = defaultdict(list)
    for r in per_case:
        by_case[(str(r.get("example_id")), int(float(r.get("seed", 0))), int(float(r.get("budget", 0))))].append(r)

    path_rows = []
    abandon_rows = []
    commit_rows = []
    cost_rows = []
    bucket_counts = Counter()
    present_but_misselected = 0
    full_trace_completed = 0

    selected_lookup = {(s["example_id"], int(s["seed"]), int(s["budget"])): s for s in selected_cases}
    for key, rows in by_case.items():
        sel = selected_lookup.get(key)
        if not sel:
            continue
        methods_present = {str(r.get("method")) for r in rows}
        needed = {"strict_f3", "external_l1_max"}
        if needed.issubset(methods_present):
            full_trace_completed += 1
        bucket = str(sel.get("path_proximity_bucket", "trace_unavailable"))
        bucket_counts[bucket] += 1

        strict = next((r for r in rows if str(r.get("method")) == "strict_f3"), None)
        if strict and int(float(strict.get("present_not_selected", 0))) == 1:
            present_but_misselected += 1
        path_rows.append(
            {
                "example_id": key[0],
                "seed": key[1],
                "budget": key[2],
                "path_bucket": bucket,
                "source_stratum": sel.get("stratum", "unknown"),
                "correct_region_entered_proxy": 1 if bucket in {"partial_progress", "near_miss_absent_final"} else 0,
            }
        )
        abandon_rows.append(
            {
                "example_id": key[0],
                "seed": key[1],
                "budget": key[2],
                "abandoned_before_maturity_proxy": 1 if bucket == "near_miss_absent_final" else 0,
                "supporting_note": "proxy from source path bucket",
            }
        )
        commit_rows.append(
            {
                "example_id": key[0],
                "seed": key[1],
                "budget": key[2],
                "early_commit_proxy": 1 if bucket == "partial_progress" else 0,
                "supporting_note": "proxy from source path bucket",
            }
        )
    for r in per_case:
        cost_rows.append(
            {
                "method": r.get("method", ""),
                "mean_token_estimate": safe_float(r.get("token_estimate", 0), 0.0),
                "mean_cost_estimate": safe_float(r.get("cost_estimate", 0), 0.0),
                "mean_latency_seconds": safe_float(r.get("latency_seconds", 0), 0.0),
            }
        )

    write_csv(out_dir / "path_proximity_metrics.csv", path_rows)
    write_csv(out_dir / "branch_abandonment_audit.csv", abandon_rows)
    write_csv(out_dir / "commit_timing_audit.csv", commit_rows)
    write_csv(out_dir / "token_cost_latency_summary.csv", cost_rows)

    controller_fixes = [
        "Direct-path fallback for immediate_miss-heavy cases.",
        "Delayed commit in partial_progress cases to allow maturation of promising branches.",
        "Continuation-score and anti-collapse tuning to preserve near-miss branches.",
    ]
    (out_dir / "candidate_controller_fixes.md").write_text(
        "\n".join(
            [
                "# Candidate controller fixes",
                "",
                f"- Selected cases: {len(selected_cases)}",
                f"- Completed trace cases (strict_f3 + external_l1_max present): {full_trace_completed}",
                f"- immediate_miss: {bucket_counts.get('immediate_miss', 0)}",
                f"- partial_progress: {bucket_counts.get('partial_progress', 0)}",
                f"- near_miss_absent_final: {bucket_counts.get('near_miss_absent_final', 0)}",
                f"- present_but_misselected: {present_but_misselected}",
                "",
                "## Top 3 recommended fixes",
                *[f"- {x}" for x in controller_fixes],
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    manifest = {
        "artifact_family": "cohere_trace_complete_loss_subset",
        "timestamp": ts,
        "model": args.model,
        "cohere_api_key_present": True,
        "smoke_test_passed": True,
        "inner_run_id": f"cohere_direct_reserve_validation_{inner_ts}",
        "selected_cases": len(selected_cases),
        "rerun_cases": len(selected_cases),
        "completed_trace_cases": full_trace_completed,
        "method_mapping_notes": {
            "direct_reserve_frontier_gate_v1": "executed as direct_reserve_strong_plus_diverse_margin_gated_v1",
        },
        "files": [
            "selected_cases.jsonl",
            "per_example_trace_records.jsonl",
            "branch_traces.jsonl",
            "step_traces.jsonl",
            "path_proximity_metrics.csv",
            "branch_abandonment_audit.csv",
            "commit_timing_audit.csv",
            "token_cost_latency_summary.csv",
            "candidate_controller_fixes.md",
            "manifest.json",
        ],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    # 6) required doc
    immediate = bucket_counts.get("immediate_miss", 0)
    partial = bucket_counts.get("partial_progress", 0)
    near = bucket_counts.get("near_miss_absent_final", 0)
    region_never = immediate
    region_entered = partial + near
    strongest_fix = (
        "direct-path fallback"
        if immediate >= max(partial, near)
        else ("delayed commit" if partial >= near else "continuation-score tuning")
    )
    evidence_strong = "yes" if full_trace_completed >= 12 else "no"
    doc_lines = [
        f"# COHERE_TRACE_COMPLETE_LOSS_SUBSET_{ts}",
        "",
        "- Cohere API readiness: **passed**",
        "- Failure class: **none**",
        f"- Selected cases rerun: **{len(selected_cases)}**",
        f"- Completed with full traces: **{full_trace_completed}**",
        f"- immediate_miss: **{immediate}**",
        f"- partial_progress: **{partial}**",
        f"- near_miss_absent_final: **{near}**",
        f"- present_but_misselected: **{present_but_misselected}**",
        f"- Controller region behavior: never-enters={region_never}, enters-then-loses={region_entered}",
        f"- Most justified fix: **{strongest_fix}**",
        f"- Evidence strong enough for new controller variant design: **{evidence_strong}**",
        "",
        f"- Output directory: `outputs/cohere_trace_complete_loss_subset_{ts}`",
    ]
    doc_path = REPO_ROOT / "docs" / f"COHERE_TRACE_COMPLETE_LOSS_SUBSET_{ts}.md"
    doc_path.write_text("\n".join(doc_lines) + "\n", encoding="utf-8")

    print(str(out_dir.relative_to(REPO_ROOT)))
    print("cohere_api_key_present=present")
    print("smoke_test_passed=yes")
    print(f"selected_cases={len(selected_cases)}")
    print(f"rerun_cases={len(selected_cases)}")
    print(f"completed_trace_cases={full_trace_completed}")


if __name__ == "__main__":
    main()
