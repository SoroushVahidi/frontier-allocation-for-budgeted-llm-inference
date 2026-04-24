from __future__ import annotations

import runpy
from pathlib import Path


def test_canonical_runner_includes_claim_safety_builder() -> None:
    module_globals = runpy.run_path(str(Path("scripts/paper/run_all_neurips_paper_artifacts.py")))
    scripts = module_globals["SCRIPTS"]
    assert "build_claim_safety_statistical_table.py" in scripts


def test_compatibility_runner_points_to_canonical() -> None:
    text = Path("scripts/paper/run_all_neurips_artifacts.py").read_text(encoding="utf-8")
    assert "run_all_neurips_paper_artifacts.py" in text
