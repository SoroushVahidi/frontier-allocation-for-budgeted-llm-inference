# Codex Web Handoff (2026-05-10)

## Current Research Status
**Research Question**: How to optimally allocate budget for LLM inference using frontier search, diverse reasoning paths, and robust selection layers?
**Current Best Method**: `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal` (with Direct L1 Anchor).
**Strongest Baseline**: `external_l1_max` (external model performance).

## Latest Progress (Cursor Session 2026-05-10)
- **PR #373 (Merged)**: Implemented the **Direct L1 Anchor** patch. This injects a high-quality direct reasoning candidate into the candidate pool to combat "Frontier Collapse."
- **PR #374 (Merged)**: Conducted a **Proxy Audit** of the patch.
  - **Key Finding**: Diversity increased in 100% of evaluated cases.
  - **Key Finding**: ~15% of previously unrecoverable cases are now potentially recoverable.
  - **Conclusion**: The patch is a necessary safety net but insufficient alone; the "discovery" problem remains for 85% of gold-absent cases.

## Failure Analysis Summary
- **Dominant Failure Mode**: **Frontier Collapse / Low Diversity** (96% of gold-absent cases). The frontier search often converges on a single incorrect answer group.
- **Root Cause**: The root strategy choice is not diverse enough, and shallow frontier expansions don't always reach the final answer for multi-step problems.
- **Top Domains**: `money/cost/revenue`, `multi-step arithmetic`, `ratio/proportion/percentage`.

## Algorithmic Conclusions
1.  **Direct L1 Anchor** provides a reliable "floor" and increases candidate pool diversity.
2.  **Selection Layer** is now more robust due to commitment gates and tiebreak logic, but it can still be overwhelmed by a wrong consensus.
3.  **Next Frontier**: We must improve **Candidate Generation** diversity. Relying on a single root strategy and frontier expansion is too brittle.

## Recommended Next Task
**Implement Fixed-Budget Diverse Prompt Anchors**:
- Instead of one direct seed, generate N diverse seeds using different prompt strategies (e.g., "Plan-then-Solve", "Step-by-Step", "Algebraic").
- Use no-API tests with mocked candidates to verify that the selection layer handles N diverse groups correctly.
- Evaluate the trade-off between spending budget on more anchors vs. deeper frontier expansion.

## Key Files to Read First
- `docs/CODEX_WEB_HANDOFF_20260510.md`: This document.
- `AGENTS.md`: Instructions for future agents.
- `docs/DIRECT_L1_ANCHOR_PATCH_EFFECT_AUDIT_20260510.md`: Latest audit results.
- `docs/GOLD_ABSENT_FAILURE_SUBPATTERN_ANALYSIS_20260510.md`: Detailed failure taxonomy.
- `experiments/controllers.py`: Core logic for `DirectReserveFrontierGateController`.
- `tests/test_direct_l1_anchor_patch_20260510.py`: Reference for testing new algorithmic patches.

## Commands
### Health Checks & Tests
```bash
python3 scripts/check_repo_health.py
python3 -m pytest -q tests/test_direct_l1_anchor_patch_20260510.py
python3 -m pytest -q tests/test_frontier_router.py tests/test_check_repo_health_paths.py tests/test_reviewer_repro_guardrails.py
```

### DO NOT RUN WITHOUT APPROVAL
- Any script in `scripts/` or `experiments/` that calls external APIs (OpenAI, Cohere, Anthropic).
- `python3 scripts/run_live_validation.py` (High cost).

## GitHub Workflow
1.  Work from `main`.
2.  Create a feature branch: `feat/description-date`.
3.  Run all health checks and tests locally.
4.  Create a PR and use **Squash Merge**.
5.  Delete the branch after merge.

## Caveats & Unsafe Claims
- **Proxy Audit**: Recent claims about "recovery" are based on artifact re-runs, not live API calls.
- **Baseline Comparison**: Never claim `external_l1_max` is beaten unless you have canonical evidence from a full validation run.
- **Legacy Code**: Avoid the "strict_f3" trap in old controller configurations; use the latest `production_equiv_v1` patterns.

---
*Handoff prepared by Gemini 3 Flash on 2026-05-10.*
