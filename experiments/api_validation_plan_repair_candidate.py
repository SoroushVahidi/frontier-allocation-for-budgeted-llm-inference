"""Fresh API-validation planning for the `repair_primary_plus_unanimity_fallback`
exploratory repair candidate.

This script does not call any paid provider. It:
  - identifies a fresh, verifiably non-overlapping GSM8K train-split sample
    (checked against every known-used seed-41/61/71/31 example, both by
    example_id and by exact question-text hash), using the locally cached
    copy of `openai/gsm8k` with `HF_DATASETS_OFFLINE=1`/`HF_HUB_OFFLINE=1`
    forced so no network request is made;
  - estimates the logical-call budget for a validation run;
  - checks (without printing secrets) whether tmux, W&B, VAPI, and provider
    API keys look configured;
  - writes RUN_MANIFEST.json, VALIDATION_PLAN.md, and API_VALIDATION_COST_AND_RISK.md;
  - invokes the dry-run runner skeleton (zero API calls, synthetic
    placeholder answers only) as a smoke test of the whole pipeline, and
    writes DRY_RUN_READINESS_REPORT.md from the real result.

Guardrails: no paid API call is made anywhere in this script. The candidate
rule (`repair_primary_plus_unanimity_fallback`) is not promoted by running
this script; it remains exploratory. FTA/FIX-2+FIX-4 selector logic is not
touched.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from experiments.build_failure_feature_table import CANONICAL_DEFAULT_INPUTS, normalize_answer
from experiments.failure_analysis_common import load_jsonl, write_json, write_text
from experiments.wandb_logging import git_commit_hash, package_available as wandb_package_available

REPO_ROOT = Path(__file__).resolve().parents[1]

SEED31_SOURCE = {
    "source_id": "promotion_grade_baselines_seed31_budget6",
    "path": "outputs/promotion_grade_cohere_all_baselines_validation_20260519T005021Z/"
    "runner_output/cohere_real_model_cost_normalized_validation_20260519T005206Z/"
    "per_example_records.jsonl",
    "rationale": "Disjoint additional evidence at seed=31 (100 examples), per docs/CURRENT_CANONICAL_STATE_20260527.md.",
}

KNOWN_USED_SOURCES: tuple[dict[str, str], ...] = tuple(CANONICAL_DEFAULT_INPUTS) + (SEED31_SOURCE,)

CANDIDATE_RULE_NAME = "repair_primary_plus_unanimity_fallback"
DEFAULT_BUDGET = 6
DEFAULT_SIZE = 300
DEFAULT_CANDIDATE_SEED = 97

_GSM8K_ID_RE = re.compile(r"^openai_gsm8k_train_(\d+)$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, help="Non-destructive output directory.")
    parser.add_argument("--fresh-seed", type=int, default=DEFAULT_CANDIDATE_SEED, help="Seed for the new fresh split.")
    parser.add_argument("--size", type=int, default=DEFAULT_SIZE, help="Number of fresh examples to select (min 300 recommended).")
    parser.add_argument("--budget", type=int, default=DEFAULT_BUDGET, help="Branch budget B per method.")
    parser.add_argument(
        "--skip-dry-run-smoke-test",
        action="store_true",
        help="Skip invoking the dry-run runner as a readiness smoke test (still writes the plan/manifest).",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Environment checks (no secrets printed)
# ---------------------------------------------------------------------------


def _env_present(name: str) -> bool:
    return bool(os.environ.get(name))


def _wandb_really_installed() -> bool:
    """True only if the real wandb SDK is installed.

    `import wandb` succeeding is not sufficient: this repo has a local
    `wandb/` directory at its root (real historical W&B run logs), which
    Python 3 will happily import as an empty *namespace* package if the real
    `wandb` distribution is not actually installed -- `experiments.wandb_logging
    .package_available()` (a plain `import wandb` try/except) is fooled by
    this when run from the repo root. A genuinely installed package has a
    concrete `__file__` and a real `init` attribute; the namespace-package
    shadow has neither.
    """
    try:
        import wandb
    except ImportError:
        return False
    return getattr(wandb, "__file__", None) is not None and hasattr(wandb, "init")


def _azure_openai_env_status() -> dict[str, Any]:
    """Report Azure OpenAI config presence (names/booleans only, never values).

    Checks both the native `openai` SDK's `AzureOpenAI` client env-var names
    (AZURE_OPENAI_API_KEY/ENDPOINT/DEPLOYMENT/API_VERSION) and the
    litellm-style aliases (AZURE_API_KEY/AZURE_API_BASE/AZURE_API_VERSION)
    found in this machine's ~/.bashrc. An earlier diagnosis reported no VAPI
    and defaulted to Cohere without ever checking for AZURE_* variables at
    all; those variables are in fact present here (sourced via
    `~/.api_tokens`, itself sourced from `~/.bashrc`), but only visible in a
    shell that actually sources dotfiles -- a bare/non-login subprocess would
    not see them.
    """
    native = {
        "AZURE_OPENAI_API_KEY": _env_present("AZURE_OPENAI_API_KEY"),
        "AZURE_OPENAI_ENDPOINT": _env_present("AZURE_OPENAI_ENDPOINT"),
        "AZURE_OPENAI_DEPLOYMENT": _env_present("AZURE_OPENAI_DEPLOYMENT"),
        "AZURE_OPENAI_API_VERSION": _env_present("AZURE_OPENAI_API_VERSION"),
    }
    litellm_style = {
        "AZURE_API_KEY": _env_present("AZURE_API_KEY"),
        "AZURE_API_BASE": _env_present("AZURE_API_BASE"),
        "AZURE_API_VERSION": _env_present("AZURE_API_VERSION"),
    }
    try:
        import openai  # noqa: F401

        openai_sdk_importable = True
    except ImportError:
        openai_sdk_importable = False

    native_configured = all(native.values())
    litellm_configured = all(litellm_style.values())

    return {
        "env_vars_present": {**native, **litellm_style},
        "native_openai_sdk_style_configured": native_configured,
        "litellm_style_configured": litellm_configured,
        "openai_sdk_importable": openai_sdk_importable,
        "configured": (native_configured or litellm_configured) and openai_sdk_importable,
        "note": (
            "Azure OpenAI env vars found (names only, values never printed): "
            f"{sorted(k for k, v in {**native, **litellm_style}.items() if v)}. "
            "The `openai` Python SDK is installed and its `AzureOpenAI` client can be constructed "
            "from these -- see experiments/run_api_validation_repair_candidate.py "
            "resolve_provider_client_status(). Client construction performs no network call."
        ),
    }


def check_environment() -> dict[str, Any]:
    tmux_path = shutil.which("tmux")
    tmux_version = None
    if tmux_path:
        try:
            out = subprocess.run([tmux_path, "-V"], capture_output=True, text=True, timeout=5, check=False)
            tmux_version = out.stdout.strip() or None
        except OSError:
            tmux_version = None

    wandb_importable = wandb_package_available()
    wandb_installed = _wandb_really_installed()
    wandb_api_key_present = _env_present("WANDB_API_KEY")
    wandb_project_present = _env_present("WANDB_PROJECT")

    vapi_module_found = False
    try:
        __import__("vapi")
        vapi_module_found = True
    except ImportError:
        vapi_module_found = False
    vapi_env_present = any(_env_present(name) for name in ("VAPI_API_KEY", "VAPI_KEY", "VAPI_TOKEN"))

    provider_keys = {
        "COHERE_API_KEY": _env_present("COHERE_API_KEY"),
        "CO_API_KEY": _env_present("CO_API_KEY"),
        "OPENAI_API_KEY": _env_present("OPENAI_API_KEY"),
        "MISTRAL_API_KEY": _env_present("MISTRAL_API_KEY"),
        "CLOUDRIFT_API_KEY": _env_present("CLOUDRIFT_API_KEY"),
        "AZURE_OPENAI_API_KEY": _env_present("AZURE_OPENAI_API_KEY"),
        "AZURE_API_KEY": _env_present("AZURE_API_KEY"),
    }

    azure_openai = _azure_openai_env_status()

    return {
        "tmux": {
            "available": tmux_path is not None,
            "path": tmux_path,
            "version": tmux_version,
        },
        "wandb": {
            "import_succeeds": wandb_importable,
            "package_actually_installed": wandb_installed,
            "api_key_env_present": wandb_api_key_present,
            "project_env_present": wandb_project_present,
            "configured": wandb_installed and wandb_api_key_present,
            "note": (
                "experiments/wandb_logging.py already implements lazy, no-op-safe W&B logging in this "
                "repo; reused here rather than reimplemented. IMPORTANT: `import wandb` succeeds from "
                "the repo root even though the real SDK is not pip-installed (`pip show wandb` finds "
                "nothing) -- this repo has a local wandb/ directory of real historical run logs, which "
                "Python 3 imports as an empty namespace package. `package_actually_installed` checks for "
                "a real __file__/init attribute to avoid this false positive; `import_succeeds` alone "
                "would have reported this repo as W&B-ready when a call to wandb.init() would in fact "
                "raise AttributeError. WANDB_API_KEY/WANDB_PROJECT env vars are set and local run history "
                "exists, so W&B was evidently used successfully before -- just not with this exact .venv."
            ),
        },
        "vapi": {
            "module_found": vapi_module_found,
            "env_vars_present": vapi_env_present,
            "configured": vapi_module_found and vapi_env_present,
            "note": (
                "No 'VAPI' package, module, or reference was found anywhere in this repository "
                "(checked via `pip show`, a repo-wide case-insensitive grep, and env var inspection). "
                "This plan defaults to the 'cohere' provider, matching every canonical FTA result in "
                "this repo. If VAPI refers to a specific tool not present in this checkout, it needs to "
                "be installed/configured before --provider vapi can do anything beyond report this "
                "same 'not found' status."
            ),
        },
        "provider_api_keys_present": provider_keys,
        "any_provider_key_present": any(provider_keys.values()),
        "azure_openai": azure_openai,
    }


# ---------------------------------------------------------------------------
# Fresh, non-overlapping GSM8K split selection
# ---------------------------------------------------------------------------


def _extract_gsm8k_idx(example_id: str) -> int | None:
    match = _GSM8K_ID_RE.match(str(example_id))
    return int(match.group(1)) if match else None


def load_used_examples(sources: tuple[dict[str, str], ...] = KNOWN_USED_SOURCES) -> dict[str, Any]:
    """Load every known-used GSM8K example_id + question text across seeds 41/61/71/31."""
    used_ids: set[str] = set()
    used_question_hashes: set[str] = set()
    per_source: list[dict[str, Any]] = []
    for spec in sources:
        path = REPO_ROOT / spec["path"]
        rows = load_jsonl(path)
        ids_here: set[str] = set()
        for row in rows:
            example_id = str(row.get("example_id"))
            ids_here.add(example_id)
            question = row.get("question")
            if question:
                used_question_hashes.add(hashlib.sha256(str(question).strip().lower().encode("utf-8")).hexdigest())
        overlap_with_prior = ids_here & used_ids
        per_source.append(
            {
                "source_id": spec["source_id"],
                "path": str(spec["path"]),
                "example_count": len(ids_here),
                "overlap_with_already_loaded_sources": len(overlap_with_prior),
            }
        )
        used_ids |= ids_here
    return {
        "used_example_ids": used_ids,
        "used_question_hashes": used_question_hashes,
        "used_gsm8k_indices": {idx for idx in (_extract_gsm8k_idx(eid) for eid in used_ids) if idx is not None},
        "per_source": per_source,
        "total_unique_used": len(used_ids),
    }


def load_gsm8k_train_split_offline() -> list[dict[str, Any]]:
    """Load the full openai/gsm8k train split from the local HF cache only.

    Forces HF_DATASETS_OFFLINE/HF_HUB_OFFLINE so this never makes a network
    request; if the dataset is not already cached locally this will raise
    rather than silently fetching it.
    """
    os.environ.setdefault("HF_DATASETS_OFFLINE", "1")
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    from datasets import load_dataset

    ds = load_dataset("openai/gsm8k", "main", split="train")
    rows = []
    for idx, row in enumerate(ds):
        answer_text = str(row.get("answer") or "")
        gold_canonical = answer_text.split("####")[-1].strip() if "####" in answer_text else answer_text.strip()
        rows.append(
            {
                "idx": idx,
                "example_id": f"openai_gsm8k_train_{idx}",
                "question": row.get("question"),
                "gold_answer": answer_text,
                "gold_answer_canonical": normalize_answer(gold_canonical) or gold_canonical,
            }
        )
    return rows


def select_fresh_split(
    *,
    fresh_seed: int,
    size: int,
    used: dict[str, Any],
    gsm8k_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    import random

    used_indices = used["used_gsm8k_indices"]
    available = [row for row in gsm8k_rows if row["idx"] not in used_indices]
    if len(available) < size:
        raise ValueError(f"only {len(available)} unused GSM8K rows available, need {size}")

    rng = random.Random(fresh_seed)
    selected = rng.sample(available, size)
    selected.sort(key=lambda r: r["idx"])

    selected_ids = {r["example_id"] for r in selected}
    selected_hashes = {
        hashlib.sha256(str(r["question"]).strip().lower().encode("utf-8")).hexdigest() for r in selected if r["question"]
    }

    id_overlap = selected_ids & used["used_example_ids"]
    hash_overlap = selected_hashes & used["used_question_hashes"]

    return {
        "fresh_seed": fresh_seed,
        "size": size,
        "gsm8k_train_total_rows": len(gsm8k_rows),
        "gsm8k_train_rows_already_used": len(used_indices),
        "gsm8k_train_rows_available": len(available),
        "examples": selected,
        "verification": {
            "example_id_overlap_count": len(id_overlap),
            "example_id_overlap": sorted(id_overlap),
            "question_hash_overlap_count": len(hash_overlap),
            "non_overlapping": len(id_overlap) == 0 and len(hash_overlap) == 0,
        },
    }


# ---------------------------------------------------------------------------
# Call/token/latency estimation
# ---------------------------------------------------------------------------


def estimate_call_plan(n_examples: int, *, budget: int) -> dict[str, Any]:
    per_method = {
        "direct_reserve_semantic_frontier_v2": n_examples * budget,
        "external_l1_max": n_examples * budget,
        "external_s1_budget_forcing": n_examples * budget,
        "external_tale_prompt_budgeting": n_examples * budget,
    }
    total_logical_calls = sum(per_method.values())
    return {
        "n_examples": n_examples,
        "budget_per_method": budget,
        "logical_calls_per_method": per_method,
        "total_logical_calls": total_logical_calls,
        "logical_calls_per_example": total_logical_calls // n_examples if n_examples else 0,
        "formula_note": (
            "Matches the existing documented FTA budget accounting (docs/CLAIMS.md required disclosure "
            "#2): full pool generation costs 4 x B logical calls per example; B=6 here to match every "
            "canonical FTA run. FTA/the repair candidate itself add zero *additional* calls at "
            "selection time -- this is candidate-pool generation cost, not selector cost."
        ),
        "fields_to_fill_after_smoke_test": [
            "observed_prompt_tokens_per_call",
            "observed_completion_tokens_per_call",
            "observed_latency_seconds_per_call",
            "observed_cost_usd_per_call",
            "observed_call_failure_rate",
        ],
    }


# ---------------------------------------------------------------------------
# Manifest / report rendering
# ---------------------------------------------------------------------------


def build_run_manifest(
    *,
    env_check: dict[str, Any],
    used: dict[str, Any],
    split: dict[str, Any],
    call_plan: dict[str, Any],
) -> dict[str, Any]:
    return {
        "candidate_rule": CANDIDATE_RULE_NAME,
        "candidate_rule_status": "exploratory_not_promoted",
        "canonical_selector_unchanged": True,
        "manuscript_claims_unchanged": True,
        "no_paid_api_calls_made_by_this_script": True,
        "git_commit": git_commit_hash(REPO_ROOT),
        "environment_check": env_check,
        "used_sources_summary": used["per_source"],
        "used_examples_total": used["total_unique_used"],
        "fresh_split": {
            "fresh_seed": split["fresh_seed"],
            "size": split["size"],
            "gsm8k_train_total_rows": split["gsm8k_train_total_rows"],
            "gsm8k_train_rows_already_used": split["gsm8k_train_rows_already_used"],
            "gsm8k_train_rows_available": split["gsm8k_train_rows_available"],
            "verification": split["verification"],
            "example_id_sample": [r["example_id"] for r in split["examples"][:5]],
        },
        "call_plan": call_plan,
        "provider_default": "cohere",
        "vapi_status": env_check["vapi"],
        "azure_openai_status": env_check["azure_openai"],
    }


def render_validation_plan(manifest: dict[str, Any], split: dict[str, Any]) -> str:
    lines = [
        "# Fresh API Validation Plan",
        "",
        f"Candidate under test: `{CANDIDATE_RULE_NAME}` (exploratory; not promoted by this plan).",
        "",
        "## Split",
        "",
        f"- Recommended fresh seed: **{split['fresh_seed']}** (distinct from every known-used seed 31/41/61/71).",
        f"- Recommended size: **{split['size']}** (>= 300, matching the existing Final-300 precedent).",
        f"- GSM8K train split total rows: {split['gsm8k_train_total_rows']}",
        f"- Already used by prior canonical/disjoint runs: {split['gsm8k_train_rows_already_used']}",
        f"- Available for a fresh split: {split['gsm8k_train_rows_available']}",
        f"- Non-overlap verification: example_id_overlap={split['verification']['example_id_overlap_count']}, "
        f"question_hash_overlap={split['verification']['question_hash_overlap_count']} "
        f"(non_overlapping={split['verification']['non_overlapping']})",
        "",
        "## Provider / dataset / scope",
        "",
        "- Provider: Cohere (matches every canonical FTA result; VAPI was not found in this repo -- see "
        "environment check below).",
        "- Dataset: openai/gsm8k, train split (same as every canonical seed).",
        "- Do not extrapolate to MATH-500 or any other benchmark (existing scope disclosure, "
        "docs/CLAIMS.md).",
        "",
        "## Call budget",
        "",
    ]
    call_plan = manifest["call_plan"]
    for method, count in call_plan["logical_calls_per_method"].items():
        lines.append(f"- `{method}`: {count} logical calls")
    lines.append(f"- **total logical calls: {call_plan['total_logical_calls']}** ({call_plan['logical_calls_per_example']} per example)")
    lines.append("")
    lines.append("## Metrics to report")
    lines.append("")
    lines.extend(
        [
            "- accuracy with source-stratified bootstrap CI vs canonical FTA",
            "- wins/losses/ties vs canonical FTA, net wins",
            "- regression rate among FTA-correct rows",
            "- per-override_reason breakdown (the safety signal found offline is override_reason-specific)",
            "- rule decision legality audit (must stay 100% runtime-legal)",
        ]
    )
    lines.append("")
    lines.append("## Anti-overfitting")
    lines.append("")
    lines.append(
        "Evaluate the candidate exactly as offline-replayed (see "
        "outputs/failure_analysis/rule_stress_test_20260708T145603Z/ and "
        "outputs/failure_analysis/pattern_cause_repair_20260708T151516Z/repair_candidate_report.md) "
        "-- do not re-tune its gate conditions using the new split before evaluating."
    )
    lines.append("")
    lines.append("## Stopping criteria (reject the candidate)")
    lines.append("")
    lines.extend(
        [
            "- bootstrap CI vs canonical FTA on the new split includes zero, OR",
            "- any single override_reason bucket shows a regression rate materially higher than its "
            "offline rate (~0.17%), OR",
            "- net wins go negative on more than one source/split evaluated.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def render_cost_and_risk(manifest: dict[str, Any], split: dict[str, Any]) -> str:
    call_plan = manifest["call_plan"]
    lines = [
        "# API Validation Cost and Risk",
        "",
        f"- estimated_number_of_examples: {split['size']}",
        f"- estimated_logical_calls_per_example: {call_plan['logical_calls_per_example']}",
        f"- **total_logical_calls: {call_plan['total_logical_calls']}**",
        "",
        "## Fields to fill in after the tiny smoke test (not estimated here)",
        "",
    ]
    for field in call_plan["fields_to_fill_after_smoke_test"]:
        lines.append(f"- {field}: TBD")
    lines.extend(
        [
            "",
            "## Failure modes",
            "",
            "- provider rate limiting / transient errors (retry with backoff, cap retries, log failures "
            "-- do not silently drop examples)",
            "- parse/extraction failures on candidate answers (already tracked as "
            "`parse_extraction_failure` in the existing schema)",
            "- schema drift vs the existing FTA replay pipeline (mitigated: the runner skeleton writes "
            "the same per-example JSONL schema consumed by experiments/build_failure_feature_table.py)",
            "- accidental reuse of an already-used GSM8K example (mitigated: id + question-hash "
            "non-overlap check before any run)",
            "",
            "## Stop criteria",
            "",
            "- Stop immediately if the smoke test (`--limit`, small N) shows a call-failure rate above "
            "10%, or if any generated record fails to parse under the existing feature-table builder.",
            "- Stop and do not scale to the full N if the observed cost/call materially exceeds the "
            "estimate above without prior approval.",
            "",
            "## Rollback / no-overwrite policy",
            "",
            "- Every run writes to a new output directory; the writer helpers "
            "(`experiments/failure_analysis_common.py`) refuse to overwrite existing files.",
            "- Nothing under `outputs/` is ever deleted or modified by this plan or runner.",
            "",
            "## Why this is fresh validation, not promotion",
            "",
            f"`{CANDIDATE_RULE_NAME}` remains exploratory. This plan prepares infrastructure to test it "
            "on data disjoint from every corpus used to discover or offline-replay it (seeds 31/41/61/71); "
            "running it (with human authorization for the paid calls) would produce independent evidence, "
            "but promotion is a separate, later decision requiring its own explicit review -- not a side "
            "effect of running this plan or even the live validation job.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _tmux_session_name(timestamp: str) -> str:
    return f"fta_api_validation_{timestamp}"


def render_tmux_scripts(*, output_dir: Path, timestamp: str, split: dict[str, Any], env_check: dict[str, Any]) -> dict[str, str]:
    session_name = _tmux_session_name(timestamp)
    split_manifest = output_dir / "fresh_split_manifest.json"
    python_bin = "./.venv/bin/python"

    dry_run_smoke_test = f"""#!/usr/bin/env bash
# Tiny, clearly-marked smoke test. Makes ZERO API calls (synthetic
# placeholder answers only). Safe to run any time.
set -euo pipefail
cd "{REPO_ROOT}"
RUN_DIR="{output_dir}/manual_dry_run_$(date -u +%Y%m%dT%H%M%SZ)"
{python_bin} -m experiments.run_api_validation_repair_candidate \\
  --split-manifest "{split_manifest}" \\
  --output-dir "$RUN_DIR" \\
  --dry-run --limit 5 --seed 0
echo "dry-run smoke test output: $RUN_DIR"
"""

    launch_full = f"""#!/usr/bin/env bash
# Launches the FULL live API validation run under tmux.
# Requires an explicit human decision to run: this script is never invoked
# automatically by any other script in this directory.
#
# The --live code path in experiments/run_api_validation_repair_candidate.py
# is intentionally stubbed to raise rather than call a provider -- per
# AGENTS.md / AGENTS_LOCAL_AUTONOMY.md, paid API calls require explicit,
# separate, per-call user authorization that this script alone cannot grant.
# A human operator must wire up an authorized provider client before this
# can actually spend money.
set -euo pipefail
cd "{REPO_ROOT}"

if ! command -v tmux >/dev/null 2>&1; then
  echo "tmux is not available. Per project policy, do not run long jobs directly outside tmux. Stopping." >&2
  exit 1
fi

SESSION="{session_name}"
RUN_DIR="{output_dir}/live_run_$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$RUN_DIR"

tmux new-session -d -s "$SESSION" \\
  "{python_bin} -m experiments.run_api_validation_repair_candidate \\
     --split-manifest '{split_manifest}' \\
     --output-dir '$RUN_DIR' \\
     --live --provider cohere --seed {split['fresh_seed']} \\
     2>&1 | tee '$RUN_DIR/launch.log'"

echo "tmux session name: $SESSION"
echo "attach command: tmux attach -t $SESSION"
echo "log-watch command: tail -f '$RUN_DIR/launch.log'"
echo "output directory: $RUN_DIR"
"""

    watch_logs = f"""#!/usr/bin/env bash
set -euo pipefail
SESSION="{session_name}"
if tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "Attaching to tmux session $SESSION (Ctrl-b d to detach)."
  tmux attach -t "$SESSION"
else
  echo "No live tmux session named $SESSION found; tailing the most recent live_run log instead."
  LATEST_LOG=$(ls -t "{output_dir}"/live_run_*/launch.log 2>/dev/null | head -1 || true)
  if [ -z "$LATEST_LOG" ]; then
    echo "No live_run logs found under {output_dir} yet."
    exit 1
  fi
  tail -f "$LATEST_LOG"
fi
"""

    return {
        "dry_run_smoke_test.sh": dry_run_smoke_test,
        "launch_full_api_validation_tmux.sh": launch_full,
        "watch_logs.sh": watch_logs,
    }


def render_dry_run_readiness_report(smoke_result: dict[str, Any]) -> str:
    lines = [
        "# Dry-Run Readiness Report",
        "",
        "Result of actually invoking `experiments/run_api_validation_repair_candidate.py --dry-run` "
        "as a readiness smoke test. This makes zero network/API calls (synthetic placeholder answers "
        "only) and is safe to run in any session.",
        "",
    ]
    if smoke_result.get("skipped"):
        lines.append("Smoke test was skipped (`--skip-dry-run-smoke-test`).")
        return "\n".join(lines).rstrip() + "\n"
    lines.append(f"- return_code: {smoke_result['return_code']}")
    lines.append(f"- records_written: {smoke_result.get('records_written')}")
    lines.append(f"- schema_compatible_with_build_failure_feature_table: {smoke_result.get('schema_compatible')}")
    lines.append(f"- output_dir: {smoke_result.get('output_dir')}")
    lines.append("")
    lines.append("## stdout")
    lines.append("```")
    lines.append(smoke_result.get("stdout", "").strip())
    lines.append("```")
    if smoke_result.get("stderr"):
        lines.append("")
        lines.append("## stderr")
        lines.append("```")
        lines.append(smoke_result["stderr"].strip())
        lines.append("```")
    return "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------------------
# Dry-run smoke test invocation (zero API calls)
# ---------------------------------------------------------------------------


def run_dry_run_smoke_test(*, split_manifest_path: Path, output_dir: Path, limit: int = 5) -> dict[str, Any]:
    smoke_dir = output_dir / "dry_run_smoke_test"
    cmd = [
        sys.executable,
        "-m",
        "experiments.run_api_validation_repair_candidate",
        "--split-manifest",
        str(split_manifest_path),
        "--output-dir",
        str(smoke_dir),
        "--dry-run",
        "--limit",
        str(limit),
        "--seed",
        "0",
    ]
    proc = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=60, check=False)

    records_written = None
    schema_compatible = None
    records_path = smoke_dir / "per_example_records.jsonl"
    if records_path.exists():
        rows = load_jsonl(records_path)
        records_written = len(rows)
        required_fields = {"example_id", "method", "gold_answer_canonical", "final_answer_canonical", "result_metadata"}
        schema_compatible = all(required_fields.issubset(row.keys()) for row in rows)

    return {
        "return_code": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "records_written": records_written,
        "schema_compatible": schema_compatible,
        "output_dir": str(smoke_dir),
    }


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    env_check = check_environment()
    used = load_used_examples()
    gsm8k_rows = load_gsm8k_train_split_offline()
    split = select_fresh_split(fresh_seed=args.fresh_seed, size=args.size, used=used, gsm8k_rows=gsm8k_rows)
    if not split["verification"]["non_overlapping"]:
        raise RuntimeError(f"fresh split failed non-overlap verification: {split['verification']}")
    call_plan = estimate_call_plan(split["size"], budget=args.budget)

    manifest = build_run_manifest(env_check=env_check, used=used, split=split, call_plan=call_plan)
    write_json(output_dir / "RUN_MANIFEST.json", manifest)

    split_manifest_path = output_dir / "fresh_split_manifest.json"
    write_json(split_manifest_path, {"fresh_seed": split["fresh_seed"], "examples": split["examples"]})

    write_text(output_dir / "VALIDATION_PLAN.md", render_validation_plan(manifest, split))
    write_text(output_dir / "API_VALIDATION_COST_AND_RISK.md", render_cost_and_risk(manifest, split))

    if args.skip_dry_run_smoke_test:
        smoke_result: dict[str, Any] = {"skipped": True}
    else:
        smoke_result = run_dry_run_smoke_test(split_manifest_path=split_manifest_path, output_dir=output_dir)
    write_text(output_dir / "DRY_RUN_READINESS_REPORT.md", render_dry_run_readiness_report(smoke_result))

    timestamp = output_dir.name.split("_")[-1]
    tmux_scripts = render_tmux_scripts(output_dir=output_dir, timestamp=timestamp, split=split, env_check=env_check)
    for filename, content in tmux_scripts.items():
        script_path = output_dir / filename
        write_text(script_path, content)
        script_path.chmod(0o755)

    print(
        json.dumps(
            {
                "output_dir": str(output_dir),
                "fresh_seed": split["fresh_seed"],
                "size": split["size"],
                "non_overlapping": split["verification"]["non_overlapping"],
                "total_logical_calls": call_plan["total_logical_calls"],
                "tmux_available": env_check["tmux"]["available"],
                "wandb_configured": env_check["wandb"]["configured"],
                "vapi_configured": env_check["vapi"]["configured"],
                "dry_run_smoke_test_ok": smoke_result.get("return_code") == 0 if not smoke_result.get("skipped") else None,
                "tmux_session_name": _tmux_session_name(timestamp),
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
