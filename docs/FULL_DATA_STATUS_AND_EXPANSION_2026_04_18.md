# Full data status and expansion pass (2026-04-18)

## Purpose

This note records the full repository-guided dataset expansion pass requested for 2026-04-18.

Scope:
1. tighten dataset naming/canonicalization discipline,
2. fully integrate the currently prioritized expansion datasets,
3. keep evaluation vs supervision roles explicit,
4. produce machine-readable readiness/coverage outputs.

This is a data-quality and expansion pass, **not** a new-method pass.

## Current core dataset situation

Current benchmark-facing core remains math-heavy, anchored by:
- GSM8K
- MATH / MATH mirror
- MATH-500
- AIME
- OlympiadBench
- AMO-Bench
- GPQA Diamond
- NaturalPlan (clone-based)
- LiveCodeBench (optional/extended)

This core is useful but biased toward math-centric reasoning, with less direct coverage of:
- paragraph-grounded evidence selection ambiguity,
- long-context narrative disambiguation,
- broader cross-domain symbolic/logical tasks.

## New datasets added in this pass

The full next-step expansion target has now been integrated around the canonical ids below:

1. **DROP**
   - Canonical key: `allenai/drop`
   - Current loader repo id in environment: `ucinlp/drop`
   - Role: expansion evaluation dataset (evaluation-first)
   - Why it matters: paragraph-grounded numerical + evidence selection ambiguity.

2. **MuSR**
   - Canonical key: `TAUR-Lab/MuSR`
   - Role: expansion evaluation dataset (evaluation-first)
   - Why it matters: long-lived ambiguity across multiple plausible interpretations.

3. **BIG-Bench Hard**
   - Canonical key: `openeval/BIG-Bench-Hard`
   - Role: expansion evaluation dataset (evaluation-first)
   - Why it matters: broader logical/symbolic diversity beyond math-only story.

4. **AQuA**
   - Canonical key: `deepmind/aqua_rat`
   - Role: expansion evaluation dataset (evaluation-first; optional supervised use once normalization policy is frozen)
   - Why it matters: MCQ structure supports cleaner target normalization and branch-comparison supervision experiments.

## Integration and consistency changes made

### 1) Canonicalization and aliases

- Canonical registry keys are kept in `experiments/hf_datasets.py`.
- Alias resolution remains case-insensitive.
- Explicit alias map is now exported via helper functions and expansion-pass artifacts.

### 2) Role classification discipline

Explicit role map is now maintained in code and emitted in outputs:
- main evaluation datasets,
- expansion evaluation datasets,
- optional/extended only.

This avoids blurring evaluation datasets with supervision/prep datasets.

### 3) Standardized example formatting discipline

The HF sampling helper now formats rows into a repo-standard schema:
- `example_id`, `dataset`, `question`, `answer`, `split`, `config` (+ optional fields).

Dataset-specific handling added for:
- DROP (`passage` + `question`, span-answer candidates),
- MuSR (narrative + choices + answer index/choice),
- BIG-Bench Hard (task-packed row unpacking to nested example),
- AQuA (options surfaced in question and choices fields).

### 4) Existing-dataset quality pass (bounded)

During this pass, existing wiring was normalized/kept consistent for:
- canonical ids vs aliases,
- split/config defaults per registry,
- explicit provenance caveats (mirror/fallback/gated/clone-dependent).

## Machine-readable output bundle

Generated under:
- `outputs/dataset_expansion_full_20260418/`

Files:
- `manifest.json`
- `integrated_datasets.json`
- `dataset_role_map.json`
- `dataset_alias_map.json`
- `dataset_processing_summary.json`
- `dataset_readiness_table.json`
- `ambiguity_regime_coverage_summary.json`
- `commands_assumptions_caveats.md`

## Are datasets now used in the right role?

Short answer: **yes, with explicit caveats**.

- DROP, MuSR, BIG-Bench Hard, AQuA are integrated as **expansion evaluation datasets**.
- External supervision datasets remain separate in their own supervision/prep layer.
- No claim is made that expansion integration alone implies final-method gains.

## Does ambiguity-regime coverage improve materially?

Short answer: **yes, relative to prior math-heavy concentration**.

Improved coverage now includes:
- paragraph evidence selection + numeric extraction ambiguity (DROP),
- long-context narrative interpretation ambiguity (MuSR),
- cross-domain logical/symbolic heterogeneity (BIG-Bench Hard),
- MCQ option-level answer disambiguation (AQuA).

Still under-covered:
- interactive tool-use ambiguity,
- code-execution-grounded reasoning ambiguity,
- multi-turn dialogic ambiguity.

## Is the current data amount enough now?

For the **next stage** (target-definition and evaluation-breadth consolidation): **yes, conditionally**.

Conditionally means:
- enough dataset breadth exists to run disciplined evaluation-first breadth checks,
- but success still depends on clean metric policy and target-definition discipline,
- and should not be replaced by random additional dataset ingestion.

## Is data processing/canonicalization clean now?

Short answer: **cleaner and substantially more explicit, but not perfect**.

What is now clean:
- canonical ids + aliases are explicit,
- role map is explicit,
- sample formatting is standardized with dataset-specific logic,
- expansion/readiness artifacts are consolidated in one bundle.

Remaining caveats:
- DROP canonical HF ownership path remains a known caveat (`allenai/drop` key with `ucinlp/drop` loader fallback in this environment).
- BIG-Bench Hard still needs explicit task-unpacking policy in full training pipelines.
- NaturalPlan remains clone-dependent.
- LiveCodeBench remains optional/extended with environment caveats.

## Does the project still need more datasets immediately?

Short answer: **not by default**.

Current bottleneck remains:
- target-definition evaluation quality,
- disagreement/near-tie semantic adjudication quality,
- and disciplined cross-regime evaluation execution.

So the next bottleneck is not "more datasets" but:

> **cleaner evaluation execution across the newly broadened ambiguity regimes, with explicit oracle/target-definition adjudication on hard disagreement slices.**

## Conservative conclusion

This pass delivers the full repository-guided next-step expansion target (DROP, MuSR, BIG-Bench Hard, AQuA) with better role clarity, improved canonicalization discipline, and a machine-readable readiness bundle.

The dataset layer is now better aligned with paper-readiness goals: broader ambiguity regimes, cleaner evaluation-vs-supervision separation, and explicit caveats where integration remains partial.
