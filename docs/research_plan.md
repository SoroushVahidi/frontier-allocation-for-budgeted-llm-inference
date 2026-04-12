# Research Plan

> **Living document — updated as the project evolves.**

---

## Immediate Next Steps

1. Complete initial literature review (see checklist below).
2. Finalize the candidate problem formulation in `docs/problem_statement.md`.
3. Implement a minimal toy experiment to explore the allocation problem empirically.
4. Identify 2–3 theoretical results worth pursuing based on the literature gap.
5. Decide on the primary benchmark and evaluation protocol.

---

## Literature Review Checklist

### Test-Time Compute Scaling
- [ ] Snell et al. (2024): Scaling LLM Test-Time Compute Optimally
- [ ] OpenAI o1 technical report / blog post
- [ ] DeepSeek-R1 technical report
- [ ] Brown et al. (2024): Large Language Monkeys (best-of-N scaling)

### Process Reward Models / Verifiers
- [ ] Lightman et al. (2023): Let's Verify Step by Step
- [ ] Math-Shepherd (Wang et al., 2024)
- [ ] OmegaPRM / RL-based verifier training papers

### Tree Search for LLM Reasoning
- [ ] Yao et al. (2023): Tree of Thoughts
- [ ] Hao et al. (2023): RAP (Reasoning via Planning)
- [ ] MCTS-based LLM reasoning papers (survey)

### Bandit Theory / Budget Allocation
- [ ] Best-arm identification: Audibert & Bubeck (2010)
- [ ] Pure exploration in multi-armed bandits (survey)
- [ ] Parallel bandit problems

### Benchmarks
- [ ] Cobbe et al. (2021): GSM8K
- [ ] Hendrycks et al. (2021): MATH dataset
- [ ] AIME problem sets and evaluation protocols

---

## Theory Milestones

| Milestone | Description | Status |
|-----------|-------------|--------|
| T1 | Formal model of budget allocation over reasoning tree | Planned |
| T2 | Analysis of uniform allocation baseline | Planned |
| T3 | Greedy allocation policy under noiseless value estimates | Planned |
| T4 | Effect of noise on greedy policy (regret or success probability) | Planned |
| T5 | Optimal allocation policy (or approximation) | Planned |
| T6 | Reduction to / comparison with bandit problem | Planned |

---

## Experiment Milestones

| Milestone | Description | Status |
|-----------|-------------|--------|
| E1 | Set up benchmark evaluation harness (GSM8K) | Planned |
| E2 | Implement uniform and best-of-N baselines | Planned |
| E3 | Matched-budget evaluation protocol | Planned |
| E4 | Implement simple adaptive allocation strategy | Planned |
| E5 | Evaluate on MATH dataset | Planned |
| E6 | Ablation: effect of value estimate noise | Planned |
| E7 | AIME-style subset evaluation (if feasible) | Planned |

---

## Paper-Writing Milestones

| Milestone | Description | Status |
|-----------|-------------|--------|
| P1 | Draft problem statement and motivation section | Planned |
| P2 | Draft related work section | Planned |
| P3 | Draft theory section (model + main result) | Planned |
| P4 | Draft experiments section | Planned |
| P5 | Internal draft for review | Planned |
| P6 | Submit to venue (NeurIPS / ICML / ICLR / COLT) | Planned |

---

## Risks and Alternatives

| Risk | Mitigation |
|------|------------|
| Problem formulation does not yield clean theory | Broaden to empirical contribution; focus on algorithm design |
| Adaptive allocation does not improve over baselines | Characterize when it does/does not; negative result is publishable |
| Compute cost of large-scale experiments | Use smaller models or cached completions; focus on mid-scale benchmarks |
| Related work makes the contribution redundant | Continuously monitor arxiv; pivot formulation if needed |
| Noisy value estimates make problem intractable | Restrict to structured noise models (e.g., sub-Gaussian) |
