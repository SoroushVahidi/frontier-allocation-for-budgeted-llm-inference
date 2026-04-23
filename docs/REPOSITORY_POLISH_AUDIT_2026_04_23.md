# Repository polish audit — 2026-04-23

## Scope and constraints

This audit focused on repository organization, front-door clarity, and provenance-preserving navigation.

No scientific claims were changed, no heavy experiments were rerun, and no quantitative results were regenerated.

## What was confusing before this pass

1. Front-door guidance was rich but diffuse; collaborators could still miss the exact six practical questions (what/what-not/read-first/checks/reproduction/claim source).
2. Directory role boundaries were implicit in many places but not consistently stated in each top-level area.
3. `outputs/` interpretation could still be misread without an immediate canonical/exploratory/historical classifier.
4. Some contributor-facing directories (`experiments/`, `tests/`, `jobs/`) lacked local README front doors.
5. `references/README.md` still looked partially “planned” rather than reflecting current usage discipline.

## What was improved

1. Top-level README rewritten into a strict front-door contract answering the six collaborator questions directly.
2. `outputs/README.md` reframed around interpretation classes to reduce accidental citation of non-canonical runs.
3. Added directory front doors:
   - `experiments/README.md`
   - `tests/README.md`
   - `jobs/README.md`
4. Updated `references/README.md` to better reflect active usage and provenance expectations.
5. Added this dated audit note to preserve rationale and unresolved items explicitly.

## Remaining unresolved (human decision needed)

1. Large volume of dated docs in `docs/` still includes overlap; full consolidation should be a separate editorial pass to avoid accidental provenance loss.
2. Some script naming remains long and timestamp-heavy; harmonization should be done gradually with compatibility wrappers to avoid breaking existing references.
3. External baseline completeness remains bounded and should continue to be stated conservatively.
4. Real-model confirmation remains useful but limited; manuscript claims should keep this boundary explicit.

## Safety/claim-boundary check

- Maintained explicit separation between:
  - manuscript-facing matched-surface winner: `strict_f3`
  - broader operational default on a different surface: `strict_gate1_cap_k6`
- No changes to experimental code paths or result artifacts.
