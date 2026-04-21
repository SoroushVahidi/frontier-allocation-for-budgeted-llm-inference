# Current default-model and strict-phased status (2026-04-21)

## Purpose

This note is the shortest current answer to:
- what the newest strict-phased hard-coverage experiments changed,
- what the current strongest default-candidate methods are,
- and what is still needed before the repository should finalize a default promoted model.

## Current status in one paragraph

The repository has now upgraded the hard early-coverage experiments from a looser minimum-depth interpretation to a **strict phased law**:

> **finish F1 first, then finish F2, then finish F3**

for the forced shallow-coverage phases over root families. This made the intervention cleaner and more faithful to the intended budget discipline. Under this stricter interpretation, the earlier simple "full forced depth-3" advantage weakened, and the strongest candidates shifted toward **strict phased gate variants**, especially **Gate 1** and **Gate 2**, rather than an unconditional forced-F3 default.

## Strict phased law

For the first three levels, the controller now enforces:
- **F1 must complete before F2 can start**,
- **F2 must complete before F3 can start**,
- and no family may enter a deeper forced phase while another required root family is still below the current forced phase depth.

Within a phase, ordering remains controller-driven by the normal priorities / scores / anti-collapse logic. The intervention constrains **eligibility**, not the within-phase priority order.

## Why this matters

The stricter law is better aligned with the practical compute-allocation question. If the controller may not have enough budget to assess all three shallow levels, it should first guarantee the shallower coverage before spending forced exploration budget on deeper levels.

This also means the current experiments are now easier to interpret scientifically: improvements can be attributed to true phased shallow coverage rather than to a looser min-depth behavior.

## Current strongest findings from the strict-phased failure-slice experiments

The strict-phased experiments still strongly beat the baseline on the frozen hundred-case failure surface, but they changed the relative ranking among the leading variants:
- **strict forced F2** remains strong,
- **strict forced F3** still helps, but is no longer clearly the best overall choice,
- **strict Gate 1** looks strongest on collapse-reduction and present-not-selected behavior,
- **strict Gate 2** looks strongest on upstream coverage and gold-in-tree style metrics.

So the repo's current decision is no longer simply "make forced F3 the default."

## Current best default candidates

At this point the repository should treat the following as the strongest default candidates pending broader matched evaluation:

### Candidate A: strict Gate 2
Use this when prioritizing:
- fewer absent-from-tree failures,
- stronger gold-in-tree behavior,
- and broader upstream coverage repair.

### Candidate B: strict Gate 1
Use this when prioritizing:
- reduced repeated same-family expansion,
- fewer present-not-selected errors,
- and a cleaner anti-collapse / selection compromise.

### Candidate C: strict forced F3
Still valuable as a simple strong anchor, but no longer the clear default under the stricter law.

## What is not yet finalized

The repository should **not** yet finalize the default promoted model solely from the frozen hundred-case slice.

The missing step is:
- a **broader matched evaluation** under the strict phased law,
- comparing at least baseline, strict forced F2, strict forced F3, strict Gate 1, and strict Gate 2.

That experiment should determine whether one of the strict gate variants really deserves to replace the simpler forced-F2 / forced-F3 anchors as the default promoted model.

## Current safest repository-facing conclusion

The safest current conclusion is:

> **Strict phased shallow coverage is now the correct experimental protocol. Under that protocol, the strongest default candidates are strict Gate 1 and strict Gate 2 rather than an unconditional forced-F3 default, but broader matched evaluation is still required before finalizing the repository’s default promoted model.**

## Current reading path

Read these first:
1. `CURRENT_PROMOTED_METHOD_LINE_2026_04_20.md`
2. `CURRENT_RESULTS_AND_ARTIFACTS_INDEX_2026_04_20.md`
3. `STRICT_PHASED_HARD_EARLY_COVERAGE_REPORT_20260421T020917Z.md`
4. `HUNDRED_THREE_GATE_DESIGN_COMPARISON_STRICT_PHASED_20260421T022459Z.md`
5. `CURRENT_SAFE_CLAIMS.md`

## Practical next step

The next highest-value experiment is:
- broader matched evaluation under the strict phased F1 → F2 → F3 law,
- with direct comparison among strict forced F2, strict forced F3, strict Gate 1, and strict Gate 2,
- and an explicit default-model recommendation section in the resulting report.
