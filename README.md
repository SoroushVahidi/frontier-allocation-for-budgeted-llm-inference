# adaptive-reasoning-budget-allocation

Repository for **adaptive test-time compute allocation for LLM reasoning** with two intentionally separate research tracks:

1. **Old manuscript track**: binary revise-routing (**"when should we revise?"**).
2. **New paper track**: cross-controller frontier allocation (**"where should the next unit of compute go?"**).

> This repository keeps both tracks for continuity, but they should not be mixed in claims, evaluation narratives, or script interpretation.

## Start here

- Track split and naming guardrail: [`docs/OLD_VS_NEW_PAPER_TRACKS.md`](docs/OLD_VS_NEW_PAPER_TRACKS.md)
- Canonical repo map and entry points: [`docs/REPO_MAP.md`](docs/REPO_MAP.md)
- Documentation index: [`docs/README.md`](docs/README.md)
- Script index: [`scripts/README.md`](scripts/README.md)

## What is canonical vs exploratory

| Area | Current status | Where to start |
|---|---|---|
| Old manuscript (binary revise-routing) | **Canonical for submitted manuscript support** | `scripts/run_heavy_real_routing_eval.sh`, `docs/safe_manuscript_claims_2026-04-13.md` |
| New paper (frontier allocation) | **Canonical active research direction** | `docs/NEW_PAPER_CURRENT_STATUS.md`, `scripts/run_cross_strategy_frontier_allocation.py` |
| Branch-scorer variants (BT, reliability, warm-start, diagnostics) | **Exploratory within new-paper track** | `docs/BRANCH_SCORER_STATUS.md`, `experiments/*branch_scorer*_result_note.md` |
| External reasoning datasets integration/readiness | **Preparation/integration layer (not final method)** | `docs/DATASET_STATUS.md`, `configs/external_reasoning_datasets_registry.json` |
| Dated memos and audits | **Historical provenance** | `docs/README.md` → “Historical notes” |

## Track A: old manuscript (binary revise-routing)

Use when you need evidence for the existing manuscript story.

- Question: **When should we revise?**
- Primary entry: `scripts/run_heavy_real_routing_eval.sh`
- Manuscript-safe wording/index:
  - `docs/safe_manuscript_claims_2026-04-13.md`
  - `docs/manuscript_support_index_2026-04-13.md`

## Track B: new paper (cross-controller frontier allocation)

Use for ongoing work on budgeted allocation across controller families.

- Question: **Where should the next unit of compute go?**
- Current practical status: `docs/NEW_PAPER_CURRENT_STATUS.md`
- Bottleneck note: `docs/NEW_PAPER_CURRENT_BOTTLENECKS.md`
- Safe-claim guardrail: `docs/NEW_PAPER_SAFE_CLAIMS.md`
- Immediate next-step plan: `docs/NEW_PAPER_NEXT_STEPS.md`

Primary scripts:

- `scripts/run_cross_strategy_frontier_allocation.py` (legacy filename; frontier allocation scaffold)
- `scripts/run_multi_action_allocation_pass.sh`
- `scripts/evaluate_branch_scorer_controller.py`
- `scripts/evaluate_branch_scorer_robustness.py`
- branch-scorer workflow scripts listed in `scripts/README.md`

## Datasets and external integrations

- Main evaluation datasets + policy: `docs/main_datasets.md`, `docs/datasets_access.md`, `datasets/README.md`
- New-paper dataset status (evaluation vs external supervision vs readiness): `docs/DATASET_STATUS.md`
- External supervision registry: `configs/external_reasoning_datasets_registry.json`

## Repository hygiene conventions

- Put run artifacts under `outputs/` (gitignored).
- Keep external datasets download-on-demand; do not commit raw dataset dumps.
- Treat external warm-start and reliability-weighted BT as **promising exploratory methods**, not final winners.
