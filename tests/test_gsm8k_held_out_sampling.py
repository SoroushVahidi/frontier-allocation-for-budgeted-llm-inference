"""Unit tests for GSM8K held-out sampling (no Hugging Face)."""

from __future__ import annotations

import pytest

from experiments.gsm8k_held_out_sampling import exclusion_example_ids_from_csv_rows, held_out_sample_example_ids


def test_exclusion_example_ids_from_csv_rows_collects_and_skips_blank() -> None:
    rows = [
        {"example_id": "openai_gsm8k_1"},
        {"example_id": "  openai_gsm8k_2  "},
        {"example_id": ""},
        {"foo": "bar"},
    ]
    assert exclusion_example_ids_from_csv_rows(rows) == {"openai_gsm8k_1", "openai_gsm8k_2"}


def test_held_out_sample_deterministic_and_excludes() -> None:
    pool = [f"id_{i}" for i in range(20)]
    exclude = {f"id_{i}" for i in range(5)}
    k = 8
    seed = 20260503
    a = held_out_sample_example_ids(pool_example_ids=pool, exclude=exclude, held_out_seed=seed, k=k)
    b = held_out_sample_example_ids(pool_example_ids=pool, exclude=exclude, held_out_seed=seed, k=k)
    assert a == b
    assert len(a) == k
    assert set(a).isdisjoint(exclude)
    remainder_sorted = sorted(set(pool) - exclude)
    assert set(a).issubset(set(remainder_sorted))


def test_held_out_sample_raises_when_pool_too_small() -> None:
    pool = ["x", "y", "z"]
    exclude = {"y"}
    with pytest.raises(ValueError, match="held-out pool too small"):
        held_out_sample_example_ids(pool_example_ids=pool, exclude=exclude, held_out_seed=1, k=5)


def test_held_out_sample_stable_snapshot_order() -> None:
    """Regression guard: shuffle outcome for a fixed seed over a tiny remainder."""
    pool = ["a", "b", "c", "d", "e"]
    out = held_out_sample_example_ids(pool_example_ids=pool, exclude=set(), held_out_seed=20260503, k=5)
    assert out == ["c", "d", "e", "a", "b"]
