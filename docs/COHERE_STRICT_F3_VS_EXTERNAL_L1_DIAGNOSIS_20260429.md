> **WARNING (diagnostic/small-sample):** This document is not standalone canonical paper-facing evidence. Do not use for broad superiority claims without canonical matched-surface confirmation.

# Cohere strict_f3 vs external_l1 diagnostic (2026-04-29)

## Scope
This diagnosis uses existing artifacts only (no new broad API experiment) to analyze why `strict_f3` underperforms `external_l1_max` on Cohere GSM8K.

Analyzed timestamps:
- Budget 2: `20260429T_COHERE_NEURIPS_MINIMAL_RUN1` (aggregate-only available in this workspace)
- Budget 4: `20260429T_COHERE_GSM8K_B4_CLAIM_SAFETY` (per-example available)

## Is the loss real paired-case loss or missingness artifact?
- **Budget 4 paired result is real performance loss**, not missingness:
  - Paired cases: 100
  - Missing/unpaired: 0
  - `strict_f3 - external_l1_max` paired gap: `-0.17`
  - Outcome matrix: both correct 47, both wrong 20, f3-only wins 8, l1-only wins 25.
- **Budget 2**: per-example artifacts are unavailable in this checkout path, so paired-case decomposition cannot be recomputed here; only previously reported aggregate gap (`-0.15`) is available.

## Repeated failure patterns
From budget-4 strict_f3 loss cases (`f3_wrong_l1_correct`), recurring strict_f3 failure tags are:
- `correct answer absent from explored tree` (most frequent)
- `correct answer present but not selected` (second most frequent)
- rare `parse/extraction failure`

This indicates both **coverage failures** and **selection/aggregation failures** under the current budget contract.

## Likely mechanism class
Most likely contributors (from available artifacts):
1. **Method-design interaction with provider behavior** (primary): strict_f3 spends more actions/tokens but does not translate that into higher paired-case accuracy versus simple external-l1 path.
2. **Coverage + selection mix** (secondary): many loss cases are either absent-from-tree or present-but-not-selected.
3. **Extraction/evaluation mismatch** (minor): present but comparatively rare.

## Budget effect (2 -> 4)
- Budget 2 aggregate gap: `-0.15`
- Budget 4 paired gap: `-0.17`
- Interpretation: budget 4 **does not reduce** this failure pattern in currently completed slices; direction stays unfavorable.

## strict_gate1 / tale / s1 status for this budget-4 timestamp
- These are not final in the current budget-4 timestamped run and therefore not used for final-safe ordering claims in this diagnosis.

## Manuscript impact
Recommended limitations sentence (appendix-safe, conservative):
> In Cohere GSM8K diagnostics, our frontier-allocation strict_f3 variant underperformed a simpler external_l1_max baseline at both low and moderate action budgets (2 and 4), indicating provider- and budget-dependent failure modes in search coverage/selection rather than universal gains from additional structured exploration.

## Most justified next experiment
A **targeted paired replay** (not broad rerun) on the budget-4 `f3_wrong_l1_correct` cases to separate:
- absent-from-tree vs present-but-not-selected mechanisms,
- with controlled selection-rerank/commit-ablation logging,
- while keeping dataset/budget/seed fixed.

## Claim status
- This diagnosis does **not** upgrade any headline manuscript claim.
- It strengthens a conservative appendix limitation: current Cohere diagnostics are unfavorable to strict_f3 vs external_l1_max at budgets 2 and 4.
