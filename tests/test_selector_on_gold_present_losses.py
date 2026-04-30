from scripts import run_selector_on_gold_present_losses as mod


def test_filter_only_trace_gold_present_oracle_fix() -> None:
    rows = [
        {"trace_available": 1, "gold_present_in_candidate_groups": 1, "oracle_selector_would_fix": 1},
        {"trace_available": 1, "gold_present_in_candidate_groups": 0, "oracle_selector_would_fix": 1},
        {"trace_available": 0, "gold_present_in_candidate_groups": 1, "oracle_selector_would_fix": 1},
    ]
    out = mod.filter_selector_recoverable(rows)
    assert len(out) == 1


def test_support_family_selector_deterministic() -> None:
    cands = [
        {"answer": "a", "support": 2, "source_family_count": 1, "branch_depth": 1},
        {"answer": "b", "support": 2, "source_family_count": 2, "branch_depth": 1},
    ]
    ans, _ = mod.support_family_selector(cands, current="a")
    assert ans == "b"


def test_conservative_blocks_weak_override() -> None:
    cands = [
        {"answer": "cur", "support": 2, "source_family_count": 1},
        {"answer": "new", "support": 3, "source_family_count": 1},
    ]
    ans, _ = mod.conservative_support_selector(cands, current="cur")
    assert ans == "cur"


def test_risk_gated_only_overrides_when_current_weak() -> None:
    cands = [
        {"answer": "cur", "support": 1, "source_family_count": 1},
        {"answer": "new", "support": 2, "source_family_count": 2},
    ]
    ans, _ = mod.risk_gated_support_selector(cands, current="cur")
    assert ans == "new"


def test_pairwise_cache_key_stability() -> None:
    k1 = mod._hash_key(["pairwise", "m", "q", "a", "b"])
    k2 = mod._hash_key(["pairwise", "m", "q", "a", "b"])
    assert k1 == k2


def test_model_alias_maps_to_supported_model() -> None:
    assert mod.normalize_model("command-r-plus") == "command-r-plus-08-2024"
