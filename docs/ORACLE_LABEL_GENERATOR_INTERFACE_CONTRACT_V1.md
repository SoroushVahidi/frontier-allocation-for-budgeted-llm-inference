# Oracle-label heavy generator interface contract (v1)

## Purpose

This note defines the **stable interface contract** for the future heavy oracle-label generator used by the first stop-vs-act oracle-label pilot.

It exists to prevent implementation drift across HPC environments.

This is an interface/specification document, **not** evidence that heavy oracle generation has already run.

---

## 1) What the heavy generator is expected to do

Given:
- the pilot config,
- a deterministic pilot state manifest,
- and output paths,

the generator must compute paired ACT-vs-STOP teacher estimates for each selected state, then emit:
1. row-level oracle labels (`oracle_stop_vs_act_labels.jsonl`),
2. run-level generation manifest (`oracle_label_manifest.json`),
3. optional diagnostics.

For each state, generator semantics must match the pilot protocol:
- ACT = spend one action now on current branch, then continue under teacher policy.
- STOP = do not spend now; preserve/reallocate compute under same teacher policy context.

---

## 2) Required inputs

Minimum required inputs:
1. `--pilot-config` (JSON): expected to match `configs/stop_vs_act_oracle_label_pilot_v1.json` schema.
2. `--state-manifest` (JSONL): pilot states (typically from `scripts/build_oracle_label_pilot_state_manifest.py`).
3. `--output-dir` (directory): destination for required outputs.

Recommended explicit controls:
- `--teacher-mode` override (must match config unless intentionally overridden and recorded),
- `--seed` for reproducibility,
- `--max-states` for bounded debug runs.

Environment-variable equivalent (used by HPC wrapper):
- `ORACLE_PILOT_CONFIG`
- `ORACLE_STATE_MANIFEST`
- `ORACLE_OUTPUT_DIR`
- `ORACLE_LABELS_JSONL`
- `ORACLE_LABEL_MANIFEST`

---

## 3) Required outputs

The generator must write to `--output-dir`:
1. `oracle_stop_vs_act_labels.jsonl` (required)
2. `oracle_label_manifest.json` (required)

Optional:
- `oracle_label_diagnostics.json`
- per-state trace/debug artifacts

If required outputs are missing, pipeline must fail before distillation.

---

## 4) Required fields for each label row

Every row in `oracle_stop_vs_act_labels.jsonl` must include, at minimum:
- `state_id`
- `example_id`
- `budget`
- `remaining_budget`
- `current_branch_id`
- `q_act`
- `q_stop`
- `oracle_action_gap`
- `oracle_label_act`
- `horizon`
- `rollout_depth`
- `teacher_mode`
- `paired_randomness_used`

These are aligned with `required_row_fields` in the pilot config and consumed by the validator.

---

## 5) Optional diagnostics fields

Rows may include optional uncertainty/diagnostic metadata, for example:
- `gap_std`
- `gap_ci_low`
- `gap_ci_high`
- `agreement_rate`
- `rollout_count`
- `trace_id`
- `runtime_ms`

Run-level manifest may include:
- code/version hash,
- hostname/job id,
- wall-clock runtime,
- sampler/teacher settings,
- failure/retry counters.

---

## 6) Required invariants and consistency guarantees

The generator must guarantee:
1. Numeric validity: `q_act`, `q_stop`, `oracle_action_gap` are finite numbers.
2. Gap identity: `oracle_action_gap == q_act - q_stop` (within tolerance used by validator).
3. Label sign rule: `oracle_label_act = 1` iff `oracle_action_gap > 0`, else `0`.
4. Teacher metadata consistency: `teacher_mode`, `horizon`, and `rollout_depth` must be row-consistent with run settings.
5. Pairing flag integrity: `paired_randomness_used` must truthfully record whether paired randomness was applied.
6. State identity integrity: emitted `state_id`/`current_branch_id` must correspond to consumed manifest rows.

---

## 7) Validator assumptions

`scripts/validate_oracle_label_pilot_outputs.py` assumes:
- required row fields exist,
- core numeric fields are non-missing,
- gap/label consistency checks pass,
- paired-randomness rate and coverage gates are met,
- minimum row-count gate is met before distillation.

So a generator output that is merely schema-shaped but fails quality gates is **not** acceptable for distillation.

---

## 8) Core requirements vs implementation freedom

### Core requirements (must not vary)
- output artifact names/locations expected by wrapper,
- required row fields,
- ACT/STOP semantics,
- gap/label consistency invariants,
- provenance manifest emission,
- compatibility with validator hard gates.

### Implementation freedom (may vary)
- rollout engine implementation details,
- parallelization strategy,
- cluster scheduling approach,
- optional diagnostics richness,
- internal caching/retry mechanics.

Any implementation freedom that changes semantics must be reflected in a versioned contract update.

---

## Mock/testing-only outputs (important)

Interface-test/mock outputs are permitted only when clearly marked as non-oracle, e.g.:
- run manifest includes `mock_mode: true`,
- rows include explicit mock marker fields.

Mock/testing outputs must never be presented as real heavy oracle labels.
