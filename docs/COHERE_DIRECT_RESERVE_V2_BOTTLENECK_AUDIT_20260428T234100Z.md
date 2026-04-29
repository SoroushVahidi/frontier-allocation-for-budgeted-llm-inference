# Cohere DR-v2 bottleneck audit (artifact-first)

Status: partial diagnostic audit using existing artifacts only (no new large run).

## Main question
Why can DR-v2 look strong in small diagnostics but trail `external_l1_max` in newer live partial validation?

## Audit command
```bash
python scripts/analyze_cohere_direct_reserve_v2_bottlenecks.py \
  --input-dirs outputs/cohere_direct_reserve_v2_vs_external_l1_local_validation_20260428T222827Z,outputs/cohere_real_model_cost_normalized_validation_20260425T133000Z_COHERE_STAGE1_MIN \
  --output-dir outputs/cohere_direct_reserve_v2_bottleneck_audit_20260428T234036Z
```

## Current evidence snapshot
- Matched DR-v2 vs `external_l1_max` cases used by audit: 20 (from local partial-audit fallback signal).
- Paired delta (DR-v2 - `external_l1_max`): **-0.15**.
- Direct cost/action deltas on matched DR-v2-vs-L1 rows: unavailable in discovered artifact set.

## Bottleneck interpretation against decision categories
1. **Data/sample instability:** likely contributes (n=20 matched is small).
2. **Direct-reserve algorithm weakness:** possible (negative paired delta).
3. **Extraction/canonicalization issue:** unknown from current artifacts.
4. **Cost/action inefficiency:** unproven from current artifact overlap.
5. **Branch proposal quality issue:** unknown (missing branch-presence tables on matched set).
6. **Final selection/commit failure:** unknown (no present-vs-selected decomposition on matched set).
7. **External L1 stronger strategy:** plausible on currently observed matched slice.

## Decision-support takeaway
- This audit currently supports: **sample instability + potential method weakness** as the leading explanation pair.
- It does **not** yet isolate extraction vs proposal vs commit failure.
- Safe near-term action: resume only a bounded paired continuation that explicitly logs proposal-present / selected / extraction-normalization fields.
- Keep DR-v2 in **diagnostic-only** status until that decomposition closes.

## Claim safety
Do not use this audit as manuscript headline evidence.
