from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Any

NUM_RE=re.compile(r'-?\d+(?:\.\d+)?')
WEEKDAY_RE=re.compile(r'\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b',re.I)
CATEG_RE=re.compile(r'\b(weekday|day of the week|month|yes or no)\b',re.I)
MORE_RE=re.compile(r'how\s+much\s+more',re.I)
FIRST_PRICE_RE=re.compile(r'\$\s*(\d+(?:\.\d+)?)')
TAIL_EQ_RE=re.compile(r'=\s*\$?\s*(-?[\d,]+(?:\.\d+)?)\s*(?:$|\n|\.|\))',re.I)
COUNT_RE=re.compile(r'\b(how many|number of)\b',re.I)
RATE_RE=re.compile(r'\b(per|each|rate)\b',re.I)
TOTAL_RE=re.compile(r'\b(total|in all)\b',re.I)
REMAIN_RE=re.compile(r'\b(remaining|left)\b',re.I)


def _to_float(s:str|None):
    if s is None: return None
    try:return float(str(s).replace(',','').strip())
    except: return None

def _extract_final_num(ans:str)->float|None:
    m=list(NUM_RE.finditer(ans or ''))
    return _to_float(m[-1].group(0)) if m else None

def compute_candidate_consistency_flags(question:str, trace:str, final_answer:str)->dict[str,bool]:
    q=(question or '').lower(); t=(trace or ''); a=(final_answer or '').strip().lower()
    anum=_extract_final_num(a)
    last_eq=TAIL_EQ_RE.findall(t)
    last_eq_num=_to_float(last_eq[-1].replace(',','')) if last_eq else None
    first_price=_to_float(FIRST_PRICE_RE.findall(question)[0]) if FIRST_PRICE_RE.findall(question) else None
    flags={
      'categorical_numeric_mismatch': bool((WEEKDAY_RE.search(q) or CATEG_RE.search(q)) and anum is not None),
      'how_much_more_echo_original_price': bool(MORE_RE.search(q) and first_price is not None and anum is not None and abs(anum-first_price)<1e-9),
      'last_equation_disagrees_with_final': bool(last_eq_num is not None and anum is not None and abs(last_eq_num-anum)>1e-9),
      'numeric_type_mismatch': bool((NUM_RE.search(q) is not None) and (anum is None)),
      'non_integer_count': bool(COUNT_RE.search(q) and anum is not None and abs(anum-round(anum))>1e-9),
      'negative_impossible': bool(anum is not None and anum<0 and ('temperature' not in q)),
      'remaining_total_conflict': bool(REMAIN_RE.search(q) and TOTAL_RE.search(q) and anum is not None and anum==0),
      'rate_vs_total_conflict': bool(RATE_RE.search(q) and TOTAL_RE.search(q) and anum is not None and anum<1),
      'intermediate_echo_risk': bool(anum is not None and str(int(anum) if anum.is_integer() else anum) in (question or '')),
    }
    return flags


def compute_unified_confidence_error(question:str, trace:str, final_answer:str, support_count:int=1, ov_score:float|None=None, prm_score:float|None=None)->dict[str,float]:
    flags=compute_candidate_consistency_flags(question,trace,final_answer)
    err=float(sum(flags.values()))
    model=0.0
    if ov_score is not None: model+=max(min(float(ov_score),1.0),0.0)
    if prm_score is not None: model+=max(min(float(prm_score),1.0),0.0)
    if ov_score is not None and prm_score is not None: model/=2.0
    elif ov_score is None and prm_score is None: model=0.5
    support=min(1.0, max(0.0, support_count/3.0))
    confidence=max(0.0, min(1.0, 0.55*model + 0.25*support + 0.20*(1.0-min(err/5.0,1.0))))
    return {'unified_error_score':err,'unified_confidence_score':confidence,'hybrid_selector_score':confidence-0.15*err}


def build_group_feature_rows(question:str, candidate_groups:list[dict[str,Any]])->list[dict[str,Any]]:
    out=[]
    for g in candidate_groups:
        flags=compute_candidate_consistency_flags(question,str(g.get('trace','')),str(g.get('final_answer','')))
        scores=compute_unified_confidence_error(question,str(g.get('trace','')),str(g.get('final_answer','')),int(g.get('support_count',1)),g.get('ov_score'),g.get('prm_score'))
        row=dict(g)
        row['consistency_flags']=flags
        row.update(scores)
        out.append(row)
    return out
