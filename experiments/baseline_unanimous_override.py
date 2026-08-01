"""Gold-free baseline-unanimous override utility (post-hoc / finalizer only)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from experiments.frontier_max_support_tiebreak import normalize_answer_group_key

BASELINE_UNANIMOUS_OVERRIDE_POLICY_VERSION = "20260706_v1"
MCQ_DATASETS = frozenset({"gpqa_diamond"})
LETTER_RE = re.compile(r"^\s*(?:option\s*)?\(?([A-D])\)?\s*$", re.IGNORECASE)
BOXED_RE = re.compile(r"\\boxed\{([^{}]+)\}")
FORBIDDEN_OVERRIDE_FEATURE_KEYS = frozenset(
    {
        "gold_answer",
        "gold_in_tree",
        "is_correct",
        "oracle",
        "exact_match",
        "correct_answer",
        "d6_bucket",
        "d9_bucket",
    }
)

BASELINE_LABELS = ("L1", "S1", "TALE")


@dataclass(frozen=True)
class BaselineUnanimousOverrideResult:
    selected_answer: str | None
    metadata: dict[str, Any]


def clean_answer_text(answer: Any) -> str:
    text = str(answer or "").strip()
    if not text:
        return ""
    boxed = BOXED_RE.search(text)
    if boxed:
        return boxed.group(1).strip()
    return text


def is_baseline_answer_valid(answer: Any, *, dataset: str = "", question: str = "") -> bool:
    """Gold-free validity check for baseline answers used by the override gate."""
    cleaned = clean_answer_text(answer)
    if not cleaned:
        return False
    lowered = cleaned.lower()
    if lowered in {"__unknown__", "unknown", "none", "null"}:
        return False
    if dataset in MCQ_DATASETS or "Answer with a single letter" in (question or ""):
        return bool(LETTER_RE.match(cleaned)) or lowered == "none"
    nums = re.findall(r"[-+]?\d+(?:\.\d+)?", cleaned.replace(",", ""))
    if nums:
        return True
    # For numeric-heavy datasets accept any non-empty cleaned answer; for symbolic/text
    # require at least one alphanumeric token so empty punctuation-only strings fail.
    if dataset in {"gsm8k", "math500", "openai/gsm8k", "huggingfaceh4/math-500"}:
        return True
    return bool(re.search(r"[A-Za-z0-9]", cleaned))


def normalize_final_answer_group(answer: Any) -> tuple[str, str]:
    raw = clean_answer_text(answer)
    if not raw:
        return "", ""
    group = normalize_answer_group_key(raw) or ""
    return raw, group


def _base_metadata(
    *,
    enabled: bool,
    before_answer: str,
    after_answer: str,
    reason: str,
) -> dict[str, Any]:
    return {
        "baseline_unanimous_override_enabled": bool(enabled),
        "baseline_unanimous_override_applied": False,
        "baseline_unanimous_override_reason": str(reason),
        "baseline_unanimous_override_before_answer": before_answer,
        "baseline_unanimous_override_after_answer": after_answer,
        "baseline_unanimous_override_baseline_answer": "",
        "baseline_unanimous_override_normalized_fta": "",
        "baseline_unanimous_override_normalized_baselines": {},
        "baseline_unanimous_override_available_baselines": [],
        "baseline_unanimous_override_policy_version": BASELINE_UNANIMOUS_OVERRIDE_POLICY_VERSION,
    }


def apply_baseline_unanimous_override(
    fta_answer: str | None,
    l1_answer: str | None,
    s1_answer: str | None,
    tale_answer: str | None,
    *,
    enabled: bool = False,
    dataset: str = "",
    question: str = "",
) -> BaselineUnanimousOverrideResult:
    """Apply unanimous baseline override policy; never uses gold or correctness fields."""
    before_raw, before_group = normalize_final_answer_group(fta_answer)
    before_s = before_raw
    meta = _base_metadata(enabled=enabled, before_answer=before_s, after_answer=before_s, reason="disabled")
    meta["baseline_unanimous_override_normalized_fta"] = before_group

    if not enabled:
        return BaselineUnanimousOverrideResult(selected_answer=fta_answer if before_s else None, metadata=meta)

    meta["baseline_unanimous_override_reason"] = "not_evaluated"
    baseline_inputs = {
        "L1": l1_answer,
        "S1": s1_answer,
        "TALE": tale_answer,
    }
    available: list[str] = []
    normalized_by_label: dict[str, str] = {}
    raw_by_label: dict[str, str] = {}

    for label, answer in baseline_inputs.items():
        raw, group = normalize_final_answer_group(answer)
        if not raw:
            meta["baseline_unanimous_override_reason"] = f"missing_baseline_answer_{label.lower()}"
            meta["baseline_unanimous_override_available_baselines"] = available
            return BaselineUnanimousOverrideResult(selected_answer=fta_answer if before_s else None, metadata=meta)
        if not is_baseline_answer_valid(raw, dataset=dataset, question=question):
            meta["baseline_unanimous_override_reason"] = f"invalid_baseline_answer_{label.lower()}"
            meta["baseline_unanimous_override_available_baselines"] = available
            meta["baseline_unanimous_override_normalized_baselines"] = dict(normalized_by_label)
            return BaselineUnanimousOverrideResult(selected_answer=fta_answer if before_s else None, metadata=meta)
        available.append(label)
        normalized_by_label[label] = group
        raw_by_label[label] = raw

    meta["baseline_unanimous_override_available_baselines"] = list(available)
    meta["baseline_unanimous_override_normalized_baselines"] = dict(normalized_by_label)

    groups = set(normalized_by_label.values())
    if len(groups) != 1:
        meta["baseline_unanimous_override_reason"] = "baselines_disagree"
        return BaselineUnanimousOverrideResult(selected_answer=fta_answer if before_s else None, metadata=meta)

    unanimous_group = next(iter(groups))
    if not unanimous_group:
        meta["baseline_unanimous_override_reason"] = "empty_unanimous_group"
        return BaselineUnanimousOverrideResult(selected_answer=fta_answer if before_s else None, metadata=meta)

    if before_group and before_group == unanimous_group:
        meta["baseline_unanimous_override_reason"] = "fta_already_matches_unanimous_baselines"
        return BaselineUnanimousOverrideResult(selected_answer=fta_answer if before_s else None, metadata=meta)

    if not before_group and not before_s:
        meta["baseline_unanimous_override_reason"] = "missing_fta_answer"
        return BaselineUnanimousOverrideResult(selected_answer=None, metadata=meta)

    # Deterministic representative: first valid baseline in L1, S1, TALE order.
    chosen_answer = raw_by_label["L1"]
    meta["baseline_unanimous_override_applied"] = True
    meta["baseline_unanimous_override_reason"] = "all_three_baselines_agree_against_fta"
    meta["baseline_unanimous_override_baseline_answer"] = chosen_answer
    meta["baseline_unanimous_override_after_answer"] = chosen_answer
    return BaselineUnanimousOverrideResult(selected_answer=chosen_answer, metadata=meta)


def apply_baseline_unanimous_override_from_mapping(
    fta_answer: str | None,
    baseline_answers: dict[str, str | None],
    *,
    enabled: bool = False,
    dataset: str = "",
    question: str = "",
) -> BaselineUnanimousOverrideResult:
    """Convenience wrapper using label->answer mapping keys L1/S1/TALE."""
    return apply_baseline_unanimous_override(
        fta_answer,
        baseline_answers.get("L1"),
        baseline_answers.get("S1"),
        baseline_answers.get("TALE"),
        enabled=enabled,
        dataset=dataset,
        question=question,
    )
