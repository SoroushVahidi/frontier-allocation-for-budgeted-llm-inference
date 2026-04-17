# Repository cleanup and organization audit (2026-04-16)

## Purpose

This audit records the current repository-organization state for the NeurIPS-oriented `adaptive-reasoning-budget-allocation` project and proposes a concrete cleanup plan.

## Executive summary

The repository already has a strong **conceptual organization**:
- clear README framing,
- a canonical docs path,
- explicit canonical/exploratory/historical labels,
- a serious scripts index,
- and clear paper-positioning discipline.

However, the repository still has a **surface-area and physical-layout problem**:
- canonical vs exploratory vs historical separation is stronger in documentation than in the directory layout,
- `scripts/README.md` is too dense to serve as an effective day-to-day collaborator entry point,
- legacy names remain in canonical paths,
- several active method families live side-by-side without a stronger physical namespace,
- and paper-facing vs experiment-facing outputs are not yet enforced strongly enough at the top level.

## What is already working well

1. README correctly defines the current project identity as fixed-budget adaptive test-time compute allocation.
2. `docs/README.md` gives a canonical reading order.
3. `docs/REPO_MAP.md` explains the intended collaborator path clearly.
4. `docs/CURRENT_PROJECT_STATUS.md` is unusually strong and honest about what is built vs unresolved.
5. The repo already uses careful provenance language and avoids overclaiming.

## Main organization problems

### 1. Documentation-level separation is ahead of filesystem-level separation
The repo clearly says what is canonical, exploratory, and historical, but the physical layout still appears too mixed for fast onboarding.

### 2. Script namespace is overloaded
The scripts index is comprehensive, but it is too long and combines:
- canonical project runners,
- exploratory method variants,
- oracle-label infrastructure,
- baseline integration tooling,
- external-baseline validation,
- and historical scripts,
all under one broad `scripts/` surface.

### 3. Legacy names still leak into canonical paths
Examples already acknowledged in repo docs include legacy names such as `run_cross_strategy_frontier_allocation.py`. These are understandable for compatibility, but they weaken conceptual cleanliness.

### 4. Current canonical paper path is not yet physically privileged enough
The current repo identity is frontier allocation / branch-priority allocation, but the tree still seems to carry substantial adjacent lines that can visually compete with the canonical path.

### 5. Canonical outputs vs exploratory outputs need stronger top-level policy
The repo already writes under `outputs/`, but a stronger canonical output policy would help collaborators know which artifacts matter for the paper.

## Recommended target structure

### Top-level directories
- `docs/`
- `scripts/`
- `experiments/`
- `configs/`
- `datasets/`
- `external/`
- `jobs/`
- `outputs/`
- `archive/`

### Docs substructure
- `docs/canonical/`
- `docs/exploratory/`
- `docs/historical/`
- `docs/integration/`
- `docs/status/`
- `docs/paper/`

Suggested mapping:
- move canonical planning/status files into `docs/canonical/` or `docs/status/`,
- move external baseline and dataset integration notes into `docs/integration/`,
- move superseded notes into `docs/historical/`,
- keep `docs/README.md` at the root of `docs/` as the index.

### Scripts substructure
- `scripts/canonical/`
- `scripts/exploratory/`
- `scripts/integration/`
- `scripts/oracle_labels/`
- `scripts/external_baselines/`
- `scripts/historical/`

Suggested mapping:
- current paper-path scripts into `scripts/canonical/`,
- tie-aware / warm-start / Rao-Kupper / ambiguity variants into `scripts/exploratory/`,
- dataset-access and corpus-building utilities into `scripts/integration/`,
- brute-force/oracle-label generation and related learner pipelines into `scripts/oracle_labels/`,
- s1 / TALE / L1 / BEST-Route / OpenR / ReST-MCTS / import-verifier tools into `scripts/external_baselines/`,
- old revise-routing support into `scripts/historical/`.

### Outputs substructure
- `outputs/canonical/`
- `outputs/exploratory/`
- `outputs/integration/`
- `outputs/oracle_labels/`
- `outputs/external_baselines/`
- `outputs/historical/`
- `outputs/paper_tables/`
- `outputs/paper_figures/`
- `outputs/audits/`

This is the biggest practical cleanup win after the docs/scripts split.

## Naming policy recommendations

1. Prefer `frontier_allocation`, `branch_allocation`, `branch_scorer`, and `controller` over older strategy/routing names when referring to the new canonical track.
2. Keep legacy filenames only behind thin compatibility wrappers.
3. Put the real canonical names in the primary entry points and docs.
4. Add a short naming policy note in `docs/canonical/NAMING_POLICY.md`.

## Minimal high-value cleanup tasks

### Phase 1: entry-point cleanup
1. Keep top-level `README.md`.
2. Keep top-level `docs/README.md`.
3. Replace the current long `scripts/README.md` with:
   - a short entry page,
   - plus dedicated sub-readmes inside script subfolders.
4. Add `archive/README.md` describing what was moved and why.

### Phase 2: physical separation
1. Create `archive/`.
2. Move historical binary revise-routing materials there.
3. Move non-canonical dated memos into `docs/historical/`.
4. Move method-specific exploratory notes into `docs/exploratory/`.
5. Move external-baseline notes into `docs/integration/`.

### Phase 3: script re-namespacing
1. Create the script subfolders listed above.
2. Move files physically.
3. Leave tiny wrapper scripts at old paths only where compatibility matters.
4. Update README and docs references.

### Phase 4: output policy
1. Define canonical output roots in one file, for example `docs/canonical/OUTPUT_POLICY.md`.
2. Separate paper-facing outputs from raw experimental outputs.
3. Mark any non-paper artifacts clearly as exploratory.

## Safe claim about current repo state

A conservative summary is:

> The repository is already intellectually well organized, but it is not yet physically organized to the same standard. The next cleanup should reduce surface area, privilege the canonical frontier-allocation path, and move historical and exploratory material into clearer namespaces.

## Recommended immediate next action

If only one cleanup pass is done first, it should be:

> **physically separate canonical / exploratory / historical docs and scripts, then shorten the collaborator entry path accordingly.**
