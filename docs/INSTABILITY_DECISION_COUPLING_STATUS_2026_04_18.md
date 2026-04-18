# Instability-to-decision coupling status (2026-04-18)

## Insertion-point summary

This bounded pass adds a dedicated decision-policy experiment line focused on whether better ambiguity-aware coupling (especially defer activation behavior) can improve fixed-budget next-step branch allocation **without introducing a new target family**.

Inserted components:
- `scripts/run_instability_decision_coupling_experiment.py`
- output bundle: `outputs/branch_label_bruteforce_learning/instability_decision_coupling_eval_20260418/`

The pass reuses existing target-regime artifacts from:
- `outputs/branch_label_bruteforce_targets/rank_instability_target_20260418/`

## Existing signals used

No new simulator/supervision object was introduced. The experiment uses already materialized signals:
- multistep k3 target score (`multistep_branch_utility_target` via learned pointwise scorer)
- outside-option evidence (`branch_vs_outside_gap`)
- near-tie state indicator (`near_tie_flag` aggregated to state)
- adjacent-rank hard-slice indicator (`pair_type == adjacent_rank`)
- rank-instability state label/score (`rank_instability_state_label`, `rank_instability_state_score`)
- rank-instability pair features (`rank_instability_pair_label`, disagreement count, margin-relative features)
- learned top-2 instability probability from existing pair rows
- margin/confidence proxy from top-2 score gap

Supporting diagnostics also keep discounted/response-curve anchors in model-status provenance for parity checks.

## Exact decision-policy definitions

Compared policies:
1. `baseline_all_pairs`
2. `multistep_k3_current`
3. `rank_instability_aware_current` (existing policy family)
4. `defer_on_instability`
5. `instability_penalized_top_score`
6. `instability_outside_option_gate`
7. `selective_hard_case_abstention`

### Defer activation behavior by variant

- **rank_instability_aware_current**:
  - defer iff `(instability_prob >= 0.01 OR state_instability_label)` and `top2_gap <= 1.5 * current_margin_threshold`.

- **defer_on_instability**:
  - defer iff `instability_prob >= 0.01` and `top2_gap <= 0.20`.

- **instability_penalized_top_score**:
  - score adjustment per branch: `raw_score - penalty_weight * instability_prob * (outside_weak + state_score_weight * state_instability_score)`
  - where `outside_weak = max(0, 0.12 - outside_gap)`
  - choose adjusted top branch, then defer iff `instability_prob >= 0.01` and `adjusted_top2_gap <= 0.12`.

- **instability_outside_option_gate**:
  - accept top branch iff `instability_prob <= 0.01` OR `outside_gap >= 0.08`
  - otherwise defer when `top2_gap <= 0.20`.

- **selective_hard_case_abstention**:
  - on hard states (`near_tie OR adjacent`) with `instability_prob >= 0.01`, require both:
    - `top2_gap >= 0.12`
    - `outside_gap >= 0.08`
  - else defer.

## Commands run

```bash
python scripts/run_instability_decision_coupling_experiment.py \
  --targets-root outputs/branch_label_bruteforce_targets/rank_instability_target_20260418 \
  --run-id instability_decision_coupling_eval_20260418 \
  --output-root outputs/branch_label_bruteforce_learning \
  --seeds 11,29,47 \
  --feature-set v3 \
  --near-tie-margin 0.03 \
  --defer-instability-threshold 0.01 \
  --defer-margin-threshold 0.2 \
  --penalty-weight 1.0 \
  --penalty-state-score-weight 1.0 \
  --penalty-outside-weak-floor 0.12 \
  --penalty-defer-instability-threshold 0.01 \
  --penalty-defer-adjusted-margin-threshold 0.12 \
  --gate-instability-threshold 0.01 \
  --gate-outside-gap-threshold 0.08 \
  --gate-margin-threshold 0.2 \
  --hard-instability-threshold 0.01 \
  --hard-margin-threshold 0.12 \
  --hard-outside-threshold 0.08 \
  --current-instability-threshold 0.01 \
  --current-margin-threshold 0.12

python -m py_compile scripts/run_instability_decision_coupling_experiment.py
```

## Key metrics

Source: `outputs/branch_label_bruteforce_learning/instability_decision_coupling_eval_20260418/aggregate_comparison_summary.json`

### Anchors
- `multistep_k3_current`: accepted=0.6667, coverage=1.0000, defer=0.0000, near-tie accepted=0.6667, strict hard-slice accepted=0.6667.
- `rank_instability_aware_current`: accepted=0.6111, coverage=0.8889, defer=0.1111, near-tie accepted=0.3333, strict hard-slice accepted=0.3333.

### New coupling variants
- `defer_on_instability`: accepted=0.6667, coverage=0.5556, defer=0.4444, near-tie accepted=0.3333, strict hard-slice accepted=0.3333.
- `instability_penalized_top_score`: accepted=0.6667, coverage=0.6667, defer=0.3333, near-tie accepted=0.3333, strict hard-slice accepted=0.3333.
- `instability_outside_option_gate`: accepted=0.6667, coverage=0.5556, defer=0.4444, near-tie accepted=0.3333, strict hard-slice accepted=0.3333.
- `selective_hard_case_abstention`: accepted=0.6667, coverage=0.5556, defer=0.4444, near-tie accepted=0.3333, strict hard-slice accepted=0.3333.

### Failure/support diagnostics
- Compared with multistep-k3, defer-based coupling variants reduced delayed-payoff-overvaluation failures (mean delta -0.3333) and fragile overconfident wrong accepts in some variants, but these reductions came with major coverage loss and weaker near-tie accepted quality.
- easy-state defer spillover remained 0.0 in this bounded run (defer concentrated in hard slice under current sample).

## Caveats

- Very small bounded support (few test states per seed) means coarse metric steps.
- Instability probabilities are low-range on this artifact slice; defer activation required aggressive low thresholds.
- No claim is made that current thresholds are globally calibrated.

## Hard conclusion

**Outcome classification: mostly diagnostic / no improvement.**

The new decision-coupling variants did not beat `multistep_k3_current` on accepted accuracy or hard-slice accepted accuracy. They did demonstrate that defer can be explicitly activated and can suppress certain failure signatures, but in this bounded run the tradeoff was mostly coverage loss and hard-slice accepted degradation rather than net gain.

Core question tested:
- “Can better ambiguity-aware decision coupling outperform current multistep-k3 without adding a new target family?”

Current answer from this bounded pass:
- **Not yet.** Evidence is useful diagnostically (defer controllability and failure-type sensitivity), but no performance displacement of multistep-k3 was observed.
