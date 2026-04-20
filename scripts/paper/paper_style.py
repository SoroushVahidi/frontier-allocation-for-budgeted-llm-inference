from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FigureStyle:
    width: float = 7.0
    height: float = 4.2
    title_size: int = 13
    label_size: int = 11
    tick_size: int = 9
    legend_size: int = 9
    line_width: float = 2.0
    marker_size: float = 5.0
    grid_alpha: float = 0.22


STYLE = FigureStyle()

CANONICAL_METHOD_ORDER = [
    "Promoted (Strict-Coupled Tie-Aware, bridged)",
    "Adaptive Budget Guarded",
    "Reasoning Beam-2",
    "Self-Consistency-3",
    "Reasoning Greedy",
    "Verifier-Guided Search",
    "Program-of-Thought",
    "Oracle Frontier Upper Bound",
]

CANONICAL_DATASET_ORDER = [
    "openai/gsm8k",
    "HuggingFaceH4/MATH-500",
    "Idavidrein/gpqa",
    "HuggingFaceH4/aime_2024",
]

CANONICAL_BUDGET_ORDER = [4, 6, 8, 10]

METHOD_NAME_MAP = {
    "strict_coupled_tie_aware_promoted": "Promoted (Strict-Coupled Tie-Aware, bridged)",
    "adaptive_budget_guarded": "Adaptive Budget Guarded",
    "reasoning_beam2": "Reasoning Beam-2",
    "self_consistency_3": "Self-Consistency-3",
    "reasoning_greedy": "Reasoning Greedy",
    "verifier_guided_search": "Verifier-Guided Search",
    "program_of_thought": "Program-of-Thought",
    "oracle_frontier_upper_bound": "Oracle Frontier Upper Bound",
}

METHOD_COLORS = {
    "Promoted (Strict-Coupled Tie-Aware, bridged)": "#1b9e77",
    "Adaptive Budget Guarded": "#66a61e",
    "Reasoning Beam-2": "#377eb8",
    "Self-Consistency-3": "#984ea3",
    "Reasoning Greedy": "#4daf4a",
    "Verifier-Guided Search": "#ff7f00",
    "Program-of-Thought": "#a65628",
    "Oracle Frontier Upper Bound": "#e41a1c",
}

METRIC_NAME_MAP = {
    "accuracy": "Accuracy",
    "gap_to_oracle": "Gap to Oracle",
    "oracle_gap": "Gap to Oracle",
    "avg_actions": "Average Actions",
    "budget_exhaustion_rate": "Budget Exhaustion Rate",
}


def canonical_method_name(raw: str) -> str:
    return METHOD_NAME_MAP.get(raw, raw)


def method_sort_key(name: str) -> tuple[int, str]:
    if name in CANONICAL_METHOD_ORDER:
        return (CANONICAL_METHOD_ORDER.index(name), name)
    return (999, name)


def dataset_sort_key(name: str) -> tuple[int, str]:
    if name in CANONICAL_DATASET_ORDER:
        return (CANONICAL_DATASET_ORDER.index(name), name)
    return (999, name)
