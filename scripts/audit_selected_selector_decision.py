#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, hashlib, json
from pathlib import Path
from datetime import datetime, timezone
import subprocess, tempfile

BANNED_KEYS = {"gold_answer","oracle_selector_answer","oracle_selector_would_fix","correct_answer","evaluation_only","gold","oracle","label","is_correct"}


def jlines(path: Path):
    for ln in path.read_text(encoding='utf-8').splitlines():
        if ln.strip():
            yield json.loads(ln)


def score_key(case_id:str,candidate_id:str)->str:
    return hashlib.sha256(f"{case_id}|{candidate_id}".encode()).hexdigest()


def deep_has_banned(obj, path=""):
    hits=[]
    if isinstance(obj, dict):
        for k,v in obj.items():
            p=f"{path}.{k}" if path else k
            if k.lower() in BANNED_KEYS:
                hits.append(p)
            hits.extend(deep_has_banned(v,p))
    elif isinstance(obj,list):
        for i,v in enumerate(obj):
            hits.extend(deep_has_banned(v,f"{path}[{i}]"))
    return hits


def sanitize_record(r:dict)->dict:
    keep={k:r.get(k) for k in ["case_id","dataset","example_id","problem","problem_statement","candidate_nodes","current_answer","current_normalized_answer","current_candidate_id","selected_answer","selected_normalized_answer","verifier_input","provenance_source"] if k in r}
    # strip eval-only and overwrite suspicious top-levels
    for k in list(r.keys()):
        lk=k.lower()
        if any(x in lk for x in ["gold","oracle","correct_answer","evaluation_only","label","is_correct"]):
            continue
        if k not in keep and k in ("candidate_nodes","verifier_input"):
            keep[k]=r[k]
    return keep


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--selector-config',required=True)
    ap.add_argument('--input',required=True)
    ap.add_argument('--score-cache',required=True)
    ap.add_argument('--selector-output',required=True)
    ap.add_argument('--final-decision',required=True)
    ap.add_argument('--output-dir',required=True)
    args=ap.parse_args()
    out=Path(args.output_dir); out.mkdir(parents=True,exist_ok=True)
    cfg=json.loads(Path(args.selector_config).read_text())
    records=list(jlines(Path(args.input)))
    casebook=list(jlines(Path(args.selector_output)))
    casebook_map={r['case_id']:r for r in casebook}
    cache=list(jlines(Path(args.score_cache)))

    # cache audit
    failures=[]; cache_join=[]
    keys=[r.get('item_hash') or score_key(r['case_id'],r['candidate_id']) for r in cache]
    dup_keys=sorted({k for k in keys if keys.count(k)>1})
    cache_map={(r.get('item_hash') or score_key(r['case_id'],r['candidate_id'])):r for r in cache}
    cache_tuple={(r['case_id'],r['candidate_id']):r for r in cache}
    # call plan (expected 94)
    call_plan=list(jlines(Path('outputs/outcome_verifier_answer_group_selector_20260501T152447Z/verifier_call_plan.jsonl')))
    used_keys=set(); missing_scores=0
    for it in call_plan:
        k=(it['case_id'],it['candidate_id'])
        used=k in cache_tuple
        used_keys.add((cache_tuple[k].get('item_hash') or score_key(*k)) if used else None)
        if not used: missing_scores+=1
        cache_join.append({'kind':'call_plan_item','case_id':it['case_id'],'candidate_id':it['candidate_id'],'score_key':k,'in_cache':used})

    # reproducibility rerun
    tmp=Path(tempfile.mkdtemp(prefix='selector_repro_'))
    cmd=['python','scripts/run_outcome_verifier_answer_group_selector.py','--input',args.input,'--output-dir',str(tmp),'--selector-name',cfg['selector_name'],'--scorer-mode',cfg['scorer_mode'],'--score-cache',args.score_cache,'--min-verifier-margin',str(cfg['min_verifier_margin']),'--require-trace-for-override','--dedupe-verifier-items','--no-gold-features']
    subprocess.run(cmd,check=True)
    repro_summary=json.loads((tmp/'selector_summary.json').read_text())
    repro_casebook={r['case_id']:r for r in jlines(tmp/'selector_casebook.jsonl')}

    expected={'total_cases':47,'total_overrides':42,'fixes':21,'breaks':0,'net_fixes_minus_breaks':21,'accuracy':0.44680851063829785}
    for k,v in expected.items():
        if repro_summary.get(k)!=v:
            failures.append({'type':'repro_metric_mismatch','metric':k,'expected':v,'actual':repro_summary.get(k)})
    for cid,row in casebook_map.items():
        if repro_casebook.get(cid,{}).get('selected_normalized_answer')!=row.get('selected_normalized_answer'):
            failures.append({'type':'repro_case_mismatch','case_id':cid,'note':'selector-output path does not match selected config run'})

    # leakage audit via sanitized input
    san_path=out/'sanitized_input.jsonl'
    with san_path.open('w',encoding='utf-8') as f:
        for r in records: f.write(json.dumps(sanitize_record(r))+'\n')
    tmp2=Path(tempfile.mkdtemp(prefix='selector_sanitized_'))
    cmd2=cmd.copy(); cmd2[cmd2.index(args.input)]=str(san_path); cmd2[cmd2.index(str(tmp))]=str(tmp2)
    subprocess.run(cmd2,check=True)
    san_casebook={r['case_id']:r for r in jlines(tmp2/'selector_casebook.jsonl')}
    leakage_diffs=[]
    for cid,row in repro_casebook.items():
        b=san_casebook.get(cid,{})
        if b.get('selected_normalized_answer')!=row.get('selected_normalized_answer') or b.get('decision_reason')!=row.get('decision_reason'):
            leakage_diffs.append({'case_id':cid})
    banned_scan={'input_records_banned_hits':sum(len(deep_has_banned(r)) for r in records),
                 'call_plan_banned_hits':sum(len(deep_has_banned(r)) for r in call_plan),
                 'score_rows_banned_hits':sum(len(deep_has_banned(r)) for r in cache)}

    # override audit
    overrides=[]
    for r in repro_casebook.values():
        if not r.get('override'): continue
        case=r['case_id']
        sel_group=r.get('group_scores',{}).get(str(r.get('selected_normalized_answer')),{})
        sel_id=r.get('selected_candidate_id') or sel_group.get('best_candidate_id')
        inp=next(x for x in records if x.get('case_id')==case)
        cands=inp.get('candidate_nodes',[])
        cand={c.get('candidate_id'):c for c in cands}.get(sel_id,{})
        has_trace=bool(sel_group.get('best_candidate_trace_available')) if sel_group else bool(str(cand.get('trace_text','')).strip())
        skey=score_key(case,sel_id)
        sscore=cache_tuple.get((case,sel_id),{}).get('verifier_score')
        ikey=score_key(case,r.get('incumbent_candidate_id','')) if r.get('incumbent_candidate_id') else None
        iscore=cache_tuple.get((case,r.get('incumbent_candidate_id','')),{}).get('verifier_score') if r.get('incumbent_candidate_id') else None
        margin=(sscore-iscore) if isinstance(sscore,(int,float)) and isinstance(iscore,(int,float)) else None
        if cfg['require_trace_for_override'] and has_trace is False:
            failures.append({'type':'override_missing_trace','case_id':case})
        if sscore is None:
            failures.append({'type':'override_missing_score','case_id':case})
        overrides.append({'case_id':case,'dataset':inp.get('dataset'),'example_id':inp.get('example_id'),'provenance_source':inp.get('provenance_source'),'incumbent_normalized_answer':r.get('incumbent_normalized_answer'),'selected_normalized_answer':r.get('selected_normalized_answer'),'selected_candidate_id':sel_id,'selected_score':sscore,'incumbent_score':iscore,'score_margin':margin,'selected_has_trace':has_trace,'fix_break_evaluation_only':{'would_fix':r.get('oracle_selector_would_fix'),'would_break':r.get('oracle_selector_would_break')}})

    # scope audit
    doc=Path('docs/CURRENT_SELECTOR_DECISION.md').read_text(encoding='utf-8').lower()
    scope_ok=('not runtime-promoted' in doc) or ('requires current-correct risk validation' in doc) or ('cannot be fully validated' in doc)
    if not scope_ok: failures.append({'type':'scope_overclaim_doc'})

    summary={
      'audit_passed': len(failures)==0 and len(leakage_diffs)==0 and not dup_keys and missing_scores==0,
      'reproducibility': {'matches_expected_metrics': len([f for f in failures if f['type'].startswith('repro_')])==0,'expected':expected,'actual':{k:repro_summary.get(k) for k in expected}},
      'leakage': {'sanitized_decisions_identical': len(leakage_diffs)==0,'diff_cases':len(leakage_diffs), 'banned_key_scan':banned_scan},
      'cache_join': {'cache_rows':len(cache),'unique_cache_keys':len(set(keys)),'duplicate_cache_keys':len(dup_keys),'call_plan_items':len(call_plan),'missing_call_plan_scores':missing_scores,'unused_cache_rows':len(set(keys)-used_keys)},
      'override_validity': {'overrides':len(overrides),'missing_trace_overrides':len([f for f in failures if f['type']=='override_missing_trace'])},
      'evaluation_correctness': {'fixes':repro_summary.get('fixes'),'breaks':repro_summary.get('breaks')},
      'prompt_hygiene': {'call_plan_has_banned':banned_scan['call_plan_banned_hits']>0,'score_rows_has_banned':banned_scan['score_rows_banned_hits']>0},
      'scope_audit': {'doc_mentions_not_runtime_promoted_or_gap':scope_ok},
    }

    (out/'audit_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    with (out/'audit_summary.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f); w.writerow(['section','key','value'])
        for s,v in summary.items():
            if isinstance(v,dict):
                for k,vv in v.items(): w.writerow([s,k,json.dumps(vv)])
            else: w.writerow(['root',s,json.dumps(v)])
    (out/'audited_overrides.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in overrides),encoding='utf-8')
    (out/'cache_join_audit.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in cache_join),encoding='utf-8')
    (out/'leakage_audit.json').write_text(json.dumps({'diffs':leakage_diffs,'banned_scan':banned_scan},indent=2)+'\n')
    (out/'reproducibility_audit.json').write_text(json.dumps({'expected':expected,'actual':{k:repro_summary.get(k) for k in expected}},indent=2)+'\n')
    (out/'failures_or_warnings.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in failures),encoding='utf-8')
    (out/'audit_report.md').write_text('# Selected selector audit\n\n- Passed: '+str(summary['audit_passed'])+'\n',encoding='utf-8')
    print(out)

if __name__=='__main__':
    main()
