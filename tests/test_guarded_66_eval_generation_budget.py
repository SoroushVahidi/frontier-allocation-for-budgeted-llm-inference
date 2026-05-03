"""Budget / CLI guards for Cohere pilot hooks on the guarded 66-case evaluator (no network)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from experiments.branching import APIBranchGenerator, configure_logical_api_call_budget
from experiments.frontier_matrix_core import resolve_api_key_for_provider

REPO_ROOT = Path(__file__).resolve().parents[1]
EVAL_SCRIPT = REPO_ROOT / "scripts" / "run_diverse_root_frontier_v1_66_eval_with_guarded.py"


@pytest.fixture(autouse=True)
def _reset_logical_api_budget() -> None:
    configure_logical_api_call_budget(None)
    yield
    configure_logical_api_call_budget(None)


def test_logical_api_budget_blocks_extra_calls() -> None:
    configure_logical_api_call_budget(2)
    gen = APIBranchGenerator(
        api_key="test-key",
        model="m",
        temperature=0.1,
        max_tokens=8,
        timeout_seconds=5,
        provider="openai",
    )
    with patch.object(APIBranchGenerator, "_call_responses_api", return_value="{}"):
        gen._call_api({}, "p1")
        gen._call_api({}, "p2")
        with pytest.raises(RuntimeError, match="Global logical API call cap"):
            gen._call_api({}, "p3")


def test_generation_dry_run_exits_without_hf_or_api() -> None:
    proc = subprocess.run(
        [sys.executable, str(EVAL_SCRIPT), "--generation-dry-run", "--limit", "2"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "GENERATION DRY RUN" in proc.stdout
    assert "Planned cases after --limit: 2" in proc.stdout


def test_real_generation_requires_api_key() -> None:
    env = os.environ.copy()
    env.pop("COHERE_API_KEY", None)
    env.pop("CO_API_KEY", None)
    proc = subprocess.run(
        [
            sys.executable,
            str(EVAL_SCRIPT),
            "--real-generation",
            "--max-total-api-calls",
            "10",
            "--limit",
            "1",
            "--timestamp",
            "TEST_SHOULD_NOT_RUN",
        ],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0
    out = proc.stdout + proc.stderr
    assert "API key missing" in out


def test_resolve_api_key_cohere_prefers_primary_then_co_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("COHERE_API_KEY", raising=False)
    monkeypatch.delenv("CO_API_KEY", raising=False)
    assert resolve_api_key_for_provider("cohere") is None
    monkeypatch.setenv("CO_API_KEY", "alias-key")
    assert resolve_api_key_for_provider("cohere") == "alias-key"
    monkeypatch.setenv("COHERE_API_KEY", "primary-key")
    assert resolve_api_key_for_provider("cohere") == "primary-key"


def test_real_generation_requires_positive_call_cap() -> None:
    env = {**os.environ, "COHERE_API_KEY": "dummy-not-used"}
    proc = subprocess.run(
        [
            sys.executable,
            str(EVAL_SCRIPT),
            "--real-generation",
            "--limit",
            "1",
            "--timestamp",
            "TEST_SHOULD_NOT_RUN",
        ],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0
    assert "max-total-api-calls" in (proc.stdout + proc.stderr).lower()
