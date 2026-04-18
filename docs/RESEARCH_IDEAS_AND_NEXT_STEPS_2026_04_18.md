# Research ideas and next steps (2026-04-18)

## Purpose

This note records:
- the strongest current research ideas,
- which ideas are already partly or fully pressure-tested,
- what kind of next experiments are still worth running,
- and the recommended ordering of those next experiments.

This note is intended to reduce repeated rediscovery of nearby weak ideas.

## Current diagnosis to start from

The current best repository-backed diagnosis is:
- one-step/local targets appear too weak for the hardest close-branch states,
- the current multistep line is the first recent promising break from that pattern,
- but the dominant remaining failure group suggests the method can still overvalue delayed payoff relative to immediate next-step value and outside-option strength.

Any new idea should be judged against that diagnosis first.

## Ideas that are already pressure-tested enough to not be default next steps

These ideas are informative evidence, but they should not be the default next move without a new reason:
- conditional near-tie extra-information expansion,
- probabilistic branch-value allocation,
- opportunity-intensity-weighted upstream supervision,
- statewise supervision-object reformulation,
- allocation-regret target reformulation,
- broad scalar-target tweaks that do not materially change the prediction object or control loop.

## Highest-priority bounded ideas now

### 1. Discounted multistep targets
Core idea:
- nearer expected gains should count more than farther expected gains.

Why it is plausible:
- the dominant current failure pattern is delayed-payoff overvaluation.

Why it is still bounded:
- it modifies target construction while reusing the current multistep path.

Main risk:
- too much discounting may collapse the method back toward one-step behavior and destroy the useful part of multistep signal.

### 2. Compute-response curve prediction
Core idea:
- predict the short compute-response curve of each branch (gain after 1, 2, 3... additional units) rather than a single scalar score.

Why it is stronger than another scalar-target tweak:
- it changes the prediction object itself.

Why it is attractive now:
- it directly separates immediate marginal gain from delayed payoff.

Main risk:
- labels may become noisier and harder to learn than the current scalar targets.

### 3. Rank-instability supervision
Core idea:
- supervise not only which branch wins, but whether that ranking is fragile under small bounded continuation changes.

Why it fits the current repo state:
- current failures are not only wrong rankings, but often rankings that look too confident.

Main risk:
- instability labels can be noisy or conflate stochasticity with genuine fragility.

## Strong combined idea

The strongest combined next idea is:

> **compute-response curve prediction + rank-instability supervision**

Why this combination is attractive:
- response curves target the immediate-vs-delayed payoff confusion,
- instability supervision targets the false-confidence side of the remaining failures.

This is currently the strongest conceptually different research direction if bounded scalar-target refinements stall.

## Medium-priority ideas

### 4. Explicit information-gathering actions under budget
Core idea:
- allow a small diagnostic/probe action inside the fixed budget for hard near-tie states.

Why it is meaningful:
- it changes the control loop rather than just asking the scorer to do everything.

Main risk:
- the probe may consume budget without changing enough decisions.

### 5. Distributional branch utility
Core idea:
- predict a distribution or quantiles for branch utility rather than a single point estimate.

Why it is attractive:
- it may represent overlap and uncertainty more honestly on hard close cases.

Main risk:
- better uncertainty language may not translate into better decisions unless paired with a stronger control action.

## Lower-priority but still plausible idea

### 6. Latent-regime / mixture-of-experts branch scorers
Core idea:
- different hidden branch regimes may need different ranking rules.

Why it is weaker as a first next step:
- it adds complexity early,
- and it is easier to overfit or tell a less clean paper story unless the regime separation is very crisp.

## Practical next-step order

### Recommended order if we want bounded near-term progress
1. discounted multistep target experiment,
2. richer failure-case diagnosis under the current multistep line,
3. compute-response curve prediction,
4. rank-instability auxiliary supervision,
5. combined response-curve + instability experiment.

### Recommended order if we want stronger concept shift immediately
1. compute-response curve prediction,
2. rank-instability supervision,
3. explicit information-gathering action for hard near-ties,
4. distributional branch utility,
5. mixture-of-experts only after a clearer heterogeneity story emerges.

## What to avoid repeating now

Avoid defaulting to:
- another threshold-only tweak,
- another confidence calibration pass with unchanged target semantics,
- another small reweighting of the same supervision family,
- or another generic fallback variant with no new diagnosis.

These may still be useful later, but they are not currently the highest-leverage moves.

## How to choose between the next two ideas

### Choose discounted multistep next if:
- you want the cheapest bounded follow-up,
- you want to test the dominant current failure pattern directly,
- and you want to stay close to the current promising line.

### Choose compute-response curve next if:
- you want the strongest conceptually different research step,
- you want to stop asking one scalar target to do everything,
- and you want a more paper-worthy change to the prediction object.

## Recommended current answer

If only one next experiment is chosen right now, the best practical split is:
- **bounded next experiment:** discounted multistep target,
- **stronger next research direction:** compute-response curve prediction with possible rank-instability supervision.

## Conservative conclusion

The repository now has enough evidence that the next strong ideas should change:
- the prediction object,
- the target horizon semantics,
- or the control loop,

rather than merely reweighting examples or shifting a threshold around the same scalar local target.
