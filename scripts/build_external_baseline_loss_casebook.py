#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json,re
from pathlib import Path
from collections import defaultdict,Counter

INTERNAL=['direct_reserve_semantic_frontier_v2','direct_reserve_semantic_frontier_v2_selection_fix_v1','direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1','direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1']

def nrm(x): return str(x or '').strip().lower()
def edit(a,b):
 a=nrm(a);b=nrm(b)
 if not a and not b:return 0.0
 dp=[[0]*(len(b)+1) for _ in range(len(a)+1)]
 for i in range(len(a)+1):dp[i][0]=i
 for j in range(len(b)+1):dp[0][j]=j
 for i in range(1,len(a)+1):
  for j in range(1,len(b)+1): dp[i][j]=min(dp[i-1][j]+1,dp[i][j-1]+1,dp[i-1][j-1]+(a[i-1]!=b[j-1]))
 return dp[-1][-1]/max(1,max(len(a),len(b)))

def to_num(s):
 m=re.search(r'-?\d+(?:\.\d+)?',str(s or ''))
 return float(m.group()) if m else None

def main():
 p=argparse.ArgumentParser();p.add_argument('--artifact-dir',required=True);p.add_argument('--timestamp',required=True);a=p.parse_args();ad=Path(a.artifact_dir)
 rows=[json.loads(l) for l in (ad/'per_example_records.jsonl').read_text().splitlines() if l.strip()]
 by=defaultdict(dict)
 for r in rows:
  k=(r.get('example_id'),r.get('dataset'),r.get('seed'),r.get('budget'));by[k][r.get('method')]=r
 out=[]
 for k,m in by.items():
  l1=m.get('external_l1_max')
  if not l1 or not l1.get('exact_match'): continue
  for im in INTERNAL:
   r=m.get(im)
   if not r or r.get('exact_match'): continue
   md=r.get('result_metadata') or {}
   cands=[]
   if isinstance(md.get('selector_candidate_pool',[]),list): cands=md.get('selector_candidate_pool',[])
   cand_ans=[str(x.get('predicted_answer','')) for x in cands if isinstance(x,dict)]
   gold=nrm(r.get('gold_answer_canonical') or r.get('gold_answer'))
   present=int(any(nrm(x)==gold for x in cand_ans))
   parse_fb=sum(1 for arr in (md.get('prm_step_scores',{}) or {}).values() for x in (arr if isinstance(arr,list) else []) if isinstance(x,dict) and x.get('parse_fallback'))
   loss='unknown_missing_metadata'
   if present: loss='present_but_not_selected'
   elif cand_ans: loss='absent_from_tree'
   elif md.get('parse_extraction_failure'): loss='canonicalization_or_extraction_failure'
   ed=edit(r.get('final_answer_canonical') or r.get('final_answer_raw'), gold)
   numg=to_num(gold);nums=[to_num(x) for x in cand_ans if to_num(x) is not None];numf=to_num(r.get('final_answer_canonical') or r.get('final_answer_raw'))
   mind=min([edit(x,gold) for x in cand_ans],default=1.0)
   if loss=='absent_from_tree' and nums and numg is not None and min(abs(x-numg) for x in nums)<=max(1.0,0.1*abs(numg)): dist='near_numeric'
   elif loss=='absent_from_tree' and mind<=0.25: dist='near_textual'
   elif loss=='absent_from_tree' and int(md.get('answer_group_count',0) or 0)<=1: dist='collapsed_wrong_answer_group'
   elif loss=='absent_from_tree' and int(md.get('answer_group_count',0) or 0)>1: dist='diverse_but_no_gold'
   elif loss=='absent_from_tree': dist='unknown'
   else: dist='n/a'
   out.append({'example_id':k[0],'dataset':k[1],'seed':k[2],'budget':k[3],'question':r.get('question',''),'gold_answer_raw':r.get('gold_answer'),'gold_answer_canonical':r.get('gold_answer_canonical'),'external_l1_max_final_answer_raw':l1.get('final_answer_raw'),'external_l1_max_final_answer_canonical':l1.get('final_answer_canonical'),'external_l1_max_correct':l1.get('exact_match'),'internal_method_name':im,'internal_final_answer_raw':r.get('final_answer_raw'),'internal_final_answer_canonical':r.get('final_answer_canonical'),'internal_correct':r.get('exact_match'),'gold_present_in_candidate_pool':present,'loss_type':loss,'distance_category':dist,'candidate_count':md.get('candidate_count'),'answer_group_count':md.get('answer_group_count'),'candidate_extraction_sources':json.dumps(md.get('candidate_extraction_sources',[])),'fallback_reason':md.get('fallback_reason',''),'rerank_applied':md.get('ov_rerank_applied',md.get('prm_rerank_applied',False)),'verifier_backend':md.get('verifier_backend',md.get('prm_step_verifier_backend','')),'verifier_calls':md.get('verifier_calls',md.get('prm_step_verifier_calls',0)),'parse_fallback_count':parse_fb,'candidate_answers_raw':json.dumps(cand_ans),'candidate_answers_canonical':json.dumps([nrm(x) for x in cand_ans]),'candidate_group_scores':json.dumps(md.get('prm_group_scores',md.get('ov_rerank_group_scores',[]))),'candidate_trace_scores':json.dumps(md.get('prm_trace_scores',{})),'selected_candidate_id':md.get('selected_candidate_id',''),'selected_group_score':md.get('selected_group_score',None),'top2_margin':None,'incumbent_group_score':None,'reranker_selected_answer':md.get('prm_selected_answer',md.get('ov_rerank_selected_answer','')),'original_dr_v2_answer':md.get('prm_original_dr_v2_selected_answer',md.get('ov_rerank_original_dr_v2_selected_answer','')),'recovered_present_not_selected':md.get('prm_recovered_present_not_selected',md.get('ov_rerank_recovered_present_not_selected',0)),'regression_from_original_dr_v2':None,'normalized_edit_distance_final_to_gold':ed,'min_candidate_edit_distance_to_gold':mind,'numeric_abs_error_final': (None if (numf is None or numg is None) else abs(numf-numg))})
 csvp=ad/'external_l1_loss_casebook.csv';jsonlp=ad/'external_l1_loss_casebook.jsonl'
 if out:
  with csvp.open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=list(out[0].keys()));w.writeheader();w.writerows(out)
 with jsonlp.open('w',encoding='utf-8') as f:
  for r in out:f.write(json.dumps(r,ensure_ascii=False)+'\n')
 c_method=Counter(r['internal_method_name'] for r in out);c_loss=Counter((r['internal_method_name'],r['loss_type']) for r in out);c_dist=Counter((r['internal_method_name'],r['distance_category']) for r in out if r['loss_type']=='absent_from_tree')
 md=Path(f'docs/EXTERNAL_L1_LOSS_CASEBOOK_{a.timestamp}.md')
 rep='\n'.join([f"- {r['example_id']} | {r['internal_method_name']} | {r['loss_type']} | {r['distance_category']}" for r in out[:8]])
 md.write_text(f"# External L1 Loss Casebook\n\nTotal paired examples: {len(by)}\n\nL1 beats counts per method: {dict(c_method)}\n\nLoss taxonomy counts: {dict(c_loss)}\n\nDistance categories (absent_from_tree): {dict(c_dist)}\n\nRepresentative failures:\n{rep}\n",encoding='utf-8')
 print(csvp);print(jsonlp);print(md)

if __name__=='__main__': main()
