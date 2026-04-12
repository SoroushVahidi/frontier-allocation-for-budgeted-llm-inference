# TODO

First 10 concrete tasks for this project.

---

- [ ] **1. Literature review: test-time compute scaling**
  Read and take notes on Snell et al. (2024), OpenAI o1 report, DeepSeek-R1, and Brown et al. (2024). Add notes to `references/papers/`.

- [ ] **2. Literature review: process reward models**
  Read Lightman et al. (2023) and Math-Shepherd (Wang et al., 2024). Summarize relevance to value estimation in `references/papers/`.

- [ ] **3. Literature review: tree search for LLM reasoning**
  Read Tree of Thoughts (Yao et al., 2023) and RAP (Hao et al., 2023). Note connections to this project's formulation.

- [ ] **4. Refine the problem formulation**
  Based on the literature, update `docs/problem_statement.md` with a cleaner formal model. Decide on budget unit and tree vs. graph structure.

- [ ] **5. Identify the key baseline**
  Determine the primary comparison point: uniform allocation, best-of-N, or beam search? Justify in `docs/research_plan.md`.

- [ ] **6. Set up GSM8K evaluation harness**
  Implement a minimal script to evaluate a model on GSM8K with a fixed token budget. Add to `experiments/`.

- [ ] **7. Implement uniform allocation baseline**
  Implement uniform compute allocation as a baseline strategy. Evaluate on GSM8K.

- [ ] **8. Draft the formal model**
  Write a first draft of the formal problem model in `theory/model.md`, including notation, assumptions, and objective.

- [ ] **9. Survey bandit literature for connections**
  Read Audibert & Bubeck (2010) on best-arm identification. Assess whether the budget allocation problem reduces to a known bandit problem.

- [ ] **10. Define matched-budget evaluation protocol**
  Write a clear protocol for matched-budget comparisons in `experiments/README.md`. Ensure all future experiments follow this protocol.
