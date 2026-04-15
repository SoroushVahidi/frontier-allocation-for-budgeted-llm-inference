# Oracle-distilled regime bundle runner protocol (pre-HPC readiness)

## Why manual multi-step execution is no longer ideal

The evaluation pipeline now has multiple required controls (matched coverage, repeated random draws, variance-aware comparison). Running these manually across separate scripts is error-prone and makes provenance harder to audit.

## What one bundled regime run should include

A bundled regime run should execute, in one orchestrated path:

1. repeated matched-random baseline generation for the chosen regime,
2. anchor student run (current default anchor role in summary package),
3. selective student run for the chosen regime,
4. student runs for every random draw,
5. one comparison summary package over those runs,
6. one top-level bundle manifest with command provenance and output pointers.

## Initial regime support

Support first:

- `accepted_only`
- `accepted_plus_borderline`

## Required emitted artifacts per bundle

At minimum:

- random-draw builder summary JSON,
- anchor run summary JSON,
- selective run summary JSON,
- per-draw random run summaries,
- comparison summary JSON/CSV/MD,
- top-level bundle manifest JSON with command list and return codes.

## Repeated random integration rule

For each bundle:

- source pool and regime are fixed,
- retained coverage target is fixed,
- optional stratification rule is fixed,
- random seed changes per draw.

## Automatic comparison outputs

The bundle comparison should report:

- selective metric values,
- repeated-random mean/spread,
- selective-minus-random-mean deltas,
- win counts across draws,
- readiness status under required role and draw-count gates.

## Safe vs unsafe claims before real oracle labels

### Safe

- The bundle runner improves reproducibility and provenance for pre-pilot structural evaluation.
- The bundle runner can verify that repeated-random controls are present and wired.

### Unsafe

- Any claim of oracle-distilled superiority from mock/non-oracle runs.
- Any final model-selection claim before real validated pilot labels.
