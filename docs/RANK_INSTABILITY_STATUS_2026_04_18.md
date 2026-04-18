# Rank-instability supervision status (2026-04-18)

## Insertion-point summary

This bounded pass adds a first-class **rank-instability target family** to the canonical target-regime builder and a runnable experiment line for branch allocation under fixed budget.

Inserted components:
- `rank_instability_target_v1` in `scripts/build_bruteforce_target_regimes.py`.
- `scripts/run_rank_instability_experiment.py` for matched baseline comparison.
- machine-readable outputs under:
  - `outputs/branch_label_bruteforce_targets/rank_instability_target_20260418/`
  - `outputs/branch_label_bruteforce_learning/rank_instability_eval_20260418/`

## Exact instability target definition (bounded, explicit)

For each state, derive four auditable orderings from stored artifacts:
1. one-step value (`estimated_value_if_allocate_next`),
2. multistep utility k3,
3. discounted multistep utility (`gamma=0.8`),
4. compute-response-curve scalar.

State instability (`rank_instability_state_label=True`) iff:
- top-1 identity disagrees across signals (at least one disagreement), and
- the minimum top-1 margin across these signals is at most `0.03`.

State score (`rank_instability_state_score`) is a bounded [0,1] blend of disagreement count and margin fragility.

Pair instability (`rank_instability_pair_label=True`) iff:
- pairwise orientation disagrees with one-step orientation for at least 2 of {multistep, discounted, curve}, and
- pair margin is at most `0.03`.

Pair score (`rank_instability_pair_score`) is a bounded disagreement fraction (`disagreement_count / 3`).

Primary winner label for this regime remains conservative and explicit:
- winner supervision remains anchored to multistep-k3 ordering (`label_source=rank_instability_target_multistep_k3_anchor`),
- instability is stored as an additional first-class supervision object.

## How instability is derived from stored artifacts

No new simulator was introduced. Signals are derived from already stored label artifacts and existing target constructors:
- one-step value from candidate labels,
- multistep utility from best-followup allocation self-mass proxy,
- discounted utility from existing discounted multistep construction,
- compute-response curve scalar from existing response-curve target construction.

All derived instability fields are materialized directly into candidate and pairwise regime artifacts.

## How instability affects decisions

Bounded policy used in `run_rank_instability_experiment.py`:
- train a pairwise winner model on `rank_instability_target_v1`,
- train an auxiliary instability head on pair rows (`rank_instability_pair_label`),
- defer only when:
  - predicted top-2 instability probability is high **or** state instability label is true,
  - and top-2 score gap is small (`<= 1.5 * decision_margin_threshold`).

This intentionally tests a single conservative defer path (not a large controller family).

## Commands run

1. Build target regimes:

```bash
python scripts/build_bruteforce_target_regimes.py \
  --labels-dir outputs/branch_label_bruteforce_targets/compute_response_curve_target_20260418/regime_all_pairs \
  --output-dir outputs/branch_label_bruteforce_targets \
  --run-id rank_instability_target_20260418 \
  --pair-strategies all_pairs,multistep_branch_utility_target_k3,discounted_multistep_branch_utility_target_gamma080,compute_response_curve_target_h123,rank_instability_target_v1 \
  --near-tie-margin 0.03 \
  --rank-instability-discount-gamma 0.8 \
  --rank-instability-margin-threshold 0.03 \
  --rank-instability-min-disagreement-count 1
```

2. Run bounded experiment:

```bash
python scripts/run_rank_instability_experiment.py \
  --targets-root outputs/branch_label_bruteforce_targets/rank_instability_target_20260418 \
  --run-id rank_instability_eval_20260418 \
  --output-root outputs/branch_label_bruteforce_learning \
  --seeds 11,29,47 \
  --feature-set v3 \
  --near-tie-margin 0.03 \
  --baseline-regime all_pairs \
  --multistep-regime multistep_branch_utility_target_k3 \
  --discounted-regime discounted_multistep_branch_utility_target_gamma080 \
  --curve-regime compute_response_curve_target_h123 \
  --rank-instability-regime rank_instability_target_v1 \
  --instability-threshold 0.35 \
  --decision-margin-threshold 0.10
```

## Key metrics

From `outputs/branch_label_bruteforce_learning/rank_instability_eval_20260418/aggregate_comparison_summary.json`:

- `multistep_k3_current` accepted accuracy mean: **0.6667**.
- `rank_instability_aware` accepted accuracy mean: **0.5000** (delta vs multistep: **-0.1667**).
- near-tie accepted accuracy mean: **0.6667** (multistep) vs **0.1667** (instability-aware).
- strict near-tie+adjacent accepted accuracy mean: **0.6667** vs **0.1667**.
- overconfident wrong rate on failures: **0.1111** (multistep) vs **0.8333** (instability-aware).

Target-side support diagnostics:
- instability state-label rate: **0.1868**,
- instability pair-label rate: **0.0769**,
- mean pair disagreement count: **0.3956**.

## Caveats

- Bounded support is small (very few test states per seed in this pass).
- Defer policy rarely activated under this exact bounded setup (coverage remained 1.0 in this run), so this should be read as a first insertion-point validation rather than a strong policy sweep.
- Current instability construction uses deterministic derived targets from stored proxies; no stochastic perturbation simulator was added.

## Hard conclusion

In this bounded pass, **rank-instability supervision did not improve branch allocation beyond current multistep k3**. It currently provides **diagnostic value and instrumentation**, but not a performance win yet. The strongest practical continuation is to keep the instability object, then retune or redesign the decision-use path (especially defer activation and uncertainty coupling) before claiming allocation gains.
