# Stage-3 Best-External Gap Patch Checkpoint

- Tested 2 patch cases (1078, 1198) plus 1 control (1155) under strict <=4 call cap.
- Actual calls: 3; exact total: 2/3.
- 1078 exact: 1; 1198 exact: 0; 1155 exact: 1.
- Recomputed best-external gap closures: 2.

## Decision signal
- Patch stability for 50-case rerun: not yet sufficient.

## Caveats
- Tiny checkpoint only; prompt-policy verification, not production-runtime equivalence proof.