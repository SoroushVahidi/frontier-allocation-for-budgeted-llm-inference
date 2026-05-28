#!/usr/bin/env python3
"""
Offline re-extraction tool for D6 JSON-first contract.
Reads a generation_outputs.jsonl and applies extraction rules in order:
 1) strict JSON object with required "answer" key
 2) JSON inside markdown fence with "answer"
 3) Python-dict-like via ast.literal_eval with "answer"
 4) FINAL_ANSWER line fallback
 5) boxed answer fallback (\\boxed{...})
 6) last-line numeric conservative fallback
Writes CSV and markdown reports to given output directory.
"""
import sys
import json
import re
import ast
from pathlib import Path
import csv

FORBIDDEN_FIELDS = ['gold','correct','correctness','oracle','source_correct','action_correct','frontier_correct','l1_correct','s1_correct','tale_correct','ground_truth']


def try_strict_json(s):
    t = s.strip()
    if not (t.startswith('{') and t.endswith('}')):
        return None
    try:
        obj = json.loads(t)
    except Exception:
        return None
    if isinstance(obj, dict) and 'answer' in obj:
        return obj['answer'], obj
    return None


def try_fenced_json(s):
    # look for ```json ... ``` or ``` ... ``` containing JSON
    fences = re.findall(r"```(?:json)?\n(.*?)```", s, flags=re.S|re.I)
    for block in fences:
        try:
            obj = json.loads(block)
            if isinstance(obj, dict) and 'answer' in obj:
                return obj['answer'], obj
        except Exception:
            # try to find JSON substring
            m = re.search(r"\{.*\}", block, flags=re.S)
            if m:
                try:
                    obj = json.loads(m.group(0))
                    if isinstance(obj, dict) and 'answer' in obj:
                        return obj['answer'], obj
                except Exception:
                    pass
    return None


def try_python_literal(s):
    # find a python-dict like substring
    m = re.search(r"\{.*\}", s, flags=re.S)
    if not m:
        return None
    candidate = m.group(0)
    try:
        obj = ast.literal_eval(candidate)
        if isinstance(obj, dict) and 'answer' in obj:
            return obj['answer'], obj
    except Exception:
        return None
    return None


def try_final_answer_line(s):
    # look for lines with FINAL_ANSWER or FINAL ANSWER or FINAL-ANSWER
    for line in s.splitlines():
        line = line.strip()
        m = re.match(r"(?:FINAL[_\- ]?ANSWER)[:=\s]*`?\{?\\?\\?([^`\}]+)`,?`?", line, flags=re.I)
    # fallback simpler
    for line in reversed(s.splitlines()):
        line = line.strip()
        if line.upper().startswith('FINAL_ANSWER') or line.upper().startswith('FINAL ANSWER') or line.upper().startswith('FINAL-ANSWER'):
            parts = re.split(r'[:=]', line, maxsplit=1)
            if len(parts) == 2:
                return parts[1].strip().strip('`').strip()
    return None


def try_boxed_answer(s):
    m = re.search(r"\\boxed\{([^}]+)\}", s)
    if m:
        return m.group(1).strip()
    return None


def try_last_line_numeric(s):
    lines = [l.strip() for l in s.splitlines() if l.strip()]
    if not lines:
        return None
    last = lines[-1]
    # if last line is a simple number or single token like '22' or '22.' or '22\n'
    m = re.search(r"([-+]?[0-9]*\.?[0-9]+(?:e[-+]?\d+)?)", last)
    if m and m.group(1) == last:
        return last
    # otherwise try to find a number token in last line but conservative: only integer
    m2 = re.search(r"\b(\d+)\b", last)
    if m2:
        return m2.group(1)
    return None


def normalize_answer(a):
    if a is None:
        return None
    return str(a).strip()


def main():
    if len(sys.argv) < 3:
        print("Usage: d6_reextract_json_first.py <generation_outputs.jsonl> <out_dir>")
        sys.exit(2)
    src = Path(sys.argv[1])
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    strict_json_count = 0
    total = 0
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

            # 1. strict JSON object with required 'answer'
            t = resp.strip()
            if t.startswith('{') and t.endswith('}'):
                try:
                    obj = json.loads(t)
                    if isinstance(obj, dict) and 'answer' in obj and len(t)==len(json.dumps(obj,ensure_ascii=False)) or True:
                        # if parsed and has 'answer'
                        if 'answer' in obj:
                            extracted = obj['answer']
                            method = 'strict_valid_json_answer'
                            strict_compliance = True
                            response_format = 'json_object'
                except Exception:
                    pass
            if extracted is None:
                # 2. fenced JSON
                try_res = try_fenced_json(resp)
                if try_res:
                    extracted, obj = try_res
                    method = 'fenced_json_answer'
                    response_format = 'json_in_fence'
            if extracted is None:
                # 3. python-dict-like
                try_res = try_python_literal(resp)
                if try_res:
                    extracted, obj = try_res
                    method = 'python_literal_answer'
                    response_format = 'python_dict_like'
            if extracted is None:
                # 4. FINAL_ANSWER line fallback
                fa = try_final_answer_line(resp)
                if fa:
                    extracted = fa
                    method = 'final_answer_line'
                    response_format = 'final_line'
            if extracted is None:
                # 5. boxed answer
                bx = try_boxed_answer(resp)
                if bx:
                    extracted = bx
                    method = 'boxed_answer'
                    response_format = 'boxed'
            if extracted is None:
                # 6. last-line numeric conservative fallback
                ln = try_last_line_numeric(resp)
                if ln:
                    extracted = ln
                    method = 'last_line_numeric'
                    response_format = 'numeric_last_line'

            if method is None:
                method = 'none'
            normalized = normalize_answer(extracted)
            if method == 'strict_valid_json_answer':
                strict_json_count += 1

            rows.append({
                'generation_item_id': item.get('generation_item_id'),
                'original_example_id': item.get('original_example_id'),
                'response_text': resp,
                'extracted_answer': normalized,
                'extraction_method': method,
                'extraction_status': 'ok' if normalized is not None else 'failed',
                'strict_json_contract_compliance': 'true' if strict_compliance else 'false',
                'extraction_error': '' if normalized is not None else item.get('extraction_error','no_supported_pattern'),
                'response_format_type': response_format
            })

    # write CSV
    csv_path = out / 'd6_existing_10_json_reextraction.csv'
    with csv_path.open('w', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else ['generation_item_id'])
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    # write analysis md
    md_path = out / 'd6_existing_10_json_reextraction_report.md'
    with md_path.open('w') as fh:
        fh.write('# D6 existing-10 JSON re-extraction report\n\n')
        fh.write(f'Total items processed: {total}\n\n')
        fh.write(f'Strict JSON with required "answer" key: {strict_json_count}\n\n')
        fh.write('Extraction method distribution:\n\n')
        dist = {}
        for r in rows:
            dist[r['extraction_method']] = dist.get(r['extraction_method'],0)+1
        for k,v in sorted(dist.items(), key=lambda x:-x[1]):
            fh.write(f'- {k}: {v}\n')
        fh.write('\nRecovered answers count: %d\n' % sum(1 for r in rows if r['extraction_status']=='ok'))

    # also write d6_json_output_analysis.csv and md (summary of fields)
    analysis_csv = out / 'd6_json_output_analysis.csv'
    with analysis_csv.open('w', newline='') as fh:
        writer = csv.writer(fh)
        writer.writerow(['generation_item_id','original_example_id','extracted_answer','extraction_method','extraction_status','strict_json_contract_compliance'])
        for r in rows:
            writer.writerow([r['generation_item_id'], r['original_example_id'], r['extracted_answer'], r['extraction_method'], r['extraction_status'], r['strict_json_contract_compliance']])

    analysis_md = out / 'd6_json_output_analysis.md'
    with analysis_md.open('w') as fh:
        fh.write('# D6 JSON output analysis\n\n')
        fh.write('See CSV for per-item results.\n')

    print('Wrote re-extraction outputs to', out)


if __name__ == '__main__':
    main()
