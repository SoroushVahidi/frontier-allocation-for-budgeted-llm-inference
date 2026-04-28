# Cohere API Key Readiness OK

- timestamp_utc: 20260428T181029Z
- COHERE_API_KEY: present
- smoke_test: success
- model_used: command-r-plus-08-2024
- package_import_status: import_ok
- token_metadata:
  - input_tokens: 202.0
  - output_tokens: 2.0

Cohere API is usable in this environment for minimal chat requests.

## Exact minimal smoke-test command

```bash
python - <<'PY'
import os
import cohere

client = cohere.ClientV2(api_key=os.environ['COHERE_API_KEY'])
resp = client.chat(
    model='command-r-plus-08-2024',
    messages=[{'role': 'user', 'content': 'OK'}],
    max_tokens=2,
)
print('ok')
PY
```
