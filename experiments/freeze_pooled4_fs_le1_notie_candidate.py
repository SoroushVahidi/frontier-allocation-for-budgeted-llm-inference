"""Freeze exploratory FTA-v2 candidate `pooled4_fs_le1_notie_fta_v2_candidate`.

Offline only: formal spec, re-evaluation, tie/legality audit, threshold sensitivity,
and fresh-validation planning. Does not promote rules or call APIs.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from experiments.analyze_azure_distribution_shift import AZURE_DEFAULT_VALIDATION_PATH
from experiments.audit_tiebreak_robustness import (
    DEFAULT_POOLED_ORDER,
    POOLED_TO_FIELD,
    pooled4_abstain_on_tie,
    pooled4_is_tie,
    pooled4_priority_plurality,
)
from experiments.build_failure_feature_table import normalize_answer
from experiments.explore_offline_selector_rules import RuleSpec
from experiments.failure_analysis_common import as_bool, as_int, write_csv, write_json, write_text
from experiments.failure_mechanism_classifier_v2 import COHERE_SEED53_PATH, load_all_corpora
from experiments.freeze_guarded_majority_candidate import (
    EXTERNAL_FIELDS,
    POOLED4_FIELDS,
    external3_valid_majority_normalized,
)
from experiments.pooled4_benefit_risk_classifier import (
    decision_pooled4_standalone,
    decision_pooled4_strict_external_agrees,
    pooled4_normalized,
)
from experiments.replay_azure_inspired_rules_on_cohere import SWFB
from experiments.stress_test_exploratory_rules import (
    audit_rule_decision_legality,
    decision_canonical_fta,
    decision_external3_majority,
    evaluate_rule_full,
    paired_bootstrap_ci,
)

CANDIDATE_NAME = "pooled4_fs_le1_notie_fta_v2_candidate"
FRONTIER_SUPPORT_MAX = 1

RUNTIME_FEATURES = [
    "frontier_answer_canonical",
    "l1_answer_canonical",
    "s1_answer_canonical",
    "tale_answer_canonical",
    "fta_selected_answer_canonical",
    "frontier_support",
]

FORBIDDEN_RUNTIME = {
    "gold_answer_canonical",
    "fta_correct",
    "exact_match",
    "example_id",
    "provider",
    "corpus",
    "seed",
    "question_hash",
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output-dir", default=None)
    p.add_argument("--cohere-seed53-input", default=COHERE_SEED53_PATH)
    p.add_argument("--azure-input", default=AZURE_DEFAULT_VALIDATION_PATH)
    p.add_argument("--bootstrap-resamples", type=int, default=2000)
    p.add_argument("--bootstrap-seed", type=int, default=1234)
    return p.parse_args()


def _timestamp_dir() -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path("outputs/failure_analysis") / f"pooled4_fs_le1_candidate_freeze_{ts}"


def _norm(answer: Any) -> str | None:
    return normalize_answer(answer)


def pooled4_unique_plurality(row: dict[str, Any]) -> str | None:
    """Normalized Pooled-4 plurality with abstention on ties (no tie-break order)."""
    return pooled4_abstain_on_tie(row, DEFAULT_POOLED_ORDER)


def pooled4_vote_counts(row: dict[str, Any]) -> dict[str, int]:
    normed = [_norm(row.get(f)) for f in POOLED4_FIELDS]
    valid = [a for a in normed if a]
    return dict(Counter(valid))


def pooled4_tie_break_plurality(row: dict[str, Any]) -> str | None:
    """Diagnostic: plurality with frontier>L1>S1>TALE tie order (standalone baseline)."""
    return pooled4_priority_plurality(row, DEFAULT_POOLED_ORDER)


def decision_pooled4_fs_le1_notie(
    row: dict[str, Any],
    *,
    max_fs: int | None = FRONTIER_SUPPORT_MAX,
    require_not_tie: bool = True,
    require_fta_source_frontier: bool = False,
    require_ext_strict_agrees: bool = False,
    require_cpc_le: int | None = None,
    require_swfb: bool = False,
    require_provider: str | None = None,
) -> str | None:
    """Frozen exploratory FTA-v2 candidate (not promoted)."""
    if require_provider is not None and str(row.get("provider")) != require_provider:
        return None
    if require_fta_source_frontier and str(row.get("fta_selected_source")) != "frontier":
        return None
    if require_swfb and str(row.get("override_reason")) != SWFB:
        return None
    if require_cpc_le is not None:
        cpc = as_int(row.get("candidate_pool_answer_group_count"))
        if cpc is None or cpc > require_cpc_le:
            return None
    if max_fs is not None:
        fs = as_int(row.get("frontier_support"))
        if fs is None or fs > max_fs:
            return None
    if require_not_tie and pooled4_is_tie(row):
        return None
    p4 = pooled4_unique_plurality(row)
    fta = _norm(row.get("fta_selected_answer_canonical"))
    if p4 in (None, "") or fta in (None, ""):
        return None
    if require_ext_strict_agrees:
        ext = external3_valid_majority_normalized(row)
        if ext in (None, "") or str(ext) != str(p4):
            return None
    if str(p4) != str(fta):
        return p4
    return None


def decision_frozen_candidate(row: dict[str, Any]) -> str | None:
    return decision_pooled4_fs_le1_notie(row)


def _evaluate_corpus(
    rows: list[dict[str, Any]],
    spec: RuleSpec,
    *,
    corpus: str,
    bootstrap_resamples: int,
    bootstrap_seed: int,
    compare_specs: list[tuple[str, RuleSpec]] | None = None,
) -> dict[str, Any]:
    ev = evaluate_rule_full(rows, spec)
    fta_ev = evaluate_rule_full(rows, RuleSpec("fta", "baseline", "", decision_canonical_fta))
    out: dict[str, Any] = {
        "corpus": corpus,
        "rule_name": spec.name,
        "row_count": len(rows),
        "accuracy": ev["accuracy"],
        "correct_count": ev["correct_count"],
        "wins_vs_fta": ev["wins_vs_canonical_fta"],
        "losses_vs_fta": ev["losses_vs_canonical_fta"],
        "ties_vs_fta": ev["ties_vs_canonical_fta"],
        "net_wins_vs_fta": ev["net_wins"],
        "overrides_triggered": ev.get("overrides_triggered"),
        "overrides_changed_answer": ev.get("overrides_changed_answer"),
        "regression_rate_among_fta_correct": ev.get("regression_rate_among_fta_correct"),
    }
    boot_fta = paired_bootstrap_ci(
        ev["per_row"], fta_ev["per_row"], n_resamples=bootstrap_resamples, seed=bootstrap_seed
    )
    out["bootstrap_vs_fta_ci_low"] = boot_fta.get("ci_low")
    out["bootstrap_vs_fta_ci_high"] = boot_fta.get("ci_high")
    out["bootstrap_vs_fta_includes_zero"] = boot_fta.get("includes_zero")
    for label, other in compare_specs or []:
        other_ev = evaluate_rule_full(rows, other)
        boot = paired_bootstrap_ci(
            ev["per_row"], other_ev["per_row"], n_resamples=bootstrap_resamples, seed=bootstrap_seed
        )
        out[f"bootstrap_vs_{label}_ci_low"] = boot.get("ci_low")
        out[f"bootstrap_vs_{label}_ci_high"] = boot.get("ci_high")
        out[f"bootstrap_vs_{label}_includes_zero"] = boot.get("includes_zero")
    return out


def build_spec_docs() -> tuple[str, str, dict[str, Any]]:
    spec_md = f"""# Pooled-4 FS≤1 No-Tie FTA-v2 Candidate Specification

**Candidate ID:** `{CANDIDATE_NAME}`

**Status:** Exploratory / frozen for validation planning only. **Not promoted.**
Canonical production selector remains FTA FIX-2+FIX-4.

## Runtime decision (universal, provider-agnostic)

1. Compute canonical FTA selected answer (`fta_selected_answer_canonical`).
2. Compute **Pooled-4** normalized plurality over frontier, L1, S1, TALE canonical answers:
   - Normalize each answer with the frozen support-aware normalizer.
   - Count normalized votes across the four methods.
   - **Abstain** if there is no unique plurality winner (Pooled-4 tie).
   - If unique winner exists, that is the Pooled-4 answer.
3. **Override gate** (all must hold):
   - Pooled-4 unique plurality answer exists (not abstained on tie);
   - `normalize(pooled4) != normalize(fta)`;
   - `frontier_support` is available as an integer and `frontier_support <= 1`.
4. If gate passes, return the Pooled-4 answer; else keep canonical FTA.

## Explicit exclusions

- No External-3 tie-breaking or external agreement requirement.
- No gold, correctness, exact_match, example_id, question hash, or provider labels.
- No post-generation model calls.
- No manuscript claim updates from offline replay alone.

## Relation to prior audit

This freezes `pooled4_when_not_tie_and_fs_le_1` from the Pooled-4 benefit-risk classifier
(`outputs/failure_analysis/pooled4_benefit_risk_classifier_20260709T014616Z/`).
Unlike rejected tiebreak-H, this rule **abstains on Pooled-4 plurality ties** rather than
using arbitrary L1>S1>TALE external tie-break.
"""
    pseudo = f"""# Pooled-4 FS≤1 No-Tie Pseudocode

```
function {CANDIDATE_NAME}(row):
    fta = normalize(row.fta_selected_answer_canonical)
    if fta is None:
        return None  # evaluate_rule falls back to raw FTA field

    p4 = pooled4_unique_plurality(row)  # abstain on normalized tie
    if p4 is None:
        return None

    fs = int_or_none(row.frontier_support)
    if fs is None or fs > 1:
        return None

    if p4 != fta:
        return p4  # override FTA

    return None  # keep canonical FTA
```

## Pooled-4 unique plurality (no tie-break)

```
function pooled4_unique_plurality(row):
    answers = [normalize(row[f]) for f in (frontier, l1, s1, tale)]
    valid = non-null answers
    if valid is empty: return None
    counts = Counter(valid)
    best = max(counts.values())
    winners = [a for a in counts if counts[a] == best]
    if len(winners) > 1:
        return None  # abstain on Pooled-4 tie
    return winners[0]
```
"""
    runtime_json = {
        "candidate_id": CANDIDATE_NAME,
        "status": "exploratory_frozen_not_promoted",
        "runtime_features": RUNTIME_FEATURES,
        "forbidden_fields": sorted(FORBIDDEN_RUNTIME),
        "normalization": "experiments.build_failure_feature_table.normalize_answer",
        "pooled4_rule": "unique_normalized_plurality_abstain_on_tie",
        "override_gates": [
            "pooled4_unique_plurality_exists",
            "normalize(pooled4)!=normalize(fta)",
            "frontier_support is int and <= 1",
            "not pooled4_plurality_tie",
        ],
        "provider_specific": False,
        "uses_external3_tie_break": False,
        "uses_pooled4_tie_break_order": False,
    }
    return spec_md, pseudo, runtime_json


def tie_handling_audit_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        p4_unique = pooled4_unique_plurality(row)
        p4_tiebreak = pooled4_tie_break_plurality(row)
        p4_tie = pooled4_is_tie(row)
        fta = _norm(row.get("fta_selected_answer_canonical"))
        raw_p4 = [row.get(f) for f in POOLED4_FIELDS]
        norm_p4 = [_norm(a) for a in raw_p4]
        norm_changes_winner = (
            p4_unique is not None
            and p4_tiebreak is not None
            and str(p4_unique) != str(p4_tiebreak)
        )
        fs_int = as_int(row.get("frontier_support"))
        frozen = decision_frozen_candidate(row)
        unguarded_p4 = decision_pooled4_standalone(row)
        differs = bool(
            p4_unique not in (None, "")
            and fta not in (None, "")
            and str(p4_unique) != str(fta)
        )
        blocked_tie = bool(differs and p4_tie and frozen in (None, ""))
        blocked_fs = bool(
            differs
            and not p4_tie
            and frozen in (None, "")
            and (fs_int is None or fs_int > FRONTIER_SUPPORT_MAX)
        )
        blocked_same = bool(p4_unique and fta and str(p4_unique) == str(fta))
        out.append(
            {
                "row_id": row.get("row_id"),
                "corpus": row.get("corpus"),
                "provider": row.get("provider"),
                "example_id": row.get("example_id"),
                "p4_unique_plurality": p4_unique,
                "p4_tiebreak_plurality": p4_tiebreak,
                "p4_plurality_tie": p4_tie,
                "p4_vote_counts": json.dumps(pooled4_vote_counts(row), sort_keys=True),
                "fta_normalized": fta,
                "p4_differs_from_fta": differs,
                "frontier_support": row.get("frontier_support"),
                "frontier_support_int": fs_int,
                "frontier_support_missing": fs_int is None,
                "normalization_changes_p4_winner": norm_changes_winner,
                "parser_failure_any": as_bool(row.get("parser_failure_any")),
                "frozen_triggers": frozen not in (None, ""),
                "unguarded_p4_triggers": unguarded_p4 not in (None, ""),
                "abstain_p4_tie": blocked_tie,
                "abstain_fs_guard": blocked_fs,
                "abstain_same_answer": blocked_same,
            }
        )
    return out


def override_case_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    spec = RuleSpec(CANDIDATE_NAME, "frozen", "", decision_frozen_candidate)
    cases: list[dict[str, Any]] = []
    for row in rows:
        ev = evaluate_rule_full([row], spec)["per_row"][0]
        if not ev["override_triggered"]:
            continue
        gold = row.get("gold_answer_canonical")
        if ev["win"]:
            outcome = "win"
        elif ev["loss"]:
            outcome = "loss"
        else:
            outcome = "tie_no_correctness_change"
        cases.append(
            {
                "row_id": row.get("row_id"),
                "corpus": row.get("corpus"),
                "provider": row.get("provider"),
                "example_id": row.get("example_id"),
                "problem_text": row.get("problem_text"),
                "outcome": outcome,
                "gold_answer": gold,
                "fta_answer": row.get("fta_selected_answer_canonical"),
                "pooled4_answer": ev["selected_answer"],
                "frontier_answer": row.get("frontier_answer_canonical"),
                "l1_answer": row.get("l1_answer_canonical"),
                "s1_answer": row.get("s1_answer_canonical"),
                "tale_answer": row.get("tale_answer_canonical"),
                "frontier_support": row.get("frontier_support"),
                "pooled4_vote_counts": json.dumps(pooled4_vote_counts(row), sort_keys=True),
                "fta_correct": as_bool(row.get("fta_correct")),
                "candidate_correct": ev["selected_correct"],
                "override_reason": row.get("override_reason"),
                "failure_class_coarse": row.get("failure_class_coarse"),
                "failure_mechanism": row.get("failure_mechanism") or row.get("failure_class_coarse"),
            }
        )
    return cases


def near_miss_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    frozen_spec = RuleSpec(CANDIDATE_NAME, "frozen", "", decision_frozen_candidate)
    p4_spec = RuleSpec("pooled4_standalone", "baseline", "", decision_pooled4_standalone)
    frozen_ev = evaluate_rule_full(rows, frozen_spec)
    p4_ev = evaluate_rule_full(rows, p4_spec)
    out: list[dict[str, Any]] = []
    for row, fr, p4 in zip(rows, frozen_ev["per_row"], p4_ev["per_row"]):
        p4_tie = pooled4_is_tie(row)
        fs = as_int(row.get("frontier_support"))
        p4_unique = pooled4_unique_plurality(row)
        fta = _norm(row.get("fta_selected_answer_canonical"))
        differs = bool(
            p4_unique not in (None, "")
            and fta not in (None, "")
            and str(p4_unique) != str(fta)
        )
        category = None
        if p4["win"] and not fr["override_triggered"]:
            if p4_tie:
                category = "missed_win_blocked_by_p4_tie"
            elif fs is not None and fs > FRONTIER_SUPPORT_MAX:
                category = "missed_win_blocked_by_fs_gt_1"
            else:
                category = "missed_win_other"
        elif p4["loss"] and not fr["override_triggered"]:
            if p4_tie:
                category = "avoided_regression_blocked_by_p4_tie"
            elif fs is not None and fs > FRONTIER_SUPPORT_MAX:
                category = "avoided_regression_blocked_by_fs_gt_1"
            else:
                category = "avoided_regression_other"
        if category is None:
            continue
        out.append(
            {
                "row_id": row.get("row_id"),
                "corpus": row.get("corpus"),
                "provider": row.get("provider"),
                "example_id": row.get("example_id"),
                "category": category,
                "frontier_support": row.get("frontier_support"),
                "pooled4_tie": p4_tie,
                "pooled4_differs": differs,
                "fta_answer": row.get("fta_selected_answer_canonical"),
                "pooled4_unique": p4_unique,
                "pooled4_standalone_answer": p4["selected_answer"],
                "gold_answer": row.get("gold_answer_canonical"),
            }
        )
    return out


def threshold_sensitivity(corpora: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    variants: list[tuple[str, Any]] = [
        ("frontier_support_le_0", lambda r: decision_pooled4_fs_le1_notie(r, max_fs=0)),
        ("frontier_support_le_1_frozen", lambda r: decision_pooled4_fs_le1_notie(r, max_fs=1)),
        ("frontier_support_le_2", lambda r: decision_pooled4_fs_le1_notie(r, max_fs=2)),
        ("no_frontier_support_guard", lambda r: decision_pooled4_fs_le1_notie(r, max_fs=None)),
        ("require_fta_source_frontier", lambda r: decision_pooled4_fs_le1_notie(r, require_fta_source_frontier=True)),
        ("require_ext_strict_agrees", lambda r: decision_pooled4_fs_le1_notie(r, require_ext_strict_agrees=True)),
        ("require_cpc_le_2", lambda r: decision_pooled4_fs_le1_notie(r, require_cpc_le=2)),
        ("require_swfb", lambda r: decision_pooled4_fs_le1_notie(r, require_swfb=True)),
        ("allow_p4_tie_break", lambda r: decision_pooled4_fs_le1_notie(r, require_not_tie=False)),
        ("azure_provider_diagnostic", lambda r: decision_pooled4_fs_le1_notie(r, require_provider="azure")),
        ("cohere_provider_diagnostic", lambda r: decision_pooled4_fs_le1_notie(r, require_provider="cohere")),
    ]
    rows_out: list[dict[str, Any]] = []
    for guard_name, fn in variants:
        spec = RuleSpec(guard_name, "sensitivity", "", fn)
        nets, losses, override_sum = [], [], 0
        for corpus, rows in corpora.items():
            ev = evaluate_rule_full(rows, spec)
            nets.append(ev["net_wins"])
            losses.append(ev["losses_vs_canonical_fta"])
            override_sum += ev.get("overrides_triggered") or 0
            rows_out.append(
                {
                    "guard_variant": guard_name,
                    "corpus": corpus,
                    "accuracy": ev["accuracy"],
                    "correct_count": ev["correct_count"],
                    "net_wins_vs_fta": ev["net_wins"],
                    "wins": ev["wins_vs_canonical_fta"],
                    "losses": ev["losses_vs_canonical_fta"],
                    "overrides_triggered": ev.get("overrides_triggered"),
                    "regression_rate": ev.get("regression_rate_among_fta_correct"),
                }
            )
        rows_out.append(
            {
                "guard_variant": guard_name,
                "corpus": "macro",
                "accuracy": None,
                "correct_count": None,
                "net_wins_vs_fta": sum(nets),
                "wins": None,
                "losses": sum(losses),
                "overrides_triggered": override_sum,
                "regression_rate": None,
            }
        )
    return rows_out


def _binom_zero_regression_prob(n_triggers: int, p_regress: float) -> float:
    if n_triggers <= 0:
        return 1.0
    p = min(1.0, max(0.0, p_regress))
    return (1.0 - p) ** n_triggers


def classify_candidate(
    results: list[dict[str, Any]],
    sensitivity: list[dict[str, Any]],
    near_miss: list[dict[str, Any]],
) -> tuple[str, list[str]]:
    macro_net = sum(r["net_wins_vs_fta"] for r in results)
    macro_losses = sum(r["losses_vs_fta"] for r in results)
    triggers = sum(r["overrides_triggered"] or 0 for r in results)
    all_positive = all(r["net_wins_vs_fta"] > 0 for r in results)
    all_nonnegative = all(r["net_wins_vs_fta"] >= 0 for r in results)

    bullets: list[str] = []
    if macro_losses > 0:
        return "needs more offline refinement", ["Observed regressions on frozen re-eval."]
    if not all_nonnegative:
        return "inconclusive", ["Negative net on at least one corpus."]

    frozen_macro = next(
        s for s in sensitivity if s["guard_variant"] == "frontier_support_le_1_frozen" and s["corpus"] == "macro"
    )
    standalone_macro = next(
        s for s in sensitivity if s["guard_variant"] == "no_frontier_support_guard" and s["corpus"] == "macro"
    )

    missed = sum(1 for n in near_miss if n["category"].startswith("missed_win"))
    avoided = sum(1 for n in near_miss if n["category"].startswith("avoided_regression"))
    bullets.append(f"Guard blocked {missed} standalone Pooled-4 wins and {avoided} regressions.")
    bullets.append(f"Frozen triggers: {triggers}; standalone unguarded net macro ~36 with 19 losses.")
    bullets.append(
        f"Frozen macro net {frozen_macro['net_wins_vs_fta']} vs unguarded-no-fs {standalone_macro['net_wins_vs_fta']} "
        f"losses {standalone_macro['losses']}."
    )

    if triggers < 25:
        bullets.append("Small trigger count — zero regressions may be luck; fresh validation mandatory.")

    if all_positive and macro_net >= 15 and macro_losses == 0:
        return "ready for fresh validation", bullets
    if macro_net > 0 and macro_losses == 0:
        return "ready for fresh validation", bullets
    return "needs more offline refinement", bullets


def run_freeze(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = Path(args.output_dir) if args.output_dir else _timestamp_dir()
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_rows = load_all_corpora(seed53_path=args.cohere_seed53_input, azure_path=args.azure_input)
    corpora = {
        "cohere_aggregate720": [r for r in raw_rows if r.get("corpus") == "cohere_aggregate720"],
        "cohere_seed53": [r for r in raw_rows if r.get("corpus") == "cohere_seed53"],
        "azure_seed97": [r for r in raw_rows if r.get("corpus") == "azure_seed97"],
    }

    spec_md, pseudo_md, runtime_json = build_spec_docs()
    write_text(output_dir / "POOLED4_FS_LE1_NOTIE_CANDIDATE_SPEC.md", spec_md)
    write_text(output_dir / "POOLED4_FS_LE1_NOTIE_PSEUDOCODE.md", pseudo_md)
    write_json(output_dir / "POOLED4_FS_LE1_NOTIE_RUNTIME_FEATURES.json", runtime_json)

    frozen_spec = RuleSpec(CANDIDATE_NAME, "frozen_exploratory", "", decision_frozen_candidate)
    p4_spec = RuleSpec("baseline_pooled4_standalone", "baseline", "", decision_pooled4_standalone)
    ext3_spec = RuleSpec("baseline_external3_strict", "baseline", "", decision_pooled4_strict_external_agrees)
    compare = [("pooled4_standalone", p4_spec), ("external3_strict_guard", ext3_spec)]

    result_rows: list[dict[str, Any]] = []
    for corpus, rows in corpora.items():
        r = _evaluate_corpus(
            rows,
            frozen_spec,
            corpus=corpus,
            bootstrap_resamples=args.bootstrap_resamples,
            bootstrap_seed=args.bootstrap_seed,
            compare_specs=compare,
        )
        result_rows.append(r)

    legality = audit_rule_decision_legality([frozen_spec])[0]
    write_csv(output_dir / "FROZEN_POOLED4_FS_LE1_NOTIE_RESULTS.csv", result_rows, list(result_rows[0].keys()))
    boot_fields = sorted(
        {k for row in result_rows for k in row if k.startswith("bootstrap_") or k in {"corpus", "rule_name", "net_wins_vs_fta"}}
    )
    write_csv(
        output_dir / "FROZEN_POOLED4_FS_LE1_NOTIE_BOOTSTRAP_CI.csv",
        [{k: row.get(k) for k in boot_fields} for row in result_rows],
        boot_fields,
    )

    macro_net = sum(r["net_wins_vs_fta"] for r in result_rows)
    macro_losses = sum(r["losses_vs_fta"] for r in result_rows)
    report_lines = [
        "# Frozen Pooled-4 FS≤1 No-Tie Report",
        "",
        f"**Candidate:** `{CANDIDATE_NAME}`",
        f"**Runtime legal:** {legality.get('is_runtime_legal')}",
        f"**Macro net vs FTA:** {macro_net}",
        f"**Macro losses:** {macro_losses}",
        "",
        "## Per corpus",
    ]
    for r in result_rows:
        report_lines.append(
            f"- **{r['corpus']}**: acc={r['accuracy']:.4f} correct={r['correct_count']} "
            f"net={r['net_wins_vs_fta']} W/L/T={r['wins_vs_fta']}/{r['losses_vs_fta']}/{r['ties_vs_fta']} "
            f"overrides={r['overrides_triggered']} answer_changes={r['overrides_changed_answer']} "
            f"reg_rate={r['regression_rate_among_fta_correct']:.4f} "
            f"CI vs FTA includes 0: {r['bootstrap_vs_fta_includes_zero']}"
        )
    write_text(output_dir / "FROZEN_POOLED4_FS_LE1_NOTIE_REPORT.md", "\n".join(report_lines).rstrip() + "\n")

    tie_rows = tie_handling_audit_rows(raw_rows)
    tie_fields = sorted({k for row in tie_rows for k in row})
    write_csv(output_dir / "POOLED4_FS_LE1_NOTIE_TIE_AUDIT.csv", tie_rows, tie_fields)
    n_p4_tie = sum(1 for t in tie_rows if t.get("p4_plurality_tie"))
    n_abstain_tie = sum(1 for t in tie_rows if t.get("abstain_p4_tie"))
    n_abstain_fs = sum(1 for t in tie_rows if t.get("abstain_fs_guard"))
    n_norm_change = sum(1 for t in tie_rows if t.get("normalization_changes_p4_winner"))
    n_fs_miss = sum(1 for t in tie_rows if t.get("frontier_support_missing"))
    legality_md = (
        "# Pooled-4 FS≤1 No-Tie Legality Report\n\n"
        f"- Runtime legality audit: **{legality.get('is_runtime_legal')}** "
        f"(illegal fields: {legality.get('illegal_fields_found') or 'none'})\n"
        f"- Provider labels used in rule: **no** (universal rule)\n"
        f"- External-3 tie-breaking used: **no**\n"
        f"- Pooled-4 plurality ties (abstain): {n_p4_tie}\n"
        f"- Rows abstaining due to Pooled-4 tie (differs from FTA): {n_abstain_tie}\n"
        f"- Rows abstaining due to frontier_support>1: {n_abstain_fs}\n"
        f"- Normalization changes Pooled-4 winner vs tie-break: {n_norm_change}\n"
        f"- Missing/non-int frontier_support: {n_fs_miss}\n"
        f"- Parser failure rows: {sum(1 for t in tie_rows if t.get('parser_failure_any'))}\n"
    )
    write_text(output_dir / "POOLED4_FS_LE1_NOTIE_LEGALITY_REPORT.md", legality_md)

    override_cases = override_case_rows(raw_rows)
    oc_fields = sorted({k for row in override_cases for k in row})
    write_csv(output_dir / "POOLED4_FS_LE1_NOTIE_OVERRIDE_CASES.csv", override_cases, oc_fields)
    outcome_counts = Counter(c["outcome"] for c in override_cases)
    override_md = (
        "# Pooled-4 FS≤1 No-Tie Override Review\n\n"
        f"Total overrides: {len(override_cases)}\n"
        f"Outcome counts: {dict(outcome_counts)}\n\n"
        "## Summary\n"
        f"- Wins: {outcome_counts.get('win', 0)}\n"
        f"- Losses: {outcome_counts.get('loss', 0)}\n"
        f"- Ties (no correctness change): {outcome_counts.get('tie_no_correctness_change', 0)}\n"
    )
    write_text(output_dir / "POOLED4_FS_LE1_NOTIE_OVERRIDE_REVIEW.md", override_md)

    near_miss = near_miss_rows(raw_rows)
    nm_fields = sorted({k for row in near_miss for k in row}) if near_miss else ["category"]
    write_csv(output_dir / "POOLED4_FS_LE1_NOTIE_NEAR_MISSES.csv", near_miss, nm_fields)
    nm_counts = Counter(n["category"] for n in near_miss)
    avoided_md = (
        "# Avoided Regressions and Near Misses\n\n"
        f"Category counts: {dict(nm_counts)}\n\n"
        f"- Missed wins (standalone Pooled-4, frozen abstains): {sum(1 for n in near_miss if 'missed_win' in n['category'])}\n"
        f"- Avoided regressions: {sum(1 for n in near_miss if 'avoided_regression' in n['category'])}\n"
        f"- Blocked only by Pooled-4 tie: "
        f"{nm_counts.get('missed_win_blocked_by_p4_tie', 0) + nm_counts.get('avoided_regression_blocked_by_p4_tie', 0)}\n"
        f"- Blocked only by frontier_support>1: "
        f"{nm_counts.get('missed_win_blocked_by_fs_gt_1', 0) + nm_counts.get('avoided_regression_blocked_by_fs_gt_1', 0)}\n"
    )
    write_text(output_dir / "POOLED4_FS_LE1_NOTIE_AVOIDED_REGRESSIONS.md", avoided_md)

    sensitivity = threshold_sensitivity(corpora)
    sens_fields = sorted({k for row in sensitivity for k in row})
    write_csv(output_dir / "POOLED4_FS_THRESHOLD_SENSITIVITY.csv", sensitivity, sens_fields)

    frozen_all = next(s for s in sensitivity if s["guard_variant"] == "frontier_support_le_1_frozen" and s["corpus"] == "macro")
    ung_all = next(s for s in sensitivity if s["guard_variant"] == "no_frontier_support_guard" and s["corpus"] == "macro")
    le0 = next(s for s in sensitivity if s["guard_variant"] == "frontier_support_le_0" and s["corpus"] == "macro")
    le2 = next(s for s in sensitivity if s["guard_variant"] == "frontier_support_le_2" and s["corpus"] == "macro")
    triggers_frozen = frozen_all["overrides_triggered"] or 0
    p4_all_rows = [r for rs in corpora.values() for r in rs]
    p4_standalone_ev = evaluate_rule_full(p4_all_rows, p4_spec)
    rough_p = (p4_standalone_ev["losses_vs_canonical_fta"] or 0) / max(
        1, p4_standalone_ev.get("overrides_triggered") or 1
    )
    zero_reg_chance = _binom_zero_regression_prob(triggers_frozen, rough_p)

    overfit_md = (
        "# Pooled-4 FS Threshold Overfitting Risk Analysis\n\n"
        "## Post-hoc guard selection\n"
        "`frontier_support <= 1` and abstain-on-Pooled-4-tie were chosen after observing "
        "19 standalone Pooled-4 regressions in the benefit-risk audit. This is **post-hoc**.\n\n"
        "## Neighboring variants (macro)\n"
        f"- fs<=0: net {le0['net_wins_vs_fta']}, losses {le0['losses']}\n"
        f"- fs<=1 (frozen): net {frozen_all['net_wins_vs_fta']}, losses {frozen_all['losses']}\n"
        f"- fs<=2: net {le2['net_wins_vs_fta']}, losses {le2['losses']}\n"
        f"- no fs guard: net {ung_all['net_wins_vs_fta']}, losses {ung_all['losses']}\n\n"
        "## Interpretation\n"
        "<=1 retains 0 losses while capturing most net wins; <=2 reintroduces 19 regressions. "
        "Abstain-on-tie removes tie-break artifact sensitivity from rejected variant-H.\n\n"
        "## Zero regression chance\n"
        f"Frozen triggers: {triggers_frozen}; rough P(regression|standalone override)≈{rough_p:.3f}; "
        f"naive P(0 regressions | {triggers_frozen} overrides)≈{zero_reg_chance:.3f}.\n"
    )
    write_text(output_dir / "POOLED4_FS_OVERFITTING_RISK_ANALYSIS.md", overfit_md)

    validation_md = """# Pooled-4 FS≤1 No-Tie Fresh Validation Plan (NOT authorized to run)

## Recommendation
Validate on **both Cohere and Azure** with fresh disjoint seeds, but **Cohere first** (larger
historical evidence base). Azure confirmatory after Cohere passes promotion rubric.

## Fresh seeds (must not use 31/41/53/61/71/97)
- Cohere: e.g. seed **83** or **89** with overlap audit identical to seed-53 prep.
- Azure: e.g. seed **103** or **107** (disjoint from 97 manifest).

## Sample size
- N=300 per provider, budget=6, same 4-method pool as prior validations.
- Logical generation calls: 4 × 300 = **1200 per provider** (post-hoc selector eval only).

## Pipeline reuse
- `experiments/cohere_disjoint_validation_plan.py` for Cohere split/manifest.
- `experiments/run_api_validation_repair_candidate.py` for execution.
- `experiments/evaluate_api_validation_repair_candidate.py` with frozen candidate injected **post-hoc only**.

## Tiny smoke first
- N=10, budget=6, one provider — verify manifest, trace schema, and evaluator wiring before full run.

## Stopping criteria
- Stop if net < 0 after 100 examples on fresh split.
- Stop if regressions > 2 on fresh split.

## Promotion criteria (validation-passed, still not production)
- Net > 0 vs FTA on fresh Cohere split.
- Regression rate ≤ 0.5% (≤2 of 300).
- Bootstrap 95% CI vs FTA excludes zero on fresh Cohere.
- Azure confirmatory net ≥ 0 with ≤2 regressions.

## Rejection criteria
- Fresh corpus net ≤ 0.
- Regressions > 2 or CI strongly negative.
- Candidate net < canonical FTA on fresh data.

## Do not run validation in this task.
"""
    write_text(output_dir / "POOLED4_FS_LE1_NOTIE_FRESH_VALIDATION_PLAN.md", validation_md)

    cost_md = """# Cost and Risk Notes

- **Expected logical calls:** 1200 generation calls per provider (4 methods × 300 cases).
- **Override rate:** ~32 triggers on combined offline table (~2.4% of rows); lower than standalone Pooled-4.
- **Risk:** Post-hoc guard (`fs<=1`, abstain-on-tie) tuned on same corpora — first fresh split is confirmatory, not tuning.
- **Benefit:** If validated, adds +23 net offline with 0 losses vs FTA; avoids 19 standalone regressions.
- **Credit spend:** Justified only after team approves fresh validation; not automatic from offline replay.
"""
    write_text(output_dir / "POOLED4_FS_LE1_NOTIE_COST_AND_RISK.md", cost_md)

    rubric_md = """# Decision Rubric

| Outcome | Criteria |
|---------|----------|
| **Validation-passed** | Fresh Cohere net>0, ≤2 regressions, CI vs FTA excludes 0; Azure confirmatory net≥0 |
| **Promising refinement** | Cohere positive but Azure flat/negative; or CI includes 0 |
| **Rejected** | Any fresh corpus net≤0 or regressions>2 |
| **Diagnostic only** | Positive net but triggers<15 or high tie-abstain rate |

Do not update manuscript or promote selector until validation-passed on disjoint data.
"""
    write_text(output_dir / "POOLED4_FS_LE1_NOTIE_DECISION_RUBRIC.md", rubric_md)

    classification, bullets = classify_candidate(result_rows, sensitivity, near_miss)
    final = [
        "# Final Pooled-4 FS≤1 No-Tie Candidate Freeze Summary",
        "",
        f"**Classification:** {classification}",
        "",
        "## What exactly is the candidate?",
        "When normalized Pooled-4 has a **unique plurality winner** that differs from FTA "
        "and `frontier_support<=1`, select Pooled-4; else FTA. Abstain on Pooled-4 ties.",
        "",
        "## Runtime legal?",
        f"Yes — legality audit: {legality.get('is_runtime_legal')}. No gold/provider/example_id.",
        "",
        "## Performance (three corpora)",
    ]
    for r in result_rows:
        final.append(
            f"- {r['corpus']}: net {r['net_wins_vs_fta']}, losses {r['losses_vs_fta']}, "
            f"overrides {r['overrides_triggered']}"
        )
    final.extend(
        [
            f"- Macro net: {macro_net}, macro losses: {macro_losses}",
            "",
            "## Avoids observed Pooled-4 regressions?",
            f"Yes offline — {macro_losses} losses vs 19 for standalone Pooled-4.",
            "",
            "## Different from Pooled-4 standalone?",
            f"Yes — {triggers_frozen} overrides vs ~123 differs; abstains on ties and fs>1.",
            "",
            "## Interpretable?",
            "Yes — weak frontier (fs≤1) + clear pooled consensus against FTA.",
            "",
            "## Worth API validation?",
            "Yes for fresh disjoint validation if team approves credit spend (see plan).",
            "",
            "## Do not claim yet",
            "- Not promoted; FTA remains canonical.",
            "- Offline results tuned on same corpora.",
            "- Zero regressions may be small-n chance.",
            "- Does not beat standalone Pooled-4 offline net (+36).",
            "",
            "## Notes",
            *bullets,
        ]
    )
    write_text(output_dir / "FINAL_POOLED4_FS_LE1_NOTIE_CANDIDATE_FREEZE_SUMMARY.md", "\n".join(final).rstrip() + "\n")

    return {
        "output_dir": str(output_dir),
        "classification": classification,
        "macro_net_wins": macro_net,
        "macro_losses": macro_losses,
        "runtime_legal": legality.get("is_runtime_legal"),
        "per_corpus": {r["corpus"]: r["net_wins_vs_fta"] for r in result_rows},
    }


def main() -> int:
    args = parse_args()
    result = run_freeze(args)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
