# Method Inspiration References

Tracks ideas related to our method and whether they are directly implemented or conceptual.

| Idea | External reference | How it influenced our method | Directly implemented or conceptual |
|---|---|---|---|
| Test-time compute / budgeted inference | General test-time scaling literature (plus internal budgeted frontier work) | Motivated explicit action budgets and bounded extra-call policies | directly implemented |
| Self-consistency / candidate diversity | [Self-Consistency](https://arxiv.org/abs/2203.11171) | Informed multi-candidate reasoning and answer-group support logic | directly implemented (adapted) |
| PAL / program-aided reasoning | [PAL paper](https://arxiv.org/pdf/2211.10435.pdf) | Motivated executable arithmetic branch and PAL integration checks | directly implemented (adapted) |
| Budget forcing / S1-style | [S1 paper](https://arxiv.org/html/2501.19393v1), [S1 repo](https://github.com/simplescaling/s1) | Informed constrained inference-depth baseline behavior | directly implemented as baseline-style adaptation |
| Token-budget prompting / TALE-style | [TALE ACL PDF](https://aclanthology.org/2025.findings-acl.1274.pdf), [TALE arXiv](https://arxiv.org/abs/2412.18547) | Informed budget-prompting baseline comparisons | directly implemented as baseline-style adaptation |
| Decomposition and final-target verification | Conceptually related to decomposition prompting and verifier-based consistency lines | Influenced final-target checks, target mismatch risk features, and selected retry scaffolds | directly implemented (internal formulation) |
| Structural commitment | Internal design (Track B commitment/overlay gates) | Provides conservative, auditable final answer commitment policy under uncertainty | directly implemented (internal) |
| Targeted retry | Internal design with bounded extra-call loop and scaffold restrictions | Adds controlled second-chance correction only under deterministic triggers | directly implemented (internal, partially wired for production-equivalent path) |

## Notes

- `discovery3_candidate_diversity_selection_v1` is a negative-result patch and is intentionally excluded from production-equivalent recommendations.
- Production-equivalent v1 planning keeps inspiration links but avoids unvalidated discovery prompts.

- Schema-grounded retry (internal): Tested as a fixed-schema grounding and structural validation idea; live format-contract probes failed and it remains a negative diagnostic rather than a deployed method.

- **Next direction (research, not yet implemented):** PAL-aware **hybrid selection** should wait on a **larger PAL-only / PAL-vs-production_equiv disagreement casebook** produced via a **multi-batch targeted loop**, so failure modes are representative before selector design.
