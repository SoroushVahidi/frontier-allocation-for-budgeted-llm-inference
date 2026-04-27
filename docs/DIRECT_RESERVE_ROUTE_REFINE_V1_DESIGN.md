# DIRECT_RESERVE_ROUTE_REFINE_V1 Design

## Purpose

`direct_reserve_route_refine_v1` is an experimental diagnostic controller for Cohere that protects a direct/L1-style incumbent and only escalates to frontier search when cheap uncertainty signals indicate risk.

This is a prototype for diagnosis, not a canonical paper-facing method.

## Core policy

1. **Direct reserve**
   - Run `external_l1_max` first as a protected incumbent.
   - Record incumbent raw/canonical answer and token/cost/latency.

2. **Cheap uncertainty gate**
   - Compute deterministic signals:
     - parseability of incumbent answer
     - direct answer length
     - question length
     - number count in question
     - multi-step risk heuristic
     - incumbent unstable/unparseable flag
   - Optional extra-sample disagreement is supported as a field; in the smoke run it remains disabled.

3. **Routing decision**
   - `stop_with_incumbent` when confidence is high and risk is low.
   - `longer_direct_continuation` for moderate uncertainty.
   - `frontier_search_challenger` for high uncertainty or multi-step risk.

4. **Frontier search as challenger**
   - Challenger is run without automatically replacing incumbent.
   - In the current diagnostic runner:
     - `strict_f3` is used for `frontier_search_challenger`.
     - `direct_reserve_frontier_gate_v1` is used for `longer_direct_continuation` when available.

5. **Guarded commit**
   - Challenger replaces incumbent only if deterministic replacement rules pass:
     - incumbent is unparseable, or
     - challenger has stronger support margin, or
     - challenger resolves multi-step uncertainty.
   - Otherwise incumbent is preserved.

## Trace and diagnostics

Per-case logging includes:
- `route_decision`, `route_reason`
- incumbent/challenger answers and support proxies
- `incumbent_replaced`, `replace_reason`, `direct_path_preserved`
- token/cost/latency for incumbent and challenger
- challenger branch traces and action traces when available

Run outputs are written under:
- `outputs/direct_reserve_route_refine_cohere_diagnostic_<timestamp>/`

## Safety and scope

- Keeps existing `strict_f3` behavior unchanged.
- Uses Cohere API readiness checks and explicit failure reporting.
- Caps default run size to small smoke runs; hard cap `<=30`.
- Never logs API key values.
