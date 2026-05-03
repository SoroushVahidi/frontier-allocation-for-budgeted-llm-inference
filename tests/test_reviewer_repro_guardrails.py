from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.outcome_verifier_answer_group_selector import score_item, stable_score_seed


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_reviewer_first_doc_exists_and_points_to_safe_commands():
    text = (REPO_ROOT / "REVIEWER_FIRST.md").read_text(encoding="utf-8")
    assert "make health" in text
    assert "make reviewer-test" in text
    assert "make selector-test" in text
    assert "external_l1_max" in text
    assert "Do not treat missing-score fallback behavior" in text


def test_selected_selector_config_stays_cache_based_and_recovery_scoped():
    cfg = json.loads((REPO_ROOT / "configs" / "selected_selector_current.json").read_text(encoding="utf-8"))
    assert cfg["selector_name"] == "outcome_verifier_answer_group_selector_v1"
    assert cfg["scorer_mode"] == "cached_jsonl"
    assert cfg["require_trace_for_override"] is True
    assert cfg["dedupe_verifier_items"] is True
    assert "recovery" in cfg["status"].lower()
    assert "runtime" in cfg["status"].lower()


def test_outcome_selector_live_api_mode_is_not_silent_missing_scores():
    item = {"case_id": "case-a", "candidate_id": "cand-b"}
    with pytest.raises(ValueError, match="does not perform live API scoring"):
        score_item(item, "api")


def test_mock_score_seed_is_stable_and_content_based():
    item = {"case_id": "case-a", "candidate_id": "cand-b"}
    assert stable_score_seed(item) == stable_score_seed(dict(item))
    assert score_item(item, "mock_oracle_disabled_random_safe") == score_item(dict(item), "mock_oracle_disabled_random_safe")


def test_optional_api_dependency_extra_is_declared_without_making_it_default():
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "api = [" in pyproject
    assert "cohere>=5.0" in pyproject
    dependencies_block = pyproject.split("dependencies = [", 1)[1].split("]", 1)[0]
    assert "cohere" not in dependencies_block.lower()


def test_ci_workflow_runs_reviewer_safe_subset():
    workflow = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "make health" in workflow
    assert "make reviewer-test" in workflow
    assert "make selector-test" in workflow
    assert "python -m pip install -e .[dev]" in workflow
