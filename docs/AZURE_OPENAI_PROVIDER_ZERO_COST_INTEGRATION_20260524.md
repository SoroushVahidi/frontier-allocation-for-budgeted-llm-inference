# Azure OpenAI Provider — Zero-Cost Integration Report

> Created: 2026-05-24T15:55:00Z | No API calls. No Azure cost. No jobs launched.

---

## 1. Was Azure Support Implemented or Only Planned?

**IMPLEMENTED.** The `azure_openai` provider is now fully wired into:
- `experiments/branching.py` — `APIBranchGenerator` constructor, routing, new `_call_azure_chat_api()` method
- `experiments/frontier_matrix_core.py` — `resolve_api_key_for_provider()`
- `scripts/run_cohere_real_model_cost_normalized_validation.py` — allowlist, argparse, model/key dicts, readiness check, `use_openai_api` flag

No Azure API calls were made. All validation was done via mocked unit tests and offline dry-run.

---

## 2. Files Changed

### `experiments/branching.py`
- Added `import os` to module imports (was missing; required for `os.environ.get()` in `__init__`)
- `APIBranchGenerator.__init__()`: Added `azure_openai` case for `default_base_url`:
  ```python
  elif self.provider == "azure_openai":
      default_base_url = os.environ.get("AZURE_OPENAI_ENDPOINT", "https://api.openai.com/v1")
  ```
- `_call_api()`: Added routing before the OpenAI fallthrough:
  ```python
  if self.provider == "azure_openai":
      return self._call_azure_chat_api(prompt)
  ```
- **New method `_call_azure_chat_api()`**: Uses `/chat/completions`, `max_tokens` (not `max_completion_tokens`), `Bearer` auth, full retry/backoff logic matching `_call_mistral_chat_api()`.

### `experiments/frontier_matrix_core.py`
- `resolve_api_key_for_provider()`: Added:
  ```python
  if p == "azure_openai":
      return os.getenv("AZURE_OPENAI_API_KEY")
  ```

### `scripts/run_cohere_real_model_cost_normalized_validation.py`
- Provider allowlist: `{"cohere", "openai", "cerebras", "mistral", "azure_openai"}`
- New CLI argument: `--azure-model` (default: `AZURE_OPENAI_DEPLOYMENT` env var)
- `model_by_provider["azure_openai"] = args.azure_model`
- `api_keys["azure_openai"] = os.getenv("AZURE_OPENAI_API_KEY", "")`
- Readiness check: checks `AZURE_OPENAI_API_KEY` AND `AZURE_OPENAI_ENDPOINT` presence; reason string never contains key values
- `use_openai_api=(provider in {"openai", "mistral", "azure_openai"})` — enables real `LLMVerifyProxyVerifier`

---

## 3. Were Any Real Azure API Calls Made?

**NO.** Confirmed zero Azure API calls:
- All unit tests use `unittest.mock.patch` on `urllib.request.urlopen`
- Dry-run call plans use `--dry-run-call-plan` flag (no network I/O)
- Azure cost: $0.00

---

## 4. Azure Env Vars Present (Boolean Check Only)

| Variable | Present |
|---|---|
| `AZURE_OPENAI_API_KEY` | **YES** |
| `AZURE_OPENAI_ENDPOINT` | **YES** |
| `AZURE_OPENAI_DEPLOYMENT` | **YES** (`gpt-4.1-mini`) |
| `AZURE_OPENAI_API_VERSION` | **YES** (not needed for v1-compat endpoint) |
| `AZURE_OPENAI_STRONG_DEPLOYMENT` | **YES** (`gpt-5.4` — not used yet) |

All required vars present. Readiness: **READY**.

---

## 5. Tests Added and Results

**File:** `tests/test_azure_openai_provider_integration.py`  
**Count:** 23 tests — **23 passed, 0 failed**

| Test class | Count | Coverage |
|---|---|---|
| `TestProviderAllowlist` | 4 | `azure_openai` accepted; unknowns rejected; existing providers unaffected |
| `TestApiKeyResolution` | 3 | Key resolved from env; `None` when absent; existing providers unaffected |
| `TestAPIBranchGeneratorAzure` | 6 | `base_url` from env; trailing slash stripped; model = deployment name; routed to `_call_azure_chat_api`; `_call_responses_api` never called |
| `TestCallAzureChatApiPayload` | 3 | Endpoint is `/chat/completions`; `Authorization: Bearer ...` header present; `max_tokens` (not `max_completion_tokens`); no real network call |
| `TestAzureReadinessCheck` | 5 | All four key/endpoint presence combos; reason string never contains secret value |
| `TestAzureDryRunCallPlan` | 2 | 4000-row plan (1000 examples × 4 methods); 40-row 10-example smoke plan |

All tests are offline — no network calls, no API cost.

---

## 6. Smoke-Test Plans Prepared for Later Approval

Both plans validated via `--dry-run-call-plan` (zero API calls). **Both require explicit user approval before launch.**

### Plan A: 1-Example Smoke (minimal)
- **Examples:** 1 × 4 methods = **4 planned rows**
- **Estimated API calls:** 4
- **Estimated cost:** < $0.01
- **Purpose:** Confirm end-to-end auth, endpoint, and response parsing work

### Plan B: 10-Example Smoke
- **Examples:** 10 × 4 methods = **40 planned rows**
- **Estimated API calls:** 40
- **Estimated cost:** < $0.05
- **Purpose:** Validate method scheduling, retry logic, and per-example record writing

---

## 7. Estimated Call Counts

| Plan | Examples | Methods | Rows | API Calls | Est. Cost |
|---|---|---|---|---|---|
| 1-example smoke | 1 | 4 | **4** | ~4 | < $0.01 |
| 10-example smoke | 10 | 4 | **40** | ~40 | < $0.05 |
| Full 1K auxiliary | 1,000 | 4 | **4,000** | ~4,000 | ~$1–5 |

---

## 8. Command to Use Only If User Explicitly Approves

**DO NOT run this without explicit approval.**

```bash
# Plan A — 1-example smoke (requires: AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_DEPLOYMENT)
UTC=$(date -u +"%Y%m%dT%H%M%SZ")
tmux new-session -d -s "azure_smoke_${UTC}" bash -lc "
set -euo pipefail
cd /home/soroush/frontier-allocation-for-budgeted-llm-inference
exec >\"outputs/azure_openai_smoke_${UTC}.log\" 2>&1
echo \"[start] \$(date -u +%Y-%m-%dT%H:%M:%SZ)\"
python3 scripts/run_cohere_real_model_cost_normalized_validation.py \
  --providers azure_openai \
  --azure-model \"\$AZURE_OPENAI_DEPLOYMENT\" \
  --datasets openai/gsm8k \
  --seeds 71 --budgets 6 \
  --methods direct_reserve_semantic_frontier_v2,external_l1_max,external_s1_budget_forcing,external_tale_prompt_budgeting \
  --target-scored-per-slice 1 --max-examples 1 \
  --exact-cases-jsonl outputs/mistral_large_router_training_gsm8k_20260524/mistral_gsm8k_train_1000_exact_cases.jsonl \
  --allowed-example-ids-file outputs/azure_openai_zero_cost_integration_20260524/azure_smoke_1_example_allowed_ids.jsonl \
  --api-retry-max-attempts 5 \
  --api-retry-base-delay-seconds 1.0 \
  --api-retry-backoff-multiplier 2.0 \
  --api-retry-max-delay-seconds 20.0 \
  --api-retry-jitter-seconds 0.5 \
  --max-recovery-passes 2 \
  --output-root \"outputs/azure_openai_smoke_${UTC}\"
echo \"[done] \$(date -u +%Y-%m-%dT%H:%M:%SZ)\"
"
```

**Or submit as the next query:**
> "Launch the 1-example Azure OpenAI smoke test in detached TMUX using the plans in `outputs/azure_openai_zero_cost_integration_20260524/azure_smoke_test_call_plans.json`."

---

## 9. Safety Confirmation

- No Azure API calls made.
- No Cohere/Mistral/Cerebras jobs touched or modified.
- Mistral GSM8K router training (tmux: `mistral_large_gsm8k_router_train_20260524T151853Z`) observed only.
- Cohere MATH-500 Scenario 4 (tmux: `cohere_math500_s4_official_20260524T144902Z`) observed only.
- Cerebras GSM8K (session `55`) observed only.
- No tmux sessions launched.
- No commit or push made.
- No secret values printed or logged anywhere.

---

## 10. Technical Design Notes

**Why `openai.OpenAI` with `base_url` instead of `AzureOpenAI`?**
The `AZURE_OPENAI_ENDPOINT` already contains `/openai/v1`. The `AzureOpenAI` SDK client appends `/openai/deployments/...` causing a double-prefix 404. Confirmed in the May 16 connectivity check. All existing Azure scripts in this repo use `openai.OpenAI(base_url=...)`.

**Why `max_tokens` not `max_completion_tokens`?**
`gpt-4.1-mini` (the default deployment) supports the standard `max_tokens` parameter. Only `gpt-5.4` (reasoning model) requires `max_completion_tokens`. Since all current plans use `gpt-4.1-mini`, `max_tokens` is correct. If `gpt-5.4` is needed later, a conditional in `_call_azure_chat_api()` can be added.

**`use_openai_api=True` for Azure:**
This flag controls whether `LLMVerifyProxyVerifier` (real LLM verify) or `SimulatedScorerVerifier` is used. Azure uses real LLM calls, so it belongs in the `{"openai", "mistral", "azure_openai"}` set.
