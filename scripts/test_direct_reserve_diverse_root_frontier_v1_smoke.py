"""Integration smoke test for DirectReserveDiverseRootFrontierV1Controller.

Verifies:
- Controller instantiation and method registration
- No API calls or paid services
- Inherited functionality from DirectReserveFrontierGateV2Controller
"""

import random
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))  # noqa: E402

from experiments.branching import SimulatedBranchGenerator
from experiments.scoring import ScoreConfig, SimpleBranchScorer
from experiments.strategy_seeded_semantic_diversity_frontier_v1 import (
    DirectReserveDiverseRootFrontierV1Controller,
    METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1,
)


def test_controller_instantiation():
    """Smoke test: verify controller can be instantiated."""
    rng = random.Random(42)
    generator_factory = lambda: SimulatedBranchGenerator(  # noqa: E731
        rng=rng,
        max_depth=3,
        finish_prob_base=0.4,
        answer_noise=0.1,
    )

    scorer = SimpleBranchScorer(ScoreConfig())
    budget = 10

    controller = DirectReserveDiverseRootFrontierV1Controller(
        generator=generator_factory(),
        scorer=scorer,
        max_actions_per_problem=budget,
    )

    assert controller is not None
    print("✓ Controller instantiated successfully")


def test_controller_method_name():
    """Smoke test: verify controller has correct method_name."""
    rng = random.Random(42)
    generator_factory = lambda: SimulatedBranchGenerator(  # noqa: E731
        rng=rng,
        max_depth=3,
        finish_prob_base=0.4,
        answer_noise=0.1,
    )

    scorer = SimpleBranchScorer(ScoreConfig())
    budget = 10

    controller = DirectReserveDiverseRootFrontierV1Controller(
        generator=generator_factory(),
        scorer=scorer,
        max_actions_per_problem=budget,
    )

    assert hasattr(controller, "method_name")
    assert controller.method_name == "direct_reserve_diverse_root_frontier_v1"
    assert controller.method_name == METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1
    print("✓ Method name registered correctly")


def test_controller_attributes():
    """Smoke test: verify controller has expected attributes."""
    rng = random.Random(42)
    generator_factory = lambda: SimulatedBranchGenerator(  # noqa: E731
        rng=rng,
        max_depth=3,
        finish_prob_base=0.4,
        answer_noise=0.1,
    )

    scorer = SimpleBranchScorer(ScoreConfig())
    budget = 10

    controller = DirectReserveDiverseRootFrontierV1Controller(
        generator=generator_factory(),
        scorer=scorer,
        max_actions_per_problem=budget,
    )

    assert hasattr(controller, "_run_direct_attempt")
    assert callable(controller._run_direct_attempt)
    assert hasattr(controller, "run")
    assert callable(controller.run)
    print("✓ Controller attributes present")


def test_no_paid_services():
    """Smoke test: verify no API calls are triggered on instantiation."""
    import os

    original_keys = {
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
        "COHERE_API_KEY": os.getenv("COHERE_API_KEY"),
        "GROQ_API_KEY": os.getenv("GROQ_API_KEY"),
    }

    for key in original_keys:
        if key in os.environ:
            del os.environ[key]

    try:
        rng = random.Random(42)
        generator_factory = lambda: SimulatedBranchGenerator(  # noqa: E731
            rng=rng,
            max_depth=3,
            finish_prob_base=0.4,
            answer_noise=0.1,
        )

        scorer = SimpleBranchScorer(ScoreConfig())
        budget = 10

        controller = DirectReserveDiverseRootFrontierV1Controller(
            generator=generator_factory(),
            scorer=scorer,
            max_actions_per_problem=budget,
        )
        assert controller is not None
        print("✓ No paid API keys required for instantiation")
    finally:
        for key, val in original_keys.items():
            if val is not None:
                os.environ[key] = val


if __name__ == "__main__":
    print(
        "Running smoke tests for DirectReserveDiverseRootFrontierV1Controller...\n"
    )

    try:
        test_controller_instantiation()
        test_controller_method_name()
        test_controller_attributes()
        test_no_paid_services()
        print("\n✓ All smoke tests passed!")
        sys.exit(0)
    except Exception as e:
        print(f"\n✗ Smoke test failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
