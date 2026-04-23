# Canonical external baseline fairness checklist

Timestamp (UTC): `20260423T021422Z`

This document is generated for reviewer-defensible external baseline integration across four specific paper targets.

## Canonical conclusions
1. **Zhai (2026 / arXiv:2604.14853) is the cleanest main-table target** once a matched-surface contract and runner are added.
2. **DIPA (OpenReview ztGHhyicWs) is main-table only under a compatible per-attempt/verifiable-task contract**; otherwise appendix-only.
3. **compute-optimal TTS (OpenReview 4FWAwZtd2n; arXiv:2408.03314) is appendix-only** unless re-instantiated under the same mechanism family and accounting with resolved provenance.
4. **Bilal et al. (arXiv:2602.01070) is adjacent-only** unless PRM/tool/search infrastructure is genuinely shared and counted.

## Artifact bundle
- `outputs/canonical_external_baseline_fairness_checklist_20260423T021422Z/baseline_contract_matrix.csv`
- `outputs/canonical_external_baseline_fairness_checklist_20260423T021422Z/baseline_contract_matrix.json`
- `outputs/canonical_external_baseline_fairness_checklist_20260423T021422Z/main_table_eligibility.csv`
- `outputs/canonical_external_baseline_fairness_checklist_20260423T021422Z/fairness_violations.csv`
- `outputs/canonical_external_baseline_fairness_checklist_20260423T021422Z/normalization_rules.json`
- `outputs/canonical_external_baseline_fairness_checklist_20260423T021422Z/required_shared_infrastructure.json`
- `outputs/canonical_external_baseline_fairness_checklist_20260423T021422Z/baseline_presence_audit.csv`
- `outputs/canonical_external_baseline_fairness_checklist_20260423T021422Z/summary.md`

## Presence interpretation notes
- `already_present_partial` means evidence exists in docs/registry/adapter artifacts but no fully fair canonical direct-comparison lane is ready.
- `already_present_blocked` means baseline is tracked with explicit blocker artifacts.
- `not_present` means no meaningful footprint in current repo taxonomy/registry/docs/scripts/outputs.
