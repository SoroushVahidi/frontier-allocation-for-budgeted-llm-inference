from __future__ import annotations

import argparse

from scripts.run_cohere_real_model_cost_normalized_validation import validate_methods_only


def test_validate_methods_only_includes_outcome_verifier_rerank_runnable(tmp_path):
    args = argparse.Namespace(
        timestamp="TEST_OV_RERANK_VALIDATE",
        output_root=str(tmp_path),
    )
    try:
        validate_methods_only(
            args=args,
            providers=["cohere"],
            budgets=[4],
            methods=["direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1"],
        )
    except SystemExit as exc:
        assert exc.code == 0
