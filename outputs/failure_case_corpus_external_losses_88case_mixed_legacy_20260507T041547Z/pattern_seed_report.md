# Failure Case Corpus Pattern Seed Report

- Failure/loss cases collected: 88
- Top outcome buckets: {'external_only': 69, 'both_correct': 19}
- Top operation/quantity patterns: operation={'rate_ratio': 30, 'temporal_change': 21, 'none': 20, 'difference': 18, 'product': 15}, quantity={'qnum_2_3': 39, 'qnum_4_5': 37, 'qnum_6p': 8, 'qnum_0_1': 4}
- Top gold-absence stages: {'gold_absent_everywhere_detectable': 87, 'gold_in_selector_pool': 1}
- External trace availability (cases): yes=0 no=88
- Missing external traces limit pairwise tree-diagnostics where availability=no.

## Top cases for manual inspection
- openai_gsm8k_3 | bucket=both_correct | our_exact=1 | external_exact=1 | stage=gold_absent_everywhere_detectable
- openai_gsm8k_2 | bucket=both_correct | our_exact=1 | external_exact=1 | stage=gold_absent_everywhere_detectable
- openai_gsm8k_1 | bucket=both_correct | our_exact=1 | external_exact=1 | stage=gold_absent_everywhere_detectable
- openai_gsm8k_6 | bucket=external_only | our_exact=0 | external_exact=1 | stage=gold_absent_everywhere_detectable
- openai_gsm8k_576 | bucket=external_only | our_exact=0 | external_exact=1 | stage=gold_absent_everywhere_detectable
- openai_gsm8k_3 | bucket=external_only | our_exact=0 | external_exact=1 | stage=gold_absent_everywhere_detectable
- openai_gsm8k_158 | bucket=external_only | our_exact=0 | external_exact=1 | stage=gold_absent_everywhere_detectable
- openai_gsm8k_12 | bucket=external_only | our_exact=0 | external_exact=1 | stage=gold_absent_everywhere_detectable
- openai_gsm8k_7 | bucket=external_only | our_exact=0 | external_exact=1 | stage=gold_absent_everywhere_detectable
- openai_gsm8k_3 | bucket=external_only | our_exact=0 | external_exact=1 | stage=gold_absent_everywhere_detectable
- openai_gsm8k_17 | bucket=external_only | our_exact=0 | external_exact=1 | stage=gold_absent_everywhere_detectable
- openai_gsm8k_158 | bucket=external_only | our_exact=0 | external_exact=1 | stage=gold_absent_everywhere_detectable
- openai_gsm8k_12 | bucket=external_only | our_exact=0 | external_exact=1 | stage=gold_absent_everywhere_detectable
- openai_gsm8k_6 | bucket=external_only | our_exact=0 | external_exact=1 | stage=gold_absent_everywhere_detectable
- openai_gsm8k_5 | bucket=external_only | our_exact=0 | external_exact=1 | stage=gold_absent_everywhere_detectable
