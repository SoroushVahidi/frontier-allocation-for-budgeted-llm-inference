# Page Length Audit

Date: 2026-08-01

Build command:

```sh
tectonic --keep-logs -p main.tex
tectonic --keep-logs -p main_with_titlepage.tex
```

## Final Counts

| Variant | Total pages | Main text and declarations | References | Appendix |
| --- | ---: | ---: | ---: | ---: |
| Anonymous (`main.pdf`) | 34 | 22 full pages plus declarations on page 23 | pages 23-26 | pages 27-34 |
| Title-page (`main_with_titlepage.pdf`) | 34 | 22 full pages plus declarations on page 23 | pages 23-26 | pages 27-34 |

Notes:

- References begin on page 23 after declarations.
- Appendix content begins on page 27.
- The length reduction from Pass 5 is 36 to 34 pages in both compiled variants.

## Source of Length

- Elsevier `preprint,12pt` formatting accounts for substantial vertical expansion.
- Dense tables in Sections 6, 8, 9 and Appendix F/L/O remain necessary evidence.
- Appendix occupies 8 pages and carries provenance, pseudocode, historical diagnostics, and supplemental controls.
- No fonts were reduced below the existing readable table settings.

## Layout Results

- Undefined references/citations: zero after final rerun.
- Duplicate labels: zero detected by label scan and logs.
- Missing figures: zero.
- Material overfull boxes: none observed.
- Residual LaTeX warning: one 2.608 pt `Overfull \hbox ... while \output is active` in the introduction with no text content shown in the log; recorded as non-material page-output noise.
- Underfull boxes remain in dense tables and bibliography entries; they do not indicate clipping or missing content.

