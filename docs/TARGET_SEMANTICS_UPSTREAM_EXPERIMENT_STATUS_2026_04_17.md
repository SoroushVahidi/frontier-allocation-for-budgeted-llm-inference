# TARGET_SEMANTICS_UPSTREAM_EXPERIMENT_STATUS_2026_04_17

## Scope and objective

Bounded upstream target-semantics experiment on canonical fixed-budget branch-allocation supervision.

Question tested: can a target-semantic weighting regime focused on close relative next-step opportunity improve hard close-branch discrimination without introducing a new downstream decision rule?

---

## Insertion points inspected before implementation

1. `scripts/build_bruteforce_target_regimes.py`
   - Existing canonical insertion point for pair-row target regime construction and manifests.
   - Pair-row augmentation and supervision-weight fields already supported.

2. `experiments/bruteforce_branch_allocator.py`
   - `_pairwise_weight` is the minimal place where pair-level supervision multipliers are consumed.
   - Existing `supervision_reliability_weight` consumption already canonical.

3. `scripts/run_branch_value_uncertainty_strict_validation_pass.py`
   - Strongest existing matched strict harness for accepted-accuracy / coverage / defer / near-tie / adjacent metrics.
   - Kept unchanged for evaluation logic; added a tiny external summarizer script to generate per-regime deltas and weight diagnostics.

---

## New bounded target-semantic regime

### Regime names

- `opportunity_intensity_weighted`
- Ablation: `opportunity_intensity_weighted_no_outside_norm`

### Definition

For pair `(i, j)` with candidate values `v_i`, `v_j` and outside estimate `outside`:

- Main regime intensity:

\[
I = \frac{|v_i - v_j|}{|v_i| + |v_j| + |outside| + \epsilon}
\]

- Ablation intensity:

\[
I_{\text{no outside}} = \frac{|v_i - v_j|}{|v_i| + |v_j| + \epsilon}
\]

Raw close-pair emphasis:

\[
w_{raw} = \operatorname{clip}(w_{min}, w_{max}, 1 / (I + \tau))
\]

Then global min-max normalization into bounded final multiplier:

\[
w_{final} \in [m_{min}, m_{max}]
\]

and

\[
\text{supervision\_reliability\_weight} \leftarrow \text{supervision\_reliability\_weight} \times w_{final}
\]

Direction label remains canonical binary winner (no direction-label rewrite, no downstream decision-rule patch).

### Why materially different from current regimes

- Baseline canonical pair supervision is effectively flat winner semantics with existing reliability gates.
- New regime adds explicit **advantage-intensity semantics** to supervision pressure:
  - low-intensity (close opportunity) pairs are upweighted,
  - high-intensity (clear gap) pairs are relatively downweighted,
  while preserving label direction and evaluation harness.

---

## Implementation summary

### Code changes

- Added two new strategies in target regime builder with required fields:
  - `opportunity_intensity_raw`
  - `opportunity_intensity_weight_raw`
  - `opportunity_intensity_weight`
  - `opportunity_intensity_weight_final`
  - `opportunity_intensity_weight_source`
  - `opportunity_intensity_used_outside_norm`
  - normalization constants/metadata.
- Added minimal pairwise-weight integration guard in allocator (`_pairwise_weight`) so optional multiplier can be consumed if not already baked.
- Added tiny summarizer script:
  - `scripts/summarize_upstream_target_semantics_experiment.py`
  producing machine-readable per-seed/aggregate/delta/weight-diagnostic summaries.

---

## Commands run

See:

- `outputs/branch_label_bruteforce_learning/target_semantics_upstream_strict_validation_20260417/upstream_target_semantics_commands_assumptions_caveats.md`

Primary run IDs:

- Targets root: `outputs/branch_label_bruteforce_targets/target_semantics_upstream_20260417`
- Strict validation run dir: `outputs/branch_label_bruteforce_learning/target_semantics_upstream_strict_validation_20260417`

---

## Main metrics (matched strict validation)

Compared regimes:

1. `all_pairs_approx` (canonical baseline path)
2. `opportunity_intensity_weighted`
3. `opportunity_intensity_weighted_no_outside_norm` (ablation)

### Aggregate strict full-method metrics

All three regimes were identical in this bounded run:

- accepted accuracy: `0.9333`
- coverage: `0.2698`
- defer rate: `0.7302`
- near-tie accepted accuracy: `0.0000`
- adjacent-rank accepted accuracy: `0.8889`
- accepted mean true-value-gap: `0.1743`
- deferred mean true-value-gap: `0.0817`

Delta vs baseline: `0.0000` on all reported aggregate metrics.

### Pairwise-binary baseline (same strict run artifact)

Aggregate pairwise-binary metrics were also unchanged across compared regimes:

- pairwise binary accuracy: `0.8214`
- pairwise binary near-tie accuracy: `0.7667`
- pairwise binary adjacent accuracy: `0.7714`

Delta vs baseline: `0.0000`.

### Weight concentration diagnostics

From `upstream_target_semantics_weight_diagnostics.json`:

- Baseline all-pairs mean weight: `1.0000`
- New regimes mean weight: `1.2788`
- Near-tie mean weight (new): `1.6000`
- Non-near-tie mean weight (new): `1.1571`
- Adjacent mean weight (new): `1.3617`
- Non-adjacent mean weight (new): `1.1014`
- Weight percentiles (new): p05 `0.7723`, p50 `1.3503`, p95 `1.6000`

Interpretation: weighting **did** concentrate training pressure on intended hard slices, but this did not convert into measured metric gains in this bounded evaluation.

---

## Assumptions and caveats

- Matched canonical strict-validation settings were preserved (seeds `11,29,47`; feature set `v3`).
- This recovered canonical root is small and openai/gsm8k-focused.
- In this artifact set, outside-option term is effectively unavailable/zero in pair rows, so with/without-outside normalization regimes collapsed to the same numeric weights in practice.

---

## Hard conclusion (go / no-go)

**Conclusion: DROP this direction for now (no-go).**

Reason:

- Upstream weighting successfully targeted close/adjacent hard pairs,
- but produced **no measurable improvement** in accepted accuracy / coverage / defer / near-tie / adjacent metrics under matched strict validation,
- and no evidence of robust gain vs canonical baseline in this bounded pass.

Recommendation:

- Do not continue this exact weighting form as a primary path.
- If revisiting upstream semantics, use a different construction that changes effective supervisory information (not only weight reallocation), and rerun matched strict validation.

---

## Artifact index

- Targets root manifest: `outputs/branch_label_bruteforce_targets/target_semantics_upstream_20260417/manifest.json`
- Strict validation outputs:
  - `strict_validation_config.json`
  - `strict_validation_results.json`
  - `strict_validation_summary.json`
- Upstream comparison outputs:
  - `upstream_target_semantics_experiment_config.json`
  - `upstream_target_semantics_summary.json`
  - `upstream_target_semantics_aggregate_comparison.json`
  - `upstream_target_semantics_per_seed_summary.json`
  - `upstream_target_semantics_weight_diagnostics.json`
  - `upstream_target_semantics_ablation_summary.json`
  - `upstream_target_semantics_commands_assumptions_caveats.md`
  - `upstream_target_semantics_manifest.json`
