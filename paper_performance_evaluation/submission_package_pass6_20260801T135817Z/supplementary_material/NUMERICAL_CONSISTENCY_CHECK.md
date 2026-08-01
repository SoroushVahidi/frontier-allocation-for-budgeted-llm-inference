# Performance Evaluation Numerical Consistency Check

Updated for Pass 6 supplementary packaging.

## Scope

This check records manuscript-facing numerical invariants after redundancy reduction, layout
revision, and submission packaging. It does not compare against another journal manuscript and does
not alter scientific records.

## Headline Values Preserved

- Completed cells: 15/16.
- Blocked outcome: Fireworks x GPQA-Diamond `BLOCKED_PROTOCOL_NONCONVERGENCE`.
- Completed-cell paired examples: n=3394.
- Nominal budget: B=6.
- FTA aggregate accuracy: 65.00%.
- Pooled-4 aggregate accuracy: 66.53%.
- Pooled-4 vs FTA McNemar p-value: 0.00027.
- FTA/Pooled-4/tie discordants: 73/125/3196.
- Frontier aggregate count: 2176/3394.
- Held-out selector: Pooled-4 selected in all 15 leave-one-cell-out folds.
- Azure x GSM8K same-model self-consistency control: 276/300 for both Frontier and SC-N=6.
- Successful-call reconstruction: 2.78 uncorrected to 5.38 reconstructed.
- Azure FIX-2 rescue/regression patterns: 2/18 and 7/31.
- Repair external winner flips under the uniform-repair counterfactual: 0.

## Packaging Checks

- Anonymous and title-page manuscripts compile to 34 pages.
- Flat LaTeX source compiles independently after path flattening.
- Submission and supplementary ZIP files pass `unzip -t`.
- Supplement checksums pass `sha256sum -c`.
- Supplement scan has no journal-migration wording from prior manuscript targets.

## Interpretation

Pass 6 changed prose organization, repeated explanations, captions, frontmatter wording, and package
layout. It did not change tables, result values, p-values, counts, blocked-outcome semantics, or
claim boundaries.

