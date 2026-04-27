# SIM_VS_COHERE_FRONTIER_GAP_AUDIT_20260427T213520Z

- Output directory: `outputs/sim_vs_cohere_frontier_gap_audit_20260427T213520Z`
- Exact overlap cases found: **120**
- Real Cohere loss cases analyzed: **156**
- Taxonomy counts: bad seeding=1, bad maturation=0, bad allocation=0, bad selection=2, trace unavailable=153

## Why simulation may beat external while real Cohere does not
- Simulation strict_f3 has materially lower absent-from-tree rates than real Cohere strict_f3 on available artifacts.
- Real Cohere traces show repeated family collapse / shallow maturation on several loss cases despite hard early depth forcing.
- Real Cohere also has non-trivial trace-unavailable losses, reducing confidence that current controls reach correct regions.

## Failure mode emphasis
- Dominant observed mode: **trace_unavailable**.
- Existing depth-2/depth-3 coverage appears insufficient as a semantic-diversity guarantee.
- Semantic family diversity (strict_f3 trace-available mean): family_count=2.08, redundancy_ratio=0.49.

## Simulation substrate ease check
- Simulation appears easier/richer: **yes**.
- Evidence: simulation strict_f3 accuracy=0.628, real strict_f3 accuracy=0.592, simulation absent=0.294, real absent=0.319.

## Missing data
- See `outputs/.../missing_data_report.md` for required artifacts for stronger causal attribution.

## Most justified next fix
- Move from root-count coverage to semantic-family maturation guarantees before late-stage allocation.
