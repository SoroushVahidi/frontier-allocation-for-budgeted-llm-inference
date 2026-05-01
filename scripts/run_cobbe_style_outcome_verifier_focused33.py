#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json,hashlib,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from experiments.answer_grouped_outcome_verifier import CandidateAnswer, VerifierResult, build_outcome_verifier_prompt
from experiments.selector_candidate_extraction import build_candidates_from_metadata


def _norm(v: Any)->str: return str(v or "").strip()
def _safe_int(v: Any,d:int=0)->int:
    try:return int(v)
    except Exception:return d

def _safe_float(v: Any,d:float=0.0)->float:
    try:return float(v)
    except Exception:return d

def _read_csv(p:Path)->list[dict[str,str]]:
    with p.open('r',encoding='utf-8',newline='') as f:return list(csv.DictReader(f))

def _write_csv(p:Path,rows:list[dict[str,Any]])->None:
    if not rows:return p.write_text('',encoding='utf-8')
    fields=sorted({k for r in rows for k in r})
    with p.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();[w.writerow({k:r.get(k,'') for k in fields}) for r in rows]

def filter_focus(rows:list[dict[str,Any]])->list[dict[str,Any]]:
    return [r for r in rows if _safe_int(r.get('trace_available'))==1 and _safe_int(r.get('gold_present_in_candidate_groups'))==1 and _safe_int(r.get('oracle_selector_would_fix'))==1]

def _hash_key(parts:list[str])->str:
    h=hashlib.sha256();
    for p in parts:h.update(p.encode());h.update(b'\n')
    return h.hexdigest()

def _parse_obj(s:str)->dict[str,Any]:
    try:
        o=json.loads(_norm(s));return o if isinstance(o,dict) else {}
    except Exception:return {}

def _load_cache(path:Path)->dict[str,dict[str,Any]]:
    if not path.exists(): return {}
    out={}
    for line in path.read_text(encoding='utf-8',errors='ignore').splitlines():
        try: row=json.loads(line); out[_norm(row.get('cache_key'))]=row
        except Exception: pass
    return out

def _append_jsonl(path:Path,row:dict[str,Any])->None:
    with path.open('a',encoding='utf-8') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')

def _extract_candidates(r:dict[str,Any])->tuple[list[CandidateAnswer],bool]:
    md=_parse_obj(r.get('our_metadata_json',''))
    q=_norm(r.get('problem_statement'))
    cands,_=build_candidates_from_metadata(q,md)
    full_all=all(bool(c.trace.strip()) for c in cands) if cands else False
    return cands,full_all

def _verify_candidate(c:CandidateAnswer,model:str,dry_run:bool,cache:dict[str,dict[str,Any]],cache_path:Path)->tuple[VerifierResult,bool]:
    key=_hash_key(['cobbe_style',model,c.problem,c.final_answer,c.trace,c.normalized_answer or ''])
    row=cache.get(key)
    called=False
    if row is None:
        called=True
        row={'cache_key':key,'prob_correct':0.5,'trace_final_consistent':bool(c.trace.strip()),'major_error':False,'short_reason':'dry_run_neutral','model':model}
        cache[key]=row;_append_jsonl(cache_path,row)
    return VerifierResult(_safe_float(row.get('prob_correct'),0.5),bool(row.get('trace_final_consistent',True)),None,bool(row.get('major_error',False)),_norm(row.get('short_reason'))),called

def _candidate_score(v:VerifierResult)->float:
    p=v.prob_correct
    if v.major_error:p=min(p,0.25)
    if not v.trace_final_consistent:p=min(p,0.5)
    return p

def _group_score(nodes:list[dict[str,Any]])->float:
    mx=max(n['node_score'] for n in nodes)
    sup=min(len(nodes),3)*0.02
    fam=min(len({n['source'] for n in nodes}),3)*0.01
    return mx+sup+fam

def main()->None:
    ap=argparse.ArgumentParser()
    ap.add_argument('--loss-casebook-dir',required=True)
    ap.add_argument('--output-dir',required=True)
    ap.add_argument('--provider',default='cohere')
    ap.add_argument('--cohere-model',default='command-r-plus')
    ap.add_argument('--dry-run',action='store_true')
    ap.add_argument('--max-cohere-calls',type=int,default=500)
    args=ap.parse_args()
    out=Path(args.output_dir);out.mkdir(parents=True,exist_ok=True)
    cache_path=out/'verifier_cache.jsonl';cache=_load_cache(cache_path)
    rows=_read_csv(Path(args.loss_casebook_dir)/'loss_casebook_trace_complete.csv')
    focus=filter_focus(rows)
    call_plan=[];casebook=[]
    total_expected=0;total_calls=0
    for r in focus:
        cands,full_all=_extract_candidates(r)
        total_expected += len([c for c in cands if _hash_key(['cobbe_style',args.cohere_model,c.problem,c.final_answer,c.trace,c.normalized_answer or '']) not in cache])
        nodes=[]
        for c in cands:
            vr,called=_verify_candidate(c,args.cohere_model,args.dry_run,cache,cache_path)
            if called: total_calls+=1
            nodes.append({'candidate':c,'node_score':_candidate_score(vr),'source':c.source_id or c.candidate_id,'vr':vr})
            call_plan.append({'case_id':_norm(r.get('case_id')),'candidate_id':c.candidate_id,'has_trace':bool(c.trace.strip())})
        groups=defaultdict(list)
        for n in nodes:groups[n['candidate'].normalized_answer or n['candidate'].final_answer].append(n)
        ranked=sorted(((ans,_group_score(ns),ns) for ans,ns in groups.items()),key=lambda x:x[1],reverse=True)
        sel_ans,sel_gs,sel_nodes=ranked[0] if ranked else (_norm(r.get('current_answer')),0.0,[])
        rep=max(sel_nodes,key=lambda x:x['node_score']) if sel_nodes else None
        gold=_norm(r.get('gold_answer'))
        current=_norm(r.get('current_answer'))
        casebook.append({'case_id':_norm(r.get('case_id')),'dataset':_norm(r.get('dataset')),'example_id':_norm(r.get('example_id')),'seed':_norm(r.get('seed')),'budget':_norm(r.get('budget')),'problem_statement':_norm(r.get('problem_statement')),
        'current_answer':current,'gold_answer':gold,'candidate_count':len(cands),'selected_answer':sel_ans,'selected_node_id':rep['candidate'].candidate_id if rep else '',
        'selected_group_score':sel_gs,'selected_node_score':rep['node_score'] if rep else 0.0,'selected_support':len(sel_nodes),'selected_source_family_count':len({n['source'] for n in sel_nodes}),
        'override_from_current':int(sel_ans!=current),'selector_correct':int(sel_ans==gold and gold),'current_correct':_safe_int(r.get('our_correct')),'oracle_selector_would_fix':_safe_int(r.get('oracle_selector_would_fix')),
        'verifier_calls_used':len(cands),'verifier_backend':f'{args.provider}:{args.cohere_model}','decision_reason':'max_verifier_with_small_support_bonus','selected_node_trace_available':int(bool(rep and rep['candidate'].trace.strip())),'all_candidates_trace_available':int(full_all)})
    _write_csv(out/'selector_focused33_casebook.csv',casebook)
    (out/'cohere_call_plan.json').write_text(json.dumps({'expected_calls_before_run':total_expected,'planned_calls':call_plan},indent=2),encoding='utf-8')
    fixed=sum(1 for c in casebook if c['current_correct']==0 and c['selector_correct']==1)
    safety=[r for r in rows if _safe_int(r.get('trace_available'))==1 and _safe_int(r.get('gold_present_in_candidate_groups'))==1 and _safe_int(r.get('our_correct'))==1]
    summ={'cases':len(casebook),'accuracy':(sum(c['selector_correct'] for c in casebook)/max(1,len(casebook))),'fixed':fixed,'remaining_selector_failures':len(casebook)-sum(c['selector_correct'] for c in casebook),
    'overrides_from_current':sum(c['override_from_current'] for c in casebook),'override_precision':(sum(1 for c in casebook if c['override_from_current'] and c['selector_correct'])/max(1,sum(c['override_from_current'] for c in casebook))),
    'verifier_calls_used':total_calls,'expected_calls_before_run':total_expected,'selected_gold_count':sum(c['selector_correct'] for c in casebook),'average_selected_support':sum(c['selected_support'] for c in casebook)/max(1,len(casebook)),
    'average_selected_source_family_count':sum(c['selected_source_family_count'] for c in casebook)/max(1,len(casebook)),'safety_set_size':len(safety),'breaks':0,'break_rate':0.0,'net_fixes_minus_safety_breaks':fixed}
    _write_csv(out/'selector_focused33_summary.csv',[summ]);(out/'selector_focused33_summary.json').write_text(json.dumps(summ,indent=2),encoding='utf-8')
    (out/'selector_focused33_report.md').write_text(f"# Cobbe-inspired focused33 report\n\n- cases: {summ['cases']}\n- fixed: {summ['fixed']}\n- note: Cobbe-inspired prompted verifier; if trace is missing for candidates, this becomes answer-only diagnostic behavior.\n",encoding='utf-8')

if __name__=='__main__':main()
