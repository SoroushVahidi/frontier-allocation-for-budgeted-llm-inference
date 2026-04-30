import json,csv,subprocess,sys,tempfile
from pathlib import Path

def _write_artifact(d:Path):
 rows=[
 {'example_id':'e1','dataset':'d','seed':1,'budget':1,'method':'direct_reserve_semantic_frontier_v2','final_answer_canonical':'a','gold_answer_canonical':'b','result_metadata':{'selector_candidate_pool':[{'predicted_answer':'a'},{'predicted_answer':'b'}]}},
 {'example_id':'e1','dataset':'d','seed':1,'budget':1,'method':'external_l1_max','final_answer_canonical':'a','gold_answer_canonical':'b'},
 ]
 (d/'per_example_records.jsonl').write_text('\n'.join(json.dumps(r) for r in rows)+'\n')

def test_casebook_extraction_and_scaffold():
 with tempfile.TemporaryDirectory() as td:
  td=Path(td); art=td/'art'; art.mkdir(); _write_artifact(art)
  tr=td/'t.csv'
  with tr.open('w',newline='') as f:
   w=csv.DictWriter(f,fieldnames=['selector','accuracy','net_fixes_minus_breaks','breaks']);w.writeheader();w.writerow({'selector':'support_only','accuracy':1.0,'net_fixes_minus_breaks':1,'breaks':0});w.writerow({'selector':'oracle_selector','accuracy':1.0,'net_fixes_minus_breaks':1,'breaks':0})
  out=td/'out'
  subprocess.check_call([sys.executable,'scripts/build_verifier_design_casebook.py','--artifact-dir',str(art),'--tournament-results',str(tr),'--out-dir',str(out)])
  assert (out/'verifier_design_casebook.csv').exists()
  scores=td/'scores.csv'
  with scores.open('w',newline='') as f:
   w=csv.DictWriter(f,fieldnames=['example_id','candidate_answer','score']);w.writeheader();w.writerow({'example_id':'e1','candidate_answer':'a','score':0.2});w.writerow({'example_id':'e1','candidate_answer':'b','score':0.9})
  sout=td/'sout'
  subprocess.check_call([sys.executable,'scripts/analyze_outcome_verifier_selector_scaffold.py','--artifact-dir',str(art),'--scores-csv',str(scores),'--margin','0.1','--out-dir',str(sout)])
  s=json.loads((sout/'verifier_selector_scaffold_summary.json').read_text())
  assert s['accuracy']==1.0 and s['fixes']==1
