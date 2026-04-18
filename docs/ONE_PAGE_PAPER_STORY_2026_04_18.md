# One-page paper story (2026-04-18)

## What is the paper?

A narrow paper on **fixed-budget next-step branch allocation for LLM reasoning**:
- we treat test-time reasoning as repeated allocation of scarce compute across active branches,
- we show a continuation-centered multistep allocation line is a strong current method,
- and we contribute diagnostics that reveal where this method succeeds and where target mismatch remains.

## Why does it matter?

Most broad adaptive-compute narratives blur the core decision:
- not “more compute or less,”
- but **where the next compute unit should go** under budget.

Getting this decision wrong is costly precisely in close-call states, where branch options look similar but lead to different outcomes.

## What did we actually show?

1. The repository now has a clear branch-allocation framing and comparison discipline.
2. Multistep continuation-centered allocation remains strongest among nearby bounded alternatives tested.
3. Many tempting nearby refinements did not yield broad successor wins.
4. New observability + final-answer recovery enables direct semantic adjudication on contested failures.
5. Oracle-definition disagreement is small but non-zero and concentrated in near-tie slices in bounded runs.
6. Therefore, the strongest current stance is: continuation as core target, plus bounded completion-aware correction in disagreement slices.

## Where are we strongest?

In **hard ambiguity-sensitive near-tie branch-allocation states**:
- where target fidelity matters more than extra heuristic tweaks,
- and where semantic disagreement analysis materially improves scientific clarity.

## What remains unresolved?

- Broad universal method dominance is not established.
- Global replacement of continuation by completion-aware objectives is not supported.
- External baseline closure is still partial in places.
- The remaining key question is precise hybrid target definition and validation under broader ambiguity-diverse data.

## Paper writing rule (short)

Write this as:
- a **strong narrow contribution** with clear regime-of-strength and explicit limitations,

not as:
- a universal best-method claim.

## Canonical frozen summary

> We contribute a defensible fixed-budget branch-allocation formulation, a strong continuation-centered multistep method line, and an ambiguity-focused diagnostic framework showing that bounded completion-aware correction is useful in near-tie disagreement states without justifying global objective replacement.
