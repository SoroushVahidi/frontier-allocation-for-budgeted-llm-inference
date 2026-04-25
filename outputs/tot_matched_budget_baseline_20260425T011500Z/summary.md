# Matched-budget ToT-style baseline summary

This bundle compares frontier allocation methods against **matched-budget ToT-style BFS/beam/DFS adapters** under the shared action ledger.
It is **not** an official Tree-of-Thoughts reproduction.

- Datasets ran: ['openai/gsm8k', 'HuggingFaceH4/MATH-500', 'HuggingFaceH4/aime_2024']
- Budgets: [4, 6, 8]; seeds: [11, 23, 37, 41, 53]; subset size: 20
- Best overall method by mean accuracy: **strict_f3_anti_collapse_weak_v1** (acc=0.6578)
- Best ToT adapter by mean accuracy: **tot_beam_matched_budget**
- `strict_f3_anti_collapse_weak_v1` mean accuracy: **0.6578** (avg actions 5.37)

## Manuscript-safe wording
- We compare against matched-budget ToT-style BFS/beam/DFS adapters under the same action-budget ledger.
- The result supports comparison against a recognizable search-style baseline under matched-budget adapter conditions.
- This is not an official ToT reproduction; do not claim universal dominance over all search-based reasoning.
