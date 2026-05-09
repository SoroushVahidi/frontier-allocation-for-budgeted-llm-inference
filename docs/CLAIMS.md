# Claims guide

This is the shortest claim-scope guide for readers, reviewers, and agents. It does not replace `docs/PAPER_SOURCE_OF_TRUTH.md` or `docs/PAPER_CLAIMS_AND_EVIDENCE_MAP.md`; it summarizes the current safe interpretation.

## Current safe claims

- On the **2026-05-08 matched-50 case ID suite**, **`production_equiv_v1` scores 36/50** and **beats** the fair L1, SC4, S1, and TALE-EP external implementations on that same slice, **ties SC6** (36/50), and **does not beat** the **PAL/PoT fair** baseline (**40/50**) — cite `external_full_suite_summary.json` in `outputs/external_full_suite_matched50_comparison_20260508T222631Z/`.
- **Free-form / targeted discovery retry** and **schema-grounded retry v1** are documented **negative diagnostics** (not integrated winning methods) unless a new promotion doc says otherwise.
- The project studies frontier allocation and final-answer selection under explicit inference-budget contracts.
- The repository has an audited recovery-track selector: `outcome_verifier_answer_group_selector_v1` with cached verifier scores.
- The selected verifier selector improves over conservative and trace-quality selector baselines on the recovery evidence package.
- `external_l1_max` is the current strong external comparator for real-model GSM8K-style comparisons.
- Recent diagnostics indicate that many residual failures are discovery/coverage failures: the gold answer is often absent from the candidate pool.
- Timestamped `outputs/` directories are provenance. Cite them only through canonical docs, manifests, and artifact-status tables.

## Current unsafe claims

Do not claim any of the following unless a new canonical promotion document explicitly supports it:

- that **`production_equiv_v1` beats every individual external baseline** on matched evidence (false on the 2026-05-08 matched-50 suite: **PAL/PoT fair is 40/50** vs **production_equiv 36/50**; see `outputs/external_full_suite_matched50_comparison_20260508T222631Z/`);
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
