# Mistral Deep Error and Selector Diagnostic (2026-05-23)

**Scope:** offline diagnostic only.

- **Source bundle:** `outputs/mistral_frozen_agreement_only_2of3_validation_20260523T145416Z`
- **Processed bundle:** `outputs/mistral_frozen_agreement_only_2of3_live_result_20260523/`
- **Deep diagnostic bundle:** `outputs/mistral_deep_error_and_selector_diagnostic_20260523/`
- **Active Cohere/Cerebras jobs:** left untouched.

## Oracle gap

- Frontier: 78.33%
- Best single source: S1 at 89.67%
- Agreement-only: 85.33%
- Pooled-4: 83.67%
- Best S1-aware diagnostic so far: provider_prior_weighted_selector_mistral_s1_prior at 89.33%
- Oracle over four sources: 93.33%
- Oracle gain over frontier: 15.00 pp
- Agreement-only captures 46.7% of oracle gain
- S1 captures 75.6% of oracle gain
- Best diagnostic captures 37.8% of oracle gain

## Where agreement-only loses value

Agreement-only mainly loses on cases where it keeps frontier on no-majority ties or follows a wrong external majority that excludes S1.

## S1 under isolation

S1 remains strong even when isolated, so its advantage is not just support-driven.

## Useful runtime-legal signals

The best signals for trusting S1 are: external-majority absence, S1 being short/clean numeric, and S1 remaining strong in isolated cases.

## Diagnostic selector results

Best diagnostic selector in this bundle: **tree_depth2_source_selector** at **84.00%**.

Best learned selector on held-out splits: **tree_depth3_source_selector** with held-out accuracy 81.67% on average across folds.

No learned selector reliably beats always-S1 out of sample.

## Main failure source

The main failure source is source-majority logic plus frontier fallback; missing runtime features are not the main issue. S1 is already strong, but agreement rules do not exploit that strength consistently.

## Recommended next algorithm family

Use a provider-calibrated source-prior selector with a conservative S1 trust override, validated offline first on a locked holdout and a second matched Mistral seed.
