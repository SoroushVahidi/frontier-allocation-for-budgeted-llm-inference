# Stage-3 Patch-Focused 50-case Rerun

- Base 50-case Stage-3 scaffold reused; patches applied only to 1078/1198/1155.
- Patch-focused correct: 39/50 (prior integrated: 38/50; best_external: 40/50).
- Deltas: vs prior 1, vs L1 7, vs TALE 8, vs S1 6, vs best_external -1.
- Patch-only vs best-external-only: 1 vs 2.

## Patch case behavior
- openai_gsm8k_1078: correct=1 (prior=0, best_external=1).
- openai_gsm8k_1155: correct=1 (prior=0, best_external=1).
- openai_gsm8k_1198: correct=0 (prior=0, best_external=1).

## Recommendation
- 245-case expansion justified now: not yet.

## Caveats
- Pilot-scaffolded runtime; still not full production-runtime equivalence.