# Applied Intelligence — Warning and Reference Cleanup (2026-05-30)

---

## 2026-05-30 Update: Aggregate Terminology Harmonized

Replaced residual "robustness aggregate" with "source-stratified supporting aggregate" in two body locations:

- `sections/06_results.tex` — paragraph heading (Results §Aggregate-720 paragraph)
- `tables/table2_source_by_source.tex` — table caption row label

Same changes applied to `submission_applied_intelligence_single_tex/main.tex`.
Zero "robustness aggregate" matches remain in any active source file.
Three occurrences of "source-stratified supporting aggregate" now appear in each source (abstract, paragraph heading, table row).
Both builds compiled: 28 pages, 0 BibTeX errors, 0 unresolved.
Final zip recreated: `applied_intelligence_fta_single_tex_source_20260530.zip`.

---

## 2026-05-30 Update: ECO Precision Wording Softened

Replaced remaining overstrong "high-precision / highly precise" ECO language with cautious
"observed without regressions in this evaluation" phrasing in three locations:

- `main.tex` abstract (ECO description)
- `sections/06_results.tex` — FTA-vs-External-3 paragraph
- `sections/06_results.tex` — Gate-action decomposition paragraph

Same changes applied to `submission_applied_intelligence_single_tex/main.tex`.
Zero matches for "high-precision" or "highly precise" in either source after fix.
Both canonical and single-tex builds compiled: 28 pages, 0 BibTeX errors, 0 unresolved.
Final zip recreated: `applied_intelligence_fta_single_tex_source_20260530.zip`.

---

## 2026-05-30 Update: Reproducibility and Scope Additions

Three low-risk audit-identified improvements applied after the warning/reference cleanup:

**Added independent offline re-derivation row** (`tables/tableA1_reproducibility.tex`):
> "Independent offline re-derivation / complete / Final-300 (86.67%) and Aggregate-720 (80.69%) independently reproduced from raw per-example records using the policy implementation; all stored values confirmed exact / outputs/fta_independent_verification_20260527/"

**Added gold-free leakage audit PASS row** (`tables/tableA1_reproducibility.tex`):
> "Gold-free leakage audit / pass / No gate decision accesses gold labels, exact-match correctness, example identifiers, or artifact paths at runtime; all trigger features are runtime-visible metadata / fta_leakage_and_budget_audit.json"

**Added cautious MATH-500 scope sentence** (`sections/10_limitations.tex`, §Benchmark scope):
> "Preliminary diagnostics on Cohere × MATH-500 suggest that selector-only transfer can fail when the candidate pool changes: in that setting, FTA did not improve over the frontier baseline, and pool-miss cases dominated, reinforcing that benchmark-level replication is required before broader claims."

Both builds after update: 28 pages, 0 BibTeX errors, 0 unresolved references.
Final zip: `applied_intelligence_fta_single_tex_source_20260530.zip` (8 files, 1 .tex, no PDF).

---

## Compile commands used

Both builds use Tectonic 0.16.9 via the `latexmk` shim:

```
tectonic --keep-logs main.tex
```

(The `latexmk` shim wraps Tectonic and handles multi-pass compilation including BibTeX.)

---

## Warnings before cleanup

### BibTeX errors (FIXED — severity: high)

From `main.blg` (canonical source):
```
I was expecting a `,' or a `}'---line 20 of file refs.bib
  eprint = {2205.11916},
(Error may have been on previous line)
I'm skipping whatever remains of this entry

I was expecting a `,' or a `}'---line 33 of file refs.bib
  eprint = {2408.03314},
(Error may have been on previous line)
I'm skipping whatever remains of this entry

Warning--can't use both volume and number fields in besta2024graph
```

- **Entry `kojima2022large`**: Missing comma after `year = {2022}` before the `eprint` field. BibTeX was skipping this entry.
- **Entry `snell2024scaling`**: Missing comma after `url = {...}` before the `eprint` field. BibTeX was skipping this entry.
- **Entry `besta2024graph`**: Had both `volume` and `number` fields; removed `number` to eliminate the warning.

### Underfull `\hbox` warnings (REMAINING — harmless)

All remaining warnings are underfull `\hbox` in `p{}`-column table cells (table3_ablation, table4_policy_rules, table7_negative_results, tableA1_reproducibility, tableA4_parameter_sensitivity, tableA5_feature_legality). These are caused by long verbatim strings in narrow `p{}` columns and cannot be fixed without changing table layout or scientific content. They do not affect PDF output correctness.

### `Object @table.N already defined` (REMAINING — harmless)

These are cosmetic Tectonic/hyperref bookmarking warnings that appear when hyperref creates named anchors for floating environments. They do not affect the PDF output.

---

## Warnings fixed

| Warning | File | Fix applied |
|---------|------|-------------|
| BibTeX error: missing comma | `refs.bib` line 18 (`kojima2022large`) | Added `,` after `year = {2022}` |
| BibTeX error: missing comma | `refs.bib` line 31 (`snell2024scaling`) | Added `,` after `url = {...}` |
| BibTeX warning: volume+number | `refs.bib` (`besta2024graph`) | Removed `number = {16}` field |

---

## Remaining warnings (harmless)

- Underfull `\hbox` in narrow table `p{}` columns — cosmetic, not fixable without altering content
- Tectonic hyperref bookmark duplicates — harmless, artifact of Tectonic's single-pass bookmarking

---

## References added

| Key | Citation |
|-----|---------|
| `mozannar2023who` | Mozannar, Lang, Wei, Sattigeri, Das, Saria. "Who Should Predict? Exact Algorithms for Learning to Defer to Humans." AISTATS 2023, PMLR vol. 206, pp. 10520–10545. |

`geifman2017selectiveclassificationdeepneural` was already present and cited.
`mao2023defer` was already present; added to Mozannar citation in Related Work.

---

## Text changes made

| File | Change |
|------|--------|
| `main.tex` abstract | "robustness aggregate" → "source-stratified supporting aggregate" |
| `sections/02_related_work.tex` | Added 2 sentences connecting FTA to learning-to-defer literature, citing `mozannar2023who` and `mao2023defer` |
| `sections/06_results.tex` | "low-frequency high-precision safeguard in this evaluation" → "low-frequency safeguard that fires without regressions in this evaluation" |
| `sections/10_limitations.tex` | Added new paragraph: "No formal risk-coverage objective" with citations to Geifman and Mozannar |
| `sections/11_conclusion.tex` | "a low-frequency high-precision safeguard in this evaluation" → "a low-frequency safeguard observed without regressions in this evaluation" |

---

## Final compilation status

| Build | Result | Pages | `??` markers | BibTeX errors |
|-------|--------|-------|-------------|---------------|
| Canonical (`paper_applied_intelligence/`) | **success** | 28 | 0 | **0** |
| Single-tex (`submission_applied_intelligence_single_tex/`) | **success** | 28 | 0 | **0** |

---

## Final zip

- **Path:** `applied_intelligence_fta_single_tex_source_20260530.zip`
- **Contents (8 items):**
  - `submission_applied_intelligence_single_tex/main.tex` — single inlined manuscript
  - `submission_applied_intelligence_single_tex/refs.bib` — bibliography (BibTeX errors fixed, Mozannar added)
  - `submission_applied_intelligence_single_tex/svjour3.cls` — Springer journal class
  - `submission_applied_intelligence_single_tex/figure1_fta_method_overview.png`
  - `submission_applied_intelligence_single_tex/figure2_main_quantitative_results.png`
  - `submission_applied_intelligence_single_tex/figure3_gate_activation.png`
  - `submission_applied_intelligence_single_tex/figure4_residual_failure_analysis.png`
- **`.tex` files in zip:** exactly 1
- **`main.pdf` in zip:** no
- **Build artifacts in zip:** none
