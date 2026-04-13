# Real API pilot notes (2026-04-13)

This note records the current plan for the first real-model pilot now that authenticated Hugging Face access is available and provider API keys have been tested in the execution environment.

## 1. Immediate purpose

The purpose of the real API pilot is to check whether the main simulator-side conclusions survive contact with actual model behavior.

The pilot should therefore be small, controlled, and diagnostic-heavy rather than broad.

## 2. Primary datasets currently usable

The currently verified HF-accessible datasets most relevant for the pilot are:
- `openai/gsm8k`
- `EleutherAI/hendrycks_math`
- `Idavidrein/gpqa`
- `Hothan/OlympiadBench`

A reasonable first pilot should start with GSM8K, then extend to MATH.

## 3. Primary methods to compare

The first real pilot should prioritize a small internal comparison set rather than a large benchmark zoo. A good initial comparison set is:
- `adaptive_relative_rank`
- `adaptive_score_plus_progress`
- the strongest current learned scorer available in the repo

The goal is not to declare a final winner yet, but to detect whether simulator-side rank orderings survive on real APIs.

## 4. Provider strategy

Provider choice should be configurable. A good immediate plan is:
- OpenAI provider run
- Gemini provider run

The same dataset subset and branch budget should be used across providers where possible.

## 5. Diagnostics to track

The real pilot should not rely on final accuracy alone. Useful internal diagnostics include:
- branch diversity / collapse,
- verifier or branch-score variance,
- semantic redundancy of explored branches,
- budget usage pattern over the trajectory,
- and cross-provider differences in these quantities.

## 6. Calibration caution

Cross-provider raw scores should not be assumed comparable by default. If score scales differ materially across providers, calibration or at least provider-specific normalization may be needed before strong conclusions are drawn.

## 7. Safe interpretation rule

A simulator-side result should not be treated as strongly established unless a small real-model pilot gives at least directionally similar behavior.

## 8. Near-term objective

The near-term objective is not yet to optimize every part of the controller, but to answer:

> Does the current branch-allocation logic retain any useful signal under real OpenAI / Gemini branch generation?

## 9. Status

This note is a planning memo and should be revised after the first real-provider pilot is executed.