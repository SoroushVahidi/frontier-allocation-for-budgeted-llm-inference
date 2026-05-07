from __future__ import annotations

from experiments.controllers import (
    PAL_EXECUTION_SELECTOR_POOL_SOURCE_ID,
    merge_pal_execution_into_selector_candidate_pool,
)


def _pal_meta(er: dict, *, observed: int = 1, score: float = 0.5) -> dict:
    return {
        "pal_budget_cost_observed": observed,
        "pal_score": score,
        "pal_execution_result": er,
    }


def test_merge_adds_execution_numeric_with_source_label() -> None:
    pool_in: list[dict] = [{"branch_id": "direct_reserve_0", "predicted_answer": "7", "source_id": "direct_reserve"}]
    er = {
        "pal_stdout": "",
        "pal_answer_raw": "42",
        "pal_answer_normalized": "42",
    }
    out = merge_pal_execution_into_selector_candidate_pool(
        pool_in,
        _pal_meta(er),
        actions_used=2,
        selected_group_key="42",
    )
    pal_rows = [r for r in out if isinstance(r, dict) and r.get("source_id") == PAL_EXECUTION_SELECTOR_POOL_SOURCE_ID]
    assert len(pal_rows) == 1
    assert pal_rows[0].get("predicted_answer") == "42"
    assert pal_rows[0].get("source_metadata") == "pal_execution:pal_answer_normalized"
    assert pal_rows[0].get("is_original_selected") == 1


def test_merge_dedupes_normalized_raw_stdout_same_group() -> None:
    pool_in: list[dict] = []
    er = {
        "pal_stdout": "42\n",
        "pal_answer_raw": "42",
        "pal_answer_normalized": "42",
    }
    out = merge_pal_execution_into_selector_candidate_pool(
        pool_in,
        _pal_meta(er),
        actions_used=1,
        selected_group_key="__unknown__",
    )
    n_pal_exec = sum(1 for r in out if r.get("source_id") == PAL_EXECUTION_SELECTOR_POOL_SOURCE_ID)
    assert n_pal_exec == 1


def test_merge_dedupes_against_existing_pool_row() -> None:
    pool_in: list[dict] = [
        {
            "branch_id": "pal_seed_0",
            "predicted_answer": "100",
            "source_id": "pal_seed",
            "source_family": "pal_seed",
        }
    ]
    er = {"pal_stdout": "", "pal_answer_raw": "100", "pal_answer_normalized": "100"}
    out = merge_pal_execution_into_selector_candidate_pool(
        pool_in,
        _pal_meta(er),
        actions_used=1,
        selected_group_key="100",
    )
    assert sum(1 for r in out if r.get("source_id") == PAL_EXECUTION_SELECTOR_POOL_SOURCE_ID) == 0


def test_stdout_numeric_when_normalized_empty_no_gold() -> None:
    pool_in: list[dict] = []
    er = {"pal_stdout": "17\n", "pal_answer_raw": "", "pal_answer_normalized": ""}
    out = merge_pal_execution_into_selector_candidate_pool(
        pool_in,
        _pal_meta(er),
        actions_used=1,
        selected_group_key="999",
    )
    labels = {(r.get("predicted_answer"), r.get("source_metadata")) for r in out}
    assert ("17", "pal_execution:pal_stdout_numeric") in labels


def test_merge_skips_when_pal_budget_not_observed() -> None:
    pool_in: list[dict] = []
    er = {"pal_stdout": "9\n", "pal_answer_normalized": "9"}
    out = merge_pal_execution_into_selector_candidate_pool(
        pool_in,
        _pal_meta(er, observed=0),
        actions_used=0,
        selected_group_key="__unknown__",
    )
    assert out == []
