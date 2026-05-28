from __future__ import annotations

from collections import defaultdict

import pandas as pd

from scripts.evaluate_ag01_agreement_only_gate import (
    AG01_VARIANTS,
    action_table_pick,
    ag01_variant_answer,
    base_decisions,
    external_2of3_against_frontier,
)


def _row(**kwargs) -> pd.Series:
    base = {
        "provider": "cohere",
        "dataset": "HuggingFaceH4/MATH-500",
        "scenario_id": "cohere_math500",
        "frontier_ans": "10",
        "L1_ans": "42",
        "S1_ans": "42",
        "TALE_ans": "7",
        "majority_answer": "10",
        "has_majority": 0,
        "external_majority_exists": 1,
        "external_majority_excludes_frontier": 1,
        "S1_isolated": 0,
        "majority_size": 2,
        "question_number_count": 4,
        "question_has_equation_flag": 1,
        "gold": "42",
    }
    base.update(kwargs)
    return pd.Series(base)


def _calib() -> dict:
    tbl = defaultdict(lambda: {a: (0, 0) for a in ["beta", "c1d", "pooled4", "agreement", "best_source"]})
    key_pd = ("cohere", "HuggingFaceH4/MATH-500", "l1=s1!=tale", 1, 1, 0, 2, 1)
    key_pf = ("l1=s1!=tale", 1, 1, 0, 2, 1)
    tbl[key_pd] = {"beta": (6, 10), "c1d": (6, 10), "pooled4": (5, 10), "agreement": (8, 10), "best_source": (6, 10)}
    tbl[key_pf] = {"beta": (6, 10), "c1d": (6, 10), "pooled4": (5, 10), "agreement": (8, 10), "best_source": (6, 10)}
    return {
        "ranked_sources": ["frontier", "L1", "S1", "TALE"],
        "best_source": "frontier",
        "second_source": "L1",
        "spread_best_second": 0.02,
        "entropy": 1.37,
        "ext_support": 10,
        "ext_ag_shr": 0.75,
        "ext_beta_shr": 0.55,
        "ext_c1d_shr": 0.55,
        "corr_support": 0,
        "corr_ag_shr": 0.5,
        "action_table_provider_dataset": tbl,
        "action_table_provider_free": tbl,
    }


def test_exact_agreement_only_rule_against_frontier() -> None:
    row = _row(frontier_ans="10", L1_ans="42", S1_ans="42", TALE_ans="7")
    on, ans = external_2of3_against_frontier(row)
    assert on is True
    assert ans == "42"

    row2 = _row(frontier_ans="42", L1_ans="42", S1_ans="42", TALE_ans="7")
    on2, ans2 = external_2of3_against_frontier(row2)
    assert on2 is False
    assert ans2 == "42"

    row3 = _row(frontier_ans="10", L1_ans="42", S1_ans="", TALE_ans="7")
    on3, _ = external_2of3_against_frontier(row3)
    assert on3 is False


def test_ag01a_gate_uses_agreement_only_only_when_condition_passes() -> None:
    calib = _calib()
    row = _row()
    ans = ag01_variant_answer(row, calib, "ag01a_np05")
    assert ans == "42"

    row_off = _row(external_majority_exists=0, external_majority_excludes_frontier=0, L1_ans="20", S1_ans="30", TALE_ans="40")
    ans_off = ag01_variant_answer(row_off, calib, "ag01a_np05")
    # falls back to beta_shrinkage (which falls to pooled4 under spread<0.05)
    assert ans_off == base_decisions(row_off, calib)["beta_shrinkage"]


def test_ag01b_min_support_fallback_to_base_selector() -> None:
    calib = _calib()
    calib["ext_support"] = 3
    row = _row()
    ans = ag01_variant_answer(row, calib, "ag01b_beta_d00_s5")
    assert ans == base_decisions(row, calib)["beta_shrinkage"]


def test_provider_free_variant_excludes_provider_dataset_identity() -> None:
    calib = _calib()
    r1 = _row(provider="cohere", dataset="HuggingFaceH4/MATH-500")
    r2 = _row(provider="mistral", dataset="openai/gsm8k")
    a1 = ag01_variant_answer(r1, calib, "ag01e_mean_s5_b11")
    a2 = ag01_variant_answer(r2, calib, "ag01e_mean_s5_b11")
    assert a1 == a2


def test_no_gold_used_in_inference() -> None:
    calib = _calib()
    r1 = _row(gold="42")
    r2 = _row(gold="999")
    assert ag01_variant_answer(r1, calib, "ag01c_reg_guard") == ag01_variant_answer(r2, calib, "ag01c_reg_guard")


def test_deterministic_tie_breaking_in_action_table() -> None:
    calib = _calib()
    # Force equal scores/support for beta and c1d, lower for others.
    key = ("cohere", "HuggingFaceH4/MATH-500", "l1=s1!=tale", 1, 1, 0, 2, 1)
    calib["action_table_provider_dataset"][key] = {
        "beta": (6, 10),
        "c1d": (6, 10),
        "pooled4": (1, 10),
        "agreement": (1, 10),
        "best_source": (1, 10),
    }
    row = _row()
    ans = action_table_pick(row, calib, True, min_support=5, alpha=1.0, beta=1.0, select_lcb=False)
    # lexical tie-break among equal scores picks beta first.
    assert ans == base_decisions(row, calib)["beta_shrinkage"]


def test_all_variants_return_valid_answer_string() -> None:
    calib = _calib()
    row = _row()
    for v in AG01_VARIANTS:
        ans = ag01_variant_answer(row, calib, v)
        assert isinstance(ans, str)
        assert ans != ""
