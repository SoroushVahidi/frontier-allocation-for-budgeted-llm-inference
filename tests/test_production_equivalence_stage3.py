from __future__ import annotations

import csv
import json
import random
import subprocess
import sys
from pathlib import Path

from experiments.frontier_matrix_core import build_frontier_strategies
from experiments.call_accounting import compute_call_accounting
from experiments.targeted_discovery_retry import (
    build_production_equivalence_stage3_config,
)
from scripts.run_cohere_real_model_cost_normalized_validation import METHODS

REPO = Path(__file__).resolve().parents[1]
ALIAS = (
    "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal_"
    "structural_commit_v1_production_equiv_v1"
)


def test_new_alias_registered_and_resolvable() -> None:
    assert ALIAS in METHODS
    assert METHODS[ALIAS]["runtime"] == ALIAS
    rng = random.Random(0)
    specs = build_frontier_strategies(
        lambda: None,
        budget=4,
        adaptive_min_expand_grid=[1],
        rng=rng,
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
        include_external_l1_baseline=True,
        include_external_s1_baseline=True,
        include_external_tale_baseline=True,
    )
    assert ALIAS in specs
    assert "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal_structural_commit_v1" in specs


def test_production_equivalence_config_defaults() -> None:
    cfg = build_production_equivalence_stage3_config()
    assert cfg.enable_structural_commit_v1 is True
    assert cfg.enable_adaptive_retry_router_v3 is True
    assert cfg.enable_final_target_verifier_v1 is True
    assert cfg.enable_targeted_retry is True
    assert cfg.targeted_retry_max_extra_calls == 1
    assert cfg.no_api_mode is True
    assert cfg.enable_percent_base_denominator is False
    assert cfg.enable_discovery3_candidate_diversity_selection_v1 is False
    assert cfg.method_alias.endswith("production_equiv_v1")
    assert "final_target_extraction_repair" in cfg.targeted_retry_allowed_scaffolds
    assert "l1_style_concise_decomposition" in cfg.targeted_retry_allowed_scaffolds
    assert "tale_style_decomposition" not in cfg.targeted_retry_allowed_scaffolds


def test_production_equivalence_dry_run_outputs() -> None:
    out = REPO / "outputs" / "production_equiv_v1_runtime_wired_stage3_50_dry_run_test"
    if out.exists():
        for p in sorted(out.rglob("*"), reverse=True):
            if p.is_file():
                p.unlink()
            elif p.is_dir():
                p.rmdir()
    cmd = [
        sys.executable,
        "scripts/run_production_equivalence_stage3_dry_run.py",
        "--output-dir",
        str(out),
    ]
    subprocess.run(cmd, cwd=REPO, check=True, capture_output=True, text=True)

    manifest = json.loads((out / "production_equiv_v1_runtime_manifest.json").read_text(encoding="utf-8"))
    summary = json.loads((out / "production_equiv_v1_runtime_summary.json").read_text(encoding="utf-8"))
    rows = list(csv.DictReader((out / "production_equiv_v1_runtime_cases.csv").open(encoding="utf-8")))
    plan_rows = list(csv.DictReader((out / "production_equiv_v1_runtime_call_plan.csv").open(encoding="utf-8")))

    assert manifest["no_api_calls"] is True
    assert summary["no_api_calls"] is True
    assert len(rows) == 50
    assert summary["case_count"] == 50
    assert len(plan_rows) == 50
    assert summary["estimated_total_calls"] <= 100
    assert rows[0]["production_equiv_v1_enabled"] == "True"
    assert rows[0]["runtime_targeted_retry_enabled"] == "True"
    assert "production_equiv_surface_source" in rows[0]
    assert "production_equiv_excluded_patches" in rows[0]
    assert summary["runtime_targeted_retry_hook_wired"] is True
    assert summary["surface_parity_source_wired"] is True
    assert manifest["runtime_targeted_retry_hook_wired"] is True
    assert manifest["surface_parity_source_wired"] is True
    assert manifest["enable_discovery3_candidate_diversity_selection_v1"] is False


def test_call_accounting_detects_cap_hit_mismatch() -> None:
    acct = compute_call_accounting(
        completed_rows=20,
        total_rows=50,
        cap_error_count=30,
        per_case_calls_sum=41,
        budget_snapshot={"budget": 80, "consumed": 80},
        inferred_from_errors=80,
    )
    assert acct.actual_cohere_calls_completed_rows == 41
    assert acct.actual_cohere_calls_run_level == 80
    assert acct.global_cap_reached is True
    assert acct.cap_error_count == 30
    assert acct.completed_rows == 20
    assert acct.incomplete_rows == 30
    assert "cap_enforcer" in acct.call_accounting_source
    assert "run-level logical call consumption differs" in acct.call_accounting_warning
