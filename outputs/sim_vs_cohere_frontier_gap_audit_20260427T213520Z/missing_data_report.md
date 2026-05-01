# Missing data report

- Simulation source used: `outputs/matched_surface_multiseed_main_comparison_20260423T235900Z`
- Real Cohere source used: `outputs/real_model_ours_vs_external_validation_20260425T_WULVER_COHERE_LONG`
- Cohere trace source used: `outputs/cohere_direct_reserve_failure_replay_seed_latest`
- Missing for strongest comparison:
  - per-branch trace table for simulation strict_f3/strict_f2 with branch depths and reasoning text
  - matched seed/budget/example mapping between simulation and real Cohere runs
  - token/cost/latency in simulation raw case rows
  - explicit path bucket tags (`immediate_miss`, `partial_progress`, `near_miss_absent_final`) for simulation
