"""Prepare fresh Cohere disjoint validation for `pooled4_fs_le1_notie_fta_v2_candidate`.

Zero API calls in plan mode. Writes split manifest, environment report, tmux
launch scripts (tiny smoke authorized separately; full N=300 blocked).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from experiments.api_validation_plan_repair_candidate import (
    DEFAULT_BUDGET,
    estimate_call_plan,
    load_gsm8k_train_split_offline,
    select_fresh_split,
)
from experiments.cohere_disjoint_validation_plan import (
    COHERE_LIVE_SMOKE_MAX_LIMIT,
    REPO_ROOT,
    build_split_manifest,
    check_cohere_environment,
    cohere_known_used_sources,
    load_used_examples_extended,
    render_disjoint_split_audit,
    verify_split_extended,
)
from experiments.failure_analysis_common import load_jsonl, write_json, write_text
from experiments.freeze_pooled4_fs_le1_notie_candidate import CANDIDATE_NAME
from experiments.wandb_logging import git_commit_hash

POOLED4_FRESH_SEED = 83
POOLED4_FRESH_SIZE = 300
FORBIDDEN_FRESH_SEEDS = frozenset({31, 41, 53, 61, 71, 97})

# Optional local env files (sourced only when present; never printed).
OPTIONAL_ENV_SOURCE_FILES = (
    "$HOME/.api_tokens",
    "$HOME/.cloudrift_env",
    "$HOME/.wandb_env",
    "$HOME/.profile",
)


def render_optional_env_loader_bash(*, indent: str = "") -> str:
    """Bash snippet: source known local env files if they exist (no secret output)."""
    lines: list[str] = []
    for path in OPTIONAL_ENV_SOURCE_FILES:
        lines.append(f'{indent}if [ -f "{path}" ]; then')
        lines.append(f"{indent}  # shellcheck disable=SC1090")
        lines.append(f'{indent}  source "{path}"')
        lines.append(f"{indent}fi")
    return "\n".join(lines)


def render_wandb_preflight_bash(*, indent: str = "") -> str:
    """Print WANDB_API_KEY=set|missing only; never the value."""
    return "\n".join(
        [
            f'{indent}if [ -n "${{WANDB_API_KEY:-}}" ]; then',
            f'{indent}  echo "WANDB_API_KEY=set"',
            f"{indent}else",
            f'{indent}  echo "WANDB_API_KEY=missing"',
            f"{indent}fi",
        ]
    )


def render_cohere_preflight_bash(*, indent: str = "") -> str:
    """Print COHERE_API_KEY=set|missing only (presence check, no values)."""
    return "\n".join(
        [
            f'{indent}if [ -n "${{COHERE_API_KEY:-}}${{CO_API_KEY:-}}" ]; then',
            f'{indent}  echo "COHERE_API_KEY=set"',
            f"{indent}else",
            f'{indent}  echo "COHERE_API_KEY=missing"',
            f"{indent}fi",
        ]
    )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output-dir", default="")
    p.add_argument("--fresh-seed", type=int, default=POOLED4_FRESH_SEED)
    p.add_argument("--size", type=int, default=POOLED4_FRESH_SIZE)
    p.add_argument("--budget", type=int, default=DEFAULT_BUDGET)
    return p.parse_args()


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def build_pooled4_split_manifest(*, split: dict[str, Any], verification: dict[str, Any], budget: int) -> dict[str, Any]:
    base = build_split_manifest(split=split, verification=verification, budget=budget)
    base["candidate_rule"] = CANDIDATE_NAME
    base["validation_suite"] = "pooled4_fs_le1_notie"
    base["forbidden_prior_seeds"] = sorted(FORBIDDEN_FRESH_SEEDS)
    return base


def render_pooled4_split_audit(*, used: dict[str, Any], split: dict[str, Any], verification: dict[str, Any]) -> str:
    text = render_disjoint_split_audit(used=used, split=split, verification=verification)
    return text.replace("# Cohere Disjoint Split Audit", "# Cohere Pooled-4 FS≤1 No-Tie Split Audit", 1)


def render_environment_report_pooled4(env: dict[str, Any]) -> str:
    cohere = env["cohere"]
    wandb = env["wandb"]
    shell = env.get("shell_startup", {})
    api_tokens = next(
        (f for f in shell.get("startup_files_checked", []) if str(f.get("path", "")).endswith(".api_tokens")),
        {},
    )
    lines = [
        "# Cohere Pooled-4 FS≤1 Environment Report",
        "",
        "Presence-only checks; **no secret values** printed.",
        "",
        "## Cohere API",
        f"- COHERE_API_KEY_present: {cohere['COHERE_API_KEY_present']}",
        f"- CO_API_KEY_present: {cohere['CO_API_KEY_present']}",
        f"- api_key_configured: {cohere['api_key_configured']}",
        f"- cohere_sdk_importable: {cohere['cohere_sdk_importable']}",
        f"- delegate_script_help_runs: {cohere['delegate_script_help_runs']}",
        f"- configured: {cohere['configured']}",
        "",
        "## W&B",
        f"- package_installed: {wandb['package_actually_installed']}",
        f"- WANDB_API_KEY_present: {wandb['api_key_env_present']}",
        f"- configured: {wandb['configured']}",
        "",
        "## Shell startup",
        f"- ~/.api_tokens exists: {api_tokens.get('exists', False)}",
        f"- ~/.api_tokens readable: {api_tokens.get('readable', False)}",
        f"- mentions COHERE_API_KEY/CO_API_KEY: {api_tokens.get('mentions_cohere_api_key', False)}",
        "",
        "## tmux",
        f"- available: {env['tmux']['available']}",
        f"- version: {env['tmux'].get('version')}",
    ]
    return "\n".join(lines).rstrip() + "\n"


def write_sanitized_environment(path: Path, env: dict[str, Any], *, tmux_session: str | None = None) -> None:
    cohere = env["cohere"]
    wandb = env["wandb"]
    lines = [
        f"timestamp_utc: {datetime.now(timezone.utc).isoformat()}",
        f"COHERE_API_KEY_present: {cohere['COHERE_API_KEY_present']}",
        f"CO_API_KEY_present: {cohere['CO_API_KEY_present']}",
        f"cohere_sdk_importable: {cohere['cohere_sdk_importable']}",
        f"WANDB_API_KEY_present: {wandb['api_key_env_present']}",
        f"WANDB_PROJECT_present: {wandb.get('project_env_present', False)}",
        f"tmux_session: {tmux_session or 'n/a'}",
        "optional_env_sources: .api_tokens,.cloudrift_env,.wandb_env,.profile",
    ]
    write_text(path, "\n".join(lines) + "\n")


def render_launch_scripts(
    *,
    plan_dir: Path,
    plan_timestamp: str,
    split_manifest: Path,
    split: dict[str, Any],
    budget: int,
    env: dict[str, Any],
) -> dict[str, str]:
    session_smoke = f"cohere_pooled4_smoke_{plan_timestamp}"
    session_full = f"cohere_pooled4_full_{plan_timestamp}"
    python_bin = "./.venv/bin/python"
    fresh_seed = split["fresh_seed"]
    smoke_base = REPO_ROOT / "outputs" / "api_validation_smoke" / f"cohere_pooled4_fs_le1_notie_{plan_timestamp}"
    wandb_run_name = f"cohere_pooled4_smoke_{plan_timestamp}"
    env_loader = render_optional_env_loader_bash(indent="")
    wandb_preflight = render_wandb_preflight_bash(indent="")
    cohere_preflight = render_cohere_preflight_bash(indent="")

    inner_script_body = f"""#!/usr/bin/env bash
# Inner tmux worker for pooled4_fs_le1 Cohere smoke (generated by validation plan).
set -euo pipefail
cd "{REPO_ROOT}"

{env_loader}

{cohere_preflight}
{wandb_preflight}

export WANDB_DIR="{smoke_base}/wandb"
mkdir -p "$WANDB_DIR"

{python_bin} -m experiments.run_api_validation_repair_candidate \\
  --split-manifest "{split_manifest}" \\
  --output-dir "{smoke_base}" \\
  --live --provider cohere --seed {fresh_seed} --budget {budget} \\
  --limit {COHERE_LIVE_SMOKE_MAX_LIMIT} \\
  --wandb --wandb-project frontier-allocation --wandb-run-name "{wandb_run_name}" \\
  2>&1 | tee "{smoke_base}/smoke.log"

{python_bin} -m experiments.cohere_pooled4_fs_le1_validation_plan \\
  --postprocess-smoke "{smoke_base}" \\
  --plan-dir "{plan_dir}" \\
  --tmux-session-name "{session_smoke}"
"""

    tiny_smoke = f"""#!/usr/bin/env bash
# TINY COHERE LIVE SMOKE — pooled4_fs_le1_notie_fta_v2_candidate plumbing test (≤{COHERE_LIVE_SMOKE_MAX_LIMIT} examples).
set -euo pipefail
cd "{REPO_ROOT}"

if ! command -v tmux >/dev/null 2>&1; then
  echo "tmux required. Stopping." >&2
  exit 1
fi

{env_loader}

echo "=== environment preflight (presence only; no secret values) ==="
{cohere_preflight}
{wandb_preflight}

SESSION="{session_smoke}"
RUN_DIR="{smoke_base}"
mkdir -p "$RUN_DIR/wandb"

{python_bin} -m experiments.cohere_pooled4_fs_le1_validation_plan \\
  --write-smoke-env-report "$RUN_DIR/environment_sanitized.txt" \\
  --tmux-session-name "$SESSION"

INNER_SCRIPT="$RUN_DIR/run_inner.sh"
cat > "$INNER_SCRIPT" <<'INNER_EOF'
{inner_script_body}INNER_EOF
chmod +x "$INNER_SCRIPT"

tmux new-session -d -s "$SESSION" "bash '$RUN_DIR/run_inner.sh'"

echo "tmux session name: $SESSION"
echo "attach command: tmux attach -t $SESSION"
echo "log-watch command: tail -f '$RUN_DIR/smoke.log'"
echo "output directory: $RUN_DIR"
"""

    full_blocked = f"""#!/usr/bin/env bash
# FULL N=300 COHERE POOLED-4 FS≤1 VALIDATION — INTENTIONALLY DISABLED.
set -euo pipefail
cd "{REPO_ROOT}"

echo "Full N=300 Cohere validation for {CANDIDATE_NAME} is intentionally disabled." >&2
echo "Complete tiny smoke first: launch_tiny_cohere_pooled4_fs_le1_smoke_tmux.sh" >&2
echo "Full-scale live validation requires separate explicit human authorization." >&2
exit 1

# Blocked body (do not enable without review):
{env_loader}
{wandb_preflight}
SESSION="{session_full}"
RUN_DIR="{plan_dir}/live_run_$(date -u +%Y%m%dT%H%M%SZ)"
export WANDB_DIR="$RUN_DIR/wandb"
mkdir -p "$RUN_DIR/wandb"
{python_bin} -m experiments.run_api_validation_repair_candidate \\
  --split-manifest "{split_manifest}" \\
  --output-dir "$RUN_DIR" \\
  --live --provider cohere --allow-full-live --seed {fresh_seed} --budget {budget} --resume \\
  --wandb --wandb-project frontier-allocation --wandb-run-name "cohere_pooled4_full_{plan_timestamp}"
"""

    return {
        "launch_tiny_cohere_pooled4_fs_le1_smoke_tmux.sh": tiny_smoke,
        "launch_full_cohere_pooled4_fs_le1_validation_tmux.sh": full_blocked,
    }


def postprocess_smoke_run(
    run_dir: Path,
    *,
    plan_dir: Path,
    tmux_session_name: str | None = None,
) -> dict[str, Any]:
    """Evaluate smoke output and write summaries (no API calls)."""
    run_dir = run_dir.resolve()
    plan_dir = plan_dir.resolve()
    manifest_path = plan_dir / "COHERE_POOLED4_FS_LE1_NOTIE_SPLIT_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    records_path = run_dir / "per_example_records.jsonl"
    records = load_jsonl(records_path) if records_path.exists() else []

    env = check_cohere_environment()
    env_path = run_dir / "environment_sanitized.txt"
    if not env_path.exists():
        write_sanitized_environment(env_path, env, tmux_session=tmux_session_name)

    eval_dir = run_dir / "evaluation"
    eval_dir.mkdir(parents=True, exist_ok=True)
    eval_proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "experiments.evaluate_api_validation_repair_candidate",
            "--input",
            str(records_path),
            "--output-dir",
            str(eval_dir),
            "--source-id",
            f"cohere_pooled4_fs_le1_smoke_{run_dir.name}",
            "--validation-suite",
            "pooled4_fs_le1",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )

    api_failures = sum(1 for r in records if r.get("status") == "failed" or r.get("provider_call_failed"))
    parse_failures = sum(
        1
        for r in records
        if r.get("final_answer_canonical") in (None, "") and r.get("status") != "failed"
    )
    logical_calls = sum(int(r.get("cohere_logical_api_calls", 0) or 0) for r in records)
    tokens_in = sum(int(r.get("token_count_prompt", 0) or 0) for r in records)
    tokens_out = sum(int(r.get("token_count_completion", 0) or 0) for r in records)
    latency = sum(float(r.get("latency_seconds", 0) or 0) for r in records)
    example_ids = sorted({str(r.get("example_id")) for r in records})
    methods = sorted({str(r.get("method")) for r in records})
    run_meta_path = run_dir / "run_metadata.json"
    run_meta = json.loads(run_meta_path.read_text(encoding="utf-8")) if run_meta_path.exists() else {}
    delegate = run_meta.get("live_delegate_run") or {}
    delegate_usage = delegate.get("usage") or {}

    usage = {
        "examples_run": len(example_ids),
        "example_ids": example_ids,
        "method_example_calls_attempted": len(records),
        "method_example_calls_completed": sum(1 for r in records if r.get("status") != "failed"),
        "api_failures": api_failures,
        "parse_failures": parse_failures,
        "logical_api_calls": delegate_usage.get("total_logical_api_calls") or logical_calls,
        "token_count_prompt": delegate_usage.get("total_input_tokens") or tokens_in,
        "token_count_completion": delegate_usage.get("total_output_tokens") or tokens_out,
        "total_tokens": delegate_usage.get("total_tokens") or (tokens_in + tokens_out),
        "latency_seconds_summed": delegate_usage.get("total_latency_seconds") or latency,
        "provider": run_meta.get("provider", "cohere"),
        "model": delegate.get("model") or delegate.get("cohere_model"),
        "budget": manifest.get("budget", DEFAULT_BUDGET),
        "evaluator_returncode": eval_proc.returncode,
        "evaluator_ok": eval_proc.returncode == 0,
        "plumbing_only": True,
        "n_too_small_for_science": len(example_ids) <= 2,
    }
    write_json(run_dir / "LIVE_COHERE_POOLED4_SMOKE_USAGE_SUMMARY.json", usage)

    eval_summary: dict[str, Any] = {"evaluator_ok": eval_proc.returncode == 0, "candidates": []}
    results_csv = eval_dir / "validation_results.csv"
    if results_csv.exists():
        import csv

        with results_csv.open(encoding="utf-8") as f:
            eval_summary["candidates"] = list(csv.DictReader(f))
    frozen = next((c for c in eval_summary["candidates"] if c.get("candidate") == CANDIDATE_NAME), None)
    if frozen:
        eval_summary["frozen_candidate"] = frozen
    write_json(run_dir / "LIVE_COHERE_POOLED4_SMOKE_EVALUATION_SUMMARY.json", eval_summary)

    smoke_manifest = {
        "authorization": "explicit tiny-smoke-only Cohere authorization (<=2 examples, no full validation)",
        "candidate_rule": CANDIDATE_NAME,
        "budget": manifest.get("budget"),
        "dataset": manifest.get("dataset"),
        "delegated_to": "scripts/run_cohere_real_model_cost_normalized_validation.py",
        "example_ids": example_ids,
        "fresh_split_seed": manifest.get("fresh_seed"),
        "full_n300_validation_run": False,
        "limit_examples": COHERE_LIVE_SMOKE_MAX_LIMIT,
        "live_run_failed": delegate.get("returncode", 0) != 0 if delegate else api_failures > 0,
        "methods": methods,
        "model": usage.get("model"),
        "output_dir": str(run_dir.relative_to(REPO_ROOT)),
        "provider": "cohere",
        "records_written": len(records),
        "split_manifest": str(manifest_path.relative_to(REPO_ROOT)),
        "timestamp_utc_completed": datetime.now(timezone.utc).isoformat(),
        "tmux_session_name": tmux_session_name,
        "usage": usage,
    }
    write_json(run_dir / "LIVE_COHERE_POOLED4_SMOKE_RUN_MANIFEST.json", smoke_manifest)

    full_cmd = f"./{plan_dir.relative_to(REPO_ROOT)}/launch_full_cohere_pooled4_fs_le1_validation_tmux.sh"
    readiness = f"""# Smoke Readiness for Full Run

- **Smoke plumbing:** {'PASS' if usage['evaluator_ok'] and records else 'FAIL'}
- **Scientific evidence:** none (n≤2)
- **Schema compatible with full validation:** {bool(records)}
- **Full validation:** BLOCKED — run `{full_cmd}` exits 1 by design.

## Next step (requires separate authorization)

1. Human review of smoke logs and evaluator output.
2. Explicit authorization for N=300 Cohere run at seed {manifest.get('fresh_seed')}.
3. Remove guard from full launch script after review.
"""
    write_text(run_dir / "LIVE_COHERE_POOLED4_SMOKE_READINESS_FOR_FULL_RUN.md", readiness)

    final = f"""# Final Tiny Cohere Pooled-4 FS≤1 Smoke Summary

Tiny live Cohere smoke for `{CANDIDATE_NAME}` (≤2 examples). **Plumbing only — not scientific evidence.**

## Headline

| Metric | Value |
| --- | --- |
| Examples run | **{usage['examples_run']}** |
| Method-example calls | **{usage['method_example_calls_completed']}** / {usage['method_example_calls_attempted']} |
| API failures | **{api_failures}** |
| Parse failures | **{parse_failures}** |
| Logical API calls | **{logical_calls}** |
| Total tokens | **{usage['total_tokens']}** |
| Evaluator | **{'OK' if eval_proc.returncode == 0 else 'FAILED'}** |

## Frozen candidate (n≤2 — do not cite)

{frozen if frozen else 'Evaluator did not produce frozen candidate row.'}

## Full validation (BLOCKED)

```bash
{full_cmd}
```

Exits **1** by design. Full N=300 not run.

## Confirmations

- No selector promotion; FTA unchanged.
- No manuscript changes; no commits/pushes.
- No outputs overwritten (new directory only).
"""
    write_text(run_dir / "FINAL_TINY_COHERE_POOLED4_FS_LE1_SMOKE_SUMMARY.md", final)

    return {
        "run_dir": str(run_dir),
        "usage": usage,
        "evaluator_ok": eval_proc.returncode == 0,
        "records": len(records),
    }


def run_plan(args: argparse.Namespace) -> dict[str, Any]:
    if args.fresh_seed in FORBIDDEN_FRESH_SEEDS:
        raise ValueError(f"fresh_seed {args.fresh_seed} forbidden: {sorted(FORBIDDEN_FRESH_SEEDS)}")

    timestamp = _timestamp()
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = REPO_ROOT / "outputs" / "api_validation_plans" / f"cohere_pooled4_fs_le1_notie_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)
    plan_timestamp = output_dir.name.split("_")[-1]

    sources = cohere_known_used_sources()
    used = load_used_examples_extended(sources)
    gsm8k_rows = load_gsm8k_train_split_offline()
    split = select_fresh_split(fresh_seed=args.fresh_seed, size=args.size, used=used, gsm8k_rows=gsm8k_rows)
    verification = verify_split_extended(split=split, used=used, gsm8k_rows=gsm8k_rows)
    split["verification"] = verification
    if not verification["non_overlapping"]:
        raise RuntimeError(f"split failed overlap verification: {verification}")

    env = check_cohere_environment()
    manifest = build_pooled4_split_manifest(split=split, verification=verification, budget=args.budget)
    manifest["git_commit"] = git_commit_hash(REPO_ROOT)
    manifest["used_sources_summary"] = used["per_source"]
    manifest["used_examples_total"] = used["total_unique_used"]
    manifest["environment_check"] = env
    manifest["call_plan"] = estimate_call_plan(split["size"], budget=args.budget)

    split_manifest_path = output_dir / "COHERE_POOLED4_FS_LE1_NOTIE_SPLIT_MANIFEST.json"
    write_json(split_manifest_path, manifest)
    write_text(output_dir / "COHERE_POOLED4_FS_LE1_NOTIE_SPLIT_AUDIT.md", render_pooled4_split_audit(used=used, split=split, verification=verification))
    write_text(output_dir / "COHERE_POOLED4_ENVIRONMENT_REPORT.md", render_environment_report_pooled4(env))

    scripts = render_launch_scripts(
        plan_dir=output_dir,
        plan_timestamp=plan_timestamp,
        split_manifest=split_manifest_path,
        split=split,
        budget=args.budget,
        env=env,
    )
    for name, body in scripts.items():
        path = output_dir / name
        write_text(path, body)
        path.chmod(0o755)

    return {
        "output_dir": str(output_dir),
        "fresh_seed": split["fresh_seed"],
        "non_overlapping": verification["non_overlapping"],
        "cohere_configured": env["cohere"]["configured"],
        "launch_tiny": str(output_dir / "launch_tiny_cohere_pooled4_fs_le1_smoke_tmux.sh"),
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output-dir", default="")
    p.add_argument("--fresh-seed", type=int, default=POOLED4_FRESH_SEED)
    p.add_argument("--size", type=int, default=POOLED4_FRESH_SIZE)
    p.add_argument("--budget", type=int, default=DEFAULT_BUDGET)
    p.add_argument("--postprocess-smoke", default="", help=argparse.SUPPRESS)
    p.add_argument("--plan-dir", default="", help=argparse.SUPPRESS)
    p.add_argument("--write-smoke-env-report", default="", help=argparse.SUPPRESS)
    p.add_argument("--tmux-session-name", default="", help=argparse.SUPPRESS)
    args = p.parse_args()

    if args.write_smoke_env_report:
        env = check_cohere_environment()
        write_sanitized_environment(Path(args.write_smoke_env_report), env, tmux_session=args.tmux_session_name or None)
        return 0

    if args.postprocess_smoke:
        result = postprocess_smoke_run(
            Path(args.postprocess_smoke),
            plan_dir=Path(args.plan_dir),
            tmux_session_name=args.tmux_session_name or None,
        )
        print(json.dumps(result, sort_keys=True))
        return 0

    result = run_plan(args)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
