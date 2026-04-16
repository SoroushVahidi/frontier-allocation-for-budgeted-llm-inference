# Current project status (canonical)

## Scope

This is the canonical status note for the current NeurIPS-oriented project on:
- fixed-budget adaptive test-time compute allocation,
- cross-controller frontier allocation,
- branch-priority / next-step allocation over active branches.

## Core project goal

Learn and evaluate policies that decide **which active branch should receive the next unit of compute**, while respecting a fixed budget and avoiding allocation collapse.

## Final paper goal

The final paper should show that:
1. budgeted test-time compute allocation is a meaningful and distinct problem,
2. a clean frontier / controller framing is more honest than a vague “more reasoning helps” story,
3. branch ranking / next-step allocation is the right conceptual center,
4. and the main methodological challenge is supervision-target quality.

## What has been built

The repo already contains:
- a runnable frontier/controller experimentation scaffold,
- anti-collapse controller mechanisms and audits,
- branch-scorer experimentation stack,
- local-gate / stop-vs-act dataset / train / eval machinery,
- dataset and baseline integration/readiness tooling,
- oracle-label pilot infrastructure,
- provenance-aware output and reporting patterns.

## What has been learned

1. The new project framing is sound and distinct from the old binary revise-routing track.
2. Anti-collapse controller design matters for realized budget use and frontier behavior.
3. Pairwise BT remains one of the strongest active learned directions.
4. The clean conceptual center is branch ranking / next-step allocation over active branches.
5. A local stop-vs-act formulation is useful only as a bounded approximation or continuation gate.
6. Larger scale alone is unlikely to fix the current weaknesses without better targets.

## Main unresolved issue

The main unresolved issue is **supervision target quality** for branch allocation:
- proxy-label mismatch,
- noisy branch-comparison targets,
- imperfect opportunity-cost modeling,
- uneven controller robustness across budgets / seeds / datasets.

## Current methodological interpretation

The project should currently be interpreted as:

> **a strong platform and paper direction whose main open problem is learning how to compare active branches and allocate the next unit of compute well.**

## Current best next implementation direction

- Keep branch-priority / next-step allocation as the canonical conceptual center.
- Use pairwise or pointwise branch scoring as the main learned object.
- Treat any local stop-vs-act gate as a helper mechanism, not the full algorithm.
- Continue matched bounded comparisons versus strong heuristics and BT baseline.
- Integrate the most important external paper baselines carefully and fairly.

## Practical implication

The repo is already ready for serious paper planning, collaborator onboarding, and baseline integration work. The next phase should focus on sharpening the branch-comparison signal and tightening the evaluation story, not on simply adding more scale.

## Brute-force label-data status update (2026-04-16 medium run)

- A real GSM8K-backed medium-scale brute-force/near-brute-force label run has now been executed with 220 frontier states, 593 candidate rows, and 559 pairwise rows (`outputs/branch_label_bruteforce/gsm8k_medium_20260416/`).
- A matched tiny-state exact-vs-approx slice showed high but imperfect agreement (winner agreement 0.956; branch-vs-outside sign agreement 0.961), which supports approximate-mode usability as bounded supervision.
- A pilot learner trains end-to-end on this corpus and achieves non-trivial but still moderate held-out metrics, consistent with “labels usable, bottleneck not closed”.
- Canonical interpretation: label-data bottleneck is now **partially resolved**, not fully resolved. See `docs/BRUTEFORCE_LABEL_DATA_STATUS.md` for commands, artifacts, metrics, and caveats.

## Brute-force label-data scaling update (2026-04-16 multi-dataset run)

- A broader multi-dataset label campaign was executed across GSM8K, MATH-500, and AMO-Bench with multiple budget caps and multiple seeds, then merged into one provenance-preserving corpus.
- Merged corpus size reached 684 states, 1,857 candidate rows, and 1,755 pairwise rows (about 3.1x the prior medium GSM8K corpus on key row-count axes).
- Exact-vs-approx provenance is explicit in the merged corpus (`approx`: 1,770 candidate rows; `exact`: 87 candidate rows), with exact rows intentionally sparse and treated as bounded slice evidence.
- Multi-seed learned allocator training/evaluation was run on the merged corpus with full-corpus and leave-one-dataset-out slices; results are non-trivial but still mixed across datasets and margins.
- Canonical interpretation remains: the labeled-data bottleneck is **still partially resolved** (materially improved, not closed). See `docs/BRUTEFORCE_LABEL_SCALING_STATUS.md` for commands, artifacts, and metrics.


## External baseline completeness status (2026-04-16 pass)

- s1 / TALE / L1: integrated with runnable MODE A and partial MODE B adapters with explicit blocker state reporting.
- BEST-Route: upgraded to runnable-adjacent via strict import validation protocol (`scripts/verify_best_route_import.py`), with explicit adjacent-only claim boundaries.
- when_solve_when_verify: upgraded from link-only to runnable-adjacent via strict import validation protocol (`scripts/verify_when_solve_when_verify_import.py`) for SC-vs-GenRM fixed-budget adjacent comparisons.
- cascade_routing: upgraded from link-only to runnable-adjacent via strict import validation protocol (`scripts/verify_cascade_routing_import.py`) for adjacent routing/cascading/cascade-routing comparisons.
- mob_majority_of_bests: upgraded from link-only to runnable-adjacent via strict import validation protocol (`scripts/verify_mob_import.py`) for adjacent best-of-N/MoB comparisons.
- rest_mcts: upgraded from link-only to runnable-adjacent via strict import validation protocol (`scripts/verify_rest_mcts_import.py`) for adjacent process-reward-guided MCTS comparison scope only.
- openr: upgraded from link-only to runnable-adjacent via strict import validation protocol (`scripts/verify_openr_import.py`) for adjacent search-strategy comparison scope only.
- Completeness artifact: `docs/external_baseline_completeness_report.md` plus machine-readable `outputs/external_baseline_completeness_summary.{json,csv}`.
- Runnability artifact: `outputs/external_baseline_runnability/<run_id>/verification_summary.json`.

- compute_optimal_tts: moved from vague link-only to explicit blocked/protocol status with machine-readable artifacts and provenance checks.

## GBDT branch-allocator integration status (2026-04-16 bounded implementation pass)

- LightGBM LambdaRank and CatBoost YetiRankPairwise were integrated into the brute-force branch-allocator learning pipeline as matched tabular ranking baselines alongside existing linear anchors.
- Pairwise near-tie handling and uncertainty-aware weighting controls were added to training configuration/manifest paths for explicit reproducibility.
- A bounded in-workspace evaluation pass was completed and documented in `docs/GBDT_BRANCH_ALLOCATOR_STATUS.md`; results were mixed and did not justify changing the core bottleneck interpretation.

## Target-fidelity branch-comparison status (2026-04-16 bounded implementation pass)

- A manifest-backed target-construction layer now exists for branch-comparison supervision (`all_pairs`, `top_vs_rest`, `adjacent_rank`, `high_margin_only`, `uncertainty_filtered`) with pair-quality metadata.
- A targeted exact-vs-approx disagreement audit path now reports dataset/budget/margin/pair-type/branch-count slices.
- A matched regime-comparison run indicates supervision-regime choice can move pairwise learner metrics more than model-class swap alone in this bounded setting; see `docs/TARGET_FIDELITY_BRANCH_COMPARISON_STATUS.md`.

## Hard-region exact-supervision expansion status (2026-04-16 bounded implementation pass)

- A hard-region pipeline is now integrated end-to-end: hard-pair mining, bounded targeted exact relabeling, exact-augmented regime materialization, and matched multi-seed evaluation (`docs/HARD_REGION_EXACT_SUPERVISION_STATUS.md`).
- The implementation is provenance-preserving and resumable (priority-scored mined candidates; exact relabel manifests/checksums; explicit `replaced_approx_label` tracking in promoted regimes).
- In this bounded run, targeted exact promotion on mined hard regions did not produce clear improvements over all-pairs approximate baseline on the hardest reported slices (near-tie and adjacent-rank remained difficult).
- Canonical interpretation remains conservative: bottleneck is better localized and better instrumented, but not solved.

## Hard-case feature-representation status (2026-04-16 bounded implementation pass)

- Feature-set versioning (`v1` vs `v2`) is now integrated in the brute-force branch-allocation learning pipeline with a hard-case-focused feature audit path (`docs/HARD_CASE_FEATURE_REPRESENTATION_STATUS.md`).
- New engineered representation adds frontier competition context, branch rank/gap structure, verification dynamics normalization, trend/stagnation interactions, and budget-context interactions while preserving backward compatibility.
- In this bounded run, richer features materially improved the pairwise logistic baseline on near-tie and adjacent-rank slices under fixed supervision; CatBoost did not show the same lift signal.
- Conservative interpretation: representation quality is a meaningful part of the remaining bottleneck, but hard-case ambiguity is not fully resolved.
