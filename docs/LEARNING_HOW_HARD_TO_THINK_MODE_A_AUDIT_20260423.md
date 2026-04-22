# Audit: learning_how_hard_to_think_mode_a (2026-04-23)

## Scope audited

- Config: `configs/learning_how_hard_to_think_mode_a_v1.json`
- Runner: `scripts/run_learning_how_hard_to_think_mode_a.py`
- Registry entries: `configs/external_baselines_registry.json`
- Baseline docs: `external/learning_how_hard_to_think/README.md`, `docs/learning_how_hard_to_think_integration.md`
- Output artifacts: `outputs/learning_how_hard_to_think_mode_a/20260423T011500Z/`

## Scientific validity assessment

### 1) Does it implement adaptive best-of-k meaningfully?

Yes, after this pass:

- The adapter runs a policy bundle under matched budget accounting.
- `learning_how_hard_to_think_mode_a` allocates candidate slots via hardness-weighted redistribution.
- Comparator policies include uniform/fixed-k/easy→hard/hard→easy under the same substrate.

### 2) Hardness signal quality

- Current signal is still heuristic (length/digits/operators/multi-step lexical cues).
- It is deterministic and auditable, but may not track true reasoning difficulty robustly.
- This is acceptable for conservative adapter status but limits paper strength.

### 3) Budget accounting fairness

- Budget unit is explicit (`actions_per_example`).
- Actions are converted to candidate slots through `candidate_action_cap`.
- All policies are evaluated under the same conversion and action accounting.
- Reporting includes unspent-action accounting.

### 4) Risk of artifact-driven performance

- A prior artifact (degenerate budgets where all policies collapsed to same allocation) is fixed by using budgets that force non-uniform allocation (`[5,7]`).
- Diagnostic contrast against both ordering baselines and fixed/uniform baselines is now available.

## Empirical diagnostic (run: 20260423T011500Z)

Source files:

- `comparison_summary.csv`
- `diagnostic_summary.json`
- `diagnostic_report.md`

Observed behavior:

- At budget 5, mode_a underperforms uniform/fixed/easy→hard and is close to hard→easy.
- At budget 7, mode_a remains below uniform/fixed, ties hard→easy, slightly beats easy→hard.
- Allocation-hardness rank correlation is positive and high for mode_a, so behavior is driven by redistribution rather than implementation no-op.

Interpretation:

- The adapter is functioning as intended mechanically.
- Current heuristic hardness signal is not yet yielding strong gains in this substrate.

## Paper usability recommendation

**Recommendation: keep in repo but not main paper-facing baseline table yet (`repo_only_not_paper_facing_yet`).**

Rationale:

- comparator is honest and auditable,
- fairness accounting is now solid,
- but current results do not show stable strength vs simple matched-compute controls.

## Claim boundary (must keep)

- `adapter_based`
- `control_equivalence: adjacent`
- `paper-inspired matched-substrate comparator`
- `not an official reproduction`
