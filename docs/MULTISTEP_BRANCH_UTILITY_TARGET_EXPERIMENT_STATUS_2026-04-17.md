# MULTISTEP branch-utility target experiment status (2026-04-17)

## Scope and framing (canonical)
This is a **bounded target-semantics experiment** in canonical fixed-budget branch-allocation / frontier-allocation framing.

- Objective: test whether a small-horizon multi-step candidate target improves hard close-branch discrimination.
- Constraint adherence: reused canonical target regime builder, canonical learning-table preparation, and strict matched pairwise evaluation path; no broad redesign.

## Insertion points inspected before implementation
1. `scripts/build_bruteforce_target_regimes.py`
   - Existing candidate/pair regime construction and per-regime artifact writing.
   - Existing pairwise target semantics hooks (`allocation_regret_target`, tie-aware targets) confirmed as clean insertion point for a new regime.
2. `experiments/bruteforce_branch_allocator.py`
   - Pointwise model target hard-coded to `estimated_value_if_allocate_next`; minimal extension added to permit configurable candidate target field.
3. Existing evaluation path
   - Reused `load_label_artifacts` + `prepare_learning_tables` + pairwise test-slice metrics on canonical pair labels.
   - Added bounded runner for multi-step target ablation and diagnostics only.

## Exact multi-step target definition
Regime names:
- `multistep_branch_utility_target_k1` (ablation)
- `multistep_branch_utility_target_k3` (main)

For candidate branch `b` in state `s`:
- One-step base value: `v1 = estimated_value_if_allocate_next`.
- Continuation signal from existing artifact: `best_followup_allocation`.
- Let `u_self` be the follow-up allocation units assigned to the same branch index as `b`.
- Horizon cap for k: `u_cap = min(max(u_self, 0), k-1)`.
- Ratio: `r = u_cap / max(1, k-1)` (for `k=1`, `r=0`).
- Multi-step target: `utility_k = v1 * (1 + lambda * r)`, with `lambda=0.35`.

In this run:
- `k1` gives `utility_1 == v1` (one-step analogue).
- Main horizon: `k3`.

Why materially different:
- Uses continuation-allocation mass from `best_followup_allocation` to encode value of allocating additional near-term compute to the same branch, not just one-step utility.

## Commands run
```bash
python scripts/build_bruteforce_target_regimes.py \
  --labels-dir outputs/branch_label_bruteforce_targets/target_semantics_upstream_20260417/regime_all_pairs_approx \
  --output-dir outputs/branch_label_bruteforce_targets \
  --run-id multistep_branch_utility_target_20260417 \
  --pair-strategies all_pairs,multistep_branch_utility_target_k1,multistep_branch_utility_target_k3 \
  --near-tie-margin 0.03

python scripts/run_multistep_branch_utility_target_experiment.py \
  --targets-root outputs/branch_label_bruteforce_targets/multistep_branch_utility_target_20260417 \
  --run-id multistep_branch_utility_target_eval_20260417 \
  --output-root outputs/branch_label_bruteforce_learning \
  --seeds 11,29,47 \
  --feature-set v3 \
  --near-tie-margin 0.03
```

## Main metrics (aggregate, matched on canonical baseline pair labels)
From `outputs/branch_label_bruteforce_learning/multistep_branch_utility_target_eval_20260417/aggregate_comparison_summary.json`:

- Canonical baseline:
  - accepted accuracy: **0.5595**
  - near-tie accepted accuracy: **0.2000**
  - adjacent-rank accepted accuracy: **0.5460**
- `k1` ablation:
  - accepted accuracy: **0.5952** (delta +0.0357)
  - near-tie accepted accuracy: **0.2000** (delta +0.0000)
  - adjacent-rank accepted accuracy: **0.4794** (delta -0.0667)
- `k3` main:
  - accepted accuracy: **0.7063** (delta +0.1468)
  - near-tie accepted accuracy: **0.6000** (delta +0.4000)
  - adjacent-rank accepted accuracy: **0.6381** (delta +0.0921)

Ablation (`k3 - k1`):
- accepted accuracy: **+0.1786**
- near-tie accepted accuracy: **+0.4667**
- adjacent-rank accepted accuracy: **+0.2254**

## Target-difference diagnostics
- One-step vs multi-step top-branch disagreement by test state:
  - `k1`: disagreement rate **0.000** across seeds.
  - `k3`: disagreement rates **0.333, 0.333, 0.000** (seed-wise).
- Target distribution shift:
  - overall target mean increases from ~`0.7387` (`k1`) to ~`0.8155` (`k3`) due to continuation-ratio boost.

## Assumptions and caveats
1. `best_followup_allocation` index order is assumed to align with state candidate order preserved in candidate artifacts.
2. Multi-step utility is a bounded proxy (`best_followup_allocation`-weighted), not exact re-simulation of fixed `k` forced allocations.
3. Support is very small in this bounded run (per-seed test pairs: 7, 12, 4), so variance is high.
4. Some diagnostics have sparse non-near-tie test-state coverage in this corpus slice.

## Hard conclusion (continue or drop)
**Decision: DROP for now (no-go to continue directly).**

Reasoning:
- The bounded `k3` proxy shows positive deltas on hard slices and accepted accuracy in this small run, but evidence is **not yet credible enough** under current support size to pass continuation bar for a new target direction.
- The direction is not rejected conceptually, but with current artifact fidelity + sample size this result is too unstable for continuation commitment.
- Recommended next action: switch to another idea unless this can be rerun on a materially larger canonical support slice with the same bounded protocol.
