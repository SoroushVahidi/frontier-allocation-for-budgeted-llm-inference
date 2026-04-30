#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
import statistics
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from experiments.selector_error_features import build_group_feature_rows
from scripts.selector_reconstruction import support_only_with_guard_v1_choice

L1='external_l1_max'; DR='direct_reserve_semantic_frontier_v2'; OV='direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1'; PRM='direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1'

def n(x: Any)->str: return str(x or '').strip().lower()

def resolve(p:str)->Path:
    q=Path(p)
    return q if q.is_file() else q/'per_example_records.jsonl'

def best(groups:list[dict[str,Any]], key):
    if not groups: return ''
    return max(groups,key=key)['normalized_answer']

def load_cases(rows:list[dict[str,Any]]):
    idx=defaultdict(dict)
    for r in rows: idx[(r.get('example_id'),r.get('dataset'),r.get('seed'),r.get('budget'))][r.get('method')]=r
    out=[]
    for k,mm in idx.items():
        if DR not in mm or L1 not in mm: continue
        dr=mm[DR]; l1=mm[L1]; gold=n(dr.get('gold_answer_canonical') or dr.get('gold_answer') or l1.get('gold_answer_canonical') or l1.get('gold_answer'))
        md=dr.get('result_metadata') or {}
        pool=(md.get('selector_candidate_pool') or md.get('final_branch_states') or dr.get('final_nodes') or [])
        pool=[x for x in pool if isinstance(x,dict)]
        groups_map={}
        for r in pool:
            ans=n(r.get('predicted_answer') or r.get('final_answer') or r.get('answer'))
            if not ans: continue
            g=groups_map.setdefault(ans,{'normalized_answer':ans,'support_count':0,'trace':str(r.get('trace','') or ''),'final_answer':ans,'source_family':str(r.get('source_family') or r.get('source') or ''),'ov_score':None,'prm_score':None})
            g['support_count']+=1
        groups=list(groups_map.values())
        ov=mm.get(OV); prm=mm.get(PRM)
        if ov:
            cs=((ov.get('result_metadata') or {}).get('ov_rerank_candidate_scores') or {})
            for g in groups:
                hits=[v for v in cs.values() if n((v or {}).get('normalized_answer'))==g['normalized_answer']]
                if hits: g['ov_score']=float((hits[0] or {}).get('candidate_score',0.0))
        if prm:
            ps=((prm.get('result_metadata') or {}).get('prm_group_scores') or [])
            for g in groups:
                hits=[v for v in ps if n((v or {}).get('normalized_answer'))==g['normalized_answer']]
                if hits: g['prm_score']=float((hits[0] or {}).get('group_score',0.0))
        feats=build_group_feature_rows(str(dr.get('question') or dr.get('question_raw') or ''),groups)
        out.append({'key':k,'gold':gold,'question':str(dr.get('question') or dr.get('question_raw') or ''),'groups':feats,'dr_pred':n(dr.get('final_answer_canonical') or dr.get('final_answer_raw') or dr.get('selected_answer_canonical') or dr.get('selected_answer_raw')),'l1_pred':n(l1.get('final_answer_canonical') or l1.get('final_answer_raw') or l1.get('selected_answer_canonical') or l1.get('selected_answer_raw'))})
    return out

def select(rule:str,case:dict[str,Any])->str:
    gs=case['groups']; gold=case['gold']; dr=case['dr_pred']
    if rule=='actual_current_selector': return dr
    if rule=='oracle_selector': return gold if any(g['normalized_answer']==gold for g in gs) else dr
    if rule=='support_only': return best(gs,lambda g:(g.get('support_count',0),g['normalized_answer']))
    if rule=='support_only_with_guard_v1':
        chosen,_=support_only_with_guard_v1_choice(dr,gs)
        return chosen
    if rule=='consistency_penalized': return best(gs,lambda g:g.get('support_count',0)-0.6*sum(g['consistency_flags'].values()))
    if rule=='unified_confidence_error': return best(gs,lambda g:g.get('unified_confidence_score',0)-0.2*g.get('unified_error_score',0))
    if rule=='hybrid_support_confidence_consistency': return best(gs,lambda g:0.6*g.get('support_count',0)+0.8*g.get('unified_confidence_score',0)-0.5*g.get('unified_error_score',0))
    if rule=='source_aware_direct_reserve_prior':
        top=best(gs,lambda g:(g.get('support_count',0),g.get('unified_confidence_score',0)))
        direct=[g for g in gs if 'direct' in str(g.get('source_family','')).lower()]
        if not direct: return top
        d=max(direct,key=lambda g:(g.get('support_count',0),g.get('unified_confidence_score',0)))
        tg=next((g for g in gs if g['normalized_answer']==top),None)
        if tg and d['normalized_answer']!=top and (tg.get('support_count',0)>=d.get('support_count',0)+1 or tg.get('unified_confidence_score',0)>=d.get('unified_confidence_score',0)+0.08):
            return top
        return d['normalized_answer']
    if rule=='ov_score_selector':
        have=[g for g in gs if g.get('ov_score') is not None]
        return best(have,lambda g:g.get('ov_score',0.0)) if have else dr
    if rule=='prm_score_selector':
        have=[g for g in gs if g.get('prm_score') is not None]
        return best(have,lambda g:g.get('prm_score',0.0)) if have else dr
    if rule=='hybrid_support_ov_prm':
        have=[g for g in gs if g.get('ov_score') is not None or g.get('prm_score') is not None]
        return best(have if have else gs,lambda g:0.6*g.get('support_count',0)+0.4*float(g.get('ov_score') or 0)+0.4*float(g.get('prm_score') or 0)-0.2*g.get('unified_error_score',0))
    return dr

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--artifact-dir',required=True); ap.add_argument('--output-dir',required=True); a=ap.parse_args()
    rows=[json.loads(x) for x in resolve(a.artifact_dir).read_text().splitlines() if x.strip()]
    cases=load_cases(rows)
    rules=['actual_current_selector','support_only','support_only_with_guard_v1','consistency_penalized','unified_confidence_error','hybrid_support_confidence_consistency','source_aware_direct_reserve_prior','oracle_selector']
    ov_avail=any(any(g.get('ov_score') is not None for g in c['groups']) for c in cases)
    prm_avail=any(any(g.get('prm_score') is not None for g in c['groups']) for c in cases)
    skipped=[]
    if ov_avail: rules.append('ov_score_selector')
    else: skipped.append('ov_score_selector: no ov scores found')
    if prm_avail: rules.append('prm_score_selector')
    else: skipped.append('prm_score_selector: no prm scores found')
    if ov_avail or prm_avail: rules.append('hybrid_support_ov_prm')
    else: skipped.append('hybrid_support_ov_prm: no ov/prm scores found')

    l1_acc=sum(int(c['l1_pred']==c['gold']) for c in cases)/max(1,len(cases))
    dr_acc=sum(int(c['dr_pred']==c['gold']) for c in cases)/max(1,len(cases))
    per=[]; casebook=[]
    for r in rules:
        preds=[select(r,c) for c in cases]
        correct=[int(p==c['gold']) for p,c in zip(preds,cases)]
        acc=sum(correct)/max(1,len(cases))
        changes=0; fixes=0; breaks=0; recovered=0; remain_sel=0; remain_cov=0
        gp_idx=[i for i,c in enumerate(cases) if any(g['normalized_answer']==c['gold'] for g in c['groups'])]
        ga_idx=[i for i,c in enumerate(cases) if i not in gp_idx]
        for i,c in enumerate(cases):
            old_ok=int(c['dr_pred']==c['gold']); new_ok=correct[i]
            if preds[i]!=c['dr_pred']:
                changes+=1; fixes+=int(old_ok==0 and new_ok==1); breaks+=int(old_ok==1 and new_ok==0)
                casebook.append({'selector':r,'example_id':c['key'][0],'question':c['question'],'gold':c['gold'],'l1_answer':c['l1_pred'],'l1_correct':int(c['l1_pred']==c['gold']),'dr_answer':c['dr_pred'],'dr_correct':old_ok,'new_answer':preds[i],'new_correct':new_ok,'candidate_groups':json.dumps([g['normalized_answer'] for g in c['groups']]),'support_counts':json.dumps({g['normalized_answer']:g['support_count'] for g in c['groups']}),'source_labels':json.dumps({g['normalized_answer']:g.get('source_family','') for g in c['groups']}),'consistency_flags':json.dumps({g['normalized_answer']:g.get('consistency_flags',{}) for g in c['groups']}),'score_components':json.dumps({g['normalized_answer']:{'support':g.get('support_count',0),'conf':g.get('unified_confidence_score',0),'err':g.get('unified_error_score',0),'ov':g.get('ov_score'),'prm':g.get('prm_score')} for g in c['groups']}),'change_type':'fix' if old_ok==0 and new_ok==1 else ('break' if old_ok==1 and new_ok==0 else 'other')})
            if c['l1_pred']==c['gold'] and old_ok==0 and new_ok==1: recovered+=1
            if any(g['normalized_answer']==c['gold'] for g in c['groups']) and new_ok==0: remain_sel+=1
            if not any(g['normalized_answer']==c['gold'] for g in c['groups']) and new_ok==0: remain_cov+=1
        per.append({'selector':r,'accuracy':acc,'delta_vs_actual':acc-dr_acc,'delta_vs_external_l1_max':acc-l1_acc,'gold_present_case_accuracy':(sum(correct[i] for i in gp_idx)/max(1,len(gp_idx))), 'gold_absent_case_accuracy':(sum(correct[i] for i in ga_idx)/max(1,len(ga_idx))), 'changes_from_current':changes,'changes_fix_current_mistakes':fixes,'changes_break_current_correct':breaks,'l1_correct_ours_wrong_recovered':recovered,'selector_failure_remaining_count':remain_sel,'coverage_failure_remaining_count':remain_cov})
    deploy=[x for x in per if x['selector']!='oracle_selector']
    deploy=sorted(deploy,key=lambda x:(-x['accuracy'],x['changes_break_current_correct'],len(x['selector'])))
    rec=deploy[0] if deploy else None
    out=Path(a.output_dir); out.mkdir(parents=True,exist_ok=True)
    with (out/'offline_selector_variant_results.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(per[0].keys())); w.writeheader(); w.writerows(per)
    with (out/'offline_selector_variant_casebook.csv').open('w',newline='',encoding='utf-8') as f:
        fields=list(casebook[0].keys()) if casebook else ['selector','example_id']; w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(casebook)
    summary={'rows':len(cases),'external_l1_max_accuracy':l1_acc,'actual_current_selector_accuracy':dr_acc,'selectors':per,'skipped_selectors':skipped,'recommended_deployable_selector':rec}
    (out/'offline_selector_variant_summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    rep=['# Offline selector variants','',f'- rows: {len(cases)}',f'- external_l1_max accuracy: {l1_acc:.4f}',f'- current DR-v2 accuracy: {dr_acc:.4f}','',f'- skipped: {", ".join(skipped) if skipped else "none"}','',f'- recommended deployable selector: {rec["selector"] if rec else "none"}']
    (out/'offline_selector_variant_report.md').write_text('\n'.join(rep)+'\n',encoding='utf-8')
    print(out)

if __name__=='__main__': main()
