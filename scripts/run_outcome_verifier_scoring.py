#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, json, os, hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import requests

COHERE_URL = "https://api.cohere.com/v2/chat"


def now_stamp() -> str:
    return datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')


def build_prompt(item: dict[str, Any], max_trace_chars: int = 6000) -> tuple[str, str, bool]:
    trace = str(item.get('trace_text') or '')
    truncated = False
    if len(trace) > max_trace_chars:
        trace = trace[:max_trace_chars]
        truncated = True
    user = (
        "Judge whether the candidate final answer is correct for the problem.\n"
        "Return strict JSON only with keys: candidate_id, case_id, normalized_answer, score, verdict, reason, used_trace, major_error.\n"
        "score must be float in [0,1]. verdict must be one of likely_correct, uncertain, likely_incorrect.\n\n"
        f"case_id: {item.get('case_id')}\n"
        f"candidate_id: {item.get('candidate_id')}\n"
        f"problem_statement:\n{item.get('problem_statement','')}\n\n"
        f"candidate_final_answer:\n{item.get('final_answer','')}\n\n"
        f"normalized_answer: {item.get('normalized_answer','')}\n"
        f"trace_present: {bool(trace.strip())}\n"
        f"trace_truncated: {truncated}\n"
        f"trace:\n{trace if trace else '(none)'}\n"
    )
    system = "You are a careful outcome verifier. Output JSON only."
    return system, user, truncated


def parse_verifier_response(text: str) -> dict[str, Any]:
    raw = text.strip()
    if raw.startswith('```'):
        raw = raw.strip('`')
        if raw.startswith('json'):
            raw = raw[4:].strip()
    obj = json.loads(raw)
    required = ['candidate_id', 'case_id', 'normalized_answer', 'score', 'verdict', 'reason', 'used_trace', 'major_error']
    missing = [k for k in required if k not in obj]
    if missing:
        raise ValueError(f'missing fields: {missing}')
    score = float(obj['score'])
    if not (0.0 <= score <= 1.0):
        raise ValueError('score_out_of_range')
    if obj['verdict'] not in {'likely_correct', 'uncertain', 'likely_incorrect'}:
        raise ValueError('invalid_verdict')
    obj['score'] = score
    obj['used_trace'] = bool(obj['used_trace'])
    return obj


def cache_key(item: dict[str, Any]) -> str:
    return hashlib.sha256((str(item.get('case_id'))+'|'+str(item.get('candidate_id'))+'|'+str(item.get('problem_statement'))+'|'+str(item.get('normalized_answer'))).encode()).hexdigest()


def call_cohere(api_key: str, model: str, system: str, user: str, temperature: float) -> str:
    resp = requests.post(COHERE_URL, headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}, json={
        'model': model,
        'temperature': temperature,
        'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}],
    }, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    return data['message']['content'][0]['text']


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--call-plan', required=True)
    ap.add_argument('--output-dir', required=True)
    ap.add_argument('--backend', required=True, choices=['cohere'])
    ap.add_argument('--model', default='command-a-03-2025')
    ap.add_argument('--max-calls', type=int, required=True)
    ap.add_argument('--allow-api', action='store_true')
    ap.add_argument('--cache-path', required=True)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--resume', action='store_true')
    ap.add_argument('--temperature', type=float, default=0.0)
    ap.add_argument('--no-gold-features', action='store_true')
    args = ap.parse_args()

    out = Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)
    items = [json.loads(x) for x in Path(args.call_plan).read_text(encoding='utf-8').splitlines() if x.strip()]
    total = len(items)
    existing: dict[tuple[str, str], dict[str, Any]] = {}
    cache_path = Path(args.cache_path)
    if args.resume and cache_path.exists():
        for line in cache_path.read_text(encoding='utf-8').splitlines():
            if line.strip():
                r = json.loads(line)
                existing[(str(r['case_id']), str(r['candidate_id']))] = r

    attempted = successful = failed = skipped = calls = 0
    failures = []
    results = list(existing.values())
    api_key = os.getenv('COHERE_API_KEY', '')
    if not args.dry_run and args.allow_api and not api_key:
        miss = out / 'missing_credentials_report.md'
        miss.write_text('# Missing credentials\n\nCOHERE_API_KEY is not set; no API calls made.\n', encoding='utf-8')
        print(str(out))
        return

    for idx,it in enumerate(items, start=1):
        key = (str(it.get('case_id')), str(it.get('candidate_id')))
        if key in existing:
            skipped += 1
            continue
        if calls >= args.max_calls:
            failures.append({'item': it, 'error': 'max_calls_reached'})
            failed += 1
            continue
        attempted += 1
        system, user, truncated = build_prompt(it)
        try:
            print(f"scoring {idx}/{total}")
            if args.dry_run or not args.allow_api:
                raise RuntimeError('api_disabled')
            text = call_cohere(api_key, args.model, system, user, args.temperature)
            parsed = parse_verifier_response(text)
            rec = {
                'case_id': str(parsed['case_id']),
                'candidate_id': str(parsed['candidate_id']),
                'normalized_answer': str(parsed['normalized_answer']),
                'verifier_score': float(parsed['score']),
                'verdict': parsed['verdict'],
                'reason': str(parsed['reason'])[:500],
                'used_trace': bool(parsed['used_trace']),
                'major_error': parsed['major_error'],
                'trace_truncated': truncated,
                'item_hash': cache_key(it),
            }
            results.append(rec)
            successful += 1
            calls += 1
        except Exception as e:
            failed += 1
            failures.append({'item': {'case_id': it.get('case_id'), 'candidate_id': it.get('candidate_id')}, 'error': str(e)})

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text('\n'.join(json.dumps(r) for r in results) + ('\n' if results else ''), encoding='utf-8')
    (out / 'verifier_scores.jsonl').write_text(cache_path.read_text(encoding='utf-8'), encoding='utf-8')
    (out / 'failed_or_skipped_items.jsonl').write_text('\n'.join(json.dumps(r) for r in failures) + ('\n' if failures else ''), encoding='utf-8')

    vals = [r['verifier_score'] for r in results if isinstance(r.get('verifier_score'), (int, float))]
    bins = {'0-0.2':0,'0.2-0.4':0,'0.4-0.6':0,'0.6-0.8':0,'0.8-1.0':0}
    for v in vals:
        if v < 0.2: bins['0-0.2'] += 1
        elif v < 0.4: bins['0.2-0.4'] += 1
        elif v < 0.6: bins['0.4-0.6'] += 1
        elif v < 0.8: bins['0.6-0.8'] += 1
        else: bins['0.8-1.0'] += 1

    summary = {
        'backend': args.backend, 'model': args.model, 'total_call_plan_items': total,
        'attempted_calls': attempted, 'successful_scores': successful, 'failed_calls': failed,
        'skipped_existing_cached_scores': skipped, 'max_calls': args.max_calls, 'api_calls_made': calls,
        'estimated_or_actual_cost': None,
        'no_gold_oracle_evaluation_only_in_prompts': True,
        'score_distribution': bins,
    }
    (out / 'manifest.json').write_text(json.dumps({'call_plan': args.call_plan, 'cache_path': str(cache_path)}, indent=2) + '\n', encoding='utf-8')
    (out / 'verifier_scoring_summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    with (out / 'verifier_scoring_summary.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(summary.keys())); w.writeheader(); w.writerow(summary)
    (out / 'verifier_scoring_report.md').write_text('# Verifier scoring report\n\n' + '\n'.join(f'- {k}: {v}' for k,v in summary.items()) + '\n', encoding='utf-8')
    print(str(out))


if __name__ == '__main__':
    main()
