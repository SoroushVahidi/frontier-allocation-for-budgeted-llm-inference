from __future__ import annotations
import json, subprocess, sys
from pathlib import Path


def jwrite(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in rows)+"\n", encoding="utf-8")


def test_recovery_script_synthetic(tmp_path: Path) -> None:
    case = {
        'case_id':'c1','dataset':'openai/gsm8k','example_id':'e1','seed':'11','budget':'4','our_method_name':'direct_reserve_semantic_frontier_v2',
        'problem_statement':'Q','gold_answer':'10','selected_answer_group':'11','all_candidate_answer_groups':'["10","11"]','gold_present_in_candidate_groups':True
    }
    casebook = tmp_path/'casebook.jsonl'; jwrite(casebook,[case, dict(case)|{'case_id':'missing','example_id':'e2'}])
    rec = {'dataset':'openai/gsm8k','example_id':'e1','seed':11,'budget':4,'method':'direct_reserve_semantic_frontier_v2','question':'Q',
           'result_metadata':{'selector_candidate_pool':[{'branch_id':'b1','final_answer':'10','trace':'step a','source':'sf1'},{'branch_id':'b2','final_answer':'11','steps':['x'],'source':'sf2'}]}}
    jwrite(tmp_path/'src'/'per_example_records.jsonl',[rec])
    out=tmp_path/'out'
    subprocess.run([sys.executable,'scripts/recover_selector_evidence_traces.py','--casebook',str(casebook),'--source-root',str(tmp_path/'src'),'--output-dir',str(out),'--max-cases','50'],check=True,cwd=Path(__file__).resolve().parents[1])
    summ=json.loads((out/'trace_recovery_summary.json').read_text())
    assert summ['input cases']==2 and summ['raw records matched']==1 and summ['raw records missing']==1
    assert summ['cases with candidate nodes']==1 and summ['cases with at least one candidate trace']==1
    enr=[json.loads(x) for x in (out/'candidate_trace_enriched.jsonl').read_text().splitlines() if x.strip()]
    assert len(enr)==1
    txt=json.dumps(enr[0]['verifier_input'])
    assert 'gold' not in txt.lower() and 'oracle' not in txt.lower()
    assert enr[0]['gold_in_extracted_terminal_node_finals'] is True
