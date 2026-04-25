"""Diagnostic reasoning-diversity feature extraction and scoring utilities."""

from __future__ import annotations

from collections import Counter
import re
from typing import Any


_OPERATION_HINTS: list[tuple[str, tuple[str, ...]]] = [
    ("percentage", ("%", "percent", "percentage")),
    ("ratio", ("ratio", "proportion", "per ", "\bper\b")),
    ("unit_conversion", ("convert", "unit", "km", "cm", "meter", "mile", "inch", "hour", "minute")),
    ("case_split", ("case", "cases", "if ", "split")),
    ("enumeration", ("enumerate", "list", "count", "ways", "possibilities", "possible")),
    ("equation_setup", ("equation", "let ", "solve for", "=")),
    ("verification", ("check", "verify", "sanity", "confirm")),
    ("add", ("+", " sum", "total", "combined", "together")),
    ("subtract", ("-", "remaining", "left", "less than", "difference")),
    ("multiply", ("*", "times", "twice", "double", "product", "each")),
    ("divide", ("/", "divide", "average", "quotient", "half")),
]

_ROLE_LABELS: tuple[str, ...] = (
    "direct_solve",
    "case_split",
    "enumeration_or_decomposition",
    "small_example_pattern",
    "verification",
    "unit_conversion",
    "equation_setup",
    "unknown",
)


def _safe_text(text: str | None) -> str:
    return str(text or "").strip()


def extract_operation_sequence(text: str, question: str | None = None) -> list[str]:
    """Extract a coarse operation sequence from branch reasoning text."""
    joined = f"{_safe_text(question)}\n{_safe_text(text)}".lower()
    if not joined.strip():
        return ["unknown"]

    ops: list[str] = []
    for op, hints in _OPERATION_HINTS:
        for hint in hints:
            if hint.startswith("\\b"):
                if re.search(hint, joined):
                    ops.append(op)
                    break
            elif hint in joined:
                ops.append(op)
                break

    if re.search(r"\d+\s*/\s*\d+", joined) and "divide" not in ops:
        ops.append("divide")
    if re.search(r"\d+\s*\+\s*\d+", joined) and "add" not in ops:
        ops.append("add")
    if re.search(r"\d+\s*\-\s*\d+", joined) and "subtract" not in ops:
        ops.append("subtract")
    if re.search(r"\d+\s*\*\s*\d+", joined) and "multiply" not in ops:
        ops.append("multiply")

    return ops or ["unknown"]


def extract_intermediate_values(text: str) -> set[str]:
    """Extract normalized numeric values (ints/decimals/fractions/percentages)."""
    raw = _safe_text(text)
    if not raw:
        return set()

    values: set[str] = set()
    for pct in re.findall(r"[-+]?\d+(?:\.\d+)?\s*%", raw):
        values.add(pct.replace(" ", ""))
    for frac in re.findall(r"[-+]?\d+\s*/\s*\d+", raw):
        values.add(re.sub(r"\s+", "", frac))
    for num in re.findall(r"[-+]?\d+(?:\.\d+)?", raw):
        if "." in num:
            values.add(str(float(num)).rstrip("0").rstrip("."))
        else:
            values.add(str(int(num)))
    return values


def infer_reasoning_role(text: str, strategy_family: str | None = None) -> str:
    """Infer a coarse reasoning role from metadata/text."""
    fam = _safe_text(strategy_family).lower()
    body = _safe_text(text).lower()
    joined = f"{fam} {body}".strip()
    if not joined:
        return "unknown"

    if any(t in joined for t in ("verify", "check", "sanity")):
        return "verification"
    if any(t in joined for t in ("unit", "convert", "km", "cm", "hour", "minute")):
        return "unit_conversion"
    if any(t in joined for t in ("equation", "let ", "solve for", "algebra")):
        return "equation_setup"
    if any(t in joined for t in ("case", "if ", "split")):
        return "case_split"
    if any(t in joined for t in ("enumerate", "list", "count", "decompose", "ways")):
        return "enumeration_or_decomposition"
    if any(t in joined for t in ("example", "try n=", "small n", "pattern")):
        return "small_example_pattern"
    if re.search(r"\d", joined):
        return "direct_solve"
    return "unknown"


def _normalize_answer_group(answer: Any) -> str:
    if answer is None:
        return "__unknown__"
    txt = str(answer).strip()
    return txt if txt else "__unknown__"


def reasoning_signature(branch: Any, question: str | None = None) -> dict[str, Any]:
    """Build a robust signature from a BranchState-like object."""
    steps = getattr(branch, "steps", None)
    text = "\n".join(str(s) for s in steps) if isinstance(steps, list) and steps else ""
    text_available = bool(text.strip())
    op_seq = extract_operation_sequence(text, question=question)
    op_key = "|".join(op_seq)
    strategy_family = str(getattr(branch, "strategy_family", "") or "unknown")
    answer_group = _normalize_answer_group(getattr(branch, "predicted_answer", None))
    role = infer_reasoning_role(text, strategy_family=strategy_family)
    ints = sorted(extract_intermediate_values(text))
    sig_key = f"{strategy_family}::{op_key}::{role}::{answer_group}"
    return {
        "operation_sequence": op_seq,
        "operation_sequence_key": op_key,
        "intermediate_values": ints,
        "reasoning_role": role,
        "strategy_family": strategy_family,
        "answer_group": answer_group,
        "signature_key": sig_key,
        "text_available": text_available,
    }


def compute_reasoning_diversity_components(
    candidate_signature: dict[str, Any], existing_signatures: list[dict[str, Any]]
) -> dict[str, float]:
    """Compute novelty/redundancy/plausibility components and combined diagnostic bonus."""
    existing = existing_signatures or []
    fam_counts = Counter(str(s.get("strategy_family", "unknown")) for s in existing)
    op_counts = Counter(str(s.get("operation_sequence_key", "unknown")) for s in existing)
    role_counts = Counter(str(s.get("reasoning_role", "unknown")) for s in existing)
    ans_seen = {str(s.get("answer_group", "__unknown__")) for s in existing}
    ints_seen = {str(v) for s in existing for v in list(s.get("intermediate_values", []))}

    fam = str(candidate_signature.get("strategy_family", "unknown"))
    op_key = str(candidate_signature.get("operation_sequence_key", "unknown"))
    role = str(candidate_signature.get("reasoning_role", "unknown"))
    ans = str(candidate_signature.get("answer_group", "__unknown__"))
    cand_ints = {str(v) for v in list(candidate_signature.get("intermediate_values", []))}

    strategy_family_novelty = 1.0 if fam_counts.get(fam, 0) == 0 else (0.5 if fam_counts.get(fam, 0) <= 1 else 0.0)

    if op_counts.get(op_key, 0) == 0:
        operation_sequence_novelty = 1.0
    else:
        cand_ops = set(str(op_key).split("|"))
        seen_ops = set()
        for k in op_counts:
            seen_ops.update(str(k).split("|"))
        unseen_frac = len([o for o in cand_ops if o and o not in seen_ops]) / max(1, len([o for o in cand_ops if o]))
        operation_sequence_novelty = 0.5 if unseen_frac > 0 else 0.0

    if cand_ints:
        intermediate_value_novelty = max(0.0, min(1.0, len(cand_ints - ints_seen) / max(1, len(cand_ints))))
    else:
        intermediate_value_novelty = 0.0

    answer_group_novelty = 1.0 if ans not in ans_seen else 0.0
    reasoning_role_novelty = 1.0 if role_counts.get(role, 0) == 0 else (0.5 if role_counts.get(role, 0) <= 1 else 0.0)

    exact_duplicates = [
        s
        for s in existing
        if str(s.get("strategy_family", "")) == fam
        and str(s.get("operation_sequence_key", "")) == op_key
        and str(s.get("answer_group", "")) == ans
    ]
    redundancy_penalty = min(1.0, 0.7 if exact_duplicates else 0.0)

    has_text = bool(candidate_signature.get("text_available", False))
    has_numbers = bool(cand_ints)
    has_coherent_ops = op_key not in {"", "unknown"}
    plausibility_score = 0.5 if not has_text else min(1.0, 0.2 + (0.4 if has_numbers else 0.0) + (0.4 if has_coherent_ops else 0.0))

    raw_bonus = (
        0.40 * strategy_family_novelty
        + 0.30 * operation_sequence_novelty
        + 0.25 * intermediate_value_novelty
        + 0.20 * answer_group_novelty
        + 0.20 * reasoning_role_novelty
        - 0.50 * redundancy_penalty
    )
    useful_reasoning_diversity_bonus = max(0.0, raw_bonus) * plausibility_score

    return {
        "strategy_family_novelty": float(strategy_family_novelty),
        "operation_sequence_novelty": float(operation_sequence_novelty),
        "intermediate_value_novelty": float(intermediate_value_novelty),
        "answer_group_novelty": float(answer_group_novelty),
        "reasoning_role_novelty": float(reasoning_role_novelty),
        "redundancy_penalty": float(redundancy_penalty),
        "plausibility_score": float(plausibility_score),
        "useful_reasoning_diversity_bonus": float(useful_reasoning_diversity_bonus),
    }
