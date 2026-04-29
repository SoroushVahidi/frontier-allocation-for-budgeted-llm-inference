from pathlib import Path
import json
from scripts import collect_external_baseline_loss_cases as mod


def test_family_and_failure_classification() -> None:
    assert mod.EXTERNAL_FAMILY_MAP["external_l1_max"] == "direct_length_control"
    assert mod._classify_failure(False, False, "tale") == "unknown_no_trace"
    assert mod._classify_failure(True, False, "tale") == "trace_missing_unclassifiable"
    assert mod._classify_failure(True, True, "external_l1_max") == "external_direct_advantage"


def test_scan_dirs_includes_existing_outputs() -> None:
    dirs = mod._scan_dirs([])
    assert any("cohere_real_model_cost_normalized_validation_" in d.name for d in dirs)


def test_manifest_schema_fields_present(tmp_path: Path) -> None:
    manifest = {
        "created_at": "2026-01-01T00:00:00+00:00",
        "input_dirs": ["outputs/x"],
        "output_dir": "outputs/y",
        "counts": {"paired_cases": 1, "external_win_cases": 1},
        "coverage": {"external_l1_max": 0},
    }
    p = tmp_path / "m.json"
    p.write_text(json.dumps(manifest))
    data = json.loads(p.read_text())
    assert {"created_at", "input_dirs", "output_dir", "counts", "coverage"}.issubset(data)
