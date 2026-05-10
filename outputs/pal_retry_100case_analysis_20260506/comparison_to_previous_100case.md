# Comparison to previous no-retry 100-case run

Different samples were used, so this is **not** a paired ablation and must be interpreted cautiously.

## Side-by-side
- External accuracy: previous **75%** vs new **85%**
- PAL accuracy: previous **80%** vs new PAL+retry **84%**
- PAL-vs-external gap: previous **+5 pp** vs new **-1 pp**
- Discordants: previous (ext-only=5, pal-only=10) vs new (ext-only=9, pal-only=8)
- Retry opportunities: previous N/A vs new **4/100**

## Interpretation
- Both methods performed better in absolute terms on the new sample, suggesting sample-difficulty/composition shift.
- The relative gap moved from PAL-favoring to near parity/slight external edge, but discordants remain balanced.
- Because retry triggered in only 4% of cases, global movement from retry is mechanically limited on this sample.
