#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, json, os, hashlib, time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import requests

COHERE_URL = "https://api.cohere.com/v2/chat"


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')


def build_prompt(item: dict[str, Any], max_trace_chars: int = 6000) -> tuple[str, str, bool]:
    trace = str(item.get('trace_text') or '')
    truncated = len(trace) > max_trace_chars
    if truncated:
        trace = trace[:max_trace_chars]
    user = (
        "Judge if the candidate final answer is correct for the problem. "
        "Return JSON only with keys: candidate_id, case_id, normalized_answer, score, verdict, reason, used_trace, major_error. "
        "score in [0,1], verdict in {likely_correct, uncertain, likely_incorrect}. Keep reason short.\n\n"
        f"case_id: {item.get('case_id')}\n"
        f"candidate_id: {item.get('candidate_id')}\n"
        f"problem_statement:\n{item.get('problem_statement','')}\n\n"
        f"candidate_final_answer:\n{item.get('final_answer','')}\n\n"
        f"normalized_answer: {item.get('normalized_answer','')}\n"
        f"trace_present: {bool(trace.strip())}\n"
        f"trace_truncated: {truncated}\n"
        f"trace:\n{trace if trace else '(none)'}\n"
    )
    system = "You are a careful outcome verifier. Output strict JSON only, no markdown."
    return system, user, truncated


def prompt_hygiene_ok(system: str, user: str) -> bool:
    s = (system + "\n" + user).lower()
    return all(t not in s for t in ["gold_answer", "evaluation_only", "oracle"])


def parse_verifier_response(text: str) -> dict[str, Any]:
    raw = text.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()
    obj = json.loads(raw)
    need = ["candidate_id", "case_id", "normalized_answer", "score", "verdict", "reason", "used_trace", "major_error"]
    miss = [k for k in need if k not in obj]
    if miss:
        raise ValueError(f"missing_fields:{miss}")
    score = float(obj["score"])
    if not (0.0 <= score <= 1.0):
        raise ValueError("score_out_of_range")
    if obj["verdict"] not in {"likely_correct", "uncertain", "likely_incorrect"}:
        raise ValueError("invalid_verdict")
    obj["score"] = score
    obj["used_trace"] = bool(obj["used_trace"])
    return obj


def cache_key(item: dict[str, Any]) -> str:
    return hashlib.sha256((str(item.get("case_id"))+"|"+str(item.get("candidate_id"))+"|"+str(item.get("problem_statement"))+"|"+str(item.get("normalized_answer"))).encode()).hexdigest()


def call_cohere(api_key: str, model: str, system: str, user: str, temperature: float, timeout_seconds: float) -> str:
    payload = {
        "model": model,
        "temperature": temperature,
        "max_tokens": 400,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }
    r = requests.post(COHERE_URL, headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, json=payload, timeout=timeout_seconds)
    r.raise_for_status()
    d = r.json()
    return d["message"]["content"][0]["text"]


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
        f.flush()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--call-plan", required=True)
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--backend", required=True, choices=["cohere"])
    ap.add_argument("--model", default="command-a-03-2025")
    ap.add_argument("--max-calls", type=int, required=True)
    ap.add_argument("--max-new-calls", type=int)
    ap.add_argument("--start-index", type=int, default=0)
    ap.add_argument("--allow-api", action="store_true")
    ap.add_argument("--cache-path", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True)
    ap.add_argument("--validate-call-plan-only", action="store_true")
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--request-timeout-seconds", type=float, default=45)
    ap.add_argument("--max-retries", type=int, default=2)
    ap.add_argument("--retry-backoff-seconds", type=float, default=5)
    ap.add_argument("--no-gold-features", action="store_true")
    args = ap.parse_args()

    t0 = time.time()
    out = Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)
    cache_path = Path(args.cache_path); cache_path.parent.mkdir(parents=True, exist_ok=True)
    failed_path = out / "failed_or_skipped_items.jsonl"
    progress_path = out / "progress_summary.json"
    score_out_path = out / "verifier_scores.jsonl"
    if not score_out_path.exists(): score_out_path.write_text("", encoding="utf-8")
    if not failed_path.exists(): failed_path.write_text("", encoding="utf-8")

    items = [json.loads(x) for x in Path(args.call_plan).read_text(encoding="utf-8").splitlines() if x.strip()]
    total = len(items)

    existing = {}
    if args.resume and cache_path.exists():
        for line in cache_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                existing[(str(r.get("case_id")), str(r.get("candidate_id")))] = r

    attempted = succeeded = failed = skipped = calls = 0

    def write_progress(current_index: int):
        progress = {
            "total_items": total, "attempted": attempted, "succeeded": succeeded, "failed": failed, "skipped": skipped,
            "current_index": current_index, "elapsed_seconds": round(time.time()-t0, 3), "backend": args.backend,
            "model": args.model, "last_updated_timestamp": utc_stamp(),
        }
        progress_path.write_text(json.dumps(progress, indent=2) + "\n", encoding="utf-8")

    for i, it in enumerate(items):
        if i < args.start_index:
            continue
        system, user, truncated = build_prompt(it)
        if not prompt_hygiene_ok(system, user):
            raise SystemExit("prompt hygiene check failed")
        if args.validate_call_plan_only:
            attempted += 1
            write_progress(i)
            continue

        key = (str(it.get("case_id")), str(it.get("candidate_id")))
        if key in existing:
            skipped += 1
            write_progress(i)
            continue
        if calls >= args.max_calls:
            append_jsonl(failed_path, {"item": key, "error": "max_calls_reached"})
            failed += 1
            write_progress(i)
            continue
        if args.max_new_calls is not None and calls >= args.max_new_calls:
            break

        attempted += 1
        if args.dry_run or not args.allow_api:
            append_jsonl(failed_path, {"item": key, "error": "api_disabled"})
            failed += 1
            write_progress(i)
            continue

        api_key = os.getenv("COHERE_API_KEY", "")
        if not api_key:
            (out / "missing_credentials_report.md").write_text("# Missing credentials\n\nCOHERE_API_KEY is not set; no API calls made.\n", encoding="utf-8")
            break

        err = None
        for retry in range(args.max_retries + 1):
            try:
                text = call_cohere(api_key, args.model, system, user, args.temperature, args.request_timeout_seconds)
                parsed = parse_verifier_response(text)
                rec = {
                    "case_id": str(parsed["case_id"]), "candidate_id": str(parsed["candidate_id"]), "normalized_answer": str(parsed["normalized_answer"]),
                    "verifier_score": float(parsed["score"]), "verdict": parsed["verdict"], "reason": str(parsed["reason"])[:500],
                    "used_trace": bool(parsed["used_trace"]), "major_error": parsed["major_error"], "trace_truncated": truncated, "item_hash": cache_key(it),
                }
                append_jsonl(cache_path, rec)
                if score_out_path.resolve() != cache_path.resolve():
                    append_jsonl(score_out_path, rec)
                existing[key] = rec
                succeeded += 1
                calls += 1
                err = None
                break
            except Exception as e:
                err = str(e)
                if retry < args.max_retries:
                    time.sleep(args.retry_backoff_seconds)
        if err is not None:
            failed += 1
            append_jsonl(failed_path, {"item": {"case_id": key[0], "candidate_id": key[1]}, "error": err})
        write_progress(i)

    vals = []
    for line in cache_path.read_text(encoding="utf-8").splitlines() if cache_path.exists() else []:
        if line.strip():
            r = json.loads(line)
            if isinstance(r.get("verifier_score"), (int, float)):
                vals.append(float(r["verifier_score"]))
    bins = {"0-0.2":0,"0.2-0.4":0,"0.4-0.6":0,"0.6-0.8":0,"0.8-1.0":0}
    for v in vals:
        bins["0-0.2" if v < 0.2 else "0.2-0.4" if v < 0.4 else "0.4-0.6" if v < 0.6 else "0.6-0.8" if v < 0.8 else "0.8-1.0"] += 1

    summary = {"backend": args.backend, "model": args.model, "total_call_plan_items": total, "attempted_calls": attempted, "successful_scores": succeeded, "failed_calls": failed,
               "skipped_existing_cached_scores": skipped, "max_calls": args.max_calls, "api_calls_made": calls, "estimated_or_actual_cost": None,
               "no_gold_oracle_evaluation_only_in_prompts": True, "score_distribution": bins}
    (out / "manifest.json").write_text(json.dumps({"call_plan": args.call_plan, "cache_path": str(cache_path)}, indent=2)+"\n", encoding="utf-8")
    (out / "verifier_scoring_summary.json").write_text(json.dumps(summary, indent=2)+"\n", encoding="utf-8")
    with (out / "verifier_scoring_summary.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(summary.keys())); w.writeheader(); w.writerow(summary)
    (out / "verifier_scoring_report.md").write_text("# Verifier scoring report\n\n" + "\n".join(f"- {k}: {v}" for k,v in summary.items()) + "\n", encoding="utf-8")
    write_progress(total-1)
    print(str(out))


if __name__ == "__main__":
    main()
