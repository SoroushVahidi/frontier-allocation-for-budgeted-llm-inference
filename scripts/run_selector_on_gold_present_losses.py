#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _norm(v: Any) -> str:
    return str(v or "").strip()


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = sorted({k for r in rows for k in r.keys()})
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _parse_obj(s: str) -> dict[str, Any]:
    txt = _norm(s)
    if not txt:
        return {}
    try:
        obj = json.loads(txt)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def normalize_model(model: str) -> str:
    return "command-r-plus-08-2024" if _norm(model) == "command-r-plus" else _norm(model)


def filter_selector_recoverable(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for r in rows:
        if _safe_int(r.get("trace_available")) != 1:
            continue
        if _safe_int(r.get("gold_present_in_candidate_groups")) != 1:
            continue
        if _safe_int(r.get("oracle_selector_would_fix")) != 1:
            continue
        out.append(r)
    return out


def _candidate_groups_from_row(r: dict[str, Any]) -> list[dict[str, Any]]:
    supports = _parse_obj(_norm(r.get("support_count_by_answer_group")))
    fams = _parse_obj(_norm(r.get("source_family_by_answer_group")))
    depths = _parse_obj(_norm(r.get("depth_by_answer_group")))
    first_idx = _parse_obj(_norm(r.get("first_action_index_by_answer_group")))
    out: list[dict[str, Any]] = []
    for ans in sorted(set(list(supports.keys()) + list(fams.keys()) + list(depths.keys()) + list(first_idx.keys()))):
        fam_raw = fams.get(ans, "")
        fam_list = [x.strip() for x in str(fam_raw).split("|") if x.strip()] if isinstance(fam_raw, str) else []
        fam_count = len(set(fam_list)) if fam_list else (_safe_int(fam_raw, 0) if isinstance(fam_raw, (int, float, str)) else 0)
        out.append(
            {
                "answer": _norm(ans),
                "support": _safe_int(supports.get(ans, 0)),
                "source_family_count": fam_count,
                "source_family": "|".join(sorted(set(fam_list))) if fam_list else _norm(fam_raw),
                "branch_depth": _safe_int(depths.get(ans, 0)),
                "first_action_index": _safe_int(first_idx.get(ans, 0)),
            }
        )
    return out


def support_family_selector(cands: list[dict[str, Any]], current: str) -> tuple[str, str]:
    if not cands:
        return current, "no_candidates"
    ranked = sorted(
        cands,
        key=lambda c: (
            _safe_int(c.get("support")),
            _safe_int(c.get("source_family_count")),
            _safe_int(c.get("branch_depth")),
            c.get("answer") == current,
            _norm(c.get("answer")),
        ),
        reverse=True,
    )
    best = ranked[0]
    return _norm(best.get("answer")), "support_family_rank"


def conservative_support_selector(cands: list[dict[str, Any]], current: str) -> tuple[str, str]:
    by = {_norm(c["answer"]): c for c in cands}
    cur = by.get(current, {"support": 0, "source_family_count": 0})
    top, _ = support_family_selector(cands, current)
    best = by.get(top, {"support": 0, "source_family_count": 0})
    if top != current and (
        _safe_int(best.get("support")) - _safe_int(cur.get("support")) >= 2
        or _safe_int(best.get("source_family_count")) - _safe_int(cur.get("source_family_count")) >= 1
    ):
        return top, "conservative_override"
    return current, "conservative_keep"


def risk_gated_support_selector(cands: list[dict[str, Any]], current: str) -> tuple[str, str]:
    by = {_norm(c["answer"]): c for c in cands}
    cur = by.get(current, {"support": 0, "source_family_count": 0})
    top, _ = support_family_selector(cands, current)
    best = by.get(top, {"support": 0, "source_family_count": 0})
    cur_weak = _safe_int(cur.get("support")) <= 1 and _safe_int(cur.get("source_family_count")) <= 1
    challenger_strong = _safe_int(best.get("support")) >= _safe_int(cur.get("support")) + 1 and _safe_int(best.get("source_family_count")) >= _safe_int(cur.get("source_family_count"))
    if top != current and cur_weak and challenger_strong:
        return top, "risk_gate_override"
    return current, "risk_gate_keep"


def _cohere_chat(api_key: str, model: str, prompt: str) -> str:
    payload = {"model": model, "message": prompt, "temperature": 0.0}
    req = urllib.request.Request(
        "https://api.cohere.ai/v1/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return _norm(body.get("text", ""))


def _parse_json(text: str) -> dict[str, Any]:
    try:
        out = json.loads(text)
        return out if isinstance(out, dict) else {}
    except Exception:
        return {}


def _hash_key(parts: list[str]) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8", errors="ignore"))
        h.update(b"\n")
    return h.hexdigest()


def _load_cache(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    out: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            out[_norm(row.get("cache_key"))] = row
        except Exception:
            continue
    return out


def outcome_verifier_selector(
    api_key: str,
    model: str,
    question: str,
    current: str,
    cands: list[dict[str, Any]],
    cache: dict[str, dict[str, Any]],
    cache_path: Path,
    dry_run: bool,
    margin: float = 0.15,
) -> tuple[str, str, int]:
    if not cands:
        return current, "no_candidates", 0
    best = current
    best_p = -1.0
    cur_p = 0.5
    calls = 0
    for c in cands:
        cand = _norm(c.get("answer"))
        prompt = (
            "Return JSON only with keys correctness_probability, verdict, brief_reason.\n"
            "Question:\n"
            f"{question}\n\n"
            f"Candidate answer:\n{cand}\n"
        )
        key = _hash_key(["outcome", model, question, cand])
        row = cache.get(key)
        if row is None:
            if dry_run or not api_key:
                row = {"cache_key": key, "correctness_probability": 0.5, "verdict": "dry_run", "brief_reason": "dry_run_or_missing_key"}
            else:
                calls += 1
                try:
                    raw = _cohere_chat(api_key, model, prompt)
                    parsed = _parse_json(raw)
                    row = {
                        "cache_key": key,
                        "correctness_probability": _safe_float(parsed.get("correctness_probability"), 0.5),
                        "verdict": _norm(parsed.get("verdict")),
                        "brief_reason": _norm(parsed.get("brief_reason"))[:200],
                    }
                except urllib.error.HTTPError as e:
                    row = {"cache_key": key, "correctness_probability": 0.5, "verdict": "http_error", "brief_reason": f"http_{e.code}"}
            cache[key] = row
            _append_jsonl(cache_path, row)
        p = _safe_float(row.get("correctness_probability"), 0.5)
        if cand == current:
            cur_p = p
        if p > best_p:
            best_p = p
            best = cand
    if best != current and (best_p - cur_p) > margin:
        return best, f"override_p_margin={best_p-cur_p:.3f}", calls
    return current, "keep_current", calls


def pairwise_verifier_selector(
    api_key: str,
    model: str,
    question: str,
    current: str,
    cands: list[dict[str, Any]],
    cache: dict[str, dict[str, Any]],
    cache_path: Path,
    dry_run: bool,
    min_margin: float = 0.20,
) -> tuple[str, str, int]:
    if len(cands) < 2:
        return current, "no_pairwise_needed", 0
    wins = defaultdict(float)
    calls = 0
    answers = [_norm(c.get("answer")) for c in cands]
    # Conservative/cost-bounded tournament: compare each challenger only against current.
    challengers = [a for a in answers if a != current]
    for challenger in challengers:
            a, b = current, challenger
            key = _hash_key(["pairwise", model, question, a, b])
            row = cache.get(key)
            if row is None:
                prompt = (
                    "Return JSON only with keys winner, confidence, brief_reason.\n"
                    "winner must be exactly one of: A, B, tie.\n"
                    "Question:\n"
                    f"{question}\n\n"
                    f"A: {a}\n"
                    f"B: {b}\n"
                    "Which answer is more likely correct?"
                )
                if dry_run or not api_key:
                    row = {"cache_key": key, "winner": "tie", "confidence": 0.5, "brief_reason": "dry_run_or_missing_key"}
                else:
                    calls += 1
                    try:
                        raw = _cohere_chat(api_key, model, prompt)
                        parsed = _parse_json(raw)
                        row = {
                            "cache_key": key,
                            "winner": _norm(parsed.get("winner", "tie")),
                            "confidence": _safe_float(parsed.get("confidence", 0.5)),
                            "brief_reason": _norm(parsed.get("brief_reason"))[:200],
                        }
                    except urllib.error.HTTPError as e:
                        row = {"cache_key": key, "winner": "tie", "confidence": 0.5, "brief_reason": f"http_{e.code}"}
                cache[key] = row
                _append_jsonl(cache_path, row)
            w = _norm(row.get("winner", "tie")).lower()
            conf = max(0.0, min(1.0, _safe_float(row.get("confidence"), 0.5)))
            if w == "a":
                wins[a] += conf
            elif w == "b":
                wins[b] += conf
            else:
                wins[a] += 0.5 * conf
                wins[b] += 0.5 * conf
    ranked = sorted(answers, key=lambda x: (wins[x], x == current, x), reverse=True)
    best = ranked[0]
    margin = wins[best] - wins[current]
    if best != current and margin >= min_margin:
        return best, f"pairwise_override_margin={margin:.3f}", calls
    return current, "pairwise_keep", calls


def _selector_metrics(rows: list[dict[str, Any]], selector: str) -> dict[str, Any]:
    n = len(rows)
    correct = sum(_safe_int(r.get(f"{selector}_correct")) for r in rows)
    overrides = sum(_safe_int(r.get(f"{selector}_override")) for r in rows)
    fixes = sum(1 for r in rows if _safe_int(r.get("current_correct")) == 0 and _safe_int(r.get(f"{selector}_correct")) == 1)
    remaining = n - correct
    override_hits = sum(1 for r in rows if _safe_int(r.get(f"{selector}_override")) == 1 and _safe_int(r.get(f"{selector}_correct")) == 1)
    avg_sup = (sum(_safe_float(r.get(f"{selector}_selected_support")) for r in rows) / n) if n else 0.0
    avg_fam = (sum(_safe_float(r.get(f"{selector}_selected_family_count")) for r in rows) / n) if n else 0.0
    calls = sum(_safe_int(r.get(f"{selector}_cohere_calls")) for r in rows)
    return {
        "selector": selector,
        "cases": n,
        "accuracy": round(correct / n, 4) if n else 0.0,
        "fixed": fixes,
        "remaining_selector_failures": remaining,
        "selected_gold_count": correct,
        "overrides_from_current": overrides,
        "override_precision": round((override_hits / overrides), 4) if overrides else 0.0,
        "avg_selected_support": round(avg_sup, 4),
        "avg_selected_family_count": round(avg_fam, 4),
        "cohere_calls_used": calls,
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--loss-casebook-dir", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--provider", default="cohere")
    p.add_argument("--cohere-model", default="command-r-plus")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--max-cohere-calls", type=int, default=500)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = Path(args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    casebook_dir = Path(args.loss_casebook_dir).resolve()
    model = normalize_model(args.cohere_model)
    api_key = os.environ.get("COHERE_API_KEY", "") if args.provider == "cohere" else ""

    trace_csv = casebook_dir / "loss_casebook_trace_complete.csv"
    if not trace_csv.exists():
        raise SystemExit(f"Missing required file: {trace_csv}")
    trace_rows = _read_csv(trace_csv)
    selected = filter_selector_recoverable(trace_rows)

    safety = []
    for r in trace_rows:
        if _safe_int(r.get("trace_available")) != 1:
            continue
        if _safe_int(r.get("gold_present_in_candidate_groups")) != 1:
            continue
        if _safe_int(r.get("our_correct")) != 1:
            continue
        safety.append(r)

    outcome_cache_path = out_dir / "cohere_outcome_verifier_cache.jsonl"
    pair_cache_path = out_dir / "cohere_pairwise_verifier_cache.jsonl"
    outcome_cache = _load_cache(outcome_cache_path)
    pair_cache = _load_cache(pair_cache_path)

    expected_outcome_calls = 0
    expected_pair_calls = 0
    for r in selected:
        q = _norm(r.get("problem_statement"))
        cands = _candidate_groups_from_row(r)
        expected_outcome_calls += len(cands)
        expected_pair_calls += max(0, len(cands) - 1)
    call_plan = {
        "cases": len(selected),
        "cohere_model": model,
        "output_dir": str(out_dir),
        "cohere_outcome_verifier_cache_path": str(outcome_cache_path),
        "cohere_pairwise_verifier_cache_path": str(pair_cache_path),
        "expected_outcome_calls_upper_bound": expected_outcome_calls,
        "expected_pairwise_calls_upper_bound": expected_pair_calls,
        "expected_total_calls_upper_bound": expected_outcome_calls + expected_pair_calls,
    }
    (out_dir / "cohere_call_plan.json").write_text(json.dumps(call_plan, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(call_plan, indent=2))
    if args.dry_run:
        return
    if call_plan["expected_total_calls_upper_bound"] > args.max_cohere_calls:
        raise SystemExit(f"Expected cohere calls exceed cap: {call_plan['expected_total_calls_upper_bound']} > {args.max_cohere_calls}")

    selectors = [
        "current_default_selector",
        "support_family_selector",
        "conservative_support_family_selector",
        "risk_gated_support_family_selector",
        "cohere_outcome_verifier_selector",
        "cohere_pairwise_verifier_selector",
        "oracle_selector",
    ]

    case_rows: list[dict[str, Any]] = []
    for row in selected:
        gold = _norm(row.get("gold_answer"))
        current = _norm(row.get("our_final_answer"))
        q = _norm(row.get("problem_statement"))
        cands = _candidate_groups_from_row(row)
        by_ans = {_norm(c["answer"]): c for c in cands}

        support_ans, _ = support_family_selector(cands, current)
        cons_ans, _ = conservative_support_selector(cands, current)
        risk_ans, _ = risk_gated_support_selector(cands, current)
        out_ans, _, out_calls = outcome_verifier_selector(api_key, model, q, current, cands, outcome_cache, outcome_cache_path, args.dry_run)
        pair_ans, _, pair_calls = pairwise_verifier_selector(api_key, model, q, current, cands, pair_cache, pair_cache_path, args.dry_run)
        oracle = gold if gold in by_ans else current

        rec = {
            "case_id": _norm(row.get("case_id")),
            "dataset": _norm(row.get("dataset")),
            "example_id": _norm(row.get("example_id")),
            "seed": _safe_int(row.get("seed")),
            "budget": _safe_int(row.get("budget")),
            "current_answer": current,
            "gold_answer": gold,
            "current_correct": int(current == gold),
            "candidate_count": len(cands),
            "trace_available": 1,
            "gold_present_in_candidate_groups": 1,
            "oracle_selector_would_fix": 1,
        }
        answer_map = {
            "current_default_selector": current,
            "support_family_selector": support_ans,
            "conservative_support_family_selector": cons_ans,
            "risk_gated_support_family_selector": risk_ans,
            "cohere_outcome_verifier_selector": out_ans,
            "cohere_pairwise_verifier_selector": pair_ans,
            "oracle_selector": oracle,
        }
        calls_map = {
            "cohere_outcome_verifier_selector": out_calls,
            "cohere_pairwise_verifier_selector": pair_calls,
        }
        for s in selectors:
            ans = answer_map[s]
            cand = by_ans.get(ans, {"support": 0, "source_family_count": 0})
            rec[f"{s}_answer"] = ans
            rec[f"{s}_correct"] = int(ans == gold)
            rec[f"{s}_override"] = int(ans != current)
            rec[f"{s}_selected_support"] = _safe_int(cand.get("support"))
            rec[f"{s}_selected_family_count"] = _safe_int(cand.get("source_family_count"))
            rec[f"{s}_cohere_calls"] = calls_map.get(s, 0)
        case_rows.append(rec)

    safety_rows: list[dict[str, Any]] = []
    for row in safety:
        gold = _norm(row.get("gold_answer"))
        current = _norm(row.get("our_final_answer"))
        q = _norm(row.get("problem_statement"))
        cands = _candidate_groups_from_row(row)
        by_ans = {_norm(c["answer"]): c for c in cands}
        support_ans, _ = support_family_selector(cands, current)
        cons_ans, _ = conservative_support_selector(cands, current)
        risk_ans, _ = risk_gated_support_selector(cands, current)
        out_ans, _, out_calls = outcome_verifier_selector(api_key, model, q, current, cands, outcome_cache, outcome_cache_path, args.dry_run)
        pair_ans, _, pair_calls = pairwise_verifier_selector(api_key, model, q, current, cands, pair_cache, pair_cache_path, args.dry_run)
        oracle = gold if gold in by_ans else current
        rec = {
            "case_id": _norm(row.get("case_id")),
            "example_id": _norm(row.get("example_id")),
            "current_answer": current,
            "gold_answer": gold,
            "current_correct": int(current == gold),
        }
        answer_map = {
            "current_default_selector": current,
            "support_family_selector": support_ans,
            "conservative_support_family_selector": cons_ans,
            "risk_gated_support_family_selector": risk_ans,
            "cohere_outcome_verifier_selector": out_ans,
            "cohere_pairwise_verifier_selector": pair_ans,
            "oracle_selector": oracle,
        }
        for s in selectors:
            ans = answer_map[s]
            rec[f"{s}_correct"] = int(ans == gold)
            rec[f"{s}_break"] = int(int(current == gold) == 1 and int(ans == gold) == 0)
            rec[f"{s}_cohere_calls"] = out_calls if s == "cohere_outcome_verifier_selector" else (pair_calls if s == "cohere_pairwise_verifier_selector" else 0)
        safety_rows.append(rec)

    summary = [_selector_metrics(case_rows, s) for s in selectors]
    safety_summary = []
    for s in selectors:
        n = len(safety_rows)
        br = sum(_safe_int(r.get(f"{s}_break")) for r in safety_rows)
        fx = next((x["fixed"] for x in summary if x["selector"] == s), 0)
        safety_summary.append(
            {
                "selector": s,
                "safety_set_size": n,
                "breaks": br,
                "break_rate": round(br / n, 4) if n else 0.0,
                "fixes_on_33": fx,
                "net_fixes_minus_safety_breaks": fx - br,
            }
        )

    _write_csv(out_dir / "selector_gold_present_casebook.csv", case_rows)
    _write_csv(out_dir / "selector_safety_casebook.csv", safety_rows)
    _write_csv(out_dir / "selector_gold_present_summary.csv", summary)
    _write_csv(out_dir / "selector_safety_summary.csv", safety_summary)
    (out_dir / "selector_gold_present_summary.json").write_text(
        json.dumps(
            {
                "selected_case_count": len(case_rows),
                "expected_33": 33,
                "actual_case_count": len(case_rows),
                "count_match_expected_33": int(len(case_rows) == 33),
                "selectors": summary,
                "safety": safety_summary,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (out_dir / "selector_gold_present_report.md").write_text(
        "\n".join(
            [
                "# Selector on Gold-Present External Losses",
                "",
                f"- expected_case_count: 33",
                f"- actual_case_count: {len(case_rows)}",
                f"- exact_33_match: {len(case_rows)==33}",
                f"- best_fixes_selector: {max(summary, key=lambda x: x['fixed'])['selector'] if summary else 'none'}",
                f"- best_safety_adjusted_selector: {max(safety_summary, key=lambda x: x['net_fixes_minus_safety_breaks'])['selector'] if safety_summary else 'none'}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    doc_path = Path("docs") / f"SELECTOR_ON_GOLD_PRESENT_LOSSES_{ts}.md"
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.write_text(
        "\n".join(
            [
                "# Selector Experiment on 33 Gold-Present Losses",
                "",
                f"- Did we find exactly 33 cases: {len(case_rows)==33} (actual={len(case_rows)})",
                f"- Selector fixing most cases: {max(summary, key=lambda x: x['fixed'])['selector'] if summary else 'none'}",
                f"- Best safety-adjusted net gain: {max(safety_summary, key=lambda x: x['net_fixes_minus_safety_breaks'])['selector'] if safety_summary else 'none'}",
                f"- Support-family selector fixes: {next((x['fixed'] for x in summary if x['selector']=='support_family_selector'), 0)}",
                f"- Cohere outcome verifier fixes: {next((x['fixed'] for x in summary if x['selector']=='cohere_outcome_verifier_selector'), 0)}",
                f"- Cohere pairwise verifier fixes: {next((x['fixed'] for x in summary if x['selector']=='cohere_pairwise_verifier_selector'), 0)}",
                "- Bottleneck on this subset is selector quality by construction (gold present, oracle fixable).",
                "- Recommendation: promote selector with highest net_fixes_minus_safety_breaks for larger validation.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"output_dir": str(out_dir), "selected_cases": len(case_rows), "doc_path": str(doc_path)}, indent=2))


if __name__ == "__main__":
    main()
