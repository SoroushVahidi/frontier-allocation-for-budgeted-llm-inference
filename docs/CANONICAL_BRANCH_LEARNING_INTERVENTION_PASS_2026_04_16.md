# Canonical targeted intervention pass (2026-04-16)

Intervention: **balanced_hardcase_weighting** (single bounded supervision-quality change).

## Why this intervention

- Prior canonical pass showed weak hard-slice reliability and uneven hard-slice coverage pressure.
- This intervention reweights pairwise train rows by inverse frequency over `dataset x budget x hardness_bucket` to reduce supervision imbalance while keeping the same canonical corpus and matched learner stack.

## Baseline vs intervention setup

- Corpus (unchanged): `outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_v1`
- Baseline run: `real_canonical_learning_20260416_baseline_repro`
- Intervention run: `real_canonical_learning_20260416_intervention_balanced_hardcase`
- Baseline model anchor: `reweighted::pairwise`
- Intervention model anchor: `intervention::pairwise`

## Aggregate metrics (anchor model comparison)

- Pairwise acc: baseline=0.3333, intervention=0.3333, delta=+0.0000
- Top1 acc: baseline=0.0000, intervention=0.3333, delta=+0.3333

## Hard-slice metrics (anchor model comparison)

- near_tie: baseline_acc=0.0000 (n=1), intervention_acc=1.0000 (n=1), delta=+1.0000
- adjacent_rank: baseline_acc=0.3333 (n=6), intervention_acc=0.3333 (n=6), delta=+0.0000
- small_margin: baseline_acc=0.0000 (n=3), intervention_acc=0.3333 (n=3), delta=+0.3333
- exact_promoted: baseline_acc=0.0000 (n=0), intervention_acc=0.0000 (n=0), delta=+0.0000
- exact_only: baseline_acc=0.3333 (n=9), intervention_acc=0.3333 (n=9), delta=+0.0000
- approx_only: baseline_acc=0.0000 (n=0), intervention_acc=0.0000 (n=0), delta=+0.0000

## Dataset and budget slices (anchor model)

- dataset=HuggingFaceH4/MATH-500: baseline_acc=0.1667 (n=6), intervention_acc=0.0000 (n=6)
- dataset=openai/gsm8k: baseline_acc=0.6667 (n=3), intervention_acc=1.0000 (n=3)
- budget=2: baseline_acc=0.3333 (n=3), intervention_acc=0.0000 (n=3)
- budget=3: baseline_acc=0.3333 (n=6), intervention_acc=0.5000 (n=6)

## Exact commands run

- `python scripts/run_canonical_branch_learning_pass.py --canonical-corpus-dir outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_v1 --output-root outputs/canonical_branch_learning_pass --run-id real_canonical_learning_20260416_baseline_repro --seed 17 --near-tie-margin 0.03 --feature-set v2 --hard-case-mult 1.75 --exact-promoted-mult 2.0 --uncertainty-weighting`
- `python scripts/run_canonical_branch_learning_pass.py --canonical-corpus-dir outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_v1 --output-root outputs/canonical_branch_learning_pass --run-id real_canonical_learning_20260416_intervention_balanced_hardcase --seed 17 --near-tie-margin 0.03 --feature-set v2 --hard-case-mult 1.75 --exact-promoted-mult 2.0 --uncertainty-weighting --intervention balanced_hardcase_weighting --intervention-target-boost 0.6`

## Interpretation (conservative)

- This intervention improved near-tie and small-margin accuracy for the pairwise anchor model in this bounded run, with no aggregate pairwise gain and a top1 gain in this tiny held-out split.
- Exact-promoted slice remains unresolved because held-out coverage is zero in both baseline and intervention (`n=0`).
- Because near-tie test coverage is tiny (`n=1`), this is suggestive protocol evidence, not strong bottleneck-closure evidence.
- Overall diagnosis remains: supervision-target quality/coverage is still a first-order bottleneck; weighting helps behavior but does not solve fidelity limits.
