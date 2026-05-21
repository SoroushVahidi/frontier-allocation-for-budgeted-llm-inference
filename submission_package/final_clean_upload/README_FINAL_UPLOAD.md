# Final Clean Upload Package (MLJ / Springer Portal)

## Primary upload files
- `mlj_final_main_manuscript_snjnl.pdf` (directly viewable manuscript PDF for quick inspection)
- `mlj_final_main_latex_snjnl.zip` (updated Springer `sn-jnl` manuscript source ZIP)
- `mlj_final_main_pdf.zip` (packaged PDF ZIP for portal upload, if needed)
- `mlj_final_figures_tables.zip`
- `mlj_final_admin_texts.zip`

## Additional files (if requested / applicable)
- `mlj_final_supplementary_reproducibility.zip`
- `mlj_final_related_files.zip`

## Notes
- Package refreshed on 2026-05-20 after title and conclusion polish: title shortened to "Failure-Trace-Guided Answer Allocation for Budgeted LLM Reasoning"; file-path reference removed from Conclusion; cover letter wording updated.
- Package refreshed on 2026-05-20 after appendix layout simplification: collapsed to single appendix section with subsection labels; guaranteed heading-before-table order in rendered PDF; no B/C/D/E appendix headings appearing without content.
- Package refreshed on 2026-05-20 after Data/Code Availability and appendix wording polish: journal-style availability statements, Appendix A intro updated, tableA1 Rerun requirements row simplified.
- Package refreshed on 2026-05-20 after appendix section reorganization fix: each appendix heading now immediately precedes its tables; empty Algorithm Listing section removed; note about Algorithm 1 placed in Appendix A.
- Package refreshed on 2026-05-20 after Related Work polish in commit `9b4c6301b04813a3e6b5af310ac6830d7a377333`.
- Reviewer-risk fixes from commit `81adc69c9f327d73d048c061ca35969d92bab49d` remain included: budget-accounting clarification, four-way pooled ensemble baseline, FIX-4 action decomposition, seed-61 diagnostic text, frontier predicate/metadata description, tie-breaker sensitivity, and bootstrap positive-delta wording.
- Canonical and staged manuscripts retain the 7-section journal structure.
- Related Work uses the polished four-theme journal-style structure in canonical and staged sources.
- Figure 1 yes/no label placement fix is preserved in staged and canonical sources.
- Main LaTeX ZIP is built from `paper_ml_journal_snjnl_stage/` sources.
- `mlj_final_main_manuscript_snjnl.pdf` and `mlj_final_main_pdf.zip` both contain the rebuilt `paper_ml_journal_snjnl_stage/main.pdf` content.
- Scientific claims/results were not changed during packaging.
- Supplementary ZIP is reviewer-facing only.
- If editor requests: add the related under-review manuscript PDF to `mlj_final_related_files.zip`.
