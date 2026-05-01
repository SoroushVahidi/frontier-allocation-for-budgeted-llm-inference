# Focused-33 trace enrichment (2026-05-01T00:09:06Z)

## Inputs

- Broad loss casebook: `outputs/external_loss_casebook_broad_20260430T185500Z/loss_casebook_trace_complete.csv`
- Same filter as `scripts/run_selector_on_gold_present_losses.py`:
  `trace_available == gold_present_in_candidate_groups == oracle_selector_would_fix == 1`

## Outputs (committed snapshot)

Directory: [`outputs/focused33_trace_enriched_20260501T000906Z/`](../outputs/focused33_trace_enriched_20260501T000906Z/)

| File | Role |
|------|------|
| `focused33_trace_enriched.jsonl` | One enrichment object per focused row (candidate nodes + verifier-safe payloads) |
| `focused33_trace_enriched.csv` | Flattened view (heavy JSON encoded in CSV columns) |
| `focused33_trace_enrichment_summary.json` | Machine-readable counts |
| `focused33_trace_enrichment_report.md` | Short Markdown summary |

## Counts

From `focused33_trace_enrichment_summary.json`:

- Focused rows: **33**
- Raw upstream records matched: **33 / 33** (via `per_example_records.jsonl` **or** `final_branch_states.jsonl` under each `source_artifact`)
- Cases with extracted candidate nodes: **33**
- Cases with ≥1 candidate trace text: **33**
- Cases where **every** extracted candidate carries trace text: **28**
- Extracted candidate nodes (dedup by `(candidate_id, final_answer)`): **73**, with trace text **64** (~87.7%)

### Gold alignment (canonical GSM8K-style normalization)

Two distinct checks:

1. **`cases_gold_canonical_in_casebook_candidates_aggregate`** = **33**  
   Gold appears in `all_candidate_answer_groups` for each focused row (expected by the filter definition).

2. **`cases_gold_canonical_in_extracted_node_finals`** = **8**  
   Gold appears among **final_answer** strings on the reconstructed branch/final-node list we extract from upstream JSON. Lower count is normal when casebook aggregates list more answer buckets than surviving distinct terminal branches in `final_branch_states`.

### Casebook vs reconstructed buckets

Canonical answer-group disagreement (casebook JSON list vs reconstructed node finals) remains high (**32**) for the same reason: aggregate answer buckets are not identical to distilled terminal-branch finals.

## Sufficiency for *true* Cobbe-style full-solution verification

**Partial.**

**What improved:** Compared with the CSV-only aggregate casebook, this bundle exposes `trace_text` (from `trace` / `trace_events` / `steps`, via `experiments/selector_candidate_extraction._extract_trace`) per extracted candidate wherever those fields exist upstream, plus `problem_statement`. `verifier_input` omits gold/oracle hints for offline evaluation workflows.

**What is still incomplete:** For many cases, the reconstructed branch finals are **a strict subset** of the answer buckets recorded in `all_candidate_answer_groups`. Some aggregates represent answer families that collapsed or were summarized away in `final_branch_states` / pooled metadata. Cobbe verification that requires **every** competing full solution alongside the oracle gold still needs richer upstream payloads (full `selector_candidate_pool` coverage, fused `loss_cases.jsonl`, or regenerated `per_example_records.jsonl`) so every bucket has a surviving branch record.

Missing fields by construction if absent upstream:

- Dedicated `selector_candidate_pool` blobs on TRACE_SUBSET bundles (often only `final_branch_states`)
- `our_metadata_json` / `final_branch_states` verbatim from cost-normalization runs unless present in matched `result_metadata`

## How to rerun enrichment

```bash
python scripts/enrich_focused33_with_candidate_traces.py \
  --loss-casebook-dir outputs/external_loss_casebook_broad_20260430T185500Z \
  --output-dir outputs/focused33_trace_enriched_$(date -u +%Y%m%dT%H%M%SZ)
```

Implemented script: [`scripts/enrich_focused33_with_candidate_traces.py`](../scripts/enrich_focused33_with_candidate_traces.py).

## Next offline Cobbe-inspired step (once coverage is satisfactory)

Adapt or extend **`scripts/run_cobbe_style_outcome_verifier_diagnostic.py`** (or **`scripts/run_outcome_verifier_selector_diagnostic.py`**) so it ingests **`focused33_trace_enriched.jsonl`** as a canonical candidate/trace source—today those diagnostics assume separate trace-dir + casebook contracts. No paid API execution is implied by this enrichment step itself.
