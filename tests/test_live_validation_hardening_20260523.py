from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from scripts import run_cohere_real_model_cost_normalized_validation as runner

REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def test_failure_taxonomy_classifier_covers_key_categories() -> None:
    assert runner.classify_failure_taxonomy_row({"error": "HTTPError 500: upstream"}) == "HTTP 500"
    assert runner.classify_failure_taxonomy_row({"error": "Read timeout while waiting"}) == "timeout"
    assert runner.classify_failure_taxonomy_row({"error": "HTTPError 429: too many requests"}) == "rate limit"
    assert runner.classify_failure_taxonomy_row({"status": "scored", "parse_extraction_failure": 1}) == "parse failure"
    assert runner.classify_failure_taxonomy_row({"status": "scored", "final_answer_raw": "abc", "final_answer_canonical": ""}) == "unparseable answer"
    assert runner.classify_failure_taxonomy_row({"error": "returned no text output"}) == "provider response error"


def test_build_failure_taxonomy_outputs_includes_example_ids_only_in_machine_readable() -> None:
    failures = [
        {"dataset": "openai/gsm8k", "method": "external_l1_max", "example_id": "e1", "error": "HTTPError 500: boom", "status": "failed"},
        {"dataset": "openai/gsm8k", "method": "external_l1_max", "example_id": "e2", "error": "HTTPError 429: retry", "status": "failed"},
    ]
    records = [
        {"dataset": "openai/gsm8k", "method": "external_l1_max", "example_id": "e3", "status": "scored", "scored": 1, "parse_extraction_failure": 1}
    ]
    out_json, out_rows = runner.build_failure_taxonomy_outputs(records=records, failures=failures)
    assert out_json["counts_by_category"]["HTTP 500"] == 1
    assert out_json["counts_by_category"]["rate limit"] == 1
    assert out_json["counts_by_category"]["parse failure"] == 1
    assert "e1" in out_json["example_ids_by_category"]["HTTP 500"]
    assert any(r["failure_category"] == "HTTP 500" and "e1" in r["example_ids_json"] for r in out_rows)


def test_dry_run_call_plan_does_not_require_cohere_api_key(tmp_path: Path) -> None:
    exact_cases = tmp_path / "exact_cases.jsonl"
    _write_jsonl(
        exact_cases,
        [
            {
                "example_id": "case_1",
                "dataset": "openai/gsm8k",
                "question": "What is 2 + 2?",
                "gold_answer_canonical": "4",
            }
        ],
    )
    out_root = tmp_path / "out"
    cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts/run_cohere_real_model_cost_normalized_validation.py"),
        "--timestamp",
        "TEST_DRYRUN_NO_KEY_20260523T000000Z",
        "--providers",
        "cohere",
        "--datasets",
        "openai/gsm8k",
        "--seeds",
        "11",
        "--budgets",
        "6",
        "--methods",
        "external_l1_max",
        "--target-scored-per-slice",
        "1",
        "--max-examples",
        "1",
        "--exact-cases-jsonl",
        str(exact_cases),
        "--dry-run-call-plan",
        "--output-root",
        str(out_root),
    ]
    env = dict(os.environ)
    env.pop("COHERE_API_KEY", None)
    env.pop("CO_API_KEY", None)
    proc = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True, check=False, env=env)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    dry_plan = out_root / "cohere_real_model_cost_normalized_validation_TEST_DRYRUN_NO_KEY_20260523T000000Z" / "dry_run_call_plan.json"
    assert dry_plan.exists()
    payload = json.loads(dry_plan.read_text(encoding="utf-8"))
    assert payload["provider_status"]["cohere"]["reason"] == "dry_run_call_plan_offline_no_readiness_probe"
    assert payload["total_planned_case_rows"] == 1


def test_dry_run_call_plan_supports_mistral_without_key(tmp_path: Path) -> None:
    exact_cases = tmp_path / "exact_cases.jsonl"
    _write_jsonl(
        exact_cases,
        [
            {
                "example_id": "case_1",
                "dataset": "openai/gsm8k",
                "question": "What is 2 + 2?",
                "gold_answer_canonical": "4",
            }
        ],
    )
    out_root = tmp_path / "out"
    cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts/run_cohere_real_model_cost_normalized_validation.py"),
        "--timestamp",
        "TEST_DRYRUN_MISTRAL_20260523T000000Z",
        "--providers",
        "mistral",
        "--datasets",
        "openai/gsm8k",
        "--seeds",
        "11",
        "--budgets",
        "6",
        "--methods",
        "external_l1_max",
        "--target-scored-per-slice",
        "1",
        "--max-examples",
        "1",
        "--exact-cases-jsonl",
        str(exact_cases),
        "--dry-run-call-plan",
        "--mistral-model",
        "mistral-small-latest",
        "--output-root",
        str(out_root),
    ]
    env = dict(os.environ)
    env.pop("MISTRAL_API_KEY", None)
    proc = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True, check=False, env=env)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    dry_plan = out_root / "cohere_real_model_cost_normalized_validation_TEST_DRYRUN_MISTRAL_20260523T000000Z" / "dry_run_call_plan.json"
    assert dry_plan.exists()
    payload = json.loads(dry_plan.read_text(encoding="utf-8"))
    assert payload["provider_status"]["mistral"]["reason"] == "dry_run_call_plan_offline_no_readiness_probe"
    assert payload["total_planned_case_rows"] == 1
