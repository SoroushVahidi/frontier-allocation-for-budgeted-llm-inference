# Instructions for AI Agents

Welcome to the `frontier-allocation-for-budgeted-llm-inference` repository. To maintain research integrity and repository health, please follow these guidelines.

## Development Workflow
1. **Respect the active project branch**: In this project, the active working branch is usually `feat/missing-gold-topology-v1` unless the user says otherwise. Do not switch to `main` unless explicitly instructed.
2. **Inspect before changing**: Before source changes, check `git status --short`, `git branch --show-current`, and, when appropriate, `python3 scripts/check_repo_health.py`.
3. **Commit/push when appropriate**: When source/tests/docs change, run relevant tests and the repo health check. If clean, stage only intended source/tests/docs, commit with a clear message, and push to the active branch.
4. **Never stage local artifacts**: Do not stage or commit `outputs/`, `.claude/`, caches, bytecode, `.env`, secrets, or unrelated files.
5. **Output-only runs stay local**: When only outputs are generated, do not commit. Report output directories, key metrics, and safety status.
6. **Test coverage**: Add or update tests in `tests/` for algorithmic changes. Use mocks/dry-runs to avoid API calls unless the user explicitly approves provider/API use.

## Safety & Cost Guardrails
1.  **NO PAID API CALLS**: Do not run any commands that call paid LLM APIs (OpenAI, Cohere, etc.) without explicit user approval.
2.  **Use Artifacts for Analysis**: Prefer analyzing existing JSONL/CSV outputs in `outputs/` or `docs/project_handoff_20260510/` instead of running new experiments.
3.  **Preserve Provenance**: Do not delete or overwrite existing output files in `outputs/` unless specifically asked. They are essential for reproducibility.
4.  **Preserve current evidence hierarchy**: The primary evidence is the **aggregate-720 FIX-2+FIX-4 result** (581/720 = 80.69%) and the **final-300 result** (260/300 = 86.67%). The old 300-case PAL+retry bundle (252/300 vs 244/300, p≈0.322) is historical background only and is not the headline result. FIX-5, FIX-6/LoVEC, FIX-7, and FIX-8 were tested and **not promoted**.
5.  **Read the canonical results doc first**: After `README.md`, read `docs/LATEST_RESULTS_AND_CLAIMS.md` before interpreting any outputs or planning new work. `docs/CURRENT_STATE_SUMMARY_20260511.md` is historical background (pre-FIX series) and should not be treated as the current canonical state.

## Research Integrity
1.  **No Unsubstantiated Claims**: Do not claim a method is "better" or "beats the baseline" based on small samples or proxy audits alone. Use the term "potentially recoverable" for artifact-based improvements.
2.  **Baseline Consistency**: The `external_l1_max` baseline is the current gold standard. Any claims of improvement must be measured against it using canonical evaluation scripts.
3.  **Avoid Legacy Patterns**: Do not use old "strict_f3" or "v0" controller configurations. Follow the patterns in `experiments/controllers.py` used by the `production_equiv_v1` method.
4.  **Do not mix evidence tiers**: Do not confuse strict-method diagnostics with PAL+retry evidence, and do not confuse the 15-case Direct L1 strong-seed result with the 300-case main bundle.
5.  **Do not overread structural replay**: The `pal_frontier_structural_target_replay_v1` offline replay is useful for structural analysis and logging, but it is not runtime promotion evidence until interpreted and validated.

## Next Research Focus
The current priority is **paper write-up** for the FIX-2+FIX-4 result.

Completed phases:
- RelationReady verifier training: closed. Selected verifier: SetFit `all-mpnet-base-v2` cfg1 (ready-F1=0.8646, PR-AUC=0.883). Within-method reranking validated (+4.58pp, cluster-CI lower bound +0.28pp). Cross-method routing was method-entangled; not promoted.
- Stage-2 calibrated gate: evaluated; safe-gate holdout gain neutral; not promoted.
- FIX-1 through FIX-8: all evaluated. FIX-2+FIX-4 promoted; all others not promoted.
- Aggregate-720 evidence assembled from 3 disjoint sources (seeds 41, 61, 71). Decision A (begin write-up) recorded.
- Paper manuscript in progress: `paper_ml_journal/` (MLJ format, 11 sections, 9 tables).

Current priorities:
1. Complete `paper_ml_journal/` manuscript: finalize figures from CSV data, replace placeholder references in `refs.bib`.
2. Keep provider prompts gold-free; gold/exact_match is offline evaluation only.
3. Use no-API dry-runs and manifests before any paid/API generation.
4. Use tmux for long/API jobs.
5. Do not overclaim FIX-5/6/7/8 improvements — they were tested and not promoted.

## Codex Session Defaults
These defaults should be applied for future Codex sessions in this repository unless the user explicitly overrides them.

1. **Access / permission default**
   - Prefer the broadest safe workspace access available for this repository by default.
   - Prefer full read/write access to the repository workspace when supported.
   - Do **not** modify secrets, `.env` files, credentials, SSH keys, API keys, or unrelated system files.
   - If the environment exposes formal approval/sandbox settings, use the most permissive safe setting available only when appropriate.

2. **Instruction-file shortcut**
   - If the user message is only a filename/path (for example `task.txt`, `instructions.md`, `/tmp/file.txt`), treat it as an instruction-file reference.
   - Search for that file in this order:
     a. exact path provided (absolute or relative),
     b. current working directory,
     c. repository root,
     d. parent directory of repository root,
     e. `/tmp/`,
     f. `/mnt/data/` (if it exists).
   - If found, read it fully and follow it.
   - Do not ask the user to paste file contents unless the file cannot be found or cannot be read.
   - If multiple matching files exist, use the closest one to the current working directory and report which file was used.

   ### Instruction-file cleanup
   - If the user message is only a filename/path to an instruction file, and the file is found, read, and successfully executed, Codex may delete that instruction file after completion only if **all** conditions below are true:
     1. The file is untracked by git.
     2. The file is not under `docs/`, `scripts/`, `tests/`, `outputs/`, `.git/`, or any source/project directory.
     3. The file is not a config file, credential, secret, `.env`, SSH key, API key, persistent project note, or research artifact.
     4. The file appears to be a temporary one-off instruction file, usually in `/home/soroush/`, `/tmp/`, or another scratch location.
     5. The file extension is a plain instruction-like text/markdown extension such as `.txt`, `.md`, or `.instructions`.
     6. Deleting it will not delete generated outputs, logs, data, code, docs, or research artifacts.
   - If any condition is uncertain, preserve the file and report that it was not deleted.
   - Never delete a directory as part of instruction-file cleanup.
   - Never delete more than the single instruction file that was explicitly used.
   - The final report must say:
     - which instruction file was used,
     - whether it was deleted or preserved,
     - if preserved, why.

3. **Model preference**
   - When starting Codex for this repository, prefer GPT-5.3 with high reasoning if available; otherwise use the strongest available GPT-5 reasoning model approved by the user.

## Key Documentation
- `docs/LATEST_RESULTS_AND_CLAIMS.md`: **Canonical current results** — FIX-1..8 outcomes, aggregate-720 evidence, safe/unsafe claims, decision records. Read this before any other results doc.
- `docs/STAGE2_CALIBRATED_GATE_STATUS_20260518.md`: Stage-2 gate evaluation detail (not promoted).
- `docs/RELATION_VERIFIER_PHASE_CLOSURE_20260517.md`: Formal closure and approved-use boundary for the verifier phase.
- `docs/FRONTIER_ALLOCATION_VERIFIER_INTEGRATION_STATUS_20260517.md`: Compact verifier/frontier integration handoff with CI-backed claim scope.
- `docs/PAPER_DRAFT_VERIFIER_GUIDED_WITHIN_METHOD_RERANKING_20260517.md`: Paper-ready narrative for verifier-guided within-method reranking.
- `docs/STAGE2_BASELINE_GATED_HYBRID_ALLOCATOR_PLAN_20260517.md`: Stage-2 plan (historical; gate not promoted).
- `docs/CURRENT_STATE_SUMMARY_20260511.md`: Historical background only (pre-FIX series, as of 2026-05-11). Do not treat as current canonical state.
- `docs/CURRENT_METHOD_STATUS_20260511.md`: Method roles supplement (historical).
- `docs/CURRENT_ARTIFACTS_INDEX_20260511.md`: Artifact navigation supplement (historical).
