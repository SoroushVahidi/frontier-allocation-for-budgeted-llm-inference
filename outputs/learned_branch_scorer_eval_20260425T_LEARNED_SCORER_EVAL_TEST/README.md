{
  "diagnostic_only": true,
  "selected_split": "joint_holdout",
  "comparisons": [
    "strict_f3",
    "external_l1_max",
    "support_rerank_proxy",
    "learned_branch_scorer_v1",
    "direct_reserve_gate_rerank_proxy",
    "learned_on_direct_reserve_proxy"
  ],
  "note": "Learned scorer mainly targets present_not_selected when gold is already present.",
  "limitation": "Absent-from-tree failures are not directly solved by this reranking-only diagnostic pass."
}
