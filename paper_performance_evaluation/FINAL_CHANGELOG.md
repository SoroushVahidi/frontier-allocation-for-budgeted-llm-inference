# Final Changelog

Date: 2026-08-01

## Manuscript Edits

- Corrected appendix cross-reference rendering by replacing source patterns of
  `Appendix~\ref{app:...}` with `\ref{app:...}` where `elsarticle` already renders appendix labels
  with the word "Appendix". This removed compiled strings such as `Appendix Appendix K`.
- Removed trailing periods inside `\paragraph{...}` headings so compiled paragraph headings no
  longer show doubled punctuation such as `Contribution..`.
- Updated the Introduction roadmap to mention Section 10 offline counterfactuals explicitly.
- Added leading separators in selected `.bib` note fields so venue notes no longer concatenate with
  arXiv identifiers in the compiled references.

## Files With Source Content Changes

- `main.tex`
- `main_with_titlepage.tex`
- `refs.bib`
- `sections/01_introduction.tex`
- `sections/02_related_work.tex`
- `sections/03_problem_formulation.tex`
- `sections/04_method.tex`
- `sections/05_experimental_setup.tex`
- `sections/06_main_results.tex`
- `sections/07_search_vs_selection.tex`
- `sections/08_provider_analysis.tex`
- `sections/09_compute_accounting.tex`
- `sections/10_ablations.tex`
- `sections/11_limitations.tex`
- `sections/12_discussion.tex`
- `sections/appendix.tex`
- `tables/table4_baseline_fidelity.tex`

The same final source text was synchronized into
`submission_package_pass6_20260801T135817Z/latex_flat/`.

## Regenerated Or Synchronized Files

- `main.pdf`
- `main_with_titlepage.pdf`
- `main.bbl`
- `main.blg`
- `main.log`
- `main_with_titlepage.bbl`
- `main_with_titlepage.blg`
- `main_with_titlepage.log`
- `submission_package_pass6_20260801T135817Z/anonymous_manuscript.pdf`
- `submission_package_pass6_20260801T135817Z/titlepage_manuscript.pdf`
- `submission_package_pass6_20260801T135817Z/latex_flat/main.pdf`
- `submission_package_pass6_20260801T135817Z/latex_flat/main_with_titlepage.pdf`
- `submission_package_pass6_20260801T135817Z/performance_evaluation_submission_source.zip`

## New Audit Files

- `FINAL_SUBMISSION_AUDIT.md`
- `FINAL_CHANGELOG.md`

## Scientific Content

- No scientific values were changed.
- No experimental results were recomputed.
- No new experiments, API calls, commits, or pushes were performed.
- No figure/table data, plotted values, captions' scientific claims, or evidence boundaries were
  changed in this pass.

## Package Status

The existing Pass 6 submission package was refreshed to reflect final source and PDF edits:

- `submission_package_pass6_20260801T135817Z/anonymous_manuscript.pdf`: 262198 bytes.
- `submission_package_pass6_20260801T135817Z/titlepage_manuscript.pdf`: 267485 bytes.
- `submission_package_pass6_20260801T135817Z/performance_evaluation_submission_source.zip`:
  1157033 bytes at validation time.
- `submission_package_pass6_20260801T135817Z/performance_evaluation_supplementary_material.zip`:
  14369 bytes.
