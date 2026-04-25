# REAL_MODEL_DECISION_PACKAGE_20260425T025417Z

## Scope and provenance

This decision package is a repository-grounded synthesis of existing artifacts only (no new model runs), focused on Cohere GSM8K Stage-1 strict_f3 vs external_l1_max implications for NeurIPS manuscript safety.

Primary inputs:
- `outputs/cohere_gsm8k_strict_f3_vs_external_l1_max_diagnostic_20260425T235500Z/`
- `docs/COHERE_GSM8K_STRICT_F3_VS_EXTERNAL_L1_MAX_DIAGNOSTIC_20260425T235500Z.md`
- `outputs/cohere_real_model_cost_normalized_validation_20260425T133000Z_COHERE_STAGE1_MIN/`
- `docs/COHERE_REAL_MODEL_COST_NORMALIZED_VALIDATION_20260425T133000Z_COHERE_STAGE1_MIN.md`
- `docs/UNIFIED_CLAIM_SAFETY_STATISTICAL_AUDIT_20260424T200000Z.md`
- `docs/MANUSCRIPT_SUPPORT_DASHBOARD.md`
- `docs/PAPER_SOURCE_OF_TRUTH.md`

## Key observed numbers (Cohere Stage-1)

- Matched examples: 30
- strict_f3 accuracy: 0.5333
- external_l1_max accuracy: 0.8000
- Paired delta (strict_f3 - external_l1_max): -0.2667
- Bootstrap 95% CI: [-0.4667, -0.0667]
- Budget deltas: b4=-0.3, b6=-0.3, b8=-0.2
- Seed deltas: s11=-0.2, s23=-0.3333
- Cost-normalized metrics favor external_l1_max
- Runner checks: mostly pass; matched IDs warning remains
- Claim tier: diagnostic_only_incomplete

## Required question answers

1. **Does the current Cohere Stage-1 result support using real-model evidence as main-paper evidence?**
   - **No** for dominance-facing use. The current real-model evidence on this comparison is unfavorable and incomplete.

2. **Does it support claiming strict_f3 or frontier allocation beats external_l1_max under real API execution?**
   - **No.** Current paired evidence is negative overall and negative across all observed budgets and both seeds.

3. **Does it instead support only appendix/diagnostic framing?**
   - **Yes.** Current status is diagnostic_unfavorable_incomplete.

4. **Is the negative result strong enough to require changing manuscript claim language now?**
   - **Yes.** Immediate claim-language downgrade is required for safety.

5. **Should we run OpenAI fallback confirmation, complete more Cohere examples, improve the algorithm, or revise framing now?**
   - **Primary now:** revise manuscript framing immediately (appendix-only for this real-model dominance comparison).
   - **Secondary bounded step:** run OpenAI fallback only as calibration/confirmation, not as replacement for Cohere adverse evidence.
   - **Do not** do blind unlimited Cohere expansion without a pre-specified hypothesis.

6. **Safest NeurIPS-facing story after this result?**
   - Formulation + diagnostic + bounded external-validity story.
   - Real-model strict_f3-vs-external_l1_max remains mixed/unfavorable and non-dominant.

## Decision logic application

Conservative rules applied:
- strict_f3 loses + cost-normalized disadvantage -> **real-model dominance = not_safe**.
- Matched set small/incomplete warnings -> **diagnostic_unfavorable_incomplete**, not universal final evidence.
- All budget slices negative -> **avoid blind API expansion** without mechanism hypothesis.
- Runner correctness mostly pass -> treat result as **real warning**, not a likely scoring bug.
- OpenAI fallback -> **calibration only**, not failure-hiding.

## Recommendation among options A-E

- **Primary recommendation: E** (abandon real-model evidence as main-paper dominance evidence; keep appendix-only).
- **Secondary recommendation: B** (bounded OpenAI fallback confirmation for calibration).
- **Conditional tertiary: D** (algorithm improvement only under explicit failure hypothesis).
- **Lower priority: C** (complete Cohere to larger sample only after hypothesis + budget plan).
- **Not sufficient alone: A** (reframe-only without acknowledging unresolved method risk).

## Output package

Directory: `outputs/real_model_decision_package_20260425T025417Z/`

Files:
- `manifest.json`
- `real_model_decision_table.csv`
- `cohere_stage1_key_numbers.csv`
- `claim_status_update.csv`
- `recommended_manuscript_changes.md`
- `next_action_options.csv`
- `failure_diagnosis_summary.csv`
- `openai_fallback_decision.csv`

## Bottom line

Current Cohere Stage-1 evidence is scientifically important and unfavorable to any real-model superiority claim over `external_l1_max`. The manuscript should be revised now to a safe non-dominance framing, with optional bounded OpenAI fallback only for calibration.
