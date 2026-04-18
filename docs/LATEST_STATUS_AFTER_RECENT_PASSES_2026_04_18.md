# Latest status after recent bounded passes (2026-04-18)

## Purpose

This note records the shortest current repository-facing update after the most recent bounded method and observability passes.

It is intended to answer:
- what the newest experiments changed,
- what they did **not** change,
- what the current bottleneck now looks like,
- and what should happen next.

## Short current answer

The shortest honest update is:

- the repository has now pressure-tested several stronger nearby target/control ideas,
- none of the recent bounded refinements clearly beat the current multistep-k3 line,
- and the most important positive infrastructure result is now **forward-looking branch observability** for future runs.

In practical terms:

> the repo is now better at knowing what has **not** worked, and is now finally equipped to inspect future real failures semantically rather than only through proxy signals.

## What was just added and what it means

### 1. Discounted multistep target
Status:
- integrated and evaluated.

What happened:
- helped some delayed-payoff failure diagnostics,
- but did not produce a clear aggregate accepted-metric win over the current multistep family.

Interpretation:
- useful diagnostic evidence,
- not a clear replacement-family win.

### 2. Compute-response curve prediction
Status:
- integrated as a first-class target family and evaluated.

What happened:
- changed the prediction object from a single scalar to a short horizon response object,
- but still did not beat the current multistep-k3 family on accepted/hard-slice metrics in the bounded pass.

Interpretation:
- richer short-horizon target structure alone was not enough.

### 3. Rank-instability supervision
Status:
- integrated as a first-class supervision object and evaluated.

What happened:
- produced mostly diagnostic value,
- but did not beat current multistep-k3 in the bounded pass.

Interpretation:
- instability looks meaningful as a signal,
- but its current use is not yet enough to improve decisions.

### 4. Instability-to-decision coupling / defer activation
Status:
- explicit bounded policy family implemented and evaluated.

What happened:
- no policy variant beat the current multistep-k3 baseline,
- defer-heavy variants hurt strict hard-slice accepted accuracy.

Interpretation:
- better ambiguity-aware gating alone, in this bounded form, was still not enough.

### 5. Rich failure-case recovery from historical artifacts
Status:
- bounded recovery pass implemented and run.

What happened:
- historical selected cases remained proxy-only,
- no direct branch reasoning traces or direct method/oracle final branch answers were recoverable from the inspected old artifacts.

Interpretation:
- old artifact sets are not sufficient for true semantic branch diagnosis.

### 6. Branch observability instrumentation
Status:
- implemented at the frontier/state materialization path and validated with a bounded smoke run.

What happened:
- future instrumentation-enabled runs can now preserve:
  - branch text,
  - branch reasoning text,
  - branch final-answer text,
  - normalized final answers,
  - extracted numbers,
  - branch role summaries,
  - explicit provenance and recoverability metadata.

Interpretation:
- future real runs can support true semantic failure diagnosis,
- even though old runs remain mostly unrecoverable post hoc.

## What these results collectively now mean

The current repository-backed interpretation is:

- the multistep family remains the best current bounded method lead,
- but recent nearby refinements did **not** produce a clear successor,
- and the repo may be near the limit of what the current artifact set and current feature/signal substrate can support through bounded target/control tweaks alone.

The remaining issue is therefore less well-described as:
- “we just need another richer target,”
- or “we just need another defer rule,”

and better described as:

> **we now need fresh, observability-enabled real failure examples to understand what the branches are actually doing semantically, and then design the next method change from those examples.**

## Updated bottleneck statement

A stronger current bottleneck statement is:

> **The repository now appears bottlenecked not only by supervision/control design, but by the need for real semantic failure analysis on new observability-enabled runs.**

Equivalently:

> the repo has now pressure-tested enough nearby target/control ideas that the highest-value next step is to inspect real worst failures with preserved branch reasoning and final answers.

## What should happen next

### Best immediate next step
Run a bounded **real trace-backed observability-enabled experiment** and then extract the worst real failures into a semantic casebook that includes:
- full problem text,
- method-chosen branch reasoning,
- oracle-best branch reasoning,
- final answers for both when recoverable,
- where the reasoning diverges,
- and what design lesson each case suggests.

### What should not be the default next move
Do **not** make the next main step:
- another nearby target-weighting tweak,
- another auxiliary target family in the same bounded neighborhood,
- another generic defer-policy sweep,
- or another attempt to semantically recover old non-instrumented artifacts.

These may still matter later, but they are no longer the highest-leverage default move.

## Best single-sentence summary

> The repository is now in a stronger diagnostic state: recent bounded target/control refinements did not clearly surpass multistep-k3, but future runs can now preserve true branch-semantic evidence, so the most valuable next step is a real observability-enabled worst-failure casebook.
