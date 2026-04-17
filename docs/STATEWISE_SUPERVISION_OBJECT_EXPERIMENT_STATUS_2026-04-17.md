# Statewise supervision-object experiment status (2026-04-17)

## Scope and canonical framing

This is a bounded fixed-budget branch-allocation / frontier-allocation experiment focused strictly on the canonical question:

- among active branches in a state, which branch should receive the next unit of compute?

No broad redesign was introduced; existing canonical data preparation and evaluation conventions were reused.

## Insertion-point summary (pre-implementation)

1. **Candidate-level target field**
   - Reused canonical candidate target `estimated_value_if_allocate_next` as the supervision signal for next-branch allocation order.
2. **State grouping**
   - Reused `state_id` grouping and existing candidate-state table construction from `prepare_learning_tables(...)`.
3. **Matched baseline**
   - Reused canonical pairwise baseline path (`train_models(...)` pairwise model) and existing accepted/hard-slice metric conventions.
4. **Minimal candidate-level learning path**
   - Reused existing pointwise ridge candidate scorer for the new statewise supervision object.
5. **Evaluation style / artifacts**
   - Reused strict-validation/canonical-pass reporting style: per-seed + aggregate + mode deltas + machine-readable manifests.

## Exact supervision object implemented

### `statewise_next_branch_value`

- Train candidate-level scorer on canonical candidate rows.
- Supervision target per candidate: `estimated_value_if_allocate_next`.
- Selection/evaluation rule: **statewise `argmax(predicted_value)`** for next-branch choice.

### Why this is materially different from canonical pairwise regimes

- Canonical baseline supervision is pairwise-local (i vs j winner labels).
- This experiment shifts supervision to **statewise candidate value ordering** and derives pair decisions only as a mapped diagnostic/evaluation view.

## Modes compared

1. `baseline_pairwise_canonical`
2. `statewise_next_branch_value`
3. `statewise_next_branch_binary_top1_only` (low-overhead ablation included)

## Implementation summary

Added a bounded experiment runner:

- `scripts/run_statewise_supervision_object_experiment.py`

This script:

- Loads canonical labels artifacts (`candidate_labels.jsonl`, `pairwise_labels.jsonl`, `state_summaries.jsonl`).
- Reuses canonical table/feature path (`prepare_learning_tables`).
- Trains matched models for each seed:
  - canonical pairwise baseline,
  - statewise value scorer (existing pointwise ridge),
  - optional binary top1 ablation (candidate binary logistic).
- Computes required metrics:
  - accepted accuracy,
  - coverage,
  - defer rate,
  - near-tie accepted accuracy,
  - adjacent-rank accepted accuracy,
  - per-seed and aggregate delta vs baseline.
- Computes candidate/statewise diagnostics:
  - statewise top1 agreement with oracle-next-branch,
  - near-tie-heavy state top1 agreement,
  - per-state candidate-count summary.

## Commands run

- `python scripts/run_statewise_supervision_object_experiment.py --labels-dir outputs/branch_label_bruteforce_targets/target_semantics_upstream_20260417/regime_all_pairs_approx --run-id statewise_supervision_object_20260417 --output-root outputs/branch_label_bruteforce_learning --seeds 11,29,47 --feature-set v2 --near-tie-margin 0.03`

(Also recorded in output note file listed below.)

## Output artifacts

Run directory:

- `outputs/branch_label_bruteforce_learning/statewise_supervision_object_20260417/`

Machine-readable outputs:

- `statewise_supervision_manifest.json` (config + manifest + per-seed + aggregate)
- `matched_summary_by_mode.json`
- `aggregate_comparison_summary.json`
- `per_seed_summary.json`
- `statewise_top1_agreement_diagnostics.json`
- `commands_assumptions_caveats.md`

## Main metrics (aggregate, seeds=11/29/47)

Baseline (`baseline_pairwise_canonical`):

- accepted accuracy: **0.4206**
- coverage: **1.0000**
- defer rate: **0.0000**
- near-tie accepted accuracy: **0.4000**
- adjacent-rank accepted accuracy: **0.4508**

Statewise value object (`statewise_next_branch_value`):

- accepted accuracy: **0.4008** (**delta -0.0198** vs baseline)
- coverage: **1.0000**
- defer rate: **0.0000**
- near-tie accepted accuracy: **0.2000** (**delta -0.2000**)
- adjacent-rank accepted accuracy: **0.3683** (**delta -0.0825**)
- statewise top1 agreement with oracle-next-branch: **0.3889**
- near-tie-heavy state top1 agreement: **0.1667**

Optional ablation (`statewise_next_branch_binary_top1_only`):

- accepted accuracy: **0.6230** (**delta +0.2024**)
- near-tie accepted accuracy: **0.5333** (**delta +0.1333**)
- adjacent-rank accepted accuracy: **0.5429** (**delta +0.0921**)
- statewise top1 agreement: **0.5556**

## Assumptions and caveats

- The evaluated target regime (`target_semantics_upstream_20260417/regime_all_pairs_approx`) has a small effective test-state count under these seeds (2–3 states per seed in this run), so variance is high.
- No defer head is introduced in this bounded experiment; coverage is 1.0 and defer rate is 0 by design.
- Statewise modes are mapped back to pairwise accepted/hard-slice metrics by induced pair predictions from candidate scores.
- Baseline statewise top1 agreement is not computed in this script for the pairwise baseline path (baseline is intentionally kept canonical pairwise-first).

## Hard conclusion (go / no-go)

### Decision on the requested supervision object: `statewise_next_branch_value`

**No-go / drop.**

Under matched bounded evaluation, `statewise_next_branch_value` fails the continuation bar:

- overall accepted accuracy declines,
- near-tie behavior declines materially,
- adjacent-rank behavior declines.

Given the goal of improving hard close-branch behavior without unacceptable deterioration in accepted accuracy, this value-target statewise object is **not useful enough to continue**.

### Interpretation

- This negative result suggests that simply switching from pairwise-local supervision to this particular statewise value target does not resolve the bottleneck in current canonical conditions.
- The optional binary top1 ablation is interesting but should be treated as **diagnostic only** in this run (small test-state support and different target semantics); it is not sufficient evidence to continue the value-aware statewise object direction.
