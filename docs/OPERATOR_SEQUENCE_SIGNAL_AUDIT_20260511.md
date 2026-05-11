# Operator Sequence Signal Audit

## Bottleneck Targeted

Candidate generation, gold-in-pool behavior, and frontier collapse.

## Goal

Test whether exported operator-prefix and artifact-level pseudo-path features contain predictive signal that can guide which reasoning operator or branch to try next under a tiny 4-8 call budget.

## Scope

- This is a no-API offline analysis step.
- This is not a live controller.
- This is not a baseline comparison.
- This is not evidence of beating any external baseline.

## Source Expectations

- Prefer exported rows produced by `scripts/export_operator_sequence_mining_rows.py`.
- If the chosen artifact source only supports pseudo-path rows, treat operator sequences as ordered trace approximations rather than verified tree paths.
- Real path mining should only be attempted after the source artifact proves it can support stable parent/child structure.

## Decision Rule

Proceed to learned policy or dataset work only if the signal audit shows nontrivial separation between higher-quality and lower-quality endpoint rows.

If the separation is weak, the next step is to collect a richer artifact source or a more reliable tree-path export before training anything.
