# PR #324 review audit — external-loss artifact transfer

- **PR:** https://github.com/SoroushVahidi/frontier-allocation-for-budgeted-llm-inference/pull/324  
- **Base:** `main` — **Head:** `chore/local-outputs-snapshot-20260501`  
- **Audit date:** 2026-05-01 (UTC)  
- **Method:** Local `git diff origin/main...origin/chore/local-outputs-snapshot-20260501` (GitHub `gh pr diff` returned HTTP 406: &gt;300 files). No experiments, APIs, or regeneration.

## 1. PR metadata (from `gh pr view 324`)

| Field | Value |
|-------|--------|
| State | OPEN |
| Draft | false |
| Mergeable | **MERGEABLE** |
| Changed files | **3274** |
| Additions (lines) | **373462** |
| Deletions (lines) | **0** |

## 2. Size check (working tree files in the PR file list)

| Metric | Value |
|--------|------:|
| Files listed | 3274 |
| All paths resolved on disk | yes (0 missing) |
| **Sum of file sizes** | **37 312 949 bytes (~35.6 MiB)** |
| Largest file | `outputs/family_normalized_rerank_eval_20260425T_FAMILY_NORMALIZED_RERANK_FULL_DRYRUN/per_case_results.csv` — **1 780 708 bytes (~1.70 MiB)** |
| Files **&gt; 20 MiB** | **0** |
| Files **&gt; 100 MiB** (GitHub hard limit) | **0** |

**Largest 20 files (bytes, path):** see generator log; top includes family-normalized rerank CSVs, `real_model_fixed_budget_heavy/.../results.json`, `detailed_loss_case_package_.../all_paired_cases.csv`, semantic-diversity `per_case_results.csv`, `slurm_logs/...1013340.out`.

**GitHub / LFS:** No blob exceeds 100 MiB; no LFS requirement for size alone. Line-count additions are large because of many text/CSV/JSON rows, not because of giant binaries.

## 3. High-priority package: `strict_f3_vs_external_l1_max_more_loss_cases_20260425T_WULVER_COHERE_LONG`

**Present in PR (6 paths):**

- `README.md`
- `loss_cases_for_manual_inspection.md`
- `loss_cases_strict_f3_wrong_external_correct.csv`
- `matched_examples.csv`
- `rich_feature_table.csv`
- `summary.json`

**On disk but not in PR (`.gitignore` — `outputs/**/*.jsonl`):**

- `loss_cases_strict_f3_wrong_external_correct.jsonl`
- `matched_examples.jsonl`
- `rich_feature_table.jsonl`

**CSV / JSON summary:**

| File | Rows | Notes |
|------|-----:|-------|
| `loss_cases_strict_f3_wrong_external_correct.csv` | **150** | 25 columns including `strict_f3_correct`, `external_l1_max_correct` |
| `matched_examples.csv` | **720** | same column family |
| `rich_feature_table.csv` | **150** | same column family |
| `summary.json` | — | `strict_f3_wrong_external_correct`: **150**, `matched_examples`: **720**, seeds `[11,23]`, budgets `[4,6,8]` |

**Row semantics (key CSV):** All **150** rows satisfy `strict_f3_correct == 0` and `external_l1_max_correct == 1` (definition of this extract).

**Related Wulver detail bundle in PR:** `outputs/detailed_loss_case_package_20260425T_WULVER_COHERE_LONG_DETAIL/all_paired_cases.csv` — **720** rows; **150** rows with `strict_f3_correct == 0` and `external_l1_max_correct == 1` (consistent with strict_f3 package).

## 4. Categorization of changed paths (heuristic)

Order of rules: strict_f3 → external loss casebook strings → trace_complete → cohere DR validation → semantic diversity → absent-from-tree → selector/gold → best_methods → docs/logs → unknown.

| Category | Approx. file count |
|----------|-------------------:|
| `semantic_diversity_diagnostic` | 1062 |
| `unknown` (see breakdown below) | ~1980 |
| `trace_complete_loss_bundle` | 100 |
| `cohere_direct_reserve_validation` | 86 |
| `absent_from_tree_loss_diagnostic` | 22 |
| `logs` | 16 |
| `strict_f3_vs_external_l1_max_loss_package` | 6 |
| `docs` | 2 |
| `external_loss_casebook` | 0 in diff (already on `main` pre-PR) |
| `selector_loss_or_gold_present` | 0 in diff |
| `best_methods_on_external_losses` | 0 in diff |

**Top `outputs/` top-level directories by file count in this PR:** `semantic_diversity_controller_diagnostic_*` (hundreds), `real_model_fixed_budget_heavy` (144), `branch_scorer_v3_heavy_ml` (99), `anonymization_audit`, `new_paper_frontier_matrix`, `trace_complete_external_losses_smoke_*`, `canonical_real_model_validation_*`, etc.

**Interpretation:** The PR is **not** only “external-loss” artifacts; it is a **broad snapshot** of many experiment trees. Semantic-diversity and real-model fixed-budget trees dominate the diff.

## 5. Caches / logs / jsonl in PR

- **`*.jsonl` in PR file list:** **0** (policy: blanket ignore under `outputs/**/*.jsonl` unless whitelisted).
- **`*.log` in PR:** **16** (mostly under `outputs/slurm_logs/`).
- **Risky extensions** (`.tar.gz`, `.pem`, `.key`, etc.): **0** in the PR file list.

## 6. Potentially unnecessary or risky content (judgment)

- **Volume / focus drift:** ~**1980** files fall in the generic “unknown” bucket—mostly canonical validation matrices, branch-scorer heavy ML, paper frontier matrix, integrated ablations, etc. These are **not** all “external baseline beats us” narratives; merging as-is bloats `main` with unrelated historical runs.
- **`real_model_fixed_budget_heavy`:** Many `manifest.json` / `results.json` contain **boolean** flags like `"OPENAI_API_KEY": true` (environment present), not secret strings—see secrets section.
- **No binary model archives** detected in this PR list (large `.tar.gz` caches were excluded at commit time per prior snapshot rules).

## 7. Intentionally not added (per `docs/ARTIFACTS_MISSING_FROM_MAIN_INVENTORY_20260501.md`)

- **65** disk-only paths (mostly **`*.jsonl`**, **caches**, **`*.log`**, **`cohere_annotation_cache.jsonl`**) remain **ignored** and are listed in the inventory doc. They are **not** in this PR.

## 8. Inventory doc consistency

File: `docs/ARTIFACTS_MISSING_FROM_MAIN_INVENTORY_20260501.md`

| Claim in doc | Present |
|--------------|---------|
| 894 relevant local files | yes (table “Relevant local files”) |
| 551 not on `origin/main` | yes |
| 486 branch-only vs `main` | yes |
| 65 disk-only ignored | yes |
| High-priority subtree table | yes |
| `strict_f3_vs_external_l1_max_more_loss_cases_...` section | yes |

**Note:** The inventory header still records **`HEAD` `0f52949`**; the branch later advanced to **`e2d89f3`** when the inventory file was committed. Counts refer to the scan at inventory generation time.

**Inventory file in PR:** **yes** — `docs/ARTIFACTS_MISSING_FROM_MAIN_INVENTORY_20260501.md` is part of the branch.

## 9. Secrets scan

Patterns: `COHERE_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `sk-[A-Za-z0-9]{20,}`, Bearer tokens, `api_key:`, `authorization:`, `x-api-key:` — over all PR files **&lt; 20 MiB**.

**Result:**

- **~109** files matched **key name** substrings (e.g. JSON fields `openai_api_key_present`, markdown discussing `OPENAI_API_KEY`, inventory text listing `cohere_api_key_issue.md`, anonymization audit prose). **No raw `sk-…` API key strings** found (`sk-` pattern scan over &lt;5 MiB files: **0** hits).
- **Conclusion:** Matches are **metadata / documentation / boolean presence flags**, not pasted credentials. **No merge block** for secrets based on this scan.

## 10. Tests

| Command | Result |
|---------|--------|
| `pytest -q tests/test_inventory_trace_artifacts.py` | **Skipped** — file **not present** in repo |
| `pytest -q tests/test_enrich_focused33_with_candidate_traces.py tests/test_selector_on_gold_present_losses.py tests/test_answer_grouped_outcome_verifier.py` | **25 passed** |

## 11. Recommendation

- **Safety / size / secrets:** **OK to merge** from a blob-size and credential-scan perspective (all files &lt; 100 MiB; no `sk-` secrets found).
- **Scope:** The PR is a **large mixed snapshot**; only a **small fraction** is the strict_f3 vs `external_l1_max` Wulver loss package. **If the goal is narrowly “external-loss artifacts,”** consider a **follow-up PR** that trims or relocates non-loss trees—or accept this as a one-time bulk archive.
- **Process:** **Do not merge** in this audit unless maintainers explicitly approve scope.
