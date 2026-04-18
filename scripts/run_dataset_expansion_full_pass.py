#!/usr/bin/env python3
"""Run full dataset-expansion readiness bundle generation for 2026-04-18 pass."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.hf_datasets import (  # noqa: E402
    DATASET_AMBIGUITY_REGIMES,
    GIT_DATASET_SPECS,
    HF_DATASET_SPECS,
    check_git_dataset_access,
    check_hf_dataset_access,
    get_dataset_alias_map,
    get_dataset_role_map,
    hf_token_presence,
    sample_hf_examples,
)

EXPANSION_DATASETS = [
    "allenai/drop",
    "TAUR-Lab/MuSR",
    "openeval/BIG-Bench-Hard",
    "deepmind/aqua_rat",
]


def _license_probe(dataset_name: str) -> dict[str, Any]:
    try:
        from huggingface_hub import dataset_info  # type: ignore

        info = dataset_info(dataset_name)
        card_data = getattr(info, "cardData", None) or {}
        return {
            "ok": True,
            "private": bool(getattr(info, "private", False)),
            "gated": bool(getattr(info, "gated", False)),
            "license": card_data.get("license"),
            "license_tags": [
                t for t in (getattr(info, "tags", None) or []) if str(t).startswith("license:")
            ],
            "sha": getattr(info, "sha", None),
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def _readiness_row(dataset_key: str, access: dict[str, Any], license_meta: dict[str, Any]) -> dict[str, Any]:
    spec = HF_DATASET_SPECS[dataset_key]
    role = get_dataset_role_map().get(dataset_key, "unclassified")
    role_note_map = {
        "main_evaluation_dataset": "main evaluation dataset",
        "expansion_evaluation_dataset": "expansion evaluation dataset",
        "optional_extended_only": "optional/extended only",
        "supervision_prep_source": "supervision/prep source",
    }
    return {
        "dataset": dataset_key,
        "canonical_id": dataset_key,
        "loader_repo_id": spec.repo_id,
        "default_split": spec.default_split,
        "default_config": spec.default_config,
        "role": role,
        "role_label": role_note_map.get(role, role),
        "access_ok": bool(access.get("ok")),
        "gated": bool(access.get("gated", spec.gated)),
        "token_present": bool(access.get("token_present", False)),
        "license": license_meta.get("license"),
        "license_tags": license_meta.get("license_tags", []),
        "first_row_keys": access.get("first_row_keys", []),
        "provenance_note": spec.provenance_note,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate full dataset expansion readiness bundle")
    parser.add_argument("--output-dir", default="outputs/dataset_expansion_full_20260418")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    created = datetime.now(timezone.utc).isoformat()
    alias_map = get_dataset_alias_map()
    role_map = get_dataset_role_map()

    integrated_hf = sorted(HF_DATASET_SPECS.keys())
    integrated_git = sorted(GIT_DATASET_SPECS.keys())

    hf_access: dict[str, dict[str, Any]] = {}
    hf_license: dict[str, dict[str, Any]] = {}
    for dataset in integrated_hf:
        hf_access[dataset] = check_hf_dataset_access(dataset)
        hf_license[dataset] = _license_probe(dataset)

    git_access: dict[str, dict[str, Any]] = {}
    for dataset in integrated_git:
        git_access[dataset] = check_git_dataset_access(dataset)

    expansion_sample_rows: dict[str, Any] = {}
    for dataset in EXPANSION_DATASETS:
        try:
            sample = sample_hf_examples(dataset, pilot_size=1, seed=args.seed)
            expansion_sample_rows[dataset] = {"ok": True, "sample": sample[0] if sample else None}
        except Exception as exc:  # noqa: BLE001
            expansion_sample_rows[dataset] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    readiness_rows = [_readiness_row(d, hf_access[d], hf_license[d]) for d in integrated_hf]
    readiness_rows.extend(
        {
            "dataset": d,
            "canonical_id": d,
            "loader_repo_id": GIT_DATASET_SPECS[d].repo_url,
            "default_split": "n/a",
            "default_config": "n/a",
            "role": role_map.get(d, "unclassified"),
            "role_label": "main evaluation dataset",
            "access_ok": bool(git_access[d].get("ok")),
            "gated": False,
            "token_present": False,
            "license": None,
            "license_tags": [],
            "first_row_keys": [],
            "provenance_note": GIT_DATASET_SPECS[d].provenance_note,
        }
        for d in integrated_git
    )

    ambiguity_summary = {
        "math_heavy_core_datasets": [
            "openai/gsm8k",
            "hendrycks/competition_math",
            "EleutherAI/hendrycks_math",
            "HuggingFaceH4/MATH-500",
            "HuggingFaceH4/aime_2024",
            "Hothan/OlympiadBench",
            "meituan-longcat/AMO-Bench",
        ],
        "new_expansion_datasets": EXPANSION_DATASETS,
        "expansion_coverage_improvements": {
            "allenai/drop": ["paragraph-grounded evidence selection", "numerical + span answer extraction"],
            "TAUR-Lab/MuSR": ["long narrative disambiguation", "multiple plausible hypotheses"],
            "openeval/BIG-Bench-Hard": ["cross-domain symbolic/logical variety", "task-diversity stress test"],
            "deepmind/aqua_rat": ["multiple-choice reasoning", "answer option normalization"],
        },
        "remaining_undercovered_regimes": [
            "interactive/tool-using reasoning",
            "code-execution-grounded ambiguity",
            "multi-turn dialogic ambiguity",
        ],
        "dataset_ambiguity_regimes": DATASET_AMBIGUITY_REGIMES,
    }

    manifest = {
        "run_name": "dataset_expansion_full_20260418",
        "created_utc": created,
        "script": "scripts/run_dataset_expansion_full_pass.py",
        "focus": "data quality + targeted expansion (DROP, MuSR, BIG-Bench Hard, AQuA)",
        "outputs": [
            "manifest.json",
            "integrated_datasets.json",
            "dataset_role_map.json",
            "dataset_alias_map.json",
            "dataset_processing_summary.json",
            "dataset_readiness_table.json",
            "ambiguity_regime_coverage_summary.json",
            "commands_assumptions_caveats.md",
        ],
    }

    processing_summary = {
        "token_env_presence": hf_token_presence(),
        "canonicalization_rules": {
            "dataset_aliases_case_insensitive": True,
            "canonical_ids_are_registry_keys": True,
            "split_default_policy": "dataset-specific default split from HFDatasetSpec",
            "row_schema_for_smoke": ["example_id", "dataset", "question", "answer", "split", "config"],
            "drop_policy": "canonical key allenai/drop with loader fallback repo_id ucinlp/drop",
            "musr_policy": "keep task-family split names (default murder_mysteries)",
            "bbh_policy": "task-packed rows; sample formatter unpacks first nested example",
            "aqua_policy": "canonical id deepmind/aqua_rat with raw config default",
        },
        "expansion_samples": expansion_sample_rows,
        "hf_access": hf_access,
        "git_access": git_access,
        "hf_license_probe": hf_license,
    }

    integrated = {
        "hf_datasets": integrated_hf,
        "git_clone_datasets": integrated_git,
        "expansion_datasets": EXPANSION_DATASETS,
    }

    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (out_dir / "integrated_datasets.json").write_text(json.dumps(integrated, indent=2), encoding="utf-8")
    (out_dir / "dataset_role_map.json").write_text(json.dumps(role_map, indent=2), encoding="utf-8")
    (out_dir / "dataset_alias_map.json").write_text(json.dumps(alias_map, indent=2), encoding="utf-8")
    (out_dir / "dataset_processing_summary.json").write_text(
        json.dumps(processing_summary, indent=2), encoding="utf-8"
    )
    (out_dir / "dataset_readiness_table.json").write_text(json.dumps(readiness_rows, indent=2), encoding="utf-8")
    (out_dir / "ambiguity_regime_coverage_summary.json").write_text(
        json.dumps(ambiguity_summary, indent=2), encoding="utf-8"
    )

    caveats = [
        "# Commands, assumptions, and caveats",
        "",
        "## Commands used for this bundle",
        "",
        "```bash",
        "python scripts/run_dataset_expansion_full_pass.py --output-dir outputs/dataset_expansion_full_20260418",
        "python scripts/verify_hf_dataset_access.py --output-dir outputs/dataset_expansion_full_20260418/hf_access_check",
        "python scripts/dataset_smoke_sample.py --output-dir outputs/dataset_expansion_full_20260418/smoke_check --datasets allenai/drop,TAUR-Lab/MuSR,openeval/BIG-Bench-Hard,deepmind/aqua_rat",
        "```",
        "",
        "## Assumptions",
        "",
        "- Dataset loader checks are bounded readiness checks, not full benchmark runs.",
        "- Canonical dataset naming follows `experiments/hf_datasets.py` registry keys.",
        "- Evaluation vs supervision roles are tracked explicitly in `dataset_role_map.json`.",
        "",
        "## Caveats",
        "",
        "- DROP is tracked as canonical key `allenai/drop` but currently loads from mirror repo id `ucinlp/drop` in this environment.",
        "- BIG-Bench Hard has task-packed rows and still needs task-unpacking policy for full training pipelines.",
        "- NaturalPlan remains clone-dependent and is not available unless local clone exists.",
        "- LiveCodeBench remains optional/extended due current environment loader limitations.",
    ]
    (out_dir / "commands_assumptions_caveats.md").write_text("\n".join(caveats) + "\n", encoding="utf-8")

    print(str(out_dir / "manifest.json"))


if __name__ == "__main__":
    main()
