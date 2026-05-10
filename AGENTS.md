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

## Research Integrity
1.  **No Unsubstantiated Claims**: Do not claim a method is "better" or "beats the baseline" based on small samples or proxy audits alone. Use the term "potentially recoverable" for artifact-based improvements.
2.  **Baseline Consistency**: The `external_l1_max` baseline is the current gold standard. Any claims of improvement must be measured against it using canonical evaluation scripts.
3.  **Avoid Legacy Patterns**: Do not use old "strict_f3" or "v0" controller configurations. Follow the patterns in `experiments/controllers.py` used by the `production_equiv_v1` method.

## Next Research Focus
The current priority is **Candidate Generation Diversity**.
- Focus on **Diverse Prompt Anchors** (generating multiple initial reasoning paths).
- Do NOT spend more time on "Selector-only" patches (e.g., more complex tiebreak rules) until the candidate pool diversity is improved.

## Key Documentation
- `docs/CODEX_WEB_HANDOFF_20260510.md`: The latest state of the project.
- `docs/GOLD_ABSENT_FAILURE_SUBPATTERN_ANALYSIS_20260510.md`: Detailed failure analysis.
- `docs/DIRECT_L1_ANCHOR_PATCH_EFFECT_AUDIT_20260510.md`: Latest patch audit.
