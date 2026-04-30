# Current project status

This document is the short, current orientation note for the repository. It supersedes older broad-status notes for day-to-day work, while preserving all dated documents as provenance.

## Current project identity

This repository studies **frontier allocation for budgeted LLM inference** under explicit compute/action-budget contracts.

The current paper-facing frame is not the old binary revise-routing story. The central question is:

> Given a fixed inference budget and multiple active reasoning/candidate paths, where should the next unit of compute go, and how should the final answer be selected from the explored frontier?

## Current development goal

The active engineering goal is now **defeat `external_l1_max` honestly**, not by overclaiming, but by producing a trace-complete, paired, claim-safe result.

The immediate subgoal is selector-first:

> Determine whether the current candidate pool already contains the correct answer often enough that better final selection can close the gap to L1.

## Current phase

**Phase:** selector-oracle and candidate-pool trace diagnostics.

Current priority order:

1. Make real artifacts trace-complete enough for selector-oracle analysis.
2. Measure `gold_present_rate`, `oracle_selector_accuracy`, and `selector_gap` on real candidate pools.
3. If oracle ceiling is high, improve selectors/rerankers.
4. If oracle ceiling is low, move to candidate generation / frontier coverage repair.

## Current known blocker

The repository has datasets and many result artifacts, but the immediate blocker is narrower:

> Existing real outputs are not yet consistently confirmed to contain the candidate-pool schema required for selector-oracle analysis.

The next decisive measurement requires per-example rows with gold answer, selected answer, correctness, and candidate answer groups with normalized answers, support/source metadata, and optional OV/PRM scores.

## Current safe claim boundary

Safe:

- The repository implements a fixed-budget frontier-allocation framework with multiple controller families, selectors, diagnostics, and canonical artifact builders.
- The evidence hierarchy is explicit and conservative.
- DR-v2/OV/PRM selector work is a promising development direction because some failures are present-but-not-selected.

Not safe yet:

- Do **not** claim robust or broad superiority over `external_l1_max`.
- Do **not** claim OV/PRM rerankers defeat L1 without completed paired rows.
- Do **not** treat mock-backed verifier results as real Cohere verifier evidence.

## Current method interpretation

- `strict_f3` remains the manuscript-facing matched-surface representative under the existing canonical paper surface.
- `strict_gate1_cap_k6` remains a broader operational default on a different surface.
- DR-v2 and its OV/PRM rerank variants are the active L1-defeat development family, not automatically promoted manuscript winners.

## Current next action

The next non-circular task is:

1. Audit all `per_example_records.jsonl` artifacts under `outputs/`.
2. Classify each artifact as usable, schema-adaptable, final-rows-only, empty/unscored, or unclear.
3. Adapt `scripts/analyze_selector_oracle_ceiling.py` if a schema-adaptable artifact exists.
4. If no existing artifact is usable, patch runtime metadata emission and run only a tiny trace-complete smoke test.
5. Run selector-oracle analysis on that real trace-complete artifact.

## Important documents

- `docs/CANONICAL_START_HERE.md` — canonical reviewer/collaborator orientation.
- `docs/DOCS_INDEX.md` — active vs diagnostic vs historical document map.
- `docs/SELECTOR_START_HERE.md` — current selector/L1-defeat track.
- `docs/OUTPUTS_SELECTOR_TRACE_INDEX.md` — selector trace artifact index and usability policy.
- `docs/PAPER_SOURCE_OF_TRUTH.md` — claim-eligible evidence rules.
- `docs/PAPER_CLAIMS_AND_EVIDENCE_MAP.md` — safe vs unsafe claim map.
- `docs/PAPER_OPEN_GAPS_AND_RISKS.md` — known open gaps.

## One-sentence status

The repository is organized enough for serious paper work, but the active L1-defeat path now depends on one real trace-complete selector-oracle measurement that tells us whether selector improvements alone can beat L1 or whether frontier coverage must be repaired next.
