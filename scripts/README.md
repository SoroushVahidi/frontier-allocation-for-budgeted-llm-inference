# Scripts index

All scripts write run artifacts under `outputs/` unless overridden.

## Fast start

- Current project entry path: [`CANONICAL_START_HERE.md`](CANONICAL_START_HERE.md)
- Current repository interpretation: [`../docs/CANONICAL_START_HERE.md`](../docs/CANONICAL_START_HERE.md)
- Full code/document map: [`../docs/REPO_MAP.md`](../docs/REPO_MAP.md)

## Interpretation labels

- **Canonical**: current frontier-allocation path for the NeurIPS-oriented project.
- **Exploratory**: useful active branches and diagnostics, not settled default winners.
- **Integration/prep**: dataset/baseline readiness tooling.
- **Historical**: older-track support scripts retained for provenance.

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

| Script | Role |
|---|---|
| `run_heavy_real_routing_eval.sh` | Older binary revise-routing track support |
| `run_final_manuscript_eval.sh` | Older manuscript evaluation wrapper |

## Notes

- `run_cross_strategy_frontier_allocation.py` keeps a legacy filename for compatibility; docs refer to this as cross-controller frontier allocation.
- Current canonical method direction is documented in `../docs/STOP_VS_ACT_DIRECTION.md` and the broader branch-allocation docs; stop-vs-act is a bounded helper formulation, not the whole project identity.

## Oracle-label pilot execution

| Script | Role |
|---|---|
| `run_bruteforce_branch_label_generator.py` | Heavy-compute branch-comparison label generator: builds frontier states, runs exact/approx continuation evaluations, emits candidate/pairwise/outside-option labels with resume-safe auditable artifacts. |
| `analyze_bruteforce_label_quality.py` | Produces label-quality diagnostics for brute-force runs (counts, margin/near-tie/gap distributions, per-budget breakdown, and exact-vs-approx agreement) and optional pilot-learner summary. |
| `train_bruteforce_branch_allocator.py` | Trains pairwise / pointwise / outside-option branch-allocation models from brute-force label artifacts and writes evaluation + manifests. |
| `evaluate_bruteforce_branch_allocator.py` | Re-evaluates trained brute-force-label branch allocators with near-tie, ranking, mode-slice, budget-slice, and dataset-slice metrics. |
| `merge_bruteforce_branch_label_runs.py` | Consolidates multiple brute-force run directories into a single provenance-preserving merged corpus with dataset/budget/mode/near-tie summaries and output checksums. |
| `run_bruteforce_allocator_scaling_experiment.py` | Multi-seed allocator scaling runner over a merged corpus with full-corpus evaluation plus leave-one-dataset-out generalization slices, including linear baselines and GBDT ranking baselines (LightGBM LambdaRank + CatBoost YetiRankPairwise when available). |
| `build_bruteforce_target_regimes.py` | Builds manifest-backed pair-construction target regimes (all-pairs, top-vs-rest, adjacent-rank, high-margin-only, uncertainty-filtered) with pair-quality metadata and optional exact-label promotion. |
| `audit_bruteforce_exact_vs_approx_pairs.py` | Runs targeted exact-vs-approx disagreement audits with slices by dataset, budget, margin bucket, branch count, and pair type. |
| `run_target_fidelity_regime_experiment.py` | Runs matched multi-seed learner comparisons across target regimes to isolate supervision-quality effects from model-class effects. |
| `mine_bruteforce_hard_regions.py` | Mines hard branch-comparison regions (near-tie/small-margin/high-uncertainty/adjacent-rank/disagreement-risk) and emits priority-scored relabel candidates with provenance. |
| `expand_bruteforce_exact_hard_regions.py` | Runs bounded exact relabeling only for mined hard-region pairs, with resume-safe progress, per-row provenance, and manifest checksums. |
| `build_exact_augmented_target_regimes.py` | Materializes exact-augmented supervision regimes that combine approximate easy-region labels with selectively promoted exact hard-region labels. |
| `run_hard_region_exact_supervision_experiment.py` | Executes matched multi-seed learning across exact-augmented regimes and reports hard-slice metrics (near-tie, adjacent-rank, exact-promoted). |
| `audit_bruteforce_feature_representation.py` | Audits hard-case feature coverage (v1 vs v2) and emits canonical feature-audit artifacts for near-tie/adjacent slices. |
| `run_hard_case_feature_representation_experiment.py` | Runs matched old-vs-richer feature-set experiments on fixed supervision regimes and reports hard-slice metrics. |
| `run_ternary_or_abstain_branch_comparison_experiment.py` | Runs matched binary-forced vs ternary tie-aware vs selective-abstention branch-comparison experiments with configurable tie-band rules and explicit fallback semantics. |
| `run_ambiguity_calibration_and_fallback_experiment.py` | Runs matched ambiguity-handling experiments for abstention/tie decisions with confidence calibration (none/temperature/Platt/isotonic) and configurable fallback policies. |
| `run_near_tie_policy_experiment.py` | Runs matched dedicated near-tie detection/routing experiments, including non-forced balanced/shared fallback policy comparisons against binary and calibrated-abstention baselines. |
| `run_near_tie_pointwise_expert_experiment.py` | Runs matched dedicated near-tie pointwise-expert experiments with specialized/reweighted pointwise fallbacks, routing gates, and near-tie pairwise-vs-pointwise diagnostic artifacts. |

### Brute-force allocator learning: GBDT ranking + uncertainty-aware options

`train_bruteforce_branch_allocator.py` now supports:

- **GBDT ranking baselines**:
  - LightGBM LambdaRank (`lightgbm_ranker`)
  - CatBoost YetiRankPairwise (`catboost_ranker`)
- **Near-tie handling for pairwise linear learner**:
  - `--pairwise-near-tie-action {none,filter,downweight}`
  - `--pairwise-near-tie-downweight <float>`
- **Uncertainty-aware pairwise weighting**:
  - `--uncertainty-weighting`
  - `--margin-weight-power`
  - `--std-weight-scale`
  - `--approx-mode-weight`
  - `--exact-mode-weight`

Example (matched linear + GBDT run):

```bash
python scripts/train_bruteforce_branch_allocator.py \
  --labels-dir outputs/branch_label_bruteforce_merged/<merged_run_id> \
  --run-id gbdt_matched_baseline \
  --seed 17 \
  --near-tie-margin 0.03
```

Example (uncertainty-aware pairwise weighting):

```bash
python scripts/train_bruteforce_branch_allocator.py \
  --labels-dir outputs/branch_label_bruteforce_merged/<merged_run_id> \
  --run-id gbdt_uncertainty_weighted \
  --seed 17 \
  --near-tie-margin 0.03 \
  --pairwise-near-tie-action downweight \
  --pairwise-near-tie-downweight 0.2 \
  --uncertainty-weighting
```

Example (multi-seed matched scaling + leave-one-dataset-out):

```bash
python scripts/run_bruteforce_allocator_scaling_experiment.py \
  --labels-dir outputs/branch_label_bruteforce_merged/<merged_run_id> \
  --run-id gbdt_scaling_matched \
  --seeds 11,29,47 \
  --near-tie-margin 0.03
```

### Target-fidelity / pair-construction workflow

Build pair-construction regimes with pair-quality metadata:

```bash
python scripts/build_bruteforce_target_regimes.py \
  --labels-dir outputs/branch_label_bruteforce_merged/<approx_run> \
  --run-id target_regimes_v1 \
  --exact-labels-dir outputs/branch_label_bruteforce_merged/<exact_run> \
  --promote-exact-over-approx
```

Run exact-vs-approx targeted disagreement audit:

```bash
python scripts/audit_bruteforce_exact_vs_approx_pairs.py \
  --approx-labels-dir outputs/branch_label_bruteforce_targets/target_regimes_v1/regime_all_pairs \
  --exact-labels-dir outputs/branch_label_bruteforce_targets/target_regimes_exact_v1/regime_all_pairs \
  --output-dir outputs/branch_label_bruteforce_targets/target_regimes_v1/exact_vs_approx_audit
```

Run matched multi-seed learning across regimes:

```bash
python scripts/run_target_fidelity_regime_experiment.py \
  --targets-root outputs/branch_label_bruteforce_targets/target_regimes_v1 \
  --run-id target_fidelity_learning_v1 \
  --seeds 11,29,47 \
  --near-tie-margin 0.03
```

### Hard-region exact-supervision workflow

Mine hard relabeling candidates:

```bash
python scripts/mine_bruteforce_hard_regions.py \
  --labels-dir outputs/branch_label_bruteforce/<base_run_id> \
  --run-id hard_region_mining_v1 \
  --near-tie-margin 0.03 \
  --small-margin-threshold 0.08 \
  --high-std-threshold 0.07 \
  --max-candidates 200
```

Run targeted exact relabeling for mined hard pairs:

```bash
python scripts/expand_bruteforce_exact_hard_regions.py \
  --base-labels-dir outputs/branch_label_bruteforce/<base_run_id> \
  --mined-candidates-jsonl outputs/branch_label_bruteforce_targets/hard_region_mining_v1/mined_hard_candidates.jsonl \
  --run-id hard_region_exact_expansion_v1 \
  --max-target-pairs 200
```

Build exact-augmented regimes and run matched evaluation:

```bash
python scripts/build_exact_augmented_target_regimes.py \
  --labels-dir outputs/branch_label_bruteforce/<base_run_id> \
  --exact-expansion-dir outputs/branch_label_bruteforce_targets/hard_region_exact_expansion_v1 \
  --run-id hard_region_exact_augmented_regimes_v1

python scripts/run_hard_region_exact_supervision_experiment.py \
  --targets-root outputs/branch_label_bruteforce_targets/hard_region_exact_augmented_regimes_v1 \
  --run-id hard_region_exact_matched_v1 \
  --seeds 11,29,47 \
  --near-tie-margin 0.03
```

### Hard-case feature-representation workflow

Run feature audit on a fixed regime:

```bash
python scripts/audit_bruteforce_feature_representation.py \
  --labels-dir outputs/branch_label_bruteforce_targets/<regime_root>/regime_promoted_exact_hard_region \
  --run-id hard_case_feature_audit_v1 \
  --near-tie-margin 0.03
```

Run matched v1-vs-v2 feature experiments (same supervision):

```bash
python scripts/run_hard_case_feature_representation_experiment.py \
  --targets-root outputs/branch_label_bruteforce_targets/<regime_root> \
  --run-id hard_case_feature_representation_v1 \
  --seeds 11,29,47 \
  --feature-sets v1,v2 \
  --regimes all_pairs_approx,promoted_exact_hard_region \
  --near-tie-margin 0.03
```

Direct learner training with richer features is also available:

```bash
python scripts/train_bruteforce_branch_allocator.py \
  --labels-dir outputs/branch_label_bruteforce_targets/<regime_root>/regime_promoted_exact_hard_region \
  --run-id hard_case_feature_train_v2 \
  --feature-set v2
```

### Ternary / selective-abstention branch-comparison workflow

Build exact-augmented regimes with tie/ambiguous annotations:

```bash
python scripts/build_exact_augmented_target_regimes.py \
  --labels-dir outputs/branch_label_bruteforce/<base_run_id> \
  --exact-expansion-dir outputs/branch_label_bruteforce_targets/<exact_expansion_run_id> \
  --run-id ternary_abstain_regimes_v1 \
  --tie-abs-margin-threshold 0.03 \
  --tie-relative-margin-threshold 0.15 \
  --tie-std-threshold 0.08 \
  --tie-use-near-tie-flag \
  --tie-include-approx
```

Run matched binary vs ternary vs abstaining comparison with fixed feature representation (`v2`):

```bash
python scripts/run_ternary_or_abstain_branch_comparison_experiment.py \
  --targets-root outputs/branch_label_bruteforce_targets/ternary_abstain_regimes_v1 \
  --run-id ternary_or_abstain_v1 \
  --seeds 11,29,47 \
  --feature-set v2 \
  --regimes all_pairs_approx,promoted_exact_hard_region \
  --tie-abs-margin-threshold 0.03 \
  --tie-relative-margin-threshold 0.15 \
  --tie-std-threshold 0.08 \
  --tie-use-near-tie-flag \
  --tie-include-approx \
  --abstain-confidence-threshold 0.20 \
  --fallback-policy pointwise_value
```

### Ambiguity calibration + fallback workflow

Run matched calibration/fallback comparisons on fixed feature representation (`v2`):

```bash
python scripts/run_ambiguity_calibration_and_fallback_experiment.py \
  --targets-root outputs/branch_label_bruteforce_targets/<regime_root> \
  --run-id ambiguity_calibration_fallback_v1 \
  --seeds 11,29,47 \
  --feature-set v2 \
  --regimes all_pairs_approx,promoted_exact_hard_region \
  --calibration-methods none,temperature,platt,isotonic \
  --primary-calibration temperature \
  --abstain-confidence-threshold 0.20 \
  --ternary-fallback-policy outside_option_aware
```

### Dedicated near-tie policy workflow

Run matched dedicated near-tie routing comparisons under fixed representation (`v2`):

```bash
python scripts/run_near_tie_policy_experiment.py \
  --targets-root outputs/branch_label_bruteforce_targets/<regime_root> \
  --run-id near_tie_policy_v1 \
  --seeds 11,29,47 \
  --feature-set v2 \
  --regimes all_pairs_approx,promoted_exact_hard_region \
  --primary-calibration temperature \
  --abstain-confidence-threshold 0.20 \
  --near-tie-detector-abs-margin 0.03 \
  --near-tie-detector-relative-margin 0.15 \
  --near-tie-detector-std 0.08 \
  --near-tie-detector-confidence-max 0.30 \
  --near-tie-detector-use-near-tie-flag \
  --near-tie-detector-min-signals 2
```

### Dedicated near-tie pointwise expert workflow

Run matched near-tie pointwise-expert comparisons (generic vs specialized vs reweighted pointwise fallback):

```bash
python scripts/run_near_tie_pointwise_expert_experiment.py \
  --targets-root outputs/branch_label_bruteforce_targets/<regime_root> \
  --run-id near_tie_pointwise_expert_v1 \
  --seeds 11,29,47 \
  --feature-set v2 \
  --regimes all_pairs_approx,promoted_exact_hard_region \
  --primary-calibration temperature \
  --detector-threshold-mode base \
  --pointwise-margin-min 0.03 \
  --pointwise-fallback-if-uncertain pairwise_binary \
  --near-tie-specialized-margin-max 0.08 \
  --near-tie-specialized-min-states 6 \
  --near-tie-reweight-factor 2.5 \
  --adjacent-reweight-factor 1.5
```
| `run_oracle_label_pilot_hpc.sh` | HPC-oriented wrapper: preflight, optional manifest build, generator hook, validator gate, run summary |
| `run_oracle_label_generator_interface_stub.py` | Interface-stabilization stub CLI for heavy generator contract; supports testing-only `--mock-mode` outputs |
| `run_oracle_label_generator_prototype.py` | First real paired-rollout oracle-label prototype generator (limited subset, CPU-oriented) |
| `run_oracle_label_generator_heavy.py` | Production-leaning heavy-path generator with resume/progress/state-error handling for shard-scale runs |
| `oracle_label_pilot_sharding.py` | Deterministic shard split/merge utility for pilot-state manifests and per-shard oracle-label outputs |
| `run_allocation_target_generator_heavy.py` | Resumable heavy-path allocation-target generator; emits outside-option + pairwise labels with progress/state-error checkpoints |
| `allocation_target_pilot_sharding.py` | Deterministic shard split/merge utility for allocation-target state manifests and per-shard outside/pairwise outputs |
| `build_stop_vs_act_oracle_distillation_dataset.py` | Selective-distillation preprocessing: bucket oracle rows into accepted/borderline/rejected, apply manifest-aware mock checks, and emit weighted distillation-ready JSONL |
| `build_random_matched_coverage_oracle_distillation_dataset.py` | Build deterministic random matched-coverage distillation baselines per regime (accepted-only or accepted+borderline), including repeated-draw mode and overlap summaries |
| `train_oracle_distilled_stop_vs_act_student.py` | Oracle-distilled student train/eval path with retained-coverage accounting, ACT-rate reporting, and required slice summaries (uncertainty/margin/disagreement/budget) |
| `compare_oracle_distilled_stop_vs_act_runs.py` | Matched-control comparison scaffold with required roles (anchor, accepted-only, accepted+borderline, matched random), repeated-random variance summaries, and readiness gates |
| `run_oracle_distilled_regime_bundle.py` | Regime-level orchestration runner that bundles repeated random draws, selective/anchor/random student runs, and one comparison-ready package |


### Frontier target-construction command examples

#### Tiny pilot (local exact-mode smoke)

Use a tiny deterministic state-manifest build and a tiny generation pass for local validation.

```bash
RUN_ID="tiny_$(date -u +%Y%m%dT%H%M%SZ)"
OUT_ROOT="outputs/frontier_target_construction/${RUN_ID}"

python3 scripts/build_oracle_label_pilot_state_manifest.py \
  --selection-config configs/stop_vs_act_oracle_pilot_state_selection_v1.json \
  --output-dir "${OUT_ROOT}/state_manifest" \
  --max-candidate-rows 64

python3 scripts/run_oracle_label_generator_heavy.py \
  --pilot-config configs/stop_vs_act_oracle_label_pilot_v1.json \
  --selection-config configs/stop_vs_act_oracle_pilot_state_selection_v1.json \
  --state-manifest "${OUT_ROOT}/state_manifest/pilot_state_manifest.jsonl" \
  --output-dir "${OUT_ROOT}/labels" \
  --max-states 32 \
  --paired-rollouts 2
```

> Note: branch-value exactness is still row-level (`value_is_exact`) and only exact for trivial terminal/zero-budget cases.

#### Heavy long-run (approximate mode, resume, shard-aware)

For longer runs, use deterministic sharding and heavy generator resume support.

```bash
RUN_ID="heavy_$(date -u +%Y%m%dT%H%M%SZ)"
OUT_ROOT="outputs/frontier_target_construction/${RUN_ID}"

python3 scripts/oracle_label_pilot_sharding.py split \
  --state-manifest outputs/stop_vs_act_oracle_pilot_state_manifest/pilot_state_manifest.jsonl \
  --num-shards 16 \
  --output-dir "${OUT_ROOT}/split"

python3 scripts/run_oracle_label_generator_heavy.py \
  --pilot-config configs/stop_vs_act_oracle_label_pilot_v1.json \
  --selection-config configs/stop_vs_act_oracle_pilot_state_selection_v1.json \
  --state-manifest "${OUT_ROOT}/split/shard_manifests/shard_000.jsonl" \
  --output-dir "${OUT_ROOT}/shards/shard_000" \
  --split-manifest "${OUT_ROOT}/split/shard_split_manifest.json" \
  --shard-name shard_000 \
  --shard-id 0 \
  --expected-state-count 75 \
  --paired-rollouts 8 \
  --resume \
  --continue-on-state-error \
  --max-state-errors 10
```

#### Output tree + manifest quick reference

```text
outputs/frontier_target_construction/<run_id>/
  state_manifest/
    pilot_state_manifest.jsonl
    pilot_state_manifest_meta.json
    pilot_state_manifest_schema.json
  split/                               # optional sharded runs
    shard_split_manifest.json
    shard_manifests/shard_XXX.jsonl
  labels/ or shards/shard_XXX/
    oracle_stop_vs_act_labels.jsonl
    oracle_label_manifest.json
    oracle_label_progress.json
    oracle_label_state_errors.jsonl
```

Manifest notes:
- `oracle_label_manifest.json`: run provenance, config pointers, output completeness, and error stats.
- `oracle_label_progress.json`: rolling progress, including resume skips and last processed `state_id`.
- `shard_split_manifest.json`: deterministic shard membership and source-manifest hash for merge-time verification.

## s1 baseline integration scripts (fair split)

| Script | Role |
|---|---|
| `run_s1_budget_forcing_baseline.py` | Canonical s1 fair-baseline runner with MODE A (inference-only) and MODE B (strict official/full import + verification). MODE B emits `official_mode_import.csv`, `official_mode_import_report.md`, `fairness_report.md`, and `manifest.json` under `outputs/s1_baseline/<run_id>/`. |
| `run_s1_baseline_comparison_bundle.py` | Merge one or more s1 run directories into manuscript-ready aggregate comparison artifacts. |
| `verify_s1_mode_b_import.py` | Strict validator for s1 MODE B official/full import packages (required files, metadata schema, fairness checks, and table-readiness checks). |
| `generate_s1_mode_b_import_report.py` | Generates reviewer-facing markdown report from MODE B verification JSON. |

## TALE baseline integration scripts (fair split)

| Script | Role |
|---|---|
| `run_tale_baseline.py` | Canonical TALE fair-baseline runner with MODE A (prompt budgeting inference-only) and MODE B (strict official/full import + verification with TALE-vs-TALE-PT variant separation). MODE B emits `official_mode_import.csv`, `official_mode_import_report.md`, `fairness_report.md`, and `manifest.json` under `outputs/tale_baseline/<run_id>/`. |
| `run_tale_comparison_bundle.py` | Merge one or more TALE run directories into manuscript-ready aggregate comparison artifacts. |
| `verify_tale_mode_b_import.py` | Strict validator for TALE MODE B official/full import packages (schema, provenance, fairness checks, and TALE-vs-TALE-PT variant separation checks). |
| `generate_tale_mode_b_import_report.py` | Generates reviewer-facing markdown report from TALE MODE B verification JSON. |

## L1 baseline integration scripts (fair split)

| Script | Role |
|---|---|
| `run_l1_baseline.py` | Canonical L1 fair-baseline runner with MODE A (inference-only L1-style Exact/Max length control adapter) and MODE B (official/full adapter reporting). Writes manifest, summary CSV, per-example JSONL, fairness report, and comparison tables under `outputs/l1_baseline/`. |
| `run_l1_comparison_bundle.py` | Merge one or more L1 run directories into manuscript-ready aggregate comparison artifacts. |


## External baseline completeness / runnability scripts

| Script | Role |
|---|---|
| `verify_external_baseline_runnability.py` | Smoke-verifies that s1/TALE/L1 MODE A runners execute and that MODE B adapters correctly report blocked/import status boundaries, and runs BEST-Route / when_solve_when_verify / cascade_routing / MoB / ReST-MCTS / OpenR adjacent import fixture checks. Writes artifacts under `outputs/external_baseline_runnability/<run_id>/`. |
| `generate_external_baseline_completeness_report.py` | Generates repository-facing external-baseline completeness report and machine-readable summary artifacts (`docs/external_baseline_completeness_report.md`, `outputs/external_baseline_completeness_summary.{json,csv}`). |
| `verify_best_route_import.py` | Strict validator for BEST-Route adjacent import packages (`metadata.json` + `results.csv`) with workflow-stage, bo-arm schema, and adjacent-only comparability checks. |
| `generate_best_route_status_report.py` | Generates conservative BEST-Route status artifacts under `outputs/external_baseline_completeness/` and documents safe vs unsafe claims. |
| `verify_when_solve_when_verify_import.py` | Strict validator for When-To-Solve-When-To-Verify adjacent import packages (SC-vs-GenRM strategy coverage, fixed-budget fields, and adjacent-only comparability checks). |
| `generate_when_solve_when_verify_status_report.py` | Generates conservative when_solve_when_verify status artifacts under `outputs/external_baseline_completeness/`. |
| `verify_cascade_routing_import.py` | Strict validator for Cascade Routing adjacent import packages (upstream workflow-stage declarations, routing/cascading/cascade-routing strategy coverage, and adjacent-only comparability checks). |
| `generate_cascade_routing_status_report.py` | Generates conservative cascade_routing status artifacts under `outputs/external_baseline_completeness/`. |
| `verify_mob_import.py` | Strict validator for MoB adjacent import packages (workflow-stage declarations, benchmark/model/num-samples identity checks, BoN+MoB algorithm coverage, and adjacent-only comparability checks). |
| `generate_mob_status_report.py` | Generates conservative mob_majority_of_bests status artifacts under `outputs/external_baseline_completeness/`. |
| `verify_rest_mcts_import.py` | Strict validator for ReST-MCTS adjacent import packages (workflow-stage declarations, dataset/model/search-setting checks, MCTS-search coverage, and adjacent-only comparability checks). |
| `generate_rest_mcts_status_report.py` | Generates conservative rest_mcts status artifacts under `outputs/external_baseline_completeness/`. |
| `verify_openr_import.py` | Strict validator for OpenR adjacent import packages (workflow-stage declarations, method-coverage checks, metric sanity checks, and adjacent-only comparability checks). |
| `generate_openr_status_report.py` | Generates conservative openr status artifacts under `outputs/external_baseline_completeness/`. |
| `verify_compute_optimal_tts_provenance.py` | Audits paper↔repo provenance signals for compute_optimal_tts (target OpenReview paper vs linked repo identity) and emits machine-readable provenance checks. |
| `generate_compute_optimal_tts_blocker_report.py` | Generates conservative blocker/status artifacts for compute_optimal_tts under `outputs/external_baseline_completeness/`. |
