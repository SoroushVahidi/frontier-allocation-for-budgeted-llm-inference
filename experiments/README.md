# Experiments

This directory contains experiment code, scripts, and results for the project.

> **Placeholder — experiments will be added as the research develops.**

---

## Planned Benchmark Experiments

All experiments use a **matched-budget evaluation protocol**: strategies are compared at the same total inference compute budget, so differences in performance reflect allocation strategy rather than total compute.

### Benchmarks

| Benchmark | Description | Priority |
|-----------|-------------|----------|
| GSM8K | Grade-school math word problems | High |
| MATH | Competition math (5 difficulty levels) | High |
| AIME-style subsets | Hard competition math problems | Medium |

### Experiment Types

1. **Baseline comparisons**: Uniform allocation, best-of-N, greedy search.
2. **Adaptive allocation**: Proposed strategy vs. baselines at matched budgets.
3. **Noise ablations**: Vary the quality of the value estimate; measure robustness.
4. **Budget scaling**: Fix strategy, vary total budget; measure performance curve.

---

## Evaluation Protocol

- **Matched-budget comparison**: All methods receive the same total token / call budget.
- **Metric**: Exact-match accuracy (for math) or pass@1 (for code).
- **Repetitions**: Multiple seeds per experiment; report mean ± std.
- **Output**: Results saved to `outputs/` (gitignored); summary tables in experiment notes.

---

## File Organization (Planned)

```
experiments/
├── README.md               # This file
├── baselines/              # Baseline allocation strategies
├── adaptive/               # Adaptive allocation strategies
└── eval/                   # Evaluation harness and metrics
```

---

## Notes

- Do not commit raw model outputs or large data files.
- All experiments should be runnable from configs in `configs/`.
- See `scripts/smoke_test.py` for a minimal end-to-end test.
