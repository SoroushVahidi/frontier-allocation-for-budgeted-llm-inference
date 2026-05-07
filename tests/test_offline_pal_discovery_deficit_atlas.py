from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load_module():
    p = ROOT / "scripts" / "offline_pal_discovery_deficit_atlas.py"
    spec = importlib.util.spec_from_file_location("offline_pal_discovery_deficit_atlas", p)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_discovery_deficit_atlas_minimal(tmp_path: Path) -> None:
    mod = _load_module()
    fx = ROOT / "tests" / "fixtures" / "offline_pal_discovery_deficit_atlas_minimal"
    out = tmp_path / "out"
    summary = mod.run_atlas(
        casebook_path=fx / "paired_casebook.csv",
        pal_results_path=fx / "pal_results.jsonl",
        output_dir=out,
    )
    assert summary["focus_rows"] == 3
    stage_counts = summary["stage_counts"]
    assert stage_counts["gold_in_direct_attempts"] >= 1
    assert stage_counts["gold_in_execution_only"] >= 1
    assert stage_counts["gold_absent_all_detectable"] >= 1
    assert (out / "summary.json").is_file()
    assert (out / "deficit_archetype_table.csv").is_file()
    assert (out / "anchor_cases.csv").is_file()
    assert (out / "report.md").is_file()
