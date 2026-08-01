"""Deterministic GSM8K held-out sampling helpers (unit-testable without Hugging Face)."""

from __future__ import annotations

import random
from typing import Iterable


def exclusion_example_ids_from_csv_rows(rows: Iterable[dict[str, str]]) -> set[str]:
    """Collect ``example_id`` values from a gold-absent / diagnostic case-list CSV."""
    out: set[str] = set()
    for r in rows:
        eid = str(r.get("example_id", "")).strip()
        if eid:
            out.add(eid)
    return out


def held_out_sample_example_ids(
    *,
    pool_example_ids: list[str],
    exclude: set[str],
    held_out_seed: int,
    k: int,
) -> list[str]:
    """Shuffle ``sorted(unique(pool) - exclude)`` with ``held_out_seed`` and take ``k`` IDs."""
    remainder = sorted({str(x).strip() for x in pool_example_ids if str(x).strip()} - exclude)
    if len(remainder) < k:
        raise ValueError(
            f"held-out pool too small after exclusions: remainder={len(remainder)} need_k={k}"
        )
    shuffled = list(remainder)
    random.Random(held_out_seed).shuffle(shuffled)
    return shuffled[:k]
