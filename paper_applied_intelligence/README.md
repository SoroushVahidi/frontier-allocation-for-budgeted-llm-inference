# Applied Intelligence Manuscript Skeleton (`paper_applied_intelligence`)

This directory is the Applied Intelligence Journal working manuscript, bootstrapped from the MLJ manuscript. See README_APPLIED_INTELLIGENCE_CONVERSION.md for conversion status.

- Source of truth: `outputs/machine_learning_journal_result_package_20260520_20260520T035127Z/`
- Main method: `FIX-2+FIX-4`
- Claim scope: Cohere command-r-plus-08-2024, matched budget (`budget=6`) evaluations.

## Structure
- `main.tex`: paper entrypoint.
- `sections/`: section skeletons with evidence-scoped language.
- `tables/`: LaTeX tables generated from package CSVs.
- `figures/`: placeholders and data-source notes.
- `appendix.tex`: appendix tables and supplemental pointers.
- `refs.bib`: bibliography starter placeholders.
- `notes/`: writing-support docs (review matrix, checklist).

## Compile locally
```bash
cd paper_applied_intelligence
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
```

## Overleaf setup
1. Push repo to GitHub.
2. In Overleaf, import the `paper_applied_intelligence/` folder.
3. Ensure Springer class file availability (`svjour3.cls`) in project template.
4. Set main document to `main.tex`.

## Important constraints
- Do not expand claims beyond validated evidence.
- Ablation variants (e.g., FIX-5/6/7/8/9) must remain clearly marked as not retained.
- Cost claims must stay aligned with measured tokens/calls/latency fields only.
