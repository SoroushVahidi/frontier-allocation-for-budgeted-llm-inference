"""Tests for build_relation_verifier_training_dataset.py"""
from __future__ import annotations

import csv
import importlib
import io
import json
import pathlib
import sys
import tempfile

import pytest

# ---------------------------------------------------------------------------
# Import guard: must not import any network/API library
# ---------------------------------------------------------------------------
FORBIDDEN_IMPORTS = {"openai", "anthropic", "cohere", "requests", "httpx", "boto3"}


def test_no_api_imports():
    spec = importlib.util.find_spec("scripts.build_relation_verifier_training_dataset")
    if spec is None:
        # load from file path
        import importlib.util as ilu

        p = pathlib.Path("scripts/build_relation_verifier_training_dataset.py")
        src = p.read_text()
    else:
        import scripts.build_relation_verifier_training_dataset as mod

        src = pathlib.Path(mod.__file__).read_text()
    for lib in FORBIDDEN_IMPORTS:
        assert lib not in src, f"Forbidden import '{lib}' found in dataset builder"


# ---------------------------------------------------------------------------
# Fixture: minimal CSV rows
# ---------------------------------------------------------------------------

MINIMAL_ROWS = [
    {
        "row_id": "r1",
        "problem_id": "pid1",
        "case_id": "cid1",
        "split_group_id": "train",
        "candidate_source": "direct_formula_family",
        "question": "How many apples?",
        "target_phrase": "total apples",
        "target_semantic_type": "count",
        "candidate_answer": "5",
        "candidate_trace_short": "There are 5 apples.",
        "gold_answer_metadata_only": "",
        "relation_ready_label_manual": "ready",
        "first_error_axis_manual": "",
        "notes_manual": "some reviewer note",
    },
    {
        "row_id": "r2",
        "problem_id": "pid2",
        "case_id": "cid2",
        "split_group_id": "train",
        "candidate_source": "explicit_case_split_family",
        "question": "How many oranges?",
        "target_phrase": "total oranges",
        "target_semantic_type": "count",
        "candidate_answer": "3",
        "candidate_trace_short": "There are 3 oranges.",
        "gold_answer_metadata_only": "3",  # present but must not appear in features
        "relation_ready_label_manual": "not_ready",
        "first_error_axis_manual": "source_fact_missing",
        "notes_manual": "reviewer says bad",
    },
    {
        "row_id": "r3",
        "problem_id": "pid3",
        "case_id": "cid3",
        "split_group_id": "val",
        "candidate_source": "direct_formula_family",
        "question": "How many bananas?",
        "target_phrase": "total bananas",
        "target_semantic_type": "count",
        "candidate_answer": "7",
        "candidate_trace_short": "There are 7 bananas.",
        "gold_answer_metadata_only": "",
        "relation_ready_label_manual": "uncertain",
        "first_error_axis_manual": "",
        "notes_manual": "",
    },
]


def write_csv(rows: list[dict], path: pathlib.Path) -> None:
    cols = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


# ---------------------------------------------------------------------------
# Helper: import main function
# ---------------------------------------------------------------------------

def _import_builder():
    sys.path.insert(0, str(pathlib.Path("scripts").resolve().parent))
    import importlib.util as ilu

    spec = ilu.spec_from_file_location(
        "build_relation_verifier_training_dataset",
        "scripts/build_relation_verifier_training_dataset.py",
    )
    mod = ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_gold_not_in_feature_text():
    mod = _import_builder()
    row = MINIMAL_ROWS[1].copy()  # gold_answer_metadata_only = "3"
    ft = mod.build_feature_text(row)
    assert "gold_answer_metadata_only" not in ft
    # gold value "3" could legitimately appear in candidate_answer or other fields,
    # but the column name itself must not appear
    for forbidden in mod.FORBIDDEN_COLS:
        assert forbidden not in ft, f"Forbidden column '{forbidden}' leaked into feature_text"


def test_notes_not_in_feature_text():
    mod = _import_builder()
    row = MINIMAL_ROWS[0].copy()
    ft = mod.build_feature_text(row)
    assert "reviewer note" not in ft
    assert "notes_manual" not in ft


def test_uncertain_excluded_by_default():
    mod = _import_builder()
    exclude = {"uncertain", "gold_inconsistent"}
    out_rows, stats = mod.build_dataset(MINIMAL_ROWS, exclude, "binary", None)
    row_ids = [r["row_id"] for r in out_rows]
    assert "r3" not in row_ids, "uncertain row must be excluded"
    assert stats["excluded_by_label"]["uncertain"] == 1


def test_ready_not_ready_labels_map_correctly():
    mod = _import_builder()
    out_rows, stats = mod.build_dataset(MINIMAL_ROWS, {"uncertain"}, "binary", None)
    labels = {r["row_id"]: r["label"] for r in out_rows}
    assert labels["r1"] == 1, "ready → 1"
    assert labels["r2"] == 0, "not_ready → 0"


def test_dataset_report_written():
    mod = _import_builder()
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = pathlib.Path(tmpdir) / "audit.csv"
        out_dir = pathlib.Path(tmpdir) / "out"
        write_csv(MINIMAL_ROWS, csv_path)
        ret = mod.main(
            ["--input-csv", str(csv_path), "--output-dir", str(out_dir)]
        )
        assert ret == 0
        assert (out_dir / "dataset_report.md").exists()
        assert (out_dir / "train_rows.jsonl").exists()


def test_jsonl_rows_gold_free():
    mod = _import_builder()
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = pathlib.Path(tmpdir) / "audit.csv"
        out_dir = pathlib.Path(tmpdir) / "out"
        write_csv(MINIMAL_ROWS, csv_path)
        mod.main(["--input-csv", str(csv_path), "--output-dir", str(out_dir)])
        rows = []
        with open(out_dir / "train_rows.jsonl") as f:
            for line in f:
                rows.append(json.loads(line))
        for row in rows:
            ft = row["feature_text"]
            sf = row["structured_features"]
            for key in mod.FORBIDDEN_COLS:
                assert key not in ft, f"forbidden key '{key}' in feature_text"
                assert key not in sf, f"forbidden key '{key}' in structured_features"


def test_max_rows_limit():
    mod = _import_builder()
    out_rows, _ = mod.build_dataset(MINIMAL_ROWS, {"uncertain"}, "binary", max_rows=1)
    assert len(out_rows) == 1


def test_gold_inconsistent_excluded():
    mod = _import_builder()
    rows = MINIMAL_ROWS + [
        {**MINIMAL_ROWS[0], "row_id": "r_gi", "relation_ready_label_manual": "gold_inconsistent"}
    ]
    out_rows, stats = mod.build_dataset(rows, {"uncertain", "gold_inconsistent"}, "binary", None)
    ids = [r["row_id"] for r in out_rows]
    assert "r_gi" not in ids
    assert stats["excluded_by_label"]["gold_inconsistent"] == 1


def test_auxiliary_axis_in_output():
    mod = _import_builder()
    out_rows, _ = mod.build_dataset(MINIMAL_ROWS, {"uncertain"}, "binary", None)
    row2 = next(r for r in out_rows if r["row_id"] == "r2")
    assert row2["auxiliary_axis"] == "source_fact_missing"


def test_gold_answer_metadata_only_never_feature():
    """gold_answer_metadata_only must never appear as a key in structured_features."""
    mod = _import_builder()
    out_rows, _ = mod.build_dataset(MINIMAL_ROWS, {"uncertain"}, "binary", None)
    for row in out_rows:
        assert "gold_answer_metadata_only" not in row["structured_features"]
        assert "gold_answer_metadata_only" not in row["feature_text"]
