"""External reasoning-supervision dataset integration for the new-paper track.

This module intentionally focuses on integration prep only:
- no raw dataset dumps committed,
- download-on-demand inspection via HF datasets,
- schema/sample/normalization previews,
- explicit candidate audit status for datasets that are not integrated.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import importlib
import json
import os
from pathlib import Path
import sys
from typing import Any

from huggingface_hub import HfApi


REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class ExternalReasoningDatasetSpec:
    key: str
    hf_dataset_id: str
    preferred_config: str | None
    preferred_split: str
    supervision_type: str
    structure_type: str
    branch_scoring_fit: str
    verifier_training_fit: str
    pairwise_branch_ranking_fit: str
    trajectory_supervision_fit: str
    frontier_label_distance: str
    variant_candidates: tuple[str, ...] = ()
    note: str | None = None


@dataclass(frozen=True)
class CandidateAuditStatus:
    candidate_name: str
    requested_source: str
    chosen_source: str
    integration_status: str
    dataset_key: str | None
    reason: str


EXTERNAL_REASONING_DATASET_SPECS: dict[str, ExternalReasoningDatasetSpec] = {
    # Existing integrations.
    "prm800k": ExternalReasoningDatasetSpec(
        key="prm800k",
        hf_dataset_id="tasksource/PRM800K",
        preferred_config="default",
        preferred_split="train",
        supervision_type="step_supervision",
        structure_type="trajectory_with_step_labels",
        branch_scoring_fit="high",
        verifier_training_fit="high",
        pairwise_branch_ranking_fit="low",
        trajectory_supervision_fit="low",
        frontier_label_distance="medium",
        variant_candidates=("tasksource/PRM800K",),
        note="Includes step-wise annotations usable for PRM-style supervision.",
    ),
    "math_shepherd": ExternalReasoningDatasetSpec(
        key="math_shepherd",
        hf_dataset_id="peiyi9979/Math-Shepherd",
        preferred_config="default",
        preferred_split="train",
        supervision_type="step_supervision",
        structure_type="trajectory_with_step_labels",
        branch_scoring_fit="high",
        verifier_training_fit="high",
        pairwise_branch_ranking_fit="low",
        trajectory_supervision_fit="low",
        frontier_label_distance="medium",
        variant_candidates=("peiyi9979/Math-Shepherd", "trl-lib/math_shepherd"),
        note="Raw Math-Shepherd schema is preserved; TRL variant kept as swap option.",
    ),
    "ultrainteract_pair": ExternalReasoningDatasetSpec(
        key="ultrainteract_pair",
        hf_dataset_id="openbmb/UltraInteract_pair",
        preferred_config="default",
        preferred_split="train",
        supervision_type="pairwise_preference",
        structure_type="interaction_or_trajectory_pair",
        branch_scoring_fit="medium",
        verifier_training_fit="medium",
        pairwise_branch_ranking_fit="high",
        trajectory_supervision_fit="high",
        frontier_label_distance="medium",
        variant_candidates=("openbmb/UltraInteract_pair",),
        note="Chosen/rejected trajectories support pairwise ranking workflows.",
    ),
    "ultrainteract_sft": ExternalReasoningDatasetSpec(
        key="ultrainteract_sft",
        hf_dataset_id="openbmb/UltraInteract_sft",
        preferred_config="default",
        preferred_split="train",
        supervision_type="trajectory_supervision",
        structure_type="interaction_or_trajectory_single",
        branch_scoring_fit="medium",
        verifier_training_fit="low",
        pairwise_branch_ranking_fit="low",
        trajectory_supervision_fit="high",
        frontier_label_distance="medium_high",
        variant_candidates=("openbmb/UltraInteract_sft",),
        note="SFT trajectories without explicit step correctness labels.",
    ),
    # Newly requested candidates (integrated where accessible).
    "deepstep_math_5k": ExternalReasoningDatasetSpec(
        key="deepstep_math_5k",
        hf_dataset_id="BlackSnowDot/DeepStep-Math-5K",
        preferred_config="default",
        preferred_split="train_positives",
        supervision_type="process_reward",
        structure_type="step_labeled_math_trajectory",
        branch_scoring_fit="high",
        verifier_training_fit="high",
        pairwise_branch_ranking_fit="low",
        trajectory_supervision_fit="medium",
        frontier_label_distance="medium",
        variant_candidates=("BlackSnowDot/DeepStep-Math-5K",),
        note="Positive/negative step-labeled splits align with process reward style supervision.",
    ),
    "webinstruct_verified": ExternalReasoningDatasetSpec(
        key="webinstruct_verified",
        hf_dataset_id="TIGER-Lab/WebInstruct-verified",
        preferred_config="default",
        preferred_split="train",
        supervision_type="trajectory_supervision",
        structure_type="instruction_answer_pair",
        branch_scoring_fit="medium",
        verifier_training_fit="medium",
        pairwise_branch_ranking_fit="low",
        trajectory_supervision_fit="high",
        frontier_label_distance="medium_high",
        variant_candidates=("TIGER-Lab/WebInstruct-verified",),
        note="Verified instruction-answer data with broad task coverage.",
    ),
    "judgelm_collection_v1": ExternalReasoningDatasetSpec(
        key="judgelm_collection_v1",
        hf_dataset_id="BAAI/JudgeLM-data-collection-v1.0",
        preferred_config="default",
        preferred_split="train",
        supervision_type="judge_preference",
        structure_type="pairwise_judgment_records",
        branch_scoring_fit="medium",
        verifier_training_fit="high",
        pairwise_branch_ranking_fit="high",
        trajectory_supervision_fit="low",
        frontier_label_distance="medium",
        variant_candidates=("BAAI/JudgeLM-data-collection-v1.0",),
        note="Pairwise judged responses with reviewer scores and metadata.",
    ),
    "judgelm_100k": ExternalReasoningDatasetSpec(
        key="judgelm_100k",
        hf_dataset_id="BAAI/JudgeLM-100K",
        preferred_config="default",
        preferred_split="train",
        supervision_type="judge_preference",
        structure_type="pairwise_judgment_records",
        branch_scoring_fit="medium",
        verifier_training_fit="high",
        pairwise_branch_ranking_fit="high",
        trajectory_supervision_fit="low",
        frontier_label_distance="medium",
        variant_candidates=("BAAI/JudgeLM-100K",),
        note="Smaller JudgeLM release with same core pairwise judgment schema.",
    ),
    "mt_bench_human_judgments": ExternalReasoningDatasetSpec(
        key="mt_bench_human_judgments",
        hf_dataset_id="lmsys/mt_bench_human_judgments",
        preferred_config="default",
        preferred_split="human",
        supervision_type="judge_preference",
        structure_type="human_pairwise_judgment",
        branch_scoring_fit="medium",
        verifier_training_fit="high",
        pairwise_branch_ranking_fit="high",
        trajectory_supervision_fit="low",
        frontier_label_distance="medium",
        variant_candidates=("lmsys/mt_bench_human_judgments",),
        note="Stable public MT-Bench human judgment source on HF.",
    ),
    "prometheus_feedback_collection": ExternalReasoningDatasetSpec(
        key="prometheus_feedback_collection",
        hf_dataset_id="prometheus-eval/Feedback-Collection",
        preferred_config="default",
        preferred_split="train",
        supervision_type="verifier_supervision",
        structure_type="rubric_feedback_records",
        branch_scoring_fit="medium",
        verifier_training_fit="high",
        pairwise_branch_ranking_fit="low",
        trajectory_supervision_fit="medium",
        frontier_label_distance="medium_high",
        variant_candidates=("prometheus-eval/Feedback-Collection",),
        note="Rubric-style feedback suitable for judge/verifier tuning experiments.",
    ),
    "prometheus_preference_collection": ExternalReasoningDatasetSpec(
        key="prometheus_preference_collection",
        hf_dataset_id="prometheus-eval/Preference-Collection",
        preferred_config="default",
        preferred_split="train",
        supervision_type="judge_preference",
        structure_type="rubric_pairwise_preference",
        branch_scoring_fit="medium",
        verifier_training_fit="high",
        pairwise_branch_ranking_fit="high",
        trajectory_supervision_fit="low",
        frontier_label_distance="medium",
        variant_candidates=("prometheus-eval/Preference-Collection",),
        note="Pairwise preference judgments with rubric context.",
    ),
    "math_verify_s1k_r1": ExternalReasoningDatasetSpec(
        key="math_verify_s1k_r1",
        hf_dataset_id="HuggingFaceH4/s1k_r1_math_verify",
        preferred_config="default",
        preferred_split="train",
        supervision_type="verifier_supervision",
        structure_type="math_generation_with_correctness_signals",
        branch_scoring_fit="high",
        verifier_training_fit="high",
        pairwise_branch_ranking_fit="low",
        trajectory_supervision_fit="medium",
        frontier_label_distance="medium",
        variant_candidates=("HuggingFaceH4/s1k_r1_math_verify",),
        note="Public math_verify-labeled release used as concrete math_verify-style source.",
    ),
    "arctraj": ExternalReasoningDatasetSpec(
        key="arctraj",
        hf_dataset_id="SejinKimm/ARCTraj",
        preferred_config="default",
        preferred_split="train",
        supervision_type="trajectory_supervision",
        structure_type="arc_trajectory_table_payload",
        branch_scoring_fit="medium",
        verifier_training_fit="medium",
        pairwise_branch_ranking_fit="low",
        trajectory_supervision_fit="high",
        frontier_label_distance="high",
        variant_candidates=("SejinKimm/ARCTraj",),
        note="Public ARCTraj dataset card is accessible; schema is table-centric and needs task-specific parsing later.",
    ),
    "apps": ExternalReasoningDatasetSpec(
        key="apps",
        hf_dataset_id="codeparrot/apps",
        preferred_config="all",
        preferred_split="train",
        supervision_type="verifier_backed_code_reasoning",
        structure_type="coding_problem_with_testcase_verifier",
        branch_scoring_fit="medium",
        verifier_training_fit="high",
        pairwise_branch_ranking_fit="medium",
        trajectory_supervision_fit="low",
        frontier_label_distance="high",
        variant_candidates=("codeparrot/apps",),
        note=(
            "APPS provides coding tasks with public/private testcase fields and reference solutions. "
            "Useful primarily as verifier-backed supervision source; branch-allocation labels are derived, not native."
        ),
    ),
}


CANDIDATE_AUDIT_STATUSES: tuple[CandidateAuditStatus, ...] = (
    CandidateAuditStatus(
        candidate_name="DeepStep-Math-5K",
        requested_source="HF: BlackSnowDot/DeepStep-Math-5K",
        chosen_source="HF: BlackSnowDot/DeepStep-Math-5K",
        integration_status="integrated",
        dataset_key="deepstep_math_5k",
        reason="Public HF dataset and loader access succeeded.",
    ),
    CandidateAuditStatus(
        candidate_name="WebInstruct-verified",
        requested_source="HF: TIGER-Lab/WebInstruct-verified",
        chosen_source="HF: TIGER-Lab/WebInstruct-verified",
        integration_status="integrated",
        dataset_key="webinstruct_verified",
        reason="Public HF dataset and loader access succeeded.",
    ),
    CandidateAuditStatus(
        candidate_name="JudgeLM data collection",
        requested_source="HF: BAAI/JudgeLM-data-collection-v1.0",
        chosen_source="HF: BAAI/JudgeLM-data-collection-v1.0",
        integration_status="integrated",
        dataset_key="judgelm_collection_v1",
        reason="Public HF dataset and loader access succeeded.",
    ),
    CandidateAuditStatus(
        candidate_name="JudgeLM-100K",
        requested_source="HF: BAAI/JudgeLM-100K",
        chosen_source="HF: BAAI/JudgeLM-100K",
        integration_status="integrated",
        dataset_key="judgelm_100k",
        reason="Public HF dataset and loader access succeeded.",
    ),
    CandidateAuditStatus(
        candidate_name="PairS",
        requested_source="GitHub: cambridgeltl/PairS (or stable HF mirror)",
        chosen_source="GitHub: cambridgeltl/PairS",
        integration_status="not_integrated",
        dataset_key=None,
        reason="Repository is code-first for ranking/evaluation; no canonical standalone dataset artifact or stable HF mirror was identified.",
    ),
    CandidateAuditStatus(
        candidate_name="MT-Bench human annotation",
        requested_source="Stable public dataset if available",
        chosen_source="HF: lmsys/mt_bench_human_judgments",
        integration_status="integrated",
        dataset_key="mt_bench_human_judgments",
        reason="Public HF dataset with human and gpt4_pair splits is available.",
    ),
    CandidateAuditStatus(
        candidate_name="Prometheus feedback / rubric preference",
        requested_source="Stable public dataset if available",
        chosen_source="HF: prometheus-eval/Feedback-Collection + prometheus-eval/Preference-Collection",
        integration_status="integrated",
        dataset_key="prometheus_feedback_collection",
        reason="Both public HF collections are accessible; preference collection also integrated separately.",
    ),
    CandidateAuditStatus(
        candidate_name="Math_Verify",
        requested_source="Real public dataset/release",
        chosen_source="HF: HuggingFaceH4/s1k_r1_math_verify",
        integration_status="integrated",
        dataset_key="math_verify_s1k_r1",
        reason="Concrete public HF math_verify-style release was found and is loadable.",
    ),
    CandidateAuditStatus(
        candidate_name="AgentPRM / InversePRM",
        requested_source="Concrete public dataset release",
        chosen_source="HF: Jolandaaa/agentprm (gated), no inverseprm HF dataset found",
        integration_status="not_integrated",
        dataset_key=None,
        reason="agentprm exists but is gated and inaccessible in this environment; no stable public InversePRM dataset artifact was found.",
    ),
    CandidateAuditStatus(
        candidate_name="ARCTraj",
        requested_source="Public dataset if available",
        chosen_source="HF: SejinKimm/ARCTraj",
        integration_status="integrated",
        dataset_key="arctraj",
        reason="Public HF dataset is accessible and supports loader-based schema/sample inspection.",
    ),
    CandidateAuditStatus(
        candidate_name="APPS",
        requested_source="HF coding benchmark with executable verification signal",
        chosen_source="HF: codeparrot/apps",
        integration_status="integrated",
        dataset_key="apps",
        reason="Public HF dataset is accessible; testcase fields support verifier-backed derived supervision paths.",
    ),
)


def _import_hf_datasets_module() -> Any:
    """Import HF `datasets` while avoiding local `datasets/` path shadowing."""
    original_path = list(sys.path)
    try:
        sys.path = [p for p in original_path if Path(p).resolve() != REPO_ROOT]
        return importlib.import_module("datasets")
    finally:
        sys.path = original_path


def _get_hf_token() -> str | None:
    for env_name in ("HF_TOKEN", "HUGGINGFACE_HUB_TOKEN"):
        token = os.getenv(env_name)
        if token:
            return token
    return None


def _safe_json_preview(row: dict[str, Any], max_chars: int = 320) -> str:
    text = json.dumps(row, ensure_ascii=False, default=str)
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


def _normalize_row(spec: ExternalReasoningDatasetSpec, row: dict[str, Any]) -> dict[str, Any]:
    """Lightweight common normalization preview for planning later training work."""
    if spec.supervision_type in {"step_supervision", "process_reward"}:
        prompt = row.get("question") or row.get("problem") or row.get("input") or row.get("prompt") or ""
        labels = row.get("label") or row.get("labels") or row.get("step_labels") or row.get("correctness_math_verify")
        return {
            "normalization_type": spec.supervision_type,
            "prompt": str(prompt),
            "signal_preview": str(labels)[:200],
        }

    if spec.supervision_type in {"pairwise_preference", "judge_preference"}:
        prompt = row.get("question") or row.get("question_body") or row.get("instruction") or row.get("task") or ""
        chosen = row.get("chosen") or row.get("answer1_body") or row.get("conversation_a") or row.get("orig_response_A")
        rejected = row.get("rejected") or row.get("answer2_body") or row.get("conversation_b") or row.get("orig_response_B")
        score = row.get("score") or row.get("winner") or row.get("orig_preference")
        return {
            "normalization_type": spec.supervision_type,
            "prompt": str(prompt)[:240],
            "chosen_preview": str(chosen)[:180],
            "rejected_preview": str(rejected)[:180],
            "score_or_winner": str(score)[:120],
        }

    prompt = row.get("instruction") or row.get("task") or row.get("question") or row.get("name") or row.get("prompt") or ""
    response = row.get("response") or row.get("answer") or row.get("output") or row.get("table") or ""
    return {
        "normalization_type": spec.supervision_type,
        "prompt": str(prompt)[:240],
        "response_preview": str(response)[:220],
    }


def list_external_reasoning_dataset_specs() -> list[ExternalReasoningDatasetSpec]:
    return [EXTERNAL_REASONING_DATASET_SPECS[k] for k in sorted(EXTERNAL_REASONING_DATASET_SPECS)]


def list_candidate_audit_statuses() -> list[dict[str, Any]]:
    return [asdict(item) for item in CANDIDATE_AUDIT_STATUSES]


def inspect_external_reasoning_dataset(spec: ExternalReasoningDatasetSpec, sample_rows: int = 2) -> dict[str, Any]:
    """Inspect one external reasoning dataset with light-touch streaming access."""
    token = _get_hf_token()
    api = HfApi(token=token)
    datasets_module = _import_hf_datasets_module()
    get_dataset_config_names = getattr(datasets_module, "get_dataset_config_names")
    get_dataset_split_names = getattr(datasets_module, "get_dataset_split_names")
    load_dataset = getattr(datasets_module, "load_dataset")
    load_dataset_builder = getattr(datasets_module, "load_dataset_builder")

    report: dict[str, Any] = {
        "dataset_key": spec.key,
        "hf_dataset_id": spec.hf_dataset_id,
        "chosen_variant_reason": spec.note,
        "variant_candidates": list(spec.variant_candidates),
        "supervision_type": spec.supervision_type,
        "structure_type": spec.structure_type,
        "usefulness": {
            "branch_scoring": spec.branch_scoring_fit,
            "verifier_training": spec.verifier_training_fit,
            "pairwise_branch_ranking": spec.pairwise_branch_ranking_fit,
            "trajectory_supervision": spec.trajectory_supervision_fit,
            "frontier_allocation_label_distance": spec.frontier_label_distance,
        },
        "access_ok": False,
        "gated": None,
        "license": None,
        "configs": [],
        "splits": {},
        "selected_config": spec.preferred_config,
        "selected_split": spec.preferred_split,
        "row_count": None,
        "schema_fields": [],
        "sample_previews": [],
        "normalization_preview": [],
        "error": None,
    }

    try:
        info = api.dataset_info(spec.hf_dataset_id)
        report["gated"] = bool(getattr(info, "gated", False))
        card_data = getattr(info, "cardData", None) or {}
        if isinstance(card_data, dict):
            report["license"] = card_data.get("license")
        if not report["license"]:
            tags = list(getattr(info, "tags", []) or [])
            for tag in tags:
                if isinstance(tag, str) and tag.startswith("license:"):
                    report["license"] = tag.split("license:", 1)[1]
                    break
    except Exception as exc:  # noqa: BLE001
        report["error"] = f"dataset_info_failed: {type(exc).__name__}: {exc}"

    try:
        config_names = get_dataset_config_names(spec.hf_dataset_id, token=token)
        report["configs"] = config_names
        selected_config = spec.preferred_config if spec.preferred_config in config_names else (config_names[0] if config_names else None)
        report["selected_config"] = selected_config

        if selected_config is None:
            split_names = get_dataset_split_names(spec.hf_dataset_id, token=token)
        else:
            split_names = get_dataset_split_names(spec.hf_dataset_id, selected_config, token=token)
        report["splits"] = {split_name: {"num_rows": None} for split_name in split_names}

        selected_split = spec.preferred_split if spec.preferred_split in split_names else (split_names[0] if split_names else spec.preferred_split)
        report["selected_split"] = selected_split

        builder_kwargs: dict[str, Any] = {"path": spec.hf_dataset_id, "token": token}
        if selected_config is not None:
            builder_kwargs["name"] = selected_config
        builder = load_dataset_builder(**builder_kwargs)
        split_info = getattr(builder.info, "splits", {}) or {}
        for split_name in split_names:
            num_rows = None
            if split_name in split_info:
                num_rows = getattr(split_info[split_name], "num_examples", None)
            report["splits"][split_name] = {"num_rows": num_rows}

        kwargs: dict[str, Any] = {
            "path": spec.hf_dataset_id,
            "split": selected_split,
            "streaming": True,
            "token": token,
        }
        if selected_config is not None:
            kwargs["name"] = selected_config

        ds = load_dataset(**kwargs)
        samples: list[dict[str, Any]] = []
        for row in ds:
            samples.append(row)
            if len(samples) >= sample_rows:
                break

        first = samples[0] if samples else {}
        report["schema_fields"] = sorted(first.keys()) if first else []
        report["sample_previews"] = [_safe_json_preview(row) for row in samples]
        report["normalization_preview"] = [_normalize_row(spec, row) for row in samples]
        report["access_ok"] = True
        report["row_count"] = report["splits"].get(selected_split, {}).get("num_rows")

    except Exception as exc:  # noqa: BLE001
        report["access_ok"] = False
        report["error"] = report["error"] or f"load_failed: {type(exc).__name__}: {exc}"

    return report


def run_external_reasoning_dataset_inspection(sample_rows: int = 2) -> dict[str, Any]:
    specs = list_external_reasoning_dataset_specs()
    results = [inspect_external_reasoning_dataset(spec, sample_rows=sample_rows) for spec in specs]
    candidate_audit = list_candidate_audit_statuses()
    integrated_names = {r["dataset_key"] for r in results}
    for row in candidate_audit:
        key = row.get("dataset_key")
        if key and key not in integrated_names and row["integration_status"] == "integrated":
            row["integration_status"] = "not_integrated"
            row["reason"] = f"Declared integrated but no live spec found for key={key}."

    return {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_count": len(results),
        "all_access_ok": all(bool(r.get("access_ok")) for r in results),
        "results": results,
        "candidate_audit": candidate_audit,
    }
