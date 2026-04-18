# Compute-response curve status (2026-04-18)

## Insertion-point summary

This pass adds a **first-class target regime family** for compute-response curve supervision in the existing branch-label brute-force pipeline, without replacing the canonical multistep path.

Implemented insertion points:
- `scripts/build_bruteforce_target_regimes.py`
  - new strategy: `compute_response_curve_target_h123`
  - candidate-level curve targets (`h1`, `h2`, `h3`) with explicit provenance fields
  - pair-level labels derived from an explicit curve-to-decision map
- `scripts/run_compute_response_curve_experiment.py`
  - bounded training/evaluation runner for curve supervision
  - matched comparison against `all_pairs` baseline and current `multistep_branch_utility_target_k3`
  - machine-readable per-seed + aggregate + failure-group outputs under `outputs/branch_label_bruteforce_learning/`
- `scripts/CANONICAL_START_HERE.md`
  - script index updated to include the new experiment entrypoint

## Exact target definition

For each candidate branch in state `s`, define a target curve over horizons `h ∈ {1,2,3}`:

- `U_h(s,b) := multistep_branch_utility_target_kh(s,b)`
- where each `U_h` reuses the canonical multistep utility construction (`best_followup_allocation_self_mass_proxy_v1`) already in-repo.

Stored per candidate:
- `compute_response_curve_h1`, `compute_response_curve_h2`, `compute_response_curve_h3`
- marginalized components:
  - `m1 = U1`
  - `m2 = U2 - U1`
  - `m3 = U3 - U2`
- provenance:
  - `compute_response_curve_target_version = compute_response_curve_target_v1`
  - `compute_response_curve_target_source = multistep_self_followup_proxy_horizon_h1_h3`

Secondary scalar (explicitly marked derived):
- `S(s,b) = w1*m1 + w2*m2 + w3*m3`
- bounded run weights: `(w1,w2,w3)=(1.0,0.6,0.3)`
- stored as `compute_response_curve_decision_scalar` and weight metadata.

## How next-step decisions are derived from predicted curves

Training object:
- A multi-output ridge model predicts `(Û1,Û2,Û3)` for each branch candidate.

Decision derivation (next-step branch allocation score):
- `m̂1 = Û1`, `m̂2 = Û2-Û1`, `m̂3 = Û3-Û2`
- `ŝ = w1*m̂1 + w2*m̂2 + w3*m̂3`
- next-step branch = `argmax_b ŝ(s,b)`

This keeps the main prediction object as a curve, and only uses scalarization as a transparent decision readout.

## Commands run

```bash
python -m py_compile scripts/build_bruteforce_target_regimes.py scripts/run_compute_response_curve_experiment.py scripts/run_multistep_branch_utility_target_experiment.py

python scripts/build_bruteforce_target_regimes.py \
  --labels-dir outputs/branch_label_bruteforce_targets/multistep_branch_utility_target_20260417/regime_all_pairs \
  --output-dir outputs/branch_label_bruteforce_targets \
  --run-id compute_response_curve_target_20260418 \
  --pair-strategies all_pairs,multistep_branch_utility_target_k3,compute_response_curve_target_h123 \
  --near-tie-margin 0.03 \
  --multistep-utility-lambda 0.35 \
  --response-curve-score-w1 1.0 \
  --response-curve-score-w2 0.6 \
  --response-curve-score-w3 0.3

python scripts/run_compute_response_curve_experiment.py \
  --targets-root outputs/branch_label_bruteforce_targets/compute_response_curve_target_20260418 \
  --output-root outputs/branch_label_bruteforce_learning \
  --run-id compute_response_curve_eval_20260418 \
  --seeds 11,29,47 \
  --feature-set v3 \
  --near-tie-margin 0.03 \
  --baseline-regime all_pairs \
  --current-multistep-regime multistep_branch_utility_target_k3 \
  --curve-regime compute_response_curve_target_h123 \
  --curve-score-w1 1.0 \
  --curve-score-w2 0.6 \
  --curve-score-w3 0.3
```

## Key metrics (bounded pass)

From `outputs/branch_label_bruteforce_learning/compute_response_curve_eval_20260418/aggregate_comparison_summary.json`:

- baseline `all_pairs` accepted accuracy mean: **0.5595**
- current multistep (`k3`) accepted accuracy mean: **0.7063**
- response-curve accepted accuracy mean: **0.7063**
- response-curve delta vs baseline: **+0.1468**
- response-curve delta vs current multistep: **0.0000**

Hard slices:
- near-tie accepted accuracy mean
  - baseline: **0.2000**
  - current multistep: **0.6000**
  - response-curve: **0.6000**
- strict near-tie+adjacent slice accepted accuracy mean
  - current multistep: **0.5833**
  - response-curve: **0.5833**

Failure-group diagnostic (delayed-payoff confusion proxy, bounded):
- current multistep delayed-payoff confusion rate on failures mean: **0.0000**
- response-curve delayed-payoff confusion rate on failures mean: **0.1111**

## Caveats

- This is a bounded small-data pass (91 pair rows in each regime in this run family), so variance is high.
- The response-curve labels currently reuse the existing multistep self-followup proxy rather than a fundamentally new rollout estimator.
- The decision scalar weights were fixed (`1.0, 0.6, 0.3`) and not swept; other policies may behave differently.
- The delayed-payoff confusion diagnostic here is a lightweight proxy, not a full causal attribution.

## Hard conclusion

In this bounded implementation pass, compute-response curve prediction is **successfully integrated as a first-class target/experiment path**, but it shows **no aggregate improvement over the current multistep line** on accepted accuracy or hard-slice accepted accuracy under matched settings.

So the current evidence does **not** support replacing or surpassing the canonical multistep family yet; the response-curve path is now available for follow-up sweeps and stronger validation.
