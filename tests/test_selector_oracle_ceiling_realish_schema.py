import json, subprocess, sys
from pathlib import Path

def test_oracle_accepts_realish_schema():
    p='tests/fixtures/selector_oracle_realish/per_example_records.jsonl'
    subprocess.check_call([sys.executable,'scripts/analyze_selector_oracle_ceiling.py','--artifact-dir',p])
    s=json.loads((Path(p).parent/'selector_oracle_ceiling_summary.json').read_text())
    assert s['total_scored_examples']==1
    assert s['oracle_selector_accuracy']>=1.0
