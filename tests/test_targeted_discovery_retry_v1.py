"""Tests for offline targeted discovery retry v1 router/prompts."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from experiments.targeted_discovery_retry import (
    build_concise_decomposition_retry_prompt,
    build_final_target_guarded_retry_prompt,
    build_final_target_extraction_repair_prompt,
    build_prompt,
    build_rate_table_retry_prompt,
    build_structural_commit_challenge_retry_prompt,
    build_tale_style_decomposition_prompt,
    choose_scaffold,
    dry_run_eligible,
    validate_prompt_no_gold,
)

REPO = Path(__file__).resolve().parents[1]


def test_scaffold_routing_matches_families() -> None:
    for fam, exp in [
        ("money_budget", "quantity_ledger"),
        ("rate_ratio", "rate_table"),
        ("temporal_change", "before_after_state"),
        ("difference_comparison", "target_difference"),
        ("multi_step_total", "quantity_ledger"),
    ]:
        assert choose_scaffold({"derived_problem_family": fam}) == exp


def test_prompts_nonempty_and_no_gold_leak() -> None:
    p = build_prompt("A cake costs $12. You pay $20. How much change?", "quantity_ledger")
    assert len(p.strip()) > 50
    assert "boxed" in p.lower()
    assert validate_prompt_no_gold(p, "8") is True


def test_validate_prompt_detects_leaked_boxed_gold() -> None:
    bad = "Reasoning\n\\boxed{42}"
    assert validate_prompt_no_gold(bad, "42") is False


def test_unknown_family_not_selected_by_default() -> None:
    row = {
        "case_id": "openai_gsm8k_x",
        "cohort": "gold_absent_tagged",
        "derived_problem_family": "unknown",
        "problem_text": "Some text long enough to pass.",
        "notes": "union_mech=gold_absent_discovery",
        "external_winner_names": "external_l1_max",
        "derivation_confidence": "unknown",
    }
    anchor_ids = frozenset({"openai_gsm8k_x"})
    ok, _reason = dry_run_eligible(row, anchor_ids=anchor_ids)
    assert ok is False


def test_high_risk_excluded_without_anchor() -> None:
    row = {
        "case_id": "openai_gsm8k_z",
        "cohort": "gold_absent_tagged",
        "derived_problem_family": "money_budget",
        "problem_text": "Costs $5 and $10.",
        "notes": "recommended_next_track=reproduce_in_minimal_slice",
        "external_winner_names": "external_l1_max",
        "derivation_confidence": "heuristic_high",
    }
    ok, reason = dry_run_eligible(row, anchor_ids=frozenset())
    assert ok is False
    assert "high" in reason or "provenance" in reason


def test_fullwidth_problem_avoids_gold_substring_false_positive() -> None:
    problem = "There were 29 items. How many were lost if 2 remain?"
    p = build_prompt(problem, "quantity_ledger")
    assert validate_prompt_no_gold(p, "2")
    assert "29" not in p and "\uff12\uff19" in p


def test_manifest_no_api_if_dry_run_dir_exists() -> None:
    out_dirs = sorted(REPO.glob("outputs/targeted_discovery_retry_v1_dry_run_*"))
    if not out_dirs:
        pytest.skip("dry-run dir not generated yet")
    out = out_dirs[-1]
    manifest = json.loads((out / "targeted_retry_manifest.json").read_text(encoding="utf-8"))
    assert manifest.get("no_api_calls") is True


def test_stage3_patch_prompt_builders_exist_and_constraints() -> None:
    p1 = build_final_target_extraction_repair_prompt("A jar has 12 marbles. 5 are removed. How many remain?")
    p2 = build_tale_style_decomposition_prompt("A bag has 12 marbles. 5 are removed. How many remain?")
    for p in (p1, p2):
        low = p.lower()
        assert "final answer" in low
        assert "exactly once" in low
        assert "gold" not in low
        assert "external prediction" not in low
    assert "restat" in p1.lower() and "target" in p1.lower()
    assert "subquestion" in p2.lower() and "target_check" in p2.lower()


def test_retry_parsefix_prompt_builders_enforce_final_answer_contract() -> None:
    question = "A store has 12 apples and sells 5. How many remain?"
    prompts = [
        build_final_target_guarded_retry_prompt(question),
        build_structural_commit_challenge_retry_prompt(question),
        build_rate_table_retry_prompt(question),
        build_concise_decomposition_retry_prompt(question),
    ]
    for p in prompts:
        assert "FINAL_ANSWER: <number>" in p
        low = p.lower()
        assert "do not put units or words after the number" in low
        assert "do not give multiple final answers" in low
        assert "if the answer is a fraction or decimal" in low
        assert "if you are unsure, still output one best numeric answer" in low
        assert "gold" not in low
        assert "prior patch" not in low
        assert "best_core4" not in low


def test_dry_run_artifacts_integrity() -> None:
    out_dirs = sorted(REPO.glob("outputs/targeted_discovery_retry_v1_dry_run_*"))
    if not out_dirs:
        pytest.skip("dry-run dir not generated yet")
    out = out_dirs[-1]
    with (out / "targeted_retry_cases.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows
    for r in rows:
        pp = out / r["prompt_path"]
        assert pp.is_file()
        body = pp.read_text(encoding="utf-8")
        assert body.strip()
        gold = (r.get("gold_answer") or "").strip()
        if gold:
            assert gold not in body
            assert validate_prompt_no_gold(body, gold)
        assert "boxed" in body.lower()


def test_retry_parsefix_dry_run_prompts_contain_final_answer_literal() -> None:
    out_dirs = sorted(REPO.glob("outputs/production_equiv_v1_retry_prompt_parsefix_dry_run_*"))
    if not out_dirs:
        pytest.skip("retry parsefix dry-run dir not generated yet")
    out = out_dirs[-1]
    manifest = json.loads((out / "retry_parsefix_manifest.json").read_text(encoding="utf-8"))
    assert manifest["no_api_calls"] is True
    assert manifest["planned_calls"] <= 10
    assert manifest["no_gold_in_prompts_verified"] is True
    assert manifest["no_prediction_leakage_verified"] is True
    rows = list(csv.DictReader((out / "retry_parsefix_call_plan.csv").open(encoding="utf-8")))
    assert rows
    for r in rows:
        p = REPO / r["prompt_path"]
        assert p.exists()
        txt = p.read_text(encoding="utf-8")
        assert "FINAL_ANSWER: <number>" in txt
