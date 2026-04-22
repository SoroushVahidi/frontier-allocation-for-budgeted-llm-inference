#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]

CANONICAL_RANKING = REPO_ROOT / "outputs/canonical_full_method_ranking_20260421T212948Z/overall_ranking.csv"
ADJACENT_BUNDLE = REPO_ROOT / "outputs/external_adjacent_baseline_bundle/20260422T201000Z/summary.csv"


@dataclass(frozen=True)
class Decision:
    readiness: str
    claim_boundary: str
    fairness_for_main_table: str
    scientific_meaningfulness: str
    recommendation_reason: str


DECISION_OVERRIDES: dict[str, Decision] = {
    "s1_simple_test_time_scaling": Decision(
        readiness="main_table_ready",
        claim_boundary="MODE A only (inference-only adapter; not official full-stack reproduction)",
        fairness_for_main_table="yes_with_mode_a_boundary",
        scientific_meaningfulness="near_direct practical compute-scaling comparator",
        recommendation_reason="Included in canonical ranking with auditable rows; near-direct matched-substrate comparator.",
    ),
    "tale_token_budget_aware_reasoning": Decision(
        readiness="main_table_ready",
        claim_boundary="MODE A only (prompt-budgeting adapter; not official TALE-PT/full stack)",
        fairness_for_main_table="yes_with_mode_a_boundary",
        scientific_meaningfulness="near_direct/adjacent practical token-budgeting comparator",
        recommendation_reason="Included in canonical ranking with auditable rows; strong practical neighbor under shared budget accounting.",
    ),
    "l1_length_control_rl": Decision(
        readiness="main_table_ready",
        claim_boundary="MODE A only (external_l1_exact/external_l1_max adapter rows; not official RL stack)",
        fairness_for_main_table="yes_with_mode_a_boundary",
        scientific_meaningfulness="near_direct practical length-control comparator",
        recommendation_reason="Included in canonical ranking with strongest external row (`external_l1_max`) under matched-substrate conventions.",
    ),
    "best_route_microsoft": Decision(
        readiness="appendix_only",
        claim_boundary="adjacent import-validated routing comparator",
        fairness_for_main_table="no_control_space_mismatch",
        scientific_meaningfulness="adjacent reviewer-useful routing comparator",
        recommendation_reason="Auditable adjacent contract lane exists, but control space differs from frontier allocation.",
    ),
    "when_solve_when_verify": Decision(
        readiness="appendix_only",
        claim_boundary="adjacent solve-vs-verify import-validated comparator",
        fairness_for_main_table="no_control_space_mismatch",
        scientific_meaningfulness="adjacent reviewer-useful comparator",
        recommendation_reason="Official import-validation exists; no direct frontier-control equivalence.",
    ),
    "rest_mcts": Decision(
        readiness="appendix_only",
        claim_boundary="adjacent partial-runnable contract lane only",
        fairness_for_main_table="no_control_space_mismatch",
        scientific_meaningfulness="adjacent search/verifier comparator",
        recommendation_reason="Import-validated + partial-runnable evidence is present, but full stack is out-of-scope.",
    ),
    "tree_plv": Decision(
        readiness="appendix_only",
        claim_boundary="adjacent partial-runnable verifier-learning comparator",
        fairness_for_main_table="no_control_space_mismatch",
        scientific_meaningfulness="adjacent verifier/preference-learning comparator",
        recommendation_reason="Paper-linked provenance plus import-validated partial-runnable lane; still non-equivalent control space.",
    ),
    "lets_verify_step_by_step": Decision(
        readiness="appendix_only",
        claim_boundary="adjacent ingredient/completion-aware comparator",
        fairness_for_main_table="no_control_space_mismatch",
        scientific_meaningfulness="adjacent reviewer-expected verifier family",
        recommendation_reason="Adjacent lane artifacts exist in bundle outputs, but should remain separated from main-table direct ranking.",
    ),
    "cascade_routing": Decision(
        readiness="appendix_only",
        claim_boundary="adjacent import-validated cascade routing comparator",
        fairness_for_main_table="no_control_space_mismatch",
        scientific_meaningfulness="adjacent routing comparator",
        recommendation_reason="Status artifacts and validator evidence exist; remains control-space non-equivalent.",
    ),
    "mob_majority_of_bests": Decision(
        readiness="appendix_only",
        claim_boundary="adjacent import-validated best-of-n style comparator",
        fairness_for_main_table="no_control_space_mismatch",
        scientific_meaningfulness="adjacent selection comparator",
        recommendation_reason="Status artifacts and validator evidence exist; still adjacent query/completion selection family.",
    ),
    "openr": Decision(
        readiness="appendix_only",
        claim_boundary="adjacent import-validated comparator",
        fairness_for_main_table="no_control_space_mismatch",
        scientific_meaningfulness="adjacent reasoning-system comparator",
        recommendation_reason="Status artifacts and validator evidence exist; non-equivalent control space.",
    ),
    "qstar_style_adapter": Decision(
        readiness="repo_only_not_paper_facing_yet",
        claim_boundary="unofficial caveated adapter only",
        fairness_for_main_table="no_unofficial_provenance",
        scientific_meaningfulness="conceptual stress test only",
        recommendation_reason="Runnable but explicitly caveated as unofficial and not official Q* reproduction evidence.",
    ),
    "learning_how_hard_to_think_mode_a": Decision(
        readiness="repo_only_not_paper_facing_yet",
        claim_boundary="paper-inspired MODE A adapter; adjacent",
        fairness_for_main_table="no_missing_artifacts_and_non_equivalent_control",
        scientific_meaningfulness="potentially useful adjacent comparator",
        recommendation_reason="No auditable run artifacts currently present; integration docs already position this lane as caveated and mixed-strength.",
    ),
    "training_free_difficulty_proxies_mode_a": Decision(
        readiness="repo_only_not_paper_facing_yet",
        claim_boundary="paper-inspired MODE A adapter; query-level adjacent",
        fairness_for_main_table="no_missing_artifacts_and_non_equivalent_control",
        scientific_meaningfulness="adjacent query-level budget allocator",
        recommendation_reason="No auditable run artifacts currently present; query-level control is not frontier-equivalent.",
    ),
    "conformal_thinking": Decision(
        readiness="discuss_only",
        claim_boundary="official-paper record only (official public code unverified)",
        fairness_for_main_table="no",
        scientific_meaningfulness="adjacent early-exit risk-control reference",
        recommendation_reason="Primary paper verified, but no clearly verified official public repository from primary sources.",
    ),
    "conformal_thinking_mode_a": Decision(
        readiness="repo_only_not_paper_facing_yet",
        claim_boundary="paper-inspired MODE A risk-controlled early-exit adapter",
        fairness_for_main_table="no_control_space_mismatch",
        scientific_meaningfulness="adjacent early-exit comparator",
        recommendation_reason="Adapter lane should remain caveated until run artifacts are audited and stability is demonstrated.",
    ),
    "compute_optimal_tts": Decision(
        readiness="discuss_only",
        claim_boundary="blocked provenance / mapping",
        fairness_for_main_table="no_blocked",
        scientific_meaningfulness="adjacent but blocked",
        recommendation_reason="Registry marks unresolved paper↔repo mapping blocker.",
    ),
}


def _default_decision(key: str, integration: str) -> Decision:
    if integration in {"discuss_only", "blocked"}:
        return Decision(
            readiness="discuss_only",
            claim_boundary="related-work only",
            fairness_for_main_table="no",
            scientific_meaningfulness="framing or blocked reference",
            recommendation_reason="No fair runnable in-repo lane with auditable artifacts.",
        )
    if integration in {"import_validated", "runnable_adjacent"}:
        return Decision(
            readiness="appendix_only",
            claim_boundary="adjacent import-validated",
            fairness_for_main_table="no_control_space_mismatch",
            scientific_meaningfulness="adjacent comparator",
            recommendation_reason="Runnable/validated as adjacent lane but not direct control-equivalent.",
        )
    if integration == "adapter_based":
        return Decision(
            readiness="repo_only_not_paper_facing_yet",
            claim_boundary="adapter lane",
            fairness_for_main_table="no_without_matched_audited_results",
            scientific_meaningfulness="depends_on_artifact_strength",
            recommendation_reason="Adapter exists but paper-facing evidence is incomplete.",
        )
    return Decision(
        readiness="repo_only_not_paper_facing_yet",
        claim_boundary="unknown",
        fairness_for_main_table="no",
        scientific_meaningfulness="unknown",
        recommendation_reason="Conservative fallback.",
    )


def _exists_any(pattern: str) -> bool:
    if "<run_id>" in pattern:
        pattern = pattern.replace("<run_id>", "*")
    return any(REPO_ROOT.glob(pattern))


def _build_rows() -> list[dict[str, Any]]:
    registry = json.loads((REPO_ROOT / "configs/external_baselines_registry.json").read_text(encoding="utf-8"))["baselines"]
    ranking_df = pd.read_csv(CANONICAL_RANKING) if CANONICAL_RANKING.exists() else pd.DataFrame()
    adjacent_df = pd.read_csv(ADJACENT_BUNDLE) if ADJACENT_BUNDLE.exists() else pd.DataFrame()

    score_map: dict[str, float] = {}
    method_to_key = {
        "external_s1_budget_forcing": "s1_simple_test_time_scaling",
        "external_tale_prompt_budgeting": "tale_token_budget_aware_reasoning",
        "external_l1_max": "l1_length_control_rl",
        "external_l1_exact": "l1_length_control_rl",
    }
    if not ranking_df.empty:
        for _, row in ranking_df.iterrows():
            m = str(row.get("method", ""))
            if m in method_to_key:
                key = method_to_key[m]
                score = float(row.get("mean_accuracy", 0.0))
                score_map[key] = max(score_map.get(key, -1.0), score)

    adjacent_status: dict[str, str] = {}
    if not adjacent_df.empty and "baseline_id" in adjacent_df.columns:
        for _, row in adjacent_df.iterrows():
            adjacent_status[str(row["baseline_id"])] = str(row.get("latest_integration_status", "unknown"))

    rows: list[dict[str, Any]] = []
    for key, info in registry.items():
        decision = DECISION_OVERRIDES.get(key, _default_decision(key, str(info.get("integration", "unknown"))))
        status_artifacts = info.get("status_artifacts", [])
        existing_artifacts = [p for p in status_artifacts if _exists_any(p)]
        runner = info.get("integration_runner")
        control = "adjacent"
        if key in {"s1_simple_test_time_scaling", "tale_token_budget_aware_reasoning", "l1_length_control_rl"}:
            control = "near_direct (MODE A)"
        elif key in {"qstar_deliberative_planning"}:
            control = "direct_family (discuss_only)"

        rows.append(
            {
                "baseline_key": key,
                "current_status_classification": info.get("integration", "unknown"),
                "control_equivalence": control,
                "runnable_now": "yes" if runner and (REPO_ROOT / runner).exists() else "no_or_import_only",
                "auditable_artifacts": "yes" if existing_artifacts else "no_or_weak",
                "auditable_artifact_count": len(existing_artifacts),
                "scientific_meaningfulness": decision.scientific_meaningfulness,
                "neurips_main_table_fair": decision.fairness_for_main_table,
                "claim_boundary": decision.claim_boundary,
                "readiness_decision": decision.readiness,
                "recommendation_reason": decision.recommendation_reason,
                "ranking_signal_mean_accuracy": score_map.get(key),
                "adjacent_bundle_status": adjacent_status.get(key),
            }
        )
    return rows


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    rows = _build_rows()
    generated_utc = datetime.now(timezone.utc).isoformat()

    out_dir = REPO_ROOT / "outputs/external_baseline_readiness"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "paper_readiness_decision_matrix.json"
    csv_path = out_dir / "paper_readiness_decision_matrix.csv"
    docs_json_path = REPO_ROOT / "docs/external_baseline_paper_readiness_decision_matrix.json"
    docs_csv_path = REPO_ROOT / "docs/external_baseline_paper_readiness_decision_matrix.csv"

    payload = {
        "generated_utc": generated_utc,
        "decision_labels": [
            "main_table_ready",
            "appendix_only",
            "repo_only_not_paper_facing_yet",
            "discuss_only",
        ],
        "rows": rows,
    }
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _write_csv(csv_path, rows)
    docs_json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _write_csv(docs_csv_path, rows)

    by_decision: dict[str, list[str]] = {}
    for row in rows:
        by_decision.setdefault(row["readiness_decision"], []).append(row["baseline_key"])

    near_direct_rank = sorted(
        [r for r in rows if r["baseline_key"] in {"s1_simple_test_time_scaling", "tale_token_budget_aware_reasoning", "l1_length_control_rl"}],
        key=lambda x: (x["ranking_signal_mean_accuracy"] is None, -(x["ranking_signal_mean_accuracy"] or -1.0), x["baseline_key"]),
    )

    md = REPO_ROOT / "docs/EXTERNAL_BASELINE_PAPER_READINESS_DECISION_PACKAGE.md"
    lines = [
        "# External baseline paper-readiness decision package",
        "",
        f"- Generated (UTC): `{generated_utc}`",
        "- Scope: full audit of all current external baseline entries in `configs/external_baselines_registry.json`.",
        "- Decision labels: `main_table_ready`, `appendix_only`, `repo_only_not_paper_facing_yet`, `discuss_only`.",
        "",
        "## Canonical decisions (conservative)",
    ]
    for label in ["main_table_ready", "appendix_only", "repo_only_not_paper_facing_yet", "discuss_only"]:
        keys = sorted(by_decision.get(label, []))
        lines.append(f"- **{label}** ({len(keys)}): {', '.join(f'`{k}`' for k in keys) if keys else '(none)'}")

    lines += [
        "",
        "## MODE A additions (explicit decision)",
        "- `learning_how_hard_to_think_mode_a`: **repo_only_not_paper_facing_yet** (no auditable run artifacts found; keep caveated).",
        "- `training_free_difficulty_proxies_mode_a`: **repo_only_not_paper_facing_yet** (no auditable run artifacts found; query-level control mismatch).",
        "- Conservative manuscript guidance now: keep both out of manuscript-facing empirical tables in this repository state.",
        "",
        "## Strongest baseline ranking for this paper state",
        "",
        "### Direct / near-direct practical comparators",
    ]
    for idx, row in enumerate(near_direct_rank, 1):
        score = row["ranking_signal_mean_accuracy"]
        score_text = "n/a" if score is None else f"{score:.6f}"
        lines.append(f"{idx}. `{row['baseline_key']}` (canonical ranking signal mean_accuracy: {score_text})")

    lines += [
        "",
        "### Adjacent but reviewer-useful comparators",
        "- `tree_plv`, `rest_mcts`, `lets_verify_step_by_step`, `best_route_microsoft`, `when_solve_when_verify`, `cascade_routing`, `mob_majority_of_bests`, `openr`.",
        "",
        "### Framing-only / discuss-only references",
        "- `qstar_deliberative_planning`, `rational_metareasoning_llm`, `best_arm_identification_fixed_budget`, `pgts`, `scaling_automated_process_verifiers`, `compute_optimal_tts`, `mcts_llm_community`, `llm_tree_search_waterhorse`, `learning_how_hard_to_think`, `adaptive_test_time_compute_allocation_training_free_proxies`.",
        "",
        "## Machine-readable matrix",
        "- `docs/external_baseline_paper_readiness_decision_matrix.json`",
        "- `docs/external_baseline_paper_readiness_decision_matrix.csv`",
        "- (runtime copy) `outputs/external_baseline_readiness/paper_readiness_decision_matrix.json`",
        "- (runtime copy) `outputs/external_baseline_readiness/paper_readiness_decision_matrix.csv`",
        "",
        "## Concise recommendation",
        "- **Main table (safe now):** `l1_length_control_rl`, `tale_token_budget_aware_reasoning`, `s1_simple_test_time_scaling` (MODE A adapter rows only).",
        "- **Appendix only:** adjacent import-validated/partial-runnable baselines listed above.",
        "- **Keep out of empirical tables for now:** all `repo_only_not_paper_facing_yet` and `discuss_only` rows (including both new MODE A additions).",
        "",
        "## Evidence fields audited per baseline",
        "- registry entry",
        "- integration docs / runners / configs when present",
        "- status artifact presence",
        "- adjacent bundle integration status (when available)",
        "- canonical ranking signal availability (near-direct MODE A families)",
    ]
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
