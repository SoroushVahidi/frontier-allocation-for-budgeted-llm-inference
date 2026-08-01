# Cover Letter

**Date:** August 1, 2026

**To:**  
Editor-in-Chief  
*Performance Evaluation*

**Re:** Submission of “Nominal Budgets and Realized Resources in Closed-API Large-Language-Model Inference: A Performance Evaluation Protocol”

Dear Editor-in-Chief,

I respectfully submit the enclosed manuscript, “Nominal Budgets and Realized Resources in Closed-API Large-Language-Model Inference: A Performance Evaluation Protocol,” for consideration for publication in *Performance Evaluation*.

Budgeted closed-API large language model (LLM) evaluations are often summarized by accuracy under a shared nominal inference budget. Equal nominal budgets need not imply equal realized resource use, and they can conflate candidate discovery with final-answer selection. Closed commercial APIs intensify the measurement problem: providers differ in operational behavior, telemetry may be incomplete, and attribution and reproducibility are correspondingly difficult. Without an auditable accounting contract, budget-matched comparisons can be mistaken for resource-matched ones, and selector gains for stronger discovery.

The manuscript contributes a unified, auditable performance-evaluation protocol for closed-API, budgeted inference. The protocol separates nominal budget from realized resources, separates candidate discovery from final-answer selection, evaluates identical-pool selector controls, labels provider transfer for failure-mined rules, and reports incomplete telemetry and protocol-blocked outcomes rather than silently dropping or imputing them. Named generators, adapters, and selectors are measurement objects used to exercise the protocol, not a general ranking of reasoning systems.

Empirically, the protocol is exercised on four providers and four datasets, yielding 15 completed provider-by-dataset cells with 3,394 paired examples and one explicitly retained protocol-blocked cell (Fireworks×GPQA-Diamond). On the shared four-generator pool, identical-pool plurality (Pooled-4) exceeds the failure-trace gated selector (FTA) overall (66.53% versus 65.00%; McNemar *p*=0.00027). Transfer failures concentrate primarily in the dominant FIX-2 gate, especially in Azure mathematics cells. Reconstructing successful-completion counts changes interpretation of nominally matched methods: Frontier successful completions rise from 2.78 to 5.38 of nominal budget *B*=6, while token and dollar fields remain lower bounds.

The manuscript fits *Performance Evaluation* as a measurement-methodology contribution concerning workload and resource semantics under closed-service benchmarking, experimental attribution between discovery and selection, and reproducibility practice when telemetry is incomplete. Its claim is that defensible closed-API inference-performance conclusions require an explicit resource layer and attribution controls. The manuscript does not claim a universally superior reasoning algorithm; official reproduction of L1, s1, or TALE; a complete cost-efficiency or Pareto analysis; or full regeneration of proprietary API outputs.

This manuscript is original, has not been published elsewhere, and is not under consideration elsewhere. I am the sole author and approve this submission. Funding and competing-interest disclosures are included with the manuscript. Evaluation code and frozen aggregate audit artifacts supporting verification of the reported aggregates are publicly available at https://github.com/SoroushVahidi/frontier-allocation-for-budgeted-llm-inference.

This research received in-kind computational support through API and cloud-service credits from the Cohere Labs Catalyst Grant Program, the Google Cloud Research Credits Program, Microsoft Azure for Students, and AMD-provided Fireworks AI credits. Cohere Labs provided USD 1,000 in API credits, and AMD provided USD 50 in Fireworks AI credits. These organizations had no role in the study design, data collection, analysis, interpretation, manuscript preparation, or decision to submit the work.

Thank you for your consideration.

Sincerely,

Soroush Vahidi  
Corresponding Author  
Ying Wu College of Computing, New Jersey Institute of Technology  
Newark, New Jersey, USA  
Email: sv96@njit.edu  
ORCID: 0000-0003-1934-6282
