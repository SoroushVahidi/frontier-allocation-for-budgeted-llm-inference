# Fast selector execution policy

This policy is intended to prevent slow, expensive, or circular selector work.

## Current selector goal

The immediate selector goal is not to add more heuristic selectors. It is to test an outcome-verifier-style selector over existing DR-v2 candidate groups.

The selector should estimate:

```text
score(question, candidate answer, optional reasoning trace)
  -> probability that the candidate answer is correct
```

Then it should choose the best candidate answer, preferably with a margin or fallback that avoids unsafe overrides.

## Current active artifact

Use the compact 50-case tournament artifact for offline selector development:

```text
outputs/selector_tournament_compact_export_20260430T_SELECTOR_TOURNAMENT_50CASE_COHERE/
```

Associated real run:

```text
outputs/cohere_real_model_cost_normalized_validation_20260430T_SELECTOR_TOURNAMENT_50CASE_COHERE/
```

## Current known evidence

| Method / diagnostic | Accuracy |
|---|---:|
| `external_l1_max` | 0.72 |
| current DR-v2 | 0.64 |
| best deployable heuristic selector | 0.66 |
| oracle selector ceiling | 0.84 |

Heuristic selector behavior:

- fixes: 5
- breaks: 4
- net fixes-minus-breaks: +1
- overrides: 17
- override precision: 0.2941

Conclusion: heuristic selectors are too noisy for runtime promotion.

## Rules for future selector work

1. **No paid calls before dry-run accounting.**
   - Report number of examples.
   - Report number of candidate groups to score.
   - Report estimated verifier calls.
   - Report estimated cost if possible.

2. **Never regenerate answers for selector testing unless explicitly required.**
   - Selector experiments should score existing candidate groups.
   - Reuse compact artifacts whenever possible.

3. **Cache every verifier score.**
   - The cache key should include at least question id, normalized candidate answer, reasoning snippet/hash if used, verifier model, and prompt version.
   - Do not rescore cached candidate groups.

4. **One selector experiment should produce a complete decision table.**
   Required comparison:
   - current DR-v2,
   - best heuristic selector,
   - outcome-verifier selector,
   - `external_l1_max`,
   - oracle selector ceiling.

5. **No runtime promotion without evidence.**
   A selector can be promoted only if it improves offline with acceptable fixes/breaks and then survives a focused paid validation.

6. **No broad artifact archaeology.**
   Use the active compact artifact unless a specific blocker requires another artifact.

7. **After any paid run, immediately export a compact artifact.**
   Run:
   - compact export,
   - selector tournament,
   - core diagnostics,
   before moving to the next method idea.

## What not to do

- Do not run broad multi-dataset sweeps for selector debugging.
- Do not add more support-only variants before testing the outcome-verifier selector.
- Do not use gold answers, correctness labels, L1 answers, or oracle outputs in deployable selector decisions.
- Do not claim a selector beats L1 from one diagnostic slice.
- Do not leave paid run artifacts unexported or non-portable.

## Current next selector task

Implement and test a cached outcome-verifier selector scaffold:

1. Read candidate groups from the compact 50-case artifact.
2. Dry-run call count.
3. Score candidate groups only if explicitly authorized.
4. Cache scores.
5. Evaluate margin-based verifier selection offline.
6. Report fixes, breaks, net gain, override precision, and gap to L1/oracle.
