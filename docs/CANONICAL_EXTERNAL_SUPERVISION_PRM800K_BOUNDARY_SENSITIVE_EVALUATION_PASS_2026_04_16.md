# Canonical external-supervision pass: boundary-sensitive held-out evaluation (2026-04-16)

## Objective
Treat the current bottleneck as evaluation design: add one boundary-sensitive held-out protocol (protected strata + local boundary metric + paired uncertainty) on the strongest low-budget/exact-promoted regime, with method family fixed.

## 1) What the old evaluation missed
Using the current strongest regime (`real_branch_learning_corpus_20260416_lowbudget_exactpromoted_v1`), prior reporting still had blind spots:
- low-budget extreme support remains tiny (`budget=1`, n=2)
- exact-promoted and exact-only remain tiny (n=2 each)
- near-boundary behavior was mostly summarized via one global boundary diagnostic
- no explicit protected strata crossing provenance (`exact-promoted` vs `approx`) with boundary proximity
- no paired uncertainty intervals for method deltas on identical held-out rows

This can hide real differences by mixing fundamentally different decision contexts.

## 2) Boundary-sensitive protocol added (bounded)
Added one evaluation layer script:
- `scripts/run_canonical_boundary_sensitive_evaluation.py`

Protocol components:
1. **Protected strata** (explicit, not collapsed):
   - exact-promoted / near-boundary
   - exact-promoted / non-boundary
   - approximate / near-boundary
   - approximate / non-boundary
   - low-budget / near-boundary
   - low-budget / non-boundary
2. **Near-boundary definition** (matched to boundary method semantics):
   - `abs(base_pointwise_margin) <= 0.02` and `pair_uncertainty_std_mean >= 0.02`
3. **Local boundary metric**:
   - pivot-boundary consistency across local state boundary sets
   - for each eligible state, whether the true top branch (pivot) is consistently preferred in boundary-near pairs
4. **Paired uncertainty reporting**:
   - paired bootstrap CIs for method deltas on the same held-out rows
   - reported for anchor vs broad, anchor vs aligned, anchor vs boundary

## 3) Exact artifact paths used
- Canonical corpus: `outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_lowbudget_exactpromoted_v1`
- External PRM artifact: `outputs/branch_learning_corpora_external/external_prm_mathshepherd_apps_20260416`
- Boundary-sensitive evaluation JSON output:
  - `outputs/canonical_branch_learning_pass/boundary_sensitive_eval_20260416.json`

## 4) Exact commands run
```bash
python -m py_compile scripts/run_canonical_boundary_sensitive_evaluation.py
python scripts/run_canonical_boundary_sensitive_evaluation.py --canonical-corpus-dir outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_lowbudget_exactpromoted_v1 --external-prm-corpus-dir outputs/branch_learning_corpora_external/external_prm_mathshepherd_apps_20260416 --output-json outputs/canonical_branch_learning_pass/boundary_sensitive_eval_20260416.json --seed 17 --near-tie-margin 0.05 --feature-set v2 --hard-case-mult 1.75 --exact-promoted-mult 2.0 --intervention-target-boost 0.6 --external-source-key prm800k --external-source-split train --external-pointwise-blend-alpha 0.2 --external-gate-uncertainty-std-threshold 0.03 --external-gate-top-gap-threshold 0.04 --external-boundary-pair-margin-threshold 0.02 --external-boundary-pair-uncertainty-std-threshold 0.02 --external-prm-max-uncertainty-std 1.0 --bootstrap-samples 2000
```

## 5) Support counts (global + strata)
Global held-out support:
- total test pairs: 30
- total top-1 states: 9
- near-tie: 12
- adjacent-rank: 18
- small-margin: 22
- exact-promoted: 2
- exact-only: 2
- approx-only: 28
- low-budget (<=2): 8
- boundary-eligible: 4
- dataset slices: MATH-500=15, GSM8K=15
- budget slices: b1=2, b2=6, b3=9, b4=13

Protected strata counts:
- exact-promoted / near-boundary: 1
- exact-promoted / non-boundary: 1
- approximate / near-boundary: 3
- approximate / non-boundary: 25
- low-budget / near-boundary: 1
- low-budget / non-boundary: 7

Still too small for strong inference:
- exact-promoted strata (n=1 each)
- low-budget-near-boundary (n=1)
- boundary-eligible overall (n=4)

## 6) Matched method comparison under boundary-sensitive protocol
### Aggregate
- anchor: 0.5333
- broad: 0.6000
- aligned: 0.6000
- boundary: 0.6333

### Hard slices
- near-tie (n=12): anchor 0.4167, broad 0.4167, aligned 0.4167, boundary 0.5000
- adjacent-rank (n=18): anchor 0.5556, broad 0.5000, aligned 0.5000, boundary 0.5556
- small-margin (n=22): anchor 0.4545, broad 0.5000, aligned 0.5000, boundary 0.5455

### Boundary-sensitive strata highlights
- exact-promoted / near-boundary (n=1): anchor 0.0 vs broad/aligned/boundary 1.0
- approximate / non-boundary (n=25): anchor 0.64, broad 0.60, aligned 0.60, boundary 0.64
- low-budget / non-boundary (n=7): anchor 0.5714, broad 0.4286, aligned 0.4286, boundary 0.5714

### Local boundary metric (pivot-boundary consistency)
Eligible states: 4
- anchor: 0.25
- broad: 0.50
- aligned: 0.50
- boundary: 0.50

### Paired uncertainty (delta vs anchor, paired bootstrap)
All pairs (n=30):
- broad-anchor: +0.0667, 95% CI [-0.0667, +0.2000]
- aligned-anchor: +0.0667, 95% CI [-0.0667, +0.2000]
- boundary-anchor: +0.1000, 95% CI [0.0000, +0.2333]

Low-budget (n=8):
- broad-anchor: +0.0000, 95% CI [-0.3750, +0.3750]
- aligned-anchor: +0.0000, 95% CI [-0.3750, +0.3750]
- boundary-anchor: +0.1250, 95% CI [0.0000, +0.3750]

Boundary-eligible (n=4):
- broad-anchor: +0.7500, 95% CI [+0.2500, +1.0000]
- aligned-anchor: +0.7500, 95% CI [+0.2500, +1.0000]
- boundary-anchor: +0.7500, 95% CI [+0.2500, +1.0000]

## 7) Conservative diagnosis
1. The new protocol materially improves interpretability: method deltas are now stratified by boundary/provenance/low-budget context with paired uncertainty.
2. It does **not** yet prove bottleneck closure: key strata remain tiny.
3. Broad vs aligned still tie on aggregate and major hard slices.
4. Boundary remains mostly diagnostic for top-1 (no top-1 flip evidence here).

## 8) Recommendation on Math-Shepherd
Still wait. This pass improved evaluation quality and interpretability, but support in exact-promoted and extreme low-budget boundary strata is still too sparse for strong causal claims.

## Files added/modified
- Added: `scripts/run_canonical_boundary_sensitive_evaluation.py`
- Added: `docs/CANONICAL_EXTERNAL_SUPERVISION_PRM800K_BOUNDARY_SENSITIVE_EVALUATION_PASS_2026_04_16.md`
- Added: `docs/canonical_external_supervision_prm800k_boundary_sensitive_evaluation_pass_2026_04_16_summary.json`
