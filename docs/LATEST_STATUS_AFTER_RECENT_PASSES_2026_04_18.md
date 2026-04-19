# Latest status after recent bounded passes (2026-04-18)

## Purpose

This note records the shortest current repository-facing update after the most recent bounded method, observability, and target-definition passes.

It is intended to answer:
- what the newest experiments changed,
- what they did **not** change,
- what the current bottleneck now looks like,
- and what should happen next.

## Short current answer

The shortest honest update is:

- the repository has now pressure-tested several stronger nearby target/control ideas,
- none of those nearby refinements clearly displaced the current multistep-k3 line as a broad successor,
- fresh observability-enabled runs now support real semantic failure diagnosis,
- and the newest bounded target-definition studies support **augmenting** the continuation-value oracle rather than replacing it globally.

In practical terms:

> the repo is now in a decision phase rather than a broad-experiment phase: the key question is no longer “what extra tweak should we try next,” but “what target/oracle definition should govern hard close-branch decisions?”

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
- implemented at the frontier/state materialization path and validated with a bounded smoke run, then extended on fresh real runs.

What happened:
- fresh instrumentation-enabled runs can preserve:
  - branch text,
  - branch reasoning text,
  - branch final-answer text when directly present,
  - normalized final answers,
  - extracted numbers,
  - branch role summaries,
  - explicit provenance and recoverability metadata.

Interpretation:
- fresh real runs can support true semantic failure diagnosis,
- even though old runs remain mostly unrecoverable post hoc.

### 7. Worst real failure casebook with reasoning
Status:
- bounded real trace-backed worst-failure casebook implemented and run.

What happened:
- direct reasoning recovery for both method and oracle branches became available on selected worst cases,
- contested cases showed that method and oracle branches can share early reasoning while differing in visible completion or answer-completeness.

Interpretation:
- semantic/objective mismatch is now a directly inspectable repository object rather than only a proxy-level suspicion.

### 8. Completion-aware decision study
Status:
- bounded completion-aware decision experiment implemented and run.

What happened:
- completion-aware variants improved oracle-alignment metrics on the bounded slice,
- but did not robustly resolve the semantic/objective-mismatch pattern by themselves.

Interpretation:
- completion/answer-evidence is a real signal,
- but it is not a global replacement for continuation value.

### 9. Final-answer recovery on contested states
Status:
- bounded branch-emission and contested-state final-answer recovery added and run.

What happened:
- direct final-answer recovery remained limited,
- but recovered direct-or-completion final-answer recovery became sufficient on the bounded contested slice to support semantic adjudication.

Interpretation:
- the repository can now decide contested semantic cases much more concretely than before.

### 10. Oracle mismatch study
Status:
- bounded continuation-vs-completion-vs-hybrid oracle comparison implemented and run.

What happened:
- disagreement across oracle definitions was small and concentrated in near-tie states,
- and the hard conclusion was to **augment the current oracle**, not replace it.

Interpretation:
- the continuation-value oracle remains a good core object,
- but bounded completion-aware correction is justified in disagreement slices.

## What these results collectively now mean

The current repository-backed interpretation is:

- the multistep family remains the best current bounded method lead,
- recent nearby refinements did **not** produce a broad successor,
- fresh semantic failure analysis is now available on new runs,
- and the main unresolved question has narrowed to the exact target/oracle definition for hard close-branch states.

The remaining issue is therefore less well-described as:
- “we just need another richer target,”
- or “we just need another defer rule,”

and better described as:

> **we now need to freeze the target/oracle definition for hard disagreement states: continuation value as the core signal, with bounded completion-aware correction only where semantic branch quality and immediate continuation value diverge.**

## Updated bottleneck statement

A stronger current bottleneck statement is:

> **The repository is currently bottlenecked by target-definition clarity, not by lack of more nearby experiments.**

More concretely:

> the main remaining work is to formalize and validate the right hybrid oracle/controller definition for near-tie disagreement states now that fresh semantic case adjudication is possible.

## What should happen next

### Best immediate next step
Pause broad method coding and consolidate the current target-definition decision.

That means:
- use the fresh semantic casebook plus recovered final answers to adjudicate contested disagreement cases,
- freeze the current repository stance on the oracle/target,
- and only then decide what the next admissible experiment should be.

### Current recommended stance
The current bounded evidence supports this stance:

> **keep continuation value as the core oracle/target, and augment it with bounded completion-aware evidence only in disagreement slices, especially near-ties.**

### What should not be the default next move
Do **not** make the next main step:
- another nearby target-weighting tweak,
- another auxiliary target family in the same bounded neighborhood,
- another generic defer-policy sweep,
- another broad controller variant pass,
- or another attempt to semantically recover old non-instrumented artifacts.

These may still matter later, but they are no longer the highest-leverage default move.

## Best single-sentence summary

> The repository is now in a stronger decision state: recent bounded target/control refinements did not clearly surpass multistep-k3, fresh observability-enabled runs now permit semantic adjudication of contested failures, and the current evidence supports a continuation-value core with bounded completion-aware correction in near-tie disagreement states.

Additional real-model note:
- `docs/BROAD_DIVERSITY_AGGREGATION_COHERE_GEMINI_CONFIRMATION_2026_04_18.md` documents the Cohere+Gemini-only bounded confirmation sweep and its provider-limited outcome.
