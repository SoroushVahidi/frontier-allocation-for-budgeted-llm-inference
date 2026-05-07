from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load_module():
    p = ROOT / "scripts" / "offline_pal_path_coverage_counterfactual.py"
    spec = importlib.util.spec_from_file_location("offline_pal_path_coverage_counterfactual", p)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_counterfactual_minimal_fixture(tmp_path: Path) -> None:
    mod = _load_module()
    fx = ROOT / "tests" / "fixtures" / "offline_pal_path_coverage_counterfactual_minimal"
    out = tmp_path / "out"
    summary = mod.run_counterfactual(
        casebook_path=fx / "paired_casebook.csv",
        pal_results_path=fx / "pal_results.jsonl",
        output_dir=out,
    )
    assert summary["focus_rows"] == 3
    c = summary["counterfactual_counts"]
    assert c["selection_or_overlay_likely_loss"] == 1
    assert c["gold_available_somewhere_not_selector_pool"] == 1
    assert c["gold_absent_everywhere_detectable"] == 1
    assert c["upstream_generation_likely_loss"] == 1
    gate = summary["discovery_first_gate"]
    assert gate["would_trigger"] >= 2
    assert gate["recoverable_if_trigger"] == 1
    assert (out / "summary.json").is_file()
    assert (out / "coverage_table.csv").is_file()
    assert (out / "anchor_cases.csv").is_file()
    assert (out / "report.md").is_file()
