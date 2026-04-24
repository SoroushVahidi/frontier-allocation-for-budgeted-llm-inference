# Real-model ours-vs-external validation summary

## Headline framing
- Headline question: frontier-allocation family (strict_f3/strict_gate1_cap_k6/strict_f2) vs external adaptive-compute adapters under shared API-backed substrate.
- Internal ordering among ours variants is treated as surface-sensitive and non-headline.

## Provider status
- OpenAI: attempted=True completed=False reason=dry_run_no_api_calls
- Cohere: attempted=True completed=False reason=dry_run_no_api_calls

## Did ours beat strongest external?
- OpenAI gap (best ours - best external): +0.0000
- Cohere gap (best ours - best external): +0.0000
- Combined gap (across available providers): +0.0000

## Error and failure profile
- OpenAI API/runtime error rows: 0
- Cohere API/runtime error rows: 0
- Failure decomposition for best ours/external is in combined_failure_decomposition.csv.

## Claim safety
- openai: not safe (gap=+0.0000, rows=0)

## Conservative manuscript conclusion
- The real-model validation tests whether the proposed frontier-allocation family, represented by strict_f3/strict_gate1_cap_k6/strict_f2, improves over near-direct external adaptive-compute adapter baselines under a shared API-backed substrate.
- Internal variant ordering is treated as surface-sensitive and is not the headline claim.

## Cross-provider note
- If Cohere is incomplete/unsupported, cross-provider validation remains open and OpenAI-only evidence is bounded.
