from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
PLOT_DATA_DIR = REPO_ROOT / "outputs" / "paper_plot_data"
TABLE_DIR = REPO_ROOT / "outputs" / "paper_tables"

CANONICAL_IMPORT_RUN = REPO_ROOT / "outputs" / "imported_methodology_frontier_eval" / "20260417T000000Z"
CANONICAL_NEAR_TIE_RUN = (
    REPO_ROOT
    / "outputs"
    / "branch_label_bruteforce_learning"
    / "near_tie_two_stage_complementarity_audit_upgrade_20260417"
)
CANONICAL_TERNARY_RUN = (
    REPO_ROOT / "outputs" / "branch_label_bruteforce_learning" / "soft_prob_tie_matched_20260417"
)
CANONICAL_BRANCH_SCORER_RUN = REPO_ROOT / "outputs" / "branch_scorer_v3_final_eval"

METHOD_NAME_MAP = {
    "adaptive_budget_guarded": "Adaptive Budget Guarded",
    "reasoning_beam2": "Reasoning Beam-2",
    "self_consistency_3": "Self-Consistency-3",
    "reasoning_greedy": "Reasoning Greedy",
    "verifier_guided_search": "Verifier-Guided Search",
    "program_of_thought": "Program-of-Thought",
    "oracle_frontier_upper_bound": "Oracle Frontier Upper Bound",
    "strict_coupled_near_tie_specialized_pointwise_v1": "Strict-Coupled Near-Tie Specialized Pointwise v1",
    "binary_forced_baseline": "Binary Forced Baseline",
    "strict_coupled_tie_aware_posthoc_deferral_v1": "Strict-Coupled Tie-Aware Posthoc Deferral v1",
}

METHOD_ORDER = [
    "Adaptive Budget Guarded",
    "Reasoning Beam-2",
    "Self-Consistency-3",
    "Reasoning Greedy",
    "Verifier-Guided Search",
    "Program-of-Thought",
    "Oracle Frontier Upper Bound",
]


def canonical_method_name(raw: str) -> str:
    return METHOD_NAME_MAP.get(raw, raw)


def ensure_exists(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Required canonical artifact is missing: {path}")


def read_csv(path: Path) -> list[dict[str, str]]:
    ensure_exists(path)
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError(f"Refusing to write empty CSV: {path}")
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def to_float(row: dict[str, str], key: str) -> float:
    return float(row[key])


def to_int(row: dict[str, str], key: str) -> int:
    return int(float(row[key]))
