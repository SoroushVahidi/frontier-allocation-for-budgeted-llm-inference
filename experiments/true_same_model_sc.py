"""True same-model self-consistency (SC) primitives — expand-only, N independent samples.

This module deliberately does **not** use SelfConsistencyFairController or any
expand+verify budget allocator. Historical matched_sc_n6_* packages under B=6
claimed N=6 while producing ≤3 branch answers; loaders here reject that pattern.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping, Sequence

from experiments.frontier_max_support_tiebreak import normalize_answer_group_key

TIE_BREAK_RULE = "max_votes_then_lexicographic_normalized_key"
EXPERIMENT_TYPE = "true_same_model_self_consistency"


class SCValidationStatus(str, Enum):
    VALID_N_INDEPENDENT_GENERATIONS = "VALID_N_INDEPENDENT_GENERATIONS"
    INVALID_NOT_SIX_INDEPENDENT_GENERATIONS = "INVALID_NOT_SIX_INDEPENDENT_GENERATIONS"
    INVALID_INCOMPLETE_SAMPLES = "INVALID_INCOMPLETE_SAMPLES"
    INVALID_CONTROLLER_BRANCH_PATTERN = "INVALID_CONTROLLER_BRANCH_PATTERN"
    INVALID_REPAIR_OVERRIDE_PRESENT = "INVALID_REPAIR_OVERRIDE_PRESENT"
    INVALID_CALL_COUNT_WITHOUT_GENERATIONS = "INVALID_CALL_COUNT_WITHOUT_GENERATIONS"
    INVALID_CONFIG = "INVALID_CONFIG"


@dataclass(frozen=True)
class TrueSCConfig:
    experiment_type: str = EXPERIMENT_TYPE
    samples_per_example: int = 6
    controller_enabled: bool = False
    repair_override_enabled: bool = False
    cost_ceiling_usd: float | None = None

    def validate(self) -> None:
        if self.experiment_type != EXPERIMENT_TYPE:
            raise ValueError(f"experiment_type must be {EXPERIMENT_TYPE!r}, got {self.experiment_type!r}")
        if int(self.samples_per_example) < 2:
            raise ValueError("samples_per_example must be >= 2")
        if self.controller_enabled:
            raise ValueError("controller_enabled must be false for true same-model SC")
        if self.repair_override_enabled:
            raise ValueError("repair_override_enabled must be false for true same-model SC")
        if self.cost_ceiling_usd is None:
            raise ValueError("cost_ceiling_usd is required")
        if float(self.cost_ceiling_usd) <= 0:
            raise ValueError("cost_ceiling_usd must be positive")


@dataclass
class SampleRecord:
    sample_index: int
    raw_text: str
    extracted_answer: str | None
    success: bool
    attempt_count: int = 1
    input_tokens: int = 0
    output_tokens: int = 0
    latency_seconds: float = 0.0
    estimated_cost_usd: float = 0.0
    provider_request_id: str | None = None
    seed: int | None = None
    error: str = ""


@dataclass
class ExampleSCResult:
    example_id: str
    samples: list[SampleRecord]
    selected_answer: str | None
    answer_votes: dict[str, int]
    tie_break_rule: str = TIE_BREAK_RULE
    n_requested: int = 6
    n_raw_attempts: int = 0
    n_successful_responses: int = 0
    n_valid_extracted_answers: int = 0
    status: SCValidationStatus = SCValidationStatus.VALID_N_INDEPENDENT_GENERATIONS
    notes: list[str] = field(default_factory=list)


def plurality_select(extracted_answers: Sequence[str | None]) -> tuple[str | None, dict[str, int]]:
    """Deterministic max-votes then lexicographic normalized-key tie-break (gold-free)."""
    answers: list[str] = []
    norm_to_raw: dict[str, str] = {}
    for raw in extracted_answers:
        if raw is None:
            continue
        text = str(raw).strip()
        if not text:
            continue
        key = normalize_answer_group_key(text)
        if not key:
            continue
        if key not in norm_to_raw:
            norm_to_raw[key] = text
        answers.append(key)
    votes = dict(Counter(answers))
    if not votes:
        return None, votes
    max_v = max(votes.values())
    ties = sorted(k for k, v in votes.items() if v == max_v)
    selected_key = ties[0]
    return norm_to_raw.get(selected_key, selected_key), votes


def count_valid_extracted(samples: Sequence[SampleRecord]) -> int:
    return sum(1 for s in samples if s.success and str(s.extracted_answer or "").strip())


def aggregate_example(
    *,
    example_id: str,
    samples: Sequence[SampleRecord],
    n_requested: int,
) -> ExampleSCResult:
    if len(samples) != n_requested:
        status = SCValidationStatus.INVALID_INCOMPLETE_SAMPLES
    elif any(not s.success for s in samples):
        status = SCValidationStatus.INVALID_INCOMPLETE_SAMPLES
    elif count_valid_extracted(samples) < n_requested:
        # All API successes required; empty extractions still incomplete for strict N scoring
        status = SCValidationStatus.INVALID_INCOMPLETE_SAMPLES
    else:
        status = SCValidationStatus.VALID_N_INDEPENDENT_GENERATIONS

    selected, votes = plurality_select([s.extracted_answer for s in samples])
    return ExampleSCResult(
        example_id=example_id,
        samples=list(samples),
        selected_answer=selected,
        answer_votes=votes,
        n_requested=n_requested,
        n_raw_attempts=sum(max(1, int(s.attempt_count)) for s in samples),
        n_successful_responses=sum(1 for s in samples if s.success),
        n_valid_extracted_answers=count_valid_extracted(samples),
        status=status,
    )


def validate_historical_controller_record(
    record: Mapping[str, Any],
    *,
    required_n: int = 6,
) -> SCValidationStatus:
    """Reject B=6 expand+verify SC packages that claim call_count=N without N generations."""
    md = record.get("result_metadata") or {}
    call_count = md.get("call_count")
    nodes = record.get("final_nodes") or []
    n_pred = sum(1 for n in nodes if str(n.get("predicted_answer") or "").strip())
    n_text = sum(1 for n in nodes if str(n.get("reasoning_text") or "").strip())
    final_src = str(record.get("final_answer_source") or "")

    if call_count == required_n and max(n_pred, n_text) < required_n:
        return SCValidationStatus.INVALID_NOT_SIX_INDEPENDENT_GENERATIONS
    if call_count == required_n and max(n_pred, n_text) <= required_n // 2:
        return SCValidationStatus.INVALID_CONTROLLER_BRANCH_PATTERN
    if final_src == "repair_layer":
        # Historical SC fair methods always set this; treat as override contamination signal
        meta_sel = (md.get("selected_answer") or "")
        stored = record.get("final_answer_canonical") or record.get("selected_answer_canonical") or ""
        if normalize_answer_group_key(str(meta_sel)) != normalize_answer_group_key(str(stored)):
            return SCValidationStatus.INVALID_REPAIR_OVERRIDE_PRESENT
    if call_count == required_n and n_pred == 0 and n_text == 0:
        return SCValidationStatus.INVALID_CALL_COUNT_WITHOUT_GENERATIONS
    if n_pred >= required_n and all(
        str((nodes[i] if i < len(nodes) else {}).get("predicted_answer") or "").strip() for i in range(required_n)
    ):
        return SCValidationStatus.VALID_N_INDEPENDENT_GENERATIONS
    return SCValidationStatus.INVALID_NOT_SIX_INDEPENDENT_GENERATIONS


def assert_table2_ids(expected: Iterable[str], actual: Iterable[str]) -> None:
    exp, act = set(expected), set(actual)
    if exp != act:
        missing = sorted(exp - act)[:5]
        extra = sorted(act - exp)[:5]
        raise ValueError(f"Table-2 ID mismatch: missing={missing} extra={extra} |Δ|={len(exp ^ act)}")


def assert_single_model(model_ids: Sequence[str]) -> None:
    uniq = {m for m in model_ids if m}
    if len(uniq) != 1:
        raise ValueError(f"model IDs must be identical within a cell; got {sorted(uniq)}")


def resource_accounting(samples: Sequence[SampleRecord]) -> dict[str, Any]:
    return {
        "requested_samples": len(samples),
        "raw_api_attempts": sum(max(1, int(s.attempt_count)) for s in samples),
        "successful_api_responses": sum(1 for s in samples if s.success),
        "valid_extracted_answers": count_valid_extracted(samples),
        "retries_beyond_first": sum(max(0, int(s.attempt_count) - 1) for s in samples),
        "input_tokens": sum(int(s.input_tokens) for s in samples),
        "output_tokens": sum(int(s.output_tokens) for s in samples),
        "total_tokens": sum(int(s.input_tokens) + int(s.output_tokens) for s in samples),
        "latency_seconds_sum": sum(float(s.latency_seconds) for s in samples),
        "estimated_cost_usd": sum(float(s.estimated_cost_usd) for s in samples),
    }


def resume_missing_indices(existing: Sequence[SampleRecord], n_requested: int) -> list[int]:
    """Return sample indices still needed; existing valid indices are immutable."""
    have = {s.sample_index for s in existing if s.success and 0 <= s.sample_index < n_requested}
    return [i for i in range(n_requested) if i not in have]


def merge_immutable_samples(
    existing: Sequence[SampleRecord],
    new_samples: Sequence[SampleRecord],
    n_requested: int,
) -> list[SampleRecord]:
    by_idx = {s.sample_index: s for s in existing if 0 <= s.sample_index < n_requested}
    for s in new_samples:
        if s.sample_index in by_idx and by_idx[s.sample_index].success:
            raise ValueError(f"refusing to overwrite immutable sample_index={s.sample_index}")
        by_idx[s.sample_index] = s
    return [by_idx[i] for i in range(n_requested) if i in by_idx]
