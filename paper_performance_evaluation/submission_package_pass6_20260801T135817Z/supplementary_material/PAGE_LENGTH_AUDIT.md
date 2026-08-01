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
| Anonymous (`main.pdf`) | 30 | main text through page 20; declarations on pages 21-22 | pages 23-27 | pages 28-30 |
| Title-page (`main_with_titlepage.pdf`) | 32 | title page plus main text through page 21; declarations on pages 22-23 | pages 24-27 | pages 28-32 |

Notes:

- References begin on page 23 in the anonymous build and page 24 in the identified build.
- Appendix content begins on page 28 in both compiled variants.
- The focused correction pass reduced the identified manuscript from 35 to 32 pages and the
  anonymous manuscript from 34 to 30 pages in Elsevier preprint formatting.

## Source of Length

- Elsevier `preprint,12pt` formatting accounts for substantial vertical expansion.
- Dense tables in Sections 6, 8, and 9 remain necessary evidence.
- Appendix now occupies 5 pages in the identified build and carries provenance, pseudocode,
  current-evidence diagnostics, and compute detail.
- No fonts were reduced below the existing readable table settings.

## Layout Results

- Undefined references/citations: zero after final rerun.
- Duplicate labels: zero detected by label scan and logs.
- Missing figures: zero.
- Material overfull boxes: none observed.
- Residual LaTeX warning: one 2.608 pt `Overfull \hbox ... while \output is active` in the introduction with no text content shown in the log; recorded as non-material page-output noise.
- Underfull boxes remain in dense tables and bibliography entries; they do not indicate clipping or missing content.
