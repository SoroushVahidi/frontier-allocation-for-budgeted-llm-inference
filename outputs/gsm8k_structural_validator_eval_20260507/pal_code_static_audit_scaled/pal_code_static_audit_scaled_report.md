# PAL code static audit — scaled (all local bundles)

Offline only — **no** API, **no** controllers, **no** selection changes.

## Cohort counts (offline labels)

```json
{
  "gold_absent_discovery": 20,
  "present_not_selected": 21,
  "pal_correct_guardrail": 200,
  "pal_wrong_other": 26,
  "pilot_track_b": 0,
  "unknown": 2021
}
```

## Trigger metrics

| Trigger | GA fires / rate | Guardrail fires / rate | PN fires / rate | Precision-like (labeled fires) | Policy |
|---------|-----------------|------------------------|-----------------|--------------------------------|--------|
| `any_static_pal_suspicion` | 7 / 0.350 | 35 / 0.175 | 7 / 0.333 | **0.115** | **weak** |
| `high_precision_static_pal_suspicion` | 7 / 0.350 | 23 / 0.115 | 3 / 0.143 | **0.200** | **weak** |
| `many_unused_final_sparse` | 4 / 0.200 | 20 / 0.100 | 2 / 0.095 | **0.143** | **mixed** |
| `opaque_one_expr_low_coverage` | 0 / 0.000 | 7 / 0.035 | 1 / 0.048 | **0.000** | **weak** |
| `rate_no_muldiv` | 2 / 0.100 | 4 / 0.020 | 2 / 0.095 | **0.222** | **weak** |
| `rate_specific_retry_candidate` | 2 / 0.100 | 4 / 0.020 | 2 / 0.095 | **0.222** | **weak** |
| `syntax_exec_or_empty` | 1 / 0.050 | 0 / 0.000 | 0 / 0.000 | **1.000** | **weak** |
| `temporal_no_state_no_sub` | 5 / 0.250 | 13 / 0.065 | 6 / 0.286 | **0.147** | **mixed** |
| `temporal_specific_retry_candidate` | 5 / 0.250 | 13 / 0.065 | 6 / 0.286 | **0.147** | **mixed** |
| `ungrounded_final_literal` | 0 / 0.000 | 0 / 0.000 | 1 / 0.048 | **0.000** | **weak** |

### Policy buckets

- **Promising:** ≥20% of `gold_absent_discovery` **and** ≤5% of `pal_correct_guardrail`, with cohort denominators n_ga≥10 and n_gr≥15; else **inconclusive** if too small. **Weak:** ≤10% GA **or** >10% guardrail.

- **Promising triggers now:** _(none)_
- **Weak / noisy:** `rate_no_muldiv`, `ungrounded_final_literal`, `syntax_exec_or_empty`, `opaque_one_expr_low_coverage`, `any_static_pal_suspicion`, `high_precision_static_pal_suspicion`, `rate_specific_retry_candidate`
- **Inconclusive (small denominators):** _(none)_

## Bundle coverage

- Bundles scanned: **16** with ≥1 PAL-code row.
- Total deduped rows: **2288**.

## Top fired cases (per trigger, first 20 in JSON)

See `pal_code_static_audit_scaled_summary.json` → `triggers.*.top_cases` and `bundle_breakdown_fires`.

## Track A retry / TRCE path

**Verdict:** No trigger met the **promising** thresholds on this scaled offline slice. **Static PAL-code triggers are not yet strong enough** to justify implementing Track A retry/TRCE policy — **pause** this direction until richer offline pools or stronger signals.

**API:** not required for this audit.