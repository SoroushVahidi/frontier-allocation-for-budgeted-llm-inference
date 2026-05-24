# Regime-Aware Fixed-Pool Selection Research Roadmap (2026-05-24)

## A) Title and Abstract

**Regime-aware fixed-pool answer selection under matched inference budgets**

This roadmap defines a general ML framing for zero-extra-call answer selection over a precomputed fixed candidate pool (`frontier/default`, `L1`, `S1/budget-forcing`, `TALE/prompt-budgeting`). The selection problem is to pick the best available answer under a strict runtime constraint: no additional generation calls beyond the fixed pool. The central hypothesis is that optimal selection depends on the observed reliability regime of the source pool, not a single global voting rule.

## B) Problem Setting

- Fixed candidate pool per example: four precomputed sources.
- Matched generation budget contract across sources.
- Selector runtime budget: zero additional model calls.
- Allowed features: runtime-observable answer patterns, agreement structures, source metadata, and precomputed confidence proxies.
- Evaluation discipline: calibration/fit split vs held-out test split.
- Objective:
  - maximize held-out accuracy;
  - minimize oracle regret to best-in-pool source;
  - preserve robust behavior across providers/regimes.

## C) Ideas Tried So Far

| Idea | Motivation | Where It Helped | Where It Failed | Status |
|---|---|---|---|---|
| Agreement-only 2-of-3 vs frontier | Conservative override only with external majority | Reduced risky switching in some settings | No-majority cases keep wrong frontier; misses recoveries | Diagnostic (insufficient) |
| Pooled-4 vote with fallback | Use all four sources to exploit pooled signal | Strong on Cohere Final-300 (near-peer) | Underweights dominant source on Mistral | Keep (regime-conditional) |
| Always-S1 | Exploit strongest source when S1 dominates | Best on Mistral 300 | Harms Cohere where sources are near-peer | Reject as global policy; keep as dominant-regime branch |
| Provider-prior selector | Route by provider-level observed reliability | Matched best behavior in diagnostics across Cohere/Mistral | Coarse; can miss within-provider variation | Keep as baseline branch |
| Accuracy-spread regime selector | Detect heterogeneity and route pooled vs dominant | Matched near-peer vs dominant pattern in diagnostics | Needs calibrated thresholds and uncertainty handling | Validate next |
| Frontier fallback calibrated | Replace hard frontier fallback in no-majority | Conceptually addresses known failure mode | Not yet fully validated on held-out merged reruns | Validate next |
| Dominant-source veto | Override majority when strong dominance observed | Improves dominant-source slices | Can over-trigger if dominance estimate noisy | Validate next |
| Majority requires dominant-source when dominant | Guard against weak majorities in heterogenous pools | Improves logic coherence for Mistral-like regime | Needs confidence intervals/shrinkage | Validate next |
| Source-family discount (e.g., L1+TALE) | Reduce redundant correlated votes | Useful for diagnostics/interpretability | Did not clearly resolve Mistral gap alone | Diagnostic |
| Log-odds weighted vote | Weighted ensemble by source reliability | Flexible unification across regimes | Calibration instability with small samples | Diagnostic/validate next |
| Targeted failure-case reruns | Fast hypothesis testing on failure clusters | Helped generate useful candidate rules | Biased; cannot support final claims | Keep as hypothesis generation only |
| Error-correlation and double-fault diagnostics | Explain when voting helps/hurts | Clarified mechanism beyond raw wins | Correlation-only explanation was insufficient | Keep (analysis tool) |

## D) What Worked

- Pooled-4 works strongly on Cohere in a near-peer competence regime.
- S1/provider-prior behavior works on Mistral in a dominant-source regime.
- `regime_selector_accuracy_spread` diagnostics align with the best observed per-provider behavior.
- Targeted Mistral failure reruns supported dominance-aware routing hypotheses.
- Failure analysis clarified that agreement-only fails mainly at no-majority frontier-fallback errors.

## E) What Failed or Is Insufficient

- Agreement-only is too conservative for no-majority cases.
- Always-S1 is not transferable; it damages Cohere.
- Source-family discounting alone did not clearly fix Mistral.
- Raw pairwise-correlation explanation was incomplete/wrong as a primary mechanism.
- Failure-only reruns are biased and cannot justify final improvement claims.
- Small 300-example calibration increases overfitting risk if thresholds are tuned on the same slice.

## F) Supported Hypotheses

- Near-peer source strengths favor pooled voting.
- Dominant-source regime favors best-source/provider-prior routing.
- No-majority cases need calibrated fallback, not hard frontier fallback.
- All-sources-wrong cases are generation bottlenecks, not selection bottlenecks.
- In current Cohere/Mistral evidence, competence heterogeneity matters more than raw pairwise correlation.

## G) Ideas to Try Next

- Merge repaired Cohere and Mistral outputs with original frontier rows.
- Replay selectors on merged complete slices only.
- Add beta-binomial shrinkage to regime estimation.
- Use confidence-interval dominance tests instead of raw spread thresholds.
- Calibrate a no-majority fallback branch on calibration data only.
- Build a larger fixed-pool labeled set (target: 1000+ examples/provider if feasible).
- Train lightweight learned routers (logistic regression, shallow tree, gradient-boosted diagnostics).
- Run cross-provider validation to test transferability.
- Classify Cerebras regime once that run is complete.
- Consider MATH-500 (or another dataset) after GSM8K protocol is stable.

## H) Proposed Algorithm Family

- Raw-spread regime selector:
  - near-peer -> pooled-4;
  - dominant -> best-source/provider-prior.
- Beta-shrinkage regime selector:
  - posterior source competence with uncertainty-aware dominance detection.
- Calibrated fallback branch:
  - explicit no-majority handling using calibrated fallback logic.
- Correlation/family discount branch:
  - penalize redundant source families when supported by diagnostics.
- Learned router extension:
  - learn `P(source correct | features)` and map to selection policy.

## I) Validation Protocol

- Strict calibration/test split discipline.
- No threshold tuning on held-out test examples.
- Paired bootstrap confidence intervals.
- McNemar tests for paired significance checks.
- Oracle-regret reporting vs best in fixed pool.
- Recovery/regression accounting relative to baseline selectors.
- Failure-case analyses used only for hypothesis generation.
- Promotion decision requires full held-out rerun on complete merged artifacts.

## J) Risks and Limitations

- Overfitting to provider/model-specific behavior.
- API stochasticity and model-version drift.
- Paid API cost constraints can reduce replication breadth.
- Dataset-specific effects may limit transfer.
- Incorrect use of failure-only reruns can overstate gains.
- Source drift and prompt-version updates can invalidate priors.
- Small calibration samples produce unstable thresholds.

## K) Key Reference Papers and Literature

| Reference | Category | Why Relevant | Supports |
|---|---|---|---|
| Wang et al., *Self-Consistency Improves Chain of Thought Reasoning in Language Models* (<https://arxiv.org/abs/2203.11171>) | LLM ensemble voting | Majority-over-reasoning-path baseline logic | Algorithm/baseline |
| Mozannar & Sontag, *Consistent Estimators for Learning to Defer to an Expert* (<https://arxiv.org/abs/2006.01862>) | Learning to defer | Formal defer/routing framing for selective handoff | Theory/algorithm |
| Madras et al., *Predict Responsibly: Improving Fairness and Accuracy by Learning to Defer* (<https://papers.nips.cc/paper_files/paper/2018/hash/09d37c08f7b129e96277388757530c72-Abstract.html>) | Learning to defer | Practical defer optimization with performance tradeoffs | Theory/algorithm |
| Geifman & El-Yaniv, *Selective Classification for Deep Neural Networks* (<https://arxiv.org/abs/1705.08500>) | Selective prediction | Risk-coverage/selective abstention perspective for fallback logic | Theory/metrics |
| Kuncheva & Whitaker, *Measures of Diversity in Classifier Ensembles and Their Relationship with Ensemble Accuracy* (<https://link.springer.com/article/10.1023/A:1022859003006>) | Ensemble diversity | Diversity vs accuracy metrics (Q, disagreement, double-fault) | Metrics/analysis |
| Kuncheva, *Combining Pattern Classifiers: Methods and Algorithms* (<https://onlinelibrary.wiley.com/doi/book/10.1002/9781118914564>) | Ensemble methods | Ensemble foundations and weighting schemes | Theory/algorithm |
| Cruz et al., *DESlib: A Dynamic Ensemble Selection Library in Python* (<https://jmlr.org/papers/v21/18-144.html>) | Dynamic ensemble selection | DES taxonomy and practical selector patterns | Algorithm/tooling |
| Cruz et al., *Dynamic Classifier Selection: Recent Advances and Perspectives* (<https://www.sciencedirect.com/science/article/pii/S1566253520303772>) | Dynamic selection survey | Modern dynamic-selection design space | Theory/algorithm |
| Jacobs et al., *Adaptive Mixtures of Local Experts* (<https://direct.mit.edu/neco/article/3/1/79/5560/Adaptive-Mixtures-of-Local-Experts>) | Mixture-of-experts | Gating/routing under heterogeneous expertise | Theory/algorithm |
| Shazeer et al., *Outrageously Large Neural Networks* (<https://arxiv.org/abs/1701.06538>) | Sparse MoE | Conditional routing inspiration at scale | Theory/framing |
| Dietterich, *Ensemble Methods in Machine Learning* (<https://link.springer.com/chapter/10.1007/3-540-45014-9_1>) | Ensemble foundations | Bias-variance and ensemble principles | Theory |
| Krogh & Vedelsby, *Neural Network Ensembles, Cross Validation, and Active Learning* (<https://papers.nips.cc/paper_files/paper/1994/hash/b8c37e33defde51cf91e1e03e51657da-Abstract.html>) | Ensemble theory | Ambiguity decomposition and ensemble benefit intuition | Theory |
| *Harnessing the Power of Multiple Minds: Lessons Learned from LLM Routing* | LLM routing | Empirical routing lessons across model families | Framing/algorithm |
| *Efficient Contextual LLM Cascades through Budget-Aware Prompting and Model Selection (TREACLE)* | Budget-aware routing | Budget-constrained contextual routing analogies | Algorithm/validation |
| *Adaptive LLM Routing Under Budget Constraints* | LLM routing | Budget-aware routing objective alignment | Algorithm/validation |
| *Universal Model Routing for Efficient LLM Inference* | LLM routing | General-purpose routing abstraction | Theory/framing |
| Cobbe et al., *Training Verifiers to Solve Math Word Problems* (<https://arxiv.org/abs/2110.14168>) | Verifier/reranking | Verifier-guided selection evidence style | Algorithm/validation |
| Lightman et al., *Let’s Verify Step by Step* (<https://arxiv.org/abs/2305.20050>) | Verifier/reranking | Process supervision and verification signals | Algorithm |
| Jiang et al., *LLM-Blender* (<https://arxiv.org/abs/2306.02561>) | LLM blending/reranking | Model blending and pairwise ranking ideas | Algorithm |
| Beta-binomial references (e.g., Bayes Rules chapter) | Empirical Bayes shrinkage | Stabilize source-competence estimates with uncertainty | Theory/algorithm |
| McNemar and paired-model evaluation references | Statistical testing | Correct paired comparison protocol for selector claims | Validation/metrics |

## L) Concise Contribution Statement

We introduce **regime-aware fixed-pool answer selection under matched inference budgets**, a zero-extra-call selection framework that treats each candidate source as an expert and routes decisions according to observable reliability regimes of the fixed candidate pool. Instead of assuming one universal selector, the method adapts between pooled voting, dominant-source routing, and calibrated fallback logic while preserving strict runtime constraints. The resulting formulation is a general ML contribution to budget-constrained inference-time selection, with clear statistical validation and oracle-regret accounting.

## M) Immediate Next Actions Checklist

- [ ] Wait for/confirm Mistral missing-method repair completion status (now complete on disk; keep merge step separate from this hygiene task).
- [ ] Merge Cohere targeted original + repair rows.
- [ ] Merge Mistral full original + repair rows.
- [ ] Run merged-slice integrity and dedup checks.
- [ ] Replay selectors on merged complete slices.
- [ ] Run beta-shrinkage regime selector variant.
- [ ] Decide whether to run full Cohere validation for calibrated no-majority fallback.
- [ ] Classify Cerebras regime once Cerebras run completes.

## Claim Boundary Reminder

- No policy promotion decision changes are made in this roadmap.
- Failure-only reruns remain diagnostic only.
- Canonical evidence hierarchy remains the FIX-2+FIX-4 final-300 and aggregate-720 record in `docs/LATEST_RESULTS_AND_CLAIMS.md`.
