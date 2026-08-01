"""Freeze and audit `pooled4_fs0_notie_risk_controlled_candidate`.

A conservative variant of `pooled4_fs_le1_notie_fta_v2_candidate`
(experiments/freeze_pooled4_fs_le1_notie_candidate.py) discovered offline in the
2026-07-09 overnight subgroup-robustness pass
(outputs/failure_analysis/pooled4_global_overnight_20260709T033720Z/): restricting
the override gate to `frontier_support == 0` (dropping the `frontier_support == 1`
slice) cut the global bank's losses from 42 to 8 while keeping 73 of 237 wins.

This module:
  - defines the frozen runtime rule (`decision_fs0_risk_controlled`), a strict
    syntactic subset of the original rule (`decision_original_fs_le1`, reimplemented
    here independently of freeze_pooled4_fs_le1_notie_candidate.py's own
    canonical-schema implementation so both candidates are evaluated through one
    consistent code path against the global-bank row schema);
  - runs a side-by-side global replay of both candidates, partitioned by
    artifact-quality / provider / dataset (diagnostic-only partitions);
  - separately analyzes the dropped `frontier_support == 1` slice;
  - re-runs the same chronological / leave-one-family / leave-one-provider /
    leave-one-dataset pseudo-prospective checks as the overnight pass, for both
    candidates;
  - writes a freeze spec, a runtime-legality audit, and a fresh-validation
    readiness decision.

Zero API calls. Opens the global bank CSV read-only. Gold is read only through
the bank's already-computed post-hoc correctness columns
(fta_correct / pooled4_correct) to label win/loss/tie for reporting -- never
passed into a firing-condition function. See `audit_function_legality()` and
`test_freeze_pooled4_fs0_notie_risk_controlled_candidate.py`'s tripwire-dict
test for an *executed*, not just textual, enforcement of that separation.
"""

from __future__ import annotations

import argparse
import csv
import inspect
import json
import random
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from experiments.freeze_pooled4_fs_le1_notie_candidate import CANDIDATE_NAME as ORIGINAL_CANDIDATE_NAME
from experiments.global_existing_failure_case_inventory import (
    normalize_answer,
    pooled4_plurality_vote,
)
from experiments.pooled4_fs_le1_global_risk_region_analysis import (
    DEFAULT_BANK_CSV,
    DEFAULT_DISCOVERY_TABLE,
    artifact_family,
    load_artifact_mtimes,
    load_bank_rows,
)

CANDIDATE_NAME = "pooled4_fs0_notie_risk_controlled_candidate"

RUNTIME_FEATURES = ("frontier_answer", "l1_answer", "s1_answer", "tale_answer", "fta_answer", "frontier_support")
FORBIDDEN_RUNTIME = {
    "gold", "example_id", "provider", "dataset", "artifact_quality", "canonical_or_diagnostic",
    "seed", "budget", "question", "question_hash", "normalized_question_text_hash",
    "frontier_correct", "l1_correct", "s1_correct", "tale_correct", "fta_correct",
    "pooled4_correct", "external3_correct", "candidate_result", "source_artifact_path",
    "external3_answer",  # excluded deliberately: no External-3 tie-break in this candidate
}


def _parse_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def decision_original_fs_le1(row: dict[str, Any]) -> str | None:
    """Reimplementation of pooled4_fs_le1_notie_fta_v2_candidate against the
    global-bank row schema (frontier_support <= 1), for a like-for-like
    side-by-side comparison in this module. Runtime-legal: only reads
    frontier_support and the four raw answers plus the FTA answer."""
    fs = _parse_float(row.get("frontier_support"))
    if fs is None or fs > 1:
        return None
    p4 = pooled4_plurality_vote(row.get("frontier_answer"), row.get("l1_answer"), row.get("s1_answer"), row.get("tale_answer"))
    if p4 is None:
        return None
    fta_norm = normalize_answer(row.get("fta_answer"))
    if fta_norm is None:
        return None
    if p4 == fta_norm:
        return None
    return p4


def decision_fs0_risk_controlled(row: dict[str, Any]) -> str | None:
    """Frozen runtime rule for pooled4_fs0_notie_risk_controlled_candidate.

    1. Compute canonical FTA answer (row['fta_answer'], already produced upstream).
    2. Compute Pooled-4 unique normalized plurality over frontier/L1/S1/TALE.
    3. Abstain if the Pooled-4 plurality is tied or missing.
    4. Override FTA only when frontier_support == 0, Pooled-4 has a unique
       winner, and it differs (normalized) from FTA's answer.
    5. Otherwise return None (keep FTA).

    No gold, no provider/dataset/artifact/example_id, no arbitrary Pooled-4 or
    External-3 tie-break order.
    """
    fs = _parse_float(row.get("frontier_support"))
    if fs is None or fs != 0:
        return None
    p4 = pooled4_plurality_vote(row.get("frontier_answer"), row.get("l1_answer"), row.get("s1_answer"), row.get("tale_answer"))
    if p4 is None:
        return None
    fta_norm = normalize_answer(row.get("fta_answer"))
    if fta_norm is None:
        return None
    if p4 == fta_norm:
        return None
    return p4


def fires(decision_fn: Callable[[dict[str, Any]], str | None], row: dict[str, Any]) -> bool:
    return decision_fn(row) is not None


def audit_function_legality(fn: Callable, forbidden_substrings: set[str]) -> dict[str, Any]:
    """Static source-scan audit (mirrors experiments/stress_test_exploratory_rules.py
    ::audit_rule_decision_legality and the equivalent check in
    experiments/global_existing_failure_case_inventory.py). Complements, but does
    not replace, the executed tripwire-dict test in the test module."""
    src = inspect.getsource(fn)
    code_lines = []
    in_doc = False
    for line in src.splitlines():
        stripped = line.strip()
        if stripped.startswith('"""'):
            in_doc = not in_doc
            continue
        if in_doc or stripped.startswith("#"):
            continue
        code_lines.append(line)
    code_only = "\n".join(code_lines).lower()
    found = sorted({s for s in forbidden_substrings if s.lower() in code_only})
    return {"function": fn.__name__, "is_runtime_legal": len(found) == 0, "forbidden_substrings_found": found}


def compute_result(fires_flag: bool, pooled4_correct: bool | None, fta_correct: bool | None) -> str:
    if not fires_flag:
        return "not_fired"
    if pooled4_correct is None or fta_correct is None:
        return "unknown_gold_missing"
    if pooled4_correct and not fta_correct:
        return "win"
    if fta_correct and not pooled4_correct:
        return "loss"
    return "tie"


def compute_metrics(rows: list[dict[str, Any]], decision_fn: Callable[[dict[str, Any]], str | None]) -> dict[str, Any]:
    triggered = []
    for r in rows:
        proposal = decision_fn(r)
        if proposal is None:
            continue
        result = compute_result(True, r.get("pooled4_correct"), r.get("fta_correct"))
        triggered.append({**r, "result": result})
    wins = sum(1 for r in triggered if r["result"] == "win")
    losses = sum(1 for r in triggered if r["result"] == "loss")
    ties = sum(1 for r in triggered if r["result"] == "tie")
    n = len(triggered)
    return {
        "n_triggered": n, "wins": wins, "losses": losses, "ties": ties, "net": wins - losses,
        "regression_rate": (losses / n) if n else None,
        "triggered_rows": triggered,
    }


def bootstrap_net_ci(triggered_rows: list[dict[str, Any]], *, n_resamples: int = 2000, seed: int = 1234) -> dict[str, Any]:
    if not triggered_rows:
        return {"n": 0, "observed_net": None, "ci_low": None, "ci_high": None}
    rng = random.Random(seed)
    n = len(triggered_rows)
    outcomes = [1 if r["result"] == "win" else (-1 if r["result"] == "loss" else 0) for r in triggered_rows]
    observed_net = sum(outcomes)
    resampled_nets = []
    for _ in range(n_resamples):
        resampled_nets.append(sum(outcomes[rng.randrange(n)] for _ in range(n)))
    resampled_nets.sort()
    lo_idx = max(0, int(round(0.025 * n_resamples)) - 1)
    hi_idx = min(n_resamples - 1, int(round(0.975 * n_resamples)) - 1)
    return {"n": n, "observed_net": observed_net, "ci_low": resampled_nets[lo_idx], "ci_high": resampled_nets[hi_idx], "n_resamples": n_resamples}


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    fieldnames = fieldnames or (list(rows[0].keys()) if rows else ["(empty)"])
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


ARTIFACT_QUALITY_PARTITIONS = ("canonical", "auxiliary", "diagnostic", "smoke", "dry-run", "test", "unclassified")


def is_failure_enriched(source_artifact_path: str) -> bool:
    return "failure" in source_artifact_path.lower() or "loss" in source_artifact_path.lower()


# ---------------------------------------------------------------------------
# Task 1: formal freeze
# ---------------------------------------------------------------------------


def task1_freeze(output_dir: Path) -> dict[str, Any]:
    spec = {
        "candidate_name": CANDIDATE_NAME,
        "status": "exploratory_frozen_not_promoted",
        "relation_to": ORIGINAL_CANDIDATE_NAME,
        "discovery_source": "outputs/failure_analysis/pooled4_global_overnight_20260709T033720Z/analysis/ (guard B)",
        "runtime_rule_steps": [
            "1. Compute canonical FTA answer.",
            "2. Compute Pooled-4 unique normalized plurality over frontier/L1/S1/TALE.",
            "3. Abstain if Pooled-4 plurality is tied or missing.",
            "4. Override FTA only when: frontier_support == 0, Pooled-4 has a unique normalized plurality winner, "
            "and Pooled-4 normalized answer differs from FTA normalized answer.",
            "5. Otherwise keep FTA.",
        ],
        "runtime_features": list(RUNTIME_FEATURES),
        "forbidden_runtime_fields": sorted(FORBIDDEN_RUNTIME),
        "explicit_exclusions": [
            "No gold, correctness, exact_match, example_id, question hash, or provider/dataset/artifact labels.",
            "No arbitrary Pooled-4 tie-break order -- ties abstain.",
            "No External-3 tie-break or agreement requirement.",
            "No post-generation model calls.",
            "Not promoted; canonical production selector remains FTA FIX-2+FIX-4.",
            "Does not replace or supersede pooled4_fs_le1_notie_fta_v2_candidate -- evaluated here purely for comparison.",
        ],
    }
    write_json(output_dir / "FROZEN_RULE_SPEC.json", spec)

    spec_md = [
        f"# {CANDIDATE_NAME} -- Frozen Rule Specification", "",
        f"**Candidate ID:** `{CANDIDATE_NAME}`", "",
        "**Status:** Exploratory / frozen for validation planning only. **Not promoted.** "
        "Canonical production selector remains FTA FIX-2+FIX-4.", "",
        f"**Relation to prior candidate:** conservative sub-variant of `{ORIGINAL_CANDIDATE_NAME}` "
        "(experiments/freeze_pooled4_fs_le1_notie_candidate.py), restricting its frontier_support<=1 gate to "
        "frontier_support==0 only. Discovered in the 2026-07-09 overnight subgroup-robustness pass (guard B).", "",
        "## Runtime decision (universal, provider-agnostic)", "",
    ] + [f"{s}" for s in spec["runtime_rule_steps"]] + [
        "", "## Legality requirements", "",
        "- Uses only runtime-available fields: " + ", ".join(RUNTIME_FEATURES),
        "- Does not use gold.",
        "- Does not use provider/dataset/artifact labels.",
        "- Does not use example_id.",
        "- Does not use post-hoc correctness.",
        "- Does not use arbitrary Pooled-4 tie-break order (ties abstain).",
        "- Does not use External-3 tie-break order (no External-3 involvement at all).",
        "", "## Explicit exclusions", "",
    ] + [f"- {e}" for e in spec["explicit_exclusions"]]
    write_text(output_dir / "FROZEN_RULE_SPEC.md", "\n".join(spec_md) + "\n")
    return spec


def task1_legality_audit(output_dir: Path, bank_rows: list[dict[str, Any]]) -> dict[str, Any]:
    audit_fs0 = audit_function_legality(decision_fs0_risk_controlled, FORBIDDEN_RUNTIME)
    audit_original = audit_function_legality(decision_original_fs_le1, FORBIDDEN_RUNTIME)

    # Subset property: every row fs0 fires on, the original rule must also fire on.
    violations = []
    for r in bank_rows:
        if fires(decision_fs0_risk_controlled, r) and not fires(decision_original_fs_le1, r):
            violations.append(r.get("example_id") or r.get("question_hash"))
    subset_holds = len(violations) == 0

    # Cross-check against the bank's own precomputed candidate_fires column
    # (built independently in experiments/global_existing_failure_case_inventory.py
    # with the same fs<=1 logic) as a consistency check on this reimplementation.
    mismatches = 0
    checked = 0
    for r in bank_rows:
        bank_fires = r.get("candidate_fires")
        if bank_fires is None:
            continue
        checked += 1
        if bool(bank_fires) != fires(decision_original_fs_le1, r):
            mismatches += 1

    result = {
        "fs0_function_legality": audit_fs0,
        "original_function_legality": audit_original,
        "fs0_subset_of_original_holds": subset_holds,
        "fs0_subset_violations_count": len(violations),
        "original_vs_bank_precomputed_consistency_checked_rows": checked,
        "original_vs_bank_precomputed_mismatches": mismatches,
    }
    write_json(output_dir / "RUNTIME_LEGALITY_AUDIT.json", result)
    lines = [
        "# Runtime Legality Audit", "",
        f"- `{CANDIDATE_NAME}` decision function: is_runtime_legal={audit_fs0['is_runtime_legal']}, "
        f"forbidden_found={audit_fs0['forbidden_substrings_found']}",
        f"- `{ORIGINAL_CANDIDATE_NAME}` reimplementation: is_runtime_legal={audit_original['is_runtime_legal']}, "
        f"forbidden_found={audit_original['forbidden_substrings_found']}",
        f"- fs0 is a strict subset of fs<=1 (every fs0-firing row also fires under the original rule): {subset_holds} "
        f"({len(violations)} violations{' -- see IDs: ' + str(violations[:20]) if violations else ''})",
        f"- Consistency check vs bank's own precomputed `candidate_fires` column (built independently in "
        f"global_existing_failure_case_inventory.py): {checked} rows checked, {mismatches} mismatches.",
    ]
    write_text(output_dir / "RUNTIME_LEGALITY_AUDIT.md", "\n".join(lines) + "\n")
    if not (audit_fs0["is_runtime_legal"] and audit_original["is_runtime_legal"] and subset_holds):
        raise RuntimeError(f"Legality/consistency audit failed: {result}")
    return result


# ---------------------------------------------------------------------------
# Task 2: side-by-side global replay
# ---------------------------------------------------------------------------

REPLAY_FIELDS = [
    "candidate", "scope", "scope_value", "n_triggered", "wins", "losses", "ties", "net", "regression_rate",
    "preserved_win_fraction_vs_original", "loss_reduction_fraction_vs_original", "accuracy_if_computable",
]


def _accuracy_if_computable(triggered_rows: list[dict[str, Any]]) -> float | None:
    scored = [r for r in triggered_rows if r["result"] in ("win", "loss", "tie")]
    if not scored:
        return None
    correct = sum(1 for r in scored if r.get("pooled4_correct") is True)
    return correct / len(scored)


def _replay_row(candidate: str, scope: str, scope_value: str, metrics: dict[str, Any], orig_wins: int, orig_losses: int) -> dict[str, Any]:
    return {
        "candidate": candidate, "scope": scope, "scope_value": scope_value,
        "n_triggered": metrics["n_triggered"], "wins": metrics["wins"], "losses": metrics["losses"],
        "ties": metrics["ties"], "net": metrics["net"], "regression_rate": metrics["regression_rate"],
        "preserved_win_fraction_vs_original": (metrics["wins"] / orig_wins) if orig_wins else None,
        "loss_reduction_fraction_vs_original": (1 - metrics["losses"] / orig_losses) if orig_losses else None,
        "accuracy_if_computable": _accuracy_if_computable(metrics["triggered_rows"]),
    }


def task2_global_replay(output_dir: Path, bank_rows: list[dict[str, Any]]) -> dict[str, Any]:
    orig_metrics_all = compute_metrics(bank_rows, decision_original_fs_le1)
    fs0_metrics_all = compute_metrics(bank_rows, decision_fs0_risk_controlled)
    orig_wins, orig_losses = orig_metrics_all["wins"], orig_metrics_all["losses"]

    global_rows = [
        _replay_row(ORIGINAL_CANDIDATE_NAME, "all", "all", orig_metrics_all, orig_wins, orig_losses),
        _replay_row(CANDIDATE_NAME, "all", "all", fs0_metrics_all, orig_wins, orig_losses),
    ]

    by_quality_rows = []
    for quality in ARTIFACT_QUALITY_PARTITIONS:
        subset = [r for r in bank_rows if r.get("artifact_quality") == quality]
        if not subset:
            continue
        om = compute_metrics(subset, decision_original_fs_le1)
        fm = compute_metrics(subset, decision_fs0_risk_controlled)
        by_quality_rows.append(_replay_row(ORIGINAL_CANDIDATE_NAME, "artifact_quality", quality, om, orig_wins, orig_losses))
        by_quality_rows.append(_replay_row(CANDIDATE_NAME, "artifact_quality", quality, fm, orig_wins, orig_losses))

    # failure-enriched (diagnostic proxy: path contains "failure"/"loss")
    failure_enriched_subset = [r for r in bank_rows if is_failure_enriched(r.get("source_artifact_path", ""))]
    if failure_enriched_subset:
        om = compute_metrics(failure_enriched_subset, decision_original_fs_le1)
        fm = compute_metrics(failure_enriched_subset, decision_fs0_risk_controlled)
        by_quality_rows.append(_replay_row(ORIGINAL_CANDIDATE_NAME, "failure_enriched_diagnostic", "true", om, orig_wins, orig_losses))
        by_quality_rows.append(_replay_row(CANDIDATE_NAME, "failure_enriched_diagnostic", "true", fm, orig_wins, orig_losses))

    by_pd_rows = []
    provider_datasets = sorted({f"{r.get('provider')}|{r.get('dataset')}" for r in bank_rows if r.get("provider") and r.get("dataset")})
    for pd in provider_datasets:
        p, d = pd.split("|", 1)
        subset = [r for r in bank_rows if r.get("provider") == p and r.get("dataset") == d]
        om = compute_metrics(subset, decision_original_fs_le1)
        fm = compute_metrics(subset, decision_fs0_risk_controlled)
        by_pd_rows.append(_replay_row(ORIGINAL_CANDIDATE_NAME, "provider_dataset", pd, om, orig_wins, orig_losses))
        by_pd_rows.append(_replay_row(CANDIDATE_NAME, "provider_dataset", pd, fm, orig_wins, orig_losses))

    write_csv(output_dir / "FS0_VS_FSLE1_GLOBAL_REPLAY.csv", global_rows, REPLAY_FIELDS)
    write_csv(output_dir / "FS0_VS_FSLE1_BY_PROVIDER_DATASET.csv", by_pd_rows, REPLAY_FIELDS)
    write_csv(output_dir / "FS0_VS_FSLE1_BY_ARTIFACT_QUALITY.csv", by_quality_rows, REPLAY_FIELDS)

    ci_orig = bootstrap_net_ci(orig_metrics_all["triggered_rows"])
    ci_fs0 = bootstrap_net_ci(fs0_metrics_all["triggered_rows"])

    report_lines = [
        "# FS0 vs FS<=1 Global Replay Report", "",
        f"## Global (all {len(bank_rows)} bank rows)", "",
        f"- `{ORIGINAL_CANDIDATE_NAME}`: n={orig_metrics_all['n_triggered']}, wins={orig_metrics_all['wins']}, "
        f"losses={orig_metrics_all['losses']}, ties={orig_metrics_all['ties']}, net={orig_metrics_all['net']}, "
        f"bootstrap_net_95ci=[{ci_orig['ci_low']}, {ci_orig['ci_high']}]",
        f"- `{CANDIDATE_NAME}`: n={fs0_metrics_all['n_triggered']}, wins={fs0_metrics_all['wins']}, "
        f"losses={fs0_metrics_all['losses']}, ties={fs0_metrics_all['ties']}, net={fs0_metrics_all['net']}, "
        f"bootstrap_net_95ci=[{ci_fs0['ci_low']}, {ci_fs0['ci_high']}]",
        f"- preserved_win_fraction: {(fs0_metrics_all['wins'] / orig_wins) if orig_wins else None}",
        f"- loss_reduction_fraction: {(1 - fs0_metrics_all['losses'] / orig_losses) if orig_losses else None}",
        "",
        "## By artifact quality (diagnostic partition)", "",
    ]
    for row in by_quality_rows:
        report_lines.append(f"- {row['candidate']} / {row['scope_value']}: n={row['n_triggered']}, net={row['net']}, losses={row['losses']}")
    report_lines += ["", "## By provider/dataset (diagnostic partition)", ""]
    for row in by_pd_rows:
        report_lines.append(f"- {row['candidate']} / {row['scope_value']}: n={row['n_triggered']}, net={row['net']}, losses={row['losses']}")
    write_text(output_dir / "FS0_VS_FSLE1_REPORT.md", "\n".join(report_lines) + "\n")

    return {
        "orig_metrics_all": orig_metrics_all, "fs0_metrics_all": fs0_metrics_all,
        "ci_orig": ci_orig, "ci_fs0": ci_fs0,
    }


# ---------------------------------------------------------------------------
# Task 3: dropped fs==1 slice
# ---------------------------------------------------------------------------

DROPPED_SLICE_FIELDS = [
    "source_artifact_path", "artifact_quality", "provider", "dataset", "seed", "budget", "example_id",
    "question_hash", "question", "gold", "frontier_answer", "l1_answer", "s1_answer", "tale_answer",
    "fta_answer", "pooled4_answer", "frontier_support", "candidate_pool_answer_group_count",
    "override_reason", "fta_correct", "pooled4_correct", "result",
]


def task3_dropped_slice(output_dir: Path, bank_rows: list[dict[str, Any]]) -> dict[str, Any]:
    dropped = []
    for r in bank_rows:
        fires_orig = fires(decision_original_fs_le1, r)
        fires_fs0_flag = fires(decision_fs0_risk_controlled, r)
        if fires_orig and not fires_fs0_flag:
            result = compute_result(True, r.get("pooled4_correct"), r.get("fta_correct"))
            dropped.append({**r, "result": result})

    wins = sum(1 for r in dropped if r["result"] == "win")
    losses = sum(1 for r in dropped if r["result"] == "loss")
    ties = sum(1 for r in dropped if r["result"] == "tie")
    write_csv(output_dir / "FS1_DROPPED_SLICE_CASES.csv", dropped, DROPPED_SLICE_FIELDS)

    by_pd: dict[str, dict[str, int]] = defaultdict(lambda: {"wins": 0, "losses": 0, "ties": 0})
    by_quality: dict[str, dict[str, int]] = defaultdict(lambda: {"wins": 0, "losses": 0, "ties": 0})
    for r in dropped:
        if r["result"] in ("win", "loss", "tie"):
            key = "losses" if r["result"] == "loss" else r["result"] + "s"
            by_pd[f"{r.get('provider')}|{r.get('dataset')}"][key] += 1
            by_quality[r.get("artifact_quality")][key] += 1

    # Safer subguards restricted to just this fs==1 slice.
    def _group_le_2(r):
        gc = _parse_float(r.get("candidate_pool_answer_group_count"))
        return gc is not None and gc <= 2

    subguard_metrics = compute_metrics(dropped, lambda r: decision_original_fs_le1(r) if _group_le_2(r) else None)

    total_losses = losses
    report_lines = [
        "# FS==1 Dropped Slice Analysis", "",
        f"Rows where the original fs<=1 rule fires but the fs0 rule blocks (frontier_support == 1 exactly): {len(dropped)}",
        f"- wins={wins}, losses={losses}, ties={ties}, net={wins - losses}",
        "", "## Provider/dataset distribution (diagnostic)", "",
    ]
    for k, v in sorted(by_pd.items(), key=lambda kv: -kv[1]["losses"]):
        report_lines.append(f"- {k}: {v}")
    report_lines += ["", "## Artifact-quality distribution (diagnostic)", ""]
    for k, v in sorted(by_quality.items(), key=lambda kv: -kv[1]["losses"]):
        report_lines.append(f"- {k}: {v}")
    report_lines += [
        "", "## Loss concentration",
        f"- {total_losses} of {len(dropped)} triggered rows in this slice are losses "
        f"({(total_losses/len(dropped)) if dropped else None} regression rate).",
        "", "## Does fs==1 have an identifiable safer subguard?",
        f"- restricting fs==1 further to candidate_pool_answer_group_count<=2: "
        f"n={subguard_metrics['n_triggered']}, wins={subguard_metrics['wins']}, losses={subguard_metrics['losses']}, "
        f"net={subguard_metrics['net']}.",
        "", "## Should fs==1 be its own high-gain hypothesis rather than folded into the conservative candidate?",
        (f"Yes -- this slice alone nets {wins - losses} ({wins} wins / {losses} losses), a substantial positive "
         f"contribution on its own; it is exactly what pooled4_fs0_notie_risk_controlled_candidate deliberately "
         f"excludes for conservatism. It should be tracked as a separate, higher-risk/higher-gain hypothesis "
         f"(e.g. a future 'pooled4_fs1_only' candidate), not silently discarded.") if (wins - losses) > 0 else
        (f"No strong case -- this slice nets {wins - losses}, i.e. it is not a clearly beneficial regime on its own."),
    ]
    write_text(output_dir / "FS1_DROPPED_SLICE_ANALYSIS.md", "\n".join(report_lines) + "\n")

    return {"dropped": dropped, "wins": wins, "losses": losses, "ties": ties, "net": wins - losses}


# ---------------------------------------------------------------------------
# Task 4: pseudo-prospective stability (fs0 vs fs<=1)
# ---------------------------------------------------------------------------


def task4_stability(output_dir: Path, bank_rows: list[dict[str, Any]], discovery_table: Path) -> dict[str, Any]:
    action_region = [r for r in bank_rows if fires(decision_original_fs_le1, r) or fires(decision_fs0_risk_controlled, r)]

    def _eval(rows: list[dict[str, Any]], split: str, fold: str) -> list[dict[str, Any]]:
        out = []
        for name, fn in ((ORIGINAL_CANDIDATE_NAME, decision_original_fs_le1), (CANDIDATE_NAME, decision_fs0_risk_controlled)):
            m = compute_metrics(rows, fn)
            out.append({
                "split": split, "fold": fold, "candidate": name, "n_rows_in_fold": len(rows),
                "n_triggered": m["n_triggered"], "wins": m["wins"], "losses": m["losses"], "ties": m["ties"], "net": m["net"],
            })
        return out

    mtimes = load_artifact_mtimes(discovery_table)
    dated = []
    for r in action_region:
        mtime = mtimes.get(r.get("source_artifact_path"))
        if mtime:
            dated.append((mtime, r))
    dated.sort(key=lambda mr: mr[0])
    half = len(dated) // 2
    discovery_half = [r for _, r in dated[:half]]
    prospective_half = [r for _, r in dated[half:]]

    rows_out = _eval(discovery_half, "chronological", "discovery_half") + _eval(prospective_half, "chronological", "prospective_half")

    families = sorted({artifact_family(r["source_artifact_path"]) for r in action_region})
    for fam in families:
        held_out = [r for r in action_region if artifact_family(r["source_artifact_path"]) == fam]
        rows_out += _eval(held_out, "leave_one_family_out", fam)

    providers = sorted({r.get("provider") for r in action_region if r.get("provider")})
    for p in providers:
        held_out = [r for r in action_region if r.get("provider") == p]
        rows_out += _eval(held_out, "leave_one_provider_out", p)

    datasets = sorted({r.get("dataset") for r in action_region if r.get("dataset")})
    for d in datasets:
        held_out = [r for r in action_region if r.get("dataset") == d]
        rows_out += _eval(held_out, "leave_one_dataset_out", d)

    write_csv(
        output_dir / "FS0_PSEUDO_PROSPECTIVE_STABILITY.csv", rows_out,
        ["split", "fold", "candidate", "n_rows_in_fold", "n_triggered", "wins", "losses", "ties", "net"],
    )

    def _stable(candidate: str, split: str) -> bool:
        subset = [r for r in rows_out if r["candidate"] == candidate and r["split"] == split and r["n_triggered"] > 0]
        return len(subset) > 0 and all(r["net"] >= 0 for r in subset)

    stability = {}
    for name in (ORIGINAL_CANDIDATE_NAME, CANDIDATE_NAME):
        stability[name] = {
            "stable_chronological": _stable(name, "chronological"),
            "stable_leave_one_family_out": _stable(name, "leave_one_family_out"),
            "stable_leave_one_provider_out": _stable(name, "leave_one_provider_out"),
            "stable_leave_one_dataset_out": _stable(name, "leave_one_dataset_out"),
        }

    write_text(
        output_dir / "FS0_PSEUDO_PROSPECTIVE_STABILITY.md",
        "\n".join(
            [
                "# FS0 Pseudo-Prospective Stability", "",
                f"discovery_half n={len(discovery_half)}, prospective_half n={len(prospective_half)} "
                f"(chronological, by artifact mtime); families={len(families)}, providers={len(providers)}, datasets={len(datasets)}.",
                "", "## Stability (net >= 0 in every non-empty fold)", "",
            ]
            + [f"- `{name}`: {stab}" for name, stab in stability.items()]
        )
        + "\n",
    )
    return stability


# ---------------------------------------------------------------------------
# Task 5: decision reports
# ---------------------------------------------------------------------------


def task5_decision(
    output_dir: Path, *, replay: dict[str, Any], dropped_slice: dict[str, Any], stability: dict[str, Any],
    protected_tmux_session: str,
) -> None:
    orig = replay["orig_metrics_all"]
    fs0 = replay["fs0_metrics_all"]
    fs0_safer = fs0["losses"] < orig["losses"] and fs0["regression_rate"] is not None and orig["regression_rate"] is not None and fs0["regression_rate"] <= orig["regression_rate"]
    too_conservative = fs0["n_triggered"] < 0.5 * orig["n_triggered"] if orig["n_triggered"] else True

    final_lines = [
        "# Final FS0 Risk-Controlled Freeze Summary", "",
        f"generated_utc: {now_iso()}", "",
        f"## Global comparison", "",
        f"- `{ORIGINAL_CANDIDATE_NAME}`: n={orig['n_triggered']}, wins={orig['wins']}, losses={orig['losses']}, net={orig['net']}, "
        f"regression_rate={orig['regression_rate']}",
        f"- `{CANDIDATE_NAME}`: n={fs0['n_triggered']}, wins={fs0['wins']}, losses={fs0['losses']}, net={fs0['net']}, "
        f"regression_rate={fs0['regression_rate']}",
        f"- fs==1 dropped slice: wins={dropped_slice['wins']}, losses={dropped_slice['losses']}, net={dropped_slice['net']}",
        "", "## Is fs0 safer than fs<=1?",
        f"{'Yes' if fs0_safer else 'Not clearly'} -- lower absolute losses ({fs0['losses']} vs {orig['losses']}) "
        f"and regression_rate ({fs0['regression_rate']} vs {orig['regression_rate']}).",
        "", "## Is fs0 too conservative?",
        f"{'Possibly -- ' if too_conservative else 'No -- '}it triggers on {fs0['n_triggered']} of {orig['n_triggered']} "
        f"original-rule cases ({(fs0['n_triggered']/orig['n_triggered']) if orig['n_triggered'] else None} of the action region), "
        f"discarding the fs==1 slice which alone nets {dropped_slice['net']}.",
        "", "## Should fs0 replace fs<=1, or should both be kept as separate candidates?",
        "Both should be kept as separate candidates. fs0 is strictly more conservative and does not dominate fs<=1 "
        f"(the fs==1 slice it drops is net {'positive' if dropped_slice['net'] > 0 else 'non-positive'} on its own). "
        "Neither has been prospectively validated; keeping both preserves the option to freeze/validate whichever the "
        "fresh data supports, per FRESH_VALIDATION_DECISION.md.",
        "", "## Should the running seed-83 result still be evaluated against original fs<=1?",
        f"Yes. That live validation was pre-registered against `{ORIGINAL_CANDIDATE_NAME}`; this freeze/audit is retrospective "
        f"and offline and must not change how that already-launched run (tmux session `{protected_tmux_session}`) is scored.",
        "", "## Should the next Azure validation test fs<=1, fs0, or both post-hoc?",
        "Both, post-hoc, from the same generated records: fs<=1 and fs0 are both deterministic functions of the same "
        "four raw answers + frontier_support + FTA answer, so a single live generation run can evaluate both candidates "
        "without any additional API calls.",
        "", "## Is fs0 ready for fresh API validation later?",
        f"{'Yes, as a pseudo-prospective-supported candidate' if all(stability.get(CANDIDATE_NAME, {}).values()) else 'Not yet -- some stability checks failed, see FS0_PSEUDO_PROSPECTIVE_STABILITY.md'} "
        "-- but 'ready for fresh validation' means eligible to be proposed for a future, separately-authorized live run, "
        "not validated or promoted by this offline pass.",
        "", "## What should not be claimed?",
        "- That fs0 is safer in general -- only that it is safer *on this historical bank*.",
        "- That fs0 has been prospectively validated on fresh data (it has not).",
        "- That fs0 replaces or supersedes pooled4_fs_le1_notie_fta_v2_candidate.",
        "- That the fs==1 dropped slice is worthless -- it is a separate, potentially high-gain hypothesis, not evidence against fs0.",
        "- Any manuscript claim change or production promotion from this offline freeze/audit.",
    ]
    write_text(output_dir / "FINAL_FS0_RISK_CONTROLLED_FREEZE_SUMMARY.md", "\n".join(final_lines) + "\n")

    decision_lines = [
        "# Fresh Validation Decision", "",
        f"- Is fs0 safer than fs<=1 (on historical data)? {'Yes' if fs0_safer else 'Not clearly'}",
        f"- Is fs0 too conservative? {'Possibly' if too_conservative else 'No'}",
        "- Should fs0 replace fs<=1? No -- keep as two separate tracked candidates.",
        "- Should the running seed-83 result still be scored against original fs<=1? Yes, unconditionally.",
        "- Should the next Azure validation test fs<=1, fs0, or both? Both, post-hoc, from one generation run.",
        f"- Is fs0 ready for fresh API validation later? "
        f"{'Yes (pseudo-prospective-supported)' if all(stability.get(CANDIDATE_NAME, {}).values()) else 'Not yet'}",
        "- What should not be claimed? See FINAL_FS0_RISK_CONTROLLED_FREEZE_SUMMARY.md's final section.",
    ]
    write_text(output_dir / "FRESH_VALIDATION_DECISION.md", "\n".join(decision_lines) + "\n")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--bank-csv", default=str(DEFAULT_BANK_CSV))
    parser.add_argument("--discovery-table", default=str(DEFAULT_DISCOVERY_TABLE))
    parser.add_argument("--protected-tmux-session", default="cohere_pooled4_fs_le1_validation_20260709T024735Z")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    if output_dir.exists():
        raise FileExistsError(f"refusing to write into an existing directory: {output_dir}")
    output_dir.mkdir(parents=True)

    bank_rows = load_bank_rows(Path(args.bank_csv))

    task1_freeze(output_dir)
    task1_legality_audit(output_dir, bank_rows)
    replay = task2_global_replay(output_dir, bank_rows)
    dropped_slice = task3_dropped_slice(output_dir, bank_rows)
    stability = task4_stability(output_dir, bank_rows, Path(args.discovery_table))
    task5_decision(output_dir, replay=replay, dropped_slice=dropped_slice, stability=stability, protected_tmux_session=args.protected_tmux_session)

    print(json.dumps({
        "output_dir": str(output_dir),
        "fs0_wins": replay["fs0_metrics_all"]["wins"],
        "fs0_losses": replay["fs0_metrics_all"]["losses"],
        "fs0_net": replay["fs0_metrics_all"]["net"],
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
