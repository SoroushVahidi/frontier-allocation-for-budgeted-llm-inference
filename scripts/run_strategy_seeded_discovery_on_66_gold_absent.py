#!/usr/bin/env python3
"""Orchestrate strategy_seeded_semantic_diversity_frontier_v1 discovery on gold-absent 66-case subset.

Loads case keys from diagnostic CSVs; runs bounded Cohere generation via run_cohere_real_model_cost_normalized_validation;
compares versus cached DR-v2 / external_l1_max records from baseline discovery JSONL (no regeneration of baseline).

Phase B (selector + verifier scoring) is skipped by default: emit explicit nonzero missing_score fields if rerun later.
Claim boundary: subset diagnostic — no dominance vs external_l1_max.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.data import normalize_answer_text
from experiments.gold_absent_path_gap import load_per_example_index
from experiments.strategy_seeded_semantic_diversity_frontier_v1 import (
    ROOT_STRATEGY_FAMILY_SPECS,
    infer_semantic_family_proxy,
    shannon_entropy_from_counts,
)

METHOD_NEW = "strategy_seeded_semantic_diversity_frontier_v1"
BASELINE_METHOD_ID = "direct_reserve_semantic_frontier_v2"
REF_EXTERNAL_METHOD = "external_l1_max"

DEFAULT_PATH_GAP = (
    REPO_ROOT / "outputs/gold_absent_path_gap_diagnostic_20260502T215957Z/per_case_path_gap_diagnostic.csv"
)
DEFAULT_STILL_LOST = (
    REPO_ROOT / "outputs/full_score_completed_best_selector_on_88_external_losses_20260502T213834Z/still_lost_cases.csv"
)
DEFAULT_SELECTED_100 = REPO_ROOT / "outputs/best_methods_on_external_losses_20260430T195200Z/selected_100_cases.csv"
DEFAULT_BASELINE_JSONL = REPO_ROOT / (
    "outputs/cohere_real_model_cost_normalized_validation_20260502T210610Z_DISCOVERY/per_example_records.jsonl"
)


def norm_ans(text: Any) -> str:
    try:
        return str(normalize_answer_text(str(text or "").strip())).strip().lower()
    except Exception:
        return str(text or "").strip().lower()


def parse_tri(v: Any) -> int | None:
    try:
        if v is None or str(v).strip() == "":
            return None
        return int(float(str(v)))
    except (TypeError, ValueError):
        return None


def load_rows_from_path_gap(path: Path, still_lost_hint: Path, selected_hint: Path) -> list[dict[str, Any]]:
    by_ex: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8", newline="") as fp:
        for row in csv.DictReader(fp):
            d_abs = parse_tri(row.get("discovery_failure_gold_absent"))
            g_grp = parse_tri(row.get("gold_present_in_candidate_groups"))
            g_tree = parse_tri(row.get("gold_present_in_tree"))
            if not (
                (d_abs == 1)
                or (g_grp == 0)
                or (g_tree == 0)
            ):
                continue
            ex = str(row.get("example_id") or "").strip()
            ds = str(row.get("dataset") or "openai/gsm8k").strip()
            try:
                seed = int(row.get("seed") or -1)
                budget = int(row.get("budget") or -1)
            except (TypeError, ValueError):
                continue
            key = f"{ds}::{ex}::{seed}::{budget}"
            by_ex[key] = {
                "dataset": ds,
                "example_id": ex,
                "seed": seed,
                "budget": budget,
                "case_id": str(row.get("case_id") or key),
                "gold_answer_canonical_hint": str(row.get("gold_answer") or ""),
            }
    if not by_ex and still_lost_hint.is_file():
        with still_lost_hint.open(encoding="utf-8", newline="") as fp:
            for row in csv.DictReader(fp):
                if parse_tri(row.get("discovery_failure_gold_absent")) != 1:
                    continue
                # still_lost has mixed rows; discovery_failure gold absent selects our 66-ish set
                ex = str(row.get("example_id") or "").strip()
                ds = str(row.get("dataset") or "").strip()
                try:
                    seed = int(row.get("seed") or -1)
                    budget = int(row.get("budget") or -1)
                except (TypeError, ValueError):
                    continue
                key = f"{ds}::{ex}::{seed}::{budget}"
                by_ex[key] = {
                    "dataset": ds,
                    "example_id": ex,
                    "seed": seed,
                    "budget": budget,
                    "case_id": str(row.get("case_id") or key),
                    "gold_answer_canonical_hint": str(row.get("gold_answer") or ""),
                }
    ordered = sorted(by_ex.values(), key=lambda r: (r["dataset"], r["budget"], r["seed"], r["example_id"]))
    sel_ids: set[str] = set()
    if selected_hint.is_file():
        with selected_hint.open(encoding="utf-8", newline="") as fp:
            for row in csv.DictReader(fp):
                sel_ids.add(str(row.get("example_id") or row.get("id") or "").strip())
    if sel_ids:
        ordered = [r for r in ordered if r["example_id"] in sel_ids]
    return ordered


def gold_present_in_selector_pool(md: dict[str, Any], gold: str) -> bool:
    pool = md.get("selector_candidate_pool")
    if not isinstance(pool, list):
        return False
    g = norm_ans(gold)
    if not g:
        return False
    for c in pool:
        if not isinstance(c, dict):
            continue
        na = c.get("normalized_answer")
        pa = c.get("predicted_answer")
        cand = norm_ans(na if na is not None else pa)
        if cand and cand == g:
            return True
    return False


def gold_present_in_final_branch_states(md: dict[str, Any], gold: str) -> bool:
    g = norm_ans(gold)
    if not g:
        return False
    fbs = md.get("final_branch_states")
    if not isinstance(fbs, list):
        return False
    for s in fbs:
        if not isinstance(s, dict):
            continue
        cand = norm_ans(s.get("predicted_answer") or "")
        if cand == g:
            return True
    return False


def _int_optional(x: Any) -> int | None:
    try:
        if x is None or str(x).strip() == "":
            return None
        return int(float(x))
    except (TypeError, ValueError):
        return None


def count_strategy_metrics_from_md(md: dict[str, Any]) -> dict[str, Any]:
    dra = md.get("direct_reserve_attempts")
    root_families: list[str] = []
    semantics: Counter[str] = Counter()
    seen_root_seen_for_redundant: Counter[str] = Counter()
    red_same_strat_exp = 0
    redundant_semantic_exp = 0
    per_strat_candidates: defaultdict[str, set[str]] = defaultdict(set)
    if isinstance(dra, list):
        for ev in dra:
            if not isinstance(ev, dict):
                continue
            rsp = str(ev.get("root_strategy_family") or ev.get("strategy_family") or "")
            rsp_text = str(ev.get("response_text") or ev.get("reasoning_text") or "")
            sem = infer_semantic_family_proxy(reasoning_text=rsp_text, root_strategy_family=rsp or "unknown")
            semantics[sem] += 1
            if rsp:
                root_families.append(rsp)
                seen_root_seen_for_redundant[rsp] += 1
                if seen_root_seen_for_redundant[rsp] > 1:
                    red_same_strat_exp += 1
        for _fam, ct in semantics.items():
            ct_i = int(ct)
            if ct_i > 1:
                redundant_semantic_exp += ct_i - 1
        for c in md.get("selector_candidate_pool") or []:
            if not isinstance(c, dict):
                continue
            grp = norm_ans(c.get("normalized_answer") or c.get("predicted_answer"))
            sf = str(c.get("source_family") or c.get("branch_id") or "")
            prefix = sf.split("_")[0] if sf else ""
            if grp:
                per_strat_candidates[prefix].add(grp)
    pool_sz = md.get("selector_candidate_pool_size")
    grp_ct = md.get("selector_candidate_answer_group_count")
    frontier_meta = md.get("frontier_metadata") or {}
    strat_ent = frontier_meta.get("strategy_entropy") if isinstance(frontier_meta, dict) else None
    return {
        "strategy_family_count": len(set(root_families)) if root_families else len(ROOT_STRATEGY_FAMILY_SPECS),
        "semantic_family_count": len(semantics),
        "semantic_proxy_histogram_json": json.dumps(dict(semantics), sort_keys=True),
        "strategy_entropy": float(strat_ent) if strat_ent not in {None, ""} else shannon_entropy_from_counts(semantics),
        "repeated_same_strategy_expansion_count": red_same_strat_exp,
        "redundant_semantic_expansion_count": redundant_semantic_exp,
        "per_strategy_candidate_counts_json": json.dumps({k: len(v) for k, v in per_strat_candidates.items()}, sort_keys=True),
        "per_strategy_answer_groups_json": json.dumps({k: sorted(v) for k, v in per_strat_candidates.items()}, sort_keys=True),
        "candidate_group_count_proxy": _int_optional(grp_ct),
        "selector_candidate_pool_size": _int_optional(pool_sz),
    }


def gold_in_tree_from_record(rec: dict[str, Any], md: dict[str, Any], gold: str) -> int:
    gtree = parse_tri(rec.get("gold_in_tree"))
    if gtree is not None:
        return int(gtree)
    return int(gold_present_in_final_branch_states(md, gold))


def baseline_record(
    baseline_idx: dict[tuple[str, str, int, int, str], dict[str, Any]],
    *,
    dataset: str,
    example_id: str,
    seed: int,
    budget: int,
    method_id: str,
) -> dict[str, Any] | None:
    return baseline_idx.get((dataset, example_id, seed, budget, method_id))


def run_validation_subrun(
    *,
    allowed_rows: Path,
    budgets_csv: str,
    seeds_csv: str,
    val_timestamp: str,
    output_root_under: Path,
    cohere_model: str,
    resume: bool,
) -> Path:
    out_dir_parent = Path(output_root_under)
    disk_out = out_dir_parent / f"cohere_real_model_cost_normalized_validation_{val_timestamp}"
    cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts/run_cohere_real_model_cost_normalized_validation.py"),
        "--timestamp",
        val_timestamp,
        "--providers",
        "cohere",
        "--cohere-model",
        cohere_model,
        "--datasets",
        "openai/gsm8k",
        "--budgets",
        budgets_csv,
        "--seeds",
        seeds_csv,
        "--methods",
        METHOD_NEW,
        "--target-scored-per-slice",
        str(max(allowed_line_count(Path(allowed_rows)), 128)),
        "--max-examples",
        str(max(allowed_line_count(Path(allowed_rows)), 128)),
        "--allowed-example-ids-file",
        str(allowed_rows),
        "--output-root",
        str(out_dir_parent.relative_to(REPO_ROOT)),
    ]
    if resume:
        cmd.append("--resume")
    print("[subprocess]", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, cwd=str(REPO_ROOT))
    return disk_out


def allowed_line_count(p: Path) -> int:
    return sum(1 for line in p.read_text(encoding="utf-8").splitlines() if line.strip())


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, sort_keys=True) + "\n")


def md_escape(text: str) -> str:
    return str(text or "").replace("\n", " ").strip()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--stamp", default="", help="Output directory UTC stamp; default now.")
    p.add_argument("--path-gap-csv", type=Path, default=DEFAULT_PATH_GAP)
    p.add_argument("--still-lost-csv", type=Path, default=DEFAULT_STILL_LOST)
    p.add_argument("--selected-100-csv", type=Path, default=DEFAULT_SELECTED_100)
    p.add_argument("--baseline-jsonl", type=Path, default=DEFAULT_BASELINE_JSONL)
    p.add_argument("--cohere-model", default=os.environ.get("STRATEGY_COHERE_MODEL", "command-r-plus-08-2024"))
    p.add_argument("--preflight-only", action="store_true")
    p.add_argument("--expect-case-count", type=int, default=66)
    p.add_argument("--case-count-slop", type=int, default=3)
    p.add_argument("--skip-discovery", action="store_true", help="Only summarize if validation output already populated.")
    p.add_argument("--resume-validation", action="store_true")
    p.add_argument(
        "--max-budget-sum",
        type=int,
        default=620,
        help="Abort before paid calls if sum(budget) over cases exceeds ceiling (safeguard).",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    stamp = (
        args.stamp.strip()
        or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    )
    out_main = REPO_ROOT / "outputs" / f"strategy_seeded_discovery_on_66_gold_absent_{stamp}"
    out_main.mkdir(parents=True, exist_ok=True)

    rows = load_rows_from_path_gap(args.path_gap_csv, args.still_lost_csv, args.selected_100_csv)
    n_cases = len(rows)
    uniq_budgets = sorted({int(r["budget"]) for r in rows})
    uniq_seeds = sorted({int(r["seed"]) for r in rows})
    sum_budget = sum(int(r["budget"]) for r in rows)
    ceilings = {}
    ceilings["estimated_generation_completion_calls_ceiling_cases_times_budget"] = int(sum_budget)

    manifest = {
        "timestamp_utc": stamp,
        "method_new": METHOD_NEW,
        "baseline_method": BASELINE_METHOD_ID,
        "reference_external": REF_EXTERNAL_METHOD,
        "filtered_case_count": n_cases,
        "unique_budgets": uniq_budgets,
        "unique_seeds": uniq_seeds,
        "sum_budget_cases": sum_budget,
        "claim_boundary": (
            "Selected gold-absent / gold-not-in-groups diagnostic subset; gold used only post-hoc "
            "(no dominance vs external_l1_max)."
        ),
        "strategy_root_specs": [{"id": a[0], "prompt_digest": md_escape(a[1][:240])} for a in ROOT_STRATEGY_FAMILY_SPECS],
    }
    write_json(out_main / "manifest.json", manifest)
    allowed_path = out_main / "allowed_example_ids_strategy_seeded.jsonl"
    with allowed_path.open("w", encoding="utf-8") as wf:
        for r in rows:
            wf.write(
                json.dumps(
                    {
                        "dataset": r["dataset"],
                        "example_id": r["example_id"],
                        "seed": int(r["seed"]),
                        "budget": int(r["budget"]),
                        "method": METHOD_NEW,
                    },
                    sort_keys=True,
                )
                + "\n"
            )

    with (out_main / "gold_absent_case_list.csv").open("w", encoding="utf-8", newline="") as fp:
        w = csv.DictWriter(
            fp,
            fieldnames=["dataset", "example_id", "seed", "budget", "case_id", "gold_answer_canonical_hint"],
        )
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in w.fieldnames})

    write_jsonl(out_main / "gold_absent_case_list.jsonl", rows)

    run_cfg = {
        "discovery_script_invoked": METHOD_NEW,
        "allowed_example_ids_strategy_seeded_jsonl": str(allowed_path.relative_to(REPO_ROOT)),
        "path_gap_csv": str(args.path_gap_csv),
        "baseline_discovery_jsonl": str(args.baseline_jsonl),
        "cohere_model": args.cohere_model,
        "expected_case_rows": int(n_cases),
        "sum_budget": int(sum_budget),
        "uniq_budget_list": uniq_budgets,
        "uniq_seed_list": uniq_seeds,
        "exploration_hyperparameters": {
            "min_strategy_families_before_commit_proxy": 3,
            "frontier_override_min_maturity": 3,
            "strategy_seed_max_actions_per_root": 1,
            "inner_diagnostic_semantic_maturation_min_depth": 2,
            "allow_early_commit_if_verifier_confident": False,
            "direct_reserve_enabled": True,
            "semantic_gate_is_proxy": True,
        },
    }
    write_json(out_main / "run_config.json", run_cfg)

    print(
        json.dumps(
            {
                "preflight": bool(args.preflight_only),
                "case_count": n_cases,
                "expect": args.expect_case_count,
                "sum_budget_ceiling_hint": sum_budget,
                "budgets": uniq_budgets,
                "seeds_count": len(uniq_seeds),
            },
            indent=2,
        ),
        flush=True,
    )

    if not args.baseline_jsonl.is_file():
        raise SystemExit(f"baseline jsonl missing: {args.baseline_jsonl}")

    if abs(n_cases - int(args.expect_case_count)) > int(args.case_count_slop):
        raise SystemExit(
            f"case count {n_cases} not within slop {args.case_count_slop} of expect {args.expect_case_count}"
        )
    if sum_budget > int(args.max_budget_sum):
        raise SystemExit(f"sum_budget {sum_budget} exceeds --max-budget-sum {args.max_budget_sum}")

    pf_obj = {
        "case_count": n_cases,
        "expect_case_count": int(args.expect_case_count),
        "case_count_slop": int(args.case_count_slop),
        "sum_budget_ceiling_hint": int(sum_budget),
        "uniq_budget_list": uniq_budgets,
        "uniq_seed_count": len(uniq_seeds),
        "estimated_generation_completion_calls_ceiling_cases_times_budget": int(sum_budget),
    }
    write_json(out_main / "preflight_stats.json", pf_obj)

    if args.preflight_only:
        return 0

    baseline_idx = load_per_example_index([args.baseline_jsonl], methods={BASELINE_METHOD_ID, REF_EXTERNAL_METHOD})

    val_ts = f"{stamp}_SSDFV1"
    val_out = out_main / f"cohere_real_model_cost_normalized_validation_{val_ts}"
    jsonl_path = val_out / "per_example_records.jsonl"

    if not args.skip_discovery:
        run_validation_subrun(
            allowed_rows=allowed_path,
            budgets_csv=",".join(str(b) for b in uniq_budgets),
            seeds_csv=",".join(str(s) for s in uniq_seeds),
            val_timestamp=val_ts,
            output_root_under=out_main,
            cohere_model=args.cohere_model,
            resume=bool(args.resume_validation),
        )
    elif not jsonl_path.is_file():
        raise SystemExit(f"--skip-discovery but missing {jsonl_path}")

    # ---- Post-process ---
    new_idx = load_per_example_index([jsonl_path], methods={METHOD_NEW})
    discovery_rows: list[dict[str, Any]] = []
    diag_rows_strategy: list[dict[str, Any]] = []
    diag_sem: list[dict[str, Any]] = []

    still_absent_csv: list[dict[str, Any]] = []
    newly_present_csv: list[dict[str, Any]] = []

    base_g_grp = 0
    new_g_grp = 0
    base_tree = 0
    new_tree = 0
    ext_g_grp = 0
    ext_tree = 0
    disc_rec = 0
    grp_means_bl: list[int] = []
    grp_means_new: list[int] = []
    act_bl: list[int] = []
    act_new: list[int] = []
    strat_fam_new: list[int] = []
    sem_fam_new: list[int] = []

    for r in rows:
        ds, ex = r["dataset"], r["example_id"]
        seed, budget = int(r["seed"]), int(r["budget"])
        gold = str(r.get("gold_answer_canonical_hint") or "")
        # Gold from baseline record if hint empty
        br = baseline_record(baseline_idx, dataset=ds, example_id=ex, seed=seed, budget=budget, method_id=BASELINE_METHOD_ID)
        if br and not gold:
            gold = str(br.get("gold_answer_canonical") or br.get("gold_answer") or "")
        nr = baseline_record(new_idx, dataset=ds, example_id=ex, seed=seed, budget=budget, method_id=METHOD_NEW)
        if not nr:
            raise RuntimeError(f"missing new record for {ds} {ex} {seed} {budget}")
        md_new = nr.get("result_metadata") if isinstance(nr.get("result_metadata"), dict) else {}
        md_bl = br.get("result_metadata") if br and isinstance(br.get("result_metadata"), dict) else {}
        xr = baseline_record(baseline_idx, dataset=ds, example_id=ex, seed=seed, budget=budget, method_id=REF_EXTERNAL_METHOD)
        md_xr = xr.get("result_metadata") if xr and isinstance(xr.get("result_metadata"), dict) else {}

        g_new_pool = int(gold_present_in_selector_pool(md_new, gold))
        g_new_tree = gold_in_tree_from_record(nr or {}, md_new, gold)
        g_bl_pool = int(gold_present_in_selector_pool(md_bl, gold)) if br else 0
        g_bl_tree = gold_in_tree_from_record(br or {}, md_bl, gold) if br else 0

        base_g_grp += g_bl_pool
        new_g_grp += g_new_pool
        base_tree += g_bl_tree
        new_tree += g_new_tree
        if xr:
            g_ext_pool = int(gold_present_in_selector_pool(md_xr, gold))
            g_ext_tree = gold_in_tree_from_record(xr, md_xr, gold)
            ext_g_grp += g_ext_pool
            ext_tree += int(g_ext_tree)
        if (not g_bl_pool) and g_new_pool:
            disc_rec += 1
            newly_present_csv.append(
                {
                    "dataset": ds,
                    "example_id": ex,
                    "seed": seed,
                    "budget": budget,
                    "gold_answer": gold,
                }
            )
        if (not g_new_pool) and (not g_new_tree):
            still_absent_csv.append(
                {
                    "dataset": ds,
                    "example_id": ex,
                    "seed": seed,
                    "budget": budget,
                    "gold_answer": gold,
                }
            )

        sm = count_strategy_metrics_from_md(md_new)
        strat_fam_new.append(int(sm["strategy_family_count"]))
        sem_fam_new.append(int(sm["semantic_family_count"]))

        try:
            grp_means_bl.append(int(md_bl.get("selector_candidate_answer_group_count") or 0))
        except Exception:
            pass
        sm_c = sm.get("candidate_group_count_proxy")
        if sm_c is not None:
            grp_means_new.append(int(sm_c))
        if br:
            try:
                act_bl.append(int(br.get("actions_used") or 0))
            except Exception:
                pass
        try:
            act_new.append(int(nr.get("actions_used") or 0))
        except Exception:
            pass

        row = {
            "dataset": ds,
            "example_id": ex,
            "seed": seed,
            "budget": budget,
            "gold_answer_canonical": gold,
            "baseline_gold_present_in_candidate_groups": g_bl_pool,
            "new_gold_present_in_candidate_groups": g_new_pool,
            "baseline_gold_present_in_tree": g_bl_tree,
            "new_gold_present_in_tree": g_new_tree,
            "discovery_recovered_this_case": int((not g_bl_pool) and g_new_pool),
            "new_actions_used": int(nr.get("actions_used") or 0),
            "baseline_actions_used": int(br.get("actions_used") or 0) if br else "",
            **sm,
        }
        discovery_rows.append(row)
        diag_rows_strategy.append(
            {
                "example_id": ex,
                "seed": seed,
                "budget": budget,
                "strategy_family_count": sm["strategy_family_count"],
                "semantic_family_count": sm["semantic_family_count"],
                "strategy_entropy": sm["strategy_entropy"],
                "repeated_same_strategy_expansion_count": sm["repeated_same_strategy_expansion_count"],
                "redundant_semantic_expansion_count": sm["redundant_semantic_expansion_count"],
            }
        )
        diag_sem.append(
            {
                "example_id": ex,
                "seed": seed,
                "budget": budget,
                "semantic_family_histogram_json": sm.get("semantic_proxy_histogram_json", "{}"),
            }
        )

    def mean(xs: list[float | int]) -> float:
        return float(sum(xs) / max(1, len(xs)))

    discovery_summary = {
        "total_cases": n_cases,
        "evaluated_cases": n_cases,
        "skipped_cases": 0,
        "baseline_method": BASELINE_METHOD_ID,
        "new_method": METHOD_NEW,
        "baseline_gold_present_count": int(base_g_grp),
        "new_gold_present_count": int(new_g_grp),
        "discovery_recovered_count": int(disc_rec),
        "discovery_recovery_rate": float(disc_rec / max(1, n_cases)),
        "still_gold_absent_count": int(
            sum(
                1
                for r in discovery_rows
                if (not r["new_gold_present_in_candidate_groups"]) and (not r["new_gold_present_in_tree"])
            )
        ),
        "mean_candidate_group_count_baseline": mean(grp_means_bl) if grp_means_bl else 0.0,
        "mean_candidate_group_count_new": mean(grp_means_new) if grp_means_new else 0.0,
        "median_candidate_group_count_baseline": float(median(grp_means_bl)) if grp_means_bl else 0.0,
        "median_candidate_group_count_new": float(median(grp_means_new)) if grp_means_new else 0.0,
        "mean_strategy_family_count_new": mean(strat_fam_new),
        "mean_semantic_family_count_new": mean(sem_fam_new),
        "median_strategy_family_count_new": float(median(strat_fam_new)) if strat_fam_new else 0.0,
        "median_semantic_family_count_new": float(median(sem_fam_new)) if sem_fam_new else 0.0,
        "mean_actions_baseline": mean(act_bl) if act_bl else 0.0,
        "mean_actions_new": mean(act_new) if act_new else 0.0,
        "mean_tokens_baseline": "",
        "mean_tokens_new": "",
        "api_call_count_generation": int(sum(act_new)) if act_new else 0,
        "api_call_count_verifier": 0,
        "paid_api_call_count_total": int(sum(act_new)) if act_new else 0,
        "trace_available_count": n_cases,
        "skipped_reasons": [],
        "aux_baseline_gold_present_in_tree_count": int(base_tree),
        "aux_new_gold_present_in_tree_count": int(new_tree),
    }
    write_json(out_main / "discovery_summary.json", discovery_summary)
    with (out_main / "discovery_summary.csv").open("w", encoding="utf-8", newline="") as fp:
        w = csv.DictWriter(fp, fieldnames=list(discovery_summary.keys()))
        w.writeheader()
        w.writerow(discovery_summary)

    write_jsonl(out_main / "per_case_discovery_results.jsonl", discovery_rows)
    with (out_main / "per_case_discovery_results.csv").open("w", encoding="utf-8", newline="") as fp:
        if discovery_rows:
            w = csv.DictWriter(fp, fieldnames=list(discovery_rows[0].keys()))
            w.writeheader()
            w.writerows(discovery_rows)

    with (out_main / "strategy_family_diagnostics.csv").open("w", encoding="utf-8", newline="") as fp:
        if diag_rows_strategy:
            w = csv.DictWriter(fp, fieldnames=list(diag_rows_strategy[0].keys()))
            w.writeheader()
            w.writerows(diag_rows_strategy)
    with (out_main / "semantic_diversity_diagnostics.csv").open("w", encoding="utf-8", newline="") as fp:
        if diag_sem:
            w = csv.DictWriter(fp, fieldnames=list(diag_sem[0].keys()))
            w.writeheader()
            w.writerows(diag_sem)

    with (out_main / "still_gold_absent_cases.csv").open("w", encoding="utf-8", newline="") as fp:
        wr = csv.DictWriter(fp, fieldnames=["dataset", "example_id", "seed", "budget", "gold_answer"])
        wr.writeheader()
        wr.writerows(still_absent_csv)
    with (out_main / "newly_gold_present_cases.csv").open("w", encoding="utf-8", newline="") as fp:
        wr = csv.DictWriter(fp, fieldnames=["dataset", "example_id", "seed", "budget", "gold_answer"])
        wr.writeheader()
        wr.writerows(newly_present_csv)

    comparison = {
        "cases_total": n_cases,
        "baseline_method": BASELINE_METHOD_ID,
        "new_method": METHOD_NEW,
        "reference_external_method": REF_EXTERNAL_METHOD,
        "reference_external_gold_present_in_candidate_groups_count": int(ext_g_grp),
        "reference_external_gold_present_in_tree_count": int(ext_tree),
        "delta_gold_present_in_candidate_groups": int(new_g_grp - base_g_grp),
        "delta_gold_present_in_tree": int(new_tree - base_tree),
        "discovery_recovered_count": int(disc_rec),
        "interpretation": (
            "Positive delta_gold_present_in_candidate_groups is the primary success signal for this pilot; "
            "subset-only; proxy semantic gate. external_l1_max counts are reference-only from cached JSONL, "
            "not a broad superiority claim."
        ),
    }
    write_json(out_main / "comparison_vs_dr_v2.json", comparison)
    (out_main / "comparison_vs_dr_v2.md").write_text(
        "\n".join(
            [
                "# Comparison vs DR-v2 baseline (cached JSONL)",
                "",
                f"- Cases: **{n_cases}**",
                f"- Baseline method: `{BASELINE_METHOD_ID}`",
                f"- New method: `{METHOD_NEW}`",
                f"- Δ gold present in candidate groups (new − baseline): **{comparison['delta_gold_present_in_candidate_groups']}**",
                f"- Δ gold present in tree (new − baseline): **{comparison['delta_gold_present_in_tree']}**",
                f"- Discovery recovered count (0→1 in groups): **{disc_rec}**",
                "",
                "Claim boundary: diagnostic subset; not broad external baseline dominance.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    final_sel = {
        "phase_b_status": "skipped_discovery_only_eval",
        "total_cases": n_cases,
        "correct_count": "",
        "wrong_count": "",
        "final_accuracy_on_66": "",
        "newly_fixed_count_vs_baseline": "",
        "newly_broken_count_vs_baseline": "",
        "missing_score_count": n_cases,
        "fallback_due_to_missing_score_count": 0,
        "selected_candidate_not_in_pool_count": "",
        "verifier_scores_added_count": 0,
        "expected_verifier_api_calls": 0,
        "actual_verifier_api_calls": 0,
        "note": "Run outcome-verifier selector with bounded plan in a follow-up job if needed.",
    }
    write_json(out_main / "final_selector_summary.json", final_sel)
    with (out_main / "final_selector_summary.csv").open("w", encoding="utf-8", newline="") as fp:
        w = csv.DictWriter(fp, fieldnames=list(final_sel.keys()))
        w.writeheader()
        w.writerow(final_sel)
    Path(out_main / "per_case_final_selector_results.jsonl").write_text("", encoding="utf-8")
    Path(out_main / "per_case_final_selector_results.csv").write_text("", encoding="utf-8")
    Path(out_main / "still_wrong_cases.csv").write_text("example_id\n", encoding="utf-8")
    Path(out_main / "newly_fixed_cases.csv").write_text("example_id\n", encoding="utf-8")

    (out_main / "summary_report.md").write_text(
        "\n".join(
            [
                "# Strategy-seeded semantic diversity frontier pilot",
                "",
                f"- Cases: **{n_cases}**",
                f"- New method `{METHOD_NEW}` discovery vs cached `{BASELINE_METHOD_ID}` from `{args.baseline_jsonl.name}`.",
                f"- Δ groups gold-present: **{comparison['delta_gold_present_in_candidate_groups']}** "
                f"({base_g_grp} → {new_g_grp}).",
                f"- Δ tree gold-present: **{comparison['delta_gold_present_in_tree']}** ({base_tree} → {new_tree}).",
                f"- Reference `{REF_EXTERNAL_METHOD}` (cached) groups / tree gold-present case-totals: **{ext_g_grp} / {ext_tree}** "
                "(diagnostic subset only).",
                f"- Mean actions (new): **{discovery_summary['mean_actions_new']}**.",
                "",
                "See `discovery_summary.json` and `comparison_vs_dr_v2.json`.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (out_main / "artifact_summary.md").write_text(
        "\n".join(
            [
                "# Artifact summary",
                "",
                f"- Output dir: `{out_main.relative_to(REPO_ROOT)}/`",
                f"- Cohort validation subdir: `{val_out.relative_to(REPO_ROOT)}/`",
                "- Phase B verifier selector deliberately skipped (`final_selector_summary.json`).",
                "",
            ]
        ),
        encoding="utf-8",
    )
    subprocess_info = {
        "submitted_job_id": os.environ.get("SLURM_JOB_ID", ""),
        "orchestration_script": "scripts/run_strategy_seeded_discovery_on_66_gold_absent.py",
        "validation_subdirectory": str(val_out.relative_to(REPO_ROOT)),
        "expected_budget_sum_generation_ceiling": int(sum_budget),
    }
    write_json(out_main / "batch_submission_info.json", subprocess_info)
    Path(out_main / "monitor_log.jsonl").touch()

    envlog = (
        "\n".join(
            [
                f"stamp={stamp}",
                f"cases={n_cases}",
                f"sum_budget_ceiling_hint={sum_budget}",
                os.environ.get("HOSTNAME") or "",
            ]
        )
        + "\n"
    )
    (out_main / "run_env.log").write_text(envlog, encoding="utf-8")
    write_json(out_main / "budget_ceilings.json", ceilings)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
