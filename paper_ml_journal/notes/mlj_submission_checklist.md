# MLJ Submission Checklist

This file tracks items requiring manual author action before submitting to
Springer Machine Learning Journal. Do not include this file in the compiled PDF.

---

## Manuscript Class

- [ ] Replace `paper_ml_journal/svjour3.cls` (80-line compatibility stub) with the
  official Springer `svjour3.cls` from the Springer Author Kit before uploading to
  the journal system. Overleaf provides this automatically when you import the project.

---

## Electronic Supplementary Material

- [ ] **Confirm MLJ submission-system requirement for Electronic Supplementary
  Material heading/metadata.** The appendix is currently included inline in the
  PDF via `\input{appendix}`. Verify whether the MLJ submission portal requires
  the appendix to be submitted as a separate file with an "Electronic Supplementary
  Material" cover sheet, or whether inline appendix inclusion is acceptable.
  Reference: https://link.springer.com/journal/10994/submission-guidelines

---

## Author Information

- [x] Author name: Soroush Vahidi (filled)
- [x] Institute: Department of Computer Science, NJIT, Newark, NJ
- [x] Email: sv96@njit.edu (filled)
- [ ] If adding co-authors, update `\author{}` and `\institute{}` in `main.tex`
  and update Author Contributions in `appendix.tex`.

---

## Funding

- [x] Funding statement present: "no specific grant" (neutral, complete)
- [ ] Update funding statement if a grant is awarded before submission.

---

## Data and Code Availability

- [x] Data Availability statement present (appendix)
- [x] Code Availability statement present (appendix)
- [ ] Ensure artifact paths in Data/Code Availability remain valid at submission
  (e.g., the result package directory exists and is publicly accessible or
  included in the repository).

---

## Reference Verification

- [x] All 16 bib entries verified and cited
- [x] besta2024graph: AAAI 2024 (updated)
- [x] chen2023frugalgpt: TMLR 2024 (updated)
- [x] cobbe2021training: arXiv 2110.14168 (no published proceedings — correct)
- [ ] Check whether snell2024scaling (arXiv 2408.03314) has been published in
  a venue by submission time; update bib entry if so.
- [ ] Check whether muennighoff2025s1 (arXiv 2501.19393) has been published in
  a venue by submission time; update bib entry if so.

---

## Figures

- [x] Figure 1 (method overview): regenerated with spelled-out trigger conditions;
  no undefined abbreviations; readable at journal width.
- [x] Figure 2 (accuracy CI): clear, all CI bounds labeled.
- [x] Figure 3 (failure breakdown): clear taxonomy.
- [ ] Compile with official svjour3.cls and inspect figure sizing at actual
  print column width before final submission.

---

## Final Scan Before Submission

Run the following grep to check for stale content before upload:

```bash
grep -rn "TODO\|placeholder\|anonymous\|NeurIPS\|STRICT-F3\|STRICT-GATE1\|anti-collapse\|PAL+retry\|McNemar\|252/300\|significantly outperforms" \
  paper_ml_journal/sections/ paper_ml_journal/tables/ paper_ml_journal/appendix.tex paper_ml_journal/main.tex
```
