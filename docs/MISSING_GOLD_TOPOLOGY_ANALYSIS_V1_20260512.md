# Missing Gold Topology Analysis v1
**Date:** 2026-05-12  
**Script:** `scripts/analyze_missing_gold_topology_v1.py`  
**Primary outputs:** `outputs/missing_gold_topology_v1_20260512T231513Z/` (heuristic) and `outputs/missing_gold_topology_v1_20260512T231758Z/` (API-assisted, audited final bundle)

## Why "gold absent" is insufficient

`gold absent from candidate pool` is too coarse for next-method decisions. It tells us the selector cannot recover the answer, but it does not tell us:

- which explored node was closest to the correct target
- whether the tree already contained the needed quantities or formulas
- whether the miss was one target-binding edge away or several relation-construction steps away
- whether the right next intervention is selector rebinding, unit conversion, equation setup, or new candidate generation

This analysis reframes each case as a **missing-edge / topology** diagnosis rather than a binary gold-present / gold-absent tag.

## Framework

Per case, the script unions evidence from:

- `/tmp/codex_pattern_mining_wrong_consensus_97_packets/trace_packets.jsonl`
- `outputs/bftc_live_pilot_v1_20cases_20260512T210634Z/`
- `outputs/bftc_executable_repair_v1_live_20cases_20260512T221521Z/`
- `outputs/bftc_candidate_rebinding_selector_v1_20260512T224257Z/`
- `docs/project_handoff_20260510/exhaustive_failure_audit/gold_absent_subpattern_analysis_20260510.csv`

For each case it records:

- explored numeric candidates plus provenance / branch-family hints
- closest numeric and semantic node to gold
- a controlled `missing_edge_type`
- a `tree_topology_label`
- estimated steps from the closest explored node to gold
- whether existing variables / formulas appear sufficient for deterministic local repair
- whether a genuinely new model generation edge is still needed

## Taxonomy

Implemented `missing_edge_type` values:

- `target_rebinding`
- `inverse_state_transition`
- `difference_to_total`
- `total_to_difference`
- `per_unit_to_total`
- `total_to_per_unit`
- `ratio_base_correction`
- `percentage_base_correction`
- `unit_conversion`
- `profit_to_sale_price`
- `sale_price_to_profit`
- `original_before_process`
- `final_after_process`
- `equation_setup_missing`
- `source_fact_missing`
- `relation_composition_missing`
- `arithmetic_precision`
- `prompt_gold_inconsistent`
- `selector_rebinding`
- `unknown`

Topology labels:

- `wrong_target_basin_collapse`
- `diverse_wrong_pool`
- `near_miss_pool`
- `missing_source_fact`
- `missing_relation_composition`
- `selector_only_failure`
- `prompt_gold_inconsistent`
- `unknown`

## Two Modes

### 1. Heuristic mode

Default, no API. Uses numeric distance, question text, BFTC postmortems, executable-repair postmortems, formula-variable sufficiency, and rebinding-pool evidence.

20-case heuristic result:

| Metric | Count |
|---|---:|
| `prompt_gold_inconsistent` | 6 |
| `selector_rebinding` | 5 |
| `percentage_base_correction` | 2 |
| `unit_conversion` | 2 |
| `deterministic_local_repair_possible` | 18 |
| `new_model_generation_needed` | 2 |

This pass is useful as a cheap first cut, but it over-attributes some cases to selector-only recovery because it sees the full offline union of BFTC-only, executable, and rebinding artifacts.

### 2. API-assisted diagnostic mode

Enabled only with:

```bash
--allow-api-diagnostic-labeling --allow-gold-in-analysis-api
```

The prompt is explicitly marked:

- `analysis_only_gold_conditioned=true`
- `not_for_runtime=true`
- `not_for_provider_request_reuse=true`

The gold-conditioned prompt is allowed here only for offline error localization. It must not be reused as a future candidate-generation or provider-runtime prompt.

Final audited API bundle:

- output dir: `outputs/missing_gold_topology_v1_20260512T231758Z/`
- parsed labels: `20/20`
- prompt audit violations: `0`
- all 20 prompts marked analysis-only, not-for-runtime, and not-for-reuse

## API-Assisted 20-Case Counts

### Missing-edge counts

| Missing edge | Count |
|---|---:|
| `relation_composition_missing` | 7 |
| `prompt_gold_inconsistent` | 5 |
| `final_after_process` | 4 |
| `arithmetic_precision` | 3 |
| `unit_conversion` | 1 |

Case IDs by dominant API-assisted label:

- `relation_composition_missing`: `openai_gsm8k_1003`, `openai_gsm8k_1006`, `openai_gsm8k_1021`, `openai_gsm8k_162`, `openai_gsm8k_180`, `openai_gsm8k_190`, `openai_gsm8k_262`
- `prompt_gold_inconsistent`: `openai_gsm8k_1035`, `openai_gsm8k_1069`, `openai_gsm8k_213`, `openai_gsm8k_228`, `openai_gsm8k_239`
- `final_after_process`: `openai_gsm8k_1029`, `openai_gsm8k_184`, `openai_gsm8k_22`, `openai_gsm8k_233`
- `arithmetic_precision`: `openai_gsm8k_1025`, `openai_gsm8k_1027`, `openai_gsm8k_166`
- `unit_conversion`: `openai_gsm8k_183`

### Needed branch-family counts

| Branch family | Count |
|---|---:|
| `relation_verifier` | 6 |
| `declarative_equation_branch` | 2 |
| `backward_from_target_check` | 1 |
| `unit_conversion_branch` | 1 |
| `other` | 10 |

### Distance-to-gold on the combined offline artifact pool

| Estimated steps | Count |
|---|---:|
| `0` | 18 |
| `1` | 2 |

Important caveat:
These `0-step` labels are **offline union-pool labels**, not runtime evidence. In many cases the exact answer appears only after combining BFTC-only outputs, executable results, formula-variable values, or rebinding artifacts. This should not be read as proof that the original live runtime already had the gold answer in its explored tree.

## What Dominates

The main API-assisted story on this 20-case slice is:

1. **Relation composition dominates.** The largest bucket is not arithmetic execution failure by itself. It is failure to compose the right relation from already available quantities.
2. **Prompt/gold inconsistency remains a real confounder.** Five cases look mismatched at the prompt surface and should be quarantined from clean live gating.
3. **State-target mistakes are still material.** Four cases are after-state / final-state binding failures rather than missing raw arithmetic capability.
4. **Pure arithmetic repair exists, but it is a minority.** Only three cases land in `arithmetic_precision`.

## How This Changes The Next Method Decision

This analysis pushes the next-method priority toward:

1. `relation_verifier`
   Validate whether the candidate or formula preserves the intended relation structure before trusting it.

2. `declarative_equation_branch`
   Especially for age systems, circular percentage bills, and multi-relation setup failures.

3. explicit final-state / target binding checks
   The `final_after_process` cluster says we still need target-sensitive profit / remaining / after-state validation.

4. quarantine prompt/gold mismatches before more live gating
   The five inconsistent cases should not be used as clean success/failure evidence for runtime promotion.

Lower priority from this slice:

- pure selector-rebinding as the headline next fix
- another prompt-only BFTC rerun

The heuristic run surfaced selector-only recoveries in the offline union pool, but the gold-conditioned API labels re-centered the diagnosis on **relation construction and state-target binding**, which is the more actionable design signal for new runtime work.

## Gold-Conditioned Prompt Policy

The analysis-only API prompts differ from future runtime/provider prompts in three ways:

1. They may include the gold answer, but only under `--allow-gold-in-analysis-api`.
2. They are written to `api_diagnostic_prompts.jsonl` and audited in `prompt_audit.json`.
3. They are explicitly barred from runtime use or provider-request reuse.

That boundary is part of the artifact and should stay explicit.

## Files Added By This Work

- `scripts/analyze_missing_gold_topology_v1.py`
- `tests/test_missing_gold_topology_analysis_v1.py`
- `docs/MISSING_GOLD_TOPOLOGY_ANALYSIS_V1_20260512.md`

## Recommended Immediate Follow-up

- Build the next offline `relation_verifier` scaffold against the 7 `relation_composition_missing` cases.
- Keep `unit_conversion_branch` as a narrow sidecar, not the primary direction.
- Separate the 5 prompt/gold inconsistent cases from the clean topology slice before any new live capped pilot.
- Treat the 18 zero-step offline cases as **artifact-localization evidence only**, not runtime promotion evidence.
