# Current research state (compact)

**Matched GSM8K n=50 (same case IDs; see `external_full_suite_matched50_comparison_20260508T222631Z`):**

| Method / role | Score /50 |
|---------------|----------:|
| production_equiv_v1 | 36 |
| external_l1_max_fair_v1 | 31 |
| external_self_consistency_4_fair_v1 | 33 |
| external_self_consistency_6_fair_v1 | 36 |
| external_pal_pot_fair_v1 | **40** |
| external_s1_budget_forcing_faithful_v1 | 32 |
| external_tale_ep_prompt_budgeting_faithful_v1 | 34 |
| best full external oracle (analysis) | 43 |
| prior patch-focused integrated (alignment artifact) | 39 |

**Headline:** PAL/PoT fair is the strongest *individual* external baseline on this matched-50 slice (40/50). production_equiv_v1 is 36/50 — beats L1/SC4/S1/TALE-EP, ties SC6, **does not** beat PAL/PoT.

**Negative diagnostics (not integrated winning methods):** free-form / targeted discovery retry pilots; schema-grounded retry v1 (parse/format failures).

**Claim hygiene:** “Beats all individual external baselines” is **unsafe**. Safer framing: beats listed weaker individual baselines and ties SC6; trails PAL/PoT on matched 50.

**Oracle caveat:** `best_full_external_oracle` is analysis-only, not a deployable single method.
