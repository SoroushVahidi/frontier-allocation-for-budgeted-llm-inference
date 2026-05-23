# Cohere Canonical Final-300: Frozen Agreement-Only Live Result — 2026-05-23

**Analysis timestamp:** 2026-05-23T22:10Z  
**Analyzed by:** Claude Code (offline/read-only; no API calls made; Cerebras not touched)  
**Output directory:** `outputs/cohere_canonical_final300_frozen_agreement_live_result_20260523/`

---

## 1. Run Integrity and Health

**Verdict: PASS — Fully complete, no failures.**

| Field | Value |
|---|---|
| Provider | cohere |
| Model | command-r-plus-08-2024 |
| Dataset | openai/gsm8k |
| Seed | 71 |
| Budget | 6 |
| Total records | 1200 |
| Expected records | 1200 |
| Scored rows | 1200 |
| Failed rows | 0 |
| Duplicate rows | 0 |
| Skipped rows | 0 |
| All 4 methods × 300 examples complete | YES |
| Integrity pass | **YES** |

**Per-method completion:**

| Method | Label | Scored | Missing | Failed |
|---|---|---|---|---|
| `direct_reserve_semantic_frontier_v2` | frontier | 300/300 | 0 | 0 |
| `external_l1_max` | L1 | 300/300 | 0 | 0 |
| `external_s1_budget_forcing` | S1 | 300/300 | 0 | 0 |
| `external_tale_prompt_budgeting` | TALE | 300/300 | 0 | 0 |

**Errors:** One transient HTTP 502 recovered by retry mechanism (attempt 1/5, 1.047s wait). No rate-limit, quota, 429, or fatal errors.

---

## 2. Canonical Contract Verification

**Verdict: EXACT MATCH — All 300 canonical Final-300 IDs present, none extra, none missing.**

| Field | Value |
|---|---|
| Canonical prep IDs | 300 |
| Run unique IDs | 300 |
| Overlap | 300/300 |
| Extra in run | 0 |
| Missing from run | 0 |
| Exact ID set match | **YES** |
| All IDs are `openai_gsm8k_train_*` | YES |
| Not test-set contamination | YES |
| Allowed IDs contract | 1200 entries (300 examples × 4 methods) |

The run used exactly the canonical Final-300 training examples as specified in the contract-matching prep files. This is not the previous nonmatched `openai_gsm8k_*` (test-split) sample.

---

## 3. Per-Method Accuracies (New Contract-Matched Live Run)

| Method | Correct | Total | Accuracy |
|---|---|---|---|
| frontier | 237 | 300 | **0.7900** |
| L1 | 239 | 300 | **0.7967** |
| S1 | 240 | 300 | **0.8000** |
| TALE | 242 | 300 | **0.8067** |
| **agreement_only** | **247** | **300** | **0.8233** |
| **pooled_4** | **257** | **300** | **0.8567** |
| oracle | 280 | 300 | 0.9333 |

---

## 4. Frozen Agreement-Only Full-Coverage Result

**Agreement-only (2-of-3 external against frontier): 247/300 = 82.33%**

Definition used:
- Default = frontier answer.
- If at least 2 of L1/S1/TALE agree on an answer that differs from frontier → select that external majority answer.
- Otherwise keep frontier.
- Every example receives a decision.

**Agreement-only vs baselines:**
- vs frontier: **+10 net** (24 recoveries, 14 regressions); delta = +3.33 pp
- vs L1: **+8 net** (wins=20, losses=12); delta = +2.67 pp
- vs S1: **+7 net** (wins=18, losses=11); delta = +2.33 pp
- vs TALE: **+5 net** (wins=13, losses=8); delta = +1.67 pp

**Bootstrap 95% CI (agreement_only vs frontier):** diff = +0.033, CI: [+0.007, +0.060] — **significant** (CI does not contain zero)  
**Bootstrap 95% CI (agreement_only vs S1):** diff = +0.023, CI straddles zero — borderline  

**FTA/FIX-2+FIX-4 replayability:** FTA requires support-awareness metadata (PRM/verifier scores) and gate decision fields. These are not present or populated in this artifact. **FTA is not replayable from this per_example_records.jsonl** — only frozen agreement-only and pooled-4 are fully replayable.

---

## 5. Pooled-4 Result

**Pooled-4 with fallback: 257/300 = 85.67%**

Definition used:
- Strict majority among all 4 (frontier/L1/S1/TALE). If majority differs from frontier, switch.
- Otherwise keep frontier.

**Pooled-4 vs baselines:**
- vs frontier: **+20 net** (22 recoveries, 2 regressions); delta = +6.67 pp
- vs agreement_only: **+10 net** (12 recoveries, 2 regressions); delta = +3.33 pp
- vs S1: **+17 net** (18 wins, 1 loss); delta = +5.67 pp

Pooled-4 is substantially better than agreement-only (10 net gain, only 2 regressions vs frontier). This suggests pooling all 4 sources — including frontier — is a much stronger policy than external-only majority.

---

## 6. Bootstrap CIs and Win/Loss/Tie (Selected)

| Comparison | Obs diff | 95% CI lo | 95% CI hi | Significant? |
|---|---|---|---|---|
| agreement_only vs frontier | +0.0333 | +0.0067 | +0.0600 | **YES** |
| pooled_4 vs frontier | +0.0667 | +0.0400 | +0.0900 | **YES** |
| pooled_4 vs agreement_only | +0.0333 | +0.0133 | +0.0533 | **YES** |
| agreement_only vs S1 | +0.0233 | -0.0033 | +0.0500 | borderline |
| agreement_only vs L1 | +0.0267 | 0.0000 | +0.0533 | borderline |

---

## 7. Old vs New Canonical Comparison

Both old (final_fix24, 2026-05-19) and new (contract-matched, 2026-05-23) runs use:
- Same provider: cohere
- Same model: command-r-plus-08-2024
- Same 300 examples: `openai_gsm8k_train_*` (300/300 overlap)
- Same seed: 71, budget: 6

| Method | Old accuracy | New accuracy | Delta (new−old) |
|---|---|---|---|
| frontier | 0.7667 (230/300) | 0.7900 (237/300) | **+0.0233** |
| L1 | 0.8300 (249/300) | 0.7967 (239/300) | **−0.0333** |
| S1 | 0.8200 (246/300) | 0.8000 (240/300) | **−0.0200** |
| TALE | 0.7833 (235/300) | 0.8067 (242/300) | **+0.0233** |

### Does the new live run reproduce old canonical numbers?

**Partially — not exact, but consistent with expected API non-determinism.**

The same 300 examples with the same model produce results that differ by 2–3 percentage points per method. This is expected because:
1. `direct_reserve_semantic_frontier_v2` uses a multi-node tree search with stochastic sampling — responses vary across runs.
2. Cohere's API is not deterministic even at temperature 0; output can vary across calls.
3. The external methods (L1, S1, TALE) also show ~2–3 pp variation consistent with stochastic API behavior.

**The differences do not indicate a bug or a change in the canonical example set** — the IDs are exactly matched. This is expected API variance across independent live runs.

**Agreement-only on old run (computed from old per_example_records):** not directly available from pre-computed summaries, but method-level changes suggest agreement-only would also shift by a similar margin (~1–3 pp).

---

## 8. Recovery/Regression Case Counts

| Case type | Count |
|---|---|
| Agreement recovers frontier errors | **24** |
| Agreement breaks frontier correct | **14** |
| Net agreement vs frontier | **+10** |
| Pooled-4 recovers frontier errors | **22** |
| Pooled-4 breaks frontier correct | **2** |
| Net pooled-4 vs frontier | **+20** |
| S1 beats agreement (S1 correct, agreement wrong) | **11** |
| Agreement beats S1 (agreement correct, S1 wrong) | **18** |
| L1+TALE agree wrong while S1 correct | **9** |
| External majority excludes correct S1 | **7** |
| Agreement keeps wrong frontier (no external majority) | **17** |

**L1+TALE correlated errors on Cohere canonical:** 9/300 = 3.0% bad L1+TALE majority rate. Compare: Mistral had 13/300 = 4.3%. The pattern is present but somewhat less frequent on Cohere.

---

## 9. Mistral-Derived Correlation-Aware Rules on Cohere Canonical

All variants are **offline/diagnostic only**. No policy was promoted.

| Rule | Accuracy | Δ vs agr-only | Recoveries | Regressions | Verdict |
|---|---|---|---|---|---|
| frontier | 0.7900 | −0.0333 | 14 | 24 | baseline |
| L1 | 0.7967 | −0.0267 | 12 | 20 | baseline |
| S1 | 0.8000 | −0.0233 | 11 | 18 | baseline |
| TALE | 0.8067 | −0.0167 | 8 | 13 | baseline |
| agreement_only | 0.8233 | 0 | — | — | baseline |
| pooled_4 | 0.8567 | **+0.0333** | 12 | 2 | baseline |
| `agreement_downweight_lt_if_frontier_disagrees_and_s1_clean` | **0.8300** | **+0.0067** | 7 | 5 | **transfers_positively** |
| `agreement_choose_s1_when_lt_against_s1_and_s1_clean` | 0.8067 | −0.0167 | 9 | 14 | **harms_cohere** |
| `clean_numeric_s1_override` | 0.8000 | −0.0233 | 11 | 18 | **harms_cohere** |
| `always_s1_provider_prior` (Mistral-specific reference) | 0.8000 | −0.0233 | 11 | 18 | **harms_cohere** |
| `source_family_vote_L1TALE_family_plus_S1_plus_frontier` | **0.8367** | **+0.0133** | 14 | 10 | **transfers_positively** |
| oracle | 0.9333 | +0.1100 | 33 | 0 | ceiling |

### Key findings on Cohere canonical:

1. **`agreement_downweight_lt_if_frontier_disagrees_and_s1_clean`**: +0.67 pp gain (249/300), 7 recoveries, 5 regressions. **Transfers positively** to Cohere canonical. Net +2 cases.

2. **`source_family_vote_L1TALE_family_plus_S1_plus_frontier`**: +1.33 pp gain (251/300), 14 recoveries, 10 regressions. **Transfers positively.** Best of the diagnostic variants, but regressions are substantial.

3. **`agreement_choose_s1_when_lt_against_s1_and_s1_clean`**: −1.67 pp (242/300). **Harms Cohere** — 14 regressions vs only 9 recoveries. This rule over-overrides to S1 on cases where S1 is clean but agreement-only was already choosing the right answer.

4. **`clean_numeric_s1_override`** and **`always_s1`**: Both produce 240/300 = 0.80, the same as raw S1. **Harm Cohere** by discarding agreement benefits.

5. **Pooled-4 dominates all diagnostic variants** (257/300 = 85.67%), with only 2 regressions vs frontier. It is the strongest policy evaluated and does not require any Mistral-specific tuning.

---

## 10. Algorithm Recommendation

### Main findings:

1. **Agreement-only (82.33%) beats all individual methods** and is validated on contract-matched Cohere canonical Final-300.

2. **Pooled-4 (85.67%) substantially outperforms agreement-only** (+3.33 pp, only 2 regressions vs frontier). If the frontier method can be included in the pooling vote at runtime, pooled-4 is the stronger policy.

3. **L1+TALE correlated errors on Cohere canonical: 9/300 = 3.0%** (vs 13/300 = 4.3% on Mistral). The pattern is present but smaller.

4. **Safe transfer candidates** from Mistral to Cohere canonical:
   - `agreement_downweight_lt_if_frontier_disagrees_and_s1_clean`: net +2 cases, transfers positively
   - `source_family_vote`: net +4 cases, transfers positively but with 10 regressions
   - Both are smaller gains than pooled-4

5. **Harmful rules on Cohere canonical:** `agreement_choose_s1_when_lt_against_s1_and_s1_clean`, `clean_numeric_s1_override`, `always_s1`. These aggressively override to S1 and lose the agreement benefit.

### Recommendation:

- **Primary algorithm:** `pooled_4_with_fallback` is the strongest evaluated policy (85.67%), provider-agnostic, and has only 2 regressions vs frontier.
- **Secondary/conservative:** `agreement_only_2of3_against_frontier` (82.33%) as a robust fallback if frontier vote cannot be included at inference time.
- **Next validation needed:** Run pooled-4 on Cerebras when the Cerebras job completes. If pooled-4 also outperforms agreement-only on Cerebras, it should be the promoted algorithm.
- **Mistral-derived rules:** `agreement_downweight_lt_if_frontier_disagrees_and_s1_clean` is safe across Mistral + nonmatched Cohere + contract-matched Cohere canonical, but the gain is small (+0.67 pp on canonical). Not worth promoting over pooled-4.

---

## 11. Cerebras Current Status (Non-Invasive Monitor)

| Field | Value |
|---|---|
| Cerebras per_example count | **165** (was 164 at prior check; progressed +1) |
| Last heartbeat | `example_start` for attempt 166, scored=164 |
| Log last modified | 2026-05-23T22:03:55Z |
| Time since log update | ~7 min (at time of check) |
| Status | **RESUMED — no longer stalled** |

**The Cerebras job recovered from its ~52-minute stall.** It processed `openai_gsm8k_164` (the example it was stuck on) and moved on to example 165. The job is alive and progressing, though slowly (~1 min/example on frontier method).

Remaining work on Cerebras: ~136 examples on method 1 (frontier) + 300×3 examples on methods 2–4 = ~1036 examples remaining. At ~60–120s/example on frontier, completion of method 1 is expected in ~2–3 more hours. Methods 2–4 (L1/S1/TALE) are typically faster.

**Do not touch the Cerebras job.**

---

## Constraints Confirmed

- No API calls were made.
- Cerebras job (PID 2195513) was not touched, killed, restarted, interrupted, or attached to.
- Frozen policy logic was not modified.
- No replay was run on Cerebras.
- No new policies were promoted.
- No existing artifacts were overwritten.
- All diagnostic variants are labeled offline/diagnostic only.
