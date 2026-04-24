# PAPER_CLAIMS_AND_EVIDENCE_MAP

Conservative map from claim type to evidence status.

## Legend

- **Safe**: defensible from current canonical docs/artifacts.
- **Supportive**: useful but not headline-safe without caveat.
- **Speculative / open**: not yet submission-safe.

## Claims map

| Claim | Status | Primary evidence | Notes |
|---|---|---|---|
| Repository identity is fixed-budget adaptive compute allocation with branch allocation + commit control + anti-collapse under budget. | Safe | `README.md`, `CANONICAL_START_HERE.md` | Keep explicit “not old binary revise-routing” statement. |
| Broader operational strict-phased default is `strict_gate1_cap_k6`. | Safe | `FINAL_STRICT_PHASED_DEFAULT_DECISION_EVAL_20260421T042913Z.md`, `CURRENT_DEFAULT_MODEL_AND_STRICT_PHASED_STATUS_2026_04_21.md` | Broader strict-phased surface only. |
| Manuscript-facing matched-surface internal winner is `strict_f3`. | Safe | `INTERNAL_METHOD_FINAL_DECISION_PACKAGE_2026_04_22.md`, `MANUSCRIPT_METHOD_VS_OPERATIONAL_DEFAULT.md`, `PAPER_METHOD_DECISION_BUNDLE_20260422T175142Z.md` | Matched-surface internal comparison only. |
| Diversity + answer-group aggregation + anti-collapse contributes to final behavior under budget. | Safe (mechanistic) | `CURRENT_PROMOTED_METHOD_LINE_2026_04_20.md`, component ablation reports | Use as mechanism statement, not universal guarantee. |
| Failure modes are concentrated in early tree coverage / branch-family control. | Safe (within audited surfaces) | `CURRENT_BOTTLENECKS.md`, strict-phased and failure-stat docs | State audited-surface scope. |
| External baselines are comprehensively closed for all paper tables. | Not safe | `EXTERNAL_BASELINE_PAPER_READINESS_DECISION_PACKAGE.md` | Only a subset is main-table ready. |
| Adjacent imported baselines dominate our method on canonical surface. | Not safe | N/A | No canonical evidence to assert this. |
| Real-model confirmation is broad and final across many independent settings. | Supportive only | `CANONICAL_REAL_MODEL_VALIDATION_20260423T121500Z.md`, related docs | Keep “bounded confirmation” wording. |
| Canonical paper-facing ours-vs-external real-model package is fully completed cross-provider. | Speculative / open | `REAL_MODEL_OURS_VS_EXTERNAL_VALIDATION_20260424T002900Z.md` | Current item is dry-run/package scaffolding; cross-provider API-backed completion remains open. |
| OpenAI smoke ours-vs-external run establishes main-paper-safe direction. | Not safe | `REAL_MODEL_OURS_VS_EXTERNAL_VALIDATION_20260424T_OPENAI_REAL_SMOKE.md` | OpenAI-only subset-5 smoke with nonzero rows; observed direction in this run does not favor ours (best-ours < best-external), so it is not headline-safe and motivates larger rerun. |

## Rules before writing a claim

1. Choose surface: broader operational vs manuscript matched.
2. Confirm evidence family is canonical in `PAPER_SOURCE_OF_TRUTH.md`.
3. If evidence is supportive-only, mark claim as bounded / appendix.
4. If evidence missing, mark as open gap in `PAPER_OPEN_GAPS_AND_RISKS.md`.
