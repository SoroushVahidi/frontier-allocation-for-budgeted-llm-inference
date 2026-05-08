"""Tests for targeted discovery retry v2 (quantity_ledger scaffold only)."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
import subprocess

from experiments.targeted_discovery_retry import build_prompt, validate_prompt_no_gold


REPO = Path(__file__).resolve().parents[1]
V1_DRY = (
    REPO
    / "outputs/targeted_discovery_retry_v1_dry_run_20260508T010738Z"
)


def test_quantity_ledger_v2_prompt_has_fixed_increment_and_raised_salary() -> None:
    prompt = build_prompt(
        "A store changes by 20% of the original price every period and then raises a salary by 5% with a bonus half a month's salary.",
        "quantity_ledger",
        prompt_version="v2",
    )
    assert "fixed increment" in prompt.lower()
    assert "raised salary" in prompt.lower()
    # Quantity_ledger v2 template should not include ASCII digits; digits in the problem text are embedded as fullwidth.
    assert not re.search(r"[0-9]", prompt)
    assert "\\boxed" in prompt


def test_quantity_ledger_v21_prompt_has_recurrence_classification() -> None:
    prompt = build_prompt(
        "A bonus worth half a month's salary is given after a salary is raised by 5%. Compute annual total.",
        "quantity_ledger",
        prompt_version="quantity_ledger_v2_1",
    )
    pl = prompt.lower()
    assert "recurrence classification" in pl
    assert "never multiply a one-time" in pl
    assert "one-time" in pl
    # Still gold-free and final answer directive present.
    assert "\\boxed" in prompt
    assert not re.search(r"[0-9]", prompt)


def test_v2_materialization_smoke(tmp_path: Path) -> None:
    out_dir = tmp_path / "v2_dry_run"
    cmd = [
        "python3",
        str(REPO / "scripts/materialize_targeted_discovery_retry_v2.py"),
        "--output-dir",
        str(out_dir),
    ]
    subprocess.check_call(cmd, cwd=str(REPO))

    manifest = json.loads((out_dir / "targeted_retry_v2_manifest.json").read_text(encoding="utf-8"))
    assert manifest.get("no_api_calls") is True
    assert manifest.get("selected_case_count", 0) <= 15

    cases = list(csv.DictReader((out_dir / "targeted_retry_v2_cases.csv").open(encoding="utf-8")))
    assert cases
    assert len(cases) == manifest["selected_case_count"]

    for r in cases:
        prompt_path = out_dir / r["prompt_path"]
        assert prompt_path.is_file()
        prompt = prompt_path.read_text(encoding="utf-8")
        assert prompt.strip()
        assert "\\boxed" in prompt
        # Validate gold leak: prompt must not include ASCII gold answer.
        gold = (r.get("gold_answer") or "").strip()
        if gold:
            assert validate_prompt_no_gold(prompt, gold)
        if r["scaffold"] == "quantity_ledger":
            assert r["prompt_version"] == "v2"
        else:
            assert r["prompt_version"] == "v1"


def test_percent_base_denominator_v2_prompt_has_fixed_base_guard() -> None:
    prompt = build_prompt(
        "A battery loses 9% of total capacity each hour for 5 hours, then 7% of total capacity for 3 hours.",
        "percent_base_denominator_v2",
    )
    pl = prompt.lower()
    assert "fixed base for every period" in pl
    assert "base-consistency check" in pl
    assert "\\boxed" in prompt


def test_v21_materialization_smoke(tmp_path: Path) -> None:
    out_dir = tmp_path / "v21_dry_run"
    cmd = [
        "python3",
        str(REPO / "scripts/materialize_targeted_discovery_retry_v21.py"),
        "--output-dir",
        str(out_dir),
    ]
    subprocess.check_call(cmd, cwd=str(REPO))

    manifest = json.loads((out_dir / "targeted_retry_v21_manifest.json").read_text(encoding="utf-8"))
    assert manifest.get("no_api_calls") is True
    assert manifest.get("selected_case_count", 0) <= 10

    cases = list(csv.DictReader((out_dir / "targeted_retry_v21_cases.csv").open(encoding="utf-8")))
    assert cases
    assert len(cases) == manifest["selected_case_count"]

    for r in cases:
        prompt_path = out_dir / r["prompt_path"]
        assert prompt_path.is_file()
        prompt = prompt_path.read_text(encoding="utf-8")
        assert prompt.strip()
        assert "\\boxed" in prompt
        gold = (r.get("gold_answer") or "").strip()
        if gold:
            assert validate_prompt_no_gold(prompt, gold)
        if r["scaffold"] == "quantity_ledger":
            assert r["prompt_version"] == "quantity_ledger_v2_1"
            pl = prompt.lower()
            assert "recurrence classification" in pl
            assert "never multiply a one-time" in pl
        else:
            assert r["prompt_version"] == "v1"

