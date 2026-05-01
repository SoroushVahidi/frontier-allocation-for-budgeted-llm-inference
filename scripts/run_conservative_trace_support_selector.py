#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json,sys
from datetime import datetime,timezone
from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from experiments.conservative_trace_support_selector import select_case,evaluate_case

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--input',required=True)
    ap.add_argument('--output-dir',required=True)
    ap.add_argument('--selector-name',default='conservative_trace_support_selector_v1')
    ap.add_argument('--min-support-margin',type=int,default=1)
    ap.add_argument('--require-trace-for-override',action='store_true')
    ap.add_argument('--prefer-source-diversity',action='store_true')
    ap.add_argument('--no-gold-features',action='store_true')
    args=ap.parse_args()

    rows=[json.loads(x) for x in Path(args.input).read_text(encoding='utf-8').splitlines() if x.strip()]
    out=Path(args.output_dir); out.mkdir(parents=True,exist_ok=True)
    casebook=[]
    reasons={}
    for i,case in enumerate(rows):
        d=select_case(case,selector_name=args.selector_name,min_support_margin=args.min_support_margin,require_trace_for_override=args.require_trace_for_override,prefer_source_diversity=args.prefer_source_diversity,no_gold_features=args.no_gold_features)
        e=evaluate_case(case,d)
        rec={"case_index":i,**d,**e}
        casebook.append(rec)
        reasons[d['decision_reason']]=reasons.get(d['decision_reason'],0)+1

    total=len(casebook)
    overrides=sum(1 for r in casebook if r['override'])
    fixes=sum(1 for r in casebook if r['fix'])
    breaks=sum(1 for r in casebook if r['break'])
    sel_acc=sum(1 for r in casebook if r['selector_correct'])/max(1,total)
    cur_acc=sum(1 for r in casebook if r['current_correct'])/max(1,total)

    def _ev(case):
        return case.get('evaluation_only') or {}

    recoverable=sum(1 for c in rows if bool(c.get('gold_in_extracted_terminal_node_finals')))
    aggregate_only=sum(
        1 for c in rows
        if bool(c.get('gold_in_aggregate_answer_groups')) and not bool(c.get('gold_in_extracted_terminal_node_finals'))
    )
    oracle= recoverable / max(1,total)
    recov=sum(1 for r,c in zip(casebook,rows) if bool(c.get('gold_in_extracted_terminal_node_finals')) and r['selector_correct'])
    gold_in_terminal_fail=sum(1 for r,c in zip(casebook,rows) if bool(c.get('gold_in_extracted_terminal_node_finals')) and (not r['selector_correct']))
    summary={"timestamp":datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'),"selector_name":args.selector_name,
        "total_cases":total,"total_overrides":overrides,"fixes":fixes,"breaks":breaks,"net_fixes_minus_breaks":fixes-breaks,
        "override_precision":(fixes/max(1,overrides)),"accuracy":sel_acc,"current_incumbent_accuracy":cur_acc,
        "oracle_ceiling_on_package":oracle,"recoverable_trace_terminal_cases":recoverable,
        "recoveries_among_gold_in_terminal_node_cases":recov,"failures_gold_present_in_terminal_nodes_not_chosen":gold_in_terminal_fail,
        "aggregate_only_cases_count":aggregate_only,"decision_reasons":reasons}

    (out/'selector_summary.json').write_text(json.dumps(summary,indent=2)+"\n",encoding='utf-8')
    with (out/'selector_summary.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(summary.keys())); w.writeheader(); w.writerow(summary)
    with (out/'selector_casebook.jsonl').open('w',encoding='utf-8') as f:
        for r in casebook: f.write(json.dumps(r)+"\n")
    with (out/'selector_casebook.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(casebook[0].keys()) if casebook else ['case_index']); w.writeheader(); w.writerows(casebook)
    report=["# Conservative trace-support selector report","",f"- selector: `{args.selector_name}`",f"- input: `{args.input}`",f"- cases: {total}","","> Note: this package is a present-not-selected recovery benchmark; it does not measure runtime break risk.","",f"- overrides: {overrides}",f"- fixes: {fixes}",f"- breaks: {breaks}",f"- accuracy: {sel_acc:.3f}",f"- incumbent accuracy: {cur_acc:.3f}"]
    (out/'selector_report.md').write_text("\n".join(report)+"\n",encoding='utf-8')
    print(out)

if __name__=='__main__':
    main()
