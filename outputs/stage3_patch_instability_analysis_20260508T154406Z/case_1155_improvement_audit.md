# Case 1155 Improvement Audit

- Prior micro-pilot status: parsed `162` vs gold `342` (exact=0).
- Patch-checkpoint variant: `final_target_extraction_repair`
- Patch-checkpoint parsed answer: `342` vs gold `342` (exact=1).

## Response Summary
- Earlier run summary: **Problem Restatement:** How much money will Pat spend at the store to fill up her flower bed? **Target Type:** Total (total cost of additional plants needed). **Equations:** 1. **Total space per plant (including spacing):** \( 1.5 \, \text{feet} + 1 \, \text{foot} = 2.5 \, \text{feet} \) (Note: 12 inches = 1 foot, so each plant occupies 1 foot of space.) 2....
- Checkpoint run summary: **target_type:** total **equations:** 1. **Spacing per plant:** 1.5 feet (given). 2. **Total length of flower bed:** 111 feet. 3. **Number of plants that fit:** \( \frac{111}{1.5} = 74 \) plants. 4. **Plants needed to buy:** \( 74 - 17 = 57 \) plants. 5. **Total cost:** \( 57 \times 6 = 342 \) dollars. **final_answer:** 342

- What changed: likely `prompt_drift_reduced_target_misread`
- Include 1155 as patch case now: `yes`
- Risk: `medium`