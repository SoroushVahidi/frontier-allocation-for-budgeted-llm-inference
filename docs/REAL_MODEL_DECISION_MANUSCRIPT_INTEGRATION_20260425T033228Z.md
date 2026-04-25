# Real-model decision manuscript integration report (20260425T033228Z)

## Scope and objective
Integrate `docs/REAL_MODEL_DECISION_PACKAGE_20260425T025417Z.md` into manuscript-facing docs and claim-language materials so the paper does not imply real-model dominance over `external_l1_max`.

## Files inspected
- `docs/MANUSCRIPT_SUPPORT_DASHBOARD.md`
- `docs/PAPER_SOURCE_OF_TRUTH.md`
- `docs/PAPER_CLAIMS_AND_EVIDENCE_MAP.md`
- `manuscript_integration/neurips_claim_safe_revision_20260424T234500Z/README.md`
- `manuscript_integration/neurips_claim_safe_revision_20260424T234500Z/abstract_safe_revision.txt`
- `manuscript_integration/neurips_claim_safe_revision_20260424T234500Z/main_results_claim_safety_table_insert.tex`
- `manuscript_integration/neurips_claim_safe_revision_20260424T234500Z/limitations_rewrite.tex`
- `manuscript_integration/neurips_claim_safe_revision_20260424T234500Z/appendix_claim_boundary_insert.tex`
- `docs/REAL_MODEL_DECISION_PACKAGE_20260425T025417Z.md`
- `outputs/real_model_decision_package_20260425T025417Z/`


## Files changed
- `docs/MANUSCRIPT_SUPPORT_DASHBOARD.md`
- `docs/PAPER_SOURCE_OF_TRUTH.md`
- `docs/PAPER_CLAIMS_AND_EVIDENCE_MAP.md`
- `manuscript_integration/neurips_claim_safe_revision_20260424T234500Z/README.md`
- `manuscript_integration/neurips_claim_safe_revision_20260424T234500Z/abstract_safe_revision.txt`
- `manuscript_integration/neurips_claim_safe_revision_20260424T234500Z/main_results_claim_safety_table_insert.tex`
- `manuscript_integration/neurips_claim_safe_revision_20260424T234500Z/limitations_rewrite.tex`
- `manuscript_integration/neurips_claim_safe_revision_20260424T234500Z/appendix_claim_boundary_insert.tex`
- `docs/REAL_MODEL_DECISION_MANUSCRIPT_INTEGRATION_20260425T033228Z.md`
- `outputs/real_model_decision_manuscript_integration_20260425T033228Z/manifest.json`
- `outputs/real_model_decision_manuscript_integration_20260425T033228Z/unsafe_phrase_scan.csv`
- `outputs/real_model_decision_manuscript_integration_20260425T033228Z/files_changed.csv`
- `outputs/real_model_decision_manuscript_integration_20260425T033228Z/claim_wording_update.csv`

## Unsafe phrases found and action taken
- Repository scan found 115 unsafe-phrase matches (many are historical/guardrail uses that negate overclaiming). See outputs/real_model_decision_manuscript_integration_20260425T033228Z/unsafe_phrase_scan.csv.
- Action policy:
  - **Updated in manuscript-facing authorities/snippets** where needed to reinforce non-dominance and appendix-only framing.
  - **Flagged (not bulk-edited)** in historical docs/scripts/tests/outputs when phrases are used as forbidden examples or negative guardrails.
- Machine-readable scan: `outputs/real_model_decision_manuscript_integration_20260425T033228Z/unsafe_phrase_scan.csv`.

## Final safe claim wording
- Main-paper headline evidence is the matched action-budget simulation/diagnostic surface.
- Real-model evidence is appendix-only calibration/diagnostic evidence.
- Cohere Stage-1 real-model result is mixed/unfavorable against `external_l1_max` and does **not** support dominance/superiority claims.
- `REAL_MODEL_DECISION_PACKAGE_20260425T025417Z.md` is a claim-boundary guardrail authority.

## Final forbidden claim wording
- "Real-model evidence shows dominance/superiority over `external_l1_max`."
- "Cohere Stage-1 confirms real-model dominance."
- "Main-paper real-model evidence establishes provider-independent or universal dominance/SOTA."

## Manuscript safety status
- **Status:** safer and claim-bounded after integration.
- **Conclusion:** manuscript-facing docs now explicitly block real-model dominance wording and keep real-model evidence appendix-only unless future stronger evidence changes the decision package.

## Remaining risk
- Historical and generated artifacts across the repository still contain unsafe-phrase strings (often as explicit guardrail negatives, test fixtures, or prior reports). These are now flagged in scan artifacts but not globally rewritten.
- Future edits can reintroduce overclaiming unless authors continue to route real-model wording through the decision-package guardrail.

## Artifact bundle
- `outputs/real_model_decision_manuscript_integration_20260425T033228Z/manifest.json`
- `outputs/real_model_decision_manuscript_integration_20260425T033228Z/unsafe_phrase_scan.csv`
- `outputs/real_model_decision_manuscript_integration_20260425T033228Z/files_changed.csv`
- `outputs/real_model_decision_manuscript_integration_20260425T033228Z/claim_wording_update.csv`
