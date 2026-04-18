# FAILURE CASEBOOK: Current Leading Multistep Method (2026-04-17 Artifacts)
## Scope and canonical framing
- This is a bounded diagnostic pass for fixed-budget branch allocation/frontier allocation: which active branch should receive the next unit of compute.
- No method redesign is proposed here; this report only extracts and diagnoses severe current failures.

## How the leading method was chosen
- Source validation artifact: `outputs/branch_label_bruteforce_learning/multistep_branch_utility_target_eval_20260417/aggregate_comparison_summary.json`.
- Selection rule: choose the multistep mode with highest `accepted_accuracy_mean` among multistep settings.
- Result: `multistep_branch_utility_target_k3` (accepted_accuracy_mean=0.706349) over `k1` (0.595238).
- Caveat from the same run: support is small; conclusions are promising but not yet trustworthy.

## Selection rule for the 4 worst cases
- Build per-seed test-state predictions for the leading mode by fitting the same linear pointwise model class used in the multistep evaluation pipeline (`Ridge` over v3 features, seed-matched splits).
- Define oracle-best branch per state as the branch with max `estimated_value_if_allocate_next` under the same test-state candidate table.
- Rank states by: (1) failures first (`method_choice != oracle_best`), (2) largest oracle regret gap `oracle_best_one_step - chosen_one_step`, (3) smallest predicted top-2 margin.
- If fewer than four strict failures exist, backfill with boundary-control states to keep a fixed-size casebook while preserving explicit labels. In this run, only 3 strict failures were available.

## Detailed cases
### Case 1: `seed11::exopenai_gsm8k_0_ep1_d3` (failure)
- **State identity:** state_id=`exopenai_gsm8k_0_ep1_d3`, example_id=`openai_gsm8k_0`, dataset=`openai/gsm8k`, seed=11, remaining_budget=5.
- **Question/problem text availability:** not present in current artifacts; diagnosis is state/branch-ID level only.
- **Method selection (k3):** `b0` with method score 0.751481.
- **Oracle-best branch:** `b2` with oracle one-step value 0.587786.
- **Chosen-branch realized oracle value:** 0.406921.
- **Oracle regret gap from method choice:** 0.180865.
- **k1 vs k3 disagreement:** False (k1 chose `b0`).
- **Near-tie / adjacency flags:** near_tie=False, adjacent_rank=True, strict_slice=False.
- **Margin signals:** predicted top-2 margin=0.058120; oracle top-2 margin=0.180865.
- **Candidate branches and key signals:**
  - `b0`: k3_score=0.751481, k1_score=0.616095, oracle_one_step=0.406921, multistep_target=0.478132, delta_vs_one_step=0.071211, std=0.034317, branch_vs_outside_gap=-0.180865, self_followup_ratio=0.500000.
  - `b2`: k3_score=0.693361, k1_score=0.552421, oracle_one_step=0.587786, multistep_target=0.793510, delta_vs_one_step=0.205725, std=0.134487, branch_vs_outside_gap=0.180865, self_followup_ratio=1.000000.
- **Short diagnosis:** failure appears to be a value-estimation miss where the fitted k3 scorer over-prioritizes a non-oracle branch despite measurable oracle gap.
### Case 2: `seed11::exopenai_gsm8k_3_ep7_d3` (failure)
- **State identity:** state_id=`exopenai_gsm8k_3_ep7_d3`, example_id=`openai_gsm8k_3`, dataset=`openai/gsm8k`, seed=11, remaining_budget=5.
- **Question/problem text availability:** not present in current artifacts; diagnosis is state/branch-ID level only.
- **Method selection (k3):** `b3` with method score 0.938568.
- **Oracle-best branch:** `b2` with oracle one-step value 0.712575.
- **Chosen-branch realized oracle value:** 0.599029.
- **Oracle regret gap from method choice:** 0.113547.
- **k1 vs k3 disagreement:** False (k1 chose `b3`).
- **Near-tie / adjacency flags:** near_tie=True, adjacent_rank=True, strict_slice=True.
- **Margin signals:** predicted top-2 margin=0.022242; oracle top-2 margin=0.105568.
- **Candidate branches and key signals:**
  - `b0`: k3_score=0.916326, k1_score=0.822464, oracle_one_step=0.607007, multistep_target=0.819459, delta_vs_one_step=0.212452, std=0.093126, branch_vs_outside_gap=-0.105568, self_followup_ratio=1.000000.
  - `b2`: k3_score=0.894637, k1_score=0.783543, oracle_one_step=0.712575, multistep_target=0.712575, delta_vs_one_step=0.000000, std=0.107146, branch_vs_outside_gap=0.105568, self_followup_ratio=0.000000.
  - `b3`: k3_score=0.938568, k1_score=0.843721, oracle_one_step=0.599029, multistep_target=0.808689, delta_vs_one_step=0.209660, std=0.090123, branch_vs_outside_gap=-0.113547, self_followup_ratio=1.000000.
- **Short diagnosis:** failure appears to be a value-estimation miss where the fitted k3 scorer over-prioritizes a non-oracle branch despite measurable oracle gap.
### Case 3: `seed11::exopenai_gsm8k_7_ep14_d5` (failure)
- **State identity:** state_id=`exopenai_gsm8k_7_ep14_d5`, example_id=`openai_gsm8k_7`, dataset=`openai/gsm8k`, seed=11, remaining_budget=3.
- **Question/problem text availability:** not present in current artifacts; diagnosis is state/branch-ID level only.
- **Method selection (k3):** `b0` with method score 0.903797.
- **Oracle-best branch:** `b2` with oracle one-step value 0.747908.
- **Chosen-branch realized oracle value:** 0.723212.
- **Oracle regret gap from method choice:** 0.024696.
- **k1 vs k3 disagreement:** False (k1 chose `b0`).
- **Near-tie / adjacency flags:** near_tie=True, adjacent_rank=True, strict_slice=True.
- **Margin signals:** predicted top-2 margin=0.155246; oracle top-2 margin=0.024696.
- **Candidate branches and key signals:**
  - `b0`: k3_score=0.903797, k1_score=0.783111, oracle_one_step=0.723212, multistep_target=0.723212, delta_vs_one_step=0.000000, std=0.114442, branch_vs_outside_gap=-0.024696, self_followup_ratio=0.000000.
  - `b1`: k3_score=0.641817, k1_score=0.678105, oracle_one_step=0.537642, multistep_target=0.537642, delta_vs_one_step=0.000000, std=0.080262, branch_vs_outside_gap=-0.210266, self_followup_ratio=0.000000.
  - `b2`: k3_score=0.748550, k1_score=0.724927, oracle_one_step=0.747908, multistep_target=0.747908, delta_vs_one_step=0.000000, std=0.091760, branch_vs_outside_gap=0.024696, self_followup_ratio=0.000000.
- **Short diagnosis:** failure appears to be a value-estimation miss where the fitted k3 scorer over-prioritizes a non-oracle branch despite measurable oracle gap.
### Case 4: `seed47::exopenai_gsm8k_1_ep2_d4` (boundary_control)
- **State identity:** state_id=`exopenai_gsm8k_1_ep2_d4`, example_id=`openai_gsm8k_1`, dataset=`openai/gsm8k`, seed=47, remaining_budget=4.
- **Question/problem text availability:** not present in current artifacts; diagnosis is state/branch-ID level only.
- **Method selection (k3):** `b1` with method score 1.153466.
- **Oracle-best branch:** `b1` with oracle one-step value 1.199804.
- **Chosen-branch realized oracle value:** 1.199804.
- **Oracle regret gap from method choice:** 0.000000.
- **k1 vs k3 disagreement:** False (k1 chose `b1`).
- **Near-tie / adjacency flags:** near_tie=True, adjacent_rank=True, strict_slice=True.
- **Margin signals:** predicted top-2 margin=0.011168; oracle top-2 margin=0.096352.
- **Candidate branches and key signals:**
  - `b1`: k3_score=1.153466, k1_score=1.025657, oracle_one_step=1.199804, multistep_target=1.199804, delta_vs_one_step=0.000000, std=0.103764, branch_vs_outside_gap=0.096352, self_followup_ratio=0.000000.
  - `b2`: k3_score=1.142298, k1_score=1.001508, oracle_one_step=1.103452, multistep_target=1.103452, delta_vs_one_step=0.000000, std=0.143071, branch_vs_outside_gap=-0.096352, self_followup_ratio=0.000000.
  - `b3`: k3_score=1.111283, k1_score=1.023808, oracle_one_step=1.078932, multistep_target=1.078932, delta_vs_one_step=0.000000, std=0.193205, branch_vs_outside_gap=-0.120873, self_followup_ratio=0.000000.
- **Short diagnosis:** boundary-control (not a strict error); kept because strict failures were <4 and this state has very small predicted margin (fragile decision).
## Cross-case pattern summary
- Three strict failures were concentrated in seed 11; this is consistent with small-support instability rather than broad robustness.
- Two of three strict failures are near-tie states, supporting the view that near-tie ambiguity remains a central failure mode.
- One strict failure (`seed11::exopenai_gsm8k_7_ep14_d5`) has very small oracle gap but large model margin, indicating overconfident ranking on effectively ambiguous states.
- k1 and k3 agreed on all selected cases; failures here are not driven by k-horizon disagreement at decision time, but by shared scoring error on these test states.
- Plausible next diagnostic idea (not a redesign): add a targeted audit table for "high predicted margin + low oracle margin" states to isolate overconfidence pockets.

## Short diagnostic takeaway
- The current leading multistep mode (`k3`) remains the best aggregate option in the latest multistep pass, but this bounded extraction finds a small number of concentrated, high-regret misses plus one fragile boundary case under very small support. Treat current gains as provisional.

## Commands, assumptions, caveats
- Commands run are recorded in `outputs/branch_label_bruteforce_learning/current_leading_failure_case_extraction_20260418/commands_assumptions_caveats.md`.
- Full machine-readable diagnostics (manifest, ranking table, selected IDs, structured cases) are under `outputs/branch_label_bruteforce_learning/current_leading_failure_case_extraction_20260418/`.
