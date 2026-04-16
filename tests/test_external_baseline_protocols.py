from __future__ import annotations

import json
from pathlib import Path

from scripts.generate_compute_optimal_tts_blocker_report import main as compute_blocker_main
from scripts.verify_best_route_import import verify_best_route_import
from scripts.verify_when_solve_when_verify_import import verify_when_solve_when_verify_import
from scripts.verify_cascade_routing_import import verify_cascade_routing_import
from scripts.verify_mob_import import verify_mob_import
from scripts.verify_rest_mcts_import import verify_rest_mcts_import
from scripts.verify_openr_import import verify_openr_import


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


def test_verify_cascade_routing_import_valid_fixture() -> None:
    fixture = REPO_ROOT / "tests" / "fixtures" / "cascade_routing_import_valid"
    report = verify_cascade_routing_import(
        requested_path=fixture,
        expected_dataset="routerbench",
        expected_split="test",
    )
    assert report["status"] == "valid"
    assert report["issues"] == []
    assert len(report["imported_rows"]) == 3


def test_verify_cascade_routing_import_rejects_missing_strategy_family(tmp_path: Path) -> None:
    package = tmp_path / "bad_cascade_package"
    package.mkdir(parents=True, exist_ok=True)

    metadata = {
        "source": {"type": "official"},
        "upstream": {
            "repo_url": "https://github.com/eth-sri/cascade-routing",
            "paper_url": "https://proceedings.mlr.press/v267/dekoninck25a.html",
            "workflow_stages_completed": [
                "query_generation_or_data_download",
                "dataset_preprocessing",
                "routing_and_cascading_experiment_execution",
                "postprocess_result_aggregation",
            ],
        },
        "dataset": {"name": "routerbench", "split": "test"},
        "budget": {"unit": "usd_per_query", "metric": "max_expected_cost"},
        "strategy_space": ["routing", "cascading"],
        "provenance": {
            "exported_at_utc": "2026-04-16T00:00:00Z",
            "source_uri": "https://example.org",
            "artifact_id": "x",
            "commit_or_version_if_available": "y",
        },
    }
    (package / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    (package / "results.csv").write_text(
        "mode,source_type,dataset,split,benchmark,strategy_family,max_expected_cost,quality_metric,quality_value,cost_metric,cost_value,artifact_id,commit_or_version,comparability_scope\n"
        "cascade_routing_adjacent_import,official,routerbench,test,routerbench_0shot,routing,0.003,accuracy,0.67,avg_cost_usd,0.0018,x,y,adjacent_only\n"
        "cascade_routing_adjacent_import,official,routerbench,test,routerbench_0shot,cascading,0.003,accuracy,0.69,avg_cost_usd,0.0023,x,y,adjacent_only\n",
        encoding="utf-8",
    )

    report = verify_cascade_routing_import(
        requested_path=package,
        expected_dataset="routerbench",
        expected_split="test",
    )

    assert report["status"] == "invalid"
    assert "missing_strategy_family_cascade_routing" in report["issues"]


def test_verify_mob_import_valid_fixture() -> None:
    fixture = REPO_ROOT / "tests" / "fixtures" / "mob_import_valid"
    report = verify_mob_import(
        requested_path=fixture,
        expected_benchmark="gsm8k",
        expected_gen_model="qwen2.5-3b-instruct",
        expected_reward_model="grm3b",
        expected_num_samples=128,
    )
    assert report["status"] == "valid"
    assert report["issues"] == []
    assert len(report["imported_rows"]) == 2


def test_verify_mob_import_rejects_missing_bon(tmp_path: Path) -> None:
    package = tmp_path / "bad_mob_package"
    package.mkdir(parents=True, exist_ok=True)

    metadata = {
        "source": {"type": "official"},
        "upstream": {
            "repo_url": "https://github.com/arakhsha/mob",
            "paper_url": "https://openreview.net/forum?id=aEAbRPXV37",
            "workflow_stages_completed": [
                "dataset_loading_from_jsonl_gz",
                "algorithm_evaluation_via_main_py",
                "aggregated_csv_export",
            ],
        },
        "dataset": {"benchmarks": ["gsm8k"]},
        "models": {
            "generator_models": ["qwen2.5-3b-instruct"],
            "reward_models": ["grm3b"],
        },
        "budget": {"unit": "samples", "num_samples": [128]},
        "algorithm_set": ["mob_adaptive_m"],
        "provenance": {
            "exported_at_utc": "2026-04-16T00:00:00Z",
            "source_uri": "https://example.org",
            "artifact_id": "x",
            "commit_or_version_if_available": "y",
        },
    }
    (package / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    (package / "results.csv").write_text(
        "mode,source_type,benchmark,gen_model,reward_model,num_samples,algorithm,accuracy,num_trials,artifact_id,commit_or_version,comparability_scope\n"
        "mob_adjacent_import,official,gsm8k,qwen2.5-3b-instruct,grm3b,128,mob_adaptive_m,0.761,500,x,y,adjacent_only\n",
        encoding="utf-8",
    )

    report = verify_mob_import(
        requested_path=package,
        expected_benchmark="gsm8k",
        expected_gen_model="qwen2.5-3b-instruct",
        expected_reward_model="grm3b",
        expected_num_samples=128,
    )

    assert report["status"] == "invalid"
    assert "missing_bon_algorithm" in report["issues"]


def test_verify_rest_mcts_import_valid_fixture() -> None:
    fixture = REPO_ROOT / "tests" / "fixtures" / "rest_mcts_import_valid"
    report = verify_rest_mcts_import(
        requested_path=fixture,
        expected_dataset="math",
        expected_split="test",
    )
    assert report["status"] == "valid"
    assert report["issues"] == []
    assert len(report["imported_rows"]) == 2


def test_verify_rest_mcts_import_rejects_missing_mcts_mode(tmp_path: Path) -> None:
    package = tmp_path / "bad_rest_mcts_package"
    package.mkdir(parents=True, exist_ok=True)

    metadata = {
        "source": {"type": "official"},
        "upstream": {
            "repo_url": "https://github.com/THUDM/ReST-MCTS",
            "paper_url": "https://arxiv.org/abs/2406.03816",
            "workflow_stages_completed": [
                "value_model_bootstrap_or_training",
                "mcts_trace_generation",
                "policy_self_training",
                "benchmark_evaluation",
            ],
        },
        "dataset": {"name": "math", "split": "test"},
        "models": {
            "policy_model_family": "llama3-8b-instruct",
            "value_model_family": "mistral-7b",
        },
        "search": {"iteration_limits": [50], "branch_factors": [3]},
        "self_training": {"iterations_completed": [1]},
        "provenance": {
            "exported_at_utc": "2026-04-16T00:00:00Z",
            "source_uri": "https://example.org",
            "artifact_id": "x",
            "commit_or_version_if_available": "y",
        },
    }
    (package / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    (package / "results.csv").write_text(
        "mode,source_type,dataset,split,policy_model,value_model,search_mode,self_training_iteration,iteration_limit,branch,accuracy,num_examples,artifact_id,commit_or_version,comparability_scope\n"
        "rest_mcts_adjacent_import,official,math,test,llama3-8b-instruct,mistral-7b,cot,1,50,1,0.58,500,x,y,adjacent_only\n",
        encoding="utf-8",
    )

    report = verify_rest_mcts_import(
        requested_path=package,
        expected_dataset="math",
        expected_split="test",
    )

    assert report["status"] == "invalid"
    assert "missing_mcts_search_mode" in report["issues"]


def test_verify_openr_import_valid_fixture() -> None:
    fixture = REPO_ROOT / "tests" / "fixtures" / "openr_import_valid"
    report = verify_openr_import(
        requested_path=fixture,
        expected_dataset="MATH",
        expected_split="test",
    )
    assert report["status"] == "valid"
    assert report["issues"] == []
    assert len(report["imported_rows"]) == 2


def test_verify_openr_import_rejects_missing_tree_search_method(tmp_path: Path) -> None:
    package = tmp_path / "bad_openr_package"
    package.mkdir(parents=True, exist_ok=True)

    metadata = {
        "source": {"type": "official"},
        "upstream": {
            "repo_url": "https://github.com/openreasoner/openr",
            "paper_url": "https://arxiv.org/abs/2410.09671",
            "workflow_stages_completed": [
                "lm_rm_service_startup",
                "inference_evaluation_run",
                "result_artifact_export",
            ],
        },
        "dataset": {"name": "MATH", "split": "test"},
        "models": {"generator_model": "Qwen2.5-Math-1.5B-Instruct"},
        "search": {"methods_evaluated": ["cot"]},
        "service": {"controller_addr": "http://0.0.0.0:28777"},
        "provenance": {
            "exported_at_utc": "2026-04-16T00:00:00Z",
            "source_uri": "https://example.org",
            "artifact_id": "x",
            "commit_or_version_if_available": "y",
        },
    }
    (package / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    (package / "results.csv").write_text(
        "mode,source_type,dataset,split,generator_model,reward_model,method,budget_setting,majority_vote,total_completion_tokens,artifact_id,commit_or_version,comparability_scope\n"
        "openr_adjacent_import,official,MATH,test,Qwen2.5-Math-1.5B-Instruct,dummy,cot,2^0,0.734,559.13,x,y,adjacent_only\n",
        encoding="utf-8",
    )

    report = verify_openr_import(
        requested_path=package,
        expected_dataset="MATH",
        expected_split="test",
    )

    assert report["status"] == "invalid"
    assert "missing_tree_search_method" in report["issues"]
