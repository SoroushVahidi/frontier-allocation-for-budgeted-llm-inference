# Ignored/Unpushed Artifact Audit

- generated_at_utc: 2026-04-30T19:28:59.966899+00:00
- head: `5d9347d2cd4c5ec0d4bf91ae7c41f95ef9917323`
- origin_main: `5d9347d2cd4c5ec0d4bf91ae7c41f95ef9917323`
- head_equals_origin_main: `True`
- ignored_file_count: `778`
- total_ignored_size: `1.3GB`

## Counts By Category

- cache: 608 files, 12.3MB
- loss_casebook_output: 4 files, 343.9KB
- per_example_records: 34 files, 98.0MB
- raw_casebook: 6 files, 1.3MB
- selector_output: 9 files, 103.2KB
- summary_or_report: 3 files, 22.5KB
- unknown: 114 files, 1.2GB

## Focus Directory Snapshot

- outputs/external_loss_casebook_20260430T184023Z/: 4 ignored files
- outputs/external_loss_casebook_broad_20260430T185500Z/: 8 ignored files
- outputs/large_selector_tournament_20260430T182316Z/: 18 ignored files
- outputs/l1_defeat_selector_wulver_20260430T182316Z/: 7 ignored files
- logs/loss_casebook_200_1016382.: 0 ignored files
- logs/loss_casebook_broad_: 0 ignored files

## Explicit `git check-ignore -v` Checks

- `outputs/external_loss_casebook_broad_20260430T185500Z/loss_summary.json` -> `TRACKABLE (no ignore match)`
- `outputs/external_loss_casebook_broad_20260430T185500Z/loss_summary.md` -> `TRACKABLE (no ignore match)`
- `outputs/external_loss_casebook_broad_20260430T185500Z/loss_casebook_combined_200.csv` -> `.gitignore:58:outputs/**/*casebook*.csv	outputs/external_loss_casebook_broad_20260430T185500Z/loss_casebook_combined_200.csv`
- `outputs/external_loss_casebook_broad_20260430T185500Z/loss_casebook_combined_200.jsonl` -> `.gitignore:59:outputs/**/*casebook*.jsonl	outputs/external_loss_casebook_broad_20260430T185500Z/loss_casebook_combined_200.jsonl`
- `outputs/external_loss_casebook_broad_20260430T185500Z/cohere_annotation_cache.jsonl` -> `.gitignore:63:outputs/**/cohere_annotation_cache.jsonl	outputs/external_loss_casebook_broad_20260430T185500Z/cohere_annotation_cache.jsonl`
- `outputs/large_selector_tournament_20260430T182316Z/selector_tournament/selector_summary.csv` -> `TRACKABLE (no ignore match)`
- `outputs/large_selector_tournament_20260430T182316Z/selector_tournament/selector_summary.json` -> `TRACKABLE (no ignore match)`

## High-Importance Ignored Files

- `outputs/dataset_integration_report.json` (13.5KB)
- `outputs/external_baseline_integration_report.json` (9.0KB)
- `outputs/local_only_anonymity_scan_report.csv` (26.0B)

## Recommended Keep Ignored

- `*.jsonl` raw casebooks/per-example traces/caches
- verifier/cohere cache files
- large logs and bulky raw artifacts

## Recommended Consider Tracking

- lightweight summary/report artifacts currently ignored
- focus run summaries if they support paper/repo decisions

## `docs/` Untracked/Unpushed Check

- untracked_docs_count: `0`
- none

## Optional `git add -f` Commands (not executed)

git add -f "outputs/dataset_integration_report.json"
git add -f "outputs/external_baseline_integration_report.json"
git add -f "outputs/local_only_anonymity_scan_report.csv"
