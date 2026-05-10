# Baseline Fairness Report

## What each baseline is
- `external_l1_max`: in-repo inference-only L1-style length-control adapter.
- `external_tale_prompt_budgeting`: in-repo TALE-style prompt-budgeting adapter (MODE A), not TALE-PT reproduction.
- `external_s1_budget_forcing`: in-repo S1-style budget-forcing adapter (behavior-level).
- `best_external`: oracle upper bound over the three baseline columns.

## Source closeness
- S1-style: close behavior-level match; not full official model/checkpoint/harness parity.
- TALE-style: partial match (prompt-budgeting only); official TALE-PT/full path not reproduced.
- L1-style: partial internal adapter; no official external reproduction claim.
- best_external: not applicable as official method.

## Highest fairness risks
- Highest: TALE-style (`high`) due EP/PT split, heuristic estimator, and uncertain full official parity.
- Medium: S1-style and L1-style due adapter-vs-official stack differences.

## Safe wording now
- Use: "our implemented L1-style, TALE-style, and S1-style baselines".
- Use: "best_external oracle upper bound over our external-style baselines".

## Stronger wording requirements
- To claim faithful official reproduction: verify official repo/paper mapping, checkpoint, prompt templates, budget units, stop-token behavior, and eval harness parity; then rerun baselines.

## Recommendation on tables
- Label rows as "style/adapted" unless strict official parity is established.
- Consider rerunning baseline rows after higher-faithfulness adapters are implemented.
