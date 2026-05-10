# Excluded or Non-FULL Failure Summary

This document summarizes the failures that were identified but excluded from the FULL failure inventory or categorized as PARTIAL/ID_ONLY.

## Categorization
- **PARTIAL**: 467 records. These records have some metadata but lack critical components (e.g., problem text, gold answer, or selected answer) required for full pattern mining.
- **ID_ONLY**: 445 records. Only the case ID and method ID were found in the logs or archives, with no associated trace data.

## Reasons for Exclusion from FULL
1. **Missing Trace Data**: 445 cases lacked any associated trace data in the searched artifacts.
2. **Incomplete Records**: 467 cases were found but had missing fields (e.g., API errors during collection, or truncated logs).
3. **Older Methods**: Hundreds of FULL failures were identified for methods like `strict_f3` or `strict_gate1_cap_k6` which are not the current "latest/best" method and thus excluded from this specific bundle.
4. **Successes**: Most records in the searched artifacts were successes and were naturally excluded.

## Usage
For pattern mining and error analysis, please refer to `full_latest_method_failures.csv` or `canonical_latest_method_failures.csv`.
