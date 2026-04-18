# Canonical objective and function stack (2026-04-18)

## Purpose

This note freezes the repository's **single top-level objective** and the now-explicit **surrogate decomposition** used for branch-allocation decisions under a fixed budget.

This is a targeted objective/function implementation pass (not a broad method-family search).

---

## 1) Unique top-level objective (frozen)

> **Maximize expected final task correctness/utility under a fixed total compute budget.**

Operational form:
- at each decision state, choose among `expand(i)`, `expand(j)`, or `commit_now`,
- where the objective is final utility under total-budget constraint, not local score maximization in isolation.

Canonical machine-readable anchor:
- `outputs/objective_stack_20260418/canonical_objective.json`

---

## 2) Explicit surrogate decomposition

We now separate three branch-level surrogate quantities:

### A. `process_quality(b)`
Meaning:
- local reasoning quality/progress so far,
- does **not** imply branch is commit-ready by itself.

Current proxy family:
- completion signal and answer-evidence strength,
- semantic incompleteness inverse penalty.

### B. `target_completion(b)`
Meaning:
- probability branch has actually reached the asked target variable and is commit-ready,
- explicitly penalizes intermediate-result traps.

Current proxy family:
- completion signal + answer evidence,
- explicit semantic incompleteness penalty from intermediate-result failure work.

### C. `continuation_value(b)`
Meaning:
- expected value of allocating one more compute unit to branch `b` under remaining budget,
- remains the canonical expansion/default signal.

Current proxy family:
- `expected_value_if_branch`, `estimated_value_if_allocate_next`, `multistep_branch_utility_target_k3`.

Canonical machine-readable anchor:
- `outputs/objective_stack_20260418/surrogate_quantity_map.json`

---

## 3) Explicit metalevel decision rule

Canonical rule:
1. Rank expansions by `continuation_value`.
2. Build incumbent commit-quality from `target_completion + process_quality`.
3. Default action: expand continuation-top branch.
4. Near ties / disagreement slices only: apply bounded local correction toward higher `target_completion` if continuation-value drop is bounded.
5. Allow `commit_now` when bounded commit-quality dominates expansion-quality.

Canonical machine-readable anchor:
- `outputs/objective_stack_20260418/decision_rule_schema.json`

---

## 4) Mapping old function families into the new schema

### Canonical mappings
- `multistep_branch_utility_target_k3` -> `continuation_value`
- `estimated_value_if_allocate_next` -> `continuation_value`
- `branch_completion_score` -> `target_completion` surrogate
- `branch_answer_evidence_score` -> `target_completion` surrogate
- `semantic_incompleteness_score` -> target-completion penalty

### Decision modifiers / local gates
- `completion_bonus_policy`
- `completion_outside_gate_policy`
- `completion_tie_resolution_policy`
- near-tie / instability / outside-option gates

These are useful **local modifiers**, not global objective replacements.

### Exploratory / non-canonical global targets
- discounted multistep target family,
- compute-response-curve target,
- rank-instability target,
- penalized-marginal defer targets,
- other broad weighting overlays.

Canonical machine-readable anchor:
- `outputs/objective_stack_20260418/legacy_to_canonical_mapping.json`

---

## 5) Why this decomposition is better than one undifferentiated branch score

This decomposition directly addresses observed failure evidence:
- previously, a single score could reward a branch that computed a correct intermediate quantity but did not answer the asked variable,
- now, `continuation_value` and `target_completion` are explicit and separable,
- local corrections are bounded to disagreement/near-tie slices instead of replacing the global objective.

Net effect:
- clearer objective semantics,
- clearer decision semantics (`expand i`, `expand j`, `commit_now`),
- reduced objective drift from ad hoc score blending.

---

## 6) Bounded evaluation summary (this pass)

This pass includes bounded artifact-based checks across:
- saved failure slice,
- near-tie disagreement slice,
- bounded oracle-alignment comparison,
- baseline learned branch score vs completion-aware variant vs decomposed-objective proxy behavior,
- broader accepted-metric reference from canonical multistep validation artifact.

Primary evaluation bundle:
- `outputs/objective_stack_20260418/bounded_evaluation_summary.json`

Interpretation from bounded evidence:
- clear **local disagreement-slice sensibility** and objective/semantic clarity gains,
- oracle-alignment improvement over baseline in bounded observability slices,
- broader accepted metrics still primarily anchored by current multistep-k3 canonical validation line.

So in this pass:
- improvement is strongest in **objective clarity + localized failure handling**,
- not yet evidence of a broad global metric displacement claim by decomposition alone.

---

## 7) Canonical status after this pass

Canonical now:
- one unique top-level objective,
- three explicit surrogate quantities,
- one explicit metalevel decision rule,
- explicit legacy/exploratory classification.

Still exploratory:
- broader target-family replacements,
- global replacement of continuation-value objective,
- broad benchmark claims from bounded disagreement slices.
