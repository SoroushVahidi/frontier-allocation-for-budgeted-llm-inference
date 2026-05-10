# Final no-API preflight recommendation (PAL vs external_l1_max)

## Scope

- Candidate comparison: `external_l1_max` vs `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal`
- Dataset: fresh GSM8K IDs only (exclude previously selected/allowed/casebook IDs discovered under `outputs/`)

## Known evidence so far

- Targeted PAL corrected/replayed set: **21/28** exact.
- Capped paired pilot (`n=43`, fully paired):
  - `external_l1_max`: **36/43** (83.72%)
  - `..._tiebreak_pal`: **40/43** (93.02%)
  - Delta: **+9.30 pp**

## Claim boundary

This is still **small/capped** evidence. It is promising, but not yet paper-level proof.

## Fresh-pool preflight result

- Excluded IDs discovered from prior artifacts: **113**
- Fresh candidate IDs remaining in GSM8K test split: **1206**

## Call-cap estimates (conservative)

Assumptions are deliberately conservative because prior pilot indicated row-sum can understate global cap use.

- Cap **500**: recommended fully paired target ~**33**
- Cap **750**: recommended fully paired target ~**50**
- Cap **1000**: recommended fully paired target ~**67**
- Cap **1500**: recommended fully paired target ~**100**

## Recommendation

- **Default next API batch:** `max_total_api_calls=1000`, target around **67 fully paired** fresh examples.
- **Stronger option (only with explicit approval):** `max_total_api_calls=1500`, target around **100 fully paired** fresh examples.

## Is 1000 enough?

- **Enough for a meaningful next step** (materially larger than 43 paired).
- Still moderate; may be insufficient if per-pair call cost rises due to harder samples.

## Is 1500 better?

- **Yes for robustness** and reduced partial-pairing risk.
- Preferred when budget allows and user explicitly approves additional spend.

## Risks to track during live run

1. Cap saturation before all planned pairs complete.
2. Partial pairing (missing one method’s row for an example).
3. Repeated cases slipping into fresh pool.
4. Metric inconsistency between raw and corrected/replay summaries.

## Hard gate before any live batch

- Keep API paused until explicit approval.
- Run no-API preflight checks first (already done here for method validation).
- Enforce fresh-ID allowlist and pairing completeness checks in the runner pipeline.
