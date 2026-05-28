from pathlib import Path

import pandas as pd


REPO = Path("/home/soroush/frontier-allocation-for-budgeted-llm-inference")
OUT = REPO / "outputs" / "router_v2_manuscript_reproduction_20260524"


def test_official_row_count_is_1200():
    df = pd.read_csv(OUT / "reproduced_official4_case_table.csv")
    assert len(df) == 1200
    assert df[["scenario_id", "example_id"]].drop_duplicates().shape[0] == 1200
    counts = df.groupby("scenario_id")["example_id"].nunique().to_dict()
    for scenario in ["cohere_gsm8k", "mistral_gsm8k", "cohere_math500", "mistral_math500"]:
        assert counts.get(scenario, 0) == 300


def test_no_leaky_features_in_whitelist():
    wl = pd.read_csv(OUT / "reproduced_feature_whitelist.csv")
    used = wl[wl["status"] == "used"]["feature_name"].str.lower()
    bad_tokens = [
        "correct",
        "gold",
        "reference",
        "oracle",
        "label",
        "target",
        "failure",
        "all_sources",
        "only_",
        "wrong",
        "best_action",
    ]
    for feat in used:
        assert not any(tok in feat for tok in bad_tokens), feat


def test_oracle_ceiling_not_below_router():
    cmp_df = pd.read_csv(OUT / "same_row_method_comparison.csv")
    router = float(cmp_df.loc[cmp_df["method"] == "corrected_router_v2_independent", "accuracy"].iloc[0])
    oracle_classification = float(
        cmp_df.loc[cmp_df["method"] == "oracle_binary_classification_ceiling", "accuracy"].iloc[0]
    )
    assert oracle_classification >= router


def test_key_tables_and_figures_exist():
    required = [
        "table_main_official_scenarios.csv",
        "table_macro_micro_summary.csv",
        "table_transfer_robustness.csv",
        "table_leakage_audit_summary.csv",
        "table_ablation_summary.csv",
        "fig_method_accuracy_by_scenario.png",
        "fig_macro_accuracy_comparison.png",
        "fig_oracle_regret_comparison.png",
        "fig_router_v2_action_distribution.png",
        "fig_leakage_correction.png",
    ]
    for name in required:
        assert (OUT / name).exists(), name
