# Matched-coverage filtering result note (lightweight, pre-oracle)

## Setup
- Anchor kept fixed: current default stop-vs-act label path (`proxy_best_other_gain`, no stabilization).
- Three train-set variants on matched state pools per seed/budget: default, selective filtered, random filtered with matched retained coverage.
- Retained coverage for filtered variants: 0.70 of train rows (rounded per run).
- Grid: seeds=[31, 32, 33], budgets=[10, 14], train episodes=520, controller eval episodes=220.

## Aggregate highlights
- Selective vs matched-random: Δ controller avg_best_score = -0.0023.
- Selective vs matched-random: Δ controller accuracy = +0.0038.
- Selective vs matched-random: Δ controller avg_actions = +0.0000.
- Selective vs matched-random: Δ test ROC-AUC = -0.0009.
- Uncertainty slice (test labels): selective minus random uncertain-slice accuracy = -0.0143.

## Conservative interpretation
- This is a low-compute proxy-label study only; it is not oracle evidence.
- If selective > random at matched coverage, that is consistent with supervision-quality signal beyond pure data reduction.
- If selective gains also come with large action-rate shifts, matched-rate follow-up is still needed before causal claims about quality-only improvements.
- Use this as design input for later oracle-distillation: preserve matched-coverage random baselines and add matched-rate checks.
