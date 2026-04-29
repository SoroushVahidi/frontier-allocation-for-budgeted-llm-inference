# Cohere DR-v2 vs external_l1_max bottleneck audit

Status: diagnostic artifact audit only (no new large live run).

## Key question
Why did DR-v2 look competitive/winning in small diagnostics but trail external_l1_max in later live partial Cohere validation?

## Inputs reviewed
- `docs/COHERE_DIRECT_RESERVE_V2_LOCAL_PARTIAL_AUDIT_20260428T223833Z.md`
- `docs/COHERE_DIRECT_RESERVE_V2_VS_EXTERNAL_L1_LOCAL_VALIDATION_20260428T222827Z.md`
- `docs/SEMANTIC_DIVERSITY_EXPANDED_POOL_RESULT_ANALYSIS_20260428T185326Z.md`
- `docs/SEMANTIC_DIVERSITY_EXPANDED_POOL_RESULT_ANALYSIS_20260428T_DR_V2_LONG.md`
- `docs/REAL_MODEL_DECISION_PACKAGE_20260425T025417Z.md`
- `scripts/run_cohere_real_model_cost_normalized_validation.py`
- `scripts/postprocess_cohere_scaleup_outputs.py`

## New audit tool
- Added: `scripts/analyze_cohere_direct_reserve_v2_bottlenecks.py`
- Run output: `outputs/cohere_direct_reserve_v2_bottleneck_audit_20260428T231311Z/`

## What we can conclude now
1. **Sample/scope mismatch is real**: available Cohere Stage-1 real-model package does not contain DR-v2 rows, so strict paired DR-v2-vs-L1 bottleneck decomposition cannot be fully reconstructed from that package alone.
2. **Live partial signal is unfavorable**: documented local partial run reports DR-v2 trailing external_l1_max by paired delta -0.15 over 20 matched cases.
3. **Current evidence points first to instability/scope and possible algorithm weakness, not extraction bug proof**:
   - no direct extraction-failure dominant signature is established in available artifacts,
   - but no definitive branch-present-vs-selected decomposition is available either.
4. **Decision status**: keep DR-v2 as diagnostic-only; do not promote.

## Missing fields still blocking strong diagnosis
- Per-case DR-v2 vs L1 matched traces with branch-presence indicators.
- A standardized "present but not selected" table for DR-v2 loss cases.
- Consistent token/action/cost rows for both DR-v2 and L1 on the same matched slices.

## Recommended next minimal step (non-random)
If/when live calls are resumed, run **only** a bounded continuation that closes missing paired fields for the same dataset/seed/budget slices, then rerun this bottleneck analyzer. Do not run broad expansion until these decomposition fields are available.

## Claim discipline
This audit is diagnostic-only and must not be treated as manuscript headline evidence.
