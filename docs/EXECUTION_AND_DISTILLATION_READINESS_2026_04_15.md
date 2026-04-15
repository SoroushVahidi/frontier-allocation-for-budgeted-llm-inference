# Execution and distillation readiness (2026-04-15)

## Purpose

This note explains what is already ready for the first oracle-label pilot and the first oracle-distilled student run, what still depends on real compute and real labels, and how the repository should be interpreted at this stage.

It is meant to separate clearly:
- what has already been prepared,
- what can already be validated locally,
- and what must still wait for real pilot execution.

---

## What is already ready

The repository now has all of the following preparation assets for the first oracle-label pilot and post-pilot student phase.

### 1. Oracle-label pilot protocol and config
A concrete protocol exists for:
- what ACT and STOP mean,
- what oracle quantities should be produced,
- what rollout/horizon regime the pilot should use,
- and what quality gates must be checked before trusting the labels.

### 2. Pilot state-selection and manifest generation
A concrete protocol now exists for:
- what a pilot state is,
- where pilot states come from,
- how states are deduplicated,
- how they are stratified,
- what metadata must be retained,
- and how a deterministic pilot-state manifest is built.

### 3. Oracle-label generator stack
The repo now includes:
- a heavy-generator interface contract,
- a generator stub for interface testing,
- a real prototype generator,
- and a production-leaning heavy generator path with shard-aware operational features.

### 4. Oracle-label validation and sharding support
The repository now includes:
- a validator/report utility for future oracle outputs,
- deterministic shard split/merge support,
- hard merge consistency checks,
- HPC wrapper/runbook assets,
- and an sbatch template.

### 5. Selective-distillation preprocessing
The repository now includes a selective-distillation preprocessing layer that:
- consumes contract-compliant oracle labels,
- buckets rows into accepted / borderline / rejected,
- enforces config structure and required fields,
- supports manifest-aware mock checks,
- and emits weighted distillation-ready outputs.

### 6. Oracle-student training/evaluation scaffold
The repository now includes:
- a distillation-training protocol,
- a machine-readable training config,
- a first oracle-distilled student train/eval path,
- and a comparison scaffold for accepted-only vs accepted+borderline and related post-pilot comparisons.

That means the repository is now prepared for both:
- the oracle-label pilot itself,
- and the first post-pilot student-training runs.

---

## What can already be done locally

The following can already be done now without real HPC pilot completion:
- dry-run config validation,
- dry-run manifest generation,
- interface smoke tests,
- tiny local generator prototype tests,
- shard split/merge smoke tests,
- selective-distillation preprocessing on mock/test outputs,
- and student train/eval path smoke tests in explicitly non-claim mode.

These local checks are useful because they reduce integration risk before expensive compute is spent.

---

## What must still wait for real pilot execution

The following has **not** yet been completed and must wait for real pilot execution:
- full sharded oracle ACT/STOP rollout generation on the pilot manifest,
- merged pilot-scale oracle outputs,
- pilot-scale oracle validation passing all quality gates,
- selective-distillation preprocessing on real accepted pilot outputs,
- oracle-distilled student training on real non-mock labels,
- and real comparative evaluation against the current default anchor baseline.

Those are the actual next empirical steps.

---

## What is still outside the current repository preparation layer

Only a limited set of practical execution details remain outside the current repository preparation layer.

Most importantly:
- the actual full cluster launch,
- scheduler/resource tuning,
- full runtime envelope confirmation,
- and successful pilot completion at scale.

These are execution details rather than conceptual gaps.

---

## How this changes project interpretation

Before this phase, the project was still trying to rescue the stop-vs-act line with bounded local target tweaks.

Now the project should be interpreted as:
- having learned enough from bounded lightweight failures,
- having preserved those failures honestly,
- being ready to test a higher-fidelity teacher-signal phase,
- and already having the first post-pilot student-training path prepared.

So the project is no longer primarily asking:
- “which small local target tweak should we try next?”

It is now asking:
- **“can selectively trusted oracle ACT-vs-STOP labels improve the lightweight stop-vs-act student over the current default path?”**

---

## What should remain fixed before real pilot outputs exist

Keep fixed:
- the current default stop-vs-act setup as the anchor baseline,
- the pilot config and manifest schema unless a very strong reason appears,
- the conservative validator gates,
- the selective-distillation bucket policy defaults unless real pilot evidence says otherwise,
- and the interpretation that the heavy phase is prepared but not yet empirically completed.

---

## Safe wording

Safe to say:
- the repository is execution-ready for the first oracle-label pilot in terms of protocol, config, generation contract, validation, sharding, and state-manifest preparation,
- the repository is also ready for the first oracle-distilled student runs once real validated pilot labels exist,
- but the actual oracle pilot has not yet been completed,
- and no oracle-distilled improvement claims should yet be made.

Not safe to say:
- that pilot-scale oracle labels already exist,
- that the validator gates have already passed at pilot scale,
- that oracle-distilled students already outperform the current default,
- or that the heavy phase is complete.

---

## Bottom line

The repository is now:

**methodologically and operationally ready for the first oracle-label pilot and the first post-pilot oracle-student training runs**

but not yet:

**empirically complete for those phases.**
