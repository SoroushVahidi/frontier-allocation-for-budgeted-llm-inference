# HPC launch protocol for first oracle-label pilot (v1)

## Purpose

This runbook makes the first heavy oracle-label pilot **operationally launch-ready** on HPC.

It does **not** claim the pilot has already run. It defines exactly what must happen at runtime and what must pass before distillation is allowed.

---

## Scope and pilot definition (fixed)

This protocol is for the first pilot only:
- paired ACT-vs-STOP oracle action-gap labels,
- STOP semantics = preserve-and-reallocate,
- shared policy context,
- budgets `{10, 14}`,
- horizon `6`, rollout depth `9`,
- `64` paired rollouts per state,
- pilot target `~1200` states (`>=600` minimum gate).

Anchor baseline remains the current default stop-vs-act setup.

---

## Required inputs before launch

The following must be present and version-locked in the run directory:
1. Pilot config: `configs/stop_vs_act_oracle_label_pilot_v1.json`.
2. State-selection config: `configs/stop_vs_act_oracle_pilot_state_selection_v1.json`.
3. Pilot state manifest (`pilot_state_manifest.jsonl`) either:
   - provided explicitly, or
   - deterministically generated at launch-time via `scripts/build_oracle_label_pilot_state_manifest.py`.
4. Oracle label generator entrypoint command (cluster-specific), wired to emit:
   - `oracle_stop_vs_act_labels.jsonl`,
   - `oracle_label_manifest.json`.
5. Validator utility: `scripts/validate_oracle_label_pilot_outputs.py`.

If any required input is missing, the pipeline must stop before label generation.

---

## Start-to-finish HPC sequence (must be followed)

### Stage 0 — Preflight + provenance snapshot
1. Create a unique run directory under `outputs/oracle_label_pilot_hpc/<run_id>/`.
2. Snapshot pilot and selection configs into that run directory.
3. Run config dry validation:
   - `python3 scripts/validate_oracle_label_pilot_outputs.py --pilot-config ... --dry-run`
4. Fail immediately if config validation fails.

### Stage 1 — State manifest readiness
1. If `--state-manifest` is provided, verify file exists and is readable.
2. Otherwise deterministically build manifest:
   - `python3 scripts/build_oracle_label_pilot_state_manifest.py --selection-config ... --output-dir ...`
3. Fail immediately if `pilot_state_manifest.jsonl` was not produced.

### Stage 2 — Oracle label generation
Generator contract reference:
- `docs/ORACLE_LABEL_GENERATOR_INTERFACE_CONTRACT_V1.md`
- `configs/oracle_label_generator_interface_contract_v1.json`
- testing-only stub: `scripts/run_oracle_label_generator_interface_stub.py --mock-mode`
- real limited prototype: `scripts/run_oracle_label_generator_prototype.py`

1. Export generator interface variables:
   - `ORACLE_PILOT_CONFIG`
   - `ORACLE_STATE_MANIFEST`
   - `ORACLE_OUTPUT_DIR`
   - `ORACLE_LABELS_JSONL`
   - `ORACLE_LABEL_MANIFEST`
2. Run the cluster-specific heavy generator command once.
3. Stop on non-zero exit.
4. After command returns, enforce output existence gates:
   - labels jsonl exists,
   - label manifest exists.
5. If either output is missing, stop pipeline before distillation.

### Stage 3 — Mandatory post-generation validation/report
1. Run validator on generated labels + manifest:
   - `python3 scripts/validate_oracle_label_pilot_outputs.py --pilot-config ... --labels-jsonl ... --manifest-json ... --quality-report-out ...`
2. Validation is a hard gate.
3. If validator exits non-zero or quality gates fail, stop pipeline before distillation.

### Stage 4 — Final summary and handoff status
1. Write `run_summary.json` with command, paths, statuses.
2. Declare run status:
   - `ready_for_distillation` only when generation + all validation gates pass.
   - otherwise `blocked_pre_distillation`.

---

## Artifacts consumed

- `configs/stop_vs_act_oracle_label_pilot_v1.json`
- `configs/stop_vs_act_oracle_pilot_state_selection_v1.json`
- `scripts/build_oracle_label_pilot_state_manifest.py`
- heavy generator entrypoint (cluster-specific command)
- `scripts/validate_oracle_label_pilot_outputs.py`
- wrapper: `scripts/run_oracle_label_pilot_hpc.sh`

---

## Artifacts expected on successful pilot generation

Under `outputs/oracle_label_pilot_hpc/<run_id>/`:
- `oracle_stop_vs_act_labels.jsonl`
- `oracle_label_manifest.json`
- `oracle_label_quality_report.json`
- `run_summary.json`
- `pilot_config.snapshot.json`
- `selection_config.snapshot.json`
- `preflight_config_validation.json`
- `logs/state_manifest_build.log`
- `logs/generator.log`
- `logs/validator.log`

Note: the manifest builder also emits its own metadata in the manifest subdirectory when used.

---

## Failure conditions that must block distillation

Any of the following is a hard stop:
- pilot config dry validation failure,
- missing/unreadable state manifest,
- generator non-zero exit,
- missing labels or label manifest after generation,
- validator non-zero exit,
- any label quality gate fail (row count/schema/core/gap/sign/paired-randomness).

No oracle distillation run is allowed after a hard-stop condition.

---

## Logs + provenance that must be preserved

Must retain all run-local artifacts:
- config snapshots,
- full generator and validator logs,
- final run summary,
- label manifest and quality report,
- state-manifest file used for that run.

These are required for reproducibility and for auditing safe claims.

---

## Safe vs unsafe claims after successful pilot label generation

Safe after successful pilot label generation + validation:
- the oracle pilot pipeline executed end-to-end,
- label artifacts were generated with reproducible provenance,
- pre-distillation quality gates passed on this pilot run.

Still unsafe until distillation + evaluation complete:
- superiority over default stop-vs-act baseline,
- broad generalization claims,
- claims that heavy oracle phase is complete beyond this pilot,
- manuscript-level performance claims.

---

## Immediate next action once HPC is available

Run the wrapper in non-dry mode with the real generator command, then proceed to distillation **only if** validation gates pass:

```bash
scripts/run_oracle_label_pilot_hpc.sh \
  --build-state-manifest \
  --generator-cmd '<cluster generator command using exported ORACLE_* paths>'
```

If generation interface details are still evolving, keep them explicit in the generator command and do not weaken any validation gate.
