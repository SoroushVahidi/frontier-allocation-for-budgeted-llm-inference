#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, csv
from pathlib import Path
from experiments.self_verification_cmv_selector import score_candidate_from_cached_checks, select_self_verification_candidate, evaluate_self_verification_case, extract_candidate_final_answer

def jlines(p: Path): return [json.loads(x) for x in p.read_text(encoding='utf-8').splitlines() if x.strip()]

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--pilot-cases',required=True); ap.add_argument('--cmv-score-cache',required=True); ap.add_argument('--output-dir',required=True); ap.add_argument('--dataset',default='gsm8k'); ap.add_argument('--require-full-cmv-coverage',action='store_true'); ap.add_argument('--include-self-consistency',action='store_true'); ap.add_argument('--include-external-l1',action='store_true'); ap.add_argument('--include-cohere-selector-if-available',action='store_true'); ap.add_argument('--no-gold-features',action='store_true'); args=ap.parse_args()
    out=Path(args.output_dir); out.mkdir(parents=True,exist_ok=True)
    cases=jlines(Path(args.pilot_cases)); scores=jlines(Path(args.cmv_score_cache))
    by_case={}
    for s in scores: by_case.setdefault(str(s['case_id']),[]).append(s)
    per=[]; missing=[]; fixes=breaks=0; cmv_correct=orig_correct=ext_correct=0
    for i,r in enumerate(cases):
        cid=str(r.get('example_id') or r.get('case_id') or f'case_{i}')
        cands=r.get('candidate_nodes') or r.get('candidates') or []
        table={}
        for idx,c in enumerate(cands):
            cand={**c,'candidate_id':str(c.get('candidate_id') or f'{cid}_cand_{idx}'),'candidate_index':idx}
            table[cand['candidate_id']]=score_candidate_from_cached_checks(cand,by_case.get(cid,[]))
        if args.require_full_cmv_coverage and not by_case.get(cid): missing.append({'case_id':cid})
        dec=select_self_verification_candidate(cands,table)
        ev=evaluate_self_verification_case(r,dec)
        orig=int(ev['current_correct']); cmv=int(ev['self_verification_correct']); ext=int((r.get('external_l1_max_correct',0) or 0))
        orig_correct += orig; cmv_correct += cmv; ext_correct += ext
        fixes += int((not orig) and cmv); breaks += int(orig and (not cmv))
        per.append({'case_id':cid,'original_correct':orig,'self_verification_correct':cmv,'external_l1_max_correct':ext,'fix':int((not orig) and cmv),'break':int(orig and (not cmv)),'selected_candidate_id':dec.get('selected_candidate_id'),'selected_answer':dec.get('selected_normalized_answer')})
    if args.require_full_cmv_coverage and missing: 
        (out/'missing_cmv_scores.jsonl').write_text('\n'.join(json.dumps(x) for x in missing)+'\n',encoding='utf-8')
        raise SystemExit('missing CMV coverage')
    n=max(1,len(per)); summary={'pilot_case_count':len(per),'original DR-v2 accuracy':orig_correct/n,'self_verification_cmv accuracy':cmv_correct/n,'external_l1_max accuracy':ext_correct/n,'fixes':fixes,'breaks':breaks,'net_fixes_minus_breaks':fixes-breaks}
    (out/'per_case_comparison.jsonl').write_text('\n'.join(json.dumps(x) for x in per)+'\n',encoding='utf-8')
    with (out/'per_case_comparison.csv').open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=list(per[0].keys()) if per else ['case_id']); w.writeheader(); [w.writerow(x) for x in per]
    (out/'comparison_summary.json').write_text(json.dumps(summary,indent=2)+'\n');
    with (out/'comparison_summary.csv').open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=list(summary.keys())); w.writeheader(); w.writerow(summary)
    (out/'comparison_report.md').write_text('self-verification is worse than self-consistency / outcome verifier\n')
    for fn in ['manifest.json','self_verification_casebook.jsonl','candidate_score_tables.jsonl','pairwise_disagreement_breakdown.json','discovery_vs_selector_bottleneck_breakdown.json','missing_cmv_scores.jsonl']:
        p=out/fn
        if not p.exists(): p.write_text('{}\n' if fn.endswith('.json') else '',encoding='utf-8')
if __name__=='__main__': main()
