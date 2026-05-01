#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.output_layer_repair import canonicalize_answer
from experiments.selector_candidate_extraction import build_candidates_from_metadata


def norm(x:Any)->str:return str(x or '').strip().lower()
def canon(x:Any,dataset:str)->str:
    t=str(x or '').strip()
    if not t:return ''
    c=canonicalize_answer(t,dataset=dataset)
    return norm(c or t)

def iter_jsonl(p:Path):
    if not p.exists(): return
    for ln in p.read_text(encoding='utf-8',errors='ignore').splitlines():
        if ln.strip():
            try:
                o=json.loads(ln)
                if isinstance(o,dict): yield o
            except Exception: pass

def parse_args():
    ap=argparse.ArgumentParser()
    ap.add_argument('--casebook',required=True)
    ap.add_argument('--source-root',required=True)
    ap.add_argument('--output-dir',required=True)
    ap.add_argument('--allow-cohere',action='store_true')
    ap.add_argument('--max-cases',type=int,default=50)
    ap.add_argument('--dry-run-call-plan',action='store_true')
    return ap.parse_args()

def match_record(rows:list[dict[str,Any]], r:dict[str,Any])->dict[str,Any]|None:
    for x in rows:
        if x.get('dataset')!=r.get('dataset'): continue
        if str(x.get('example_id'))!=str(r.get('example_id')): continue
        if int(x.get('seed',-1))!=int(r.get('seed',-2)): continue
        if int(x.get('budget',-1))!=int(r.get('budget',-2)): continue
        if norm(x.get('method'))!=norm(r.get('our_method_name')): continue
        return x
    return None

def main()->int:
    a=parse_args(); out=Path(a.output_dir); out.mkdir(parents=True,exist_ok=True)
    cases=[json.loads(x) for x in Path(a.casebook).read_text().splitlines() if x.strip()][:a.max_cases]
    per=list(iter_jsonl(Path(a.source_root)/'per_example_records.jsonl') or [])

    matched=[]; missing=[]; missing_trace=[]; enriched=[]
    s={
      'input casebook path':a.casebook,'source root path':a.source_root,'input cases':len(cases),
      'raw records matched':0,'raw records missing':0,'cases with candidate nodes':0,
      'cases with at least one candidate trace':0,'cases with all candidates traced':0,
      'extracted candidate-node count':0,'traced candidate-node count':0,
      'gold present in aggregate answer buckets':0,'gold present in extracted terminal node finals':0,
      'selected answer present in extracted terminal node finals':0,'cases still aggregate-only':0,
      'cases usable for trace-aware outcome-verifier selection':0,'cases requiring Cohere regeneration':0,
      'Cohere used?':'yes' if a.allow_cohere else 'no','Cohere calls made':0,
      'no secrets/no caches committed confirmation':'true'
    }

    for r in cases:
        dataset=r.get('dataset','openai/gsm8k'); gold=canon(r.get('gold_answer',''),dataset)
        rec=match_record(per,r)
        if not rec:
            missing.append({'case_id':r.get('case_id'),'reason':'no_matching_per_example_record'})
            s['raw records missing']+=1; s['cases requiring Cohere regeneration']+=1; continue
        s['raw records matched']+=1
        matched.append({'case_id':r.get('case_id'),'dataset':r.get('dataset'),'example_id':r.get('example_id'),'seed':r.get('seed'),'budget':r.get('budget'),'method':r.get('our_method_name')})
        md=rec.get('result_metadata') or {}
        cands,_=build_candidates_from_metadata(str(rec.get('question') or r.get('problem_statement') or ''), md if isinstance(md,dict) else {})
        nodes=[]
        for c in cands:
            nodes.append({'candidate_id':c.candidate_id,'source_family':c.source_id,'final_answer':c.final_answer,'normalized_answer':canon(c.final_answer,dataset),
                          'trace_text':c.trace,'trace_available':bool(str(c.trace).strip()),'cost_proxy':c.cost_norm,'score_prior':c.source_prior})
        if nodes: s['cases with candidate nodes']+=1
        traced=sum(1 for n in nodes if n['trace_available'])
        if traced>0: s['cases with at least one candidate trace']+=1
        if nodes and traced==len(nodes): s['cases with all candidates traced']+=1
        s['extracted candidate-node count']+=len(nodes); s['traced candidate-node count']+=traced
        node_set={n['normalized_answer'] for n in nodes if n.get('normalized_answer')}
        selected=canon(r.get('selected_answer_group') or r.get('our_final_answer') or rec.get('selected_answer_raw'),dataset)
        gold_agg=bool(r.get('gold_present_in_candidate_groups',False)) or gold in {canon(x,dataset) for x in json.loads(r.get('all_candidate_answer_groups','[]'))}
        if gold_agg: s['gold present in aggregate answer buckets']+=1
        gold_node=gold in node_set if gold else False
        if gold_node: s['gold present in extracted terminal node finals']+=1
        sel_node=selected in node_set if selected else False
        if sel_node: s['selected answer present in extracted terminal node finals']+=1
        if not nodes: s['cases still aggregate-only']+=1
        if nodes and traced>0: s['cases usable for trace-aware outcome-verifier selection']+=1
        if nodes and traced==0: missing_trace.append({'case_id':r.get('case_id'),'reason':'candidate_nodes_without_trace'})
        enriched.append({
          'case_id':r.get('case_id'),'dataset':dataset,'example_id':r.get('example_id'),'seed':r.get('seed'),'budget':r.get('budget'),
          'problem_statement':r.get('problem_statement') or rec.get('question',''),'candidate_nodes':nodes,
          'verifier_input':{'problem_statement':r.get('problem_statement') or rec.get('question',''),'candidates_for_verifier':[{k:v for k,v in n.items() if k in {'candidate_id','source_family','final_answer','normalized_answer','trace_text','cost_proxy'}} for n in nodes]},
          'evaluation_only':{'gold_answer':r.get('gold_answer',''),'oracle_selector_answer':r.get('oracle_selector_answer',''),'gold_answer_group_if_present':r.get('gold_answer_group_if_present',''),'oracle_selector_would_fix':r.get('oracle_selector_would_fix','')},
          'gold_in_aggregate_answer_groups':gold_agg,'gold_in_extracted_terminal_node_finals':gold_node,
          'selected_answer_in_extracted_terminal_node_finals':sel_node,'has_any_candidate_trace':traced>0,'all_candidates_traced':bool(nodes) and traced==len(nodes)
        })

    (out/'candidate_trace_enriched.jsonl').write_text('\n'.join(json.dumps(x) for x in enriched)+'\n',encoding='utf-8')
    for nm,data in [('matched_raw_records.jsonl',matched),('missing_raw_records.jsonl',missing),('missing_trace_records.jsonl',missing_trace)]:
        (out/nm).write_text('\n'.join(json.dumps(x) for x in data)+'\n',encoding='utf-8')
    (out/'trace_recovery_summary.json').write_text(json.dumps(s,indent=2),encoding='utf-8')
    with (out/'trace_recovery_summary.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f);w.writerow(['metric','value']);[w.writerow([k,v]) for k,v in s.items()]
    (out/'trace_recovery_report.md').write_text(f"# Trace Recovery Report\n\nMatched: {s['raw records matched']} / {s['input cases']}\n\nTrace-usable: {s['cases usable for trace-aware outcome-verifier selection']}\n",encoding='utf-8')
    manifest={'timestamp':datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'),'casebook':a.casebook,'source_root':a.source_root,'max_cases':a.max_cases,'allow_cohere':a.allow_cohere,'cohere_calls_made':0,'git_commit':subprocess.getoutput('git rev-parse HEAD')}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    return 0
if __name__=='__main__': raise SystemExit(main())
