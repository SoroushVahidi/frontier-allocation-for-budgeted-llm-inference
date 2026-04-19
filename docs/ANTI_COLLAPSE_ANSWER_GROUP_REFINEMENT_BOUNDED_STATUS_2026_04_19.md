# Anti-collapse + answer-group-aware refinement bounded status (2026-04-19)

## Goal
Address the currently dominant structural failure mode in the broad diversity/aggregation family: early branch monopolization (repeated expansion of one branch), shallow alternatives, and weak development of answer-distinct competitors under fixed budget.

## Implemented refinement (same broad family)
New variant: `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_v1`.

### A) Early anti-collapse repeated-expansion control
- Added an early-window repeated-same-branch structural penalty (`repeated_same_branch_penalty`).
- Added an early incumbent repeat cap (`repeated_same_branch_cap`) with a monopolization margin requirement (`monopolization_margin_requirement`) before allowing continued repeat expansion.

### B) Answer-group-aware expansion value
- Added answer-group distinctness bonus weighted by target-alignment (`answer_group_distinctness_bonus`).
- Added duplicate answer-group pressure (`duplicate_answer_group_penalty`) so value is not only local branch promise.

### C) Alternative maturity protection
- If early-preservation selects a plausible target-aligned alternative, mark it as protected and require bounded follow-up allocation:
  - `min_followup_steps_for_preserved_alternative`
  - `alternative_maturity_window`
- Added maturity observability:
  - `matured_alternative_count`
  - `shallow_preserved_alternative_count`

### D) Regime-aware diagnostics (per-example)
Added `regime_failure_category` with explicit categories:
1. `correct_answer_group_absent`
2. `correct_answer_group_present_but_underweighted`
3. `correct_group_preserved_but_insufficiently_matured`
4. `repeated_same_branch_expansion_dominated_budget`
5. `final_commit_lost_despite_viable_alternative`

## Bounded comparison setup
- Baseline broad: `broad_diversity_aggregation_strong_v1`
- Existing early-preservation reference: `broad_diversity_aggregation_strong_v1_early_answer_group_preservation_v1`
- New refinement: `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_v1`
- Datasets: `openai/gsm8k`, `HuggingFaceH4/MATH-500`, `HuggingFaceH4/aime_2024`
- Seeds: `[11, 23]`
- Budgets: `[6, 8]`
- Subset size: 20 per dataset/seed

## Key bounded metrics
- Mean accuracy:
  - baseline broad: **0.6583**
  - early-preservation: **0.6250**
  - anti-collapse refinement: **0.6958**
  - delta vs baseline: **+0.0375**
- First/second split gold-group survival:
  - baseline: **0.6250 / 0.6167**
  - early-preservation: **0.6000 / 0.6000**
  - refinement: **0.6542 / 0.6417**
- Improved / harmed / unchanged vs baseline:
  - **60 / 51 / 129**
- Failure counts (not_generated / underweighted / collapsed_early / committed_away):
  - baseline: **68 / 11 / 0 / 14**
  - early-preservation: **83 / 6 / 0 / 7**
  - refinement: **61 / 12 / 0 / 12**

## Compact structural diagnostics
### Repeated same-branch expansion
- Mean repeated-same-branch expansion rate:
  - baseline: **0.5659**
  - refinement: **0.4413** (delta **-0.1246**)
- Total repeated-same-branch expansion count:
  - baseline: **950**
  - refinement: **615**

### Shallow child spawning / alternative maturity
- `matured_alternative_count`:
  - baseline: **0**
  - early-preservation: **0**
  - refinement: **18**
- `shallow_preserved_alternative_count`:
  - baseline: **0**
  - early-preservation: **0**
  - refinement: **0**

### Regime-aware failure buckets (refinement)
- correct group absent: **61**
- correct group present but underweighted: **10**
- correct group preserved but insufficiently matured: **0**
- repeated same-branch dominated budget: **0**
- final commit lost despite viable alternative: **2**

## Conservative assessment
- This bounded run supports the structural hypothesis directionally: repeated-branch domination dropped, matured alternatives increased, split survival improved, and final accuracy improved over both comparison methods.
- Harmed cases remain non-trivial (51), so this is still an active refinement line, not a solved endpoint.
- Within the same broad family, this is currently strong enough to remain the promoted next line for bounded follow-up.

## Exact next recommendation
1. Keep this refinement as the promoted near-term line.
2. Run one bounded follow-up targeted at harmed cases where baseline was already correct, with minimal tuning of repeat penalties/cap thresholds only.
3. Keep all new structural diagnostics fixed and report improved/harmed with the same matrix before any wider claim.
