# HPC experiments and training backlog (current project)

## Purpose

This note lists the **main experiments, label-generation jobs, and training pipelines that should be run when HPC becomes available again**.

It is written so that later we can directly turn each item into a cluster-ready query, runbook, or Slurm job.

This document is for the **current repository and current project only**:
- fixed-budget adaptive test-time compute allocation,
- cross-controller frontier allocation,
- budget-conditioned stop-vs-act / spend-vs-reallocate control.

## Main rule

When HPC returns, do **not** start with random large runs.

Use this order:
1. large label-generation / brute-force jobs,
2. large supervised training jobs that depend on those labels,
3. large robustness sweeps,
4. larger real-model evaluation runs.

The reason is simple: the current project bottleneck is still target quality, so the highest-value HPC use is first to improve supervision, then to train on that supervision.

---

## Priority A — large brute-force / rollout label generation

### A1. Large local brute-force ACT-vs-STOP label generation

**Goal**
Generate many more action-conditional labels for the local decision:
- spend the next unit of compute here,
- or preserve / reallocate it elsewhere.

**Why HPC is needed**
This requires many repeated rollouts, matched local comparisons, or bounded brute-force state expansions over many branch states, seeds, and budgets.

**What to generate**
- per-state ACT-vs-STOP labels,
- uncertainty / instability estimates,
- repeated-rollout variance estimates,
- budget-conditioned labels,
- matched-control labels for small horizons,
- richer STOP-side comparator variants.

**What this data is for**
Training the main stop-vs-act controller and improving target quality.

**Expected outputs**
- large JSONL / CSV label datasets,
- manifest files,
- per-slice disagreement summaries,
- ambiguity / instability audit reports.

**Priority**
Very high. This is one of the first HPC jobs to run.

### A2. Oracle-label pilot expansion / brute-force frontier labeling

**Goal**
Run larger oracle-style or near-oracle frontier labeling jobs to estimate which branch/controller/action would have been best under bounded future rollouts.

**Why HPC is needed**
These jobs are expensive because they require many paired rollouts, shard management, resume logic, and broader coverage across states and budgets.

**What to generate**
- oracle or near-oracle label manifests,
- selective accepted / borderline / rejected buckets,
- policy-behavior summaries,
- matched-rate and frontier-evaluation summaries.

**What this data is for**
- stronger target construction,
- selective distillation,
- hard-slice analysis,
- better evidence for opportunity-cost-aware STOP semantics.

**Expected outputs**
- sharded oracle label outputs,
- merged manifests,
- selective-distillation-ready datasets,
- protocol summaries and audit notes.

**Priority**
Very high.

---

## Priority B — large supervised training pipelines

### B1. Large stop-vs-act controller training

**Goal**
Train stronger budget-conditioned stop-vs-act controllers using improved large-scale labels.

**Why HPC is needed**
The training should be repeated across:
- multiple target variants,
- uncertainty-aware data policies,
- multiple seeds,
- budgets,
- datasets,
- and possibly richer models than the current lightweight baselines.

**What to train**
- lightweight classifiers first,
- stronger models later if justified,
- variants with uncertainty-aware filtering / reweighting,
- variants using different target families.

**What this training is for**
This is the main controller-learning pipeline for the current paper direction.

**Expected outputs**
- trained controller artifacts,
- calibration reports,
- matched-budget controller comparison tables,
- slice analyses by uncertainty, margin, disagreement, and budget.

**Priority**
Very high.

### B2. Large pairwise branch-comparison / branch-ranking training

**Goal**
Train larger branch-comparison models for deciding which branch is better to continue.

**Why HPC is needed**
This line may require large pairwise datasets, many pair constructions, multiple BT-style or preference-style models, and broader robustness sweeps.

**What to train**
- pairwise BT branch scorers,
- reliability-aware pairwise variants,
- tie-aware / ambiguity-aware variants,
- possibly stronger learned ranking models if label quality supports them.

**What this training is for**
This is the main large training line for **learning comparison between branches**.

**Expected outputs**
- trained pairwise models,
- ranking / selection robustness summaries,
- comparisons against simpler heuristics,
- branch-level calibration and contradiction audits.

**Priority**
Very high.

### B3. Oracle-distilled student training

**Goal**
Train students from oracle or selective-distillation datasets once the oracle-label pipeline is large enough.

**Why HPC is needed**
The regime involves repeated random controls, accepted-only vs accepted+borderline buckets, and matched-rate evaluation bundles.

**What to train**
- oracle-distilled stop-vs-act students,
- matched random-control baselines,
- selective-distillation variants with retained-coverage accounting.

**What this training is for**
To test whether stronger supervision distilled from oracle-style labels improves controller quality beyond current proxy targets.

**Expected outputs**
- trained student models,
- matched-control comparison packages,
- retained-coverage and ACT-rate reports,
- slice summaries for manuscript tables later.

**Priority**
High, but after enough oracle labels exist.

---

## Priority C — large robustness and ablation sweeps

### C1. Multi-seed / multi-budget / multi-dataset controller robustness sweeps

**Goal**
Run large matched sweeps to see whether learned controllers are actually robust.

**Why HPC is needed**
These are combinatorially large once we sweep:
- datasets,
- budgets,
- seeds,
- target variants,
- uncertainty policies,
- controller models.

**What to measure**
- controller-level accuracy / solve rate,
- average budget use,
- under-spend,
- calibration drift,
- robustness of wins over heuristics and BT baselines.

**Priority**
High.

### C2. Anti-collapse / frontier-behavior sweeps

**Goal**
Stress-test anti-collapse mechanisms and frontier behavior over many regimes.

**Why HPC is needed**
These require broad parameter grids and repeated runs across datasets and budgets.

**What to measure**
- realized budget use,
- action-trace behavior,
- forced-expand share,
- prune share,
- regime dependence of min-expand or related knobs.

**Priority**
High.

---

## Priority D — larger real-model evaluation jobs

### D1. Larger matched-budget real-model comparisons

**Goal**
Run larger real-model experiments after the supervision and controller story is stronger.

**Why HPC is needed**
Even if provider APIs are external, the orchestration, repeated evaluation, logging, and larger sweep management benefit from cluster scheduling.

**What to compare**
- our main controller,
- strong in-repo heuristic baselines,
- pairwise BT baseline,
- important external paper baselines once implemented fairly.

**What to report**
- matched-budget quality,
- cost / quality frontiers,
- budget adherence,
- failure slices,
- enough stable output for manuscript tables.

**Priority**
Important, but after better targets and training.

---

## Which HPC tasks involve actual training?

These are the main training-heavy items:

1. **Large stop-vs-act controller training**
2. **Large pairwise branch-comparison / branch-ranking training**
3. **Oracle-distilled student training**

These are the main non-training but still HPC-heavy items:

4. **Large brute-force / rollout label generation**
5. **Oracle-label pilot expansion**
6. **Large robustness / ablation sweeps**
7. **Larger real-model evaluation bundles**

---

## Recommended execution order when HPC returns

### Phase 1 — data / labels
1. Large brute-force ACT-vs-STOP label generation
2. Oracle-label pilot expansion

### Phase 2 — main supervised learning
3. Large stop-vs-act controller training
4. Large pairwise branch-comparison training

### Phase 3 — stronger supervision experiments
5. Oracle-distilled student training

### Phase 4 — evidence consolidation
6. Multi-seed / multi-budget / multi-dataset robustness sweeps
7. Anti-collapse / frontier sweeps
8. Larger real-model matched-budget evaluations

---

## What to ask for later

When HPC is available again, future queries should be written against one of these exact items, for example:
- “Give me the HPC query for large brute-force ACT-vs-STOP label generation.”
- “Give me the HPC query for large pairwise branch-comparison training.”
- “Give me the HPC query for oracle-distilled student training.”
- “Give me the HPC query for large controller robustness sweeps.”

This file exists so that we can refer to these jobs unambiguously later.
