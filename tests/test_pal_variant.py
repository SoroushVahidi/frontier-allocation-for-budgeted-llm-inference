from __future__ import annotations

import importlib.util
import random
import subprocess
import sys
from pathlib import Path

from experiments.controllers import MethodResult
from experiments.frontier_matrix_core import build_frontier_strategies, generator_factory_for_mode, load_pilot_examples
from experiments.strategy_seeded_semantic_diversity_frontier_v1 import (
    METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4_FRONTIER_TIEBREAK,
    METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4_FRONTIER_TIEBREAK_DIRECT_HYBRID,
    METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4_FRONTIER_TIEBREAK_OPCHECK,
    METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4_FRONTIER_TIEBREAK_PAL,
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


def _strong_pal_meta(ans: str = "24") -> dict[str, object]:
    return {
        "pal_code": "a=3\nb=8\nanswer=a*b\nprint(answer)",
        "pal_json_answer": "24",
        "pal_confidence": 0.9,
        "pal_execution_result": {
            "pal_parse_ok": True,
            "pal_safety_ok": True,
            "pal_exec_ok": True,
            "pal_stdout": "24\n",
            "pal_answer_raw": ans,
            "pal_answer_normalized": ans,
            "pal_error_type": "",
            "pal_error_message_sanitized": "",
        },
        "pal_candidate_answer": ans,
        "pal_parse_ok": 1,
        "pal_safety_ok": 1,
        "pal_exec_ok": 1,
        "pal_answer_parseable": 1,
        "pal_score": 0.95,
        "pal_quality_bucket": "strong",
        "pal_candidate_is_strong": 1,
    }


def test_method_registry_contains_pal() -> None:
    spec = importlib.util.spec_from_file_location("runner_mod_pal", RUNNER)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["runner_mod_pal"] = mod
    spec.loader.exec_module(mod)
    row = mod.METHODS.get("direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal")
    assert row is not None
    assert row["runtime"] == "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal"


def test_build_frontier_includes_pal_variant() -> None:
    specs = _build_specs(1)
    assert METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4_FRONTIER_TIEBREAK_PAL in specs
    ctrl = specs[METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4_FRONTIER_TIEBREAK_PAL]
    assert getattr(ctrl, "enable_pal_branch", False) is True
    assert int(getattr(ctrl, "pal_budget_actions", 0)) == 1


def test_pal_metadata_fields_present() -> None:
    specs = _build_specs(2)
    ctrl = specs[METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4_FRONTIER_TIEBREAK_PAL]
    ex = load_pilot_examples("openai/gsm8k", 7, 11)[0]
    result = ctrl.run(ex.question, ex.answer)
    md = result.metadata or {}
    assert "pal_execution" in md
    px = md["pal_execution"]
    assert "pal_parse_ok" in px
    assert "pal_safety_ok" in px
    assert "pal_exec_ok" in px
    assert "pal_candidate_is_strong" in px


def test_strong_pal_candidate_appears_in_candidate_pool_when_executed() -> None:
    specs = _build_specs(3)
    ctrl = specs[METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4_FRONTIER_TIEBREAK_PAL]
    ex = load_pilot_examples("openai/gsm8k", 11, 11)[0]
    result = ctrl.run(ex.question, ex.answer)
    md = result.metadata or {}
    if int((md.get("pal_execution") or {}).get("pal_budget_cost_observed", 0) or 0) > 0:
        pool = md.get("selector_candidate_pool") or []
        assert any(isinstance(s, dict) and str(s.get("source_family")) == "pal_seed" for s in pool)


def test_pal_candidate_can_replace_weak_fallback_no_candidate_output() -> None:
    specs = _build_specs(4)
    ctrl = specs[METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4_FRONTIER_TIEBREAK_PAL]
    ex = load_pilot_examples("openai/gsm8k", 13, 11)[0]
    ctrl._run_direct_attempt = lambda _q, _g, _i, _b: (None, 1, [])  # type: ignore[method-assign]
    ctrl._run_pal_seed_attempt = lambda _q, _g, _b: ("24", 1, _strong_pal_meta("24"), [])  # type: ignore[method-assign]
    ctrl.strict_controller_factory = lambda _remaining: type(  # type: ignore[assignment]
        "_WeakFrontier", (), {"run": lambda self, _q, _g: MethodResult("weak", None, False, 0, 0, 0, 1.0, False, {"answer_group_support_counts": {}})}
    )()
    result = ctrl.run(ex.question, ex.answer)
    ov = (result.metadata or {}).get("pal_overlay") or {}
    assert ov.get("pal_overlay_applied") is True


def test_strong_frontier_tiebreak_evidence_beats_conflicting_pal() -> None:
    specs = _build_specs(5)
    ctrl = specs[METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4_FRONTIER_TIEBREAK_PAL]
    ex = load_pilot_examples("openai/gsm8k", 16, 11)[0]
    ctrl._run_direct_attempt = lambda _q, _g, _i, _b: (None, 1, [])  # type: ignore[method-assign]
    ctrl._run_pal_seed_attempt = lambda _q, _g, _b: ("5", 1, _strong_pal_meta("5"), [])  # type: ignore[method-assign]
    ctrl.strict_controller_factory = lambda _remaining: type(  # type: ignore[assignment]
        "_StrongFrontier",
        (),
        {"run": lambda self, _q, _g: MethodResult("strong", "9", False, 1, 1, 1, 1.0, False, {"answer_group_support_counts": {"9": 3}})},
    )()
    result = ctrl.run(ex.question, ex.answer)
    ov = (result.metadata or {}).get("pal_overlay") or {}
    assert ov.get("pal_overlay_applied") is False
    assert "conflict" in str(ov.get("pal_overlay_reason", ""))


def test_failed_or_unsafe_pal_is_not_promoted() -> None:
    specs = _build_specs(6)
    ctrl = specs[METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4_FRONTIER_TIEBREAK_PAL]
    ex = load_pilot_examples("openai/gsm8k", 18, 11)[0]
    ctrl._run_direct_attempt = lambda _q, _g, _i, _b: (None, 1, [])  # type: ignore[method-assign]
    bad = _strong_pal_meta("24")
    bad["pal_exec_ok"] = 0
    bad["pal_candidate_is_strong"] = 0
    ctrl._run_pal_seed_attempt = lambda _q, _g, _b: ("24", 1, bad, [])  # type: ignore[method-assign]
    ctrl.strict_controller_factory = lambda _remaining: type(  # type: ignore[assignment]
        "_WeakFrontier", (), {"run": lambda self, _q, _g: MethodResult("weak", None, False, 0, 0, 0, 1.0, False, {"answer_group_support_counts": {}})}
    )()
    result = ctrl.run(ex.question, ex.answer)
    ov = (result.metadata or {}).get("pal_overlay") or {}
    assert ov.get("pal_overlay_applied") is False


def test_pal_scoring_and_selection_are_gold_free_contract() -> None:
    specs = _build_specs(7)
    ctrl = specs[METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4_FRONTIER_TIEBREAK_PAL]
    ex = load_pilot_examples("openai/gsm8k", 20, 11)[0]
    r1 = ctrl.run(ex.question, ex.answer)
    r2 = ctrl.run(ex.question, "999999")
    p1 = (r1.metadata or {}).get("pal_execution", {})
    p2 = (r2.metadata or {}).get("pal_execution", {})
    for k in ("pal_parse_ok", "pal_safety_ok", "pal_exec_ok", "pal_answer_parseable"):
        assert k in p1 and k in p2


def test_baseline_k1_tiebreak_unchanged_without_pal_fields() -> None:
    specs = _build_specs(8)
    base = specs[METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4_FRONTIER_TIEBREAK]
    ex = load_pilot_examples("openai/gsm8k", 9, 11)[0]
    result = base.run(ex.question, ex.answer)
    md = result.metadata or {}
    assert "pal_execution" not in md
    assert "pal_overlay" not in md


def test_baseline_k1_tiebreak_has_no_optional_seed_metadata() -> None:
    specs = _build_specs(18)
    base = specs[METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4_FRONTIER_TIEBREAK]
    ex = load_pilot_examples("openai/gsm8k", 9, 11)[0]
    md = (base.run(ex.question, ex.answer).metadata or {})
    assert "pal_execution" not in md
    assert "unit_track_execution" not in md
    assert "opcheck_execution" not in md
    assert "decomp_eq_execution" not in md


def test_unit_track_and_opcheck_behaviors_unchanged() -> None:
    specs = _build_specs(9)
    ut = specs[METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4_FRONTIER_TIEBREAK_UNIT_TRACK]
    oc = specs[METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4_FRONTIER_TIEBREAK_OPCHECK]
    ex = load_pilot_examples("openai/gsm8k", 10, 11)[0]
    md_ut = (ut.run(ex.question, ex.answer).metadata or {})
    md_oc = (oc.run(ex.question, ex.answer).metadata or {})
    assert "unit_track_execution" in md_ut
    assert "opcheck_execution" in md_oc


def test_pal_budget_and_frontier_budget_accounting_with_mocked_path() -> None:
    specs = _build_specs(19)
    ctrl = specs[METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4_FRONTIER_TIEBREAK_PAL]
    ex = load_pilot_examples("openai/gsm8k", 3, 11)[0]
    ctrl.max_actions = 3
    ctrl._run_direct_attempt = lambda _q, _g, _i, _b: (None, 1, [])  # type: ignore[method-assign]
    ctrl._run_pal_seed_attempt = lambda _q, _g, _b: ("24", 1, _strong_pal_meta("24"), [])  # type: ignore[method-assign]
    ctrl.strict_controller_factory = lambda _remaining: type(  # type: ignore[assignment]
        "_WeakFrontier",
        (),
        {"run": lambda self, _q, _g: MethodResult("weak", None, False, 1, 1, 0, 1.0, False, {"answer_group_support_counts": {}})},
    )()
    result = ctrl.run(ex.question, ex.answer)
    md = result.metadata or {}
    px = md.get("pal_execution") or {}
    assert int(px.get("pal_seed_ran", 0) or 0) == 1
    assert int(md.get("frontier_budget_before_pal", -1)) == 2
    assert int(md.get("frontier_budget_after_pal", -1)) == 1
    assert int(result.actions_used) <= int(ctrl.max_actions)


def test_pal_skips_seed_when_remaining_budget_is_zero() -> None:
    specs = _build_specs(20)
    ctrl = specs[METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4_FRONTIER_TIEBREAK_PAL]
    ex = load_pilot_examples("openai/gsm8k", 4, 11)[0]
    ctrl.max_actions = 1
    ctrl._run_direct_attempt = lambda _q, _g, _i, _b: ("7", 1, [])  # type: ignore[method-assign]
    result = ctrl.run(ex.question, ex.answer)
    md = result.metadata or {}
    assert int(md.get("remaining_budget_before_frontier", -1)) == 0
    assert int(md.get("frontier_budget_before_pal", -1)) == 0
    assert int(md.get("pal_seed_ran", 0) or 0) == 0
    assert bool(md.get("frontier_executed")) is False


def test_pal_method_does_not_activate_opcheck_or_unit_track_or_decomp_eq() -> None:
    specs = _build_specs(21)
    ctrl = specs[METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4_FRONTIER_TIEBREAK_PAL]
    ex = load_pilot_examples("openai/gsm8k", 5, 11)[0]
    md = (ctrl.run(ex.question, ex.answer).metadata or {})
    assert "opcheck_execution" not in md
    assert "unit_track_execution" not in md
    assert "decomp_eq_execution" not in md


def test_direct_hybrid_frontier_budget_respects_max_actions() -> None:
    specs = _build_specs(22)
    ctrl = specs[METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4_FRONTIER_TIEBREAK_DIRECT_HYBRID]
    ex = load_pilot_examples("openai/gsm8k", 6, 11)[0]
    ctrl.max_actions = 3
    ctrl._run_direct_attempt = lambda _q, _g, _i, _b: (None, 1, [])  # type: ignore[method-assign]
    captured: dict[str, int] = {}

    def _factory(rem: int):  # type: ignore[no-untyped-def]
        captured["remaining"] = int(rem)
        return type(
            "_Frontier",
            (),
            {"run": lambda self, _q, _g: MethodResult("f", None, False, int(rem), int(rem), 0, 1.0, False, {"answer_group_support_counts": {}})},
        )()

    ctrl.strict_controller_factory = _factory  # type: ignore[assignment]
    result = ctrl.run(ex.question, ex.answer)
    assert int(captured.get("remaining", -1)) <= int(ctrl.max_actions) - 2
    assert int(result.actions_used) <= int(ctrl.max_actions)


def test_validate_methods_only_accepts_pal_no_api() -> None:
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
            "external_l1_max,direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal",
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


def test_external_l1_max_still_registered() -> None:
    spec = importlib.util.spec_from_file_location("runner_mod_external_l1_pal", RUNNER)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["runner_mod_external_l1_pal"] = mod
    spec.loader.exec_module(mod)
    assert "external_l1_max" in mod.METHODS
    assert mod.METHODS["external_l1_max"]["runtime"] == "external_l1_max"
