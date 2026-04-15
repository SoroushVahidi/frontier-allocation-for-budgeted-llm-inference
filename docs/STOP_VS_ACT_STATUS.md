# Stop-vs-act status (canonical supporting note)

## Purpose

This note summarizes what has actually been implemented and learned from the stop-vs-act line so far.

Use it to answer:
- what was built,
- what bounded experiments were run,
- what improved,
- what failed to improve,
- what remains the current best stop-vs-act setup,
- and what the next step should be.

This is a **canonical supporting note** for the current project phase.

---

## What has been implemented

The repo now contains a runnable lightweight stop-vs-act pipeline built around bounded simulation-backed experiments.

Core pieces include:
- `experiments/stop_vs_act_controller.py`
- `scripts/build_stop_vs_act_dataset.py`
- `scripts/train_stop_vs_act_controller.py`
- `scripts/run_new_paper_stop_vs_act_controller.py`

Additional bounded evaluation / diagnostic passes were also added, including:
- robustness sweep,
- diagnosis + targeted revision pass,
- label-refinement pass,
- counterfactual target pass,
- small-horizon ACT-vs-STOP target pass.

The stop-vs-act line is therefore no longer only a planned direction; it is an implemented experimental branch with multiple bounded follow-up passes.

---

## What has been learned so far

### 1. Initial feasibility was promising
The first lightweight stop-vs-act run was encouraging enough to justify deeper bounded validation, but it was only a feasibility signal and not sufficient for strong claims on its own.

### 2. Robustness versus the heuristic baseline is mixed
The bounded robustness sweep showed that learned stop-vs-act is competitive and often better than the uncertainty-only baseline, but it is still mixed versus the stronger heuristic baseline.

The important practical conclusion is:
- stop-vs-act is **promising**,
- but not yet stable enough to claim robust superiority.

### 3. ACT labels are sparse and interact badly with uncertainty
The diagnosis pass found that ACT-positive labels are relatively sparse and that many of them are also marked uncertain. This means generic uncertainty suppression can remove useful positive supervision.

### 4. One targeted uncertainty-handling revision helped somewhat
A targeted revision that preserved uncertain ACT examples while only downweighting uncertain STOP examples improved over the prior best bounded setup on a small matched grid.

This was a useful result, but not strong enough by itself to declare the method solved or universally better.

### 5. Simple threshold / uncertainty-band refinements did not solve the deeper issue
A later label-refinement pass reduced uncertainty coverage but did not improve controller-level performance versus the heuristic baseline. This suggests the main bottleneck is deeper than threshold tuning.

### 6. Two counterfactual target revisions were informative but not replacement-level improvements
Two lightweight counterfactual target ideas were tested:
- one-step here-vs-best-other counterfactual target,
- small-horizon ACT-vs-STOP target.

Both were reasonable and informative, but neither clearly beat the current default stop-vs-act setup in bounded matched tests.

### 7. Current bottleneck is deeper target quality / noise control
At this point, the stop-vs-act line appears to be limited less by classifier choice and more by the quality and stability of the local target itself.

The current evidence suggests that the next step should focus on:
- target stabilization,
- variance reduction,
- and better local target estimation,
rather than more threshold-only tuning.

---

## Current best interpretation of the stop-vs-act line

The most honest current interpretation is:

- stop-vs-act remains the most promising near-term controller framing,
- the pipeline is implemented and auditable,
- the current default stop-vs-act setup remains the best bounded baseline within this line,
- but later revisions have not yet produced a clean replacement.

So this direction should currently be treated as:
- **implemented**,
- **important**,
- **promising but mixed**,
- and still under active target-design refinement.

---

## What should remain default for now

Keep the current default stop-vs-act setup as the working baseline for this line.

Do **not** replace it yet with:
- the instability-guard-band label refinement,
- the one-step here-vs-best-other counterfactual target,
- or the small-horizon ACT-vs-STOP target,
unless stronger bounded evidence appears later.

---

## Safe claims from the stop-vs-act line

Safe to say now:
- A budget-conditioned stop-vs-act controller has been implemented.
- The line is promising and useful enough to justify continued bounded study.
- The strongest current limitation is local target quality / noise control.
- Some targeted revisions improved locally, but no later revision has clearly displaced the current default setup.

Not safe to say now:
- That stop-vs-act is already a robust winner versus the best heuristic baseline.
- That a counterfactual target revision has already solved the supervision problem.
- That simple threshold or uncertainty tuning is sufficient.

---

## Current next move

The next best move is **not** another minor local target tweak.

After multiple bounded local passes (including matched comparator and policy-coupled STOP variants), the most plausible bottleneck is now supervision fidelity rather than another lightweight estimator adjustment.

So the next move is:
- keep the current default setup as the anchor baseline,
- transition planning toward higher-fidelity offline label generation,
- and prepare an oracle/distillation path that can be executed when heavier compute is available.

Appropriate immediate actions:
- freeze a canonical schema for oracle-style ACT-vs-STOP labels,
- add a tiny scaffold/dry-run generator for that schema,
- define heavy-run manifests (teacher objective, horizon/depth, rollout counts, provenance fields),
- avoid claiming heavy-label benefits before those labels are actually generated.

---

## Bottom line

The stop-vs-act line has matured from a planning idea into a real experimental branch.

The repo should now reflect the following summary:
- it has been implemented,
- it has been tested through multiple bounded passes,
- it remains one of the most important near-term method directions,
- and the main unresolved issue is now label fidelity for ACT-vs-STOP supervision (best addressed by planned offline oracle/distillation data generation).
