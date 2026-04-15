# Oracle phase execution readiness (2026-04-15)

## Purpose

This note explains what is already ready for the first oracle-label pilot, what is still missing, and how the repository should be interpreted at this stage.

It is meant to cleanly separate:
- what has already been prepared,
- what can be validated now,
- and what must wait for heavier compute.

---

## What is already ready

The repository now has all of the following preparation assets for the first oracle-label pilot:

### 1. Oracle-label pilot protocol
A concrete protocol exists for:
- what ACT and STOP mean,
- what oracle quantities should be produced,
- what rollout/horizon regime the pilot should use,
- what quality gates must be checked before trusting the labels.

### 2. Oracle-label pilot config
A dedicated pilot config exists so the pilot can be launched reproducibly rather than from ad hoc settings.

### 3. Oracle-label output validator
The repository now includes a validator/report utility that can:
- validate pilot config integrity,
- validate future oracle-label outputs,
- compute quality statistics,
- and decide whether quality gates pass before distillation proceeds.

### 4. Pilot state-selection protocol
A concrete protocol now exists for:
- what a pilot state is,
- where pilot states come from,
- how states are deduplicated,
- how they are stratified,
- and what metadata must be retained.

### 5. Pilot state manifest builder
A deterministic manifest builder now exists that can:
- extract candidate states,
- deduplicate and stratify them,
- select the pilot subset reproducibly,
- and emit manifest/schema/meta artifacts.

That means the oracle-label pilot is now specified both:
- on the output side,
- and on the input side.

---

## What can already be done without heavy compute

The following can already be done now:
- dry-run validation of pilot config,
- dry-run validation of manifest generation,
- schema checks for future oracle output structure,
- provenance checks on pilot-state extraction,
- note and config review,
- and code-path sanity checks.

This is useful because it reduces avoidable execution risk before expensive compute is spent.

---

## What must wait for heavier compute

The following has **not** been done yet and must wait for compute-rich execution:
- true oracle ACT/STOP rollout generation over the pilot states,
- production of actual `q_act`, `q_stop`, and `oracle_action_gap` values,
- post-run oracle label quality reporting on real pilot outputs,
- distillation of the oracle labels into the stop-vs-act controller,
- and controller-level evaluation of oracle-distilled supervision versus the current default anchor baseline.

Those are the real next empirical steps.

---

## What is still underspecified

Only a limited set of practical execution details remain outside the current repository preparation layer.

Most importantly:
- runtime resource envelope sizing on the target cluster,
- cluster-specific generator command wiring,
- and submission-time scheduler parameters (partition/time/memory/GPU policy).

A repo-level HPC orchestration wrapper and launch protocol now exist (`scripts/run_oracle_label_pilot_hpc.sh`, `docs/HPC_ORACLE_LABEL_PILOT_LAUNCH_PROTOCOL_V1.md`). The remaining gap is cluster-specific command/resource wiring, not methodological framing.

Generator-interface status update:
- A concrete heavy-generator contract now exists: `docs/ORACLE_LABEL_GENERATOR_INTERFACE_CONTRACT_V1.md` + `configs/oracle_label_generator_interface_contract_v1.json`.
- A testing-only CLI scaffold now exists: `scripts/run_oracle_label_generator_interface_stub.py` (mock mode clearly labeled non-oracle).
- A first real (limited) generator prototype now exists: `scripts/run_oracle_label_generator_prototype.py` with scope note `docs/ORACLE_LABEL_GENERATOR_PROTOTYPE_V1_NOTE.md`.
- Real heavy oracle rollout logic is still pending and remains the main compute-dependent implementation step.

---

## How this changes project interpretation

Before this phase, the project was still trying to rescue the stop-vs-act line with bounded local target tweaks.

Now the project should be interpreted as:
- having learned enough from bounded lightweight failures,
- having preserved those failures honestly,
- and being operationally prepared to test a more serious higher-fidelity supervision path.

So the current project is no longer primarily asking:
- “which small local target tweak should we try next?”

It is now asking:
- **“can oracle-style paired ACT-vs-STOP labels provide a materially stronger teacher signal than lightweight local targets?”**

---

## What should remain fixed before the pilot runs

Keep fixed:
- the current default stop-vs-act setup as the anchor baseline,
- the pilot config and manifest schema unless a very strong reason appears,
- the conservative quality-gate logic,
- the current interpretation that the heavy phase is planned and prepared, but not yet completed.

---

## Safe wording

Safe to say:
- the repository is execution-ready for a first oracle-label pilot in terms of protocol, config, validation, and state-manifest preparation,
- but the actual oracle-label run has not yet been executed,
- and no oracle-distilled performance claims should yet be made.

Not safe to say:
- that oracle labels already exist,
- that distillation has already been validated,
- or that the heavier phase is complete.

---

## Bottom line

The repository is now:

**methodologically ready for the first oracle-label pilot**

but not yet:

**empirically complete for that phase.**

---

## Selective distillation layer status update (pre-HPC)

A concrete selective-distillation policy/scaffold is now defined for the post-generation phase:

- design note: `docs/ORACLE_SELECTIVE_DISTILLATION_PLAN_V1.md`
- policy config: `configs/stop_vs_act_oracle_selective_distillation_v1.json`
- preprocessing tool: `scripts/build_stop_vs_act_oracle_distillation_dataset.py`

This addition keeps phase boundaries explicit:

1. Oracle-label generation + validator gates must pass first.
2. Then selective distillation preprocessing assigns `accepted` / `borderline` / `rejected` buckets and emits weighted training rows.
3. Only then should student training/evaluation be run against the unchanged default anchor baseline.

So the immediate next action after obtaining valid non-mock pilot oracle labels is:
- run the distillation preprocessing tool on validated labels,
- inspect bucket summary diagnostics,
- and launch first selective-distillation training/eval pass.

---

## Oracle-distilled student path status update (pre-pilot execution)

The repository now also includes the first concrete post-pilot student path:

- protocol: `docs/ORACLE_DISTILLED_STUDENT_TRAINING_PROTOCOL_V1.md`
- training defaults: `configs/stop_vs_act_oracle_distilled_student_train_v1.json`
- train/eval script: `scripts/train_oracle_distilled_stop_vs_act_student.py`
- run-comparison scaffold: `scripts/compare_oracle_distilled_stop_vs_act_runs.py`

Interpretation remains unchanged:
- this is **execution readiness** for post-pilot training/evaluation,
- not evidence that real oracle-distilled gains have already been demonstrated.
