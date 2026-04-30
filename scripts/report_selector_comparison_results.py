#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
from collections import defaultdict, Counter
from statistics import mean

METHODS=["external_l1_max","direct_reserve_semantic_frontier_v2","direct_reserve_semantic_frontier_v2_selection_fix_v1","direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1","direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1"]

def load_rows(p:Path):
 rows=[]
 for ln in p.read_text(encoding='utf-8').splitlines():
  if ln.strip(): rows.append(json.loads(ln))
 return rows

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--artifact-dir',required=True);ap.add_argument('--timestamp',required=True);a=ap.parse_args()
 ad=Path(a.artifact_dir)
 rows=load_rows(ad/'per_example_records.jsonl')
 by=defaultdict(list)
 for r in rows:
  if r.get('method') in METHODS and r.get('status')=='scored': by[r['method']].append(r)
 lines=[f"# Selector Comparison 30-case Cohere ({a.timestamp})","",f"Artifact: `{ad}`","","## Accuracy table","","|method|scored|correct|accuracy|mean_tokens|mean_cost_usd|mean_latency_s|","|---|---:|---:|---:|---:|---:|---:|"]
 acc={}
 for m in METHODS:
  rs=by[m];sc=len(rs);corr=sum(1 for r in rs if bool(r.get('exact_match',False)));ac=(corr/sc if sc else 0.0);acc[m]=ac
  toks=[float(r.get('total_tokens',0) or 0) for r in rs];cost=[float(r.get('estimated_cost_usd',0) or 0) for r in rs];lat=[float(r.get('latency_seconds',0) or 0) for r in rs]
  lines.append(f"|{m}|{sc}|{corr}|{ac:.3f}|{(mean(toks) if toks else 0):.1f}|{(mean(cost) if cost else 0):.6f}|{(mean(lat) if lat else 0):.3f}|")

 # paired
 key=lambda r:(r.get('example_id'),r.get('dataset'),r.get('seed'),r.get('budget'))
 idx={m:{key(r):r for r in by[m]} for m in METHODS}
 pairs=[('OV vs DRv2','direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1','direct_reserve_semantic_frontier_v2'),('PRM vs DRv2','direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1','direct_reserve_semantic_frontier_v2'),('OV vs selection_fix','direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1','direct_reserve_semantic_frontier_v2_selection_fix_v1'),('PRM vs selection_fix','direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1','direct_reserve_semantic_frontier_v2_selection_fix_v1'),('OV vs L1','direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1','external_l1_max'),('PRM vs L1','direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1','external_l1_max'),('DRv2 vs L1','direct_reserve_semantic_frontier_v2','external_l1_max')]
 lines += ["","## Paired comparisons","","|pair|N|W|T|L|delta_acc|","|---|---:|---:|---:|---:|---:|"]
 for name,a1,b1 in pairs:
  ks=set(idx[a1]).intersection(idx[b1]);w=t=l=0
  for k in ks:
   ea=bool(idx[a1][k].get('exact_match',False));eb=bool(idx[b1][k].get('exact_match',False))
   if ea and not eb:w+=1
   elif eb and not ea:l+=1
   else:t+=1
  da=(w-l)/len(ks) if ks else 0
  lines.append(f"|{name}|{len(ks)}|{w}|{t}|{l}|{da:.3f}|")

 # present but not selected using selector rows
 dr=idx['direct_reserve_semantic_frontier_v2']; ov=idx['direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1']; prm=idx['direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1']
 wrong=[k for k,v in dr.items() if not bool(v.get('exact_match',False)) and k in ov and k in prm]
 gold_pool=sum(int((ov[k].get('result_metadata',{}) or {}).get('ov_rerank_gold_present_in_candidates',0) or 0) for k in wrong)
 rec_ov=sum(int((ov[k].get('result_metadata',{}) or {}).get('ov_rerank_recovered_present_not_selected',0) or 0) for k in wrong)
 rec_prm=sum(int((prm[k].get('result_metadata',{}) or {}).get('prm_recovered_present_not_selected',0) or 0) for k in wrong)
 remain=max(0,gold_pool-rec_ov-rec_prm)
 correct_keys=[k for k,v in dr.items() if bool(v.get('exact_match',False)) and k in ov and k in prm]
 reg_ov=sum(1 for k in correct_keys if not bool(ov[k].get('exact_match',False)))
 reg_prm=sum(1 for k in correct_keys if not bool(prm[k].get('exact_match',False)))
 lines += ["","## Present-but-not-selected analysis",f"- DR-v2 wrong cases (paired with OV+PRM): {len(wrong)}",f"- Gold present in OV selector candidates: {gold_pool}",f"- Recovered by OV: {rec_ov}",f"- Recovered by PRM: {rec_prm}",f"- Remaining missed among gold-present: {remain}",f"- Regressions when DR-v2 originally correct: OV={reg_ov}, PRM={reg_prm}"]

 # selector surface
 sel=[r for r in rows if r.get('method') in ('direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1','direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1') and r.get('status')=='scored']
 cc=Counter();ag=Counter();src=Counter();fb=Counter();ovap=Counter();prmap=Counter();vc=Counter();back=Counter();parse=Counter()
 for r in sel:
  md=(r.get('result_metadata') or {})
  cc[int(md.get('candidate_count',0) or 0)] +=1; ag[int(md.get('answer_group_count',0) or 0)] +=1
  for s in md.get('candidate_extraction_sources',[]) if isinstance(md.get('candidate_extraction_sources',[]),list) else []: src[str(s)]+=1
  fb[str(md.get('fallback_reason','') or '')]+=1
  ovap[bool(md.get('ov_rerank_applied',False))]+=1; prmap[bool(md.get('prm_rerank_applied',False))]+=1
  vc[int(md.get('verifier_calls',md.get('prm_step_verifier_calls',0)) or 0)] +=1
  if 'verifier_backend' in md: back[str(md.get('verifier_backend'))]+=1
  if 'prm_step_verifier_backend' in md: back[str(md.get('prm_step_verifier_backend'))]+=1
  for v in (md.get('ov_rerank_verifier_results',{}) or {}).values():
   if isinstance(v,dict) and 'parse' in str(v.get('short_reason','')).lower(): parse['ov_parse_or_json']+=1
  for arr in (md.get('prm_step_scores',{}) or {}).values():
   if isinstance(arr,list):
    for x in arr:
      if isinstance(x,dict) and bool(x.get('parse_fallback',False)): parse['prm_parse_fallback']+=1
 lines += ["","## Selector surface (OV+PRM rows)",f"- selector rows analyzed: {len(sel)}",f"- candidate_count distribution: {dict(cc)}",f"- answer_group_count distribution: {dict(ag)}",f"- extraction-source distribution: {dict(src)}",f"- fallback-reason distribution: {dict(fb)}",f"- ov_rerank_applied counts: {dict(ovap)}",f"- prm_rerank_applied counts: {dict(prmap)}",f"- verifier-call distribution: {dict(vc)}",f"- backend values: {dict(back)}",f"- parse-fallback/error counts: {dict(parse)}"]

 complete=all(len(by[m])>=30 for m in METHODS)
 if not complete: cls='incomplete_not_claim_safe'
 else:
  best=max(acc['direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1'],acc['direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1'])
  dracc=acc['direct_reserve_semantic_frontier_v2'];l1=acc['external_l1_max']
  if best>dracc and best>l1: cls='diagnostic_strong_positive'
  elif best>dracc: cls='diagnostic_positive'
  else: cls='diagnostic_negative'
 lines += ["","## Claim safety",f"- classification: **{cls}**", "- This is a 30-case diagnostic only; not final paper evidence."]
 out=Path('docs/SELECTOR_COMPARISON_30CASE_COHERE_20260429.md');out.write_text('\n'.join(lines),encoding='utf-8');print(out)

if __name__=='__main__': main()
