import csv, subprocess, sys
from pathlib import Path

def test_schema_audit_runs_and_classifies(tmp_path):
    subprocess.check_call([sys.executable,'scripts/audit_selector_artifact_schema.py','--output-root',str(tmp_path)])
    d=next(tmp_path.glob('selector_artifact_schema_audit_*/selector_artifact_schema_audit.csv'))
    rows=list(csv.DictReader(d.open()))
    assert len(rows)>=1
    assert all(r['artifact_class'] in {'usable_now','schema_adaptable','final_rows_only','not_scored_or_empty','unknown_needs_manual_inspection'} for r in rows)
