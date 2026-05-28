# Overleaf-Ready Package Manifest

## Core manuscript files to upload/copy

- `main.tex`
- `appendix.tex`
- `refs.bib`
- `mlj_contribution_information_sheet.tex`
- `sections/` (all `.tex` section files)
- `tables/` (all table `.tex` files)
- `figures/` (figure wrappers and required figure assets)

## Required figures

- Figure 1: TikZ source in `figures/figure1_method_overview.tex` (and optional rendered PDF)
- Figure 2: `figures/figure2_accuracy_ci.pdf` (or high-resolution PNG if required)
- Figure 3: `figures/figure3_failure_breakdown.pdf` (or high-resolution PNG if required)

## Do not upload

- `main.pdf` unless the portal asks separately
- `notes/` (except files intentionally uploaded as related/cover content)
- build artifacts: `.aux`, `.log`, `.out`, `.fls`, `.fdb_latexmk`, `.synctex.gz`
- caches and temporary files
- `.env` files or any credential files
- API keys or secrets
- large `outputs/` directories
- private/internal artifacts not intended for review

## Manual submission steps

- Create or import the official Springer Nature `sn-jnl` template in Overleaf.
- Confirm current MLJ class/template requirements in the portal guidance.
- Compile under the official template and perform final visual PDF inspection.
- Upload the MLJ contribution information sheet separately if requested by the portal.
