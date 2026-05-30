# Submission artifacts — Applied Intelligence (2026-05-30)

Quick reference for which paths are **current**, **visual-only**, or **historical**. Do not upload historical packages to Editorial Manager.

---

## Artifact table

| Path | Role | Upload / use |
|------|------|----------------|
| [`applied_intelligence_fta_single_tex_source_20260530.zip`](../applied_intelligence_fta_single_tex_source_20260530.zip) | **Current APIN LaTeX source package** (single `main.tex`, no PDF) | **Use this** for Editorial Manager source upload |
| [`submission_applied_intelligence_single_tex/`](../submission_applied_intelligence_single_tex/) | Unzipped current source package (7 files) | Reproducibility / local compile; mirror of zip contents |
| [`applied_intelligence_fta_final_visual_check_20260530.pdf`](../applied_intelligence_fta_final_visual_check_20260530.pdf) | Visual-check PDF (28 pages) | Human review only; **not** inside source zip |
| [`paper_applied_intelligence/`](../paper_applied_intelligence/) | Canonical **multi-file** manuscript source | Editorial development; not the portal upload package |
| [`archive/submission_applied_intelligence_20260530/`](../archive/submission_applied_intelligence_20260530/) | Archived **old** APIN packages (20260528 flat/multi-tex) | **Do not upload** — provenance only |
| `submission_applied_intelligence_flat/` (if still referenced) | Superseded flat multi-`.tex` tree | **Do not upload** — see archive |
| `applied_intelligence_fta_*_20260528.zip` | Superseded multi-`.tex` zips | **Do not upload** — see archive |
| [`paper_ml_journal/`](../paper_ml_journal/) | MLJ manuscript (historical) | Not current APIN submission |
| [`paper_ml_journal_snjnl_stage/`](../paper_ml_journal_snjnl_stage/) | MLJ sn-jnl staging (historical) | Not current APIN submission |
| [`submission_package/`](../submission_package/) | MLJ final upload bundle (historical) | Not current APIN submission |

---

## Final zip contents (expected)

The committed zip `applied_intelligence_fta_single_tex_source_20260530.zip` contains **exactly eight entries**:

- `submission_applied_intelligence_single_tex/main.tex` — **only** `.tex` file
- `submission_applied_intelligence_single_tex/refs.bib`
- `submission_applied_intelligence_single_tex/svjour3.cls`
- Four figure PNGs (`figure1` … `figure4`)

**Must not contain:** `main.pdf`, other `.tex` fragments, build artifacts (`.aux`, `.log`, …), MLJ admin files, or notes.

---

## Why old packages were archived

Applied Intelligence returned the first upload because **multiple `.tex` files** were present; Editorial Manager compiled extra fragments into the PDF. The **20260530** package inlines all content into one `main.tex`. Older flat and 20260528 zips are kept under `archive/submission_applied_intelligence_20260530/` for provenance only.

Details: [`APIN_SENT_BACK_RESUBMISSION_PACKAGE_20260530.md`](APIN_SENT_BACK_RESUBMISSION_PACKAGE_20260530.md)

---

## Related documentation

- [`APIN_WARNING_REFERENCE_CLEANUP_20260530.md`](APIN_WARNING_REFERENCE_CLEANUP_20260530.md) — last reference/wording fixes before resubmission
- [`PROJECT_STATUS.md`](../PROJECT_STATUS.md) — repository front door
- [`OUTPUT_INDEX_20260528.md`](OUTPUT_INDEX_20260528.md) — canonical experiment output directories
