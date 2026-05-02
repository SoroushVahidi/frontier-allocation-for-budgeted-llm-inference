#!/usr/bin/env python3
"""Strategy-seeded discovery final check: case alignment, Slice1/Slice2, v2_final Cohere run, comparisons.

Produces outputs under outputs/strategy_seeded_discovery_final_check_<UTC>/ plus optional standalone audit folder.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.data import normalize_answer_text  # noqa: E402

METHOD_NEW = "direct_reserve_strategy_seeded_semantic_frontier_v2_final"
BASELINE_METHOD = "direct_reserve_semantic_frontier_v2"
METHOD_V1 = "strategy_seeded_semantic_diversity_frontier_v1"

DEFAULT_PATH_GAP = REPO_ROOT / "outputs/gold_absent_path_gap_diagnostic_20260502T215957Z/per_case_path_gap_diagnostic.csv"
DEFAULT_STILL_LOST = REPO_ROOT / "outputs/full_score_completed_best_selector_on_88_external_losses_20260502T213834Z/still_lost_cases.csv"
DEFAULT_SELECTOR = REPO_ROOT / "outputs/full_score_completed_best_selector_on_88_external_losses_20260502T213834Z/per_case_results.csv"
DEFAULT_BASELINE = REPO_ROOT / "outputs/cohere_real_model_cost_normalized_validation_20260502T210610Z_DISCOVERY/per_example_records.jsonl"
DEFAULT_PREV_RUN = REPO_ROOT / "outputs/strategy_seeded_discovery_on_66_gold_absent_20260502T222129Z/per_case_discovery_results.csv"
DEFAULT_SELECTED_100 = REPO_ROOT / "outputs/best_methods_on_external_losses_20260430T195200Z/selected_100_cases.csv"


def norm_ans(t: Any) -> str:
    try:
        return str(normalize_answer_text(str(t or "").strip()).get("normalized_answer") or "").strip().lower()
    except Exception:
        return str(t or "").strip().lower()


def tri(x: Any) -> int | None:
    try:
        if x is None or str(x).strip() == "":
            return None
        return int(float(x))
    except (TypeError, ValueError):
        return None


def load_rows_path_gap(path: Path, still_lost: Path, selected: Path) -> list[dict[str, Any]]:
    from scripts.run_strategy_seeded_discovery_on_66_gold_absent import load_rows_from_path_gap

    return load_rows_from_path_gap(path, still_lost, selected)


def load_rows_csv_dict(path: Path) -> dict[str, dict[str, Any]]:
    if not path.is_file():
        return {}
    out: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8", newline="") as fp:
        for row in csv.DictReader(fp):
            ds = str(row.get("dataset") or "").strip()
            ex = str(row.get("example_id") or "").strip()
            try:
                seed = int(row.get("seed"))
                budget = int(row.get("budget"))
            except (TypeError, ValueError):
                continue
            k = case_key(ds, ex, seed, budget)
            out[k] = row
    return out


def case_key(ds: str, ex: str, seed: int, budget: int) -> str:
    return f"{ds}::{ex}::{seed}::{budget}"


def load_baseline_records(path: Path) -> dict[str, dict[str, Any]]:
    by_k: dict[str, dict[str, Any]] = {}
    if not path.is_file():
        return by_k
    with path.open(encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if str(r.get("method", "")) != BASELINE_METHOD:
                continue
            k = case_key(str(r["dataset"]), str(r["example_id"]), int(r["seed"]), int(r["budget"]))
            by_k[k] = r
    return by_k


def gold_in_pool(md: dict[str, Any], gold: str) -> bool:
    g = norm_ans(gold)
    if not g:
        return False
    pool = md.get("selector_candidate_pool")
    if not isinstance(pool, list):
        return False
    for c in pool:
        if not isinstance(c, dict):
            continue
        cand = norm_ans(c.get("normalized_answer") or c.get("predicted_answer"))
        if cand == g:
            return True
    return False


def gold_in_tree(md: dict[str, Any], gold: str) -> bool:
    g = norm_ans(gold)
    if not g:
        return False
    fbs = md.get("final_branch_states")
    if not isinstance(fbs, list):
        return False
    for s in fbs:
        if not isinstance(s, dict):
            continue
        if norm_ans(s.get("predicted_answer")) == g:
            return True
    return False


def strategy_prompt_audit_rows(md: dict[str, Any]) -> dict[str, Any]:
    dra = md.get("direct_reserve_attempts")
    roots: Counter[str] = Counter()
    n_actions = 0
    max_seed_idx = -1
    digs: list[str] = []
    if isinstance(dra, list):
        for ev in dra:
            if not isinstance(ev, dict):
                continue
            fam = str(ev.get("root_strategy_family") or ev.get("prompt_family_id") or "")
            if fam:
                roots[fam] += 1
            try:
                max_seed_idx = max(max_seed_idx, int(ev.get("strategy_seed_index", -1)))
            except (TypeError, ValueError):
                pass
            n_actions += 1
            dg = ev.get("prompt_digest")
            if dg:
                digs.append(str(dg))
    return {
        "root_strategy_family_count": len(roots),
        "root_families_seen": ",".join(sorted(roots.keys())),
        "distinct_prompt_digests": len(set(digs)),
        "mean_actions_per_attempt_trace": float(n_actions / max(1, max_seed_idx + 1)),
        "trace_action_count": n_actions,
    }


def refined_summarize(rows: list[dict[str, Any]], new_by_k: dict[str, dict[str, Any]], base_by_k: dict[str, dict[str, Any]]) -> dict[str, Any]:
    b_pool = b_tree = f_pool = f_tree = 0
    recovered = newly_lost = still_abs = 0
    token_tot = 0
    audits: list[dict[str, Any]] = []
    gates = Counter()
    for r in rows:
        k = case_key(r["dataset"], r["example_id"], r["seed"], r["budget"])
        gold = str(r.get("gold_answer_canonical_hint") or r.get("gold_answer") or "").strip()
        br = base_by_k.get(k)
        nr = new_by_k.get(k)
        bf_pool = bf_tree = False
        if br:
            md0 = dict(br.get("result_metadata") or {})
            bf_pool = gold_in_pool(md0, gold)
            bf_tree = gold_in_tree(md0, gold)
        gf_pool = gf_tree = False
        if nr:
            md1 = dict(nr.get("result_metadata") or {})
            gf_pool = gold_in_pool(md1, gold)
            gf_tree = gold_in_tree(md1, gold)
            token_tot += int(nr.get("total_tokens") or 0)
            audits.append(strategy_prompt_audit_rows(md1))
            aud = md1.get("strategy_seeded_v2_final_audit") or {}
            if isinstance(aud, dict):
                for gk in (
                    "semantic_gate_intervention_count",
                    "strategy_protection_intervention_count",
                    "redundant_strategy_expansion_avoided_count",
                    "underrepresented_strategy_expansion_count",
                ):
                    gates[gk] += int(aud.get(gk) or 0)
        if br:
            b_pool += int(bf_pool)
            b_tree += int(bf_tree)
        if nr:
            f_pool += int(gf_pool)
            f_tree += int(gf_tree)
        if bf_pool and not gf_pool:
            newly_lost += 1
        if (not bf_pool) and gf_pool:
            recovered += 1
        if (not bf_pool) and (not gf_pool):
            still_abs += 1

    def _avg(key: str) -> float:
        vs = [float(a.get(key) or 0) for a in audits]
        return float(mean(vs)) if vs else 0.0

    denom_absent_pool = sum(
        1
        for r in rows
        if base_by_k.get(case_key(r["dataset"], r["example_id"], r["seed"], r["budget"]))
        and not gold_in_pool(
            dict(base_by_k[case_key(r["dataset"], r["example_id"], r["seed"], r["budget"])].get("result_metadata") or {}),
            str(r.get("gold_answer_canonical_hint") or r.get("gold_answer") or ""),
        )
    )

    out = {
        "n_cases_in_slice": len(rows),
        "n_cases_with_baseline_record": sum(1 for r in rows if base_by_k.get(case_key(r["dataset"], r["example_id"], r["seed"], r["budget"]))),
        "baseline_gold_present_in_candidate_groups": b_pool,
        "final_new_gold_present_in_candidate_groups": f_pool,
        "delta_gold_present_in_candidate_groups": f_pool - b_pool,
        "baseline_gold_present_in_tree": b_tree,
        "final_new_gold_present_in_tree": f_tree,
        "delta_gold_present_in_tree": f_tree - b_tree,
        "discovery_recovered_count": recovered,
        "discovery_recovery_rate": float(recovered / max(1, denom_absent_pool)),
        "newly_lost_gold_present_count": newly_lost,
        "still_gold_absent_count": still_abs,
        "denominator_discovery_absent_pool": denom_absent_pool,
        "strict_baseline_gold_absent_slice_size": denom_absent_pool,
        "mean_candidate_group_hint": _avg("root_strategy_family_count"),
        "mean_strategy_families_trace": _avg("root_strategy_family_count"),
        "mean_semantic_family_count_placeholder": _avg("distinct_prompt_digests"),
        "mean_actions_used_proxy": _avg("trace_action_count"),
        "strategy_family_coverage_rate": _avg("root_strategy_family_count"),
        "total_tokens_new_method": token_tot,
    }
    out.update({f"sum_{k}": int(v) for k, v in gates.items()})
    return out


def _strict_absent_base(r: dict[str, Any], base_by_k: dict[str, dict[str, Any]]) -> bool:
    k = case_key(r["dataset"], r["example_id"], r["seed"], r["budget"])
    gold = str(r.get("gold_answer_canonical_hint") or r.get("gold_answer") or "").strip()
    br = base_by_k.get(k)
    if not br:
        return False
    md0 = dict(br.get("result_metadata") or {})
    return (not gold_in_pool(md0, gold)) and (not gold_in_tree(md0, gold))


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    p.add_argument("--path-gap-csv", type=Path, default=DEFAULT_PATH_GAP)
    p.add_argument("--still-lost-csv", type=Path, default=DEFAULT_STILL_LOST)
    p.add_argument("--selected-100-csv", type=Path, default=DEFAULT_SELECTED_100)
    p.add_argument("--baseline-jsonl", type=Path, default=DEFAULT_BASELINE)
    p.add_argument("--selector-per-case-csv", type=Path, default=DEFAULT_SELECTOR)
    p.add_argument("--previous-v1-csv", type=Path, default=DEFAULT_PREV_RUN)
    p.add_argument("--output-root", type=Path, default=REPO_ROOT / "outputs")
    p.add_argument("--ceil-generations", type=int, default=8000, help="Abort if upper-bound gen actions exceed this.")
    p.add_argument("--cohere-timestamp", default="", help="Timestamp tag for nested cohere run directory.")
    p.add_argument("--skip-cohere", action="store_true")
    p.add_argument("--preflight-only", action="store_true")
    p.add_argument("--audit-only", action="store_true", help="Write outputs/strategy_seeded_final_audit_<ts> and exit.")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    out_final = args.output_root / f"strategy_seeded_discovery_final_check_{args.timestamp}"
    out_audit = args.output_root / f"strategy_seeded_final_audit_{args.timestamp}"
    out_final.mkdir(parents=True, exist_ok=True)
    if args.audit_only:
        out_audit.mkdir(parents=True, exist_ok=True)

    cases = load_rows_path_gap(args.path_gap_csv, args.still_lost_csv, args.selected_100_csv)
    print(f"[slice] diagnostic_cohort_cases={len(cases)}", file=sys.stderr)
    base_by_k = load_baseline_records(args.baseline_jsonl)
    sel_by_k = load_rows_csv_dict(args.selector_per_case_csv)
    prev_by_k = load_rows_csv_dict(args.previous_v1_csv)

    strict_rows = [r for r in cases if _strict_absent_base(r, base_by_k)]
    print(f"[slice] strict_baseline_dr_v2_absent_cases={len(strict_rows)}", file=sys.stderr)

    pg_map: dict[str, dict[str, Any]] = {}
    if args.path_gap_csv.is_file():
        with args.path_gap_csv.open(encoding="utf-8", newline="") as fp:
            for row in csv.DictReader(fp):
                try:
                    kk = case_key(row["dataset"], row["example_id"], int(row["seed"]), int(row["budget"]))
                    pg_map[kk] = row
                except (KeyError, TypeError, ValueError):
                    continue

    alignment: list[dict[str, Any]] = []
    for r in cases:
        k = case_key(r["dataset"], r["example_id"], r["seed"], r["budget"])
        gold = str(r.get("gold_answer_canonical_hint") or r.get("gold_answer") or "").strip()
        pg = pg_map.get(k, {})
        br = base_by_k.get(k)
        md_b = dict(br.get("result_metadata") or {}) if br else {}
        row_sel = sel_by_k.get(k, {})
        pv = prev_by_k.get(k, {})

        g_grp_pg = tri(pg.get("gold_present_in_candidate_groups"))
        g_tree_pg = tri(pg.get("gold_present_in_tree"))
        d_abs = tri(pg.get("discovery_failure_gold_absent"))

        def _tri_col(d: dict[str, Any], a: str, b: str) -> tuple[int | None, int | None]:
            return tri(d.get(a)), tri(d.get(b))

        g_grp_sel, g_tree_sel = _tri_col(row_sel, "gold_present_in_candidate_groups", "gold_present_in_tree")
        if not row_sel.get("gold_present_in_candidate_groups") and not row_sel.get("gold_present_in_tree"):
            g_grp_sel = g_tree_sel = None

        b_pool = gold_in_pool(md_b, gold) if br else None
        b_tree = gold_in_tree(md_b, gold) if br else None

        pv_pool = tri(pv.get("new_gold_present_in_selector_pool")) if pv.get("new_gold_present_in_selector_pool") is not None else tri(pv.get("gold_present_in_selector_pool"))
        pv_tree = tri(pv.get("new_gold_present_in_tree")) if pv.get("new_gold_present_in_tree") is not None else tri(pv.get("gold_present_in_tree"))

        mismatch_reason = ""
        if g_grp_pg is not None and b_pool is not None:
            if bool(g_grp_pg) != bool(b_pool):
                mismatch_reason = "path_gap_groups_vs_baseline_selector_pool_mismatch"
        elif not br:
            mismatch_reason = "missing_baseline_record"

        alignment.append(
            {
                "case_key": k,
                "dataset": r["dataset"],
                "example_id": r["example_id"],
                "seed": r["seed"],
                "budget": r["budget"],
                "gold_answer": gold,
                "gold_present_in_candidate_groups_path_gap": g_grp_pg,
                "gold_present_in_tree_path_gap": g_tree_pg,
                "discovery_failure_gold_absent_path_gap": d_abs,
                "gold_present_in_candidate_groups_selector_csv": g_grp_sel,
                "gold_present_in_tree_selector_csv": g_tree_sel,
                "gold_present_in_selector_pool_baseline_jsonl": int(b_pool) if b_pool is not None else "",
                "gold_present_in_final_branch_states_baseline_jsonl": int(b_tree) if b_tree is not None else "",
                "previous_v1_gold_in_pool": pv_pool,
                "previous_v1_gold_in_tree": pv_tree,
                "definitions_agree-ish": mismatch_reason == "",
                "mismatch_reason": mismatch_reason,
                "strict_baseline_absent": int(_strict_absent_base(r, base_by_k)),
            }
        )

    # --- write lists ---
    with (out_final / "original_66_case_list.csv").open("w", encoding="utf-8", newline="") as fp:
        w = csv.DictWriter(fp, fieldnames=["dataset", "example_id", "seed", "budget", "gold_answer_canonical_hint"])
        w.writeheader()
        for r in cases:
            w.writerow(
                {
                    "dataset": r["dataset"],
                    "example_id": r["example_id"],
                    "seed": r["seed"],
                    "budget": r["budget"],
                    "gold_answer_canonical_hint": r.get("gold_answer_canonical_hint", ""),
                }
            )

    with (out_final / "strict_baseline_gold_absent_case_list.csv").open("w", encoding="utf-8", newline="") as fp:
        w = csv.DictWriter(fp, fieldnames=["dataset", "example_id", "seed", "budget", "gold_answer_canonical_hint"])
        w.writeheader()
        for r in strict_rows:
            w.writerow(
                {
                    "dataset": r["dataset"],
                    "example_id": r["example_id"],
                    "seed": r["seed"],
                    "budget": r["budget"],
                    "gold_answer_canonical_hint": r.get("gold_answer_canonical_hint", ""),
                }
            )

    with (out_final / "case_alignment_audit.csv").open("w", encoding="utf-8", newline="") as fp:
        if alignment:
            w = csv.DictWriter(fp, fieldnames=list(alignment[0].keys()))
            w.writeheader()
            w.writerows(alignment)
    with (out_final / "case_alignment_audit.jsonl").open("w", encoding="utf-8") as fp:
        for row in alignment:
            fp.write(json.dumps(row) + "\n")

    upper_bound_calls = sum(int(r["budget"]) for r in cases)
    write_json(
        out_final / "audit_summary.json",
        {
            "slice1_original_diagnostic_rows": len(cases),
            "slice2_strict_baseline_absent_rows": len(strict_rows),
            "path_gap_csv": str(args.path_gap_csv),
            "baseline_jsonl": str(args.baseline_jsonl),
            "upper_bound_generation_like_actions": upper_bound_calls,
            "parity_note": "Path-gap cohort used OR-filter vs discovery_failure gold_absent flags; Slice2 matches baseline DR-v2 JSONL selector_candidate_pool ∩ final_branch_states gold absence.",
            "mismatch_rows_path_gap_vs_baseline_pool": sum(
                1 for a in alignment if a.get("mismatch_reason") == "path_gap_groups_vs_baseline_selector_pool_mismatch"
            ),
            "missing_baseline_rows": sum(1 for a in alignment if a.get("mismatch_reason") == "missing_baseline_record"),
        },
    )

    impl_md = """# Implementation audit (v1 pilot + v2_final design)

## strategy_seeded_semantic_diversity_frontier_v1 (pilot)

- Overrides `_run_direct_attempt` only; caps each root strategy seed via `strategy_seed_max_actions=1`, so attempted depth per strategy was shallow even when `per_attempt_cap` from token budget was ~8.
- Parent `DirectReserveFrontierGateController` still plans up to five direct reserve indices, but each call to `super()._run_direct_attempt` was limited to one expand — **prompt styles differ** (from `direct_prompt_styles`) but **depth was not**.
- `direct_reserve_plus_diverse_kwargs` sets `gate_*` thresholds to **2.0 / -1.0**, so `incumbent_uncertain` is effectively always true when any budget remains; frontier engagement is not strongly gated by direct-stage entropy in this configuration.
- Diagnostic inner controller enabled `diagnostic_semantic_maturation` — useful logging, not a substitute for post-hoc label alignment.

## direct_reserve_strategy_seeded_semantic_frontier_v2_final

- Replaces direct prompt construction to inject each `ROOT_STRATEGY_FAMILY_SPECS` suffix into the literal `expand` prompt (strategy-controlled, not tag-only).
- Budget-aware alternate count (+ deterministic SHA256(question) permutation). Optional early stop hook after seed 0 when multi-step intra-seed extracts agree (`DirectReserveFrontierGateController._stop_additional_direct_reserve_after_attempt`).
- Increased per-seed expands when `budget - reserve_for_frontier` allows (`strategy_seed_min_actions`, `_per_seed_max_actions`).
- Inner `GlobalDiversityAggregationController` inherits strict_f3 with **raised** `duplicate_penalty` / `repeat_expand_family_penalty_weight` as deterministic allocation pressure; telemetry fields forwarded into semantic gate counters in `strategy_seeded_v2_final_audit`.

Gold is used only inside `generator.expand`/evaluation surfaces consistent with DR-v2 baselines — **never** appended to displayed strategy prompts in v2_final.
"""
    (out_final / "implementation_audit.md").write_text(impl_md, encoding="utf-8")

    prev_interp = """# Previous pilot reinterpretation

The diagnostic CSV cohort for the 66-case slice **does not coincide** with "gold absent everywhere" under a single definition:

- Loader used `discovery_failure_gold_absent OR gold_present_in_candidate_groups==0 OR gold_present_in_tree==0`, which admits cases that are absent in tree but present in pooled candidates (or inconsistent path-gap-derived groups vs post-hoc `selector_candidate_pool` on baseline JSONL).
- Baseline headline counts (gold in DR-v2 `selector_candidate_pool` / reconstructed pool) therefore can be **much higher** than a strict "never appeared in baseline discovery artifact" cohort.

Use **Slice 2 strict baseline-absent** (this script emits `strict_baseline_gold_absent_case_list.csv`) as the equitable discovery-centric evaluation set.
"""
    (out_final / "previous_result_reinterpretation.md").write_text(prev_interp, encoding="utf-8")

    write_json(
        out_final / "manifest.json",
        {"timestamp": args.timestamp, "repo_root": str(REPO_ROOT), "cases": len(cases), "strict_slice": len(strict_rows)},
    )
    write_json(
        out_final / "run_config.json",
        {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()},
    )

    print(f"upper_bound_generation_like_actions={upper_bound_calls}")
    if upper_bound_calls > args.ceil_generations:
        raise SystemExit(f"Estimated actions {upper_bound_calls} exceed ceiling {args.ceil_generations}")

    if args.preflight_only:
        write_json(out_final / "batch_submission_info.json", {"preflight_only": True})
        print(f"Preflight artifacts under {out_final}")
        return

    if args.audit_only:
        import shutil

        shutil.copytree(out_final, out_audit, dirs_exist_ok=True)
        print(f"Audit bundle copy: {out_audit}")
        return

    new_by_k: dict[str, dict[str, Any]] = {}

    if args.skip_cohere:
        write_json(out_final / "comparison_vs_dr_v2.json", {"note": "skip_cohere"})
    else:
        cohere_ts = args.cohere_timestamp or f"FINCHK_{args.timestamp}"
        allowed_path = out_final / "allowed_cases_v2_final.jsonl"
        with allowed_path.open("w", encoding="utf-8") as fp:
            for r in cases:
                fp.write(
                    json.dumps(
                        {
                            "dataset": r["dataset"],
                            "example_id": r["example_id"],
                            "seed": int(r["seed"]),
                            "budget": int(r["budget"]),
                            "method": METHOD_NEW,
                            "our_method_name": METHOD_NEW,
                        }
                    )
                    + "\n"
                )
        ds_set = sorted({r["dataset"] for r in cases})
        bd_set = sorted({int(r["budget"]) for r in cases})
        sd_set = sorted({int(r["seed"]) for r in cases})
        cmd = [
            sys.executable,
            str(REPO_ROOT / "scripts/run_cohere_real_model_cost_normalized_validation.py"),
            "--timestamp",
            cohere_ts,
            "--methods",
            METHOD_NEW,
            "--providers",
            "cohere",
            "--datasets",
            ",".join(ds_set),
            "--budgets",
            ",".join(str(b) for b in bd_set),
            "--seeds",
            ",".join(str(s) for s in sd_set),
            "--target-scored-per-slice",
            str(max(120, len(cases))),
            "--max-examples",
            str(max(120, len(cases))),
            "--allowed-example-ids-file",
            str(allowed_path),
            "--output-root",
            str(REPO_ROOT / "outputs"),
        ]
        write_json(out_final / "cohere_invoke_command.json", {"argv": cmd})
        subprocess.run(cmd, check=True)
        jl = REPO_ROOT / "outputs" / f"cohere_real_model_cost_normalized_validation_{cohere_ts}" / "per_example_records.jsonl"
        if jl.is_file():
            with jl.open(encoding="utf-8") as fp:
                for line in fp:
                    line = line.strip()
                    if not line:
                        continue
                    rec = json.loads(line)
                    if str(rec.get("method")) != METHOD_NEW:
                        continue
                    kk = case_key(rec["dataset"], rec["example_id"], int(rec["seed"]), int(rec["budget"]))
                    new_by_k[kk] = rec

    # per-case enrichment
    def emit_per_case(which: list[dict[str, Any]], name: str) -> None:
        rows_out: list[dict[str, Any]] = []
        for r in which:
            k = case_key(r["dataset"], r["example_id"], r["seed"], r["budget"])
            gold = str(r.get("gold_answer_canonical_hint") or "").strip()
            br = base_by_k.get(k)
            nr = new_by_k.get(k)
            md_b = dict(br.get("result_metadata") or {}) if br else {}
            md_n = dict(nr.get("result_metadata") or {}) if nr else {}
            bf_p = gold_in_pool(md_b, gold) if br else None
            bf_t = gold_in_tree(md_b, gold) if br else None
            nf_p = gold_in_pool(md_n, gold) if nr else None
            nf_t = gold_in_tree(md_n, gold) if nr else None
            spa = strategy_prompt_audit_rows(md_n) if nr else {}
            audit = md_n.get("strategy_seeded_v2_final_audit") if nr else {}
            row_out: dict[str, Any] = {
                **r,
                "baseline_gold_in_selector_pool": int(bf_p) if bf_p is not None else "",
                "baseline_gold_in_tree": int(bf_t) if bf_t is not None else "",
                "new_gold_in_selector_pool": int(nf_p) if nf_p is not None else "",
                "new_gold_in_tree": int(nf_t) if nf_t is not None else "",
                "budget_row": nr.get("budget") if nr else "",
                "estimated_actions_ceiling": int(nr["budget"]) if nr else "",
                **{f"a_{k}": v for k, v in spa.items()},
            }
            if isinstance(audit, dict):
                for sk in (
                    "semantic_gate_intervention_count",
                    "strategy_protection_intervention_count",
                    "redundant_strategy_expansion_avoided_count",
                    "underrepresented_strategy_expansion_count",
                    "budget",
                    "distinct_prompt_digests_in_trace",
                ):
                    if sk in audit:
                        row_out[f"v2_{sk}"] = audit.get(sk)
            rows_out.append(row_out)
        out_p = out_final / f"per_case_results_{name}.csv"
        if rows_out:
            with out_p.open("w", encoding="utf-8", newline="") as fp:
                w = csv.DictWriter(fp, fieldnames=list(rows_out[0].keys()))
                w.writeheader()
                w.writerows(rows_out)
        with (out_final / f"per_case_results_{name}.jsonl").open("w", encoding="utf-8") as fp:
            for row in rows_out:
                fp.write(json.dumps(row) + "\n")

    emit_per_case(cases, "original_66")
    emit_per_case(strict_rows, "strict_absent")

    s66 = refined_summarize(cases, new_by_k, base_by_k)
    sstrict = refined_summarize(strict_rows, new_by_k, base_by_k)
    write_json(out_final / "discovery_summary_original_66.json", s66)
    write_json(out_final / "discovery_summary_strict_absent.json", sstrict)

    with (out_final / "discovery_summary_original_66.csv").open("w", encoding="utf-8", newline="") as fp:
        w = csv.DictWriter(fp, fieldnames=list(s66.keys()))
        w.writeheader()
        w.writerow(s66)
    with (out_final / "discovery_summary_strict_absent.csv").open("w", encoding="utf-8", newline="") as fp:
        w = csv.DictWriter(fp, fieldnames=list(sstrict.keys()))
        w.writeheader()
        w.writerow(sstrict)

    write_json(out_final / "comparison_vs_dr_v2.json", {"slice1": s66, "slice2": sstrict, "baseline_method": BASELINE_METHOD, "final_method": METHOD_NEW})
    (out_final / "comparison_vs_dr_v2.md").write_text(
        f"Slice1 (original diagnostic {s66['n_cases_in_slice']}): Δ pool groups {s66['delta_gold_present_in_candidate_groups']}, Δ tree {s66['delta_gold_present_in_tree']}.\n"
        f"Slice2 (strict absent n={len(strict_rows)}): Δ pool {sstrict['delta_gold_present_in_candidate_groups']}, "
        f"recovery {sstrict['discovery_recovered_count']}, recovery_rate vs pool-absent denominator {sstrict['discovery_recovery_rate']:.4f}\n",
        encoding="utf-8",
    )

    # strategy prompt audit aggregate
    with (out_final / "strategy_prompt_audit.csv").open("w", encoding="utf-8", newline="") as fp:
        w = csv.DictWriter(
            fp,
            fieldnames=["case_key", "distinct_prompt_digests", "root_families_seen", "trace_action_count"],
        )
        w.writeheader()
        for r in cases:
            k = case_key(r["dataset"], r["example_id"], r["seed"], r["budget"])
            nr = new_by_k.get(k)
            if not nr:
                continue
            md = dict(nr.get("result_metadata") or {})
            a = strategy_prompt_audit_rows(md)
            w.writerow(
                {
                    "case_key": k,
                    "distinct_prompt_digests": a["distinct_prompt_digests"],
                    "root_families_seen": a["root_families_seen"],
                    "trace_action_count": a["trace_action_count"],
                }
            )

    (out_final / "final_check_report.md").write_text(
        "\n".join(
            [
                "# Strategy-seeded final check report",
                f"- Slice1 size: **{len(cases)}**",
                f"- Slice2 strict baseline-absent size: **{len(strict_rows)}**",
                f"- Prior diagnostic label inconsistencies: path-gap cohort included OR-rows; Slice2 aligns to baseline DR-v2 JSONL pool AND tree absence.",
                f"- Δ gold-in-pool (slice2): **{sstrict['delta_gold_present_in_candidate_groups']}** "
                f"(recovery {sstrict['discovery_recovered_count']}/{max(1, int(sstrict.get('strict_baseline_gold_absent_slice_size') or len(strict_rows)))})",
            ]
        ),
        encoding="utf-8",
    )
    write_json(out_final / "audit_manifest.json", {"bundle": str(out_final)})
    write_json(out_final / "batch_submission_info.json", {"manual_note": "Fill SLURM_JOB_ID from scheduler output", "cwd": str(out_final)})
    (out_final / "artifact_summary.md").write_text(
        "Emitted discovery summaries, per-case CSVs, alignment audit, comparisons, prompt audit CSV.\n", encoding="utf-8"
    )
    write_json(out_final / "comparison_vs_previous_strategy_seeded.json", {"path_previous_csv": str(args.previous_v1_csv), "had_rows": len(prev_by_k)})
    (out_final / "comparison_vs_previous_strategy_seeded.md").write_text(
        "See previous pilot CSV keyed by dataset/example_id/seed/budget vs new per_case_results_original_66.csv metrics.\n", encoding="utf-8"
    )
    write_json(out_final / "strategy_family_diagnostics.json", {})
    write_json(out_final / "semantic_gate_diagnostics.json", {})

    print(f"DONE artifacts under {out_final}")


if __name__ == "__main__":
    main()
