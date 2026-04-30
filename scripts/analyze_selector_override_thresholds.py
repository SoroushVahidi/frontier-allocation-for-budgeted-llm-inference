#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json
from pathlib import Path
from itertools import product

MARGINS=[0.0,0.05,0.10,0.15,0.20,0.30]
MINS=[0.0,0.5,0.75,1.0,1.25,1.5]
PARSE=[0,1,None]

def nrm(x): return str(x or '').strip().lower()

def main():
 p=argparse.ArgumentParser();p.add_argument('--artifact-dir',required=True);p.add_argument('--timestamp',required=True);a=p.parse_args();ad=Path(a.artifact_dir)
 rows=[json.loads(l) for l in (ad/'per_example_records.jsonl').read_text().splitlines() if l.strip()]
 idx={}
 for r in rows:
  k=(r.get('example_id'),r.get('dataset'),r.get('seed'),r.get('budget'),r.get('method'))
  idx[k]=r
 dr={k[:-1]:v for k,v in idx.items() if k[-1]=='direct_reserve_semantic_frontier_v2'}
 prm={k[:-1]:v for k,v in idx.items() if k[-1]=='direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1'}
 out=[]
 base_correct=sum(1 for k,v in dr.items() if v.get('exact_match'))
 for m,s,mp in product(MARGINS,MINS,PARSE):
  corr=0;over=0;rec=0;reg=0;keep=0
  for k,d in dr.items():
   p=prm.get(k)
   if not p: continue
   md=p.get('result_metadata') or {}
   groups=md.get('prm_group_scores',[]) if isinstance(md.get('prm_group_scores',[]),list) else []
   gmap={nrm(g.get('normalized_answer')):float(g.get('group_score',0.0) or 0.0) for g in groups if isinstance(g,dict)}
   sel=nrm(md.get('selected_normalized_answer') or md.get('prm_selected_answer'))
   inc=nrm(md.get('prm_original_dr_v2_selected_answer') or d.get('final_answer_canonical') or d.get('final_answer_raw'))
   sscore=gmap.get(sel,0.0);iscore=gmap.get(inc,0.0)
   top2=sorted([float(g.get('group_score',0) or 0) for g in groups if isinstance(g,dict)],reverse=True)
   top2_margin=(top2[0]-top2[1]) if len(top2)>1 else (top2[0] if top2 else 0.0)
   parse_count=sum(1 for arr in (md.get('prm_step_scores',{}) or {}).values() for x in (arr if isinstance(arr,list) else []) if isinstance(x,dict) and x.get('parse_fallback'))
   would=sel and sel!=inc
   gate=bool(would and (sscore-iscore)>=m and sscore>=s and top2_margin>=m and (mp is None or parse_count<=mp))
   pred = p.get('final_answer_canonical') if gate else d.get('final_answer_canonical')
   gold=nrm(d.get('gold_answer_canonical') or d.get('gold_answer'))
   ok=nrm(pred)==gold
   corr+=int(ok)
   over+=int(gate)
   if gate and (not d.get('exact_match')) and ok: rec+=1
   if gate and d.get('exact_match') and not ok: reg+=1
   if not gate: keep+=1
  out.append({'margin_threshold':m,'min_selected_score':s,'max_parse_fallback':('unlimited' if mp is None else mp),'simulated_correct':corr,'simulated_accuracy':corr/max(1,len(dr)),'base_dr_v2_correct':base_correct,'delta_vs_dr_v2':corr-base_correct,'overrides':over,'recoveries':rec,'regressions':reg,'kept_incumbent':keep})
 csvp=ad/'selector_override_threshold_sweep.csv'
 with csvp.open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=list(out[0].keys()));w.writeheader();w.writerows(out)
 best=max(out,key=lambda r:(r['simulated_correct'],-r['regressions']))
 mdp=Path('docs/SELECTOR_OVERRIDE_THRESHOLD_ANALYSIS_20260429.md')
 mdp.write_text('# Selector Override Threshold Analysis\n\nBest setting: '+json.dumps(best)+'\n\nAny improvement over DR-v2: '+str(any(r['delta_vs_dr_v2']>0 for r in out))+'\n',encoding='utf-8')
 print(csvp);print(mdp)

if __name__=='__main__': main()
