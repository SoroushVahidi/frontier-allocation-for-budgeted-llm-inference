# Results Index Canonical (2026-04-29)

## canonical paper-facing
- Canonical manuscript artifacts under `outputs/paper_*`.

## real-model diagnostic
- DR-v2 100-case: 0.56 vs external_l1_max 0.72.
- DR-v2 selection-fix 100-case: 0.55 vs external_l1_max 0.72.
- strict_f3 same-run 100-case: 0.56 vs external_l1_max 0.72.
- strict_gate1_cap_k6 100-case: 0.48 vs external_l1_max 0.75.

## small-sample/preflight
- DR-v2 small n=10 positive signal existed but was rejected by 100-case follow-up.

## failed/incomplete
- Chunked/incomplete runs and interrupted diagnostics remain non-canonical.

## superseded
- Selection-only DR-v2 fixes are superseded by outcome-verifier rerank direction for next iteration.

## provenance-only
- Historical markdown notes without compact-ledger backing.

## Key failure conclusions
- strict_gate1 losses: mostly absent-from-tree.
- DR-v2 trace-complete losses: mostly present-not-selected.
