#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_DOCS = [
    "docs/CANONICAL_PROJECT_STATE_AND_NEXT_STEPS_20260429.md",
    "docs/METHOD_REGISTRY_CANONICAL_20260429.md",
    "docs/RESULTS_INDEX_CANONICAL_20260429.md",
    "docs/SCRIPT_REGISTRY_CANONICAL_20260429.md",
    "docs/ANSWER_GROUPED_OUTCOME_VERIFIER_RERANK_V1.md",
]


LIVE_COMPARISON_SET = {
    "external_l1_max",
    "strict_f3",
    "strict_gate1_cap_k6",
    "strict_f2",
    "direct_reserve_semantic_frontier_v1",
    "direct_reserve_semantic_frontier_v2",
    "direct_reserve_semantic_frontier_v2_selection_fix_v1",
    "direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1",
    "direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1",
    "near_direct_reserve_frontier_gate_v1",
    "calibrated_near_direct_frontier_gate_v1",
}


def parse_registry_rows(registry_text: str) -> list[list[str]]:
    rows = []
    for line in registry_text.splitlines():
        if not line.strip().startswith("|") or "method ID" in line or "---" in line:
            continue
        cols = [c.strip() for c in line.strip("|").split("|")]
        if len(cols) >= 12:
            rows.append(cols)
    return rows


def main() -> int:
    errors: list[str] = []
    missing = [p for p in REQUIRED_DOCS if not (REPO_ROOT / p).exists()]
    if missing:
        errors.append(f"Missing required docs: {missing}")

    registry_text = (REPO_ROOT / "docs/METHOD_REGISTRY_CANONICAL_20260429.md").read_text(encoding="utf-8")
    state_doc = (REPO_ROOT / "docs/CANONICAL_PROJECT_STATE_AND_NEXT_STEPS_20260429.md").read_text(encoding="utf-8")

    for cols in parse_registry_rows(registry_text):
        method_id, live, diagnostic = cols[0], cols[2].lower(), cols[3].lower()
        if method_id == "direct_reserve_semantic_frontier_v2_thresholded_ordered" and live == "yes":
            errors.append("thresholded_ordered must not be listed live-runnable")
        if live == "yes" and method_id not in LIVE_COMPARISON_SET and method_id not in {"strict_f3_anti_collapse_weak_v1"}:
            errors.append(f"live-runnable method missing from known live comparison set: {method_id}")
        if diagnostic == "yes" and method_id in LIVE_COMPARISON_SET:
            errors.append(f"diagnostic-only method included in live comparison set: {method_id}")

    if "direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1" not in state_doc:
        errors.append("next recommended method is missing outcome verifier rerank v1")

    if errors:
        for e in errors:
            print(f"ERROR: {e}")
        return 1
    print("Repository status consistency checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
