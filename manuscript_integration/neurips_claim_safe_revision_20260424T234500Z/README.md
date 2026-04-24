# NeurIPS claim-safe revision integration package (20260424T234500Z)

## Purpose
This package converts existing audit and experiment artifacts into manuscript-ready, claim-safe text and tables.

## Claim disposition summary

### Safe for main text
1. **Formulation + diagnostics claim (primary)**: the paper is strongest as an operational formulation plus diagnostic evaluation under action-budget matching.
2. **Method specification claim**: the controller can be specified operationally (implementation-level state, gates, commit logic, bounded repair), while acknowledging heuristic/state-dependent components.
3. **Top-cluster positioning claim**: Strict-F3 and Strict-Gate1-Cap-K6 form a statistically close matched-surface top cluster; Strict-F3 is used as a representative for continuity, not as a decisive winner.
4. **Baseline framing claim**: frontier methods are competitive but non-dominant versus `external_l1_max` in aggregate claim-safety framing.

### Appendix-only claims
1. OpenAI/Cohere real-model results as bounded robustness corroboration.
2. Held-out/dry-run surface checks as boundary/sensitivity evidence.
3. Token/latency/cost accounting details as diagnostic fairness accounting (not equivalence proof).

### Claims that must **not** be made
1. Universal/decisive Strict-F3 superiority over Strict-Gate1-Cap-K6.
2. Frontier-family dominance over `external_l1_max` across providers/surfaces.
3. Real-model evidence as headline proof of dominance.
4. Fixed action-budget as equivalent hardware/token/latency/dollar parity.

## Reviewer concern response map

### 1) Method under-specification
**Address**: Replace Equation 4 as literal objective interpretation with operational controller definition, including answer groups, branch families, commit thresholds, bounded repair, and gate caveats.

**Evidence artifacts**:
- `docs/OPERATIONAL_CONTROLLER_SPECIFICATION_FOR_MANUSCRIPT_20260424T164500Z.md`
- `outputs/operational_controller_specification_*/` (supporting outputs when present)

**Manuscript action**:
- Insert `method_operational_specification_insert.tex`

### 2) Narrow/selective framing
**Address**: Explicitly define matched manuscript surface vs broader operational surface; move held-out and real-model evidence to bounded appendix framing; state non-SOTA scope.

**Evidence artifacts**:
- `docs/UNIFIED_CLAIM_SAFETY_STATISTICAL_AUDIT_20260424T200000Z.md`
- `docs/HELD_OUT_SURFACE_GENERALIZATION_CLAIM_SAFETY_20260424T231500Z_DRY.md`
- `outputs/held_out_surface_generalization_claim_safety_20260424T231500Z_DRY/*`
- `docs/OPENAI_REAL_MODEL_MAIN_RUN_AUDIT_20260424T160421Z.md`
- `docs/COHERE_REAL_MODEL_MAIN_RUN_AUDIT_20260424T163700Z.md`
- `docs/CROSS_PROVIDER_REAL_MODEL_MAIN_RUN_AUDIT_20260424T163701Z.md`

**Manuscript action**:
- Insert `experimental_scope_and_claim_boundaries_insert.tex`

### 3) Small/statistically weak Strict-F3 margin
**Address**: State that Strict-F3 vs Strict-Gate1-Cap-K6 evidence is supportive but fragile; use Strict-F3 as matched-surface representative, not universal winner.

**Evidence artifacts**:
- `outputs/unified_claim_safety_statistical_audit_20260424T200000Z/pairwise_statistical_tests.csv`
- `outputs/unified_claim_safety_statistical_audit_20260424T200000Z/claim_safety_table.csv`
- `outputs/unified_claim_safety_statistical_audit_20260424T200000Z/winner_instability_by_surface.csv`

**Manuscript action**:
- Insert `statistical_strength_insert.tex`
- Insert `main_results_claim_safety_table_insert.tex`
- Insert `appendix_claim_boundary_insert.tex`

### 4) Baseline fairness and budget-accounting limitations
**Address**: Clarify near-direct matched-substrate baseline role, action-budget as primary contract, and token/latency/dollar as appendix diagnostics rather than full systems-cost equivalence.

**Evidence artifacts**:
- `outputs/unified_claim_safety_statistical_audit_20260424T200000Z/token_latency_accounting_summary.csv`
- `outputs/unified_claim_safety_statistical_audit_20260424T200000Z/artifact_limitations.csv`
- `outputs/paper_tables/table8_method_contract.tex`
- `docs/UNIFIED_CLAIM_SAFETY_STATISTICAL_AUDIT_20260424T200000Z.md`

**Manuscript action**:
- Insert `baseline_fairness_budget_accounting_insert.tex`

## Safe manuscript positioning (single-paragraph version)
The claim-safe version of the paper should present adaptive reasoning-budget allocation as an operationally specified controller formulation evaluated under action-budget-matched comparisons, with evidence emphasizing diagnostic and bounded robustness value rather than across-all-slice dominance. Matched-surface simulation supports competitiveness of Strict-F3 as a representative method, but pairwise margins against Strict-Gate1-Cap-K6 are fragile and winner identity is surface-sensitive. Real-model and held-out artifacts provide appendix-level corroboration and limitation context, not headline superiority claims.

## Package contents
- LaTeX inserts: method/specification, scope boundaries, statistical strength, fairness/budget accounting, limitations rewrite
- Main claim box and abstract-safe revision text
- Main-results and appendix claim-boundary insert paragraphs tied to the new claim-safety statistical table
- Forbidden overclaim checklist
- Four paper-ready CSV + LaTeX tables
