# Call accounting calibration report

- Planned rows undercount logical calls because each method row can execute multiple internal generation/verification actions.
- Most expensive observed methods: Self-Consistency variants (especially SC-6).
- Observed one-case total for all six methods: 19 calls (near 20-call smoke cap).
- Recommended next checkpoint: 5-case budget-4-first run with core four methods under ~100 call cap.
- Claim supported by that checkpoint: stable live execution and calibrated call accounting on multi-case sample; not final quality ranking.
- Scale to 50/245 only after a successful 5-case then 10-case calibration pass confirms projection error is acceptable.
- Caveat: projections are linear from a single case and may be biased by case-specific reasoning depth.
