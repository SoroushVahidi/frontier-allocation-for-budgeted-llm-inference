# NATURAL-LANGUAGE FAILURE CASEBOOK (Dominant Group, 2026-04-18)
## Scope and canonical framing
- Fixed-budget branch-allocation/frontier-allocation diagnosis: which active branch should receive the next unit of compute.
- Bounded analysis only; no redesign and no drift to binary revise-routing framing.

## How the leading method was chosen
- Source: `/workspace/adaptive-reasoning-budget-allocation/outputs/branch_label_bruteforce_learning/multistep_branch_utility_target_validation_eval_20260417/aggregate_comparison_summary.json`.
- Rule: argmax accepted_accuracy_mean among multistep_k* modes in latest validation aggregate summary.
- Selected mode: `multistep_branch_utility_target_k3` (accepted_accuracy_mean=0.706349).

## Mistake taxonomy for current failures
- **delayed_payoff_overvaluation_with_outside_option_miss**: chosen branch has multistep uplift but negative outside-gap while oracle branch has positive outside-gap.
- **fragile_boundary_overconfidence**: near-tie with tiny oracle gap but large learned top-2 margin.
- **other_score_ordering_error**: residual mismatch not satisfying the stronger signatures.

### Failure counts
- delayed_payoff_overvaluation_with_outside_option_miss: 2
- fragile_boundary_overconfidence: 1

## Dominant mistake group
- Dominant group: **delayed_payoff_overvaluation_with_outside_option_miss** (2/3 failures, share=0.67).
- Why dominant: it is the largest interpretable bucket under rule-based assignment from available artifact fields.

## Selection rule for 4 examples
- Prioritize strict failures in the dominant group by largest oracle regret (`oracle_gap_if_choose_k3`).
- If strict dominant-group failures are <4, backfill with clearly-labeled controls exhibiting the strongest same-signature multistep-uplift tendency.

## Case 1: `seed11::exopenai_gsm8k_0_ep1_d3`
- state_id=`exopenai_gsm8k_0_ep1_d3`, dataset=`openai/gsm8k`, example_id=`openai_gsm8k_0`.
- Question text (preview): John plans to sell all his toys and use the money to buy video games. He has 13 lego sets and he sells them for $15 each. He ends up buying 8 video games for $20 each and has $5 le
- Method choice: `b0`; oracle-best: `b2`.
- Margins: predicted_top2=0.058120, oracle_top2=0.180865, oracle_regret_if_method=0.180865.
- Mistake type: `delayed_payoff_overvaluation_with_outside_option_miss`.
- Branch narratives:
  - b0: method-chosen; moderate multistep uplift; trails outside option; depth=0.0, verify_count=0.0, recent_delta=0.0000. (k3_score=0.751481, oracle_one_step=0.406921, multistep_target=0.478132, outside_gap=-0.180865).
  - b2: oracle-best; strong multistep uplift; beats outside option; depth=1.0, verify_count=0.0, recent_delta=-0.0478. (k3_score=0.693361, oracle_one_step=0.587786, multistep_target=0.793510, outside_gap=0.180865).
- Why model likely chose it: Chosen branch had higher learned k3 score and appeared attractive under multistep utility uplift/self-followup proxy.
- Why oracle differed: Oracle branch has higher one-step value and stronger outside-option gap, indicating better immediate compute return.
- Representative of dominant group: True

## Case 2: `seed11::exopenai_gsm8k_3_ep7_d3`
- state_id=`exopenai_gsm8k_3_ep7_d3`, dataset=`openai/gsm8k`, example_id=`openai_gsm8k_3`.
- Question text (preview): Gretchen has some coins. There are 30 more gold coins than silver coins. If she had 70 gold coins, how many coins did Gretchen have in total?
- Method choice: `b3`; oracle-best: `b2`.
- Margins: predicted_top2=0.022242, oracle_top2=0.105568, oracle_regret_if_method=0.113547.
- Mistake type: `delayed_payoff_overvaluation_with_outside_option_miss`.
- Branch narratives:
  - b3: method-chosen; strong multistep uplift; trails outside option; depth=1.0, verify_count=1.0, recent_delta=0.0106. (k3_score=0.938568, oracle_one_step=0.599029, multistep_target=0.808689, outside_gap=-0.113547).
  - b0: competing; strong multistep uplift; trails outside option; depth=1.0, verify_count=0.0, recent_delta=0.0182. (k3_score=0.916326, oracle_one_step=0.607007, multistep_target=0.819459, outside_gap=-0.105568).
  - b2: oracle-best; no multistep uplift; beats outside option; depth=0.0, verify_count=0.0, recent_delta=0.0000. (k3_score=0.894637, oracle_one_step=0.712575, multistep_target=0.712575, outside_gap=0.105568).
- Why model likely chose it: Chosen branch had higher learned k3 score and appeared attractive under multistep utility uplift/self-followup proxy.
- Why oracle differed: Oracle branch has higher one-step value and stronger outside-option gap, indicating better immediate compute return.
- Representative of dominant group: True

## Case 3: `seed47::exopenai_gsm8k_3_ep7_d4`
- state_id=`exopenai_gsm8k_3_ep7_d4`, dataset=`openai/gsm8k`, example_id=`openai_gsm8k_3`.
- Question text (preview): Gretchen has some coins. There are 30 more gold coins than silver coins. If she had 70 gold coins, how many coins did Gretchen have in total?
- Method choice: `b3`; oracle-best: `b3`.
- Margins: predicted_top2=0.151628, oracle_top2=0.185834, oracle_regret_if_method=0.000000.
- Mistake type: `correct_or_control`.
- Backfill label: Backfill control: strict dominant-group failures < 4; selected highest-uplift states to illustrate same delayed-payoff scoring tendency.
- Branch narratives:
  - b3: method-chosen, oracle-best; strong multistep uplift; beats outside option; depth=1.0, verify_count=1.0, recent_delta=0.0106. (k3_score=0.833011, oracle_one_step=0.737546, multistep_target=0.995687, outside_gap=0.185834).
  - b2: competing; no multistep uplift; trails outside option; depth=0.0, verify_count=0.0, recent_delta=0.0000. (k3_score=0.681383, oracle_one_step=0.551712, multistep_target=0.551712, outside_gap=-0.185834).
- Why model likely chose it: Chosen branch had higher learned k3 score and appeared attractive under multistep utility uplift/self-followup proxy.
- Why oracle differed: No oracle disagreement in this backfill control; included only to show the same multistep-uplift tendency under a correct decision.
- Representative of dominant group: False

## Case 4: `seed29::exopenai_gsm8k_9_ep18_d3`
- state_id=`exopenai_gsm8k_9_ep18_d3`, dataset=`openai/gsm8k`, example_id=`openai_gsm8k_9`.
- Question text (preview): Brittany and her mom go to the museum. The cost of admission is $12 for adults and $10 for children. Brittany's mom gives the cashier money for 1 child ticket and 1 adult ticket. I
- Method choice: `b0`; oracle-best: `b0`.
- Margins: predicted_top2=0.049496, oracle_top2=0.015978, oracle_regret_if_method=0.000000.
- Mistake type: `correct_or_control`.
- Backfill label: Backfill control: strict dominant-group failures < 4; selected highest-uplift states to illustrate same delayed-payoff scoring tendency.
- Branch narratives:
  - b0: method-chosen, oracle-best; strong multistep uplift; beats outside option; depth=0.0, verify_count=0.0, recent_delta=0.0000. (k3_score=1.099902, oracle_one_step=1.096666, multistep_target=1.288583, outside_gap=0.015978).
  - b3: competing; strong multistep uplift; trails outside option; depth=0.0, verify_count=0.0, recent_delta=0.0000. (k3_score=1.050406, oracle_one_step=1.080688, multistep_target=1.269809, outside_gap=-0.015978).
  - b1: competing; strong multistep uplift; trails outside option; depth=0.0, verify_count=0.0, recent_delta=0.0000. (k3_score=0.991413, oracle_one_step=0.931010, multistep_target=1.093936, outside_gap=-0.165656).
  - b2: competing; no multistep uplift; trails outside option; depth=3.0, verify_count=2.0, recent_delta=-0.0009. (k3_score=0.771847, oracle_one_step=0.931170, multistep_target=0.931170, outside_gap=-0.165497).
- Why model likely chose it: Chosen branch had higher learned k3 score and appeared attractive under multistep utility uplift/self-followup proxy.
- Why oracle differed: No oracle disagreement in this backfill control; included only to show the same multistep-uplift tendency under a correct decision.
- Representative of dominant group: False

## Cross-case summary of dominant group
- Dominant group is `delayed_payoff_overvaluation_with_outside_option_miss` and concentrates failures where multistep-uplift signals can outrank branches that are stronger on immediate oracle/outside-option value.
- Shared pattern: chosen branch often has high learned score plus positive self-followup/uplift proxies, while oracle-best branch has better one-step return for the next compute unit.
- Practical next diagnostic step: audit calibration between multistep uplift proxies and outside-option gap on near-boundary states before any method redesign.

## Commands / assumptions / caveats
- Commands and caveats are recorded in `outputs/branch_label_bruteforce_learning/natural_language_failure_casebook_dominant_group_20260418/commands_assumptions_caveats.md`.
- Natural-language branch traces are partially recoverable only through stored signals; full free-text branch reasoning is unavailable in inspected artifacts.
