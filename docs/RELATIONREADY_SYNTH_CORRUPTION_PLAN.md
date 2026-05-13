Synthetic corruption plan — generate negative/ambiguous candidates without API calls

Objectives
- Produce realistic semantically-wrong but locally-plausible candidates by deterministic transformations of correct formulas or candidates.
- Avoid using gold as input; use gold only to select corruption targets and for evaluation.

Corruption methods (offline, deterministic)
1. Variable rebinding: swap variable bindings (e.g., swap numerator/denominator variables) to create wrong bindings.
2. Relation deletion: remove a linking relation step from an equation chain (creates relation_composition_missing).
3. Unit/scale inversion: introduce a missing unit conversion (×12 or ÷12) and tag as unit_scale_error.
4. Off-by-one/aggregation errors: apply simple arithmetic perturbations (+/- small integer, scale by factor 2/3, rounding) to create arithmetic_precision errors.
5. Final-after-process omission: remove a final transformation step that occurs after an intermediate calculation.
6. Mix plausible distractor constants from other variables in the same case.

Procedure
- Start from verified correct candidate rows (synthetic or curated). For each, produce N corrupted variants via deterministic transformations and record the corruption type.
- Run deterministic checks (parsable, exec value) locally; keep only corruptions that remain executable or locally plausible (to stress verifier).

Labeling
- Flag each synthetic row with corruption_source: e.g., "var_rebind_swap_v1" and lemma describing transformation.
- Annotators or automated heuristics should validate corruption semantics and then label accept/reject.

Safety
- No API/model calls required for generation; use local scripts and deterministic rules.

