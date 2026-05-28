#!/usr/bin/env python3
"""
v3: Aggressive offline re-extraction heuristics for D6 JSON-first contract.
Adds:
- inspect reasoning/verification fields for boxed or 'final answer' phrases
- regex extraction of key-like patterns inside text (final_answer, finalAnswer, result, answer)
- LaTeX boxed extraction anywhere
- conservative numeric token normalization
- records answer_key_used and extraction confidence hints
"""
import sys
import json
import re
import ast
from pathlib import Path
import csv

ALIAS_KEYS = ['answer','final_answer','finalAnswer','final','result']

def clean_answer_token(s):
    if s is None:
        return None
    t = str(s).strip()
    # remove LaTeX \boxed{...}
    t = re.sub(r"\\\\?boxed\{([^}]*)\}", r"\1", t)
    # remove dollar signs
    t = t.replace('$','')
    # unwrap markdown/code fences
    t = re.sub(r"^```+|```+$", '', t)
    # strip quotes
    if (t.startswith('"') and t.endswith('"')) or (t.startswith("'") and t.endswith("'")):
        t = t[1:-1].strip()
    # strip surrounding text like 'Answer: 22' -> keep the token
    m = re.search(r"([-+]?\d+\.?\d*(?:e[-+]?\d+)?)", t, flags=re.I)
    if m:
        # prefer numeric token if present
        return m.group(1).strip()
    # otherwise collapse whitespace
    t = ' '.join(t.split())
    # remove trailing punctuation
    t = t.rstrip('.;:,')
    return t.strip()

def find_json_in_text(s):
    m = re.search(r"\{.*\}", s, flags=re.S)
    if not m:
        return None
    candidate = m.group(0)
    try:
        obj = json.loads(candidate)
        return obj
    except Exception:
        return None

def try_strict_or_alias_json(obj_text):
    t = obj_text.strip()
    if t.startswith('{') and t.endswith('}'):
        try:
            obj = json.loads(t)
        except Exception:
            obj = find_json_in_text(obj_text)
    else:
        obj = find_json_in_text(obj_text)
    if obj and isinstance(obj, dict):
        for k in ALIAS_KEYS:
            if k in obj and obj[k] is not None and str(obj[k]).strip()!='':
                return obj[k], k, obj
        # inspect reasoning/verification fields
        for field in ['reasoning','verification','explanation']:
            if field in obj and obj[field]:
                # search for boxed or final answer phrases
                text = obj[field]
                # boxed
                m = re.search(r"\\boxed\{([^}]+)\}", text)
                if m:
                    return m.group(1), field+':boxed', obj
                # final answer phrase
                m2 = re.search(r"final\s*answer\s*(?:is|:)?\s*([\d\-+\.eE]+)", text, flags=re.I)
                if m2:
                    return m2.group(1), field+':final_phrase', obj
                # "Final answer: 22" with words
                m3 = re.search(r"final\s*answer\s*(?:is|:)?\s*([^\\n\\.]+)", text, flags=re.I)
                if m3:
                    return m3.group(1), field+':final_phrase_text', obj
    return None

def try_json_fenced(text):
    fences = re.findall(r"```(?:json)?\n(.*?)```", text, flags=re.S|re.I)
    for block in fences:
        try:
            obj = json.loads(block)
            if isinstance(obj, dict):
                for k in ALIAS_KEYS:
                    if k in obj and obj[k]:
                        return obj[k], k, obj
        except Exception:
            obj = find_json_in_text(block)
            if obj:
                for k in ALIAS_KEYS:
                    if k in obj and obj[k]:
                        return obj[k], k, obj
    return None

def try_python_literal(text):
    m = re.search(r"\{.*\}", text, flags=re.S)
    if not m:
        return None
    candidate = m.group(0)
    try:
        obj = ast.literal_eval(candidate)
        if isinstance(obj, dict):
            for k in ALIAS_KEYS:
                if k in obj and obj[k]:
                    return obj[k], k, obj
            for field in ['reasoning','verification','explanation']:
                if field in obj and obj[field]:
                    # boxed
                    mm = re.search(r"\\boxed\{([^}]+)\}", str(obj[field]))
                    if mm:
                        return mm.group(1), field+':boxed', obj
    except Exception:
        # try mild cleanup
        cleaned = re.sub(r",\s*}\s*$","}", candidate)
        try:
            obj = ast.literal_eval(cleaned)
            if isinstance(obj, dict):
                for k in ALIAS_KEYS:
                    if k in obj and obj[k]:
                        return obj[k], k, obj
        except Exception:
            pass
    return None

def try_regex_final_phrase(text):
    # search for patterns like 'Final answer: 22' or 'The final answer is 22.'
    m = re.search(r"final\s*answer\s*(?:is|:)?\s*`?\\?\\?\{?\s*([\d\-+\.eE]+)\s*\}?`?", text, flags=re.I)
    if m:
        return m.group(1), 'final_phrase_regex', None
    # more general: 'Final answer: <word>' capture non-newline up to punctuation
    m2 = re.search(r"final\s*answer\s*(?:is|:)?\s*([^\n\.]+)", text, flags=re.I)
    if m2:
        return m2.group(1).strip(), 'final_phrase_text_regex', None
    return None

def try_boxed_anywhere(text):
    m = re.search(r"\\boxed\{([^}]+)\}", text)
    if m:
        return m.group(1).strip(), 'boxed_anywhere', None
    return None

def try_any_answer_keyword_in_text(text):
    # look for 'answer:' or 'Answer =' etc, capture following token
    m = re.search(r"(?:answer|final_answer|finalAnswer|result)\s*[:=]\s*`?\\?\\?\{?\s*([^\n`\}]+)`,?`?", text, flags=re.I)
    if m:
        return m.group(1).strip(), 'keyword_colon', None
    return None

def try_last_numeric_token(text):
    # last numeric in text
    nums = re.findall(r"[-+]?\d+\.?\d*(?:e[-+]?\d+)?", text, flags=re.I)
    if nums:
        return nums[-1], 'last_numeric_token', None
    return None


def normalize_answer(a):
    if a is None:
        return None
    return clean_answer_token(a)


def main():
    if len(sys.argv) < 3:
        print("Usage: d6_reextract_json_first_v3.py <generation_outputs.jsonl> <out_dir>")
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

            # 1. strict or alias JSON
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

            # 2. fenced json
            if extracted is None:
                res = try_json_fenced(resp)
                if res:
                    val, key, obj = res
                    extracted = val
                    method = 'json_fenced'
                    response_format = 'json_in_fence'
                    answer_key_used = key
                    if key == 'answer':
                        strict_compliance = True
                        strict_json_count += 1

            # 3. python literal
            if extracted is None:
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

            # 4. inspect any JSON parsed object's reasoning/verification already done above in try_strict_or_alias_json
            # 5. search for boxed answer anywhere
            if extracted is None:
                res = try_boxed_anywhere(resp)
                if res:
                    val, tag, obj = res
                    extracted = val
                    method = tag
                    response_format = 'boxed_anywhere'
                    answer_key_used = 'boxed_anywhere'

            # 6. search for final phrase regex
            if extracted is None:
                res = try_regex_final_phrase(resp)
                if res:
                    val, tag, obj = res
                    extracted = val
                    method = tag
                    response_format = 'final_phrase'
                    answer_key_used = 'final_phrase'

            # 7. any answer keyword colon pattern
            if extracted is None:
                res = try_any_answer_keyword_in_text(resp)
                if res:
                    val, tag, obj = res
                    extracted = val
                    method = tag
                    response_format = 'keyword_colon'
                    answer_key_used = 'keyword_colon'

            # 8. last numeric token as conservative fallback
            if extracted is None:
                res = try_last_numeric_token(resp)
                if res:
                    val, tag, obj = res
                    extracted = val
                    method = tag
                    response_format = 'last_numeric'
                    answer_key_used = 'last_numeric'

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
    csv_path = out / 'd6_job1_reextraction_after_parser_patch_v3.csv'
    with csv_path.open('w', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else ['generation_item_id'])
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    # write report md
    md_path = out / 'd6_job1_reextraction_after_parser_patch_report_v3.md'
    with md_path.open('w') as fh:
        fh.write('# D6 re-extraction after parser patch v3\n\n')
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

    print('Wrote re-extraction v3 outputs to', out)

if __name__ == '__main__':
    main()
