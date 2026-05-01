#!/usr/bin/env python3
import argparse, csv, json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

def load_jsonl(path):
    with open(path) as f:
        for l in f:
            if l.strip(): yield json.loads(l)

def canon(x):
    return '' if x is None else str(x).strip()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--paired-records', required=True)
    ap.add_argument('--selected-config', required=True)
    ap.add_argument('--score-cache', required=True)
    ap.add_argument('--max-examples', type=int, default=100)
    ap.add_argument('--output-dir', required=True)
    args=ap.parse_args()

    cfg=json.load(open(args.selected_config))
    scores={}
    for r in load_jsonl(args.score_cache):
        scores[(r.get('case_id'), r.get('candidate_id'))]=float(r.get('verifier_score',0.0))

    bykey=defaultdict(dict)
    for r in load_jsonl(args.paired_records):
        k=(r.get('dataset'), r.get('example_id'), r.get('seed'), r.get('budget'))
        bykey[k][r.get('method')]=r

    selected_keys=[]
    for k,m in bykey.items():
        if 'direct_reserve_semantic_frontier_v2' in m and 'external_l1_max' in m:
            selected_keys.append(k)
    selected_keys=sorted(selected_keys)[:args.max_examples]

    out=Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)
    per=[]; missing=[]
    for ds,eid,seed,budget in selected_keys:
        dr=bykey[(ds,eid,seed,budget)]['direct_reserve_semantic_frontier_v2']
        ex=bykey[(ds,eid,seed,budget)]['external_l1_max']
        md=dr.get('result_metadata') or {}
        pool=md.get('selector_candidate_pool') or []
        case_id=f"{ds}::{eid}::{seed}::{budget}"
        best=None; best_sc=-1e9
        for c in pool:
            cid=c.get('candidate_id')
            sc=scores.get((case_id,cid))
            if sc is None:
                missing.append({'case_id':case_id,'candidate_id':cid,'normalized_answer':c.get('normalized_answer'),'trace':c.get('trace','')[:500]})
                continue
            if (sc>best_sc) and (c.get('trace') or not cfg.get('require_trace_for_override',False)):
                best_sc=sc; best=c
        orig_ans=canon(dr.get('selected_answer_canonical') or dr.get('final_answer_canonical'))
        sel_ans=canon(best.get('normalized_answer') if best else orig_ans)
        gold=canon(dr.get('gold_answer_canonical'))
        orig_ok=int(canon(dr.get('exact_match'))=='1' or orig_ans==gold)
        sel_ok=int(sel_ans==gold)
        ext_ok=int(canon(ex.get('exact_match'))=='1' or canon(ex.get('selected_answer_canonical') or ex.get('final_answer_canonical'))==gold)
        gold_in=int(any(canon(c.get('normalized_answer'))==gold for c in pool))
        row={
            'dataset':ds,'example_id':eid,'seed':seed,'budget':budget,'problem_statement':dr.get('question'),
            'gold_answer':gold,'external_l1_max_answer':canon(ex.get('selected_answer_canonical') or ex.get('final_answer_canonical')),
            'external_l1_max_correct':ext_ok,'original_dr_v2_answer':orig_ans,'original_dr_v2_correct':orig_ok,
            'selected_selector_answer':sel_ans,'selected_selector_correct':sel_ok,'gold_present_in_dr_v2_tree':gold_in,
            'original_missed_despite_gold_present':int(gold_in and not orig_ok),'selected_selector_fixed':int((not orig_ok) and sel_ok),
            'selected_selector_broke_current_correct':int(orig_ok and not sel_ok),
            'external_correct_selected_wrong':int(ext_ok and not sel_ok), 'selected_correct_external_wrong':int(sel_ok and not ext_ok)
        }
        if row['selected_selector_fixed']: ft='selector_fixed'
        elif row['selected_selector_broke_current_correct']: ft='selector_broke'
        elif sel_ok and ext_ok: ft='both_correct'
        elif (not sel_ok) and (not ext_ok): ft='both_wrong'
        elif sel_ok and (not ext_ok): ft='selected_only_correct'
        elif ext_ok and (not sel_ok): ft='external_only_correct'
        elif (not sel_ok) and (not gold_in): ft='discovery_absent_gold'
        else: ft='selection_missed_gold_present'
        row['failure_type']=ft
        per.append(row)

    n=max(1,len(per))
    sumry={
        'num_examples':len(per),
        'original_dr_v2_accuracy':sum(r['original_dr_v2_correct'] for r in per)/n,
        'selected_selector_accuracy':sum(r['selected_selector_correct'] for r in per)/n,
        'external_l1_max_accuracy':sum(r['external_l1_max_correct'] for r in per)/n,
    }
    sumry['delta_selected_vs_original']=sumry['selected_selector_accuracy']-sumry['original_dr_v2_accuracy']
    sumry['delta_selected_vs_external']=sumry['selected_selector_accuracy']-sumry['external_l1_max_accuracy']
    sumry['selected_beats_external_count']=sum(r['selected_correct_external_wrong'] for r in per)
    sumry['external_beats_selected_count']=sum(r['external_correct_selected_wrong'] for r in per)
    sumry['both_correct']=sum(int(r['selected_selector_correct'] and r['external_l1_max_correct']) for r in per)
    sumry['both_wrong']=sum(int((not r['selected_selector_correct']) and (not r['external_l1_max_correct'])) for r in per)
    sumry['original_correct_cases']=sum(r['original_dr_v2_correct'] for r in per)
    sumry['selected_breaks_among_original_correct']=sum(r['selected_selector_broke_current_correct'] for r in per)
    sumry['break_rate']=sumry['selected_breaks_among_original_correct']/max(1,sumry['original_correct_cases'])
    breakdown=Counter(r['failure_type'] for r in per)

    (out/'per_case_comparison.jsonl').write_text('\n'.join(json.dumps(r) for r in per)+'\n')
    with (out/'per_case_comparison.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(per[0].keys()) if per else []); w.writeheader(); w.writerows(per)
    (out/'missing_selector_scores.jsonl').write_text('\n'.join(json.dumps(r) for r in missing)+'\n')
    (out/'comparison_summary.json').write_text(json.dumps(sumry,indent=2))
    with (out/'comparison_summary.csv').open('w',newline='') as f:
        w=csv.writer(f); w.writerow(['metric','value']); [w.writerow([k,v]) for k,v in sumry.items()]
    (out/'discovery_vs_selection_failure_breakdown.json').write_text(json.dumps(dict(breakdown),indent=2))
    (out/'selector_application_casebook.jsonl').write_text((out/'per_case_comparison.jsonl').read_text())
    (out/'manifest.json').write_text(json.dumps({'timestamp':datetime.now(timezone.utc).isoformat(),'paired_records':args.paired_records,'selected_config':args.selected_config,'score_cache':args.score_cache,'max_examples':args.max_examples},indent=2))
    headline='comparison inconclusive due to too few cases / missing verifier scores'
    if len(missing)==0:
        if sumry['selected_selector_accuracy']>sumry['external_l1_max_accuracy']: headline='selected selector beats external_l1_max on this bounded pilot'
        elif sumry['selected_selector_accuracy']<sumry['external_l1_max_accuracy']: headline='external_l1_max remains ahead'
        else: headline='selected selector closes gap but does not beat external_l1_max'
    report=f"## Headline\n\n{headline}\n\n## Accuracy table\n\n- original DR-v2: {sumry['original_dr_v2_accuracy']:.3f}\n- DR-v2 + selected selector: {sumry['selected_selector_accuracy']:.3f}\n- external_l1_max: {sumry['external_l1_max_accuracy']:.3f}\n\n## Pairwise table\n\n- both correct: {sumry['both_correct']}\n- both wrong: {sumry['both_wrong']}\n- selected only correct: {sumry['selected_beats_external_count']}\n- external only correct: {sumry['external_beats_selected_count']}\n\n## Bottleneck table\n\n"+'\n'.join([f"- {k}: {v}" for k,v in breakdown.items()])+"\n\n## Safety caveats\n\n- bounded pilot run.\n- selected selector chosen on recovery evidence and not runtime promoted.\n- no external_l1_max defeat claim unless supported by metrics.\n- current-correct break risk may be nonzero.\n"
    (out/'comparison_report.md').write_text(report)

if __name__=='__main__': main()
