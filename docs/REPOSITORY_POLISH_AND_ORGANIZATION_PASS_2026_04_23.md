# Repository polish and organization pass (2026-04-23)

## Scope

This pass was a conservative repository-organization cleanup only.

Out of scope and unchanged:
- scientific claims,
- new experiments,
- method-family additions,
- promotion decision reopening,
- canonical artifact overwrites.

## What was cleaned

1. **Front-door alignment**
   - Aligned `README.md`, `QUICKSTART.md`, `docs/CANONICAL_START_HERE.md`, `docs/REPO_MAP.md`, `docs/CANONICAL_INSTALL_AND_DEV.md`, and `scripts/CANONICAL_START_HERE.md` around one shorter onboarding path.
   - Reduced repetitive language and made cross-links more direct.

2. **Manuscript-support navigation consolidation**
   - Added `MANUSCRIPT_SUPPORT_DASHBOARD.md` as a compact, canonical-first collaborator guide.
   - Explicitly grouped: current claim surface, canonical evidence set, resolved outcomes, and guardrails.

3. **Canonical status hygiene updates**
   - Reinforced current resolved outcomes in source-of-truth/output guidance:
     - `strict_f3` remains manuscript-facing matched-surface method,
     - conditional-risk line remains supportive/appendix-level,
     - main-table baseline fairness audit reports no material issue.

4. **Stale/confusion reduction by demotion rather than deletion**
   - Kept historical/provenance policy explicit and avoided deleting historical materials.
   - Front-door docs now direct readers to canonical pages first, with historical notes interpreted as provenance.

## What remains intentionally historical

- Prior dated status notes and exploratory bundles remain preserved for traceability.
- Historical documents are still available, but no longer treated as front-door interpretation authority.

## Remaining cleanup debt (intentionally deferred)

- `docs/` and `scripts/README.md` still contain broad historical inventories; additional reduction can be done in future passes if done carefully and without provenance loss.
- Optional future consistency pass: lightweight automated markdown-link integrity check in CI for front-door docs only.
