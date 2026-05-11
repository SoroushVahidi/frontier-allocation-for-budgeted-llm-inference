# Direct L1 Strong Seed 15-Case Live Result (2026-05-11)

## Scope

This is a 15-case diagnostic only.

- Baseline: `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_direct_hybrid`
- Treatment: `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_direct_l1_strong_seed_v1`
- Exact cases: `docs/project_handoff_20260510/exact_case_replay/direct_l1_strong_seed_15case_exact_cases_20260511.jsonl`
- Budget: `4`

This run is not a baseline claim and does not promote `direct_l1_strong_seed_v1`.

## Result

- Overall exact accuracy tied: `11/30` baseline vs `11/30` treatment.
- Seed `11`: baseline `5/15`, treatment `6/15`.
- Seed `23`: baseline `6/15`, treatment `5/15`.

## Case-Level Outcome

Improved:

- `openai_gsm8k_354`

Regressed in seed `23`:

- `openai_gsm8k_190`
- `openai_gsm8k_213`

No worsened cases were observed in seed `11`.

## Proxy Signals

- Gold-in-tree proxy worsened: baseline `15/30`, treatment `11/30`.
- Candidate answer group count average: baseline `1.8333`, treatment `1.9333`.
- Answer entropy average: baseline `0.63999`, treatment `0.64769`.
- Direct L1 anchor metadata was present in `30/30` rows for both methods.

## Cost

- Baseline: `30,604` tokens, `$0.147036`.
- Treatment: `32,873` tokens, `$0.161991`.

## Verdict

- Mixed result overall.
- Success criteria were not met.
- Stop/regression criteria were hit in seed `23`.

## Provenance

The generated live-run artifacts are preserved under:

- `outputs/direct_l1_strong_seed_15case_live_20260511T202624Z/`

The Cohere validation summary is preserved at:

- `docs/COHERE_REAL_MODEL_COST_NORMALIZED_VALIDATION_20260511T202624Z.md`

## Next Step

Do a no-API case-level analysis of the improvement and regression cases before any further paid runs.
