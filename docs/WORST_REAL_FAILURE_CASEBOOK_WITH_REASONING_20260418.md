# WORST REAL FAILURE CASEBOOK WITH REASONING (2026-04-18)

- Run ID: `worst_real_failure_observability_20260418T022231Z`
- Selected worst failures: `5`
- Canonical framing: fixed-budget branch allocation for next-step compute.

## Recoverability summary
- Direct reasoning recovery (method+oracle): 5/5
- Direct final-answer recovery (method+oracle): 5/5

## Case 1: `s_ep2_d3_r2_229775698cc45b671f2e`
- dataset/example: `openai/gsm8k` / `openai_gsm8k_2`
- method: `adaptive_learned_branch_score_v3` chose `b1`; oracle-best `b2`
- oracle_regret=0.007620, method_margin_top2=0.120000, hard_slice=near_tie
- Full problem: Sam sells bread. He has a target of selling 120 crates of bread in a week. One week he was closed on Monday and Friday. Over the weekend he sold 20 crates. On Tuesday he sold 15 crates, on Wednesday 12 crates, and Thursday 18 crates. By how many crates was Sam off from his target for the week?
- Ground truth answer: `55`
- Method branch final answer text (direct-or-recovered): `120`
- Oracle branch final answer text (direct-or-recovered): `65`
- Method normalized answer: `120`
- Oracle normalized answer: `65`
- Method reasoning text (direct): Calculate total crates sold from Tuesday to Thursday and the weekend: 15 + 12 + 18 + 20 = 65 crates.
Calculate how many crates Sam was off from his target by subtracting total crates sold (65) from the target (120).
- Oracle reasoning text (direct): Calculate total crates sold: 20 (weekend) + 15 (Tuesday) + 12 (Wednesday) + 18 (Thursday) = 65 crates.
- Method extracted numbers: `[15.0, 12.0, 18.0, 20.0, 65.0, 65.0, 120.0]`
- Oracle extracted numbers: `[20.0, 15.0, 12.0, 18.0, 65.0]`
- Divergence: method selected `b1` under higher learned margin while oracle rollout target preferred `b2` with higher expected value.
- Design lesson: penalize high-confidence selection when branch-level answer evidence is weak or lagging against oracle-immediate value.

## Case 2: `s_ep2_d0_r5_fe63a77683a39d50ccbe`
- dataset/example: `openai/gsm8k` / `openai_gsm8k_2`
- method: `adaptive_learned_branch_score_v3` chose `b0`; oracle-best `b2`
- oracle_regret=0.038084, method_margin_top2=0.000000, hard_slice=near_tie
- Full problem: Sam sells bread. He has a target of selling 120 crates of bread in a week. One week he was closed on Monday and Friday. Over the weekend he sold 20 crates. On Tuesday he sold 15 crates, on Wednesday 12 crates, and Thursday 18 crates. By how many crates was Sam off from his target for the week?
- Ground truth answer: `55`
- Method branch final answer text (direct-or-recovered): `65`
- Oracle branch final answer text (direct-or-recovered): `65`
- Method normalized answer: `65`
- Oracle normalized answer: `65`
- Method reasoning text (direct): Calculate total crates sold from Tuesday to Thursday and weekend: 15 + 12 + 18 + 20 = 65 crates.
- Oracle reasoning text (direct): Calculate total crates sold: 20 (weekend) + 15 (Tuesday) + 12 (Wednesday) + 18 (Thursday) = 65 crates.
- Method extracted numbers: `[15.0, 12.0, 18.0, 20.0, 65.0]`
- Oracle extracted numbers: `[20.0, 15.0, 12.0, 18.0, 65.0]`
- Divergence: method selected `b0` under higher learned margin while oracle rollout target preferred `b2` with higher expected value.
- Design lesson: penalize high-confidence selection when branch-level answer evidence is weak or lagging against oracle-immediate value.

## Case 3: `s_ep3_d1_r4_d69ede3958bfe0e8c072`
- dataset/example: `openai/gsm8k` / `openai_gsm8k_3`
- method: `adaptive_learned_branch_score_v3` chose `b0`; oracle-best `b2`
- oracle_regret=0.091262, method_margin_top2=0.120000, hard_slice=strict
- Full problem: Sandra's neighbor gives her a basket of 9 eggs every time she babysits their daughter. To make a Spanish flan, she needs 3 eggs. If Sandra has been tasked to make 15 Spanish flans for her school fundraiser, how many times does Sandra have to babysit?
- Ground truth answer: `5`
- Method branch final answer text (direct-or-recovered): `45`
- Oracle branch final answer text (direct-or-recovered): `45`
- Method normalized answer: `45`
- Oracle normalized answer: `45`
- Method reasoning text (direct): Calculate the total number of eggs needed by multiplying the number of flans (15) by the eggs per flan (3).
Total eggs needed = 15 flans * 3 eggs/flan = 45 eggs.
- Oracle reasoning text (direct): Sandra needs 3 eggs per flan and must make 15 flans, so she needs 3 * 15 = 45 eggs in total.
- Method extracted numbers: `[15.0, 3.0, 15.0, 3.0, 45.0]`
- Oracle extracted numbers: `[3.0, 15.0, 3.0, 15.0, 45.0]`
- Divergence: method selected `b0` under higher learned margin while oracle rollout target preferred `b2` with higher expected value.
- Design lesson: penalize high-confidence selection when branch-level answer evidence is weak or lagging against oracle-immediate value.

## Case 4: `s_ep1_d0_r5_b08c6cc8e4911f612ce1`
- dataset/example: `openai/gsm8k` / `openai_gsm8k_1`
- method: `adaptive_learned_branch_score_v3` chose `b0`; oracle-best `b2`
- oracle_regret=0.022843, method_margin_top2=0.000000, hard_slice=near_tie
- Full problem: Eve had 20 pieces of pomelos. After giving her friend some pomelos, Eve is left with 1/4 of the pomelos she originally had. How many pomelos did Eve give away?
- Ground truth answer: `15`
- Method branch final answer text (direct-or-recovered): `5`
- Oracle branch final answer text (direct-or-recovered): `5`
- Method normalized answer: `5`
- Oracle normalized answer: `5`
- Method reasoning text (direct): Eve is left with 1/4 of 20 pomelos, which is 20 * 1/4 = 5 pomelos.
- Oracle reasoning text (direct): Eve is left with 1/4 of 20 pomelos, which is 20 * 1/4 = 5 pomelos.
- Method extracted numbers: `[1.0, 4.0, 20.0, 20.0, 1.0, 4.0, 5.0]`
- Oracle extracted numbers: `[1.0, 4.0, 20.0, 20.0, 1.0, 4.0, 5.0]`
- Divergence: method selected `b0` under higher learned margin while oracle rollout target preferred `b2` with higher expected value.
- Design lesson: penalize high-confidence selection when branch-level answer evidence is weak or lagging against oracle-immediate value.

## Case 5: `s_ep1_d1_r4_5d1858d3a0b597a59a9f`
- dataset/example: `openai/gsm8k` / `openai_gsm8k_1`
- method: `adaptive_learned_branch_score_v3` chose `b1`; oracle-best `b2`
- oracle_regret=0.014299, method_margin_top2=0.000000, hard_slice=near_tie
- Full problem: Eve had 20 pieces of pomelos. After giving her friend some pomelos, Eve is left with 1/4 of the pomelos she originally had. How many pomelos did Eve give away?
- Ground truth answer: `15`
- Method branch final answer text (direct-or-recovered): `5`
- Oracle branch final answer text (direct-or-recovered): `5`
- Method normalized answer: `5`
- Oracle normalized answer: `5`
- Method reasoning text (direct): Eve originally had 20 pomelos and is left with 1/4 of them, so she has 20 * 1/4 = 5 pomelos left.
- Oracle reasoning text (direct): Eve is left with 1/4 of 20 pomelos, which is 20 * 1/4 = 5 pomelos.
- Method extracted numbers: `[20.0, 1.0, 4.0, 20.0, 1.0, 4.0, 5.0]`
- Oracle extracted numbers: `[1.0, 4.0, 20.0, 20.0, 1.0, 4.0, 5.0]`
- Divergence: method selected `b1` under higher learned margin while oracle rollout target preferred `b2` with higher expected value.
- Design lesson: penalize high-confidence selection when branch-level answer evidence is weak or lagging against oracle-immediate value.

