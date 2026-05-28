#!/usr/bin/env python3
"""
v4: Deep recursive extractor. Searches JSON/dict-like structures recursively, inspects all string fields for boxed answers, final-answer phrases, numeric tokens, and returns the best candidate.
Records answer_key_used and confidence hints.
"""
import sys, json, re, ast
from pathlib import Path
import csv

ALIAS_KEYS = ['answer','final_answer','finalAnswer','final','result']

def clean_token(t):
    if t is None:
        return None
    s = str(t).strip()
    s = re.sub(r"\\\\?boxed\{([^}]+)\}", r"\1", s)
    s = s.replace('$','')
    s = re.sub(r"^```+|```+$", '', s)
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        s = s[1:-1].strip()
    # prefer numeric token
    m = re.search(r"[-+]?\d+\.?\d*(?:e[-+]?\d+)?", s, flags=re.I)
    if m:
        return m.group(0)
    s = ' '.join(s.split())
    s = s.rstrip('.;:,')
    return s.strip()


def find_json(candidate_text):
    m = re.search(r"\{.*\}", candidate_text, flags=re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def recursive_search(obj):
    # returns list of candidate (value, reason)
    candidates = []
    if isinstance(obj, dict):
        for k,v in obj.items():
            if isinstance(v, (dict,list)):
                candidates += [(c, f"nested:{k}" ) for c in recursive_search(v)]
            else:
                # if key is alias
                if k in ALIAS_KEYS and v not in (None, ''):
                    candidates.append((v, f"key:{k}"))
                # search for boxed
                if isinstance(v, str):
                    m = re.search(r"\\boxed\{([^}]+)\}", v)
                    if m:
                        candidates.append((m.group(1), f"boxed_in_field:{k}"))
                    m2 = re.search(r"final\s*answer\s*(?:is|:)?\s*([^\n\.]+)", v, flags=re.I)
                    if m2:
                        candidates.append((m2.group(1), f"final_phrase_in_field:{k}"))
                    # numeric token
                    m3 = re.search(r"[-+]?\d+\.?\d*(?:e[-+]?\d+)?", v)
                    if m3:
                        candidates.append((m3.group(0), f"numeric_in_field:{k}"))
    elif isinstance(obj, list):
        for i,el in enumerate(obj):
            if isinstance(el, (dict,list)):
                candidates += [(c, f"nested_list:{i}") for c in recursive_search(el)]
            else:
                if isinstance(el, str):
                    m = re.search(r"\\boxed\{([^}]+)\}", el)
                    if m:
                        candidates.append((m.group(1), f"boxed_in_list:{i}"))
                    m2 = re.search(r"final\s*answer\s*(?:is|:)?\s*([^\n\.]+)", el, flags=re.I)
                    if m2:
                        candidates.append((m2.group(1), f"final_phrase_in_list:{i}"))
                    m3 = re.search(r"[-+]?\d+\.?\d*(?:e[-+]?\d+)?", el)
                    if m3:
                        candidates.append((m3.group(0), f"numeric_in_list:{i}"))
    return candidates


def extract_from_text(text):
    # try direct json
    obj = find_json(text)
    if obj:
        candidates = recursive_search(obj)
        if candidates:
            return candidates
    # try fenced json
    fences = re.findall(r"```(?:json)?\n(.*?)```", text, flags=re.S|re.I)
    for block in fences:
        obj = find_json(block)
        if obj:
            candidates = recursive_search(obj)
            if candidates:
                return candidates
    # boxed anywhere
    m = re.findall(r"\\boxed\{([^}]+)\}", text)
    if m:
        return [(v, 'boxed_anywhere') for v in m]
    # final phrase anywhere
    m2 = re.findall(r"final\s*answer\s*(?:is|:)?\s*([^\n\.]+)", text, flags=re.I)
    if m2:
        return [(v, 'final_phrase_anywhere') for v in m2]
    # last number
    m3 = re.findall(r"[-+]?\d+\.?\d*(?:e[-+]?\d+)?", text)
    if m3:
        return [(m3[-1], 'last_numeric_anywhere')]
    return []


def main():
    if len(sys.argv)<3:
        print('usage: v4 <jsonl> <outdir>')
        return
    src = Path(sys.argv[1])
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    rows=[]
    total=0
    recovered=0
    key_dist={}
    with src.open() as fh:
        for line in fh:
            line=line.strip()
            if not line: continue
            total+=1
            try:
                item=json.loads(line)
            except Exception:
                continue
            resp=item.get('response_text','')
            candidates=extract_from_text(resp)
            chosen=None
            chosen_method='none'
            answer_key_used=''
            if candidates:
                # prefer key:answer or key in aliases
                for val,reason in candidates:
                    if 'key:answer' in reason or reason.startswith('key:answer'):
                        chosen=clean_token(val); chosen_method='key:answer'; answer_key_used='answer'; break
                if not chosen:
                    # prefer any key aliases
                    for val,reason in candidates:
                        if reason.startswith('key:'):
                            chosen=clean_token(val); chosen_method=reason; answer_key_used=reason.split(':',1)[1]; break
                if not chosen:
                    # boxed preference
                    for val,reason in candidates:
                        if 'boxed' in reason:
                            chosen=clean_token(val); chosen_method=reason; answer_key_used='boxed'; break
                if not chosen:
                    chosen=clean_token(candidates[0][0]); chosen_method=candidates[0][1]; answer_key_used=chosen_method
            if chosen:
                recovered+=1
            rows.append({
                'generation_item_id': item.get('generation_item_id'),
                'original_example_id': item.get('original_example_id'),
                'extracted_answer': chosen or '',
                'extraction_method': chosen_method,
                'extraction_status': 'ok' if chosen else 'failed',
                'answer_key_used': answer_key_used
            })
    csvp=out/'d6_loop_reextraction_after_patch_v4.csv'
    with csvp.open('w',newline='') as fh:
        w=csv.DictWriter(fh, fieldnames=rows[0].keys() if rows else ['generation_item_id'])
        w.writeheader()
        for r in rows: w.writerow(r)
    mdp=out/'d6_loop_reextraction_after_patch_report_v4.md'
    with mdp.open('w') as fh:
        fh.write('# D6 loop re-extraction after patch v4\n\n')
        fh.write(f'Total items: {total}\n')
        fh.write(f'Recovered answers: {recovered}\n')
    print('Wrote v4 re-extraction to', out)

if __name__=='__main__':
    main()
