# Project Handoff — 2026-05-10

## Overview
This folder contains a curated set of documents and artifacts consolidated from multiple local paths:
- `/home/soroush/research-next-wt`
- `/home/soroush/frontier-allocation-for-budgeted-llm-inference`

The goal is to provide a GitHub-ready package for the next phase of the project, focusing on the latest failure inventories, experiment summaries, and research state.

**Note**: This handoff folder is a curated summary, not raw source-of-truth output. PR #362 (first continue-answer fix) is merged. Hard-continue patch and targeted Cohere validation results may not be fully present in this local folder if the Codex Web output was not copied locally.

## Contents
- `CURRENT_RESEARCH_STATE.md`: High-level summary of the current best method and failure patterns.
- `FAILURE_BANK_SUMMARY.md`: Summary of the consolidated failure bank.
- `canonical_failure_bank.csv`: The main inventory of 81 unique failure cases.
- `full_failure_cases.csv`: Detailed data for a subset of high-quality failure cases.
- `failure_family_counts.csv`: Breakdown of failure modes by category.
- `newly_discovered_cases.csv`: Cases identified in the most recent live sweeps.
- `LOCAL_ONLY_ARTIFACTS_TO_PRESERVE.md`: List of large artifacts (e.g., raw logs) that are kept locally but not included in this curated folder.
- `NEXT_PATTERN_MINING_PLAN.md`: Proposed next steps for analyzing the failure bank.
- `EXPERIMENT_SUMMARY_INDEX.md`: Index of recent experiments and their key findings.
- `TEST_AND_FIX_STATUS.md`: Current status of unit tests and bug fixes.
- `file_manifest.csv`: Manifest of all files included in this handoff.

## Usage
This folder is intended to be pushed to the main repository to preserve the research state across environments.
