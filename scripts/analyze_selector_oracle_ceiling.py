#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json,statistics
from pathlib import Path
import sys
from datetime import datetime, timezone

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from experiments.selector_error_features import build_group_feature_rows

DR='direct_reserve_semantic_frontier_v2'; L1='external_l1_max'; OV='direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1'; PRM='direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1'

def nrm(x): return str(x or '').strip().lower()

def resolve(p:str):
    q=Path(p)
    if q.is_file(): return q.parent,q
    return q,q/'per_example_records.jsonl'

def pick(groups,mode):
    if not groups:return ''
    if mode=='support_only': return max(groups,key=lambda g:(g.get('support_count',0),g['normalized_answer']))['normalized_answer']
    if mode=='consistency_penalized': return max(groups,key=lambda g:g['hybrid_selector_score']-0.3*sum(g['consistency_flags'].values()))['normalized_answer']
    if mode=='unified_confidence': return max(groups,key=lambda g:g['unified_confidence_score'])['normalized_answer']
    if mode=='hybrid': return max(groups,key=lambda g:g['hybrid_selector_score'])['normalized_answer']
    return ''

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--artifact-dir',required=True);ap.add_argument('--output-dir',default='');a=ap.parse_args()
    out_dir,inp=resolve(a.artifact_dir)
    if a.output_dir:
        out_dir = Path(a.output_dir)
    elif inp.is_file() and 'tests/fixtures' not in str(inp):
        stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        out_dir = out_dir / f"selector_oracle_ceiling_{stamp}"
    rows=[json.loads(l) for l in inp.read_text().splitlines() if l.strip()]
    idx={(r.get('example_id'),r.get('dataset'),r.get('seed'),r.get('budget'),r.get('method')):r for r in rows}
    methods={k[-1] for k in idx}
    base_method = DR if DR in methods else ('direct_reserve_frontier_gate_v1' if 'direct_reserve_frontier_gate_v1' in methods else None)
    if base_method is None:
        raise SystemExit('No base direct-reserve method found in artifact.')
    dr_keys=[k for k in idx if k[-1]==base_method]
    recs=[]; ccounts=[];gcounts=[]; gold_present=0
    accs={m:0 for m in [L1,DR,OV,PRM]}; present_not_sel=absent=0;l1_ours_wrong_present=0;l1_ours_wrong_absent=0
    accs.setdefault(base_method,0)
    for k in dr_keys:
        base=idx[k]; key4=k[:-1]; gold=nrm(base.get('gold_answer_canonical') or base.get('gold_answer')); q=base.get('question_raw') or base.get('question') or ''
        md=base.get('result_metadata') or {}
        pool=md.get('selector_candidate_pool') or md.get('final_branch_states') or base.get('final_nodes') or []
        groups={}
        for r in pool:
            if not isinstance(r,dict): continue
            ans=nrm(r.get('predicted_answer') or r.get('final_answer') or r.get('answer'))
            if not ans: continue
            g=groups.setdefault(ans,{'normalized_answer':ans,'support_count':0,'source_family':str(r.get('source','')),'trace':str(r.get('trace','') or ''),'final_answer':ans,'ov_score':None,'prm_score':None})
            g['support_count']+=1
        grouped=list(groups.values())
        drr=idx.get((*key4,base_method));ov=idx.get((*key4,OV));pr=idx.get((*key4,PRM));l1=idx.get((*key4,L1))
        if ov:
            om=ov.get('result_metadata') or {}
            cs=om.get('ov_rerank_candidate_scores') or {}
            for g in grouped:
                for cid,v in cs.items():
                    if nrm((v or {}).get('normalized_answer'))==g['normalized_answer']: g['ov_score']=float((v or {}).get('candidate_score',0.0))
        if pr:
            pm=pr.get('result_metadata') or {}
            gs=pm.get('prm_group_scores') or []
            for g in grouped:
                hit=[x for x in gs if nrm((x or {}).get('normalized_answer'))==g['normalized_answer']]
                if hit: g['prm_score']=float(hit[0].get('group_score',0.0))
        feats=build_group_feature_rows(q,grouped)
        oracle_ok=any(g['normalized_answer']==gold for g in feats)
        gold_present+=int(oracle_ok)
        if oracle_ok and nrm(drr.get('final_answer_canonical') or drr.get('final_answer_raw'))!=gold: present_not_sel+=1
        if not oracle_ok: absent+=1
        row={'example_id':k[0],'oracle_correct':int(oracle_ok)}
        for mode in ['support_only','consistency_penalized','unified_confidence','hybrid']:
            pred=pick(feats,mode); row[f'{mode}_pred']=pred; row[f'{mode}_correct']=int(pred==gold)
        for m in [L1,base_method,OV,PRM]:
            rr=idx.get((*key4,m));
            if rr: accs[m]+=int(nrm(rr.get('final_answer_canonical') or rr.get('final_answer_raw'))==gold)
        ours_row = pr or ov or drr
        ours_ok=nrm((ours_row).get('final_answer_canonical') or (ours_row).get('final_answer_raw') or (ours_row).get('selected_answer_canonical') or (ours_row).get('selected_answer_raw'))==gold
        l1_ok=l1 and nrm(l1.get('final_answer_canonical') or l1.get('final_answer_raw'))==gold
        if l1_ok and not ours_ok:
            if oracle_ok: l1_ours_wrong_present+=1
            else: l1_ours_wrong_absent+=1
        ccounts.append(len(pool)); gcounts.append(len(groups)); recs.append(row)
    out_dir.mkdir(parents=True,exist_ok=True)
    with (out_dir/'selector_oracle_ceiling.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(recs[0].keys()) if recs else ['example_id']);w.writeheader();w.writerows(recs)
    tot=max(1,len(dr_keys));
    summary={
      'total_scored_examples':len(dr_keys),'l1_accuracy':accs[L1]/tot if dr_keys else None,'dr_v2_accuracy':accs.get(base_method,accs[DR])/tot if dr_keys else None,'ov_accuracy':accs[OV]/tot if dr_keys else None,'prm_accuracy':accs[PRM]/tot if dr_keys else None,
      'candidate_count_mean':statistics.mean(ccounts) if ccounts else 0,'candidate_count_median':statistics.median(ccounts) if ccounts else 0,'candidate_count_max':max(ccounts) if ccounts else 0,
      'answer_group_count_mean':statistics.mean(gcounts) if gcounts else 0,'answer_group_count_median':statistics.median(gcounts) if gcounts else 0,'answer_group_count_max':max(gcounts) if gcounts else 0,
      'gold_present_rate':gold_present/tot,'oracle_selector_accuracy':gold_present/tot,'selector_gap':(gold_present-accs[PRM])/tot if dr_keys else 0,
      'l1_correct_ours_wrong_gold_present':l1_ours_wrong_present,'l1_correct_ours_wrong_gold_absent':l1_ours_wrong_absent,'present_not_selected_loss_count':present_not_sel,'absent_from_pool_loss_count':absent
    }
    (out_dir/'selector_oracle_ceiling_summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    print(out_dir/'selector_oracle_ceiling.csv')
    print(out_dir/'selector_oracle_ceiling_summary.json')

if __name__=='__main__': main()
