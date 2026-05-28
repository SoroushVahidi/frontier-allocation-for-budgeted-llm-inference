from pathlib import Path

import pandas as pd


REPO = Path("/home/soroush/frontier-allocation-for-budgeted-llm-inference")
OUT = REPO / "outputs" / "learned_router_v2_corrected_validation_20260524"


def test_corrected_validation_outputs_exist():
    assert (OUT / "validation_summary.json").exists()
    assert (OUT / "corrected_feature_whitelist.csv").exists()
    assert (OUT / "corrected_repeated_cv_summary.csv").exists()


def test_corrected_feature_whitelist_nonempty():
    df = pd.read_csv(OUT / "corrected_feature_whitelist.csv")
    assert len(df) > 0

