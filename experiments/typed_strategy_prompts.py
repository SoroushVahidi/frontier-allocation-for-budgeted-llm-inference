from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TypedStrategyPrompt:
    strategy_family: str
    strategy_name: str
    strategy_prompt: str
    strategy_rationale: str
    expected_failure_mode_addressed: str
    is_required_for_problem_type: bool


def get_typed_strategy_prompts(question: str, problem_type: str) -> list[TypedStrategyPrompt]:
    _ = question
    if problem_type != "counting_combinatorics":
        return []
    return [
        TypedStrategyPrompt(
            strategy_family="direct_formula_family",
            strategy_name="direct_formula_compact",
            strategy_prompt=(
                "Use direct counting/arithmetic formula reasoning. Keep the derivation compact, avoid exhaustive listing, "
                "and output the final numeric answer only after checking units and what is being counted."
            ),
            strategy_rationale="Compact direct derivation can find clean combinatorial structure quickly.",
            expected_failure_mode_addressed="absent_from_tree",
            is_required_for_problem_type=True,
        ),
        TypedStrategyPrompt(
            strategy_family="explicit_case_split_family",
            strategy_name="explicit_disjoint_case_split",
            strategy_prompt=(
                "First identify distinct cases, explain why they are disjoint, solve each case independently, "
                "then aggregate all case counts into a final answer."
            ),
            strategy_rationale="Explicit disjoint case reasoning reduces missed-case and overlap errors.",
            expected_failure_mode_addressed="present_not_selected",
            is_required_for_problem_type=True,
        ),
        TypedStrategyPrompt(
            strategy_family="enumeration_or_decomposition_family",
            strategy_name="enumerate_or_decompose_subcounts",
            strategy_prompt=(
                "Enumerate categories/subcases when feasible; if large, decompose into smaller subcounts. "
                "Explicitly check omissions and duplicate counting before summing."
            ),
            strategy_rationale="Decomposition exposes hidden branches and coverage gaps.",
            expected_failure_mode_addressed="absent_from_tree",
            is_required_for_problem_type=True,
        ),
        TypedStrategyPrompt(
            strategy_family="small_example_pattern_family",
            strategy_name="small_example_then_generalize",
            strategy_prompt=(
                "Solve one or two simplified smaller versions first, detect a pattern, generalize to the original problem, "
                "then verify the generalized result against the original constraints."
            ),
            strategy_rationale="Small-instance patterning can surface structure missing in direct attempts.",
            expected_failure_mode_addressed="absent_from_tree",
            is_required_for_problem_type=True,
        ),
        TypedStrategyPrompt(
            strategy_family="sanity_check_verifier_family",
            strategy_name="sanity_check_and_verify",
            strategy_prompt=(
                "Act as verifier: check ordered vs unordered interpretation, possible double counting, completeness of cases, "
                "disjointness of cases, arithmetic aggregation consistency, and whether the final answer exactly matches the question ask."
            ),
            strategy_rationale="Verifier-style branch can prevent high-confidence wrong commits.",
            expected_failure_mode_addressed="present_not_selected",
            is_required_for_problem_type=True,
        ),
    ]

