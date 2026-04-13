# Current experimental status (2026-04-13)

This note summarizes the current empirical state of the adaptive branch-scoring line.

## 1. What has been established

### Internal heuristic baselines are strong
The strongest simple internal baselines remain difficult to beat robustly, especially `adaptive_relative_rank` and, in some settings, `adaptive_score_plus_progress`.

### Learned scoring can win in individual settings
Several learned scorer variants have shown single-setting wins over the strongest hand-designed baseline, but these wins have not yet held robustly across multi-seed / multi-budget / multi-initial-branch sweeps.

### Weak pointwise and static-promise targets are not enough
The project has already learned that purely static or weak local targets are insufficient for robust controller-level gains.

### Better local targets help, but not enough yet
Continuation/progress-style targets and lightweight subtree/future-snapshot targets improved single-setting controller behavior, but robustness is still missing.

### Compact tabular representations still appear limiting
Even stronger logged-trajectory supervision with compact feature sets and simple linear/logistic models has not yet robustly beaten the strongest heuristic baselines.

## 2. Current empirical bottleneck

The current bottleneck is likely no longer only target construction. It is increasingly a combination of:
- imperfect long-horizon target alignment,
- limited path-state representation,
- and unstable generalization across seeds / budgets / branching settings.

## 3. Current best safe claim

A safe internal claim is:

> Learned branch scoring is competitive and can outperform strong hand-designed ranking rules in some settings, but the current learned scorer family does not yet robustly outperform the best internal heuristics across controlled robustness sweeps.

## 4. Implication for next experiments

The next meaningful progress is more likely to come from one of these:
1. a stronger path/state representation,
2. a better budget-aware continuation target,
3. or a combination of both.

Further small proxy tweaks on the same weak feature backbone are less likely to produce a decisive gain.

## 5. Status

This note is intentionally conservative and should be updated when a learned scorer robustly beats the strongest internal heuristic or when the main evaluation protocol changes.