#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _hash_obj(x: Any) -> str:
    return hashlib.sha256(json.dumps(x, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


def build_verifier_prompt(question: str, candidate_answer: str, incumbent_answer: str) -> str:
    payload = {
        "task": "outcome_verifier",
        "question": question,
        "candidate_answer": candidate_answer,
        "incumbent_answer": incumbent_answer,
        "instructions": "Return strict JSON only with correctness_probability (0..1), verdict, brief_reason.",
    }
    return json.dumps(payload, ensure_ascii=False)


def cache_key(model: str, question: str, candidate_answer: str, evidence: Any | None = None) -> str:
    return json.dumps(
        {
            "model": model,
            "question": question,
            "candidate_answer": candidate_answer,
            "evidence_hash": _hash_obj(evidence) if evidence is not None else "",
        },
        sort_keys=True,
        ensure_ascii=False,
    )


def load_cache(path: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for r in _read_jsonl(path):
        key = str(r.get("cache_key", ""))
        if key:
            out[key] = r
    return out


def append_cache(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _parse_json_maybe(text: str) -> dict[str, Any]:
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t.startswith("json"):
            t = t[4:].strip()
    try:
        return json.loads(t)
    except Exception:
        i = t.find("{")
        j = t.rfind("}")
        if i >= 0 and j > i:
            return json.loads(t[i : j + 1])
        return {"correctness_probability": 0.5, "verdict": "uncertain", "brief_reason": "invalid_json"}


def cohere_score(api_key: str, model: str, prompt: str) -> dict[str, Any]:
    payload = {"model": model, "message": prompt, "temperature": 0.0}
    req = urllib.request.Request(
        "https://api.cohere.ai/v1/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"correctness_probability": 0.5, "verdict": "uncertain", "brief_reason": f"http_{e.code}"}
    parsed = _parse_json_maybe(str(body.get("text", "")))
    return {
        "correctness_probability": float(parsed.get("correctness_probability", 0.5)),
        "verdict": str(parsed.get("verdict", "uncertain")),
        "brief_reason": str(parsed.get("brief_reason", "uncertain"))[:200],
    }


def support_family_selector(record: dict[str, Any]) -> tuple[str, str]:
    dr = str(record.get("current_dr_v2_answer", "NA"))
    groups = list(record.get("candidate_groups", []))
    if not groups:
        return dr, "no_groups_keep_dr"
    by_ans: dict[str, dict[str, Any]] = {}
    for g in groups:
        ans = str(g.get("normalized_answer", "NA"))
        slot = by_ans.setdefault(ans, {"support": 0, "families": set()})
        slot["support"] += _safe_int(g.get("support", 0), 0)
        src = str(g.get("source_method", g.get("method", "NA")))
        slot["families"].add(src)

    dr_support = by_ans.get(dr, {"support": 0})["support"]
    dr_fams = len(by_ans.get(dr, {"families": set()})["families"])
    ranked = sorted(
        by_ans.items(),
        key=lambda kv: (
            int(kv[1]["support"]),
            len(kv[1]["families"]),
            kv[0] == dr,
            kv[0],
        ),
        reverse=True,
    )
    best_ans, best_meta = ranked[0]
    # conservative risk gating: keep DR unless clear margin + no weaker family support
    if best_ans != dr and int(best_meta["support"]) >= dr_support + 1 and len(best_meta["families"]) >= dr_fams:
        return best_ans, f"override_support={best_meta['support']}_families={len(best_meta['families'])}"
    return dr, "risk_gated_keep_dr"


def evaluate_metrics(case_rows: list[dict[str, Any]], selector_name: str) -> dict[str, Any]:
    n = len(case_rows)
    acc = sum(int(r.get(f"{selector_name}_correct", 0)) for r in case_rows) / n if n else 0.0
    dr_acc = sum(int(r.get("current_dr_v2_selector_correct", 0)) for r in case_rows) / n if n else 0.0
    l1_acc = sum(int(r.get("external_l1_max_correct", 0)) for r in case_rows) / n if n else 0.0
    fixes = breaks = overrides = override_hits = gp_fixed = 0
    for r in case_rows:
        dr = int(r.get("current_dr_v2_selector_correct", 0))
        me = int(r.get(f"{selector_name}_correct", 0))
        if dr == 0 and me == 1:
            fixes += 1
        if dr == 1 and me == 0:
            breaks += 1
        if int(r.get(f"{selector_name}_override_applied", 0)) == 1:
            overrides += 1
            if dr == 0 and me == 1:
                override_hits += 1
        if int(r.get("gold_present_and_dr_wrong", 0)) == 1 and me == 1:
            gp_fixed += 1
    remaining_failures = n - sum(int(r.get(f"{selector_name}_correct", 0)) for r in case_rows)
    remaining_coverage_failures = sum(int(r.get("oracle_selector_correct", 0)) == 0 for r in case_rows)
    oracle_gap = sum(int(r.get("oracle_selector_correct", 0)) for r in case_rows) - sum(int(r.get(f"{selector_name}_correct", 0)) for r in case_rows)
    return {
        "selector": selector_name,
        "accuracy": acc,
        "delta_vs_current_dr_v2_selector": acc - dr_acc,
        "delta_vs_external_l1_max": acc - l1_acc,
        "fixes": fixes,
        "breaks": breaks,
        "net_fixes_minus_breaks": fixes - breaks,
        "overrides": overrides,
        "override_precision": (override_hits / overrides) if overrides else "",
        "gold_present_dr_v2_failures_fixed": gp_fixed,
        "selector_failures_remaining": remaining_failures,
        "coverage_failures_remaining": remaining_coverage_failures,
        "oracle_gap_remaining": oracle_gap,
        "beats_external_l1_max": int(acc > l1_acc),
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--artifact-dir", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--skip-cohere", action="store_true")
    p.add_argument("--dry-run-cohere", action="store_true")
    p.add_argument("--cohere-cache", default="")
    p.add_argument("--cohere-model", default="command-r-plus")
    p.add_argument("--margin", type=float, default=0.15)
    p.add_argument("--max-cohere-calls", type=int, default=1000)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    artifact_dir = Path(args.artifact_dir).resolve()
    out_dir = Path(args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    cache_path = Path(args.cohere_cache).resolve() if args.cohere_cache else (out_dir / "cohere_verifier_cache.jsonl")
    records = _read_jsonl(artifact_dir / "per_example_records.jsonl")
    if not records:
        raise SystemExit("Missing/empty per_example_records.jsonl")

    api_key = os.environ.get("COHERE_API_KEY", "")
    cache = load_cache(cache_path)
    verifier_plan: list[dict[str, Any]] = []
    cohere_scores_rows: list[dict[str, Any]] = []
    uncached_calls = 0
    for r in records:
        question = str(r.get("question", ""))
        dr = str(r.get("current_dr_v2_answer", "NA"))
        for g in r.get("candidate_groups", []):
            cand = str(g.get("normalized_answer", "NA"))
            evidence = {"candidate_group": g, "source": r.get("source_artifact_path", "")}
            key = cache_key(args.cohere_model, question, cand, evidence)
            hit = key in cache
            if not hit:
                uncached_calls += 1
            verifier_plan.append(
                {
                    "example_id": r.get("example_id", ""),
                    "cache_key": key,
                    "model": args.cohere_model,
                    "candidate_answer": cand,
                    "incumbent_answer": dr,
                    "cache_hit": int(hit),
                    "would_call": int((not hit) and (cand != dr)),
                }
            )

    with (out_dir / "verifier_call_plan.jsonl").open("w", encoding="utf-8") as f:
        for r in verifier_plan:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    dry_meta = {
        "examples": len(records),
        "uncached_calls": uncached_calls,
        "cache_path": str(cache_path),
        "cohere_model": args.cohere_model,
        "output_dir": str(out_dir),
    }
    print(json.dumps(dry_meta, indent=2))

    case_rows: list[dict[str, Any]] = []
    overrides_casebook: list[dict[str, Any]] = []
    for rec in records:
        gold = str(rec.get("gold_answer", "NA"))
        dr = str(rec.get("current_dr_v2_answer", "NA"))
        l1 = str(rec.get("external_l1_max_answer", "NA"))
        oracle = str(rec.get("oracle_selector_answer", dr))
        gpdr = int(int(rec.get("oracle_selector_correct", 0)) == 1 and int(rec.get("current_dr_v2_correct", 0)) == 0)

        support_ans, support_reason = support_family_selector(rec)
        cohere_ans = dr
        cohere_reason = "cohere_skipped"
        cohere_override = 0
        best_score = -1.0
        dr_score = 0.5
        if not args.skip_cohere:
            for g in rec.get("candidate_groups", []):
                cand = str(g.get("normalized_answer", "NA"))
                evidence = {"candidate_group": g, "source": rec.get("source_artifact_path", "")}
                key = cache_key(args.cohere_model, str(rec.get("question", "")), cand, evidence)
                if key in cache:
                    row = cache[key]
                elif args.dry_run_cohere:
                    row = {
                        "cache_key": key,
                        "model": args.cohere_model,
                        "correctness_probability": "",
                        "verdict": "dry_run",
                        "brief_reason": "dry_run_uncached",
                    }
                else:
                    if not api_key:
                        row = {
                            "cache_key": key,
                            "model": args.cohere_model,
                            "correctness_probability": 0.5,
                            "verdict": "uncertain",
                            "brief_reason": "missing_api_key",
                        }
                    else:
                        prompt = build_verifier_prompt(str(rec.get("question", "")), cand, dr)
                        row = {"cache_key": key, "model": args.cohere_model, **cohere_score(api_key, args.cohere_model, prompt)}
                        append_cache(cache_path, row)
                        cache[key] = row
                score = float(row.get("correctness_probability", 0.5) or 0.5)
                if cand == dr:
                    dr_score = score
                if score > best_score:
                    best_score = score
                    cohere_ans = cand
                    cohere_reason = str(row.get("brief_reason", ""))
                cohere_scores_rows.append(
                    {
                        "example_id": rec.get("example_id", ""),
                        "candidate_answer": cand,
                        "correctness_probability": row.get("correctness_probability", ""),
                        "verdict": row.get("verdict", ""),
                        "brief_reason": row.get("brief_reason", ""),
                        "cache_key": key,
                    }
                )
            if (best_score - dr_score) > args.margin and cohere_ans != dr:
                cohere_override = 1
            else:
                cohere_ans = dr
                cohere_reason = f"margin_keep_dr_gap={best_score-dr_score:.4f}"

        row = {
            "dataset": rec.get("dataset", "NA"),
            "example_id": rec.get("example_id", ""),
            "seed": rec.get("seed", 0),
            "budget": rec.get("budget", 0),
            "gold_answer": gold,
            "current_dr_v2_selector_answer": dr,
            "external_l1_max_answer": l1,
            "support_family_selector_answer": support_ans,
            "cohere_outcome_verifier_selector_answer": cohere_ans,
            "oracle_selector_answer": oracle,
            "current_dr_v2_selector_correct": int(dr == gold and gold != "NA"),
            "external_l1_max_correct": int(l1 == gold and gold != "NA"),
            "support_family_selector_correct": int(support_ans == gold and gold != "NA"),
            "cohere_outcome_verifier_selector_correct": int(cohere_ans == gold and gold != "NA"),
            "oracle_selector_correct": int(oracle == gold and gold != "NA"),
            "gold_present_and_dr_wrong": gpdr,
            "current_dr_v2_selector_override_applied": 0,
            "support_family_selector_override_applied": int(support_ans != dr),
            "cohere_outcome_verifier_selector_override_applied": cohere_override,
            "oracle_selector_override_applied": int(oracle != dr),
            "support_override_reason": support_reason,
            "cohere_override_reason": cohere_reason,
        }
        if cohere_override:
            overrides_casebook.append(
                {
                    "example_id": rec.get("example_id", ""),
                    "dataset": rec.get("dataset", "NA"),
                    "dr_answer": dr,
                    "cohere_answer": cohere_ans,
                    "gold_answer": gold,
                    "cohere_reason": cohere_reason,
                }
            )
        case_rows.append(row)

    selectors = [
        "current_dr_v2_selector",
        "support_family_selector",
        "cohere_outcome_verifier_selector",
        "oracle_selector",
    ]
    summary = [evaluate_metrics(case_rows, s) for s in selectors]

    if summary and any(s["selector"] == "cohere_outcome_verifier_selector" for s in summary):
        c = next(s for s in summary if s["selector"] == "cohere_outcome_verifier_selector")
        c["cohere_uncached_calls"] = uncached_calls
        c["cohere_calls_within_limit"] = int(uncached_calls <= int(args.max_cohere_calls))

    summary_fields: list[str] = []
    for r in summary:
        for k in r.keys():
            if k not in summary_fields:
                summary_fields.append(k)
    with (out_dir / "selector_summary.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=summary_fields)
        w.writeheader()
        w.writerows(summary)
    (out_dir / "selector_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    with (out_dir / "override_casebook.csv").open("w", encoding="utf-8", newline="") as f:
        if overrides_casebook:
            w = csv.DictWriter(f, fieldnames=list(overrides_casebook[0].keys()))
            w.writeheader()
            w.writerows(overrides_casebook)
        else:
            f.write("example_id,cohere_reason\n")
    failure = [
        {
            "metric": "coverage_failures",
            "count": sum(int(r.get("oracle_selector_correct", 0)) == 0 for r in case_rows),
        },
        {
            "metric": "selector_failures_cohere",
            "count": sum(int(r.get("cohere_outcome_verifier_selector_correct", 0)) == 0 for r in case_rows),
        },
    ]
    with (out_dir / "failure_decomposition.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(failure[0].keys()))
        w.writeheader()
        w.writerows(failure)
    with (out_dir / "cohere_verifier_scores.csv").open("w", encoding="utf-8", newline="") as f:
        if cohere_scores_rows:
            w = csv.DictWriter(f, fieldnames=list(cohere_scores_rows[0].keys()))
            w.writeheader()
            w.writerows(cohere_scores_rows)
        else:
            f.write("example_id,candidate_answer,correctness_probability\n")

    report_lines = [
        "# Large Selector Tournament Report",
        "",
        f"- examples: {len(case_rows)}",
        f"- cohere_model: `{args.cohere_model}`",
        f"- cohere_cache: `{cache_path}`",
        f"- dry_run_cohere: {int(args.dry_run_cohere)}",
        f"- skip_cohere: {int(args.skip_cohere)}",
        f"- uncached_cohere_calls: {uncached_calls}",
        "",
        "## Selector Summary",
    ]
    for r in summary:
        report_lines.append(
            f"- {r['selector']}: acc={r['accuracy']:.4f}, delta_vs_l1={r['delta_vs_external_l1_max']:.4f}, net_fixes={r['net_fixes_minus_breaks']}"
        )
    (out_dir / "large_selector_tournament_report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print(f"Wrote {out_dir / 'selector_summary.csv'}")


if __name__ == "__main__":
    main()
