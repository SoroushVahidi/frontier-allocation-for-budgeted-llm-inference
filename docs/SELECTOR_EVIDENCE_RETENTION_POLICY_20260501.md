# Selector Evidence Retention Policy (2026-05-01)

This policy defines what to keep when collecting more cases where our method loses to external baselines while the correct answer is present in the discovered tree / candidate answer groups.

## Why this exists

Selector choosing needs more than aggregate accuracy summaries. We need enough evidence to separate:

- present-not-selected failures;
- absent-from-tree failures;
- trace-reconstruction failures;
- current-correct cases that a selector might break.

The repository's default `.gitignore` intentionally ignores most raw `outputs/` payloads. That protects the repo from logs, caches, and huge transient files, but it can also hide selector casebooks and JSONL trace payloads unless they are explicitly whitelisted.

## Recommended output prefixes

Use one of these timestamped output roots for new selector-evidence collections:

```text
outputs/selector_evidence_package_<timestamp>/
outputs/selector_loss_case_collection_<timestamp>/
outputs/external_loss_selector_case_collection_<timestamp>/
```

These prefixes are whitelisted in `.gitignore` so curated evidence files are visible to git.

## Keep these files

Commit these when they are generated and do not contain secrets:

| File type | Why keep it |
|---|---|
| `manifest.json` | Run contract, command, commit, dataset, method list, seed, budget, provider/model metadata. |
| `selector_evidence_summary.json` / `.csv` / `.md` | First-pass counts and interpretation. |
| `loss_casebook*.csv` and `loss_casebook*.jsonl` | Aggregate and row-level present-not-selected inventory. |
| `present_not_selected_casebook*.csv` / `.jsonl` | Direct input to selector choice. |
| `absent_from_tree_casebook*.csv` / `.jsonl` | Needed to separate coverage failure from selector failure. |
| `current_correct_risk_casebook*.csv` / `.jsonl` | Needed to measure selector break risk. |
| `per_example_records.jsonl` | Often required to reconstruct candidate pools and traces. |
| `final_branch_states.jsonl` | Required when full per-example records are unavailable. |
| `selector_candidate_pool.jsonl` | Best source for answer-group candidates if available. |
| `trace_index.csv` / `per_case_trace_index.csv` | Maps cases to trace files and upstream records. |
| `traces/*.json` / `traces/*.jsonl` | Required for trace-aware outcome-verifier selectors. |
| `focused_trace_enriched*.jsonl` / `.csv` | Verifier-safe candidate-node payloads. |
| `verifier_call_plan.json` / `.jsonl` | Dry-run call accounting before paid verifier scoring. |
| `selector_summary.csv` / `.json` / `.md` | Selector comparison outputs. |
| `selector_casebook.csv` / `.jsonl` | Fix/break/no-op case-level selector decisions. |
| `README.md` or `REPORT.md` | Human-readable interpretation and cautions. |

## Usually omit these files

Keep ignored unless a separate review says they are safe and necessary:

| File type | Reason |
|---|---|
| `*cache*.jsonl`, `*cache*.json` | May contain paid API outputs, prompts, accidental sensitive text, or large duplicates. |
| `logs/`, `*.log`, Slurm stdout/stderr | Usually noisy and not needed once manifest/report exists. |
| `progress_heartbeat.jsonl` | Runtime progress only. |
| `compressed_*.tar.gz` | Too large for normal GitHub review. |
| raw environment or readiness files | Risk of secrets or machine-specific state. |

## Required fields for present-not-selected rows

Each row in a selector-loss casebook should include, where available:

- stable case ID;
- dataset and split;
- question/problem statement;
- gold answer in evaluation-only field;
- our selected answer;
- external baseline selected answer;
- whether external is correct;
- whether our selected answer is correct;
- all discovered answer groups;
- whether gold is present in aggregate answer groups;
- extracted candidate nodes;
- whether gold appears in extracted terminal node finals;
- trace availability for each candidate;
- source artifact path;
- method/budget/seed/provider/model metadata;
- no gold/oracle fields in verifier input payloads.

## Required summary counts

Every package should report:

- total paired cases scanned;
- external-correct / our-wrong cases;
- trace-complete external-loss rows;
- present-not-selected aggregate rows;
- absent-from-tree rows;
- rows matched to raw records;
- cases with candidate nodes;
- cases with at least one candidate trace;
- cases with all extracted candidates traced;
- extracted candidate-node count;
- traced candidate-node count;
- gold present in aggregate answer buckets;
- gold present in extracted terminal node finals;
- current-correct cases available for break-risk testing.

## Gitignore rule of thumb

Do not loosen `.gitignore` globally for all `outputs/**/*.jsonl` or all casebooks. Use curated selector-evidence package prefixes instead. This keeps the repo reviewable while preventing important selector evidence from becoming invisible.

## Claim boundary

A selector-evidence package is diagnostic unless promoted by canonical docs. It can justify choosing the next selector family, but it does not by itself justify a broad claim that we beat `external_l1_max`.

- Added artifacts-only collector script `scripts/collect_selector_evidence_present_not_selected.py` and synthetic regression test `tests/test_collect_selector_evidence_present_not_selected.py` to produce selector-evidence packages without paid API calls.
