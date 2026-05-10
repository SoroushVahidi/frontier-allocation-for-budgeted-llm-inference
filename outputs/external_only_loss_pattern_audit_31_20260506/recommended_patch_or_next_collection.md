# Recommended patch or next collection

- Recommended next step: **B. add retry-on-empty-code**
- Prompt/executor/selection/retry-fixable: 21/31 (67.7%)
- Enough to choose patch now: yes
- More API collection needed before patching: no
- Exact patch target and why: Implement retry when PAL seed runs but pal_code_present==0: force one constrained regeneration requiring executable code and explicit final answer print.
