# Submission Package Manifest

Date: 2026-08-01

Package root:

`paper_performance_evaluation/submission_package_pass6_20260801T135817Z/`

## Top-Level Files

| File | Size |
| --- | ---: |
| `anonymous_manuscript.pdf` | 262494 bytes |
| `titlepage_manuscript.pdf` | 269874 bytes |
| `performance_evaluation_submission_source.zip` | 586863 bytes |
| `performance_evaluation_supplementary_material.zip` | 14377 bytes |

## Separate Artwork

| File | Size | Status |
| --- | ---: | --- |
| `artwork/Figure_1_protocol_schematic.pdf` | 11623 bytes | Added TikZ protocol schematic export. |
| `artwork/Figure_2_fta_frontier_delta_heatmap.pdf` | 24366 bytes | Retained. |
| `artwork/Figure_3_search_vs_selection_scatter.pdf` | 20832 bytes | Retained. |
| `artwork/Figure_4_accuracy_vs_cost_tradeoff.pdf` | 20372 bytes | Retained. |
| `artwork/Figure_5_fta_vs_pooled4_delta_heatmap.pdf` | 23105 bytes | Retained. |

## Submission Assets

- `submission_assets/highlights.txt`: five highlights; each is <=85 characters.
- `submission_assets/cover_letter.md`: draft cover letter with author placeholders.
- `submission_assets/declarations.md`: declarations draft and author-confirmation list.
- `submission_assets/title_page.tex`: separate title-page source with public author name and author-confirmation fields for affiliation/contact metadata.

## LaTeX Source Package

`performance_evaluation_submission_source.zip` contains:

- Flat `latex_flat/` source with no `sections/`, `tables/`, or `figures/` path dependencies.
- `main.tex` anonymous manuscript source.
- `main_with_titlepage.tex` title-page manuscript source.
- `title_page.tex`.
- `refs.bib`, `main.bbl`, `main_with_titlepage.bbl`.
- Elsevier numbered and alternative bibliography styles.
- Current table `.tex` files.
- Current figure files, including the standalone protocol schematic source/PDF.
- Manuscript PDFs generated from the flat source for validation.

The legacy concept PDF no longer used in the manuscript is not included in the source ZIP.

## Supplementary Material

`performance_evaluation_supplementary_material.zip` contains:

- `README.md`.
- `CLAIM_EVIDENCE_MAP.md` adapted for Performance Evaluation packaging.
- `CLAIM_SCOPE_AUDIT.md`.
- `NUMERICAL_CONSISTENCY_CHECK.md` adapted for Performance Evaluation packaging.
- `FIGURE_TABLE_AUDIT.md`.
- `LAYOUT_AND_PAGE_AUDIT.md`.
- `REDUNDANCY_FINAL_AUDIT.md`.
- `JOURNAL_COMPLIANCE_FINAL_AUDIT.md`.
- `PAGE_LENGTH_AUDIT.md`.
- `CHECKSUMS_SHA256.txt`.

## Validation Results

- Root compile:
  - `latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex`: succeeded; 34 pages.
  - `latexmk -pdf -interaction=nonstopmode -halt-on-error main_with_titlepage.tex`: succeeded; 34 pages.
- Flat-source compile:
  - `latex_flat/main.tex`: succeeded independently with `latexmk`; 34 pages.
  - `latex_flat/main_with_titlepage.tex`: succeeded independently with `latexmk`; 34 pages.
- ZIP extraction:
  - `unzip -t performance_evaluation_submission_source.zip`: no errors.
  - `unzip -t performance_evaluation_supplementary_material.zip`: no errors.
- Supplement checksums:
  - `sha256sum -c CHECKSUMS_SHA256.txt`: all OK.
- Citation/reference validation:
  - Undefined references/citations: zero after final rerun.
  - Duplicate labels: zero.
  - Missing figures: zero.
  - Unreferenced figures/tables/equations: zero.
- Layout:
  - One residual 2.608 pt `Overfull \hbox ... while \output is active` warning with no text content in the log; recorded as non-material.
  - Remaining underfull warnings occur in dense tables and bibliography lines.
- Anonymity and safety:
  - Anonymous PDF metadata author is `Anonymous Author(s)`.
  - Anonymous PDF scan found no placeholder author string, placeholder email, ORCID placeholder, or local username.
  - Supplement scan found no prior-venue private-workflow wording.
  - Package scan found no absolute local paths.
  - Package scan found no secret-like strings.

## Remaining Author Confirmations

- Affiliations and corresponding author email.
- ORCID/phone/address fields if requested by Editorial Manager.
- Funding statement or explicit no-specific-funding statement.
- Competing-interest statement.
- Repository DOI, if minted.
- Final acknowledgments, keeping emotional support, academic/advisory assistance, software support,
  and API credits distinct.
- Exact names of generative-AI tools/services if the submission form requires them.
