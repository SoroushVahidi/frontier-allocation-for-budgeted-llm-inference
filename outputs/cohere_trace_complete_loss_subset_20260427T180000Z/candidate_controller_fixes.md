# Candidate controller fixes

- Selected cases: 4
- Completed trace cases (strict_f3 + external_l1_max present): 4
- immediate_miss: 4
- partial_progress: 0
- near_miss_absent_final: 0
- present_but_misselected: 1

## Top 3 recommended fixes
- Direct-path fallback for immediate_miss-heavy cases.
- Delayed commit in partial_progress cases to allow maturation of promising branches.
- Continuation-score and anti-collapse tuning to preserve near-miss branches.
