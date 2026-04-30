# Selector transfer from -adaptive-llm-inference (2026-04-29)

Transferred ideas (adapted for selector diagnostics only):
- Oracle ceiling evaluation pattern over existing candidate pools (diagnostic-only).
- Candidate consistency checks inspired by policy v6/v7 sanity guards.
- Unified confidence/error scoring pattern inspired by unified error signal.
- Policy-catalog style documentation discipline for selector methods.

Intentionally not transferred:
- Binary route/revise policies (adaptive v6/v7 as runtime methods).
- Any generation-time or exploration-time routing control.
- Old cost-routing claims/thresholds.

Why:
- Current track is L1-defeat via answer selection fidelity, not route/revise control.
- We need offline, artifact-backed diagnostics first.

Diagnostic-only note:
- `oracle_answer_selector` is non-deployable and uses gold only for analysis.
