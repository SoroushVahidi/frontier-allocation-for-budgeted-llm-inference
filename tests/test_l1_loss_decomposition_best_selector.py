from scripts.run_l1_loss_decomposition_for_best_selector import (
    METHOD_DRV2,
    METHOD_L1,
    METHOD_OV,
    classify_loss_bucket,
    group_by_case,
    paired_stats_from_groups,
)

def test_classify_gold_absent() -> None:
    l1 = {"exact_match": 1, "scored": 1}
    sel = {
        "exact_match": 0,
        "scored": 1,
        "parse_extraction_failure": 0,
        "status": "scored",
        "final_nodes": [{"predicted_answer_normalized": "1"}],
        "gold_in_tree": 0,
        "result_metadata": {"selector_candidate_pool": [{"predicted_answer": "1"}]},
    }
    assert classify_loss_bucket(l1_row=l1, sel_row=sel) == "gold_absent_from_candidate_tree"


def test_paired_stats_tiny() -> None:
    k = ("cohere", "d", 1, 4, "e1")
    m = {
        METHOD_L1: {"exact_match": 1},
        METHOD_DRV2: {"exact_match": 0},
        METHOD_OV: {"exact_match": 0},
    }
    groups = {k: m}
    st = paired_stats_from_groups(groups, selected_method=METHOD_OV)
    assert st["l1_correct_ours_wrong_count"] == 1
    assert st["both_correct_count"] == 0


def test_group_by_case_skips_unscored_rows() -> None:
    rows = [
        {"provider": "cohere", "dataset": "d", "seed": 1, "budget": 4, "example_id": "x", "method": METHOD_L1, "scored": 1},
        {"provider": "cohere", "dataset": "d", "seed": 1, "budget": 4, "example_id": "x", "method": METHOD_OV, "scored": 0},
    ]
    g = group_by_case(rows)
    assert METHOD_L1 in g[("cohere", "d", 1, 4, "x")]
    assert METHOD_OV not in g[("cohere", "d", 1, 4, "x")]
