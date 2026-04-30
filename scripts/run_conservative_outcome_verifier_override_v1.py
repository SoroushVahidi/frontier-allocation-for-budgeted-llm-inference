#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, csv
from pathlib import Path
from typing import Dict, Any, List, Tuple

DR='direct_reserve_frontier_gate_v1'
L1='external_l1_max'

def nrm(x: Any)->str:
    return str(x or '').strip().lower()

def get_group_scores(md: Dict[str,Any], key: str) -> Dict[str,float]:
    raw = md.get(key) or {}
    out: Dict[str,float] = {}
    if isinstance(raw, dict):
        for k,v in raw.items():
            try: out[str(k)] = float(v)
            except Exception: pass
    return out

def conservative_override_choice(row: Dict[str,Any]) -> Tuple[str, Dict[str,Any]]:
    md = row.get('result_metadata') or {}
    selected = str(md.get('post_rerank_selected_answer_group') or md.get('pre_rerank_selected_answer_group') or md.get('selected_answer_group') or '')
    support = get_group_scores(md,'raw_support_count_by_answer_group')
    fam_support = get_group_scores(md,'num_supporting_strategy_families_by_answer_group')
    proc = get_group_scores(md,'mean_process_score_by_answer_group')
    entropy = float(md.get('answer_entropy') or 0.0)
    top_gap = float(md.get('top2_support_gap') or 0.0)

    winner = selected
    reason = {'override': False, 'selected_group': selected, 'candidate_group': selected, 'reasons': []}
    if not selected or len(support) < 2:
        return winner, reason

    cand = max((g for g in support if g != selected), key=lambda g: (support.get(g,0), fam_support.get(g,0), proc.get(g,0)), default=selected)
    sup_adv = support.get(cand,0)-support.get(selected,0)
    fam_adv = fam_support.get(cand,0)-fam_support.get(selected,0)
    proc_adv = proc.get(cand,0)-proc.get(selected,0)
    selected_risk = int(entropy >= 0.65) + int(top_gap <= 1.0)
    cand_clean = int(proc.get(cand,0) >= proc.get(selected,0))

    # Conservative gate: large evidence margin + selected inconsistency risk + candidate not weaker in process quality.
    if sup_adv >= 2 and fam_adv >= 1 and selected_risk >= 1 and cand_clean == 1 and proc_adv >= -0.02:
        winner = cand
        reason = {
            'override': True,
            'selected_group': selected,
            'candidate_group': cand,
            'reasons': [
                f'support_advantage={sup_adv:.2f}',
                f'family_diversity_advantage={fam_adv:.2f}',
                f'selected_risk_score={selected_risk}',
                f'process_advantage={proc_adv:.3f}',
            ],
        }
    return winner, reason

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--artifact-dir', required=True)
    ap.add_argument('--out-dir', required=True)
    args=ap.parse_args()
    ad=Path(args.artifact_dir); out=Path(args.out_dir); out.mkdir(parents=True, exist_ok=True)
    rows=[json.loads(l) for l in (ad/'per_example_records.jsonl').read_text().splitlines() if l.strip()]
    idx={(r['example_id'],r['dataset'],r['seed'],r['budget'],r['method']):r for r in rows}
    base=[]
    for k,r in idx.items():
        if k[-1]!=DR: continue
        kk=k[:-1]
        if (*kk,L1) in idx: base.append((kk,r,idx[(*kk,L1)]))

    total=len(base)
    dr_ok=l1_ok=sup_ok=new_ok=oracle_ok=0
    fixes=breaks=overrides=override_correct=0
    casebook=[]
    for kk,dr,l1 in base:
        gold=nrm(dr.get('gold_answer_canonical') or dr.get('gold_answer'))
        dr_ans=nrm(dr.get('final_answer_canonical') or dr.get('final_answer_raw'))
        l1_ans=nrm(l1.get('final_answer_canonical') or l1.get('final_answer_raw'))
        md=dr.get('result_metadata') or {}
        selected=str(md.get('post_rerank_selected_answer_group') or md.get('selected_answer_group') or '')
        ag=md.get('answer_groups') or []
        support=get_group_scores(md,'raw_support_count_by_answer_group')
        sup_choice=max(support, key=lambda g:support[g]) if support else selected

        new_group, reason = conservative_override_choice(dr)
        g_to_ans={str(g.get('group_key')):nrm(g.get('answer_canonical') or g.get('answer')) for g in ag if isinstance(g,dict)}
        new_ans=g_to_ans.get(new_group, dr_ans)
        sup_ans=g_to_ans.get(sup_choice, dr_ans)
        cand_answers=set(g_to_ans.values())

        d_ok=(dr_ans==gold); ll_ok=(l1_ans==gold); s_ok=(sup_ans==gold); n_ok=(new_ans==gold)
        o_ok=(gold in cand_answers) or d_ok
        dr_ok+=d_ok; l1_ok+=ll_ok; sup_ok+=s_ok; new_ok+=n_ok; oracle_ok+=o_ok
        if reason['override']:
            overrides += 1
            override_correct += int(n_ok)
        if (not d_ok) and n_ok: fixes+=1
        if d_ok and (not n_ok): breaks+=1

        support_break = d_ok and (not s_ok)
        gold_present_selected_wrong = (not d_ok) and (gold in cand_answers)
        if gold_present_selected_wrong or support_break:
            casebook.append({
                'example_id':kk[0],'dataset':kk[1],'seed':kk[2],'budget':kk[3],
                'dr_correct':d_ok,'support_only_correct':s_ok,'new_correct':n_ok,
                'gold_present_in_candidates':gold in cand_answers,
                'case_type':'gold_present_dr_selected_wrong' if gold_present_selected_wrong else 'support_only_break_case',
                'decision':reason
            })

    with (out/'conservative_override_decisions.jsonl').open('w') as f:
        for _,dr,_ in base:
            g,reason=conservative_override_choice(dr)
            f.write(json.dumps({'example_id':dr['example_id'],'seed':dr['seed'],'budget':dr['budget'],'selected_group':reason['selected_group'],'chosen_group':g,'override':reason['override'],'reasons':reason['reasons']})+'\n')

    metrics=[
        ['external_l1_max',l1_ok/total,l1_ok],
        ['current_dr_v2_selector',dr_ok/total,dr_ok],
        ['support_only',sup_ok/total,sup_ok],
        ['conservative_outcome_verifier_override_v1',new_ok/total,new_ok],
        ['oracle_selector_ceiling_over_candidates',oracle_ok/total,oracle_ok],
    ]
    with (out/'accuracy_table.csv').open('w',newline='') as f:
        w=csv.writer(f); w.writerow(['method','accuracy','correct']); w.writerows(metrics)
    with (out/'override_metrics.json').open('w') as f:
        json.dump({'total':total,'fixes':fixes,'breaks':breaks,'net_fixes_minus_breaks':fixes-breaks,'overrides':overrides,'override_precision':(override_correct/overrides if overrides else 0.0)},f,indent=2)
    with (out/'focused_casebook.jsonl').open('w') as f:
        for r in casebook: f.write(json.dumps(r)+'\n')

if __name__=='__main__':
    main()
