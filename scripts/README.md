# Scripts index

All scripts write run artifacts under `outputs/` unless overridden.

## Short entry paths

- Current project entry path: [`CANONICAL_START_HERE.md`](CANONICAL_START_HERE.md)
- Current repository interpretation: [`../docs/CANONICAL_START_HERE.md`](../docs/CANONICAL_START_HERE.md)
- Goal-based repo navigation: [`../docs/REPOSITORY_START_PATHS.md`](../docs/REPOSITORY_START_PATHS.md)
- Full code/document map: [`../docs/REPO_MAP.md`](../docs/REPO_MAP.md)
- Historical script entry points: [`HISTORICAL_INDEX.md`](HISTORICAL_INDEX.md)

## Interpretation labels

- **Canonical**: current frontier-allocation path for the NeurIPS-oriented project.
- **Exploratory**: useful active branches and diagnostics, not settled default winners.
- **Integration/prep**: dataset/baseline readiness tooling.
- **Historical**: older-track support scripts retained only for provenance.

## Most common workflows

### 1. Run the current paper path
Use:
- `run_cross_strategy_frontier_allocation.py`
- `run_multi_action_allocation_pass.sh`
- `evaluate_branch_scorer_controller.py`
- `evaluate_branch_scorer_robustness.py`
- `run_new_paper_frontier_matrix.py`
- `run_comparative_frontier_audit.py`
- `run_imported_methodology_frontier_eval.py`

### 2. Work on hard ambiguous cases / branch-allocation learning
Use:
- `build_bruteforce_target_regimes.py`
- `train_bruteforce_branch_allocator.py`
- `run_target_fidelity_regime_experiment.py`
- `run_hard_case_feature_representation_experiment.py`
- `run_ambiguity_calibration_and_fallback_experiment.py`
- `run_near_tie_policy_experiment.py`
- `run_near_tie_pointwise_expert_experiment.py`
- `run_pairwise_svm_margin_experiment.py`
- `run_structured_ambiguity_experiment.py`
- `run_defer_fallback_experiment.py`

### 3. Check datasets and external baselines
Use:
- `verify_hf_dataset_access.py`
- `generate_dataset_integration_report.py`
- `generate_external_baseline_integration_report.py`
- `list_external_baselines.py`

## Canonical scripts (current project path)

| Script | Role |
|---|---|
| `run_cross_strategy_frontier_allocation.py` | Main frontier-allocation scaffold (legacy filename) |
| `run_multi_action_allocation_pass.sh` | Multi-action allocation run wrapper |
| `evaluate_branch_scorer_controller.py` | Controller-level comparison for learned/heuristic policies |
| `evaluate_branch_scorer_robustness.py` | Multi-seed/budget/init robustness sweep |
| `run_new_paper_frontier_matrix.py` | Frontier matrix / anti-collapse summary tables |
| `run_comparative_frontier_audit.py` | Matched-budget comparative audit |
| `run_imported_methodology_frontier_eval.py` | Bounded old-manuscript-style evaluation layer (matched/fixed-vs-adaptive-vs-oracle/frontier/signal-slice) for current branch allocation |
| `wulver_comparative_frontier_audit.sh` | Wulver/cluster wrapper (API keys, env); called from `jobs/comparative_frontier_audit_wulver.sbatch` |
| `run_light_external_style_baseline_comparison.py` | Lightweight internal-vs-external-style local comparison |
| `run_light_anchor_vs_s1_comparison.py` | Lightweight matched anchor vs external s1 baseline adapter |
| `run_new_paper_stop_vs_act_controller.py` | Stop-vs-act lightweight pipeline (dataset + train/eval) |
| `run_new_paper_stop_vs_act_target_stabilization_pass.py` | Bounded default-target stabilization/variance-reduction comparison |
| `run_new_paper_stop_vs_act_matched_comparator_pass.py` | Bounded matched ACT-vs-STOP comparator pass |
| `run_new_paper_stop_vs_act_policy_coupled_stop_pass.py` | Bounded policy-coupled STOP-baseline pass |

## Exploratory branch-scorer workflows

| Script | Role |
|---|---|
| `run_new_paper_bt_pairwise_branch_scorer.py` | End-to-end pairwise BT pipeline |
| `run_new_paper_bt_reliability_weighted_branch_scorer.py` | Reliability-aware BT variants |
| `run_new_paper_external_warmstart_branch_scorer.py` | External warm-start variants |
| `run_new_paper_tie_aware_bt.py` | Tie-aware BT variant |
| `run_new_paper_tie_aware_bt_stability.py` | Tie-aware stability/calibration checks |
| `run_new_paper_tie_aware_hybrid_gating.py` | Hybrid gating variant |
| `run_new_paper_ambiguous_branch_dataset.py` | Ambiguous-pair dataset construction |
| `run_new_paper_ambiguous_pair_targeted_experiment.py` | Targeted ambiguous-pair experiment |
| `run_new_paper_pairwise_diagnostic_audit.py` | Pairwise confidence/label diagnostics |
| `run_new_paper_raokupper_resolution_audit.py` | Rao-Kupper contradiction-resolution audit |
| `run_new_paper_raokupper_confirmation.py` | Bounded independent confirmation for Rao-Kupper audit |

## Integration/preparation scripts

| Script | Role |
|---|---|
| `verify_hf_dataset_access.py` | Verify evaluation-dataset access (HF + git-clone-backed dataset keys) and summarize status |
| `dataset_smoke_sample.py` | Lightweight dataset smoke samples (HF datasets + local-clone datasets such as NaturalPlan) |
| `generate_dataset_integration_report.py` | Main evaluation-dataset integration report (includes MATH-500, AMO-Bench, and NaturalPlan clone-path status) |
| `verify_external_reasoning_datasets.py` | External supervision access/schema checks |
| `generate_external_reasoning_dataset_integration_report.py` | External supervision integration report |
| `build_canonical_branch_learning_corpus.py` | Build canonical processed branch-learning corpora (candidate/pairwise/outside-option rows, manifests, checksums, hard-slice summaries) |
| `run_canonical_branch_learning_pass.py` | Run a matched canonical learning pass from canonical corpora with aggregate + hard-slice metrics and machine-readable summaries |
| `run_protected_strata_holdout_expansion.py` | Runs one bounded split-seed holdout expansion pass targeting sparse protected strata, materializes a split-frozen corpus, and writes a reusable protected-strata holdout manifest. |
| `build_external_prm_mathshepherd_apps_corpus.py` | Build conservative canonical-aligned external rows (PRM800K/Math-Shepherd/APPS) with provenance and readiness summary |
| `prepare_external_reasoning_datasets.py` | Readiness ranking and normalized previews |
| `generate_external_baseline_integration_report.py` | External baseline integration report |
| `list_external_baselines.py` | Print external baseline registry |

## Historical/provenance scripts

Historical script entry points have been moved to:
- [`HISTORICAL_INDEX.md`](HISTORICAL_INDEX.md)
- `../archive/historical_scripts/`

## Notes

- `run_cross_strategy_frontier_allocation.py` keeps a legacy filename for compatibility; docs refer to this as cross-controller frontier allocation.
- Current canonical method direction is documented in `../docs/STOP_VS_ACT_DIRECTION.md` and the broader branch-allocation docs; stop-vs-act is a bounded helper formulation, not the whole project identity.

## Oracle-label pilot execution and current hard-case learning path

| Script | Role |
|---|---|
| `run_bruteforce_branch_label_generator.py` | Heavy-compute branch-comparison label generator: builds frontier states, runs exact/approx continuation evaluations, emits candidate/pairwise/outside-option labels with resume-safe auditable artifacts. |
| `analyze_bruteforce_label_quality.py` | Produces label-quality diagnostics for brute-force runs (counts, margin/near-tie/gap distributions, per-budget breakdown, and exact-vs-approx agreement) and optional pilot-learner summary. |
| `train_bruteforce_branch_allocator.py` | Trains pairwise / pointwise / outside-option / defer-aware / fallback-aware branch-allocation models from brute-force label artifacts and writes evaluation + manifests. |
| `evaluate_bruteforce_branch_allocator.py` | Re-evaluates trained brute-force-label branch allocators with near-tie, ranking, mode-slice, budget-slice, and dataset-slice metrics. |
| `merge_bruteforce_branch_label_runs.py` | Consolidates multiple brute-force run directories into a single provenance-preserving merged corpus with dataset/budget/mode/near-tie summaries and output checksums. |
| `run_bruteforce_allocator_scaling_experiment.py` | Multi-seed allocator scaling runner over a merged corpus with full-corpus evaluation plus leave-one-dataset-out generalization slices, including linear baselines and GBDT ranking baselines (LightGBM LambdaRank + CatBoost YetiRankPairwise when available). |
| `build_bruteforce_target_regimes.py` | Builds manifest-backed pair-construction target regimes (including budget-priced penalized-marginal left/right/defer supervision) with pair-quality metadata and optional exact-label promotion. |
| `audit_bruteforce_exact_vs_approx_pairs.py` | Runs targeted exact-vs-approx disagreement audits with slices by dataset, budget, margin bucket, branch count, and pair type. |
| `run_target_fidelity_regime_experiment.py` | Runs matched multi-seed learner comparisons across target regimes to isolate supervision-quality effects from model-class effects. |
| `mine_bruteforce_hard_regions.py` | Mines hard branch-comparison regions (near-tie/small-margin/high-uncertainty/adjacent-rank/disagreement-risk) and emits priority-scored relabel candidates with provenance. |
| `expand_bruteforce_exact_hard_regions.py` | Runs bounded exact relabeling only for mined hard-region pairs, with resume-safe progress, per-row provenance, and manifest checksums. |
| `build_exact_augmented_target_regimes.py` | Materializes exact-augmented supervision regimes that combine approximate easy-region labels with selectively promoted exact hard-region labels. |
| `run_hard_region_exact_supervision_experiment.py` | Executes matched multi-seed learning across exact-augmented regimes and reports hard-slice metrics (near-tie, adjacent-rank, exact-promoted). |
| `audit_bruteforce_feature_representation.py` | Audits hard-case feature coverage (v1 vs v2 vs richer paths) and emits canonical feature-audit artifacts for near-tie/adjacent slices. |
| `run_hard_case_feature_representation_experiment.py` | Runs matched old-vs-richer feature-set experiments on fixed supervision regimes and reports hard-slice metrics. |
| `run_ternary_or_abstain_branch_comparison_experiment.py` | Runs matched binary-forced vs ternary tie-aware vs selective-abstention branch-comparison experiments, including penalized-marginal defer metrics (coverage/fallback/near-tie slices). |
| `run_ambiguity_calibration_and_fallback_experiment.py` | Runs matched ambiguity-handling experiments for abstention/tie decisions with confidence calibration (none/temperature/Platt/isotonic) and configurable fallback policies. |
| `run_near_tie_policy_experiment.py` | Runs matched dedicated near-tie detection/routing experiments, including non-forced balanced/shared fallback policy comparisons against binary and calibrated-abstention baselines. |
| `run_near_tie_pointwise_expert_experiment.py` | Runs matched dedicated near-tie pointwise-expert experiments with specialized/reweighted pointwise fallbacks, routing gates, and near-tie pairwise-vs-pointwise diagnostic artifacts. |
| `run_pairwise_svm_margin_experiment.py` | Runs matched logistic-vs-SVM bounded margin comparisons on hard branch-comparison regimes. |
| `run_structured_ambiguity_experiment.py` | Runs matched v2/v3 representation, defer-target, and oracle-proxy defer comparisons focused on ambiguous hard cases. |
| `run_defer_fallback_experiment.py` | Runs matched defer-only vs defer-plus-fallback policy comparisons, including binary, pointwise, outside-option-aware, and optional deferred-specialist backups. |
| `run_branch_value_uncertainty_derived_defer_experiment.py` | Bounded branch-level value-target + uncertainty-head pass; derives pairwise preference vs defer from predicted value-gap and uncertainty-adjusted separation, then reports coverage/accepted-accuracy hard slices. |
| `run_branch_value_uncertainty_strict_validation_pass.py` | Strict validation harness for the branch-value+uncertainty method: matched ablations (value-only/raw-uncertainty/learned-risk/outside-option/full), baseline comparisons, and hard-slice budget/dataset diagnostics. |
| `run_cohere_rerank_branch_allocation_experiment.py` | Bounded Cohere Rerank listwise branch-scoring comparison over canonical candidate sets with matched top-1 proxy metrics vs heuristic/pairwise baselines. |

## Notes on learning workflows

- `train_bruteforce_branch_allocator.py` is the main unified training entrypoint for branch-allocation learning from brute-force supervision artifacts.
- The current hard-case line should usually be interpreted through the paired docs notes in `../docs/STRUCTURED_AMBIGUITY_STATUS_2026_04_18.md`, `../docs/ORACLE_PROXY_DEFER_TARGET_STATUS.md`, and `../docs/DEFER_CONDITIONED_FALLBACK_STATUS.md`.
- Hard-case experiments should usually be interpreted together with the relevant docs notes in `../docs/` rather than as standalone headline results.
- Use `../docs/OUTPUTS_INTERPRETATION_GUIDE.md` when reviewing generated artifacts under `outputs/`.
