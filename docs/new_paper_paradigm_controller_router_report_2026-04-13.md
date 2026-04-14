# New-paper: Paradigm/Controller Router Prototype (2026-04-13)

## Scope

This prototype stays in the **cross-controller frontier allocation** track and adds a lightweight, optional query router over these frontier families:

- reasoning_greedy
- self_consistency_3
- reasoning_beam2
- adaptive_min_expand_0
- adaptive_min_expand_1
- adaptive_min_expand_2
- verifier_guided_search
- program_of_thought

## Where labels come from

The existing frontier path already emits per-example × per-controller outcomes (`per_example_eval.jsonl`).
From those artifacts, we derive oracle labels per query (best controller under a fixed budget) using a deterministic tie-break:

1. prefer correct over incorrect
2. lower actions
3. lower expansions
4. lower verifications
5. stable family order

Materialized label table: `router_dataset.csv`.

## Router baseline

- Model: `TfidfVectorizer(1-2gram, max_features=512) + LogisticRegression(class_weight="balanced")`
- Fallback: constant-majority label when calibration labels have <2 classes.
- No finetuning, no heavyweight training pipeline.

## Integration

`scripts/run_cross_strategy_frontier_allocation.py` now supports:

- `--selector-mode static_calib_best` (existing behavior)
- `--selector-mode router` (new per-query selector)
- `--selector-mode both` (default; side-by-side comparison)

Outputs default to `outputs/new_paper/paradigm_controller_router/<run_id>/`.

## Example run and results

Command used:

```bash
python scripts/run_cross_strategy_frontier_allocation.py \
  --subset-size 10 \
  --budgets 4,6 \
  --adaptive-min-expand-grid 0,1,2 \
  --selector-mode both
```

Run directory:

- `outputs/new_paper/paradigm_controller_router/20260413T234802Z/`

Observed (small simulated pilot):

- Budget 4: static selector 0.40, router 0.40, oracle 1.00 (router recovered 0% of static→oracle gap).
- Budget 6: static selector 0.40, router 0.20, oracle 1.00 (router worsened vs static in this tiny sample).
- Primary fixed method (`adaptive_min_expand_1`) at budget 6 reached 0.80, outperforming static and router.

## Honesty / limitations

- Existing aggregate-only outputs (e.g., `strategy_metrics.csv`) are insufficient for routing labels by themselves; per-example frontier outcomes are required.
- This run is tiny and simulated; conclusions are directional only.
- The prototype is intentionally minimal and is meant to establish a defensible baseline + artifact flow for larger evaluations.
