# New-paper current status (practical snapshot)

## Scope

This note is only for the **new paper track**:
- cross-controller frontier allocation,
- budgeted branch/controller compute allocation,
- branch-level scoring as the key local decision component.

It is intentionally separate from the old manuscript binary revise-routing track.

## Main goal

Estimate and use the **marginal value of one more unit of compute** so budget can be allocated across competing controllers/branches under a fixed inference budget.

## What appears strongest right now

1. **Frontier-allocation framing** (not binary routing) is clear and distinct.
2. **Anti-collapse controller constraints** are important for avoiding under-spending behavior.
3. **Pairwise BT branch scoring with richer ordered-history features** is currently the strongest branch-scorer direction.
4. External datasets are useful as **warm-start supervision**, but internal/repo-specific labels remain central.

## What has been tested (high-level)

- Basic branch scorers (early pointwise/static variants).
- Ordered-history feature upgrades.
- Pairwise BT training and scalar-at-inference controllers.
- Reliability-weighted BT extensions.
- External warm-start comparisons.
- Pairwise diagnostic audits.

## What worked

- Moving from weak static targets toward continuation/progress and pairwise formulations improved competitiveness.
- Plain BT pairwise often improves over simple adaptive baselines in simulator-backed runs.
- Anti-collapse design improves budget realization behavior.

## What partly worked / mixed

- Reliability-weighted BT sometimes helps (not consistently across datasets/settings).
- External warm-start can give small gains, but not a stable replacement for internal supervision.

## What failed or remains weak

- No robust, broad, settled win over strongest internal heuristics across all controlled sweeps.
- Confidence/reliability signals for pairwise data still have limited dynamic range in current diagnostics.
- Real-model evidence is still limited compared with simulator coverage.

## Current bottleneck (one line)

The main bottleneck is still **label/target quality and calibration for decision-time marginal compute value**, not basic infrastructure.

## Current best direction

Use pairwise BT as baseline, then improve confidence calibration / uncertain-pair handling and evaluate robustness before adding heavier model complexity.

## Role of external data vs internal/oracle labels

- External datasets: warm-start, regularization, and auxiliary supervision only.
- Internal/oracle-style labels: still required for project-specific allocation targets and meaningful controller-level validation.

## Safe interpretation

The repo is strong in infrastructure and honest diagnostics, but the method should still be treated as **active development rather than finalized**.
