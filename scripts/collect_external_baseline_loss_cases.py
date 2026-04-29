#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = REPO_ROOT / "outputs"

EXTERNAL_FAMILY_MAP = {
    "external_l1_max": "direct_length_control",
    "external_l1_exact": "direct_length_control",
    "tale": "token_budgeting",
    "external_tale_prompt_budgeting": "token_budgeting",
    "s1": "budget_forcing",
    "external_s1_budget_forcing": "budget_forcing",
    "self_consistency_3": "self_consistency",
    "self_consistency_5": "self_consistency",
    "tot_beam_matched_budget": "tot_search",
    "tot_bfs_matched_budget": "tot_search",
    "tot_dfs_matched_budget": "tot_search",
}
INTERNAL_METHODS = {
    "strict_f3",
    "strict_gate1_cap_k6",
    "strict_f3_anti_collapse_weak_v1",
    "direct_reserve_semantic_frontier_v2",
    "direct_reserve_semantic_frontier_v2_selection_fix_v1",
    "direct_reserve_frontier_gate_v1",
}

@dataclass
class Case:
    run_dir:str; source_kind:str; provider:str; model:str; dataset:str; seed:str; budget:str; example_id:str; method:str; exact:int; trace:bool


def _scan_dirs(extra:list[str]) -> list[Path]:
    pats=["cohere_real_model_cost_normalized_validation_*","cohere_direct_reserve_v2_vs_external_l1_local_validation_*","semantic_diversity_controller_diagnostic_*","openai_real_model_main_run_audit_*","cohere_real_model_main_run_audit_*","cross_provider_real_model_main_run_audit_*","real_model_decision_package_*"]
    out=[]
    for p in pats:
        out.extend(sorted(OUTPUTS.glob(p)))
    for x in extra:
        px=Path(x)
        root = px if px.is_absolute() else REPO_ROOT/px
        if (root / "per_example_records.jsonl").exists():
            out.append(root)
        else:
            out.extend(sorted(p.parent for p in root.rglob("per_example_records.jsonl")))
    seen=[]
    for d in out:
        if d.is_dir() and d not in seen:
            seen.append(d)
    return seen


def _load_records(run_dir:Path, source_kind:str)->list[Case]:
    p=run_dir/"per_example_records.jsonl"
    if not p.exists():
        return []
    trace_idx={}
    t=run_dir/"per_case_trace_index.csv"
    if t.exists():
        with t.open() as f:
            for r in csv.DictReader(f):
                key=(r.get("example_id",""),r.get("method",""),str(r.get("budget","")),str(r.get("seed","")),r.get("provider",""))
                trace_idx[key]=str(r.get("trace_available","")).lower()=="true"
    cases=[]
    with p.open() as f:
        for line in f:
            d=json.loads(line)
            method=d.get("method","")
            if method not in INTERNAL_METHODS and method not in EXTERNAL_FAMILY_MAP and "verifier" not in method and "route" not in method:
                continue
            key=(d.get("example_id",""),method,str(d.get("budget","")),str(d.get("seed","")),d.get("provider",""))
            trace=trace_idx.get(key,False)
            cases.append(Case(run_dir.name,source_kind,d.get("provider",""),d.get("model",""),d.get("dataset",""),str(d.get("seed","")),str(d.get("budget","")),d.get("example_id",""),method,int(d.get("exact_match",0) or 0),trace))
    return cases


def _classify_failure(int_trace:bool, ext_trace:bool, ext_method:str)->str:
    if EXTERNAL_FAMILY_MAP.get(ext_method)=="direct_length_control":
        return "external_direct_advantage"
    if not (int_trace or ext_trace):
        return "unknown_no_trace"
    if int_trace and not ext_trace:
        return "trace_missing_unclassifiable"
    return "present_not_selected"


def main()->None:
    ap=argparse.ArgumentParser()
    ap.add_argument("--output-dir")
    ap.add_argument("--extra-input-dir",action="append",default=[])
    args=ap.parse_args()
    ts=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    out=(Path(args.output_dir) if args.output_dir else OUTPUTS/f"external_baseline_loss_case_collection_{ts}").resolve()
    out.mkdir(parents=True,exist_ok=True)

    dirs=_scan_dirs(args.extra_input_dir)
    all_cases=[]
    for d in dirs:
        kind="live" if "external_baseline_loss_case_live_collection_" in d.name else "existing"
        all_cases.extend(_load_records(d,kind))

    grouped=defaultdict(dict)
    for c in all_cases:
        k=(c.provider,c.model,c.dataset,c.seed,c.budget,c.example_id,c.run_dir,c.source_kind)
        grouped[k][c.method]=c

    ext_win=[]; paired=[]
    by_method=Counter(); by_family=Counter(); by_fail=Counter(); hardest=Counter()
    for k,mm in grouped.items():
        ints=[m for m in mm if m in INTERNAL_METHODS]
        exts=[m for m in mm if m in EXTERNAL_FAMILY_MAP or "verifier" in m or "route" in m]
        for i in ints:
            for e in exts:
                ic,ec=mm[i],mm[e]
                paired.append({"provider":k[0],"model":k[1],"dataset":k[2],"seed":k[3],"budget":k[4],"example_id":k[5],"run_dir":k[6],"source_kind":k[7],"internal_method":i,"external_method":e,"external_family":EXTERNAL_FAMILY_MAP.get(e,"other_external"),"internal_exact":ic.exact,"external_exact":ec.exact,"external_win":int(ec.exact>ic.exact),"trace_available":int(ic.trace or ec.trace)})
                if ec.exact>ic.exact:
                    ft=_classify_failure(ic.trace,ec.trace,e)
                    row=paired[-1]|{"failure_type":ft}
                    ext_win.append(row)
                    by_method[i]+=1; by_family[row["external_family"]]+=1; by_fail[ft]+=1; hardest[e]+=1

    def wcsv(name,rows,fields):
        with (out/name).open("w",newline="") as f:
            w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

    wcsv("paired_case_matrix.csv",paired,list(paired[0].keys()) if paired else ["provider"])
    wcsv("external_win_cases.csv",ext_win,list(ext_win[0].keys()) if ext_win else ["provider"])
    wcsv("loss_case_summary_by_method.csv",[{"internal_method":k,"external_win_cases":v} for k,v in by_method.items()],["internal_method","external_win_cases"])
    wcsv("loss_case_summary_by_external_family.csv",[{"external_family":k,"external_win_cases":v} for k,v in by_family.items()],["external_family","external_win_cases"])
    wcsv("loss_case_summary_by_failure_type.csv",[{"failure_type":k,"count":v} for k,v in by_fail.items()],["failure_type","count"])
    wcsv("hardest_external_baselines_ranked.csv",[{"external_method":k,"external_win_cases":v} for k,v in hardest.most_common()],["external_method","external_win_cases"])

    cov={"external_l1_max":0,"tale_or_s1":0,"self_consistency_or_tot":0,"traced_external_win":0}
    for p in paired:
        m=p["external_method"]
        if m=="external_l1_max": cov["external_l1_max"]+=1
        if m in {"tale","external_tale_prompt_budgeting","s1","external_s1_budget_forcing"}: cov["tale_or_s1"]+=1
        if m.startswith("self_consistency") or m.startswith("tot_"): cov["self_consistency_or_tot"]+=1
    cov["traced_external_win"]=sum(1 for e in ext_win if e["trace_available"]==1)
    gap=[{"metric":k,"count":v,"threshold":t,"meets_threshold":int(v>=t)} for k,v,t in [("external_l1_max",cov["external_l1_max"],50),("tale_or_s1",cov["tale_or_s1"],20),("self_consistency_or_tot",cov["self_consistency_or_tot"],20),("traced_external_win",cov["traced_external_win"],20)]]
    wcsv("baseline_family_gap_report.csv",gap,["metric","count","threshold","meets_threshold"])

    with (out/"top_loss_case_examples.md").open("w") as f:
        f.write("# Top external-win loss cases\n\n")
        for r in ext_win[:20]:
            f.write(f"- {r['example_id']}: {r['external_method']} beat {r['internal_method']} ({r['external_exact']}>{r['internal_exact']}); failure_type={r['failure_type']}\\n")

    manifest={"created_at":datetime.now(timezone.utc).isoformat(),"input_dirs":[str(d.relative_to(REPO_ROOT)) if str(d).startswith(str(REPO_ROOT)) else str(d) for d in dirs],"output_dir":str(out.relative_to(REPO_ROOT)) if str(out).startswith(str(REPO_ROOT)) else str(out),"counts":{"paired_cases":len(paired),"external_win_cases":len(ext_win)},"coverage":cov}
    (out/"loss_case_collection_manifest.json").write_text(json.dumps(manifest,indent=2))
    print(out)

if __name__=="__main__": main()
