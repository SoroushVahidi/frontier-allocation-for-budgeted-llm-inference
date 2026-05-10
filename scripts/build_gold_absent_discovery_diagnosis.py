#!/usr/bin/env python3
"""Build gold-absent discovery diagnosis bundle from existing CSV/JSON artifacts only."""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def load_csv_dict(path: Path, key: str) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8") as f:
        return {row[key]: row for row in csv.DictReader(f)}


def has_gold_absent_tag(cell: str) -> bool:
    if not cell:
        return False
    return any(p.strip() == "gold_absent_discovery" for p in cell.split(";"))


def derive_family(text: str, cluster_hints: str) -> tuple[str, str]:
    """Return (derived_problem_family, derivation_confidence)."""
    hints = (cluster_hints or "").strip()
    t = (text or "").lower()
    if hints:
        hint_parts = [h.strip() for h in hints.split("|") if h.strip()]
        if len(hint_parts) == 1:
            h = hint_parts[0]
            if h == "rate_ratio":
                return "rate_ratio", "artifact_label"
            if h == "temporal_change":
                return "temporal_change", "artifact_label"
            if h == "difference":
                return "difference_comparison", "artifact_label"
        elif len(hint_parts) > 1:
            # Prefer rate_ratio if present (often dominant in multi-tag GSM8K)
            if "rate_ratio" in hint_parts:
                return "rate_ratio", "artifact_label"
            if "temporal_change" in hint_parts:
                return "temporal_change", "artifact_label"

    # Heuristic fallback (gold-free; text only)
    def hit(pat: str) -> bool:
        return re.search(pat, t, re.I) is not None

    if hit(r"\baverage\b"):
        return "average", "heuristic_high"
    if hit(r"split into|equal in number|smallest group|groups such that"):
        return "counting_combinatorics", "heuristic_high"
    if hit(r"\$|dollars?\b|cents\b|profit\b|cost\b|interest\b|budget|bill|price|discount|%\s*off"):
        return "money_budget", "heuristic_high"
    if hit(r"square footage|perimeter|area\b|inch|feet|foot\b|kg\b|meter|mph|minutes? per"):
        if hit(r"inch|feet|foot") and hit(r"long\b|wide\b|between"):
            return "unit_conversion", "heuristic_high"
    if hit(r"\bhow many more\b|\bmore than\b|\bless than\b|\bdifference\b|\bfewer\b"):
        return "difference_comparison", "heuristic_medium"
    if hit(
        r"per minute|per hour|mph|times as|\bfast\b.*\brate|"
        r"\d+%\s+of|interest|doubled|twice as"
    ):
        return "rate_ratio", "heuristic_medium"
    if hit(
        r"each day|every week|first week|second week|after \d+|"
        r"monday|chronological|minutes for"
    ):
        return "temporal_change", "heuristic_medium"
    if hit(r"total\b|combined|altogether|all have|all \w+ combined"):
        return "multi_step_total", "heuristic_low"
    if hit(r"geometric|level of|sandcastle|square footage of a level"):
        return "geometry", "heuristic_low"
    return "unknown", "unknown"


def pick_scaffold(family: str) -> str:
    m = {
        "rate_ratio": "rate_table",
        "temporal_change": "before_after_state",
        "difference_comparison": "target_difference",
        "multi_step_total": "quantity_ledger",
        "unit_conversion": "quantity_ledger",
        "counting_combinatorics": "quantity_ledger",
        "average": "quantity_ledger",
        "money_budget": "quantity_ledger",
        "geometry": "least_to_most",
        "unknown": "unknown",
    }
    return m.get(family, "unknown")


def needs_flags(family: str, text: str) -> tuple[str, str, str, str, str]:
    """Return why_hypothesis, missing_step, scaffold, likely_needs_PAL, likely_needs_decomposition."""
    t = (text or "").lower()
    if family in {"rate_ratio", "money_budget", "multi_step_total", "counting_combinatorics", "unit_conversion", "average"}:
        pal = "yes"
    elif family in {"temporal_change", "difference_comparison", "geometry"}:
        pal = "no"
    else:
        pal = "unknown"

    if family in {"multi_step_total", "geometry", "difference_comparison", "rate_ratio", "money_budget", "temporal_change"}:
        decomp = "yes"
    elif family in {"unit_conversion", "counting_combinatorics", "average"}:
        decomp = "yes"
    else:
        decomp = "unknown"

    family_line = {
        "rate_ratio": "likely missing multi-step rate accounting or unit alignment before summing.",
        "temporal_change": "likely missing ordered state updates across time segments.",
        "difference_comparison": "likely confused target entity (A vs B vs total vs half/difference).",
        "multi_step_total": "likely dropped a quantity or mis-aggregated partial totals.",
        "unit_conversion": "likely inconsistent units across steps (ft/in, weeks/meals).",
        "counting_combinatorics": "likely mis-modeled partition constraints (equal groups + remainder).",
        "average": "likely averaged wrong set or skipped a layer in hierarchical counts.",
        "money_budget": "likely mis-modeled percent-of-total vs additive costs or change due.",
        "geometry": "likely mis-applied scaling (half each level) vs mean.",
        "unknown": "insufficient typed cues in available text; could be discovery or artifact gap.",
    }
    miss = {
        "rate_ratio": "normalize rates to common time/quantity, then accumulate.",
        "temporal_change": "explicit timeline with remaining resource after each event.",
        "difference_comparison": "label entities and restate exact quantity asked.",
        "multi_step_total": "full quantity checklist with running subtotal.",
        "unit_conversion": "conversion table and one base unit for all arithmetic.",
        "counting_combinatorics": "solve partition equations symbolically before rounding.",
        "average": "list layer sizes, then compute mean over correct denominator.",
        "money_budget": "money line items + verify percent base (subtotal vs total bill).",
        "geometry": "layer-by-layer sizes then combine for asked statistic.",
        "unknown": "human read of trace if/when available.",
    }
    scaffold = pick_scaffold(family)
    return family_line.get(family, ""), miss.get(family, ""), scaffold, pal, decomp


def hit(pat: str, t: str) -> bool:
    return re.search(pat, t, re.I) is not None


def recommended_family_prompt(scaffold: str) -> str:
    return {
        "rate_table": "numeric_leaf_rate_table_v1",
        "before_after_state": "numeric_leaf_timeline_v1",
        "target_difference": "numeric_leaf_target_restate_v1",
        "quantity_ledger": "numeric_leaf_quantity_ledger_v1",
        "least_to_most": "numeric_leaf_subquestion_decomp_v1",
        "PAL_program_first": "pal_program_then_boxed_v1",
        "direct_restatement": "numeric_leaf_plain_restate_v1",
        "unknown": "unspecified_pending_human_anchor",
    }.get(scaffold, "unspecified_pending_human_anchor")


def main() -> None:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = REPO / "outputs" / f"gold_absent_discovery_diagnosis_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    union_path = REPO / "outputs/latest_pal_external_loss_bank_20260508T004000Z/latest_pal_external_loss_union_by_case.csv"
    bank_path = REPO / "outputs/latest_pal_external_loss_bank_20260508T004000Z/latest_pal_external_loss_bank.csv"
    cluster_path = (
        REPO
        / "outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z/failure_cluster_summary.csv"
    )

    with union_path.open(encoding="utf-8") as f:
        union_rows = list(csv.DictReader(f))
    bank_by = load_csv_dict(bank_path, "case_id")
    cluster_by = load_csv_dict(cluster_path, "case_id") if cluster_path.is_file() else {}

    selected: list[tuple[str, dict[str, str]]] = []
    for row in union_rows:
        mech = row.get("gold_absent_or_present_not_selected") or ""
        if has_gold_absent_tag(mech):
            selected.append(("gold_absent_tagged", row))
        elif not mech.strip():
            selected.append(("mechanism_unknown_union", row))

    out_rows: list[dict[str, str]] = []
    for cohort, u in selected:
        cid = u["case_id"]
        b = bank_by.get(cid, {})
        cl = cluster_by.get(cid, {})
        text = u.get("problem_text") or b.get("problem_text") or ""
        cluster_hints = cl.get("operation_hint_tags") or ""
        family, conf = derive_family(text, cluster_hints)
        if cohort == "mechanism_unknown_union":
            family, conf = "unknown", "unknown"
        why, miss, scaffold, pal_n, decomp = needs_flags(family, text)
        if cohort == "mechanism_unknown_union":
            why = (
                "Union row left mechanism blank; recommended_next_track=reproduce_in_minimal_slice in source. "
                "May be non-GSM8K slice artifact or incomplete tagging — not assumed discovery without review."
            )
            miss = "manual trace review or skip for pilot until cohort membership confirmed."
            scaffold = "unknown"
            pal_n, decomp = "unknown", "unknown"

        ext_win = u.get("known_external_winners") or b.get("best_external_name") or ""
        tag = b.get("failure_tag") or u.get("known_failure_tags") or cl.get("failure_tag") or ""
        pattern = cl.get("failure_type") or ""

        out_rows.append(
            {
                "case_id": cid,
                "cohort": cohort,
                "source_artifacts": u.get("source_artifacts") or b.get("source_artifact") or "",
                "problem_text": text.replace("\n", " ").strip(),
                "gold_answer": u.get("gold_answer") or b.get("gold_answer") or "",
                "pal_prediction": u.get("best_available_pal_prediction") or b.get("pal_prediction") or "",
                "external_l1_prediction": b.get("external_l1_prediction") or "",
                "best_external_prediction": u.get("best_available_external_prediction")
                or b.get("external_l1_prediction")
                or "",
                "external_winner_names": ext_win,
                "original_failure_tag": tag,
                "existing_pattern_label": pattern,
                "derived_problem_family": family,
                "derivation_confidence": conf,
                "why_gold_absent_hypothesis": why,
                "missing_reasoning_step_hypothesis": miss,
                "candidate_retry_scaffold": scaffold,
                "likely_needs_PAL": pal_n if cohort != "mechanism_unknown_union" else "unknown",
                "likely_needs_decomposition": decomp if cohort != "mechanism_unknown_union" else "unknown",
                "recommended_retry_prompt_family": recommended_family_prompt(scaffold),
                "notes": "; ".join(
                    [
                        f"union_mech={u.get('gold_absent_or_present_not_selected') or '∅'}",
                        f"recommended_next_track={u.get('recommended_next_track') or ''}",
                    ]
                ),
            }
        )

    # CSV
    fieldnames = list(out_rows[0].keys()) if out_rows else []
    with (out_dir / "gold_absent_discovery_cases.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in out_rows:
            w.writerow(row)

    families = [r["derived_problem_family"] for r in out_rows if r["cohort"] == "gold_absent_tagged"]
    scaffolds = [r["candidate_retry_scaffold"] for r in out_rows if r["cohort"] == "gold_absent_tagged"]
    fc = Counter(families)
    sc = Counter(scaffolds)

    counts = {
        "total_union_rows_written": len(out_rows),
        "total_gold_absent_cases": sum(1 for r in out_rows if r["cohort"] == "gold_absent_tagged"),
        "mechanism_unknown_union_rows": sum(1 for r in out_rows if r["cohort"] == "mechanism_unknown_union"),
        "cases_with_problem_text": sum(1 for r in out_rows if (r.get("problem_text") or "").strip()),
        "rate_ratio": int(fc.get("rate_ratio", 0)),
        "temporal_change": int(fc.get("temporal_change", 0)),
        "difference_comparison": int(fc.get("difference_comparison", 0)),
        "multi_step_total": int(fc.get("multi_step_total", 0)),
        "unit_conversion": int(fc.get("unit_conversion", 0)),
        "counting_combinatorics": int(fc.get("counting_combinatorics", 0)),
        "average": int(fc.get("average", 0)),
        "money_budget": int(fc.get("money_budget", 0)),
        "geometry": int(fc.get("geometry", 0)),
        "unknown": int(fc.get("unknown", 0)),
        "recommended_rate_table": int(sc.get("rate_table", 0)),
        "recommended_before_after_state": int(sc.get("before_after_state", 0)),
        "recommended_target_difference": int(sc.get("target_difference", 0)),
        "recommended_quantity_ledger": int(sc.get("quantity_ledger", 0)),
        "recommended_least_to_most": int(sc.get("least_to_most", 0)),
        "recommended_PAL_program_first": 0,
        "recommended_direct_restatement": 0,
        "recommended_unknown_scaffold": int(sc.get("unknown", 0)),
        "source_union_csv": str(union_path.relative_to(REPO)),
        "notes": {
            "bank_mechanism_json_still_reports_36": "Union+bank both show 37 rows with gold_absent_discovery=yes; "
            "mechanism_counts.json in loss bank may round/dedupe dual-tagged rows.",
            "unknown_union": "11 low-ID GSM8K-style case_ids tagged for minimal-slice reproduction; "
            "not auto-classified as discovery.",
        },
    }
    (out_dir / "mechanism_counts.json").write_text(json.dumps(counts, indent=2), encoding="utf-8")

    # Anchors: pick from gold_absent_tagged with L1 win and text
    def _anchor_prio(r: dict[str, str]) -> int:
        w = r.get("external_winner_names") or ""
        return 0 if "external_l1_max" in w else 1

    anchors_pool = [
        r
        for r in out_rows
        if r["cohort"] == "gold_absent_tagged"
        and (r.get("problem_text") or "").strip()
        and (r.get("gold_answer") or "").strip()
    ]
    by_f: dict[str, list[dict[str, str]]] = {}
    for r in anchors_pool:
        by_f.setdefault(r["derived_problem_family"], []).append(r)

    chosen: list[dict[str, str]] = []
    for fam, lst in sorted(by_f.items(), key=lambda x: -len(x[1])):
        lst.sort(key=lambda r: (_anchor_prio(r), len(r.get("problem_text") or "")))
        need = 3 if len(lst) >= 3 else max(1, min(2, len(lst)))
        chosen.extend(lst[:need])

    # Cap 18 anchors, prefer diversity
    seen = set()
    final_anchors: list[dict[str, str]] = []
    for r in chosen:
        if r["case_id"] in seen:
            continue
        seen.add(r["case_id"])
        final_anchors.append(r)
    final_anchors = final_anchors[:18]

    lines = [
        "# Gold-absent discovery — anchor cases",
        "",
        f"Generated from `{out_dir.relative_to(REPO)}`. One paragraph per case (problem summary is abbreviated).",
        "",
    ]
    for r in final_anchors:
        cid = r["case_id"]
        g = r["gold_answer"]
        p = r["pal_prediction"][:40] + ("..." if len(r["pal_prediction"]) > 40 else "")
        ext = (r.get("external_l1_prediction") or r.get("best_external_prediction") or "")[:40]
        txt = (r.get("problem_text") or "")[:200].replace("\n", " ")
        lines.append(
            f"## {cid}\n\n"
            f"**Summary:** {txt}...\n\n"
            f"**Gold** {g} vs **PAL** {p} vs **external (L1/best)** {ext}. "
            f"**Hypothesis:** {r['why_gold_absent_hypothesis']} "
            f"**Scaffold:** {r['candidate_retry_scaffold']} ({r['recommended_retry_prompt_family']}).\n"
        )

    (out_dir / "anchor_cases.md").write_text("\n".join(lines), encoding="utf-8")

    policy = """# Proposed discovery retry policy v1 (gold-free scaffolds)

Grounded in PAL vs external losses where the correct numeric never appeared in the explored tree
(`gold_absent_discovery`). These are **prompt / decomposition** retries, not consensus.

## A. `rate_table` scaffold

- **Trigger signals (no gold):** phrases like *per minute*, *% of total*, *twice as fast*, parallel rates,
  or strong disagreement between branches on a ratio line while magnitudes differ by orders (see e.g. clog-dance rate case).
- **Procedure:** list entities, units, baseline interval, then one equation per row; sum only after
  converting to a common time/quantity base.
- **Budget cost:** ~1 extra direct or PAL-backed synthesis call if PAL used only for final arithmetic.
- **Target families:** `rate_ratio`, parts of `money_budget` with percentages on total.
- **Risks:** over-fitting to bogus rates parsed from text; needs abstain if units stay ambiguous.
- **Example anchors:** `openai_gsm8k_1125`, `openai_gsm8k_1003`, `openai_gsm8k_1099`.

## B. `before_after_state` scaffold

- **Trigger signals:** multi-day/week story, sequential *spills/consumption*, *first half/second half* of month.
- **Procedure:** single state vector per day/phase; apply deltas in chronological order; answer is last phase
  or comparison across phases.
- **Budget cost:** ~1 call; can share with structural commit path (no interaction yet).
- **Target families:** `temporal_change`.
- **Risks:** calendar edge cases (15 vs 14 days); keep explicit day index.
- **Example anchors:** `openai_gsm8k_1166`, `openai_gsm8k_1198`, `openai_gsm8k_773`.

## C. `target_difference` scaffold

- **Trigger signals:** *how many more*, *half the total*, *difference between*, multi-actor eggs/pencils.
- **Procedure:** name A/B/total; restate **exact** target (“half of combined spots” vs “spots on one species”).
- **Budget cost:** ~1 short rewrite + one solve.
- **Target families:** `difference_comparison`, tricky wordings in `multi_step_total`.
- **Risks:** doubling/halving wrong layer; abstain if question has nested quantifiers without clear referent.
- **Example anchors:** `openai_gsm8k_1099`, `openai_gsm8k_1187`, `openai_gsm8k_1248`.

## D. `quantity_ledger` scaffold

- **Trigger signals:** many numeric literals, `% off then multi-buy`, jelly-bean mix, rice consumption.
- **Procedure:** table: quantity | meaning | consumed? | equation slot.
- **Budget cost:** 1–2 calls if PAL used for execution after ledger.
- **Target families:** `money_budget`, `unit_conversion`, `multi_step_total`, `average`.
- **Risks:** ledger explosion; cap rows or merge duplicates.
- **Example anchors:** `openai_gsm8k_1006`, `openai_gsm8k_1019`, `openai_gsm8k_1027`.

## E. `PAL_program_first` scaffold

- **Trigger signals:** ledger already stable but repeated arithmetic errors; PAL stdout historically unreliable.
- **Procedure:** emit Python from ledger, print single numeric, `\boxed{}`.
- **Budget cost:** +1 PAL slot (already modeled in budget-6 PAL runs).
- **Target families:** `money_budget`, dense `rate_ratio`, `counting_combinatorics`.
- **Risks:** code drift from story; validator should check units/dimensions symbolically when possible.
- **Example anchors:** `openai_gsm8k_750`, `openai_gsm8k_769`, `openai_gsm8k_752`.

## F. `least_to_most` scaffold

- **Trigger signals:** nested textual conditions (lines of song vs scenes), hierarchical geometric levels.
- **Procedure:** ordered subquestions with intermediate answers; final restatement of target quantity.
- **Budget cost:** 1 chain-of-subquestions call (may substitute for an expand slot, not add infinitely).
- **Target families:** `geometry`, deep `multi_step_total`.
- **Risks:** verbosity; pair with short final numeric-only pass.
- **Example anchors:** `openai_gsm8k_1230`, `openai_gsm8k_1281`, `openai_gsm8k_1215`.
"""
    (out_dir / "proposed_discovery_retry_policy_v1.md").write_text(policy, encoding="utf-8")

    budget6 = """# Discovery retry — budget-6 integration plan

Budget **6** is tight; avoid broad self-consistency. Use **one** targeted retry slot when structural
commitment does not apply (no present-not-selected fix) and the run is in the **gold-absent** regime.

## Interaction with `structural_commit_v1`

1. Structural commit runs **after** PAL channel merge (existing order). It repairs commitment/surfacing,
   not missing discovery.
2. If structural abstains **and** answer-group support shows a single weak leaf with no peer agreement,
   mark candidate for **discovery retry** (gold-free proxy: low support diversity + PAL-external mismatch
   in historical bank patterns — implementation TBD).
3. Never spend discovery retry **only** to duplicate structural’s channel; they are orthogonal.

## When to abstain

- Minimal text or unit ambiguity persists after restatement.
- Scaffold triggers disagree (e.g. both rate_table and timeline match); prefer abstain over double retry.

## When to spend extra call

- Exactly **one** scaffold fired with high confidence (mechanism tag or heuristic ≥ medium).
- External reference in offline bank suggests gold existed but tree lacked it (discovery hypothesis).

## When **not** to retry

- Present-not-selected pattern with gold in pool (Track B / structural jurisdiction).
- Known `reproduce_in_minimal_slice` rows without full GSM8K problem text in union.

---

## Schedule A — conservative fixed retry

- Slot 5 or 6 (last expand): if `discovery_eligible` flag set from offline bank features or live
  emptiness signal, run **one** scaffold matching derived family (from lightweight keyword router).
- Cost: **+0** to base if it replaces a generic diversity expand; **+1** if added (must drop a weak expand).

## Schedule B — adaptive last-slot

- Hold last slot until frontier summary is built.
- Trigger retry only if: normalized answer groups ≥2 with tie/near-tie **or** validator/PAL-exec failure
  on incumbent — AND scaffold trigger present.
- Cost: usually **0** net (swap), occasional **1** when frontier collapsed early.

**Recommendation for pilots:** start with **Schedule A** on a frozen list of ~37 gold-absent IDs;
measure harm on PNS + structural guardrails before Schedule B.
"""
    (out_dir / "discovery_retry_budget6_plan.md").write_text(budget6, encoding="utf-8")

    ga_ids = sorted({r["case_id"] for r in out_rows if r["cohort"] == "gold_absent_tagged"})
    guard_path = REPO / "outputs/structural_commit_v1_replay_20260508T120000Z/structural_commit_v1_replay_cases.csv"
    guard_ids: list[str] = []
    if guard_path.is_file():
        with guard_path.open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if str(row.get("cohort", "")).startswith("guardrail"):
                    guard_ids.append(row["case_id"])
    exp = f"""# Discovery retry — experiment / replay plan

## Proposed method id

`direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal_structural_commit_v1_targeted_retry_v1`

## Positive targets (gold-absent union)

Exact case_ids ({len(ga_ids)}):

```
{", ".join(ga_ids)}
```

## Guardrail cases (avoid regressions)

- **Structural commit v1 replay guardrails:** {len(guard_ids)} rows from
  `outputs/structural_commit_v1_replay_20260508T120000Z/structural_commit_v1_replay_cases.csv`
  (`guardrail_*` cohorts). Any new retry must keep **0** correct→wrong flips on that set offline.
- **Present-not-selected fixed anchors:** continue to monitor `openai_gsm8k_1087`, `1279`, `1290`.

## Dry-run / offline first

- **Yes:** keyword scaffold router + manifest-only dry run using `problem_text` from union/bank CSV
  (no API): emit `planned_scaffold`, slot consumption, estimated tokens (rough).
- **No HF / no Cohere** for offline manifests.

## When Cohere API is needed

- After offline manifest review: **one** capped pilot on a 10–15 case anchor subset per family
  to measure real win rate and guardrail harm.

## Proposed manifest fields (pre-API)

- `case_id`, `source_artifact`, `derived_problem_family`, `derivation_confidence`
- `candidate_retry_scaffold`, `recommended_retry_prompt_family`
- `budget_schedule` (A or B), `slot_index`, `replaced_action_kind`
- `structural_commit_applied` (bool), `discovery_retry_eligible` (bool), `abstain_reason`

## Metrics

- Gold-absent primary: exact-match delta vs baseline PAL method on frozen 37-case list.
- Secondary: average tokens, scaffold distribution, guardrail flip count (must stay 0 initially).
"""
    (out_dir / "discovery_retry_experiment_plan.md").write_text(exp, encoding="utf-8")

    print(out_dir)


if __name__ == "__main__":
    main()
