# Azure OpenAI Provider Integration Audit

> Created: 2026-05-24T15:35:00Z | Read-only audit. No API calls made. No jobs launched.

---

## 1. Is Azure Already Supported?

**NO** — Azure OpenAI is **not** supported in the main validation runner (`run_cohere_real_model_cost_normalized_validation.py`).

The runner has a hard provider allowlist at line 515:

```python
allowed = {"cohere", "openai", "cerebras", "mistral"}
```

`azure_openai` is not in this set. Any attempt to pass `--providers azure_openai` raises `ValueError`.

Azure IS already supported in two **other** scripts:
- `scripts/run_relation_verifier_azure_labeler.py` — uses `openai.OpenAI(base_url=AZURE_ENDPOINT)` for relation-verification labeling
- `scripts/build_relation_verifier_provider_payloads.py` — lists `azure_openai` in `SUPPORTED_PROVIDERS`

These scripts handle Azure correctly but are separate from the fixed-pool validation runner.

---

## 2. Environment Variables — Current Status

All required Azure env vars are **PRESENT** (boolean check only, no values printed):

| Variable | Status | Notes |
|---|---|---|
| `AZURE_OPENAI_API_KEY` | **PRESENT** | Primary auth key |
| `AZURE_OPENAI_ENDPOINT` | **PRESENT** | Full v1-compat URL including `/openai/v1` path |
| `AZURE_OPENAI_DEPLOYMENT` | **PRESENT** | `gpt-4.1-mini` (confirmed from May 16 report) |
| `AZURE_OPENAI_API_VERSION` | **PRESENT** | `2024-10-21` — not needed for v1-compat endpoint |
| `AZURE_OPENAI_STRONG_DEPLOYMENT` | **PRESENT** | `gpt-5.4` — reasoning-class model |

**Connectivity was already confirmed working** (2026-05-16):
- `gpt-4.1-mini`: tested with `openai.OpenAI(api_key=..., base_url=...)` → `"AZURE_OK"` ✓
- `gpt-5.4`: tested similarly → `"STRONG_AZURE_OK"` ✓

**Critical endpoint note:** The `AZURE_OPENAI_ENDPOINT` already contains `/openai/v1`. Using `openai.AzureOpenAI` causes 404 (double-prefixes the path). The correct pattern is `openai.OpenAI` with `base_url` — exactly how `run_relation_verifier_azure_labeler.py` does it.

---

## 3. Which Files Need Changes

### 3.1 `experiments/branching.py` — 3 edit blocks

**a) `APIBranchGenerator.__init__()` (line ~277–291) — add Azure `default_base_url`:**

```python
# After the groq case:
elif self.provider in {"azure_openai", "azure"}:
    default_base_url = os.environ.get("AZURE_OPENAI_ENDPOINT", "https://api.openai.com/v1")
```

**b) `_call_api()` (line ~453–465) — add Azure routing:**

```python
if self.provider in {"azure_openai", "azure"}:
    return self._call_azure_chat_api(prompt)
```

Currently, unknown providers fall through to `_call_responses_api()` which hits `/responses` (OpenAI Responses API). Azure exposes `/chat/completions` only — the fallthrough would 404.

**c) New `_call_azure_chat_api()` method** — modelled after `_call_mistral_chat_api()`:

```python
def _call_azure_chat_api(self, prompt: str) -> str:
    headers = {"Content-Type": "application/json"}
    if self.api_key:
        headers["Authorization"] = f"Bearer {self.api_key}"
    payload = {
        "model": self.model,  # deployment name
        "messages": [
            {"role": "system", "content": "Return only valid JSON matching the requested schema."},
            {"role": "user", "content": prompt},
        ],
        "temperature": self.temperature,
        "max_tokens": self.max_tokens,
    }
    # ... same retry logic as _call_mistral_chat_api ...
    # Hits f"{self.base_url}/chat/completions"
```

### 3.2 `experiments/frontier_matrix_core.py` — 1 edit block

**`resolve_api_key_for_provider()` (line ~80–94):**

```python
if p in {"azure_openai", "azure"}:
    return os.getenv("AZURE_OPENAI_API_KEY")
```

### 3.3 `scripts/run_cohere_real_model_cost_normalized_validation.py` — 5 edit blocks

**a) Provider allowlist (line 515):**
```python
allowed = {"cohere", "openai", "cerebras", "mistral", "azure_openai"}
```

**b) Argparse — add `--azure-model` flag:**
```python
p.add_argument("--azure-model", default=os.getenv("AZURE_OPENAI_DEPLOYMENT", ""))
```

**c) `model_by_provider` dict (line ~1264):**
```python
"azure_openai": args.azure_model,
```

**d) `api_keys` dict (line ~1314):**
```python
"azure_openai": os.getenv("AZURE_OPENAI_API_KEY", ""),
```

**e) Readiness check (line ~1276) — add Azure branch:**
```python
elif provider == "azure_openai":
    ok = bool(os.getenv("AZURE_OPENAI_API_KEY")) and bool(os.getenv("AZURE_OPENAI_ENDPOINT"))
    reason = "azure_openai_key_and_endpoint_present" if ok else "azure_openai_env_vars_missing"
```

**f) `use_openai_api` flag (line ~1422):**
```python
use_openai_api=(provider in {"openai", "mistral", "azure_openai"}),
```

This ensures `LLMVerifyProxyVerifier` (real verifier) is used instead of `SimulatedScorerVerifier`.

**g) `factory()` lambda — pass `base_url` for Azure:**
```python
APIBranchGenerator(
    provider=provider,
    api_key=api_keys[provider],
    model=model_by_provider[provider],
    base_url=(os.getenv("AZURE_OPENAI_ENDPOINT") if provider == "azure_openai" else None),
    ...
)
```

**Total: ~3 files, ~8 edit blocks, ~20 lines net new code.**

---

## 4. Suggested Provider Name

`azure_openai` — already used by relation-verifier infrastructure and consistent with the `build_relation_verifier_provider_payloads.py` convention.

---

## 5. Required Environment Variables

| Variable | Required | Notes |
|---|---|---|
| `AZURE_OPENAI_API_KEY` | **Yes** | Auth key |
| `AZURE_OPENAI_ENDPOINT` | **Yes** | Full URL including `/openai/v1` |
| `AZURE_OPENAI_DEPLOYMENT` | **Yes** | Deployment/model name (`gpt-4.1-mini` or `gpt-5.4`) |
| `AZURE_OPENAI_API_VERSION` | No | Not needed for v1-compat endpoint |

---

## 6. Minimal Smoke-Test Plan (No API Calls Yet)

Once the 3-file patch is applied:

```bash
# 1. Dry-run — zero API calls, validates method scheduling and allowlist:
python3 scripts/run_cohere_real_model_cost_normalized_validation.py \
  --providers azure_openai \
  --azure-model "$AZURE_OPENAI_DEPLOYMENT" \
  --datasets openai/gsm8k \
  --seeds 71 --budgets 6 \
  --methods direct_reserve_semantic_frontier_v2,external_l1_max,external_s1_budget_forcing,external_tale_prompt_budgeting \
  --target-scored-per-slice 10 --max-examples 10 \
  --dry-run-call-plan

# 2. Live smoke run — 10 examples, 4 methods = 40 rows, in TMUX:
tmux new-session -d -s azure_smoke_20260524 bash -c "
python3 scripts/run_cohere_real_model_cost_normalized_validation.py \
  --providers azure_openai \
  --azure-model \"\$AZURE_OPENAI_DEPLOYMENT\" \
  --datasets openai/gsm8k --seeds 71 --budgets 6 \
  --methods direct_reserve_semantic_frontier_v2,external_l1_max,external_s1_budget_forcing,external_tale_prompt_budgeting \
  --target-scored-per-slice 10 --max-examples 10 \
  --output-root outputs/azure_openai_smoke_20260524 \
  > outputs/azure_openai_smoke_20260524.log 2>&1
"
```

**Expected: 10 examples × 4 methods = 40 rows, ~$0.01–$0.05 in Azure compute credits.**

---

## 7. Estimated Risks

| Risk | Severity | Mitigation |
|---|---|---|
| `gpt-5.4` uses `max_completion_tokens` not `max_tokens` | **High** for strong deployment | Use `gpt-4.1-mini` (standard deployment) for initial runs; add conditional parameter name for reasoning models |
| Azure rate limits differ from OpenAI | Medium | Start with 10-example smoke run; set conservative retry delays (already at 1.0s base, 2.0× multiplier) |
| Endpoint `/openai/v1` path — double-prefix with `AzureOpenAI` client | **Critical** | Already handled: use `openai.OpenAI` with `base_url`, not `AzureOpenAI` |
| Deployment name ≠ model family name | Low | Pass deployment name as `--azure-model`; runner uses it as the `model` field |
| Cost ambiguity (tokens × Azure pricing) | Low | Azure `gpt-4.1-mini` costs are similar to OpenAI; monitor token usage |
| `_call_responses_api()` fallthrough path hits wrong endpoint | **Critical** | Must add explicit `_call_azure_chat_api()` before any live run |

---

## 8. Recommended Use Order: Official Scenario vs Auxiliary Training

**Recommended: Use auxiliary router-training data first.**

Rationale:
1. Azure has not been validated in the main runner at all — any bugs (wrong endpoint, wrong payload format, `max_tokens` issue) are best caught on cheap auxiliary data
2. Official scenario results must be reproducible and auditable — introducing an untested provider path risks silent failures
3. The Mistral large router training (1,000 examples) is already running; Azure could be used for a **second 1,000-example auxiliary corpus** (different provider, different regime characteristics) at low cost
4. A 10-example smoke run + 100-example validation + 1,000-example auxiliary run provides three checkpoints before any official scenario

**Recommended sequence:**
1. Apply 3-file patch
2. Dry-run validation (0 API calls)
3. 10-example smoke run in TMUX
4. If successful: 100-example validation (same GSM8K train split, seed=11)
5. If successful: 1,000-example auxiliary corpus (seed=71)
6. Only then: consider official provider×dataset scenario

---

## 9. Recommended Next Step

If the audit looks feasible (it does — env vars present, connectivity confirmed, patch is small and localized):

> **Next query:** "Implement the Azure OpenAI provider patch across the 3 files described in the audit, validate with dry-run, and launch a 10-example smoke test in detached TMUX."

The patch is mechanical and low-risk. The `_call_azure_chat_api()` method is a near-copy of `_call_mistral_chat_api()` with the same retry logic and `/chat/completions` endpoint. The `gpt-4.1-mini` deployment avoids the `max_completion_tokens` complication (that only applies to `gpt-5.4`).

---

## 10. Files Created

- `docs/AZURE_PROVIDER_INTEGRATION_AUDIT_20260524.md` — this report
- `outputs/azure_provider_integration_audit_20260524/audit_findings.json` — structured findings

## 11. Safety Confirmation

- No API calls made.
- No tmux sessions launched or attached.
- No active jobs modified.
- No files committed or pushed.
- Azure env var presence checked (boolean only — no values printed or logged).
