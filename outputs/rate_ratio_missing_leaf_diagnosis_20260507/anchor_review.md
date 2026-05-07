# Anchor Review (rate_ratio + gold_absent)

## openai_gsm8k_812
- outcome: both_wrong
- quantity_bucket: qnum_6p
- candidate_diversity: 2
- root_cause_tags: multi_step_quantity_tracking
- trace_data: pal=1 external=1

## openai_gsm8k_953
- outcome: both_wrong
- quantity_bucket: qnum_6p
- candidate_diversity: 2
- root_cause_tags: unit_rate_missing|percent_or_fraction_conversion
- trace_data: pal=1 external=1

## openai_gsm8k_814
- outcome: external_only
- quantity_bucket: qnum_4_5
- candidate_diversity: 2
- root_cause_tags: unit_rate_missing|denominator_or_base_quantity_missing
- trace_data: pal=1 external=1

## openai_gsm8k_979
- outcome: both_wrong
- quantity_bucket: qnum_4_5
- candidate_diversity: 1
- root_cause_tags: unit_rate_missing|candidate_generation_empty_or_low_diversity
- trace_data: pal=1 external=1

## openai_gsm8k_1069
- outcome: both_wrong
- quantity_bucket: qnum_6p
- candidate_diversity: 2
- root_cause_tags: unit_rate_missing|percent_or_fraction_conversion
- trace_data: pal=1 external=1

