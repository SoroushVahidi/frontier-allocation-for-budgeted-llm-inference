# Next phase plan (2026-04-16)

## Purpose

This note is the updated next-phase plan after the latest stop-vs-act bounded passes.

It supersedes older “next lightweight steps” notes for the current stop-vs-act phase, while keeping them for provenance.

---

## Current phase objective

The current phase objective is:

**improve the local ACT-vs-STOP comparator so that STOP better reflects the downstream opportunity cost of preserving compute.**

This is now more precise than the older formulation “improve target stability.”

Target stability still matters, but the sharper current issue is the meaning of STOP under bounded future allocation.

---

## Main current diagnosis

The project has already tried several sensible fixes:
- uncertainty/threshold refinements,
- label-band refinements,
- one-step counterfactual target,
- small-horizon ACT-vs-STOP target,
- repeated averaging / target stabilization,
- matched-RNG comparator,
- one-step policy-coupled STOP reallocation.

The consistent lesson is:
- better local estimates are not enough if the comparator is still not aligned,
- and one-step policy-coupled STOP remains too shallow.

So the current best diagnosis is:

**the remaining high-value problem is a bounded, reallocation-aware, policy-coupled STOP baseline that better represents future use of preserved compute.**

---

## Immediate next experimental direction

### Highest-priority next step
Run a bounded pass on:

**slightly longer-horizon policy-coupled STOP reallocation**

while keeping:
- the current default stop-vs-act setup as anchor,
- the same lightweight simulation path,
- and the same conservative matched-grid regime.

### Why this is next
Because the current evidence suggests:
- one-step policy-coupled STOP is still too local,
- matched randomness alone does not fix the semantics,
- and preserved compute likely needs a slightly richer future-policy interpretation.

---

## What a good next target should mean

A stronger STOP baseline should approximate:

- **ACT**: spend one unit of compute on the current branch now, then continue under the normal bounded downstream policy,
- **STOP**: do not spend that unit here now; preserve it and let the downstream allocator reuse it naturally over a small bounded future horizon.

The important part is that STOP should represent:
- released resource,
- downstream policy reuse,
- same remaining-budget context,
- and as much matched future context as practical.

---

## Promotion rule for this phase

Do **not** promote a new mode unless bounded evidence shows:
- improved mean margin versus the heuristic baseline,
- improved win/loss counts versus the current default,
- and at least comparable or better local comparator stability.

If these are not met:
- keep the current default,
- preserve the new mode as provenance,
- and continue treating the line as promising but mixed.

---

## Explicit non-goals right now

Do **not** prioritize:
- heavier controller models,
- broad dataset scaling,
- broad benchmark expansion,
- another threshold-only tweak,
- a major controller redesign,
- or a search for more existing external labeled data as the main immediate fix.

---

## Secondary priorities after the next pass

If the longer-horizon policy-coupled STOP baseline is still weak, then the next likely directions are:
- slightly richer bounded opportunity-cost targets,
- better downstream-policy coupling for preserve-budget paths,
- or heavier label generation later when more compute becomes available.

But those are secondary until the next bounded pass is tested.

---

## Bottom line

The next phase is not about inventing a different controller family.

It is about making the STOP side of the local stop-vs-act comparison more faithful to:

**what the downstream allocator would actually do with preserved compute.**
