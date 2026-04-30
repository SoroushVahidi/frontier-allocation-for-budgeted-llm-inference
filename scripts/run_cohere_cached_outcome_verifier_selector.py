#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, hashlib, json, os
from dataclasses import dataclass
from datetime import datetime, UTC
from pathlib import Path
from typing import Any, Callable
from collections import defaultdict

DR = "direct_reserve_semantic_frontier_v2"
L1 = "external_l1_max"


def n(x: Any) -> str:
    return str(x or "").strip().lower()


def load_rows(artifact_dir: str) -> list[dict[str, Any]]:
    p = Path(artifact_dir)
    rec = p if p.is_file() else p / "per_example_records.jsonl"
    return [json.loads(l) for l in rec.read_text(encoding="utf-8").splitlines() if l.strip()]


def reconstruct_cases(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    idx = defaultdict(dict)
    for r in rows:
        idx[(r.get("example_id"), r.get("dataset"), r.get("seed"), r.get("budget"))][r.get("method")] = r
    out = []
    for k, mm in idx.items():
        if DR not in mm or L1 not in mm:
            continue
        dr = mm[DR]
        l1 = mm[L1]
        gold = n(dr.get("gold_answer_canonical") or l1.get("gold_answer_canonical"))
        md = dr.get("result_metadata") or {}
        pool = (md.get("selector_candidate_pool") or md.get("final_branch_states") or dr.get("final_nodes") or [])
        pool = [x for x in pool if isinstance(x, dict)]
        groups = {}
        for p in pool:
            ans = n(p.get("normalized_answer") or p.get("predicted_answer") or p.get("final_answer") or p.get("answer"))
            if not ans:
                continue
            g = groups.setdefault(ans, {"normalized_answer": ans, "support_count": 0, "source_families": set()})
            g["support_count"] += 1
            sf = n(p.get("source_family") or p.get("source") or p.get("source_id"))
            if sf:
                g["source_families"].add(sf)
        g_list = []
        for g in groups.values():
            g["source_family_count"] = len(g["source_families"])
            g["source_families"] = sorted(g["source_families"])
            g_list.append(g)
        out.append({
            "key": k,
            "example_id": k[0],
            "dataset": k[1],
            "seed": k[2],
            "budget": k[3],
            "question": str(dr.get("question_raw") or dr.get("question") or ""),
            "gold": gold,
            "dr_pred": n(dr.get("final_answer_canonical") or dr.get("final_answer_raw")),
            "l1_pred": n(l1.get("final_answer_canonical") or l1.get("final_answer_raw")),
            "groups": g_list,
        })
    return out


def build_verifier_prompt(question: str, candidate_answer: str) -> str:
    return (
        "You are a math answer verifier. Determine whether the candidate final answer is likely correct for the question. "
        "Return JSON only with keys: correctness_probability (0..1 number), verdict (likely_correct|uncertain|likely_wrong), "
        "brief_reason (<=20 words).\n"
        f"Question: {question}\n"
        f"Candidate final answer: {candidate_answer}\n"
    )


def cache_key(model: str, question: str, candidate_answer: str) -> str:
    s = json.dumps({"m": model, "q": question, "a": candidate_answer}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def parse_verifier_json(text: str) -> dict[str, Any]:
    try:
        data = json.loads(text)
        return {
            "correctness_probability": float(data.get("correctness_probability", 0.0)),
            "verdict": str(data.get("verdict", "uncertain")),
            "brief_reason": str(data.get("brief_reason", "")),
        }
    except Exception:
        return {"correctness_probability": 0.5, "verdict": "uncertain", "brief_reason": "parse_failure"}


class CohereClient:
    def __init__(self, model: str) -> None:
        self.model = model
        self.api_key = os.getenv("COHERE_API_KEY", "")

    def score(self, prompt: str) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("COHERE_API_KEY missing")
        import requests
        r = requests.post(
            "https://api.cohere.com/v2/chat",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={"model": self.model, "messages": [{"role": "user", "content": prompt}], "temperature": 0},
            timeout=60,
        )
        r.raise_for_status()
        data = r.json()
        txt = data.get("message", {}).get("content", [{}])[0].get("text", "{}")
        out = parse_verifier_json(txt)
        out["raw_text"] = txt
        return out


def run_selector(cases: list[dict[str, Any]], scores: dict[tuple[str, str], float], margin: float) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows = []
    casebook = []
    for c in cases:
        dr = c["dr_pred"]
        best_ans, best_score = dr, scores.get((c["example_id"], dr), 0.0)
        cur_score = best_score
        for g in c["groups"]:
            a = g["normalized_answer"]
            s = scores.get((c["example_id"], a), 0.0)
            if s > best_score:
                best_score, best_ans = s, a
        pred = dr
        reason = "keep_current"
        if best_ans != dr and (best_score - cur_score) >= margin:
            pred = best_ans
            reason = f"override_margin_{best_score-cur_score:.3f}"
            casebook.append({"example_id": c["example_id"], "gold": c["gold"], "dr_pred": dr, "new_pred": pred, "dr_score": cur_score, "new_score": best_score, "reason": reason})
        rows.append({"example_id": c["example_id"], "pred": pred, "reason": reason})
    return rows, casebook


def summary_for(name: str, preds: dict[str, str], cases: list[dict[str, Any]]) -> dict[str, Any]:
    dr_map = {c["example_id"]: c["dr_pred"] for c in cases}
    corr = fixes = breaks = ov = ovc = rem_sel = rem_cov = 0
    for c in cases:
        p = preds[c["example_id"]]
        ok = int(p == c["gold"])
        dr_ok = int(c["dr_pred"] == c["gold"])
        corr += ok
        changed = int(p != c["dr_pred"])
        ov += changed
        ovc += int(changed and ok)
        fixes += int((not dr_ok) and ok)
        breaks += int(dr_ok and (not ok))
        gold_present = any(g["normalized_answer"] == c["gold"] for g in c["groups"])
        rem_sel += int(gold_present and not ok)
        rem_cov += int((not gold_present) and not ok)
    n = max(1, len(cases))
    dr_acc = sum(int(c["dr_pred"] == c["gold"]) for c in cases) / n
    l1_acc = sum(int(c["l1_pred"] == c["gold"]) for c in cases) / n
    acc = corr / n
    return {
        "selector": name, "accuracy": acc, "delta_vs_current_dr_v2": acc - dr_acc, "delta_vs_external_l1_max": acc - l1_acc,
        "fixes": fixes, "breaks": breaks, "net_fixes_minus_breaks": fixes - breaks, "overrides": ov,
        "override_precision": (ovc / ov if ov else 0.0), "remaining_selector_failures": rem_sel, "remaining_coverage_failures": rem_cov,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifact-dir", required=True)
    ap.add_argument("--output-dir", default=None)
    ap.add_argument("--cache-path", default=None)
    ap.add_argument("--model", default="command-r-plus-08-2024")
    ap.add_argument("--margin", type=float, default=0.15)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    rows = load_rows(args.artifact_dir)
    cases = reconstruct_cases(rows)
    if args.limit > 0:
        cases = cases[: args.limit]
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(args.output_dir) if args.output_dir else Path("outputs") / f"cohere_cached_outcome_verifier_selector_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)
    cache_path = Path(args.cache_path) if args.cache_path else out_dir / "verifier_cache.jsonl"

    cached = {}
    if cache_path.exists():
        for l in cache_path.read_text(encoding="utf-8").splitlines():
            if not l.strip():
                continue
            r = json.loads(l)
            cached[r["cache_key"]] = r

    plan = []
    total_groups = 0
    uncached = 0
    for c in cases:
        for g in c["groups"]:
            total_groups += 1
            key = cache_key(args.model, c["question"], g["normalized_answer"])
            prompt = build_verifier_prompt(c["question"], g["normalized_answer"])
            is_cached = key in cached
            if not is_cached:
                uncached += 1
            plan.append({"example_id": c["example_id"], "candidate_answer": g["normalized_answer"], "cache_key": key, "cached": is_cached, "prompt": prompt})

    (out_dir / "verifier_call_plan.jsonl").write_text("\n".join(json.dumps(x) for x in plan) + "\n", encoding="utf-8")
    cost_note = "cost estimate unavailable"
    print(json.dumps({"examples": len(cases), "candidate_groups": total_groups, "uncached_cohere_calls": uncached, "cache_path": str(cache_path), "model": args.model, "output_dir": str(out_dir), "estimated_cost": cost_note}, indent=2))
    if args.dry_run:
        return

    client = CohereClient(args.model)
    cache_append = cache_path.open("a", encoding="utf-8")
    scores = {}
    score_rows = []
    for p in plan:
        ck = p["cache_key"]
        if ck in cached:
            rec = cached[ck]
        else:
            rec = {"cache_key": ck, "model": args.model, "example_id": p["example_id"], "candidate_answer": p["candidate_answer"], **client.score(p["prompt"]) }
            cache_append.write(json.dumps(rec) + "\n")
            cache_append.flush()
            cached[ck] = rec
        scores[(p["example_id"], p["candidate_answer"])] = float(rec.get("correctness_probability", 0.0))
        score_rows.append({"example_id": p["example_id"], "candidate_answer": p["candidate_answer"], "score": rec.get("correctness_probability", 0.0), "verdict": rec.get("verdict", ""), "brief_reason": rec.get("brief_reason", "")})
    cache_append.close()

    pred_rows, ov_cases = run_selector(cases, scores, args.margin)
    preds = {r["example_id"]: r["pred"] for r in pred_rows}

    cur = summary_for("current_dr_v2", {c["example_id"]: c["dr_pred"] for c in cases}, cases)
    support_preds = {}
    oracle_preds = {}
    l1_preds = {}
    for c in cases:
        l1_preds[c["example_id"]] = c["l1_pred"]
        oracle_preds[c["example_id"]] = c["gold"] if any(g["normalized_answer"] == c["gold"] for g in c["groups"]) else c["dr_pred"]
        support_preds[c["example_id"]] = max(c["groups"], key=lambda g: (g["support_count"], g["normalized_answer"]))["normalized_answer"] if c["groups"] else c["dr_pred"]
    summ = [cur, summary_for("support_only", support_preds, cases), summary_for("cohere_outcome_verifier_selector_v1", preds, cases), summary_for("external_l1_max", l1_preds, cases), summary_for("oracle_selector", oracle_preds, cases)]

    with (out_dir / "cohere_verifier_scores.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(score_rows[0].keys()) if score_rows else ["example_id"]); w.writeheader(); w.writerows(score_rows)
    with (out_dir / "selector_summary.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(summ[0].keys())); w.writeheader(); w.writerows(summ)
    with (out_dir / "override_casebook.csv").open("w", newline="", encoding="utf-8") as f:
        fields = list(ov_cases[0].keys()) if ov_cases else ["example_id"]; w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(ov_cases)
    summary = {"artifact_dir": args.artifact_dir, "model": args.model, "margin": args.margin, "uncached_calls": uncached, "selectors": summ,
               "best_deployable": max([x for x in summ if x['selector'] not in {'oracle_selector'}], key=lambda r: (r['accuracy'], r['net_fixes_minus_breaks'], -r['breaks']))}
    (out_dir / "selector_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (out_dir / "cohere_outcome_verifier_selector_report.md").write_text("# Cohere cached outcome verifier selector\n\n- model: %s\n- uncached calls: %d\n" % (args.model, uncached), encoding="utf-8")
    print(out_dir)


if __name__ == "__main__":
    main()
