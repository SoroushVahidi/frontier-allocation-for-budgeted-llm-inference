#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json,sys
from collections import defaultdict, Counter
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT=Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path: sys.path.insert(0,str(REPO_ROOT))

from experiments.self_consistency_majority_selector import select_self_consistency_answer, normalize_gsm8k_numeric_answer, group_candidates_by_answer
from experiments.outcome_verifier_answer_group_selector import build_verifier_item, select_case as cohere_select_case


def load_jsonl(path):
    with open(path,encoding='utf-8') as f:
        for l in f:
            if l.strip(): yield json.loads(l)

def canon(x):
    return normalize_gsm8k_numeric_answer('' if x is None else str(x))

def choose_keys(rows,max_examples=50):
    by=defaultdict(dict)
    for r in rows:
        k=(r.get('dataset'),r.get('example_id'),r.get('seed'),r.get('budget'))
        by[k][r.get('method')]=r
    keys=[k for k,v in by.items() if 'direct_reserve_semantic_frontier_v2' in v and 'external_l1_max' in v]
    keys=sorted(keys)
    if max_examples: keys=keys[:max_examples]
    return by,keys

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--pilot-cases',required=True)
    ap.add_argument('--cohere-score-cache',required=True)
    ap.add_argument('--selected-selector-config',default='configs/selected_selector_current.json')
    ap.add_argument('--output-dir',required=True)
    ap.add_argument('--dataset',default='gsm8k')
    ap.add_argument('--margins',nargs='*',type=float,default=[0.0])
    ap.add_argument('--require-full-cohere-coverage',action='store_true')
    ap.add_argument('--no-gold-features',action='store_true')
    ap.add_argument('--max-examples',type=int,default=50)
    args=ap.parse_args()

    rows=list(load_jsonl(args.pilot_cases))
    by,keys=choose_keys(rows,args.max_examples)
    cfg=json.load(open(args.selected_selector_config,encoding='utf-8'))
    margin=float(cfg.get('min_verifier_margin',0.0))
    score_map={(r.get('case_id'),r.get('candidate_id')):float(r.get('verifier_score')) for r in load_jsonl(args.cohere_score_cache) if r.get('verifier_score') is not None}

    per=[]; miss=[]; sc_casebook=[]; co_casebook=[]; vote_hist=[]; invalid_rows=[]
    fallback=0; selected_not_in_pool=0; cases_with_missing=0

    for ds,eid,seed,budget in keys:
        dr=by[(ds,eid,seed,budget)]['direct_reserve_semantic_frontier_v2']
        ex=by[(ds,eid,seed,budget)]['external_l1_max']
        pool=(dr.get('candidate_nodes') or (dr.get('result_metadata') or {}).get('selector_candidate_pool') or [])
        case_id=f"{ds}::{eid}::{seed}::{budget}"

        sc_dec=select_self_consistency_answer(pool)
        grouped=group_candidates_by_answer(pool)
        for inv in grouped['invalid']:
            invalid_rows.append({'case_id':case_id,**inv})
        sc_casebook.append({'case_id':case_id,**sc_dec})
        vote_hist.append({'case_id':case_id,'histogram':sc_dec['answer_vote_histogram']})

        items=[]; scores={}
        for i,c in enumerate(pool):
            it=build_verifier_item(dr,c,case_id,i)
            items.append(it)
            s=score_map.get((case_id,it['candidate_id']))
            scores[(case_id,it['candidate_id'])]=s
            if s is None:
                miss.append({'case_id':case_id,'candidate_id':it['candidate_id']});
        if any(scores[(case_id,it['candidate_id'])] is None for it in items):
            cases_with_missing += 1
        co_dec=cohere_select_case(dr,items,scores,margin,cfg.get('require_trace_for_override',True))
        if co_dec['selected_normalized_answer']==canon(dr.get('selected_answer_canonical') or dr.get('final_answer_canonical')) and len(items)>0 and any(scores[(case_id,it['candidate_id'])] is None for it in items):
            fallback += 1
        pool_answers={canon(c.get('normalized_answer') or c.get('final_answer') or c.get('predicted_answer')) for c in pool}
        if co_dec['selected_normalized_answer'] not in pool_answers and co_dec['selected_normalized_answer']!=canon(dr.get('selected_answer_canonical') or dr.get('final_answer_canonical')):
            selected_not_in_pool += 1
        co_casebook.append({'case_id':case_id,**co_dec})

        gold=canon(dr.get('gold_answer_canonical') or (dr.get('evaluation_only') or {}).get('gold_answer'))
        orig=canon(dr.get('selected_answer_canonical') or dr.get('final_answer_canonical'))
        sca=sc_dec['selected_normalized_answer']
        coa=co_dec['selected_normalized_answer']
        exa=canon(ex.get('selected_answer_canonical') or ex.get('final_answer_canonical'))
        gold_in=int(gold in pool_answers)
        row={'case_id':case_id,'dataset':ds,'example_id':eid,'seed':seed,'budget':budget,'gold_answer':gold,
             'original_answer':orig,'original_correct':int(orig==gold),
             'self_consistency_answer':sca,'self_consistency_correct':int(sca==gold),
             'cohere_answer':coa,'cohere_correct':int(coa==gold),
             'external_answer':exa,'external_correct':int(exa==gold),
             'gold_present_in_candidate_pool':gold_in,
             'self_fix':int(orig!=gold and sca==gold),'self_break':int(orig==gold and sca!=gold),
             'cohere_fix':int(orig!=gold and coa==gold),'cohere_break':int(orig==gold and coa!=gold),
             'self_valid_vote_count':sc_dec['valid_vote_count'],'self_invalid_candidate_count':sc_dec['invalid_candidate_count'],
             'self_tie_flag':int(sc_dec['tie_flag']),'self_vote_share':sc_dec['vote_share']}
        per.append(row)

    if args.require_full_cohere_coverage and (len(miss)>0 or fallback>0 or selected_not_in_pool>0):
        raise SystemExit(f'full coverage failed: missing={len(miss)} fallback={fallback} selected_not_in_pool={selected_not_in_pool}')

    n=max(1,len(per)); orig_correct=sum(r['original_correct'] for r in per)
    summary={
        'pilot_case_count':len(per),
        'original_dr_v2_accuracy':sum(r['original_correct'] for r in per)/n,
        'self_consistency_accuracy':sum(r['self_consistency_correct'] for r in per)/n,
        'cohere_accuracy':sum(r['cohere_correct'] for r in per)/n,
        'external_l1_max_accuracy':sum(r['external_correct'] for r in per)/n,
        'self_overrides_vs_original':sum(int(r['self_consistency_answer']!=r['original_answer']) for r in per),
        'cohere_overrides_vs_original':sum(int(r['cohere_answer']!=r['original_answer']) for r in per),
        'self_fixes':sum(r['self_fix'] for r in per),'self_breaks':sum(r['self_break'] for r in per),
        'cohere_fixes':sum(r['cohere_fix'] for r in per),'cohere_breaks':sum(r['cohere_break'] for r in per),
        'self_net_fixes_minus_breaks':sum(r['self_fix'] for r in per)-sum(r['self_break'] for r in per),
        'cohere_net_fixes_minus_breaks':sum(r['cohere_fix'] for r in per)-sum(r['cohere_break'] for r in per),
        'self_override_precision':sum(r['self_fix'] for r in per)/max(1,sum(int(r['self_consistency_answer']!=r['original_answer']) for r in per)),
        'cohere_override_precision':sum(r['cohere_fix'] for r in per)/max(1,sum(int(r['cohere_answer']!=r['original_answer']) for r in per)),
        'self_original_correct_break_rate':sum(r['self_break'] for r in per)/max(1,orig_correct),
        'cohere_original_correct_break_rate':sum(r['cohere_break'] for r in per)/max(1,orig_correct),
        'self_valid_answer_rate':sum(r['self_valid_vote_count'] for r in per)/max(1,sum(r['self_valid_vote_count']+r['self_invalid_candidate_count'] for r in per)),
        'self_tie_rate':sum(r['self_tie_flag'] for r in per)/n,
        'self_average_selected_vote_share':sum(r['self_vote_share'] for r in per)/n,
        'cohere_missing_score_count':len(miss),'cohere_fallback_count':fallback,'cohere_selected_not_in_pool_count':selected_not_in_pool,
        'cohere_cases_with_missing_scores':cases_with_missing,
    }

    pairwise={
        'self_vs_cohere':{
            'both_correct':sum(int(r['self_consistency_correct'] and r['cohere_correct']) for r in per),
            'both_wrong':sum(int((not r['self_consistency_correct']) and (not r['cohere_correct'])) for r in per),
            'self_consistency_only_correct':sum(int(r['self_consistency_correct'] and not r['cohere_correct']) for r in per),
            'cohere_only_correct':sum(int(r['cohere_correct'] and not r['self_consistency_correct']) for r in per),
            'same_selected_answer_count':sum(int(r['self_consistency_answer']==r['cohere_answer']) for r in per),
            'different_selected_answer_count':sum(int(r['self_consistency_answer']!=r['cohere_answer']) for r in per),
        },
        'self_vs_external':{
            'both_correct':sum(int(r['self_consistency_correct'] and r['external_correct']) for r in per),
            'both_wrong':sum(int((not r['self_consistency_correct']) and (not r['external_correct'])) for r in per),
            'selector_only_correct':sum(int(r['self_consistency_correct'] and not r['external_correct']) for r in per),
            'external_only_correct':sum(int(r['external_correct'] and not r['self_consistency_correct']) for r in per),
        },
        'cohere_vs_external':{
            'both_correct':sum(int(r['cohere_correct'] and r['external_correct']) for r in per),
            'both_wrong':sum(int((not r['cohere_correct']) and (not r['external_correct'])) for r in per),
            'selector_only_correct':sum(int(r['cohere_correct'] and not r['external_correct']) for r in per),
            'external_only_correct':sum(int(r['external_correct'] and not r['cohere_correct']) for r in per),
        },
    }

    def bottleneck(selector_key):
        wrong=[r for r in per if not r[f'{selector_key}_correct']]
        d=sum(int(not r['gold_present_in_candidate_pool']) for r in wrong)
        s=sum(int(r['gold_present_in_candidate_pool']) for r in wrong)
        n=max(1,len(wrong))
        return {'wrong_cases':len(wrong),'gold_absent_from_candidate_pool':d,'gold_present_but_not_selected':s,'discovery_bottleneck_share':d/n,'selector_bottleneck_share':s/n}
    bott={'self_consistency':bottleneck('self_consistency'),'cohere':bottleneck('cohere')}

    headline='Results inconclusive because full Cohere score coverage is unavailable.'
    if summary['cohere_missing_score_count']==0 and summary['cohere_fallback_count']==0:
        if summary['cohere_accuracy']>summary['self_consistency_accuracy']:
            headline='Cohere outcome-verifier selector remains best on same-pilot comparison.'
        elif summary['self_consistency_accuracy']>summary['cohere_accuracy']:
            headline='Self-consistency beats Cohere on the same pilot.'
        else:
            headline='Self-consistency majority vote is competitive and cheaper but has higher break risk.'

    out=Path(args.output_dir); out.mkdir(parents=True,exist_ok=True)
    (out/'manifest.json').write_text(json.dumps({'timestamp':datetime.now(timezone.utc).isoformat(),'pilot_cases':args.pilot_cases,'cohere_score_cache':args.cohere_score_cache,'selected_selector_config':args.selected_selector_config,'require_full_cohere_coverage':args.require_full_cohere_coverage},indent=2)+'\n')
    (out/'selector_comparison_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    with (out/'selector_comparison_summary.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f); w.writerow(['metric','value']); [w.writerow([k,v]) for k,v in summary.items()]
    (out/'per_case_selector_comparison.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in per),encoding='utf-8')
    with (out/'per_case_selector_comparison.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(per[0].keys()) if per else ['case_id']); w.writeheader(); w.writerows(per)
    (out/'self_consistency_casebook.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in sc_casebook),encoding='utf-8')
    (out/'cohere_selector_casebook.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in co_casebook),encoding='utf-8')
    (out/'vote_histograms.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in vote_hist),encoding='utf-8')
    (out/'pairwise_disagreement_breakdown.json').write_text(json.dumps(pairwise,indent=2)+'\n')
    (out/'discovery_vs_selector_bottleneck_breakdown.json').write_text(json.dumps(bott,indent=2)+'\n')
    (out/'missing_cohere_scores.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in miss),encoding='utf-8')
    (out/'invalid_or_unparsable_self_consistency_candidates.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in invalid_rows),encoding='utf-8')
    (out/'selector_comparison_report.md').write_text(f"## Headline\n\n{headline}\n\n## Accuracy table\n\n- original DR-v2: {summary['original_dr_v2_accuracy']:.3f}\n- self-consistency majority vote: {summary['self_consistency_accuracy']:.3f}\n- Cohere outcome-verifier selected selector: {summary['cohere_accuracy']:.3f}\n- external_l1_max: {summary['external_l1_max_accuracy']:.3f}\n\n## Fix/break table\n\n- self-consistency: fixes={summary['self_fixes']} breaks={summary['self_breaks']} net={summary['self_net_fixes_minus_breaks']}\n- cohere outcome-verifier: fixes={summary['cohere_fixes']} breaks={summary['cohere_breaks']} net={summary['cohere_net_fixes_minus_breaks']}\n\n## Pairwise table\n\n- both correct: {pairwise['self_vs_cohere']['both_correct']}\n- both wrong: {pairwise['self_vs_cohere']['both_wrong']}\n- self-consistency only correct: {pairwise['self_vs_cohere']['self_consistency_only_correct']}\n- Cohere only correct: {pairwise['self_vs_cohere']['cohere_only_correct']}\n\n## Safety/break-risk table\n\n- original-correct cases: {orig_correct}\n- self-consistency breaks: {summary['self_breaks']} ({summary['self_original_correct_break_rate']:.3f})\n- cohere breaks: {summary['cohere_breaks']} ({summary['cohere_original_correct_break_rate']:.3f})\n\n## Bottleneck table\n\n- self-consistency wrong: discovery={bott['self_consistency']['gold_absent_from_candidate_pool']} selector={bott['self_consistency']['gold_present_but_not_selected']}\n- cohere wrong: discovery={bott['cohere']['gold_absent_from_candidate_pool']} selector={bott['cohere']['gold_present_but_not_selected']}\n",encoding='utf-8')
    print(out)

if __name__=='__main__': main()
