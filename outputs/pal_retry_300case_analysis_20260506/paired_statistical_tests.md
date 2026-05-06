# Paired statistical tests (300-case fresh sample)

- Paired rows: **300**
- External exact: **244/300** (0.8133)
- PAL+retry exact: **252/300** (0.8400)
- Estimated gap (PAL+retry − external): **2.67 pp**

## Wilson 95% confidence intervals
- External: **[76.54%, 85.34%]**
- PAL+retry: **[79.43%, 87.71%]**

## Discordant contingency (exact-match pairs)
- Both correct: **223**
- External only correct: **21**
- PAL only correct: **29**
- Both wrong: **27**

## McNemar-style exact test on discordants
Conditional on discordant pairs where exactly one side is correct, test symmetry with exact binomial (two-sided) with \(p = 1/2\).

- Discordants: \(b=21\) (external wins), \(c=29\) (PAL wins), \(n=50\)
- Two-sided binomial \(p \approx **0.3222**\)
- Interpretation: **not statistically significant**; data remain compatible with no average paired advantage.

## Bootstrap 95% CI for paired accuracy difference

- 20,000 resamples of paired mean difference (p_pal_retry minus p_external): **[-2.00 pp, 7.33 pp]**
- Interval includes 0: **yes**.

## Superiority?

- Statistical superiority claim (paired exact-match, McNemar + bootstrap excludes 0): **False**.
- Directionally PAL+retry is ahead on this draw, but evidence is compatible with modest noise.
