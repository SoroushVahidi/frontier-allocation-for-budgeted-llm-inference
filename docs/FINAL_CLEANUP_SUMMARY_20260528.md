# Final Cleanup Summary — 2026-05-28

**Cleanup pass 3 (final) completed:** 2026-05-28  
**Commit:** see docs/PROJECT_PAUSE_STATE_20260528.md for final hash  
**Branch:** `main`

---

## What Was Deleted

### SetFit / Relation-Verifier ML Outputs (~40.1 GB freed)

These were from a mid-May 2026 experiment using SetFit (sentence-transformer fine-tuning)
for a relation-verifier task. The project pivoted completely away from this approach.
Not referenced in any docs, manuscript, or evidence chain.

| Dir | Size |
|---|---|
| `outputs/relation_verifier_setfit_tuning_20260516_20260517T000951Z/` | 31GB |
| `outputs/relation_verifier_setfit_mpnet_train_20260516T233217Z/` | 6.2GB |
| `outputs/relation_verifier_setfit_mpnet_heldout_sanity_20260517T023803Z/` | 1.3GB |
| `outputs/relation_verifier_setfit_mpnet_train_20260516T232041Z/` | 1.3GB |
| `outputs/relation_verifier_setfit_mpnet_train_20260516T231744Z/` | 12KB |
| `outputs/relation_verifier_setfit_mpnet_train_20260516T231924Z/` | 8KB |
| `outputs/relation_verifier_setfit_mpnet_train_20260516T232009Z/` | 8KB |
| `outputs/relation_verifier_setfit_mpnet_dryrun_20260516T231734Z/` | 12KB |
| `outputs/relation_verifier_setfit_cfg1_ci_analysis_20260517T025701Z/` | 16KB |

### TMUX Audit Snapshot (1.5 GB freed)

| Dir | Size |
|---|---|
| `outputs/completed_tmux_jobs_audit_20260524/` | 1.5GB |

### Dry-run / No-key / Test Dirs (~0.7 MB freed)

- `outputs/cohere_real_model_cost_normalized_validation_20260527T013{350,417,451}Z/` — 3 aborted runs
- `outputs/cohere_coverage_generation_ablation_TEST_COHERE_COVERAGE_{DRY,NO_KEY}/`
- `outputs/cohere_direct_reserve_validation_TEST_DIRECT_RESERVE_NO_KEY/`
- `outputs/adaptive_router_v3_dry_run_20260508T025{218,305}Z/`
- `outputs/direction_combinatorics_guard_eval_20260425T_*_TEST_DRY/`
- `outputs/direct_reserve_candidate_scorer_eval_PTEST/`
- `outputs/direct_reserve_candidate_scorer_validation_audit_PTEST/`
- `outputs/direct_reserve_gate_rerank_eval_20260425T_*_TEST_DRY/`
- `outputs/family_normalized_rerank_eval_20260425T_*_TEST_DRY/`
- `outputs/strategy_seeded_discovery_final_check_TESTPREFLIGHT_20260502T224848Z/`
- `outputs/typed_strategy_seeded_eval_20260425T_*_TEST_DRY/`
- `outputs/non_math_external_validity_TESTNONMATH20260424T000000Z/`
- `outputs/bounded_real_trace_learned_scorer_eval_20260425T_TRACE_EVAL_REQUIRED_TEST/`

### Root Clutter Removed

- 6 tracked UUID root PNG screenshots (iOS screenshots, no references anywhere):
  `77CF6228-*.png`, `7BB51D06-*.png`, `8A550AC1-*.png`, `A28473BC-*.png`,
  `A4569A96-*.png`, `AC3C98E0-*.png` — removed with `git rm`
- 18 manuscript `.bak_*` files in `paper_applied_intelligence/` — already gitignored

### Worktrees Removed

| Worktree | Branch | State | Action |
|---|---|---|---|
| `.claude/worktrees/cheerful-giggling-star` | worktree-cheerful-giggling-star | Clean | `git worktree remove` |
| `.claude/worktrees/embedding-baseline` | worktree-embedding-baseline | Clean | `git worktree remove` |
| `.claude/worktrees/shimmering-greeting-squirrel` | 82b5912a | DIRTY — 1-line PRM doc change | Diff archived; `git worktree remove --force` |
| `/tmp/fa_feat_verify_20260520T1912` | Detached HEAD | Clean | `git worktree remove` |
| `/tmp/fa_merge_main_20260520T1910` | codex/merge-main-20260520 | Clean | `git worktree remove` |
| `/tmp/wording-worktree` | polish-availability | DIRTY — MLJ table longtable conversion | Diff archived; `git worktree remove --force` |

Archived diffs: `docs/archived_worktree_diffs_20260528/`

**Total space freed: ~42 GB**

---

## What Was Protected

All of the following were verified to exist after cleanup:

| Category | Key paths |
|---|---|
| Canonical FTA validation | `outputs/final_fix24_all_external_validation_*/` |
| FTA independent verification | `outputs/fta_independent_verification_20260527/` |
| D9 canonical evidence | `outputs/job_d9_retrain_with_mistral_20260526/` |
| Cohere MATH-500 official | `outputs/cohere_math500_official_scenario4_20260524/` |
| MATH-500 failure pool audit | `outputs/math500_cohere_failure_pool_audit_20260528/` |
| FTA-CG diagnosis | `outputs/fta_cg_transfer_failure_analysis_20260528/` |
| MATH-500 mining data | `outputs/local_failure_workbench_20260525/` |
| Applied Intelligence source | `paper_applied_intelligence/main.tex`, `refs.bib`, `main.pdf` |
| Submitted package | `submission_applied_intelligence_flat/` |
| Clean EM upload zip | `applied_intelligence_fta_clean_latex_source_20260528.zip` (local, gitignored) |
| D6/D8/D9/router future research | ~30 output dirs (see `docs/OUTPUT_INDEX_20260528.md`) |

---

## Remaining Dirty State (Expected, Normal)

- **91 modified tracked output files** — all in pre-.gitignore-era whitelisted output dirs
  (`paper_figures/`, `paper_tables/`, `branch_label_bruteforce/`, `TEST_*`, etc.).
  Leave dirty. Do not revert or commit.
- **~430 untracked output dirs** — all research/diagnostic artifacts from May 2026.
  Leave local. Classified in `docs/OUTPUT_INDEX_20260528.md`.

---

## First Steps When Resuming

1. `git pull origin main` — sync any remote changes
2. Read `docs/PROJECT_PAUSE_STATE_20260528.md` (this file's sibling)
3. Read `docs/CURRENT_CANONICAL_STATE_20260527.md` — canonical evidence
4. Run `python3 -m pytest tests/ --collect-only -q` — verify test suite
5. Start with **MATH-500 selector rule mining** — 300 canonical examples ready in:
   `outputs/local_failure_workbench_20260525/generalization_replay_20260524T220438/official_four_scenario_case_level_replay.csv`
6. Before any new Cloudrift generation: fix Qwen prompt (move JSON schema to system message)

---

## Gitignore Pattern Fixed

Pass 2 added `applied_intelligence_fta_*_latex_*.zip` which did not match both files.
Pass 3 fixed to `applied_intelligence_fta_*latex*.zip` — broader pattern that correctly
covers both `applied_intelligence_fta_clean_latex_source_*.zip` and
`applied_intelligence_fta_latex_submission_*.zip`.
