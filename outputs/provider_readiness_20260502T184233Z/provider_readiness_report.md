# Provider Readiness Report

**Timestamp:** 2026-05-02T18:42:33.891030+00:00
**Git Commit:** unknown
**Python:** 3.12.3 (/usr/bin/python3)

## Summary

- **Cohere**: SDK_INSTALL_FAILED
- **Hugging Face**: SDK_INSTALL_FAILED
- **No secret values printed or written**: Yes

## Cohere Status

- **Readiness:** sdk_install_failed
- **Key present:** False
- **SDK import (initial):** False
- **SDK install attempted:** True
- **SDK import (after install):** False
- **Model requested:** command-a-03-2025

**Error (sanitized):** Failed to install cohere SDK

## Hugging Face Status

- **Readiness:** sdk_install_failed
- **HF_TOKEN present:** False
- **HUGGINGFACE_HUB_TOKEN present:** False
- **SDK import (initial):** False
- **SDK install attempted:** True
- **SDK import (after install):** False

**Error (sanitized):** Failed to install huggingface_hub SDK


## Recommendation

❌ At least one provider blocked. Recommendation: **Fix provider readiness before running experiments**

## Security Note

No secret values (API keys, tokens) were printed to stdout, logged, or written to output files.
