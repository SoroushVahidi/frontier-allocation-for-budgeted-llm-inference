# Current baseline next steps (2026-04-21)

## Purpose

This note is the shortest current answer to:
- which external baselines are already in the strongest usable state,
- which external baseline should be strengthened next,
- and what the safest integration order is after the default-model lock-in.

## Current repository state

The repository now has a finalized current broad default promoted model on the evaluated strict-phased surface:
- **`strict_gate1_cap_k6`**

So the next major strengthening task is no longer default-model selection.
It is:
- **external-baseline strengthening and closure**.

## Current safest baseline taxonomy summary

Use the normalized v1 taxonomy from:
- `BASELINE_REPAIR_AND_STATUS_AUDIT_20260420T225833Z.md`
- `outputs/baseline_repair_and_status_audit_20260420T225833Z/baseline_status_matrix.json`

At a high level:
- **MODE A adapter-based near-direct:** `s1`, `TALE`, `L1`
- **official/import-validated adjacent:** `BEST-Route`, `when_solve_when_verify`, `rest_mcts`, and similar adjacent imports
- **discuss-only:** `Q*`, `Let's Verify Step by Step`, `Rational Metareasoning` and other framing/ingredient references without strong runnable integration

## Current next baseline to strengthen first

### 1. BEST-Route (strengthened in this pass)

**Current role:** official adjacent adaptive-routing baseline with reproducible import-validation artifact lane

**Why first (now completed):**
- strongest provenance among the currently non-fully-strengthened external baselines,
- official code availability,
- clearer import/validation path than Q*,
- lower honesty risk than speculative unofficial adapters,
- reviewer-defensible as an official adaptive-compute neighbor even though it is query-level rather than frontier-level.

**How to treat it:**
- official
- import_validated
- adjacent

**Not safe to claim:**
- direct frontier-allocation equivalence
- full faithful paper reproduction unless the repo truly supports that later

## Current next baseline after BEST-Route

### 2. When To Solve / When To Verify (strengthened in this pass)

**Why second:**
- closer to solve-vs-verify control than BEST-Route,
- more relevant to bounded verification and continuation-value logic,
- closer to the repo's branch-allocation story than pure query-level routing,
- but still safer to integrate after BEST-Route rather than before it.

**Current safest treatment (confirmed):**
- official
- import_validated
- adjacent

**Strengthening status (now complete):**
- validator lane kept strict and adjacent-only,
- canonical adjacent runner + comparison contract added,
- output artifact family now mirrors BEST-Route style (`outputs/when_solve_when_verify_adjacent_integration/<run_id>/`),
- blocker language now explicitly captures HF/OpenAI/compute requirements for fuller reproduction.

## Current next baseline after this strengthening

### 3. ReST-MCTS* (current next target)

**Why next:**
- still official and relevant as a search-guided adjacent baseline,
- currently import-validated but lacking the same standardized strengthened lane quality now established for BEST-Route and when_solve_when_verify.

## What should not be next

### Q*
Q* is still scientifically important, but it should **not** be the next external baseline to fix immediately after BEST-Route.

Why:
- closer conceptually to frontier expansion control,
- but higher reproduction and provenance risk,
- no equally clean official integration path in the current repo state,
- more likely to tempt overclaiming via an unofficial adapter.

So Q* now remains a **provenance-hardened discuss-only** baseline with explicit blockers unless the official-code/provenance situation becomes much stronger.

## Practical strengthening order

Recommended order:
1. **BEST-Route**
2. **When To Solve / When To Verify**
3. **ReST-MCTS*** (if stronger official import evidence becomes worth the added heaviness)
4. **Q*** only after verified official artifacts exist or a strictly caveated/auditable adapter contract is added

## Current paper-facing guidance

For manuscript-facing text right now:
- treat `s1`, `TALE`, and `L1` as the strongest matched-substrate near-direct external comparisons,
- treat `BEST-Route` as the first external adjacent official baseline to strengthen,
- treat `when_solve_when_verify` as the next adjacent baseline most worth strengthening after BEST-Route,
- and treat `Q*` as an important discuss-only baseline with explicit provenance blockers unless its integration path becomes much stronger.

## Cross-links

Also see:
- `CURRENT_REFERENCES_AND_BASELINES_INDEX_2026_04_20.md`
- `main_baselines.md`
- `BASELINE_REPAIR_AND_STATUS_AUDIT_20260420T225833Z.md`
- `QSTAR_PROVENANCE_AND_INTEGRATION_PASS_20260422T013736Z.md`
- `CURRENT_DEFAULT_MODEL_AND_STRICT_PHASED_STATUS_2026_04_21.md`


## BEST-Route strengthening artifact

- `BEST_ROUTE_STRENGTHENING_PASS_2026_04_21.md`
- `outputs/best_route_adjacent_integration/<run_id>/`


## BEST-Route runtime stabilization follow-up (2026-04-22)

- Two-lane pass completed via `scripts/run_best_route_runtime_stabilization_pass.py`.
- Latest artifact family: `outputs/best_route_runtime_stabilization/<run_id>/`.
- Report: `docs/BEST_ROUTE_RUNTIME_STABILIZATION_PASS_20260422T020000Z.md`.
- Current safest classification remains **partial-runnable adjacent** (stronger than import-only, not full faithful reproduction).
