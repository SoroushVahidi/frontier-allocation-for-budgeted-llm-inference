import csv, json
from pathlib import Path
from scripts.analyze_offline_selector_variants import load_cases, select

ART=Path('outputs/cohere_real_model_cost_normalized_validation_20260430T_TRACE_COMPLETE_30CASE_COHERE_REGEN/per_example_records.jsonl')

def test_paths_match_on_active_artifact_if_present():
    if not ART.exists():
        return
    rows=[json.loads(l) for l in ART.read_text().splitlines() if l.strip()]
    cases=load_cases(rows)
    n=len(cases)
    assert n>0
    sup=sum(int(select('support_only',c)==c['gold']) for c in cases)/n
    ora=sum(int(select('oracle_selector',c)==c['gold']) for c in cases)/n
    grd=sum(int(select('support_only_with_guard_v1',c)==c['gold']) for c in cases)/n
    acc=Path('outputs/cohere_real_model_cost_normalized_validation_20260430T_TRACE_COMPLETE_30CASE_COHERE_REGEN/diagnostics/conservative_outcome_verifier_override_v1/accuracy_table.csv')
    if not acc.exists():
        return
    m={r['method']:float(r['accuracy']) for r in csv.DictReader(acc.open())}
    assert m['support_only']==sup
    assert m['oracle_selector_ceiling_over_candidates']==ora
    assert m['support_only_with_guard_v1']==grd
