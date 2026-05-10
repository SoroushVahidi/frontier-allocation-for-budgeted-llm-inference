# Excluded or Appendix-Only Baselines

- Least-to-Most: appendix-only (additional decomposition protocol complexity).
- Reflexion retry: appendix-only (iterative feedback loop overhead and protocol variance).
- Training-free adaptive allocation: appendix/separate protocol (average-budget handling differs from fixed tiny-budget main table).
- Shallow ToT-style baseline: appendix-only (branching protocol ambiguity under tiny budgets).
- PRM/verifier-guided: excluded unless public verifier parity is available.
- Budget Guidance: excluded (requires token-level generation control not uniformly available).
- Learned allocator/CPO: excluded (training required).
- ReAct: excluded (GSM8K is not interactive tool-use).
