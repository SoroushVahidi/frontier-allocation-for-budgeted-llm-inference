#!/usr/bin/env python3
"""Build candidate-level rows from Cohere direct-reserve validation output package(s)."""
from __future__ import annotations

import argparse
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from itertools import count
from pathlib import Path
import re
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.output_layer_repair import canonicalize_answer
from scripts.learned_branch_scorer_utils import as_float, as_int, read_csv, write_csv, write_json

TRACE_BRANCH = "trace_level_branch"
SRC_GROUP = "answer_group"
MARGIN = "direct_reserve_strong_plus_diverse_margin_gated_v1"
TARGET = "direct_reserve_strong_plus_diverse_v1"


def _norm(v: Any, dataset: str) -> str:
    t = str(v or "").strip()
    if not t:
        return "NA"
    try:
        return str(canonicalize_answer(t, dataset=dataset))
    except Exception:
        t2 = t.lower()
        return t2 if t2 else "NA"


def _try_float(s: str) -> float | None:
    t = re.sub(r"[^0-9.+\-eE]", "", s.replace(",", ""))
    if t in {"", ".", "-", "+", "e", "E"}:
        return None
    try:
        return float(t)
    except Exception:
        return None


def _entropy(support: Counter[str]) -> float:
    vals = [int(c) for c in support.values() if int(c) > 0]
    t = float(sum(vals))
    if t <= 0 or len(vals) < 2:
        return 0.0
    e = 0.0
    for c in vals:
        p = c / t
        e -= p * math.log2(p + 1e-12)
    return e


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    p.add_argument("--input-dirs", required=True, help="Comma paths under repo root")
    p.add_argument("--include-methods", default="")
    p.add_argument("--exclude-methods", default="")
    p.add_argument(
        "--include-margin-gated",
        action="store_true",
        help="Also emit margin_gated rows (for comparison; default: omit).",
    )
    p.add_argument(
        "--train-on-margin-gated",
        action="store_true",
        help="If margin rows are emitted, set excluded_from_training=0 for them.",
    )
    return p.parse_args()


def _want_method(
    m: str,
    include: set[str],
    exclude: set[str],
    emit_margin: bool,
) -> bool:
    if m == MARGIN:
        return emit_margin
    if m in exclude:
        return False
    if include and m not in include:
        return False
    return True


def main() -> None:
    args = parse_args()
    include = {x.strip() for x in str(args.include_methods).split(",") if x.strip()}
    exclude = {x.strip() for x in str(args.exclude_methods).split(",") if x.strip()}
    inp_dirs = [d.strip() for d in str(args.input_dirs).split(",") if d.strip()]
    if not inp_dirs:
        raise SystemExit("No --input-dirs")

    rows: list[dict[str, Any]] = []
    id_gen = count(1)
    by_problem: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for rel in inp_dirs:
        base = (REPO_ROOT / rel).resolve()
        if not base.is_dir():
            raise SystemExit(f"Not found: {base}")
        cb = read_csv(base / "candidate_branch_table.csv")
        per = read_csv(base / "per_case_method_results.csv")
        ag = read_csv(base / "answer_group_summary.csv")
        planned = read_csv(base / "planned_cases.csv")
        if not per:
            raise SystemExit(f"No per_case rows in {base}")

        stratum: dict[tuple[str, int, int], str] = {}
        gold_by: dict[tuple[str, int, int], str] = {}
        for r in planned:
            k = (str(r.get("example_id", "")), as_int(r.get("seed", -1), -1), as_int(r.get("budget", -1), -1))
            stratum[k] = str(r.get("stratum", "unknown") or "unknown")
            gold_by[k] = str(r.get("gold_answer", "") or "")

        per_idx: dict[tuple[str, int, int, str], dict[str, str]] = {}
        for r in per:
            m = str(r.get("method", ""))
            k4 = (str(r.get("example_id", "")), as_int(r.get("seed", -1), -1), as_int(r.get("budget", -1), -1), m)
            per_idx[k4] = r

        final_ans: dict[tuple[str, int, int], dict[str, str]] = defaultdict(dict)
        for r in per:
            m = str(r.get("method", ""))
            ds0 = str(r.get("dataset", "openai/gsm8k"))
            ck = (str(r.get("example_id", "")), as_int(r.get("seed", -1), -1), as_int(r.get("budget", -1), -1))
            final_ans[ck][m] = _norm(r.get("normalized_selected_answer", r.get("final_selected_answer", "")), ds0)

        sup: dict[tuple[str, int, int, str], Counter[str]] = defaultdict(Counter)
        for r in ag:
            m = str(r.get("method", ""))
            ck2 = (str(r.get("example_id", "")), as_int(r.get("seed", -1), -1), as_int(r.get("budget", -1), -1))
            g = str(r.get("answer_group", "NA"))
            sup[(*ck2, m)][g] += max(1, as_int(r.get("support", 0), 0) or 1)
        rank_by: dict[tuple[str, int, int, str], dict[str, int]] = {}
        for k, c in sup.items():
            eid, sd, bud, m = k
            ordered = sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))
            rank_by[(eid, sd, bud, m)] = {g: i + 1 for i, (g, _) in enumerate(ordered)}

        branch_key_set: set[tuple[str, int, int, str, str]] = set()
        for b in cb:
            m = str(b.get("method", ""))
            eid = str(b.get("example_id", ""))
            seed = as_int(b.get("seed", -1), -1)
            bud = as_int(b.get("budget", -1), -1)
            gk = str(b.get("answer_group", ""))
            branch_key_set.add((eid, seed, bud, m, gk))

        for b in cb:
            m = str(b.get("method", ""))
            if not _want_method(m, include, exclude, args.include_margin_gated):
                continue
            eid = str(b.get("example_id", ""))
            seed = as_int(b.get("seed", -1), -1)
            bud = as_int(b.get("budget", -1), -1)
            ds = str(b.get("dataset", "openai/gsm8k"))
            ck3 = (eid, seed, bud)
            gold = gold_by.get(ck3, "")
            gnorm = _norm(gold, ds)
            pnorm = _norm(b.get("normalized_candidate_answer", b.get("predicted_answer", "")), ds)
            gkey = str(b.get("answer_group", pnorm) or pnorm)
            pr = per_idx.get((eid, seed, bud, m), {})
            mkey = (*ck3, m)
            sctr = sup.get(mkey, Counter())
            top2 = as_float(pr.get("top2_support_gap", 0.0), 0.0)
            entp = as_float(pr.get("answer_entropy", 0.0), 0.0)
            if sctr and entp == 0.0:
                entp = _entropy(sctr)
            is_sel = as_int(b.get("is_selected", 0), 0)
            is_g = int(pnorm == gnorm and gnorm not in ("NA", "na"))
            n_same = sum(1 for a in final_ans[ck3].values() if a and a not in ("NA", "na") and a == pnorm)
            ng, npred = _try_float(gnorm), _try_float(pnorm)
            abs_e = rel_e = None
            if ng is not None and npred is not None and abs(ng) > 1e-9:
                abs_e = abs(npred - ng)
                rel_e = abs_e / (abs(ng) + 1e-9)
            excl = 0
            if m == MARGIN:
                excl = 0 if args.train_on_margin_gated else 1
            sm = str(pr.get("support_margin", "NA"))
            row: dict[str, Any] = {
                "row_id": f"cb_{next(id_gen)}",
                "source_package": rel,
                "source_type": TRACE_BRANCH,
                "excluded_from_training": excl,
                "example_id": eid,
                "dataset": ds,
                "gold_norm": gnorm,
                "question": str(b.get("question", ""))[:20000],
                "stratum": str(b.get("stratum", stratum.get(ck3, "unknown"))),
                "seed": seed,
                "budget": bud,
                "method": m,
                "branch_id": str(b.get("branch_id", "")),
                "parent_branch_id": str(b.get("parent_branch_id", "")),
                "branch_depth": as_int(b.get("branch_depth", 0), 0),
                "prompt_style": str(b.get("branch_prompt_style", "NA")),
                "reasoning_text": str(b.get("reasoning_text", "NA"))[:12000],
                "raw_branch_text": str(b.get("raw_branch_text", "NA"))[:8000],
                "extracted_answer": str(b.get("predicted_answer", "NA")),
                "normalized_answer": pnorm,
                "answer_group_id": gkey,
                "answer_group_support": int(sctr.get(gkey, 0) or 0) if sctr else 0,
                "answer_group_rank": int(rank_by.get(mkey, {}).get(gkey, 99) or 99),
                "selected_by_method": is_sel,
                "top_answer_group": str(pr.get("top_answer_group", "NA")),
                "selected_answer_group": str(pr.get("selected_answer_group", "NA")),
                "top2_support_gap": top2,
                "answer_entropy": entp,
                "support_margin": sm,
                "prompt_style_agreement": str(pr.get("prompt_style_agreement", "NA")),
                "action_count": as_int(pr.get("action_count", 0), 0),
                "expansion_count": as_int(pr.get("expansion_count", 0), 0),
                "verification_count": as_int(pr.get("verification_count", 0), 0),
                "token_estimate": str(pr.get("token_estimate", "NA")),
                "cost_estimate": str(pr.get("cost_estimate", "NA")),
                "latency_seconds": str(pr.get("latency_seconds", "NA")),
                "operation_sequence": str(b.get("operation_sequence", "NA"))[:2000],
                "intermediate_values": str(b.get("intermediate_values", "NA"))[:2000],
                "reasoning_role": str(b.get("reasoning_role", "NA"))[:2000],
                "useful_reasoning_diversity_score": str(b.get("useful_reasoning_diversity_bonus", "NA")),
                "is_gold_candidate": is_g,
                "is_selected_gold": int(is_sel and is_g),
                "match_strict_f3_final": int(pnorm == final_ans[ck3].get("strict_f3", "NA")),
                "match_external_l1_max_final": int(pnorm == final_ans[ck3].get("external_l1_max", "NA")),
                "match_direct_reserve_strong_v1_final": int(
                    pnorm == final_ans[ck3].get("direct_reserve_strong_v1", "NA")
                ),
                "match_direct_reserve_strong_plus_diverse_v1_final": int(
                    pnorm == final_ans[ck3].get("direct_reserve_strong_plus_diverse_v1", "NA")
                ),
                "n_methods_sharing_norm_answer": n_same,
                "numeric_gold": "" if ng is None else f"{ng}",
                "numeric_pred": "" if npred is None else f"{npred}",
                "abs_numeric_error": "" if abs_e is None else f"{abs_e}",
                "rel_numeric_error": "" if rel_e is None else f"{rel_e}",
                "extraction_ok": 1 if pnorm not in ("", "NA", "na") else 0,
                "data_quality_flags": "bad_norm" if pnorm in ("", "na") else "",
            }
            by_problem[f"{eid}::{seed}::{bud}"].append(row)
            rows.append(row)

        for r in ag:
            m = str(r.get("method", ""))
            if not _want_method(m, include, exclude, args.include_margin_gated):
                continue
            eid = str(r.get("example_id", ""))
            seed = as_int(r.get("seed", -1), -1)
            bud = as_int(r.get("budget", -1), -1)
            gk = str(r.get("answer_group", "NA"))
            if (eid, seed, bud, m, gk) in branch_key_set:
                continue
            pr = per_idx.get((eid, seed, bud, m), {})
            ds = str(pr.get("dataset", "openai/gsm8k")) or "openai/gsm8k"
            ck3 = (eid, seed, bud)
            gold = gold_by.get(ck3, "")
            gnorm = _norm(gold, ds)
            pnorm = _norm(gk, ds)
            mkey = (*ck3, m)
            sctr = sup.get(mkey, Counter())
            is_g = int(pnorm == gnorm and gnorm not in ("NA", "na"))
            is_sel = as_int(r.get("is_selected_group", 0), 0)
            excl = 0
            if m == MARGIN:
                excl = 0 if args.train_on_margin_gated else 1
            n_same = sum(1 for a in final_ans[ck3].values() if a and a not in ("NA", "na") and a == pnorm)
            row2: dict[str, Any] = {
                "row_id": f"ag_{next(id_gen)}",
                "source_package": rel,
                "source_type": SRC_GROUP,
                "excluded_from_training": excl,
                "example_id": eid,
                "dataset": ds,
                "gold_norm": gnorm,
                "question": str(pr.get("question", ""))[:20000],
                "stratum": str(pr.get("stratum", stratum.get(ck3, "unknown"))),
                "seed": seed,
                "budget": bud,
                "method": m,
                "branch_id": f"answer_group::{gk}",
                "parent_branch_id": "",
                "branch_depth": 0,
                "prompt_style": "NA",
                "reasoning_text": "NA",
                "raw_branch_text": "NA",
                "extracted_answer": gk,
                "normalized_answer": pnorm,
                "answer_group_id": gk,
                "answer_group_support": as_int(r.get("support", 0), 0) or int(sctr.get(gk, 0) or 0),
                "answer_group_rank": int(rank_by.get(mkey, {}).get(gk, 99) or 99),
                "selected_by_method": is_sel,
                "top_answer_group": str(pr.get("top_answer_group", "NA")),
                "selected_answer_group": str(pr.get("selected_answer_group", "NA")),
                "top2_support_gap": as_float(pr.get("top2_support_gap", 0.0), 0.0),
                "answer_entropy": as_float(pr.get("answer_entropy", 0.0), 0.0),
                "support_margin": str(pr.get("support_margin", "NA")),
                "prompt_style_agreement": str(pr.get("prompt_style_agreement", "NA")),
                "action_count": as_int(pr.get("action_count", 0), 0),
                "expansion_count": as_int(pr.get("expansion_count", 0), 0),
                "verification_count": as_int(pr.get("verification_count", 0), 0),
                "token_estimate": str(pr.get("token_estimate", "NA")),
                "operation_sequence": "NA",
                "is_gold_candidate": is_g,
                "is_selected_gold": int(is_sel and is_g),
                "match_direct_reserve_strong_plus_diverse_v1_final": int(
                    pnorm == final_ans[ck3].get("direct_reserve_strong_plus_diverse_v1", "NA")
                ),
                "n_methods_sharing_norm_answer": n_same,
            }
            by_problem[f"{eid}::{seed}::{bud}"].append(row2)
            rows.append(row2)

    for e in rows:
        eid = str(e.get("example_id", ""))
        sd = as_int(e.get("seed", 0), 0)
        bud = as_int(e.get("budget", 0), 0)
        keyp = f"{eid}::{sd}::{bud}"
        any_g = max((as_int(z.get("is_gold_candidate", 0), 0) for z in by_problem.get(keyp, [])), default=0)
        pns0, gpf0 = 0, 0
        for d in inp_dirs:
            pff = (REPO_ROOT / d) / "per_case_method_results.csv"
            for r in read_csv(pff) if pff.exists() else []:
                if str(r.get("method", "")) != TARGET:
                    continue
                if str(r.get("example_id", "")) == eid and as_int(r.get("seed", -1), -1) == sd and as_int(
                    r.get("budget", -1), -1
                ) == bud:
                    pns0 = as_int(r.get("present_not_selected", 0), 0)
                    gpf0 = as_int(r.get("gold_present", 0), 0)
        e["problem_gold_present"] = max(gpf0, any_g)
        e["problem_present_not_selected"] = pns0
        e["diverse_gold_in_pool"] = gpf0

    out = REPO_ROOT / "outputs" / f"direct_reserve_candidate_scorer_dataset_{args.timestamp}"
    out.mkdir(parents=True, exist_ok=True)
    if not rows:
        write_csv(out / "examples.csv", [])
        print(f"Wrote {out} (empty examples)")
        return
    n_train = sum(
        1
        for e in rows
        if as_int(e.get("is_gold_candidate", 0), 0) == 1 and as_int(e.get("excluded_from_training", 0), 0) == 0
    )
    write_csv(out / "examples.csv", rows)
    fea = [k for k in sorted({k for e in rows for k in e.keys()}) if k not in ("reasoning_text", "raw_branch_text", "question")]
    write_json(
        out / "feature_schema.json",
        {
            "label_columns": ["is_gold_candidate", "is_selected_gold", "problem_gold_present", "problem_present_not_selected"],
            "feature_columns": fea,
        },
    )
    uniq = len(
        {f"{e.get('example_id')}|{e.get('seed')}|{e.get('budget')}|{e.get('source_package', '')}" for e in rows}
    )
    write_csv(
        out / "dataset_summary.csv",
        [
            {
                "n_rows": len(rows),
                "n_positive_gold_excluding_train_margin": n_train,
                "n_unique_cases": uniq,
            }
        ],
    )
    cov: list[dict[str, str]] = []
    for d in inp_dirs:
        p = (REPO_ROOT / d) / "planned_cases.csv"
        pcr = read_csv(p) if p.exists() else []
        cov.append(
            {
                "source_package": d,
                "n_planned": str(len(pcr)),
                "n_unique_example": str(len({str(r.get("example_id", "")) for r in pcr})),
            }
        )
    write_csv(out / "case_coverage.csv", cov)
    (out / "README.md").write_text(
        f"Built from {args.input_dirs!r}.\nRows: {len(rows)}.\n",
        encoding="utf-8",
    )
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
