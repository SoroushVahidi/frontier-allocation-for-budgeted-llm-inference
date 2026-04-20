# Repository audit and cleanup note (2026-04-20)

## Executive summary

This repository is already in materially better shape than a typical fast-moving research repo.

It already has:
- a clear top-level project identity,
- lightweight packaging and development files (`pyproject.toml`, `requirements.txt`, `Makefile`),
- basic tests and a health check,
- canonical/exploratory/historical interpretation rules,
- and multiple navigation indexes for collaborators.

The main weakness is **not missing infrastructure**. The main weakness is **navigation entropy**:
- too many front-door documents say overlapping things,
- too many filenames encode dates in the primary reading path,
- the README/doc indexes repeat large bullet lists,
- and the shortest collaborator path is longer than it should be.

In other words: the repo is substantially **documented**, but not yet fully **compressed**.

## Audit verdict

### What is strong
- Clear project scope: fixed-budget adaptive test-time compute allocation for LLM reasoning.
- Explicit separation from the older revise-routing paper line.
- Good baseline repo hygiene for a research codebase.
- Useful canonical vs exploratory vs historical interpretation policy.
- Existing health-check and structure tests.
- Reasonable runnable-entrypoint documentation.

### What is weak
- Front-door duplication across `README.md`, `docs/README.md`, `docs/REPO_MAP.md`, and `scripts/README.md`.
- Canonical reading path is still too wide for a first-time collaborator.
- Date-stamped filenames are useful for provenance but create cognitive load when they dominate the entry path.
- Script indexes are comprehensive but longer than needed for the first pass.
- The repo currently asks readers to absorb many status notes before they can identify the stable core.

## Cleanup goals for this pass

This pass is intentionally conservative.

It does **not** try to rename large numbers of files, move major directories, or rewrite the whole documentation stack.

Instead, it aims to:
1. reduce front-door duplication,
2. make the canonical entry path easier to follow,
3. preserve provenance-heavy dated notes without deleting them,
4. and make the top-level repo feel more organized for collaborators and paper writing.

## Changes made in this cleanup pass

### 1. Tightened the top-level README
The README is now more front-door oriented:
- shorter project identity,
- shorter current-state summary,
- clearer directory map,
- and a smaller canonical reading path.

### 2. Tightened `docs/README.md`
The docs index now emphasizes:
- what to read first,
- what is canonical,
- what is exploratory,
- and where results/references live,
without repeating every possible note at the top.

### 3. Tightened `scripts/README.md`
The scripts index now better separates:
- canonical workflows,
- exploratory workflows,
- integration/preparation tools,
- and historical material,
while keeping the first screen focused on the most important entry points.

### 4. Added this audit note
This file records the audit verdict and cleanup rationale so future polish passes can build from an explicit baseline rather than repeating the same diagnosis.

## Recommended next cleanup phase

The next pass should be slightly more structural.

### High-value next steps
1. Introduce a small number of **stable alias docs** such as:
   - `docs/CURRENT_METHOD.md`
   - `docs/CURRENT_RESULTS.md`
   - `docs/CURRENT_REFERENCES.md`
   - `docs/CURRENT_NEXT_STEPS.md`

   These can point to or absorb dated notes while giving collaborators stable names.

2. Move superseded or low-value dated notes more aggressively under:
   - `archive/`
   - or a narrower `docs/exploratory/` / `docs/historical/` split.

3. Add one canonical machine-readable manifest for the paper-facing working set, for example:
   - `docs/CANONICAL_PAPER_WORKING_SET.md`

4. Extend `scripts/check_repo_health.py` or tests so they also verify the canonical front-door docs referenced by the README.

## Practical rule going forward

When the repo state changes materially, update these together:
- `README.md`
- `docs/README.md`
- `docs/REPO_MAP.md`
- `scripts/README.md`
- the current canonical dashboard/state note
- the current canonical results/artifacts index
- the current canonical references/baselines index

This prevents the front door from drifting away from the real project state.

## Bottom line

This repository is already **research-serious** and **paper-usable**.

Its main remaining organizational problem is not missing content; it is that the current content is spread across too many overlapping entry documents.

The right cleanup strategy is therefore **compression and canonicalization**, not a wholesale rewrite.
