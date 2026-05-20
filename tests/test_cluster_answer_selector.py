from __future__ import annotations

from experiments.cluster_answer_selector import (
    AnswerEvidence,
    apply_fix7_offline,
    canonicalize_answer_text,
    cluster_answers,
    compute_cluster_features,
    extract_final_answer_candidates,
)


def test_parser_cue_extraction_prefers_explicit_markers() -> None:
    text = "Reasoning...\nFinal answer: 42\n#### 42"
    cands = extract_final_answer_candidates(text)
    assert cands
    assert any(c.cue in {"final_answer", "hashes"} for c in cands)
    assert any(c.canonical.canonical_answer == "42" for c in cands)


def test_multiple_number_ambiguity_is_low_confidence() -> None:
    can = canonicalize_answer_text("I got 12 then 18 maybe", cue="numeric_fallback", explicit=False)
    assert can.ambiguous is True
    assert can.parser_confidence in {"low", "medium"}


def test_fraction_and_decimal_normalization() -> None:
    frac = canonicalize_answer_text("3/2")
    dec = canonicalize_answer_text("1.5")
    assert frac.canonical_answer == dec.canonical_answer == "1.5"


def test_currency_and_unit_handling() -> None:
    can = canonicalize_answer_text("$1,200 miles")
    assert can.canonical_answer == "1200"
    assert can.normalized_unit == "miles"


def test_answer_clustering_equivalence() -> None:
    e1 = AnswerEvidence(
        source="external_l1_max",
        source_kind="external_method",
        raw_text="1.50",
        parser_confidence="high",
        canonical_answer="1.5",
        normalized_unit=None,
    )
    e2 = AnswerEvidence(
        source="external_s1_budget_forcing",
        source_kind="external_method",
        raw_text="3/2",
        parser_confidence="high",
        canonical_answer="1.5",
        normalized_unit=None,
    )
    clusters = cluster_answers([e1, e2])
    assert len(clusters) == 1
    assert clusters[0].canonical_answer == "1.5"


def test_external_majority_realized_in_pool_condition_available() -> None:
    evs = [
        AnswerEvidence("external_l1_max", "external_method", "10", "high", "10", None),
        AnswerEvidence("external_s1_budget_forcing", "external_method", "10", "high", "10", None),
        AnswerEvidence("direct_reserve_semantic_frontier_v2", "frontier_pool", "10", "high", "10", None),
        AnswerEvidence("direct_reserve_semantic_frontier_v2", "frontier_selected", "12", "low", "12", None),
    ]
    clusters = cluster_answers(evs)
    f = []
    for c in clusters:
        f.append(
            compute_cluster_features(
                c,
                baseline_answer="12",
                frontier_answer="12",
                l1_answer="10",
                s1_answer="10",
                tale_answer="12",
                low_depth_flag=False,
                high_disagreement_flag=True,
                support_margin=0.0,
                override_reason="direct_frontier_agree",
            )
        )
    challenger = next(x for x in f if x["canonical_answer"] == "10")
    assert challenger["external_count"] >= 2
    assert challenger["frontier_count"] >= 1


def test_runtime_features_do_not_include_gold_or_exact() -> None:
    evs = [
        AnswerEvidence("external_l1_max", "external_method", "10", "high", "10", None),
        AnswerEvidence("direct_reserve_semantic_frontier_v2", "frontier_selected", "12", "low", "12", None),
    ]
    c = cluster_answers(evs)[0]
    feat = compute_cluster_features(
        c,
        baseline_answer="12",
        frontier_answer="12",
        l1_answer="10",
        s1_answer="10",
        tale_answer="12",
        low_depth_flag=False,
        high_disagreement_flag=True,
        support_margin=0.0,
        override_reason="direct_frontier_agree",
    )
    forbidden_tokens = ("gold", "exact", "correct")
    assert not any(any(tok in k.lower() for tok in forbidden_tokens) for k in feat.keys())


def test_safe_default_keep_baseline_when_weak_evidence() -> None:
    group = {
        "baseline_answer": "12",
        "cluster_features": [
            {
                "cluster_id": "C01",
                "canonical_answer": "12",
                "contains_fix24_answer": True,
                "external_count": 0,
                "frontier_count": 1,
                "independent_path_count": 1,
                "parser_confidence_mean": 2.0,
                "support_mass": 1,
                "low_depth_flag": True,
            },
            {
                "cluster_id": "C02",
                "canonical_answer": "10",
                "contains_fix24_answer": False,
                "external_count": 3,
                "frontier_count": 0,
                "independent_path_count": 0,
                "parser_confidence_mean": 2.0,
                "support_mass": 3,
                "low_depth_flag": True,
            },
        ],
    }
    d = apply_fix7_offline(group)
    assert d.override_applied is False
    assert d.selected_answer == "12"
