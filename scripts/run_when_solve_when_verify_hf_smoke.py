#!/usr/bin/env python3
"""HF-backed upstream smoke checks for when_solve_when_verify."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import tarfile

from huggingface_hub import HfApi, hf_hub_download
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = REPO_ROOT / "outputs" / "when_solve_when_verify_hf_smoke" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    upstream_dir = REPO_ROOT / "external" / "when_solve_when_verify" / "upstream" / "sc-genrm-scaling"
    upstream_dir.parent.mkdir(parents=True, exist_ok=True)
    if (upstream_dir / ".git").exists():
        subprocess.run(["git", "-C", str(upstream_dir), "pull", "--ff-only"], check=True)
    else:
        subprocess.run(
            ["git", "clone", "https://github.com/nishadsinghi/sc-genrm-scaling.git", str(upstream_dir)],
            check=True,
        )
    upstream_head = subprocess.check_output(
        ["git", "-C", str(upstream_dir), "rev-parse", "HEAD"],
        text=True,
    ).strip()

    api = HfApi()
    models = [m.id for m in api.list_models(author="sc-genrm-scaling", limit=20)]
    datasets = [d.id for d in api.list_datasets(author="sc-genrm-scaling", limit=40)]

    downloads_dir = out_dir / "downloads"
    downloads_dir.mkdir(parents=True, exist_ok=True)
    sol_tar = Path(
        hf_hub_download(
            repo_id="sc-genrm-scaling/MATH128_Solutions_Llama-3.1-8B-Instruct",
            repo_type="dataset",
            filename="compressed_Llama-3.1-8B-Instruct.tar.gz",
            local_dir=str(downloads_dir),
        )
    )
    ver_tar = Path(
        hf_hub_download(
            repo_id="sc-genrm-scaling/MATH128_verifications_GenRM-FT_Llama-3.1-8B-Instruct",
            repo_type="dataset",
            filename="compressed_MATH128_verifications_GenRM-FT_Llama-3.1-8B-Instruct.tar.gz",
            local_dir=str(downloads_dir),
        )
    )

    with tarfile.open(sol_tar, "r:gz") as tf:
        sample_sol = next(m for m in tf if m.isfile() and m.name.endswith(".yaml") and "/logs/" not in m.name)
        sol_row = yaml.safe_load(tf.extractfile(sample_sol).read())
    with tarfile.open(ver_tar, "r:gz") as tf:
        sample_ver = next(m for m in tf if m.isfile() and m.name.endswith(".yaml"))
        ver_row = yaml.safe_load(tf.extractfile(sample_ver).read())

    summary = {
        "run_id": run_id,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "upstream_repo": str(upstream_dir.relative_to(REPO_ROOT)),
        "upstream_head": upstream_head,
        "hf_models_count": len(models),
        "hf_datasets_count": len(datasets),
        "hf_models_sample": models[:8],
        "hf_datasets_sample": datasets[:12],
        "artifact_pulls": [
            str(sol_tar.relative_to(REPO_ROOT)),
            str(ver_tar.relative_to(REPO_ROOT)),
        ],
        "minimal_schema_check": {
            "solution_yaml": {
                "path_in_tar": sample_sol.name,
                "keys": sorted(sol_row.keys()),
                "num_samples": len(sol_row.get("samples", [])),
                "has_gt_answer": "gt_answer" in sol_row,
            },
            "verification_yaml": {
                "path_in_tar": sample_ver.name,
                "keys": sorted(ver_row.keys()),
                "num_verifications": len(ver_row.get("verifications", [])),
            },
        },
        "status": "ok",
    }
    (out_dir / "smoke_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "run_dir": str(out_dir)}, indent=2))


if __name__ == "__main__":
    main()
