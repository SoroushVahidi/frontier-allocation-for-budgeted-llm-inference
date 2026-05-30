# Applied Intelligence Resubmission — Single-TeX Package (2026-05-30)

## Background

Applied Intelligence sent the submission back because the original package contained
multiple `.tex` files; Editorial Manager compiled extra files into the generated PDF.

## What was done

Created a corrected single-tex source package by inlining all `\input{}`/`\include{}`
files from `paper_applied_intelligence/main.tex` into one self-contained `main.tex`.
No scientific content, wording, citations, or results were changed; only paths were
adjusted for flat-package compilation.

## Package

- **Folder:** `submission_applied_intelligence_single_tex/`
- **Zip:** `applied_intelligence_fta_single_tex_source_20260530.zip`

### Contents

| File | Role |
|------|------|
| `main.tex` | Single self-contained manuscript (all sections inlined) |
| `refs.bib` | Bibliography |
| `svjour3.cls` | Springer journal class |
| `figure1_fta_method_overview.png` | Figure 1 |
| `figure2_main_quantitative_results.png` | Figure 2 |
| `figure3_gate_activation.png` | Figure 3 |
| `figure4_residual_failure_analysis.png` | Figure 4 |

## Compile verification

- Compiled with Tectonic (via `latexmk` shim): **success**
- PDF page count: **28 pages**
- Unresolved citations (`??`): **0**
- Duplicate BibTeX keys: **0**
- `.tex` files in package: **exactly 1**
- `main.pdf` in zip: **no** (excluded per source-package convention)
