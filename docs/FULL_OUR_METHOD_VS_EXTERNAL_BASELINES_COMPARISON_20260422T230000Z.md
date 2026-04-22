# Full our-method vs external baselines comparison (20260422T230000Z)

- Canonical our method: `strict_f3`.
- Strongest external baseline on full matched surface: `external_l1_max`.
- Our mean accuracy: 0.658333.
- Strongest external mean accuracy: 0.497222.
- Gap (our - strongest external): 0.161111.

## Baseline taxonomy and comparability
- near_direct rows are ranked on canonical matched surface.
- adjacent rows are preserved separately and not merged into direct claim space.
- discuss_only rows are explicitly excluded with reasons.
- unofficial caveated adapters remain in their own trust bucket.

## Loss-analysis note
- Requested 100 strict losses, but canonical matched surface provides 56 strict losses.
- This bundle includes all 56 available strict losses without fabricating extra rows.