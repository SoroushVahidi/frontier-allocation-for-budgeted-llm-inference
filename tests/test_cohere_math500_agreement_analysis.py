from __future__ import annotations

from pathlib import Path

import pandas as pd


REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "outputs" / "cohere_math500_agreement_only_analysis_20260524"
OFF4 = REPO / "outputs" / "failure_pattern_workbench_official4_20260524"


def _metric(df: pd.DataFrame, metric: str) -> int:
    row = df[df["metric"] == metric]
    assert len(row) == 1
    return int(row["count"].iloc[0])


def test_pairwise_net_recovery_matches_component_counts() -> None:
    p4 = pd.read_csv(OUT / "agreement_vs_pooled4_pairwise.csv")
    rec = _metric(p4, "agreement_only_correct_pooled4_wrong")
    reg = _metric(p4, "agreement_only_wrong_pooled4_correct")
    net = _metric(p4, "net_recovery")
    assert net == rec - reg


def test_case_table_has_expected_shape_and_required_columns() -> None:
    case = pd.read_csv(OUT / "cohere_math500_official_case_table.csv")
    assert len(case) == 300
    for col in [
        "example_id",
        "agreement_only_selected_answer",
        "agreement_only_selected_correct",
        "pooled4_selected_answer",
        "pooled4_selected_correct",
        "external_majority_exists",
        "question_has_equation_flag",
    ]:
        assert col in case.columns


def test_official4_unified_table_is_complete() -> None:
    df = pd.read_csv(OFF4 / "official4_unified_case_table.csv")
    assert len(df) == 1200
    counts = df["scenario_id"].value_counts().to_dict()
    assert counts == {
        "cohere_gsm8k": 300,
        "mistral_gsm8k": 300,
        "cohere_math500": 300,
        "mistral_math500": 300,
    }
