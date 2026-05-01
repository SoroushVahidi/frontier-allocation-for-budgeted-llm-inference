# Repository Cleanup Policy — 2026-05-01

This policy exists because Wulver/MMFS artifacts were transferred into GitHub to preserve selector provenance. Cleanup should make those artifacts easier to understand, not erase evidence needed for future selector work.

## Rules

1. **Index before deleting.** Do not remove Wulver-transferred artifacts until their purpose, counts, and downstream dependencies are recorded in an artifact index.
2. **Do not commit secrets.** Never commit API keys, environment files, or raw authentication headers.
3. **Avoid API caches unless explicitly reviewed.** Files such as `cohere_annotation_cache.jsonl`, generation caches, and verifier caches should usually stay ignored unless a result note says they are required and safe.
4. **Do not relabel answer-only verification.** A verifier that sees only final answers is not Cobbe-style full-solution verification.
5. **Distinguish artifact levels.** Mark each artifact as aggregate casebook, trace-enriched candidate-node artifact, raw trace index, raw trace file, or diagnostic output.
6. **Do not overwrite real-model outputs.** Timestamped paid-run outputs are provenance. Prefer adding a new output directory or report.
7. **Keep claim-bearing evidence small and interpretable.** Summaries, manifests, row counts, and result notes should be the first thing a reviewer reads.
8. **Use dry-runs before paid calls.** Selector/verifier work must report expected calls before any paid API run.
9. **Keep gold out of verifier inputs.** Gold answers and oracle labels belong only in post-hoc evaluation fields.
10. **Prefer PR cleanup over force pushes.** Large artifact transfers should be followed by indexing/polish PRs, not destructive history edits.

## Cleanup candidates should be labeled, not removed

When finding a suspicious or redundant output directory, add it to an index or report as a cleanup candidate with:

- path;
- size;
- likely purpose;
- whether any canonical doc references it;
- whether tests or scripts depend on it;
- whether it contains caches, traces, summaries, or paid outputs.

## Selector artifact cautions

- `outputs/external_loss_casebook_broad_20260430T185500Z/loss_casebook_trace_complete.csv` is aggregate-level despite the phrase `trace_complete`.
- `outputs/focused33_trace_enriched_20260501T000906Z/focused33_trace_enriched.jsonl` is the current trace-enriched input for full-solution selector experiments.
- The aggregate oracle ceiling for the focused set is 33/33.
- The trace-preserved-node oracle ceiling in the enriched artifact is currently 8/33.

## Safe cleanup sequence

1. Build or update an artifact inventory.
2. Confirm counts and dependencies.
3. Add a doc note explaining what will be removed or ignored.
4. Remove only caches, duplicate transient logs, or outputs explicitly marked nonessential.
5. Run relevant tests.
6. Commit with a message that names the cleanup scope.
