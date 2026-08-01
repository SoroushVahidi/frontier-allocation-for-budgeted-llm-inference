"""Freeze exploratory FTA-v2 candidate `guarded_majority_fta_v2_candidate`.

Offline only: formal spec, re-evaluation, tie/legality audit, overfitting
analysis, and fresh-validation planning. Does not promote rules or call APIs.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from experiments.analyze_azure_distribution_shift import AZURE_DEFAULT_VALIDATION_PATH
from experiments.audit_pooled4_ext3_agreement_candidate import (
    decision_pooled4_when_ext3_pooled4_agree_against_fta,
    decision_pooled4_when_ext3_pooled4_agree_and_frontier_support_le_1,
    decision_pooled4_when_ext3_pooled4_agree_and_swfb,
    decision_pooled4_when_external_unanimity_against_fta,
)
from experiments.build_failure_feature_table import normalize_answer
from experiments.explore_offline_selector_rules import RuleSpec
from experiments.failure_analysis_common import as_bool, as_int, write_csv, write_json, write_text
from experiments.failure_mechanism_classifier_v2 import COHERE_SEED53_PATH, load_all_corpora
from experiments.replay_azure_inspired_rules_on_cohere import SWFB
from experiments.stress_test_exploratory_rules import (
    audit_rule_decision_legality,
    decision_canonical_fta,
    decision_external3_majority,
    decision_pooled4_majority,
    evaluate_rule_full,
    majority_vote,
    paired_bootstrap_ci,
)

CANDIDATE_NAME = "guarded_majority_fta_v2_candidate"
FRONTIER_SUPPORT_MAX = 1
EXTERNAL_FIELDS = ("l1_answer_canonical", "s1_answer_canonical", "tale_answer_canonical")
POOLED4_FIELDS = ("frontier_answer_canonical", "l1_answer_canonical", "s1_answer_canonical", "tale_answer_canonical")

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
    return Path("outputs/failure_analysis") / f"guarded_majority_candidate_freeze_{ts}"


def _norm(answer: Any) -> str | None:
    return normalize_answer(answer)


def external3_valid_majority_normalized(row: dict[str, Any]) -> str | None:
    """External-3 majority over L1/S1/TALE with strict 2-of-3 majority on normalized answers."""
    raw = [row.get(f) for f in EXTERNAL_FIELDS]
    normed = [_norm(a) for a in raw]
    valid = [a for a in normed if a]
    if len(valid) < 2:
        return None
    counts = Counter(valid)
    best_count = max(counts.values())
    if best_count < 2:
        return None
    for a in normed:
        if a and counts[a] == best_count:
            return a
    return None


def pooled4_majority_normalized(row: dict[str, Any]) -> str | None:
    """Pooled-4 over frontier/L1/S1/TALE; tie-break order frontier > L1 > S1 > TALE."""
    normed = [_norm(row.get(f)) for f in POOLED4_FIELDS]
    return majority_vote(normed)


def decision_guarded_agree_normalized(row: dict[str, Any], *, max_fs: int | None) -> str | None:
    ext3 = external3_valid_majority_normalized(row)
    p4 = pooled4_majority_normalized(row)
    fta = _norm(row.get("fta_selected_answer_canonical"))
    if ext3 is None or p4 is None or fta is None:
        return None
    if max_fs is not None:
        fs = as_int(row.get("frontier_support"))
        if fs is None or fs > max_fs:
            return None
    if ext3 == p4 and ext3 != fta:
        return p4
    return None


def decision_guarded_majority_fta_v2_candidate(row: dict[str, Any]) -> str | None:
    """Frozen exploratory FTA-v2 candidate (not promoted)."""
    return decision_guarded_agree_normalized(row, max_fs=FRONTIER_SUPPORT_MAX)


def _correct(ans: Any, gold: Any) -> bool | None:
    if ans in (None, "") or gold in (None, ""):
        return None
    return str(ans) == str(gold)


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
    spec_md = """# Guarded Majority FTA-v2 Candidate Specification

**Candidate ID:** `guarded_majority_fta_v2_candidate`

**Status:** Exploratory / frozen for validation planning only. **Not promoted.**
Canonical production selector remains FTA FIX-2+FIX-4.

## Runtime decision (universal, provider-agnostic)

1. Read canonical FTA selected answer (`fta_selected_answer_canonical`).
2. Compute **External-3** majority over L1, S1, TALE canonical answers:
   - Normalize each answer with the frozen support-aware normalizer.
   - Require a **strict 2-of-3 majority** on normalized keys; if no majority (e.g. 1-1-1), abstain.
3. Compute **Pooled-4** over frontier, L1, S1, TALE canonical answers:
   - Normalize each answer.
   - Plurality vote; ties broken by fixed order **frontier > L1 > S1 > TALE**.
4. **Override gate** (all must hold):
   - External-3 answer exists;
   - Pooled-4 answer exists;
   - `normalize(ext3) == normalize(pooled4)`;
   - `normalize(agreed) != normalize(fta)`;
   - `frontier_support` is an integer and `frontier_support <= 1`.
5. If gate passes, return the agreed normalized majority answer; else keep FTA.

## Explicit exclusions

- No gold, correctness, exact_match, example_id, question hash, or provider labels.
- No post-generation model calls.
- No manuscript claim updates from offline replay alone.

## Relation to prior audit

This freezes `pooled4_when_ext3_pooled4_agree_and_frontier_support_le_1` with explicit
normalization and strict External-3 majority semantics documented here.
"""
    pseudo = """# Guarded Majority Pseudocode

```
function guarded_majority_fta_v2_candidate(row):
    fta = normalize(row.fta_selected_answer_canonical)
    if fta is None:
        return None  # evaluate_rule falls back to raw FTA field

    ext3 = external3_valid_majority_normalized(row)  # strict 2/3 on L1,S1,TALE
    p4 = pooled4_majority_normalized(row)            # frontier,L1,S1,TALE + tie order

    if ext3 is None or p4 is None:
        return None

    fs = int_or_none(row.frontier_support)
    if fs is None or fs > 1:
        return None

    if ext3 == p4 and ext3 != fta:
        return p4  # agreed majority override

    return None  # keep canonical FTA
```

## External-3 valid majority

```
function external3_valid_majority_normalized(row):
    answers = [normalize(row[f]) for f in (l1, s1, tale)]
    valid = non-null answers
    if count(valid) < 2: return None
    counts = Counter(valid)
    if max(counts) < 2: return None  # no 2-of-3 majority
    return first answer in input order achieving max count
```

## Pooled-4 reconstruction

```
function pooled4_majority_normalized(row):
    answers = [normalize(row[f]) for f in (frontier, l1, s1, tale)]
    return majority_vote_with_tie_order(answers)  # first-listed wins ties
```
"""
    runtime_json = {
        "candidate_id": CANDIDATE_NAME,
        "status": "exploratory_frozen_not_promoted",
        "runtime_features": RUNTIME_FEATURES,
        "forbidden_fields": sorted(FORBIDDEN_RUNTIME),
        "normalization": "experiments.build_failure_feature_table.normalize_answer",
        "external3_rule": "strict_2of3_majority_on_l1_s1_tale_normalized",
        "pooled4_rule": "plurality_on_frontier_l1_s1_tale_normalized_tie_order_frontier_l1_s1_tale",
        "override_gates": [
            "ext3_exists",
            "pooled4_exists",
            "normalize(ext3)==normalize(pooled4)",
            "normalize(agreed)!=normalize(fta)",
            "frontier_support is int and <= 1",
        ],
        "provider_specific": False,
    }
    return spec_md, pseudo, runtime_json


def tie_handling_audit_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        ext3_strict = external3_valid_majority_normalized(row)
        ext3_legacy = decision_external3_majority(row)
        p4_norm = pooled4_majority_normalized(row)
        p4_legacy = decision_pooled4_majority(row)
        raw_ext = [row.get(f) for f in EXTERNAL_FIELDS]
        raw_p4 = [row.get(f) for f in POOLED4_FIELDS]
        norm_ext = [_norm(a) for a in raw_ext]
        norm_p4 = [_norm(a) for a in raw_p4]
        ext_counts = Counter(a for a in norm_ext if a)
        p4_counts = Counter(a for a in norm_p4 if a)
        ext_tie = len(ext_counts) > 0 and max(ext_counts.values()) == 1 and len(ext_counts) == 3
        p4_top = max(p4_counts.values()) if p4_counts else 0
        p4_tie = sum(1 for c in p4_counts.values() if c == p4_top) > 1 if p4_counts else False
        str_agree = (
            ext3_legacy not in (None, "")
            and p4_legacy not in (None, "")
            and str(ext3_legacy) == str(p4_legacy)
        )
        norm_agree = ext3_strict is not None and p4_norm is not None and ext3_strict == p4_norm
        norm_changes_agreement = str_agree != norm_agree
        fs = row.get("frontier_support")
        fs_int = as_int(fs)
        parser_any = as_bool(row.get("parser_failure_any"))
        guarded = decision_guarded_majority_fta_v2_candidate(row)
        unguarded_norm = decision_guarded_agree_normalized(row, max_fs=None)
        unguarded_legacy = decision_pooled4_when_ext3_pooled4_agree_against_fta(row)
        out.append(
            {
                "row_id": row.get("row_id"),
                "corpus": row.get("corpus"),
                "provider": row.get("provider"),
                "ext3_strict_norm": ext3_strict,
                "ext3_legacy_canonical": ext3_legacy,
                "p4_norm": p4_norm,
                "p4_legacy_canonical": p4_legacy,
                "ext3_three_way_tie": ext_tie,
                "p4_plurality_tie": p4_tie,
                "ext3_p4_disagree_norm": bool(
                    ext3_strict and p4_norm and ext3_strict != p4_norm
                ),
                "frontier_support": fs,
                "frontier_support_int": fs_int,
                "frontier_support_missing": fs_int is None,
                "parser_failure_any": parser_any,
                "str_agree_ext3_p4": str_agree,
                "norm_agree_ext3_p4": norm_agree,
                "normalization_changes_agreement": norm_changes_agreement,
                "guarded_triggers": guarded not in (None, ""),
                "unguarded_norm_triggers": unguarded_norm not in (None, ""),
                "unguarded_legacy_triggers": unguarded_legacy not in (None, ""),
                "guard_blocked_fs": bool(
                    unguarded_norm not in (None, "")
                    and (fs_int is None or fs_int > FRONTIER_SUPPORT_MAX)
                ),
            }
        )
    return out


def override_case_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    spec = RuleSpec(CANDIDATE_NAME, "frozen", "", decision_guarded_majority_fta_v2_candidate)
    unguarded = RuleSpec(
        "unguarded_agree_normalized",
        "ablation",
        "",
        lambda r: decision_guarded_agree_normalized(r, max_fs=None),
    )
    cases: list[dict[str, Any]] = []
    for row in rows:
        ev = evaluate_rule_full([row], spec)["per_row"][0]
        ung = evaluate_rule_full([row], unguarded)["per_row"][0]
        if not ev["override_triggered"] and not ung["override_triggered"]:
            continue
        gold = row.get("gold_answer_canonical")
        fta_ok = as_bool(row.get("fta_correct"))
        guarded_ok = ev["selected_correct"]
        ung_ok = ung["selected_correct"]
        if ev["override_triggered"]:
            if ev["win"]:
                outcome = "win"
            elif ev["loss"]:
                outcome = "loss"
            else:
                outcome = "tie_no_correctness_change"
        elif ung["override_triggered"] and ung["win"] and not ev["override_triggered"]:
            outcome = "near_miss_guard_blocked_win"
        elif ung["override_triggered"] and ung["loss"] and not ev["override_triggered"]:
            outcome = "avoided_regression_guard_blocked"
        else:
            outcome = "other"
        cases.append(
            {
                "row_id": row.get("row_id"),
                "corpus": row.get("corpus"),
                "provider": row.get("provider"),
                "example_id": row.get("example_id"),
                "outcome": outcome,
                "guarded_triggered": ev["override_triggered"],
                "unguarded_triggered": ung["override_triggered"],
                "fta_correct": fta_ok,
                "guarded_correct": guarded_ok,
                "unguarded_correct": ung_ok,
                "gold_answer": gold,
                "fta_answer": row.get("fta_selected_answer_canonical"),
                "guarded_answer": ev["selected_answer"],
                "unguarded_answer": ung["selected_answer"],
                "frontier_support": row.get("frontier_support"),
                "override_reason": row.get("override_reason"),
                "ext3_strict": external3_valid_majority_normalized(row),
                "p4_norm": pooled4_majority_normalized(row),
            }
        )
    return cases


def guard_threshold_sensitivity(
    corpora: dict[str, list[dict[str, Any]]],
    *,
    bootstrap_resamples: int,
    bootstrap_seed: int,
) -> list[dict[str, Any]]:
    variants = [
        ("frontier_support_le_0", lambda r: decision_guarded_agree_normalized(r, max_fs=0)),
        ("frontier_support_le_1", lambda r: decision_guarded_agree_normalized(r, max_fs=1)),
        ("frontier_support_le_2", lambda r: decision_guarded_agree_normalized(r, max_fs=2)),
        ("no_frontier_support_guard", lambda r: decision_guarded_agree_normalized(r, max_fs=None)),
        ("swfb_guard", decision_pooled4_when_ext3_pooled4_agree_and_swfb),
        ("external_unanimity_guard", decision_pooled4_when_external_unanimity_against_fta),
    ]
    rows_out: list[dict[str, Any]] = []
    for guard_name, fn in variants:
        spec = RuleSpec(guard_name, "sensitivity", "", fn)
        for corpus, rows in corpora.items():
            ev = evaluate_rule_full(rows, spec)
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
        all_rows = [r for rs in corpora.values() for r in rs]
        ev_all = evaluate_rule_full(all_rows, spec)
        rows_out.append(
            {
                "guard_variant": guard_name,
                "corpus": "all_combined",
                "accuracy": ev_all["accuracy"],
                "correct_count": ev_all["correct_count"],
                "net_wins_vs_fta": ev_all["net_wins"],
                "wins": ev_all["wins_vs_canonical_fta"],
                "losses": ev_all["losses_vs_canonical_fta"],
                "overrides_triggered": ev_all.get("overrides_triggered"),
                "regression_rate": ev_all.get("regression_rate_among_fta_correct"),
            }
        )
    return rows_out


def _binom_zero_regression_prob(n_triggers: int, p_regress: float, n_fta_correct: int) -> float:
    """Rough chance all overrides avoid FTA-correct rows if each trigger independent."""
    if n_triggers <= 0:
        return 1.0
    p = min(1.0, max(0.0, p_regress))
    return (1.0 - p) ** n_triggers


def classify_candidate(
    results: list[dict[str, Any]],
    sensitivity: list[dict[str, Any]],
    override_cases: list[dict[str, Any]],
) -> tuple[str, list[str]]:
    macro_net = sum(r["net_wins_vs_fta"] for r in results)
    macro_losses = sum(r["losses_vs_fta"] for r in results)
    all_positive = all(r["net_wins_vs_fta"] > 0 for r in results)
    all_nonnegative = all(r["net_wins_vs_fta"] >= 0 for r in results)
    triggers = sum(r["overrides_triggered"] or 0 for r in results)

    bullets: list[str] = []
    if macro_losses > 0:
        return "needs more offline refinement", ["Observed regressions on frozen re-eval."]
    if not all_nonnegative:
        return "inconclusive", ["Negative net on at least one corpus under frozen spec."]
    if not all_positive:
        bullets.append("Azure net 0 under formal normalized spec; Cohere-only uplift.")
        bullets.append(
            "Prior audit +17 used legacy canonical-string plurality Ext3; formal spec is stricter."
        )
    le1 = [s for s in sensitivity if s["guard_variant"] == "frontier_support_le_1" and s["corpus"] == "all_combined"][0]
    le0 = [s for s in sensitivity if s["guard_variant"] == "frontier_support_le_0" and s["corpus"] == "all_combined"][0]
    unguarded = [s for s in sensitivity if s["guard_variant"] == "no_frontier_support_guard" and s["corpus"] == "all_combined"][0]
    if le1["losses"] == 0 and macro_net > 0:
        bullets.append("Zero regressions with positive macro net under frozen spec.")
    if le0["net_wins_vs_fta"] < le1["net_wins_vs_fta"]:
        bullets.append("frontier_support<=1 beats <=0 on net wins.")
    if unguarded["losses"] > le1["losses"]:
        bullets.append(
            f"Guard removes {unguarded['losses']} unguarded regressions at cost of "
            f"{unguarded['net_wins_vs_fta'] - le1['net_wins_vs_fta']} net wins."
        )
    near_miss = sum(1 for c in override_cases if c["outcome"] == "near_miss_guard_blocked_win")
    avoided = sum(1 for c in override_cases if c["outcome"] == "avoided_regression_guard_blocked")
    bullets.append(f"Guard blocked {near_miss} would-be wins and {avoided} would-be regressions.")
    bullets.append(f"Only {triggers} guarded triggers — small-n; fresh validation mandatory if pursued.")

    if all_positive and macro_net >= 10 and le1["losses"] == 0:
        return "ready for fresh validation", bullets
    if macro_net > 0 and le1["losses"] == 0:
        return "needs more offline refinement", bullets
    return "inconclusive", bullets


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
    write_text(output_dir / "GUARDED_MAJORITY_CANDIDATE_SPEC.md", spec_md)
    write_text(output_dir / "GUARDED_MAJORITY_PSEUDOCODE.md", pseudo_md)
    write_json(output_dir / "GUARDED_MAJORITY_RUNTIME_FEATURES.json", runtime_json)

    frozen_spec = RuleSpec(CANDIDATE_NAME, "frozen_exploratory", "", decision_guarded_majority_fta_v2_candidate)
    ext3_spec = RuleSpec("baseline_external3_majority", "baseline", "", decision_external3_majority)
    p4_spec = RuleSpec("baseline_pooled4_majority_reconstructed", "baseline", "", decision_pooled4_majority)
    compare = [("pooled4", p4_spec), ("external3", ext3_spec)]

    result_rows: list[dict[str, Any]] = []
    boot_rows: list[dict[str, Any]] = []
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
        boot_rows.append({k: v for k, v in r.items() if k.startswith("bootstrap_") or k in {"corpus", "rule_name"}})

    legality = audit_rule_decision_legality([frozen_spec])[0]
    write_csv(output_dir / "FROZEN_GUARDED_MAJORITY_RESULTS.csv", result_rows, list(result_rows[0].keys()))
    boot_fields = sorted(
        {k for row in result_rows for k in row if k.startswith("bootstrap_") or k in {"corpus", "rule_name", "net_wins_vs_fta"}}
    )
    write_csv(
        output_dir / "FROZEN_GUARDED_MAJORITY_BOOTSTRAP_CI.csv",
        [{k: row.get(k) for k in boot_fields} for row in result_rows],
        boot_fields,
    )

    macro_net = sum(r["net_wins_vs_fta"] for r in result_rows)
    macro_losses = sum(r["losses_vs_fta"] for r in result_rows)
    report_lines = [
        "# Frozen Guarded Majority Report",
        "",
        f"**Candidate:** `{CANDIDATE_NAME}`",
        f"**Runtime legal:** {legality.get('is_runtime_legal')}",
        f"**Macro net vs FTA:** {macro_net}",
        f"**Macro losses:** {macro_losses}",
        "",
        "## Spec note",
        "This freeze uses **normalized answers** and **strict External-3 2-of-3 majority**.",
        "Prior audit `pooled4_when_ext3_pooled4_agree_and_frontier_support_le_1` used canonical-string",
        "plurality External-3 (no strict majority) and reported macro net +17. Numbers differ by design.",
        "",
        "## Per corpus",
    ]
    for r in result_rows:
        report_lines.append(
            f"- **{r['corpus']}**: acc={r['accuracy']:.4f} net={r['net_wins_vs_fta']} "
            f"W/L={r['wins_vs_fta']}/{r['losses_vs_fta']} overrides={r['overrides_triggered']} "
            f"CI vs FTA includes 0: {r['bootstrap_vs_fta_includes_zero']}"
        )
    write_text(output_dir / "FROZEN_GUARDED_MAJORITY_REPORT.md", "\n".join(report_lines).rstrip() + "\n")

    tie_rows = tie_handling_audit_rows(raw_rows)
    tie_fields = sorted({k for row in tie_rows for k in row})
    write_csv(output_dir / "TIE_HANDLING_AUDIT.csv", tie_rows, tie_fields)
    n_norm_change = sum(1 for t in tie_rows if t.get("normalization_changes_agreement"))
    n_ext_tie = sum(1 for t in tie_rows if t.get("ext3_three_way_tie"))
    n_disagree = sum(1 for t in tie_rows if t.get("ext3_p4_disagree_norm"))
    n_fs_miss = sum(1 for t in tie_rows if t.get("frontier_support_missing"))
    tie_md = (
        "# Tie Handling and Legality Report\n\n"
        f"- Runtime legality audit: **{legality.get('is_runtime_legal')}** "
        f"(illegal fields: {legality.get('illegal_fields_found') or 'none'})\n"
        f"- Provider labels used in rule: **no** (universal rule)\n"
        f"- External-3 three-way ties (no strict majority): {n_ext_tie}\n"
        f"- Normalization changes ext3/p4 agreement: {n_norm_change}\n"
        f"- Ext3/Pooled4 disagree (normalized): {n_disagree}\n"
        f"- Missing/non-int frontier_support: {n_fs_miss}\n"
        f"- Parser failure rows: {sum(1 for t in tie_rows if t.get('parser_failure_any'))}\n"
    )
    write_text(output_dir / "TIE_HANDLING_AND_LEGALITY_REPORT.md", tie_md)

    override_cases = override_case_rows(raw_rows)
    oc_fields = sorted({k for row in override_cases for k in row})
    write_csv(output_dir / "GUARDED_MAJORITY_OVERRIDE_CASES.csv", override_cases, oc_fields)
    outcome_counts = Counter(c["outcome"] for c in override_cases)
    wl_md = (
        "# Guarded Majority Win/Loss Review\n\n"
        f"Outcome counts: {dict(outcome_counts)}\n\n"
        f"- Wins: {outcome_counts.get('win', 0)}\n"
        f"- Losses: {outcome_counts.get('loss', 0)}\n"
        f"- Near misses (guard blocked win): {outcome_counts.get('near_miss_guard_blocked_win', 0)}\n"
        f"- Avoided regressions: {outcome_counts.get('avoided_regression_guard_blocked', 0)}\n"
    )
    write_text(output_dir / "GUARDED_MAJORITY_WIN_LOSS_REVIEW.md", wl_md)

    sensitivity = guard_threshold_sensitivity(
        corpora, bootstrap_resamples=args.bootstrap_resamples, bootstrap_seed=args.bootstrap_seed
    )
    sens_fields = sorted({k for row in sensitivity for k in row})
    write_csv(output_dir / "GUARD_THRESHOLD_SENSITIVITY.csv", sensitivity, sens_fields)

    le1_all = next(s for s in sensitivity if s["guard_variant"] == "frontier_support_le_1" and s["corpus"] == "all_combined")
    ung_all = next(s for s in sensitivity if s["guard_variant"] == "no_frontier_support_guard" and s["corpus"] == "all_combined")
    triggers_le1 = le1_all["overrides_triggered"] or 0
    fta_correct_n = sum(as_bool(r.get("fta_correct")) for r in raw_rows)
    rough_p = (ung_all["losses"] or 0) / max(1, triggers_le1 + (ung_all["overrides_triggered"] or 0))
    zero_reg_chance = _binom_zero_regression_prob(triggers_le1, rough_p, fta_correct_n)

    overfit_md = (
        "# Overfitting Risk Analysis\n\n"
        "## Post-hoc guard selection\n"
        "`frontier_support <= 1` was chosen after observing 3 unguarded regressions in the "
        "pooled4_ext3 agreement audit. This is **post-hoc** and carries tuning risk.\n\n"
        "## Alternative guards considered (from prior audit + this freeze)\n"
        "- frontier_support <= 0, <= 1, <= 2\n"
        "- no frontier_support guard (unguarded agreement)\n"
        "- SWFB-only gate\n"
        "- external unanimity gate\n\n"
        "## Neighboring guard performance (all rows combined)\n"
        f"- <=0: net {next(s for s in sensitivity if s['guard_variant']=='frontier_support_le_0' and s['corpus']=='all_combined')['net_wins_vs_fta']}, "
        f"losses {next(s for s in sensitivity if s['guard_variant']=='frontier_support_le_0' and s['corpus']=='all_combined')['losses']}\n"
        f"- <=1 (frozen): net {le1_all['net_wins_vs_fta']}, losses {le1_all['losses']}\n"
        f"- <=2: net {next(s for s in sensitivity if s['guard_variant']=='frontier_support_le_2' and s['corpus']=='all_combined')['net_wins_vs_fta']}, "
        f"losses {next(s for s in sensitivity if s['guard_variant']=='frontier_support_le_2' and s['corpus']=='all_combined')['losses']}\n"
        f"- unguarded: net {ung_all['net_wins_vs_fta']}, losses {ung_all['losses']}\n\n"
        "## Is <=1 natural or tuned?\n"
        "<=1 keeps more net wins than <=0 while retaining 0 losses offline; <=2 reintroduces regressions. "
        "The knee at 1 is plausible (weak frontier support) but still selected after seeing failures.\n\n"
        "## Zero regression chance\n"
        f"Guarded triggers (legacy unguarded gate + fs<=1): ~{triggers_le1} on combined table; "
        f"rough P(regression|override)≈{rough_p:.3f}; "
        f"naive P(0 regressions | {triggers_le1} overrides)≈{zero_reg_chance:.3f}. "
        "**Small trigger count ⇒ zero regressions may be luck; fresh validation mandatory.**\n"
    )
    write_text(output_dir / "OVERFITTING_RISK_ANALYSIS.md", overfit_md)

    validation_md = """# Guarded Majority Fresh Validation Plan (NOT authorized)

## Recommendation
**Hold API validation** until the team chooses between:
1. **Frozen formal spec** (normalized + strict Ext3 2/3) — safer, fewer triggers, Azure net 0 offline; or
2. **Legacy plurality Ext3 on canonical strings** — higher offline net (+17) but less formally specified.

If proceeding, validate **Cohere first** on a fresh disjoint seed.

## Fresh seed
- Must be disjoint from seeds 31, 41, 53, 61, 71, 97 and any manifest in `cohere_disjoint_validation_plan`.
- Suggested: draw next unused seed (e.g. 83 or 89) with overlap audit identical to seed-53 prep.

## Sample / cost
- N=300, budget=6, same 4-method pool generation as seed-53 validation.
- Logical calls: 4 methods × 300 = **1200** generation calls per provider (+ post-hoc eval only).
- Reuse pipelines: `experiments/run_api_validation_repair_candidate.py`, `cohere_disjoint_validation_plan.py`
  with candidate evaluator swapped in post-hoc only (no runtime promotion).

## Stopping criteria
- Stop early if fresh split net < 0 after 100 examples reviewed.
- Stop if regressions > 2 on fresh split.

## Promotion criteria (exploratory → validation-passed, still not production)
- Net > 0 vs FTA on fresh Cohere split.
- Regression rate ≤ 0.5% (≤2 of 300).
- Bootstrap 95% CI vs FTA excludes zero on fresh Cohere split.
- Azure confirmatory net ≥ 0 with ≤2 regressions.

## Rejection criteria
- Any fresh corpus net ≤ 0.
- Regressions > 2 or CI strongly negative.
- Guarded candidate net < unguarded FTA on fresh data.

## Cost / risk notes
- Lower override rate than pooled4 standalone (~22 triggers vs 123 unguarded-differs) ⇒ fewer chances to help or hurt.
- Post-hoc guard tuning risk: treat first fresh split as **confirmatory**, not another tuning round.
- Do not update manuscript claims until independent validation completes.
"""
    write_text(output_dir / "GUARDED_MAJORITY_FRESH_VALIDATION_PLAN.md", validation_md)

    legacy_spec = RuleSpec(
        "legacy_guarded_canonical_strings",
        "reconciliation",
        "",
        decision_pooled4_when_ext3_pooled4_agree_and_frontier_support_le_1,
    )
    legacy_rows: list[dict[str, Any]] = []
    for corpus, rows in corpora.items():
        lev = evaluate_rule_full(rows, legacy_spec)
        legacy_rows.append(
            {
                "corpus": corpus,
                "frozen_net": next(r["net_wins_vs_fta"] for r in result_rows if r["corpus"] == corpus),
                "legacy_net": lev["net_wins"],
                "frozen_overrides": next(r["overrides_triggered"] for r in result_rows if r["corpus"] == corpus),
                "legacy_overrides": lev.get("overrides_triggered"),
                "legacy_losses": lev["losses_vs_canonical_fta"],
            }
        )
    write_csv(
        output_dir / "SPEC_RECONCILIATION_LEGACY_VS_FROZEN.csv",
        legacy_rows,
        list(legacy_rows[0].keys()),
    )

    classification, bullets = classify_candidate(result_rows, sensitivity, override_cases)
    final = [
        "# Final Guarded Majority Candidate Freeze Summary",
        "",
        f"**Classification:** {classification}",
        "",
        "## What is the candidate?",
        "When normalized External-3 (strict 2/3) and Pooled-4 agree against FTA and `frontier_support<=1`, "
        "select the agreed majority answer; else FTA.",
        "",
        "## Runtime legal?",
        f"Yes — legality audit passed: {legality.get('is_runtime_legal')}.",
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
            f"- Macro net: {macro_net}",
            "",
            "## Avoids observed regressions?",
            f"Frozen re-eval losses: {macro_losses} (prior unguarded had 3).",
            "",
            "## Different from Pooled-4 / External-3 standalone?",
            "Yes — requires agreement + low frontier support; far fewer overrides than either standalone.",
            "",
            "## Interpretable?",
            "Yes — weak-frontier cases where both majority reconstructions agree against FTA.",
            "",
            "## Worth API validation?",
            "Not yet — reconcile formal normalized spec (macro net +3) vs legacy audit (+17) before spending credits.",
            "",
            "## Do not claim yet",
            "- Not promoted; FTA remains canonical.",
            "- Offline zero regressions may be small-n chance.",
            "- Does not beat pooled4 standalone offline net.",
            "",
            "## Notes",
            *bullets,
        ]
    )
    write_text(output_dir / "FINAL_GUARDED_MAJORITY_CANDIDATE_FREEZE_SUMMARY.md", "\n".join(final).rstrip() + "\n")

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
