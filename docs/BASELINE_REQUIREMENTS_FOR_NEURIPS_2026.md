# Baseline requirements for NeurIPS 2026 positioning

| Baseline family | Representative papers | What it tests | Whether repo currently has it | Current implementation name if present | Gap / next action |
|---|---|---|---|---|---|
| Uniform allocation / fixed budget | ToT fixed-width/fixed-depth style controls; generic fixed-K sampling | Whether adaptive policies beat naive equal allocation | Partial | `reasoning_greedy`, fixed-budget strategy families in frontier runners | Keep as mandatory denominator in all budgeted comparisons. |
| Training-free difficulty proxy allocation | Adaptive test-time via difficulty proxies (OpenReview ICLR 2026 submission) | Allocation gains without extra training | Partial/adjacent | difficulty-gated and heuristic diagnostic controllers (non-canonical) | Add explicit named proxy baseline package + matched accounting report. |
| TALE/token-budget allocation | TALE (arXiv:2412.18547 / Findings ACL 2025) | Token-budget conditioning vs action-budget methods | Yes (adapter) | `tale` / `external_tale_prompt_budgeting` | Keep appendix+cost-normalized reporting; avoid equivalence claims across budget units. |
| s1/budget forcing | s1 (arXiv:2501.19393 / EMNLP 2025) | Continuation forcing / token scaling control | Yes (adapter) | `s1` / `external_s1_budget_forcing` | Expand paired real-model runs with strict accounting and caveats. |
| Self-consistency | Wang et al. self-consistency line | Candidate aggregation baseline | Yes (canonical) | `self_consistency_3` | Continue as stable baseline in main/internal comparisons. |
| ToT/GoT/search under fixed query/action budget | ToT, Graph of Thoughts, policy-guided ToT search | Search efficiency under bounded query/action budgets | Partial/adjacent | imported/search diagnostic runners; no single canonical official GoT stack | Add clearer “official vs adapter” separation in manuscript appendix tables. |
| Verifier-guided search / intermediate verification allocation | process/verifier-guided search papers; learned intermediate heuristics | Value of verification budget allocation | Partial | `verifier_guided_search` and verifier diagnostics | Add side-by-side matched-action + verifier-call accounting in one artifact family. |
| BEST-Route / cascade-style routing | BEST-Route, TREACLE (NeurIPS 2024) | Model/prompt routing under cost/latency constraints | Adjacent import validation only | BEST-Route import/integration docs and validators | Keep as adjacent family; no direct dominance claims until full-stack reproduction. |
| `external_l1_max` / direct length-control baseline | L1-style and direct external budget controls | Strong external boundary on same slices | Yes (canonical boundary) | `external_l1_max` | Maintain as hard guardrail comparator for real-model claims. |
| `direct_reserve_semantic_frontier_v2` diagnostic challenger | internal diagnostic branch/frontier allocator | Whether improved frontier allocation closes gap to external boundary | Diagnostic only | `direct_reserve_semantic_frontier_v2` (mapped runtime alias) | Complete larger paired runs before any promotion beyond diagnostic appendix use. |

## Baseline audit tags in this repository
- **Canonical headline baseline:** `self_consistency_3`, `external_l1_max`.
- **Implemented adapter:** `tale`, `s1`, `verifier_guided_search` (scope-dependent).
- **Diagnostic only:** `direct_reserve_semantic_frontier_v2` (current evidence status).
- **Missing / not full-stack:** official Graph-of-Thoughts and some routing stacks in directly comparable matched-action form.
- **Provenance-only / adjacent:** BEST-Route import/integration notes without claim-safe equivalence to this repo’s core budget contract.
