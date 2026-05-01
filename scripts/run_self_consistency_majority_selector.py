#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, json, sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.self_consistency_majority_selector import select_self_consistency_answer, evaluate_self_consistency_case, normalize_gsm8k_numeric_answer


def _read_jsonl(p: Path):
    return [json.loads(x) for x in p.read_text(encoding='utf-8').splitlines() if x.strip()]


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--input', required=True)
    ap.add_argument('--output-dir', required=True)
    ap.add_argument('--selector-name', default='self_consistency_majority_selector_v1')
    ap.add_argument('--dataset', default='gsm8k')
    ap.add_argument('--no-gold-features', action='store_true')
    ap.add_argument('--paired-mode', action='store_true')
    ap.add_argument('--require-candidate-nodes', action='store_true')
    args=ap.parse_args()

    rows=_read_jsonl(Path(args.input))
    out=Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)

    casebook=[]; vote_rows=[]; invalid_rows=[]
    for i,r in enumerate(rows):
        nodes=r.get('candidate_nodes') or []
        if args.require_candidate_nodes and not nodes:
            continue
        d=select_self_consistency_answer(nodes)
        e=evaluate_self_consistency_case(r,d)
        inc = normalize_gsm8k_numeric_answer(r.get('selected_answer_canonical') or r.get('final_answer_canonical') or r.get('selected_normalized_answer') or '')
        rec={"case_index":i,"case_id":r.get('case_id') or f"case_{i}","selector_name":args.selector_name,"incumbent_answer":inc,**d,**e}
        casebook.append(rec)
        vote_rows.append({"case_index":i,"case_id":rec['case_id'],"answer_vote_histogram":d['answer_vote_histogram'],"tied_answers":d['tied_answers']})
        if d['all_invalid']:
            invalid_rows.append({"case_index":i,"case_id":rec['case_id'],"reason":"all_invalid"})

    total=len(casebook)
    total_cands=sum(len((r.get('candidate_nodes') or [])) for r in rows)
    valid_answers=sum(r['valid_vote_count'] for r in casebook)
    invalid_answers=sum(r['invalid_candidate_count'] for r in casebook)
    ties=sum(1 for r in casebook if r['tie_flag'])
    overrides=sum(1 for r in casebook if r['selected_normalized_answer']!=r['incumbent_answer'])
    fixes=sum(1 for r in casebook if r['fix'])
    breaks=sum(1 for r in casebook if r['break'])
    sel_acc=sum(1 for r in casebook if r['self_consistency_correct'])/max(1,total)
    cur_acc=sum(1 for r in casebook if r['current_correct'])/max(1,total)

    summary={"selector_name":args.selector_name,"dataset":args.dataset,"total_cases":total,
    "cases_with_candidate_nodes":sum(1 for r in rows if (r.get('candidate_nodes') or [])),"cases_all_invalid":sum(1 for r in casebook if r['all_invalid']),
    "total_candidates":total_cands,"valid_candidate_answers":valid_answers,"invalid_candidate_answers":invalid_answers,
    "valid_answer_rate":valid_answers/max(1,valid_answers+invalid_answers),"average_unique_answer_count":sum(r['unique_answer_count'] for r in casebook)/max(1,total),
    "tie_cases":ties,"tie_rate":ties/max(1,total),"average_selected_vote_share":sum(r['vote_share'] for r in casebook)/max(1,total),
    "current_incumbent_accuracy":cur_acc,"self_consistency_accuracy":sel_acc,"override_count":overrides,"fixes":fixes,"breaks":breaks,
    "net_fixes_minus_breaks":fixes-breaks,"override_precision":fixes/max(1,overrides),
    "oracle_pool_accuracy":None,"gold_present_in_candidate_pool":None,
    "gold_present_but_not_selected":None,"gold_absent_from_candidate_pool":None}

    (out/'manifest.json').write_text(json.dumps({"timestamp":datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'),"input":args.input,"selector_name":args.selector_name},indent=2)+"\n")
    (out/'selector_summary.json').write_text(json.dumps(summary,indent=2)+"\n")
    with (out/'selector_summary.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f); w.writerow(['metric','value']); [w.writerow([k,v]) for k,v in summary.items()]
    (out/'selector_casebook.jsonl').write_text(''.join(json.dumps(r)+"\n" for r in casebook),encoding='utf-8')
    with (out/'selector_casebook.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(casebook[0].keys()) if casebook else ['case_index']); w.writeheader(); w.writerows(casebook)
    (out/'vote_histograms.jsonl').write_text(''.join(json.dumps(r)+"\n" for r in vote_rows),encoding='utf-8')
    (out/'invalid_or_unparsable_candidates.jsonl').write_text(''.join(json.dumps(r)+"\n" for r in invalid_rows),encoding='utf-8')
    (out/'selector_report.md').write_text(f"# Self-consistency majority selector\n\n- total cases: {total}\n- accuracy: {sel_acc:.3f}\n- incumbent accuracy: {cur_acc:.3f}\n- tie rate: {summary['tie_rate']:.3f}\n",encoding='utf-8')
    print(out)

if __name__=='__main__':
    main()
