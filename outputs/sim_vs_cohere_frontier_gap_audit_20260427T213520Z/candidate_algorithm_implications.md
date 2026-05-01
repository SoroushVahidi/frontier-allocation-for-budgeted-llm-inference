# Candidate algorithm implications

- Real Cohere losses split across semantic-seeding, maturation, and selection failures, with trace-unavailable residual.
- Hard depth-2/3 coverage alone does not guarantee semantic-family diversity; redundancy remains measurable where trace exists.
- Evidence supports introducing semantic-family aware maturation guarantees before pure score-based allocation.
- Preserve direct incumbent (`external_l1_max`-like) as guarded fallback while challenger frontier searches.
