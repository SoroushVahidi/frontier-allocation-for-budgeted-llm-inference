import json
from pathlib import Path
import tempfile

from scripts.synthetic_corruption_scaffold import (
    generate_corruptions_from_rows,
    write_jsonl,
    load_jsonl,
)


def _make_fixture_rows():
    return [
        {"case_id": "c1", "candidate_id": "r1", "candidate_formula": "a + b"},
        {"case_id": "c2", "candidate_id": "r2", "candidate_formula": "100 / x"},
        {"case_id": "c3", "candidate_id": "r3", "candidate_formula": "y * 12"},
    ]


def test_generate_corruptions_deterministic(tmp_path: Path):
    rows = _make_fixture_rows()
    out1 = generate_corruptions_from_rows(rows, seed=0, n_per_row=2)
    out2 = generate_corruptions_from_rows(rows, seed=0, n_per_row=2)
    assert out1 == out2
    # Each output row should contain corruption_type and corrupted_formula
    assert all("corruption_type" in r and "corrupted_formula" in r for r in out1)


def test_cli_roundtrip(tmp_path: Path):
    rows = _make_fixture_rows()
    in_path = tmp_path / "in.jsonl"
    out_path = tmp_path / "out.jsonl"
    write_jsonl(str(in_path), rows)
    # call core function rather than subprocess
    loaded = load_jsonl(str(in_path))
    out_rows = generate_corruptions_from_rows(loaded, seed=7, n_per_row=1)
    write_jsonl(str(out_path), out_rows)
    assert out_path.exists()
    loaded_out = load_jsonl(str(out_path))
    assert len(loaded_out) >= 1
    assert all("corruption_type" in r for r in loaded_out)
