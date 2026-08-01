# Pre-HPC experiment note: matched-coverage filtering on lightweight stop-vs-act data

## Why run this now

HPC is still unavailable, and we should not run heavy oracle-label generation yet. A cheap matched-coverage filtering study can still be decision-relevant: it checks whether selective retention appears to improve learning signal quality beyond just using fewer/easier examples.

## Exact comparison

On the current default stop-vs-act pipeline (default proxy labels, no oracle labels), build one matched state pool per seed/budget and compare:

1. **Default anchor**: all training rows retained.
2. **Selective filter**: retain a fixed fraction using lightweight quality proxies already in the dataset (uncertainty + reliability).
3. **Random matched baseline**: uniformly random retained subset with the **same retained coverage** as (2).

All variants use the same model family, same test split, and same controller-eval settings.

## Hypothesis under test

At matched retained coverage, selective filtering should outperform random filtering if filtering is capturing supervision quality signal; if gains are only from removing data or from easy-example concentration, selective should not reliably beat matched random.

## Safe vs unsafe conclusions

### Safe from this study
- Whether selective filtering shows a **directional** advantage over matched random under current proxy-label conditions.
- Whether observed gains seem tied to rate/compute shifts or remain visible under roughly comparable action behavior.
- Which slice (for example uncertainty bins) carries most of the difference.

### Unsafe from this study
- Any claim that oracle labels are validated or unnecessary.
- Any claim of final causal mechanism (quality-only vs difficulty-only) without stronger matched-rate and oracle-backed follow-up.
- Any broad generalization beyond this lightweight synthetic/proxy setup.
