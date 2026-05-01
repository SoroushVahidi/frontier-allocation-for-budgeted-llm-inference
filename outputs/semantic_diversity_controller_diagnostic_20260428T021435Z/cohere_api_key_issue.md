# Cohere API key issue report

- Timestamp (UTC): 20260428T021559Z
- Runtime context (detected): `slurm`
- Model: `command-r-plus-08-2024`
- `COHERE_API_KEY` presence: `present`
- Failure class: `network_or_timeout`

## What happened
- Cohere readiness/smoke test failed before rerun.

## How to fix
- Retry from a networked environment or cluster node with outbound access.
- Set key format (placeholder only):
```bash
export COHERE_API_KEY="..."
```

## Exact rerun command
```bash
python scripts/run_semantic_diversity_controller_diagnostic.py --mode cohere --run-live-cohere
```

## Sanitized error
```text
smoke test timed out after 45s
```
