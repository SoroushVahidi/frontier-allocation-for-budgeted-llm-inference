# Next research actions

1. **PAL disagreement / failure bank:** run a multi-batch targeted loop to collect a larger set of PAL-vs-production_equiv disagreements and PAL-only failures *before* designing a PAL-hybrid selector.
2. **Casebook expansion:** reuse `pal_vs_production_equiv_casebook_*` and `pal_pot_advantage_loss_pattern_audit_*` patterns; prioritize reproducible manifests and offline replay hooks.
3. **Paper-facing tables:** cite `external_full_suite_matched50_comparison_20260508T222631Z` for apples-to-apples numerics; avoid superseded SC6 calibration folders for headline numbers.
4. **Selector design (later):** only after (1) has enough coverage — PAL-aware hybrid selection with explicit abstain/guardrails.

**Do not pursue (closed negative lines for now):** unbounded free-form retry as primary fix; schema-grounded retry v1 as integrated method without new evidence.
