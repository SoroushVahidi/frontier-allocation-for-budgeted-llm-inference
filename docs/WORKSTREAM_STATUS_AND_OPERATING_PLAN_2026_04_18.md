# Workstream status and operating plan (2026-04-18)

## Purpose

This note records:
- what workstreams are active,
- what state each workstream is in,
- what should happen next in each one,
- and how to operate the repository without losing the current thread.

## Current workstreams

### Workstream A: canonical project framing and paper story
Status:
- stable enough for current use.

Current interpretation:
- fixed-budget frontier allocation / branch allocation,
- next-step compute assignment over active branches,
- anti-collapse and supervision-target quality,
- not the old binary revise-routing story.

What next:
- keep this framing fixed unless very strong new evidence requires broad repositioning.

### Workstream B: current leading method line
Status:
- active and highest priority.

Current line:
- multi-step branch-utility targets.

Current state:
- promising,
- survived bounded follow-up better than nearby ideas,
- but not yet trustworthy enough for a strong final claim.

What next:
- continue targeted validation and dominant-failure-group analysis.

### Workstream C: current failure diagnosis
Status:
- active and highly useful.

Current state:
- current leading method now has both numeric failure extraction and natural-language dominant-group diagnosis,
- dominant current group points to delayed-payoff overvaluation relative to immediate next-step value/outside-option strength.

What next:
- use failure-case understanding to choose the next experiments rather than broad search.

### Workstream D: bounded idea pressure-testing
Status:
- many recent passes completed.

Current state:
- several nearby ideas already recorded as negative or mixed.

What next:
- do not casually repeat them without a strong new reason.

### Workstream E: repo organization and collaborator navigation
Status:
- active and improving.

Current state:
- top-level navigation is much better than before,
- but should keep being updated whenever a new leading method or new diagnostic family becomes canonical.

What next:
- integrate new major casebooks / validation passes into the main reading path once they become current.

## Operating rules for the next phase

### Rule 1
Prefer experiments that explain the current dominant failure group.

### Rule 2
Prefer experiments that materially change the target object or control loop over another small scalar-score tweak.

### Rule 3
Keep the branch-allocation framing fixed.

### Rule 4
Every meaningful pass should leave behind:
- a repo-facing note,
- machine-readable outputs,
- and a clear go / no-go or continue / drop conclusion.

### Rule 5
Do not let exploratory branches silently replace canonical interpretation.

## Recommended near-term operating sequence

### Immediate
1. Keep the multistep line as the active leading method line.
2. Continue repository polish only in ways that improve navigation and truthfulness.
3. Use the natural-language failure casebook when choosing the next experiment.

### Next bounded experiment
- discounted multistep target,
- or another bounded horizon-aware target variant directly aimed at the dominant delayed-payoff failure group.

### Next stronger concept experiment
- compute-response curve prediction,
- optionally paired with rank-instability supervision.

## Suggested doc path for collaborators right now

For a collaborator who wants the shortest correct path, recommend:
1. `CANONICAL_START_HERE.md`
2. `CURRENT_LEADING_DIRECTION_2026_04_17.md`
3. `DIAGNOSTIC_READING_PATH_2026_04_18.md`
4. `PROJECT_SITUATION_REPORT_2026_04_18.md`
5. `RESEARCH_IDEAS_AND_NEXT_STEPS_2026_04_18.md`
6. `NATURAL_LANGUAGE_FAILURE_CASEBOOK_DOMINANT_GROUP_2026_04_18.md`
7. `CONTINUATION_PLAN_2026_04_18.md`

## Suggested execution path for operators

For someone who wants to run or modify current experiments:
1. `../scripts/CANONICAL_START_HERE.md`
2. `CURRENT_LEADING_DIRECTION_2026_04_17.md`
3. `DIAGNOSTIC_READING_PATH_2026_04_18.md`
4. `PROJECT_SITUATION_REPORT_2026_04_18.md`
5. `../scripts/run_multistep_branch_utility_target_experiment.py`
6. the latest failure-case or validation artifacts relevant to the current pass

## What success would look like in the next phase

A good next phase would produce at least one of the following:
- a stronger, more trustworthy validation of the multistep line,
- a bounded target refinement that clearly reduces the dominant failure pattern,
- or a more conceptually different prediction object that cleanly beats scalar-target refinements.

## Conservative conclusion

The repository is now in a better phase than before:
- the framing is cleaner,
- the diagnosis is narrower,
- and there is a real current lead.

The next phase should be run as **targeted diagnosis-driven progress**, not broad method proliferation.
