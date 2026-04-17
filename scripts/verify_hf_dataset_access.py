#!/usr/bin/env python3
"""Verify access to required Hugging Face datasets and write text summaries."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.hf_datasets import (
    check_git_dataset_access,
    check_hf_dataset_access,
    hf_token_presence,
    resolve_dataset_spec,
    resolve_git_dataset_spec,
)

DEFAULT_DATASETS = [
    "allenai/drop",
    "TAUR-Lab/MuSR",
    "openeval/BIG-Bench-Hard",
    "deepmind/aqua_rat",
    "openai/gsm8k",
    "hendrycks/competition_math",
    "EleutherAI/hendrycks_math",
    "HuggingFaceH4/MATH-500",
    "Idavidrein/gpqa",
    "HuggingFaceH4/aime_2024",
    "Hothan/OlympiadBench",
    "meituan-longcat/AMO-Bench",
    "google-deepmind/natural-plan",
    "livecodebench/code_generation_lite",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify HF dataset access for this environment")
    parser.add_argument("--output-dir", default="outputs/hf_dataset_access")
    parser.add_argument("--datasets", default=",".join(DEFAULT_DATASETS))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    datasets = [part.strip() for part in args.datasets.split(",") if part.strip()]
    results = []
    for name in datasets:
        try:
            results.append(check_hf_dataset_access(dataset_name=name))
            continue
        except KeyError:
            pass
        try:
            results.append(check_git_dataset_access(dataset_name=name))
            continue
        except KeyError:
            pass
        results.append(
            {
                "dataset": name,
                "ok": False,
                "error": f"Unsupported dataset key: {name}",
                "source_type": "unknown",
            }
        )
    token_env_presence = hf_token_presence()

    summary = {
        "token_env_presence": token_env_presence,
        "datasets_checked": datasets,
        "results": results,
        "successful": [r["dataset"] for r in results if r.get("ok")],
        "failed": [r["dataset"] for r in results if not r.get("ok")],
        "gpqa_access_ok": next((bool(r.get("ok")) for r in results if r["dataset"] == "Idavidrein/gpqa"), False),
        "gpqa_loader_status": next(
            (
                {
                    "datasets_loader_ok": r.get("datasets_loader_ok"),
                    "pandas_fallback_ok": r.get("pandas_fallback_ok"),
                    "loader_path_used": r.get("loader_path_used"),
                    "gpqa_accessible": r.get("gpqa_accessible", r.get("ok")),
                }
                for r in results
                if r["dataset"] == "Idavidrein/gpqa"
            ),
            None,
        ),
    }

    json_path = output_dir / "hf_access_summary.json"
    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    csv_path = output_dir / "hf_access_summary.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "dataset",
                "repo_id",
                "ok",
                "gated",
                "split",
                "config",
                "token_present",
                "source_type",
                "clone_path",
                "datasets_loader_ok",
                "pandas_fallback_ok",
                "loader_path_used",
                "gpqa_accessible",
                "error",
                "pandas_error",
            ],
        )
        writer.writeheader()
        for row in results:
            writer.writerow(
                {
                    "dataset": row.get("dataset"),
                    "repo_id": row.get("repo_id"),
                    "ok": row.get("ok"),
                    "gated": row.get("gated"),
                    "split": row.get("split"),
                    "config": row.get("config"),
                    "token_present": row.get("token_present"),
                    "source_type": row.get("source_type", "hf"),
                    "clone_path": row.get("clone_path", ""),
                    "datasets_loader_ok": row.get("datasets_loader_ok"),
                    "pandas_fallback_ok": row.get("pandas_fallback_ok"),
                    "loader_path_used": row.get("loader_path_used"),
                    "gpqa_accessible": row.get("gpqa_accessible"),
                    "error": row.get("error", ""),
                    "pandas_error": row.get("pandas_error", ""),
                }
            )

    note_path = output_dir / "hf_access_note.md"
    lines = [
        "# Hugging Face dataset access check",
        "",
        "Token env presence (presence/absence only):",
        f"- HF_TOKEN: {'present' if token_env_presence['HF_TOKEN'] else 'absent'}",
        f"- HUGGINGFACE_HUB_TOKEN: {'present' if token_env_presence['HUGGINGFACE_HUB_TOKEN'] else 'absent'}",
        "",
        "Checked datasets:",
    ]
    for name in datasets:
        spec = None
        git_spec = None
        try:
            spec = resolve_dataset_spec(name)
        except KeyError:
            try:
                git_spec = resolve_git_dataset_spec(name)
            except KeyError:
                spec = None
                git_spec = None
        else:
            git_spec = None
        gated = spec.gated if spec else False
        optional = spec.optional if spec else False
        tags = []
        if gated:
            tags.append("gated")
        if optional:
            tags.append("optional")
        if git_spec is not None:
            tags.append("git_clone")
        suffix = f" ({', '.join(tags)})" if tags else ""
        lines.append(f"- {name}{suffix}")

    lines.append("")
    lines.append("## Results")
    for row in results:
        if row.get("ok"):
            lines.append(f"- ✅ {row['dataset']} loaded ({row.get('split')}, config={row.get('config')})")
        else:
            lines.append(f"- ⚠️ {row['dataset']} failed: {row.get('error', 'unknown error')}")

    gpqa_status = summary.get("gpqa_loader_status") or {}
    lines.extend(
        [
            "",
            "## GPQA loader-path verdict",
            f"- datasets loader success: {gpqa_status.get('datasets_loader_ok')}",
            f"- pandas hf:// fallback success: {gpqa_status.get('pandas_fallback_ok')}",
            f"- loader path used: {gpqa_status.get('loader_path_used')}",
            f"- final GPQA accessible verdict: {gpqa_status.get('gpqa_accessible', summary['gpqa_access_ok'])}",
            "",
            "Raw dataset files are not stored in git; this check only writes JSON/CSV/MD summaries.",
        ]
    )
    note_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps(summary, indent=2))
    print(f"Wrote: {json_path}")
    print(f"Wrote: {csv_path}")
    print(f"Wrote: {note_path}")


if __name__ == "__main__":
    main()
