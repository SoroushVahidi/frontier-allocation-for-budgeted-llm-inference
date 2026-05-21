# MLJ Cover Letter

Dear Editor,

Please consider our manuscript, *Selective Deferral for Budgeted LLM Answer Selection: Failure-Trace Signals under Matched-Budget Evaluation*, for publication in *Machine Learning*.

The manuscript studies post-generation answer selection for budgeted LLM reasoning on GSM8K under Cohere command-r-plus-08-2024 at budget B=6. Failure-Trace Allocator (FTA) is a deterministic gold-free selective-deferral policy that uses logged failure-trace metadata and external consensus signals to choose among already-generated candidates, with no additional model calls at decision time.

On Final-300, FTA achieves 260/300 = 86.67%. On the disjoint Aggregate-720 evaluation, it achieves 581/720 = 80.69%. Source-stratified bootstrap confidence intervals are positive versus L1, S1, TALE, and the source-local best external baseline. Against the pooled four-answer ensemble, FTA is ahead by point estimate but not statistically separated; the appropriate conclusion is competitiveness with strong aggregation baselines rather than broad superiority over ensembling.

The claims are scoped to the tested provider, benchmark, and budget-6 setting. We do not claim universal superiority or state-of-the-art performance across settings.

The supplementary reproducibility package supports offline verification of the reported tables and metrics from processed artifacts, without API access. Full end-to-end regeneration requires commercial provider credentials. Code and processed artifacts will be released publicly upon acceptance with a persistent identifier (e.g., Zenodo DOI); reviewer-access artifacts can be provided on request.

For transparency, we disclose the related NeurIPS manuscript *Frontier Allocation for Budgeted LLM Inference* and have uploaded it in the portal's Related files section. That manuscript studies frontier allocation during budgeted inference: a controller maintains active partial reasoning branches and decides which branch to expand or when to commit under a fixed action budget, with contributions in branch-local continuation scoring, answer-support aggregation, anti-collapse tree-shape control, and bounded repair within a frontier-allocation framework. The present *Machine Learning* submission is distinct: it studies post-generation selective deferral for final-answer selection among already generated candidate answers, using logged failure-trace metadata and external-answer agreement under a matched per-producer budget. The related manuscript concerns branch-level compute allocation during reasoning; this submission concerns final-answer selection after candidate generation.

Sincerely,
Soroush Vahidi
