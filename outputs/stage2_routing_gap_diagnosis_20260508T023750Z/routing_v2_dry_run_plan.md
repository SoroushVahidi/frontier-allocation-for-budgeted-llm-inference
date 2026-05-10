# Routing v2 dry-run plan

- Candidate pilot size: 14 (all 7 external_l1-only + all 7 both-wrong diagnosed cases).
- Call cap for next live step: <=14 Cohere calls (1 per case).
- Reuse existing prompts where possible; add new scaffold templates only for uncovered patterns.
- Success metrics:
  - rescue external_l1-only losses,
  - reduce both-wrong count,
  - no gold leakage in prompts,
  - no parsing/API errors.
- Suggested sequence:
  1) run capped routing-v2 live pilot on these 14 cases,
  2) compare against stage2 baseline/external outcomes,
  3) expand only if discordant trend improves.
