from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_patch_module():
    path = REPO_ROOT / "scripts" / "patch_pal_execution_pool_in_records.py"
    spec = importlib.util.spec_from_file_location("patch_pal_execution_pool_in_records", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_patch_jsonl_adds_execution_pool_row_for_pal_only(tmp_path: Path) -> None:
    mod = _load_patch_module()
    src = REPO_ROOT / "tests" / "fixtures" / "pal_poolfix_minimal"
    dst = tmp_path / "bundle"
    shutil.copytree(src, dst)
    jsonl = dst / "per_example_records.jsonl"
    pal_seen, pal_changed, cand_add, total_rows, labels = mod.patch_jsonl_inplace(jsonl)

    assert total_rows == 2
    assert pal_seen == 1
    assert pal_changed == 1
    assert cand_add >= 1
    assert "pal_answer_normalized" in labels or "pal_stdout_numeric" in labels

    lines = [json.loads(x) for x in jsonl.read_text(encoding="utf-8").splitlines() if x.strip()]
    assert lines[0]["method"] == "external_l1_max"
    assert lines[1]["method"] == mod.PAL_METHOD
    pool = lines[1]["result_metadata"]["selector_candidate_pool"]
    assert any(isinstance(r, dict) and r.get("source_id") == "pal_execution" for r in pool)


def test_main_writes_summary(tmp_path: Path) -> None:
    import sys

    mod = _load_patch_module()
    src = REPO_ROOT / "tests" / "fixtures" / "pal_poolfix_minimal"
    out = tmp_path / "bundle_out"
    argv = ["prog", "--input-dir", str(src), "--output-dir", str(out)]
    old = sys.argv
    try:
        sys.argv = argv
        mod.main()
    finally:
        sys.argv = old

    summary_path = out / "poolfix_patch_summary.json"
    assert summary_path.is_file()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["pal_rows_seen"] == 1
    assert summary["candidates_added"] >= 1
