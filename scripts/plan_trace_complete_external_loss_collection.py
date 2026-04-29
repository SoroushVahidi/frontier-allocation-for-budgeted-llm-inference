#!/usr/bin/env python3
from __future__ import annotations

METHODS = [
    "strict_f3", "strict_gate1_cap_k6", "direct_reserve_semantic_frontier_v2",
    "external_l1_max", "tale", "s1", "self_consistency_3", "tot_beam_matched_budget",
]
MAX_EXAMPLES = 20
BUDGETS = [4]
SEEDS = [11]


def main() -> None:
    calls = len(METHODS) * len(BUDGETS) * len(SEEDS) * MAX_EXAMPLES
    print("Dry-run plan only (no API calls executed).")
    print(f"Estimated method-example-budget calls: {calls}")
    print("Required env keys (presence only): COHERE_API_KEY or OPENAI_API_KEY")
    print("Suggested command:")
    print(
        "python scripts/run_cohere_real_model_cost_normalized_validation.py "
        "--providers cohere --datasets openai/gsm8k --budgets 4 --seeds 11 "
        "--methods strict_f3,strict_gate1_cap_k6,direct_reserve_semantic_frontier_v2,external_l1_max,tale,s1,self_consistency_3,tot_beam_matched_budget "
        "--target-scored-per-slice 20 --max-examples 20 --resume --save-branch-traces --emit-trace-audit "
        "--output-root outputs/external_baseline_loss_case_live_collection_<TIMESTAMP>"
    )


if __name__ == "__main__":
    main()
