#!/usr/bin/env python3
"""
Improved offline re-extraction tool for D6 JSON-first contract.
Adds acceptance for answer aliases, strips boxed LaTeX, dollar signs, surrounding quotes, and records answer_key_used.
Safe parsing with json and ast.literal_eval. Writes CSV and markdown reports to given output directory.
"""
import sys
import json
import re
import ast
from pathlib import Path
import csv

ALIAS_KEYS = ['answer','final_answer','finalAnswer','final','result']
FORBIDDEN_FIELDS = ['gold','correct','correctness','oracle','source_correct','action_correct','frontier_correct','l1_correct','s1_correct','tale_correct','ground_truth']


def clean_answer_token(s):
    if s is None:
        return None
    t = str(s).strip()
    # strip LaTeX boxed forms \boxed{...}
    t = re.sub(r"\\\\?boxed\{([^}]*)\}", r"\1", t)
    # remove dollar signs
    t = t.replace('$','')
    # strip surrounding quotes
    if (t.startswith('"') and t.endswith('"')) or (t.startswith("'") and t.endswith("'")):
        t = t[1:-1].strip()
    # remove trailing punctuation such as '.' unless it's part of a float like '3.14'
    if re.match(r'^-?\d+\.?\d*$', t):
        # numeric-looking, leave as is
        pass
    else:
        t = t.rstrip('.\\n \t')
    return t.strip()


def find_json_in_text(s):
    # attempt to find the first {...} that parses as json
    m = re.search(r"\{.*\}", s, flags=re.S)
    if not m:
        return None
    candidate = m.group(0)
    try:
        obj = json.loads(candidate)
        return obj
    except Exception:
        return None


def try_strict_or_alias_json(s):
    t = s.strip()
    # direct JSON object
    if t.startswith('{') and t.endswith('}'):
        try:
            obj = json.loads(t)
            if isinstance(obj, dict):
                for k in ALIAS_KEYS:
                    if k in obj:
                        return obj[k], k, obj
        except Exception:
            pass
    # try to find JSON substring
    obj = find_json_in_text(s)
    if obj:
        for k in ALIAS_KEYS:
            if k in obj:
                return obj[k], k, obj
    return None


def try_fenced_json(s):
    fences = re.findall(r"```(?:json)?\n(.*?)```", s, flags=re.S|re.I)
    for block in fences:
        try:
            obj = json.loads(block)
            if isinstance(obj, dict):
                for k in ALIAS_KEYS:
                    if k in obj:
                        return obj[k], k, obj
        except Exception:
            obj = find_json_in_text(block)
            if obj:
                for k in ALIAS_KEYS:
                    if k in obj:
                        return obj[k], k, obj
    return None


def try_python_literal(s):
    m = re.search(r"\{.*\}", s, flags=re.S)
    if not m:
        return None
    candidate = m.group(0)
    try:
        obj = ast.literal_eval(candidate)
        if isinstance(obj, dict):
            for k in ALIAS_KEYS:
                if k in obj:
                    return obj[k], k, obj
    except Exception:
        # try loose cleanup: remove trailing commas
        cleaned = re.sub(r",\s*}\s*$","}", candidate)
        try:
            obj = ast.literal_eval(cleaned)
            if isinstance(obj, dict):
                for k in ALIAS_KEYS:
                    if k in obj:
                        return obj[k], k, obj
        except Exception:
            pass
    return None


def try_final_answer_line(s):
    for line in reversed(s.splitlines()):
        line = line.strip()
        if not line:
            continue
        # common patterns
        m = re.match(r"(?:FINAL[_\- ]?ANSWER|FINAL-ANSWER|FINAL ANSWER)[:=]\s*(.*)$", line, flags=re.I)
        if m:
            return m.group(1).strip(), 'final_answer_line', None
    return None


def try_boxed_answer(s):
    m = re.search(r"\\boxed\{([^}]+)\}", s)
    if m:
        return m.group(1).strip(), 'boxed_answer', None
    return None


def try_last_line_numeric(s):
    lines = [l.strip() for l in s.splitlines() if l.strip()]
    if not lines:
        return None
    last = lines[-1]
    # exact numeric
    if re.fullmatch(r"[-+]?\d+\.?\d*(?:e[-+]?\d+)?", last, flags=re.I):
        return last, 'last_line_numeric', None
    # find first integer token
    m2 = re.search(r"\b(\d+)\b", last)
    if m2:
        return m2.group(1), 'last_line_numeric_token', None
    return None


def normalize_answer(a):
    if a is None:
        return None
    return clean_answer_token(a)


def main():
    if len(sys.argv) < 3:
        print("Usage: d6_reextract_json_first_v2.py <generation_outputs.jsonl> <out_dir>")
        sys.exit(2)
    src = Path(sys.argv[1])
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    total = 0
    strict_json_count = 0
    key_dist = {}
    with src.open('r') as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            total += 1
            try:
                item = json.loads(line)
            except Exception:
                continue
            resp = item.get('response_text','')
            extracted = None
            method = None
            strict_compliance = False
            response_format = 'unknown'
            answer_key_used = None

            # 1. strict JSON or alias keys
            res = try_strict_or_alias_json(resp)
            if res:
                val, key, obj = res
                extracted = val
                method = 'strict_or_alias_json'
                response_format = 'json_object'
                answer_key_used = key
                if key == 'answer':
                    strict_compliance = True
                    strict_json_count += 1
            if extracted is None:
                # 2. fenced JSON
                res = try_fenced_json(resp)
                if res:
                    val, key, obj = res
                    extracted = val
                    method = 'fenced_json'
                    response_format = 'json_in_fence'
                    answer_key_used = key
                    if key == 'answer':
                        strict_compliance = True
                        strict_json_count += 1
            if extracted is None:
                # 3. python-dict-like
                res = try_python_literal(resp)
                if res:
                    val, key, obj = res
                    extracted = val
                    method = 'python_literal'
                    response_format = 'python_dict_like'
                    answer_key_used = key
                    if key == 'answer':
                        strict_compliance = True
                        strict_json_count += 1
            if extracted is None:
                # 4. FINAL_ANSWER line
                res = try_final_answer_line(resp)
                if res:
                    val, mth, obj = res
                    extracted = val
                    method = 'final_answer_line'
                    response_format = 'final_line'
                    answer_key_used = 'final_answer_line'
            if extracted is None:
                # 5. boxed answer
                res = try_boxed_answer(resp)
                if res:
                    val, mth, obj = res
                    extracted = val
                    method = 'boxed_answer'
                    response_format = 'boxed'
                    answer_key_used = 'boxed'
            if extracted is None:
                # 6. last-line numeric
                res = try_last_line_numeric(resp)
                if res:
                    val, mth, obj = res
                    extracted = val
                    method = mth
                    response_format = 'numeric_last_line'
                    answer_key_used = 'last_line'

            if answer_key_used:
                key_dist[answer_key_used] = key_dist.get(answer_key_used,0)+1

            normalized = normalize_answer(extracted)
            if method is None:
                method = 'none'

            rows.append({
                'generation_item_id': item.get('generation_item_id'),
                'original_example_id': item.get('original_example_id'),
                'response_text': resp,
                'extracted_answer': normalized,
                'extraction_method': method,
                'extraction_status': 'ok' if normalized is not None else 'failed',
                'strict_json_contract_compliance': 'true' if strict_compliance else 'false',
                'extraction_error': '' if normalized is not None else item.get('extraction_error','no_supported_pattern'),
                'response_format_type': response_format,
                'answer_key_used': answer_key_used or ''
            })

    # write CSV
    csv_path = out / 'd6_job1_reextraction_after_parser_patch.csv'
    with csv_path.open('w', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else ['generation_item_id'])
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    # write report md
    md_path = out / 'd6_job1_reextraction_after_parser_patch_report.md'
    with md_path.open('w') as fh:
        fh.write('# D6 re-extraction after parser patch\n\n')
        fh.write(f'Total items processed: {total}\n\n')
        fh.write(f'Strict JSON with required "answer" key: {strict_json_count}\n\n')
        fh.write('Extraction method distribution:\n\n')
        dist = {}
        recovered = 0
        for r in rows:
            dist[r['extraction_method']] = dist.get(r['extraction_method'],0)+1
            if r['extraction_status']=='ok':
                recovered += 1
        for k,v in sorted(dist.items(), key=lambda x:-x[1]):
            fh.write(f'- {k}: {v}\n')
        fh.write('\nRecovered answers count: %d\n' % recovered)
        fh.write('\nAnswer key distribution:\n')
        for k,v in sorted(key_dist.items(), key=lambda x:-x[1]):
            fh.write(f'- {k}: {v}\n')

    print('Wrote re-extraction outputs to', out)


if __name__ == '__main__':
    main()
