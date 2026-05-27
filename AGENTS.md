# Agent Instructions

## Safety rules (always enforced)

- **No paid API calls** (OpenAI, Cohere, Mistral, Fireworks, Cerebras, Azure, Cloudrift, etc.) without explicit per-call user authorization.
- **No deletion of outputs** in `outputs/`. Do not move, rename, or overwrite existing artifacts.
- **No staging, committing, or pushing** unless explicitly requested for this specific action.
- **No printing of secrets**, API keys, tokens, .env contents, credentials, or auth headers.
- **No modification of .env**, credentials, key files, or external service configs.
- **No row-wise max correctness as a baseline.** Use corrected fixed-policy baselines only.
- **Oracle is upper bound only**, never a baseline.
- **Gold/correctness labels** may be used only for offline evaluation, never as runtime features.
- **D6 bucket labels** (rescue/regression-check) are diagnostic stratification labels only — must not appear as runtime selector features.
- **Long jobs (>1 min)** must run in tmux.

## Verification rule

Never claim a job is complete from plans, assumptions, or conceptual updates alone. Status must be based only on real evidence: real file counts, real JSONL rows, real tmux status, real logs, real evaluation outputs.

## Current evidence hierarchy (2026-05-27)

1. **FTA / FIX-2+FIX-4 (Failure-Trace Allocator)** — canonical main result
   - Final-300: 86.67% (260/300, seed=71, Cohere × GSM8K, budget=6) — verified
   - Aggregate-720: 80.69% (581/720, seeds 41+61+71) — verified
   - Gate: FIX-2=63, FIX-4=3, no-gate=234; FIX-4 causes 0 regressions
   - Leakage audit: PASS; 0 post-generation model calls
   - **Required disclosures:** CI vs pooled ensemble includes zero; full pool=24 calls; GSM8K only

2. **D9 gated selector** — supporting multi-provider evidence
   - CV 50.18%±2.52% vs frontier 34.36% (+15.82pp); 550 D6 pools; 3 providers; 0 false overrides
   - D6 standalone is negative (net=-38); D9 gate is required for positive outcome
   - Verdict: D9_MISTRAL_RETRAIN_USE_D6_AS_GATED_MODULE

3. **D6 frontier expansion** — diagnostic risky, NOT standalone headline
   - Adds unique-correct answers in rescue scenarios; causes regressions in regression-check scenarios
   - Must not be presented as a standalone positive result

4. **Cloudrift/Qwen extraction** — engineering insight
   - Lenient extraction 98.8%; prompt fix needed before new generation

## No-overclaim rules

- Do NOT claim FTA beats the pooled ensemble statistically (CI includes zero — must disclose)
- Do NOT claim FTA works on MATH-500 or any benchmark other than Cohere × GSM8K
- Do NOT claim D8.1 selector results are independent held-out end-to-end accuracy
- Do NOT use seed=61 (59.17%) as representative of typical FTA accuracy
- Do NOT claim D6 standalone net gain is positive

## Current priority

**Paper finalization — no API calls needed.** Use FTA as the canonical main result; D9 as supporting multi-provider evidence; D6 as context/motivation. State all four required disclosures in paper.

Secondary (after paper draft):
- Fix Cloudrift/Qwen prompt before new generation
- Optional: D9 refresh with repaired Cloudrift extraction

## Canonical docs

- `docs/CURRENT_CANONICAL_STATE_20260527.md` — primary reference
- `docs/LATEST_RESULTS_AND_CLAIMS.md` — full results and claim boundaries
- `experiments/support_aware_selector.py` — FTA implementation
- `outputs/fta_independent_verification_20260527/run_20260527T003000Z/` — verification artifacts
