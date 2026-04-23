# MATCHED SURFACE MULTI-SEED MAIN COMPARISON (20260423T235900Z)

## Purpose
Run a materially stronger multi-seed rerun of the manuscript-facing matched-surface main comparison to stress-test winner stability and uncertainty.

## Exact matched surface used
- Canonical surface contract: `canonical_full_method_ranking_20260421T212948Z`
- Strict rerun status: yes (same datasets, budgets, matched protocol, and simulation substrate; only seed count expanded).

## Methods included
- Requested: strict_f3, strict_gate1_cap_k6, strict_f2, l1_max, tale, s1, l1_exact, zhai_cpo_mode_a
- Runnable: strict_f3, strict_gate1_cap_k6, strict_f2, l1_max, tale, s1, l1_exact, zhai_cpo_mode_a
- Blocked: none

## Seed list used
- [11, 23, 37, 41, 53, 67]

## Datasets and budgets
- Datasets: ['openai/gsm8k', 'HuggingFaceH4/MATH-500', 'HuggingFaceH4/aime_2024']
- Budgets: [4, 6, 8]

## Main findings (plain language)
- Winner by mean accuracy: `strict_f3`.
- strict_f3 mean accuracy: 0.6213 (std 0.0315, CI95 [0.5961, 0.6465]).
- strict_gate1_cap_k6 mean accuracy: 0.6167 (std 0.0310, CI95 [0.5918, 0.6415]).
- l1_max mean accuracy: 0.4843 (std 0.0725, CI95 [0.4263, 0.5422]).
- strict_f3 minus strict_gate1_cap_k6 mean gap: +0.0046.
- strict_f3 minus l1_max mean gap: +0.1370.

## Uncertainty and significance
- strict_f3 vs strict_gate1_cap_k6 paired permutation p-value: 0.9040959040959041.
- strict_f3 vs l1_max paired permutation p-value: 0.03796203796203796.

## Honest interpretation for paper-writing
- Assessment: **mixed / fragile support**.
- This conclusion is bounded to the matched manuscript-facing surface and should not be generalized beyond it.

## Artifact bundle
- `outputs/matched_surface_multiseed_main_comparison_20260423T235900Z/`
