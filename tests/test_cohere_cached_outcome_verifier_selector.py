from scripts.run_cohere_cached_outcome_verifier_selector import build_verifier_prompt, run_selector, summary_for, cache_key


def test_prompt_excludes_gold_and_margin_blocks_small_gap() -> None:
    p = build_verifier_prompt("q", "42")
    assert "gold" not in p.lower()
    cases = [{"example_id": "e1", "gold": "b", "dr_pred": "a", "l1_pred": "b", "groups": [{"normalized_answer": "a"}, {"normalized_answer": "b"}]}]
    scores = {("e1", "a"): 0.60, ("e1", "b"): 0.70}
    pred_rows, _ = run_selector(cases, scores, margin=0.15)
    assert pred_rows[0]["pred"] == "a"


def test_summary_and_override_precision() -> None:
    cases = [
        {"example_id": "e1", "gold": "b", "dr_pred": "a", "l1_pred": "b", "groups": [{"normalized_answer": "a"}, {"normalized_answer": "b"}]},
        {"example_id": "e2", "gold": "c", "dr_pred": "c", "l1_pred": "c", "groups": [{"normalized_answer": "c"}, {"normalized_answer": "d"}]},
    ]
    preds = {"e1": "b", "e2": "d"}
    s = summary_for("x", preds, cases)
    assert s["fixes"] == 1
    assert s["breaks"] == 1
    assert s["overrides"] == 2
    assert s["override_precision"] == 0.5


def test_cache_key_deduplicates_and_oracle_excluded_from_best() -> None:
    k1 = cache_key("m", "q", "a")
    k2 = cache_key("m", "q", "a")
    k3 = cache_key("m", "q", "b")
    assert k1 == k2
    assert k1 != k3

    rows = [
        {"selector": "oracle_selector", "accuracy": 1.0, "net_fixes_minus_breaks": 3, "breaks": 0},
        {"selector": "cohere_outcome_verifier_selector_v1", "accuracy": 0.7, "net_fixes_minus_breaks": 1, "breaks": 0},
    ]
    deploy = [x for x in rows if x["selector"] != "oracle_selector"]
    best = max(deploy, key=lambda r: (r["accuracy"], r["net_fixes_minus_breaks"], -r["breaks"]))
    assert best["selector"] == "cohere_outcome_verifier_selector_v1"
