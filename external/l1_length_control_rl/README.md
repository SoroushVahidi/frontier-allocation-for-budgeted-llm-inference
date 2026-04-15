# L1 (LCPO): Controlling reasoning length with reinforcement learning

- **Paper:** https://arxiv.org/abs/2503.04697
- **Project page:** https://cmu-l3.github.io/l1/
- **Official code:** https://github.com/cmu-l3/l1
- **License (upstream):** Apache-2.0 (check upstream `LICENSE` before redistribution).

## Role in this repository

This baseline is tracked as a **direct / near-direct budget-control baseline** for the new NeurIPS project on fixed-budget adaptive test-time compute allocation.

## Fair integration status

- **MODE A:** `COMPLETE` (in-repo inference-only L1-style adapter with Exact and Max token-length conditioning).
- **MODE B:** `PARTIAL` (official/full L1 path via imported external results; this repo does not auto-reproduce full RL training stack).

## Notes

- L1 is methodologically strong for hard/controlled reasoning-length budgets.
- L1 control space (token-length conditioning of an RL-trained policy) differs from this repo's frontier stop-vs-act control over an unchanged base model.
- Comparisons should be reported as matched-budget comparisons, not strict control-equivalence claims.
