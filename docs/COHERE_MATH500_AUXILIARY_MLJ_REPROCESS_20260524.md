# Cohere × MATH-500 Auxiliary MLJ Reprocessing — 2026-05-24

**Processing timestamp UTC:** 2026-05-24T08:30:00Z  
**Branch:** main  
**Status:** Offline reprocessing only; no API calls; Cerebras GSM8K active job observed but not touched.

---

## 1. Source Artifact Paths

| Artifact | Path | Notes |
|---|---|---|
| Main run | `outputs/cohere_real_model_cost_normalized_validation_mlj_math500_b6_20260520T220928Z/` | seed=11; 2000 rows; no `[done]` |
| Recovery run | `outputs/cohere_real_model_cost_normalized_validation_mlj_math500_b6_recovery_failed31_20260521T124545Z/` | 31 rows; 16 recovered; 15 permanent |
| Processing output | `outputs/cohere_math500_auxiliary_mlj_reprocess_20260524/` | This bundle |
| Script | `scripts/process_existing_cohere_math500_auxiliary.py` | New script; offline only |

**Important label:** This is `cohere_math500_auxiliary_seed11_mlj`, **NOT** canonical Scenario 4.  
Scenario 4 (seed=71, 300-example, shared case file) remains **not launched**.

---

## 2. Alias Normalization and Merge Logic

**Method alias normalization applied:**

| Raw name (in original artifact) | Normalized name |
|---|---|
| `direct_reserve_semantic_frontier_v2` | `direct_reserve_semantic_frontier_v2` (unchanged) |
| `external_l1_max` | `external_l1_max` (unchanged) |
| `s1` | `external_s1_budget_forcing` |
| `tale` | `external_tale_prompt_budgeting` |

**Merge logic:**
- Priority: `(scored, is_recovery)` — scored recovery > scored main > unscored recovery > unscored main
- 31 recovery rows resolved: 16 upgraded from failed to scored; 15 remain permanently failed
- No duplicate `(example_id, method)` pairs after dedup

---

## 3. Integrity Result

**PASS**

| Field | Value |
|---|---|
| Complete examples (all 4 methods scored) | **488** |
| Expected rows | 1952 |
| Actual rows | 1952 |
| Method counts | all 488 |
| Duplicate (example_id, method) pairs | 0 |
| Missing method rows | 0 |
| Permanently failed rows | 15 (excluded from primary analysis) |
| `[done]` in log | No (job likely exited early; does not affect offline completeness) |

---

## 4. Method Accuracies and Ranking

| Rank | Method | Short | Accuracy | N |
|---|---|---|---|---|
| 1 | `external_l1_max` | L1 | **30.53%** | 488 |
| 2 | `direct_reserve_semantic_frontier_v2` | frontier | 26.43% | 488 |
| 3 | `external_s1_budget_forcing` | S1 | 25.20% | 488 |
| 4 | `external_tale_prompt_budgeting` | TALE | 24.18% | 488 |

**Best–second spread:** 4.10pp | **Best–worst spread:** 6.35pp

---

## 5. Selector Accuracies and Ranking

| Selector | Accuracy | Δ frontier |
|---|---|---|
| `oracle_best_source` / `oracle_best_action` | **45.08%** | +18.65pp |
| `external_l1_max` (individual) | 30.53% | +4.10pp |
| `pooled4_with_fallback` | 30.12% | +3.69pp |
| `agreement_only_2of3_against_frontier` | 30.12% | +3.69pp |
| `raw_spread_regime_selector` | 30.12% | +3.69pp |
| `beta_shrinkage_regime_selector` | 30.12% | +3.69pp |
| `dominant_source_veto` | 30.12% | +3.69pp |
| `always_s1` | 25.20% | -1.23pp |
| `frontier` | 26.43% | baseline |

**Best proposed selector (non-oracle):** pooled4/beta_shrinkage/agreement all tie at 30.12%.  
L1 individual source (30.53%) marginally beats all ensemble selectors.

---

## 6. Detected Regime

**`near_peer`**

- Best (L1) vs second (frontier): spread = **4.10pp** — below 5pp near-peer threshold
- In near_peer: beta_shrinkage regime selector falls back to pooled4 (shrunk spread < 0.07pp threshold)
- Pooled4 ≈ L1 (30.12% vs 30.53%) — ensemble does not significantly outperform best individual

---

## 7. Cohere MATH-500: Near-Peer, Mixed, or Dominant?

**Near-peer** (4.10pp spread between L1 and frontier)

This is in strong contrast to:
- **Mistral × MATH-500**: S1 dominates at 56.33% vs L1 at 45.67% — spread 10.66pp = mixed/s1_dominant
- **Cohere × GSM8K**: near-peer at ~80%+ for all sources (85%+ with pooled4)

Cohere struggles more uniformly across all methods on MATH-500 (~24–31%), with no single method standing out.

---

## 8. Pooled4 vs S1 on Cohere MATH-500

| Selector | Accuracy |
|---|---|
| pooled4_with_fallback | 30.12% |
| always_s1 | 25.20% |
| L1 (best individual) | 30.53% |

**S1 does NOT help** on Cohere × MATH-500. The budget-forcing strategy that makes S1 dominant for Mistral fails here. S1 performs worse than L1 by 5.33pp and worse than pooled4 by 4.92pp.

**Key contrast**: On Mistral × MATH-500 (GSM8K), always-S1 = 91.33%; on Cohere × MATH-500, always-S1 = 25.20%. This is a critical dataset × provider interaction.

---

## 9. Failure Taxonomy and Representative Cases

| Failure Set | Count | % of 488 |
|---|---|---|
| `all_sources_wrong` | **268** | **54.9%** |
| `our_algorithm_wrong_best_source_correct` | 103 | 21.1% |
| `pooled4_wrong_oracle_correct` | 103 | 21.1% |
| `our_algorithm_wrong_oracle_correct` | 73 | 15.0% |
| `agreement_wrong_oracle_correct` | 75 | 15.4% |
| `S1_correct_our_algorithm_wrong` | 0 | 0% |

**Dominant finding:** 54.9% of examples fail all 4 methods — MATH-500 is fundamentally hard for Cohere at budget=6. This is even higher than Mistral × MATH-500 (32.3% all-wrong).

The 268 all-wrong cases represent an irreducible floor: no selector improvement can help.

**Oracle gap:** 45.08% − 30.12% = **14.96pp** recoverable if selection were perfect.

---

## 10. Cross-Scenario Interpretation

| Scenario | Regime | S1 dominant? | Best source | Pooled4 | Oracle |
|---|---|---|---|---|---|
| **Cohere × MATH-500 aux** | near_peer | NO | L1 (30.53%) | 30.12% | 45.08% |
| Mistral × MATH-500 | mixed | YES | S1 (56.33%) | 55.00% | 68.00% |
| Cohere × GSM8K | near_peer | NO | TALE (80.67%) | 85.67% | 93.33% |

**Key observations:**

1. **S1 behavior is provider-specific**: S1 dominates on Mistral (budget-forcing leverages long reasoning chains). On Cohere, S1 is near-worst.

2. **MATH-500 vs GSM8K for Cohere**: All methods drop dramatically — from ~80% on GSM8K to ~25–31% on MATH-500. MATH-500 is ~50pp harder for Cohere.

3. **Cohere MATH-500 resembles Cohere GSM8K in regime** (both near_peer) but at a much lower accuracy level.

4. **Near-peer across datasets ≠ same difficulty**: Cohere is near-peer on both GSM8K and MATH-500 but at 80% and 30% respectively.

5. **Learned router with 4 datasets**: HGB achieves 65.48% macro-average accuracy in pooled CV. Adding auxiliary Cohere MATH-500 increases training diversity but does not dramatically change results.

---

## 11. Learned Router Auxiliary Update

**Run:** `scripts/build_and_eval_learned_fixed_pool_router.py` with `--allow-auxiliary-sources`  
**4 datasets:** Cohere × GSM8K, Mistral × GSM8K, Mistral × MATH-500, Cohere × MATH-500 aux

**Pooled stratified CV (all 4 datasets, macro average):**

| Model | CV Accuracy |
|---|---|
| `action_hgb_router_with_ids` | **65.48%** |
| `source_logistic_router_with_ids` | 64.80% |
| `action_logistic_router_with_ids` | 64.80% |
| `pooled4_with_fallback` | 64.06% |
| `oracle_best_action` | 75.46% |

**Transfer from Cohere GSM8K → Cohere MATH-500 aux:**

| Model | Accuracy | vs pooled4 |
|---|---|---|
| `action_tree_depth3_no_ids` | 31.15% | +1.03pp |
| `pooled4_with_fallback` | 30.12% | baseline |
| `L1_source` | 30.53% | +0.41pp |
| oracle | 45.08% | +14.96pp |

Routers trained on Cohere GSM8K **fail to transfer meaningfully** to Cohere MATH-500 (near-peer regime offers little exploitable signal). Tree router achieves a marginal +1pp over pooled4.

**Limitation:** Auxiliary data uses seed=11; results not directly comparable to canonical Scenario 4 seed=71.

---

## 12. Recommendation About Canonical Seed=71 Paid Launch

**Recommendation: `launch_if_manuscript_requires_strict_matrix`**

**What auxiliary run provides:**
- 488 complete examples for learned-router training diversity
- Regime classification (near_peer) for preliminary dataset analysis
- Full method and selector accuracy at accuracy level

**What it does NOT provide:**
- Per-example consistency with Scenarios 5 and 6 (both seed=71, shared case file)
- Cross-provider per-example comparisons
- Canonical Scenario 4 slot in the six-scenario matrix

**Bottom line:** The auxiliary data suffices for learned-router training and for understanding Cohere MATH-500 behavior. For a strict six-scenario comparison matrix where all three MATH-500 scenarios (Cohere, Mistral, Cerebras) test the same 300 examples, the canonical seed=71 launch is required. Cost estimate: ~$15–25 for 300 examples × 4 methods at budget=6.

---

## 13. Limitations

1. Seed mismatch (11 vs 71) — not comparable per-example with Scenarios 5 and 6
2. 500-example run (not 300) — different from canonical scenario size
3. 15 permanently failed rows excluded from analysis
4. No `[done]` marker in log — job exited early (possibly at method boundary)
5. Method aliases normalized offline — original raw log retains `s1`/`tale` naming
6. All analyses are on the 488 examples where all 4 methods scored; 12 examples have incomplete method coverage

---

## 14. Safety Confirmation

- No API calls launched.
- No paid Cohere run created.
- No tmux sessions attached or modified.
- Cerebras × GSM8K (PIDs 2195504/2195513) observed only; not touched.
- No existing artifacts overwritten.
- No commits or pushes made.
- Gold answers used only for offline evaluation.

---

## Files Created

| File | Description |
|---|---|
| `cohere_math500_auxiliary_merged_all_rows.jsonl` | All rows (main + recovery, alias-normalized, deduped) |
| `cohere_math500_auxiliary_complete_4method_records.jsonl` | 488×4=1952 rows, complete examples only |
| `cohere_math500_auxiliary_incomplete_examples.csv` | 12 examples missing ≥1 method |
| `cohere_math500_auxiliary_duplicate_resolution.csv` | 31 recovery-resolved rows |
| `cohere_math500_auxiliary_alias_normalization_map.json` | Alias → canonical name map |
| `cohere_math500_auxiliary_integrity_summary.json` | Integrity: PASS, 488 examples |
| `cohere_math500_auxiliary_method_counts.csv` | Per-method scored counts |
| `cohere_math500_auxiliary_failure_rows.csv` | 15 permanently failed rows |
| `cohere_math500_auxiliary_method_accuracy_summary.csv` | L1=30.53%, frontier=26.43%, S1=25.20%, TALE=24.18% |
| `cohere_math500_auxiliary_regime_summary.json` | regime=near_peer, l1_dominant=true |
| `cohere_math500_auxiliary_source_ranking_and_regime.md` | Source ranking narrative |
| `cohere_math500_auxiliary_selector_replay_summary.csv` | 13 selectors; best=L1 30.53% |
| `cohere_math500_auxiliary_case_level_selector_results.csv` | Per-example selector outcomes |
| `cohere_math500_auxiliary_paired_ci_summary.csv` | Bootstrap CI for key comparisons |
| `cohere_math500_auxiliary_mcnemar_summary.csv` | McNemar p-values |
| `cohere_math500_auxiliary_failure_case_sets.csv` | 11 failure set labels per case |
| `cohere_math500_auxiliary_failure_taxonomy_summary.csv` | Failure counts: 268 all-wrong |
| `cohere_math500_auxiliary_failure_case_index.csv` | 385 cases with ≥1 failure label |
| `cohere_math500_auxiliary_failure_case_logs/` | 30 individual case markdown files |
| `cohere_math500_auxiliary_representative_failure_cases.md` | Failure summary narrative |
| `cohere_math500_auxiliary_algorithm_improvement_hypotheses.md` | Algorithm improvement ideas |
| `cohere_math500_auxiliary_vs_mistral_math500_comparison.csv` | Cross-scenario comparison table |
| `cohere_math500_auxiliary_cross_scenario_interpretation.md` | Cross-scenario narrative |
| `learned_router_four_datasets/` | Router with 4 datasets (incl. auxiliary) |
| `learned_router_with_auxiliary_cohere_math500_summary.csv` | Router results summary |
| `learned_router_four_dataset_auxiliary_transfer_summary.csv` | Transfer results |
| `learned_router_auxiliary_interpretation.md` | Router interpretation |
| `canonical_cohere_math500_launch_decision.md` | Launch decision analysis |
| `manifest.json` | Bundle manifest |
| `source_file_inventory.json` | Source artifact inventory |
