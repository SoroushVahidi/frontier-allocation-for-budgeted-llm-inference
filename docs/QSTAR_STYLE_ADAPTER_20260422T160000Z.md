# Q*-style adapter lane (unofficial, caveated) — 2026-04-22T16:00:00Z

## Purpose

This document adds a reviewer-defensible runnable comparator lane for the Q* conceptual family **without** claiming official Q* reproduction.

- Official paper record remains: `qstar_deliberative_planning` (`discuss_only`, provenance-hardened).
- New runnable lane: `qstar_style_adapter` (unofficial, caveated, adapter-based).

## Canonical conceptual source

- Paper: *Q*: Improving Multi-step Reasoning for LLMs with Deliberative Planning
- URL: https://arxiv.org/abs/2406.14283
- PDF: https://arxiv.org/pdf/2406.14283.pdf
- DOI: https://doi.org/10.48550/arXiv.2406.14283

## Explicit separation rule (hard guardrail)

1. **Official paper record** (`qstar_deliberative_planning`)
   - remains provenance-hardened and discuss-only,
   - no verified official repo/artifact path is claimed.

2. **Unofficial runnable comparator** (`qstar_style_adapter`)
   - adapter-based local substrate lane,
   - inspired by Q*-style deliberative best-first search,
   - not an official reproduction and not a faithful replication claim.

## What is implemented in the adapter

- Deliberative frontier search over partial reasoning traces.
- Best-first style branch selection with value-like heuristic score.
- Bounded search budget with expansion/verification actions.
- Explicit caveat metadata and forbidden-claim guardrail in artifacts.

## What is not reproduced

- Official Q* training pipeline.
- Official Q* value/reward model artifacts.
- Official Q* data generation/filtering pipelines.
- Official upstream repo/checkpoint equivalence.

## Contract and runner

- Contract: `configs/qstar_style_adapter_contract_v1.json`
- Runner: `scripts/run_qstar_style_adapter.py`
- Canonical artifacts: `outputs/qstar_style_adapter/<run_id>/`

## Canonical run command

```bash
python scripts/run_qstar_style_adapter.py \
  --contract-config configs/qstar_style_adapter_contract_v1.json
```

## Paper/table placement guidance

- Keep official Q* paper entry in direct-family conceptual discussion with provenance limitations.
- If adapter results appear in tables, label row as:
  - **"Q*-style adapter (unofficial, caveated)"**
- Never merge this row into blocks that imply official Q* reproduction.

## Manuscript-safe wording (ready to paste)

> We also include an unofficial Q*-style deliberative-search adapter to stress-test a close conceptual family under our evaluation contract. This adapter is inspired by the Q* paper’s best-first / heuristic-guided multi-step reasoning perspective, but it is not an official reproduction of Q* and should be interpreted only as a caveated experimental comparator.

## Exact caveat wording (ready to paste)

> Unofficial comparator disclaimer: `qstar_style_adapter` is a local adapter inspired by the Q* paper (arXiv:2406.14283) and is not equivalent to, or a reproduction of, the official Q* method, code, training artifacts, or reported results.
