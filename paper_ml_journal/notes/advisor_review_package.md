# Advisor Review Package

**Scope:** MLJ manuscript review only. No scientific claims, baselines, datasets, or promoted results were changed.

## Current status

- Figure 1, Figure 2, and Figure 3 are integrated in `main.tex`.
- The manuscript builds successfully with `make pdf` in `paper_ml_journal/`.
- The promoted claim remains FIX-2+FIX-4 on Final-300 and Aggregate-720, consistent with `docs/LATEST_RESULTS_AND_CLAIMS.md`.
- FIX-5/6/7/8/9 remain non-promoted and are described as negative or insufficient results.

## What to review

- `paper_ml_journal/main.tex`
- `paper_ml_journal/sections/04_method.tex`
- `paper_ml_journal/sections/06_results.tex`
- `paper_ml_journal/sections/08_failure_analysis.tex`
- `paper_ml_journal/figures/figure1_method_overview.tex`
- `paper_ml_journal/figures/figure2_accuracy_ci.tex`
- `paper_ml_journal/figures/figure3_failure_breakdown.tex`
- `paper_ml_journal/tables/tableA6_name_mapping.tex`
- `paper_ml_journal/appendix.tex`

## Notes

- Paper-facing names are used in the figures and main text; raw repository identifiers stay in the mapping/appendix tables.
- Data and Code Availability, Funding, Competing Interests, Author Contributions, and Use of AI Tools declarations are present.
- `paper_ml_journal/main.pdf` is generated output and should remain untracked unless intentionally added.

## Remaining manual journal items

- Replace the local `svjour3.cls` stub with the official Springer class before submission.
- Do a final print-width check under the official template if needed.
- Confirm any final bibliography publication-status updates before upload.
