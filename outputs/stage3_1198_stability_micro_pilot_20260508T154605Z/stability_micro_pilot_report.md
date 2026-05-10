# 1198 Stability Micro Pilot

- Tested 2 variants for openai_gsm8k_1198: frozen known-good + fallback.
- Actual calls: 2; exact variants: 2/2.
- Frozen prompt exact: True; fallback exact: True.

## Decision
- 1198 patch stability signal: sufficient.
- Stage-3 50-case rerun justified now: yes.

## Caveats
- Single-case micro-pilot; still requires caution when scaling.