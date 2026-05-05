from __future__ import annotations

import importlib.util
import json
import random
import subprocess
import sys
from pathlib import Path

from experiments.frontier_matrix_core import build_frontier_strategies, generator_factory_for_mode, load_pilot_examples
from experiments.strategy_seeded_semantic_diversity_frontier_v1 import (
    METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4_FRONTIER_TIEBREAK,
    METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4_FRONTIER_TIEBREAK_UNIT_TRACK,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER = REPO_ROOT / "scripts/run_cohere_real_model_cost_normalized_validation.py"


def _build_specs(seed: int = 0) -> dict[str, object]:
    rng = random.Random(seed)
    gen_factory = generator_factory_for_mode(False, rng, "gpt-4o-mini", 0.1, 220, 30)
    return build_frontier_strategies(
        gen_factory,
        6,
        [1],
        rng,
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
        include_external_l1_baseline=True,
        include_external_s1_baseline=True,
        include_external_tale_baseline=True,
    )


def test_method_registry_contains_unit_track() -> None:
    spec = importlib.util.spec_from_file_location("runner_mod_unit_track", RUNNER)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["runner_mod_unit_track"] = mod
    spec.loader.exec_module(mod)
    row = mod.METHODS.get("direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_unit_track")
    assert row is not None
    assert row["runtime"] == "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_unit_track"


def test_build_frontier_includes_unit_track_variant() -> None:
    specs = _build_specs()
    assert METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4_FRONTIER_TIEBREAK_UNIT_TRACK in specs
    ctrl = specs[METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4_FRONTIER_TIEBREAK_UNIT_TRACK]
    assert getattr(ctrl, "enable_frontier_max_support_tiebreak", False) is True
    assert getattr(ctrl, "enable_unit_track_seed", False) is True
    assert int(getattr(ctrl, "unit_track_seed_budget_actions", 0)) == 1


def test_unit_track_metadata_fields_present_and_budget_recorded() -> None:
    specs = _build_specs(3)
    ctrl = specs[METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4_FRONTIER_TIEBREAK_UNIT_TRACK]
    ex = load_pilot_examples("openai/gsm8k", 8, 11)[0]
    result = ctrl.run(ex.question, ex.answer)
    md = result.metadata or {}
    assert "unit_track_execution" in md
    ux = md["unit_track_execution"]
    assert "entity_ledger" in ux
    assert "target_entity" in ux
    assert "target_unit" in ux
    assert "unit_consistency_status" in ux
    assert "unit_consistency_notes" in ux
    assert "unit_tracked_answer" in ux
    assert "unit_track_score" in ux
    assert "unit_track_candidate_is_strong" in ux
    assert "unit_track_budget_cost_planned" in md
    assert "unit_track_budget_cost_observed" in md
    assert "frontier_budget_after_unit_track" in md


def test_unit_track_does_not_force_override_without_strength() -> None:
    specs = _build_specs(7)
    ctrl = specs[METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4_FRONTIER_TIEBREAK_UNIT_TRACK]
    ex = load_pilot_examples("openai/gsm8k", 12, 11)[1]
    result = ctrl.run(ex.question, ex.answer)
    md = result.metadata or {}
    overlay = md.get("unit_track_overlay", {})
    assert isinstance(overlay, dict)
    if not int((md.get("unit_track_execution") or {}).get("unit_track_candidate_is_strong", 0)):
        assert overlay.get("unit_track_overlay_applied") is False


def test_baseline_tiebreak_method_unchanged_without_unit_track_fields() -> None:
    specs = _build_specs(5)
    base = specs[METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4_FRONTIER_TIEBREAK]
    ex = load_pilot_examples("openai/gsm8k", 6, 11)[2]
    result = base.run(ex.question, ex.answer)
    md = result.metadata or {}
    assert "unit_track_execution" not in md
    assert "unit_track_overlay" not in md


def test_validate_methods_only_accepts_unit_track_no_api() -> None:
    proc = subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            "--providers",
            "cohere",
            "--datasets",
            "openai/gsm8k",
            "--budgets",
            "6",
            "--seeds",
            "20260501",
            "--methods",
            "external_l1_max,direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_unit_track",
            "--max-examples",
            "1",
            "--target-scored-per-slice",
            "1",
            "--validate-methods-only",
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_runtime_unit_track_scoring_is_gold_free_contract() -> None:
    specs = _build_specs(9)
    ctrl = specs[METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4_FRONTIER_TIEBREAK_UNIT_TRACK]
    ex = load_pilot_examples("openai/gsm8k", 4, 11)[0]
    r1 = ctrl.run(ex.question, ex.answer)
    r2 = ctrl.run(ex.question, "999999")
    u1 = (r1.metadata or {}).get("unit_track_execution", {})
    u2 = (r2.metadata or {}).get("unit_track_execution", {})
    for k in (
        "entity_ledger_present",
        "target_entity_present",
        "target_unit_present",
        "unit_tracked_answer_present",
        "unit_tracked_answer_parseable_numeric",
    ):
        assert k in u1 and k in u2


def test_external_l1_max_still_registered() -> None:
    spec = importlib.util.spec_from_file_location("runner_mod_external_l1", RUNNER)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["runner_mod_external_l1"] = mod
    spec.loader.exec_module(mod)
    assert "external_l1_max" in mod.METHODS
    assert mod.METHODS["external_l1_max"]["runtime"] == "external_l1_max"

