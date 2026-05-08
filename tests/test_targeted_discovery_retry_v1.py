"""Tests for offline targeted discovery retry v1 router/prompts."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from experiments.targeted_discovery_retry import (
    build_prompt,
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
