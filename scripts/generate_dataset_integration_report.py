#!/usr/bin/env python3
"""Write machine-readable and human-readable dataset integration status for the paper."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.hf_datasets import check_hf_dataset_access, hf_token_presence

# Five paper-priority rows (static policy + optional live probe)
PRIORITY_ROWS: list[dict[str, str | bool | None]] = [
    {
        "dataset_name": "MATH (Hendrycks et al.)",
        "target_priority": "A",
        "official_source_link": "https://arxiv.org/abs/2103.03874",
        "access_link": "https://huggingface.co/datasets/hendrycks/competition_math",
        "public_or_gated": "public",
        "registry_keys": "hendrycks/competition_math, EleutherAI/hendrycks_math (+ aliases math, MATH, hendrycks/math)",
        "could_add_to_repository": "YES",
        "what_was_added": "HFDatasetSpec for hendrycks/competition_math; aliases to paper URL hendrycks/math; EleutherAI mirror retained.",
        "what_is_still_missing": "Hub id `hendrycks/math` does not resolve; use hendrycks/competition_math or mirror. Network-dependent load in some environments.",
        "manual_steps": "None for public mirror; pin HF revision for paper runs.",
        "schema_version_uncertainty": "Subject configs (algebra, geometry, ...) and test split; document chosen config in each run manifest.",
        "recommended_for_main_paper_now": True,
    },
    {
        "dataset_name": "GPQA Diamond",
        "target_priority": "A",
        "official_source_link": "https://arxiv.org/abs/2311.12022",
        "access_link": "https://huggingface.co/datasets/Idavidrein/gpqa",
        "public_or_gated": "gated_terms_likely",
        "registry_keys": "Idavidrein/gpqa (config gpqa_diamond) + aliases gpqa_diamond, gpqa",
        "could_add_to_repository": "YES",
        "what_was_added": "Existing spec reinforced; aliases; optional choices field in sample_hf_examples; normalization MCQ hook.",
        "what_is_still_missing": "User must accept HF terms; token required when gated.",
        "manual_steps": "huggingface-cli login or HF_TOKEN; accept dataset terms on the Hub.",
        "schema_version_uncertainty": "Default split train for diamond config per prior repo behavior; confirm against dataset card when reporting.",
        "recommended_for_main_paper_now": True,
    },
    {
        "dataset_name": "AIME",
        "target_priority": "B",
        "official_source_link": "https://artificialanalysis.ai/evaluations/aime-2025",
        "access_link": "https://huggingface.co/datasets/HuggingFaceH4/aime_2024",
        "public_or_gated": "public",
        "registry_keys": "HuggingFaceH4/aime_2024 (+ aliases aime, aime_2024)",
        "could_add_to_repository": "PARTIAL",
        "what_was_added": "HFDatasetSpec for 2024-only HuggingFaceH4 card (30 problems); wired in registry and verification list.",
        "what_is_still_missing": "Not a full multi-year AIME union; for broader coverage consider AI-MO/aimo-validation-aime (not wired; cite separately).",
        "manual_steps": "None typically.",
        "schema_version_uncertainty": "Single-card snapshot; year field exists in rows—lock revision for paper tables.",
        "recommended_for_main_paper_now": True,
    },
    {
        "dataset_name": "OlympiadBench",
        "target_priority": "B",
        "official_source_link": "https://arxiv.org/abs/2406.15513",
        "access_link": "https://huggingface.co/datasets/Hothan/OlympiadBench",
        "public_or_gated": "public",
        "registry_keys": "Hothan/OlympiadBench (THUDM Hub path THUDM/OlympiadBench not found on Hub API)",
        "could_add_to_repository": "PARTIAL",
        "what_was_added": "Canonical HF path documented as Hothan/OlympiadBench mirror; same spec as before with provenance_note.",
        "what_is_still_missing": "THUDM/OlympiadBench repo id returns 404 via Hub API; treat Hothan as mirror unless upstream republishes.",
        "manual_steps": "None for public load; pick config (default OE_TO_maths_en_COMP) explicitly in papers.",
        "schema_version_uncertainty": "Many configs; default single English math competition subset.",
        "recommended_for_main_paper_now": True,
    },
    {
        "dataset_name": "NaturalPlan",
        "target_priority": "C",
        "official_source_link": "https://arxiv.org/abs/2406.04520",
        "access_link": "https://github.com/google-deepmind/natural-plan",
        "public_or_gated": "public_repo",
        "registry_keys": "none (GitHub-hosted; not in HF_DATASET_SPECS)",
        "could_add_to_repository": "NO",
        "what_was_added": "Documentation-only status; no raw data or loader committed.",
        "what_is_still_missing": "Optional future: thin loader after license review and pinned commit policy.",
        "manual_steps": "Clone upstream repo per license; pin commit; do not vendor raw data into this repo.",
        "schema_version_uncertainty": "N/A until a pinned snapshot is adopted.",
        "recommended_for_main_paper_now": False,
    },
]


def main() -> None:
    out_dir = Path("outputs")
    out_dir.mkdir(parents=True, exist_ok=True)
    created = datetime.now(timezone.utc).isoformat()

    probe_ids = [
        "hendrycks/competition_math",
        "EleutherAI/hendrycks_math",
        "Idavidrein/gpqa",
        "HuggingFaceH4/aime_2024",
        "Hothan/OlympiadBench",
    ]
    probe_results: dict[str, object] = {}
    for name in probe_ids:
        try:
            probe_results[name] = check_hf_dataset_access(name)
        except Exception as exc:  # noqa: BLE001
            probe_results[name] = {"dataset": name, "ok": False, "error": f"{type(exc).__name__}: {exc}"}

    report = {
        "created_utc": created,
        "hf_token_env": hf_token_presence(),
        "priority_datasets": PRIORITY_ROWS,
        "hub_probe": probe_results,
    }

    json_path = out_dir / "dataset_integration_report.json"
    json_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    md_lines = [
        "# Dataset integration report",
        "",
        f"- Generated (UTC): `{created}`",
        "",
        "## Summary",
        "",
        "| Dataset | Priority | Status | Public / gated | Paper-ready now |",
        "|---|---:|---|---|---|",
    ]
    for row in PRIORITY_ROWS:
        md_lines.append(
            f"| {row['dataset_name']} | {row['target_priority']} | {row['could_add_to_repository']} | "
            f"{row['public_or_gated']} | {row['recommended_for_main_paper_now']} |"
        )
    md_lines.extend(
        [
            "",
            "## Probe results (this environment)",
            "",
            "These are non-secret connectivity checks only; they do not prove global availability.",
            "",
        ]
    )
    for name, r in probe_results.items():
        ok = r.get("ok")
        err = (r.get("error") or "")[:200]
        md_lines.append(f"- `{name}`: ok={ok} {f'({err})' if err else ''}")

    md_lines.extend(
        [
            "",
            "## Per-dataset detail",
            "",
        ]
    )
    for row in PRIORITY_ROWS:
        md_lines.append(f"### {row['dataset_name']} ({row['target_priority']})")
        md_lines.append(f"- **Could add**: {row['could_add_to_repository']}")
        md_lines.append(f"- **Official**: {row['official_source_link']}")
        md_lines.append(f"- **Access**: {row['access_link']}")
        md_lines.append(f"- **What was added**: {row['what_was_added']}")
        md_lines.append(f"- **Still missing**: {row['what_is_still_missing']}")
        md_lines.append(f"- **Manual steps**: {row['manual_steps']}")
        md_lines.append(f"- **Schema/version notes**: {row['schema_version_uncertainty']}")
        md_lines.append("")

    md_path = out_dir / "dataset_integration_report.md"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    print(str(json_path))
    print(str(md_path))


if __name__ == "__main__":
    main()
