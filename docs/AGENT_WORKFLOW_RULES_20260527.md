# Agent Workflow Rules (2026-05-27)

## Core Safety
- No paid API calls without explicit per-call authorization.
- No commit/push/stage actions unless explicitly requested.
- No deletion, overwrite, or movement of existing outputs.
- No secret exposure in logs or reports.

## Verification Standard
- Completion claims require real evidence: file counts, row counts, logs, tmux/job status, and evaluation artifacts.
- Plans and conceptual updates are not completion evidence.

## Runtime/Policy Boundaries
- Long jobs (>1 min) should run in tmux.
- Use corrected fixed-policy baselines only; no row-wise max baseline.
- Oracle is upper bound only.
- Gold/correctness labels are offline-eval only; never runtime features.
- D6 rescue/regression labels are diagnostic only; never runtime selector inputs.

## Operational Hygiene
- Keep generated artifacts in `outputs/`.
- Use narrowly-scoped commits grouped by theme.
- Preserve manuscript claim boundaries and required disclosures.
