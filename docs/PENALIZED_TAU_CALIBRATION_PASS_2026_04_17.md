# Penalized tau calibration pass (2026-04-17)

## Context

After branch-specific `delta_c` was introduced, defer remained too diffuse because tau remained broadly additive and often larger than the penalized margin in non-hard regions.

## Tau diagnosis (current code before this pass)

Previous tau form in penalized regime was effectively:

- `tau = base + relative_value_scale + uncertainty_term + budget_term`

with uncertainty and budget terms always added, regardless of whether the pair was actually in a known ambiguity slice.

This made tau too globally aggressive and defer too diffuse off true hard cases.

## Minimal options considered

1. **Global coefficient shrink only**
   - smallest change, but likely fragile and not slice-selective.
2. **Selective ambiguity-gated uncertainty/budget terms** (**chosen**)
   - keep baseline tie band, reduce uncertainty/budget amplification in non-hard slices.
3. **Hard cap tied to penalized gap scale** (**also chosen as optional small safeguard**)
   - prevents tau from overwhelming observed penalized margin scale.

## Implemented fix

In `scripts/build_bruteforce_target_regimes.py`:

- Added `--penalized-tau-mode`:
  - `legacy_additive_v1` (backward-compatible default)
  - `selective_ambiguity_gate_v1`
- Added selective controls:
  - `--penalized-tau-easy-uncertainty-multiplier`
  - `--penalized-tau-easy-budget-multiplier`
  - `--penalized-tau-gap-cap-multiplier`
- New mode behavior:
  - identify hard ambiguity via near-tie / adjacent-rank / disagreement indicators,
  - apply full uncertainty+budget tau on hard slices,
  - downscale these terms on easy slices,
  - optional tau cap relative to penalized gap scale.
- Added row-level tau auditability in `penalized_tau_components`:
  - mode, hard flag, effective uncertainty/budget terms, pre-cap tau, cap multipliers.

## Bounded validation artifacts

Primary outputs:

- `outputs/branch_label_bruteforce_learning/tau_calibration_pass_20260417/tau_calibration_summary.json`
- `outputs/branch_label_bruteforce_learning/tau_calibration_pass_20260417/tau_calibration_summary.md`

Compared three stages:

1. before branch-specific `delta_c` + old tau
2. after branch-specific `delta_c` + old tau
3. after branch-specific `delta_c` + selective tau fix

## Best bounded setting (this pass)

- `nt_l0.20_t0.02_eu0.10_cap1.50`

It reduced defer diffusion materially while preserving hard-case defer concentration and improved accepted-accuracy/coverage versus earlier penalized settings in this bounded pass.

## Commands used

- build regimes with selective tau mode:
  - `python scripts/build_bruteforce_target_regimes.py ... --penalized-delta-c-mode branch_feature_proxy_v1 --penalized-tau-mode selective_ambiguity_gate_v1 ...`
- evaluate formulations:
  - `python scripts/run_ternary_or_abstain_branch_comparison_experiment.py ... --regimes all_pairs,quality_mixed_trust,partial_order_incomparable,penalized_marginal_defer --feature-set v2`

## Caveats

- This is a bounded run on current local validation corpus (80 states, gsm8k-only, approx-only).
- Before broader rollout, rerun on larger canonical corpora and multi-dataset slices.
