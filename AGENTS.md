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
4.  **Preserve current evidence hierarchy**: The main evidence is the 300-case PAL+retry vs `external_l1_max` bundle. The 30-case four-way pilot is diagnostic only. The 15-case Direct L1 strong-seed run is a small mixed follow-up diagnostic and is not the headline result.
5.  **Read the canonical summary first**: After `README.md`, read `docs/CURRENT_STATE_SUMMARY_20260511.md` before interpreting any outputs or planning new work.

## Research Integrity
1.  **No Unsubstantiated Claims**: Do not claim a method is "better" or "beats the baseline" based on small samples or proxy audits alone. Use the term "potentially recoverable" for artifact-based improvements.
2.  **Baseline Consistency**: The `external_l1_max` baseline is the current gold standard. Any claims of improvement must be measured against it using canonical evaluation scripts.
3.  **Avoid Legacy Patterns**: Do not use old "strict_f3" or "v0" controller configurations. Follow the patterns in `experiments/controllers.py` used by the `production_equiv_v1` method.
4.  **Do not mix evidence tiers**: Do not confuse strict-method diagnostics with PAL+retry evidence, and do not confuse the 15-case Direct L1 strong-seed result with the 300-case main bundle.
5.  **Do not overread structural replay**: The `pal_frontier_structural_target_replay_v1` offline replay is useful for structural analysis and logging, but it is not runtime promotion evidence until interpreted and validated.

## Next Research Focus
The current priority is **frontier allocation validation using verifier-guided within-method reranking**.

Recent state:
- The RelationReady verifier training phase is mostly complete.
- Selected verifier: SetFit `all-mpnet-base-v2` cfg1.
- Cross-method verifier-guided selection was method-entangled and mostly reproduced `external_l1_max`.
- Within-method reranking showed useful signal: verifier-selected seeds beat random seed choice on cached multi-seed artifacts.
- Exploratory slice-aware/tie-aware policies showed potential but require independent validation.
- A new independent multi-seed validation artifact may be generated with provider/API calls only after explicit approval, capped preflight, and tmux execution.

Current research priorities:
1. Validate verifier-guided within-method reranking on independent multi-seed artifacts.
2. Keep provider prompts gold-free; use gold/exact_match only for offline evaluation/reporting.
3. Use no-API dry-runs and manifests before paid/API generation.
4. Use tmux for long/API jobs.
5. Do not overclaim exploratory slice-aware policies unless validated on disjoint data.

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

## Key Documentation
- `docs/CURRENT_STATE_SUMMARY_20260511.md`: Canonical current-state summary.
- `docs/CURRENT_METHOD_STATUS_20260511.md`: Method roles and status supplement.
- `docs/CURRENT_ARTIFACTS_INDEX_20260511.md`: Canonical artifact navigation supplement.
- `docs/CODEX_WEB_HANDOFF_20260510.md`: Earlier handoff, still useful context.
- `docs/GOLD_ABSENT_FAILURE_SUBPATTERN_ANALYSIS_20260510.md`: Detailed failure analysis.
- `docs/DIRECT_L1_ANCHOR_PATCH_EFFECT_AUDIT_20260510.md`: Latest patch audit.
