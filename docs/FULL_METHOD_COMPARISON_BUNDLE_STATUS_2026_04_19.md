# Full method comparison bundle status (2026-04-19)

## Scope and intent

This pass creates a bounded but audit-friendly full comparison bundle for the current repository framing (fixed-budget next-step branch allocation / adaptive test-time compute allocation), with explicit honesty boundaries for direct vs adapter-based vs import-validated vs blocked baselines.

Canonical output bundle:

- `outputs/full_method_comparison_bundle/20260419T214335Z/`

## Methods numerically compared in this run

### Our current main method

- `adaptive_min_expand_1`

### Internal baselines and earlier repo lines

- `adaptive_min_expand_0`
- `adaptive_min_expand_2`
- `reasoning_greedy`
- `reasoning_beam2`
- `self_consistency_3`
- `verifier_guided_search`
- `program_of_thought`

### External baselines (MODE A adapters, runnable here)

- `external_s1_budget_forcing`
- `external_tale_prompt_budgeting`
- `external_l1_exact`
- `external_l1_max`

## Methods not fully compared and why

These methods are captured in status/fairness tables but not numerically ranked in this bounded run because they require external import packages or remain blocked:

- `best_route` (import-validated adjacent path only)
- `when_solve_when_verify` (import-validated adjacent path only)
- `cascade_routing` (import-validated adjacent path only)
- `mob_majority_of_bests` (import-validated adjacent path only)
- `rest_mcts` (import-validated adjacent path only)
- `openr` (import-validated adjacent path only)
- `compute_optimal_tts` (blocked)

## Run setup

- datasets: `openai/gsm8k`, `HuggingFaceH4/MATH-500`, `HuggingFaceH4/aime_2024`
- subset size per dataset/seed: `20`
- seeds: `11, 23`
- budgets: `4, 6, 8`
- mode: bounded simulator-mode matched comparison

## Primary ranking rule

- Primary: rank by `mean_accuracy` over matched dataset × seed × budget rows.
- Tie-break: lower `mean_avg_actions`, then higher `mean_coverage`, then lexical method name.

## Compact aggregate ranking table

| Rank | Method | Family | Mean accuracy | Mean avg actions | Status |
|---:|---|---|---:|---:|---|
| 1 | external_tale_prompt_budgeting | external_baseline | 0.5306 | 1.9167 | runnable_direct |
| 2 | reasoning_beam2 | internal_baseline | 0.5028 | 4.0556 | runnable_direct |
| 3 | reasoning_greedy | internal_baseline | 0.4917 | 2.1306 | runnable_direct |
| 4 | self_consistency_3 | internal_baseline | 0.4806 | 5.9278 | runnable_direct |
| 5 | adaptive_min_expand_2 | earlier_repo_line | 0.4694 | 3.6306 | runnable_direct |
| 6 | external_s1_budget_forcing | external_baseline | 0.4556 | 3.2972 | runnable_direct |
| 7 | external_l1_max | external_baseline | 0.4500 | 1.9278 | runnable_direct |
| 8 | external_l1_exact | external_baseline | 0.4222 | 2.2500 | runnable_direct |
| 9 | adaptive_min_expand_1 | our_current_main | 0.3556 | 3.3861 | runnable_direct |
| 10 | verifier_guided_search | internal_baseline | 0.2694 | 5.3333 | runnable_direct |
| 11 | adaptive_min_expand_0 | earlier_repo_line | 0.2250 | 3.1833 | runnable_direct |
| 12 | program_of_thought | internal_baseline | 0.0167 | 2.0000 | runnable_direct |

## Strongest losses/wins for our method (`adaptive_min_expand_1`)

From `win_loss_registry.csv`:

- Largest net losses for our method:
  - vs `external_tale_prompt_budgeting`: net +63 for competitor
  - vs `reasoning_beam2`: net +53 for competitor
  - vs `reasoning_greedy`: net +49 for competitor
- Largest net wins for our method:
  - vs `program_of_thought`: net -122 (ours better)
  - vs `adaptive_min_expand_0`: net -47 (ours better)
  - vs `verifier_guided_search`: net -31 (ours better)

## Artifact inventory (machine-readable)

- `aggregate_comparison_summary.json`
- `ranking_summary.json`
- `aggregate_ranking.csv`
- `per_method_metrics.csv`
- `per_dataset_ranking.csv`
- `per_budget_ranking.csv`
- `method_status_fairness_caveats.csv`
- `win_loss_registry.csv`
- `defeat_case_registry.csv`
- `per_seed_method_metrics.csv`
- `per_example_outcomes.csv`
- `commands_assumptions_caveats.json`
- `manifest.json`

## Reviewer-defensibility gap (remaining)

Before claiming paper-ready full external-baseline completeness, still needed:

1. Import/package-backed adjacent runs for BEST-Route / when_solve_when_verify / cascade / MoB / ReST-MCTS / OpenR using explicit fair protocols.
2. Expanded scale beyond bounded subsets/seeds for stability and confidence intervals.
3. Real-model confirmation on matched slices where simulator ranking and policy behavior differ.
