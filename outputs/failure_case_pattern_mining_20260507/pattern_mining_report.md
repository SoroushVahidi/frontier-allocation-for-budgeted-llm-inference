# Failure Case Pattern Mining Report

- Still-failing cases mined: 41
- Top failure archetypes: [{'operation_hint': 'rate_ratio', 'quantity_bucket': 'qnum_6p', 'failure_stage': 'gold_absent_everywhere_detectable', 'count': 4}, {'operation_hint': 'temporal_change', 'quantity_bucket': 'qnum_6p', 'failure_stage': 'gold_absent_everywhere_detectable', 'count': 3}, {'operation_hint': 'product', 'quantity_bucket': 'qnum_2_3', 'failure_stage': 'gold_absent_everywhere_detectable', 'count': 3}, {'operation_hint': 'temporal_change', 'quantity_bucket': 'qnum_2_3', 'failure_stage': 'gold_absent_everywhere_detectable', 'count': 3}, {'operation_hint': 'rate_ratio', 'quantity_bucket': 'qnum_4_5', 'failure_stage': 'gold_absent_everywhere_detectable', 'count': 3}]
- Pattern shape: multiple meaningful patterns
- PAL trace availability: 41/41
- External trace availability: 41/41
- Current 48-case corpus is enough for offline pattern design, but still small for broad claims.
- More API is not needed now; use offline findings to define a single targeted hypothesis first.
- Single next hypothesis: For high-frequency rate_ratio/temporal_change cases where stage is gold_absent_everywhere_detectable, improve upstream candidate-generation to produce gold-equivalent numeric leaves before selector/overlay.

## Top 15 Anchor Cases
- openai_gsm8k_812 | outcome=both_wrong | stage=gold_absent_everywhere_detectable | ops=rate_ratio|temporal_change | qbucket=qnum_6p | both_traces=1
- openai_gsm8k_953 | outcome=both_wrong | stage=gold_absent_everywhere_detectable | ops=rate_ratio | qbucket=qnum_6p | both_traces=1
- openai_gsm8k_814 | outcome=external_only | stage=gold_absent_everywhere_detectable | ops=rate_ratio|temporal_change | qbucket=qnum_4_5 | both_traces=1
- openai_gsm8k_979 | outcome=both_wrong | stage=gold_absent_everywhere_detectable | ops=rate_ratio | qbucket=qnum_4_5 | both_traces=1
- openai_gsm8k_1069 | outcome=both_wrong | stage=gold_absent_everywhere_detectable | ops=rate_ratio | qbucket=qnum_6p | both_traces=1
- openai_gsm8k_878 | outcome=both_wrong | stage=gold_absent_everywhere_detectable | ops=rate_ratio | qbucket=qnum_6p | both_traces=1
- openai_gsm8k_1003 | outcome=external_only | stage=gold_absent_everywhere_detectable | ops=product|temporal_change | qbucket=qnum_0_1 | both_traces=1
- openai_gsm8k_1006 | outcome=external_only | stage=gold_absent_everywhere_detectable | ops=rate_ratio|total_sum | qbucket=qnum_4_5 | both_traces=1
- openai_gsm8k_1021 | outcome=both_wrong | stage=gold_absent_everywhere_detectable | ops=difference|temporal_change | qbucket=qnum_4_5 | both_traces=1
- openai_gsm8k_1029 | outcome=external_only | stage=gold_absent_everywhere_detectable | ops=temporal_change | qbucket=qnum_2_3 | both_traces=1
- openai_gsm8k_1035 | outcome=both_wrong | stage=gold_absent_everywhere_detectable | ops=percent|difference|temporal_change | qbucket=qnum_4_5 | both_traces=1
- openai_gsm8k_773 | outcome=external_only | stage=gold_absent_everywhere_detectable | ops=temporal_change | qbucket=qnum_6p | both_traces=1
- openai_gsm8k_781 | outcome=both_wrong | stage=gold_absent_everywhere_detectable | ops=product | qbucket=qnum_2_3 | both_traces=1
- openai_gsm8k_794 | outcome=both_wrong | stage=gold_absent_everywhere_detectable | ops=temporal_change | qbucket=qnum_2_3 | both_traces=1
- openai_gsm8k_829 | outcome=external_only | stage=gold_absent_everywhere_detectable | ops=none | qbucket=qnum_2_3 | both_traces=1
