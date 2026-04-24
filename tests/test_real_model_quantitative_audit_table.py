from __future__ import annotations

import csv
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_build_real_model_quantitative_audit_table_outputs() -> None:
    cmd = [sys.executable, "scripts/paper/build_real_model_quantitative_audit_table.py"]
    subprocess.run(cmd, cwd=REPO_ROOT, check=True)

    table_csv = REPO_ROOT / "outputs/paper_tables/table_real_model_quantitative_audit.csv"
    table_tex = REPO_ROOT / "outputs/paper_tables/table_real_model_quantitative_audit.tex"
    plot_csv = REPO_ROOT / "outputs/paper_plot_data/real_model_quantitative_audit.csv"
    pairwise_csv = REPO_ROOT / "outputs/paper_tables/table_real_model_quantitative_audit_pairwise.csv"
    sources_csv = REPO_ROOT / "outputs/paper_tables/table_real_model_quantitative_audit_sources.csv"

    for path in [table_csv, table_tex, plot_csv, pairwise_csv, sources_csv]:
        assert path.exists(), str(path)

    rows = _read_csv(table_csv)
    assert rows, "table_real_model_quantitative_audit.csv must be non-empty"
    required_cols = {
        "provider",
        "model",
        "dataset",
        "budget",
        "method",
        "paired_n",
        "accuracy",
        "confidence_interval",
        "mean_actions",
        "key_pairwise_comparison",
        "bootstrap_ci_pairwise",
        "permutation_p_value_pairwise",
        "interpretation",
    }
    assert required_cols.issubset(rows[0].keys())
    assert any(str(r.get("provider", "")).strip() for r in rows)
    assert any(str(r.get("model", "")).strip() for r in rows)

    pairwise = _read_csv(pairwise_csv)
    assert pairwise
    expected_pairs = {
        ("strict_f3_anti_collapse_weak_v1", "external_l1_max"),
        ("strict_f3_anti_collapse_weak_v1", "self_consistency_3"),
        ("strict_f3_anti_collapse_weak_v1", "strict_f3"),
        ("strict_f3", "strict_gate1_cap_k6"),
    }
    observed = {(r["method_a"], r["method_b"]) for r in pairwise}
    assert expected_pairs.issubset(observed)

    report = (REPO_ROOT / "docs/REAL_MODEL_QUANTITATIVE_AUDIT_REPORT.md").read_text(encoding="utf-8").lower()
    forbidden = [
        "frontier allocation universally dominates real-model baselines",
        "establish provider-independent dominance",
        "sota real-model performance",
        "real-model audits prove universal superiority",
    ]
    for phrase in forbidden:
        assert phrase not in report

    generated_files = [table_csv, table_tex, plot_csv, pairwise_csv, sources_csv, REPO_ROOT / "docs/REAL_MODEL_QUANTITATIVE_AUDIT_REPORT.md"]
    combined_text = "\n".join(path.read_text(encoding="utf-8").lower() for path in generated_files)
    for env_key in ("OPENAI_API_KEY", "COHERE_API_KEY", "HF_TOKEN", "HUGGINGFACE_TOKEN", "HUGGINGFACEHUB_API_TOKEN"):
        token = (os.getenv(env_key) or "").strip()
        if token:
            assert token.lower() not in combined_text
