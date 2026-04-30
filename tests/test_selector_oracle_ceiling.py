import json, subprocess, sys
from pathlib import Path

FIX='tests/fixtures/selector_oracle_synth/per_example_records.jsonl'

def test_oracle_script_synth(tmp_path):
    out=tmp_path/'diag'; out.mkdir()
    subprocess.check_call([sys.executable,'scripts/analyze_selector_oracle_ceiling.py','--artifact-dir',FIX])
    # output written beside input path
    ad=Path(FIX).parent
    s=json.loads((ad/'selector_oracle_ceiling_summary.json').read_text())
    assert s['total_scored_examples']==3
    assert s['present_not_selected_loss_count']>=1
    assert s['absent_from_pool_loss_count']>=1
    assert s['oracle_selector_accuracy']>=s['dr_v2_accuracy']
