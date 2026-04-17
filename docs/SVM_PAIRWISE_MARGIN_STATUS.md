# SVM pairwise margin baseline status

## Why this was added

This adds a bounded, reproducible margin-based learned baseline for the existing fixed-budget cross-controller frontier branch-allocation framing.
The intent is diagnostic: test whether margin geometry helps ambiguous hard-case comparisons (especially near-tie and adjacent-rank slices) under the same pairwise supervision setup.

## Implemented variants

- `pairwise_linear_svm` (primary): `LinearSVC` trained on pairwise `x_diff` rows already used by pairwise logistic regression.
- `pairwise_nystroem_svm` (bounded experimental path): RBF `Nystroem` feature map + `LinearSVC`, with deterministic capped training rows.

Configuration surface is in `LearningConfig` and CLI flags in `scripts/train_bruteforce_branch_allocator.py` (`train_pairwise_svm_nystroem`, `svm_nystroem_gamma`, `svm_max_train_rows_for_nystroem`, etc.).

## Weighting support

Both implemented variants apply existing `pair_train_weight` values through `sample_weight` during SVM fitting.
This preserves current near-tie filtering/downweighting and uncertainty-aware weighting effects insofar as those are encoded in pairwise training rows/weights.

## Ranking interpretation

For pairwise-difference-only SVM models, pairwise metrics are primary.
`ranking_top1_accuracy_test` is intentionally omitted (`null`) because candidate-wise scalar scores are not directly defined from kernelized pairwise-difference models under the current scorer abstraction.

## Safe interpretation

- This is a bounded margin-based diagnostic baseline, not a replacement claim over the current strongest scaffold.
- If gains appear in near-tie / adjacent-rank / exact-promoted-hard-region slices, interpret that as evidence boundary geometry can matter under the current supervision target.
- If gains do not appear, that also supports the standing interpretation that model class changes alone are unlikely to resolve the core bottleneck.
