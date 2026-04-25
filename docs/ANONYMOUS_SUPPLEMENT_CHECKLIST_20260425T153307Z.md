# ANONYMOUS_SUPPLEMENT_CHECKLIST_20260425T153307Z

1. **Does the repo reveal author identity?** Partially mitigated in canonical docs; legacy artifacts still require manual spot-check (`needs_manual_review`).
2. **Does the repo reveal institution?** Canonical docs scrubbed; historical files may retain institution/cluster terms.
3. **Does the repo reveal public GitHub owner?** Canonical docs avoid owner links; legacy external-link artifacts still tracked for manual review.
4. **Does the repo require API keys for paper reproduction?** No. Canonical paper regeneration path requires no OpenAI/Cohere key.
5. **Are paper-facing claims reproducible from committed artifacts?** Yes, via `scripts/paper/run_all_neurips_paper_artifacts.py` and `outputs/paper_*`.
6. **Are exploratory/negative artifacts clearly separated?** Yes, documented in artifact manifest and results guide.
7. **Are real-model results clearly marked as diagnostic/supporting only?** Yes.
8. **Are failed exploratory methods clearly marked and not promoted?** Yes (`strict_f3_case_split_direction_aware_v1` marked exploratory/provenance-only; 0.5952 vs 0.6085 strict_f3).
9. **Are all required NeurIPS-style artifact instructions present?** Added reviewer quickstart, source-of-truth, claim boundaries, and manifest docs.
10. **What risks remain before submission?** Legacy docs/filenames/links may still contain deanonymizing traces; use scan CSVs for final manual pass.
