#!/usr/bin/env python3
from __future__ import annotations

import argparse,csv,json,re,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.output_layer_repair import canonicalize_answer
from experiments.selector_candidate_extraction import build_candidates_from_metadata
from scripts.enrich_focused33_with_candidate_traces import _extract_trace


def _norm(x: Any)->str:return str(x or '').strip().lower()

def canon(x: Any,dataset:str)->str:
    t=str(x or '').strip()
    if not t:return ''
    c=canonicalize_answer(t,dataset=dataset)
    return _norm(c or t)

def iter_jsonl(p:Path):
    if not p.exists(): return
    for ln in p.read_text(encoding='utf-8',errors='ignore').splitlines():
        if not ln.strip(): continue
        try:
            o=json.loads(ln)
            if isinstance(o,dict): yield o
        except Exception: pass

def find_files(roots:list[Path], names:set[str])->list[Path]:
    out=[]
    for r in roots:
        if not r.exists(): continue
        for p in r.rglob('*'):
            if p.is_file() and p.name in names: out.append(p)
    return out

def parse_args():
    ap=argparse.ArgumentParser()
    ap.add_argument('--roots',nargs='+',default=['outputs','archive','logs'])
    ap.add_argument('--output-dir',default=None)
    ap.add_argument('--our-method-regex',default=r'(dr[-_ ]?v2|direct_reserve_semantic_frontier_v2)')
    ap.add_argument('--external-method-regex',default=r'external_l1_max')
    ap.add_argument('--max-cases',type=int,default=None)
    ap.add_argument('--dry-run',action='store_true')
    ap.add_argument('--include-current-correct-risk-cases',action='store_true')
    ap.add_argument('--no-paid-api',action='store_true',default=True)
    return ap.parse_args()

def main()->int:
    a=parse_args();ts=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out=Path(a.output_dir or f'outputs/selector_evidence_package_{ts}')
    out.mkdir(parents=True,exist_ok=True)
    roots=[Path(x) for x in a.roots]
    missing=[];used=[]
    pair_rows=[]
    for p in find_files(roots,{'loss_casebook_trace_complete.csv','loss_casebook_200.csv'}):
        used.append(str(p))
        with p.open() as f:
            for r in csv.DictReader(f):
                our=r.get('our_method_name','')
                ext=r.get('external_method_name','') or r.get('best_external_method_name','')
                if re.search(a.our_method_regex,our,re.I) and re.search(a.external_method_regex,ext,re.I):
                    pair_rows.append((r,p))
    per_example=find_files(roots,{'per_example_records.jsonl'})
    fbs=find_files(roots,{'final_branch_states.jsonl'})
    if not per_example: missing.append({'artifact':'per_example_records.jsonl','reason':'not_found'})
    if not fbs: missing.append({'artifact':'final_branch_states.jsonl','reason':'not_found'})

    present=[];absent=[];risk=[];enriched=[]
    counts={k:0 for k in ['total paired rows scanned','our-wrong / external-correct rows','trace-complete external-loss rows','present-not-selected aggregate rows','absent-from-tree rows','rows matched to raw records','cases with candidate nodes','cases with at least one candidate trace','cases with all extracted candidates traced','extracted candidate-node count','traced candidate-node count','gold present in aggregate answer buckets','gold present in extracted terminal node finals','current-correct cases available for break-risk testing']}
    counts['total paired rows scanned']=len(pair_rows);counts['trace-complete external-loss rows']=len(pair_rows)

    for r,src in pair_rows[: a.max_cases or len(pair_rows)]:
        dataset=r.get('dataset','openai/gsm8k');gold=canon(r.get('gold_answer',''),dataset)
        groups=[]
        try: groups=json.loads(r.get('all_candidate_answer_groups','[]'))
        except Exception: groups=[]
        gset={canon(x,dataset) for x in groups if str(x).strip()}
        gold_agg=gold in gset if gold else False
        if gold_agg: counts['gold present in aggregate answer buckets']+=1
        our_correct=str(r.get('our_correct','0')) in ('1','true','True')
        ext_correct=str(r.get('external_correct',r.get('external_l1_max_correct',r.get('best_external_correct','0')))) in ('1','true','True')
        if (not our_correct) and ext_correct:
            counts['our-wrong / external-correct rows']+=1
        md={}
        if r.get('our_metadata_json'):
            try: md=json.loads(r['our_metadata_json'])
            except Exception: pass
        cands,_=build_candidates_from_metadata(r.get('problem_statement',''),md if isinstance(md,dict) else {})
        nodes=[{'candidate_id':c.candidate_id,'final_answer':c.final_answer,'trace_text':c.trace,'trace_available':bool(c.trace)} for c in cands]
        traced=sum(1 for n in nodes if n['trace_available'])
        gold_node=gold in {canon(n['final_answer'],dataset) for n in nodes if n.get('final_answer')}
        if gold_node: counts['gold present in extracted terminal node finals']+=1
        has_trace=traced>0
        all_traced=bool(nodes) and traced==len(nodes)
        case={**r,'source_artifact_path':str(src),'evaluation_only':{'gold_answer':r.get('gold_answer','')},'gold_present_in_candidate_groups':gold_agg,
              'gold_in_extracted_terminal_node_finals':gold_node,'candidate_nodes':nodes,'has_any_candidate_trace':has_trace,'all_candidates_traced':all_traced}
        if nodes: counts['cases with candidate nodes']+=1
        if has_trace: counts['cases with at least one candidate trace']+=1
        if all_traced: counts['cases with all extracted candidates traced']+=1
        counts['extracted candidate-node count']+=len(nodes);counts['traced candidate-node count']+=traced
        if nodes: counts['rows matched to raw records']+=1
        if (not our_correct) and ext_correct:
            if gold_agg:
                present.append(case);counts['present-not-selected aggregate rows']+=1
                if not gold_node: pass
                enriched.append({'problem_statement':r.get('problem_statement',''),'candidate_nodes':nodes,
                    'verifier_input':{'problem_statement':r.get('problem_statement',''),'candidate_nodes':[{'candidate_id':n['candidate_id'],'trace_text':n['trace_text'],'final_answer':n['final_answer']} for n in nodes]},
                    'evaluation_only':{'gold_answer':r.get('gold_answer',''),'our_correct':our_correct,'external_correct':ext_correct},
                    'gold_in_aggregate_answer_groups':gold_agg,'gold_in_extracted_terminal_node_finals':gold_node,'has_any_candidate_trace':has_trace,'all_candidates_traced':all_traced})
            else:
                absent.append(case);counts['absent-from-tree rows']+=1
        if a.include_current_correct_risk_cases and our_correct and len(gset)>=2:
            risk.append(case);counts['current-correct cases available for break-risk testing']+=1

    def wjson(p,obj): p.write_text(json.dumps(obj,indent=2),encoding='utf-8')
    wjson(out/'manifest.json',{'command':' '.join(__import__('sys').argv),'timestamp':ts,'roots_scanned':[str(x) for x in roots],'method_filters':{'our':a.our_method_regex,'external':a.external_method_regex},'no_paid_api':True,'source_artifacts_used':used,'git_commit':subprocess.getoutput('git rev-parse HEAD')})
    for nm,rows in [('present_not_selected_casebook',present),('absent_from_tree_casebook',absent),('current_correct_risk_casebook',risk)]:
        with (out/f'{nm}.jsonl').open('w',encoding='utf-8') as f:
            for o in rows: f.write(json.dumps(o)+'\n')
        if rows:
            ks=sorted({k for o in rows for k in o.keys() if k!='candidate_nodes'})
            with (out/f'{nm}.csv').open('w',newline='',encoding='utf-8') as f:
                w=csv.DictWriter(f,fieldnames=ks);w.writeheader();
                for o in rows: w.writerow({k:(json.dumps(o[k]) if isinstance(o.get(k),(dict,list)) else o.get(k,'')) for k in ks})
    with (out/'candidate_trace_enriched.jsonl').open('w',encoding='utf-8') as f:
        for o in enriched: f.write(json.dumps(o)+'\n')
    wjson(out/'selector_evidence_summary.json',counts)
    with (out/'selector_evidence_summary.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f);w.writerow(['metric','value']);[w.writerow([k,v]) for k,v in counts.items()]
    (out/'selector_evidence_report.md').write_text(f"# Selector Evidence Report\n\nUsable present-not-selected cases: {len(present)}\n\nAggregate-only: {sum(1 for x in present if not x.get('gold_in_extracted_terminal_node_finals'))}\n\nTrace-preserved: {sum(1 for x in present if x.get('gold_in_extracted_terminal_node_finals'))}\n",encoding='utf-8')
    wjson(out/'missing_artifacts.json',missing)
    with (out/'missing_artifacts.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=['artifact','reason']);w.writeheader();w.writerows(missing)
    return 0

if __name__=='__main__': raise SystemExit(main())
