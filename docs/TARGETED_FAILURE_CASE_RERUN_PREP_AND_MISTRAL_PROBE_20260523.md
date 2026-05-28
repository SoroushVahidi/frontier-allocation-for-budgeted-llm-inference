# Targeted Failure-Case Rerun Prep and Mistral Probe — 2026-05-23

**Date:** 2026-05-23  
**Status:** Mistral targeted rerun launched and running.  
**Analyzed by:** Claude Code (offline case selection + live Mistral rerun; no Cohere paid calls; Cerebras not touched)

---

## Motivation

Cohere canonical Final-300 and Mistral Final-300 are complete. We know:
- Cohere is near-peer → pooled-4 (85.67%) is best.
- Mistral is dominant-source → S1 (89.67%) is best; pooled-4 (83.67%) and agreement-only (85.33%) underperform.

This task targets only the known failure cases to test whether algorithmic changes (regime selector, dominant-source veto, calibrated fallback) can fix them, before committing to a full 300-case or 1200-call rerun.

**Key constraint:** Failure-only targeted rerun results are diagnostic/biased — they cannot prove overall improvement. Full validation is required after probe results are reviewed.

---

## Selected Failure Cases

### Mistral (40 failure cases, 14 regression-check cases = 54 total)

| Failure Set | Count | Root Cause |
|---|---|---|
| `mistral_agreement_wrong_s1_correct` | 19 | No external majority or wrong majority; S1 correct |
| `mistral_pooled4_wrong_s1_correct` | 19 | L1+TALE+frontier outvote correct S1 |
| `mistral_no_majority_frontier_fallback_wrong` | 20 | No majority, wrong frontier fallback |
| `mistral_l1_tale_wrong_majority_s1_correct` | 13 | L1+TALE family agree wrong; S1 correct |
| `mistral_best_source_isolated_correct_pooled_wrong` | 9 | S1 isolated and correct; pooled-4 cannot recover |

Many cases overlap across sets. 40 unique failure cases selected for rerun.

14 regression-check cases: S1 correct on original run — test that new rules don't regress these.

### Cohere (30 candidate cases — NOT launched)

| Failure Set | Count |
|---|---|
| `cohere_pooled4_wrong_oracle_correct` | 23 |
| `cohere_best_source_isolated_correct_pooled_wrong` | 23 |
| `cohere_no_majority_frontier_fallback_wrong` | 13 |
| `cohere_agreement_wrong_pooled4_correct` | 12 |
| `cohere_all_sources_wrong` | 20 |

**Cohere paid rerun NOT launched.** 30 candidate cases prepared in `cohere_paid_rerun_candidate_cases.jsonl` for future authorization.

---

## Mistral Rerun Call Plan

| Field | Value |
|---|---|
| Provider | mistral |
| Model | mistral-small-latest |
| Cases | 54 (40 failure + 14 regression) |
| Methods | frontier, L1, S1, TALE |
| Estimated logical calls (upper) | ~486 |
| Estimated duration | 10–30 min |
| MISTRAL_API_KEY | present |
| tmux session | `mistral_targeted_failures_20260523T230623Z` |
| Output root | `outputs/targeted_failure_case_rerun_prep_and_mistral_probe_20260523/mistral_targeted_rerun_20260523T230623Z/` |
| Log | `outputs/targeted_failure_case_rerun_prep_and_mistral_probe_20260523/mistral_targeted_rerun_20260523T230623Z.log` |

**Monitoring instructions:**
```bash
tail -f outputs/targeted_failure_case_rerun_prep_and_mistral_probe_20260523/mistral_targeted_rerun_20260523T230623Z.log
# or
tmux attach -t mistral_targeted_failures_20260523T230623Z  # then detach with Ctrl-B d
```

---

## Diagnostic Selectors to Evaluate on Rerun Output

When rerun completes, apply these offline selectors to the 54-case results:

1. `pooled4_with_fallback` — baseline
2. `agreement_only_2of3_against_frontier` — baseline
3. `always_s1` — ceiling for Mistral
4. `regime_selector_accuracy_spread` — main hypothesis (route to S1 when spread > 0.05)
5. `frontier_fallback_calibrated` — fix no-majority cases
6. `dominant_source_veto` — when S1 isolated, override pooled majority
7. `majority_requires_dominant_source_when_dominant` — only trust majority if it includes dominant source
8. `pooled4_near_peer_else_best_source` — regime-dependent routing

---

## Cohere Paid Rerun Candidate — Not Launched

30 Cohere failure cases prepared in `cohere_paid_rerun_candidate_cases.jsonl`. **Not launched.** Will be authorized separately after Mistral probe results are reviewed and Cerebras completes.

---

## Caveat: Failure-Only Results Are Not Final Validation

Results from this rerun apply only to the selected failure/regression cases. They:
- **cannot** prove overall accuracy improvement
- may show overfitting to failure cases
- require full 300-case held-out validation before any policy is promoted

A candidate rule is worth full validation if:
- Recovers ≥50% of targeted failure cases, AND
- Regresses ≤20% of regression-check cases

---

## Constraints Confirmed

- Cohere paid rerun: NOT launched
- Cerebras job (PID 2195513): NOT touched
- Frozen policy logic: NOT modified
- No policy promoted
- All diagnostic selector variants labeled diagnostic-only
