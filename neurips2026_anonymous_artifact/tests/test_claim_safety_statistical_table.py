from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "paper" / "build_claim_safety_statistical_table.py"


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_build_claim_safety_statistical_table_outputs_and_wording(tmp_path: Path) -> None:
    pairwise_path = tmp_path / "pairwise_statistical_tests.csv"
    rows = [
        {
            "evidence_layer": "matched_surface_simulation",
            "provider": "simulation",
            "dataset": "openai/gsm8k",
            "budget": 4,
            "method_a": "strict_f3",
            "method_b": "strict_gate1_cap_k6",
            "comparison_rule": "required",
            "n_paired": 120,
            "accuracy_a": 0.64,
            "accuracy_b": 0.61,
            "mean_difference": 0.03,
            "bootstrap_ci_low": -0.09,
            "bootstrap_ci_high": 0.15,
            "permutation_p_value": 0.69,
            "win_count": 31,
            "tie_count": 62,
            "loss_count": 27,
            "interpretation": "difference fragile / not statistically decisive",
        },
        {
            "evidence_layer": "matched_surface_simulation",
            "provider": "simulation",
            "dataset": "openai/gsm8k",
            "budget": 4,
            "method_a": "strict_f3",
            "method_b": "external_l1_max",
            "comparison_rule": "required",
            "n_paired": 120,
            "accuracy_a": 0.64,
            "accuracy_b": 0.53,
            "mean_difference": 0.11,
            "bootstrap_ci_low": 0.01,
            "bootstrap_ci_high": 0.22,
            "permutation_p_value": 0.03,
            "win_count": 40,
            "tie_count": 50,
            "loss_count": 30,
            "interpretation": "strict_f3 statistically stronger",
        },
        {
            "evidence_layer": "matched_surface_simulation",
            "provider": "simulation",
            "dataset": "openai/gsm8k",
            "budget": 4,
            "method_a": "strict_gate1_cap_k6",
            "method_b": "external_l1_max",
            "comparison_rule": "required",
            "n_paired": 120,
            "accuracy_a": 0.61,
            "accuracy_b": 0.53,
            "mean_difference": 0.08,
            "bootstrap_ci_low": -0.03,
            "bootstrap_ci_high": 0.19,
            "permutation_p_value": 0.11,
            "win_count": 35,
            "tie_count": 55,
            "loss_count": 30,
            "interpretation": "difference fragile / not statistically decisive",
        },
        {
            "evidence_layer": "real_model_ours_vs_external",
            "provider": "openai",
            "dataset": "openai/gsm8k",
            "budget": 4,
            "method_a": "strict_f3",
            "method_b": "strict_gate1_cap_k6",
            "comparison_rule": "required",
            "n_paired": 25,
            "accuracy_a": 0.64,
            "accuracy_b": 0.63,
            "mean_difference": 0.01,
            "bootstrap_ci_low": -0.20,
            "bootstrap_ci_high": 0.20,
            "permutation_p_value": 0.8,
            "win_count": 4,
            "tie_count": 16,
            "loss_count": 5,
            "interpretation": "difference fragile / not statistically decisive",
        },
    ]
    _write_csv(pairwise_path, rows)

    out_csv = tmp_path / "table_claim_safety_statistical_tests.csv"
    out_tex = tmp_path / "table_claim_safety_statistical_tests.tex"
    out_plot = tmp_path / "claim_safety_statistical_tests.csv"

    subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--pairwise-input",
            str(pairwise_path),
            "--output-csv",
            str(out_csv),
            "--output-tex",
            str(out_tex),
            "--output-plot-csv",
            str(out_plot),
        ],
        check=True,
    )

    assert out_csv.exists()
    assert out_tex.exists()
    assert out_plot.exists()

    out_rows = _read_csv(out_csv)
    assert out_rows

    pair_set = {(r["method A"], r["method B"]) for r in out_rows}
    assert ("strict_f3", "strict_gate1_cap_k6") in pair_set
    assert ("strict_f3", "external_l1_max") in pair_set
    assert ("strict_gate1_cap_k6", "external_l1_max") in pair_set

    target = [r for r in out_rows if r["method A"] == "strict_f3" and r["method B"] == "strict_gate1_cap_k6"]
    assert target
    assert any("fragile" in r["interpretation"].lower() or "not statistically decisive" in r["interpretation"].lower() for r in target)

    all_text = out_csv.read_text(encoding="utf-8").lower() + "\n" + out_tex.read_text(encoding="utf-8").lower()
    assert "statistically dominates" not in all_text
    assert "universally dominates" not in all_text

    assert all(r["evidence layer"] == "matched_surface_simulation" for r in out_rows)
