# Cohere strict hard-case adjudication rerun (2026-04-17)

## Scope

This pass intentionally **did not** repeat runtime-key verification.
`docs/COHERE_PRODUCTION_KEY_RUNTIME_VERIFICATION_2026_04_17.md` already established production-key readiness.

Goal here: test whether the earlier negative Cohere relabeling result was due to a loose replacement policy, by rerunning one bounded pass with stricter acceptance/gating only.

## Stricter policy used (single conservative design)

Pipeline kept the same as `scripts/cohere_adjudicate_hard_pairs.py`, but acceptance policy was tightened:

- adjudicate only the top hard subset (`--max-pairs 18`, same bounded scope as prior run),
- allow **hard replacement only if all are true**:
  1. Cohere winner is non-tie,
  2. confidence >= `0.90`,
  3. strict hard-slice gate satisfied:
     - near-tie required,
     - adjacent-rank required,
     - pair uncertainty std >= `0.04`.
- if strict hard replacement is not triggered, allow only a conservative soft trust adjustment:
  - confidence >= `0.80` and strict gate satisfied,
  - if Cohere disagrees with existing label, downweight supervision row to `0.8` (no label flip),
  - if Cohere agrees, upweight to `1.05` (no label flip).

## Commands run

```bash
python scripts/run_bruteforce_branch_label_generator.py \
  --run-id dq_base_approx_20260417 \
  --dataset-name openai/gsm8k \
  --max-frontier-states 90 \
  --episodes-per-example 1 \
  --frontier-budget 7 \
  --min-remaining-budget 2 \
  --max-remaining-budget 4 \
  --init-branches 3 \
  --max-branches-per-state 4 \
  --rollout-samples-per-candidate 16 \
  --max-allocation-samples 32 \
  --seed 23

python scripts/cohere_adjudicate_hard_pairs.py \
  --labels-dir outputs/branch_label_bruteforce/dq_base_approx_20260417 \
  --run-id cohere_hard_adjudication_v4_strict_20260417 \
  --model command-r-plus-08-2024 \
  --max-pairs 18 \
  --near-tie-margin 0.03 \
  --replace-confidence-min 0.9 \
  --strict-hard-slice-only \
  --strict-near-tie-required \
  --strict-adjacent-required \
  --strict-min-pair-std 0.04 \
  --soft-weight-confidence-min 0.8 \
  --soft-disagree-weight 0.8 \
  --soft-agree-weight 1.05 \
  --max-retries 8 \
  --retry-sleep-sec 4.0

python scripts/run_target_fidelity_regime_experiment.py \
  --targets-root outputs/branch_label_bruteforce_targets/cohere_hard_adjudication_v4_strict_20260417 \
  --run-id cohere_hard_adjudication_matched_v4_strict_20260417 \
  --seeds 11,29,47 \
  --near-tie-margin 0.03 \
  --pairwise-near-tie-action none \
  --feature-set v2
```

## Bounded artifact summary

- Selected/adjudicated pairs: `18`
- Hard replacements: `0`
- Soft disagree downweights: `1`
- Soft agree upweights: `0`

## Matched comparison result (pairwise model means)

From `outputs/branch_label_bruteforce_learning/cohere_hard_adjudication_matched_v4_strict_20260417/cohere_delta_summary.json`:

- pairwise accuracy: `0.6313 -> 0.6313` (delta `0.0000`)
- top-1: `0.6389 -> 0.6389` (delta `0.0000`)
- near-tie: `0.1667 -> 0.1667` (delta `0.0000`)
- adjacent-rank: `0.6171 -> 0.6171` (delta `0.0000`)
- exact-promoted: `0.0000 -> 0.0000` (delta `0.0000`)
- brier: `0.24921 -> 0.24972` (slight worsening, `+0.00051`)

## Conservative conclusion

The stricter gating policy **avoided the prior degradation** by effectively preventing risky replacements, but it also produced **no meaningful improvement** in hard-slice metrics in this bounded run.

Interpretation for next step:
- bounded Cohere relabeling with very strict replacement gates appears safe but too weak to move metrics,
- current bottleneck likely still requires better supervision design/selection logic (not just another confidence threshold tweak),
- Cohere can remain a bounded adjunct, but this rerun does not support it as the primary fix for the hard-case supervision bottleneck.

## Artifacts

- Adjudication:
  - `outputs/cohere_hard_case_adjudication/cohere_hard_adjudication_v4_strict_20260417/`
- Target regimes:
  - `outputs/branch_label_bruteforce_targets/cohere_hard_adjudication_v4_strict_20260417/regime_all_pairs/`
  - `outputs/branch_label_bruteforce_targets/cohere_hard_adjudication_v4_strict_20260417/regime_cohere_hard_adjudicated/`
- Matched learning comparison:
  - `outputs/branch_label_bruteforce_learning/cohere_hard_adjudication_matched_v4_strict_20260417/`
  - `outputs/branch_label_bruteforce_learning/cohere_hard_adjudication_matched_v4_strict_20260417/cohere_delta_summary.json`
