# Cohere API Key Readiness Issue

- timestamp_utc: 20260428T180032Z
- issue_class: package_or_import_error
- COHERE_API_KEY: present
- smoke_test: failure
- model_used: command-r-plus-08-2024
- package_import_status: failed (`ModuleNotFoundError: No module named 'cohere'`)
- sanitized_error_tail: `ModuleNotFoundError: No module named 'cohere'`

## Minimal smoke-test snippet used

```python
import os
import cohere

client = cohere.ClientV2(api_key=os.environ["COHERE_API_KEY"])
resp = client.chat(
    model="command-r-plus-08-2024",
    messages=[{"role": "user", "content": "OK"}],
    max_tokens=2,
)
```

## Recommended fix

Install the Cohere Python SDK in the active runtime used for this shell/session (e.g., `pip install cohere` in the same environment), then rerun the same minimal smoke test. If running via `sbatch`, ensure the job environment also has the package installed and can import it.
