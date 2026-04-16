# Scripts index

All scripts write run artifacts under `outputs/` unless overridden.

This file is the script-level entry point for the repository. It is organized around **what to run first**, not just a flat inventory.

## Read this before running anything

The canonical project is:
- fixed-budget adaptive test-time compute allocation,
- branch-priority / next-step allocation over active branches,
- matched evaluation on canonical corpora.

The shortest documentation path is:
1. `docs/PROJECT_MASTER_PLAN.md`
2. `docs/CURRENT_PROJECT_STATUS.md`
3. `docs/CURRENT_BOTTLENECKS.md`
4. `docs/CURRENT_SAFE_CLAIMS.md`
5. `docs/REPO_MAP.md`

## Interpretation labels

- **Canonical**: default current-paper path for the repo.
- **Supporting**: scripts that feed or audit the canonical path.
- **Exploratory**: useful active branches and diagnostics, but not default winners.
- **Integration/prep**: dataset and baseline readiness tooling.
- **Historical**: older-track support retained for provenance.

## Start here: current canonical path

If you are new to the codebase, these are the main scripts to understand first.

### 1) Build internal branch-allocation supervision

| Script | Role |
|---|---|
| `run_bruteforce_branch_label_generator.py` | Generate candidate / pairwise / outside-option branch-allocation labels with resumable artifacts. |
| `merge_bruteforce_branch_label_runs.py` | Merge multiple label runs into one provenance-preserving corpus. |
| `build_bruteforce_target_regimes.py` | Build pair-construction / supervision regimes such as all-pairs, adjacent-rank, and uncertainty-filtered views. |

### 2) Build canonical processed corpora

| Script | Role |
|---|---|
| `build_canonical_branch_learning_corpus.py` | Build canonical processed branch-learning corpora with candidate, pairwise, and outside-option rows plus manifest/checksum/slice summaries. |
| `build_external_prm_mathshepherd_apps_corpus.py` | Build conservative external candidate-style corpora for PRM800K / Math-Shepherd / APPS with explicit provenance and caveats. |

### 3) Run canonical matched learning passes

| Script | Role |
|---|---|
| `run_canonical_branch_learning_pass.py` | Run matched canonical learning/evaluation from canonical corpora, including internal anchor and external-supervision variants. |

## Current canonical supporting workflows

These are important once you already understand the main path above.

### Hard-slice / exact-supervision support

| Script | Role |
|---|---|
| `mine_bruteforce_hard_regions.py` | Mine high-priority hard branch-comparison regions. |
| `expand_bruteforce_exact_hard_regions.py` | Run bounded exact relabeling for mined hard pairs. |
| `build_exact_augmented_target_regimes.py` | Materialize exact-augmented regimes combining approximate easy regions with selectively promoted exact hard regions. |
| `run_hard_region_exact_supervision_experiment.py` | Run matched learning on exact-augmented regimes. |
| `audit_bruteforce_exact_vs_approx_pairs.py` | Audit disagreement between exact and approximate labels by slice. |

### Feature and robustness support

| Script | Role |
|---|---|
| `audit_bruteforce_feature_representation.py` | Audit hard-case feature coverage. |
| `run_hard_case_feature_representation_experiment.py` | Compare feature-set variants under fixed supervision. |
| `run_bruteforce_allocator_scaling_experiment.py` | Run multi-seed scaling experiments on merged corpora. |
| `run_target_fidelity_regime_experiment.py` | Compare learning outcomes across target-construction regimes. |

### Ambiguity / near-tie support

| Script | Role |
|---|---|
| `run_ternary_or_abstain_branch_comparison_experiment.py` | Compare forced-binary, tie-aware, and abstaining branch-comparison formulations. |
| `run_ambiguity_calibration_and_fallback_experiment.py` | Compare calibration and fallback policies for ambiguity handling. |
| `run_near_tie_policy_experiment.py` | Run dedicated near-tie routing policy experiments. |
| `run_near_tie_pointwise_expert_experiment.py` | Run near-tie pointwise-expert experiments. |

## External supervision and dataset readiness

| Script | Role |
|---|---|
| `verify_hf_dataset_access.py` | Verify evaluation-dataset access and summarize status. |
| `dataset_smoke_sample.py` | Run lightweight smoke sampling for configured datasets. |
| `generate_dataset_integration_report.py` | Generate the main evaluation-dataset integration report. |
| `verify_external_reasoning_datasets.py` | Check external process-supervision dataset access/schema. |
| `generate_external_reasoning_dataset_integration_report.py` | Generate external-supervision dataset integration report. |
| `prepare_external_reasoning_datasets.py` | Produce readiness ranking and normalized previews for external supervision datasets. |

## External baseline readiness / adjacent-import tooling

| Script | Role |
|---|---|
| `generate_external_baseline_completeness_report.py` | Generate repository-facing external-baseline completeness summary artifacts. |
| `verify_external_baseline_runnability.py` | Smoke-verify runnable-adjacent baseline workflows and import boundaries. |
| `verify_best_route_import.py` | Validate BEST-Route adjacent import packages. |
| `verify_when_solve_when_verify_import.py` | Validate when_solve_when_verify adjacent import packages. |
| `verify_cascade_routing_import.py` | Validate cascade_routing adjacent import packages. |
| `verify_mob_import.py` | Validate MoB adjacent import packages. |
| `verify_rest_mcts_import.py` | Validate ReST-MCTS adjacent import packages. |
| `verify_openr_import.py` | Validate OpenR adjacent import packages. |
| `verify_compute_optimal_tts_provenance.py` | Audit compute_optimal_tts provenance / blocker state. |

## Older but still useful controller/frontier scripts

These remain useful as reference implementations and controller-oriented experiments, but they are not the shortest path into the current canonical corpus-centered workflow.

| Script | Role |
|---|---|
| `run_cross_strategy_frontier_allocation.py` | Main frontier-allocation scaffold (legacy filename). |
| `run_multi_action_allocation_pass.sh` | Multi-action allocation run wrapper. |
| `evaluate_branch_scorer_controller.py` | Controller-level comparison for learned and heuristic policies. |
| `evaluate_branch_scorer_robustness.py` | Multi-seed / budget / initialization robustness sweep. |
| `run_new_paper_frontier_matrix.py` | Frontier matrix / anti-collapse summary tables. |
| `run_comparative_frontier_audit.py` | Matched-budget comparative audit. |
| `run_new_paper_stop_vs_act_controller.py` | Stop-vs-act lightweight pipeline. |
| `run_new_paper_stop_vs_act_target_stabilization_pass.py` | Default-target stabilization comparison. |
| `run_new_paper_stop_vs_act_matched_comparator_pass.py` | Matched ACT-vs-STOP comparator pass. |
| `run_new_paper_stop_vs_act_policy_coupled_stop_pass.py` | Policy-coupled STOP-baseline pass. |

## Exploratory branch-scorer workflows

| Script | Role |
|---|---|
| `run_new_paper_bt_pairwise_branch_scorer.py` | End-to-end pairwise BT pipeline. |
| `run_new_paper_bt_reliability_weighted_branch_scorer.py` | Reliability-aware BT variants. |
| `run_new_paper_external_warmstart_branch_scorer.py` | External warm-start variants. |
| `run_new_paper_tie_aware_bt.py` | Tie-aware BT variant. |
| `run_new_paper_tie_aware_bt_stability.py` | Tie-aware stability and calibration checks. |
| `run_new_paper_tie_aware_hybrid_gating.py` | Hybrid gating variant. |
| `run_new_paper_ambiguous_branch_dataset.py` | Ambiguous-pair dataset construction. |
| `run_new_paper_ambiguous_pair_targeted_experiment.py` | Targeted ambiguous-pair experiment. |
| `run_new_paper_pairwise_diagnostic_audit.py` | Pairwise confidence/label diagnostics. |
| `run_new_paper_raokupper_resolution_audit.py` | Rao-Kupper contradiction-resolution audit. |
| `run_new_paper_raokupper_confirmation.py` | Independent confirmation for Rao-Kupper audit. |

## Historical / provenance scripts

| Script | Role |
|---|---|
| `run_heavy_real_routing_eval.sh` | Older binary revise-routing track support. |
| `run_final_manuscript_eval.sh` | Older manuscript evaluation wrapper. |

## Practical notes

- `run_cross_strategy_frontier_allocation.py` keeps a legacy filename for compatibility; docs refer to this line as cross-controller frontier allocation.
- The current repo should be read first through the **canonical corpus + matched learning** path, not through the older stop-vs-act-only scripts.
- External process supervision is currently candidate-first and conservative; broad vs aligned PRM usage is still not cleanly separated in the main evidence.
- Math-Shepherd should still wait until evidence quality is stronger on the key hard slices.

## Minimal example paths

### Canonical internal path

```bash
python scripts/run_bruteforce_branch_label_generator.py ...
python scripts/merge_bruteforce_branch_label_runs.py ...
python scripts/build_bruteforce_target_regimes.py ...
python scripts/build_canonical_branch_learning_corpus.py ...
python scripts/run_canonical_branch_learning_pass.py ...
```

### Canonical external-supervision path

```bash
python scripts/build_external_prm_mathshepherd_apps_corpus.py ...
python scripts/run_canonical_branch_learning_pass.py --external-supervision ...
```

## When to use the longer script families

- Use the **hard-slice / exact-supervision** scripts when the question is about supervision quality or difficult slices.
- Use the **ambiguity / near-tie** scripts when the question is about fragile comparator regions and fallback behavior.
- Use the **external baseline** scripts when the question is about reviewer-defensible adjacent comparisons.
- Use the **older frontier/controller** scripts when you need the legacy controller-oriented framing or compatibility with older paper pathways.
