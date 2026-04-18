# Diagnostic reading path (2026-04-18)

## Purpose

This note is the shortest collaborator-facing path for understanding:
- what the current leading method direction is,
- what recently failed,
- how to interpret those failures,
- and what diagnostic artifacts or next passes should be used before proposing another large method change.

It is not a replacement for the canonical docs. It is a compact bridge from:
- **current project truth**
- to **current leading direction**
- to **current failure diagnosis**.

## Start here if you want the shortest current diagnostic picture

Read in this order:
1. `CURRENT_LEADING_DIRECTION_2026_04_17.md`
2. `CURRENT_METHOD_SUMMARY_AND_GAPS.md`
3. `WHAT_IS_NOT_WORKING_NOW.md`
4. `CURRENT_BOTTLENECKS.md`
5. `EXPERIMENT_LEDGER_2026_04_18.md`
6. `CONTINUATION_PLAN_2026_04_18.md`

## Current diagnostic picture in one page

### What the repo currently believes

The strongest current interpretation is:
- many recent bounded fixes reused the same one-step / local target family,
- those fixes were often negative or mixed,
- the first recent line with a meaningful positive signal is the **multi-step branch-utility target** line,
- but that signal is still **promising, not yet trustworthy**.

### What not to overread

Do not overread the repo as saying:
- the problem is solved,
- the multistep line is already robust,
- or all earlier ambiguity-focused lines were useless.

The better reading is:
- the earlier failures narrowed the diagnosis,
- and the multistep line is the first currently plausible break in that pattern.

## Current dominant diagnostic question

The main question now is:

> **Is the multistep target line genuinely improving hard close-branch discrimination, or is the current positive signal still too small-support and fragile to trust?**

That is the most important question to answer before broadening into another major method family.

## Recent negative lines that should not be repeated casually

Treat these as already pressure-tested and not current default next steps:
- conditional near-tie information expansion,
- probabilistic branch-value allocation,
- opportunity-intensity-weighted upstream supervision,
- statewise supervision-object reformulation,
- allocation-regret target reformulation.

These are still useful evidence, but they are not the default continuation path.

## What kind of diagnostics are currently highest value

Highest-value near-term diagnostics are:
1. matched validation of the multistep line,
2. disagreement analysis between one-step and multistep targets,
3. support-size and hard-slice caveat checks,
4. concrete failure-case extraction for the current leading method,
5. natural-language or human-readable reconstruction of what current failures have in common.

## Rule of thumb for the next pass

Before launching another method pass, ask:
1. does it sharpen the current leading multistep diagnosis,
2. or does it directly explain current dominant failure cases,
3. or does it add clearly new supervisory information rather than another small tweak around the same local signal?

If the answer is no, it is probably not the best next move.

## Recommended paired code/doc path

If you want to understand both the diagnostic story and the runnable entry points, pair this note with:
- `../scripts/CANONICAL_START_HERE.md`
- `CURRENT_LEADING_DIRECTION_2026_04_17.md`
- `EXPERIMENT_LEDGER_2026_04_18.md`
- `CONTINUATION_PLAN_2026_04_18.md`

## Conservative takeaway

The repository should currently be read as:

> the main problem is no longer “find any new controller tweak,” but rather “understand whether longer-horizon target semantics are the first real improvement, and what current failure cases still reveal about the remaining gap.”
