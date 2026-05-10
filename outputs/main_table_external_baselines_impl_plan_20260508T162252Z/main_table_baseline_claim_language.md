# Main-Table Baseline Claim Language

## Safe wording before rerun
- "We evaluate fair/faithful style-adapted external baselines: L1-max-fair, self-consistency (n=4/n=6), PAL/PoT-style, S1-style budget forcing, and TALE-EP-style prompt budgeting."
- "These are black-box inference-only comparator implementations under matched local harness settings."

## Safe wording after rerun (if results hold)
- "Our integrated method outperforms our fair/faithful style-adapted external baseline suite under matched budgets."

## Still forbidden
- "We beat official TALE/S1/L1 baselines" without full official stack parity and reruns.
- "We reproduce TALE-PT" (not implemented).

## Naming guidance
- S1-style: "faithful S1-style budget-forcing adapter"
- TALE-EP-style: "faithful TALE-EP-style prompt-budgeting adapter"
- PAL-style: "PAL/PoT-style program-execution baseline"
- best_external: "oracle upper bound over external baselines, not a deployable single method"
