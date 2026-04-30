# Selector Experiment on 33 Gold-Present Losses

- Did we find exactly 33 cases: True (actual=33)
- Selector fixing most cases: oracle_selector
- Best safety-adjusted net gain: oracle_selector
- Support-family selector fixes: 2
- Cohere outcome verifier fixes: 1
- Cohere pairwise verifier fixes: 0
- Bottleneck on this subset is selector quality by construction (gold present, oracle fixable).
- Recommendation: promote selector with highest net_fixes_minus_safety_breaks for larger validation.
