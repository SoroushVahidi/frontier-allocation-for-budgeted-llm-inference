# Case 1198 Instability Audit

- Successful micro-pilot variant: `final_target_extraction_repair`
- Failed patch-checkpoint variant: `final_target_extraction_repair`
- Micro parsed answer: `2`; exact=1
- Checkpoint parsed answer: `4`; exact=0

## Prompt Diff
```
--- micro:openai_gsm8k_1198_final_target_extraction_repair.txt
+++ checkpoint:openai_gsm8k_1198_final_target_extraction_repair.txt
@@ -1,15 +1,16 @@
-Solve the math word problem carefully.
+Solve the math word problem with strict final-target extraction.
 
 Problem:
 A teacher uses a five-inch piece of chalk to write math equations on a chalkboard for his students. The teacher likes to conserve chalk, so he tries to only use twenty% of the chalk each day. Since the teacher cannot write with a very small piece of chalk, he recycles the chalk when it is smaller than two inches. On Monday the teacher used a new piece of chalk. His students need extra help that day, so he ended up writing more than usual. He used up forty-five% of the chalk by the end of the day. If the teacher goes back to using only twenty% of the chalk each day, how many days does he have before he has to recyc …<truncated fourteen chars>
 
 Instructions:
 - Restate exactly what final quantity is asked.
-- Identify target type: total, difference, remaining, rate, ratio part, or specific entity value.
-- Use minimal equations.
-- Give one final numeric answer.
+- Classify target type as one of: total, difference, remaining, rate, ratio part, or specific entity value.
+- Use only minimal equations needed to compute that target.
+- Verify the computed value matches the asked target (not an intermediate value).
+- Provide the final answer exactly once.
 
-Output:
-- target_type: ...
-- equations: ...
-- final_answer: ...
+Output format:
+- target_type: <one short phrase>
+- equations: <minimal equations>
+- final_answer: <single numeric answer>
```

## Response Summary
- Successful run: **Restated Final Quantity Asked:** How many days does the teacher have before he has to recycle the chalk? **Target Type:** Remaining (number of days until the chalk is smaller than 2 inches). **Equations:** 1. Chalk remaining after Monday: \( 5 \, \text{inches} \times (1 - 0.45) = 5 \times 0.55 = 2.75 \, \text{inches} \) 2. Daily usage: \( 20\% \) of remain...
- Failed run: **target_type:** remaining **equations:** 1. Initial chalk length: \( L_0 = 5 \) inches 2. Chalk used on Monday: \( 0.45 \times 5 = 2.25 \) inches 3. Remaining chalk after Monday: \( 5 - 2.25 = 2.75 \) inches 4. Daily usage after Monday: \( 0.2 \times \text{remaining chalk} \) 5. Find the number of days \( d \) until remaining chalk < 2 inches: \( 2.75 \time...

- Likely reason for instability: `prompt_drift`
- Recommended fix: `freeze_successful_micro_pilot_prompt`