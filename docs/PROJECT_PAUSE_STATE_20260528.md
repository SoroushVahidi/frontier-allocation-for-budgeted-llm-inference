# Project Pause State — 2026-05-28

**Pause date:** 2026-05-28  
**Branch:** `main`  
**HEAD commit (at pause):** `ad9cbe09` — *repo: checkpoint project state before pause*  
**Origin in sync:** YES

> **Cleanup pass 2 (same date):** Added `.gitignore` pattern for Applied Intelligence submission zips (`applied_intelligence_fta_*_latex_*.zip`); pruned 3 stale worktree references whose directories were already missing. No scientific content changed.

Read `docs/CURRENT_CANONICAL_STATE_20260527.md` for the full evidence summary.  
Read `docs/LATEST_RESULTS_AND_CLAIMS.md` for the safe/unsafe claim list.

---

## 1. Canonical FTA Result (LOCKED — do not re-derive)

| Metric | Value | Seed | N |
|---|---|---|---|
| Final-300 accuracy | **86.67%** (260/300) | 71 | 300 |
| Aggregate-720 accuracy | **80.69%** (581/720) | 41+61+71 | 720 |
| Leakage audit | **PASS** | — | — |
| Post-generation model calls | **0** | — | — |
| FIX-2 fires / wins / losses | 63 / 36 / 9 | — | — |
| FIX-4 fires / wins / losses | 3 / 3 / 0 | — | — |

Implementation: `experiments/support_aware_selector.py` → `apply_combined_fix24_to_row()`

Verification artifact: `outputs/fta_independent_verification_20260527/run_20260527T003000Z/`

**Required disclosures in paper (do not omit):**
1. CI vs pooled ensemble includes zero: Final-300 [−0.67, +5.67]; Agg-720 [−1.11, +2.78]
2. Full pool generation = 4×B=6 = 24 logical calls per example
3. Seed=61 (59.17%) is failure-enriched, not a random sample
4. Scope: Cohere × GSM8K only

---

## 2. Applied Intelligence Manuscript Status

| Item | Status |
|---|---|
| Primary source | `paper_applied_intelligence/main.tex` |
| Current PDF | `paper_applied_intelligence/main.pdf` — **28 pages** |
| LaTeX errors | None (2 minor warnings: inputenc, unused global option) |
| Conflict markers | None |
| Submitted flat folder | `submission_applied_intelligence_flat/` (tracked in repo, commit `e74758fe`) |
| Clean source zip | `applied_intelligence_fta_clean_latex_source_20260528.zip` (root, NOT committed, `.gitignore`d) |
| Full submission zip | `applied_intelligence_fta_latex_submission_20260528.zip` (root, NOT committed) |

**If Editorial Manager requires a re-upload of source:** use `applied_intelligence_fta_clean_latex_source_20260528.zip` — it is source-only (48 files, no `main.pdf`, no MLJ files, no auxiliary `.tex` wrappers). Do NOT re-upload `submission_applied_intelligence_flat.zip` as source — it contains `mlj_contribution_information_sheet.tex` and will cause the ~75-page EM merged PDF issue.

---

## 3. Supporting Evidence

### D9 Gated Selector
- **Verdict:** D9_MISTRAL_RETRAIN_USE_D6_AS_GATED_MODULE
- CV accuracy: **50.18% ± 2.52%** vs frontier 34.36% (+15.82pp); 5-fold grouped CV
- False overrides: **0** across thresholds 0.3–0.8
- D6 standalone: **negative** (net=−38 across 550 pools); gate is required
- Artifact: `outputs/job_d9_retrain_with_mistral_20260526/run_20260526T234411Z/`
- 550 D6 pools (Cohere=320, Cloudrift=80, Mistral=150); 14,150 training rows

### Cloudrift/Qwen Extraction Repair
- **Verdict:** D9-ready with current data; prompt fix required before new generation
- Lenient extraction: **98.8%** (79/80); D6 lenient accuracy 55.0% vs frontier 37.5%; 0 regressions
- Root cause: Qwen echoes JSON schema in CoT → move schema to system message before new API calls
- Artifact: `outputs/job_cloudrift_qwen_extraction_repair_20260526/run_20260527T002012Z/`

---

## 4. FTA-CG (Corroboration Guard) — OVERFIT RULE / DO NOT IMPLEMENT

- **Verdict: OVERFIT_RULE** — do not add to production
- Discovery: +1.43pp on MATH-500 seed=11 (in-sample)
- Disjoint validation: **+0.00pp** (5 wins, 5 losses) on MATH-500 seed=71
- Why: guard is not discriminating — it inherits the frontier baseline accuracy rate; 1-of-3 corroboration has no predictive signal distinguishing wins from losses
- Why it appears to work on GSM8K: frontier is 79–87% accurate on GSM8K; suppressing FIX-2 preserves a mostly-correct frontier by chance
- Artifact: `outputs/fta_cg_transfer_failure_analysis_20260528/README.md`
- Commit: `727e5c97`

---

## 5. Cohere MATH-500 Failure Pool Audit

- **Artifact:** `outputs/math500_cohere_failure_pool_audit_20260528/`
- **Commit:** `5b780df8`

| Item | Value |
|---|---|
| Total fully tracked unique examples | **498** (300 seed-71 official + 488 seed-11 auxiliary, 290 overlap) |
| Canonical (seed-71) examples | **300** (297 fully complete; 3 frontier failures) |
| Selector-fixable cases (oracle_ok) | **135** (seed-71) |
| FTA-wrong / pool-correct cases | **48** (using `fta_selected_answer`); **36** (using `agreement_only`) |
| Frontier-correct / FTA-wrong regressions | **0** — FTA never successfully overrides frontier on MATH-500 |
| "20 inspected" source | `agreement_only_recovers_vs_pooled4_cases.csv` — inspection subset only; 300 raw examples exist |
| All-sources-wrong (pool failure) | 165/300 = 55.0% — unfixable by selector changes alone |
| Oracle ceiling (any source correct) | 135/300 = 45.0% |
| Agreement_only accuracy | 99/300 = 33.0% — best non-oracle selector |
| For ≥1500-case meta-router training | Need ~1000 more; current = 498 unique |

---

## 6. Pending Next Research Steps (Priority Order)

### Immediate (no API needed)
1. **MATH-500 selector rule mining** — 300 fully tracked canonical examples exist; discover structural rules from the 135 oracle-ok cases; use `outputs/local_failure_workbench_20260525/generalization_replay_20260524T220438/official_four_scenario_case_level_replay.csv`
2. **Commit remaining untracked docs/scripts/tests** if not done in this pass

### Requires API calls
3. **Cloudrift Qwen prompt fix + new generation** — move JSON schema to system message, then generate fresh D6 rows for the rescue bucket
4. **Mistral targeted D6 rescue** — expand the Mistral rescue bucket cases
5. **D9 refresh** — incorporate repaired Cloudrift extraction (6 additional correct labels)
6. **D8.1 independent validation on Mistral × GSM8K** — if pursuing broader coverage

### Paper (if revisions requested)
7. Use `applied_intelligence_fta_clean_latex_source_20260528.zip` for any EM source re-upload
8. Do not change canonical FTA numbers without re-running the verification pipeline

---

## 7. What NOT to Touch When Returning

| Item | Reason |
|---|---|
| `outputs/final_fix24_all_external_validation_*/` | Canonical FTA evidence — do not modify |
| `outputs/fta_independent_verification_20260527/` | Independent verification record |
| `paper_applied_intelligence/main.tex`, `refs.bib` | Live submission source |
| `submission_applied_intelligence_flat/` | Represents what was submitted to the journal |
| FTA Final-300 / Agg-720 numbers | Independently verified; do not re-derive without full pipeline |
| `applied_intelligence_fta_clean_latex_source_20260528.zip` | Keep as the safe re-upload artifact |

---

## 8. First Actions When Returning

1. `git pull origin main` — sync with any remote changes
2. Read this file and `docs/CURRENT_CANONICAL_STATE_20260527.md`
3. Run `python3 -m pytest tests/ --collect-only -q` to verify test suite still collects
4. Pick up at **MATH-500 selector rule mining** (first no-API priority)
5. Check Cloudrift prompt fix status before any new Cloudrift generation

---

## 9. Dirty File Summary (at pause)

| Category | Count | Action needed |
|---|---|---|
| Modified output files (pre-.gitignore era) | 91 | None — leave in place |
| Modified experiments file | 1 | Committed in this pass |
| Untracked docs | ~56 | Committed in this pass |
| Untracked scripts | ~42 | Committed in this pass |
| Untracked tests | ~16 | Committed in this pass |
| Untracked output dirs (May 24–28) | ~447 | Not committed — large artifacts |
| .bak files in paper_applied_intelligence/ | 18 | Leave for now; not tracked |
