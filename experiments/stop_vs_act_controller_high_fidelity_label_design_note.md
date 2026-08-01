# Stop-vs-act higher-fidelity offline label-generation design note

## Context and diagnosis

The stop-vs-act controller framing remains the best near-term control interface in this repo, and the current default (`proxy_best_other_gain`) remains the anchor baseline.

However, after bounded passes on:
- uncertainty/threshold refinements,
- instability guard-bands,
- one-step counterfactuals,
- small-horizon ACT-vs-STOP,
- repeated local averaging,
- matched-RNG comparators,
- one-step policy-coupled STOP,
- slightly longer-horizon policy-coupled STOP,

the empirical pattern is now consistent with **diminishing returns from lightweight local target tweaks**.

## 1) Why lightweight local target tweaks likely saturated

The latest passes suggest the residual error is not mainly from classifier capacity or a single variance trick. It is more likely due to supervision fidelity limits:
- local bounded comparators are still shallow proxies for downstream opportunity cost,
- STOP semantics remain approximate under constrained local rollouts,
- small changes to local estimators shift noise characteristics but do not reliably improve controller outcomes.

## 2) Most justified higher-fidelity labels now

The highest-value next label type is:

**offline oracle-distilled ACT-vs-STOP action-gap labels under budget-preserving policy-coupled futures**, generated with deeper and more expensive branch completion rollouts than current lightweight passes.

Concretely, each supervision point should include a stronger estimate of:
- `Q_oracle(ACT_here_now | state, remaining_budget)`
- `Q_oracle(STOP_here_now | state, remaining_budget)`
- `oracle_action_gap = Q_oracle(ACT) - Q_oracle(STOP)`

with STOP explicitly preserving and reallocating compute under the same global budget accounting.

## 3) Stronger teacher/oracle signal in this repo

In this project, the cleanest teacher is:

**an offline compute-heavier allocator/rollout teacher that performs deeper policy-coupled branching simulations and returns paired ACT-vs-STOP value estimates from the same snapshot.**

Not a new controller family; rather, a stronger labeler for the same stop-vs-act learner.

## 4) What should be generated later (heavy-compute phase)

When heavier compute is available, generate an offline oracle-labeled dataset with:
- state features at each decision point,
- paired ACT/STOP oracle values from shared snapshots,
- oracle action-gap and confidence/variance estimates,
- label provenance metadata (teacher config, horizon/depth, rollout count, seed policy),
- train/validation/test splits keyed by instance.

Recommended heavy outputs:
1. `oracle_stop_vs_act_labels.jsonl` (row-wise labels + metadata)
2. `oracle_label_manifest.json` (teacher config and run provenance)
3. `oracle_label_quality_report.json` (coverage, uncertainty, calibration diagnostics)

## 5) What to prototype now (without overclaiming)

A lightweight bridge artifact is appropriate now:
- define and freeze the **target schema + run manifest format**,
- provide a tiny dry-run generator that emits schema-conformant rows with current lightweight estimates and placeholder oracle fields,
- avoid claiming these rows are high-fidelity oracle labels.

This keeps the pipeline ready for the future heavy teacher without pretending that heavy supervision has already been produced.

## Conservative conclusion

Current bounded evidence supports a phase transition:
- keep default stop-vs-act baseline unchanged for near-term comparisons,
- stop spending primary effort on minor local target tweaks,
- prioritize a well-specified offline oracle-distillation data phase as the next major supervision upgrade.
