# Current default-model and strict-phased status (2026-04-21)

## Purpose

This note is the shortest current answer to:
- what the strict-phased hard-coverage experiments changed,
- what the repository's broader operational default is on the current broader evaluated strict-phased surface,
- and what still remains open after that default decision.

Scope note:
- This file is about the broader operational strict-phased surface.
- For manuscript-facing internal method identity on the canonical manuscript-facing matched surface, see `INTERNAL_METHOD_FINAL_DECISION_PACKAGE_2026_04_22.md` (`strict_f3`).

## Current status in one paragraph

The repository upgraded the hard early-coverage experiments from a looser minimum-depth interpretation to a **strict phased law**:

> **finish F1 first, then finish F2, then finish F3**

for the forced shallow-coverage phases over root families. Under that stricter law, the repository compared strict forced variants, strict gates, and capped variants on both hard-slice and broader matched surfaces. The current decisive broader strict-phased pass selected:

> **`strict_gate1_cap_k6` as the broad default promoted model on the evaluated surface.**

## Strict phased law

For the first three levels, the controller now enforces:
- **F1 must complete before F2 can start**,
- **F2 must complete before F3 can start**,
- and no family may enter a deeper forced phase while another required root family is still below the current forced phase depth.

Within a phase, ordering remains controller-driven by the normal priorities / scores / anti-collapse logic. The intervention constrains **eligibility**, not the within-phase priority order.

## Why this matters

The stricter law is better aligned with the practical compute-allocation question. If the controller may not have enough budget to assess all three shallow levels, it should first guarantee the shallower coverage before spending forced exploration budget on deeper levels.

This also makes the experiments easier to interpret scientifically: improvements can be attributed to true phased shallow coverage rather than to a looser min-depth behavior.

## Final default result on the broader evaluated surface

The decisive broader strict-phased default-decision pass concluded that:
- `strict_gate1_cap_k6` outperformed the other serious finalists on the evaluated broader surface,
- including uncapped `strict_gate1`, `strict_gate2`, `strict_f3`, and `strict_f2`,
- and should therefore be treated as the repository's broader operational default on this broader strict-phased surface.

Primary evidence artifact:
- `FINAL_STRICT_PHASED_DEFAULT_DECISION_EVAL_20260421T042913Z.md`
- `outputs/final_strict_phased_default_decision_eval_20260421T042913Z/`

## Current broader operational default model

### Broader operational default model
- **`strict_gate1_cap_k6`**

### Why it won
- It performed best on the current broader strict-phased default-decision pass.
- It beat the strongest uncapped and strict-force finalists on the same evaluated surface.
- It preserved the strict phased F1 → F2 → F3 discipline while improving final broad performance enough to justify promotion.

### How to interpret it
This is the current broad default **for the evaluated surface and current repository phase**.
It is the repo's current canonical promoted model, not a claim of universal optimality across every possible future dataset or evaluation contract.

## Current strongest neighboring finalists

The strongest nearby finalists that remain important for interpretation are:
- **`strict_gate1`** — strongest uncapped gate anchor
- **`strict_f2`** — strong simpler strict-force anchor
- **`strict_f3`** — deeper forced anchor
- **`strict_gate2`** — important alternate gate emphasizing upstream coverage metrics on earlier slices

These remain useful ablations and comparison anchors, but they are not the current default.

## What is finalized vs not finalized

### Finalized now
- the repository's strict phased F1 → F2 → F3 law as the correct experimental control discipline
- the broader operational default on the evaluated broader strict-phased surface: **`strict_gate1_cap_k6`**

### Not fully closed yet
- broader independent confirmation beyond the currently evaluated broader surface
- stronger external-baseline completeness closure
- broader real-model evidence and final manuscript-facing external comparison maturity

## Current safest broader-surface conclusion

> **Strict phased shallow coverage is now the correct experimental protocol, and `strict_gate1_cap_k6` is the repository's current broader operational default on the evaluated broader strict-phased surface.**

## Current reading path

Read these first:
1. `CURRENT_PROMOTED_METHOD_LINE_2026_04_20.md`
2. `FINAL_STRICT_PHASED_DEFAULT_DECISION_EVAL_20260421T042913Z.md`
3. `CURRENT_RESULTS_AND_ARTIFACTS_INDEX_2026_04_20.md`
4. `NEW_HUNDRED_NEWEST_VS_BEST_FAILURE_STATISTICS_20260421T032711Z.md`
5. `CURRENT_SAFE_CLAIMS.md`

## Practical next step

The next highest-value work is no longer to guess the default model. It is to:
- strengthen broader independent confirmation of `strict_gate1_cap_k6`,
- tighten external-baseline completeness,
- and consolidate manuscript-facing tables/claims around the finalized current default.
