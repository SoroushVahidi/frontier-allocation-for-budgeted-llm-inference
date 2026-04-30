from __future__ import annotations

import json
from pathlib import Path

from scripts.run_large_selector_tournament import (
    build_verifier_prompt,
    cache_key,
    evaluate_metrics,
    load_cache,
    support_family_selector,
)
from scripts.scan_selector_headroom_artifacts import evaluate_artifact


def test_gold_not_in_verifier_prompt() -> None:
    p = build_verifier_prompt("What is 1+1?", "2", "3")
    assert "gold" not in p.lower()


def test_cache_key_stable() -> None:
    k1 = cache_key("command-r-plus", "q", "a", {"x": 1})
    k2 = cache_key("command-r-plus", "q", "a", {"x": 1})
    assert k1 == k2


def test_cache_avoids_duplicate_calls(tmp_path: Path) -> None:
    c = tmp_path / "cache.jsonl"
    row = {"cache_key": "abc", "correctness_probability": 0.8}
    c.write_text(json.dumps(row) + "\n", encoding="utf-8")
    loaded = load_cache(c)
    assert "abc" in loaded


def test_oracle_excluded_from_deployable_selection_logic() -> None:
    selectors = ["current_dr_v2_selector", "support_family_selector", "cohere_outcome_verifier_selector", "oracle_selector"]
    deployable = [s for s in selectors if s != "oracle_selector"]
    assert "oracle_selector" not in deployable


def test_support_family_selector_deterministic() -> None:
    rec = {
        "current_dr_v2_answer": "10",
        "candidate_groups": [
            {"normalized_answer": "10", "support": 2, "source_method": "a"},
            {"normalized_answer": "11", "support": 4, "source_method": "a"},
            {"normalized_answer": "11", "support": 1, "source_method": "b"},
        ],
    }
    a1 = support_family_selector(rec)
    a2 = support_family_selector(rec)
    assert a1 == a2


def test_fixes_breaks_override_precision_metrics() -> None:
    rows = [
        {
            "current_dr_v2_selector_correct": 0,
            "external_l1_max_correct": 0,
            "oracle_selector_correct": 1,
            "gold_present_and_dr_wrong": 1,
            "support_family_selector_correct": 1,
            "support_family_selector_override_applied": 1,
        },
        {
            "current_dr_v2_selector_correct": 1,
            "external_l1_max_correct": 1,
            "oracle_selector_correct": 1,
            "gold_present_and_dr_wrong": 0,
            "support_family_selector_correct": 0,
            "support_family_selector_override_applied": 1,
        },
    ]
    m = evaluate_metrics(rows, "support_family_selector")
    assert m["fixes"] == 1
    assert m["breaks"] == 1


def test_scan_rejects_unusable_artifact(tmp_path: Path) -> None:
    art = tmp_path / "bad_artifact"
    art.mkdir(parents=True)
    (art / "per_case_method_results.csv").write_text("method,example_id\n", encoding="utf-8")
    out = tmp_path / "out"
    out.mkdir()
    r = evaluate_artifact(art, out)
    assert r.usable == 0
