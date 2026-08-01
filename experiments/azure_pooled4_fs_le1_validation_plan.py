"""Prepare (but do not launch) a fresh Azure OpenAI disjoint validation for
`pooled4_fs_le1_notie_fta_v2_candidate` -- the same candidate already validated
fresh on Cohere seed 83
(outputs/api_validation_live/cohere_pooled4_fs_le1_notie_20260709T024735Z/,
post-hoc dual-candidate replay in
outputs/failure_analysis/cohere_seed83_dual_candidate_posthoc_20260709T143822Z/).

Zero API calls. Reuses the generic split-selection / call-plan / environment-check
helpers already used to build the Cohere disjoint plans (experiments
.api_validation_plan_repair_candidate, experiments.cohere_disjoint_validation_plan);
only the provider, forbidden-seed list, and Azure-specific artifact set differ.
`cohere_known_used_sources()` auto-discovers every prior
outputs/api_validation_live/**/per_example_records.jsonl and
outputs/api_validation_smoke/**/per_example_records.jsonl (Cohere seeds
31/41/53/61/71/83 *and* Azure seed 97), so disjointness is checked against the
full cross-provider history, not just Azure's own prior seed.

Writes a split-plan directory (outputs/api_validation_plans/azure_pooled4_fs_le1_notie_<ts>/)
with the split audit, an allowed-IDs file, a call-plan, an evaluator-readiness note,
a safety-gate audit (documents current gate behavior + a *proposed* minimal diff --
does not edit the gate itself), and an intentionally-blocked tmux launch script.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from experiments.api_validation_plan_repair_candidate import (
    DEFAULT_BUDGET,
    check_environment,
    estimate_call_plan,
    load_gsm8k_train_split_offline,
    select_fresh_split,
)
from experiments.cohere_disjoint_validation_plan import (
    _normalize_question_text,
    cohere_known_used_sources,
    load_used_examples_extended,
)
from experiments.failure_analysis_common import write_csv, write_json, write_text
from experiments.freeze_pooled4_fs_le1_notie_candidate import CANDIDATE_NAME
from experiments.run_api_validation_repair_candidate import (
    AZURE_LIVE_REQUIRED_ENV_VARS,
    FRESH_VALIDATED_SPLIT_SEED,
    FRESH_VALIDATED_SPLIT_SIZE,
    METHOD_ORDER,
)
from experiments.wandb_logging import git_commit_hash

REPO_ROOT = Path(__file__).resolve().parents[1]
DATASET = "openai/gsm8k"
AZURE_FRESH_SEED_DEFAULT = 103
AZURE_FRESH_SEED_ALTERNATE = 107
AZURE_FRESH_SIZE = 300
# Every GSM8K sample-selection seed used by ANY provider so far. All providers draw
# from the same openai/gsm8k train pool, so this is checked cross-provider, mirroring
# experiments/cohere_pooled4_fs_le1_validation_plan.py::FORBIDDEN_FRESH_SEEDS (which
# likewise includes Azure's seed 97 alongside Cohere seeds).
FORBIDDEN_FRESH_SEEDS = frozenset({31, 41, 53, 61, 71, 83, 97})


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output-dir", default="")
    p.add_argument("--summary-dir", default="")
    p.add_argument("--fresh-seed", type=int, default=AZURE_FRESH_SEED_DEFAULT)
    p.add_argument("--size", type=int, default=AZURE_FRESH_SIZE)
    p.add_argument("--budget", type=int, default=DEFAULT_BUDGET)
    return p.parse_args()


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def verify_split_azure(*, split: dict[str, Any], used: dict[str, Any], gsm8k_rows: list[dict[str, Any]]) -> dict[str, Any]:
    used_norm_texts: set[str] = set()
    gsm8k_by_id = {r["example_id"]: r for r in gsm8k_rows}
    for eid in used["used_example_ids"]:
        row = gsm8k_by_id.get(eid)
        if row and row.get("question"):
            used_norm_texts.add(_normalize_question_text(row["question"]))
    selected_norm_overlap = [
        ex["example_id"]
        for ex in split["examples"]
        if ex.get("question") and _normalize_question_text(ex["question"]) in used_norm_texts
    ]
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


def build_split(fresh_seed: int, size: int) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    sources = cohere_known_used_sources()
    used = load_used_examples_extended(sources)
    gsm8k_rows = load_gsm8k_train_split_offline()
    split = select_fresh_split(fresh_seed=fresh_seed, size=size, used=used, gsm8k_rows=gsm8k_rows)
    verification = verify_split_azure(split=split, used=used, gsm8k_rows=gsm8k_rows)
    split["verification"] = verification
    return split, used, gsm8k_rows


def render_split_audit(*, used: dict[str, Any], split: dict[str, Any], verification: dict[str, Any]) -> str:
    lines = [
        "# Azure Fresh Split Audit",
        "",
        f"- fresh_seed: **{split['fresh_seed']}**",
        f"- size: **{split['size']}**",
        f"- forbidden_prior_seeds (cross-provider): {sorted(FORBIDDEN_FRESH_SEEDS)}",
        f"- total_unique_used_examples_prior (cross-provider): **{used['total_unique_used']}**",
        "",
        "## Overlap checks",
        "",
        f"- example_id_overlap_count: **{verification['example_id_overlap_count']}**",
        f"- question_hash_overlap_count: **{verification['question_hash_overlap_count']}**",
        f"- normalized_question_text_overlap_count: **{verification['normalized_question_text_overlap_count']}**",
        f"- fresh_seed_forbidden_overlap: **{verification['fresh_seed_forbidden_overlap']}**",
        f"- non_overlapping (all checks): **{verification['non_overlapping']}**",
        "",
        "## Used sources (auto-discovered, cross-provider)",
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
            "Gold labels here are for **post-hoc evaluation only**; never used as a runtime selector feature.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def write_allowed_ids(path: Path, *, examples: list[dict[str, Any]], fresh_seed: int, budget: int) -> int:
    n = 0
    with path.open("w", encoding="utf-8") as fh:
        for ex in examples:
            for method in METHOD_ORDER:
                fh.write(
                    json.dumps(
                        {
                            "example_id": ex["example_id"],
                            "method": method,
                            "dataset": DATASET,
                            "seed": fresh_seed,
                            "budget": budget,
                        },
                        sort_keys=True,
                    )
                    + "\n"
                )
                n += 1
    return n


def render_call_plan_summary(*, call_plan: dict[str, Any], split: dict[str, Any], budget: int) -> str:
    lines = [
        "# Azure Fresh Call Plan Summary",
        "",
        f"- Provider: **azure_openai**",
        f"- Candidate under test: `{CANDIDATE_NAME}` (exploratory; already validated fresh on Cohere seed 83 -- "
        "this run would be its Azure confirmatory split per "
        "experiments/freeze_pooled4_fs_le1_notie_candidate.py's fresh-validation plan).",
        f"- Dataset: `{DATASET}`, train split",
        f"- Fresh seed: **{split['fresh_seed']}**, N=**{split['size']}**, budget B=**{budget}**",
        "",
        "## Logical call accounting",
        "",
    ]
    for method, count in call_plan["logical_calls_per_method"].items():
        lines.append(f"- `{method}`: {count} logical calls (upper bound)")
    lines.append(
        f"- **total logical calls: {call_plan['total_logical_calls']}** "
        f"({call_plan['logical_calls_per_example']} per example x {split['size']} examples)"
    )
    lines.extend(
        [
            "",
            "## Reference: observed vs upper bound on the prior Azure seed-97 run",
            "",
            "- outputs/api_validation_live/azure_openai_seed97_repair_candidate_20260708T173734Z/: "
            "1200 records written at N=300, budget=6 (matches this plan's shape 1:1).",
            "- Actual logical/token counts for *this* seed will only be known after the tiny "
            "smoke test; do not treat the upper bound above as a cost estimate.",
            "",
            "## Post-hoc candidates to evaluate from ONE generation run (no extra API calls)",
            "",
            f"- `{CANDIDATE_NAME}` (fs<=1, the pre-registered/validated definition)",
            "- `pooled4_fs0_notie_risk_controlled_candidate` (fs0, conservative)",
            "- `pooled4_fs1_only_diagnostic` (fs==1 exact slice)",
            "- Pooled-4 standalone, External-3 standalone",
            "- frontier / L1 / S1 / TALE single-method baselines",
            "- canonical FTA (baseline, unchanged)",
            "",
            "All ten are deterministic functions of the same 4 raw method answers + gold; "
            "see AZURE_DUAL_CANDIDATE_EVALUATOR_READY.md.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def render_evaluator_ready(*, split_manifest_path: Path) -> str:
    return f"""# Azure Dual-Candidate Evaluator Readiness

**Status: ready. No new code required.**

## What already exists

`experiments/cohere_seed83_dual_candidate_posthoc.py` (built for the Cohere seed-83
post-hoc replay in outputs/failure_analysis/cohere_seed83_dual_candidate_posthoc_20260709T143822Z/)
is **provider-agnostic** despite its name:

- Its only input is `--records-path <run_dir>/raw_records/per_example_records.jsonl`,
  a CLI argument with no hardcoded provider assumption.
- It builds wide feature rows via `experiments.build_failure_feature_table
  .build_feature_rows_from_specs`, which reads generic fields
  (`example_id`, `method`, `final_answer_canonical`, `gold_answer_canonical`, ...)
  written identically by the shared runner
  (`experiments/run_api_validation_repair_candidate.py`) regardless of
  `--provider cohere` or `--provider azure_openai` -- confirmed by inspecting both
  the Cohere seed-83 and Azure seed-97 `per_example_records.jsonl` schemas
  (same field set: `example_id`, `method`, `final_answer_canonical`,
  `gold_answer_canonical`, `frontier_support`, etc.).
- It evaluates all 10 requested candidates (canonical FTA, fs<=1, fs0, fs1-only
  diagnostic, Pooled-4 standalone, External-3 standalone, frontier/L1/S1/TALE)
  by reusing the frozen `decision_pooled4_fs_le1_notie(row, max_fs=...)` function
  from `experiments.freeze_pooled4_fs_le1_notie_candidate` (fs<=1: `max_fs=1`, fs0:
  `max_fs=0`, fs1-only: the set-difference) and the shared
  `build_pooled4_fs_le1_validation_specs()` baseline specs -- no selector logic is
  duplicated or modified for Azure.

## Command to run later (offline, after Azure generation completes -- do not run now)

```bash
./.venv/bin/python -m experiments.cohere_seed83_dual_candidate_posthoc \\
  --records-path <AZURE_RUN_DIR>/raw_records/per_example_records.jsonl \\
  --output-dir outputs/failure_analysis/azure_seed{{FRESH_SEED}}_dual_candidate_posthoc_<timestamp>
```

Replace `<AZURE_RUN_DIR>` with the completed live run's directory and
`{{FRESH_SEED}}` with the seed actually used (see `{split_manifest_path.name}` for the
audited seed and split this plan prepared).

## Verification performed now (offline, zero API calls)

- Confirmed the script's `--records-path` argument is not hardcoded to any Cohere
  path -- it is a plain `argparse` default that any caller can override.
- Confirmed the 300-row assertion (`if len(feature_rows) != 300: raise ...`) matches
  this plan's N=300, so it will not spuriously reject a completed Azure run of the
  same size.
- Did not run the evaluator against any data (there is no Azure run to evaluate yet).

## What is NOT ready / out of scope here

- The live Azure generation itself (blocked by design -- see
  `launch_full_azure_pooled4_fs_le1_validation_tmux.sh` and
  `AZURE_SAFETY_GATE_AUDIT.md`).
- Any manuscript or selector change based on a future Azure result.
"""


def render_safety_gate_audit(*, proposed_seed: int, proposed_size: int) -> str:
    return f"""# Azure Safety Gate Audit

Inspected: `experiments/run_api_validation_repair_candidate.py`
(`validate_full_live_request()`, the function gating `--live --provider azure_openai
--allow-full-live`), read-only. No code was changed by this audit.

## Current gate behavior (as of this audit)

```python
FRESH_VALIDATED_SPLIT_SEED = 97
FRESH_VALIDATED_SPLIT_SIZE = 300

def validate_full_live_request(*, seed, limit, examples_count) -> None:
    if seed != FRESH_VALIDATED_SPLIT_SEED:
        raise RuntimeError(...)  # only seed 97 is ever accepted
    if examples_count < FRESH_VALIDATED_SPLIT_SIZE:
        raise RuntimeError(...)  # rejects truncated N<300
    if limit is not None and limit < examples_count:
        raise RuntimeError(...)  # rejects --limit truncation of a full run
    missing = [name for name, present in azure_config_env_status().items() if not present]
    if missing:
        raise RuntimeError(...)  # rejects if Azure env vars are not all present
    if not os.environ.get("TMUX"):
        raise RuntimeError(...)  # rejects if not launched inside tmux
```

- `validate_full_live_request()` is only ever called from the `args.provider ==
  "azure_openai"` branch of the CLI dispatcher (`experiments
  /run_api_validation_repair_candidate.py`, `elif args.provider == "azure_openai":`
  block) -- **a non-Azure provider cannot reach this gate at all** when the Azure
  launcher script is used, since the launch script hardcodes `--provider
  azure_openai`. This requirement is already satisfied structurally.
- Truncated N<300 is already rejected (`examples_count < FRESH_VALIDATED_SPLIT_SIZE`
  and the `--limit` check).
- tmux-only launch is already enforced (`TMUX` env var check), matching the
  project's long-running-job policy.
- All of the above is preserved for seed 97 verbatim below.

## Gap found

**The gate currently allows exactly one Azure seed (97) and no others.** It is a
scalar equality check (`seed != FRESH_VALIDATED_SPLIT_SEED`), not an allowlist. This
plan's audited fresh seed ({proposed_seed}) would currently be **rejected** by
`validate_full_live_request()` with `"--allow-full-live requires --seed 97"`, even
though `AZURE_FRESH_SPLIT_AUDIT.md` in this same directory shows it passed every
overlap check.

This is the *same* situation Cohere's gate was in before seed 83 was added -- Cohere
already solved it with an allowlist dict (`ALLOWED_FULL_LIVE_COHERE_SEEDS: dict[int,
int]`, mapping each authorized seed to its required exact size), added only after
that seed's own overlap audit passed and was reviewed. This audit proposes the
Azure gate follow the identical, already-precedented pattern.

## Proposed minimal change (NOT applied -- for human review only)

```python
# In experiments/run_api_validation_repair_candidate.py, replacing the single-seed
# constants with an allowlist dict, mirroring ALLOWED_FULL_LIVE_COHERE_SEEDS exactly:

# Additional Azure fresh splits explicitly authorized for --allow-full-live, beyond
# the original seed-97 disjoint split. Each entry must have its own passed overlap
# audit against every prior cross-provider seed before being added here.
# seed={proposed_seed} -> pooled4_fs_le1_notie split, audited non-overlapping against
# seeds {sorted(FORBIDDEN_FRESH_SEEDS - {proposed_seed})} in
# outputs/api_validation_plans/azure_pooled4_fs_le1_notie_<ts>/AZURE_FRESH_SPLIT_AUDIT.md
# (pending explicit human authorization).
ALLOWED_FULL_LIVE_AZURE_SEEDS: dict[int, int] = {{
    FRESH_VALIDATED_SPLIT_SEED: FRESH_VALIDATED_SPLIT_SIZE,  # 97: 300 (unchanged)
    {proposed_seed}: {proposed_size},
}}

def validate_full_live_request(*, seed, limit, examples_count) -> None:
    if seed not in ALLOWED_FULL_LIVE_AZURE_SEEDS:
        raise RuntimeError(
            f"--allow-full-live --provider azure_openai requires --seed in "
            f"{{sorted(ALLOWED_FULL_LIVE_AZURE_SEEDS)}} (each an Azure disjoint split "
            f"with its own passed overlap audit); got --seed={{seed!r}}. Refusing to proceed."
        )
    required_size = ALLOWED_FULL_LIVE_AZURE_SEEDS[seed]
    if examples_count < required_size:
        raise RuntimeError(...)  # unchanged logic, now keyed by required_size
    # remainder (limit/env/tmux checks) unchanged
```

This is a pure generalization: seed 97 keeps its exact existing required size
(300) and every other check (env vars, tmux, truncation) is untouched, so **all
existing seed-97 behavior is preserved byte-for-byte**. The only new capability is
accepting a second, independently-audited seed.

## Does the gate need to change before this plan can be used?

**Yes** -- as it stands today, even a fully authorized human could not launch this
plan's seed ({proposed_seed}) through `--allow-full-live`; the gate would refuse it
regardless of authorization, because it checks a hardcoded single seed, not an
audit result. The code change above (or an equivalent one) must land, reviewed and
merged normally, **before** any future launch attempt -- this audit does not apply
it.

## What this audit does NOT do

- Does not edit `experiments/run_api_validation_repair_candidate.py`.
- Does not launch or authorize any API call.
- Does not add seed {proposed_seed} to the real `ALLOWED_FULL_LIVE_AZURE_SEEDS`-equivalent
  (which does not exist yet in the codebase).
"""


def render_launch_script(
    *,
    plan_dir: Path,
    plan_timestamp: str,
    split_manifest_path: Path,
    split: dict[str, Any],
    budget: int,
) -> str:
    session = f"azure_pooled4_full_{plan_timestamp}"
    run_dir_placeholder = f"{REPO_ROOT}/outputs/api_validation_live/azure_pooled4_fs_le1_notie_{plan_timestamp}"
    python_bin = "./.venv/bin/python"
    fresh_seed = split["fresh_seed"]
    size = split["size"]
    return f"""#!/usr/bin/env bash
# FULL N={size} AZURE POOLED-4 FS<=1 NO-TIE VALIDATION -- DRAFT, INTENTIONALLY BLOCKED.
#
# Candidate: {CANDIDATE_NAME}
# Provider: azure_openai. Fresh seed: {fresh_seed} (see AZURE_FRESH_SPLIT_AUDIT.md
# in this directory for the overlap audit). N={size}, budget={budget}.
#
# This script does NOT launch anything by default. It requires:
#   1. REQUIRE_EXPLICIT_AZURE_FULL_RUN_AUTH=1 set by a human (not by any script/agent).
#   2. The safety-gate code change proposed in AZURE_SAFETY_GATE_AUDIT.md to have
#      actually landed in experiments/run_api_validation_repair_candidate.py
#      (validate_full_live_request() currently only accepts seed {FRESH_VALIDATED_SPLIT_SEED}
#      and will reject seed {fresh_seed} with a clear error until that change is merged).
#   3. Launch from inside a tmux pane.
set -euo pipefail

cd "{REPO_ROOT}"

if [ "${{REQUIRE_EXPLICIT_AZURE_FULL_RUN_AUTH:-0}}" != "1" ]; then
  echo "Refusing to proceed: REQUIRE_EXPLICIT_AZURE_FULL_RUN_AUTH is not set to 1." >&2
  echo "This is a DRAFT launch script. Set the variable explicitly (never inside a script" >&2
  echo "or agent invocation) only after: (a) reviewing AZURE_SAFETY_GATE_AUDIT.md and" >&2
  echo "(b) the proposed gate change has actually been merged, AND (c) you have separately" >&2
  echo "decided to spend the API budget. See AZURE_LAUNCH_INSTRUCTIONS.md." >&2
  exit 1
fi

if [ -z "${{TMUX:-}}" ]; then
  echo "This script must be launched from inside a tmux pane (project long-running-job policy," >&2
  echo "also enforced again at the Python layer by validate_full_live_request())." >&2
  exit 1
fi

RUN_DIR="{run_dir_placeholder}"
SPLIT_MANIFEST="{split_manifest_path}"
mkdir -p "$RUN_DIR"

# --- Source approved env files if present (never print their contents/values).
for f in "$HOME/.api_tokens" "$HOME/.cloudrift_env" "$HOME/.wandb_env" "$HOME/.profile"; do
  if [ -f "$f" ]; then
    # shellcheck disable=SC1090
    source "$f"
  fi
done

{{
  echo "# Sanitized environment status (presence-only; no values printed)"
  echo "generated_utc: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  for v in AZURE_OPENAI_API_KEY AZURE_OPENAI_ENDPOINT AZURE_OPENAI_DEPLOYMENT AZURE_OPENAI_API_VERSION WANDB_API_KEY WANDB_PROJECT; do
    if [ -n "${{!v:-}}" ]; then echo "$v: set"; else echo "$v: NOT set"; fi
  done
  echo "tmux_pane: ${{TMUX:-unknown}}"
}} > "$RUN_DIR/environment_sanitized.txt"

cat > "$RUN_DIR/LIVE_RUN_MANIFEST.json" <<JSON
{{
  "authorized_marker": "REQUIRE_EXPLICIT_AZURE_FULL_RUN_AUTH=1",
  "provider": "azure_openai",
  "candidate": "{CANDIDATE_NAME}",
  "seed": {fresh_seed},
  "size": {size},
  "budget": {budget},
  "split_manifest": "$SPLIT_MANIFEST",
  "launched_utc": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "status": "launched"
}}
JSON

echo "=== Step 1/3: generation (frontier, L1, S1, TALE via Azure OpenAI) ===" | tee -a "$RUN_DIR/full_validation.log"

{python_bin} -m experiments.run_api_validation_repair_candidate \\
  --split-manifest "$SPLIT_MANIFEST" \\
  --output-dir "$RUN_DIR/raw_records" \\
  --live --provider azure_openai --allow-full-live --seed {fresh_seed} --budget {budget} --resume \\
  --wandb --wandb-project "${{WANDB_PROJECT:-frontier-allocation}}" --wandb-run-name "azure_pooled4_full_{plan_timestamp}" \\
  2>&1 | tee -a "$RUN_DIR/full_validation.log"

echo "=== Step 2/3: post-hoc evaluation (fs<=1 pre-registered candidate) ===" | tee -a "$RUN_DIR/full_validation.log"

{python_bin} -m experiments.evaluate_api_validation_repair_candidate \\
  --input "$RUN_DIR/raw_records/per_example_records.jsonl" \\
  --output-dir "$RUN_DIR/evaluation" \\
  --validation-suite pooled4_fs_le1 \\
  --source-id "azure_pooled4_fs_le1_notie_full_n{size}_{plan_timestamp}" \\
  2>&1 | tee -a "$RUN_DIR/full_validation.log"

echo "=== Step 3/3: offline dual-candidate post-hoc (fs<=1 / fs0 / fs1-only), zero extra API calls ===" | tee -a "$RUN_DIR/full_validation.log"

{python_bin} -m experiments.cohere_seed83_dual_candidate_posthoc \\
  --records-path "$RUN_DIR/raw_records/per_example_records.jsonl" \\
  --output-dir "{REPO_ROOT}/outputs/failure_analysis/azure_seed{fresh_seed}_dual_candidate_posthoc_{plan_timestamp}" \\
  2>&1 | tee -a "$RUN_DIR/full_validation.log"

echo "=== DONE: full Azure pooled4_fs_le1_notie validation complete ===" | tee -a "$RUN_DIR/full_validation.log"
"""


def render_launch_instructions(*, plan_dir: Path, launch_script_path: Path, proposed_seed: int) -> str:
    return f"""# Azure Launch Instructions (for later, human-authorized use only)

This is documentation only. **Nothing is launched by reading or having this file.**

## Preconditions (all required)

1. Read `AZURE_FRESH_SPLIT_AUDIT.md` and confirm `non_overlapping: True`.
2. Read `AZURE_SAFETY_GATE_AUDIT.md`. The proposed gate change must actually be
   merged into `experiments/run_api_validation_repair_candidate.py` first --
   today the gate hard-rejects any seed other than {FRESH_VALIDATED_SPLIT_SEED}.
3. Explicit human decision to spend the estimated API budget (see
   `AZURE_FRESH_CALL_PLAN_SUMMARY.md`).
4. A tiny (<=2-example) Azure smoke test should be run and reviewed first,
   mirroring the Cohere precedent (`launch_tiny_cohere_pooled4_fs_le1_smoke_tmux.sh`
   in `outputs/api_validation_plans/cohere_pooled4_fs_le1_notie_20260709T020758Z/`)
   -- not included in this prep pass; write a parallel tiny-smoke script first if
   you want that step, before touching the full launch script.

## To launch later (only after all preconditions above are met)

```bash
# Inside a tmux pane, from the repo root, after sourcing ~/.api_tokens:
export REQUIRE_EXPLICIT_AZURE_FULL_RUN_AUTH=1   # set this yourself; never let a script set it
{launch_script_path}
```

The script exits 1 immediately if `REQUIRE_EXPLICIT_AZURE_FULL_RUN_AUTH` is unset,
or if not run inside tmux, regardless of the env var.

## What the script does when authorized

1. Generates frontier/L1/S1/TALE answers for all {AZURE_FRESH_SIZE} examples via Azure OpenAI.
2. Runs the standard `pooled4_fs_le1` post-hoc evaluator (scores the pre-registered
   `{CANDIDATE_NAME}` definition only).
3. Runs the dual-candidate offline post-hoc script (fs<=1 / fs0 / fs1-only / Pooled-4
   standalone / External-3 standalone / frontier/L1/S1/TALE / FTA) against the SAME
   generated records -- zero additional API calls for steps 2-3.

## After it completes

- Do **not** promote any candidate or change manuscript claims automatically --
  that remains a separate, explicit decision regardless of outcome.
- Compare against the Cohere seed-83 result
  (`outputs/failure_analysis/cohere_seed83_dual_candidate_posthoc_20260709T143822Z/`)
  before drawing any cross-provider conclusion.
"""


def main() -> int:
    args = parse_args()
    if args.fresh_seed in FORBIDDEN_FRESH_SEEDS:
        raise ValueError(f"fresh_seed {args.fresh_seed} forbidden: {sorted(FORBIDDEN_FRESH_SEEDS)}")

    timestamp = _timestamp()
    plan_dir = Path(args.output_dir) if args.output_dir else REPO_ROOT / "outputs" / "api_validation_plans" / f"azure_pooled4_fs_le1_notie_{timestamp}"
    plan_dir.mkdir(parents=True, exist_ok=True)
    plan_timestamp = plan_dir.name.split("_")[-1]

    split, used, gsm8k_rows = build_split(args.fresh_seed, args.size)
    verification = split["verification"]
    if not verification["non_overlapping"]:
        raise RuntimeError(f"split failed overlap verification: {verification}")

    env = check_environment()
    call_plan = estimate_call_plan(split["size"], budget=args.budget)

    manifest = {
        "provider": "azure_openai",
        "dataset": DATASET,
        "split": "train",
        "fresh_seed": split["fresh_seed"],
        "fresh_seed_alternate_if_needed": AZURE_FRESH_SEED_ALTERNATE,
        "size": split["size"],
        "budget": args.budget,
        "candidate_rule": CANDIDATE_NAME,
        "candidate_rule_status": "exploratory_frozen_not_promoted_validated_fresh_on_cohere_seed83",
        "canonical_selector_unchanged": True,
        "forbidden_prior_seeds_cross_provider": sorted(FORBIDDEN_FRESH_SEEDS),
        "verification": verification,
        "examples": split["examples"],
        "used_sources_summary": used["per_source"],
        "used_examples_total": used["total_unique_used"],
        "environment_check": env,
        "call_plan": call_plan,
        "git_commit": git_commit_hash(REPO_ROOT),
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }

    split_manifest_path = plan_dir / "AZURE_FRESH_SPLIT_AUDIT.json"
    write_json(split_manifest_path, manifest)
    write_text(plan_dir / "AZURE_FRESH_SPLIT_AUDIT.md", render_split_audit(used=used, split=split, verification=verification))

    allowed_ids_path = plan_dir / "AZURE_FRESH_ALLOWED_IDS.jsonl"
    n_allowed = write_allowed_ids(allowed_ids_path, examples=split["examples"], fresh_seed=split["fresh_seed"], budget=args.budget)

    call_plan_rows = [
        {"method": method, "logical_calls_upper_bound": count, "n_examples": split["size"], "budget_per_method": args.budget}
        for method, count in call_plan["logical_calls_per_method"].items()
    ]
    call_plan_rows.append(
        {"method": "TOTAL", "logical_calls_upper_bound": call_plan["total_logical_calls"], "n_examples": split["size"], "budget_per_method": args.budget}
    )
    write_csv(plan_dir / "AZURE_FRESH_CALL_PLAN.csv", call_plan_rows, list(call_plan_rows[0].keys()))
    write_text(plan_dir / "AZURE_FRESH_CALL_PLAN_SUMMARY.md", render_call_plan_summary(call_plan=call_plan, split=split, budget=args.budget))

    write_text(plan_dir / "AZURE_DUAL_CANDIDATE_EVALUATOR_READY.md", render_evaluator_ready(split_manifest_path=split_manifest_path))
    write_text(plan_dir / "AZURE_SAFETY_GATE_AUDIT.md", render_safety_gate_audit(proposed_seed=split["fresh_seed"], proposed_size=split["size"]))

    launch_script_path = plan_dir / "launch_full_azure_pooled4_fs_le1_validation_tmux.sh"
    write_text(launch_script_path, render_launch_script(plan_dir=plan_dir, plan_timestamp=plan_timestamp, split_manifest_path=split_manifest_path, split=split, budget=args.budget))
    launch_script_path.chmod(0o755)
    write_text(plan_dir / "AZURE_LAUNCH_INSTRUCTIONS.md", render_launch_instructions(plan_dir=plan_dir, launch_script_path=launch_script_path, proposed_seed=split["fresh_seed"]))

    result = {
        "plan_dir": str(plan_dir),
        "fresh_seed": split["fresh_seed"],
        "size": split["size"],
        "non_overlapping": verification["non_overlapping"],
        "azure_env_configured": env["azure_openai"]["configured"],
        "tmux_available": env["tmux"]["available"],
        "n_allowed_id_rows": n_allowed,
        "total_logical_calls_upper_bound": call_plan["total_logical_calls"],
        "launch_script": str(launch_script_path),
    }
    print(json.dumps(result, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
