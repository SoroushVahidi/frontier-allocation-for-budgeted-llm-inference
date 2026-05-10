# Proposed discovery retry policy v1 (gold-free scaffolds)

Grounded in PAL vs external losses where the correct numeric never appeared in the explored tree
(`gold_absent_discovery`). These are **prompt / decomposition** retries, not consensus.

## A. `rate_table` scaffold

- **Trigger signals (no gold):** phrases like *per minute*, *% of total*, *twice as fast*, parallel rates,
  or strong disagreement between branches on a ratio line while magnitudes differ by orders (see e.g. clog-dance rate case).
- **Procedure:** list entities, units, baseline interval, then one equation per row; sum only after
  converting to a common time/quantity base.
- **Budget cost:** ~1 extra direct or PAL-backed synthesis call if PAL used only for final arithmetic.
- **Target families:** `rate_ratio`, parts of `money_budget` with percentages on total.
- **Risks:** over-fitting to bogus rates parsed from text; needs abstain if units stay ambiguous.
- **Example anchors:** `openai_gsm8k_1125`, `openai_gsm8k_1003`, `openai_gsm8k_1099`.

## B. `before_after_state` scaffold

- **Trigger signals:** multi-day/week story, sequential *spills/consumption*, *first half/second half* of month.
- **Procedure:** single state vector per day/phase; apply deltas in chronological order; answer is last phase
  or comparison across phases.
- **Budget cost:** ~1 call; can share with structural commit path (no interaction yet).
- **Target families:** `temporal_change`.
- **Risks:** calendar edge cases (15 vs 14 days); keep explicit day index.
- **Example anchors:** `openai_gsm8k_1166`, `openai_gsm8k_1198`, `openai_gsm8k_773`.

## C. `target_difference` scaffold

- **Trigger signals:** *how many more*, *half the total*, *difference between*, multi-actor eggs/pencils.
- **Procedure:** name A/B/total; restate **exact** target (“half of combined spots” vs “spots on one species”).
- **Budget cost:** ~1 short rewrite + one solve.
- **Target families:** `difference_comparison`, tricky wordings in `multi_step_total`.
- **Risks:** doubling/halving wrong layer; abstain if question has nested quantifiers without clear referent.
- **Example anchors:** `openai_gsm8k_1099`, `openai_gsm8k_1187`, `openai_gsm8k_1248`.

## D. `quantity_ledger` scaffold

- **Trigger signals:** many numeric literals, `% off then multi-buy`, jelly-bean mix, rice consumption.
- **Procedure:** table: quantity | meaning | consumed? | equation slot.
- **Budget cost:** 1–2 calls if PAL used for execution after ledger.
- **Target families:** `money_budget`, `unit_conversion`, `multi_step_total`, `average`.
- **Risks:** ledger explosion; cap rows or merge duplicates.
- **Example anchors:** `openai_gsm8k_1006`, `openai_gsm8k_1019`, `openai_gsm8k_1027`.

## E. `PAL_program_first` scaffold

- **Trigger signals:** ledger already stable but repeated arithmetic errors; PAL stdout historically unreliable.
- **Procedure:** emit Python from ledger, print single numeric, `oxed{}`.
- **Budget cost:** +1 PAL slot (already modeled in budget-6 PAL runs).
- **Target families:** `money_budget`, dense `rate_ratio`, `counting_combinatorics`.
- **Risks:** code drift from story; validator should check units/dimensions symbolically when possible.
- **Example anchors:** `openai_gsm8k_750`, `openai_gsm8k_769`, `openai_gsm8k_752`.

## F. `least_to_most` scaffold

- **Trigger signals:** nested textual conditions (lines of song vs scenes), hierarchical geometric levels.
- **Procedure:** ordered subquestions with intermediate answers; final restatement of target quantity.
- **Budget cost:** 1 chain-of-subquestions call (may substitute for an expand slot, not add infinitely).
- **Target families:** `geometry`, deep `multi_step_total`.
- **Risks:** verbosity; pair with short final numeric-only pass.
- **Example anchors:** `openai_gsm8k_1230`, `openai_gsm8k_1281`, `openai_gsm8k_1215`.
