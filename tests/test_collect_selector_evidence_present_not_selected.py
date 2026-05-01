from __future__ import annotations
import csv, json, subprocess, sys
from pathlib import Path


def _write_csv(path: Path, rows: list[dict[str,str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)


def test_collect_selector_evidence_fixture(tmp_path: Path) -> None:
    rows = [
        dict(dataset='openai/gsm8k',example_id='a',problem_statement='Q1',our_method_name='direct_reserve_semantic_frontier_v2',external_method_name='external_l1_max',our_correct='0',external_correct='1',gold_answer='10',all_candidate_answer_groups='["10","11"]',our_metadata_json='{}'),
        dict(dataset='openai/gsm8k',example_id='b',problem_statement='Q2',our_method_name='direct_reserve_semantic_frontier_v2',external_method_name='external_l1_max',our_correct='0',external_correct='1',gold_answer='22',all_candidate_answer_groups='["22","21"]',our_metadata_json=json.dumps({'final_branch_states':[{'branch_id':'x','final_answer':'22','trace':'t'}]})),
        dict(dataset='openai/gsm8k',example_id='c',problem_statement='Q3',our_method_name='direct_reserve_semantic_frontier_v2',external_method_name='external_l1_max',our_correct='0',external_correct='1',gold_answer='33',all_candidate_answer_groups='["31","32"]',our_metadata_json='{}'),
        dict(dataset='openai/gsm8k',example_id='d',problem_statement='Q4',our_method_name='direct_reserve_semantic_frontier_v2',external_method_name='external_l1_max',our_correct='1',external_correct='1',gold_answer='44',all_candidate_answer_groups='["44","45"]',our_metadata_json=json.dumps({'final_branch_states':[{'branch_id':'y','final_answer':'44','trace':'ok'}]})),
    ]
    _write_csv(tmp_path/'outputs'/'external_loss_casebook_broad_20260430T185500Z'/'loss_casebook_trace_complete.csv', rows)
    out = tmp_path/'outputs'/'selector_evidence_package_test'
    cmd=[sys.executable,'scripts/collect_selector_evidence_present_not_selected.py','--roots',str(tmp_path/'outputs'),'--output-dir',str(out),'--include-current-correct-risk-cases']
    subprocess.run(cmd, check=True, cwd=Path(__file__).resolve().parents[1])

    summary = json.loads((out/'selector_evidence_summary.json').read_text())
    assert summary['present-not-selected aggregate rows'] == 2
    assert summary['absent-from-tree rows'] == 1
    assert summary['gold present in extracted terminal node finals'] == 2
    assert summary['current-correct cases available for break-risk testing'] == 1

    enriched_lines=[json.loads(x) for x in (out/'candidate_trace_enriched.jsonl').read_text().splitlines() if x.strip()]
    assert len(enriched_lines)==2
    for obj in enriched_lines:
        assert 'gold_answer' not in json.dumps(obj['verifier_input'])

    missing = json.loads((out/'missing_artifacts.json').read_text())
    assert any(m['artifact']=='per_example_records.jsonl' for m in missing)
