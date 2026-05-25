# Provider Readiness for Regime Learning

Date: 2026-05-25

---

## Protocol

Each provider was tested with:
- **1 example × 4 methods** (smoke test for basic connectivity + response parsing)
- **4-method protocol smoke test** confirming all four canonical methods work end-to-end
  - `direct_reserve_semantic_frontier_v2`
  - `external_l1_max`
  - `external_s1_budget_forcing`
  - `external_tale_prompt_budgeting`
- Canonical settings: seed=71, budget=6
- No large benchmark claims from smoke tests

---

## Provider Status

| Provider | Status | Model used | Notes |
|---|---|---|---|
| Cohere | READY_NOW | command-r-plus | Baseline; 300-case MATH-500 already complete |
| Cerebras | READY_NOW | llama3.3-70b (or similar) | Slow throughput; answer quality concerns at harder levels |
| Mistral AI | READY_NOW | mistral-large-latest | 300-case GSM8K complete |
| Azure OpenAI | READY_NOW | gpt-4o (deployed endpoint) | GSM8K 300 running as of 2026-05-25 |
| Fireworks | READY_NOW | accounts/fireworks/models/llama-v3p1-70b-instruct | Slower than direct providers; adapter required |
| Cloudrift AI | READY_NOW | cloudrift/Qwen3-235B-A22B | Reasoning-content fallback required (content=null quirk) |
| Modal | UNSUITABLE_OR_UNKNOWN | — | Did not pass protocol smoke test |

---

## Model IDs

```
cohere:        command-r-plus
cerebras:      llama3.3-70b (or active model in CEREBRAS_MODEL env var)
mistral:       mistral-large-latest
azure_openai:  deployment name from AZURE_OPENAI_DEPLOYMENT env var
fireworks:     accounts/fireworks/models/llama-v3p1-70b-instruct
cloudrift_ai:  cloudrift/Qwen3-235B-A22B
```

---

## Adapter implementation notes

- **Fireworks**: Standard OpenAI-compatible Bearer-auth `/v1/chat/completions` endpoint.
  Base URL defaults to `https://api.fireworks.ai/inference/v1` or `FIREWORKS_BASE_URL` env var.
  API key: `FIREWORKS_API_KEY`.

- **Cloudrift AI**: OpenAI-compatible endpoint at `https://inference.cloudrift.ai/v1`.
  Uses `CLOUDRIFT_API_KEY` or `RIFT_API_KEY` env var.
  **Reasoning-content fallback**: Cloudrift's Qwen3 reasoning model returns
  `message.content = null` and puts the actual text in `message.reasoning`.
  The adapter checks `message.content` first, then falls back to `message.reasoning`.
  Base URL: `CLOUDRIFT_BASE_URL` env var or default above.

- **API keys are read from environment variables** and never logged or committed.

---

## Caveats

- Smoke tests validate that all 4 methods can complete one example. They do not establish
  answer quality at scale.
- **Cerebras**: Very slow throughput (~hours for 300 examples). Answer quality at
  difficulty levels 4–5 is not established.
- **Fireworks**: Noticeably slower than Cohere/Mistral direct API. Throughput adequate for
  300-case runs but not for rapid iteration.
- **Cloudrift**: Reasoning model with content=null quirk. Confirmed passing after adapter fix.
  No large benchmark claim.
- **No multi-provider MATH-500 result yet**: Only Cohere MATH-500 300-case pool exists.
  Azure/Cloudrift/Cerebras MATH-500 generation is pending GSM8K completions.

---

## Current generation status (as of 2026-05-25)

| Job | Status |
|---|---|
| Azure GSM8K 300 | Running in tmux `azure_gsm8k_regime300_20260525` |
| Cloudrift GSM8K 300 | Running in tmux `cloudrift_gsm8k_regime300_20260525` |
| Cerebras GSM8K | Running (slow) in tmux `overnight_cerebras_supervisor_20260524` |
| Azure MATH-500 | Waiting for Azure GSM8K to complete |
| Cloudrift MATH-500 | Waiting for Cloudrift GSM8K to complete |

---

## Next generation order

1. Wait for Azure GSM8K 300 to reach 1200/1200 completions
2. Validate output; then launch Azure MATH-500 300 (same canonical settings)
3. Wait for Cloudrift GSM8K 300 similarly, then launch Cloudrift MATH-500 300
4. After 3-provider MATH-500 pool complete: compute complementarity matrix and oracle ceiling lift

---

## Local output directories (not committed)

- `outputs/provider_readiness_audit_20260525/` — per-provider smoke test logs
- `outputs/provider_protocol_smoke_*/` — protocol test bundles
- `outputs/fireworks_cloudrift_adapter_readiness_*/` — adapter readiness run outputs
