# Exhaustive Latest-Method Failure Bank — 2026-05-10

## Overview
This directory contains the canonical latest-method failure bank for pattern mining and error analysis. This bank is the result of an exhaustive audit across all local worktrees, archives, and migration artifacts.

## Key Significance
- **Supersedes earlier inventories**: This bank replaces the previous 28-case and 42-case limited inventories.
- **Substantial Data**: There are **174 unique FULL latest-method failure case_ids** available for analysis.
- **Exhaustive Search**: Over 6,000 potential failure-bearing files were inspected to compile this list.

## Contents
- `README.md`: This file.
- `canonical_latest_method_failures.csv`: Unique `case_id` records (174) for the latest method variants.
- `full_latest_method_failures.csv`: All 215 FULL failure records (including duplicates across different runs). **Use this for pattern mining.**
- `partial_latest_method_failures.csv`: 467 records with incomplete evidence.
- `id_only_latest_method_failures.csv`: 445 records where only the ID was found.
- `additional_full_failures_not_in_main.csv`: 162 FULL records found locally that were not in the previous handoff/main inventories.
- `failure_family_counts.csv`: Breakdown of failure families among the 174 unique FULL case_ids.
- `artifact_inventory.csv`: Inventory of artifacts searched during the audit.
- `excluded_or_non_full_summary.md`: Summary of PARTIAL, ID_ONLY, and excluded records.
- `audit_summary.json`: Machine-readable summary of counts and sources.

## Data Normalization
All CSV files have been normalized to a standard schema:
- `case_id`, `method_id`, `method_version`, `evidence_completeness`, `failure_family`, `problem_text`, `gold_answer`, `selected_answer`, `selected_source`, `artifact_source`, `has_candidate_metadata`, `has_trace_metadata`, `has_pal_metadata`, `local_or_tracked_source`, `notes`.

*Note: Raw source artifacts (traces, logs, JSONL) remain local or in archives and are not included in this repository to keep it lightweight.*
