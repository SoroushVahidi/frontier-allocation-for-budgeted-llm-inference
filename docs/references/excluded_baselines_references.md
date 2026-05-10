# Excluded / Deferred Baselines References

Methods considered but not currently in the main matched-50 core comparison table.

| Method | Citation link | Why excluded / deferred | Appendix possible | Fair-comparison constraint |
|---|---|---|---|---|
| Least-to-Most | [arXiv:2205.10625](https://arxiv.org/abs/2205.10625) | Not prioritized in current core4 protocol and budgeted live calibration loop | yes | Needs stable prompt/harness and same budget policy as core baselines |
| Reflexion | [arXiv:2303.11366](https://arxiv.org/abs/2303.11366), [repo](https://github.com/noahshinn/reflexion) | Iterative verbal feedback loop may require protocol deviations vs fixed-call fairness setup | yes | Must enforce equal call budgets and no hidden additional supervision |
| Tree of Thoughts | [arXiv:2305.10601](https://arxiv.org/abs/2305.10601), [repo](https://github.com/princeton-nlp/tree-of-thought-llm) | Full ToT search is too expensive for tiny/strict budgets in current checkpoints | yes (shallow adaptation only) | Keep branching depth/width budget-matched to core baselines |
| Training-free adaptive allocation | [OpenReview](https://openreview.net/forum?id=ztGHhyicWs) | Requires separate protocol framing for average-budget allocation claims | yes (separate protocol) | Needs dedicated budget-accounting protocol not mixed with core4 table |
| Budget Guidance | [arXiv:2506.13752](https://arxiv.org/abs/2506.13752) | Token-level generation control not generally available in standard hosted API settings | maybe | Only fair if same control surface is available to all compared methods |
| Verifier / PRM / ORM reranking families | [OpenReview representative](https://openreview.net/forum?id=Qyile3DctL) | Excluded unless verifier is public and equally callable for all methods under same budget | yes | Equal-access verifier and identical call-cost accounting across all methods |
| ReAct | (benchmark-style method family) | Not central for GSM8K arithmetic without tool-use/action-observation task context | maybe | Should be evaluated on suitable action-observation benchmarks, not forced into arithmetic-only main table |

## Current policy summary

- Core main-table focus remains fair core4 operationally stable comparisons.
- Deferred baselines can appear in appendix only if fairness and budget parity are explicit.
