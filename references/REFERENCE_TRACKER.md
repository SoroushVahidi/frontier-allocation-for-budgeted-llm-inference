# Reference Tracker

This tracker is project-facing rather than citation-facing.
It records how each important paper relates to the repository and what we should do with it.

| Key | Paper | Role in project | Directness | Compare priority | Code / repo | Current use in this repo | Practical note |
|---|---|---|---|---|---|---|---|
| `s1_2025` | s1: Simple test-time scaling | External baseline | direct / near-direct | must-compare | official code available | should compare against it directly | Best first external baseline to integrate because it is close to explicit stop/continue control. |
| `l1_2025` | L1: Controlling How Long A Reasoning Model Thinks With Reinforcement Learning | External baseline | direct / near-direct | must-compare | official code available | should compare against it directly | Strong hard-budget baseline; caveat is RL-trained control vs our lighter controller framing. |
| `tale_2025` | Token-Budget-Aware LLM Reasoning | External baseline | partial but strong | must-compare | official repo available | should compare against it directly if feasible | Strong published per-instance budget allocation baseline; not sequential stop-vs-act, but highly relevant. |
| `learning_how_hard_2024` | Learning How Hard to Think: Input-Adaptive Allocation of LM Computation | External baseline | partial | strong secondary | code status unclear | use mainly as broader allocation comparison target | Strong conceptual predecessor for learned compute allocation under a fixed budget. |
| `best_route_2025` | BEST-Route: Adaptive LLM Routing with Test-Time Optimal Compute | External baseline | partial | strong secondary | official repo available | use as broader routing-style allocation comparison | Good broader adaptive-compute baseline, but less apples-to-apples unless multi-model routing is allowed. |
| `lightman_2023` | Let’s Verify Step by Step | Methodological idea source | indirect | not a direct baseline | paper/dataset available | shaped evaluation and process-supervision thinking | Important for same-data/different-supervision logic and active labeling ideas. |
| `autopsv_2024` | AutoPSV: Automated Process-Supervised Verifier | Methodological idea source | indirect | not a direct baseline | paper available | shaped local confidence-change / process-quality ideas | Useful for thresholded process-quality and audit-style label trust. |
| `zhang_2020_noise` | Distilling Effective Supervision From Severe Label Noise | Methodological idea source | indirect | not a direct baseline | paper available | shaped selective-distillation plan | Useful for trusted-slice supervision, reweighting, and not treating all labels equally. |
| `lakkaraju_2017` | The Selective Labels Problem | Methodological idea source | indirect | not a direct baseline | paper available | shaped matched-rate / selective evaluation caution | Important for evaluating policies at matched intervention rates rather than naive observed-label comparisons. |
| `prm_lessons_2025` | The Lessons of Developing Process Reward Models | Methodological idea source | indirect | not a direct baseline | paper available | shaped controller-behavior metrics | Important warning that coarse aggregate metrics can hide weak local decisions. |

## Current practical use

### A. Must-compare external baselines for the paper
These are the papers that should become real comparison targets in the repository:
1. `s1_2025`
2. `l1_2025`
3. `tale_2025`

### B. Strong broader-context baselines
These are highly relevant but less direct:
1. `learning_how_hard_2024`
2. `best_route_2025`

### C. Methodological references that changed the design
These papers are important because they changed how we built the project even if they are not direct experimental baselines:
- `lightman_2023`
- `autopsv_2024`
- `zhang_2020_noise`
- `lakkaraju_2017`
- `prm_lessons_2025`

## Maintenance rule

Whenever a paper becomes central enough to affect:
- the method,
- the baseline suite,
- the oracle-label phase,
- the evaluation protocol,
- or the selective-distillation logic,

update this tracker and add or revise the corresponding note under `references/papers/`.
