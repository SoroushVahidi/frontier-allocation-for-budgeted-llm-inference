# Artifact Index — 2026-05-01

Purpose: identify the Wulver-transferred selector artifacts now on `main`, distinguish aggregate casebooks from trace-enriched node artifacts, and prevent future selector work from confusing diagnostic outputs with claim-bearing evidence.

## Headline counts

| Quantity | Value | Source |
|---|---:|---|
| Broad external-loss trace-complete casebook rows | 47 | `outputs/external_loss_casebook_broad_20260430T185500Z/loss_casebook_trace_complete.csv` |
| Focused gold-present/oracle-fixable rows | 33 | same broad casebook, filtered by `trace_available == gold_present_in_candidate_groups == oracle_selector_would_fix == 1` |
| Focused rows matched to raw records | 33 / 33 | `outputs/focused33_trace_enriched_20260501T000906Z/focused33_trace_enrichment_summary.json` |
| Focused cases with candidate nodes | 33 / 33 | same |
| Focused cases with at least one candidate trace | 33 / 33 | same |
| Focused cases with all extracted candidates traced | 28 / 33 | same |
| Extracted candidate nodes | 73 | same |
| Extracted candidate nodes with trace text | 64 / 73 | same |
| Gold answer in extracted terminal node finals | 8 / 33 | same |
| Gold answer in aggregate casebook answer buckets | 33 / 33 | same |

## A. Canonical selector artifacts

| Path | Contains | Level | Use | Caution |
|---|---|---|---|---|
| `outputs/selector_tournament_compact_export_20260430T_SELECTOR_TOURNAMENT_50CASE_COHERE/` | Compact 50-case selector tournament export | candidate/selector summary | current selector tournament diagnostics | Interpret through selector docs before making claims. |
| `outputs/cohere_real_model_cost_normalized_validation_20260430T_SELECTOR_TOURNAMENT_50CASE_COHERE/` | Associated paid real-model run | real-model validation | paired selector comparison provenance | Do not rerun or overwrite casually. |

## B. Focused33 trace-enrichment artifacts

| Path | Contains | Level | Use | Caution |
|---|---|---|---|---|
| `outputs/focused33_trace_enriched_20260501T000906Z/focused33_trace_enriched.jsonl` | One enriched object per focused row, with candidate nodes and verifier-safe payloads | trace-enriched candidate-node artifact | next input for Cobbe-style full-solution selector tests | Trace-preserved node oracle is only 8/33 unless more terminal nodes are recovered. |
| `outputs/focused33_trace_enriched_20260501T000906Z/focused33_trace_enriched.csv` | Flattened version of the enriched artifact | trace-enriched / tabular | quick inspection | Heavy JSON is encoded in cells. |
| `outputs/focused33_trace_enriched_20260501T000906Z/focused33_trace_enrichment_summary.json` | Coverage counts | summary | first place to check candidate-node trace coverage | This is the authoritative coverage summary for the enriched 33. |
| `outputs/focused33_trace_enriched_20260501T000906Z/focused33_trace_enrichment_report.md` | Human-readable enrichment report | summary/report | reviewer orientation | Keep paired with the JSON summary. |

## C. Broad external-loss casebooks

| Path | Contains | Level | Use | Caution |
|---|---|---|---|---|
| `outputs/external_loss_casebook_broad_20260430T185500Z/loss_casebook_trace_complete.csv` | 47 trace-complete external-loss casebook rows | aggregate answer-group casebook | recover the 33 focused selector failures | Does not embed full candidate-node traces. |
| `outputs/external_loss_casebook_broad_20260430T185500Z/loss_casebook_trace_complete.jsonl` | JSONL version of the 47-row casebook | aggregate answer-group casebook | scripted filtering and enrichment | Same limitation: aggregate-level, not node-trace-level. |
| `outputs/external_loss_casebook_broad_20260430T185500Z/loss_casebook_combined_200.*` | Combined selected broad casebook | aggregate / diagnostic | provenance for broad external-loss review | Includes final-row-only rows; not all trace-complete. |
| `outputs/external_loss_casebook_broad_20260430T185500Z/loss_casebook_final_rows_only.*` | Final-row-only external losses | final-row diagnostic | broad failure inventory | Not suitable for trace-aware selector testing. |
| `outputs/external_loss_casebook_broad_20260430T185500Z/loss_summary.*` | Broad run summary | summary | provenance and counts | Use with the CSV/JSONL, not alone. |
| `outputs/external_loss_casebook_broad_20260430T185500Z/artifact_scan.*` | Source artifact scan | provenance | find upstream raw artifacts | May reference absolute MMFS paths. |

## D. Narrower external-loss casebook

| Path | Contains | Level | Use | Caution |
|---|---|---|---|---|
| `outputs/external_loss_casebook_20260430T184023Z/loss_casebook_200.csv` | Earlier non-broad casebook, 27 selected cases | aggregate casebook | historical reference | Superseded for focused33 work by the broad casebook. |
| `outputs/external_loss_casebook_20260430T184023Z/loss_casebook_200.jsonl` | JSONL version | aggregate casebook | scripted checks | Same scope as CSV. |
| `outputs/external_loss_casebook_20260430T184023Z/loss_summary.*` | Run summary | summary | provenance | Not the current focused selector input. |
| `outputs/external_loss_casebook_20260430T184023Z/artifact_scan.*` | Source artifact scan | provenance | path recovery | Historical. |

## E. Raw trace indexes and validation traces

| Path | Contains | Level | Use | Caution |
|---|---|---|---|---|
| `outputs/trace_complete_external_losses_retry_20260430T204900Z/trace_complete_loss_cases.csv` | 16 trace-complete external losses | trace-complete loss subset | diagnostic overlap with focused selector failures | May overlap with the 47 broad rows. |
| `outputs/trace_complete_external_losses_retry_20260430T204900Z/trace_complete_loss_summary.json` | Summary for those 16 cases | summary | count validation | Selector-failure subset, not full inventory. |
| `outputs/trace_complete_external_losses_retry_20260430T204900Z/cohere_real_model_cost_normalized_validation_20260430T204900Z/per_case_trace_index.csv` | Raw method/example trace index | raw trace index | count traced examples beyond the 47-row casebook | This includes non-loss and external-baseline traces; do not compare directly to the 47 casebook count. |
| `outputs/trace_complete_external_losses_retry_20260430T204900Z/cohere_real_model_cost_normalized_validation_20260430T204900Z/traces/` | Per-case trace JSON files | raw trace files | source for full trace reconstruction | Large-ish provenance; do not edit by hand. |

## F. Diagnostic-only outputs

Artifacts under selector tournaments, L1-defeat experiments, trace retry folders, and logs can be useful for archaeology. They are diagnostic unless a canonical doc promotes them into claim-bearing evidence.

Examples:

- `outputs/l1_defeat_selector_wulver_20260430T182316Z/`
- `outputs/large_selector_tournament_20260430T182316Z/`
- `outputs/best_methods_on_external_losses_20260430T195200Z/`
- `logs/*1016*.out`

## G. Caches and intentionally ignored files

Do not commit or rely on API caches for claims unless explicitly reviewed:

- `cohere_annotation_cache.jsonl`
- verifier/generation caches
- local `.pytest_cache/`, `.ruff_cache/`, `__pycache__/`
- environment files or API-key readiness files containing secrets

Path strings that include `api_key_readiness.json` in artifact scans are filenames, not credentials; still inspect before broad commits.

## Current selector-relevant interpretation

- The 47-row broad casebook is aggregate-level.
- The 33 focused subset is selected from that aggregate casebook.
- The focused33 enriched artifact is the correct next input for trace-aware Cobbe-inspired selector work.
- Aggregate oracle ceiling: 33/33.
- Trace-preserved-node oracle ceiling from the enriched artifact: 8/33 unless more terminal candidate nodes are recovered.
