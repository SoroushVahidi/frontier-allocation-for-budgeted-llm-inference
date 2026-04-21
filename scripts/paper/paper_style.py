from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FigureStyle:
    width: float = 6.8
    height: float = 4.0
    title_size: int = 12
    label_size: int = 10
    tick_size: int = 8
    legend_size: int = 8
    line_width: float = 1.8
    marker_size: float = 4.5
    grid_alpha: float = 0.20


STYLE = FigureStyle()

CANONICAL_METHOD_ORDER = [
    "strict_gate1_cap_k6 (default)",
    "strict_gate1",
    "strict_f2",
    "strict_f3",
    "strict_gate2",
    "baseline",
    "fixed_k6",
    "min6_half",
    "min6_third",
    "min6_quarter",
    "half",
    "third",
    "quarter",
    "Reasoning Beam-2",
    "Self-Consistency-3",
    "Reasoning Greedy",
    "Verifier-Guided Search",
    "Program-of-Thought",
]

CANONICAL_DATASET_ORDER = [
    "openai/gsm8k",
    "HuggingFaceH4/MATH-500",
    "olympiadbench",
    "HuggingFaceH4/aime_2024",
]

CANONICAL_BUDGET_ORDER = [4, 6, 8, 10, 12, 14, 16]

METHOD_NAME_MAP = {
    "baseline": "baseline",
    "strict_f2": "strict_f2",
    "strict_f3": "strict_f3",
    "strict_gate1": "strict_gate1",
    "strict_gate2": "strict_gate2",
    "strict_gate1_cap_k6": "strict_gate1_cap_k6 (default)",
    "fixed_k6": "fixed_k6",
    "min6_half": "min6_half",
    "min6_third": "min6_third",
    "min6_quarter": "min6_quarter",
    "half": "half",
    "third": "third",
    "quarter": "quarter",
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
    "strict_gate1_cap_k6 (default)": "#1b9e77",
    "strict_gate1": "#377eb8",
    "strict_f2": "#4daf4a",
    "strict_f3": "#984ea3",
    "strict_gate2": "#ff7f00",
    "baseline": "#666666",
    "fixed_k6": "#1b9e77",
    "min6_half": "#66a61e",
    "min6_third": "#377eb8",
    "min6_quarter": "#984ea3",
    "half": "#4daf4a",
    "third": "#ff7f00",
    "quarter": "#a65628",
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
