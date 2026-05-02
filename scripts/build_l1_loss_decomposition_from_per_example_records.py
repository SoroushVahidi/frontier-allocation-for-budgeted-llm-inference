#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, csv
from pathlib import Path

LANES=[
 "direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1",
 "direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1",
 "direct_reserve_semantic_frontier_v2_selection_fix_v1",
]
LOSS_TYPES=["gold_absent_from_candidate_tree","gold_present_but_not_selected","parse_or_canonicalization_failure","selector_missing_score_or_cache_limited","candidate_generation_failed_or_empty","trace_or_candidate_artifact_missing","unknown"]
METHOD_ALIASES={
 'l1_length_control_rl':'external_l1_max',
 'dr_v2':'direct_reserve_semantic_frontier_v2',
 'direct_reserve_semantic_frontier_v2_ov_rerank':'direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1',
 'ov_rerank_v1':'direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1',
 'prm_rerank_v1':'direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1',
 'selection_fix_v1':'direct_reserve_semantic_frontier_v2_selection_fix_v1',
}

def parse_args():
 p=argparse.ArgumentParser()
 p.add_argument('--input',required=True)
 p.add_argument('--output-dir',required=True)
 p.add_argument('--dataset',default='openai/gsm8k')
 p.add_argument('--split',default='test')
 p.add_argument('--seed',type=int,default=20260501)
 p.add_argument('--budget',type=int,default=4)
 p.add_argument('--target-paired-cases',type=int,default=100)
 p.add_argument('--no-gold-features-at-decision-time',action='store_true')
 return p.parse_args()

def wj(p,o): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(o,indent=2)+'\n')
def wjsonl(p,rows): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(''.join(json.dumps(r)+'\n' for r in rows))
def wcsv(p,rows):
 p.parent.mkdir(parents=True,exist_ok=True)
 if not rows: p.write_text(''); return
 with p.open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

def is_mock(rec):
 md=rec.get('result_metadata') or {}
 txt=json.dumps(md)
 return 'mock' in txt.lower()

def choose_lane(examples):
 for lane in LANES:
  ok=True
  for _,m in examples.items():
   if lane not in m: ok=False; break
   if lane==LANES[0] and is_mock(m[lane]): ok=False; break
  if ok: return lane
 return None

def classify(l1,sel):
 if not (l1.get('exact_match') and not sel.get('exact_match')): return ''
 md=sel.get('result_metadata') or {}
 pool=md.get('selector_candidate_pool')
 if not isinstance(pool,list): return 'trace_or_candidate_artifact_missing'
 if len(pool)==0: return 'candidate_generation_failed_or_empty'
 if sel.get('parse_extraction_failure'): return 'parse_or_canonicalization_failure'
 if md.get('missing_selector_score_count',0)>0: return 'selector_missing_score_or_cache_limited'
 g=sel.get('gold_answer_canonical','')
 ans={str((c or {}).get('normalized_answer','')).strip() for c in pool}; ans.discard('')
 if g and g in ans and sel.get('final_answer_canonical','')!=g: return 'gold_present_but_not_selected'
 if g and ans and g not in ans: return 'gold_absent_from_candidate_tree'
 return 'unknown'

def main():
 a=parse_args(); out=Path(a.output_dir)
 rec=[json.loads(l) for l in Path(a.input).read_text().splitlines() if l.strip()]
 by={}
 for r in rec:
  eid=r.get('case_id') or r.get('example_id') or r.get('question_id') or r.get('index') or r.get('dataset_row_index') or r.get('question_hash')
  m=METHOD_ALIASES.get(r.get('method'),r.get('method'))
  if not eid or not m: continue
  by.setdefault(eid,{})[m]=r
 complete_base={eid:m for eid,m in by.items() if 'external_l1_max' in m and 'direct_reserve_semantic_frontier_v2' in m}
 lane=choose_lane(complete_base)
 if lane is None:
  complete={}
 else:
  complete={eid:m for eid,m in complete_base.items() if lane in m and not (lane==LANES[0] and is_mock(m[lane]))}
 incomplete=[{'example_id':eid,'available_methods':sorted(list(m.keys()))} for eid,m in by.items() if eid not in complete]
 rows=[]
 for eid,m in sorted(complete.items()):
  l1,drv2,sel=m['external_l1_max'],m['direct_reserve_semantic_frontier_v2'],m[lane]
  l1c,sc=bool(l1.get('exact_match')),bool(sel.get('exact_match'))
  ob='both_correct' if l1c and sc else 'ours_correct_l1_wrong' if sc and not l1c else 'l1_correct_ours_wrong' if l1c and not sc else 'both_wrong'
  loss=classify(l1,sel) if ob=='l1_correct_ours_wrong' else ''
  md=sel.get('result_metadata') or {}
  pool=md.get('selector_candidate_pool') if isinstance(md.get('selector_candidate_pool'),list) else []
  ans=[str((c or {}).get('normalized_answer','')).strip() for c in pool if str((c or {}).get('normalized_answer','')).strip()]
  rows.append({'case_id':eid,'dataset':a.dataset,'split':a.split,'seed':a.seed,'budget':a.budget,'l1_correct':l1c,'drv2_correct':bool(drv2.get('exact_match')),'selected_method_id':lane,'selected_method_correct':sc,'outcome_bucket':ob,'loss_decomposition_for_l1_correct_ours_wrong':loss,'candidate_count':len(pool),'unique_answer_count':len(set(ans)),'missing_selector_score_count':md.get('missing_selector_score_count',0)})
 wjsonl(out/'per_case_l1_loss_decomposition.jsonl',rows); wcsv(out/'per_case_l1_loss_decomposition.csv',rows); wjsonl(out/'incomplete_cases.jsonl',incomplete)
 tot=len(rows); l1cw=sum(r['outcome_bucket']=='l1_correct_ours_wrong' for r in rows); counts={k:sum(r['loss_decomposition_for_l1_correct_ours_wrong']==k for r in rows) for k in LOSS_TYPES}
 claim='evidence_complete_100case' if tot==100 else 'diagnostic_partial' if tot>=25 else 'diagnostic_small_n' if tot>0 else 'incomplete_not_evidence'
 bott='inconclusive_due_to_small_n' if tot<25 else ('inconclusive_due_to_missing_traces' if counts['trace_or_candidate_artifact_missing']>0 else ('discovery_coverage_dominant' if counts['gold_absent_from_candidate_tree']>counts['gold_present_but_not_selected'] else 'selection_dominant' if counts['gold_present_but_not_selected']>counts['gold_absent_from_candidate_tree'] else 'mixed'))
 summary={'total_records_loaded':len(rec),'total_paired_cases':tot,'target_paired_cases':a.target_paired_cases,'selected_method_id':lane,'selected_method_reason':'highest-priority complete non-mock lane' if lane else 'no complete selected lane','l1_accuracy':sum(r['l1_correct'] for r in rows)/tot if tot else None,'drv2_accuracy':sum(r['drv2_correct'] for r in rows)/tot if tot else None,'selected_method_accuracy':sum(r['selected_method_correct'] for r in rows)/tot if tot else None,'l1_correct_ours_wrong_count':l1cw,'ours_correct_l1_wrong_count':sum(r['outcome_bucket']=='ours_correct_l1_wrong' for r in rows),'both_correct_count':sum(r['outcome_bucket']=='both_correct' for r in rows),'both_wrong_count':sum(r['outcome_bucket']=='both_wrong' for r in rows),'selected_method_vs_l1_delta_accuracy':(sum(r['selected_method_correct'] for r in rows)-sum(r['l1_correct'] for r in rows))/tot if tot else None,'selected_method_vs_l1_wins':sum((not r['l1_correct']) and r['selected_method_correct'] for r in rows),'selected_method_vs_l1_ties':sum(r['l1_correct']==r['selected_method_correct'] for r in rows),'selected_method_vs_l1_losses':sum(r['l1_correct'] and (not r['selected_method_correct']) for r in rows),**{f'{k}_count':v for k,v in counts.items()},'percent_gold_absent_from_candidate_tree':counts['gold_absent_from_candidate_tree']/l1cw if l1cw else None,'percent_gold_present_but_not_selected':counts['gold_present_but_not_selected']/l1cw if l1cw else None,'selector_recovery_count_vs_base_drv2':sum((not r['drv2_correct']) and r['selected_method_correct'] for r in rows),'selector_break_count_vs_base_drv2':sum(r['drv2_correct'] and (not r['selected_method_correct']) for r in rows),'selector_net_fixes_minus_breaks_vs_base_drv2':0,'selector_break_rate_on_drv2_correct_cases':None,'average_candidate_count':sum(r['candidate_count'] for r in rows)/tot if tot else None,'average_unique_answer_count':sum(r['unique_answer_count'] for r in rows)/tot if tot else None,'score_coverage_status':'full' if rows and all(r['missing_selector_score_count']==0 for r in rows) else ('none' if not rows else 'partial'),'claim_safety_status':claim,'bottleneck_conclusion':bott,'incomplete_case_count':len(incomplete)}
 summary['selector_net_fixes_minus_breaks_vs_base_drv2']=summary['selector_recovery_count_vs_base_drv2']-summary['selector_break_count_vs_base_drv2']
 d=sum(r['drv2_correct'] for r in rows); summary['selector_break_rate_on_drv2_correct_cases']=summary['selector_break_count_vs_base_drv2']/d if d else None
 wj(out/'l1_loss_decomposition_summary.json',summary); wcsv(out/'l1_loss_decomposition_summary.csv',[summary])
 wj(out/'selected_method_decision.json',{'selected_method_id':lane,'selected_method_reason':summary['selected_method_reason'],'priority_order':LANES,'total_complete_base_cases':len(complete_base),'total_paired_cases':tot})
 for name,f in [('casebook_l1_correct_ours_wrong.jsonl',lambda r:r['outcome_bucket']=='l1_correct_ours_wrong'),('casebook_gold_absent_from_tree.jsonl',lambda r:r['loss_decomposition_for_l1_correct_ours_wrong']=='gold_absent_from_candidate_tree'),('casebook_gold_present_but_not_selected.jsonl',lambda r:r['loss_decomposition_for_l1_correct_ours_wrong']=='gold_present_but_not_selected'),('casebook_selector_missing_score_or_cache_limited.jsonl',lambda r:r['loss_decomposition_for_l1_correct_ours_wrong']=='selector_missing_score_or_cache_limited'),('casebook_trace_missing_or_unknown.jsonl',lambda r:r['loss_decomposition_for_l1_correct_ours_wrong'] in ('trace_or_candidate_artifact_missing','unknown'))]:
  wjsonl(out/name,[r for r in rows if f(r)])
 (out/'l1_loss_decomposition_report.md').write_text(f"# Salvaged L1 loss decomposition\n\nselected_method={lane}\npaired_cases={tot}\nincomplete_cases={len(incomplete)}\nclaim_safety_status={claim}\n")
 print(json.dumps({'total_records_loaded':len(rec),'complete_paired_cases':tot,'incomplete_cases':len(incomplete),'selected_method_lane':lane,'claim_safety_status':claim,'bottleneck_conclusion':bott},indent=2))

if __name__=='__main__': main()
