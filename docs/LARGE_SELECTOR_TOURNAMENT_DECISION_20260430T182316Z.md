# LARGE SELECTOR TOURNAMENT DECISION 20260430T182316Z

- paired examples evaluated: 86
- oracle selector beats external_l1_max: yes (same margin as current DR-v2 on this artifact)
- any deployable selector beats external_l1_max: yes (all tied with current DR-v2)
- cohere verifier selector beats external_l1_max: yes (tie only; no incremental gain)
- chosen selector going forward: `current_dr_v2_selector`
- remaining bottleneck: not final-answer selection on this artifact (no selector headroom observed)
- next recommended experiment: prioritize discovery/coverage repair or run selector checks only on explicitly positive-headroom artifacts.

## Interpretation Guardrails

- `oracle_selector` is evaluation-only and not deployable.
- `oracle_selector` and `current_dr_v2_selector` are equal on this run, so this artifact provides no selector headroom.
- `support_family_selector` and `cohere_outcome_verifier_selector` also tie `current_dr_v2_selector`; there are no fixes/breaks/overrides.
- This run does **not** demonstrate that Cohere verifier selection works better than current DR-v2.
- No new selector is promoted from this large combined artifact.
