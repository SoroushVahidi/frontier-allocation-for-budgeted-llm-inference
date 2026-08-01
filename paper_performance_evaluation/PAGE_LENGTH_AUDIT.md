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
| Anonymous (`main.pdf`) | 33 | main text through page 21; declarations on page 22 | pages 23-28 | pages 29-33 |
| Title-page (`main_with_titlepage.pdf`) | 33 | title page plus main text through page 21; declarations on page 22 | pages 23-28 | pages 29-33 |

Notes:

- References begin on page 23 in both compiled variants.
- Appendix content begins on page 29 in both compiled variants.
- The final minor-edit pass leaves both variants at 33 pages in Elsevier preprint formatting.

## Source of Length

- Elsevier `preprint,12pt` formatting accounts for substantial vertical expansion.
- Dense tables in Sections 6, 8, and 9 remain necessary evidence.
- Appendix now occupies 5 pages in both builds and carries provenance, pseudocode,
  current-evidence diagnostics, and compute detail.
- No fonts were reduced below the existing readable table settings.

## Layout Results

- Undefined references/citations: zero after final rerun.
- Duplicate labels: zero detected by label scan and logs.
- Missing figures: zero.
- Material overfull boxes: none observed.
- Residual LaTeX warning: one 2.608 pt `Overfull \hbox ... while \output is active` in the introduction with no text content shown in the log; recorded as non-material page-output noise.
- Underfull boxes remain in dense tables and bibliography entries; they do not indicate clipping or missing content.
