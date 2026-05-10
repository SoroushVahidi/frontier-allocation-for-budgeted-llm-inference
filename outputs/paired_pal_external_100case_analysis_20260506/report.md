# Paired PAL vs external (100-case) analysis

- Output path: outputs/paired_pal_external_100case_analysis_20260506
- Statistical conclusion: PAL is competitive and directionally better on this sample, but not yet definitive for superiority.
- P-value (discordant exact/sign): 0.3018
- Wilson 95% CI external: 65.70% to 82.45%
- Wilson 95% CI PAL: 71.12% to 86.66%
- Bootstrap 95% CI (PAL-external): -2.00% to 13.00%

## Top PAL failure patterns (20 PAL-wrong)

- A.external_also_wrong: 15
- B.code_absent: 2
- D.exec_failed: 1
- E.exec_succeeded_wrong: 1
- C.unsafe_code: 1

## External-only vs PAL-only insight

- external_only_correct: 5
- pal_only_correct: 10
- Net discordant edge favors PAL (+5), but with limited statistical strength at n=100.

## Exact recommended next action

- C. analyze/patch the 20 PAL failures first

## API status

- Keep API paused until explicit approval after PAL failure patch plan and no-API regression pass.
