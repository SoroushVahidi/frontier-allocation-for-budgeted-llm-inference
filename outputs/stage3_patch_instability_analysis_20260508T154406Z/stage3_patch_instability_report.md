# Stage-3 Patch Instability Report

- Checkpoint mixed result: 1078 stayed fixed, 1198 regressed, 1155 improved to exact.
- 1198 instability diagnosis: `prompt_drift`; likely caused by prompt drift between micro and checkpoint templates.
- 1155 improvement likely from stricter final-target framing in checkpoint prompt; promote to candidate patch case with caution.
- Recommended action: freeze known-good 1198 micro prompt and use best-of-two fallback for 1198 only.
- Patch is not yet stable enough for 50-case rerun; run a narrow follow-up first.

## Caveats
- Offline forensic diagnosis only; no API calls were made in this step.
- Conclusions are based on very small sample sizes (3 cases).