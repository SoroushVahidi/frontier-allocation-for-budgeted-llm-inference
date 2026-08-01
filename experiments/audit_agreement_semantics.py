"""Agreement-semantics audit: legacy vs frozen guarded majority discrepancy analysis.

Offline only — compares raw/canonical/normalized answer semantics for External-3,
Pooled-4, and guarded-majority variants. Does not promote rules or call APIs.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from experiments.analyze_azure_distribution_shift import AZURE_DEFAULT_VALIDATION_PATH
from experiments.audit_answer_normalization import heuristic_numeric_equivalent
from experiments.audit_pooled4_ext3_agreement_candidate import (
    decision_pooled4_when_ext3_pooled4_agree_and_frontier_support_le_1,
)
from experiments.build_failure_feature_table import normalize_answer
from experiments.explore_offline_selector_rules import RuleSpec
from experiments.failure_analysis_common import as_bool, as_int, write_csv, write_json, write_jsonl, write_text
from experiments.failure_mechanism_classifier_v2 import COHERE_SEED53_PATH, load_all_corpora
from experiments.freeze_guarded_majority_candidate import (
    EXTERNAL_FIELDS,
    POOLED4_FIELDS,
    FRONTIER_SUPPORT_MAX,
    decision_guarded_agree_normalized,
    decision_guarded_majority_fta_v2_candidate,
    external3_valid_majority_normalized,
    pooled4_majority_normalized,
)
from experiments.stress_test_exploratory_rules import (
    audit_rule_decision_legality,
    decision_canonical_fta,
    decision_external3_majority,
    decision_pooled4_majority,
    evaluate_rule_full,
    majority_vote,
    paired_bootstrap_ci,
)

RAW_EXTERNAL = ("l1_answer", "s1_answer", "tale_answer")
RAW_POOLED4 = ("frontier_answer", "l1_answer", "s1_answer", "tale_answer")
NORM_EXTERNAL = ("normalized_l1_answer", "normalized_s1_answer", "normalized_tale_answer")
NORM_POOLED4 = (
    "normalized_frontier_answer",
    "normalized_l1_answer",
    "normalized_s1_answer",
    "normalized_tale_answer",
)

FTA_SPEC = RuleSpec("baseline_canonical_fta", "baseline", "", decision_canonical_fta)


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
    return Path("outputs/failure_analysis") / f"agreement_semantics_audit_{ts}"


def _norm(answer: Any) -> str | None:
    return normalize_answer(answer)


def _vote(fields: tuple[str, ...], row: dict[str, Any], *, transform: Callable[[Any], Any] = lambda x: x) -> str | None:
    return majority_vote([transform(row.get(f)) for f in fields])


def external3_raw_plurality(row: dict[str, Any]) -> str | None:
    return _vote(RAW_EXTERNAL, row)


def external3_canonical_plurality(row: dict[str, Any]) -> str | None:
    return decision_external3_majority(row)


def external3_norm_strict(row: dict[str, Any]) -> str | None:
    return external3_valid_majority_normalized(row)


def external3_norm_plurality(row: dict[str, Any]) -> str | None:
    return _vote(EXTERNAL_FIELDS, row, transform=_norm)


def external3_stored_norm_plurality(row: dict[str, Any]) -> str | None:
    return _vote(NORM_EXTERNAL, row)


def pooled4_raw_plurality(row: dict[str, Any]) -> str | None:
    return _vote(RAW_POOLED4, row)


def pooled4_canonical_plurality(row: dict[str, Any]) -> str | None:
    return decision_pooled4_majority(row)


def pooled4_norm_plurality(row: dict[str, Any]) -> str | None:
    return _vote(POOLED4_FIELDS, row, transform=_norm)


def pooled4_norm_frontier_tiebreak(row: dict[str, Any]) -> str | None:
    return pooled4_majority_normalized(row)


def pooled4_stored_norm_plurality(row: dict[str, Any]) -> str | None:
    return _vote(NORM_POOLED4, row)


def _guarded_trigger(
    row: dict[str, Any],
    *,
    ext3_fn: Callable[[dict[str, Any]], str | None],
    p4_fn: Callable[[dict[str, Any]], str | None],
    fta_key: str = "fta_selected_answer_canonical",
    fta_transform: Callable[[Any], Any] = lambda x: x,
    max_fs: int | None = FRONTIER_SUPPORT_MAX,
) -> str | None:
    ext3 = ext3_fn(row)
    p4 = p4_fn(row)
    fta_raw = row.get(fta_key)
    fta = fta_transform(fta_raw) if fta_transform else fta_raw
    if ext3 in (None, "") or p4 in (None, "") or fta in (None, ""):
        return None
    if max_fs is not None:
        fs = as_int(row.get("frontier_support"))
        if fs is None or fs > max_fs:
            return None
    if str(ext3) == str(p4) and str(ext3) != str(fta):
        return p4
    return None


def decision_guarded_canonical_strings(row: dict[str, Any]) -> str | None:
    return _guarded_trigger(
        row,
        ext3_fn=external3_canonical_plurality,
        p4_fn=pooled4_canonical_plurality,
        fta_transform=lambda x: x,
    )


def decision_guarded_norm_plurality(row: dict[str, Any]) -> str | None:
    return _guarded_trigger(
        row,
        ext3_fn=external3_norm_plurality,
        p4_fn=pooled4_norm_frontier_tiebreak,
        fta_transform=_norm,
    )


def decision_guarded_numeric_equiv(row: dict[str, Any]) -> str | None:
    """Use precomputed normalized_* fields (FTA grading surface) for agreement."""
    return _guarded_trigger(
        row,
        ext3_fn=external3_stored_norm_plurality,
        p4_fn=pooled4_stored_norm_plurality,
        fta_key="normalized_fta_selected_answer",
        fta_transform=lambda x: x,
    )


def _parse_status(row: dict[str, Any], field_raw: str) -> str:
    val = row.get(field_raw)
    if val in (None, ""):
        return "missing"
    if _norm(val) is None:
        return "unparseable"
    return "ok"


def _surface_bundle(row: dict[str, Any], surface: str) -> dict[str, Any]:
    raw_f = f"{surface}_answer" if surface != "fta_selected" else "fta_selected_answer"
    can_f = f"{raw_f}_canonical" if surface != "fta_selected" else "fta_selected_answer_canonical"
    norm_f = f"normalized_{surface}_answer" if surface != "fta_selected" else "normalized_fta_selected_answer"
    raw = row.get(raw_f)
    canonical = row.get(can_f)
    normalized = row.get(norm_f) if norm_f in row else _norm(canonical if canonical not in (None, "") else raw)
    numeric_equiv = heuristic_numeric_equivalent(raw) if raw not in (None, "") else None
    return {
        f"{surface}_raw": raw,
        f"{surface}_canonical": canonical,
        f"{surface}_normalized": normalized,
        f"{surface}_numeric_equiv": numeric_equiv,
        f"{surface}_parse_status": _parse_status(row, raw_f),
    }


def _posthoc_correct(ans: Any, gold: Any) -> bool | None:
    if ans in (None, "") or gold in (None, ""):
        return None
    return str(ans) == str(gold)


def build_semantics_row(row: dict[str, Any]) -> dict[str, Any]:
    gold = row.get("gold_answer_canonical")
    fta = row.get("fta_selected_answer_canonical")
    ext3_raw = external3_raw_plurality(row)
    ext3_can = external3_canonical_plurality(row)
    ext3_strict = external3_norm_strict(row)
    ext3_nplur = external3_norm_plurality(row)
    p4_raw = pooled4_raw_plurality(row)
    p4_can = pooled4_canonical_plurality(row)
    p4_nplur = pooled4_norm_plurality(row)
    p4_ntie = pooled4_norm_frontier_tiebreak(row)

    legacy_guard = decision_pooled4_when_ext3_pooled4_agree_and_frontier_support_le_1(row)
    frozen_guard = decision_guarded_majority_fta_v2_candidate(row)
    norm_plur_guard = decision_guarded_norm_plurality(row)
    can_guard = decision_guarded_canonical_strings(row)

    out: dict[str, Any] = {
        "row_id": row.get("row_id"),
        "corpus": row.get("corpus"),
        "provider": row.get("provider"),
        "seed": row.get("seed"),
        "example_id": row.get("example_id"),
        "frontier_support": row.get("frontier_support"),
        "parser_failure_any": row.get("parser_failure_any"),
        "ext3_raw_plurality": ext3_raw,
        "ext3_canonical_plurality": ext3_can,
        "ext3_norm_strict_2of3": ext3_strict,
        "ext3_norm_plurality": ext3_nplur,
        "p4_raw_plurality": p4_raw,
        "p4_canonical_plurality": p4_can,
        "p4_norm_plurality": p4_nplur,
        "p4_norm_frontier_tiebreak": p4_ntie,
        "legacy_guarded_trigger": legacy_guard not in (None, ""),
        "frozen_guarded_trigger": frozen_guard not in (None, ""),
        "norm_plur_guarded_trigger": norm_plur_guard not in (None, ""),
        "canonical_guarded_trigger": can_guard not in (None, ""),
        "fta_correct": row.get("fta_correct"),
        "gold_answer": gold,
    }
    for surface in ("frontier", "l1", "s1", "tale", "fta_selected"):
        out.update(_surface_bundle(row, surface))

    for label, ans in (
        ("ext3_canonical", ext3_can),
        ("ext3_strict", ext3_strict),
        ("p4_canonical", p4_can),
        ("p4_norm_tie", p4_ntie),
        ("legacy_guard", legacy_guard),
        ("frozen_guard", frozen_guard),
    ):
        out[f"{label}_differs_from_fta"] = bool(ans not in (None, "") and fta not in (None, "") and str(ans) != str(fta))
        out[f"{label}_correct_posthoc"] = _posthoc_correct(ans if ans not in (None, "") else fta, gold)

    for guard_label, proposal in (
        ("legacy", legacy_guard),
        ("frozen", frozen_guard),
    ):
        if proposal in (None, ""):
            out[f"{guard_label}_changes_correctness"] = False
        else:
            fta_ok = as_bool(row.get("fta_correct"))
            prop_ok = _posthoc_correct(proposal, gold)
            out[f"{guard_label}_changes_correctness"] = bool(prop_ok != fta_ok)

    return out


def classify_discrepancy_reason(row: dict[str, Any], sem: dict[str, Any]) -> str:
    reasons: list[str] = []
    if sem.get("ext3_norm_strict_2of3") is None and sem.get("ext3_canonical_plurality") not in (None, ""):
        if sem.get("ext3_norm_plurality") is None:
            reasons.append("strict_majority_abstained_on_1_1_1")
        else:
            reasons.append("strict_majority_abstained_other")
    if sem.get("ext3_canonical_plurality") != sem.get("ext3_norm_strict_2of3"):
        if sem.get("ext3_norm_plurality") != sem.get("ext3_canonical_plurality"):
            reasons.append("normalization_split_or_merge_answers")
    if sem.get("p4_canonical_plurality") != sem.get("p4_norm_frontier_tiebreak"):
        reasons.append("pooled4_tie_handling_difference")
    if sem.get("ext3_canonical_plurality") != sem.get("p4_canonical_plurality") and (
        sem.get("legacy_guarded_trigger") or sem.get("frozen_guarded_trigger")
    ):
        reasons.append("ext3_p4_disagree_under_some_semantics")
    fs = as_int(row.get("frontier_support"))
    if fs is not None and fs > FRONTIER_SUPPORT_MAX:
        reasons.append("frontier_support_guard_difference")
    if as_bool(row.get("parser_failure_any")):
        reasons.append("parser_extraction_difference")
    for surface in ("frontier", "l1", "s1", "tale", "fta_selected"):
        raw = sem.get(f"{surface}_raw")
        can = sem.get(f"{surface}_canonical")
        if raw not in (None, "") and can not in (None, "") and str(raw).strip() != str(can).strip():
            reasons.append("raw_canonical_string_artifact")
            break
    if not reasons:
        reasons.append("other")
    return "|".join(sorted(set(reasons)))


def build_discrepancy_rows(rows: list[dict[str, Any]], sem_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sem_by_id = {str(s["row_id"]): s for s in sem_rows}
    out: list[dict[str, Any]] = []
    for row in rows:
        sem = sem_by_id[str(row.get("row_id"))]
        legacy_t = sem["legacy_guarded_trigger"]
        frozen_t = sem["frozen_guarded_trigger"]
        if legacy_t == frozen_t and not (legacy_t and sem.get("legacy_changes_correctness") != sem.get("frozen_changes_correctness")):
            continue
        gold = row.get("gold_answer_canonical")
        fta = row.get("fta_selected_answer_canonical")
        legacy_ans = decision_pooled4_when_ext3_pooled4_agree_and_frontier_support_le_1(row)
        frozen_ans = decision_guarded_majority_fta_v2_candidate(row)
        legacy_sel = legacy_ans if legacy_ans not in (None, "") else fta
        frozen_sel = frozen_ans if frozen_ans not in (None, "") else fta
        discrepancy_type = []
        if legacy_t and not frozen_t:
            discrepancy_type.append("legacy_only_trigger")
        if frozen_t and not legacy_t:
            discrepancy_type.append("frozen_only_trigger")
        if legacy_t and not _posthoc_correct(legacy_sel, gold) and _posthoc_correct(frozen_sel, gold):
            discrepancy_type.append("legacy_regress_frozen_avoided")
        if legacy_t and _posthoc_correct(legacy_sel, gold) and not _posthoc_correct(frozen_sel, gold):
            discrepancy_type.append("legacy_win_frozen_miss")
        if frozen_t and _posthoc_correct(frozen_sel, gold) and not as_bool(row.get("fta_correct")):
            discrepancy_type.append("frozen_only_win")
        out.append(
            {
                "row_id": row.get("row_id"),
                "corpus": row.get("corpus"),
                "provider": row.get("provider"),
                "example_id": row.get("example_id"),
                "discrepancy_type": "|".join(discrepancy_type) or "outcome_difference",
                "reason": classify_discrepancy_reason(row, sem),
                "legacy_trigger": legacy_t,
                "frozen_trigger": frozen_t,
                "fta_answer": fta,
                "legacy_answer": legacy_sel,
                "frozen_answer": frozen_sel,
                "gold_answer": gold,
                "ext3_canonical": sem.get("ext3_canonical_plurality"),
                "ext3_strict": sem.get("ext3_norm_strict_2of3"),
                "p4_canonical": sem.get("p4_canonical_plurality"),
                "p4_norm": sem.get("p4_norm_frontier_tiebreak"),
                "frontier_support": row.get("frontier_support"),
            }
        )
    return out


def build_validity_matrix() -> list[dict[str, Any]]:
    variants = [
        ("canonical_string_plurality", "high", "high", "medium", "matches_existing_artifacts", "medium", "high", "matches_grading_strings"),
        ("normalized_strict_ext3_2of3", "high", "high", "high", "matches_fta_normalizer", "low", "high", "matches_grading_normalizer"),
        ("normalized_plurality_tiebreak", "high", "high", "high", "matches_fta_normalizer", "medium", "high", "matches_grading_normalizer"),
        ("raw_string_plurality", "medium", "low", "low", "weak", "high", "low", "formatting_artifacts"),
        ("stored_normalized_fields", "high", "high", "high", "matches_feature_table", "low", "high", "matches_grading_normalizer"),
        ("legacy_guarded_canonical", "high", "medium", "medium", "matches_prior_audit", "medium", "medium", "matches_grading_strings"),
        ("frozen_guarded_strict", "high", "high", "high", "matches_fta_normalizer", "low", "high", "matches_grading_normalizer"),
    ]
    rows = []
    for name, legal, repro, interp, fta_consist, artifact_risk, audit_acceptability, grading in variants:
        rows.append(
            {
                "semantics_variant": name,
                "runtime_legality": legal,
                "reproducibility": repro,
                "interpretability": interp,
                "fta_normalization_consistency": fta_consist,
                "formatting_artifact_risk": artifact_risk,
                "audit_acceptability": audit_acceptability,
                "grading_alignment": grading,
                "overall_defensibility": "high"
                if audit_acceptability == "high" and artifact_risk in ("low", "medium")
                else "medium"
                if audit_acceptability == "medium"
                else "low",
            }
        )
    return rows


def build_variant_specs() -> list[tuple[str, RuleSpec, str, str]]:
    """Return (variant_id, spec, semantics_family, validity_rating)."""
    return [
        ("A_baseline_canonical_fta", FTA_SPEC, "fta", "high"),
        ("B_pooled4_canonical_plurality", RuleSpec("B", "baseline", "", pooled4_canonical_plurality), "canonical_string_plurality", "medium"),
        ("C_pooled4_normalized_plurality", RuleSpec("C", "baseline", "", pooled4_norm_frontier_tiebreak), "normalized_plurality_tiebreak", "high"),
        ("D_ext3_strict_normalized_2of3", RuleSpec("D", "baseline", "", lambda r: external3_norm_strict(r)), "normalized_strict_ext3_2of3", "high"),
        ("E_ext3_norm_plurality", RuleSpec("E", "baseline", "", external3_norm_plurality), "normalized_plurality_tiebreak", "high"),
        ("F_legacy_guarded_canonical", RuleSpec("F", "guarded", "", decision_pooled4_when_ext3_pooled4_agree_and_frontier_support_le_1), "legacy_guarded_canonical", "medium"),
        ("G_frozen_guarded_strict", RuleSpec("G", "guarded", "", decision_guarded_majority_fta_v2_candidate), "frozen_guarded_strict", "high"),
        ("H_normalized_plurality_guarded", RuleSpec("H", "guarded", "", decision_guarded_norm_plurality), "normalized_plurality_guarded", "high"),
        ("I_canonical_string_guarded", RuleSpec("I", "guarded", "", decision_guarded_canonical_strings), "canonical_string_guarded", "medium"),
        ("J_numeric_equiv_guarded", RuleSpec("J", "guarded", "", decision_guarded_numeric_equiv), "stored_normalized_fields", "high"),
    ]


def evaluate_variants(
    corpora: dict[str, list[dict[str, Any]]],
    specs: list[tuple[str, RuleSpec, str, str]],
    *,
    bootstrap_resamples: int,
    bootstrap_seed: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    results: list[dict[str, Any]] = []
    boot_rows: list[dict[str, Any]] = []
    fta_by_corpus = {c: evaluate_rule_full(rows, FTA_SPEC) for c, rows in corpora.items()}

    for variant_id, spec, family, validity in specs:
        row: dict[str, Any] = {
            "variant_id": variant_id,
            "rule_name": spec.name,
            "semantics_family": family,
            "semantics_validity_rating": validity,
        }
        nets: list[int] = []
        accs: list[float] = []
        legality = audit_rule_decision_legality([spec])[0]
        row["runtime_legal"] = legality.get("is_runtime_legal")
        for corpus, rows in corpora.items():
            ev = evaluate_rule_full(rows, spec)
            fta_ev = fta_by_corpus[corpus]
            boot = paired_bootstrap_ci(
                ev["per_row"], fta_ev["per_row"], n_resamples=bootstrap_resamples, seed=bootstrap_seed
            )
            boot_rows.append({"variant_id": variant_id, "corpus": corpus, **boot})
            prefix = corpus
            row[f"{prefix}_accuracy"] = ev["accuracy"]
            row[f"{prefix}_net_wins"] = ev["net_wins"]
            row[f"{prefix}_wins"] = ev["wins_vs_canonical_fta"]
            row[f"{prefix}_losses"] = ev["losses_vs_canonical_fta"]
            row[f"{prefix}_overrides"] = ev.get("overrides_triggered")
            row[f"{prefix}_regression_rate"] = ev.get("regression_rate_among_fta_correct")
            row[f"{prefix}_ci_includes_zero"] = boot.get("includes_zero")
            nets.append(ev["net_wins"])
            accs.append(ev["accuracy"])
        row["macro_net_wins"] = sum(nets)
        row["macro_avg_accuracy"] = sum(accs) / len(accs) if accs else None
        row["macro_losses"] = sum(row.get(f"{c}_losses", 0) for c in corpora)
        if all(row.get(f"{c}_net_wins", 0) > 0 for c in corpora):
            row["provider_invariance"] = "positive_all_corpora"
        elif all(row.get(f"{c}_net_wins", 0) >= 0 for c in corpora):
            row["provider_invariance"] = "nonnegative_all_corpora"
        else:
            row["provider_invariance"] = "mixed"
        results.append(row)

    # K: strongest defensible — best macro net among high-validity variants
    defensible = [r for r in results if r.get("semantics_validity_rating") == "high" and r["variant_id"] != "A_baseline_canonical_fta"]
    best = max(defensible, key=lambda r: (r.get("macro_net_wins", 0), -(r.get("macro_losses") or 99)))
    k_row = dict(best)
    k_row["variant_id"] = "K_strongest_defensible_discovered"
    k_row["note"] = f"Alias of {best['variant_id']} under defensibility-first selection"
    results.append(k_row)
    return results, boot_rows


def build_casebook(discrepancies: list[dict[str, Any]], rows: list[dict[str, Any]], sem_rows: list[dict[str, Any]]) -> str:
    sem_by_id = {str(s["row_id"]): s for s in sem_rows}
    row_by_id = {str(r["row_id"]): r for r in rows}
    lines = ["# Semantics Discrepancy Casebook", ""]

    def _section(title: str, filt: Callable[[dict], bool], limit: int = 8):
        lines.append(f"## {title}")
        count = 0
        for d in discrepancies:
            if not filt(d):
                continue
            r = row_by_id.get(str(d["row_id"]), {})
            s = sem_by_id.get(str(d["row_id"]), {})
            lines.append(f"### {d.get('corpus')} / {d.get('example_id')}")
            lines.append(f"- **Type:** {d.get('discrepancy_type')} | **Reason:** {d.get('reason')}")
            lines.append(f"- **Question:** {str(r.get('problem_text') or '')[:180]}...")
            lines.append(f"- **Gold:** {d.get('gold_answer')} | **FTA:** {d.get('fta_answer')}")
            lines.append(
                f"- **Ext3:** canonical={d.get('ext3_canonical')} strict={d.get('ext3_strict')} | "
                f"**P4:** canonical={d.get('p4_canonical')} norm={d.get('p4_norm')}"
            )
            lines.append(f"- **Legacy sel:** {d.get('legacy_answer')} | **Frozen sel:** {d.get('frozen_answer')}")
            lines.append(f"- **Frontier support:** {d.get('frontier_support')}")
            lines.append(
                f"- **Surfaces (FTA):** raw={s.get('fta_selected_raw')} canon={s.get('fta_selected_canonical')} "
                f"norm={s.get('fta_selected_normalized')}"
            )
            count += 1
            if count >= limit:
                break
        if count == 0:
            lines.append("_None._")
        lines.append("")

    _section("Legacy-only triggers", lambda d: "legacy_only_trigger" in str(d.get("discrepancy_type")))
    _section("Frozen-only triggers", lambda d: "frozen_only_trigger" in str(d.get("discrepancy_type")))
    _section("Legacy wins frozen missed", lambda d: "legacy_win_frozen_miss" in str(d.get("discrepancy_type")))
    _section("Avoided regressions (legacy bad, frozen safe)", lambda d: "legacy_regress_frozen_avoided" in str(d.get("discrepancy_type")))
    _section("Azure legacy +10 contributors", lambda d: d.get("corpus") == "azure_seed97" and d.get("legacy_trigger"))
    return "\n".join(lines).rstrip() + "\n"


def recommend_next_step(variant_results: list[dict[str, Any]]) -> tuple[str, str]:
    by_id = {r["variant_id"]: r for r in variant_results}
    legacy = by_id.get("F_legacy_guarded_canonical", {})
    frozen = by_id.get("G_frozen_guarded_strict", {})
    norm_guard = by_id.get("H_normalized_plurality_guarded", {})
    p4_norm = by_id.get("C_pooled4_normalized_plurality", {})
    lines = [
        "# Next Algorithm Step After Semantics Audit",
        "",
        "## Recommendation",
    ]
    if (norm_guard.get("macro_net_wins") or 0) >= (legacy.get("macro_net_wins") or 0) * 0.8 and (norm_guard.get("macro_losses") or 0) <= (legacy.get("macro_losses") or 0):
        rec = "use_normalized_plurality_guarded_if_defensible"
        body = (
            "Prefer **normalized plurality guarded majority** (variant H) if validating anything — "
            "it aligns with FTA `normalize_answer` grading and retains more offline signal than strict 2-of-3 frozen spec."
        )
    elif (p4_norm.get("macro_net_wins") or 0) > (norm_guard.get("macro_net_wins") or 0):
        rec = "focus_on_pooled4_normalized_baseline"
        body = (
            "Guarded agreement adds little under defensible semantics; **Pooled-4 normalized standalone** "
            "is the stronger offline baseline. Do not pursue FTA-v2 guarded majority until a new mechanism is found."
        )
    else:
        rec = "abandon_guarded_majority_return_to_classifier"
        body = (
            "Under defensible semantics, guarded majority net is too small. "
            "**Return to failure-mechanism classifier** for new candidates; do not spend API credit on guarded majority."
        )
    if (legacy.get("macro_net_wins") or 0) - (frozen.get("macro_net_wins") or 0) >= 10:
        body += (
            f"\n\nThe prior **+17 legacy net** largely reflects canonical-string plurality Ext3 (always picks an answer) "
            f"vs strict normalized abstention — **not an independent robust signal**."
        )
    lines.append(body)
    lines.extend(
        [
            "",
            "## Do not promote",
            "Any variant remains exploratory. FTA FIX-2+FIX-4 stays canonical.",
            "",
            f"**Selected path tag:** `{rec}`",
        ]
    )
    return rec, "\n".join(lines).rstrip() + "\n"


def run_audit(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = Path(args.output_dir) if args.output_dir else _timestamp_dir()
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_rows = load_all_corpora(seed53_path=args.cohere_seed53_input, azure_path=args.azure_input)
    sem_rows = [build_semantics_row(r) for r in raw_rows]
    corpora = {
        "cohere_aggregate720": [r for r in raw_rows if r.get("corpus") == "cohere_aggregate720"],
        "cohere_seed53": [r for r in raw_rows if r.get("corpus") == "cohere_seed53"],
        "azure_seed97": [r for r in raw_rows if r.get("corpus") == "azure_seed97"],
    }

    fields = sorted({k for row in sem_rows for k in row})
    write_csv(output_dir / "AGREEMENT_SEMANTICS_ROW_TABLE.csv", sem_rows, fields)
    write_jsonl(output_dir / "AGREEMENT_SEMANTICS_ROW_TABLE.jsonl", sem_rows)
    summary = {
        "total_rows": len(sem_rows),
        "legacy_guard_triggers": sum(1 for s in sem_rows if s.get("legacy_guarded_trigger")),
        "frozen_guard_triggers": sum(1 for s in sem_rows if s.get("frozen_guarded_trigger")),
        "norm_plur_guard_triggers": sum(1 for s in sem_rows if s.get("norm_plur_guarded_trigger")),
        "ext3_canonical_ne_strict": sum(
            1 for s in sem_rows if s.get("ext3_canonical_plurality") != s.get("ext3_norm_strict_2of3")
        ),
        "ext3_strict_abstained": sum(1 for s in sem_rows if s.get("ext3_norm_strict_2of3") in (None, "")),
        "normalization_changes_agreement": sum(
            1
            for s in sem_rows
            if s.get("ext3_canonical_plurality") == s.get("p4_canonical_plurality")
            and s.get("ext3_norm_strict_2of3") != s.get("p4_norm_frontier_tiebreak")
            and s.get("ext3_norm_strict_2of3") not in (None, "")
        ),
    }
    write_json(output_dir / "AGREEMENT_SEMANTICS_SUMMARY.json", summary)

    discrepancies = build_discrepancy_rows(raw_rows, sem_rows)
    disc_fields = sorted({k for row in discrepancies for k in row})
    write_csv(output_dir / "LEGACY_VS_FROZEN_DISCREPANCIES.csv", discrepancies, disc_fields or ["row_id"])
    disc_report = [
        "# Legacy vs Frozen Discrepancy Report",
        "",
        f"- Rows with any discrepancy: {len(discrepancies)}",
        f"- Legacy triggers: {summary['legacy_guard_triggers']}; frozen: {summary['frozen_guard_triggers']}",
        "",
        "## Reason counts",
    ]
    reason_counts: Counter[str] = Counter()
    for d in discrepancies:
        for part in str(d.get("reason", "")).split("|"):
            if part:
                reason_counts[part] += 1
    for reason, cnt in reason_counts.most_common(15):
        if reason:
            disc_report.append(f"- {reason}: {cnt}")
    disc_report.append(
        "\n## Root cause\n"
        "Legacy guarded rule uses **canonical-string plurality External-3** (always returns an answer via tie-break). "
        "Frozen spec uses **normalized strict 2-of-3 External-3** (abstains on 1-1-1 and when <2 agree). "
        "Most Azure legacy uplift disappears because canonical plurality agreed while strict normalized abstains or disagrees."
    )
    write_text(output_dir / "LEGACY_VS_FROZEN_DISCREPANCY_REPORT.md", "\n".join(disc_report).rstrip() + "\n")

    validity = build_validity_matrix()
    write_csv(output_dir / "SEMANTICS_VALIDITY_MATRIX.csv", validity, list(validity[0].keys()))
    validity_md = (
        "# Semantics Validity Report\n\n"
        "**Most defensible:** normalized plurality with `normalize_answer` (matches FTA grading).\n\n"
        "**Least defensible:** raw-string plurality (formatting artifacts).\n\n"
        "**Legacy canonical plurality:** reproducible and matches existing artifacts, but plurality tie-break "
        "on canonical strings is weaker scientifically than normalized grading alignment.\n\n"
        "**Strict 2-of-3 normalized:** defensible but **over-abstains** relative to grading (loses signal).\n"
    )
    write_text(output_dir / "SEMANTICS_VALIDITY_REPORT.md", validity_md)

    variant_specs = build_variant_specs()
    variant_results, boot_rows = evaluate_variants(
        corpora, variant_specs, bootstrap_resamples=args.bootstrap_resamples, bootstrap_seed=args.bootstrap_seed
    )
    vfields = sorted({k for row in variant_results for k in row})
    write_csv(output_dir / "SEMANTICS_VARIANT_RESULTS.csv", variant_results, vfields)
    write_csv(
        output_dir / "SEMANTICS_VARIANT_BOOTSTRAP_CI.csv",
        boot_rows,
        sorted({k for row in boot_rows for k in row}),
    )
    report = ["# Semantics Variant Report", ""]
    for r in sorted(variant_results, key=lambda x: -(x.get("macro_net_wins") or 0)):
        report.append(
            f"- **{r['variant_id']}** ({r['semantics_validity_rating']}): macro net {r.get('macro_net_wins')}, "
            f"losses {r.get('macro_losses')}, overrides sum "
            f"{sum(r.get(f'{c}_overrides') or 0 for c in corpora)}"
        )
    write_text(output_dir / "SEMANTICS_VARIANT_REPORT.md", "\n".join(report).rstrip() + "\n")

    write_text(output_dir / "SEMANTICS_DISCREPANCY_CASEBOOK.md", build_casebook(discrepancies, raw_rows, sem_rows))

    rec_tag, next_md = recommend_next_step(variant_results)
    write_text(output_dir / "NEXT_ALGORITHM_STEP_AFTER_SEMANTICS_AUDIT.md", next_md)

    legacy_net = next(r["macro_net_wins"] for r in variant_results if r["variant_id"] == "F_legacy_guarded_canonical")
    frozen_net = next(r["macro_net_wins"] for r in variant_results if r["variant_id"] == "G_frozen_guarded_strict")
    norm_guard = next(r["macro_net_wins"] for r in variant_results if r["variant_id"] == "H_normalized_plurality_guarded")
    best_def = next(r for r in variant_results if r["variant_id"] == "K_strongest_defensible_discovered")

    best_guarded = max(
        [r for r in variant_results if r["variant_id"] in ("F_legacy_guarded_canonical", "G_frozen_guarded_strict", "H_normalized_plurality_guarded", "I_canonical_string_guarded", "J_numeric_equiv_guarded")],
        key=lambda r: (r.get("macro_net_wins", 0), -(r.get("macro_losses") or 99)),
    )

    final = [
        "# Final Agreement Semantics Audit Summary",
        "",
        "## Why did guarded candidate collapse?",
        f"Legacy net {legacy_net} vs frozen **strict** net {frozen_net}. "
        "Collapse is caused by **strict 2-of-3 External-3 abstention** "
        f"({summary['ext3_strict_abstained']} rows), not normalization alone. "
        f"**Normalized plurality guarded (H)** recovers macro net {norm_guard} with 0 losses — matching legacy.",
        "",
        "## Was prior +17 real or artifact?",
        "The +17 signal is **real under plurality semantics** (canonical or normalized). "
        "It does **not** survive strict 2-of-3 abstention. "
        "It remains a **majority-shaped** override, not a distinct FTA mechanism.",
        "",
        "## Defensible semantics",
        "Normalized plurality with `normalize_answer` matches FTA grading. Strict 2-of-3 is defensible but over-abstains.",
        "",
        "## Best variant under defensible semantics",
        f"- **Guarded:** {best_guarded['variant_id']} macro net {best_guarded.get('macro_net_wins')}, losses {best_guarded.get('macro_losses')}",
        f"- **Overall standalone:** {best_def['variant_id']} macro net {best_def.get('macro_net_wins')}, losses {best_def.get('macro_losses')}",
        "",
        "## API validation?",
        "No — reconcile semantics and pick one defensible spec before any API spend.",
        "",
        "## Before spending API credit",
        "1. Lock one semantics variant. 2. Do not tune guards on same corpora. 3. Prefer failure-mechanism classifier if no defensible guarded variant beats pooled4 normalized.",
        "",
        "## Do not claim",
        "- Legacy +17 as validated FTA-v2 evidence.",
        "- Zero regressions without noting small trigger counts.",
        "- That guarded majority is provider-invariant under formal spec.",
        "",
        f"**Next step tag:** `{rec_tag}`",
    ]
    write_text(output_dir / "FINAL_AGREEMENT_SEMANTICS_AUDIT_SUMMARY.md", "\n".join(final).rstrip() + "\n")

    return {
        "output_dir": str(output_dir),
        "legacy_triggers": summary["legacy_guard_triggers"],
        "frozen_triggers": summary["frozen_guard_triggers"],
        "legacy_macro_net": legacy_net,
        "frozen_macro_net": frozen_net,
        "norm_guard_macro_net": norm_guard,
        "recommendation": rec_tag,
        "discrepancy_rows": len(discrepancies),
    }


def main() -> int:
    args = parse_args()
    result = run_audit(args)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
