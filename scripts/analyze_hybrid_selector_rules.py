#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, json
from pathlib import Path
from collections import Counter

DR='direct_reserve_semantic_frontier_v2'
SF='direct_reserve_semantic_frontier_v2_selection_fix_v1'
OV='direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1'
PRM='direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1'
L1='external_l1_max'


def nrm(x):
    return str(x or '').strip().lower()

def has_two_answer_groups(row):
    md=row.get('result_metadata') or {}
    ag=md.get('answer_group_count')
    if isinstance(ag,(int,float)): return ag>1
    groups=md.get('prm_group_scores') or md.get('answer_groups') or []
    return isinstance(groups,list) and len(groups)>1

def prm_parse_fallback(row):
    md=row.get('result_metadata') or {}
    if md.get('parse_fallback') or md.get('prm_parse_fallback') or md.get('parse_error'): return True
    scores=(md.get('prm_step_scores') or {})
    if isinstance(scores,dict):
        for arr in scores.values():
            if isinstance(arr,list) and any(isinstance(x,dict) and x.get('parse_fallback') for x in arr): return True
    return False

def majority_vote(answers, fallback):
    c=Counter([a for a in answers if nrm(a)])
    if not c: return fallback
    top=max(c.values())
    winners=[k for k,v in c.items() if v==top]
    return fallback if len(winners)!=1 else winners[0]

def choose_rule(rule, m):
    d,s,p,o=[m[k] for k in (DR,SF,PRM,OV)]
    da,sa,pa,oa=[nrm(x.get('final_answer_canonical') or x.get('final_answer_raw')) for x in (d,s,p,o)]
    if rule=='keep_dr_v2': return da
    if rule=='use_selection_fix_v1': return sa
    if rule=='use_prm': return pa
    if rule=='use_ov': return oa
    if rule=='prm_if_two_answer_groups': return pa if has_two_answer_groups(p) else da
    if rule=='selection_fix_if_two_answer_groups': return sa if has_two_answer_groups(s) else da
    if rule=='prm_and_selection_fix_agree': return pa if pa and pa==sa and pa!=da else da
    if rule=='prm_or_selection_fix_majority': return majority_vote([da,sa,pa],da)
    if rule=='dr_v2_selection_fix_prm_ov_majority': return majority_vote([da,sa,pa,oa],da)
    if rule=='prm_unless_parse_fallback': return da if prm_parse_fallback(p) else pa
    if rule=='selection_fix_then_prm_on_disagreement': return da if (sa!=da and pa==da) else sa
    if rule=='prm_when_it_differs_from_ov': return pa if pa!=oa else da
    if rule=='oracle_upper_bound_existing_internal':
        g=nrm(d.get('gold_answer_canonical') or d.get('gold_answer'))
        for a in (da,sa,oa,pa):
            if a==g: return g
        return da
    raise ValueError(rule)

def rule_metrics(rule, bundle, l1_beats_dr, present, absent):
    total=len(bundle); corr=0; pred={}
    wdr=tdr=ldr=wl1=tl1=ll1=over=rec=reg=corr_over=0
    p_corr=a_corr=l1_corr=0
    for key,m in bundle.items():
        d,l1=m[DR],m[L1]
        chosen=choose_rule(rule,m)
        gold=nrm(d.get('gold_answer_canonical') or d.get('gold_answer'))
        d_ans=nrm(d.get('final_answer_canonical') or d.get('final_answer_raw'))
        l1_ans=nrm(l1.get('final_answer_canonical') or l1.get('final_answer_raw'))
        ok=(chosen==gold); d_ok=(d_ans==gold); l1_ok=(l1_ans==gold)
        corr+=ok; pred[key]=chosen
        if ok and not d_ok: wdr+=1
        elif ok and d_ok: tdr+=1
        elif (not ok) and d_ok: ldr+=1
        if ok and not l1_ok: wl1+=1
        elif ok and l1_ok: tl1+=1
        elif (not ok) and l1_ok: ll1+=1
        changed=(chosen!=d_ans); over+=changed
        if changed and ok and not d_ok: rec+=1
        if changed and (not ok) and d_ok: reg+=1
        if changed and ok: corr_over+=1
        if key in l1_beats_dr and ok: l1_corr+=1
        if key in present and ok: p_corr+=1
        if key in absent and ok: a_corr+=1
    return {
      'rule':rule,'accuracy':corr/total if total else 0,'correct_count':corr,
      'paired_vs_dr_v2_w_t_l':f'{wdr}/{tdr}/{ldr}','paired_vs_l1_w_t_l':f'{wl1}/{tl1}/{ll1}',
      'overrides_vs_dr_v2':over,'recoveries_of_dr_v2_wrong':rec,'regressions_of_dr_v2_correct':reg,
      'override_precision':(corr_over/over if over else 0.0),
      'l1_beats_dr_v2_correct':l1_corr,'l1_beats_dr_v2_total':len(l1_beats_dr),
      'present_but_not_selected_correct':p_corr,'present_but_not_selected_total':len(present),
      'absent_from_tree_correct':a_corr,'absent_from_tree_total':len(absent),
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--artifact-dir',required=True)
    ap.add_argument('--timestamp',required=True)
    a=ap.parse_args(); ad=Path(a.artifact_dir)
    rows=[json.loads(l) for l in (ad/'per_example_records.jsonl').read_text().splitlines() if l.strip()]
    idx={(r.get('example_id'),r.get('dataset'),r.get('seed'),r.get('budget'),r.get('method')):r for r in rows}
    methods=[DR,SF,PRM,OV,L1]
    bundle={}
    for k,r in idx.items():
        if k[-1]!=DR: continue
        base=k[:-1]
        if all((*base,m) in idx for m in methods): bundle[base]={m:idx[(*base,m)] for m in methods}
    cjsonl=ad/'external_l1_loss_casebook.jsonl'
    casebook=[json.loads(l) for l in cjsonl.read_text().splitlines() if l.strip()] if cjsonl.exists() else []
    l1_beats_dr=set();present=set();absent=set()
    for r in casebook:
        key=(r.get('example_id'),r.get('dataset'),r.get('seed'),r.get('budget'))
        if r.get('l1_beats_method') and r.get('method')==DR: l1_beats_dr.add(key)
        cls=nrm(r.get('loss_taxonomy') or r.get('loss_class'))
        if 'present' in cls: present.add(key)
        if 'absent' in cls: absent.add(key)
    rules=['keep_dr_v2','use_selection_fix_v1','use_prm','use_ov','prm_if_two_answer_groups','selection_fix_if_two_answer_groups','prm_and_selection_fix_agree','prm_or_selection_fix_majority','dr_v2_selection_fix_prm_ov_majority','prm_unless_parse_fallback','selection_fix_then_prm_on_disagreement','prm_when_it_differs_from_ov','oracle_upper_bound_existing_internal']
    out=[rule_metrics(r,bundle,l1_beats_dr,present,absent) for r in rules]
    best_internal=max(out[:-1], key=lambda x:x['correct_count']) if out else None
    for r in out:
        r['beats_current_best_internal_20_of_30']=r['correct_count']>20
        r['exploratory']= (r['rule']=='prm_when_it_differs_from_ov')
    csvp=ad/'hybrid_selector_rule_sweep.csv'
    with csvp.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(out[0].keys()));w.writeheader();w.writerows(out)
    md=Path('docs/HYBRID_SELECTOR_RULE_ANALYSIS_20260429.md')
    lines=['# Hybrid Selector Rule Analysis (Offline)','','Artifact directory: '+str(ad),'','| rule | correct | acc | vs DR W/T/L | vs L1 W/T/L | overrides | recoveries | regressions | override precision |','|---|---:|---:|---|---|---:|---:|---:|---:|']
    for r in out:
        lines.append(f"| {r['rule']} | {r['correct_count']} | {r['accuracy']:.3f} | {r['paired_vs_dr_v2_w_t_l']} | {r['paired_vs_l1_w_t_l']} | {r['overrides_vs_dr_v2']} | {r['recoveries_of_dr_v2_wrong']} | {r['regressions_of_dr_v2_correct']} | {r['override_precision']:.3f} |")
    lines +=['',f"Best deployable rule by correct_count: {best_internal['rule']} ({best_internal['correct_count']})" if best_internal else 'No data.',f"Any deployable rule > 20/30: {any(r['correct_count']>20 for r in out if r['rule']!='oracle_upper_bound_existing_internal')}"]
    md.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(csvp)
    print(md)

if __name__=='__main__': main()
