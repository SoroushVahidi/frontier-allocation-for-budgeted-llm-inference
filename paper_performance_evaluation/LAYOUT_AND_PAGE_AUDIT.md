# Layout and Page Audit - Pass 5

Date: 2026-08-01

## Build Commands

Run from `paper_performance_evaluation/`:

```sh
latexmk -g -pdf -interaction=nonstopmode -halt-on-error main.tex
latexmk -g -pdf -interaction=nonstopmode -halt-on-error main_with_titlepage.tex
tectonic --keep-logs -p main.tex
tectonic --keep-logs -p main_with_titlepage.tex
```

The final two commands regenerated current `.log` files for audit inspection.

## Page Counts

| Build | PDF | Pages | Page size |
|---|---|---:|---|
| Anonymous | `main.pdf` | 36 | Letter, 612 x 792 pt |
| Title-page | `main_with_titlepage.pdf` | 36 | Letter, 612 x 792 pt |

## Compile Checks

- Undefined references: none found in regenerated logs.
- Undefined citations: none found in regenerated logs.
- Duplicate labels: none found by label scan.
- Missing figures: none reported by LaTeX.
- Float-specifier conversions: none after replacing remaining `[h]` floats with flexible placement.
- Material overfull boxes: none remaining. Residual overfull boxes are small paragraph breaks only:
  `2.608pt`, `1.45953pt`, and `0.13205pt`.
- Residual underfull boxes remain in dense wrapped tables and bibliography entries. They do not
  indicate clipping or overlap in the rendered pages spot-checked for the protocol figure and main
  table flow.

## Layout Repairs Performed

- Added `tabularx`/`array` support and a ragged table column type.
- Added a compact TikZ protocol figure and verified it renders without label overlap.
- Hid hyperlink borders with `\hypersetup{hidelinks}` to remove visible red/green boxes.
- Replaced rigid `[h]` float placement with flexible `[tbp]` placement.
- Enlarged key data figures for manuscript readability.
- Abbreviated table headers/provider labels where captions define full meaning.
- Reworked appendix diagnostic tables to avoid wide-row overflow.
- Converted `main_with_titlepage.tex` from a placeholder compile to the full manuscript build.

## Visual Spot-Check

Rendered pages were inspected from `main.pdf` after the final compile. The protocol schematic and
surrounding Introduction text showed no clipping, overlap, or hyperlink-border noise. Earlier
individual figure renders for all PDF figure assets showed readable labels and no clipping.

## Residual Layout Risks

- `tables/table5_compute_matched_phase7.tex` and `tables/table8_non_math_pilot.tex` still produce
  underfull warnings because they intentionally use narrow wrapped cells for dense disclosures.
- The manuscript is in Elsevier preprint layout on Letter paper. Pass 6 packaging should confirm
  whether the submission system wants A4 source rendering or accepts the default `elsarticle`
  preprint output.
