#!/usr/bin/env python3
"""Write machine-readable and human-readable dataset integration status for the paper."""

from __future__ import annotations

import json
import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.hf_datasets import check_git_dataset_access, check_hf_dataset_access, hf_token_presence

# Paper-priority rows (static policy + optional live probe)
PRIORITY_ROWS: list[dict[str, str | bool | None]] = [
    {
        "dataset_name": "DROP",
        "target_priority": "A",
        "official_source_link": "https://aclanthology.org/N19-1246/",
        "access_link": "https://huggingface.co/datasets/allenai/drop (requested) / https://huggingface.co/datasets/ucinlp/drop (current public loader path)",
        "public_or_gated": "public",
        "registry_keys": "allenai/drop (+ alias DROP; loader currently uses repo_id ucinlp/drop)",
        "could_add_to_repository": "YES_WITH_FALLBACK",
        "what_was_added": "Registered DROP as canonical key `allenai/drop` with environment-verified loader path `ucinlp/drop` plus AWS registry provenance note.",
        "what_is_still_missing": "Requested HF repo id `allenai/drop` is not resolvable in current environment; resolve with official mirror policy before paper freeze.",
        "manual_steps": "If strict source policy requires AllenAI ownership, load from AWS Open Data registry and record conversion manifest.",
        "schema_version_uncertainty": "Validation split row keys verified (`passage`, `question`, `answers_spans`); pin dataset revision in run manifests.",
        "recommended_for_main_paper_now": True,
        "recommended_usage": "evaluation-first",
    },
    {
        "dataset_name": "MuSR",
        "target_priority": "A",
        "official_source_link": "https://huggingface.co/datasets/TAUR-Lab/MuSR",
        "access_link": "https://huggingface.co/datasets/TAUR-Lab/MuSR",
        "public_or_gated": "public",
        "registry_keys": "TAUR-Lab/MuSR (+ alias MuSR)",
        "could_add_to_repository": "YES",
        "what_was_added": "Registered MuSR with default config and split-family handling in access/smoke tooling.",
        "what_is_still_missing": "No blocker in access checks; downstream task-family balancing policy is still open.",
        "manual_steps": "Document task-family split selection (`murder_mysteries`, `object_placements`, `team_allocation`) per run.",
        "schema_version_uncertainty": "Rows include narrative/question/choices metadata; pin revision before benchmark claims.",
        "recommended_for_main_paper_now": True,
        "recommended_usage": "evaluation-first",
    },
    {
        "dataset_name": "BIG-Bench Hard",
        "target_priority": "B",
        "official_source_link": "https://huggingface.co/datasets/openeval/BIG-Bench-Hard",
        "access_link": "https://huggingface.co/datasets/openeval/BIG-Bench-Hard",
        "public_or_gated": "public",
        "registry_keys": "openeval/BIG-Bench-Hard (+ aliases BIG-Bench-Hard, bbh)",
        "could_add_to_repository": "YES",
        "what_was_added": "Registered BBH with default config and train split access checks.",
        "what_is_still_missing": "HF card does not expose a clear license field; license should be manually confirmed before redistribution-sensitive use.",
        "manual_steps": "Record task unpacking policy because rows are task-packed (`examples` list per row).",
        "schema_version_uncertainty": "Current quick probe sees row keys (`canary`, `examples`); conversion into per-item rows is a later pipeline step.",
        "recommended_for_main_paper_now": True,
        "recommended_usage": "evaluation-first",
    },
    {
        "dataset_name": "AQuA-RAT",
        "target_priority": "B",
        "official_source_link": "https://huggingface.co/datasets/deepmind/aqua_rat",
        "access_link": "https://huggingface.co/datasets/deepmind/aqua_rat",
        "public_or_gated": "public",
        "registry_keys": "deepmind/aqua_rat (+ aliases AQuA, AQuA-RAT, aqua_rat)",
        "could_add_to_repository": "YES",
        "what_was_added": "Registered AQuA with raw config and validation split in access/smoke tooling.",
        "what_is_still_missing": "Requested id `aqua_rat` is not canonical on HF Hub; repository now tracks canonical `deepmind/aqua_rat` id explicitly.",
        "manual_steps": "Choose and document raw vs tokenized config per run; current default is raw.",
        "schema_version_uncertainty": "Rows include question/options/correct/rationale; confirm MCQ normalization policy before training use.",
        "recommended_for_main_paper_now": True,
        "recommended_usage": "both",
    },
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
        "registry_keys": "google-deepmind/natural-plan (+ aliases naturalplan, natural_plan)",
        "could_add_to_repository": "PARTIAL",
        "what_was_added": "Git-clone dataset spec + access checker + sample helper; no raw data vendored.",
        "what_is_still_missing": "Local clone path must be prepared by user (`NATURAL_PLAN_DIR` or default external_datasets path).",
        "manual_steps": "Clone upstream repo per license, pin commit, and keep raw files outside git history.",
        "schema_version_uncertainty": "Upstream JSON task files may evolve; pin commit hash in run manifests.",
        "recommended_for_main_paper_now": False,
    },
    {
        "dataset_name": "MATH-500",
        "target_priority": "A",
        "official_source_link": "https://github.com/openai/prm800k#math-splits",
        "access_link": "https://huggingface.co/datasets/HuggingFaceH4/MATH-500",
        "public_or_gated": "public",
        "registry_keys": "HuggingFaceH4/MATH-500 (+ aliases math500, math-500, MATH-500)",
        "could_add_to_repository": "YES",
        "what_was_added": "Canonical HF spec + aliases + smoke/report integration.",
        "what_is_still_missing": "Mirror equivalence checks are still run-level responsibilities when comparing alternative cards.",
        "manual_steps": "Pin HF revision hash in experiment manifest.",
        "schema_version_uncertainty": "Subset mirrors share schema but not guaranteed to remain bit-identical forever.",
        "recommended_for_main_paper_now": True,
    },
    {
        "dataset_name": "AMO-Bench",
        "target_priority": "A",
        "official_source_link": "https://amo-bench.github.io/",
        "access_link": "https://huggingface.co/datasets/meituan-longcat/AMO-Bench",
        "public_or_gated": "public",
        "registry_keys": "meituan-longcat/AMO-Bench (+ aliases amo-bench, amo_bench, AMO-Bench)",
        "could_add_to_repository": "YES",
        "what_was_added": "HF spec with hard-math fields (`prompt`, `answer`) and report/smoke wiring.",
        "what_is_still_missing": "Official grading pipeline parity (parser/LLM hybrid) is external to this repo's basic access helpers.",
        "manual_steps": "Pin HF revision and record answer-type handling policy.",
        "schema_version_uncertainty": "Dataset card notes active updates; lock exact snapshot date/commit in runs.",
        "recommended_for_main_paper_now": True,
    },
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate dataset integration report")
    parser.add_argument("--output-dir", default="outputs")
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    created = datetime.now(timezone.utc).isoformat()

    probe_ids = [
        "allenai/drop",
        "TAUR-Lab/MuSR",
        "openeval/BIG-Bench-Hard",
        "deepmind/aqua_rat",
        "hendrycks/competition_math",
        "EleutherAI/hendrycks_math",
        "HuggingFaceH4/MATH-500",
        "Idavidrein/gpqa",
        "HuggingFaceH4/aime_2024",
        "Hothan/OlympiadBench",
        "meituan-longcat/AMO-Bench",
    ]
    probe_results: dict[str, object] = {}
    hub_metadata: dict[str, object] = {}
    for name in probe_ids:
        try:
            probe_results[name] = check_hf_dataset_access(name)
        except Exception as exc:  # noqa: BLE001
            probe_results[name] = {"dataset": name, "ok": False, "error": f"{type(exc).__name__}: {exc}"}
        try:
            from huggingface_hub import dataset_info  # type: ignore

            info = dataset_info(name)
            card_data = getattr(info, "cardData", None) or {}
            license_value = card_data.get("license")
            license_tags = [t for t in (getattr(info, "tags", None) or []) if str(t).startswith("license:")]
            hub_metadata[name] = {
                "private": bool(getattr(info, "private", False)),
                "gated": bool(getattr(info, "gated", False)),
                "license": license_value,
                "license_tags": license_tags,
            }
        except Exception as exc:  # noqa: BLE001
            hub_metadata[name] = {"error": f"{type(exc).__name__}: {exc}"}

    probe_results["google-deepmind/natural-plan"] = check_git_dataset_access("google-deepmind/natural-plan")

    report = {
        "created_utc": created,
        "hf_token_env": hf_token_presence(),
        "priority_datasets": PRIORITY_ROWS,
        "hub_probe": probe_results,
        "hub_metadata": hub_metadata,
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
        "| Dataset | Priority | Status | Public / gated | Usage class | Paper-ready now |",
        "|---|---:|---|---|---|---|",
    ]
    for row in PRIORITY_ROWS:
        md_lines.append(
            f"| {row['dataset_name']} | {row['target_priority']} | {row['could_add_to_repository']} | "
            f"{row['public_or_gated']} | {row.get('recommended_usage', 'evaluation-first')} | {row['recommended_for_main_paper_now']} |"
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
        meta = hub_metadata.get(name, {})
        md_lines.append(
            f"- `{name}`: ok={ok}, license={meta.get('license')}, license_tags={meta.get('license_tags')} "
            f"{f'({err})' if err else ''}"
        )

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
        md_lines.append(f"- **Usage class**: {row.get('recommended_usage', 'evaluation-first')}")
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
