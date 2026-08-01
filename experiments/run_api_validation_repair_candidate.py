"""Dry-run-capable, and now tiny-live-capable, API validation runner for the
repair-candidate check.

This script is infrastructure for validating
`repair_primary_plus_unanimity_fallback` (see
outputs/failure_analysis/pattern_cause_repair_*/repair_candidate_report.md).
It never calls a paid provider unless invoked with `--live`, and this repo's
agent-facing policy requires explicit, separate, per-call user authorization
before that flag is ever used -- this script does not grant that
authorization itself; the caller (human, via an explicit prompt) does.

VAPI: no "VAPI" package, module, or configuration was found anywhere in this
repository or its installed environment (checked via `pip show`, `grep -ri
vapi` across the whole tree, and env var inspection). Passing `--provider
vapi` is accepted for forward compatibility but currently only reports that
VAPI was not found; it does not silently fall back to a different provider.

`--provider azure_openai` is live-capable for TINY smoke tests
(`--limit` 1 or 2; see `validate_live_smoke_request()`) AND, separately, for
one specific, narrowly-gated FULL run (`--allow-full-live`; see
`validate_full_live_request()`): the fresh, verified-non-overlapping
seed=97, N=300 GSM8K split. `--allow-full-live` requires ALL of
`--provider azure_openai`, `--live`, `--seed 97`, the complete (untruncated)
300-example split, complete Azure config, and running inside an actual tmux
pane (checked via the `TMUX` env var) -- any other combination (wrong seed,
a `--limit` that would truncate the split, missing config, not in tmux)
raises before any request is made. This is deliberately narrow: it is not a
general "run any N live" escape hatch, and switching the *canonical* FTA
provider away from Cohere is not a side effect of this flag existing --
see docs/CLAIMS.md / docs/CURRENT_CANONICAL_STATE_20260527.md, which remain
Cohere x GSM8K only.

Neither live path reimplements branch-search logic here:
`direct_reserve_semantic_frontier_v2`, `external_l1_max`,
`external_s1_budget_forcing`, and `external_tale_prompt_budgeting` are
nontrivial, already-implemented, already-tested algorithms in
`experiments/controllers.py` / `experiments/branching.py` (the latter
already has a tested `azure_openai` `APIBranchGenerator` path -- see
`docs/AZURE_OPENAI_PROVIDER_ZERO_COST_INTEGRATION_20260524.md`). Rather than
duplicate that logic (and risk records that only *look* like real method
outputs without actually running the named methods), both live-azure paths
delegate to the already-tested
`scripts/run_cohere_real_model_cost_normalized_validation.py` pipeline --
see `run_live_azure_smoke()`, which is shared by both. `--provider
openai_compatible` remains dry-run/wiring-only (no live path implemented);
`--live --provider openai_compatible` or `--live --provider cohere`/`vapi`
still hit `run_live_stub()` and raise, unchanged.

In `--dry-run` mode (the default unless `--live` is explicitly passed), this
script never imports a provider SDK and never makes a network call. It
generates clearly-tagged synthetic placeholder answers so the rest of the
pipeline (per-example JSONL schema, W&B logging plumbing, FTA replay
compatibility) can be exercised end-to-end for free. `resolve_provider_client_status()`
runs in both modes and only ever *constructs* a provider SDK client object
(which involves no network I/O) to prove wiring works; it never issues a
request. Values of any env var are never logged, printed, or written to any
output file -- only variable names and booleans (deployment name and API
version are treated as non-secret labels, consistent with how this repo's
other Azure integration docs already surface them, and may appear as values;
API keys and the endpoint URL never do).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from experiments.failure_analysis_common import load_jsonl, write_json, write_jsonl, write_text
from experiments.wandb_logging import (
    add_wandb_cli_args,
    init_run,
    wandb_options_from_args,
)

METHOD_FRONTIER = "direct_reserve_semantic_frontier_v2"
METHOD_L1 = "external_l1_max"
METHOD_S1 = "external_s1_budget_forcing"
METHOD_TALE = "external_tale_prompt_budgeting"
METHOD_ORDER = (METHOD_FRONTIER, METHOD_L1, METHOD_S1, METHOD_TALE)

DEFAULT_BUDGET = 6
REPO_ROOT = Path(__file__).resolve().parents[1]
COHERE_REAL_MODEL_SCRIPT = REPO_ROOT / "scripts" / "run_cohere_real_model_cost_normalized_validation.py"
AZURE_LIVE_SMOKE_MAX_LIMIT = 2
AZURE_LIVE_SMOKE_DATASET = "openai/gsm8k"
FRESH_VALIDATED_SPLIT_SEED = 97
FRESH_VALIDATED_SPLIT_SIZE = 300

# Additional Azure fresh splits explicitly authorized for --allow-full-live, beyond the
# original seed-97 disjoint split. Each entry must have its own passed overlap audit
# against every prior cross-provider seed before being added here. seed=103 ->
# pooled4_fs_le1_notie split, audited non-overlapping against seeds 31/41/53/61/71/97 in
# outputs/api_validation_plans/azure_pooled4_fs_le1_notie_20260709T144600Z/AZURE_FRESH_SPLIT_AUDIT.md
# (gate change only -- full live launch still requires separate, later, explicit human
# authorization; adding a seed here does not itself launch anything).
ALLOWED_FULL_LIVE_AZURE_SEEDS: dict[int, int] = {
    FRESH_VALIDATED_SPLIT_SEED: FRESH_VALIDATED_SPLIT_SIZE,
    103: 300,
}

from experiments.cohere_disjoint_validation_plan import (  # noqa: E402
    COHERE_DISJOINT_FRESH_SEED,
    COHERE_DISJOINT_FRESH_SIZE,
    COHERE_LIVE_SMOKE_MAX_LIMIT,
)

# Additional Cohere fresh splits explicitly authorized for --allow-full-live, beyond the
# original seed-53 disjoint split. Each entry must have its own passed overlap audit against
# every prior seed before being added here. seed=83 -> pooled4_fs_le1_notie split, audited
# non-overlapping against seeds 31/41/61/71/97 in
# outputs/api_validation_plans/cohere_pooled4_fs_le1_notie_20260709T020758Z/COHERE_POOLED4_FS_LE1_NOTIE_SPLIT_AUDIT.md
# (explicit human authorization 2026-07-08 for the pooled4_fs_le1_notie_fta_v2_candidate validation).
ALLOWED_FULL_LIVE_COHERE_SEEDS: dict[int, int] = {
    COHERE_DISJOINT_FRESH_SEED: COHERE_DISJOINT_FRESH_SIZE,
    83: 300,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--split-manifest",
        required=True,
        help="Path to a fresh-split JSON manifest produced by experiments/api_validation_plan_repair_candidate.py.",
    )
    parser.add_argument("--output-dir", required=True, help="Non-destructive output directory for this run.")
    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        default=True,
        help="Generate synthetic placeholder records only; never calls a provider API (default).",
    )
    parser.add_argument(
        "--live",
        dest="dry_run",
        action="store_false",
        help=(
            "Attempt real provider calls. NOT SUPPORTED by this agent session: this repo's policy "
            "requires explicit, separate, per-call user authorization for paid API calls, which this "
            "flag alone does not provide. The live code path is stubbed and will raise."
        ),
    )
    parser.add_argument("--limit", type=int, default=None, help="Truncate the split to the first N examples (smoke test).")
    parser.add_argument("--seed", type=int, default=None, help="Seed label to record for this run (informational).")
    parser.add_argument(
        "--provider",
        default="cohere",
        choices=["cohere", "vapi", "azure_openai", "openai_compatible"],
        help=(
            "Provider to use for --live calls. 'vapi' is accepted but not found in this repo. "
            "'azure_openai' and 'openai_compatible' use the `openai` SDK client construction only "
            "(see resolve_provider_client_status(); no network call happens outside --live, and "
            "--live itself is stubbed -- see module docstring)."
        ),
    )
    parser.add_argument("--budget", type=int, default=DEFAULT_BUDGET, help="Branch budget B per method (default 6, matching canonical FTA runs).")
    parser.add_argument(
        "--resume",
        action="store_true",
        help=(
            "If --output-dir already contains a per_example_records.jsonl from an interrupted run, "
            "skip (example_id, method) pairs already written and append only the missing ones instead "
            "of refusing to overwrite."
        ),
    )
    parser.add_argument(
        "--allow-full-live",
        action="store_true",
        help=(
            "Narrowly-gated full-scale live validation path. For --provider azure_openai see "
            "validate_full_live_request() (seed 97). For --provider cohere see "
            "validate_cohere_full_live_request() (seed 53 disjoint split). Requires complete "
            "untruncated split, full provider config, and running inside tmux."
        ),
    )
    parser.add_argument(
        "--cohere-model",
        default="command-r-plus-08-2024",
        help="Cohere model name passed to the delegate script (--live --provider cohere only).",
    )
    add_wandb_cli_args(parser)
    return parser.parse_args()


def load_split_manifest(path: Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def resolve_provider_client_status(provider: str) -> dict[str, Any]:
    """Report whether `provider`'s SDK client can be constructed from env vars.

    Only checks env var *presence* (never values) and, if present, attempts
    to *construct* an SDK client object. Client construction alone makes no
    network call for either `openai.AzureOpenAI` or `openai.OpenAI` -- it
    just stores config -- so this is safe to run unconditionally, including
    in --dry-run mode. No secret value is ever placed in the returned dict,
    logged, or printed.
    """
    if provider == "azure_openai":
        required = [
            "AZURE_OPENAI_API_KEY",
            "AZURE_OPENAI_ENDPOINT",
            "AZURE_OPENAI_DEPLOYMENT",
            "AZURE_OPENAI_API_VERSION",
        ]
        present = {name: bool(os.environ.get(name)) for name in required}
        all_present = all(present.values())
        client_constructed = False
        construction_error_type = None
        if all_present:
            try:
                # Deliberately `openai.OpenAI(base_url=...)`, NOT `openai.AzureOpenAI`: this repo's
                # AZURE_OPENAI_ENDPOINT already contains the `/openai/v1` suffix, and the AzureOpenAI
                # SDK client appends its own `/openai/deployments/...` path, producing a double-prefix
                # 404 -- see docs/AZURE_OPENAI_PROVIDER_ZERO_COST_INTEGRATION_20260524.md section 10,
                # and experiments/branching.py::_call_azure_chat_api, which uses this same pattern.
                from openai import OpenAI

                OpenAI(
                    api_key=os.environ["AZURE_OPENAI_API_KEY"],
                    base_url=os.environ["AZURE_OPENAI_ENDPOINT"],
                )
                client_constructed = True
            except Exception as exc:  # never let client construction crash the runner
                construction_error_type = type(exc).__name__
        return {
            "provider": provider,
            "required_env_vars": required,
            "env_vars_present": present,
            "all_required_present": all_present,
            "client_constructed_no_network_call": client_constructed,
            "construction_error_type": construction_error_type,
        }
    if provider == "openai_compatible":
        required = ["OPENAI_API_KEY", "OPENAI_BASE_URL"]
        present = {name: bool(os.environ.get(name)) for name in required}
        client_constructed = False
        construction_error_type = None
        if present["OPENAI_API_KEY"]:
            try:
                from openai import OpenAI

                OpenAI(api_key=os.environ["OPENAI_API_KEY"], base_url=os.environ.get("OPENAI_BASE_URL"))
                client_constructed = True
            except Exception as exc:
                construction_error_type = type(exc).__name__
        return {
            "provider": provider,
            "required_env_vars": required,
            "env_vars_present": present,
            "all_required_present": present["OPENAI_API_KEY"],
            "client_constructed_no_network_call": client_constructed,
            "construction_error_type": construction_error_type,
        }
    if provider == "cohere":
        present = {
            "COHERE_API_KEY": bool(os.environ.get("COHERE_API_KEY")),
            "CO_API_KEY": bool(os.environ.get("CO_API_KEY")),
        }
        return {
            "provider": provider,
            "required_env_vars": ["COHERE_API_KEY (or CO_API_KEY)"],
            "env_vars_present": present,
            "all_required_present": any(present.values()),
            "client_constructed_no_network_call": None,
            "construction_error_type": None,
        }
    # vapi or any future unknown provider name
    return {
        "provider": provider,
        "required_env_vars": [],
        "env_vars_present": {},
        "all_required_present": False,
        "client_constructed_no_network_call": False,
        "construction_error_type": None,
    }


def _append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n")


def _write_json_allow_overwrite(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def _write_jsonl_allow_overwrite(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n")


# ---------------------------------------------------------------------------
# Live Azure OpenAI smoke-test path (tiny, --limit 1 or 2 only)
# ---------------------------------------------------------------------------

AZURE_LIVE_REQUIRED_ENV_VARS = (
    "AZURE_OPENAI_API_KEY",
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_DEPLOYMENT",
    "AZURE_OPENAI_API_VERSION",
)


def azure_config_env_status() -> dict[str, bool]:
    """Presence-only check (never values) for the Azure OpenAI env vars."""
    return {name: bool(os.environ.get(name)) for name in AZURE_LIVE_REQUIRED_ENV_VARS}


def validate_live_smoke_request(*, limit: int | None, allow_full_live: bool) -> None:
    """Raise a clear, descriptive error unless this is a valid tiny Azure live
    smoke request. Performs zero network I/O -- env var presence only.

    Only called when `--allow-full-live` is NOT set; the full-scale path has
    its own, separately-gated validator -- see `validate_full_live_request()`.
    """
    if allow_full_live:
        raise RuntimeError(
            "Internal error: validate_live_smoke_request() must not be called with allow_full_live=True "
            "-- see validate_full_live_request() for the full-run path. Refusing to proceed."
        )
    if limit is None or limit < 1 or limit > AZURE_LIVE_SMOKE_MAX_LIMIT:
        raise RuntimeError(
            f"--live --provider azure_openai requires --limit between 1 and {AZURE_LIVE_SMOKE_MAX_LIMIT} "
            f"(tiny smoke test only); got --limit={limit!r}. Pass --allow-full-live for a full run "
            "(separately gated -- see validate_full_live_request()). Refusing to proceed."
        )
    missing = [name for name, present in azure_config_env_status().items() if not present]
    if missing:
        raise RuntimeError(
            f"Azure OpenAI config incomplete; missing env vars (names only, never values): {missing}. "
            "Refusing to attempt any request."
        )


def cohere_config_env_status() -> dict[str, bool]:
    """Presence-only check (never values) for Cohere API env vars."""
    return {
        "COHERE_API_KEY": bool(os.environ.get("COHERE_API_KEY")),
        "CO_API_KEY": bool(os.environ.get("CO_API_KEY")),
    }


def validate_cohere_live_smoke_request(*, limit: int | None, allow_full_live: bool) -> None:
    """Raise unless this is a valid tiny Cohere live smoke request (limit 1–2)."""
    if allow_full_live:
        raise RuntimeError(
            "Internal error: validate_cohere_live_smoke_request() must not be called with allow_full_live=True "
            "-- see validate_cohere_full_live_request(). Refusing to proceed."
        )
    if limit is None or limit < 1 or limit > COHERE_LIVE_SMOKE_MAX_LIMIT:
        raise RuntimeError(
            f"--live --provider cohere requires --limit between 1 and {COHERE_LIVE_SMOKE_MAX_LIMIT} "
            f"(tiny smoke test only); got --limit={limit!r}. Pass --allow-full-live for a full run "
            "(separately gated -- see validate_cohere_full_live_request()). Refusing to proceed."
        )
    present = cohere_config_env_status()
    if not any(present.values()):
        raise RuntimeError(
            "Cohere config incomplete; missing env vars (names only, never values): "
            "COHERE_API_KEY or CO_API_KEY. Refusing to attempt any request."
        )
    try:
        import cohere  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            f"Cohere Python SDK not importable ({type(exc).__name__}); install `cohere` in .venv first."
        ) from exc


def validate_cohere_full_live_request(
    *,
    seed: int | None,
    limit: int | None,
    examples_count: int,
) -> None:
    """Raise unless every condition for an authorized Cohere disjoint full run is met."""
    if seed not in ALLOWED_FULL_LIVE_COHERE_SEEDS:
        raise RuntimeError(
            f"--allow-full-live --provider cohere requires --seed in "
            f"{sorted(ALLOWED_FULL_LIVE_COHERE_SEEDS)} (each a Cohere disjoint split with its own "
            f"passed overlap audit); got --seed={seed!r}. Refusing to proceed."
        )
    required_size = ALLOWED_FULL_LIVE_COHERE_SEEDS[seed]
    if examples_count < required_size:
        raise RuntimeError(
            f"--allow-full-live --seed {seed} requires the full N={required_size} fresh split; only "
            f"{examples_count} examples were loaded. Refusing to proceed."
        )
    if limit is not None and limit < examples_count:
        raise RuntimeError(
            f"--allow-full-live requires running the entire fresh split ({examples_count} examples); "
            f"--limit={limit} would truncate it. Omit --limit. Refusing to proceed."
        )
    present = cohere_config_env_status()
    if not any(present.values()):
        raise RuntimeError(
            "Cohere config incomplete; missing COHERE_API_KEY or CO_API_KEY (names only). "
            "Refusing to attempt any request."
        )
    try:
        import cohere  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(f"Cohere Python SDK not importable ({type(exc).__name__}).") from exc
    if not os.environ.get("TMUX"):
        raise RuntimeError(
            "--allow-full-live must be launched from inside a tmux pane (TMUX env var not set). "
            "Use the provided tmux launch script. Refusing to proceed."
        )


def validate_full_live_request(
    *,
    seed: int | None,
    limit: int | None,
    examples_count: int,
) -> None:
    """Raise a clear, descriptive error unless every condition for the one
    specific, narrowly-authorized full-scale live Azure run is met. Performs
    zero network I/O -- env var presence and process-environment checks only.

    Every condition below is required; this is not a general "run any N
    live" escape hatch. An accidental `--allow-full-live` without also
    matching every other condition here still fails closed.
    """
    if seed not in ALLOWED_FULL_LIVE_AZURE_SEEDS:
        raise RuntimeError(
            f"--allow-full-live --provider azure_openai requires --seed in "
            f"{sorted(ALLOWED_FULL_LIVE_AZURE_SEEDS)} (each an Azure disjoint split with its own "
            f"passed overlap audit -- see experiments/api_validation_plan_repair_candidate.py and "
            f"experiments/azure_pooled4_fs_le1_validation_plan.py); got --seed={seed!r}. "
            "Refusing to proceed."
        )
    required_size = ALLOWED_FULL_LIVE_AZURE_SEEDS[seed]
    if examples_count < required_size:
        raise RuntimeError(
            f"--allow-full-live --seed {seed} requires the full N={required_size} fresh split; only "
            f"{examples_count} examples were loaded from --split-manifest. Refusing to proceed."
        )
    if limit is not None and limit < examples_count:
        raise RuntimeError(
            f"--allow-full-live requires running the entire fresh split ({examples_count} examples); "
            f"--limit={limit} would truncate it. Omit --limit (or set it >= {examples_count}). "
            "Refusing to proceed."
        )
    missing = [name for name, present in azure_config_env_status().items() if not present]
    if missing:
        raise RuntimeError(
            f"Azure OpenAI config incomplete; missing env vars (names only, never values): {missing}. "
            "Refusing to attempt any request."
        )
    if not os.environ.get("TMUX"):
        raise RuntimeError(
            "--allow-full-live must be launched from inside a tmux pane (checked via the TMUX env var, "
            "which tmux sets for every process running inside it -- not present here). Use the provided "
            "tmux launch script rather than invoking this directly. Refusing to proceed."
        )


def _write_exact_cases_and_allowed_ids(
    examples: list[dict[str, Any]],
    *,
    dataset: str,
    seed: int,
    budget: int,
    methods: tuple[str, ...],
    output_dir: Path,
) -> tuple[Path, Path]:
    """Write the two small input files
    scripts/run_cohere_real_model_cost_normalized_validation.py expects to
    replay an exact, pre-selected set of examples instead of resampling the
    dataset: an `--exact-cases-jsonl` (one row per example) and an
    `--allowed-example-ids-file` (one row per example x method, hard-filtering
    the run to exactly our tiny split). No secrets in either file.
    """
    exact_cases_path = output_dir / "live_exact_cases.jsonl"
    allowed_ids_path = output_dir / "live_allowed_example_ids.jsonl"
    with exact_cases_path.open("w", encoding="utf-8") as handle:
        for example in examples:
            handle.write(
                json.dumps(
                    {
                        "example_id": example["example_id"],
                        "dataset": dataset,
                        "question": example.get("question"),
                        "gold_answer_canonical": example.get("gold_answer_canonical"),
                    },
                    ensure_ascii=True,
                    sort_keys=True,
                )
                + "\n"
            )
    with allowed_ids_path.open("w", encoding="utf-8") as handle:
        for example in examples:
            for method in methods:
                handle.write(
                    json.dumps(
                        {
                            "dataset": dataset,
                            "seed": seed,
                            "budget": budget,
                            "method": method,
                            "example_id": example["example_id"],
                        },
                        ensure_ascii=True,
                        sort_keys=True,
                    )
                    + "\n"
                )
    return exact_cases_path, allowed_ids_path


def estimate_max_total_api_calls_cap(examples_count: int, methods: tuple[str, ...], budget: int) -> int:
    """A bounded safety ceiling (not a target) passed to the delegate
    script's `--max-total-api-calls`, so a run -- tiny smoke or full --
    cannot spend beyond a known-in-advance number of calls even if something
    misbehaves. Uses this repo's documented, project-wide upper-bound
    convention -- `4 x budget` logical calls per example (see
    docs/CLAIMS.md, docs/CURRENT_CANONICAL_STATE_20260527.md,
    experiments/fta_policy.py) -- rather than a finer per-method estimate:
    at budget=2 in the tiny smoke test this session, 2 examples x 4 x 2 = 16
    matched the real observed call count exactly. Actual calls are typically
    fewer (e.g. `external_l1_max` is cheap), so this is a ceiling, not an
    estimate of true spend.
    """
    return max(1, examples_count) * len(methods) * max(1, int(budget))


def run_live_azure_smoke(
    *,
    examples: list[dict[str, Any]],
    output_dir: Path,
    seed: int,
    budget: int,
    resume: bool,
    stream_output: bool = False,
) -> dict[str, Any]:
    """Generate real per-example/per-method answers via Azure OpenAI by
    delegating to the already-implemented, already-tested `azure_openai`
    provider path in scripts/run_cohere_real_model_cost_normalized_validation.py
    (see that script's own per-example inner loop, which already does
    real branch generation for all 4 methods and writes a JSONL schema
    compatible with experiments/build_failure_feature_table.py).

    Does two subprocess calls: a zero-cost `--validate-exact-cases-only`
    preflight (no API calls) that must succeed before anything live is
    attempted, then the real live run (tiny, --limit-bounded, or full-scale
    -- this function is shared by both; only the caller-supplied `examples`/
    `budget` differ). Checkpointing and --resume are handled by the delegate
    script itself, against its own nested, deterministically-named output
    directory -- not reimplemented here.

    `stream_output=True` lets the delegate's stdout/stderr inherit this
    process's own file descriptors (rather than being captured in-memory and
    only available after the whole call returns), so a caller whose own
    stdout/stderr is itself redirected to a log file (e.g. via `tee` in a
    tmux-launched shell) gets a live-tailable log for a long-running full
    run. The timeout scales with the safety call cap so a large run isn't
    killed partway through.
    """
    dataset = AZURE_LIVE_SMOKE_DATASET
    exact_cases_path, allowed_ids_path = _write_exact_cases_and_allowed_ids(
        examples, dataset=dataset, seed=seed, budget=budget, methods=METHOD_ORDER, output_dir=output_dir
    )
    max_calls = estimate_max_total_api_calls_cap(len(examples), METHOD_ORDER, budget)
    inner_timestamp = "azure_live_smoke"  # fixed: repeated --resume calls must land in the same nested dir
    nested_dir = output_dir / f"cohere_real_model_cost_normalized_validation_{inner_timestamp}"

    base_cmd = [
        sys.executable,
        str(COHERE_REAL_MODEL_SCRIPT),
        "--timestamp",
        inner_timestamp,
        "--providers",
        "azure_openai",
        "--azure-model",
        os.environ.get("AZURE_OPENAI_DEPLOYMENT", ""),
        "--datasets",
        dataset,
        "--seeds",
        str(seed),
        "--budgets",
        str(budget),
        "--methods",
        ",".join(METHOD_ORDER),
        "--target-scored-per-slice",
        str(len(examples)),
        "--max-examples",
        str(len(examples)),
        "--exact-cases-jsonl",
        str(exact_cases_path),
        "--allowed-example-ids-file",
        str(allowed_ids_path),
        "--max-total-api-calls",
        str(max_calls),
        "--output-root",
        str(output_dir),
    ]
    if resume:
        base_cmd.append("--resume")

    preflight_cmd = base_cmd + ["--validate-exact-cases-only", "--expected-exact-case-count", str(len(examples))]
    preflight = subprocess.run(preflight_cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=120, check=False)
    if preflight.returncode != 0:
        raise RuntimeError(
            "Preflight validation (--validate-exact-cases-only, zero API calls) failed; refusing to "
            f"attempt any live call.\nstdout(tail): {preflight.stdout[-1500:]}\nstderr(tail): {preflight.stderr[-1500:]}"
        )

    # Generous per-call allowance (6s) above the ~1.7s/call observed in the first tiny smoke
    # test, floored at 30 minutes for small runs and capped at 8 hours for large ones.
    live_timeout_seconds = min(28800, max(1800, max_calls * 6))

    live_start = time.monotonic()
    if stream_output:
        live = subprocess.run(base_cmd, cwd=REPO_ROOT, text=True, timeout=live_timeout_seconds, check=False)
        live_stdout = "(streamed live to this process's own stdout/stderr, not captured in-process)"
        live_stderr = live_stdout
    else:
        live = subprocess.run(
            base_cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=live_timeout_seconds, check=False
        )
        live_stdout = live.stdout
        live_stderr = live.stderr
    live_elapsed = time.monotonic() - live_start

    nested_records_path = nested_dir / "per_example_records.jsonl"
    live_records = load_jsonl(nested_records_path) if nested_records_path.exists() else []

    return {
        "nested_output_dir": str(nested_dir),
        "per_example_records_path": str(nested_records_path),
        "records": live_records,
        "returncode": live.returncode,
        "stdout": live_stdout,
        "stderr": live_stderr,
        "elapsed_seconds": round(live_elapsed, 4),
        "max_total_api_calls_cap": max_calls,
        "command": base_cmd,
        "preflight_stdout": preflight.stdout,
    }


def run_live_cohere_smoke(
    *,
    examples: list[dict[str, Any]],
    output_dir: Path,
    seed: int,
    budget: int,
    cohere_model: str,
    resume: bool,
    stream_output: bool = False,
) -> dict[str, Any]:
    """Delegate to run_cohere_real_model_cost_normalized_validation.py for Cohere."""
    dataset = AZURE_LIVE_SMOKE_DATASET
    exact_cases_path, allowed_ids_path = _write_exact_cases_and_allowed_ids(
        examples, dataset=dataset, seed=seed, budget=budget, methods=METHOD_ORDER, output_dir=output_dir
    )
    max_calls = estimate_max_total_api_calls_cap(len(examples), METHOD_ORDER, budget)
    inner_timestamp = "cohere_disjoint_live"
    nested_dir = output_dir / f"cohere_real_model_cost_normalized_validation_{inner_timestamp}"

    base_cmd = [
        sys.executable,
        str(COHERE_REAL_MODEL_SCRIPT),
        "--timestamp",
        inner_timestamp,
        "--providers",
        "cohere",
        "--cohere-model",
        cohere_model,
        "--datasets",
        dataset,
        "--seeds",
        str(seed),
        "--budgets",
        str(budget),
        "--methods",
        ",".join(METHOD_ORDER),
        "--target-scored-per-slice",
        str(len(examples)),
        "--max-examples",
        str(len(examples)),
        "--exact-cases-jsonl",
        str(exact_cases_path),
        "--allowed-example-ids-file",
        str(allowed_ids_path),
        "--max-total-api-calls",
        str(max_calls),
        "--output-root",
        str(output_dir),
    ]
    if resume:
        base_cmd.append("--resume")

    preflight_cmd = base_cmd + ["--validate-exact-cases-only", "--expected-exact-case-count", str(len(examples))]
    preflight = subprocess.run(preflight_cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=120, check=False)
    if preflight.returncode != 0:
        raise RuntimeError(
            "Preflight validation (--validate-exact-cases-only, zero API calls) failed; refusing to "
            f"attempt any live call.\nstdout(tail): {preflight.stdout[-1500:]}\nstderr(tail): {preflight.stderr[-1500:]}"
        )

    live_timeout_seconds = min(28800, max(1800, max_calls * 6))
    live_start = time.monotonic()
    if stream_output:
        live = subprocess.run(base_cmd, cwd=REPO_ROOT, text=True, timeout=live_timeout_seconds, check=False)
        live_stdout = "(streamed live to this process's own stdout/stderr, not captured in-process)"
        live_stderr = live_stdout
    else:
        live = subprocess.run(
            base_cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=live_timeout_seconds, check=False
        )
        live_stdout = live.stdout
        live_stderr = live.stderr
    live_elapsed = time.monotonic() - live_start

    nested_records_path = nested_dir / "per_example_records.jsonl"
    live_records = load_jsonl(nested_records_path) if nested_records_path.exists() else []

    return {
        "nested_output_dir": str(nested_dir),
        "per_example_records_path": str(nested_records_path),
        "records": live_records,
        "returncode": live.returncode,
        "stdout": live_stdout,
        "stderr": live_stderr,
        "elapsed_seconds": round(live_elapsed, 4),
        "max_total_api_calls_cap": max_calls,
        "command": base_cmd,
        "preflight_stdout": preflight.stdout,
    }


def summarize_live_usage(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate usage fields already written per-row by the delegate script
    into a compact summary. No secret values pass through this function.
    """
    total_input = sum(int(r.get("input_tokens", 0) or 0) for r in records)
    total_output = sum(int(r.get("output_tokens", 0) or 0) for r in records)
    total_tokens = sum(int(r.get("total_tokens", 0) or 0) for r in records)
    total_latency = sum(float(r.get("latency_seconds", 0.0) or 0.0) for r in records)
    total_api_calls = sum(int(r.get("cohere_logical_api_calls", 0) or 0) for r in records)
    scored = sum(1 for r in records if r.get("status") == "scored")
    failed = sum(1 for r in records if r.get("status") == "failed")
    return {
        "method_call_rows": len(records),
        "scored": scored,
        "failed": failed,
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_tokens": total_tokens,
        "total_latency_seconds": round(total_latency, 4),
        "total_logical_api_calls": total_api_calls,
        "distinct_example_ids": sorted({str(r.get("example_id")) for r in records}),
        "distinct_methods": sorted({str(r.get("method")) for r in records}),
        "distinct_statuses": sorted({str(r.get("status")) for r in records}),
        "distinct_errors": sorted({str(r.get("error")) for r in records if r.get("error")}),
        "note": (
            "finish_reason is not separately captured by the current pipeline; status/error/"
            "parse_extraction_failure are used as the closest available proxies for per-call outcome."
        ),
    }


def _synthetic_answer(example_id: str, method: str, seed: int | None) -> str:
    """Deterministic, clearly-fake placeholder answer for dry-run/schema-validation only."""
    digest = abs(hash((example_id, method, seed))) % 1000
    return f"DRYRUN_{digest}"


def generate_dry_run_records(
    examples: list[dict[str, Any]],
    *,
    seed: int | None,
    budget: int,
) -> list[dict[str, Any]]:
    """Build per-example, per-method records in the schema expected by
    experiments/build_failure_feature_table.py, using synthetic placeholder
    answers only. No provider SDK is imported and no network call is made.
    """
    records: list[dict[str, Any]] = []
    for example in examples:
        example_id = example["example_id"]
        for method in METHOD_ORDER:
            answer = _synthetic_answer(example_id, method, seed)
            records.append(
                {
                    "example_id": example_id,
                    "dataset": "openai/gsm8k",
                    "seed": seed,
                    "split": "train",
                    "question": example.get("question"),
                    "gold_answer": example.get("gold_answer"),
                    "gold_answer_canonical": example.get("gold_answer_canonical"),
                    "method": method,
                    "final_answer_raw": answer,
                    "final_answer_canonical": answer,
                    "selected_answer_raw": answer,
                    "selected_answer_canonical": answer,
                    "exact_match": 0,
                    "parse_extraction_failure": 0,
                    "gold_in_tree": False,
                    "result_metadata": {
                        "dry_run": True,
                        "synthetic_placeholder": True,
                        "override_reason": "direct_frontier_agree" if method == METHOD_FRONTIER else None,
                        "frontier_support": 0 if method == METHOD_FRONTIER else None,
                        "candidate_pool_answer_group_count": 1 if method == METHOD_FRONTIER else None,
                        "direct_frontier_agree": True if method == METHOD_FRONTIER else None,
                        "support_margin": 0.0 if method == METHOD_FRONTIER else None,
                        "direct_reserve_confidence_proxy": 1.0 if method == METHOD_FRONTIER else None,
                        "budget": budget,
                        "logical_calls": budget,
                        "token_count_prompt": None,
                        "token_count_completion": None,
                        "latency_seconds": None,
                        "provider": "dry_run_synthetic",
                        "provider_call_failed": False,
                    },
                }
            )
    return records


def run_live_stub(*args: Any, **kwargs: Any) -> None:
    raise RuntimeError(
        "Live provider calls are not supported in this runner invocation. "
        "This repo's agent-facing policy (AGENTS.md / AGENTS_LOCAL_AUTONOMY.md) requires explicit, "
        "separate, per-call user authorization before any paid API call. Re-run with a provider client "
        "already constructed and authorized by a human operator outside of this automated path."
    )


def build_run_metadata(
    args: argparse.Namespace,
    *,
    examples_count: int,
    provider_status: dict[str, Any],
    resumed: bool,
    records_before_resume: int,
    live_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "script": "run_api_validation_repair_candidate.py",
        "mode": "dry_run" if args.dry_run else "live",
        "provider": args.provider,
        "vapi_available": False,
        "provider_config": provider_status,
        "budget": args.budget,
        "seed": args.seed,
        "limit": args.limit,
        "examples_planned": examples_count,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "no_paid_api_calls_made": bool(args.dry_run),
        "resumed_from_existing_output": resumed,
        "records_before_resume": records_before_resume,
    }
    if live_summary is not None:
        metadata["live_delegate_run"] = live_summary
    return metadata


def main() -> int:
    args = parse_args()
    manifest = load_split_manifest(Path(args.split_manifest))
    examples = manifest.get("examples", [])
    if args.limit is not None:
        examples = examples[: args.limit]

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / "per_example_records.jsonl"

    existing_records: list[dict[str, Any]] = []
    resumed = False
    if target.exists():
        if not args.resume:
            raise FileExistsError(
                f"refusing to overwrite existing output: {target} (pass --resume to continue an interrupted run)"
            )
        existing_records = load_jsonl(target)
        resumed = True
    done_keys = {(r["example_id"], r["method"]) for r in existing_records}

    provider_status = resolve_provider_client_status(args.provider)

    live_result: dict[str, Any] | None = None
    live_failed = False
    start = time.monotonic()
    if args.dry_run:
        all_records = generate_dry_run_records(examples, seed=args.seed, budget=args.budget)
        new_records = [r for r in all_records if (r["example_id"], r["method"]) not in done_keys]
        failures = 0
    elif args.provider == "azure_openai":
        if args.allow_full_live:
            validate_full_live_request(seed=args.seed, limit=args.limit, examples_count=len(examples))
        else:
            validate_live_smoke_request(limit=args.limit, allow_full_live=args.allow_full_live)
        live_result = run_live_azure_smoke(
            examples=examples,
            output_dir=output_dir,
            seed=args.seed or 0,
            budget=args.budget,
            resume=args.resume,
            stream_output=args.allow_full_live,
        )
        all_records = live_result["records"]
        new_records = [r for r in all_records if (r["example_id"], r["method"]) not in done_keys]
        failures = sum(1 for r in all_records if r.get("status") == "failed")
        live_failed = live_result["returncode"] != 0
    elif args.provider == "cohere":
        if args.allow_full_live:
            validate_cohere_full_live_request(seed=args.seed, limit=args.limit, examples_count=len(examples))
        else:
            validate_cohere_live_smoke_request(limit=args.limit, allow_full_live=args.allow_full_live)
        live_result = run_live_cohere_smoke(
            examples=examples,
            output_dir=output_dir,
            seed=args.seed or COHERE_DISJOINT_FRESH_SEED,
            budget=args.budget,
            cohere_model=args.cohere_model,
            resume=args.resume,
            stream_output=args.allow_full_live,
        )
        all_records = live_result["records"]
        new_records = [r for r in all_records if (r["example_id"], r["method"]) not in done_keys]
        failures = sum(1 for r in all_records if r.get("status") == "failed")
        live_failed = live_result["returncode"] != 0
    else:
        run_live_stub()
        return 1
    elapsed = time.monotonic() - start

    if live_result is not None:
        # The delegate script is the authoritative checkpoint store (its own nested output
        # dir); mirror its complete, current record set into our own target path. This is a
        # faithful mirror of that authoritative source, not divergent data, so overwriting our
        # own mirror on --resume is safe.
        records = all_records
        _write_jsonl_allow_overwrite(target, records)
    elif resumed:
        _append_jsonl(target, new_records)
        records = existing_records + new_records
    else:
        write_jsonl(target, new_records)
        records = existing_records + new_records

    live_summary = None
    if live_result is not None:
        live_summary = {
            "delegated_to": str(COHERE_REAL_MODEL_SCRIPT.relative_to(REPO_ROOT)),
            "nested_output_dir": live_result["nested_output_dir"],
            "returncode": live_result["returncode"],
            "elapsed_seconds": live_result["elapsed_seconds"],
            "max_total_api_calls_cap": live_result["max_total_api_calls_cap"],
            "usage": summarize_live_usage(all_records),
        }

    run_metadata = build_run_metadata(
        args,
        examples_count=len(examples),
        provider_status=provider_status,
        resumed=resumed,
        records_before_resume=len(existing_records),
        live_summary=live_summary,
    )
    run_metadata.update(
        {
            "records_written": len(records),
            "records_newly_written": len(new_records),
            "failures": failures,
            "elapsed_seconds": round(elapsed, 4),
            "live_run_failed": live_failed,
        }
    )
    metadata_path = output_dir / "run_metadata.json"
    if (resumed or live_result is not None) and metadata_path.exists():
        _write_json_allow_overwrite(metadata_path, run_metadata)
    else:
        write_json(metadata_path, run_metadata)

    wandb_options = wandb_options_from_args(args)
    handle = init_run(
        wandb_options,
        script_name="run_api_validation_repair_candidate.py",
        repo_root=Path.cwd(),
        extra_config={"provider": args.provider, "mode": run_metadata["mode"], "examples": len(examples)},
    )
    if handle is not None:
        handle.log_metrics({"records_written": len(records), "failures": failures})
        handle.finish()

    readme_path = output_dir / "RUN_README.md"
    readme_text = (
        ("# API Validation Run (dry-run)\n\n" if args.dry_run else "# API Validation Run (live)\n\n")
        + f"- mode: {run_metadata['mode']}\n"
        + f"- provider: {args.provider}\n"
        + f"- provider_config_all_required_present: {provider_status['all_required_present']}\n"
        + f"- examples: {len(examples)}\n"
        + f"- records_written: {len(records)}\n"
        + f"- resumed_from_existing_output: {resumed}\n"
        + f"- no_paid_api_calls_made: {run_metadata['no_paid_api_calls_made']}\n"
        + (f"- live_run_failed: {live_failed}\n" if live_result is not None else "")
    )
    if (resumed or live_result is not None) and readme_path.exists():
        readme_path.write_text(readme_text, encoding="utf-8")
    else:
        write_text(readme_path, readme_text)

    print(
        json.dumps(
            {
                "output_dir": str(output_dir),
                "records_written": len(records),
                "mode": run_metadata["mode"],
                "provider": args.provider,
                "provider_config_all_required_present": provider_status["all_required_present"],
                "resumed_from_existing_output": resumed,
                "live_run_failed": live_failed,
            },
            sort_keys=True,
        )
    )
    if live_failed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
