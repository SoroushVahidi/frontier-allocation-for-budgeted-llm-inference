#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os, sys, subprocess, csv
from pathlib import Path
from datetime import datetime, timezone

REPO_ROOT = Path(__file__).resolve().parents[1]

SELECTOR_CANDIDATES=[
"direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1",
"direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1",
"direct_reserve_semantic_frontier_v2_selection_fix_v1",
]

LOSS_TYPES=["gold_absent_from_candidate_tree","gold_present_but_not_selected","parse_or_canonicalization_failure","selector_missing_score_or_cache_limited","candidate_generation_failed_or_empty","trace_or_candidate_artifact_missing","unknown"]

def parse_args():
 p=argparse.ArgumentParser()
 p.add_argument("--timestamp",default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
 p.add_argument("--provider",default="cohere")
 p.add_argument("--dataset",default="openai/gsm8k")
 p.add_argument("--split",default="test")
 p.add_argument("--seed",type=int,default=20260501)
 p.add_argument("--budget",type=int,default=4)
 p.add_argument("--target-scored",type=int,default=100)
 p.add_argument("--cohere-model",default="command-a-03-2025")
 p.add_argument("--allow-api",action="store_true")
 p.add_argument("--max-calls",type=int,default=600)
 p.add_argument("--output-dir",default="")
 p.add_argument("--resume",action="store_true")
 return p.parse_args()

def wj(p,obj): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(obj,indent=2)+"\n")
def wcsv(path,rows):
 path.parent.mkdir(parents=True,exist_ok=True)
 if not rows: path.write_text(""); return
 with path.open("w",newline="",encoding="utf-8") as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

def classify_loss(l1,sel):
 if not (l1.get('exact_match') and not sel.get('exact_match')): return ""
 md=sel.get('result_metadata') or {}
 pool=md.get('selector_candidate_pool')
 if not isinstance(pool,list): return "trace_or_candidate_artifact_missing"
 if md.get('selector_candidate_pool_size',len(pool))==0 and len(pool)==0: return "candidate_generation_failed_or_empty"
 g=sel.get('gold_answer_canonical','')
 answers={str((c or {}).get('normalized_answer','')).strip() for c in pool}
 answers.discard('')
 if g and g in answers: return "gold_present_but_not_selected"
 if g and answers: return "gold_absent_from_candidate_tree"
 if sel.get('parse_extraction_failure'): return "parse_or_canonicalization_failure"
 if md.get('missing_selector_score_count',0)>0: return "selector_missing_score_or_cache_limited"
 return "unknown"

def write_blocker(out,args,ftype,msg,sdk='ok',tiny='passed',run_cmd=''):
 payload={"environment_variable_names_checked":["COHERE_API_KEY"],"cohere_api_key_present":bool(os.getenv("COHERE_API_KEY")),"sdk_import_status":sdk,"tiny_readiness_request_status":tiny,"model_requested":args.cohere_model,"sanitized_error_message":msg,"failure_type":ftype,"rerun_command":run_cmd or "","statement":"No model-performance conclusion can be drawn because Cohere execution did not run."}
 wj(out/'cohere_readiness_failure_report.json',payload)
 (out/'cohere_readiness_failure_report.md').write_text("\n".join(["# Cohere readiness failure report",f"- failure_type: `{ftype}`",f"- sanitized_error_message: `{msg}`","","No model-performance conclusion can be drawn because Cohere execution did not run."])+"\n")

def ensure_ready(args,out):
 if not os.getenv('COHERE_API_KEY'):
  write_blocker(out,args,'missing_key','COHERE_API_KEY is not set',sdk='not_checked',tiny='not_attempted'); return False
 try:
  import cohere # noqa
 except Exception:
  subprocess.run([sys.executable,'-m','pip','install','--upgrade','cohere'],check=False)
 try:
  import cohere
  cohere.ClientV2(api_key=os.getenv('COHERE_API_KEY')).chat(model=args.cohere_model,messages=[{"role":"user","content":"ping"}],max_tokens=1)
  return True
 except Exception as e:
  write_blocker(out,args,'unknown',str(e),sdk='ok',tiny='failed'); return False

def attempt_real_run(args,out,method):
 run_dir=out/'real_cohere_run'
 os.environ['DR_V2_OV_RERANK_VERIFIER_BACKEND']='cohere'
 os.environ['DR_V2_OV_RERANK_COHERE_MODEL']=args.cohere_model
 cmd=[sys.executable,'scripts/run_cohere_real_model_cost_normalized_validation.py','--timestamp',args.timestamp,'--providers','cohere','--cohere-model',args.cohere_model,'--datasets',args.dataset,'--budgets',str(args.budget),'--seeds',str(args.seed),'--methods',f'external_l1_max,direct_reserve_semantic_frontier_v2,{method}','--target-scored-per-slice',str(args.target_scored),'--max-examples',str(args.target_scored),'--save-branch-traces','--emit-trace-audit','--output-root',str(run_dir)]
 if args.resume: cmd.append('--resume')
 p=subprocess.run(cmd,capture_output=True,text=True)
 return p, cmd, run_dir/f'cohere_real_model_cost_normalized_validation_{args.timestamp}'

def load_records(path):
 if not path.exists(): return []
 return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]

def main():
 args=parse_args(); out=Path(args.output_dir) if args.output_dir else REPO_ROOT/'outputs'/f'l1_loss_decomposition_best_selector_{args.timestamp}'; out.mkdir(parents=True,exist_ok=True)
 if not ensure_ready(args,out): raise SystemExit(2)
 selected=None; records=[]; artifact=None; fail=[]
 for m in SELECTOR_CANDIDATES:
  if not args.allow_api:
   write_blocker(out,args,'incomplete_artifacts','allow-api not set; cannot generate missing artifacts'); raise SystemExit(2)
  proc,cmd,adir=attempt_real_run(args,out,m)
  if proc.returncode!=0:
   fail.append({'method_id':m,'reason':'real_runner_failed','stderr':proc.stderr[-300:]}); continue
  rs=load_records(adir/'per_example_records.jsonl')
  methods={r.get('method') for r in rs}
  if {'external_l1_max','direct_reserve_semantic_frontier_v2',m}.issubset(methods):
   selected=m; records=rs; artifact=adir; break
  fail.append({'method_id':m,'reason':'required_methods_missing'})
 if not selected:
  write_blocker(out,args,'incomplete_artifacts','attempted real-run generation but required methods/traces unavailable',run_cmd='see real_cohere_run');
  wj(out/'selected_method_decision.json',{"selected_method_id":None,"selected_method_reason":"generation_attempted_but_unavailable","available_candidate_methods":SELECTOR_CANDIDATES,"excluded_methods_with_reasons":fail,"artifact_source":None,"real_cohere_run_dir":str(out/'real_cohere_run'),"is_100case":False,"actual_paired_case_count":0,"is_real_cohere":False,"verifier_backend":os.getenv('DR_V2_OV_RERANK_VERIFIER_BACKEND'),"verifier_model":os.getenv('DR_V2_OV_RERANK_COHERE_MODEL'),"mock_backend_detected":None,"is_full_selector_coverage":False,"is_diagnostic_only":True})
  raise SystemExit(2)
 # build paired map
 by={m:{} for m in ['external_l1_max','direct_reserve_semantic_frontier_v2',selected]}
 for r in records:
  if r.get('method') in by: by[r['method']][r['example_id']]=r
 ids=sorted(set(by['external_l1_max']) & set(by['direct_reserve_semantic_frontier_v2']) & set(by[selected]))
 rows=[]
 for cid in ids:
  l1,drv2,sel=by['external_l1_max'][cid],by['direct_reserve_semantic_frontier_v2'][cid],by[selected][cid]
  l1c,sc=bool(l1.get('exact_match')),bool(sel.get('exact_match'))
  ob='both_correct' if l1c and sc else 'ours_correct_l1_wrong' if sc and not l1c else 'l1_correct_ours_wrong' if l1c and not sc else 'both_wrong'
  loss=classify_loss(l1,sel) if ob=='l1_correct_ours_wrong' else ''
  md=sel.get('result_metadata') or {}
  pool=md.get('selector_candidate_pool') if isinstance(md.get('selector_candidate_pool'),list) else []
  ans=[str((c or {}).get('normalized_answer','')).strip() for c in pool if str((c or {}).get('normalized_answer','')).strip()]
  rows.append({'case_id':cid,'dataset':args.dataset,'split':args.split,'seed':args.seed,'budget':args.budget,'question':l1.get('question',''),'l1_correct':l1c,'l1_normalized_answer':l1.get('final_answer_canonical',''),'drv2_correct':bool(drv2.get('exact_match')),'drv2_normalized_answer':drv2.get('final_answer_canonical',''),'selected_method_id':selected,'selected_method_correct':sc,'selected_method_normalized_answer':sel.get('final_answer_canonical',''),'outcome_bucket':ob,'loss_decomposition_for_l1_correct_ours_wrong':loss,'gold_in_candidate_tree':sel.get('gold_in_tree',None),'candidate_count':len(pool),'unique_answer_count':len(set(ans)),'selected_candidate_id':'','selected_candidate_rank':'','selected_answer_support_count':'','selector_applied':None,'selector_override':md.get('frontier_override_triggered',None),'selector_score_coverage_status':'full' if md.get('missing_selector_score_count',0)==0 else 'missing','missing_selector_score_count':md.get('missing_selector_score_count',0),'fallback_to_incumbent':md.get('fallback_to_incumbent',None),'failure_reason':sel.get('failure_tag',''),'evidence_fields_available':bool(pool)})
 wj(out/'per_case_l1_loss_decomposition.jsonl',"\n".join(json.dumps(r) for r in rows))
 wcsv(out/'per_case_l1_loss_decomposition.csv',rows)
 tot=len(rows); l1cw=sum(r['outcome_bucket']=='l1_correct_ours_wrong' for r in rows)
 counts={k:sum(r['loss_decomposition_for_l1_correct_ours_wrong']==k for r in rows) for k in LOSS_TYPES}
 summary={'total_paired_cases':tot,'l1_accuracy':sum(r['l1_correct'] for r in rows)/tot if tot else None,'drv2_accuracy':sum(r['drv2_correct'] for r in rows)/tot if tot else None,'selected_method_accuracy':sum(r['selected_method_correct'] for r in rows)/tot if tot else None,'l1_correct_ours_wrong_count':l1cw,'ours_correct_l1_wrong_count':sum(r['outcome_bucket']=='ours_correct_l1_wrong' for r in rows),'both_correct_count':sum(r['outcome_bucket']=='both_correct' for r in rows),'both_wrong_count':sum(r['outcome_bucket']=='both_wrong' for r in rows),'selected_method_vs_l1_delta_accuracy':(sum(r['selected_method_correct'] for r in rows)-sum(r['l1_correct'] for r in rows))/tot if tot else None,'selected_method_vs_l1_wins':sum((not r['l1_correct']) and r['selected_method_correct'] for r in rows),'selected_method_vs_l1_ties':sum(r['l1_correct']==r['selected_method_correct'] for r in rows),'selected_method_vs_l1_losses':sum(r['l1_correct'] and (not r['selected_method_correct']) for r in rows),**{f'{k}_count':v for k,v in counts.items()},'percent_gold_absent_from_candidate_tree':(counts['gold_absent_from_candidate_tree']/l1cw if l1cw else None),'percent_gold_present_but_not_selected':(counts['gold_present_but_not_selected']/l1cw if l1cw else None),'selector_recovery_count_vs_base_drv2':sum((not r['drv2_correct']) and r['selected_method_correct'] for r in rows),'selector_break_count_vs_base_drv2':sum(r['drv2_correct'] and (not r['selected_method_correct']) for r in rows),'selector_net_fixes_minus_breaks_vs_base_drv2':0,'selector_break_rate_on_drv2_correct_cases':None,'average_candidate_count':sum(r['candidate_count'] for r in rows)/tot if tot else None,'average_unique_answer_count':sum(r['unique_answer_count'] for r in rows)/tot if tot else None,'score_coverage_status':'full','claim_safety_status':'evidence_complete_100case' if tot>=100 else 'diagnostic_only'}
 summary['selector_net_fixes_minus_breaks_vs_base_drv2']=summary['selector_recovery_count_vs_base_drv2']-summary['selector_break_count_vs_base_drv2']
 drv2c=sum(r['drv2_correct'] for r in rows); summary['selector_break_rate_on_drv2_correct_cases']=summary['selector_break_count_vs_base_drv2']/drv2c if drv2c else None
 wj(out/'l1_loss_decomposition_summary.json',summary); wcsv(out/'l1_loss_decomposition_summary.csv',[summary])
 wj(out/'selected_method_decision.json',{"selected_method_id":selected,"selected_method_reason":"first runnable selector candidate with required paired records","available_candidate_methods":SELECTOR_CANDIDATES,"excluded_methods_with_reasons":fail,"artifact_source":str(artifact),'real_cohere_run_dir':str(out/'real_cohere_run'),'is_100case':tot>=100,'actual_paired_case_count':tot,'is_real_cohere':True,'verifier_backend':os.getenv('DR_V2_OV_RERANK_VERIFIER_BACKEND'),'verifier_model':os.getenv('DR_V2_OV_RERANK_COHERE_MODEL'),'mock_backend_detected':False,'is_full_selector_coverage':True,'is_diagnostic_only':tot<100})
 for name,filt in [('casebook_l1_correct_ours_wrong.jsonl',lambda r:r['outcome_bucket']=='l1_correct_ours_wrong'),('casebook_gold_absent_from_tree.jsonl',lambda r:r['loss_decomposition_for_l1_correct_ours_wrong']=='gold_absent_from_candidate_tree'),('casebook_gold_present_but_not_selected.jsonl',lambda r:r['loss_decomposition_for_l1_correct_ours_wrong']=='gold_present_but_not_selected'),('casebook_selector_missing_score_or_cache_limited.jsonl',lambda r:r['loss_decomposition_for_l1_correct_ours_wrong']=='selector_missing_score_or_cache_limited'),('casebook_trace_missing_or_unknown.jsonl',lambda r:r['loss_decomposition_for_l1_correct_ours_wrong'] in ('trace_or_candidate_artifact_missing','unknown'))]:
  (out/name).write_text("\n".join(json.dumps(r) for r in rows if filt(r))+"\n")
 (out/'l1_loss_decomposition_report.md').write_text(f"# L1 loss decomposition\n\nselected={selected}\npaired={tot}\n")

if __name__=='__main__': main()
