# BEST-Route integration status

## Decision

BEST-Route is now integrated in this repository as an **official adjacent import-validated baseline**.

## What “integrated” means in this repository

Integrated means:

- official provenance is documented (paper + upstream Microsoft repo),
- explicit taxonomy labels are wired (`official`, `import_validated`, `adjacent`),
- import contract is formalized in `configs/best_route_official_import_v1.json`,
- import validator exists at `scripts/verify_best_route_import.py`,
- external baseline docs/registry/status artifacts are updated,
- comparisons remain explicitly adjacent-only and manuscript-safe.

Integrated does **not** mean full paper-faithful in-repo reproduction of the upstream training/evaluation stack.

## Validator result

- Command run against fixture import package passed with `verdict=import_validated`.
- Local upstream clone was not required for this validation pass; validator reports this as a warning, not a failure.

## Remaining blockers for stronger reproduction

- Full end-to-end paper-faithful BEST-Route reproduction in this repository is still not implemented.
- No direct frontier-allocation control-space equivalence is established.
- Stronger claims would require a pinned upstream clone, full upstream pipeline execution, and auditable run artifacts under this repository.

## Safe comparison claims now

- BEST-Route can be reported as an **official adjacent import-validated baseline**.
- BEST-Route comparison rows are safe when imported artifacts pass validator checks and are labeled `adjacent_only`.
- BEST-Route should remain distinct from direct/near-direct frontier-allocation baselines.
