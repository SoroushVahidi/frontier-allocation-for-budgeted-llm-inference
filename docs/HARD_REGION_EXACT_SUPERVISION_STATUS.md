# Hard-region exact supervision status (2026-04-16)

## Scope

This pass implements the next target-fidelity step after the regime study:

- mine difficult branch-comparison regions,
- selectively expand exact labels only for mined hard pairs,
- rebuild exact-augmented training regimes,
- run matched multi-seed learning with fixed model family.

Conceptual center remains fixed-budget **next-step branch allocation** via pairwise branch comparison.

## Commands executed

```bash
python scripts/run_bruteforce_branch_label_generator.py \
  --run-id hard_region_base_approx_20260416 \
  --dataset-name openai/gsm8k \
  --max-frontier-states 120 \
  --episodes-per-example 1 \
  --frontier-budget 7 \
  --min-remaining-budget 2 \
  --max-remaining-budget 4 \
  --init-branches 3 \
  --max-branches-per-state 4 \
  --rollout-samples-per-candidate 18 \
  --max-allocation-samples 36 \
  --seed 19

python scripts/mine_bruteforce_hard_regions.py \
  --labels-dir outputs/branch_label_bruteforce/hard_region_base_approx_20260416 \
  --run-id hard_region_mining_20260416 \
  --near-tie-margin 0.03 \
  --small-margin-threshold 0.08 \
  --high-std-threshold 0.07 \
  --max-candidates 100

python scripts/expand_bruteforce_exact_hard_regions.py \
  --base-labels-dir outputs/branch_label_bruteforce/hard_region_base_approx_20260416 \
  --mined-candidates-jsonl outputs/branch_label_bruteforce_targets/hard_region_mining_20260416/mined_hard_candidates.jsonl \
  --run-id hard_region_exact_expansion_20260416 \
  --max-target-pairs 100

python scripts/build_exact_augmented_target_regimes.py \
  --labels-dir outputs/branch_label_bruteforce/hard_region_base_approx_20260416 \
  --exact-expansion-dir outputs/branch_label_bruteforce_targets/hard_region_exact_expansion_20260416 \
  --run-id hard_region_exact_augmented_regimes_20260416 \
  --near-tie-margin 0.03 \
  --high-margin-threshold 0.08 \
  --max-pair-std 0.07

python scripts/run_hard_region_exact_supervision_experiment.py \
  --targets-root outputs/branch_label_bruteforce_targets/hard_region_exact_augmented_regimes_20260416 \
  --run-id hard_region_exact_matched_20260416 \
  --seeds 11,29,47 \
  --near-tie-margin 0.03
```

## Part A — Hard-region mining

Mining priority combined these signals:

- near-tie (`|margin| <= 0.03`),
- small absolute margin,
- high pair uncertainty std,
- adjacent-rank pair type,
- disagreement-risk proxy (`std / margin_abs`),
- low learner-confidence proxy (deterministic hash proxy),
- optional known exact disagreement marker if an exact reference exists.

Canonical mined artifact:

- `outputs/branch_label_bruteforce_targets/hard_region_mining_20260416/mined_hard_candidates.jsonl`
- with provenance fields: source labels dir, regime, mode, reasons, priority score, dataset, budget, pair type.

Mining summary:

- mined hard pairs: **100**
- reason concentrations:
  - adjacent-rank: **95**
  - high uncertainty std: **85**
  - disagreement-risk proxy: **89**
  - near-tie: **33**
- budget concentration:
  - B4: **51**, B3: **31**, B2: **18**

## Part B — Selective exact-label generation

A bounded exact relabeling runner was added that:

- replays deterministic frontier states from base-run manifest config,
- computes exact-mode labels only for mined target states/pairs,
- emits resumable progress + manifest + checksums,
- preserves per-row provenance (`mined_reasons`, `original_regime`, `replaced_approx_label`, dataset/budget/pair type).

Expansion summary:

- target mined pairs: 100
- exact relabeled pairs emitted: **100**
- approx labels replaced in target set: **100**
- exact candidate rows emitted for targeted states: **173**

Artifacts:

- `outputs/branch_label_bruteforce_targets/hard_region_exact_expansion_20260416/exact_pairwise_labels.jsonl`
- `outputs/branch_label_bruteforce_targets/hard_region_exact_expansion_20260416/exact_candidate_labels.jsonl`
- `outputs/branch_label_bruteforce_targets/hard_region_exact_expansion_20260416/manifest.json`

## Part C — Exact-augmented target regimes

Materialized regimes:

1. `all_pairs_approx` (baseline)
2. `promoted_exact_hard_region`
3. `promoted_exact_top_vs_rest`
4. `promoted_exact_high_margin_only`
5. `promoted_exact_uncertainty_filtered`

Exact promotion concentration:

- hard-region promoted exact rate: **69.9%** (100 / 143)
- top-vs-rest promoted exact rate: **20.0%** (5 / 25)
- high-margin promoted exact rate: **43.8%** (28 / 64)
- uncertainty-filtered promoted exact rate: **21.7%** (5 / 23)

Artifacts:

- `outputs/branch_label_bruteforce_targets/hard_region_exact_augmented_regimes_20260416/manifest.json`
- per-regime target summaries under each `regime_*` directory.

## Part D — Matched evaluation

Matched setup:

- fixed learning stack,
- seeds: 11, 29, 47,
- compared supervision regimes above,
- models include pairwise logistic baseline and integrated non-linear model family.

### Pairwise logistic (3-seed means)

- `all_pairs_approx`: pairwise 0.4629, top-1 0.2915, near-tie 0.4762, adjacent-rank 0.4421
- `promoted_exact_hard_region`: pairwise 0.4629, top-1 0.2915, near-tie 0.4762, adjacent-rank 0.4421
- `promoted_exact_high_margin_only`: pairwise 0.5308, top-1 0.4906, near-tie 0.0000 (filtered), adjacent-rank 0.4444
- `promoted_exact_top_vs_rest`: pairwise 0.3889, top-1 0.3060, near-tie 0.3333, adjacent-rank 0.0000
- `promoted_exact_uncertainty_filtered`: pairwise 0.5000, top-1 0.3427, near-tie 0.0000 (filtered), adjacent-rank 0.5000

### CatBoost ranker (optional non-linear; 3-seed means)

- `all_pairs_approx`: pairwise 0.4152, near-tie 0.1786, adjacent-rank 0.4228
- `promoted_exact_hard_region`: pairwise 0.4152, near-tie 0.1786, adjacent-rank 0.4228
- `promoted_exact_high_margin_only`: pairwise 0.5692, near-tie 0.0000 (filtered), adjacent-rank 0.5694

### Per-dataset and per-budget slices (pairwise logistic)

Per-dataset in this run is only GSM8K-backed labels.

Per-budget (`all_pairs_approx` / `promoted_exact_hard_region`):

- B2: 0.3214
- B3: 0.4762
- B4: 0.6032

## Main question answer

Did targeted exact-label expansion on hard regions improve the difficult bottleneck slices more than generic approximate baseline scaling in this bounded pass?

- **No clear improvement signal yet** for the direct hard-region promotion regime (`promoted_exact_hard_region`) versus `all_pairs_approx` on pairwise, top-1, near-tie, or adjacent-rank metrics.
- High-margin and uncertainty-filtered regimes improve some aggregate metrics by excluding difficult/noisy pairs, but this does **not** indicate the hard near-tie bottleneck is solved.

## Conservative conclusion

This pass adds a complete auditable hard-region exact-supervision pipeline and improves localization of where supervision remains weakest.

Current evidence is consistent with:

- bottleneck **better instrumented and localized**,
- bottleneck **not yet materially reduced** on near-tie/adjacent hard slices by targeted exact promotion alone in this bounded run.

Safe interpretation: selective exact expansion is now operational and testable, but further work is still needed to convert hard-region relabeling into robust difficult-slice gains.
