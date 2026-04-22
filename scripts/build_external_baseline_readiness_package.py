#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / "configs/external_baselines_registry.json"
CANONICAL_RANKING = REPO_ROOT / "outputs/canonical_full_method_ranking_20260421T212948Z/overall_ranking.csv"
ADJACENT_BUNDLE = REPO_ROOT / "outputs/external_adjacent_baseline_bundle/20260422T201000Z/summary.csv"

NEAR_DIRECT_MODE_A_KEYS = {
    "s1_simple_test_time_scaling",
    "tale_token_budget_aware_reasoning",
    "l1_length_control_rl",
}
MODE_A_NEW_ADDITIONS = {
    "learning_how_hard_to_think_mode_a",
    "training_free_difficulty_proxies_mode_a",
}


def _exists(rel_path: str | None) -> bool:
    return bool(rel_path) and (REPO_ROOT / rel_path).exists()


def _expand_glob(pattern: str) -> list[str]:
    if "<run_id>" in pattern:
        pattern = pattern.replace("<run_id>", "*")
    return [str(p.relative_to(REPO_ROOT)) for p in REPO_ROOT.glob(pattern)]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _load_score_map() -> dict[str, float]:
    if not CANONICAL_RANKING.exists():
        return {}
    df = pd.read_csv(CANONICAL_RANKING)
    method_to_key = {
        "external_s1_budget_forcing": "s1_simple_test_time_scaling",
        "external_tale_prompt_budgeting": "tale_token_budget_aware_reasoning",
        "external_l1_max": "l1_length_control_rl",
        "external_l1_exact": "l1_length_control_rl",
    }
    out: dict[str, float] = {}
    for _, row in df.iterrows():
        method = str(row.get("method", ""))
        if method in method_to_key:
            key = method_to_key[method]
            out[key] = max(out.get(key, -1.0), float(row.get("mean_accuracy", 0.0)))
    return out


def _load_adjacent_status() -> dict[str, str]:
    if not ADJACENT_BUNDLE.exists():
        return {}
    df = pd.read_csv(ADJACENT_BUNDLE)
    if "baseline_id" not in df.columns:
        return {}
    return {str(r["baseline_id"]): str(r.get("latest_integration_status", "unknown")) for _, r in df.iterrows()}


def _decision(
    key: str,
    integration: str,
    control_equivalence: str,
    has_runner: bool,
    found_artifact_count: int,
    ranking_signal: float | None,
) -> tuple[str, str, str, str, str]:
    # returns: readiness_decision, neurips_main_table_fair, claim_boundary, scientific_meaningfulness, reason
    if key in MODE_A_NEW_ADDITIONS:
        return (
            "repo_only_not_paper_facing_yet",
            "no_missing_artifacts_and_non_equivalent_control",
            "paper-inspired MODE A adapter only; no audited run artifacts yet",
            "paper-inspired adjacent adapter comparator",
            "Mixed/early status and currently no auditable run artifacts in this repo; keep out of manuscript-facing tables.",
        )

    if integration == "adapter_based":
        return (
            "repo_only_not_paper_facing_yet",
            "no_without_stronger_audited_evidence",
            "unofficial or adapter-only lane",
            "useful exploratory comparator",
            "Adapter exists but current evidence is not robust enough for paper-facing empirical claims.",
        )

    if key in NEAR_DIRECT_MODE_A_KEYS and ranking_signal is not None:
        return (
            "main_table_ready",
            "yes_with_mode_a_boundary",
            "MODE A adapter comparator on matched substrate only (not official full-stack reproduction)",
            "near-direct practical comparator under matched budget accounting",
            "Appears in canonical matched ranking with auditable comparison rows; safe for main table with explicit MODE A boundary.",
        )

    if integration in {"import_validated", "runnable_adjacent"}:
        if found_artifact_count > 0 and (has_runner or integration == "runnable_adjacent"):
            return (
                "appendix_only",
                "no_control_space_mismatch",
                "adjacent comparator; non-equivalent control space",
                "adjacent but reviewer-useful comparator",
                "Runnable/import-validated with auditable artifacts, but not control-equivalent to frontier next-step allocation.",
            )
        return (
            "repo_only_not_paper_facing_yet",
            "no_missing_auditability",
            "adjacent comparator with weak current artifact evidence",
            "adjacent comparator with weak evidence",
            "Integration label exists, but auditable artifact support is currently weak; keep repo-only until refreshed.",
        )

    if integration in {"discuss_only", "blocked"}:
        boundary = "blocked or discuss-only reference"
        if key == "qstar_deliberative_planning":
            boundary = "direct-family framing reference only (no verified runnable official stack)"
        return (
            "discuss_only",
            "no",
            boundary,
            "related-work or framing reference",
            "No fair runnable, auditable in-repo comparison lane currently available.",
        )

    return (
        "repo_only_not_paper_facing_yet",
        "no_unknown",
        "unknown",
        "unknown",
        "Conservative fallback due to incomplete metadata.",
    )


def build_rows() -> list[dict[str, Any]]:
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))["baselines"]
    score_map = _load_score_map()
    adjacent_status = _load_adjacent_status()

    rows: list[dict[str, Any]] = []
    for key, info in registry.items():
        integration = str(info.get("integration", "unknown"))
        runner = info.get("integration_runner")
        contract = info.get("contract")
        integration_doc = info.get("integration_doc")
        status_artifacts = [str(x) for x in info.get("status_artifacts", [])]

        found_matches: list[str] = []
        for p in status_artifacts:
            found_matches.extend(_expand_glob(p))

        ranking_signal = score_map.get(key)
        control_equivalence = "adjacent"
        if key in NEAR_DIRECT_MODE_A_KEYS:
            control_equivalence = "near_direct_mode_a"
        elif key == "qstar_deliberative_planning":
            control_equivalence = "direct_family_discuss_only"

        readiness, fairness, claim_boundary, scientific_meaningfulness, reason = _decision(
            key=key,
            integration=integration,
            control_equivalence=control_equivalence,
            has_runner=_exists(runner),
            found_artifact_count=len(found_matches),
            ranking_signal=ranking_signal,
        )

        rows.append(
            {
                "baseline_key": key,
                "current_status_classification": integration,
                "control_equivalence": control_equivalence,
                "runnable_now": "yes" if _exists(runner) else "no_or_import_only",
                "runner_path": runner or "",
                "runner_exists": bool(_exists(runner)),
                "contract_path": contract or "",
                "contract_exists": bool(_exists(contract)),
                "integration_doc": integration_doc or "",
                "integration_doc_exists": bool(_exists(integration_doc)),
                "auditable_artifacts": "yes" if found_matches else "no_or_weak",
                "auditable_artifact_count": len(found_matches),
                "status_artifact_patterns_count": len(status_artifacts),
                "latest_artifact_examples": " | ".join(sorted(found_matches)[:3]),
                "adjacent_bundle_status": adjacent_status.get(key, "not_in_adjacent_bundle"),
                "ranking_signal_mean_accuracy": ranking_signal,
                "scientific_meaningfulness": scientific_meaningfulness,
                "neurips_main_table_fair": fairness,
                "claim_boundary": claim_boundary,
                "readiness_decision": readiness,
                "recommendation_reason": reason,
                "registry_blocker": str(info.get("blocker", "")),
                "paper_phase_priority": str(info.get("paper_phase_priority", "")),
                "baseline_class": str(info.get("baseline_class", "")),
            }
        )

    return sorted(rows, key=lambda r: (r["readiness_decision"], r["baseline_key"]))


def main() -> None:
    rows = build_rows()
    generated_utc = datetime.now(timezone.utc).isoformat()
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    out_dir = REPO_ROOT / f"outputs/canonical_external_baseline_paper_readiness_decision_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "generated_utc": generated_utc,
        "decision_labels": [
            "main_table_ready",
            "appendix_only",
            "repo_only_not_paper_facing_yet",
            "discuss_only",
        ],
        "source_inputs": {
            "registry": str(REGISTRY_PATH.relative_to(REPO_ROOT)),
            "canonical_ranking": str(CANONICAL_RANKING.relative_to(REPO_ROOT)) if CANONICAL_RANKING.exists() else None,
            "adjacent_bundle": str(ADJACENT_BUNDLE.relative_to(REPO_ROOT)) if ADJACENT_BUNDLE.exists() else None,
        },
        "rows": rows,
    }

    # Canonical runtime outputs
    (out_dir / "external_baseline_readiness_decision_matrix.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _write_csv(out_dir / "external_baseline_readiness_decision_matrix.csv", rows)

    # Stable docs + plumbing copies
    (REPO_ROOT / "docs/external_baseline_paper_readiness_decision_matrix.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _write_csv(REPO_ROOT / "docs/external_baseline_paper_readiness_decision_matrix.csv", rows)
    out_copy = REPO_ROOT / "outputs/external_baseline_readiness"
    out_copy.mkdir(parents=True, exist_ok=True)
    (out_copy / "paper_readiness_decision_matrix.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _write_csv(out_copy / "paper_readiness_decision_matrix.csv", rows)

    df = pd.DataFrame(rows)
    by_decision = {k: sorted(df[df["readiness_decision"] == k]["baseline_key"].tolist()) for k in payload["decision_labels"]}

    near_direct_rank = (
        df[df["baseline_key"].isin(sorted(NEAR_DIRECT_MODE_A_KEYS))]
        .sort_values(["ranking_signal_mean_accuracy", "baseline_key"], ascending=[False, True])
    )

    md_lines = [
        "# Canonical external baseline paper-facing readiness decision package",
        "",
        f"- Generated (UTC): `{generated_utc}`",
        f"- Registry entries audited: `{len(rows)}`",
        f"- Runtime artifact bundle: `outputs/{out_dir.name}/`",
        "",
        "## Canonical recommendation buckets",
    ]
    for label in payload["decision_labels"]:
        keys = by_decision.get(label, [])
        md_lines.append(f"- **{label}** ({len(keys)}): {', '.join(f'`{k}`' for k in keys) if keys else '(none)'}")

    md_lines += [
        "",
        "## MODE A additions (explicit decision)",
        "- `learning_how_hard_to_think_mode_a`: **repo_only_not_paper_facing_yet**.",
        "- `training_free_difficulty_proxies_mode_a`: **repo_only_not_paper_facing_yet**.",
        "- Rationale: both remain mixed/early and currently lack audited run artifacts on this repo state.",
        "",
        "## Concise recommendation",
        "- **Main table (safe now):** near-direct MODE A comparators with canonical matched ranking rows: `l1_length_control_rl`, `tale_token_budget_aware_reasoning`, `s1_simple_test_time_scaling`.",
        "- **Appendix only:** auditable adjacent import-validated/runnable-adjacent comparators.",
        "- **Keep out of empirical tables:** all `repo_only_not_paper_facing_yet` + `discuss_only` baselines.",
        "",
        "## Strongest external baseline ranking (near-direct practical lane)",
    ]
    for i, (_, row) in enumerate(near_direct_rank.iterrows(), start=1):
        score = row["ranking_signal_mean_accuracy"]
        score_txt = "n/a" if pd.isna(score) else f"{float(score):.6f}"
        md_lines.append(f"{i}. `{row['baseline_key']}` (canonical ranking signal mean_accuracy: {score_txt})")

    md_lines += [
        "",
        "## Files",
        "- `docs/external_baseline_paper_readiness_decision_matrix.json`",
        "- `docs/external_baseline_paper_readiness_decision_matrix.csv`",
        "- `outputs/external_baseline_readiness/paper_readiness_decision_matrix.json`",
        "- `outputs/external_baseline_readiness/paper_readiness_decision_matrix.csv`",
        "",
        "## Audit evidence fields included per baseline",
        "- registry status/class/blocker",
        "- runner/config/doc existence",
        "- status artifact pattern count and found artifact count",
        "- adjacent bundle status (when present)",
        "- canonical ranking signal (for near-direct mode-A comparators)",
        "- explicit claim boundary and fairness label",
    ]
    (out_dir / "report.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    (REPO_ROOT / "docs/CANONICAL_EXTERNAL_BASELINE_PAPER_READINESS_DECISION_2026_04_22.md").write_text(
        "\n".join(md_lines)
        + "\n\n"
        + "This report is canonical for manuscript writing until superseded by a newer dated decision package.\n",
        encoding="utf-8",
    )

    manifest = {
        "artifact_family": "canonical_external_baseline_paper_readiness_decision",
        "output_dir": f"outputs/{out_dir.name}",
        "generated_utc": generated_utc,
        "inputs": payload["source_inputs"],
        "outputs": [
            "external_baseline_readiness_decision_matrix.json",
            "external_baseline_readiness_decision_matrix.csv",
            "report.md",
        ],
        "docs_written": [
            "docs/external_baseline_paper_readiness_decision_matrix.json",
            "docs/external_baseline_paper_readiness_decision_matrix.csv",
            "docs/CANONICAL_EXTERNAL_BASELINE_PAPER_READINESS_DECISION_2026_04_22.md",
        ],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(out_dir)


if __name__ == "__main__":
    main()
