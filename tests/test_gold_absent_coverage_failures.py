import json, subprocess, sys

def test_gold_absent_coverage_script(tmp_path):
    p=tmp_path/'per_example_records.jsonl'
    rows=[
        {"example_id":"e1","dataset":"d","seed":1,"budget":4,"method":"external_l1_max","gold_answer_canonical":"10","final_answer_canonical":"10"},
        {"example_id":"e1","dataset":"d","seed":1,"budget":4,"method":"direct_reserve_semantic_frontier_v2","gold_answer_canonical":"10","final_answer_canonical":"7","result_metadata":{"selector_candidate_pool":[{"predicted_answer":"7","source":"direct_reserve"}]}},
    ]
    p.write_text("\n".join(json.dumps(r) for r in rows)+"\n")
    out=tmp_path/'out'
    subprocess.check_call([sys.executable,'scripts/analyze_gold_absent_coverage_failures.py','--artifact',str(p),'--output-dir',str(out),'--method','direct_reserve_semantic_frontier_v2'])
    s=json.loads((out/'gold_absent_coverage_summary.json').read_text())
    assert s['total_scored_examples']==1
    m=s['methods']['direct_reserve_semantic_frontier_v2']
    assert m['l1_correct_ours_wrong']==1
    assert m['gold_absent']==1
