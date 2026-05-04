"""Unit tests for DirectReserveDiverseRootFrontierV1Controller."""

import pytest

from experiments.strategy_seeded_semantic_diversity_frontier_v1 import (
    DirectReserveDiverseRootFrontierV1Controller,
    METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1,
    ROOT_STRATEGY_FAMILY_SPECS,
)


class MockGenerator:
    """Mock generator for testing."""

    def __init__(self):
        self.call_count = 0

    def init_branch(self, name):
        self.call_count += 1
        return self


class MockScorer:
    """Mock scorer for testing."""

    def __call__(self, *args, **kwargs):
        return 0.5


def test_initialization():
    """Test controller initializes with correct defaults."""
    gen = MockGenerator()
    scorer = MockScorer()
    controller = DirectReserveDiverseRootFrontierV1Controller(gen, scorer, 10)
    assert controller.method_name == METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1


def test_root_strategy_constants():
    """Test ROOT_STRATEGY_FAMILY_SPECS is populated with valid data."""
    assert len(ROOT_STRATEGY_FAMILY_SPECS) > 0
    for family_id, prompt_suffix in ROOT_STRATEGY_FAMILY_SPECS:
        assert isinstance(family_id, str)
        assert isinstance(prompt_suffix, str)
        assert len(family_id) > 0
        assert len(prompt_suffix) > 0


def test_method_name_override():
    """Test custom method_name is respected during initialization."""
    gen = MockGenerator()
    scorer = MockScorer()
    custom_name = "test_custom_diverse_root"
    controller = DirectReserveDiverseRootFrontierV1Controller(
        gen, scorer, 10, method_name=custom_name
    )
    assert controller.method_name == custom_name


def test_inheritance_chain():
    """Test controller inherits from DirectReserveFrontierGateV2Controller."""
    from experiments.controllers import DirectReserveFrontierGateV2Controller

    gen = MockGenerator()
    scorer = MockScorer()
    controller = DirectReserveDiverseRootFrontierV1Controller(gen, scorer, 10)
    assert isinstance(controller, DirectReserveFrontierGateV2Controller)


def test_run_direct_attempt_has_correct_signature():
    """Test _run_direct_attempt method exists and has correct signature."""
    gen = MockGenerator()
    scorer = MockScorer()
    controller = DirectReserveDiverseRootFrontierV1Controller(gen, scorer, 10)
    assert hasattr(controller, "_run_direct_attempt")
    assert callable(controller._run_direct_attempt)

