# Instructions for AI Agents

Welcome to the `frontier-allocation-for-budgeted-llm-inference` repository. To maintain research integrity and repository health, please follow these guidelines.

## Development Workflow
1.  **Always work from `main`**: Ensure you are synced with `origin/main` before starting.
2.  **Branch for every change**: Use descriptive branch names (e.g., `fix/issue-description` or `feat/new-feature`).
3.  **PR + Squash Merge**: All changes must go through a Pull Request. Use squash merging to keep the history clean.
4.  **Run Health Checks**: Before committing, always run:
    ```bash
    python3 scripts/check_repo_health.py
    ```
5.  **Test Coverage**: Add or update tests in `tests/` for any algorithmic changes. Use mocks to avoid API calls.

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
The current priority is **no-API case-level analysis and pre-registered experiment design**.
- Focus on clarifying candidate-generation failure modes, gold-in-pool behavior, and frontier collapse.
- Keep proposed live work bounded and explicit; do not start paid runs without an approved capped plan.
- Selector-only patches remain secondary unless a new no-API analysis changes the bottleneck diagnosis.

## Key Documentation
- `docs/CURRENT_STATE_SUMMARY_20260511.md`: Canonical current-state summary.
- `docs/CURRENT_METHOD_STATUS_20260511.md`: Method roles and status supplement.
- `docs/CURRENT_ARTIFACTS_INDEX_20260511.md`: Canonical artifact navigation supplement.
- `docs/CODEX_WEB_HANDOFF_20260510.md`: Earlier handoff, still useful context.
- `docs/GOLD_ABSENT_FAILURE_SUBPATTERN_ANALYSIS_20260510.md`: Detailed failure analysis.
- `docs/DIRECT_L1_ANCHOR_PATCH_EFFECT_AUDIT_20260510.md`: Latest patch audit.
