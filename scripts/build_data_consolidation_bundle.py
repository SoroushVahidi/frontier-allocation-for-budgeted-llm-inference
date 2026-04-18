#!/usr/bin/env python3
"""Build canonical data-consolidation bundle for the target/oracle-definition phase."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.hf_datasets import (
    DATASET_AMBIGUITY_REGIMES,
    DATASET_ROLE_MAP,
    HF_DATASET_SPECS,
    get_dataset_alias_map,
)


def _write_json(path: Path, payload: dict[str, Any] | list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _count_jsonl_rows(path: Path) -> int:
    if not path.exists():
        return 0
    n = 0
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                n += 1
    return n


def _collect_inventory(repo_root: Path) -> dict[str, Any]:
    outputs_root = repo_root / "outputs"
    labels_root = outputs_root / "branch_label_bruteforce_targets"
    learning_root = outputs_root / "branch_label_bruteforce_learning"
    merged_root = outputs_root / "branch_label_bruteforce_merged"
    observability_root = outputs_root / "branch_observability"
    recovery_root = outputs_root / "final_answer_recovery"

    latest_branch_learning_runs = sorted([p.name for p in learning_root.glob("*") if p.is_dir()])[-12:]
    latest_target_runs = sorted([p.name for p in labels_root.glob("*") if p.is_dir()])[-12:]

    schema_path = repo_root / "configs" / "branch_learning_corpus_schema_v1.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    return {
        "raw_data_sources": {
            "hf_registry_entries": len(HF_DATASET_SPECS),
            "dataset_registry_keys": sorted(HF_DATASET_SPECS.keys()),
            "external_supervision_registry_path": "configs/external_reasoning_datasets_registry.json",
        },
        "processed_data_products": {
            "branch_label_targets_root": str(labels_root.relative_to(repo_root)),
            "branch_label_learning_root": str(learning_root.relative_to(repo_root)),
            "branch_label_merged_root": str(merged_root.relative_to(repo_root)),
            "branch_observability_root": str(observability_root.relative_to(repo_root)),
            "final_answer_recovery_root": str(recovery_root.relative_to(repo_root)),
            "latest_target_runs": latest_target_runs,
            "latest_learning_runs": latest_branch_learning_runs,
        },
        "schema_inventory": {
            "branch_learning_corpus_schema_path": str(schema_path.relative_to(repo_root)),
            "branch_learning_row_types": sorted(schema.get("row_types", {}).keys()),
        },
        "row_count_probes": {
            "canonical_targets_candidate_rows": _count_jsonl_rows(
                outputs_root
                / "branch_label_bruteforce_learning"
                / "branch_value_uncertainty_canonical_regime_rebuild_20260417"
                / "canonical_targets_root"
                / "regime_promoted_exact_hard_region"
                / "candidate_labels.jsonl"
            ),
            "canonical_targets_pairwise_rows": _count_jsonl_rows(
                outputs_root
                / "branch_label_bruteforce_learning"
                / "branch_value_uncertainty_canonical_regime_rebuild_20260417"
                / "canonical_targets_root"
                / "regime_promoted_exact_hard_region"
                / "pairwise_labels.jsonl"
            ),
            "observability_rows_latest_casebook": _count_jsonl_rows(
                outputs_root
                / "branch_observability"
                / "worst_real_failure_observability_20260418T022231Z"
                / "branch_trace_records.jsonl"
            ),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build data-consolidation machine-readable bundle")
    parser.add_argument(
        "--output-dir",
        default="outputs/data_consolidation_20260418",
        help="Output directory for bundle files",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    out_dir = (repo_root / args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    alias_map = get_dataset_alias_map()
    role_map = {
        key: {
            "role": DATASET_ROLE_MAP.get(key, "unclassified"),
            "ambiguity_regimes": DATASET_AMBIGUITY_REGIMES.get(key, []),
            "repo_id_used_for_loading": HF_DATASET_SPECS[key].repo_id if key in HF_DATASET_SPECS else key,
            "default_split": HF_DATASET_SPECS[key].default_split if key in HF_DATASET_SPECS else "",
            "default_config": HF_DATASET_SPECS[key].default_config if key in HF_DATASET_SPECS else None,
            "gated": bool(HF_DATASET_SPECS[key].gated) if key in HF_DATASET_SPECS else False,
            "optional": bool(HF_DATASET_SPECS[key].optional) if key in HF_DATASET_SPECS else False,
            "question_fields": list(HF_DATASET_SPECS[key].question_fields) if key in HF_DATASET_SPECS else [],
            "answer_fields": list(HF_DATASET_SPECS[key].answer_fields) if key in HF_DATASET_SPECS else [],
            "provenance_note": HF_DATASET_SPECS[key].provenance_note if key in HF_DATASET_SPECS else None,
        }
        for key in sorted(DATASET_ROLE_MAP.keys())
    }

    normalized_example_schema = {
        "schema_name": "normalized_example_v1",
        "required_fields": [
            "dataset_name",
            "example_id",
            "split",
            "raw_question",
            "raw_answer",
            "normalized_answer",
            "answer_type",
            "numeric_answer_flag",
            "multiple_choice_flag",
            "long_form_flag",
            "recoverable_answer_flag",
            "recoverability_reason",
        ],
        "notes": [
            "raw_question/raw_answer preserve source text.",
            "normalized_answer is deterministic best-effort canonical extraction.",
            "answer_type expected values: numeric, multiple_choice, short_text, missing.",
        ],
    }

    branch_state_schema = {
        "schema_name": "branch_state_observability_v1",
        "required_fields": [
            "state_id",
            "branch_id",
            "example_id",
            "dataset_name",
            "remaining_budget",
            "branch_reasoning_text_raw",
            "branch_final_answer_text_raw",
            "branch_final_answer_normalized",
            "branch_role_summary",
            "final_answer_capture_metadata",
            "answer_normalization_metadata",
            "recoverability_flags",
        ],
        "continuation_and_quality_fields_expected_from_targets": [
            "estimated_value_if_allocate_next",
            "branch_vs_outside_gap",
            "allocation_value_std",
            "near_tie_flag",
            "adjacent_rank_flag",
        ],
    }

    decision_object_schema = {
        "schema_name": "decision_objects_v1",
        "object_types": {
            "pairwise": {
                "required_fields": [
                    "state_id",
                    "branch_i",
                    "branch_j",
                    "label",
                    "margin",
                    "near_tie_flag",
                    "adjacent_rank_flag",
                    "source_regime",
                    "label_source",
                ]
            },
            "top_vs_rest": {
                "derived_from": "candidate rows sorted by estimated_value_if_allocate_next",
                "required_fields": ["state_id", "top_branch_id", "challenger_branch_id", "value_gap", "near_tie_flag"],
            },
            "oracle_comparison": {
                "required_fields": [
                    "state_id",
                    "method_choice",
                    "oracle_choice",
                    "oracle_match_flag",
                    "oracle_regret",
                    "disagreement_flag",
                ]
            },
            "answer_adjudication": {
                "required_fields": [
                    "state_id",
                    "method_branch_normalized_answer",
                    "oracle_branch_normalized_answer",
                    "ground_truth_answer_normalized",
                    "recoverable_answer_flag",
                ]
            },
        },
    }

    semantic_diagnosis_schema = {
        "schema_name": "semantic_diagnosis_v1",
        "object_types": {
            "worst_failure_casebook_row": [
                "state_id",
                "dataset_name",
                "failure_rank",
                "method_branch_reasoning",
                "oracle_branch_reasoning",
                "method_branch_final_answer",
                "oracle_branch_final_answer",
                "semantic_disagreement_type",
                "recoverability_metadata",
            ],
            "completion_aware_mismatch_row": [
                "state_id",
                "continuation_choice",
                "completion_aware_choice",
                "oracle_choice",
                "objective_mismatch_flag",
                "resolved_by_completion_flag",
            ],
        },
    }

    quality_findings = {
        "cleaned_and_normalized_now": [
            "Unified normalized-answer metadata in experiments.data.normalize_answer_text and branch observability output.",
            "Expanded normalized example object with explicit answer-type and recoverability fields.",
            "Canonical dataset role + alias maps exported in this bundle.",
        ],
        "inconsistencies_or_risks": [
            "DROP canonical key is allenai/drop but loader currently uses repo_id ucinlp/drop fallback.",
            "Branch/state observability and branch-learning targets are still stored in separate folders and require join-on state_id for consolidated analytics.",
            "Legacy exploratory outputs coexist with canonical outputs and require role-map filtering before claims.",
        ],
        "missing_for_next_stage": [
            "A single canonical joined branch-state + utility + adjudication table is not yet materialized by default.",
            "Dataset-level normalized example snapshots are schema-defined but not yet persistently generated for every dataset split.",
        ],
    }

    inventory = _collect_inventory(repo_root)

    manifest = {
        "bundle_name": "data_consolidation_20260418",
        "created_by": "scripts/build_data_consolidation_bundle.py",
        "created_for_phase": "target_oracle_definition_hard_disagreement",
        "files": [
            "manifest.json",
            "dataset_role_map.json",
            "dataset_alias_map.json",
            "normalized_example_schema.json",
            "branch_state_schema.json",
            "decision_object_schema.json",
            "semantic_diagnosis_schema.json",
            "data_processing_inventory.json",
            "data_quality_findings.json",
            "commands_assumptions_caveats.md",
        ],
    }

    _write_json(out_dir / "manifest.json", manifest)
    _write_json(out_dir / "dataset_role_map.json", role_map)
    _write_json(out_dir / "dataset_alias_map.json", alias_map)
    _write_json(out_dir / "normalized_example_schema.json", normalized_example_schema)
    _write_json(out_dir / "branch_state_schema.json", branch_state_schema)
    _write_json(out_dir / "decision_object_schema.json", decision_object_schema)
    _write_json(out_dir / "semantic_diagnosis_schema.json", semantic_diagnosis_schema)
    _write_json(out_dir / "data_processing_inventory.json", inventory)
    _write_json(out_dir / "data_quality_findings.json", quality_findings)

    commands = [
        "# Commands, assumptions, caveats",
        "",
        "## Command run",
        f"- `python scripts/build_data_consolidation_bundle.py --output-dir {args.output_dir}`",
        "",
        "## Assumptions",
        "- Uses current repository registries and output folders as source of truth.",
        "- Treats finalized dataset set as fixed; no new dataset hunting.",
        "",
        "## Caveats",
        "- Inventory uses lightweight folder scans and selected row-count probes, not full artifact replay.",
        "- Some older exploratory outputs remain in-place and are classified by role rather than deleted.",
    ]
    (out_dir / "commands_assumptions_caveats.md").write_text("\n".join(commands) + "\n", encoding="utf-8")

    print(json.dumps({"output_dir": str(out_dir), "files_written": 10}, indent=2))


if __name__ == "__main__":
    main()
