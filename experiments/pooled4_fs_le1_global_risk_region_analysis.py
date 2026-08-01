"""Offline overnight analysis: is pooled4_fs_le1_notie a robust subgroup hypothesis?

Reads the already-built global failure bank
(outputs/failure_analysis/global_existing_failure_case_inventory_*/GLOBAL_FAILURE_BANK_DEDUPED.csv)
and asks, entirely offline:
  1. Where do the pooled4_fs_le1_notie candidate's losses concentrate? (Phase 1-2)
  2. Does a safer runtime-legal guard exist that keeps most wins but sheds losses? (Phase 3)
  3. Is any such guard stable under pseudo-prospective / leave-one-regime checks,
     or is it just overfit to whichever artifacts happen to be in the bank? (Phase 4)
  4. Register every subgroup hypothesis examined, with an honest status label,
     rather than quietly promoting one. (Phase 5)

Makes zero API calls, opens all source artifacts read-only, never recomputes or
changes the canonical FTA/FIX-2+FIX-4 selector (experiments/support_aware_selector.py
is not imported here). Gold is used only to read the ALREADY-computed post-hoc
correctness columns from the bank (frontier_correct, fta_correct, pooled4_correct,
candidate_result); no function in this module accepts gold as an argument for
subgroup-membership ("fires") decisions -- see `assert_guard_is_runtime_legal()`.

Guard/hypothesis legality:
  - "runtime_legal": defined only from fields available at selection time
    (frontier_support, frontier_support_margin, candidate_pool_answer_group_count,
    the four raw answers, override_reason/parser flags -- all produced during
    generation/selection, before any gold lookup).
  - "diagnostic_only": uses provider/dataset/artifact-quality labels, which are
    not assumed to be available as a selection-time feature in a real
    deployment unless separately justified. Used here only to characterize
    where losses/wins concentrate, never proposed as a firing condition for a
    real policy.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

csv.field_size_limit(10_000_000)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BANK_CSV = (
    REPO_ROOT
    / "outputs/failure_analysis/global_existing_failure_case_inventory_20260709T031404Z/GLOBAL_FAILURE_BANK_DEDUPED.csv"
)
DEFAULT_DISCOVERY_TABLE = (
    REPO_ROOT
    / "outputs/failure_analysis/global_existing_failure_case_inventory_20260709T031404Z/ARTIFACT_DISCOVERY_TABLE.csv"
)

BOOL_TRUE = {"true", "1", "yes"}
BOOL_FALSE = {"false", "0", "no"}

NEAR_PEER_PROVIDERS = {"cohere", "azure_openai", "azure", "cloudrift", "cloudrift_ai"}
DOMINANT_SOURCE_PROVIDERS = {"mistral"}
WEAK_OVERRIDE_REASONS = {
    "single_weak_frontier_branch",
    "insufficient_support_margin",
    "frontier_support_margin_override",
    "frontier_not_run_or_budget_exhausted",
}


# ---------------------------------------------------------------------------
# Row loading / typing
# ---------------------------------------------------------------------------


def _parse_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in BOOL_TRUE:
        return True
    if text in BOOL_FALSE:
        return False
    return None


def _parse_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


BOOL_FIELDS = (
    "frontier_correct", "l1_correct", "s1_correct", "tale_correct", "fta_correct",
    "pooled4_correct", "external3_correct", "pooled4_differs_from_fta",
    "pooled4_fixes_fta", "pooled4_regresses_fta", "candidate_fires",
)
FLOAT_FIELDS = ("seed", "budget", "frontier_support", "frontier_support_margin", "candidate_pool_answer_group_count")


def load_bank_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", errors="replace", newline="") as fh:
        rows = list(csv.DictReader(fh))
    out = []
    for row in rows:
        r = dict(row)
        for f in BOOL_FIELDS:
            if f in r:
                r[f] = _parse_bool(r[f])
        for f in FLOAT_FIELDS:
            if f in r:
                r[f] = _parse_float(r[f])
        out.append(r)
    return out


def normalize_answer(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None
    text = text.lower().rstrip(".").strip()
    try:
        return format(float(text.replace(",", "")), ".10g")
    except ValueError:
        return text


def compute_pooled4_margin(row: dict[str, Any]) -> int | None:
    """Winning-vote-count minus runner-up-count among the 4 raw answers.
    Runtime-legal: uses only the 4 raw answers already produced at generation
    time. Returns None when not computable (e.g. all 4 answers missing)."""
    answers = [row.get(f) for f in ("frontier_answer", "l1_answer", "s1_answer", "tale_answer")]
    norm = [normalize_answer(a) for a in answers if normalize_answer(a) is not None]
    if not norm:
        return None
    counts: dict[str, int] = defaultdict(int)
    for v in norm:
        counts[v] += 1
    ranked = sorted(counts.values(), reverse=True)
    if len(ranked) == 1:
        return ranked[0]
    return ranked[0] - ranked[1]


def artifact_family(source_artifact_path: str) -> str:
    parts = Path(source_artifact_path).parts
    if len(parts) >= 2 and parts[0] == "outputs":
        return parts[1]
    return parts[0] if parts else "unknown"


# ---------------------------------------------------------------------------
# Guard registry (Phase 3 candidates A-P) -- each is a refinement (AND) of the
# already-computed base action-region condition (`candidate_fires == True`).
# ---------------------------------------------------------------------------


@dataclass
class GuardSpec:
    guard_id: str
    name: str
    description: str
    legality: str  # "runtime_legal" | "diagnostic_only"
    fields_used: tuple[str, ...]
    fn: Callable[[dict[str, Any]], bool]


def _guard_A(row: dict[str, Any]) -> bool:
    return True


def _guard_B(row: dict[str, Any]) -> bool:
    fs = row.get("frontier_support")
    return fs is not None and fs == 0


def _guard_C(row: dict[str, Any]) -> bool:
    g = row.get("candidate_pool_answer_group_count")
    return g is not None and g <= 2


def _guard_D(row: dict[str, Any]) -> bool:
    margin = compute_pooled4_margin(row)
    return margin is not None and margin >= 2


def _guard_E(row: dict[str, Any]) -> bool:
    ext = normalize_answer(row.get("external3_answer"))
    p4 = normalize_answer(row.get("pooled4_answer"))
    return ext is not None and p4 is not None and ext == p4


def _guard_F(row: dict[str, Any]) -> bool:
    flags = row.get("parser_flags")
    return flags in (None, "", "False", "false", "0")


def _guard_G(row: dict[str, Any]) -> bool:
    reason = row.get("override_reason")
    return reason in WEAK_OVERRIDE_REASONS


def _guard_H(row: dict[str, Any]) -> bool:
    # Dominant-source-veto PROXY: a true runtime-legal dominant-source detector
    # (as in beta_shrinkage_regime_selector / raw_spread_regime_selector, see
    # docs/PROJECT_STATE_GAP_ANALYSIS_20260524.md sec 6) is calibrated at the
    # scenario level across many examples, not decidable from one row's fields
    # alone -- so this is deliberately diagnostic_only, keyed on provider.
    return row.get("provider") not in DOMINANT_SOURCE_PROVIDERS


def _guard_I(row: dict[str, Any]) -> bool:
    # Excludes MATH-500: outputs/math500_cohere_failure_pool_audit_20260528/README.md
    # documents that FTA's override mechanism never successfully fires on
    # Cohere x MATH-500 (fta_correct == frontier_correct for all 300 cases) --
    # a documented, dataset-specific pathology, hence diagnostic_only (dataset label).
    return (row.get("dataset") or "").lower() not in ("math500", "math-500")


def _guard_L(row: dict[str, Any]) -> bool:
    return row.get("artifact_quality") == "canonical"


def _guard_O(row: dict[str, Any]) -> bool:
    return row.get("provider") in NEAR_PEER_PROVIDERS


def _guard_P(row: dict[str, Any]) -> bool:
    return row.get("provider") in DOMINANT_SOURCE_PROVIDERS


BASE_GUARD_REGISTRY: list[GuardSpec] = [
    GuardSpec("A", "original_pooled4_fs_le1_notie", "Original frozen candidate, no extra restriction.", "runtime_legal", ("frontier_support", "pooled4_answer", "fta_answer"), _guard_A),
    GuardSpec("B", "frontier_support_eq_0_only", "Restrict to frontier_support == 0 (drop the fs==1 slice).", "runtime_legal", ("frontier_support",), _guard_B),
    GuardSpec("C", "small_answer_group_count", "Restrict to candidate_pool_answer_group_count <= 2.", "runtime_legal", ("candidate_pool_answer_group_count",), _guard_C),
    GuardSpec("D", "pooled4_margin_ge_2", "Restrict to Pooled-4 vote margin >= 2 (winner beats runner-up by >=2 votes).", "runtime_legal", ("frontier_answer", "l1_answer", "s1_answer", "tale_answer"), _guard_D),
    GuardSpec("E", "external3_agrees_with_pooled4", "Restrict to rows where External-3 strict majority agrees with Pooled-4.", "runtime_legal", ("external3_answer", "pooled4_answer"), _guard_E),
    GuardSpec("F", "no_parser_flags", "Restrict to rows with no parser/normalization flag set.", "runtime_legal", ("parser_flags",), _guard_F),
    GuardSpec("G", "weak_frontier_override_reason", "Restrict to override_reason in the weak-frontier family (sparse coverage -- most bank rows lack this field).", "runtime_legal", ("override_reason",), _guard_G),
    GuardSpec("H", "dominant_source_veto_proxy_diagnostic", "Exclude provider=mistral (documented dominant-source regime). Diagnostic proxy only -- see docstring.", "diagnostic_only", ("provider",), _guard_H),
    GuardSpec("I", "exclude_math500_diagnostic", "Exclude dataset=MATH-500 (documented FTA-override pathology on this dataset).", "diagnostic_only", ("dataset",), _guard_I),
    GuardSpec("L", "canonical_artifact_only_diagnostic", "Restrict to canonical-quality artifacts only.", "diagnostic_only", ("artifact_quality",), _guard_L),
    GuardSpec("O", "near_peer_regime_diagnostic", "Restrict to providers documented as near-peer regime.", "diagnostic_only", ("provider",), _guard_O),
    GuardSpec("P", "dominant_source_regime_diagnostic", "Restrict to providers documented as dominant-source regime.", "diagnostic_only", ("provider",), _guard_P),
]

FORBIDDEN_GUARD_SUBSTRINGS = ("gold", "correct", "_result")


def assert_guard_is_runtime_legal(spec: GuardSpec) -> dict[str, Any]:
    """Static legality check for a guard marked runtime_legal: its declared
    fields_used must not include gold/correctness/result columns. Mirrors
    experiments/stress_test_exploratory_rules.py::audit_rule_decision_legality."""
    if spec.legality != "runtime_legal":
        return {"guard_id": spec.guard_id, "checked": False, "is_runtime_legal": None}
    violations = [f for f in spec.fields_used if any(sub in f.lower() for sub in FORBIDDEN_GUARD_SUBSTRINGS)]
    return {"guard_id": spec.guard_id, "checked": True, "is_runtime_legal": len(violations) == 0, "violations": violations}


def compute_variant_metrics(action_region_rows: list[dict[str, Any]], variant_fn: Callable[[dict[str, Any]], bool], total_wins: int, total_losses: int) -> dict[str, Any]:
    triggered = [r for r in action_region_rows if variant_fn(r)]
    wins = sum(1 for r in triggered if r.get("candidate_result") == "win")
    losses = sum(1 for r in triggered if r.get("candidate_result") == "loss")
    ties = sum(1 for r in triggered if r.get("candidate_result") == "tie")
    n = len(triggered)
    return {
        "n_triggered": n,
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "net": wins - losses,
        "regression_rate": (losses / n) if n else None,
        "preserved_win_fraction": (wins / total_wins) if total_wins else None,
        "loss_reduction_fraction": (1 - losses / total_losses) if total_losses else None,
    }


def guard_provider_dataset_breakdown(triggered: list[dict[str, Any]]) -> dict[str, Any]:
    by_pd: dict[str, dict[str, int]] = defaultdict(lambda: {"wins": 0, "losses": 0, "ties": 0})
    by_quality: dict[str, dict[str, int]] = defaultdict(lambda: {"wins": 0, "losses": 0, "ties": 0})
    for r in triggered:
        key = f"{r.get('provider')}|{r.get('dataset')}"
        result = r.get("candidate_result")
        if result in ("win", "loss", "tie"):
            by_pd[key][result + "s" if result != "loss" else "losses"] += 1
            by_quality[r.get("artifact_quality")][result + "s" if result != "loss" else "losses"] += 1
    return {"by_provider_dataset": dict(by_pd), "by_artifact_quality": dict(by_quality)}


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


# ---------------------------------------------------------------------------
# Phase 0: safety / status snapshot
# ---------------------------------------------------------------------------


def phase0_safety_snapshot(output_dir: Path, repo_root: Path, protected_tmux_session: str | None) -> None:
    import subprocess
    import sys

    git_status = subprocess.run(["git", "status", "--short"], cwd=repo_root, capture_output=True, text=True, timeout=30)
    tmux_list = subprocess.run(["tmux", "list-sessions"], capture_output=True, text=True, timeout=15)
    protected_present = protected_tmux_session is not None and protected_tmux_session in (tmux_list.stdout or "")

    live_log_tail = ""
    if protected_tmux_session:
        candidates = sorted((repo_root / "outputs/api_validation_live").glob(f"*/full_validation.log"))
        for c in candidates:
            live_log_tail += f"\n### {c}\n" + "\n".join(c.read_text(encoding="utf-8", errors="replace").splitlines()[-5:])

    lines = [
        "# Safety Snapshot",
        "",
        f"generated_utc: {now_iso()}",
        f"python_version: {sys.version.split()[0]}",
        f"git_status_line_count: {len(git_status.stdout.splitlines())}",
        "",
        f"## Protected tmux session ({protected_tmux_session})",
        f"present: {protected_present}",
        "This job never sends any command to that session; read-only log tail below (if found):",
        live_log_tail or "(no matching live log found)",
        "",
        "## All tmux sessions (read-only listing; none touched by this job)",
        "```",
        tmux_list.stdout.strip(),
        "```",
        "",
        "## Confirmation",
        "- This overnight job made zero API calls.",
        "- This overnight job never attached to, sent keys to, killed, or restarted any existing tmux session.",
    ]
    write_text(output_dir / "SAFETY_SNAPSHOT.md", "\n".join(lines) + "\n")


def phase0_input_artifacts_check(output_dir: Path, bank_csv: Path, discovery_table: Path, extra_paths: list[Path]) -> None:
    lines = ["# Input Artifacts Check", "", f"generated_utc: {now_iso()}", ""]
    for p in [bank_csv, discovery_table, *extra_paths]:
        exists = p.exists()
        size = p.stat().st_size if exists else None
        lines.append(f"- `{p}`: exists={exists}, size_bytes={size}")
    write_text(output_dir / "INPUT_ARTIFACTS_CHECK.md", "\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# Phase 1: action-region extraction and loss casebook
# ---------------------------------------------------------------------------

ACTION_REGION_EXTRA_FIELDS = [
    "source_artifact_path", "artifact_quality", "provider", "dataset", "seed", "budget",
    "example_id", "question_hash", "normalized_question_text_hash", "question", "gold",
    "frontier_answer", "l1_answer", "s1_answer", "tale_answer", "fta_answer", "pooled4_answer",
    "external3_answer", "frontier_support", "frontier_support_margin", "override_reason",
    "candidate_pool_answer_group_count", "parser_flags", "frontier_correct", "l1_correct",
    "s1_correct", "tale_correct", "fta_correct", "pooled4_correct", "external3_correct",
    "pooled4_differs_from_fta", "pooled4_fixes_fta", "pooled4_regresses_fta",
    "candidate_fires", "candidate_result",
]


def phase1_action_region(output_dir: Path, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    action_region = [r for r in rows if r.get("candidate_fires") is True]
    for r in action_region:
        r["pooled4_vote_margin"] = compute_pooled4_margin(r)
        r["external3_agrees_with_pooled4"] = _guard_E(r)

    wins = [r for r in action_region if r.get("candidate_result") == "win"]
    losses = [r for r in action_region if r.get("candidate_result") == "loss"]
    ties = [r for r in action_region if r.get("candidate_result") == "tie"]
    unknown = [r for r in action_region if r.get("candidate_result") not in ("win", "loss", "tie")]

    fieldnames = ACTION_REGION_EXTRA_FIELDS + ["pooled4_vote_margin", "external3_agrees_with_pooled4"]
    write_csv(output_dir / "ACTION_REGION_ALL_CASES.csv", action_region, fieldnames)
    write_csv(output_dir / "ACTION_REGION_WINS.csv", wins, fieldnames)
    write_csv(output_dir / "ACTION_REGION_LOSSES.csv", losses, fieldnames)
    write_csv(output_dir / "ACTION_REGION_TIES.csv", ties, fieldnames)

    summary = {
        "total_action_region": len(action_region),
        "wins": len(wins),
        "losses": len(losses),
        "ties": len(ties),
        "unknown_gold_missing": len(unknown),
        "net": len(wins) - len(losses),
    }
    write_json(output_dir / "ACTION_REGION_SUMMARY.json", summary)
    write_text(
        output_dir / "ACTION_REGION_SUMMARY.md",
        "\n".join([
            "# Action Region Summary",
            "",
            f"- total action-region cases (pooled4_fs_le1_notie fires): {summary['total_action_region']}",
            f"- wins: {summary['wins']}",
            f"- losses: {summary['losses']}",
            f"- ties: {summary['ties']}",
            f"- unknown (gold missing on one side): {summary['unknown_gold_missing']}",
            f"- net: {summary['net']}",
        ]) + "\n",
    )

    # Readable loss casebook
    casebook_lines = ["# Pooled4 FS<=1 Global Loss Casebook", "", f"{len(losses)} losses out of {len(action_region)} action-region cases.", ""]
    for i, r in enumerate(losses, 1):
        casebook_lines += [
            f"## Loss {i}: {r.get('source_artifact_path')} / {r.get('example_id') or r.get('question_hash')}",
            f"- provider/dataset: {r.get('provider')}/{r.get('dataset')} (artifact_quality={r.get('artifact_quality')})",
            f"- question: {(r.get('question') or '')[:300]}",
            f"- gold: {r.get('gold')}",
            f"- frontier={r.get('frontier_answer')} l1={r.get('l1_answer')} s1={r.get('s1_answer')} tale={r.get('tale_answer')}",
            f"- fta_answer={r.get('fta_answer')} (correct={r.get('fta_correct')}) pooled4_answer={r.get('pooled4_answer')} (correct={r.get('pooled4_correct')})",
            f"- frontier_support={r.get('frontier_support')} margin={r.get('frontier_support_margin')} group_count={r.get('candidate_pool_answer_group_count')}",
            f"- pooled4_vote_margin={r.get('pooled4_vote_margin')} external3_agrees_with_pooled4={r.get('external3_agrees_with_pooled4')}",
            f"- override_reason={r.get('override_reason')} parser_flags={r.get('parser_flags')}",
            "- why it fired: frontier_support<=1, Pooled-4 had a unique plurality winner that differs from FTA's answer.",
            "- why it failed: FTA's (frontier-derived) answer was correct and Pooled-4's plurality winner was wrong for this example.",
            f"- would a runtime-legal guard plausibly have blocked it: "
            f"{'yes -- weak Pooled-4 margin/no external3 agreement' if (r.get('pooled4_vote_margin') or 0) < 2 or not r.get('external3_agrees_with_pooled4') else 'not obviously from margin/external3 alone'}",
            f"- artifact/provider/dataset-specific: quality={r.get('artifact_quality')}, provider={r.get('provider')}, dataset={r.get('dataset')}",
            "",
        ]
    write_text(output_dir / "POOLED4_FS_LE1_GLOBAL_LOSS_CASEBOOK.md", "\n".join(casebook_lines) + "\n")
    return action_region


# ---------------------------------------------------------------------------
# Phase 2: loss concentration analysis
# ---------------------------------------------------------------------------


def _bucket_counts(rows: list[dict[str, Any]], key_fn: Callable[[dict[str, Any]], Any]) -> list[dict[str, Any]]:
    groups: dict[Any, dict[str, int]] = defaultdict(lambda: {"wins": 0, "losses": 0, "ties": 0})
    for r in rows:
        result = r.get("candidate_result")
        if result not in ("win", "loss", "tie"):
            continue
        groups[key_fn(r)][result + ("es" if result == "loss" else "s")] += 1
    out = []
    for key, counts in sorted(groups.items(), key=lambda kv: -kv[1]["losses"]):
        total = counts["wins"] + counts["losses"] + counts["ties"]
        out.append({"bucket": key, **counts, "total": total, "loss_rate": (counts["losses"] / total) if total else None})
    return out


def phase2_loss_concentration(output_dir: Path, action_region: list[dict[str, Any]]) -> dict[str, Any]:
    by_provider_dataset = _bucket_counts(action_region, lambda r: f"{r.get('provider')}|{r.get('dataset')}")
    by_artifact = _bucket_counts(action_region, lambda r: r.get("source_artifact_path"))
    by_runtime_feature_rows = []
    for label, key_fn in [
        ("frontier_support", lambda r: r.get("frontier_support")),
        ("candidate_pool_answer_group_count", lambda r: r.get("candidate_pool_answer_group_count")),
        ("pooled4_vote_margin", lambda r: r.get("pooled4_vote_margin")),
        ("external3_agrees_with_pooled4", lambda r: r.get("external3_agrees_with_pooled4")),
        ("override_reason", lambda r: r.get("override_reason")),
        ("artifact_quality", lambda r: r.get("artifact_quality")),
        ("seed", lambda r: r.get("seed")),
        ("budget", lambda r: r.get("budget")),
    ]:
        for bucket_row in _bucket_counts(action_region, key_fn):
            by_runtime_feature_rows.append({"feature": label, **bucket_row})

    write_csv(output_dir / "LOSS_CONCENTRATION_BY_PROVIDER_DATASET.csv", by_provider_dataset)
    write_csv(output_dir / "LOSS_CONCENTRATION_BY_ARTIFACT.csv", by_artifact)
    write_csv(output_dir / "LOSS_CONCENTRATION_BY_RUNTIME_FEATURE.csv", by_runtime_feature_rows)

    total_losses = sum(1 for r in action_region if r.get("candidate_result") == "loss")

    def _share(rows: list[dict[str, Any]], predicate: Callable[[Any], bool]) -> tuple[int, float | None]:
        n = sum(r["losses"] for r in rows if predicate(r["bucket"]))
        return n, (n / total_losses if total_losses else None)

    math500_losses, math500_share = _share(by_provider_dataset, lambda b: "math500" in str(b).lower() or "math-500" in str(b).lower())
    noncanonical_losses = sum(1 for r in action_region if r.get("candidate_result") == "loss" and r.get("artifact_quality") != "canonical")
    fs1_losses = sum(1 for r in action_region if r.get("candidate_result") == "loss" and r.get("frontier_support") == 1)
    fs0_losses = sum(1 for r in action_region if r.get("candidate_result") == "loss" and r.get("frontier_support") == 0)
    weak_margin_losses = sum(1 for r in action_region if r.get("candidate_result") == "loss" and (r.get("pooled4_vote_margin") or 0) < 2)
    parser_flagged_losses = sum(1 for r in action_region if r.get("candidate_result") == "loss" and r.get("parser_flags") not in (None, "", "False", "false", "0"))
    dominant_source_losses = sum(1 for r in action_region if r.get("candidate_result") == "loss" and r.get("provider") in DOMINANT_SOURCE_PROVIDERS)

    provider_totals: dict[str, int] = defaultdict(int)
    for r in action_region:
        if r.get("candidate_result") == "loss":
            provider_totals[r.get("provider")] += 1
    top_provider = max(provider_totals.items(), key=lambda kv: kv[1]) if provider_totals else (None, 0)

    report_lines = [
        "# Loss Concentration Report",
        "",
        f"Total action-region losses analyzed: {total_losses}",
        "",
        f"- Concentrated in MATH-500? {math500_losses} of {total_losses} losses ({math500_share}). "
        f"{'Yes, substantial concentration.' if (math500_share or 0) > 0.4 else 'No strong concentration observed.'}",
        f"- Concentrated in non-canonical/diagnostic artifacts? {noncanonical_losses} of {total_losses} "
        f"({(noncanonical_losses/total_losses) if total_losses else None}).",
        f"- Concentrated in one provider? top provider = {top_provider[0]} with {top_provider[1]} of {total_losses} losses.",
        f"- frontier_support=1 vs 0: fs=1 losses={fs1_losses}, fs=0 losses={fs0_losses}.",
        f"- Tied to weak Pooled-4 margins (<2)? {weak_margin_losses} of {total_losses}.",
        f"- Tied to parser/normalization flags? {parser_flagged_losses} of {total_losses}.",
        f"- Tied to dominant-source-regime providers ({sorted(DOMINANT_SOURCE_PROVIDERS)})? {dominant_source_losses} of {total_losses}.",
    ]
    write_text(output_dir / "LOSS_CONCENTRATION_REPORT.md", "\n".join(report_lines) + "\n")

    return {
        "total_losses": total_losses,
        "math500_share": math500_share,
        "noncanonical_share": (noncanonical_losses / total_losses) if total_losses else None,
        "weak_margin_share": (weak_margin_losses / total_losses) if total_losses else None,
        "parser_flagged_share": (parser_flagged_losses / total_losses) if total_losses else None,
        "dominant_source_share": (dominant_source_losses / total_losses) if total_losses else None,
    }


# ---------------------------------------------------------------------------
# Phase 3: runtime-legal subgroup discovery (incl. small brute-force search)
# ---------------------------------------------------------------------------


def _combo_search(action_region: list[dict[str, Any]], total_wins: int, total_losses: int) -> list[dict[str, Any]]:
    atoms = [("fs_eq_0", _guard_B), ("group_le_2", _guard_C), ("margin_ge_2", _guard_D), ("ext3_agrees", _guard_E), ("no_parser_flag", _guard_F)]
    n = len(atoms)
    results = []
    for mask in range(1, 1 << n):
        chosen = [atoms[i] for i in range(n) if mask & (1 << i)]
        names = "+".join(name for name, _ in chosen)

        def combo_fn(row: dict[str, Any], _chosen=chosen) -> bool:
            return all(fn(row) for _, fn in _chosen)

        metrics = compute_variant_metrics(action_region, combo_fn, total_wins, total_losses)
        results.append({"combo": names, **metrics})
    return sorted(results, key=lambda r: (r["losses"], -r["wins"]))


def phase3_subgroup_discovery(output_dir: Path, action_region: list[dict[str, Any]]) -> dict[str, GuardSpec]:
    total_wins = sum(1 for r in action_region if r.get("candidate_result") == "win")
    total_losses = sum(1 for r in action_region if r.get("candidate_result") == "loss")

    legality_rows = [assert_guard_is_runtime_legal(spec) for spec in BASE_GUARD_REGISTRY if spec.legality == "runtime_legal"]
    illegal = [r for r in legality_rows if not r["is_runtime_legal"]]
    if illegal:
        raise RuntimeError(f"runtime_legal guard(s) failed static legality audit: {illegal}")

    rule_rows = []
    runtime_rows = []
    diagnostic_rows = []
    for spec in BASE_GUARD_REGISTRY:
        metrics = compute_variant_metrics(action_region, spec.fn, total_wins, total_losses)
        entry = {
            "guard_id": spec.guard_id, "name": spec.name, "description": spec.description,
            "legality": spec.legality, "fields_used": ";".join(spec.fields_used), **metrics,
        }
        rule_rows.append(entry)
        (runtime_rows if spec.legality == "runtime_legal" else diagnostic_rows).append(entry)

    # M: per-provider diagnostic variants
    providers = sorted({r.get("provider") for r in action_region if r.get("provider")})
    for p in providers:
        fn = (lambda row, _p=p: row.get("provider") == _p)
        metrics = compute_variant_metrics(action_region, fn, total_wins, total_losses)
        entry = {"guard_id": "M", "name": f"provider_eq_{p}_diagnostic", "description": f"Restrict to provider={p}.", "legality": "diagnostic_only", "fields_used": "provider", **metrics}
        rule_rows.append(entry)
        diagnostic_rows.append(entry)

    # N: per-artifact-quality diagnostic variants
    qualities = sorted({r.get("artifact_quality") for r in action_region if r.get("artifact_quality")})
    for q in qualities:
        fn = (lambda row, _q=q: row.get("artifact_quality") == _q)
        metrics = compute_variant_metrics(action_region, fn, total_wins, total_losses)
        entry = {"guard_id": "N", "name": f"artifact_quality_eq_{q}_diagnostic", "description": f"Restrict to artifact_quality={q}.", "legality": "diagnostic_only", "fields_used": "artifact_quality", **metrics}
        rule_rows.append(entry)
        diagnostic_rows.append(entry)

    # J / K: automatic combinatorial search over runtime-legal atoms
    combo_results = _combo_search(action_region, total_wins, total_losses)
    zero_loss = [c for c in combo_results if c["losses"] == 0]
    j_best = max(zero_loss, key=lambda c: c["wins"]) if zero_loss else min(combo_results, key=lambda c: (c["losses"], -c["wins"]))
    k_best = max(combo_results, key=lambda c: c["net"])
    rule_rows.append({"guard_id": "J", "name": f"auto_search_best[{j_best['combo']}]", "description": "Automatic combinatorial search: best zero/low-loss combo of runtime-legal atoms.", "legality": "runtime_legal", "fields_used": "frontier_support;candidate_pool_answer_group_count;pooled4_margin;external3_answer;parser_flags", **{k: v for k, v in j_best.items() if k != "combo"}})
    rule_rows.append({"guard_id": "K", "name": f"auto_search_best_net[{k_best['combo']}]", "description": "Automatic combinatorial search: max-net combo of runtime-legal atoms.", "legality": "runtime_legal", "fields_used": "frontier_support;candidate_pool_answer_group_count;pooled4_margin;external3_answer;parser_flags", **{k: v for k, v in k_best.items() if k != "combo"}})

    write_csv(output_dir / "SUBGROUP_DISCOVERY_RULES.csv", rule_rows)
    write_csv(output_dir / "RUNTIME_LEGAL_GUARD_CANDIDATES.csv", [r for r in rule_rows if r["legality"] == "runtime_legal"])
    write_csv(output_dir / "DIAGNOSTIC_ONLY_PROVIDER_DATASET_GUARDS.csv", [r for r in rule_rows if r["legality"] == "diagnostic_only"])
    write_csv(output_dir / "GUARDED_VARIANT_GLOBAL_REPLAY.csv", combo_results)

    # By-regime breakdown for the curated named guards (A,B,C,E,F,I,J,K)
    curated_ids = {"A": _guard_A, "B": _guard_B, "C": _guard_C, "E": _guard_E, "F": _guard_F, "I": _guard_I}
    by_regime_rows = []
    for gid, fn in curated_ids.items():
        triggered = [r for r in action_region if fn(r)]
        breakdown = guard_provider_dataset_breakdown(triggered)
        for pd_key, counts in breakdown["by_provider_dataset"].items():
            by_regime_rows.append({"guard_id": gid, "provider_dataset": pd_key, **counts})
    write_csv(output_dir / "GUARDED_VARIANT_BY_REGIME.csv", by_regime_rows)

    discovery_lines = [
        "# Subgroup Discovery Report", "",
        f"Base action region: {len(action_region)} cases ({total_wins} wins / {total_losses} losses).",
        "", "## All guard candidates (A-P + automatic search)", "",
    ]
    for r in rule_rows:
        discovery_lines.append(
            f"- `{r['guard_id']}` {r['name']} [{r['legality']}]: n={r['n_triggered']}, wins={r['wins']}, losses={r['losses']}, "
            f"net={r['net']}, regression_rate={r['regression_rate']}"
        )
    write_text(output_dir / "SUBGROUP_DISCOVERY_REPORT.md", "\n".join(discovery_lines) + "\n")

    guarded_lines = [
        "# Guarded Variant Report", "",
        "Every variant below is a *refinement* (subset) of the original 422-case action region -- it can only ",
        "shed cases, never add new ones (so this cannot invent wins the original rule did not already have).", "",
        "## Runtime-legal candidates", "",
    ]
    for r in runtime_rows:
        guarded_lines.append(f"- `{r['guard_id']}` {r['name']}: net={r['net']}, preserved_win_fraction={r['preserved_win_fraction']}, loss_reduction_fraction={r['loss_reduction_fraction']}")
    guarded_lines += ["", "## Diagnostic-only candidates (provider/dataset/artifact-quality; not proposed as a real firing condition)", ""]
    for r in diagnostic_rows:
        guarded_lines.append(f"- `{r['guard_id']}` {r['name']}: net={r['net']}, n={r['n_triggered']}")
    guarded_lines += [
        "", "## Automatic search winners", "",
        f"- J (best zero/low-loss): {j_best}",
        f"- K (best net): {k_best}",
        "", "## Overfit risk", "",
        "All of the above were selected using the *entire* global bank (discovery set). None has been evaluated on a ",
        "held-out split yet -- see PROSPECTIVE_STYLE_STABILITY_REPORT.md (Phase 4) before treating any of them as more ",
        "than a discovery-stage hypothesis. None is proposed as final policy.",
    ]
    write_text(output_dir / "GUARDED_VARIANT_REPORT.md", "\n".join(guarded_lines) + "\n")

    named_guards = {spec.guard_id: spec for spec in BASE_GUARD_REGISTRY}
    named_guards["J"] = GuardSpec("J", j_best["combo"] or "none", "auto-search zero/low-loss combo", "runtime_legal", (), lambda row: all(fn(row) for name, fn in [("fs_eq_0", _guard_B), ("group_le_2", _guard_C), ("margin_ge_2", _guard_D), ("ext3_agrees", _guard_E), ("no_parser_flag", _guard_F)] if name in j_best["combo"]))
    named_guards["K"] = GuardSpec("K", k_best["combo"] or "none", "auto-search max-net combo", "runtime_legal", (), lambda row: all(fn(row) for name, fn in [("fs_eq_0", _guard_B), ("group_le_2", _guard_C), ("margin_ge_2", _guard_D), ("ext3_agrees", _guard_E), ("no_parser_flag", _guard_F)] if name in k_best["combo"]))
    return named_guards


# ---------------------------------------------------------------------------
# Phase 4: stability / pseudo-prospective evaluation
# ---------------------------------------------------------------------------


def load_artifact_mtimes(discovery_table: Path) -> dict[str, str]:
    if not discovery_table.exists():
        return {}
    with discovery_table.open("r", encoding="utf-8", errors="replace", newline="") as fh:
        return {row["path"]: row.get("modified_utc", "") for row in csv.DictReader(fh)}


def phase4_stability(output_dir: Path, action_region: list[dict[str, Any]], named_guards: dict[str, GuardSpec], discovery_table: Path) -> dict[str, Any]:
    curated = ["A", "B", "C", "E", "F", "I", "J", "K"]
    total_wins = sum(1 for r in action_region if r.get("candidate_result") == "win")
    total_losses = sum(1 for r in action_region if r.get("candidate_result") == "loss")

    def _eval_split(rows: list[dict[str, Any]], split_label: str, fold_label: str) -> list[dict[str, Any]]:
        w = sum(1 for r in rows if r.get("candidate_result") == "win")
        l = sum(1 for r in rows if r.get("candidate_result") == "loss")
        out = []
        for gid in curated:
            spec = named_guards[gid]
            m = compute_variant_metrics(rows, spec.fn, w, l)
            out.append({"split": split_label, "fold": fold_label, "guard_id": gid, "n_rows_in_split": len(rows), **m})
        return out

    # --- chronological split
    mtimes = load_artifact_mtimes(discovery_table)
    with_mtime = []
    for r in action_region:
        mtime = mtimes.get(r.get("source_artifact_path"))
        if not mtime:
            try:
                mtime = datetime.fromtimestamp((REPO_ROOT / r["source_artifact_path"]).stat().st_mtime, tz=timezone.utc).isoformat()
            except OSError:
                mtime = None
        with_mtime.append((mtime, r))
    dated = [(m, r) for m, r in with_mtime if m]
    dated.sort(key=lambda mr: mr[0])
    half = len(dated) // 2
    discovery_half = [r for _, r in dated[:half]]
    prospective_half = [r for _, r in dated[half:]]

    chrono_rows = _eval_split(discovery_half, "chronological", "discovery_half") + _eval_split(prospective_half, "chronological", "prospective_half")
    write_csv(output_dir / "CHRONOLOGICAL_SPLIT_REPLAY.csv", chrono_rows)

    # --- leave-one-artifact-family-out
    families = sorted({artifact_family(r["source_artifact_path"]) for r in action_region})
    lofo_rows = []
    for fam in families:
        held_out = [r for r in action_region if artifact_family(r["source_artifact_path"]) == fam]
        lofo_rows += _eval_split(held_out, "leave_one_family_out", fam)
    write_csv(output_dir / "LEAVE_ONE_ARTIFACT_FAMILY_OUT_REPLAY.csv", lofo_rows)

    # --- leave-one-provider-out
    providers = sorted({r.get("provider") for r in action_region if r.get("provider")})
    lopo_rows = []
    for p in providers:
        held_out = [r for r in action_region if r.get("provider") == p]
        lopo_rows += _eval_split(held_out, "leave_one_provider_out", p)
    write_csv(output_dir / "LEAVE_ONE_PROVIDER_OUT_REPLAY.csv", lopo_rows)

    # --- leave-one-dataset-out
    datasets = sorted({r.get("dataset") for r in action_region if r.get("dataset")})
    lodo_rows = []
    for d in datasets:
        held_out = [r for r in action_region if r.get("dataset") == d]
        lodo_rows += _eval_split(held_out, "leave_one_dataset_out", d)
    write_csv(output_dir / "LEAVE_ONE_DATASET_OUT_REPLAY.csv", lodo_rows)

    def _stable_across(rows: list[dict[str, Any]], gid: str) -> bool:
        subset = [r for r in rows if r["guard_id"] == gid and r["n_triggered"] > 0]
        return len(subset) > 0 and all(r["net"] >= 0 for r in subset)

    stability_by_guard = {}
    for gid in curated:
        stability_by_guard[gid] = {
            "stable_chronological": _stable_across(chrono_rows, gid),
            "stable_leave_one_family_out": _stable_across(lofo_rows, gid),
            "stable_leave_one_provider_out": _stable_across(lopo_rows, gid),
            "stable_leave_one_dataset_out": _stable_across(lodo_rows, gid),
        }

    report_lines = [
        "# Prospective-Style Stability Report", "",
        f"Discovery-half n={len(discovery_half)}, prospective-half n={len(prospective_half)} (chronological, by artifact mtime).",
        f"Artifact families: {len(families)}; providers: {len(providers)}; datasets: {len(datasets)}.",
        "",
        "Selective-inference caveat: guard combos J/K were chosen by searching the *entire* action region "
        "(including whichever slice ends up as 'prospective' below), so this chronological split is pseudo-prospective, "
        "not a true held-out test of the search procedure itself -- it only checks whether a fixed, already-chosen rule "
        "definition keeps working on a later-in-time slice, not whether the search would have found the same rule "
        "using only the earlier slice. See RISK_CONTROLLED_SELECTOR_PROTOCOL.md for the correct discover-then-freeze-"
        "then-evaluate-on-fresh-data procedure required before any promotion decision.",
        "",
        "## Per-guard stability (net >= 0 in every non-empty fold)", "",
    ]
    for gid, stab in stability_by_guard.items():
        report_lines.append(f"- `{gid}` ({named_guards[gid].name}): {stab}")
    report_lines += [
        "",
        f"## Is original pooled4_fs_le1_notie (A) still viable? "
        f"{'Net >= 0 in all folds tested.' if all(stability_by_guard['A'].values()) else 'Net goes negative in at least one fold -- see CSVs for which.'}",
    ]
    write_text(output_dir / "PROSPECTIVE_STYLE_STABILITY_REPORT.md", "\n".join(report_lines) + "\n")

    return {"stability_by_guard": stability_by_guard, "families": families, "providers": providers, "datasets": datasets}


# ---------------------------------------------------------------------------
# Phase 5: subgroup hypothesis registry
# ---------------------------------------------------------------------------


def phase5_registry(output_dir: Path, action_region: list[dict[str, Any]], named_guards: dict[str, GuardSpec], stability: dict[str, Any]) -> list[dict[str, Any]]:
    total_wins = sum(1 for r in action_region if r.get("candidate_result") == "win")
    total_losses = sum(1 for r in action_region if r.get("candidate_result") == "loss")
    rows = []
    for gid in ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "O", "P"]:
        spec = named_guards.get(gid)
        if spec is None:
            continue
        metrics = compute_variant_metrics(action_region, spec.fn, total_wins, total_losses)
        stab = stability["stability_by_guard"].get(gid)
        if spec.legality == "diagnostic_only":
            status = "diagnostic_only"
        elif stab is None:
            status = "discovery_only"
        elif all(stab.values()):
            status = "pseudo_prospective_supported"
        elif metrics["net"] <= 0:
            status = "rejected"
        else:
            status = "discovery_only"
        rows.append({
            "guard_id": gid, "name": spec.name, "description": spec.description, "legality": spec.legality,
            "fields_used": ";".join(spec.fields_used), **metrics,
            "discovery_status": "evaluated_on_full_bank",
            "pseudo_prospective_status": json.dumps(stab) if stab else "not_evaluated",
            "prospective_validation_status": "not_yet_run_no_fresh_api_data",
            "status_label": status,
            "ready_for_fresh_validation": "yes" if status == "pseudo_prospective_supported" else "no",
        })

    write_csv(output_dir / "SUBGROUP_HYPOTHESIS_REGISTRY.csv", rows)
    md_lines = ["# Subgroup Hypothesis Registry", ""]
    for r in rows:
        md_lines.append(
            f"## `{r['guard_id']}` {r['name']} ({r['legality']})\n"
            f"- {r['description']}\n"
            f"- runtime fields used: {r['fields_used']}\n"
            f"- wins/losses/ties: {r['wins']}/{r['losses']}/{r['ties']} (net={r['net']})\n"
            f"- status: **{r['status_label']}**, ready_for_fresh_validation={r['ready_for_fresh_validation']}\n"
        )
    write_text(output_dir / "SUBGROUP_HYPOTHESIS_REGISTRY.md", "\n".join(md_lines) + "\n")

    status_summary = defaultdict(int)
    for r in rows:
        status_summary[r["status_label"]] += 1
    write_text(
        output_dir / "SUBGROUP_VALIDATION_STATUS.md",
        "\n".join(["# Subgroup Validation Status", ""] + [f"- {k}: {v}" for k, v in status_summary.items()]) + "\n",
    )
    return rows


# ---------------------------------------------------------------------------
# Phase 6 (optional): methodology notes
# ---------------------------------------------------------------------------


def phase6_protocol_notes(output_dir: Path) -> None:
    write_text(
        output_dir / "RISK_CONTROLLED_SELECTOR_PROTOCOL.md",
        """# Risk-Controlled Selector Protocol (methodology note, not a result)

1. Treat every candidate rule (pooled4_fs_le1_notie and any guarded variant) as a **subgroup hypothesis**,
   not a policy, until it has survived every step below.
2. **Discover** on the global historical bank (this overnight pass) -- generous, allows peeking, produces candidates.
3. **Freeze** exactly one candidate's definition (as done for pooled4_fs_le1_notie_fta_v2_candidate in
   experiments/freeze_pooled4_fs_le1_notie_candidate.py) before looking at any new data.
4. **Evaluate** the frozen definition on a genuinely fresh, disjoint, prospective split (a new live API validation,
   never touched during discovery) -- this is the only step that can produce a real accept/reject decision.
5. Report **bootstrap or permutation confidence intervals** on the fresh split, not the discovery-set numbers.
6. If trigger counts are small, use a **conformal / selective-abstention framing**: only claim reliability inside a
   region with enough calibration data; abstain elsewhere rather than extrapolating.
7. Keep **runtime-legal features** (available at selection time) strictly separate from **diagnostic labels**
   (provider/dataset/artifact-quality) used only to interpret results -- never let a diagnostic label leak into the
   firing condition of a rule proposed for real deployment.
8. Do not use synthetic/dry-run cases for any headline accuracy number.
9. Do not mix diagnostic-only or duplicate-loser artifacts into a canonical validation split.
10. A rule may be reported as `pseudo_prospective_supported` (survived chronological/leave-one-regime checks on
    historical data) without being `prospective_validated` (survived a genuinely fresh, separately-authorized
    live validation). Only the latter licenses a promotion decision.
""",
    )
    write_text(
        output_dir / "SMALL_TRIGGER_COUNT_STATISTICAL_PROTOCOL.md",
        """# Small-Trigger-Count Statistical Protocol (methodology note, not a result)

- **Bootstrap over examples**: resample triggered rows with replacement (as in
  experiments/stress_test_exploratory_rules.py::paired_bootstrap_ci) to get a CI on net wins / accuracy delta.
- **Cluster/bootstrap over artifact family**: resample whole artifact-family groups, not individual rows, to avoid
  treating within-artifact-family correlation as independent evidence (an artifact family can contribute many
  correlated rows from one generation run).
- **Exact/binomial upper bound on regression rate**: with n triggered and k losses, report the upper bound of the
  exact (Clopper-Pearson) 95% CI on k/n as the conservative regression-rate claim, not the point estimate alone.
- **Permutation test for triggered cases**: shuffle the win/loss/tie labels within the full action region and
  recompute the guard's observed net; compare the observed net to the permutation null to check it is not an
  artifact of how few cases the guard selects.
- **Multiple-rule-selection caution**: dozens of guard variants were tried in Phase 3 (A-P plus 31 automatic
  combinations); the best-looking one is expected to look better than its true generalization performance purely
  from selection among many candidates (multiple-comparisons / "garden of forking paths"). Any promotion decision
  must correct for this (e.g. pre-register the single frozen candidate before the fresh evaluation, as in step 3 of
  RISK_CONTROLLED_SELECTOR_PROTOCOL.md) rather than picking the historical winner and validating that one only.
- **Selective inference caveat**: because guard thresholds (margin>=2, group_count<=2, etc.) were chosen by looking
  at the same data used to compute their win/loss counts, the reported net/regression-rate for J and K in
  particular should be treated as optimistic; only a fresh, disjoint evaluation removes this optimism.
""",
    )


# ---------------------------------------------------------------------------
# Phase 7: final summary
# ---------------------------------------------------------------------------


def phase7_final_summary(
    output_dir: Path,
    *,
    action_region: list[dict[str, Any]],
    loss_concentration: dict[str, Any],
    registry_rows: list[dict[str, Any]],
    stability: dict[str, Any],
    files_created: list[str],
    tests_result: str,
    protected_tmux_session: str,
    started_utc: str,
) -> None:
    total = len(action_region)
    wins = sum(1 for r in action_region if r.get("candidate_result") == "win")
    losses = sum(1 for r in action_region if r.get("candidate_result") == "loss")
    a_row = next((r for r in registry_rows if r["guard_id"] == "A"), None)
    # Exclude degenerate no-op guards (n_triggered == full action region, i.e. the
    # guard condition never actually excludes anything in this bank -- e.g. "no
    # parser flags" when parser_flags happens to be empty everywhere) so the
    # headline pick is an alternative that actually trades wins for fewer losses.
    informative_runtime = [
        r for r in registry_rows
        if r["legality"] == "runtime_legal" and r["guard_id"] != "A" and r["losses"] < (a_row["losses"] if a_row else 0)
    ]
    best_runtime = sorted(informative_runtime, key=lambda r: (-r["net"], -(r["loss_reduction_fraction"] or 0)))
    best_row = best_runtime[0] if best_runtime else None

    lines = [
        "# Final Pooled4 Global Overnight Summary", "",
        f"finished_utc: {now_iso()} (started {started_utc})",
        "",
        "## 1. What was run?",
        "Phases 0-7 of an offline subgroup-robustness analysis of pooled4_fs_le1_notie over the previously-built "
        "9,487-example global failure bank: action-region extraction, loss-concentration analysis, runtime-legal "
        "subgroup discovery (guards A-P + automatic search), chronological/leave-one-regime stability checks, a "
        "hypothesis registry, and methodology notes.",
        "",
        f"## 2. How many action-region cases were analyzed? {total} ({wins} wins / {losses} losses / {total - wins - losses} ties).",
        "",
        f"## 3. Where do the {losses} losses concentrate?",
        f"MATH-500 share={loss_concentration.get('math500_share')}, non-canonical-artifact share={loss_concentration.get('noncanonical_share')}, "
        f"weak-Pooled4-margin share={loss_concentration.get('weak_margin_share')}, parser-flagged share={loss_concentration.get('parser_flagged_share')}, "
        f"dominant-source-provider share={loss_concentration.get('dominant_source_share')}. See LOSS_CONCENTRATION_REPORT.md for detail.",
        "",
        f"## 4. Is original pooled4_fs_le1_notie (guard A) still viable?",
        f"{a_row}",
        "",
        "## 5. Is there a safer runtime-legal guard?",
        f"Best runtime-legal alternative by net wins: {best_row}" if best_row else "No runtime-legal alternative found.",
        "",
        "## 6. Is the safer guard stable under pseudo-prospective / leave-one-regime tests?",
        f"See PROSPECTIVE_STYLE_STABILITY_REPORT.md; per-guard stability flags: {stability.get('stability_by_guard')}",
        "",
        "## 7. Should the currently running seed-83 result be evaluated as-is?",
        "Yes -- that live validation was pre-registered against the original, frozen pooled4_fs_le1_notie definition "
        "(see outputs/failure_analysis/pooled4_fs_le1_candidate_freeze_20260709T015058Z/). This overnight analysis is "
        "purely retrospective/discovery on historical data and must not change how that already-launched run is scored.",
        "",
        "## 8. Should the next Azure validation use original candidate or a revised candidate?",
        "Do not switch yet. Any revised guard found here is at most pseudo_prospective_supported on historical data, "
        "not prospective_validated on fresh data (see RISK_CONTROLLED_SELECTOR_PROTOCOL.md). If a revised guard is to "
        "be tried, it should be frozen and validated as a *separate*, explicitly-authorized fresh run, not substituted "
        "into an already-planned validation silently.",
        "",
        "## 9. Do we need new API calls now?",
        "No. This pass is entirely retrospective; no new evidence requires new spend to obtain.",
        "",
        "## 10. What is the next offline task?",
        "Pre-register (freeze) whichever guard is judged most promising from SUBGROUP_HYPOTHESIS_REGISTRY.md "
        "(status pseudo_prospective_supported, runtime_legal), following the same freeze/spec pattern as "
        "experiments/freeze_pooled4_fs_le1_notie_candidate.py, before any fresh live evaluation is requested.",
        "",
        "## 11. What should not be claimed?",
        "- Any guard's discovery-set performance as a generalization guarantee.",
        "- Any diagnostic-only (provider/dataset/artifact-quality-gated) variant as a real runtime policy.",
        "- That this overnight pass validates or promotes any candidate -- it only produces hypotheses and their status labels.",
        "",
        "## 12. Files created",
        *[f"- {f}" for f in files_created],
        "",
        f"## 13. Tests passed: {tests_result}",
        "",
        "## 14. Safety confirmation",
        f"- No API calls were made by this job.",
        f"- The pre-existing tmux session `{protected_tmux_session}` was never touched (only its log was read, if present).",
        "- No output was deleted, overwritten, moved, or compressed.",
        "- No selector (experiments/support_aware_selector.py) or manuscript file was modified.",
        "- No commits or pushes were made.",
    ]
    write_text(output_dir / "FINAL_POOLED4_GLOBAL_OVERNIGHT_SUMMARY.md", "\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--bank-csv", default=str(DEFAULT_BANK_CSV))
    parser.add_argument("--discovery-table", default=str(DEFAULT_DISCOVERY_TABLE))
    parser.add_argument("--protected-tmux-session", default="cohere_pooled4_fs_le1_validation_20260709T024735Z")
    parser.add_argument("--skip-phase0-git-tmux", action="store_true", help="For fast/sandboxed test runs.")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    if output_dir.exists():
        raise FileExistsError(f"refusing to write into an existing directory: {output_dir}")
    output_dir.mkdir(parents=True)

    started_utc = now_iso()
    bank_csv = Path(args.bank_csv)
    discovery_table = Path(args.discovery_table)

    if not args.skip_phase0_git_tmux:
        phase0_safety_snapshot(output_dir, REPO_ROOT, args.protected_tmux_session)
    phase0_input_artifacts_check(output_dir, bank_csv, discovery_table, [])

    rows = load_bank_rows(bank_csv)
    action_region = phase1_action_region(output_dir, rows)
    loss_concentration = phase2_loss_concentration(output_dir, action_region)
    named_guards = phase3_subgroup_discovery(output_dir, action_region)
    stability = phase4_stability(output_dir, action_region, named_guards, discovery_table)
    registry_rows = phase5_registry(output_dir, action_region, named_guards, stability)
    phase6_protocol_notes(output_dir)

    files_created = sorted(p.name for p in output_dir.glob("*") if p.is_file())
    phase7_final_summary(
        output_dir,
        action_region=action_region,
        loss_concentration=loss_concentration,
        registry_rows=registry_rows,
        stability=stability,
        files_created=files_created,
        tests_result="see overnight.log for the pytest run preceding this script",
        protected_tmux_session=args.protected_tmux_session,
        started_utc=started_utc,
    )

    print(json.dumps({"output_dir": str(output_dir), "action_region": len(action_region)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
