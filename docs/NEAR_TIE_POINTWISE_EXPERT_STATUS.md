# Near-tie pointwise expert status (2026-04-16)

## Scope

This pass follows `docs/NEAR_TIE_POLICY_STATUS.md` and narrows the next step:

> if near-tie routing helped only when it deferred to pointwise value, can we make that path a dedicated near-tie pointwise expert rather than a generic fallback?

Project framing is unchanged:
- fixed-budget next-step branch allocation remains the center,
- pairwise branch comparison remains the main learned object,
- pointwise value is treated as a supporting near-tie expert fallback path.

## What was added

## 1) Near-tie pairwise-vs-pointwise diagnostic audit

New runner:
- `scripts/run_near_tie_pointwise_expert_experiment.py`

For test-side **detected near-tie pairs**, the runner now audits four buckets:
- `pairwise_ok__pointwise_ok`
- `pairwise_ok__pointwise_fail`
- `pairwise_fail__pointwise_ok`
- `pairwise_fail__pointwise_fail`

Audit features include:
- `margin_abs`
- `relative_margin`
- `pair_std` (uncertainty/std)
- `rank_gap_abs`
- `pointwise_value_gap_abs`
- frontier context (`frontier_score_std_mean`, `frontier_entropy_mean`)

Artifacts are stored in run results under:
- `near_tie_pairwise_vs_pointwise_diagnostic`

## 2) Dedicated near-tie pointwise expert path

Three pointwise fallback modes are now compared in matched runs:
1. `near_tie_generic_pointwise` (baseline reuse)
2. `near_tie_specialized_pointwise` (near-tie-state-only pointwise model)
3. `near_tie_reweighted_pointwise` (global pointwise model with near-tie/adjacent emphasis)

### Specialized pointwise definition

Specialized training states are states that contain train-split pairs satisfying either:
- detector-marked near-tie, or
- `margin_abs <= near_tie_specialized_margin_max`.

A minimum-state safeguard is enforced:
- if near-tie training states `< near_tie_specialized_min_states`, specialized model is marked insufficient and generic pointwise is used as fallback scorer.

### Reweighted pointwise definition

Reweighted pointwise uses all train candidates but multiplies per-row sample weights by:
- `near_tie_reweight_factor` if row’s state is in near-tie state set,
- `adjacent_reweight_factor` if row’s state is in adjacent-rank state set.

## 3) Routing improvements into pointwise expert

Near-tie routing now supports explicit gating:
- detector threshold mode (`base`, `strict`, `loose`)
- pointwise margin gate (`pointwise_margin_min`): only trust pointwise in detected near-tie if predicted pointwise gap is large enough
- uncertain-pointwise fallback choice:
  - `pairwise_binary`
  - or `generic_pointwise`

All configs are saved in manifest-style run outputs:
- `active_detector_config`
- `pointwise_expert_config`
- per-seed model provenance under `pointwise_models`

## Commands executed

```bash
python -m py_compile \
  scripts/run_near_tie_pointwise_expert_experiment.py \
  scripts/run_near_tie_policy_experiment.py \
  scripts/run_ambiguity_calibration_and_fallback_experiment.py \
  experiments/bruteforce_branch_allocator.py \
  scripts/train_bruteforce_branch_allocator.py

python scripts/run_bruteforce_branch_label_generator.py \
  --run-id near_tie_pointwise_base_20260416 \
  --dataset-name openai/gsm8k \
  --max-frontier-states 80 \
  --episodes-per-example 1 \
  --frontier-budget 7 \
  --min-remaining-budget 2 \
  --max-remaining-budget 4 \
  --init-branches 3 \
  --max-branches-per-state 4 \
  --rollout-samples-per-candidate 16 \
  --max-allocation-samples 32 \
  --seed 23

python scripts/mine_bruteforce_hard_regions.py \
  --labels-dir outputs/branch_label_bruteforce/near_tie_pointwise_base_20260416 \
  --run-id near_tie_pointwise_hard_region_mining_20260416 \
  --near-tie-margin 0.03 \
  --small-margin-threshold 0.08 \
  --high-std-threshold 0.07 \
  --max-candidates 60

python scripts/expand_bruteforce_exact_hard_regions.py \
  --base-labels-dir outputs/branch_label_bruteforce/near_tie_pointwise_base_20260416 \
  --mined-candidates-jsonl outputs/branch_label_bruteforce_targets/near_tie_pointwise_hard_region_mining_20260416/mined_hard_candidates.jsonl \
  --run-id near_tie_pointwise_hard_region_exact_expansion_20260416 \
  --max-target-pairs 60

python scripts/build_exact_augmented_target_regimes.py \
  --labels-dir outputs/branch_label_bruteforce/near_tie_pointwise_base_20260416 \
  --exact-expansion-dir outputs/branch_label_bruteforce_targets/near_tie_pointwise_hard_region_exact_expansion_20260416 \
  --run-id near_tie_pointwise_exact_augmented_regimes_20260416 \
  --near-tie-margin 0.03 \
  --high-margin-threshold 0.08 \
  --max-pair-std 0.08 \
  --tie-abs-margin-threshold 0.03 \
  --tie-relative-margin-threshold 0.15 \
  --tie-std-threshold 0.08 \
  --tie-use-near-tie-flag \
  --tie-include-approx

python scripts/run_near_tie_pointwise_expert_experiment.py \
  --targets-root outputs/branch_label_bruteforce_targets/near_tie_pointwise_exact_augmented_regimes_20260416 \
  --run-id near_tie_pointwise_expert_20260416_v2 \
  --seeds 11,29,47 \
  --feature-set v2 \
  --regimes all_pairs_approx,promoted_exact_hard_region \
  --near-tie-margin 0.03 \
  --tie-abs-margin-threshold 0.03 \
  --tie-relative-margin-threshold 0.15 \
  --tie-std-threshold 0.08 \
  --tie-use-near-tie-flag \
  --tie-include-approx \
  --abstain-confidence-threshold 0.20 \
  --calibration-methods none,temperature,platt,isotonic \
  --primary-calibration temperature \
  --near-tie-detector-abs-margin 0.03 \
  --near-tie-detector-relative-margin 0.15 \
  --near-tie-detector-std 0.08 \
  --near-tie-detector-confidence-max 0.30 \
  --near-tie-detector-use-near-tie-flag \
  --near-tie-detector-min-signals 2 \
  --detector-threshold-mode base \
  --pointwise-margin-min 0.03 \
  --pointwise-fallback-if-uncertain pairwise_binary \
  --near-tie-specialized-margin-max 0.08 \
  --near-tie-specialized-min-states 6 \
  --near-tie-reweight-factor 2.5 \
  --adjacent-reweight-factor 1.5
```

## Diagnostic findings (near-tie buckets)

3-seed means (same in both compared regimes in this bounded run):

- `pairwise_fail__pointwise_ok` vs `pairwise_fail__pointwise_fail`:
  - lower uncertainty (`pair_std`: 0.0567 vs 0.1176)
  - slightly tighter margins (`margin_abs`: 0.0449 vs 0.0583)
  - lower frontier dispersion/entropy (`frontier_score_std_mean`: 0.0910 vs 0.1259; `frontier_entropy_mean`: 0.6755 vs 1.0294)
  - small pointwise gap in both, but still positive rescue signal when uncertainty/dispersion are lower.

- `pairwise_ok__pointwise_fail` tends to have:
  - larger relative margin (0.1855) and larger rank-gap (1.25),
  - suggesting some cases are less true-near-tie but still detector-routed; pointwise can overrule pairwise incorrectly there.

Conservative diagnostic interpretation:
- pointwise rescue appears strongest in near-ties with lower uncertainty and lower frontier competition noise;
- routing quality remains important because detector spillover into less-ambiguous cases can hurt.

## Matched policy results (3-seed means, feature set fixed at `v2`)

In this bounded run, `all_pairs_approx` and `promoted_exact_hard_region` matched exactly on summary means.

1. **binary forced baseline**
- accepted: **0.5693**
- coverage: **1.0000**
- forced: **0.5693**
- top-1: **0.5238**
- near-tie forced: **0.2222**
- adjacent forced: **0.5677**

2. **calibrated abstain + pairwise backup**
- accepted: **0.6017**
- coverage: **0.7691**
- forced: **0.5693**
- top-1: **0.5238**
- near-tie forced: **0.2222**
- adjacent forced: **0.5677**

3. **dedicated near-tie + generic pointwise**
- accepted/forced: **0.5087**
- coverage: **1.0000**
- top-1: **0.4762**
- near-tie forced: **0.2222**
- adjacent forced: **0.5306**

4. **dedicated near-tie + specialized pointwise expert**
- accepted/forced: **0.5945**
- coverage: **1.0000**
- top-1: **0.6071**
- near-tie forced: **0.5556**
- adjacent forced: **0.6343**

5. **dedicated near-tie + reweighted pointwise**
- accepted/forced: **0.5087**
- coverage: **1.0000**
- top-1: **0.4762**
- near-tie forced: **0.2222**
- adjacent forced: **0.5306**

## Per-dataset and per-budget slices (forced accuracy)

Dataset (this bounded run: GSM8K only):
- baseline: **0.5693**
- near-tie+generic pointwise: **0.5087**
- near-tie+specialized pointwise: **0.5945**
- near-tie+reweighted pointwise: **0.5087**
- abstain+pairwise backup: **0.5693**

Budget slices:
- Budget 2: baseline 0.5000, generic 0.5000, specialized 0.5000, reweighted 0.5000
- Budget 3: baseline 0.7500, generic 0.7500, specialized 0.7500, reweighted 0.7500
- Budget 4: baseline 0.5833, generic 0.5000, specialized 0.6250, reweighted 0.5000

## Main question answers

### Why pointwise fallback appears to help near-ties

- It helps in a subset where detector-routed pairs have lower uncertainty and lower frontier dispersion, where pairwise is failing but pointwise can still recover.
- But generic pointwise is not robust by default under gating in this run; specialization quality matters.

### Did specialized near-tie pointwise improve near-tie slice?

- **Yes versus binary and non-pointwise baselines in this run**:
  - near-tie forced improved from 0.2222 to 0.5556.
- **No improvement over the prior best generic-pointwise result from the previous near-tie policy pass**:
  - prior best near-tie forced was also 0.5556 (with generic pointwise fallback in that run).

### Is gain local only or globally acceptable?

- In this bounded run, specialized pointwise improved not only near-tie but also overall forced and top-1 versus binary baseline.
- However, gains are policy/config dependent; generic and reweighted variants degraded overall behavior.

### What is now the main remaining bottleneck?

Most conservative interpretation:
- bottleneck now looks concentrated in **near-tie expert quality + routing quality**,
- with likely residual irreducible ambiguity in hard near-ties.
- This pass does not justify a solved claim.

## Artifacts

- Base labels:
  - `outputs/branch_label_bruteforce/near_tie_pointwise_base_20260416/`
- Hard-region mining:
  - `outputs/branch_label_bruteforce_targets/near_tie_pointwise_hard_region_mining_20260416/`
- Exact expansion:
  - `outputs/branch_label_bruteforce_targets/near_tie_pointwise_hard_region_exact_expansion_20260416/`
- Exact-augmented regimes:
  - `outputs/branch_label_bruteforce_targets/near_tie_pointwise_exact_augmented_regimes_20260416/`
- Matched near-tie pointwise expert run:
  - `outputs/branch_label_bruteforce_learning/near_tie_pointwise_expert_20260416_v2/`
  - `near_tie_pointwise_expert_results.json`
  - `near_tie_pointwise_expert_summary.json`
  - `near_tie_pointwise_expert_report.md`
