from experiments.diversity_needed_feasibility import DiversityNeededFeasibilityConfig, run_feasibility_pass


def test_diversity_needed_feasibility_smoke(tmp_path):
    cfg = DiversityNeededFeasibilityConfig(
        run_id="smoke_diversity_needed",
        output_dir=str(tmp_path),
        max_frontier_states=12,
        rollout_samples_per_candidate=2,
        max_allocation_samples=6,
        target_estimation_repeats=1,
    )
    metrics = run_feasibility_pass(cfg)
    assert metrics["counts"]["states"] > 0
    assert "classification" in metrics["evaluation"]
    assert "regression" in metrics["evaluation"]
