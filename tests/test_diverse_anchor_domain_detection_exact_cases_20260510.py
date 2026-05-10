from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from experiments.controllers import detect_problem_domain_hint_with_source
from experiments.frontier_matrix_core import build_frontier_strategies, generator_factory_for_mode
from experiments.strategy_seeded_semantic_diversity_frontier_v1 import (
    METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4_FRONTIER_TIEBREAK_DIVERSE_ANCHOR,
)


EXACT_CASES = Path("docs/project_handoff_20260510/exact_case_replay/failure_recovery_30case_exact_cases_20260510.jsonl")


def _rows() -> list[dict]:
    out: list[dict] = []
    with EXACT_CASES.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def test_exact_case_failure_domains_map_to_detector_domains() -> None:
    rows = _rows()
    assert len(rows) == 30
    mapped = Counter()
    sources = Counter()
    for r in rows:
        q = str(r.get("question") or r.get("problem_text") or "")
        dom, src, _ev = detect_problem_domain_hint_with_source(q, explicit_domain=str(r.get("failure_domain") or ""))
        mapped[dom] += 1
        sources[src] += 1
    assert mapped["money_cost_revenue"] == 10
    assert mapped["ratio_percent"] == 10
    assert mapped["multi_step_arithmetic"] == 10
    # Exact-case metadata should be used for all 30.
    assert sources["exact_case_metadata"] == 30


def test_budget4_domain_aware_priority_executes_expected_anchors_from_exact_case_metadata(monkeypatch) -> None:
    # No API: use simulated generator factory.
    for key in ("OPENAI_API_KEY", "COHERE_API_KEY", "CO_API_KEY", "GOOGLE_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(key, raising=False)

    import random

    rng = random.Random(0)
    gen_factory = generator_factory_for_mode(False, rng, "gpt-4o-mini", 0.1, 220, 30)
    specs = build_frontier_strategies(
        gen_factory,
        4,  # budget=4 target behavior
        [1],
        rng,
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
        include_external_l1_baseline=False,
        include_external_s1_baseline=False,
        include_external_tale_baseline=False,
    )

    ctrl = specs[METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4_FRONTIER_TIEBREAK_DIVERSE_ANCHOR]

    # Force anchors to be enabled under this method.
    assert getattr(ctrl, "enable_diverse_prompt_anchors", False) is True
    assert getattr(ctrl, "enable_direct_hybrid_seed", False) is True

    # Check one representative case per slice using the explicit failure_domain label.
    reps = {
        "money/cost/revenue": ["direct_l1_anchor", "unit_ledger_money_anchor", "equation_first_anchor"],
        "ratio/proportion/percentage": ["direct_l1_anchor", "ratio_percentage_anchor", "equation_first_anchor"],
        "multi-step arithmetic": ["direct_l1_anchor", "equation_first_anchor", "backward_check_anchor"],
    }

    rows = _rows()
    for failure_domain, expected_executed in reps.items():
        row = next(r for r in rows if str(r.get("failure_domain")) == failure_domain)
        setattr(ctrl, "current_example_id", str(row.get("example_id")))
        setattr(ctrl, "current_exact_case_metadata", dict(row))
        md = ctrl.run(str(row.get("question") or ""), str(row.get("gold_answer_canonical") or row.get("gold_answer_source_raw") or "")).metadata
        assert md["domain_detection_source"] == "exact_case_metadata"
        assert md["detected_problem_domain"] in {"money_cost_revenue", "ratio_percent", "multi_step_arithmetic"}
        assert md["diverse_prompt_anchor_ids_executed"] == expected_executed
