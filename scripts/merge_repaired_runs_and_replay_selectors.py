#!/usr/bin/env python3
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import math
import random
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from experiments.support_aware_selector import agreement_only_2of3_against_frontier


REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_ROOT_DEFAULT = REPO_ROOT / "outputs" / "merged_repaired_cohere_mistral_selector_replay_20260524"

METHOD_FRONTIER = "direct_reserve_semantic_frontier_v2"
METHOD_L1 = "external_l1_max"
METHOD_S1 = "external_s1_budget_forcing"
METHOD_TALE = "external_tale_prompt_budgeting"
ALL_METHODS = [METHOD_FRONTIER, METHOD_L1, METHOD_S1, METHOD_TALE]
EXTERNAL_METHODS = [METHOD_L1, METHOD_S1, METHOD_TALE]


def normalize_answer(answer: Any) -> str | None:
    s = str(answer or "").strip()
    if not s or s.lower() in {"none", "__unknown__"}:
        return None
    s = s.replace("$", "").replace(",", "").strip()
    if s.startswith("\\boxed{") and s.endswith("}"):
        s = s[len("\\boxed{") : -1].strip()
    try:
        v = float(s)
        if math.isfinite(v):
            if v == int(v):
                return str(int(v))
            return f"{v:.8f}".rstrip("0").rstrip(".")
    except Exception:
        pass
    return s.lower()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        keys: set[str] = set()
        for r in rows:
            keys.update(r.keys())
        fieldnames = sorted(keys)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in fieldnames})


def method_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    c: dict[str, int] = collections.Counter()
    for r in rows:
        c[str(r.get("method"))] += 1
    return dict(c)


def row_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row.get("provider"),
        row.get("dataset"),
        row.get("seed"),
        row.get("budget"),
        row.get("example_id"),
        row.get("method"),
    )


def row_signature_for_dup_compare(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "normalized_final_answer": normalize_answer(row.get("final_answer_canonical") or row.get("selected_answer_canonical")),
        "exact_match": int(row.get("exact_match") or 0),
        "status": row.get("status"),
        "failed": int(row.get("failed") or 0),
        "scored": int(row.get("scored") or 0),
        "final_answer_raw": str(row.get("final_answer_raw") or ""),
        "error": str(row.get("error") or ""),
    }


def inventory_entry(path: Path) -> dict[str, Any]:
    st = path.stat()
    rows = read_jsonl(path)
    return {
        "path": str(path),
        "size_bytes": st.st_size,
        "mtime_epoch": st.st_mtime,
        "line_count": len(rows),
        "method_counts": method_counts(rows),
    }


@dataclass
class MergeResult:
    merged_rows: list[dict[str, Any]]
    pass_integrity: bool
    summary: dict[str, Any]
    duplicate_rows: list[dict[str, Any]]
    missing_rows: list[dict[str, Any]]
    duplicate_resolution_md: str | None = None


def merge_rows(
    *,
    provider_label: str,
    original_rows: list[dict[str, Any]],
    repair_rows: list[dict[str, Any]],
    expected_examples: int,
    allow_benign_dedup: bool,
) -> MergeResult:
    combined = original_rows + repair_rows
    by_key: dict[tuple[Any, ...], list[dict[str, Any]]] = collections.defaultdict(list)
    for idx, row in enumerate(combined):
        row["_merge_order"] = idx
        by_key[row_key(row)].append(row)

    duplicate_rows_report: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    merged_rows: list[dict[str, Any]] = []
    duplicate_resolution_lines: list[str] = []

    for key in sorted(by_key.keys()):
        rows = by_key[key]
        if len(rows) == 1:
            kept = rows[0]
            kept.pop("_merge_order", None)
            merged_rows.append(kept)
            continue

        # Duplicate key
        sigs = [row_signature_for_dup_compare(r) for r in rows]
        all_equal = all(s == sigs[0] for s in sigs[1:])
        for i, (r, sig) in enumerate(zip(rows, sigs)):
            duplicate_rows_report.append(
                {
                    "provider": r.get("provider"),
                    "dataset": r.get("dataset"),
                    "seed": r.get("seed"),
                    "budget": r.get("budget"),
                    "example_id": r.get("example_id"),
                    "method": r.get("method"),
                    "dup_index": i,
                    "dup_group_size": len(rows),
                    "final_answer_canonical": r.get("final_answer_canonical"),
                    "exact_match": r.get("exact_match"),
                    "status": r.get("status"),
                    "failed": r.get("failed"),
                    "scored": r.get("scored"),
                    "error": r.get("error"),
                    "normalized_final_answer": sig["normalized_final_answer"],
                    "signature_json": json.dumps(sig, sort_keys=True),
                }
            )

        if all_equal and allow_benign_dedup:
            kept = min(rows, key=lambda x: x.get("_merge_order", 0))
            kept.pop("_merge_order", None)
            merged_rows.append(kept)
            duplicate_resolution_lines.append(
                f"- benign duplicate key `{key}`: {len(rows)} rows identical on normalized answer/exact_match/status; kept first by stable merge order."
            )
        elif allow_benign_dedup:
            # Clear recovery rule: if exactly one scored-success row exists and all
            # others are failed/unscored attempts for the same key, keep scored row.
            scored_success = [
                r
                for r in rows
                if int(r.get("scored") or 0) == 1
                and int(r.get("failed") or 0) == 0
                and str(r.get("status") or "") == "scored"
            ]
            failed_or_unscored = [
                r for r in rows if r not in scored_success
            ]
            if len(scored_success) == 1 and all(int(r.get("scored") or 0) == 0 for r in failed_or_unscored):
                kept = scored_success[0]
                kept.pop("_merge_order", None)
                merged_rows.append(kept)
                duplicate_resolution_lines.append(
                    f"- resolved duplicate key `{key}` with rule `prefer_scored_over_failed`: kept scored row; dropped {len(failed_or_unscored)} failed/unscored rows."
                )
            else:
                conflicts.append(
                    {
                        "key": key,
                        "all_signatures_equal": all_equal,
                        "rows": rows,
                        "signatures": sigs,
                    }
                )
        else:
            conflicts.append(
                {
                    "key": key,
                    "all_signatures_equal": all_equal,
                    "rows": rows,
                    "signatures": sigs,
                }
            )

    # Expected coverage checks
    merged_by_ex: dict[str, dict[str, dict[str, Any]]] = collections.defaultdict(dict)
    for r in merged_rows:
        merged_by_ex[str(r.get("example_id"))][str(r.get("method"))] = r

    missing_rows: list[dict[str, Any]] = []
    for ex_id in sorted(merged_by_ex.keys()):
        for m in ALL_METHODS:
            if m not in merged_by_ex[ex_id]:
                missing_rows.append({"example_id": ex_id, "missing_method": m})

    unique_examples = len(merged_by_ex)
    counts = method_counts(merged_rows)
    expected_total_rows = expected_examples * len(ALL_METHODS)
    pass_integrity = True
    reasons: list[str] = []

    if unique_examples != expected_examples:
        pass_integrity = False
        reasons.append(f"unique_examples={unique_examples} expected={expected_examples}")
    if len(merged_rows) != expected_total_rows:
        pass_integrity = False
        reasons.append(f"rows={len(merged_rows)} expected={expected_total_rows}")
    for m in ALL_METHODS:
        if counts.get(m, 0) != expected_examples:
            pass_integrity = False
            reasons.append(f"method_count[{m}]={counts.get(m, 0)} expected={expected_examples}")
    if missing_rows:
        pass_integrity = False
        reasons.append(f"missing_rows={len(missing_rows)}")
    if conflicts:
        pass_integrity = False
        reasons.append(f"duplicate_conflicts={len(conflicts)}")

    summary = {
        "provider": provider_label,
        "original_rows": len(original_rows),
        "repair_rows": len(repair_rows),
        "merged_rows_after_dedup": len(merged_rows),
        "expected_total_rows": expected_total_rows,
        "unique_examples": unique_examples,
        "expected_examples": expected_examples,
        "method_counts": counts,
        "duplicate_key_groups": int(sum(1 for v in by_key.values() if len(v) > 1)),
        "duplicate_rows_total": int(sum(len(v) - 1 for v in by_key.values() if len(v) > 1)),
        "duplicate_conflicts": len(conflicts),
        "missing_rows": len(missing_rows),
        "pass_integrity": pass_integrity,
        "failure_reasons": reasons,
    }

    if conflicts:
        duplicate_resolution_lines.append("")
        duplicate_resolution_lines.append("## Conflicts")
        for c in conflicts:
            duplicate_resolution_lines.append(f"- conflict key `{c['key']}` with differing signatures; merge blocked.")

    duplicate_resolution_md = "\n".join(duplicate_resolution_lines) if duplicate_resolution_lines else None
    return MergeResult(
        merged_rows=merged_rows,
        pass_integrity=pass_integrity,
        summary=summary,
        duplicate_rows=duplicate_rows_report,
        missing_rows=missing_rows,
        duplicate_resolution_md=duplicate_resolution_md,
    )


def get_answer(row: dict[str, Any] | None) -> str | None:
    if not row:
        return None
    return normalize_answer(row.get("final_answer_canonical") or row.get("selected_answer_canonical"))


def get_ok(row: dict[str, Any] | None) -> int:
    if not row:
        return 0
    return int(row.get("exact_match") or 0)


def pooled4_with_fallback(frontier: str | None, l1: str | None, s1: str | None, tale: str | None) -> tuple[str | None, str]:
    votes = [("frontier", frontier), ("l1", l1), ("s1", s1), ("tale", tale)]
    valid = [a for _, a in votes if a is not None]
    if not valid:
        return frontier, "fallback_frontier_no_votes"
    counts = collections.Counter(valid)
    most = counts.most_common()
    top_ans, top_count = most[0]
    second = most[1][1] if len(most) > 1 else 0
    # strict majority winner within 4-vote pool (>=3) OR unique 2-vote lead over singles
    if top_count >= 3:
        if top_ans == frontier:
            return frontier, "frontier_pooled_match"
        return top_ans, "pooled_majority"
    # 2-vote with no tie among top also treated as pooled plurality only if unique
    if top_count == 2 and second < 2:
        if top_ans == frontier:
            return frontier, "frontier_pooled_match"
        return top_ans, "pooled_plurality_unique_2of4"
    return frontier, "fallback_frontier_no_majority"


def external_majority(l1: str | None, s1: str | None, tale: str | None) -> tuple[str | None, int]:
    vals = [v for v in [l1, s1, tale] if v is not None]
    if not vals:
        return None, 0
    c = collections.Counter(vals)
    a, n = c.most_common(1)[0]
    return a, n


def deterministic_fold(example_id: str, n_folds: int = 5) -> int:
    h = hashlib.md5(example_id.encode("utf-8")).hexdigest()
    return int(h, 16) % n_folds


def choose_best_source(train_examples: list[dict[str, Any]], source_fields: list[str]) -> tuple[str, dict[str, float]]:
    accs: dict[str, float] = {}
    n = max(1, len(train_examples))
    for f in source_fields:
        accs[f] = sum(int(e[f"{f}_ok"]) for e in train_examples) / n
    best = max(source_fields, key=lambda x: (accs[x], x))
    return best, accs


def beta_interval_wilson(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return (0.0, 1.0)
    p = successes / n
    den = 1 + (z**2) / n
    center = (p + (z**2) / (2 * n)) / den
    margin = (z * math.sqrt((p * (1 - p) / n) + (z**2) / (4 * n * n))) / den
    return (max(0.0, center - margin), min(1.0, center + margin))


def paired_bootstrap_ci(diffs: list[int], n_boot: int = 5000, seed: int = 7) -> tuple[float, float, float]:
    rng = random.Random(seed)
    n = len(diffs)
    obs = sum(diffs) / n if n else 0.0
    if n == 0:
        return obs, 0.0, 0.0
    vals = []
    for _ in range(n_boot):
        sample = [diffs[rng.randrange(n)] for _ in range(n)]
        vals.append(sum(sample) / n)
    vals.sort()
    lo = vals[int(0.025 * n_boot)]
    hi = vals[int(0.975 * n_boot)]
    return obs, lo, hi


def mcnemar(a: list[int], b: list[int]) -> dict[str, Any]:
    # b: a correct and b wrong, c: a wrong and b correct
    b_only = 0
    c_only = 0
    for xa, xb in zip(a, b):
        if xa and not xb:
            b_only += 1
        elif (not xa) and xb:
            c_only += 1
    if b_only + c_only == 0:
        chi2 = 0.0
    else:
        chi2 = ((abs(b_only - c_only) - 1) ** 2) / (b_only + c_only)
    return {"b_only": b_only, "c_only": c_only, "chi2_cc": chi2}


def build_examples(merged_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_ex: dict[str, dict[str, dict[str, Any]]] = collections.defaultdict(dict)
    for r in merged_rows:
        by_ex[str(r.get("example_id"))][str(r.get("method"))] = r
    examples: list[dict[str, Any]] = []
    for ex in sorted(by_ex.keys()):
        row = by_ex[ex]
        if any(m not in row for m in ALL_METHODS):
            continue
        f = row[METHOD_FRONTIER]
        l1 = row[METHOD_L1]
        s1 = row[METHOD_S1]
        tale = row[METHOD_TALE]
        f_ans = get_answer(f)
        l1_ans = get_answer(l1)
        s1_ans = get_answer(s1)
        tale_ans = get_answer(tale)
        pool_ans, pool_action = pooled4_with_fallback(f_ans, l1_ans, s1_ans, tale_ans)
        agr_ans, agr_meta = agreement_only_2of3_against_frontier(
            frontier_answer=f_ans,
            l1_answer=l1_ans,
            s1_answer=s1_ans,
            tale_answer=tale_ans,
        )
        ex_row = {
            "example_id": ex,
            "provider": f.get("provider"),
            "dataset": f.get("dataset"),
            "seed": f.get("seed"),
            "budget": f.get("budget"),
            "gold_answer_canonical": normalize_answer(f.get("gold_answer_canonical") or f.get("gold_answer")),
            "frontier_ans": f_ans,
            "L1_ans": l1_ans,
            "S1_ans": s1_ans,
            "TALE_ans": tale_ans,
            "frontier_ok": get_ok(f),
            "L1_ok": get_ok(l1),
            "S1_ok": get_ok(s1),
            "TALE_ok": get_ok(tale),
            "agreement_ans": agr_ans,
            "agreement_action": agr_meta.get("reason"),
            "agreement_ok": 0,  # fill later
            "pooled4_ans": pool_ans,
            "pooled4_action": pool_action,
            "pooled4_ok": 0,  # fill later
        }
        gold = ex_row["gold_answer_canonical"]
        ex_row["agreement_ok"] = int(agr_ans is not None and gold is not None and str(agr_ans) == str(gold))
        ex_row["pooled4_ok"] = int(pool_ans is not None and gold is not None and str(pool_ans) == str(gold))
        examples.append(ex_row)
    return examples


def replay_artifact(
    *,
    provider_label: str,
    merged_rows: list[dict[str, Any]],
    out_root: Path,
) -> dict[str, Any]:
    examples = build_examples(merged_rows)
    n = len(examples)
    if n == 0:
        raise RuntimeError(f"{provider_label}: no replayable examples")

    # Determine best single source in this artifact (diagnostic only)
    best_src, src_accs = choose_best_source(examples, ["frontier", "L1", "S1", "TALE"])

    # Precompute fold membership
    folds: dict[int, list[dict[str, Any]]] = collections.defaultdict(list)
    for e in examples:
        folds[deterministic_fold(e["example_id"], 5)].append(e)

    # Helpers
    def source_ans(e: dict[str, Any], source: str) -> str | None:
        return e[f"{source}_ans"]

    def source_ok(e: dict[str, Any], source: str) -> int:
        return int(e[f"{source}_ok"])

    selector_preds: dict[str, dict[str, Any]] = {}

    # Baselines
    for source in ["frontier", "L1", "S1", "TALE"]:
        selector_preds[source] = {
            e["example_id"]: {"answer": source_ans(e, source), "ok": source_ok(e, source), "meta": {"source": source}}
            for e in examples
        }

    selector_preds["best_single_source_in_this_artifact"] = {
        e["example_id"]: {"answer": source_ans(e, best_src), "ok": source_ok(e, best_src), "meta": {"best_source": best_src, "source_accs": src_accs}}
        for e in examples
    }

    selector_preds["oracle"] = {}
    for e in examples:
        chosen = None
        for s in ["frontier", "L1", "S1", "TALE"]:
            if source_ok(e, s):
                chosen = source_ans(e, s)
                break
        if chosen is None:
            chosen = source_ans(e, "frontier")
        gold = e["gold_answer_canonical"]
        ok = int(chosen is not None and gold is not None and str(chosen) == str(gold))
        selector_preds["oracle"][e["example_id"]] = {"answer": chosen, "ok": ok, "meta": {"diagnostic_only": True}}

    # Static selectors
    selector_preds["agreement_only_2of3_against_frontier"] = {
        e["example_id"]: {"answer": e["agreement_ans"], "ok": e["agreement_ok"], "meta": {"action": e["agreement_action"]}}
        for e in examples
    }
    selector_preds["pooled4_with_fallback"] = {
        e["example_id"]: {"answer": e["pooled4_ans"], "ok": e["pooled4_ok"], "meta": {"action": e["pooled4_action"]}}
        for e in examples
    }
    selector_preds["always_s1"] = {
        e["example_id"]: {"answer": e["S1_ans"], "ok": e["S1_ok"], "meta": {"source": "S1"}}
        for e in examples
    }

    # In-sample raw spread selectors
    for thresh in [0.05, 0.10]:
        spread = max(src_accs.values()) - sorted(src_accs.values(), reverse=True)[1]
        choose_best = spread > thresh
        if choose_best:
            rule = f"best_source_{best_src}"
        else:
            rule = "pooled4"
        key = f"raw_spread_regime_selector_t{thresh:.2f}"
        selector_preds[key] = {}
        for e in examples:
            if choose_best:
                ans = source_ans(e, best_src)
            else:
                ans = e["pooled4_ans"]
            gold = e["gold_answer_canonical"]
            ok = int(ans is not None and gold is not None and str(ans) == str(gold))
            selector_preds[key][e["example_id"]] = {
                "answer": ans,
                "ok": ok,
                "meta": {"threshold": thresh, "spread": spread, "chosen_rule": rule, "best_source": best_src},
            }

    # CV selectors + regime diagnostics
    cv_keys = [
        "cv5_raw_spread_regime_selector",
        "beta_shrinkage_regime_selector",
        "frontier_fallback_calibrated",
        "pooled4_with_calibrated_no_majority_fallback",
        "dominant_source_veto",
        "majority_requires_dominant_source_when_dominant",
    ]
    for k in cv_keys:
        selector_preds[k] = {}

    regime_decisions: dict[str, Any] = {"folds": {}}

    for fold in range(5):
        test_rows = folds.get(fold, [])
        train_rows = [e for f in range(5) if f != fold for e in folds.get(f, [])]
        train_n = max(1, len(train_rows))
        best_train_src, train_accs = choose_best_source(train_rows, ["frontier", "L1", "S1", "TALE"])
        sorted_accs = sorted(train_accs.values(), reverse=True)
        spread = sorted_accs[0] - sorted_accs[1]
        dominant = spread > 0.05

        # beta-shrinkage conservative dominance check using Wilson interval overlap
        counts = {s: sum(int(e[f"{s}_ok"]) for e in train_rows) for s in ["frontier", "L1", "S1", "TALE"]}
        intervals = {s: beta_interval_wilson(counts[s], train_n) for s in counts}
        best_lower = intervals[best_train_src][0]
        second_src = sorted(train_accs.keys(), key=lambda s: (train_accs[s], s), reverse=True)[1]
        second_upper = intervals[second_src][1]
        beta_choose_best = bool(best_lower > second_upper)

        # fallback source calibrated on train
        # explicit mapping to replay field names
        ext_to_src = {
            METHOD_L1: "L1",
            METHOD_S1: "S1",
            METHOD_TALE: "TALE",
        }
        fallback_source_short = max(EXTERNAL_METHODS, key=lambda m: (train_accs[ext_to_src[m]], m))
        fallback_short = ext_to_src[fallback_source_short]

        regime_decisions["folds"][str(fold)] = {
            "train_size": len(train_rows),
            "test_size": len(test_rows),
            "train_source_accuracy": train_accs,
            "spread": spread,
            "dominant_regime": dominant,
            "best_train_source": best_train_src,
            "beta_shrinkage_intervals": {k: {"low": v[0], "high": v[1]} for k, v in intervals.items()},
            "beta_choose_best": beta_choose_best,
            "calibrated_fallback_source": fallback_short,
        }

        for e in test_rows:
            exid = e["example_id"]
            gold = e["gold_answer_canonical"]

            # 11) cv5 raw spread
            if spread > 0.05:
                ans = e[f"{best_train_src}_ans"]
                meta = {"fold": fold, "mode": "best_source", "best_train_source": best_train_src, "spread": spread}
            else:
                ans = e["pooled4_ans"]
                meta = {"fold": fold, "mode": "pooled4", "best_train_source": best_train_src, "spread": spread}
            ok = int(ans is not None and gold is not None and str(ans) == str(gold))
            selector_preds["cv5_raw_spread_regime_selector"][exid] = {"answer": ans, "ok": ok, "meta": meta}

            # 12) beta shrinkage
            if beta_choose_best:
                ans = e[f"{best_train_src}_ans"]
                mode = "best_source_beta_conservative"
            else:
                ans = e["pooled4_ans"]
                mode = "pooled4_beta_fallback"
            ok = int(ans is not None and gold is not None and str(ans) == str(gold))
            selector_preds["beta_shrinkage_regime_selector"][exid] = {
                "answer": ans,
                "ok": ok,
                "meta": {"fold": fold, "mode": mode, "best_train_source": best_train_src, "beta_choose_best": beta_choose_best},
            }

            # 13) frontier_fallback_calibrated (agreement fallback calibrated)
            ext_majority_ans, ext_majority_count = external_majority(e["L1_ans"], e["S1_ans"], e["TALE_ans"])
            if ext_majority_count >= 2:
                if ext_majority_ans == e["frontier_ans"]:
                    ans = e["frontier_ans"]
                    mode = "frontier_majority_match"
                else:
                    ans = ext_majority_ans
                    mode = "external_majority"
            else:
                ans = e[f"{fallback_short}_ans"]
                mode = "no_majority_calibrated_fallback"
            ok = int(ans is not None and gold is not None and str(ans) == str(gold))
            selector_preds["frontier_fallback_calibrated"][exid] = {
                "answer": ans,
                "ok": ok,
                "meta": {"fold": fold, "mode": mode, "fallback_source": fallback_short, "ext_majority_count": ext_majority_count},
            }

            # 14) pooled4_with_calibrated_no_majority_fallback
            pool_ans, pool_action = pooled4_with_fallback(e["frontier_ans"], e["L1_ans"], e["S1_ans"], e["TALE_ans"])
            if pool_action == "fallback_frontier_no_majority":
                ans = e[f"{fallback_short}_ans"]
                mode = "pooled_no_majority_calibrated_fallback"
            else:
                ans = pool_ans
                mode = pool_action
            ok = int(ans is not None and gold is not None and str(ans) == str(gold))
            selector_preds["pooled4_with_calibrated_no_majority_fallback"][exid] = {
                "answer": ans,
                "ok": ok,
                "meta": {"fold": fold, "mode": mode, "fallback_source": fallback_short},
            }

            # 15) dominant_source_veto
            pool_ans, pool_action = pooled4_with_fallback(e["frontier_ans"], e["L1_ans"], e["S1_ans"], e["TALE_ans"])
            if dominant and pool_ans != e[f"{best_train_src}_ans"]:
                ans = e[f"{best_train_src}_ans"]
                mode = "dominant_veto_applied"
            else:
                ans = pool_ans
                mode = "pooled_or_not_dominant"
            ok = int(ans is not None and gold is not None and str(ans) == str(gold))
            selector_preds["dominant_source_veto"][exid] = {
                "answer": ans,
                "ok": ok,
                "meta": {"fold": fold, "mode": mode, "dominant": dominant, "best_train_source": best_train_src},
            }

            # 16) majority_requires_dominant_source_when_dominant
            pool_ans, pool_action = pooled4_with_fallback(e["frontier_ans"], e["L1_ans"], e["S1_ans"], e["TALE_ans"])
            dominant_ans = e[f"{best_train_src}_ans"]
            if dominant and pool_action != "fallback_frontier_no_majority":
                # Majority exists; require majority to include dominant source answer
                if pool_ans != dominant_ans:
                    ans = dominant_ans
                    mode = "majority_rejected_use_dominant"
                else:
                    ans = pool_ans
                    mode = "majority_includes_dominant"
            else:
                ans = pool_ans
                mode = "not_dominant_or_no_majority"
            ok = int(ans is not None and gold is not None and str(ans) == str(gold))
            selector_preds["majority_requires_dominant_source_when_dominant"][exid] = {
                "answer": ans,
                "ok": ok,
                "meta": {"fold": fold, "mode": mode, "dominant": dominant, "best_train_source": best_train_src},
            }

    # Summary tables
    method_rows = []
    for m in ["frontier", "L1", "S1", "TALE"]:
        correct = sum(selector_preds[m][e["example_id"]]["ok"] for e in examples)
        method_rows.append({"method": m, "correct": correct, "total": n, "accuracy": round(correct / n, 6)})
    write_csv(out_root / f"{provider_label}_method_accuracy_summary.csv", method_rows, ["method", "correct", "total", "accuracy"])

    selector_rows = []
    for name, pred in selector_preds.items():
        correct = sum(int(v["ok"]) for v in pred.values())
        selector_rows.append(
            {
                "selector": name,
                "correct": correct,
                "total": n,
                "accuracy": round(correct / n, 6),
                "delta_vs_agreement_only": round((correct - sum(v["ok"] for v in selector_preds["agreement_only_2of3_against_frontier"].values())) / n, 6),
                "delta_vs_pooled4": round((correct - sum(v["ok"] for v in selector_preds["pooled4_with_fallback"].values())) / n, 6),
            }
        )
    selector_rows = sorted(selector_rows, key=lambda r: (-r["accuracy"], r["selector"]))
    write_csv(
        out_root / f"{provider_label}_selector_replay_summary.csv",
        selector_rows,
        ["selector", "correct", "total", "accuracy", "delta_vs_agreement_only", "delta_vs_pooled4"],
    )

    cv_selector_names = set(cv_keys + ["cv5_raw_spread_regime_selector"])
    cv_rows = [r for r in selector_rows if r["selector"] in cv_selector_names]
    write_csv(
        out_root / f"{provider_label}_cv_selector_summary.csv",
        cv_rows,
        ["selector", "correct", "total", "accuracy", "delta_vs_agreement_only", "delta_vs_pooled4"],
    )

    # Recovery/regression vs frontier
    rec_reg_rows = []
    frontier_map = selector_preds["frontier"]
    for name, pred in selector_preds.items():
        rec = 0
        reg = 0
        for e in examples:
            exid = e["example_id"]
            f_ok = int(frontier_map[exid]["ok"])
            s_ok = int(pred[exid]["ok"])
            if s_ok and not f_ok:
                rec += 1
            elif f_ok and not s_ok:
                reg += 1
        rec_reg_rows.append(
            {
                "selector": name,
                "recoveries_vs_frontier": rec,
                "regressions_vs_frontier": reg,
                "net_recovery": rec - reg,
            }
        )
    rec_reg_rows = sorted(rec_reg_rows, key=lambda r: (-r["net_recovery"], r["selector"]))
    write_csv(
        out_root / f"{provider_label}_recovery_regression_summary.csv",
        rec_reg_rows,
        ["selector", "recoveries_vs_frontier", "regressions_vs_frontier", "net_recovery"],
    )

    # Case-level table
    case_rows = []
    selectors_for_case = sorted(selector_preds.keys())
    for e in examples:
        exid = e["example_id"]
        row = {
            "example_id": exid,
            "frontier_ans": e["frontier_ans"],
            "L1_ans": e["L1_ans"],
            "S1_ans": e["S1_ans"],
            "TALE_ans": e["TALE_ans"],
            "frontier_ok": e["frontier_ok"],
            "L1_ok": e["L1_ok"],
            "S1_ok": e["S1_ok"],
            "TALE_ok": e["TALE_ok"],
            "gold_answer_canonical": e["gold_answer_canonical"],
        }
        for s in selectors_for_case:
            row[f"{s}_ans"] = selector_preds[s][exid]["answer"]
            row[f"{s}_ok"] = selector_preds[s][exid]["ok"]
        case_rows.append(row)
    write_csv(out_root / f"{provider_label}_case_level_selector_results.csv", case_rows)

    # No-majority fallback analysis
    nm_rows = []
    for e in examples:
        exid = e["example_id"]
        pool_action = e["pooled4_action"]
        ext_majority_ans, ext_majority_count = external_majority(e["L1_ans"], e["S1_ans"], e["TALE_ans"])
        no_majority = bool(pool_action == "fallback_frontier_no_majority" or ext_majority_count < 2)
        if not no_majority:
            continue
        row = {
            "example_id": exid,
            "no_majority_flag": 1,
            "frontier_ok": e["frontier_ok"],
            "agreement_ok": selector_preds["agreement_only_2of3_against_frontier"][exid]["ok"],
            "pooled4_ok": selector_preds["pooled4_with_fallback"][exid]["ok"],
            "frontier_fallback_calibrated_ok": selector_preds["frontier_fallback_calibrated"][exid]["ok"],
            "pooled4_with_calibrated_no_majority_fallback_ok": selector_preds["pooled4_with_calibrated_no_majority_fallback"][exid]["ok"],
            "S1_ok": e["S1_ok"],
            "L1_ok": e["L1_ok"],
            "TALE_ok": e["TALE_ok"],
        }
        nm_rows.append(row)
    write_csv(out_root / f"{provider_label}_no_majority_fallback_analysis.csv", nm_rows)

    write_json(out_root / f"{provider_label}_regime_decision_summary.json", regime_decisions)

    # Extra stats for Mistral
    if provider_label == "mistral_full300":
        # paired CI summary vs key baselines
        ci_rows = []
        baseline_selectors = [
            "agreement_only_2of3_against_frontier",
            "pooled4_with_fallback",
            "always_s1",
            "frontier",
            "L1",
            "S1",
            "TALE",
        ]
        for s in selector_preds.keys():
            if s in baseline_selectors:
                continue
            for b in baseline_selectors:
                diffs = [
                    int(selector_preds[s][e["example_id"]]["ok"]) - int(selector_preds[b][e["example_id"]]["ok"])
                    for e in examples
                ]
                obs, lo, hi = paired_bootstrap_ci(diffs, n_boot=5000, seed=37)
                ci_rows.append(
                    {
                        "selector_a": s,
                        "selector_b": b,
                        "n": n,
                        "delta_acc": round(obs, 6),
                        "ci95_low": round(lo, 6),
                        "ci95_high": round(hi, 6),
                    }
                )
        write_csv(out_root / "mistral_full300_paired_ci_summary.csv", ci_rows)

        # McNemar summary for selected comparisons
        mcnemar_rows = []
        compare_pairs = [
            ("cv5_raw_spread_regime_selector", "pooled4_with_fallback"),
            ("cv5_raw_spread_regime_selector", "agreement_only_2of3_against_frontier"),
            ("beta_shrinkage_regime_selector", "pooled4_with_fallback"),
            ("majority_requires_dominant_source_when_dominant", "pooled4_with_fallback"),
            ("dominant_source_veto", "pooled4_with_fallback"),
            ("always_s1", "pooled4_with_fallback"),
            ("always_s1", "agreement_only_2of3_against_frontier"),
        ]
        for a, b in compare_pairs:
            av = [int(selector_preds[a][e["example_id"]]["ok"]) for e in examples]
            bv = [int(selector_preds[b][e["example_id"]]["ok"]) for e in examples]
            m = mcnemar(av, bv)
            mcnemar_rows.append({"selector_a": a, "selector_b": b, **m})
        write_csv(out_root / "mistral_full300_mcnemar_summary.csv", mcnemar_rows)

    return {
        "n_examples": n,
        "best_single_source": best_src,
        "source_accuracy": src_accs,
        "selector_summary_rows": selector_rows,
        "recovery_regression_rows": rec_reg_rows,
    }


def parse_retry_counts(log_path: Path) -> dict[str, int]:
    out = {"http_429_mentions": 0, "api_retry_mentions": 0}
    if not log_path.exists():
        return out
    with log_path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if "429" in line:
                out["http_429_mentions"] += 1
            if "api_retry" in line.lower() or "retry" in line.lower():
                out["api_retry_mentions"] += 1
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-root", type=Path, default=OUT_ROOT_DEFAULT)
    args = parser.parse_args()

    out_root = args.out_root
    out_root.mkdir(parents=True, exist_ok=True)

    # Source files (fixed for this task)
    cohere_orig = REPO_ROOT / "outputs/cohere_targeted_no_majority_fallback_rerun_20260523/cohere_real_model_cost_normalized_validation_20260523T235741Z/per_example_records.jsonl"
    cohere_repair = REPO_ROOT / "outputs/repair_incomplete_cohere_mistral_runs_20260524/cohere_missing_methods_repair_20260524T003751Z/cohere_real_model_cost_normalized_validation_20260524T003905Z/per_example_records.jsonl"
    mistral_orig = REPO_ROOT / "outputs/mistral_full300_regime_selector_validation_20260523/cohere_real_model_cost_normalized_validation_20260523T233843Z/per_example_records.jsonl"
    mistral_repair = REPO_ROOT / "outputs/repair_incomplete_cohere_mistral_runs_20260524/mistral_missing_methods_repair_20260524T003751Z/cohere_real_model_cost_normalized_validation_20260524T003905Z/per_example_records.jsonl"

    inventory = {
        "cohere_original": inventory_entry(cohere_orig),
        "cohere_repair": inventory_entry(cohere_repair),
        "mistral_original": inventory_entry(mistral_orig),
        "mistral_repair": inventory_entry(mistral_repair),
    }
    write_json(out_root / "source_file_inventory.json", inventory)

    cohere_original_rows = read_jsonl(cohere_orig)
    cohere_repair_rows = read_jsonl(cohere_repair)
    mistral_original_rows = read_jsonl(mistral_orig)
    mistral_repair_rows = read_jsonl(mistral_repair)

    # Cohere merge
    cohere_merge = merge_rows(
        provider_label="cohere",
        original_rows=cohere_original_rows,
        repair_rows=cohere_repair_rows,
        expected_examples=47,
        allow_benign_dedup=False,
    )
    write_json(out_root / "cohere_merge_integrity_summary.json", cohere_merge.summary)
    write_csv(out_root / "cohere_merge_method_counts.csv", [{"method": k, "count": v} for k, v in sorted(cohere_merge.summary["method_counts"].items())], ["method", "count"])
    write_csv(out_root / "cohere_merge_duplicate_rows.csv", cohere_merge.duplicate_rows)
    write_csv(out_root / "cohere_merge_missing_rows.csv", cohere_merge.missing_rows, ["example_id", "missing_method"])
    if cohere_merge.pass_integrity:
        write_jsonl(out_root / "cohere_targeted_merged_per_example_records.jsonl", cohere_merge.merged_rows)

    # Mistral merge
    mistral_merge = merge_rows(
        provider_label="mistral",
        original_rows=mistral_original_rows,
        repair_rows=mistral_repair_rows,
        expected_examples=300,
        allow_benign_dedup=True,
    )
    write_json(out_root / "mistral_merge_integrity_summary.json", mistral_merge.summary)
    write_csv(out_root / "mistral_merge_method_counts.csv", [{"method": k, "count": v} for k, v in sorted(mistral_merge.summary["method_counts"].items())], ["method", "count"])
    write_csv(out_root / "mistral_merge_duplicate_rows.csv", mistral_merge.duplicate_rows)
    write_csv(out_root / "mistral_merge_missing_rows.csv", mistral_merge.missing_rows, ["example_id", "missing_method"])
    (out_root / "mistral_merge_duplicate_resolution.md").write_text(
        (mistral_merge.duplicate_resolution_md or "No duplicate keys detected.\n"), encoding="utf-8"
    )
    if mistral_merge.pass_integrity:
        write_jsonl(out_root / "mistral_full300_merged_per_example_records.jsonl", mistral_merge.merged_rows)

    replay_summary: dict[str, Any] = {
        "cohere_merge_pass": cohere_merge.pass_integrity,
        "mistral_merge_pass": mistral_merge.pass_integrity,
    }

    if cohere_merge.pass_integrity:
        cohere_replay = replay_artifact(provider_label="cohere_targeted", merged_rows=cohere_merge.merged_rows, out_root=out_root)
        replay_summary["cohere_replay"] = cohere_replay

    if mistral_merge.pass_integrity:
        mistral_replay = replay_artifact(provider_label="mistral_full300", merged_rows=mistral_merge.merged_rows, out_root=out_root)
        replay_summary["mistral_replay"] = mistral_replay

    # Comparison files
    if mistral_merge.pass_integrity:
        sel_rows = {}
        with (out_root / "mistral_full300_selector_replay_summary.csv").open("r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                sel_rows[row["selector"]] = float(row["accuracy"])
        original = {
            "frontier": 235 / 300,
            "L1": 217 / 300,
            "S1": 269 / 300,
            "TALE": 189 / 300,
            "agreement_only_2of3_against_frontier": 256 / 300,
            "pooled4_with_fallback": 251 / 300,
            "always_s1": 269 / 300,
        }
        cmp_rows = []
        for k, orig_acc in original.items():
            rerun_acc = sel_rows.get(k)
            cmp_rows.append(
                {
                    "metric": k,
                    "original_accuracy": round(orig_acc, 6),
                    "rerun_accuracy": round(rerun_acc, 6) if rerun_acc is not None else "",
                    "delta_rerun_minus_original": round((rerun_acc - orig_acc), 6) if rerun_acc is not None else "",
                }
            )
        write_csv(out_root / "mistral_original_vs_rerun_comparison.csv", cmp_rows)

        # Source ranking stability note
        method_rows: list[dict[str, Any]] = []
        with (out_root / "mistral_full300_method_accuracy_summary.csv").open("r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                method_rows.append(row)
        ranked = sorted(method_rows, key=lambda r: float(r["accuracy"]), reverse=True)
        lines = [
            "# Mistral Source Ranking Stability",
            "",
            "Original ranking (provided): S1 > frontier > L1 > TALE.",
            "Rerun ranking (merged repaired): " + " > ".join(r["method"] for r in ranked),
            "",
            "| method | rerun_accuracy |",
            "|---|---:|",
        ]
        for r in ranked:
            lines.append(f"| {r['method']} | {float(r['accuracy']):.6f} |")
        (out_root / "mistral_source_ranking_stability.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Cohere targeted vs canonical context note
    cohere_ctx = [
        "# Cohere Targeted vs Canonical Context",
        "",
        "- The targeted Cohere set is failure-selected and biased.",
        "- Any gains/losses in this replay are diagnostic only and not canonical population estimates.",
        "- Canonical Cohere Final-300 evidence remains in dated canonical reports; targeted results are used only for fallback-hypothesis triage.",
    ]
    (out_root / "cohere_targeted_vs_canonical_context.md").write_text("\n".join(cohere_ctx) + "\n", encoding="utf-8")

    # Retry/429 summaries for Mistral question
    mistral_original_log = REPO_ROOT / "outputs/mistral_full300_regime_selector_validation_20260523/mistral_full300_live_20260523T233843Z.log"
    mistral_repair_log = REPO_ROOT / "outputs/repair_incomplete_cohere_mistral_runs_20260524/mistral_missing_methods_repair_20260524T003751Z.log"
    retry_summary = {
        "mistral_original_log": str(mistral_original_log),
        "mistral_repair_log": str(mistral_repair_log),
        "original_log_counts": parse_retry_counts(mistral_original_log),
        "repair_log_counts": parse_retry_counts(mistral_repair_log),
    }
    write_json(out_root / "mistral_retry_429_summary.json", retry_summary)

    write_json(out_root / "replay_execution_summary.json", replay_summary)

    # Manifest
    created_files = sorted(str(p.relative_to(REPO_ROOT)) for p in out_root.rglob("*") if p.is_file())
    manifest = {
        "task": "merge_repaired_runs_and_replay_selectors_20260524",
        "api_calls_made": False,
        "active_jobs_touched": False,
        "source_files": {
            "cohere_original": str(cohere_orig.relative_to(REPO_ROOT)),
            "cohere_repair": str(cohere_repair.relative_to(REPO_ROOT)),
            "mistral_original": str(mistral_orig.relative_to(REPO_ROOT)),
            "mistral_repair": str(mistral_repair.relative_to(REPO_ROOT)),
        },
        "scripts_used": [
            "scripts/merge_repaired_runs_and_replay_selectors.py",
            "experiments/support_aware_selector.py (agreement_only_2of3_against_frontier)",
        ],
        "merge_outputs": [
            "cohere_targeted_merged_per_example_records.jsonl",
            "mistral_full300_merged_per_example_records.jsonl",
            "cohere_merge_integrity_summary.json",
            "mistral_merge_integrity_summary.json",
            "cohere_merge_method_counts.csv",
            "mistral_merge_method_counts.csv",
            "cohere_merge_duplicate_rows.csv",
            "mistral_merge_duplicate_rows.csv",
            "cohere_merge_missing_rows.csv",
            "mistral_merge_missing_rows.csv",
            "mistral_merge_duplicate_resolution.md",
        ],
        "created_files": created_files,
    }
    write_json(out_root / "manifest.json", manifest)


if __name__ == "__main__":
    main()
