import copy

from experiments import value_of_compute_controller as voc


def _mk_group(
    *,
    frontier_ans="10",
    l1="10",
    s1="10",
    tale="10",
    support_margin=0.0,
    override_reason="direct_frontier_agree",
    low_depth=False,
    final_nodes=None,
):
    rm = {
        "support_margin": support_margin,
        "override_reason": override_reason,
        "direct_frontier_agree": override_reason == "direct_frontier_agree",
        "direct_reserve_confidence_proxy": 0.5,
        "frontier_candidate_answer": frontier_ans,
        "candidate_pool_answer_group_count": 2,
        "frontier_support": 0 if low_depth else 1,
        "node_expansion_order": ["a", "b", "c"],
        "action_trace": [{"answer": frontier_ans, "reasoning_text": "r"}],
    }
    frontier_row = {
        "method": "direct_reserve_semantic_frontier_v2",
        "final_answer_canonical": frontier_ans,
        "selected_answer_canonical": frontier_ans,
        "result_metadata": rm,
        "final_nodes": final_nodes if final_nodes is not None else [
            {"predicted_answer": frontier_ans},
            {"predicted_answer": "11"},
        ],
        "input_tokens": 10,
        "output_tokens": 20,
        "total_tokens": 30,
        "cohere_logical_api_calls": 2,
        "latency_seconds": 1.2,
        "estimated_cost_usd": 0.01,
        "promotion_review_record": {"candidate_trace": "trace", "calibrated_percentile": 0.8},
        "gold_answer": "10",
        "exact_match": 1,
    }
    return {
        "direct_reserve_semantic_frontier_v2": frontier_row,
        "external_l1_max": {"method": "external_l1_max", "final_answer_canonical": l1},
        "external_s1_budget_forcing": {"method": "external_s1_budget_forcing", "final_answer_canonical": s1},
        "external_tale_prompt_budgeting": {"method": "external_tale_prompt_budgeting", "final_answer_canonical": tale},
    }


def test_state_extractor_excludes_gold_exact_correctness():
    g = _mk_group()
    state = voc.extract_lovec_state_features(g)
    joined_keys = "|".join(state.keys()).lower()
    assert "gold" not in joined_keys
    assert "exact_match" not in joined_keys
    assert "correct" not in joined_keys


def test_agreement_features_computed_correctly():
    g = _mk_group(frontier_ans="7", l1="9", s1="9", tale="7", support_margin=1.0)
    state = voc.extract_lovec_state_features(g)
    assert state["external_agreement_signature"] == "l1=s1!=tale"
    assert state["tale_isolated"] is True
    assert state["frontier_agrees_l1_s1"] is False
    assert state["frontier_agrees_any_external"] is True
    assert state["unique_external_answer_count"] == 2


def test_low_depth_and_support_features_when_present():
    g = _mk_group(low_depth=True, support_margin=-1.0, override_reason="single_weak_frontier_branch")
    state = voc.extract_lovec_state_features(g)
    assert state["low_depth_flag"] is True
    assert state["weak_search_flag"] is True
    assert state["support_margin"] == -1.0


def test_action_availability_does_not_hallucinate():
    # final_nodes has only base answer -> no frontier alternative
    g = _mk_group(frontier_ans="10", l1="10", s1="10", tale="10", final_nodes=[{"predicted_answer": "10"}])
    actions = voc.available_lovec_actions(g)
    assert actions["logged_frontier_alternative_proxy"]["available"] is False
    assert actions["logged_external_alternative_proxy"]["available"] is False
    assert actions["no_observable_extra_action"]["available"] is True


def test_oracle_uses_labels_offline_not_in_policy_features():
    g = _mk_group(frontier_ans="10", l1="10", s1="10", tale="12")
    state_before = voc.extract_lovec_state_features(g)
    o1 = voc.choose_oracle_observable_action_offline(g, "10")
    o2 = voc.choose_oracle_observable_action_offline(g, "12")
    state_after = voc.extract_lovec_state_features(g)

    # Oracle action depends on gold label; runtime state should not.
    assert o1["oracle_action"] != o2["oracle_action"]
    assert state_before == state_after


def test_lovec_skeleton_defaults_to_fix24_when_no_action():
    g = _mk_group(frontier_ans="10", l1="10", s1="10", tale="10", final_nodes=[{"predicted_answer": "10"}])
    out = voc.apply_lovec1_controller(g)
    assert out["lovec_action"] == "stop_fix24"
    assert out["lovec_action_changed"] is False
    assert out["lovec_answer_canonical"] == "10"


def test_available_actions_include_all_required_names():
    g = _mk_group()
    actions = voc.available_lovec_actions(g)
    for name in [
        "stop_fix24",
        "stop_tale",
        "stop_external_consensus",
        "logged_frontier_alternative_proxy",
        "logged_external_alternative_proxy",
        "no_observable_extra_action",
    ]:
        assert name in actions
