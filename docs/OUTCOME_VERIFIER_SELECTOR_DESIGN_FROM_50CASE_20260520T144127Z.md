# Outcome verifier selector design

- Input: question, candidate answer, optional trace snippet.
- Candidate grouping: normalized answer groups with support/source-family features.
- Score output: probability candidate is correct in [0,1].
- Selection: keep DR default; override only if verifier margin >= m and challenger not flagged high-risk.
- Logging: per-candidate score, margin, selected answer, blocked reasons, override flag.
- Offline eval: replay compact artifact with mock scores; report accuracy/fixes/breaks/net/overrides.
