from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path
import re


REQUIRED_VARIANTS = {
    "anti_collapse_off",
    "anti_collapse_weak",
    "anti_collapse_default",
    "anti_collapse_strong",
    "anti_collapse_conditional",
}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_anti_collapse_sweep_outputs_and_safe_language() -> None:
    ts = "20260424TTESTACALZ"
    subprocess.run(
        [
            sys.executable,
            "scripts/run_anti_collapse_calibration_sweep.py",
            "--timestamp",
            ts,
            "--seeds",
            "11",
            "--budgets",
            "4",
            "--subset-size",
            "2",
        ],
        check=True,
    )

    out_dir = Path("outputs") / f"anti_collapse_calibration_sweep_{ts}"
    required = [
        "manifest.json",
        "per_case_outcomes.csv",
        "calibration_summary.csv",
        "per_budget_summary.csv",
        "per_dataset_summary.csv",
        "per_seed_summary.csv",
        "failure_decomposition.csv",
        "mechanism_diagnostics.csv",
        "summary.md",
    ]
    for name in required:
        assert (out_dir / name).exists(), name

    summary_rows = _read_csv(out_dir / "calibration_summary.csv")
    found_variants = {str(r["variant"]) for r in summary_rows}
    assert REQUIRED_VARIANTS.issubset(found_variants)

    summary_text = (out_dir / "summary.md").read_text(encoding="utf-8").lower()
    assert "surface-sensitive" in summary_text
    assert "diagnostic" in summary_text
    assert "anti-collapse is universally beneficial" not in summary_text
    assert "anti-collapse always improves accuracy" not in summary_text


def test_anti_collapse_packager_contains_all_variants() -> None:
    subprocess.run([sys.executable, "scripts/paper/build_anti_collapse_calibration_table.py"], check=True)

    csv_path = Path("outputs/paper_tables/table_anti_collapse_calibration.csv")
    tex_path = Path("outputs/paper_tables/table_anti_collapse_calibration.tex")
    assert csv_path.exists()
    assert tex_path.exists()

    rows = _read_csv(csv_path)
    variants = {str(r["variant"]) for r in rows}
    assert REQUIRED_VARIANTS.issubset(variants)

    tex_text = tex_path.read_text(encoding="utf-8")
    assert "\\begin{tabular}" in tex_text


def test_text_regression_for_claim_revision_language() -> None:
    scan_roots = [
        Path("docs/ANTI_COLLAPSE_CALIBRATION_SWEEP_REPORT.md"),
        Path("docs/MANUSCRIPT_ANTI_COLLAPSE_CLAIM_REVISION_REPORT.md"),
        Path("manuscript_integration/neurips_claim_safe_revision_20260424T234500Z/main_results_claim_safety_table_insert.tex"),
        Path("outputs/paper_tables/table_anti_collapse_calibration.csv"),
    ]
    merged = "\n".join(p.read_text(encoding="utf-8") for p in scan_roots).lower()

    banned_literals = [
        "weaker/conditional favored",
        "anti-collapse universally improves performance",
        "every component independently improves accuracy",
    ]
    for phrase in banned_literals:
        assert phrase not in merged

    assert re.search(r"weak anti-collapse (is )?favored", merged)
    assert "conditional is worse than default" in merged
