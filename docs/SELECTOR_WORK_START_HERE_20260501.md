# Selector Work — Start Here (2026-05-01)

This document is the current front door for final-answer selector work after the Wulver artifact transfer.

## Problem

We need a selector that chooses the final answer/node from already-discovered candidates. The immediate failure profile is not only candidate generation; many DR-v2 losses are **present-not-selected**: the correct answer is present in an explored answer bucket, but the runtime selector commits to a different answer.

## Literature-backed first selector

The first serious selector family should be **Cobbe-style outcome verification**, adapted to frontier nodes:

1. take a problem and a candidate solution trace;
2. estimate `p(correct | problem, candidate_trace, final_answer)`;
3. aggregate candidate scores by normalized answer group;
4. choose the winning answer group;
5. return the highest-scoring representative node in that group.

If the backend is a prompted LLM rather than a trained verifier, call it **Cobbe-inspired prompted outcome-verifier reranking**, not the exact Cobbe method.

## Files to use next

Use the trace-enriched focused artifact as the next selector input:

```text
outputs/focused33_trace_enriched_20260501T000906Z/focused33_trace_enriched.jsonl
```

Its coverage summary is:

```text
outputs/focused33_trace_enriched_20260501T000906Z/focused33_trace_enrichment_summary.json
```

The broad casebook that defines the 47/33 split is:

```text
outputs/external_loss_casebook_broad_20260430T185500Z/loss_casebook_trace_complete.csv
```

## What not to use as the main selector input

Do not use `scripts/run_selector_on_gold_present_losses.py` alone as a Cobbe-style full-solution test. That script reconstructs answer-group candidates from aggregate fields and does not score full candidate traces.

Do not treat final-answer-only verification as Cobbe-style solution verification.

Do not use final-row-only casebooks for trace-aware selector claims.

## Current ceilings

| Ceiling | Value | Meaning |
|---|---:|---|
| Aggregate casebook oracle | 33 / 33 | The correct answer bucket is present in the 33 focused aggregate casebook rows. |
| Trace-preserved-node oracle | 8 / 33 | Among extracted terminal candidate-node finals in the focused33 enrichment, only 8 cases currently expose a traced terminal node with the gold final answer. |

This distinction is critical. A trace-aware node selector over `focused33_trace_enriched.jsonl` cannot be expected to reach 33/33 unless additional gold-bearing candidate nodes are recovered.

## Immediate next implementation task

Adapt or create a selector runner that ingests:

```text
outputs/focused33_trace_enriched_20260501T000906Z/focused33_trace_enriched.jsonl
```

It should:

- build verifier prompts from problem + candidate trace + final answer;
- never include gold/oracle fields in verifier prompts;
- cache every verifier score;
- support dry-run call planning;
- report both aggregate oracle ceiling and trace-preserved-node oracle ceiling;
- compare against current selected answer and support-family baselines;
- report fixes, breaks, override precision, verifier calls, and trace coverage.

## Required reporting for a selector run

Every selector result should include:

- input artifact path;
- number of cases;
- candidate-node count;
- trace-bearing node count;
- aggregate gold-present count;
- trace-preserved gold-present count;
- selected answer and representative node;
- fixes / breaks / net fixes;
- override precision;
- verifier calls and cache hits;
- whether the result is claim-bearing or diagnostic-only.

## Claim discipline

- Do not claim broad superiority over `external_l1_max` from the 33 focused subset.
- Do not claim Cobbe-style verification if the verifier only sees answer text.
- Do not claim a verifier failed if the gold node was absent from the trace-preserved candidate set.
- Do not compare the 47 aggregate casebook rows directly against raw per-case trace-index counts; they answer different questions.
