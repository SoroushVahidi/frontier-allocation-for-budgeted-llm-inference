# Repository cleanup status (2026-04-18)

## Purpose

This note records the current state of repository cleanup, organization, and navigation.

It is not a method note.
It is a compact answer to:
- what has already been cleaned,
- what is now consistent,
- what still needs future cleanup,
- and what parts of the repo should be treated as canonical versus merely exploratory.

## Current high-level assessment

The repository is now much cleaner than before in four important ways:

1. **Project identity is clearer.**
   The front-door docs now consistently present the project as fixed-budget next-step branch allocation / frontier allocation rather than the older binary revise-routing story.

2. **The current decision phase is explicit.**
   The main open question is now clearly the target/oracle definition for hard close-branch disagreement states, not broad nearby method proliferation.

3. **Navigation is stronger.**
   The main entry docs (`README.md`, `docs/README.md`, `docs/CANONICAL_START_HERE.md`, `scripts/CANONICAL_START_HERE.md`) now point readers toward the current truth first.

4. **Reference and comparison structure is more disciplined.**
   References are now organized by role, and baselines are treated as a structured layer rather than a flat list of loosely related methods.

## What is already in good shape

### 1. Front-door navigation
The following are now good front-door entry points:
- `README.md`
- `docs/README.md`
- `docs/CANONICAL_START_HERE.md`
- `scripts/CANONICAL_START_HERE.md`
- `docs/REPOSITORY_MASTER_DASHBOARD_2026_04_18.md`

These now broadly tell the same project story.

### 2. Current phase notes
The strongest current phase notes are now:
- `docs/LATEST_STATUS_AFTER_RECENT_PASSES_2026_04_18.md`
- `docs/CURRENT_EXPERIMENT_RULE_2026_04_18.md`
- `docs/PROJECT_SITUATION_REPORT_2026_04_18.md`
- `docs/RESEARCH_IDEAS_AND_NEXT_STEPS_2026_04_18.md`
- `docs/WORKSTREAM_STATUS_AND_OPERATING_PLAN_2026_04_18.md`

These now align much better with the repo’s actual post-comparison / post-oracle-mismatch phase.

### 3. Comparison and semantic-diagnosis notes
The repo now has a much stronger set of current evaluation-facing notes:
- `docs/FULL_METHOD_COMPARISON_STATUS_2026_04_18.md`
- `docs/ORACLE_MISMATCH_STUDY_2026_04_18.md`
- `docs/FINAL_ANSWER_RECOVERY_STATUS_2026_04_18.md`
- `docs/WORST_REAL_FAILURE_CASEBOOK_WITH_REASONING_20260418.md`

These materially improved the repo’s ability to explain where the method currently stands.

### 4. Reference organization
The references layer is now much more structured through:
- `docs/REFERENCES_AUDIT_AND_CURATION_2026_04_18.md`
- `docs/REFERENCES_ORGANIZATION_2026_04_18.md`
- `docs/CURRENT_REFERENCES_SUPPLEMENT_2026_04_16.md`

This is a major improvement over a flat bibliography mindset.

## What is still not fully settled

### 1. Function/objective layer
The repository still has multiple competing live surrogate targets and scoring objects.
The code is often careful, but the canonical function stack is not yet fully frozen.

### 2. Data-processing layer
Dataset scope is increasingly clear, but the final canonical processed-data / derived-data layout still needs a stronger single-source summary and role map.

### 3. Baseline finalization layer
The baseline layer is strong and paper-usable, but still benefits from one last explicit family-role finalization pass:
- direct,
- adjacent,
- ingredient,
- blocked / adapter-only.

### 4. Some legacy summaries still exist
A few older method summaries still reflect an earlier “next experiment = one more nearby tweak” mindset more than the current target-definition / data-discipline phase.

## Canonical vs exploratory rule

A practical rule for the current repository is:

### Canonical
Use these for project interpretation and paper planning:
- front-door docs,
- current phase notes,
- method comparison note,
- oracle mismatch note,
- final answer recovery note,
- current reference audit,
- main datasets / main baselines docs,
- current experiment rule.

### Exploratory
Use these for active experiment lines and detailed diagnostics:
- one-off target-family notes,
- narrower controller tweaks,
- bounded ablation reports,
- idea-specific status notes.

### Historical / provenance
Use these only for traceability:
- old routing-era summaries,
- older memo snapshots,
- superseded interpretations.

## Recommended repository habit

When a new pass changes the project’s actual phase, update at least these files together:
- `README.md`
- `docs/README.md`
- `docs/CANONICAL_START_HERE.md`
- `docs/LATEST_STATUS_AFTER_RECENT_PASSES_2026_04_18.md`
- `docs/CURRENT_EXPERIMENT_RULE_2026_04_18.md`
- the most relevant dashboard / comparison / evaluation summary note

This prevents the repo from drifting into partial truth across different entry points.

## Conservative conclusion

The repository is now substantially more organized and coherent than before.

The main remaining cleanup is no longer broad structural disorder.
It is narrower:
- finalizing the canonical function stack,
- finalizing the canonical data-processing layer,
- and finishing explicit baseline-family classification.

So the repo should now be treated as:

> **structurally cleaned and navigable, but still awaiting final canonicalization of functions, data products, and baseline-family status.**
