"""Prepare a fresh Cohere disjoint validation for `repair_primary_plus_unanimity_fallback`.

This script makes zero paid API calls. It:
  - selects a fresh GSM8K train-split sample (N=300) disjoint from every
    known-used Cohere seed (31/41/61/71), Azure seed-97, and other local
    validation outputs (checked by example_id, question hash, and normalized
    question text);
  - checks Cohere/tmux/W&B environment readiness without printing secrets;
  - writes validation plan docs and tmux launch scripts (dry-run default;
    full live hard-blocked);
  - runs a zero-API dry-run smoke test through the existing runner.

Guardrails: does not promote any rule, does not change FTA/FIX-2+FIX-4
selector logic, and does not modify manuscript claims.
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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from experiments.api_validation_plan_repair_candidate import (
    CANDIDATE_RULE_NAME,
    DEFAULT_BUDGET,
    DEFAULT_SIZE,
    KNOWN_USED_SOURCES,
    SEED31_SOURCE,
    _wandb_really_installed,
    estimate_call_plan,
    load_gsm8k_train_split_offline,
    load_used_examples,
    select_fresh_split,
)
from experiments.build_failure_feature_table import normalize_answer
from experiments.failure_analysis_common import load_jsonl, write_json, write_text
from experiments.wandb_logging import git_commit_hash, package_available as wandb_package_available

REPO_ROOT = Path(__file__).resolve().parents[1]

# Fresh Cohere disjoint split (distinct from Azure seed-97 and canonical Cohere seeds).
COHERE_DISJOINT_FRESH_SEED = 53
COHERE_DISJOINT_FRESH_SIZE = 300
FORBIDDEN_FRESH_SEEDS = frozenset({31, 41, 61, 71, 97})
COHERE_LIVE_SMOKE_MAX_LIMIT = 2

AZURE_SEED97_USED_SOURCE = {
    "source_id": "azure_disjoint_validation_seed97_budget6",
    "path": (
        "outputs/api_validation_live/azure_openai_seed97_repair_candidate_20260708T173734Z/"
        "run_out/per_example_records.jsonl"
    ),
    "rationale": "Azure OpenAI disjoint validation at fresh seed=97 (N=300); must not overlap Cohere disjoint split.",
}

AZURE_SEED97_MANIFEST_SOURCE = {
    "source_id": "azure_disjoint_split_manifest_seed97",
    "path": (
        "outputs/api_validation_plans/repair_primary_plus_unanimity_20260708T153446Z/"
        "fresh_split_manifest.json"
    ),
    "rationale": "Manifest for Azure seed-97 split (example_ids even if live records absent).",
    "manifest_json": True,
}

_API_VALIDATION_RECORD_GLOB = (
    "outputs/api_validation_live/**/per_example_records.jsonl",
    "outputs/api_validation_smoke/**/per_example_records.jsonl",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        default="",
        help="Non-destructive output directory. Default: outputs/api_validation_plans/cohere_disjoint_repair_primary_<timestamp>/",
    )
    parser.add_argument(
        "--fresh-seed",
        type=int,
        default=COHERE_DISJOINT_FRESH_SEED,
        help=f"Seed for the new fresh Cohere split (must not be in {sorted(FORBIDDEN_FRESH_SEEDS)}).",
    )
    parser.add_argument("--size", type=int, default=COHERE_DISJOINT_FRESH_SIZE)
    parser.add_argument("--budget", type=int, default=DEFAULT_BUDGET)
    parser.add_argument(
        "--skip-dry-run-smoke-test",
        action="store_true",
        help="Skip invoking the dry-run runner as a readiness smoke test.",
    )
    return parser.parse_args()


def _env_present(name: str) -> bool:
    return bool(os.environ.get(name))


def _normalize_question_text(question: str | None) -> str:
    if not question:
        return ""
    return re.sub(r"\s+", " ", str(question).strip().lower())


def _question_hash(question: str | None) -> str:
    return hashlib.sha256(_normalize_question_text(question).encode("utf-8")).hexdigest()


def discover_additional_used_sources() -> list[dict[str, str]]:
    """Find per_example_records.jsonl under api_validation_* trees not already listed."""
    known_paths = {str(REPO_ROOT / spec["path"]) for spec in KNOWN_USED_SOURCES}
    known_paths.add(str(REPO_ROOT / AZURE_SEED97_USED_SOURCE["path"]))
    extras: list[dict[str, str]] = []
    seen: set[str] = set()
    for pattern in _API_VALIDATION_RECORD_GLOB:
        for path in sorted(REPO_ROOT.glob(pattern)):
            resolved = str(path.resolve())
            if resolved in known_paths or resolved in seen:
                continue
            seen.add(resolved)
            rel = path.relative_to(REPO_ROOT).as_posix()
            extras.append(
                {
                    "source_id": f"discovered_api_validation_{path.parent.parent.name}",
                    "path": rel,
                    "rationale": f"Auto-discovered local validation output at {rel}.",
                }
            )
    return extras


def cohere_known_used_sources() -> tuple[dict[str, str], ...]:
    base = tuple(KNOWN_USED_SOURCES) + (AZURE_SEED97_USED_SOURCE,)
    return base + tuple(discover_additional_used_sources())


def load_used_examples_from_manifest(manifest_path: Path) -> set[str]:
    if not manifest_path.exists():
        return set()
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    return {str(ex["example_id"]) for ex in payload.get("examples", [])}


def load_used_examples_extended(sources: tuple[dict[str, str], ...]) -> dict[str, Any]:
    used = load_used_examples(sources)
    manifest_path = REPO_ROOT / AZURE_SEED97_MANIFEST_SOURCE["path"]
    manifest_ids = load_used_examples_from_manifest(manifest_path)
    if manifest_ids:
        overlap = manifest_ids & used["used_example_ids"]
        used["per_source"].append(
            {
                "source_id": AZURE_SEED97_MANIFEST_SOURCE["source_id"],
                "path": AZURE_SEED97_MANIFEST_SOURCE["path"],
                "example_count": len(manifest_ids),
                "overlap_with_already_loaded_sources": len(overlap),
            }
        )
        used["used_example_ids"] |= manifest_ids
        used["total_unique_used"] = len(used["used_example_ids"])
    return used


def _shell_startup_cohere_hints() -> dict[str, Any]:
    """Report whether common shell startup files mention Cohere env vars (no values)."""
    candidates = [
        Path.home() / ".bashrc",
        Path.home() / ".profile",
        Path.home() / ".bash_profile",
        Path.home() / ".api_tokens",
        REPO_ROOT / ".env",
    ]
    cohere_var_names = ("COHERE_API_KEY", "CO_API_KEY")
    per_file: list[dict[str, Any]] = []
    for path in candidates:
        entry: dict[str, Any] = {"path": str(path), "exists": path.is_file()}
        if not path.is_file():
            per_file.append(entry)
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            entry["readable"] = False
            per_file.append(entry)
            continue
        entry["readable"] = True
        entry["mentions_cohere_api_key"] = any(name in text for name in cohere_var_names)
        per_file.append(entry)
    return {"startup_files_checked": per_file}


def check_cohere_environment() -> dict[str, Any]:
    tmux_path = shutil.which("tmux")
    tmux_version = None
    if tmux_path:
        try:
            out = subprocess.run([tmux_path, "-V"], capture_output=True, text=True, timeout=5, check=False)
            tmux_version = out.stdout.strip() or None
        except OSError:
            tmux_version = None

    cohere_key_present = _env_present("COHERE_API_KEY") or _env_present("CO_API_KEY")
    cohere_sdk_importable = False
    cohere_sdk_error: str | None = None
    try:
        import cohere  # noqa: F401

        cohere_sdk_importable = True
    except ImportError as exc:
        cohere_sdk_error = type(exc).__name__

    delegate_import_ok = False
    delegate_import_error: str | None = None
    try:
        subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "run_cohere_real_model_cost_normalized_validation.py"),
                "--help",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        delegate_import_ok = True
    except OSError as exc:
        delegate_import_error = type(exc).__name__

    wandb_installed = _wandb_really_installed()
    wandb_api_key_present = _env_present("WANDB_API_KEY")
    wandb_project_present = _env_present("WANDB_PROJECT")

    return {
        "tmux": {"available": tmux_path is not None, "path": tmux_path, "version": tmux_version},
        "cohere": {
            "COHERE_API_KEY_present": _env_present("COHERE_API_KEY"),
            "CO_API_KEY_present": _env_present("CO_API_KEY"),
            "api_key_configured": cohere_key_present,
            "cohere_sdk_importable": cohere_sdk_importable,
            "cohere_sdk_import_error_type": cohere_sdk_error,
            "delegate_script_help_runs": delegate_import_ok,
            "delegate_script_error_type": delegate_import_error,
            "configured": cohere_key_present and cohere_sdk_importable and delegate_import_ok,
        },
        "wandb": {
            "import_succeeds": wandb_package_available(),
            "package_actually_installed": wandb_installed,
            "api_key_env_present": wandb_api_key_present,
            "project_env_present": wandb_project_present,
            "configured": wandb_installed and wandb_api_key_present,
            "note": (
                "W&B is optional for validation; if WANDB_API_KEY is unset in tmux, "
                "logging is skipped without failing the run."
            ),
        },
        "shell_startup": _shell_startup_cohere_hints(),
        "python_executable": sys.executable,
        "venv_expected": str(REPO_ROOT / ".venv" / "bin" / "python"),
    }


def verify_split_extended(*, split: dict[str, Any], used: dict[str, Any], gsm8k_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Extra overlap audit: normalized question text against all GSM8K used rows."""
    used_norm_texts: set[str] = set()
    gsm8k_by_id = {r["example_id"]: r for r in gsm8k_rows}
    for eid in used["used_example_ids"]:
        row = gsm8k_by_id.get(eid)
        if row and row.get("question"):
            used_norm_texts.add(_normalize_question_text(row["question"]))

    selected_norm_overlap: list[str] = []
    for ex in split["examples"]:
        norm = _normalize_question_text(ex.get("question"))
        if norm and norm in used_norm_texts:
            selected_norm_overlap.append(ex["example_id"])

    base = split["verification"]
    non_overlapping = (
        base["non_overlapping"]
        and len(selected_norm_overlap) == 0
        and split["fresh_seed"] not in FORBIDDEN_FRESH_SEEDS
    )
    return {
        **base,
        "normalized_question_text_overlap_count": len(selected_norm_overlap),
        "normalized_question_text_overlap_example_ids": sorted(selected_norm_overlap),
        "fresh_seed_forbidden_overlap": split["fresh_seed"] in FORBIDDEN_FRESH_SEEDS,
        "non_overlapping": non_overlapping,
    }


def build_split_manifest(*, split: dict[str, Any], verification: dict[str, Any], budget: int) -> dict[str, Any]:
    return {
        "provider": "cohere",
        "dataset": "openai/gsm8k",
        "split": "train",
        "fresh_seed": split["fresh_seed"],
        "size": split["size"],
        "budget": budget,
        "candidate_rule": CANDIDATE_RULE_NAME,
        "candidate_rule_status": "exploratory_not_promoted",
        "canonical_selector_unchanged": True,
        "forbidden_prior_seeds": sorted(FORBIDDEN_FRESH_SEEDS),
        "verification": verification,
        "examples": split["examples"],
    }


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
        str(COHERE_DISJOINT_FRESH_SEED),
    ]
    proc = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=120, check=False)
    records_path = smoke_dir / "per_example_records.jsonl"
    rows = load_jsonl(records_path) if records_path.exists() else []
    required_fields = {"example_id", "method", "gold_answer_canonical", "final_answer_canonical", "result_metadata"}
    schema_compatible = bool(rows) and all(required_fields.issubset(row.keys()) for row in rows)
    return {
        "return_code": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "records_written": len(rows),
        "schema_compatible": schema_compatible,
        "output_dir": str(smoke_dir),
    }


def _tmux_session_name(timestamp: str) -> str:
    return f"cohere_disjoint_validation_{timestamp}"


def render_disjoint_split_audit(*, used: dict[str, Any], split: dict[str, Any], verification: dict[str, Any]) -> str:
    lines = [
        "# Cohere Disjoint Split Audit",
        "",
        f"- fresh_seed: **{split['fresh_seed']}**",
        f"- size: **{split['size']}**",
        f"- forbidden_prior_seeds: {sorted(FORBIDDEN_FRESH_SEEDS)}",
        f"- total_unique_used_examples_prior: **{used['total_unique_used']}**",
        "",
        "## Overlap checks",
        "",
        f"- example_id_overlap_count: **{verification['example_id_overlap_count']}**",
        f"- question_hash_overlap_count: **{verification['question_hash_overlap_count']}**",
        f"- normalized_question_text_overlap_count: **{verification['normalized_question_text_overlap_count']}**",
        f"- fresh_seed_forbidden_overlap: **{verification['fresh_seed_forbidden_overlap']}**",
        f"- non_overlapping (all checks): **{verification['non_overlapping']}**",
        "",
        "## Used sources",
        "",
    ]
    for src in used["per_source"]:
        lines.append(f"- `{src['source_id']}`: {src['example_count']} examples ({src['path']})")
    lines.extend(
        [
            "",
            "## Selected example_id range",
            "",
            f"- min_idx: {min(ex['idx'] for ex in split['examples'])}",
            f"- max_idx: {max(ex['idx'] for ex in split['examples'])}",
            "",
            "Gold labels in the manifest are for **post-hoc evaluation only**; they are never used as runtime selector features.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def render_environment_report(env: dict[str, Any]) -> str:
    cohere = env["cohere"]
    lines = [
        "# Cohere Environment Report",
        "",
        "Presence-only checks; **no secret values** are printed.",
        "",
        "## Cohere API",
        "",
        f"- COHERE_API_KEY_present: {cohere['COHERE_API_KEY_present']}",
        f"- CO_API_KEY_present: {cohere['CO_API_KEY_present']}",
        f"- api_key_configured: **{cohere['api_key_configured']}**",
        f"- cohere_sdk_importable: {cohere['cohere_sdk_importable']}",
        f"- delegate_script_help_runs: {cohere['delegate_script_help_runs']}",
        f"- configured (ready for live): **{cohere['configured']}**",
        "",
        "## tmux",
        "",
        f"- available: {env['tmux']['available']}",
        f"- version: {env['tmux'].get('version')}",
        "",
        "## W&B",
        "",
        f"- package_installed: {env['wandb']['package_actually_installed']}",
        f"- WANDB_API_KEY_present: {env['wandb']['api_key_env_present']}",
        f"- WANDB_PROJECT_present: {env['wandb']['project_env_present']}",
        f"- configured: {env['wandb']['configured']}",
        "",
        "## Shell startup files (Cohere var name mentions only)",
        "",
    ]
    for entry in env["shell_startup"]["startup_files_checked"]:
        if not entry.get("exists"):
            lines.append(f"- `{entry['path']}`: not found")
        elif not entry.get("readable", True):
            lines.append(f"- `{entry['path']}`: exists, not readable")
        else:
            lines.append(
                f"- `{entry['path']}`: mentions_cohere_api_key={entry.get('mentions_cohere_api_key', False)}"
            )
    lines.append("")
    lines.append(
        "If `api_key_configured` is false in a bare subprocess, source `~/.api_tokens` "
        "inside the tmux launch shell (launch scripts do this without printing values)."
    )
    return "\n".join(lines).rstrip() + "\n"


def render_validation_plan(*, split: dict[str, Any], call_plan: dict[str, Any], budget: int) -> str:
    return f"""# Cohere Validation Plan — `repair_primary_plus_unanimity_fallback`

## Scope

| Field | Value |
| --- | --- |
| Provider | **Cohere** (`command-r-plus-08-2024` via delegate script) |
| Dataset | `openai/gsm8k` train split |
| Fresh seed | **{split['fresh_seed']}** (disjoint from seeds 31/41/61/71/97) |
| N | **{split['size']}** |
| Budget B | **{budget}** (canonical, matches all prior FTA runs) |
| Candidate | `{CANDIDATE_RULE_NAME}` (exploratory; not promoted) |

## Baselines (post-hoc evaluation via `evaluate_api_validation_repair_candidate.py`)

| Baseline | Role |
| --- | --- |
| canonical FTA / FIX-2+FIX-4 | Primary comparison (unchanged selector logic) |
| frontier (`direct_reserve_semantic_frontier_v2`) | Method-only baseline |
| L1 (`external_l1_max`) | Method-only baseline |
| S1 (`external_s1_budget_forcing`) | Method-only baseline |
| TALE (`external_tale_prompt_budgeting`) | Method-only baseline |
| External-3 majority | Pooled external baseline |
| Pooled-4 majority | Offline reconstruction if 4 method answers present |
| `azure_ext3_when_swfb` | **Diagnostic only** — not a candidate |

## Generation phase (live run, when authorized)

1. Generate raw per-example/per-method answers for all 4 methods via
   `scripts/run_cohere_real_model_cost_normalized_validation.py` (delegated from
   `experiments/run_api_validation_repair_candidate.py --provider cohere`).
2. Write `per_example_records.jsonl` compatible with `build_failure_feature_table.py`.
3. **No selector logic runs at generation time** beyond branch search for each method.

## Evaluation phase (offline, after generation)

1. Run `experiments/evaluate_api_validation_repair_candidate.py` on completed JSONL.
2. Compare candidate vs canonical FTA: accuracy, net wins/losses/ties, paired bootstrap CI.
3. Apply decision rubric in `COHERE_VALIDATION_DECISION_RUBRIC.md`.

## Logical call accounting

- **Upper bound:** {call_plan['total_logical_calls']} logical calls ({call_plan['logical_calls_per_example']} per example × {split['size']} examples).
- **Convention:** 4 methods × B={budget} logical calls per example (docs/CLAIMS.md disclosure #2).
- **Actual calls:** typically lower due to early stopping (especially `external_l1_max`).

## Fields to log per row

- provider, model, method, example_id, question_hash
- raw response text, parsed answer, parse status
- input/output/total tokens, `cohere_logical_api_calls`, latency_seconds
- finish/error status

## W&B

- Optional: `--wandb --wandb-project frontier-allocation --wandb-run-name cohere_disjoint_seed{split['fresh_seed']}_<timestamp>`
- Skipped gracefully if `WANDB_API_KEY` unset in tmux.

## Checkpoint / resume

- `--resume` on runner; delegate script maintains nested checkpoint dir.
- Resume key: `(example_id, method)` pairs already in `per_example_records.jsonl`.

## Stopping / failure criteria

- Stop and investigate if API failure rate > 1% or parse failure rate > 2%.
- Stop if logical call cap (`--max-total-api-calls`) is hit before completion.
- Do not promote candidate based on partial runs.

## Prior evidence (discovery corpus, not independent)

- Cohere Aggregate-720: repair_primary_plus_unanimity_fallback **587/720 = 81.53%** vs FTA **581/720 = 80.69%** (net +6, 1 loss, CI excludes zero).
- This disjoint run is the **independent** stress test recommended by cross-provider synthesis.
"""


def render_cost_and_risk(*, call_plan: dict[str, Any], split: dict[str, Any]) -> str:
    return f"""# Cohere Validation Cost and Risk

## Cost estimate

| Item | Estimate |
| --- | --- |
| Examples | {split['size']} |
| Methods | 4 |
| Budget B | {call_plan['budget_per_method']} per method |
| Logical call upper bound | **{call_plan['total_logical_calls']}** |
| Observed actual calls (Azure seed-97 reference) | ~3,807 actual vs 7,200 upper bound (~53% of cap) |

Token/cost USD depends on Cohere pricing and observed tokens per call; fill after tiny smoke.

## Risks

1. **Paid API spend** — full run is ~thousands of logical calls; requires explicit human authorization.
2. **False positive from discovery corpus** — Aggregate-720 already showed +6 net; disjoint split may differ.
3. **Regression tail** — discovery corpus had 1 loss; disjoint may have more.
4. **Provider lock-in** — positive result validates Cohere only; does not generalize to Azure without separate evidence.
5. **No promotion by default** — even a positive disjoint result updates exploratory status only until manuscript review.

## Mitigations

- Tiny smoke (≤2 examples) before full run.
- Hard-blocked full launch script (`exit 1` guard).
- `--max-total-api-calls` safety cap on delegate script.
- tmux required for any live job.
- Gold used only in post-hoc evaluator, never at generation time.
"""


def render_decision_rubric() -> str:
    return """# Cohere Validation Decision Rubric

Apply **after** full N=300 generation and post-hoc evaluation.

## Primary hypothesis

`repair_primary_plus_unanimity_fallback` improves accuracy vs canonical FTA on a fresh Cohere disjoint split without unacceptable regressions.

## Outcomes

| Outcome | Criteria |
| --- | --- |
| **A — Support** | Net wins > 0 AND regression count ≤ 2 (≤0.67%) AND paired bootstrap CI vs FTA excludes zero |
| **B — Inconclusive** | Net wins ≥ 0 but CI includes zero, OR net wins > 0 with 3–5 regressions |
| **C — Reject** | Net wins ≤ 0 OR regression count > 5 OR CI upper bound < 0 |

## Required disclosures (unchanged regardless of outcome)

1. FTA vs pooled ensemble CI may include zero on discovery corpus.
2. Full pool = 4×B logical calls per example.
3. GSM8K / Cohere scope only unless separately validated.
4. Candidate remains exploratory until manuscript review — no automatic promotion.

## Not sufficient for promotion

- Beating frontier alone or External-3 alone without beating FTA with acceptable regressions.
- Azure SWFB diagnostic gains (provider-specific).
- Offline Pooled-4 macro average (high regression count on both providers).

## Next steps by outcome

- **A:** Consider manuscript supplementary / exploratory claim with full disclosures; still no code promotion without explicit review.
- **B:** Optional second disjoint seed or extended analysis; do not update main claims.
- **C:** Archive candidate; do not spend API budget on Azure SWFB until new hypothesis.
"""


def render_live_readiness(*, env: dict[str, Any], smoke: dict[str, Any], split: dict[str, Any]) -> str:
    cohere_ok = env["cohere"]["configured"]
    tmux_ok = env["tmux"]["available"]
    dry_ok = smoke.get("return_code") == 0 and smoke.get("schema_compatible")
    return f"""# Cohere Live Readiness

| Check | Status |
| --- | --- |
| Cohere API + SDK | **{'PASS' if cohere_ok else 'FAIL'}** |
| tmux available | **{'PASS' if tmux_ok else 'FAIL'}** |
| Dry-run smoke (schema) | **{'PASS' if dry_ok else 'FAIL/PENDING'}** |
| W&B (optional) | **{'configured' if env['wandb']['configured'] else 'not configured'}** |

## Tiny smoke command (≤2 examples, requires human authorization for paid calls)

```bash
# From repo root, inside tmux, after sourcing ~/.api_tokens:
./outputs/api_validation_plans/cohere_disjoint_repair_primary_<timestamp>/launch_tiny_cohere_smoke_tmux.sh
```

## Full validation command (BLOCKED — do not run without explicit authorization)

```bash
# Script exits 1 by design until human removes guard:
./outputs/api_validation_plans/cohere_disjoint_repair_primary_<timestamp>/launch_full_cohere_disjoint_validation_tmux.sh
```

Fresh split seed: **{split['fresh_seed']}**, N={split['size']}.
"""


def render_final_summary(
    *,
    output_dir: Path,
    split: dict[str, Any],
    verification: dict[str, Any],
    env: dict[str, Any],
    smoke: dict[str, Any],
) -> str:
    return f"""# Final Cohere Validation Prep Summary

- **output_dir:** `{output_dir}`
- **fresh_seed:** {split['fresh_seed']}
- **N:** {split['size']}
- **overlap audit:** {'PASS' if verification['non_overlapping'] else 'FAIL'}
- **Cohere env complete:** {env['cohere']['configured']}
- **W&B usable:** {env['wandb']['configured']}
- **dry-run smoke OK:** {smoke.get('return_code') == 0}
- **full live validation run:** NOT executed (prep only)
- **selector/manuscript changes:** none
- **commits/pushes:** none

## Artifacts

- `COHERE_DISJOINT_SPLIT_MANIFEST.json`
- `COHERE_DISJOINT_SPLIT_AUDIT.md`
- `COHERE_ENVIRONMENT_REPORT.md`
- `COHERE_VALIDATION_PLAN.md`
- `COHERE_VALIDATION_COST_AND_RISK.md`
- `COHERE_VALIDATION_DECISION_RUBRIC.md`
- `COHERE_LIVE_READINESS.md`
- `dry_run_cohere_validation.sh`
- `launch_tiny_cohere_smoke_tmux.sh`
- `launch_full_cohere_disjoint_validation_tmux.sh`
"""


def render_launch_scripts(
    *,
    output_dir: Path,
    timestamp: str,
    split_manifest: Path,
    split: dict[str, Any],
    budget: int,
) -> dict[str, str]:
    session_smoke = f"cohere_disjoint_smoke_{timestamp}"
    session_full = _tmux_session_name(timestamp)
    python_bin = "./.venv/bin/python"
    fresh_seed = split["fresh_seed"]

    dry_run = f"""#!/usr/bin/env bash
# Zero API calls — synthetic dry-run through the validation runner.
set -euo pipefail
cd "{REPO_ROOT}"
RUN_DIR="{output_dir}/manual_dry_run_$(date -u +%Y%m%dT%H%M%SZ)"
{python_bin} -m experiments.run_api_validation_repair_candidate \\
  --split-manifest "{split_manifest}" \\
  --output-dir "$RUN_DIR" \\
  --dry-run --limit 5 --seed {fresh_seed}
echo "dry-run output: $RUN_DIR"
"""

    tiny_smoke = f"""#!/usr/bin/env bash
# TINY COHERE LIVE SMOKE — at most {COHERE_LIVE_SMOKE_MAX_LIMIT} examples, ≤~{COHERE_LIVE_SMOKE_MAX_LIMIT * 4 * budget} logical calls upper bound.
# Requires explicit human authorization for paid Cohere API calls.
set -euo pipefail
cd "{REPO_ROOT}"

if ! command -v tmux >/dev/null 2>&1; then
  echo "tmux required. Stopping." >&2
  exit 1
fi

if [ -f "$HOME/.api_tokens" ]; then
  # shellcheck disable=SC1090
  source "$HOME/.api_tokens"
fi

SESSION="{session_smoke}"
RUN_DIR="{output_dir}/tiny_smoke_$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$RUN_DIR"

tmux new-session -d -s "$SESSION" \\
  "{python_bin} -m experiments.run_api_validation_repair_candidate \\
     --split-manifest '{split_manifest}' \\
     --output-dir '$RUN_DIR' \\
     --live --provider cohere --seed {fresh_seed} --budget {budget} \\
     --limit {COHERE_LIVE_SMOKE_MAX_LIMIT} \\
     2>&1 | tee '$RUN_DIR/launch.log'"

echo "tmux session name: $SESSION"
echo "attach command: tmux attach -t $SESSION"
echo "log-watch command: tail -f '$RUN_DIR/launch.log'"
echo "output directory: $RUN_DIR"
"""

    full_blocked = f"""#!/usr/bin/env bash
# FULL (N=300) COHERE DISJOINT LIVE VALIDATION — INTENTIONALLY DISABLED.
#
# Candidate: repair_primary_plus_unanimity_fallback
# Provider: Cohere only. Fresh seed: {fresh_seed}. N=300. Budget={budget}.
# Estimated up to {4 * budget * split['size']} logical API calls upper bound.
#
# Gates before enabling:
#   1. Tiny smoke (≤2 examples) must succeed.
#   2. Separate explicit human authorization for full paid run.
#   3. Remove the exit 1 guard below (or write a fresh reviewed script).
set -euo pipefail
cd "{REPO_ROOT}"

echo "Full N=300 Cohere disjoint validation is intentionally disabled." >&2
echo "Complete tiny smoke first: launch_tiny_cohere_smoke_tmux.sh" >&2
echo "Full-scale live validation requires separate explicit human authorization." >&2
exit 1

if ! command -v tmux >/dev/null 2>&1; then
  echo "tmux required." >&2
  exit 1
fi

if [ -f "$HOME/.api_tokens" ]; then
  # shellcheck disable=SC1090
  source "$HOME/.api_tokens"
fi

SESSION="{session_full}"
RUN_DIR="{output_dir}/live_run_$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$RUN_DIR"

tmux new-session -d -s "$SESSION" \\
  "{python_bin} -m experiments.run_api_validation_repair_candidate \\
     --split-manifest '{split_manifest}' \\
     --output-dir '$RUN_DIR' \\
     --live --provider cohere --allow-full-live --seed {fresh_seed} --budget {budget} \\
     --resume \\
     2>&1 | tee '$RUN_DIR/launch.log'"

echo "tmux session name: $SESSION"
echo "attach command: tmux attach -t $SESSION"
echo "log-watch command: tail -f '$RUN_DIR/launch.log'"
echo "output directory: $RUN_DIR"
"""

    return {
        "dry_run_cohere_validation.sh": dry_run,
        "launch_tiny_cohere_smoke_tmux.sh": tiny_smoke,
        "launch_full_cohere_disjoint_validation_tmux.sh": full_blocked,
    }


def main() -> int:
    args = parse_args()
    if args.fresh_seed in FORBIDDEN_FRESH_SEEDS:
        raise ValueError(f"fresh_seed {args.fresh_seed} is forbidden (prior validation seeds): {sorted(FORBIDDEN_FRESH_SEEDS)}")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = REPO_ROOT / "outputs" / "api_validation_plans" / f"cohere_disjoint_repair_primary_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)
    plan_timestamp = output_dir.name.split("_")[-1]

    sources = cohere_known_used_sources()
    used = load_used_examples_extended(sources)
    gsm8k_rows = load_gsm8k_train_split_offline()
    split = select_fresh_split(fresh_seed=args.fresh_seed, size=args.size, used=used, gsm8k_rows=gsm8k_rows)
    verification = verify_split_extended(split=split, used=used, gsm8k_rows=gsm8k_rows)
    split["verification"] = verification
    if not verification["non_overlapping"]:
        raise RuntimeError(f"fresh split failed non-overlap verification: {verification}")

    env_check = check_cohere_environment()
    call_plan = estimate_call_plan(split["size"], budget=args.budget)
    manifest = build_split_manifest(split=split, verification=verification, budget=args.budget)
    manifest["git_commit"] = git_commit_hash(REPO_ROOT)
    manifest["used_sources_summary"] = used["per_source"]
    manifest["used_examples_total"] = used["total_unique_used"]
    manifest["environment_check"] = env_check
    manifest["call_plan"] = call_plan

    split_manifest_path = output_dir / "COHERE_DISJOINT_SPLIT_MANIFEST.json"
    write_json(split_manifest_path, manifest)

    if args.skip_dry_run_smoke_test:
        smoke_result: dict[str, Any] = {"skipped": True}
    else:
        smoke_result = run_dry_run_smoke_test(split_manifest_path=split_manifest_path, output_dir=output_dir)

    write_text(output_dir / "COHERE_DISJOINT_SPLIT_AUDIT.md", render_disjoint_split_audit(used=used, split=split, verification=verification))
    write_text(output_dir / "COHERE_ENVIRONMENT_REPORT.md", render_environment_report(env_check))
    write_text(output_dir / "COHERE_VALIDATION_PLAN.md", render_validation_plan(split=split, call_plan=call_plan, budget=args.budget))
    write_text(output_dir / "COHERE_VALIDATION_COST_AND_RISK.md", render_cost_and_risk(call_plan=call_plan, split=split))
    write_text(output_dir / "COHERE_VALIDATION_DECISION_RUBRIC.md", render_decision_rubric())
    write_text(output_dir / "COHERE_LIVE_READINESS.md", render_live_readiness(env=env_check, smoke=smoke_result, split=split))
    write_text(
        output_dir / "FINAL_COHERE_VALIDATION_PREP_SUMMARY.md",
        render_final_summary(output_dir=output_dir, split=split, verification=verification, env=env_check, smoke=smoke_result),
    )

    for filename, content in render_launch_scripts(
        output_dir=output_dir,
        timestamp=plan_timestamp,
        split_manifest=split_manifest_path,
        split=split,
        budget=args.budget,
    ).items():
        script_path = output_dir / filename
        write_text(script_path, content)
        script_path.chmod(0o755)

    print(
        json.dumps(
            {
                "output_dir": str(output_dir),
                "fresh_seed": split["fresh_seed"],
                "size": split["size"],
                "non_overlapping": verification["non_overlapping"],
                "cohere_configured": env_check["cohere"]["configured"],
                "wandb_configured": env_check["wandb"]["configured"],
                "dry_run_smoke_ok": smoke_result.get("return_code") == 0 if not smoke_result.get("skipped") else None,
                "tmux_session_full": _tmux_session_name(plan_timestamp),
                "tmux_session_smoke": f"cohere_disjoint_smoke_{plan_timestamp}",
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
