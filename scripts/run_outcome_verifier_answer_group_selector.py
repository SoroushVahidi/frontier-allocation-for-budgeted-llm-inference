#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, json, sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from experiments.outcome_verifier_answer_group_selector import build_verifier_item, dedupe_key, evaluate_case, score_item, select_case, has_trace

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input', required=True)
    ap.add_argument('--output-dir', required=True)
    ap.add_argument('--selector-name', default='outcome_verifier_answer_group_selector_v1')
    ap.add_argument('--scorer-mode', required=True, choices=['dry_run_call_plan','trace_quality_heuristic','cached_jsonl','api'])
    ap.add_argument('--score-cache')
    ap.add_argument('--min-verifier-margin', type=float, default=0.15)
    ap.add_argument('--require-trace-for-override', action='store_true')
    ap.add_argument('--dedupe-verifier-items', action='store_true')
    ap.add_argument('--allow-api', action='store_true')
    ap.add_argument('--api-backend', choices=['cohere','openai','anthropic','gemini'])
    ap.add_argument('--max-api-calls', type=int)
    ap.add_argument('--no-gold-features', action='store_true')
    args = ap.parse_args()

    rows=[json.loads(x) for x in Path(args.input).read_text(encoding='utf-8').splitlines() if x.strip()]
    out=Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)

    score_map={}
    if args.scorer_mode=='cached_jsonl' and args.score_cache:
        for line in Path(args.score_cache).read_text(encoding='utf-8').splitlines():
            if line.strip():
                r=json.loads(line); score_map[(str(r['case_id']),str(r['candidate_id']))]=float(r['verifier_score'])

    plan=[]; case_items={}
    total_nodes=0; traced_nodes=0; with_inc=0; without_inc=0; with_ch=0
    before=0
    for ci,case in enumerate(rows):
        case_id=str(case.get('case_id') or ci)
        items=[]
        nodes=case.get('candidate_nodes') or []
        total_nodes += len(nodes)
        traced_nodes += sum(1 for n in nodes if has_trace(n))
        for i,n in enumerate(nodes):
            it=build_verifier_item(case,n,case_id,i)
            before += 1
            items.append(it)
        if args.dedupe_verifier_items:
            uniq={}
            for it in items: uniq[dedupe_key(it)] = it
            items=list(uniq.values())
        case_items[case_id]=items
        plan.extend(items)

    if args.scorer_mode=='api' and not args.allow_api:
        raise SystemExit('api scorer mode requires --allow-api')

    score_out=[]; missing=[]; casebook=[]; reasons=defaultdict(int)
    for ci,case in enumerate(rows):
        case_id=str(case.get('case_id') or ci)
        items=case_items[case_id]
        scores={}
        for it in items:
            s=score_item(it,args.scorer_mode,score_map)
            scores[(it['case_id'],it['candidate_id'])]=s
            if s is None: missing.append(it)
            else: score_out.append({'case_id':it['case_id'],'candidate_id':it['candidate_id'],'verifier_score':s})
        d=select_case(case,items,scores,args.min_verifier_margin,args.require_trace_for_override)
        e=evaluate_case(case,d)
        rec={'case_index':ci,'case_id':case_id,**d,**e}
        casebook.append(rec); reasons[d['decision_reason']]+=1
        inc=d['incumbent_normalized_answer']; gs=d['group_scores']
        if inc in gs: with_inc += 1
        else: without_inc += 1
        if any(k!=inc and k!='__unknown__' for k in gs.keys()): with_ch += 1

    total=len(casebook); overrides=sum(r['override'] for r in casebook); fixes=sum(r['fix'] for r in casebook); breaks=sum(r['break'] for r in casebook)
    sel_acc=sum(r['selector_correct'] for r in casebook)/max(1,total); cur_acc=sum(r['current_correct'] for r in casebook)/max(1,total)
    recoverable=sum(1 for c in rows if bool(c.get('gold_in_extracted_terminal_node_finals')))
    aggregate_only=sum(1 for c in rows if bool(c.get('gold_in_aggregate_answer_groups')) and not bool(c.get('gold_in_extracted_terminal_node_finals')))
    recov=sum(1 for r,c in zip(casebook,rows) if bool(c.get('gold_in_extracted_terminal_node_finals')) and r['selector_correct'])
    fail=sum(1 for r,c in zip(casebook,rows) if bool(c.get('gold_in_extracted_terminal_node_finals')) and not r['selector_correct'])

    byprov=defaultdict(lambda: {'count':0,'selector_correct':0})
    for r,c in zip(casebook,rows):
        p=c.get('provenance_source')
        if p:
            byprov[p]['count']+=1; byprov[p]['selector_correct']+=int(r['selector_correct'])
    byprov={k:{**v,'accuracy':v['selector_correct']/max(1,v['count'])} for k,v in byprov.items()}

    summary={'timestamp':datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'),'selector_name':args.selector_name,'total_cases':total,'total_overrides':overrides,'fixes':fixes,'breaks':breaks,'net_fixes_minus_breaks':fixes-breaks,'override_precision':(fixes/max(1,overrides)),'accuracy':sel_acc,'current_incumbent_accuracy':cur_acc,'oracle_ceiling_on_package':recoverable/max(1,total),'recoverable_trace_terminal_cases':recoverable,'recoveries_among_gold_in_terminal_node_cases':recov,'failures_gold_present_in_terminal_nodes_not_chosen':fail,'aggregate_only_cases_count':aggregate_only,'by_provenance_metrics':byprov,'decision_reasons':dict(reasons)}
    cps={'total_cases':len(rows),'total_candidate_nodes':total_nodes,'traced_candidate_nodes':traced_nodes,'candidate_scoring_items_before_dedupe':before,'candidate_scoring_items_after_dedupe':len(plan),'cases_with_incumbent_candidate_group':with_inc,'cases_without_incumbent_candidate_group':without_inc,'cases_with_at_least_one_challenger_group':with_ch,'estimated_api_calls_if_enabled':len(plan),'scorer_mode':args.scorer_mode,'api_backend':args.api_backend,'allow_api':args.allow_api}

    (out/'manifest.json').write_text(json.dumps({'input':args.input,'selector_name':args.selector_name,'scorer_mode':args.scorer_mode},indent=2)+"\n")
    (out/'verifier_call_plan.jsonl').write_text("\n".join(json.dumps(x) for x in plan)+"\n",encoding='utf-8')
    (out/'verifier_call_plan_summary.json').write_text(json.dumps(cps,indent=2)+"\n")
    (out/'selector_summary.json').write_text(json.dumps(summary,indent=2)+"\n")
    with (out/'selector_summary.csv').open('w',newline='',encoding='utf-8') as f: csv.DictWriter(f,fieldnames=list(summary.keys())).writeheader(); csv.DictWriter(f,fieldnames=list(summary.keys())).writerow(summary)
    with (out/'selector_casebook.jsonl').open('w',encoding='utf-8') as f:
        for r in casebook: f.write(json.dumps(r)+"\n")
    with (out/'selector_casebook.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(casebook[0].keys()) if casebook else ['case_index']); w.writeheader(); w.writerows(casebook)
    (out/'selector_report.md').write_text(f"# Outcome verifier answer-group selector report\n\n- scorer_mode: `{args.scorer_mode}`\n- allow_api: `{args.allow_api}`\n")
    if score_out: (out/'verifier_scores.jsonl').write_text("\n".join(json.dumps(x) for x in score_out)+"\n")
    if missing: (out/'missing_or_unscored_candidates.jsonl').write_text("\n".join(json.dumps(x) for x in missing)+"\n")
    print(out)

if __name__=='__main__':
    main()
