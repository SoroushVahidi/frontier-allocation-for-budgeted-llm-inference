# Claim Scope Audit (Pass 4)

## Scope Controls Enforced

- No full FLOP-, token-, USD-, or latency-matched comparison is claimed.
- No general superiority over self-consistency, Best-of-N, L1, S1, or TALE is claimed.
- No general claim that learned selectors, learned routing, or failure-based selectors fail.
- No generalization beyond the studied providers, datasets, budget, and frozen records is claimed.
- Oracle rows remain upper bounds only.
- Gold labels remain offline-only evaluation labels.
- D6/FIX-style diagnostic labels are not introduced as runtime selector features.

## Required Values Verified Present

| Required value | Status |
|---|---|
| Pooled-4 `2258/3394`, `66.53%` | Present |
| FTA `2206/3394`, `65.00%` | Present |
| McNemar `p=0.00027` | Present |
| Successful calls `2.78 -> 5.38` | Present |
| Azure x GSM8K SC/Frontier `276/300` | Present |
| Azure FIX-2 `2/18` and `7/31` rescue/regression patterns | Present |
| Repair asymmetry `151/3394` | Present |
| Held-out folds choosing Pooled-4 `15/15` | Present |
| Fireworks x GPQA `BLOCKED_PROTOCOL_NONCONVERGENCE` | Present |

## Evidence-Boundary Placement

- Environment/budget scope is stated in Limitations.
- Adapter fidelity is stated in Experimental Protocol and detailed in the baseline-fidelity table.
- Development adjacency is stated in Limitations and used in provider-transfer interpretation.
- Incomplete token/USD telemetry and no full resource-matched matrix are stated in Limitations, with
  detailed accounting semantics in Compute Accounting.
- Reproducibility limits are stated in Experimental Protocol/Reproducibility and Limitations.

## Overclaim Scan

Manual and `rg` scans found no remaining claims of:

- state-of-the-art performance;
- general method superiority;
- general selector failure;
- full resource-matched dominance;
- inference beyond the 15 completed cells plus the blocked Fireworks x GPQA outcome.

Remaining terms such as "highest", "beats", and "winner" occur only in descriptive table/counterfactual
contexts, repair-stability statements, or formal definitions such as consensus regret.
