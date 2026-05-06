# Recommended next step

**Recommendation: E — analyze failures more deeply (no API).**

Rationale:
- The **300-case** paired outcome is numerically favorable for PAL+retry (+2.67 pp) but **not statistically decisive** on discordants (McNemar-style exact \(p \approx 0.32\); bootstrap paired-diff CI crosses 0).
- Another 300–1000 paired cases would **narrow intervals** but is unlikely to resolve mechanistic questions (selection vs discovery vs arithmetic brittleness) without offline inspection.
- Highest leverage is structured triage of `external_only_correct`, `pal_only_correct`, and `both_wrong` buckets using existing JSONL + casebook fields.

API should remain **paused until explicit approval** after that review (or after a tightly scoped protocol change).
