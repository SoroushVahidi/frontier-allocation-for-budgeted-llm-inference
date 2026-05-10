# External-only wins (5 cases)

- `openai_gsm8k_125`: external correct (`32`), PAL wrong (`1`). Cause: PAL produced no usable code. Fixability: Likely fixable via PAL prompt/selection tuning.
- `openai_gsm8k_127`: external correct (`6`), PAL wrong (`0.8`). Cause: PAL execution failed. Fixability: Likely fixable via PAL prompt/selection tuning.
- `openai_gsm8k_31`: external correct (`12`), PAL wrong (`6`). Cause: PAL produced no usable code. Fixability: Likely fixable via PAL prompt/selection tuning.
- `openai_gsm8k_81`: external correct (`750`), PAL wrong (`1000`). Cause: PAL had gold in tree but final selection missed. Fixability: Likely fixable via PAL prompt/selection tuning.
- `openai_gsm8k_95`: external correct (`6`), PAL wrong (`1`). Cause: PAL code blocked by safety rules. Fixability: Likely fixable via PAL prompt/selection tuning.
