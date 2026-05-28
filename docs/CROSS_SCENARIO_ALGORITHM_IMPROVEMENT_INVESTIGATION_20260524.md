# Cross-Scenario Algorithm Improvement Investigation — 2026-05-24

> Generated: 2026-05-24T13:26:59Z | Offline analysis only — no API calls, no active job interference.

---

## 1. Executive Summary

Three official canonical scenarios are complete and processed: Cohere × GSM8K, Mistral × GSM8K, and Mistral × MATH-500. One auxiliary development run exists for Cohere × MATH-500 (seed=11, non-canonical). Cerebras × GSM8K is actively running (~43% complete).

**Key finding:** A single static selector cannot achieve best performance across all provider×dataset regimes. Two distinct regimes have been identified and confirmed:

- **Near-peer (Cohere):** Sources are similarly accurate; aggregation (pooled4) beats all individuals by 5–7pp.
- **S1-dominant (Mistral):** Budget-forcing (S1) outperforms pooled4 by 5.6pp on GSM8K.

The **beta-shrinkage regime selector achieves best-or-tied-best performance on all 4 scenarios** (3 official + 1 auxiliary). The learned router prototype is promising but not yet statistically superior to beta-shrinkage.

The major remaining question is: **which regime does Cerebras fall into?**

---

## 2. Data Sources and Caveats

| Scenario | Provider | Dataset | N | Type | Status |
|---|---|---|---|---|---|
| Cohere GSM8K | cohere | GSM8K | 300 | **Official** | Complete + Processed |
| Mistral GSM8K | mistral | GSM8K | 300 | **Official** | Complete + Processed |
| Mistral MATH-500 | mistral | MATH-500 | 300 | **Official** | Complete + Processed |
| Cohere MATH-500 | cohere | MATH-500 | 488 | **Auxiliary★** | Complete + Processed |
| Cerebras GSM8K | cerebras | GSM8K | — | Pending | Running (~43%) |
| Cerebras MATH-500 | cerebras | MATH-500 | — | Pending | Queued |

★ **Cohere MATH-500 is auxiliary (seed=11). Not canonical Scenario 4. Use for training/development only.**

---

## 3. Unified Scenario Performance

| Scenario | frontier | L1 | S1 | TALE | pooled4 | beta-shrink | oracle | Oracle gap | Regime |
|---|---|---|---|---|---|---|---|---|---|
| Cohere GSM8K | 79.0% | 79.7% | 80.0% | 80.7% | **85.7%** | **85.7%** | 93.3% | 7.6pp | near-peer |
| Mistral GSM8K | 78.7% | 72.7% | **91.3%** | 67.0% | 85.7% | **91.3%** | 94.0% | 2.7pp vs S1 | S1-dominant |
| Mistral MATH-500 | 40.0% | 45.7% | **56.3%** | 48.0% | 55.0% | **56.3%** | 67.7% | 11.3pp | S1-dominant |
| Cohere MATH-500★ | 26.4% | **30.5%** | 25.2% | 24.2% | 30.1% | 30.1% | 45.1% | 15.0pp | near-peer |

All-sources-wrong rates:
- Cohere GSM8K: ~6.7%
- Mistral GSM8K: ~6.0%
- **Mistral MATH-500: 32.3%**
- **Cohere MATH-500 aux: 54.9%**

---

## 4. Regime Analysis

**Provider effect dominates dataset effect.** Cohere is near-peer on both GSM8K and MATH-500. Mistral is S1-dominant on both. Dataset (GSM8K vs MATH-500) changes absolute difficulty but not regime type.

**Key asymmetry:**
- On Cohere, budget-forcing (S1) offers no advantage — S1 ≈ frontier ≈ L1 ≈ TALE
- On Mistral, S1 dominates by 12.7pp over frontier (GSM8K) and 8.3pp over second-best (MATH-500)
- On Cohere MATH-500 aux, S1 is actually **worse** than L1 (25.2% vs 30.5%)

**Beta-shrinkage correctly identifies regime in all 4 scenarios:**
- Cohere → aggregation (pooled4) — correct
- Mistral GSM8K → S1 — correct
- Mistral MATH-500 → S1 — correct
- Cohere MATH-500 aux → aggregation — correct

---

## 5. Algorithm Comparison

**Winners by scenario:**

| Scenario | Best algorithm | Runner-up | Margin |
|---|---|---|---|
| Cohere GSM8K | pooled4 = beta-shrinkage (85.7%) | agreement-only (82.3%) | +3.4pp |
| Mistral GSM8K | always-S1 = beta-shrinkage (91.3%) | pooled4_cal (89.0%) | +2.3pp |
| Mistral MATH-500 | always-S1 = beta-shrinkage (56.3%) | pooled4 (55.0%) | +1.3pp (tied by McNemar) |
| Cohere MATH-500 aux | L1 (30.5%) ≈ pooled4 (30.1%) = beta-shrink (30.1%) | — | ~0.4pp |

**Key comparisons:**
- **Pooled4 vs frontier** on Cohere GSM8K: +6.7pp (p<0.001) — strongest positive result
- **S1 vs pooled4** on Mistral GSM8K: +5.6pp (p~0.05) — beta-shrinkage recovers this
- **S1 vs pooled4** on Mistral MATH-500: +1.3pp (p=1.0 McNemar — tied)
- **Pooled4 vs always-S1** on Cohere MATH-500 aux: +4.9pp (S1 bad on Cohere MATH-500)
- **Learned router vs pooled4** on transfer: +1.0pp (not significant)

---

## 6. Failure Taxonomy Comparison

| Failure mode | Cohere GSM8K | Mistral GSM8K | Mistral MATH-500 | Cohere MATH-500 aux |
|---|---|---|---|---|
| All-sources-wrong | 6.7% | 6.0% | **32.3%** | **54.9%** |
| Selector fixable (oracle gap) | 7.6pp | 2.7pp | 11.3pp | 15.0pp |
| S1 uniquely correct / selector wrong | ~6% | **~5.7%** | ~0% | ~4.1% |
| Pooled4 outvotes dominant source | low | **~5.7%** | ~0% | low |
| Frontier correct / selector wrong | ~6.3% | ~1% | ~2.7% | ~1.6% |
| No-majority fallback wrong | few | 2.7% | moderate | **58.4%** |

**Dominant failure on MATH-500:** All-sources-wrong (32–55%). No routing algorithm can address this. The increase in oracle gap from GSM8K to MATH-500 is primarily hardness-driven, not selector-driven.

**Most actionable failure:** Pooled4 outvoting dominant S1 on Mistral (~5.7%). Beta-shrinkage already handles this at the scenario level. Case-level routing could recover additional gains.

---

## 7. Mechanism Findings

1. **Aggregation wins when sources are independent and near-peer.** Error diversity in near-peer regimes means majority vote corrects individual mistakes (22 wins vs 2 losses for pooled4/frontier on Cohere GSM8K).

2. **Budget-forcing (S1) wins when the provider responds strongly.** Mistral's instruction-following translates structured budget prompts into better final answers. Cohere does not show this effect.

3. **S1 is actively harmful for Cohere MATH-500** (25.2% vs L1 30.5%). Likely cause: Cohere's MATH-500 reasoning quality is similar across prompt styles — budget-forcing adds noise without improving reasoning.

4. **Beta-shrinkage correctly detects regime** by comparing cross-validated source accuracy intervals. The intervals for S1 vs others are non-overlapping on Mistral (both folds), overlapping on Cohere.

5. **The oracle gap on MATH-500 is mostly a hardness problem, not a routing problem.** On Cohere MATH-500 aux, 268/488 = 55% of examples are unsolvable by any source. The 15pp oracle gap is not a routing opportunity — it's a generation ceiling.

6. **The learned router is directionally positive but not yet significant.** Cross-scenario transfer shows +1pp (action tree) over pooled4. The fundamental bottleneck is training data size (~153 routing-decisive examples total).

---

## 8. Algorithm Improvement Candidates

| Candidate | Expected gain | Priority |
|---|---|---|
| C1: Reliability-gated pooled voting | 2-5pp | **High** |
| C2: Action-level router v2 (HGB + regime prior) | 2-5pp | **High** |
| C3: Oracle-gap targeting | 2-4pp | Medium |
| C4: S1-trust gate | 1-2pp | Medium |
| C5: No-majority fallback learner (provider-aware) | 1-3pp | Medium |
| C6: Family/dependence-aware voting | <1pp | Low |
| C7: Hardness-aware abstain for MATH-500 | 0pp acc (calibration) | Low |

Most impactful near-term: **C1 (gated pooling, offline, no API)** and **C2 (router v2, needs more data)**.

---

## 9. Learned Router Data Assessment

| Scenario | N | Routeable | Routing-decisive | Oracle gap |
|---|---|---|---|---|
| Cohere GSM8K | 300 | 93.3% | ~23 | 7.6pp |
| Mistral GSM8K | 300 | 94.0% | ~17 | 2.7pp |
| Mistral MATH-500 | 300 | 67.7% | ~40 | 11.3pp |
| Cohere MATH-500★ | 488 | 45.1% | ~73 | 15.0pp |
| **Total** | **1,388** | **71%** | **~153** | ~9.2pp |

**Current data is insufficient for strong learned-router generalization claims** (~153 routing-decisive examples total). Sufficient for prototype demonstration. Need 5-6 canonical scenarios and/or large auxiliary runs for confident claims.

---

## 10. Official vs Auxiliary Evidence

**Official (usable for paper claims):**
- Cohere GSM8K (Scenario 2)
- Mistral GSM8K (Scenario 3)
- Mistral MATH-500 (Scenario 5)

**Auxiliary (training only, not official):**
- Cohere MATH-500 (seed=11, Scenario 4 not official)
- 4-dataset learned router (includes auxiliary data)

**Pending:**
- Cerebras GSM8K (Scenario 4 → becomes official when complete)
- Cerebras MATH-500 (Scenario 6)

---

## 11. Recommended Next Experiments

**Immediate (no action needed — auto-managed):**
1. Wait for Cerebras GSM8K completion (~May 25 01:00–03:00 UTC)
2. Supervisor will process and launch Cerebras MATH-500

**Decision needed now:**
3. Decide whether to launch canonical Cohere MATH-500 (seed=71) for official Scenario 4

**Offline (can start now):**
4. Implement reliability-gated pooled voting (Candidate C1)
5. Implement provider-aware no-majority fallback (Candidate C5)

**After Cerebras GSM8K processed:**
6. Rebuild learned router to 5-dataset; train HGB router v2

---

## 12. Manuscript Readiness

**Can claim now (strong evidence):**
- Fixed-pool routing is necessary; no static selector is best across regimes
- Cohere near-peer → aggregation wins by 5.7pp
- Mistral S1-dominant → always-S1 wins by 5.6pp
- MATH-500 increases all-wrong rate (32.3%) and oracle gap; this is hardness-driven
- Beta-shrinkage achieves best-or-tied-best on all 3 official scenarios

**Cannot claim yet:**
- Learned router is universally best (evidence not significant)
- 6-scenario generality (Cerebras pending)
- Canonical Cohere MATH-500 result (only auxiliary exists)
- Cerebras regime classification
- SOTA benchmark performance

---

## 13. Safety Confirmation

- No TMUX sessions were attached to.
- No active jobs (Cerebras GSM8K PID 2195513, Supervisor PID 2361455) were modified.
- No API calls were launched.
- No original result files were overwritten.
- No commits or pushes were made.
- All analysis was read-only with new files written only to `outputs/cross_scenario_algorithm_improvement_investigation_20260524/`.
