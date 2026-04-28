#!/usr/bin/env python3
"""Offline analysis for outputs/semantic_diversity_controller_diagnostic_<ts>/ (no API calls)."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

FOCUS_METHODS = [
    "external_l1_max",
    "strict_f3",
    "direct_reserve_semantic_frontier_v1",
    "semantic_minimum_maturation_plus_direct_reserve_v1",
    "semantic_minimum_maturation_frontier_v1_d3",
    "branching_necessity_gate_v1",
]

NEW_METHODS = [
    "direct_reserve_semantic_frontier_v1",
    "semantic_minimum_maturation_plus_direct_reserve_v1",
    "semantic_minimum_maturation_frontier_v1_d3",
    "branching_necessity_gate_v1",
]


def _read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _f(x: Any, default: float = 0.0) -> float:
    try:
        return float(str(x).strip())
    except (TypeError, ValueError):
        return default


def _i(x: Any, default: int = 0) -> int:
    try:
        return int(float(str(x).strip()))
    except (TypeError, ValueError):
        return default


def _wait_manifest(run_dir: Path, job_id: str | None, poll: int, max_min: int) -> bool:
    manifest = run_dir / "manifest.json"
    per_case = run_dir / "per_case_results.csv"
    deadline = time.time() + max_min * 60
    while time.time() < deadline:
        if manifest.exists() and per_case.exists():
            return True
        if job_id:
            r = subprocess.run(
                ["sacct", "-j", job_id, "--format=JobID,State", "--noheader", "--parsable2"],
                capture_output=True,
                text=True,
                check=False,
            )
            for ln in r.stdout.splitlines():
                parts = ln.split("|")
                if len(parts) >= 2 and parts[0] == job_id:
                    st = parts[1]
                    if st in {"FAILED", "CANCELLED", "TIMEOUT", "NODE_FAIL", "OUT_OF_MEMORY"}:
                        print(f"job_terminal_state={st}", file=sys.stderr)
                        return manifest.exists() and per_case.exists()
        time.sleep(poll)
    return manifest.exists() and per_case.exists()


def _paired_stats(
    rows: list[dict[str, Any]],
    *,
    left: str,
    right: str,
) -> tuple[int, float, dict[str, int]]:
    """matched pairs (same example_id+budget), mean(delta is_correct), win/loss/tie."""
    by_l: dict[tuple[str, str], dict[str, Any]] = {}
    by_r: dict[tuple[str, str], dict[str, Any]] = {}
    for r in rows:
        if r.get("error"):
            continue
        k = (str(r.get("example_id")), str(r.get("budget")))
        m = str(r.get("method"))
        if m == left:
            by_l[k] = r
        elif m == right:
            by_r[k] = r
    keys = sorted(set(by_l) & set(by_r))
    wins = losses = ties = 0
    deltas: list[float] = []
    for k in keys:
        li = _i(by_l[k].get("is_correct"))
        ri = _i(by_r[k].get("is_correct"))
        d = float(li - ri)
        deltas.append(d)
        if d > 0:
            wins += 1
        elif d < 0:
            losses += 1
        else:
            ties += 1
    mu = mean(deltas) if deltas else 0.0
    return len(keys), mu, {"win": wins, "loss": losses, "tie": ties}


def _budget_breakdown(rows: list[dict[str, Any]], left: str, right: str) -> dict[str, tuple[int, float]]:
    out: dict[str, tuple[int, float]] = {}
    for b in {"4", "6", "8"}:
        sub = [r for r in rows if str(r.get("budget")) == b]
        n, mu, _ = _paired_stats(sub, left=left, right=right)
        out[b] = (n, mu)
    return out


def _safe_mean(vals: list[float]) -> float:
    return mean(vals) if vals else float("nan")


def analyze(*, run_dir: Path, ts: str, write_doc: Path) -> dict[str, Any]:
    per_case_path = run_dir / "per_case_results.csv"
    rows = _read_csv(per_case_path)
    rows_ok = [r for r in rows if not r.get("error")]

    acc_src = _read_csv(run_dir / "method_accuracy_summary.csv")
    token_rows = _read_csv(run_dir / "token_cost_latency_summary.csv")
    sem_rows = _read_csv(run_dir / "semantic_family_summary.csv")
    absent_audit = _read_csv(run_dir / "absent_from_tree_rescue_audit.csv")
    tax_rows = _read_csv(run_dir / "failure_taxonomy.csv")
    inc_rows = _read_csv(run_dir / "incumbent_replacement_audit.csv")

    by_method: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows_ok:
        by_method[str(r.get("method"))].append(r)

    acc_table: list[dict[str, Any]] = []
    if acc_src:
        for r in acc_src:
            acc_table.append(dict(r))
    else:
        for m, lst in sorted(by_method.items()):
            n = len(lst)
            acc_table.append(
                {
                    "method": m,
                    "n": str(n),
                    "accuracy": sum(_i(x.get("is_correct")) for x in lst) / max(1, n),
                    "avg_actions": _safe_mean([_f(x.get("actions_used")) for x in lst]),
                }
            )

    # Enrich acc_table with tokens/cost/latency from token_cost_latency_summary or per_case
    tok_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    for t in token_rows:
        tok_by_key[(str(t.get("example_id")), str(t.get("budget")), str(t.get("method")))] = t

    for row in acc_table:
        m = str(row.get("method"))
        lst = by_method.get(m, [])
        ins, outs, costs, lats = [], [], [], []
        for r in lst:
            tk = tok_by_key.get((str(r.get("example_id")), str(r.get("budget")), m))
            if tk:
                ins.append(_f(tk.get("estimated_input_tokens")))
                outs.append(_f(tk.get("estimated_output_tokens")))
                costs.append(_f(tk.get("estimated_cost_usd_proxy")))
                lats.append(_f(tk.get("estimated_latency_seconds")))
            else:
                ins.append(_f(r.get("estimated_input_tokens")))
                outs.append(_f(r.get("estimated_output_tokens")))
                costs.append(_f(r.get("estimated_cost_usd_proxy")))
                lats.append(_f(r.get("estimated_latency_seconds")))
        row["avg_estimated_input_tokens"] = _safe_mean([x for x in ins if x == x])
        row["avg_estimated_output_tokens"] = _safe_mean([x for x in outs if x == x])
        row["avg_estimated_cost_usd_proxy"] = _safe_mean([x for x in costs if x == x])
        row["avg_estimated_latency_seconds"] = _safe_mean([x for x in lats if x == x])

    best_row = max(acc_table, key=lambda r: float(r.get("accuracy") or 0)) if acc_table else {}
    if not best_row:
        raise SystemExit("empty accuracy table")
    strict = next((r for r in acc_table if r.get("method") == "strict_f3"), {})
    ext = next((r for r in acc_table if r.get("method") == "external_l1_max"), {})

    # Paired
    paired_vs_sf = {}
    paired_vs_ext = {}
    sf_vs_ext_n, sf_vs_ext_mu, sf_vs_ext_wlt = _paired_stats(rows_ok, left="strict_f3", right="external_l1_max")
    for m in NEW_METHODS:
        if any(str(r.get("method")) == m for r in rows_ok):
            n, mu, wlt = _paired_stats(rows_ok, left=m, right="strict_f3")
            paired_vs_sf[m] = {"n": n, "mean_delta": mu, **wlt}
            n2, mu2, wlt2 = _paired_stats(rows_ok, left=m, right="external_l1_max")
            paired_vs_ext[m] = {"n": n2, "mean_delta": mu2, **wlt2}

    bd_sf = _budget_breakdown(rows_ok, "strict_f3", "external_l1_max")

    # Wins strict in >=2 budgets for each new method
    budget_wins: dict[str, Any] = {}
    for m in NEW_METHODS:
        wins_b = 0
        for b in ["4", "6", "8"]:
            sub = [r for r in rows_ok if str(r.get("budget")) == b]
            _, mu, wl = _paired_stats(sub, left=m, right="strict_f3")
            if mu > 0:
                wins_b += 1
        budget_wins[m] = wins_b

    # Rescue table
    keys = sorted({(str(r.get("example_id")), str(r.get("budget"))) for r in rows_ok})
    rescue_rows: list[dict[str, Any]] = []

    def corr(method: str, eid: str, bud: str) -> int:
        for r in rows_ok:
            if str(r.get("method")) == method and str(r.get("example_id")) == eid and str(r.get("budget")) == bud:
                return _i(r.get("is_correct"))
        return 0

    for eid, bud in keys:
        gold = ""
        short_q = ""
        for r in rows_ok:
            if str(r.get("example_id")) == eid and str(r.get("budget")) == bud:
                gold = str(r.get("gold_answer") or "")
                short_q = str(r.get("question") or "")[:140]
                break
        ext_c = corr("external_l1_max", eid, bud)
        sf_c = corr("strict_f3", eid, bud)
        dr_c = corr("direct_reserve_semantic_frontier_v1", eid, bud)
        spd_c = corr("semantic_minimum_maturation_plus_direct_reserve_v1", eid, bud)

        new_scores = []
        for nm in NEW_METHODS:
            new_scores.append((_i(corr(nm, eid, bud)), nm))
        best_nm = max(new_scores, key=lambda x: (x[0], x[1]))[1] if new_scores else ""

        dr_rescue = bool(dr_c == 1 and sf_c == 0)
        spd_rescue = bool(spd_c == 1 and sf_c == 0)

        if ext_c == 1 and sf_c == 0 and dr_c == 0 and spd_c == 0:
            rt = "external_only_still_unsolved"
        elif dr_rescue and spd_rescue:
            rt = "both_rescue"
        elif dr_rescue:
            rt = "direct_reserve_rescue"
        elif spd_rescue:
            rt = "semantic_plus_direct_reserve_rescue"
        elif sf_c == 1 and max(_i(corr(nm, eid, bud)) for nm in NEW_METHODS) == 0:
            rt = "strict_f3_regression"
        elif ext_c == sf_c == dr_c == spd_c == 1:
            rt = "all_correct"
        elif ext_c == sf_c == dr_c == spd_c == 0:
            rt = "all_wrong"
        else:
            rt = "other"

        rescue_rows.append(
            {
                "example_id": eid,
                "budget": bud,
                "gold_answer": gold,
                "external_l1_max_correct": ext_c,
                "strict_f3_correct": sf_c,
                "direct_reserve_semantic_frontier_v1_correct": dr_c,
                "semantic_minimum_maturation_plus_direct_reserve_v1_correct": spd_c,
                "best_new_method": best_nm,
                "rescue_type": rt,
                "short_question": short_q.replace("\n", " "),
            }
        )

    rescue_cols = [
        "example_id",
        "budget",
        "gold_answer",
        "external_l1_max_correct",
        "strict_f3_correct",
        "direct_reserve_semantic_frontier_v1_correct",
        "semantic_minimum_maturation_plus_direct_reserve_v1_correct",
        "best_new_method",
        "rescue_type",
        "short_question",
    ]
    rescue_path = run_dir / "rescue_case_table.csv"
    with rescue_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rescue_cols)
        w.writeheader()
        w.writerows(rescue_rows)

    # Semantic aggregates by method
    sem_by_m: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows_ok:
        sem_by_m[str(r.get("method"))].append(r)

    def agg_sem(m: str) -> dict[str, float]:
        lst = sem_by_m.get(m, [])
        sfc = [_f(x.get("semantic_family_count")) for x in lst if str(x.get("semantic_family_count") or "").strip()]
        frr = [_f(x.get("family_redundancy_ratio")) for x in lst if str(x.get("family_redundancy_ratio") or "").strip()]
        sh2 = [_f(x.get("share_families_depth_ge_2")) for x in lst if str(x.get("share_families_depth_ge_2") or "").strip()]
        sh3 = [_f(x.get("share_families_depth_ge_3")) for x in lst if str(x.get("share_families_depth_ge_3") or "").strip()]
        im = sum(1 for x in lst if _i(x.get("immediate_miss_proxy")) == 1)
        ab = sum(1 for x in lst if _i(x.get("absent_from_tree_meta")) == 1)
        pns = sum(1 for x in lst if _i(x.get("present_not_selected_infer")) == 1)
        return {
            "avg_semantic_family_count": _safe_mean(sfc),
            "avg_family_redundancy_ratio": _safe_mean(frr),
            "avg_share_depth_ge_2": _safe_mean(sh2),
            "avg_share_depth_ge_3": _safe_mean(sh3),
            "immediate_miss_rows": float(im),
            "absent_from_tree_rows": float(ab),
            "present_not_selected_rows": float(pns),
        }

    tax_counter = Counter()
    for r in tax_rows:
        tax_counter[str(r.get("category"))] += _i(r.get("count"))

    inc_stats: dict[str, Any] = {}
    for m in (
        "direct_reserve_semantic_frontier_v1",
        "semantic_minimum_maturation_plus_direct_reserve_v1",
    ):
        ir = [r for r in inc_rows if str(r.get("method")) == m]
        if not ir:
            continue
        replaced = sum(1 for x in ir if str(x.get("incumbent_replaced")).lower() in {"1", "true", "yes"})
        inc_stats[m] = {"n": len(ir), "incumbent_replaced_rows": replaced}

    # Pareto-ish: accuracy vs avg actions
    pareto = []
    for r in acc_table:
        pareto.append(
            {
                "method": r.get("method"),
                "accuracy": _f(r.get("accuracy")),
                "avg_actions": _f(r.get("avg_actions")),
            }
        )

    best_acc = _f(best_row.get("accuracy"))
    s_acc = _f(strict.get("accuracy"))
    e_acc = _f(ext.get("accuracy"))

    rec = "diagnostic_only"
    larger = "no"
    if best_acc > s_acc + 1e-6:
        rec = "best_new_beats_strict_f3_on_aggregate"
    if e_acc >= best_acc + 1e-6:
        rec += ";external_l1_max_still_best_or_tied"

    # Heuristic larger run
    any_consistent = any(budget_wins.get(m, 0) >= 2 for m in NEW_METHODS)
    if any_consistent and best_acc > s_acc:
        larger = "yes_only_top_methods"

    final_row = {
        "best_method": str(best_row.get("method") or ""),
        "best_accuracy": f"{best_acc:.6f}",
        "strict_f3_accuracy": f"{s_acc:.6f}",
        "external_l1_max_accuracy": f"{e_acc:.6f}",
        "best_minus_strict_f3": f"{best_acc - s_acc:.6f}",
        "best_minus_external_l1_max": f"{best_acc - e_acc:.6f}",
        "best_avg_actions": f'{_f(best_row.get("avg_actions")):.4f}',
        "strict_f3_avg_actions": f'{_f(strict.get("avg_actions")):.4f}',
        "external_l1_max_avg_actions": f'{_f(ext.get("avg_actions")):.4f}',
        "recommendation": rec,
        "larger_run_recommended": larger,
        "manuscript_change_recommended": "no_diagnostic_only",
    }
    final_path = run_dir / "final_decision_summary.csv"
    with final_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(final_row.keys()))
        w.writeheader()
        w.writerow(final_row)

    # Markdown
    lines: list[str] = []
    lines.append(f"# Semantic diversity loss-full result analysis ({ts})")
    lines.append("")
    lines.append("## Job / data inputs")
    lines.append("")
    lines.append(f"- Run directory: `{run_dir.relative_to(REPO_ROOT)}`")
    lines.append(f"- Rows in `per_case_results.csv` (non-error): **{len(rows_ok)}**")
    manifest = {}
    mp = run_dir / "manifest.json"
    if mp.exists():
        try:
            manifest = json.loads(mp.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            manifest = {}
    lines.append(f"- Manifest `n_selected_cases`: **{manifest.get('n_selected_cases', '?')}**")
    lines.append("")
    lines.append("## A. Did new ideas improve results?")
    lines.append("")
    lines.append(
        f"- Aggregate: best method **`{best_row.get('method')}`** at accuracy **{best_acc:.4f}** vs strict_f3 **{s_acc:.4f}** vs external_l1_max **{e_acc:.4f}**."
    )
    lines.append("- Interpretation: **mixed / diagnostic only** unless paired deltas are consistent.")
    lines.append("")
    lines.append("### Method accuracy summary")
    lines.append("")
    lines.append("| method | n | accuracy | avg_actions | avg_est_cost_proxy | avg_latency |")
    lines.append("|---|---|---|---|---|---|")
    for r in sorted(acc_table, key=lambda x: str(x.get("method"))):
        lines.append(
            f"| {r.get('method')} | {r.get('n')} | {float(r.get('accuracy') or 0):.4f} | "
            f"{_f(r.get('avg_actions')):.2f} | {_f(r.get('avg_estimated_cost_usd_proxy')):.6f} | {_f(r.get('avg_estimated_latency_seconds')):.4f} |"
        )
    lines.append("")
    lines.append("### Paired deltas")
    lines.append("")
    lines.append(
        f"- strict_f3 vs external_l1_max: **n={sf_vs_ext_n}**, mean(delta strict - external)= **{sf_vs_ext_mu:.4f}**, "
        f"wins/losses/ties={sf_vs_ext_wlt}"
    )
    lines.append("")
    for m in NEW_METHODS:
        if m not in paired_vs_sf:
            continue
        lines.append(
            f"- `{m}` vs strict_f3: n={paired_vs_sf[m]['n']}, mean_delta={paired_vs_sf[m]['mean_delta']:.4f}, "
            f"wins={paired_vs_sf[m]['win']} losses={paired_vs_sf[m]['loss']} ties={paired_vs_sf[m]['tie']}"
        )
        lines.append(
            f"  - vs external_l1_max: n={paired_vs_ext[m]['n']}, mean_delta={paired_vs_ext[m]['mean_delta']:.4f}, "
            f"wins={paired_vs_ext[m]['win']} losses={paired_vs_ext[m]['loss']} ties={paired_vs_ext[m]['tie']}"
        )
        lines.append(f"  - budgets with positive mean delta vs strict_f3: **{budget_wins.get(m, 0)} / 3**")
    lines.append("")
    lines.append("### strict_f3 vs external_l1_max by budget")
    for b, (n, mu) in bd_sf.items():
        lines.append(f"- budget {b}: n={n}, mean(strict-external)={mu:.4f}")
    lines.append("")
    lines.append("## B–H. Interpretation (see tables below)")
    lines.append("")
    lines.append("### Rescue types (counts)")
    lines.append("")
    rc = Counter(str(x.get("rescue_type")) for x in rescue_rows)
    for k, v in rc.most_common():
        lines.append(f"- **{k}**: {v}")
    lines.append("")
    lines.append("### Semantic diversity proxies (row-based means)")
    for m in FOCUS_METHODS:
        ag = agg_sem(m)
        lines.append(
            f"- `{m}`: avg semantic_family_count={ag['avg_semantic_family_count']:.3f}, "
            f"avg redundancy={ag['avg_family_redundancy_ratio']:.3f}, "
            f"share_ge2={ag['avg_share_depth_ge_2']:.3f}, "
            f"immediate_miss_rows={int(ag['immediate_miss_rows'])}, "
            f"absent_from_tree_rows={int(ag['absent_from_tree_rows'])}"
        )
    lines.append("")
    lines.append("### Failure taxonomy (aggregate)")
    for k, v in tax_counter.most_common(12):
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("### Incumbent replacement (direct-reserve-related methods)")
    lines.append("")
    lines.append(str(inc_stats))
    lines.append("")
    lines.append("## I. Manuscript")
    lines.append("")
    lines.append("- **Default:** no manuscript change; diagnostic cohort and trace-derived proxies only.")
    lines.append("")
    lines.append(f"- Files written: `{rescue_path.relative_to(REPO_ROOT)}`, `{final_path.relative_to(REPO_ROOT)}`")
    lines.append("")

    write_doc.parent.mkdir(parents=True, exist_ok=True)
    write_doc.write_text("\n".join(lines), encoding="utf-8")

    return {
        "best_method": best_row.get("method"),
        "best_accuracy": best_acc,
        "strict_f3": s_acc,
        "external_l1_max": e_acc,
        "rows_ok": len(rows_ok),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--timestamp", required=True)
    p.add_argument("--run-dir", default="", help="Override outputs/semantic_diversity_controller_diagnostic_<ts>/")
    p.add_argument("--doc-out", default="", help="Default: docs/SEMANTIC_DIVERSITY_LOSS_FULL_RESULT_ANALYSIS_<ts>.md")
    p.add_argument("--job-id", default="", help="Slurm job id for optional wait")
    p.add_argument("--wait-for-manifest", action="store_true")
    p.add_argument("--poll-seconds", type=int, default=60)
    p.add_argument("--max-wait-minutes", type=int, default=0)
    args = p.parse_args()

    ts = str(args.timestamp)
    run_dir = Path(args.run_dir) if args.run_dir else REPO_ROOT / f"outputs/semantic_diversity_controller_diagnostic_{ts}"
    doc_out = Path(args.doc_out) if args.doc_out else REPO_ROOT / f"docs/SEMANTIC_DIVERSITY_LOSS_FULL_RESULT_ANALYSIS_{ts}.md"

    if args.wait_for_manifest and args.max_wait_minutes > 0:
        ok = _wait_manifest(run_dir, args.job_id or None, args.poll_seconds, args.max_wait_minutes)
        if not ok:
            print(f"manifest_or_per_case_missing_after_wait dir={run_dir}", file=sys.stderr)
            return 2

    if not (run_dir / "per_case_results.csv").exists():
        print(f"missing {run_dir / 'per_case_results.csv'}", file=sys.stderr)
        return 1

    analyze(run_dir=run_dir, ts=ts, write_doc=doc_out)
    print(f"wrote {doc_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
