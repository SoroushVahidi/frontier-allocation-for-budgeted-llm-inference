# Cerebras × GSM8K — Completed Processing Report

**Processing timestamp:** 2026-05-25T20:04:08Z
**Source artifact:** `outputs/cerebras_frozen_agreement_only_2of3_validation_20260523`
**Processing output:** `outputs/cerebras_gsm8k_completed_processing_20260524/`

## Integrity

| Field | Value |
|---|---|
| Total raw rows | 1201 |
| After deduplication | 1200 |
| Scored rows | 1200 |
| Complete examples (all 4 methods) | **300** |
| Duplicate pairs resolved | 1 |
| Failed rows | 0 |
| `[done]` in log | True |
| **Integrity pass** | **PASS** |

## Method Accuracies

| Method | Accuracy |
|---|---|
| L1 | 1.33% |
| S1 | 1.33% |
| TALE | 1.33% |
| frontier | 1.0% |

## Regime: `near_peer`

- Best source: L1 (1.33%)
- Best–second spread: 0.00pp
- S1 dominant: True

## Selector Results (top)

| Selector | Accuracy |
|---|---|
| oracle_best_source | 2.0% |
| oracle_best_action | 2.0% |
| pooled4_with_fallback | 1.67% |
| agreement_only_2of3_against_frontier | 1.67% |
| raw_spread_regime_selector | 1.67% |
| beta_shrinkage_regime_selector | 1.67% |
| dominant_source_veto | 1.67% |
| external_l1_max | 1.33% |

## Failure Taxonomy

| Set | Count | % |
|---|---|---|
| all_sources_wrong | 294 | 98.0% |
| our_algorithm_wrong_oracle_correct | 1 | 0.33% |
| pooled4_wrong_oracle_correct | 1 | 0.33% |
| S1_correct_our_algorithm_wrong | 0 | 0.0% |

## Safety

No API calls. No job interruptions. Offline processing only.
