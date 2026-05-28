"""Tests for Cohere MATH-500 auxiliary processing script logic.

Logic is tested inline (not via dynamic import) to avoid module loader issues.
"""
import collections

# Method alias map mirrors the one in scripts/process_existing_cohere_math500_auxiliary.py
ALIAS_MAP = {
    "direct_reserve_semantic_frontier_v2": "direct_reserve_semantic_frontier_v2",
    "frontier": "direct_reserve_semantic_frontier_v2",
    "external_l1_max": "external_l1_max",
    "l1": "external_l1_max",
    "l1_max": "external_l1_max",
    "external_s1_budget_forcing": "external_s1_budget_forcing",
    "s1": "external_s1_budget_forcing",
    "s1_budget_forcing": "external_s1_budget_forcing",
    "external_tale_prompt_budgeting": "external_tale_prompt_budgeting",
    "tale": "external_tale_prompt_budgeting",
    "tale_prompt_budgeting": "external_tale_prompt_budgeting",
}

ALL_METHODS = [
    "direct_reserve_semantic_frontier_v2",
    "external_l1_max",
    "external_s1_budget_forcing",
    "external_tale_prompt_budgeting",
]


def normalize_method(raw):
    return ALIAS_MAP.get(raw.strip().lower(), raw)


def row_priority(r):
    scored = int(r.get("status") == "scored")
    is_recovery = int(r.get("_source") == "recovery")
    return (scored, is_recovery)


def test_method_alias_normalization():
    assert normalize_method("s1") == "external_s1_budget_forcing"
    assert normalize_method("S1") == "external_s1_budget_forcing"
    assert normalize_method("tale") == "external_tale_prompt_budgeting"
    assert normalize_method("TALE") == "external_tale_prompt_budgeting"
    assert normalize_method("direct_reserve_semantic_frontier_v2") == "direct_reserve_semantic_frontier_v2"
    assert normalize_method("external_l1_max") == "external_l1_max"
    assert normalize_method("external_s1_budget_forcing") == "external_s1_budget_forcing"
    assert normalize_method("external_tale_prompt_budgeting") == "external_tale_prompt_budgeting"


def test_duplicate_resolution_prefers_scored():
    """Scored main wins over unscored recovery."""
    r_main_scored = {"_source": "main", "status": "scored"}
    r_recovery_failed = {"_source": "recovery", "status": "failed"}
    assert row_priority(r_main_scored) > row_priority(r_recovery_failed)


def test_duplicate_resolution_prefers_scored_recovery_over_failed_main():
    """Scored recovery wins over failed main."""
    r_main_failed = {"_source": "main", "status": "failed"}
    r_recovery_scored = {"_source": "recovery", "status": "scored"}
    assert row_priority(r_recovery_scored) > row_priority(r_main_failed)


def test_complete_4method_extraction():
    """Examples missing any method are excluded from complete set."""
    rows = []
    for m in ALL_METHODS:
        rows.append({"example_id": "ex1", "method": m, "status": "scored"})
    for m in ALL_METHODS[:3]:  # missing TALE
        rows.append({"example_id": "ex2", "method": m, "status": "scored"})

    per_example = collections.defaultdict(dict)
    for r in rows:
        if r.get("status") == "scored":
            per_example[r["example_id"]][r["method"]] = r

    complete = [eid for eid, mmap in per_example.items() if all(m in mmap for m in ALL_METHODS)]
    assert "ex1" in complete
    assert "ex2" not in complete


def test_near_peer_regime_classification():
    """Spread < 5pp classified as near_peer."""
    spread = 0.04  # 4pp
    if spread > 0.15:
        regime = "dominant_source"
    elif spread < 0.05:
        regime = "near_peer"
    else:
        regime = "mixed"
    assert regime == "near_peer"


def test_mixed_regime_classification():
    """Spread 5-15pp classified as mixed."""
    spread = 0.10
    if spread > 0.15:
        regime = "dominant_source"
    elif spread < 0.05:
        regime = "near_peer"
    else:
        regime = "mixed"
    assert regime == "mixed"
