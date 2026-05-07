from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load_module():
    p = ROOT / "scripts" / "offline_selector_sensitivity_replay.py"
    spec = importlib.util.spec_from_file_location("offline_selector_sensitivity_replay", p)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_selector_sensitivity_replay_minimal_fixture(tmp_path: Path) -> None:
    mod = _load_module()
    fx = ROOT / "tests" / "fixtures" / "offline_selector_sensitivity_replay_minimal"
    out = tmp_path / "out"
    summary = mod.run_replay(
        broad_per_case_csv=fx / "broad_per_case.csv",
        conservative_per_case_csv=fx / "conservative_per_case.csv",
        paired_casebook_csv=fx / "paired_casebook.csv",
        output_dir=out,
    )
    assert summary["cases_total"] == 3
    assert summary["cases_analyzed_worsened_any"] == 1
    assert summary["cases_prediction_changed_any"] == 2
    bc = summary["bucket_counts"]
    assert bc["added_candidate_flip_wrong"] == 1
    assert bc.get("gold_present_improved_but_exact_worse", 0) == 0
    assert bc["override_blocked_but_selection_changed"] == 2
    assert bc["previously_correct_regressed"] == 1
    assert (out / "summary.json").is_file()
    assert (out / "per_case_delta.csv").is_file()
    assert (out / "feature_attribution_table.csv").is_file()
    assert (out / "report.md").is_file()
