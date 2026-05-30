# Project status

**Repository:** Frontier Allocation for Budgeted LLM Inference  
**Last updated:** 2026-05-31  
**Branch:** `main`

---

## What this project is

This repository studies **budgeted LLM inference**: how to spend a fixed inference budget across reasoning branches and how to **select a final answer** from a fixed candidate pool (frontier + external baselines) without gold labels at runtime. The main method is the **Failure-Trace Allocator (FTA)**—a deterministic, gold-free policy that applies **selective deferral** using logged frontier metadata and external-consensus signals (implementation: FIX-2 + FIX-4 in `experiments/support_aware_selector.py`).

---

## Paper status (Applied Intelligence)

The **Applied Intelligence** manuscript has been **submitted** after a technical resubmission fix: the publisher required a **single self-contained `.tex` file** (multiple `.tex` fragments had been merged incorrectly in Editorial Manager). The corrected package is on `main` and documented below.

**Do not use for upload:** old multi-tex / flat packages from **2026-05-28** or `submission_applied_intelligence_flat/`—they can cause merged-PDF compile issues. See [`docs/SUBMISSION_ARTIFACTS_20260530.md`](docs/SUBMISSION_ARTIFACTS_20260530.md).

---

## Correct Applied Intelligence artifacts (use these)

| Role | Path |
|------|------|
| **Editorial Manager LaTeX source upload** | [`applied_intelligence_fta_single_tex_source_20260530.zip`](applied_intelligence_fta_single_tex_source_20260530.zip) |
| **Unzipped source package** (reproducibility) | [`submission_applied_intelligence_single_tex/`](submission_applied_intelligence_single_tex/) |
| **Visual-check PDF** (not inside source zip) | [`applied_intelligence_fta_final_visual_check_20260530.pdf`](applied_intelligence_fta_final_visual_check_20260530.pdf) |
| **Canonical multi-file manuscript source** | [`paper_applied_intelligence/`](paper_applied_intelligence/) |

Package build notes: [`docs/APIN_SENT_BACK_RESUBMISSION_PACKAGE_20260530.md`](docs/APIN_SENT_BACK_RESUBMISSION_PACKAGE_20260530.md) · wording/reference fixes: [`docs/APIN_WARNING_REFERENCE_CLEANUP_20260530.md`](docs/APIN_WARNING_REFERENCE_CLEANUP_20260530.md)

---

## Main verified result (FTA)

| Metric | Value | Notes |
|--------|-------|--------|
| Final-300 | **86.67%** (260/300) | Cohere × GSM8K, seed 71, budget 6 |
| Aggregate-720 | **80.69%** (581/720) | Seeds 41 + 61 + 71, disjoint |
| vs Pooled-4 ensemble | Point estimate lead only | Bootstrap CI **includes zero**—not statistically separated |
| Full candidate pool | **24 logical calls** / example | 4 methods × budget 6; FTA adds **0** post-generation calls |
| Seed 61 stratum | 59.17% | **Failure-enriched**—not a typical IID holdout |

Independent offline re-derivation and gold-free leakage audit: **pass** (see manuscript appendix / Table A1).

Full evidence and claim boundaries: [`docs/CURRENT_CANONICAL_STATE_20260527.md`](docs/CURRENT_CANONICAL_STATE_20260527.md) · [`docs/LATEST_RESULTS_AND_CLAIMS.md`](docs/LATEST_RESULTS_AND_CLAIMS.md)

---

## Research status

**Paused** after Applied Intelligence submission. No API calls are required for the documented canonical numbers.

**Next step (when resuming):** **MATH-500 selector rule mining** using existing fully tracked Cohere MATH-500 artifacts—offline analysis first; no API needed for initial mining.

---

## Where to start

| Audience | Start here |
|----------|------------|
| Newcomer / GitHub visitor | This file → [`README.md`](README.md) → [`docs/SUBMISSION_ARTIFACTS_20260530.md`](docs/SUBMISSION_ARTIFACTS_20260530.md) |
| Reproduce FTA claims | [`REVIEWER_FIRST.md`](REVIEWER_FIRST.md) → [`docs/CURRENT_CANONICAL_STATE_20260527.md`](docs/CURRENT_CANONICAL_STATE_20260527.md) |
| Navigate large `outputs/` | [`docs/OUTPUT_INDEX_20260528.md`](docs/OUTPUT_INDEX_20260528.md) |
| Agent / automation | [`START_HERE_CURRENT.md`](START_HERE_CURRENT.md) · [`AGENTS.md`](AGENTS.md) |

---

## Pause and cleanup history

Project pause and disk cleanup (2026-05-28): [`docs/PROJECT_PAUSE_STATE_20260528.md`](docs/PROJECT_PAUSE_STATE_20260528.md) · [`docs/FINAL_CLEANUP_SUMMARY_20260528.md`](docs/FINAL_CLEANUP_SUMMARY_20260528.md)
