# Current repository status (distillation-phase ready)

## Purpose

This note is the current high-level status summary for the repository after:
- the bounded stop-vs-act target-refinement phase,
- the transition to higher-fidelity label planning,
- the oracle-label pilot preparation phase,
- the oracle-label generation interface and heavy-path preparation,
- and the first selective-distillation and oracle-student training scaffolding phase.

Use this as the best single note for understanding the **current** state of the project.

---

## Project identity

This repository supports the current NeurIPS-oriented project on:
- fixed-budget adaptive test-time compute allocation for LLM reasoning,
- cross-controller frontier allocation,
- branch/controller decisions under a global compute budget,
- oracle frontier headroom,
- anti-collapse controller design,
- and supervision-target design for allocation decisions.

The central project question remains:

> **Is the next unit of compute worth spending here?**

That framing still holds.

---

## Current overall assessment

The repository is now in a strong **execution-readiness** state.

It has:
- a strong and stable project framing,
- substantial bounded stop-vs-act experimentation,
- preserved negative-result provenance,
- a concrete oracle-label pilot protocol,
- a production-leaning heavy generator path,
- deterministic pilot-state selection and shard orchestration,
- a selective-distillation preprocessing layer,
- and a first oracle-distilled student training/evaluation scaffold.

So the repository is no longer only prepared to generate oracle labels.
It is now prepared to move from oracle labels to student training once valid pilot outputs exist.

---

## What is strong now

### 1. Framing and infrastructure
- Frontier/controller infrastructure is present.
- Anti-collapse and comparative-audit work is present.
- Branch-scorer experimentation is substantial.
- Stop-vs-act is implemented and reproducibly testable.

### 2. Provenance quality
- The repo keeps bounded negative results rather than hiding them.
- Non-promoted variants remain available for provenance.
- Notes increasingly distinguish safe from unsafe claims.

### 3. Oracle-phase readiness
The repo now has concrete operational preparation for the oracle phase, including:
- pilot protocol,
- pilot config,
- validator,
- state-selection protocol,
- deterministic pilot-state manifest builder,
- heavy-generator interface contract,
- real generator prototype,
- production-leaning heavy generator path,
- HPC wrapper,
- sbatch template,
- deterministic sharding and merge tooling.

### 4. Post-pilot readiness
The repo now also has:
- selective-distillation preprocessing for accepted / borderline / rejected oracle labels,
- a distillation-training protocol,
- a first oracle-distilled student train/eval path,
- and a comparison scaffold for post-pilot runs.

This is a meaningful shift from “pilot-ready” to “pilot-plus-student-ready.”

---

## What has actually been implemented

### A. Bounded stop-vs-act phase
The stop-vs-act line has already included:
- default stop-vs-act dataset/train/eval path,
- bounded robustness sweep,
- diagnosis + targeted revision,
- label-refinement pass,
- one-step counterfactual target pass,
- small-horizon ACT-vs-STOP target pass,
- repeated-averaging / stabilization pass,
- matched-comparator pass,
- one-step policy-coupled STOP pass,
- longer-horizon policy-coupled STOP pass.

### B. Oracle-label transition and execution-prep phase
The repo now also includes:
- diagnosis/design note for moving to higher-fidelity supervision,
- heavy-label planning manifest,
- lightweight oracle-label scaffold,
- execution-ready pilot protocol,
- pilot output validator,
- state-selection protocol,
- deterministic pilot-state manifest builder,
- heavy-generator interface contract,
- interface stub/mock scaffold,
- real prototype generator,
- production-leaning heavy generator path,
- deterministic shard split/merge support,
- HPC launch runbook and wrapper.

### C. Selective distillation and student phase scaffolding
The repo now additionally includes:
- selective-distillation policy note,
- selective-distillation preprocessing scaffold,
- machine-readable distillation/training config,
- oracle-distilled stop-vs-act student training/evaluation path,
- and a comparison scaffold across distilled runs.

That means the repository now spans the full conceptual pipeline from:
- bounded local target experimentation
- to oracle pilot preparation
- to post-pilot student-training readiness.

---

## What has been learned

### High-confidence conclusions
1. The stop-vs-act controller framing remains the best near-term controller framing.
2. The current default stop-vs-act setup still remains the best bounded baseline inside that line.
3. The main bottleneck is not infrastructure and not mainly controller class.
4. Lightweight local target tweaking likely reached diminishing returns.
5. The next real gains likely depend on higher-fidelity supervision rather than another small target tweak.

### Important negative conclusions
1. Threshold and uncertainty tuning were not enough.
2. One-step and short-horizon counterfactual target variants did not replace the default.
3. Stabilization helped some target-side metrics but not controller outcomes.
4. Matched randomness alone did not solve the comparator problem.
5. One-step and slightly longer-horizon policy-coupled STOP baselines still did not replace the default.

### Current interpretation of those results
These are useful negative results.
They justify the transition to oracle-label generation, selective trust, and oracle-distilled student evaluation.

---

## Current main bottleneck

The main bottleneck is now best described as:

**whether high-fidelity, selectively trusted oracle ACT-vs-STOP labels can materially improve the lightweight stop-vs-act student over the current default anchor baseline.**

This means the unresolved issue is no longer primarily:
- how to invent another local target tweak,
- or how to define another slightly different bounded comparator.

It is now primarily:
- whether the heavier oracle-label phase produces labels of sufficient quality,
- whether the acceptance/filtering policy retains the right training signal,
- and whether selective distillation actually improves downstream controller behavior.

That is the right current bottleneck statement for the repository.

---

## What the repository is doing now

The repository is currently in this phase:

**oracle-label execution readiness plus post-pilot student-training readiness.**

That means the repo is now primarily doing:
- preparing and staging the first real oracle-label pilot,
- making the heavy generation path launchable and merge-safe,
- defining pre-distillation trust/acceptance logic,
- and wiring the first oracle-distilled student path for use once valid pilot labels exist.

The repo is not currently centered on:
- more threshold-only stop-vs-act tweaks,
- more small comparator variants as the main plan,
- or searching for more existing external data as the immediate fix.

---

## Current canonical interpretation

### Canonical now
- overall fixed-budget frontier-allocation framing,
- stop-vs-act as the main near-term controller family,
- current default stop-vs-act setup as the anchor baseline,
- oracle-label pilot generation and validation assets,
- selective-distillation preprocessing assets,
- oracle-distilled student train/eval readiness,
- conservative claim discipline.

### Exploratory but still useful
- non-default stop-vs-act target variants,
- matched and policy-coupled comparator variants,
- auxiliary branch-scorer variants,
- different bucket policies for borderline oracle labels until real pilot evidence exists.

### Historical / provenance only
- older binary revise-routing artifacts,
- older notes that predate the oracle-label transition,
- older notes that stop at pilot readiness but do not yet reflect student-training readiness.

---

## What should happen next

### Immediate next step once compute is available
Execute the first real sharded oracle-label pilot.

That means:
1. generate oracle ACT/STOP values on the fixed pilot-state manifest,
2. merge shard outputs deterministically,
3. validate them with the pilot validator and quality gates,
4. build the selective-distillation dataset,
5. train oracle-distilled students with at least accepted-only and accepted+borderline settings,
6. compare those students against the current default anchor baseline and strong heuristic baseline.

### Immediate pre-compute note
One remaining practical item outside the repository’s conceptual layer is the real cluster execution itself:
- scheduler/resource tuning,
- full runtime envelope confirmation,
- and pilot-scale execution discipline.

Those are execution concerns, not design gaps.

---

## Safe wording now

Safe to say:
- the repository has strong framing and strong infrastructure,
- stop-vs-act is implemented and important,
- lightweight target engineering produced useful but mostly non-promoted results,
- the current default setup remains the best bounded baseline,
- the repo is prepared for a first oracle-label pilot,
- the repo is also prepared for selective distillation and oracle-student training once valid pilot labels exist,
- the next likely gains depend on better label fidelity rather than another small local tweak.

Not safe to say:
- the oracle-label pilot has already completed successfully,
- oracle-distilled training has already improved the student,
- the stop-vs-act problem is solved,
- the current learned controller is already robustly better than the strongest heuristic baseline,
- or that the future heavy phase is guaranteed to succeed.

---

## Recommended read order now

1. `docs/CURRENT_REPO_STATUS_2026_04_15_DISTILLATION_READY.md`
2. `docs/EXECUTION_AND_DISTILLATION_READINESS_2026_04_15.md`
3. `docs/CURRENT_REFERENCES_SUPPLEMENT_2026_04_15_DISTILLATION_READY.md`
4. `docs/CURRENT_REPO_STATUS_2026_04_15_ORACLE_READY.md`
5. `docs/ORACLE_PHASE_EXECUTION_READINESS_2026_04_15.md`
6. `docs/CURRENT_REFERENCES_SUPPLEMENT_2026_04_15_ORACLE_PHASE.md`
7. pilot / validator / sharding / heavy-generator / selective-distillation / student-training notes and configs

---

## Bottom line

The repository is now in a strong execution-ready state.

It has already learned a great deal from bounded stop-vs-act refinement, and it is now organized around the next serious empirical question:

**can selectively trusted, higher-fidelity oracle ACT-vs-STOP labels unlock a better lightweight stop-vs-act student than the current default training path?**
