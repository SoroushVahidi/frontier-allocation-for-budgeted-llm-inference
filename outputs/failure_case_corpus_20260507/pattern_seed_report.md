# Failure Case Corpus Pattern Seed Report

- Failure/loss cases collected: 48
- Top outcome buckets: {'both_wrong': 27, 'external_only': 21}
- Counts by original failure source: {'pal_wrong': 48, 'gold_absent_everywhere_detectable': 34, 'both_wrong': 27, 'atlas_anchor': 23, 'external_only_loss': 21, 'selector_sensitivity': 12, 'failed_gate_anchor': 12}
- Top operation/quantity patterns: operation={'rate_ratio': 21, 'temporal_change': 17, 'difference': 10, 'product': 8, 'total_sum': 7}, quantity={'qnum_2_3': 16, 'qnum_4_5': 14, 'qnum_6p': 12, 'qnum_0_1': 6}
- Top gold-absence stages: {'gold_absent_everywhere_detectable': 34, 'gold_in_trace_candidates': 10, 'gold_in_selector_pool': 4}
- PAL trace/tree availability (cases): yes=48 no=0
- External trace availability (cases): yes=48 no=0
- Missing external traces limit pairwise tree-diagnostics where availability=no.

## Top cases for manual inspection
- openai_gsm8k_773 | bucket=external_only | our_exact=0 | external_exact=1 | stage=gold_absent_everywhere_detectable
- openai_gsm8k_778 | bucket=both_wrong | our_exact=0 | external_exact=0 | stage=gold_absent_everywhere_detectable
- openai_gsm8k_780 | bucket=both_wrong | our_exact=0 | external_exact=0 | stage=gold_in_selector_pool
- openai_gsm8k_781 | bucket=both_wrong | our_exact=0 | external_exact=0 | stage=gold_absent_everywhere_detectable
- openai_gsm8k_787 | bucket=external_only | our_exact=0 | external_exact=1 | stage=gold_in_trace_candidates
- openai_gsm8k_794 | bucket=both_wrong | our_exact=0 | external_exact=0 | stage=gold_absent_everywhere_detectable
- openai_gsm8k_812 | bucket=both_wrong | our_exact=0 | external_exact=0 | stage=gold_absent_everywhere_detectable
- openai_gsm8k_814 | bucket=external_only | our_exact=0 | external_exact=1 | stage=gold_absent_everywhere_detectable
- openai_gsm8k_818 | bucket=external_only | our_exact=0 | external_exact=1 | stage=gold_in_trace_candidates
- openai_gsm8k_819 | bucket=both_wrong | our_exact=0 | external_exact=0 | stage=gold_absent_everywhere_detectable
- openai_gsm8k_820 | bucket=both_wrong | our_exact=0 | external_exact=0 | stage=gold_in_trace_candidates
- openai_gsm8k_829 | bucket=external_only | our_exact=0 | external_exact=1 | stage=gold_absent_everywhere_detectable
- openai_gsm8k_832 | bucket=both_wrong | our_exact=0 | external_exact=0 | stage=gold_absent_everywhere_detectable
- openai_gsm8k_841 | bucket=external_only | our_exact=0 | external_exact=1 | stage=gold_absent_everywhere_detectable
- openai_gsm8k_851 | bucket=external_only | our_exact=0 | external_exact=1 | stage=gold_absent_everywhere_detectable
