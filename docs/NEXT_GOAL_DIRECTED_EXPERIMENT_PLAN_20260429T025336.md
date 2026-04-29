# Next Goal-Directed Experiment Plan

## 1) Current decision
The decision package indicates the dominant external winner is **direct_length_control** (`external_l1_max`) and the dominant failure type is **external_direct_advantage**, but coverage is still insufficient for TALE/S1 and self-consistency/ToT families.

## 2) Evidence strength
- Paired cases: 120
- External-win cases: 31
- Trace-complete external-win cases: 11
- Unknown/no-trace fraction: 0/31 = 0.00 in current labels (but trace-complete count is still below threshold)
- Dominant external family: direct_length_control
- Dominant failure type: external_direct_advantage

## 3) Next step choice
**Recommended next step: collect more trace-complete real-LLM losses** (`collect_trace_complete_losses`).
Reason: family-coverage gaps remain (`tale_or_s1=0`, `self_consistency_or_tot=0`, `traced_external_win=11<20`).

## 4) Exact next experiment
- Objective: close missing-family and trace-complete coverage gaps to make bottleneck attribution robust across external baselines.
- Hypothesis: once TALE/S1 and self-consistency/ToT are added with trace-complete rows, the dominant bottleneck may shift from direct-length advantage to selection/commit behavior.
- Methods:
  - Internal: `strict_f3`, `strict_gate1_cap_k6`, `direct_reserve_semantic_frontier_v2`
  - External: `external_l1_max`, `tale`, `s1`, `self_consistency_3`, `tot_beam_matched_budget` (or closest resolved ToT method)
- Datasets: `openai/gsm8k`
- Budgets: `4`
- Seeds: `11`
- Max examples: `20`
- Live API needed: **Yes**
- Expected outputs:
  - a bounded live output run directory,
  - refreshed `external_baseline_loss_case_collection_*`,
  - refreshed decision package,
  - methods exclusion log if any methods fail to resolve.
- Success criterion:
  - `tale_or_s1 >= 20`, `self_consistency_or_tot >= 20`, `traced_external_win >= 20`
  - at least 20 new trace-backed external-win rows added.
- Stop criterion:
  - if unresolved methods prevent required family coverage after bounded run,
  - or if trace coverage still <20 and failures are mostly missing traces.

## 5) Why this is not random
This is directly constrained by the explicit gap metrics in `baseline_family_gap_report.csv`, not open-ended exploration.

## 6) What result would justify algorithm change
If after coverage closure one failure type remains dominant with >=20 trace-backed losses (especially `present_not_selected` or commit/selection proxies), move to a targeted selection/commit algorithm patch.

## 7) What result would stop this line of work
If bounded collection cannot produce adequate trace-complete multi-family evidence, freeze claim promotion and keep this as diagnostic-only evidence.
