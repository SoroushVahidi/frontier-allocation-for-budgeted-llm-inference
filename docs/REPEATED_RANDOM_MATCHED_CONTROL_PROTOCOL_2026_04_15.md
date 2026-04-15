# Repeated matched-random control protocol for oracle-distilled stop-vs-act (pre-HPC readiness)

## Purpose

This note defines how to move from a single random matched-coverage baseline to repeated random draws with variance-aware summaries.

## 1) Why one random draw is not enough

A single matched-random baseline can be unusually easy or unusually hard by chance. If selective-vs-random conclusions rely on one draw, the conclusion can be unstable.

## 2) Why repeated random draws are the next control

Repeated draws keep the same matched-coverage logic but expose how much random baseline performance varies. This lets us compare selective performance against a random distribution rather than one point estimate.

## 3) What must stay fixed across draws

For a given repeated-draw run family, keep fixed:

1. source distillation-ready pool,
2. target regime (`accepted_only` or `accepted_plus_borderline`),
3. retained coverage target derived from that regime,
4. optional stratification policy (if enabled),
5. training/evaluation configuration downstream.

## 4) What should vary across draws

Only:

- random seed,
- resulting selected train states.

## 5) What future summaries must report

For each selective regime, report:

1. selective run metric values,
2. random-draw mean,
3. spread (at least std/min/max),
4. selective-minus-random-mean delta,
5. win/loss count across random draws when comparable.

## 6) Safe vs unsafe claims pre-pilot

### Safe

- The pipeline now supports repeated matched-random controls and variance-aware summaries.
- Structural readiness can be checked for coverage matching and draw-count requirements.

### Unsafe

- Any claim of oracle-distilled superiority from mock/non-oracle runs.
- Any claim that selective consistently beats random without real validated pilot labels.
- Any final model promotion claim.

## Operational minimum

- Use at least one random draw per regime to pass structural coverage gate.
- Prefer multiple draws (for example >=3) before interpreting selective-vs-random robustness, even in diagnostic mode.
- Keep non-claim warnings active until real oracle pilot labels are used.
