# What is not working now

## Purpose

This note records directions that are currently weak, mixed, or explicitly not validated enough.

The goal is to reduce repeated low-value exploration and to help keep future iterations focused.

## Not working as a full solution

### 1. Bigger model class alone
Adding stronger tabular ranking families has not yielded a robust universal winner.

### 2. More labels alone
Larger corpora helped, but did not remove the core mismatch around hard ambiguous comparisons.

### 3. Exact promotion alone on hard regions
Selective exact relabeling improved provenance and localization, but did not clearly fix near-tie / adjacent-rank outcomes.

### 4. Pure threshold tweaking
Thresholds, tie bands, and uncertainty cutoffs matter, but threshold tuning alone is not the method contribution.

### 5. Generic pointwise fallback
Pointwise fallback helps only in some settings; generic fallback is brittle and can degrade overall behavior.

### 6. Deferred-only specialist training
Training the specialist only on post-hoc deferred train states was a useful test, but it was not the right fix; it hurt forced/top-1 and did not improve deferred-subset quality enough.

### 7. Broad hard-pair replacement
Recent hard-pair relabeling/adjudication attempts did not justify broad label overrides as the default fix, especially under loose acceptance/replacement policies.

### 8. Broadening scope too early
The repo already has many strong active lines. Broadening into more variants before tightening the current strongest scaffold is not the best use of effort.

## Not yet strong enough for a NeurIPS-level claim

- a robust universal learned controller winner,
- a decisive cross-dataset comparison against the strongest external baselines,
- a fully principled confidence/defer mechanism for selective pairwise decisions,
- a paper story that already reads as a clear algorithmic contribution rather than a careful but still exploratory stack.

## What this means in practice

Do not spend the next pass on:
- another broad model-class sweep,
- another generic fallback policy,
- another loose hard-label replacement pass,
- or another repo-wide method branch unless it directly strengthens the current strongest scaffold.

## Current discipline rule

Before launching a new method pass, ask:
1. does it improve the current strongest scaffold,
2. does it address ambiguous hard-case supervision or selective pairwise control,
3. does it make the paper look more principled rather than just more complex?

If the answer is no, it is probably not the best next move.
