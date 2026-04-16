from __future__ import annotations

import json
from pathlib import Path

from scripts.generate_compute_optimal_tts_blocker_report import main as compute_blocker_main
from scripts.verify_best_route_import import verify_best_route_import
from scripts.verify_when_solve_when_verify_import import verify_when_solve_when_verify_import


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_verify_best_route_import_valid_fixture() -> None:
    fixture = REPO_ROOT / "tests" / "fixtures" / "best_route_import_valid"
    report = verify_best_route_import(
        requested_path=fixture,
        expected_dataset="gsm8k",
        expected_split="test",
        expected_budgets={1, 2},
    )
    assert report["status"] == "valid"
    assert report["issues"] == []
    assert len(report["imported_rows"]) == 2


def test_verify_best_route_import_rejects_missing_bo_gt_1(tmp_path: Path) -> None:
    package = tmp_path / "bad_best_route_package"
    package.mkdir(parents=True, exist_ok=True)

    metadata = {
        "source": {"type": "official"},
        "upstream": {
            "repo_url": "https://github.com/microsoft/best-route-llm",
            "paper_url": "https://arxiv.org/abs/2506.22716",
            "workflow_stages_completed": [
                "mixed_prompt_construction",
                "multi_sample_response_generation",
                "armoRM_scoring",
                "proxy_reward_model_scoring",
                "router_training",
            ],
        },
        "dataset": {"name": "gsm8k", "split": "test"},
        "budget": {"unit": "actions", "settings": [1]},
        "candidate_arms": [
            {"arm_id": "llama3_8b_bo1", "model_name": "llama3-8b", "best_of_n": 1}
        ],
        "provenance": {
            "exported_at_utc": "2026-04-16T00:00:00Z",
            "source_uri": "https://example.org",
            "artifact_id": "x",
            "commit_or_version_if_available": "y",
        },
    }
    (package / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    (package / "results.csv").write_text(
        "mode,source_type,dataset,split,router_strategy,budget_setting,accuracy,avg_token_cost,candidate_arm_space,comparability_scope,artifact_id,commit_or_version\n"
        "best_route_adjacent_import,official,gsm8k,test,best_route_router,budget_1,0.71,420.0,llama3_8b_bo1,adjacent_only,x,y\n",
        encoding="utf-8",
    )

    report = verify_best_route_import(
        requested_path=package,
        expected_dataset="gsm8k",
        expected_split="test",
        expected_budgets={1},
    )

    assert report["status"] == "invalid"
    assert "candidate_arms_missing_bo_gt_1" in report["issues"]


def test_compute_blocker_report_contains_future_contract(monkeypatch, tmp_path: Path) -> None:
    out_json = tmp_path / "compute_status.json"
    out_md = tmp_path / "compute_status.md"

    import sys

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "generate_compute_optimal_tts_blocker_report.py",
            "--status-json",
            str(out_json),
            "--status-md",
            str(out_md),
        ],
    )
    compute_blocker_main()

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["status"] == "blocked"
    contract = payload.get("future_official_import_contract", {})
    assert contract.get("required_files") == ["metadata.json", "results.csv"]
    assert "source.official_mapping_evidence" in contract.get("required_metadata_fields", [])


def test_verify_when_solve_when_verify_import_valid_fixture() -> None:
    fixture = REPO_ROOT / "tests" / "fixtures" / "when_solve_when_verify_import_valid"
    report = verify_when_solve_when_verify_import(
        requested_path=fixture,
        expected_dataset="math128",
        expected_split="test",
    )
    assert report["status"] == "valid"
    assert report["issues"] == []
    assert len(report["imported_rows"]) == 2


def test_verify_when_solve_when_verify_import_rejects_missing_sc(tmp_path: Path) -> None:
    package = tmp_path / "bad_sc_genrm_package"
    package.mkdir(parents=True, exist_ok=True)

    metadata = {
        "source": {"type": "official"},
        "upstream": {
            "repo_url": "https://github.com/nishadsinghi/sc-genrm-scaling",
            "paper_url": "https://arxiv.org/abs/2504.01005",
            "workflow_stages_completed": [
                "solution_generation",
                "verification_generation",
                "fixed_budget_evaluation",
            ],
        },
        "dataset": {"name": "math128", "split": "test"},
        "budget": {
            "unit": "tokens",
            "fixed_budget_interpretation": "generator_and_verifier_token_budget_joint",
        },
        "strategy_space": ["genrm_best_of_n"],
        "provenance": {
            "exported_at_utc": "2026-04-16T00:00:00Z",
            "source_uri": "https://example.org",
            "artifact_id": "x",
            "commit_or_version_if_available": "y",
        },
    }
    (package / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    (package / "results.csv").write_text(
        "mode,source_type,dataset,split,generator_model,verifier_model,strategy_family,num_solutions,num_verifications,compute_budget_tokens,success_rate,artifact_id,commit_or_version,comparability_scope\n"
        "when_solve_when_verify_adjacent_import,official,math128,test,m1,v1,genrm_best_of_n,32,16,65536,0.52,x,y,adjacent_only\n",
        encoding="utf-8",
    )

    report = verify_when_solve_when_verify_import(
        requested_path=package,
        expected_dataset="math128",
        expected_split="test",
    )

    assert report["status"] == "invalid"
    assert "missing_self_consistency_strategy" in report["issues"]
