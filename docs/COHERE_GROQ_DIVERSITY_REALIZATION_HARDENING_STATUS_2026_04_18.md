# Cohere/Groq diversity-realization hardening status (2026-04-18)

## Purpose of this pass

This pass was a **focused hardening pass** inside the existing broad diversity/aggregation family.

Targeted bottleneck:
- low realized answer-level diversity under real provider generation noise.

Explicit non-goals:
- no new-family search,
- no simulator-only replacement for real checks.

## Hardening mechanism added

Implemented method variant:
- `answer_group_coverage_floor_v1`

Mechanism:
- add a **plausibility-gated minimum answer-group coverage floor** early in the action sequence,
- while answer-group coverage is below target, allow bounded branch selection overrides toward plausible undercovered groups,
- cap forced steps to prevent degeneration into uniform exploration,
- retain continuation-value scoring and answer-support aggregation as core policy logic.

Concrete rule settings in this pass:
- `min_answer_groups_before_concentration=2`
- `coverage_floor_min_actions=2`
- `coverage_floor_max_actions=7`
- `coverage_floor_plausibility_threshold=0.46`
- `coverage_floor_max_forced_steps=2`

## How this differs from prior marginal-coverage logic

`marginal_coverage_diversity_v1` continuously reweights branch priorities with coverage/overlap terms.

`answer_group_coverage_floor_v1` adds a stronger bounded intervention:
- it can temporarily override top-priority concentration,
- only inside a narrow early window,
- only for plausible undercovered groups,
- and only up to a fixed small forced-step budget.

So this is a hardening of the same family, not a new family.

## Providers and models used

Allowed/run providers for fresh real checks:
- Cohere: `command-r-plus-08-2024`
- Groq: `llama-3.3-70b-versatile`

What actually executed:
- Cohere executed bounded evaluation slices successfully.
- Groq preflight failed (`HTTP 403 / error code 1010`) in this environment, so no Groq evaluation rows were completed in this run.

## Comparison set (frozen)

Methods compared:
- `self_consistency_3`
- `broad_diversity_aggregation_v1`
- `broad_diversity_aggregation_strong_v1`
- `marginal_coverage_diversity_v1`
- `answer_group_coverage_floor_v1` (new hardening variant)

## Run scale completed

Configured real-run scale:
- datasets: `openai/gsm8k`, `HuggingFaceH4/MATH-500`, `olympiadbench`
- subset size per dataset: 2
- seeds: 1 (`11`)
- budgets: 1 (`6`)
- providers requested: Cohere + Groq

Observed completed scale:
- successful seed-level rows: 10
- successful example-level rows: 20
- coverage-floor examples evaluated: 4

Caveat:
- one Cohere dataset slice timed out (`olympiadbench`)
- Groq blocked at preflight, so this remains a **bounded/partial real-model pass**.

## Key outcomes

### Diversity-realization behavior

From `diversity_realization_diagnostics.json`:
- `broad_diversity_aggregation_v1`
  - realized diversity rate: 0.00
  - low-diversity realization rate: 1.00
- `answer_group_coverage_floor_v1`
  - realized diversity rate: 0.50
  - useful answer-distinct branch rate: 0.50
  - low-diversity realization rate: 0.50

Interpretation:
- the coverage-floor mechanism **did materially change branch-coverage behavior** on the bounded real run.

From `coverage_floor_activation_summary.json`:
- activation rate: 1.00
- mean forced steps: 1.25
- mean forced-step rate: 0.333

So the hardening logic was active and not dormant.

### Competitiveness vs self_consistency_3 and v1

From `aggregate_comparison_summary.json` (bounded run):
- `self_consistency_3`: 0.50 mean accuracy
- `broad_diversity_aggregation_v1`: 0.25 mean accuracy
- `answer_group_coverage_floor_v1`: 0.75 mean accuracy
- `marginal_coverage_diversity_v1`: 0.75 mean accuracy

Gaps:
- best broad in this run (`marginal_coverage_diversity_v1`) vs `self_consistency_3`: +0.25
- best broad vs `broad_diversity_aggregation_v1`: +0.50

For the new hardening variant specifically:
- vs `self_consistency_3`: +0.25
- vs `broad_diversity_aggregation_v1`: +0.50

Interpretation:
- in this bounded partial real slice, competitiveness **improved** and did not show an immediate accuracy penalty from stronger diversity realization.

## Residual-loss comparison status

Requested residual taxonomy fields are emitted in the machine-readable bundle.

In this run:
- `residual_loss_cases.json` is empty,
- `residual_loss_taxonomy.json` is empty,

because the selected best broad method did not produce SC-win/ours-loss aligned cases on completed rows.

## Hard conclusion

- The pass successfully implemented a focused real-noise diversity hardening mechanism inside the current broad family.
- The mechanism measurably increased realized diversity and useful answer-distinct branching on completed real rows.
- On this bounded partial run, broad-family competitiveness improved relative to `self_consistency_3` and clearly improved over `broad_diversity_aggregation_v1`.
- However, Groq execution did not complete due provider access failure in this environment, and one Cohere slice timed out, so confidence is still bounded and not paper-grade.

Next decisive action should be:
- rerun the same frozen comparison set after restoring Groq access and slightly expanding real scale, to test whether the diversity-realization gain and accuracy behavior persist.
