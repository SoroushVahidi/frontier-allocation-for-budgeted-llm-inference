"""Label-free semantic reasoning-family features for diagnostic controllers.

Does not use gold labels or correctness at inference. Used for clustering
early branches into families and computing redundancy and maturation stats.
"""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from typing import Any

from experiments.problem_type_utils import classify_problem_type

_WORD_RE = re.compile(r"[a-z0-9]+", re.I)
_NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")


def _tok_set(text: str) -> set[str]:
    return {m.group(0).lower() for m in _WORD_RE.finditer(text or "") if len(m.group(0)) > 1}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    u = a | b
    if not u:
        return 0.0
    return len(a & b) / len(u)


def extract_numeric_mentions(text: str) -> tuple[str, ...]:
    s = str(text or "")
    nums = sorted({_norm_num(m.group(0)) for m in _NUM_RE.finditer(s) if m.group(0)}, key=lambda x: (len(x), x))[:8]
    return tuple(nums)


def _norm_num(n: str) -> str:
    t = n.strip()
    if re.fullmatch(r"-?\d+\.0+", t):
        t = t.split(".")[0]
    return t


def infer_branch_pattern_type(question: str, step1: str, step2: str) -> str:
    q = (question or "").lower()
    t = f"{step1} {step2}".lower()
    if any(k in t for k in ("\\frac", "ratio", "percent", "%", "proportion")) or "percent" in q:
        return "ratio_percent"
    if any(k in t for k in ("choose", "permutation", "combination", "c(", " ways ")) or "how many" in q:
        return "counting_combinatorics"
    if "equation" in t or "solve" in t or "let " in t:
        return "equation_setup"
    if any(k in t for k in ("/", "per ", "per hour", "rate", " mph ", " m/s")):
        return "unit_rate"
    if "short" in t or "instead" in t or "simpl" in t:
        return "arithmetic_shortcut"
    if "case" in t or " first " in t and " then " in t:
        return "case_split"
    if any(k in t for k in ("compare", "greater", "less", "difference ")):
        return "comparison"
    if "elimin" in t or "cannot be" in t or " not possible" in t:
        return "science_elimination"
    if "plan" in t or "step" in t[:20]:
        return "planning"
    return "general"


def infer_operation_type(question: str, branch_text: str) -> str:
    return classify_problem_type(f"{question}\n{branch_text}")


def _first_step_text(steps: list[str]) -> str:
    if not steps:
        return ""
    return str(steps[0] or "")


def _second_step_text(steps: list[str]) -> str:
    if len(steps) < 2:
        return ""
    return str(steps[1] or "")


def _answer_group_bucket(predicted: str | None) -> str:
    if not predicted:
        return "__no_answer__"
    t = re.sub(r"\s+", " ", str(predicted).strip().lower())[:32]
    return t or "__empty__"


def semantic_family_key_and_features(
    *,
    question: str,
    strategy_family: str,
    steps: list[str],
    predicted_answer: str | None = None,
) -> tuple[str, dict[str, Any]]:
    s1 = _first_step_text(steps)
    s2 = _second_step_text(steps)
    pattern = infer_branch_pattern_type(question, s1, s2)
    op = infer_operation_type(question, f"{s1}\n{s2}")
    nums_q = extract_numeric_mentions(question)
    nums_b = extract_numeric_mentions(f"{s1} {s2}")
    t1, t2 = _tok_set(s1), _tok_set(s2)
    sim12 = _jaccard(t1, t2)
    ag = _answer_group_bucket(predicted_answer)
    raw = f"{pattern}|{op}|{strategy_family}|{ag}|{sim12:.3f}|{nums_q[:3]}|{nums_b[:3]}|{s1[:40]}|{s2[:40]}"
    key = "sf_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
    features: dict[str, Any] = {
        "pattern_type": pattern,
        "operation_type": op,
        "strategy_family_label": str(strategy_family or ""),
        "answer_group_bucket": ag,
        "first_second_jaccard": float(sim12),
        "question_numeric_fingerprint": "|".join(nums_q[:4]),
        "branch_numeric_fingerprint": "|".join(nums_b[:4]),
        "first_step_len": len(s1),
        "second_step_len": len(s2),
    }
    return key, features


def family_redundancy_ratio(semantic_keys: list[str]) -> float:
    if not semantic_keys:
        return 0.0
    c = len(semantic_keys)
    u = len(set(semantic_keys))
    return float(0.0 if c == 0 else 1.0 - (u / c))


def root_semantic_family_snapshot(
    *,
    question: str,
    branches: list[Any],
    branch_family_ids: dict[str, str],
    root_family_ids: set[str] | frozenset[str],
    branch_strategy_family: dict[str, str],
    min_depth: int,
) -> dict[str, Any]:
    by_sem: dict[str, list[dict[str, Any]]] = defaultdict(list)
    root_branch_count = 0
    for b in branches:
        if b.is_pruned:
            continue
        rid = str(branch_family_ids.get(b.branch_id) or b.branch_id)
        if rid not in set(root_family_ids):
            continue
        root_branch_count += 1
        sf = str(branch_strategy_family.get(b.branch_id, "unknown_seed_family"))
        sk, feat = semantic_family_key_and_features(
            question=question,
            strategy_family=sf,
            steps=list(getattr(b, "steps", []) or []),
            predicted_answer=getattr(b, "predicted_answer", None),
        )
        d = int(getattr(b, "depth", len(getattr(b, "steps", []) or [])) or 0)
        is_invalid = len((getattr(b, "steps", []) or [])) == 0 and d == 0
        by_sem[sk].append(
            {
                "branch_id": str(b.branch_id),
                "depth": d,
                "is_done": bool(getattr(b, "is_done", False)),
                "is_invalid": is_invalid,
                "features": feat,
            }
        )
    fam_keys = list(by_sem.keys())
    semantic_family_count = len(fam_keys)
    keys_for_redund: list[str] = []
    for k, members in by_sem.items():
        keys_for_redund.extend([k] * max(1, len(members)))
    redundancy = family_redundancy_ratio(keys_for_redund) if len(keys_for_redund) > 1 else 0.0

    families_at_d2: list[str] = []
    families_at_d3: list[str] = []
    pending: list[str] = []
    invalid_or_stalled: list[str] = []
    for sk, members in by_sem.items():
        max_d = max((m["depth"] for m in members), default=0)
        if max_d >= 2:
            families_at_d2.append(sk)
        if max_d >= 3:
            families_at_d3.append(sk)
        all_done = all(m["is_done"] for m in members) if members else True
        all_invalid = all(m.get("is_invalid") for m in members) if members else False
        if all_invalid:
            invalid_or_stalled.append(sk)
        elif max_d < min_depth and not all_done:
            pending.append(sk)
        elif max_d < min_depth and all_done and members:
            invalid_or_stalled.append(sk)  # stalled shallow completion

    maturation_satisfied = min_depth <= 0 or (len(pending) == 0) or (not by_sem and root_branch_count == 0)
    if fam_keys and min_depth > 0:
        maturation_satisfied = len(pending) == 0

    return {
        "semantic_families": {k: v for k, v in by_sem.items()},
        "root_branch_count": int(root_branch_count),
        "semantic_family_count": int(semantic_family_count),
        "family_redundancy_ratio": float(redundancy),
        "families_reaching_depth_ge_2": families_at_d2,
        "families_reaching_depth_ge_3": families_at_d3,
        "families_pending_maturation": pending,
        "families_invalid_or_stalled": invalid_or_stalled,
        "maturation_satisfied": bool(maturation_satisfied or min_depth <= 0),
    }


def compute_branching_necessity_score(
    *,
    question: str,
    semantic_family_count: int,
    family_redundancy_ratio: float,
    top_support: float,
    answer_entropy: float,
    support_margin: float,
) -> tuple[float, dict[str, float]]:
    """Label-free 0-1 score; higher => frontier branching is more justified."""
    q = (question or "").strip()
    n_words = max(1, len(q.split()))
    n_num = len(extract_numeric_mentions(q))
    complexity = min(1.0, 0.25 * (n_num >= 2) + 0.12 * (n_words / 40.0) + 0.1 * (len(q) / 200.0))
    diversity = min(1.0, 0.15 * min(4, semantic_family_count))
    redundancy = min(1.0, family_redundancy_ratio) * 0.2
    concentration = (1.0 - top_support) * 0.2
    gap = min(1.0, support_margin) * 0.12
    ent = min(1.0, answer_entropy) * 0.13
    score = min(1.0, max(0.0, diversity + concentration + ent + gap + complexity - redundancy))
    parts = {
        "complexity": float(complexity),
        "diversity": float(diversity),
        "redundancy": float(redundancy),
        "concentration": float(concentration),
        "top2_margin_component": float(gap),
        "entropy_component": float(ent),
    }
    return float(score), parts
