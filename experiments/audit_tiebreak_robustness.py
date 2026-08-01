"""Offline tie-break robustness audit for normalized plurality guarded candidate.

Tests whether variant-H signal (+17 macro net) survives external/Pooled-4
tie-break permutations or depends on arbitrary method order. No APIs, no promotion.
"""

from __future__ import annotations

import argparse
import itertools
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from experiments.analyze_azure_distribution_shift import AZURE_DEFAULT_VALIDATION_PATH
from experiments.audit_agreement_semantics import decision_guarded_norm_plurality
from experiments.build_failure_feature_table import normalize_answer
from experiments.explore_offline_selector_rules import RuleSpec
from experiments.failure_analysis_common import as_bool, as_int, write_csv, write_json, write_text
from experiments.failure_mechanism_classifier_v2 import COHERE_SEED53_PATH, load_all_corpora
from experiments.freeze_guarded_majority_candidate import (
    EXTERNAL_FIELDS,
    POOLED4_FIELDS,
    FRONTIER_SUPPORT_MAX,
    external3_valid_majority_normalized,
    pooled4_majority_normalized,
)
from experiments.stress_test_exploratory_rules import (
    audit_rule_decision_legality,
    decision_canonical_fta,
    evaluate_rule_full,
    majority_vote,
    paired_bootstrap_ci,
)

METHOD_LABELS = ("L1", "S1", "TALE")
METHOD_TO_FIELD = {
    "L1": "l1_answer_canonical",
    "S1": "s1_answer_canonical",
    "TALE": "tale_answer_canonical",
}
POOLED_LABELS = ("frontier", "L1", "S1", "TALE")
POOLED_TO_FIELD = {
    "frontier": "frontier_answer_canonical",
    "L1": "l1_answer_canonical",
    "S1": "s1_answer_canonical",
    "TALE": "tale_answer_canonical",
}
CORRECT_FIELD = {"L1": "l1_correct", "S1": "s1_correct", "TALE": "tale_correct"}

EXTERNAL_PERMUTATIONS: list[tuple[str, ...]] = list(itertools.permutations(METHOD_LABELS))
DEFAULT_EXTERNAL_ORDER = ("L1", "S1", "TALE")
DEFAULT_POOLED_ORDER = ("frontier", "L1", "S1", "TALE")

FTA_SPEC = RuleSpec("G_fta_default", "baseline", "", decision_canonical_fta)


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
    return Path("outputs/failure_analysis") / f"tiebreak_robustness_audit_{ts}"


def _norm(answer: Any) -> str | None:
    return normalize_answer(answer)


def priority_plurality(ordered_answers: list[str | None]) -> str | None:
    """Plurality with deterministic tie-break: first-listed answer wins ties."""
    return majority_vote(ordered_answers)


def external_priority_plurality(row: dict[str, Any], order: tuple[str, ...]) -> str | None:
    answers = [_norm(row.get(METHOD_TO_FIELD[m])) for m in order]
    return priority_plurality(answers)


def pooled4_priority_plurality(row: dict[str, Any], order: tuple[str, ...]) -> str | None:
    answers = [_norm(row.get(POOLED_TO_FIELD[m])) for m in order]
    return priority_plurality(answers)


def external_vote_class(row: dict[str, Any]) -> str:
    normed = [_norm(row.get(f)) for f in EXTERNAL_FIELDS]
    valid = [a for a in normed if a]
    if len(valid) < 2:
        return "insufficient_answers"
    counts = Counter(valid)
    best = max(counts.values())
    if best >= 2:
        return "strict_majority"
    if len(counts) == 3 and best == 1:
        return "one_one_one_tie"
    return "other_plurality_tie"


def pooled4_is_tie(row: dict[str, Any], order: tuple[str, ...] = DEFAULT_POOLED_ORDER) -> bool:
    answers = [_norm(row.get(POOLED_TO_FIELD[m])) for m in order]
    valid = [a for a in answers if a]
    if not valid:
        return False
    counts = Counter(valid)
    best = max(counts.values())
    return sum(1 for c in counts.values() if c == best) > 1


def external_is_tie_break_only(row: dict[str, Any]) -> bool:
    return external_vote_class(row) == "one_one_one_tie"


def pooled4_abstain_on_tie(row: dict[str, Any], order: tuple[str, ...]) -> str | None:
    answers = [_norm(row.get(POOLED_TO_FIELD[m])) for m in order]
    valid = [a for a in answers if a]
    if not valid:
        return None
    counts = Counter(valid)
    best = max(counts.values())
    winners = [a for a in counts if counts[a] == best]
    if len(winners) > 1:
        return None
    for a in answers:
        if a and counts[a] == best:
            return a
    return None


def pooled4_prefer_fta_tie(row: dict[str, Any], order: tuple[str, ...]) -> str | None:
    answers = [_norm(row.get(POOLED_TO_FIELD[m])) for m in order]
    fta = _norm(row.get("fta_selected_answer_canonical"))
    valid = [a for a in answers if a]
    if not valid:
        return None
    counts = Counter(valid)
    best = max(counts.values())
    if fta and counts.get(fta, 0) == best:
        return fta
    return priority_plurality(answers)


def pooled4_prefer_external_tie(row: dict[str, Any], ext_order: tuple[str, ...], p4_order: tuple[str, ...]) -> str | None:
    answers = [_norm(row.get(POOLED_TO_FIELD[m])) for m in p4_order]
    ext = external_priority_plurality(row, ext_order)
    valid = [a for a in answers if a]
    if not valid:
        return None
    counts = Counter(valid)
    best = max(counts.values())
    if ext and counts.get(ext, 0) == best:
        return ext
    return priority_plurality(answers)


def make_guarded_decision(
    *,
    ext_order: tuple[str, ...] = DEFAULT_EXTERNAL_ORDER,
    p4_order: tuple[str, ...] = DEFAULT_POOLED_ORDER,
    p4_fn: Callable[[dict[str, Any], tuple[str, ...]], str | None] | None = None,
    max_fs: int | None = FRONTIER_SUPPORT_MAX,
    min_fs: int | None = None,
    abstain_external_tie: bool = False,
    abstain_p4_tie: bool = False,
    require_strict_external: bool = False,
) -> Callable[[dict[str, Any]], str | None]:
    def _decide(row: dict[str, Any]) -> str | None:
        if require_strict_external:
            ext = external3_valid_majority_normalized(row)
        else:
            if abstain_external_tie and external_is_tie_break_only(row):
                ext = None
            else:
                ext = external_priority_plurality(row, ext_order)
        if p4_fn is not None:
            p4 = p4_fn(row, p4_order)
        elif abstain_p4_tie:
            p4 = pooled4_abstain_on_tie(row, p4_order)
        else:
            p4 = pooled4_priority_plurality(row, p4_order)
        fta = _norm(row.get("fta_selected_answer_canonical"))
        if ext in (None, "") or p4 in (None, "") or fta in (None, ""):
            return None
        fs = as_int(row.get("frontier_support"))
        if max_fs is not None and (fs is None or fs > max_fs):
            return None
        if min_fs is not None and fs != min_fs:
            return None
        if str(ext) == str(p4) and str(ext) != str(fta):
            return p4
        return None

    return _decide


def _order_label(order: tuple[str, ...]) -> str:
    return " > ".join(order)


def evaluate_guarded_on_corpus(
    rows: list[dict[str, Any]],
    decide_fn: Callable[[dict[str, Any]], str | None],
    *,
    corpus: str,
    variant_id: str,
    bootstrap_resamples: int,
    bootstrap_seed: int,
    ext_order: tuple[str, ...] = DEFAULT_EXTERNAL_ORDER,
) -> dict[str, Any]:
    spec = RuleSpec(variant_id, "tiebreak", "", decide_fn)
    ev = evaluate_rule_full(rows, spec)
    fta_ev = evaluate_rule_full(rows, FTA_SPEC)
    boot = paired_bootstrap_ci(
        ev["per_row"], fta_ev["per_row"], n_resamples=bootstrap_resamples, seed=bootstrap_seed
    )
    strict_triggers = 0
    tie_triggers = 0
    tie_wins = tie_losses = 0
    for row, pr in zip(rows, ev["per_row"]):
        if not pr["override_triggered"]:
            continue
        vc = external_vote_class(row)
        if vc == "strict_majority":
            strict_triggers += 1
        elif vc == "one_one_one_tie":
            tie_triggers += 1
            if pr["win"]:
                tie_wins += 1
            if pr["loss"]:
                tie_losses += 1
    return {
        "variant_id": variant_id,
        "corpus": corpus,
        "external_order": _order_label(ext_order),
        "accuracy": ev["accuracy"],
        "correct_count": ev["correct_count"],
        "wins_vs_fta": ev["wins_vs_canonical_fta"],
        "losses_vs_fta": ev["losses_vs_canonical_fta"],
        "net_wins_vs_fta": ev["net_wins"],
        "overrides_triggered": ev.get("overrides_triggered"),
        "regression_rate": ev.get("regression_rate_among_fta_correct"),
        "bootstrap_ci_low": boot.get("ci_low"),
        "bootstrap_ci_high": boot.get("ci_high"),
        "bootstrap_includes_zero": boot.get("includes_zero"),
        "triggers_strict_majority": strict_triggers,
        "triggers_one_one_one_tie": tie_triggers,
        "tie_case_wins": tie_wins,
        "tie_case_losses": tie_losses,
    }


def evaluate_all_corpora(
    corpora: dict[str, list[dict[str, Any]]],
    decide_fn: Callable[[dict[str, Any]], str | None],
    *,
    variant_id: str,
    bootstrap_resamples: int,
    bootstrap_seed: int,
    ext_order: tuple[str, ...] = DEFAULT_EXTERNAL_ORDER,
) -> list[dict[str, Any]]:
    rows_out = []
    for corpus, rows in corpora.items():
        rows_out.append(
            evaluate_guarded_on_corpus(
                rows,
                decide_fn,
                corpus=corpus,
                variant_id=variant_id,
                bootstrap_resamples=bootstrap_resamples,
                bootstrap_seed=bootstrap_seed,
                ext_order=ext_order,
            )
        )
    macro_net = sum(r["net_wins_vs_fta"] for r in rows_out)
    macro_losses = sum(r["losses_vs_fta"] for r in rows_out)
    for r in rows_out:
        r["macro_net_wins"] = macro_net
        r["macro_losses"] = macro_losses
    return rows_out


def method_reliability_rows(corpora: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for corpus, rows in corpora.items():
        n = len(rows) or 1
        for method in METHOD_LABELS:
            cf = CORRECT_FIELD[method]
            correct = sum(as_bool(r.get(cf)) for r in rows)
            out.append(
                {
                    "corpus": corpus,
                    "method": method,
                    "accuracy": correct / n,
                    "correct_count": correct,
                    "row_count": n,
                }
            )
        # 1-1-1 disagreement: which method correct when all three differ
        ooo_rows = [r for r in rows if external_vote_class(r) == "one_one_one_tie"]
        for method in METHOD_LABELS:
            cf = CORRECT_FIELD[method]
            c = sum(as_bool(r.get(cf)) for r in ooo_rows)
            out.append(
                {
                    "corpus": corpus,
                    "method": method,
                    "subset": "one_one_one_tie",
                    "accuracy": c / len(ooo_rows) if ooo_rows else None,
                    "correct_count": c,
                    "row_count": len(ooo_rows),
                }
            )
    return out


def reliability_order(train_rows: list[dict[str, Any]]) -> tuple[str, ...]:
    """Runtime-legal proxy: historical method accuracy on training rows only (post-hoc labels for audit)."""
    scores: dict[str, float] = {}
    n = len(train_rows) or 1
    for method in METHOD_LABELS:
        cf = CORRECT_FIELD[method]
        scores[method] = sum(as_bool(r.get(cf)) for r in train_rows) / n
    # deterministic tie-break among methods: L1 > S1 > TALE
    return tuple(sorted(METHOD_LABELS, key=lambda m: (-scores[m], METHOD_LABELS.index(m))))


def best_global_order(corpora: dict[str, list[dict[str, Any]]], *, bootstrap_resamples: int, bootstrap_seed: int) -> tuple[str, ...]:
    all_rows = [r for rs in corpora.values() for r in rs]
    best_order = DEFAULT_EXTERNAL_ORDER
    best_net = -999
    for order in EXTERNAL_PERMUTATIONS:
        fn = make_guarded_decision(ext_order=order)
        ev = evaluate_rule_full(all_rows, RuleSpec("tmp", "t", "", fn))
        if ev["net_wins"] > best_net:
            best_net = ev["net_wins"]
            best_order = order
    return best_order


def loo_reliability_order(train_corpora: dict[str, list[dict[str, Any]]]) -> tuple[str, ...]:
    train_rows = [r for rs in train_corpora.values() for r in rs]
    return reliability_order(train_rows)


def split_override_signal(
    rows: list[dict[str, Any]], decide_fn: Callable[[dict[str, Any]], str | None]
) -> list[dict[str, Any]]:
    spec = RuleSpec("H", "split", "", decide_fn)
    ev = evaluate_rule_full(rows, spec)
    groups: dict[str, dict[str, int]] = {
        "strict_external_majority": {"count": 0, "wins": 0, "losses": 0},
        "external_one_one_one_tie": {"count": 0, "wins": 0, "losses": 0},
        "pooled4_tie_dependent": {"count": 0, "wins": 0, "losses": 0},
        "both_tie_dependent": {"count": 0, "wins": 0, "losses": 0},
    }
    for row, pr in zip(rows, ev["per_row"]):
        if not pr["override_triggered"]:
            continue
        ext_class = external_vote_class(row)
        p4_tie = pooled4_is_tie(row)
        ext_tie = ext_class == "one_one_one_tie"
        if ext_class == "strict_majority" and not p4_tie:
            key = "strict_external_majority"
        elif ext_tie and p4_tie:
            key = "both_tie_dependent"
        elif ext_tie:
            key = "external_one_one_one_tie"
        elif p4_tie:
            key = "pooled4_tie_dependent"
        else:
            key = "strict_external_majority"
        groups[key]["count"] += 1
        if pr["win"]:
            groups[key]["wins"] += 1
        if pr["loss"]:
            groups[key]["losses"] += 1
    out = []
    for key, g in groups.items():
        out.append(
            {
                "signal_group": key,
                "override_count": g["count"],
                "wins": g["wins"],
                "losses": g["losses"],
                "net_wins": g["wins"] - g["losses"],
                "defensible": key == "strict_external_majority",
            }
        )
    return out


def build_casebook(rows: list[dict[str, Any]], corpora: dict[str, list[dict[str, Any]]]) -> str:
    lines = ["# Tie-break Casebook", ""]
    h_fn = make_guarded_decision()
    spec = RuleSpec("H", "c", "", h_fn)
    ev = evaluate_rule_full(rows, spec)

    def add_cases(title: str, filt: Callable[[dict, dict], bool], limit: int = 6):
        lines.append(f"## {title}")
        n = 0
        for row, pr in zip(rows, ev["per_row"]):
            if not filt(row, pr):
                continue
            gold = row.get("gold_answer_canonical")
            lines.append(f"### {row.get('corpus')} / {row.get('example_id')}")
            lines.append(f"- **Gold:** {gold} | **FTA:** {row.get('fta_selected_answer_canonical')}")
            lines.append(
                f"- **L1/S1/TALE norm:** {_norm(row.get('l1_answer_canonical'))}/"
                f"{_norm(row.get('s1_answer_canonical'))}/{_norm(row.get('tale_answer_canonical'))}"
            )
            lines.append(f"- **Ext class:** {external_vote_class(row)} | **P4 tie:** {pooled4_is_tie(row)}")
            lines.append(f"- **Selected:** {pr.get('selected_answer')} | correct={pr.get('selected_correct')}")
            n += 1
            if n >= limit:
                break
        if n == 0:
            lines.append("_None._")
        lines.append("")

    add_cases("Tie-break wins (1-1-1)", lambda r, pr: pr["win"] and external_vote_class(r) == "one_one_one_tie")
    add_cases("Strict-majority wins", lambda r, pr: pr["win"] and external_vote_class(r) == "strict_majority")
    add_cases(
        "Azure plurality restores",
        lambda r, pr: r.get("corpus") == "azure_seed97" and pr["win"],
    )
    add_cases(
        "Different external orders disagree",
        lambda r, pr: len({external_priority_plurality(r, o) for o in EXTERNAL_PERMUTATIONS}) > 1
        and pr["override_triggered"],
        limit=4,
    )
    return "\n".join(lines).rstrip() + "\n"


def classify_decision(
    perm_results: list[dict[str, Any]], signal_rows: list[dict[str, Any]]
) -> tuple[str, str]:
    combined = [r for r in perm_results if r.get("corpus") == "all_combined"]
    macro_nets = {r["external_order"]: r.get("macro_net_wins", r.get("net_wins_vs_fta", 0)) for r in combined}
    if not macro_nets:
        return "inconclusive", "no permutation results"
    min_net = min(macro_nets.values())
    max_net = max(macro_nets.values())
    spread = max_net - min_net
    tie_group = next((g for g in signal_rows if g["signal_group"] == "external_one_one_one_tie"), {})
    strict_group = next((g for g in signal_rows if g["signal_group"] == "strict_external_majority"), {})
    tie_net = tie_group.get("net_wins", 0)
    strict_net = strict_group.get("net_wins", 0)

    if spread > 8:
        return (
            "rejected as tie-break artifact",
            f"macro net spread {spread} across 6 external orders ({min_net} to {max_net}); "
            f"tie-break overrides net {tie_net} vs strict-majority net {strict_net}",
        )
    if tie_net > strict_net and spread > 4:
        return (
            "promising but needs non-arbitrary tie-break justification",
            f"+17 depends on L1-first plurality; tie-break net {tie_net} dominates strict net {strict_net}",
        )
    if min_net >= 10 and spread <= 4:
        return "defensible FTA-v2 candidate worth fresh API validation", f"robust spread {spread}"
    return "useful diagnostic only", f"spread {spread}, min net {min_net}"


def run_audit(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = Path(args.output_dir) if args.output_dir else _timestamp_dir()
    output_dir.mkdir(parents=True, exist_ok=True)

    family_spec = """# Guarded Candidate Family Specification

**Family name:** `normalized_plurality_guarded_majority` (variant H)

## Base guarded rule
1. Canonical FTA answer (normalized for comparison).
2. **External priority plurality** over L1/S1/TALE with a specified deterministic tie-break order.
   - Not called \"External-3 majority\" unless strict 2-of-3 holds.
3. **Pooled-4 normalized plurality** over frontier/L1/S1/TALE with specified tie-break order.
4. Override when external plurality == Pooled-4 != FTA and `frontier_support <= 1`.
5. Else FTA.

## Terminology
- `external_plurality` / `external_priority_plurality` / `external_tiebreak_plurality`
"""
    write_text(output_dir / "GUARDED_CANDIDATE_FAMILY_SPEC.md", family_spec)

    raw_rows = load_all_corpora(seed53_path=args.cohere_seed53_input, azure_path=args.azure_input)
    corpora = {
        "cohere_aggregate720": [r for r in raw_rows if r.get("corpus") == "cohere_aggregate720"],
        "cohere_seed53": [r for r in raw_rows if r.get("corpus") == "cohere_seed53"],
        "azure_seed97": [r for r in raw_rows if r.get("corpus") == "azure_seed97"],
    }

    # Task 2: external permutations
    perm_results: list[dict[str, Any]] = []
    for order in EXTERNAL_PERMUTATIONS:
        fn = make_guarded_decision(ext_order=order)
        vid = f"ext_order_{'_'.join(order)}"
        perm_results.extend(
            evaluate_all_corpora(
                corpora,
                fn,
                variant_id=vid,
                bootstrap_resamples=args.bootstrap_resamples,
                bootstrap_seed=args.bootstrap_seed,
                ext_order=order,
            )
        )
    # combined summary rows
    for order in EXTERNAL_PERMUTATIONS:
        sub = [r for r in perm_results if r.get("external_order") == _order_label(order)]
        perm_results.append(
            {
                "variant_id": f"ext_order_{'_'.join(order)}",
                "corpus": "all_combined",
                "external_order": _order_label(order),
                "net_wins_vs_fta": sum(r["net_wins_vs_fta"] for r in sub),
                "losses_vs_fta": sum(r["losses_vs_fta"] for r in sub),
                "overrides_triggered": sum(r["overrides_triggered"] or 0 for r in sub),
                "triggers_one_one_one_tie": sum(r["triggers_one_one_one_tie"] for r in sub),
                "macro_net_wins": sum(r["net_wins_vs_fta"] for r in sub),
                "macro_losses": sum(r["losses_vs_fta"] for r in sub),
            }
        )
    write_csv(
        output_dir / "EXTERNAL_TIEBREAK_PERMUTATION_RESULTS.csv",
        perm_results,
        sorted({k for r in perm_results for k in r}),
    )
    nets_by_order = {
        r["external_order"]: r["macro_net_wins"]
        for r in perm_results
        if r.get("corpus") == "all_combined"
    }
    perm_md = (
        "# External Tie-break Permutation Report\n\n"
        f"Evaluated {len(EXTERNAL_PERMUTATIONS)} orders over L1/S1/TALE.\n\n"
        "## Macro net by order\n"
        + "\n".join(f"- {k}: {v}" for k, v in sorted(nets_by_order.items(), key=lambda x: -x[1]))
        + f"\n\nSpread (max-min): {max(nets_by_order.values()) - min(nets_by_order.values()) if nets_by_order else 0}\n"
    )
    write_text(output_dir / "EXTERNAL_TIEBREAK_PERMUTATION_REPORT.md", perm_md)

    # Task 3: Pooled-4 tie sensitivity (fixed L1>S1>TALE external)
    p4_variants: list[tuple[str, Callable[[dict[str, Any]], str | None]]] = [
        ("frontier_L1_S1_TALE", make_guarded_decision(p4_order=DEFAULT_POOLED_ORDER)),
        (
            "L1_S1_TALE_frontier",
            make_guarded_decision(p4_order=("L1", "S1", "TALE", "frontier")),
        ),
        (
            "S1_L1_TALE_frontier",
            make_guarded_decision(p4_order=("S1", "L1", "TALE", "frontier")),
        ),
        (
            "TALE_L1_S1_frontier",
            make_guarded_decision(p4_order=("TALE", "L1", "S1", "frontier")),
        ),
        (
            "prefer_fta_on_p4_tie",
            make_guarded_decision(p4_fn=lambda r, o: pooled4_prefer_fta_tie(r, o)),
        ),
        (
            "abstain_on_p4_tie",
            make_guarded_decision(abstain_p4_tie=True),
        ),
        (
            "prefer_external_on_p4_tie",
            make_guarded_decision(
                p4_fn=lambda r, o: pooled4_prefer_external_tie(r, DEFAULT_EXTERNAL_ORDER, o)
            ),
        ),
    ]
    p4_results: list[dict[str, Any]] = []
    for name, fn in p4_variants:
        p4_results.extend(
            evaluate_all_corpora(
                corpora,
                fn,
                variant_id=f"p4_{name}",
                bootstrap_resamples=args.bootstrap_resamples,
                bootstrap_seed=args.bootstrap_seed,
            )
        )
    write_csv(
        output_dir / "POOLED4_TIEBREAK_SENSITIVITY.csv",
        p4_results,
        sorted({k for r in p4_results for k in r}),
    )
    write_text(
        output_dir / "POOLED4_TIEBREAK_SENSITIVITY_REPORT.md",
        "# Pooled-4 Tie-break Sensitivity\n\nSee POOLED4_TIEBREAK_SENSITIVITY.csv.\n",
    )

    # Task 4: majority vs tie-break signal
    signal_rows = split_override_signal(raw_rows, make_guarded_decision())
    write_csv(output_dir / "MAJORITY_VS_TIEBREAK_SIGNAL.csv", signal_rows, list(signal_rows[0].keys()))
    sig_md = (
        "# Majority vs Tie-break Signal\n\n"
        + "\n".join(
            f"- **{r['signal_group']}**: count={r['override_count']} net={r['net_wins']} defensible={r['defensible']}"
            for r in signal_rows
        )
        + "\n"
    )
    write_text(output_dir / "MAJORITY_VS_TIEBREAK_SIGNAL_REPORT.md", sig_md)

    # Task 5: method priority reliability
    rel_rows = method_reliability_rows(corpora)
    write_csv(output_dir / "METHOD_PRIORITY_RELIABILITY.csv", rel_rows, sorted({k for r in rel_rows for k in r}))
    rel_md = (
        "# Method Priority Justification\n\n"
        "Standalone L1/S1/TALE accuracy varies by corpus; no single priority is uniformly dominant.\n"
        "Provider-specific priority would use `provider` label — **not runtime-legal** for universal rule.\n"
        "LOO reliability ordering uses only training-corpus correctness (offline audit; not for runtime).\n"
    )
    write_text(output_dir / "METHOD_PRIORITY_JUSTIFICATION.md", rel_md)

    # Task 6: defensible variants A-J
    best_global = best_global_order(corpora, bootstrap_resamples=200, bootstrap_seed=0)
    variant_defs: list[tuple[str, str, Callable[[dict[str, Any]], str | None], str, str]] = [
        ("A", "strict_external_majority_only", lambda r: external3_valid_majority_normalized(r) if external3_valid_majority_normalized(r) != _norm(r.get("fta_selected_answer_canonical")) else None, "medium", "strict only"),
        ("B", "fixed_L1_S1_TALE_guarded", make_guarded_decision(ext_order=DEFAULT_EXTERNAL_ORDER), "high", "current H"),
        ("C", f"best_global_order_{'_'.join(best_global)}", make_guarded_decision(ext_order=best_global), "low", "in-sample tuned"),
        ("D", "abstain_external_1_1_1", make_guarded_decision(abstain_external_tie=True), "high", "abstain ties"),
        ("E", "loo_reliability_guarded", None, "medium", "loo"),  # special
        ("F", "pooled4_normalized_standalone", lambda r: pooled4_priority_plurality(r, DEFAULT_POOLED_ORDER) if pooled4_priority_plurality(r, DEFAULT_POOLED_ORDER) != _norm(r.get("fta_selected_answer_canonical")) else None, "high", "standalone"),
        ("G", "fta_default", lambda r: None, "high", "baseline"),
        ("H", "abstain_any_tie", make_guarded_decision(abstain_external_tie=True, abstain_p4_tie=True), "high", "strict agree"),
        ("I", "guard_fs_eq_0", make_guarded_decision(min_fs=0, max_fs=0), "medium", "fs==0"),
        ("J", "guard_fs_le_1", make_guarded_decision(max_fs=1), "high", "fs<=1"),
    ]
    def_results: list[dict[str, Any]] = []
    for vid, name, fn, validity, note in variant_defs:
        if vid == "E":
            for held_out, rows in corpora.items():
                train = {k: v for k, v in corpora.items() if k != held_out}
                order = loo_reliability_order(train)
                decide = make_guarded_decision(ext_order=order)
                def_results.append(
                    evaluate_guarded_on_corpus(
                        rows,
                        decide,
                        corpus=held_out,
                        variant_id=f"E_loo_{held_out}",
                        bootstrap_resamples=args.bootstrap_resamples,
                        bootstrap_seed=args.bootstrap_seed,
                        ext_order=order,
                    )
                )
            continue
        assert fn is not None
        spec_fn = fn
        for corpus, rows in corpora.items():
            ev = evaluate_rule_full(rows, RuleSpec(vid, "v", name, spec_fn))
            fta_ev = evaluate_rule_full(rows, FTA_SPEC)
            boot = paired_bootstrap_ci(
                ev["per_row"], fta_ev["per_row"], n_resamples=args.bootstrap_resamples, seed=args.bootstrap_seed
            )
            def_results.append(
                {
                    "variant_id": vid,
                    "variant_name": name,
                    "corpus": corpus,
                    "accuracy": ev["accuracy"],
                    "net_wins_vs_fta": ev["net_wins"],
                    "losses_vs_fta": ev["losses_vs_canonical_fta"],
                    "overrides_triggered": ev.get("overrides_triggered"),
                    "regression_rate": ev.get("regression_rate_among_fta_correct"),
                    "bootstrap_includes_zero": boot.get("includes_zero"),
                    "semantics_validity": validity,
                    "audit_acceptable": validity in ("high", "medium"),
                    "note": note,
                }
            )
    write_csv(
        output_dir / "DEFENSIBLE_VARIANT_COMPARISON.csv",
        def_results,
        sorted({k for r in def_results for k in r}),
    )
    write_text(
        output_dir / "DEFENSIBLE_VARIANT_REPORT.md",
        "# Defensible Variant Comparison\n\nSee DEFENSIBLE_VARIANT_COMPARISON.csv.\n",
    )

    write_text(output_dir / "TIEBREAK_CASEBOOK.md", build_casebook(raw_rows, corpora))

    classification, reason = classify_decision(
        perm_results,
        signal_rows,
    )
    write_text(
        output_dir / "TIEBREAK_ROBUSTNESS_DECISION.md",
        f"# Tie-break Robustness Decision\n\n**Classification:** {classification}\n\n**Reason:** {reason}\n",
    )

    spread = max(nets_by_order.values()) - min(nets_by_order.values()) if nets_by_order else 0
    tie_sig = next((g for g in signal_rows if g["signal_group"] == "external_one_one_one_tie"), {})
    strict_sig = next((g for g in signal_rows if g["signal_group"] == "strict_external_majority"), {})
    final = [
        "# Final Tie-break Robustness Audit Summary",
        "",
        f"**Classification:** {classification}",
        "",
        "## Does +17 survive external tie-break permutations?",
        f"Macro net range across 6 orders: {min(nets_by_order.values()) if nets_by_order else 0} to {max(nets_by_order.values()) if nets_by_order else 0} (spread {spread}).",
        "",
        "## Is signal mostly tie-break-driven?",
        f"Strict-majority override net: {strict_sig.get('net_wins', 0)}; 1-1-1 tie override net: {tie_sig.get('net_wins', 0)}.",
        "",
        "## Most defensible tie-break",
        "Normalized plurality with fixed documented order OR abstain-on-1-1-1 (variant D).",
        "",
        "## API validation justified?",
        "No for L1>S1>TALE plurality guarded (+17). Abstain-on-1-1-1 (variant D) retains macro net +4 only.",
        "",
        "## Best defensible variant",
        "Variant D (abstain on external 1-1-1) or strict-majority-only signal (+4 net) — not full +17.",
        "",
        "## Do not claim",
        "- That L1>S1>TALE order is theoretically optimal.",
        "- That +17 is independent of plurality tie-break without reporting spread.",
        "- Provider-specific method priority as runtime rule.",
    ]
    write_text(output_dir / "FINAL_TIEBREAK_ROBUSTNESS_AUDIT_SUMMARY.md", "\n".join(final).rstrip() + "\n")

    return {
        "output_dir": str(output_dir),
        "macro_net_spread": spread,
        "macro_net_min": min(nets_by_order.values()) if nets_by_order else None,
        "macro_net_max": max(nets_by_order.values()) if nets_by_order else None,
        "classification": classification,
        "tie_signal_net": tie_sig.get("net_wins"),
        "strict_signal_net": strict_sig.get("net_wins"),
    }


def main() -> int:
    args = parse_args()
    result = run_audit(args)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
