# Current repository status (oracle-phase ready)

## Purpose

This note is the current high-level status summary for the repository after:
- the bounded stop-vs-act target-refinement phase,
- the transition to higher-fidelity label planning,
- the oracle-label pilot protocol work,
- and the pilot state-selection / extraction preparation.

Use this as the best single note for understanding the current state of the project.

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

The repository is in a good research state.

It now has:
- strong framing,
- strong provenance,
- a substantial implemented stop-vs-act branch,
- a clear record of bounded negative results,
- and a concrete bridge into the next high-fidelity supervision phase.

The repo is no longer only exploring ideas. It now has a structured transition from lightweight target engineering to oracle-label pilot readiness.

---

## What is strong now

### 1. Infrastructure and framing
- Frontier/controller infrastructure is present.
- Anti-collapse and comparative-audit work is present.
- Branch-scorer experimentation is substantial.
- Stop-vs-act is implemented and reproducibly testable.

### 2. Provenance quality
- The repo now contains multiple bounded stop-vs-act passes.
- Negative results were retained instead of hidden.
- Notes increasingly reflect safe claims rather than overclaiming.

### 3. Next-phase readiness
The repo now has concrete operational preparation for the first oracle-label pilot, including:
- a pilot protocol,
- a pilot config,
- an oracle-output validator,
- a pilot state-selection protocol,
- and a deterministic pilot-state manifest builder.

That is a major improvement over a vague “we need better labels” stage.

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

### B. Oracle-label transition phase
The repo now also includes:
- a diagnosis/design note for moving to higher-fidelity supervision,
- a heavy-label planning manifest,
- a lightweight oracle-label scaffold,
- an execution-ready pilot protocol,
- a pilot output validator,
- a state-selection protocol,
- a deterministic pilot-state manifest builder.

So the repository has moved beyond only tweaking local labels. It now supports a real pilot for future oracle supervision.

---

## What has been learned

### High-confidence conclusions
1. The stop-vs-act controller framing remains the best near-term controller framing.
2. The current default stop-vs-act setup still remains the best bounded baseline inside that line.
3. The main bottleneck is not infrastructure and not mainly controller class.
4. Lightweight local target tweaking has likely reached diminishing returns.

### Important negative conclusions
1. Threshold and uncertainty tuning were not enough.
2. One-step and short-horizon counterfactual target variants did not replace the default.
3. Stabilization helped some target-side metrics but not controller outcomes.
4. Matched randomness alone did not solve the comparator problem.
5. One-step and slightly longer-horizon policy-coupled STOP baselines still did not replace the default.

### Current interpretation of those results
These are useful negative results. They justify the current move toward higher-fidelity supervision.

---

## Current main bottleneck

The main bottleneck is now best described as:

**insufficient label fidelity from lightweight local target construction.**

More specifically:
- lightweight local ACT-vs-STOP labels appear too weak as surrogates,
- STOP semantics remain difficult to capture faithfully with small bounded local approximations,
- and controller gains likely need stronger teacher labels rather than another minor target tweak.

This is more precise than earlier generic “label noise” language.

---

## What the repository is doing now

The repository is currently in this phase:

**oracle-label pilot readiness and label-fidelity engineering.**

That means the repo is now primarily doing:
- preparing a higher-fidelity teacher-signal phase,
- making the first oracle-label pilot operationally reproducible,
- defining how states will be selected and validated,
- and preserving the current default stop-vs-act setup as the anchor baseline for later comparison.

That means the repo is not currently centered on:
- more threshold-only stop-vs-act tweaks,
- more small local comparator variants as the main plan,
- or a search for more existing external data as the immediate fix.

---

## Current canonical interpretation

### Canonical now
- overall fixed-budget frontier-allocation framing,
- stop-vs-act as the main near-term controller family,
- current default stop-vs-act setup as the anchor baseline,
- oracle-label pilot planning and execution-readiness artifacts,
- conservative claim discipline.

### Exploratory but still useful
- non-default stop-vs-act target variants,
- matched and policy-coupled comparator variants,
- auxiliary branch-scorer variants.

### Historical / provenance only
- older binary revise-routing artifacts,
- older phase notes that predate the oracle-label transition.

---

## What should happen next

### Immediate next step once compute is available
Execute the first oracle-label pilot on the fixed pilot-state manifest.

That means:
1. generate oracle ACT/STOP values on the selected pilot states,
2. produce oracle action-gap labels,
3. validate them with the pilot validator and quality gates,
4. only then proceed to distillation into the existing stop-vs-act controller family,
5. compare distilled results against the current default anchor baseline and strongest heuristic baseline.

### Immediate pre-compute note
One remaining practical item that still sits outside the current preparation layer is HPC run orchestration and runtime resource planning. That is an execution concern, not a conceptual gap.

---

## Safe wording now

Safe to say:
- the repository has strong framing and strong infrastructure,
- stop-vs-act is implemented and important,
- lightweight target engineering produced useful but mostly non-promoted results,
- the current default setup remains the best bounded baseline,
- the repo is now prepared for a first oracle-label pilot,
- the next likely gains depend on better label fidelity rather than another small local tweak.

Not safe to say:
- the oracle-label phase has already run,
- the stop-vs-act problem is solved,
- the current learned controller is already robustly better than the strongest heuristic baseline,
- the future heavy phase is guaranteed to succeed.

---

## Recommended read order now

1. `docs/CURRENT_REPO_STATUS_2026_04_15_ORACLE_READY.md`
2. `docs/ORACLE_PHASE_EXECUTION_READINESS_2026_04_15.md`
3. `docs/CURRENT_REFERENCES_SUPPLEMENT_2026_04_15_ORACLE_PHASE.md`
4. `docs/CURRENT_REPO_ASSESSMENT_2026_04_16.md`
5. `docs/NEXT_PHASE_PLAN_2026_04_16.md`
6. protocol / config / validator / manifest notes for the oracle pilot

---

## Bottom line

The repository is now in a strong transition state.

It has already learned a lot from lightweight stop-vs-act refinement, and it is now organized around the next serious question:

**can higher-fidelity paired ACT-vs-STOP oracle labels unlock better supervision than lightweight local target engineering could provide?**
