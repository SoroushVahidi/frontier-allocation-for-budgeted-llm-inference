# Claims guide

This is the shortest claim-scope guide for readers, reviewers, and agents. It does not replace `docs/PAPER_SOURCE_OF_TRUTH.md` or `docs/PAPER_CLAIMS_AND_EVIDENCE_MAP.md`; it summarizes the current safe interpretation.

## Current safe claims

- The project studies frontier allocation and final-answer selection under explicit inference-budget contracts.
- The repository has an audited recovery-track selector: `outcome_verifier_answer_group_selector_v1` with cached verifier scores.
- The selected verifier selector improves over conservative and trace-quality selector baselines on the recovery evidence package.
- `external_l1_max` is the current strong external comparator for real-model GSM8K-style comparisons.
- Recent diagnostics indicate that many residual failures are discovery/coverage failures: the gold answer is often absent from the candidate pool.
- Timestamped `outputs/` directories are provenance. Cite them only through canonical docs, manifests, and artifact-status tables.

## Current unsafe claims

Do not claim any of the following unless a new canonical promotion document explicitly supports it:

- broad or universal superiority over `external_l1_max`;
- runtime promotion of the selected outcome-verifier selector;
- headline wins from cache-limited verifier comparisons;
- headline wins from selected external-loss or recovery-only slices;
- causal gold-path counts from path-gap proxy diagnostics;
- manuscript claims based on an output folder without reading its `manifest.json` and the relevant canonical doc.

## Current evidence posture

The recovery-track selector result is useful and auditable, but it is not a full external-baseline victory. The latest bounded external comparison should be read as a gap-and-bottleneck diagnostic, not as a dominance claim.

Current research emphasis should therefore remain:

1. finish apples-to-apples, fully scored paired comparisons when needed;
2. compare selectors only on matched paired slices;
3. shift effort toward discovery/coverage improvements when residual losses are gold-absent from the candidate tree.

## Canonical sources

Read these before writing paper text or reviewer responses:

1. `docs/CURRENT_RESEARCH_HANDOFF_20260507.md`
2. `REVIEWER_FIRST.md`
3. `START_HERE_CURRENT.md`
4. `docs/PAPER_SOURCE_OF_TRUTH.md`
5. `docs/PAPER_CLAIMS_AND_EVIDENCE_MAP.md`
6. `docs/CURRENT_EXTERNAL_BASELINE_GAP.md`
7. `docs/CURRENT_PROJECT_STATUS.md`
8. `docs/ARTIFACT_STATUS_TABLE.md`
