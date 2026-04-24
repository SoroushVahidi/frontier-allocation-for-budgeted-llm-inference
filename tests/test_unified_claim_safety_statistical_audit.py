from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REQUIRED = [
    "manifest.json",
    "artifact_inventory.csv",
    "artifact_limitations.csv",
    "claim_safety_table.csv",
    "pairwise_statistical_tests.csv",
    "winner_instability_by_surface.csv",
    "real_model_vs_simulation_consistency.csv",
    "token_latency_accounting_summary.csv",
    "component_ablation_claim_support.csv",
    "manuscript_recommended_wording.json",
    "STATUS.md",
]


def test_unified_claim_safety_audit_minimal_synthetic(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    (repo / "outputs/matched_surface_multiseed_main_comparison_20260101T000000Z").mkdir(parents=True)
    (repo / "docs").mkdir(parents=True)

    source_script = Path(__file__).resolve().parents[1] / "scripts/build_unified_claim_safety_statistical_audit.py"
    (repo / "scripts/build_unified_claim_safety_statistical_audit.py").write_text(source_script.read_text(encoding="utf-8"), encoding="utf-8")

    raw_csv = repo / "outputs/matched_surface_multiseed_main_comparison_20260101T000000Z/raw_case_results.csv"
    raw_csv.write_text(
        "dataset,seed,budget,example_id,method,is_correct\n"
        "openai/gsm8k,11,4,1,strict_f3,1\n"
        "openai/gsm8k,11,4,1,strict_gate1_cap_k6,0\n"
        "openai/gsm8k,11,4,1,external_l1_max,0\n"
        "openai/gsm8k,11,4,2,strict_f3,0\n"
        "openai/gsm8k,11,4,2,strict_gate1_cap_k6,1\n"
        "openai/gsm8k,11,4,2,external_l1_max,0\n",
        encoding="utf-8",
    )

    ts = "20260424T190000Z_TEST"
    cmd = [
        sys.executable,
        str(repo / "scripts/build_unified_claim_safety_statistical_audit.py"),
        "--repo-root",
        str(repo),
        "--timestamp",
        ts,
        "--bootstrap-samples",
        "200",
        "--permutation-samples",
        "400",
    ]
    subprocess.run(cmd, check=True)

    out_dir = repo / f"outputs/unified_claim_safety_statistical_audit_{ts}"
    assert out_dir.exists()
    for rel in REQUIRED:
        assert (out_dir / rel).exists(), rel

    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["offline_only"] is True
    assert manifest["api_required"] is False


def test_unified_claim_safety_handles_missing_families(tmp_path: Path) -> None:
    repo = tmp_path / "repo2"
    (repo / "scripts").mkdir(parents=True)
    (repo / "outputs").mkdir(parents=True)
    (repo / "docs").mkdir(parents=True)

    source_script = Path(__file__).resolve().parents[1] / "scripts/build_unified_claim_safety_statistical_audit.py"
    (repo / "scripts/build_unified_claim_safety_statistical_audit.py").write_text(source_script.read_text(encoding="utf-8"), encoding="utf-8")

    ts = "20260424T190100Z_EMPTY"
    subprocess.run(
        [
            sys.executable,
            str(repo / "scripts/build_unified_claim_safety_statistical_audit.py"),
            "--repo-root",
            str(repo),
            "--timestamp",
            ts,
        ],
        check=True,
    )

    out_dir = repo / f"outputs/unified_claim_safety_statistical_audit_{ts}"
    assert out_dir.exists()
    assert (out_dir / "artifact_limitations.csv").exists()
    text = (out_dir / "artifact_limitations.csv").read_text(encoding="utf-8")
    assert "missing" in text
