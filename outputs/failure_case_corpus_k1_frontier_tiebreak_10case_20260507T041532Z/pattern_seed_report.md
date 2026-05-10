# Failure Case Corpus Pattern Seed Report

- Failure/loss cases collected: 4
- Top outcome buckets: {'external_only': 2, 'both_wrong': 2}
- Top operation/quantity patterns: operation={'rate_ratio': 4, 'total_sum': 1, 'difference': 1, 'product': 1}, quantity={'qnum_4_5': 1, 'qnum_6p': 1, 'qnum_0_1': 1, 'qnum_2_3': 1}
- Top gold-absence stages: {'gold_absent_everywhere_detectable': 4}
- External trace availability (cases): yes=0 no=4
- Missing external traces limit pairwise tree-diagnostics where availability=no.

## Top cases for manual inspection
- openai_gsm8k_118 | bucket=external_only | our_exact=0 | external_exact=1 | stage=gold_absent_everywhere_detectable
- openai_gsm8k_297 | bucket=both_wrong | our_exact=0 | external_exact=0 | stage=gold_absent_everywhere_detectable
- openai_gsm8k_324 | bucket=both_wrong | our_exact=0 | external_exact=0 | stage=gold_absent_everywhere_detectable
- openai_gsm8k_800 | bucket=external_only | our_exact=0 | external_exact=1 | stage=gold_absent_everywhere_detectable
