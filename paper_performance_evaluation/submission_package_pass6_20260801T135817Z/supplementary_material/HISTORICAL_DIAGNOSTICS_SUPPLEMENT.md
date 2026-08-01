# Historical Diagnostics Supplement

This note preserves diagnostic material removed from the journal manuscript during the focused
correction pass. These records are supplementary only: they are not part of the evaluated
15-cell Frontier/FTA evidence surface and they do not change any manuscript result.

## Researcher-Adaptation Boundary

FIX-2 and FIX-4 were developed on Cohere x GSM8K failure diagnostics and frozen before the
subsequent matrix evaluation. Later 4 x 4 provider x dataset cells are transfer evaluations.
Runtime features remain gold-free, but researcher adaptation on Cohere x GSM8K is real. Azure
FIX-2 regressions are therefore important transfer evidence.

## Held-Out Selector Protocol Identifier

The leave-one-cell-out selector protocol identifier printed in earlier manuscript drafts is:

`9d1978ffcd3211d62476ceb11a3e8eae06dc8d5d8c073336a9d60bf3c7724257`

## Historical Negative Variants

Agreement-region router, extra-budget recovery action, cluster reranking, and related FIX-5--9
explorations were not retained because they were net negative, budget-breaking, or below threshold.
A historical all-methods-wrong diagnostic suggested residual errors were mostly discovery-limited;
the exact reconstruction is not available in the released artifact record, so precise counts are
non-load-bearing.

## Historical Component Diagnostics

These rows summarize older STRICT-F3-surface component diagnostics. They are not Frontier/FTA
ablations for the evaluated protocol; they document calibration sensitivity of answer support,
anti-collapse, and repeat-family controls on an older method surface.

| Variant | n | Accuracy | Absent | Present-not-selected | Interpretation |
| --- | ---: | ---: | ---: | ---: | --- |
| Full integrated | 320 | 62.81% | 86 | 33 | Historical reference |
| Allocation-only core | 320 | 61.25% | 94 | 30 | Lower than full |
| No answer support | 320 | 58.44% | 96 | 32 | Answer support helps on this surface |
| No anti-collapse | 320 | 59.06% | 100 | 31 | Default not universally beneficial |
| No output repair | 320 | 62.81% | 86 | 33 | No change in this reconstruction |
| No repeat control | 320 | 63.12% | 92 | 26 | Slightly higher; calibration-sensitive |

## Natural Plan and GPQA Pilot Details

Non-math pilot records exist for Natural Plan and GPQA-Diamond, but they are small pilots, not the
evaluated 15-cell Frontier/FTA matrix and not official baseline reproductions. Manuscript GPQA
claims use the 15-cell matrix; Natural Plan remains pilot-only.

| Dataset/surface | Method | n | Budget/actions | Correct | Accuracy | Note |
| --- | --- | ---: | --- | ---: | ---: | --- |
| GPQA-Diamond pilot | strict-F3 historical | 24 | hist. 4/6 actions | 16 | 66.67% | Controlled pilot/adapted harness; no CI reported |
| GPQA-Diamond pilot | SC-N=5 | 24 | 5 | 15 | 62.50% | Historical same-model context; no CI reported |
| GPQA-Diamond pilot | Best majority | 24 | post-generation | 17 | 70.83% | Oracle-style upper context; not a policy claim |
| Natural Plan pilot | strict-F3 historical | 16 | hist. 4/6 actions | 11 | 68.75% | Controlled pilot/adapted harness; no CI reported |
| Natural Plan pilot | weak anti-collapse historical | 16 | hist. 4/6 actions | 11 | 68.75% | Historical calibration diagnostic; no CI reported |

## Historical Partial Same-Model Self-Consistency Checks

Table 5 in the manuscript supersedes the old Azure x GSM8K partial checks for the direct six-call
self-consistency question. The checks below are N-asymmetric offline context only: N=3 for
Azure/Cohere, N=5 for Vertex; GSM8K/GPQA only; not token- or cost-matched. Holm correction is
within two separate families (Azure/Vertex; Cohere), not a joint six-cell family. This is not a
full-matrix matched self-consistency or best-of-N comparison.

| Provider | Dataset | n | SC acc. | Pooled-4 acc. | Delta (pp) | Raw p | Holm p | Sig. |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Azure OpenAI | GPQA-MCQ | 198 | 48.48% | 52.53% | -4.04 | 0.2153 | 0.8613 | No |
| Azure OpenAI | GSM8K | 300 | 91.33% | 92.00% | -0.67 | 0.6250 | 1.0000 | No |
| Vertex Gemini | GPQA-MCQ | 194 | 58.76% | 61.86% | -3.09 | 0.3269 | 0.9808 | No |
| Vertex Gemini | GSM8K | 300 | 93.33% | 92.67% | +0.67 | 0.6875 | 1.0000 | No |
| Cohere | GSM8K | 300 | 81.33% | 87.00% | -5.67 | 0.0115 | 0.0230 | Yes |
| Cohere | GPQA-MCQ | 198 | 35.35% | 36.36% | -1.01 | 0.8714 | 0.8714 | No |

## Discovery-Selection Scatter Diagnostic

The descriptive appendix scatter plot from earlier manuscript drafts plotted discovery rate against
FTA-minus-Frontier accuracy delta for the 15 completed cells. The global Pearson correlation was
`r = -0.185`, not supported at `n = 15`, and leave-one-out ranges varied. This diagnostic remains a
sanity check only; the clearer transfer evidence is the provider-stratified Azure sign reversal
reported in the manuscript.
