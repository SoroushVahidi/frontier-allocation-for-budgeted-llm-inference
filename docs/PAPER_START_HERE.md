# PAPER_START_HERE

Use this page as the manuscript front door.

## Scope and identity (do not drift)

This repository is currently about **fixed-budget adaptive test-time compute allocation for LLM reasoning** with:
- cross-controller frontier allocation,
- next-step branch allocation,
- answer-group-level commit control,
- diversity realization under budget,
- anti-collapse branch-family control,
- and real-model confirmation for branch-allocation policy choices.

It is **not** centered on the older binary revise-routing story.

## Critical two-surface rule

Keep this distinction explicit in every draft:
- **Broader strict-phased operational default:** `strict_gate1_cap_k6`.
- **Canonical manuscript-facing matched-surface internal winner:** `strict_f3`.

Do not collapse these into one claim.

## Minimal reading order for paper writing

1. `CANONICAL_START_HERE.md`
2. `INTERNAL_METHOD_FINAL_DECISION_PACKAGE_2026_04_22.md`
3. `MANUSCRIPT_METHOD_VS_OPERATIONAL_DEFAULT.md`
4. `PAPER_SOURCE_OF_TRUTH.md`
5. `PAPER_METHOD_NAMING_POLICY.md`
6. `PAPER_CLAIMS_AND_EVIDENCE_MAP.md`
7. `PAPER_ARTIFACT_MAP.md`
8. `PAPER_FIGURES_AND_TABLES_PLAN.md`
9. `PAPER_BASELINE_HONESTY_STATUS.md`
10. `PAPER_REPRODUCTION_CHECKLIST.md`
11. `PAPER_OPEN_GAPS_AND_RISKS.md`

## Canonical regeneration entry points

```bash
make setup
make health
python scripts/run_broader_strict_phased_default_decision_eval.py
python scripts/run_paper_method_decision_bundle_strict_gate1_cap_k6_vs_strict_f3.py
python scripts/paper/run_all_neurips_paper_artifacts.py
```

## What is manuscript-safe vs not

- **Manuscript-safe first:** outputs/docs that appear in `PAPER_SOURCE_OF_TRUTH.md` and `PAPER_ARTIFACT_MAP.md` as canonical.
- **Supportive only:** exploratory variants and bounded diagnostics not promoted as canonical.
- **Historical/provenance only:** archive/legacy material and superseded status notes unless explicitly referenced by canonical docs.
