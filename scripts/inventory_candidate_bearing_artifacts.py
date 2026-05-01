#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, json
from pathlib import Path
from typing import Any

CAND_KEYS=["candidate_nodes","candidates","candidates_for_verifier","answer_candidates","selector_candidate_pool","final_branch_states","branch_states","branch_records","terminal_nodes","nodes","answer_groups","all_answer_groups","discovered_answer_groups","result_metadata","per_example_records","traces","trace_records"]
TRACE_KEYS=["trace_text","step_text","reasoning_trace","reasoning_steps","steps","derivation","solution_trace","trace","rationale","full_text","messages","completion","output_text","reasoning"]
ANS_KEYS=["final_answer","answer","normalized_answer","selected_answer","predicted_answer","output_answer","parsed_answer","extracted_answer","final"]
JOIN_KEYS=["case_id","example_id","dataset","seed","budget","our_method_name","source_artifact_path"]


def safe(v:Any,k:str=""):
    lk=k.lower()
    if any(x in lk for x in ["token","secret","api_key","credential","gold_answer","oracle"]):
        if isinstance(v,str): return {"type":"str","length":len(v),"preview":"[REDACTED]"}
        return {"type":type(v).__name__}
    if isinstance(v,str): return {"type":"str","length":len(v),"preview":v[:80]}
    if isinstance(v,list): return {"type":"list","length":len(v)}
    if isinstance(v,dict): return {kk:safe(vv,kk) for kk,vv in list(v.items())[:20]}
    return {"type":type(v).__name__}


def iter_records(p:Path,max_records:int):
    if p.suffix=='.jsonl':
        out=[]
        for i,l in enumerate(p.read_text(errors='ignore').splitlines()):
            if i>=max_records: break
            if l.strip():
                try: out.append(json.loads(l))
                except: pass
        return out
    if p.suffix=='.json':
        try:
            o=json.loads(p.read_text(errors='ignore'))
            if isinstance(o,list): return o[:max_records]
            if isinstance(o,dict): return [o]
        except: pass
    if p.suffix=='.csv':
        with p.open(errors='ignore') as f:
            r=csv.DictReader(f)
            return [x for _,x in zip(range(max_records),r)]
    return []


def scan(obj:Any,path:str=""):
    cand=[]; trace=set(); ans=set(); keys=set(); joins=set(); cand_objs=0
    if isinstance(obj,dict):
        keys|=set(obj.keys())
        for k,v in obj.items():
            p=f"{path}.{k}" if path else k
            lk=k.lower()
            if any(x in lk for x in CAND_KEYS) and isinstance(v,list):
                cand.append((p,len(v)))
                cand_objs+=sum(1 for z in v if isinstance(z,dict))
            if k in TRACE_KEYS: trace.add(k)
            if k in ANS_KEYS: ans.add(k)
            if k in JOIN_KEYS: joins.add(k)
            c,t,a,ks,j,co=scan(v,p); cand+=c; trace|=t; ans|=a; keys|=ks; joins|=j; cand_objs+=co
    elif isinstance(obj,list):
        for v in obj[:5]:
            c,t,a,ks,j,co=scan(v,path+'[]'); cand+=c; trace|=t; ans|=a; keys|=ks; joins|=j; cand_objs+=co
    return cand,trace,ans,keys,joins,cand_objs


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--roots', nargs='+', required=True)
    ap.add_argument('--output-dir', required=True)
    ap.add_argument('--max-files', type=int, default=5000)
    ap.add_argument('--max-records-per-file', type=int, default=20)
    ap.add_argument('--safe-preview', action='store_true', default=True)
    a=ap.parse_args()
    out=Path(a.output_dir); out.mkdir(parents=True, exist_ok=False)
    files=[]
    for r in a.roots:
        rp=Path(r)
        if not rp.exists():
            files.append({"path":str(rp),"exists":False});continue
        for p in rp.rglob('*'):
            if p.suffix in {'.json','.jsonl','.csv'} and p.is_file():
                files.append({"path":str(p),"exists":True})
            if len(files)>=a.max_files: break
    rows=[]; top=[]
    for f in files:
        if not f.get('exists'):
            rows.append(f); continue
        p=Path(f['path']); recs=iter_records(p,a.max_records_per_file)
        cand=[]; trace=set(); ans=set(); keys=set(); joins=set(); cand_objs=0
        for r in recs:
            c,t,aa,ks,j,co=scan(r)
            cand+=c; trace|=t; ans|=aa; keys|=ks; joins|=j; cand_objs+=co
        likely=bool(cand or cand_objs>0)
        row={"path":str(p),"exists":True,"size":p.stat().st_size,"sampled_records":len(recs),"top_level_keys_seen":sorted(list(keys))[:80],"candidate_like_paths":cand[:50],"total_sampled_candidate_objects":cand_objs,"trace_like_fields":sorted(trace),"final_answer_like_fields":sorted(ans),"join_keys":sorted(joins),"likely_candidate_bearing":likely,"safe_for_unified_selector_evidence":likely}
        rows.append(row)
        if likely: top.append({"path":str(p),"sample_preview":safe(recs[0]) if recs else {}})
    inv={"roots":a.roots,"files":rows,"conclusion":"no_candidate_artifact_found_for_new_cap100_in_scanned_roots"}
    (out/'candidate_artifact_inventory.json').write_text(json.dumps(inv,indent=2),encoding='utf-8')
    with (out/'candidate_artifact_inventory.csv').open('w',newline='',encoding='utf-8') as fh:
        w=csv.writer(fh); w.writerow(['path','exists','size','sampled_records','total_sampled_candidate_objects','likely_candidate_bearing'])
        for r in rows:w.writerow([r.get('path'),r.get('exists'),r.get('size'),r.get('sampled_records'),r.get('total_sampled_candidate_objects'),r.get('likely_candidate_bearing')])
    (out/'candidate_artifact_inventory_top_candidates.jsonl').write_text('\n'.join(json.dumps(x) for x in top)+'\n',encoding='utf-8')
    rep=['# Candidate Artifact Inventory', '', f"Scanned files: {len(rows)}", f"Likely candidate-bearing files: {sum(1 for r in rows if r.get('likely_candidate_bearing'))}"]
    (out/'candidate_artifact_inventory_report.md').write_text('\n'.join(rep),encoding='utf-8')

if __name__=='__main__':
    main()
