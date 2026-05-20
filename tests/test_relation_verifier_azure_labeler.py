"""Tests for the Azure OpenAI RelationReady assisted labeler."""

import csv
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = 'scripts/run_relation_verifier_azure_labeler.py'

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def write_csv(path, rows, fieldnames=None):
    if not rows:
        return
    if fieldnames is None:
        fieldnames = list(rows[0].keys())
    with Path(path).open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_jsonl(path):
    rows = []
    p = Path(path)
    if not p.exists():
        return rows
    with p.open(encoding='utf-8') as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def run_script(args, expect_success=True, env=None):
    result = subprocess.run(
        [sys.executable, SCRIPT] + args,
        capture_output=True,
        text=True,
        env=env,
    )
    if expect_success:
        assert result.returncode == 0, (
            f'Script failed.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}'
        )
    return result


_FIELDNAMES = [
    'row_id', 'problem_id', 'case_id', 'candidate_source',
    'question', 'target_phrase', 'candidate_answer', 'candidate_trace_short',
    'source_artifact', 'trace_quality_flags',
    'is_correct_offline_metadata',
    'relation_ready_label_manual', 'first_error_axis_manual', 'notes_manual',
]


def _make_row(row_id, labeled=False, label='ready', gold='yes'):
    return {
        'row_id': row_id,
        'problem_id': f'prob_{row_id}',
        'case_id': f'case_{row_id}',
        'candidate_source': 'pal_seed_0',
        'question': 'How many apples are left after eating 3 of 10?',
        'target_phrase': 'apples left',
        'candidate_answer': '7',
        'candidate_trace_short': 'apples_left = 10 - 3',
        'source_artifact': 'some/artifact',
        'trace_quality_flags': 'has_code|has_arithmetic|answer_present',
        'is_correct_offline_metadata': gold,
        'relation_ready_label_manual': label if labeled else '',
        'first_error_axis_manual': '' if labeled else '',
        'notes_manual': '',
    }


def _make_csv(tmp_path, rows):
    p = tmp_path / 'input.csv'
    write_csv(p, rows, fieldnames=_FIELDNAMES)
    return p


# ---------------------------------------------------------------------------
# dry_run — basic output files
# ---------------------------------------------------------------------------

def test_dry_run_creates_output_dir(tmp_path):
    csv_path = _make_csv(tmp_path, [_make_row('rrpool_001')])
    out = tmp_path / 'nested' / 'output'
    run_script(['--input-csv', str(csv_path), '--output-dir', str(out), '--mode', 'dry_run'])
    assert out.exists()


def test_dry_run_writes_requests_jsonl(tmp_path):
    csv_path = _make_csv(tmp_path, [_make_row('rrpool_001')])
    out = tmp_path / 'output'
    run_script(['--input-csv', str(csv_path), '--output-dir', str(out), '--mode', 'dry_run'])
    assert (out / 'azure_label_requests.jsonl').exists()


def test_dry_run_writes_manifest(tmp_path):
    csv_path = _make_csv(tmp_path, [_make_row('rrpool_001')])
    out = tmp_path / 'output'
    run_script(['--input-csv', str(csv_path), '--output-dir', str(out), '--mode', 'dry_run'])
    assert (out / 'run_manifest.json').exists()


def test_dry_run_writes_label_summary(tmp_path):
    csv_path = _make_csv(tmp_path, [_make_row('rrpool_001')])
    out = tmp_path / 'output'
    run_script(['--input-csv', str(csv_path), '--output-dir', str(out), '--mode', 'dry_run'])
    assert (out / 'label_summary.md').exists()


def test_dry_run_manifest_records_correct_row_count(tmp_path):
    rows = [_make_row(f'rrpool_{i:03d}') for i in range(5)]
    csv_path = _make_csv(tmp_path, rows)
    out = tmp_path / 'output'
    run_script(['--input-csv', str(csv_path), '--output-dir', str(out), '--mode', 'dry_run'])
    manifest = json.loads((out / 'run_manifest.json').read_text())
    assert manifest['rows_selected'] == 5
    assert manifest['total_rows_in_csv'] == 5


def test_dry_run_confirms_no_api_calls(tmp_path):
    csv_path = _make_csv(tmp_path, [_make_row('rrpool_001')])
    out = tmp_path / 'output'
    run_script(['--input-csv', str(csv_path), '--output-dir', str(out), '--mode', 'dry_run'])
    manifest = json.loads((out / 'run_manifest.json').read_text())
    assert manifest['api_calls_made'] == 0


# ---------------------------------------------------------------------------
# dry_run — only unlabeled rows selected by default
# ---------------------------------------------------------------------------

def test_dry_run_skips_labeled_rows_by_default(tmp_path):
    rows = [_make_row('rrpool_001', labeled=True),
            _make_row('rrpool_002', labeled=False)]
    csv_path = _make_csv(tmp_path, rows)
    out = tmp_path / 'output'
    run_script(['--input-csv', str(csv_path), '--output-dir', str(out), '--mode', 'dry_run'])
    reqs = read_jsonl(out / 'azure_label_requests.jsonl')
    assert len(reqs) == 1
    assert reqs[0]['row_id'] == 'rrpool_002'


def test_dry_run_include_labeled_flag_selects_all(tmp_path):
    rows = [_make_row('rrpool_001', labeled=True),
            _make_row('rrpool_002', labeled=False)]
    csv_path = _make_csv(tmp_path, rows)
    out = tmp_path / 'output'
    run_script(['--input-csv', str(csv_path), '--output-dir', str(out),
                '--mode', 'dry_run', '--include-labeled'])
    reqs = read_jsonl(out / 'azure_label_requests.jsonl')
    assert len(reqs) == 2


# ---------------------------------------------------------------------------
# dry_run — start-index and max-rows
# ---------------------------------------------------------------------------

def test_dry_run_start_index_slices_rows(tmp_path):
    rows = [_make_row(f'rrpool_{i:03d}') for i in range(10)]
    csv_path = _make_csv(tmp_path, rows)
    out = tmp_path / 'output'
    run_script(['--input-csv', str(csv_path), '--output-dir', str(out),
                '--mode', 'dry_run', '--start-index', '5', '--max-rows', '3'])
    reqs = read_jsonl(out / 'azure_label_requests.jsonl')
    assert len(reqs) == 3
    assert reqs[0]['row_id'] == 'rrpool_005'
    assert reqs[-1]['row_id'] == 'rrpool_007'


def test_dry_run_max_rows_limits_selection(tmp_path):
    rows = [_make_row(f'rrpool_{i:03d}') for i in range(10)]
    csv_path = _make_csv(tmp_path, rows)
    out = tmp_path / 'output'
    run_script(['--input-csv', str(csv_path), '--output-dir', str(out),
                '--mode', 'dry_run', '--max-rows', '2'])
    reqs = read_jsonl(out / 'azure_label_requests.jsonl')
    assert len(reqs) == 2


def test_dry_run_start_index_stored_in_manifest(tmp_path):
    rows = [_make_row(f'rrpool_{i:03d}') for i in range(10)]
    csv_path = _make_csv(tmp_path, rows)
    out = tmp_path / 'output'
    run_script(['--input-csv', str(csv_path), '--output-dir', str(out),
                '--mode', 'dry_run', '--start-index', '7'])
    manifest = json.loads((out / 'run_manifest.json').read_text())
    assert manifest['start_index'] == 7


# ---------------------------------------------------------------------------
# dry_run — row-ids selection
# ---------------------------------------------------------------------------

def test_dry_run_row_ids_selects_specific_rows(tmp_path):
    rows = [_make_row(f'rrpool_{i:03d}') for i in range(10)]
    csv_path = _make_csv(tmp_path, rows)
    out = tmp_path / 'output'
    run_script(['--input-csv', str(csv_path), '--output-dir', str(out),
                '--mode', 'dry_run', '--row-ids', 'rrpool_002,rrpool_007'])
    reqs = read_jsonl(out / 'azure_label_requests.jsonl')
    assert len(reqs) == 2
    ids = {r['row_id'] for r in reqs}
    assert ids == {'rrpool_002', 'rrpool_007'}


def test_dry_run_row_ids_takes_precedence_over_start_index(tmp_path):
    rows = [_make_row(f'rrpool_{i:03d}') for i in range(10)]
    csv_path = _make_csv(tmp_path, rows)
    out = tmp_path / 'output'
    run_script(['--input-csv', str(csv_path), '--output-dir', str(out),
                '--mode', 'dry_run', '--start-index', '8', '--row-ids', 'rrpool_001,rrpool_003'])
    reqs = read_jsonl(out / 'azure_label_requests.jsonl')
    assert len(reqs) == 2
    ids = {r['row_id'] for r in reqs}
    assert ids == {'rrpool_001', 'rrpool_003'}


def test_dry_run_unknown_row_id_yields_empty_requests(tmp_path):
    csv_path = _make_csv(tmp_path, [_make_row('rrpool_real')])
    out = tmp_path / 'output'
    run_script(['--input-csv', str(csv_path), '--output-dir', str(out),
                '--mode', 'dry_run', '--row-ids', 'rrpool_ghost'])
    reqs = read_jsonl(out / 'azure_label_requests.jsonl')
    assert len(reqs) == 0


# ---------------------------------------------------------------------------
# dry_run — gold metadata excluded from prompts
# ---------------------------------------------------------------------------

def test_dry_run_gold_metadata_excluded_from_prompt(tmp_path):
    row = _make_row('rrpool_001', gold='yes')
    csv_path = _make_csv(tmp_path, [row])
    out = tmp_path / 'output'
    run_script(['--input-csv', str(csv_path), '--output-dir', str(out), '--mode', 'dry_run'])
    reqs = read_jsonl(out / 'azure_label_requests.jsonl')
    assert len(reqs) == 1
    prompt = reqs[0]['prompt']
    assert 'is_correct_offline_metadata' not in prompt
    assert 'gold_answer_metadata_only' not in prompt


def test_dry_run_manual_labels_excluded_from_prompt(tmp_path):
    row = _make_row('rrpool_001', labeled=True, label='ready')
    csv_path = _make_csv(tmp_path, [row])
    out = tmp_path / 'output'
    run_script(['--input-csv', str(csv_path), '--output-dir', str(out),
                '--mode', 'dry_run', '--include-labeled'])
    reqs = read_jsonl(out / 'azure_label_requests.jsonl')
    assert len(reqs) == 1
    prompt = reqs[0]['prompt']
    assert 'relation_ready_label_manual' not in prompt
    assert 'first_error_axis_manual' not in prompt
    assert 'notes_manual' not in prompt


def test_dry_run_no_leakage_in_clean_row(tmp_path):
    csv_path = _make_csv(tmp_path, [_make_row('rrpool_001')])
    out = tmp_path / 'output'
    run_script(['--input-csv', str(csv_path), '--output-dir', str(out), '--mode', 'dry_run'])
    summary = (out / 'label_summary.md').read_text()
    assert 'LEAKAGE' not in summary
    assert 'CLEAN' in summary


# ---------------------------------------------------------------------------
# api mode — refuses without --allow-api
# ---------------------------------------------------------------------------

def test_api_mode_refuses_without_allow_api(tmp_path):
    csv_path = _make_csv(tmp_path, [_make_row('rrpool_001')])
    out = tmp_path / 'output'
    result = run_script(['--input-csv', str(csv_path), '--output-dir', str(out), '--mode', 'api'],
                        expect_success=False)
    assert result.returncode != 0
    assert '--allow-api' in result.stderr


def test_api_mode_fails_with_missing_api_key(tmp_path):
    csv_path = _make_csv(tmp_path, [_make_row('rrpool_001')])
    out = tmp_path / 'output'
    # Strip all Azure env vars so the key check fires
    env = {k: v for k, v in os.environ.items()
           if k not in ('AZURE_OPENAI_API_KEY', 'AZURE_OPENAI_ENDPOINT',
                        'AZURE_OPENAI_DEPLOYMENT', 'AZURE_OPENAI_API_VERSION')}
    result = run_script(['--input-csv', str(csv_path), '--output-dir', str(out),
                         '--mode', 'api', '--allow-api'],
                        expect_success=False, env=env)
    assert result.returncode != 0


# ---------------------------------------------------------------------------
# JSON normalization (via script's normalize_response function directly)
# ---------------------------------------------------------------------------

def _import_normalize():
    """Import normalize_response from the script."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        'azure_labeler', SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.normalize_response


def test_normalize_valid_response():
    normalize = _import_normalize()
    text = json.dumps({
        'row_id': 'rrpool_001',
        'relation_ready_label': 'ready',
        'first_error_axis': '',
        'confidence': 'high',
        'is_hesitant': False,
        'hesitation_reason': '',
        'rationale': 'Trace is correct.',
    })
    norm, err = normalize('rrpool_001', 'gpt-4.1-mini', text, 'stop')
    assert err is None
    assert norm['relation_ready_label'] == 'ready'
    assert norm['first_error_axis'] == ''
    assert norm['confidence'] == 'high'
    assert norm['judge_name'] == 'azure:gpt-4.1-mini'
    assert norm['is_hesitant'] is False


def test_normalize_invalid_label_returns_error():
    normalize = _import_normalize()
    text = json.dumps({
        'relation_ready_label': 'WRONG',
        'first_error_axis': '',
        'confidence': 'high',
        'is_hesitant': False,
        'hesitation_reason': '',
        'rationale': 'test',
    })
    norm, err = normalize('rrpool_001', 'gpt-4.1-mini', text, 'stop')
    assert norm is None
    assert 'invalid_label' in err


def test_normalize_invalid_axis_returns_error():
    normalize = _import_normalize()
    text = json.dumps({
        'relation_ready_label': 'not_ready',
        'first_error_axis': 'FAKE_AXIS',
        'confidence': 'high',
        'is_hesitant': False,
        'hesitation_reason': '',
        'rationale': 'test',
    })
    norm, err = normalize('rrpool_001', 'gpt-4.1-mini', text, 'stop')
    assert norm is None
    assert 'invalid_axis' in err


def test_normalize_invalid_json_returns_error():
    normalize = _import_normalize()
    norm, err = normalize('rrpool_001', 'gpt-4.1-mini', 'not json {{{{', 'stop')
    assert norm is None
    assert 'json_parse_error' in err


def test_normalize_hesitant_flag_propagated():
    normalize = _import_normalize()
    text = json.dumps({
        'relation_ready_label': 'uncertain',
        'first_error_axis': '',
        'confidence': 'low',
        'is_hesitant': True,
        'hesitation_reason': 'Could be ready or not_ready',
        'rationale': 'Ambiguous trace.',
    })
    norm, err = normalize('rrpool_001', 'gpt-4.1-mini', text, 'stop')
    assert err is None
    assert norm['is_hesitant'] is True
    assert 'Could be ready' in norm['hesitation_reason']


def test_normalize_all_valid_labels():
    normalize = _import_normalize()
    for label in ('ready', 'not_ready', 'uncertain', 'gold_inconsistent'):
        text = json.dumps({
            'relation_ready_label': label,
            'first_error_axis': '',
            'confidence': 'high',
            'is_hesitant': False,
            'hesitation_reason': '',
            'rationale': 'test',
        })
        norm, err = normalize('rrpool_x', 'dep', text, 'stop')
        assert err is None, f'Label {label!r} should be valid but got error: {err}'


def test_normalize_all_valid_axes():
    normalize = _import_normalize()
    valid_axes = ['source_fact_missing', 'unit_scale_error', 'process_state_error',
                  'relation_type_error', 'arithmetic_error', 'other', '']
    for axis in valid_axes:
        text = json.dumps({
            'relation_ready_label': 'not_ready',
            'first_error_axis': axis,
            'confidence': 'medium',
            'is_hesitant': False,
            'hesitation_reason': '',
            'rationale': 'test',
        })
        norm, err = normalize('rrpool_x', 'dep', text, 'stop')
        assert err is None, f'Axis {axis!r} should be valid but got error: {err}'


# ---------------------------------------------------------------------------
# resume — skips already-normalized rows
# ---------------------------------------------------------------------------

def test_api_dry_run_requests_contain_expected_fields(tmp_path):
    csv_path = _make_csv(tmp_path, [_make_row('rrpool_001')])
    out = tmp_path / 'output'
    run_script(['--input-csv', str(csv_path), '--output-dir', str(out), '--mode', 'dry_run'])
    reqs = read_jsonl(out / 'azure_label_requests.jsonl')
    assert len(reqs) == 1
    req = reqs[0]
    assert 'row_id' in req
    assert 'prompt' in req
    assert 'deployment' in req
    assert 'temperature' in req
    assert req['temperature'] == 0.0


# ---------------------------------------------------------------------------
# Missing input CSV
# ---------------------------------------------------------------------------

def test_missing_input_csv_exits_nonzero(tmp_path):
    result = run_script(['--input-csv', str(tmp_path / 'nonexistent.csv'),
                         '--output-dir', str(tmp_path / 'output'),
                         '--mode', 'dry_run'],
                        expect_success=False)
    assert result.returncode != 0


# ---------------------------------------------------------------------------
# SDK / network import safety
# ---------------------------------------------------------------------------

def test_no_openai_import_at_module_level():
    """openai must only be imported inside the api-mode branch, not at module level."""
    script_text = Path(SCRIPT).read_text()
    lines = script_text.splitlines()
    # Collect top-level import lines (before any function/class def)
    top_level_imports = []
    for line in lines:
        stripped = line.strip()
        # Stop once we hit a function or class definition
        if stripped.startswith('def ') or stripped.startswith('class '):
            break
        if stripped.startswith('import openai') or stripped.startswith('from openai'):
            top_level_imports.append(stripped)
    assert top_level_imports == [], (
        f'openai must not be imported at module level: {top_level_imports}')


def test_no_azure_openai_client_used():
    """Script must use openai.OpenAI (not AzureOpenAI) per the confirmed endpoint style."""
    script_text = Path(SCRIPT).read_text()
    assert 'AzureOpenAI' not in script_text, (
        'Script must use openai.OpenAI with base_url, not AzureOpenAI')


def test_openai_client_uses_base_url():
    """Script must pass base_url= when constructing the OpenAI client."""
    script_text = Path(SCRIPT).read_text()
    assert 'base_url=' in script_text, (
        'OpenAI client must use base_url= to target the Azure /openai/v1 endpoint')


def test_no_requests_post_used():
    script_text = Path(SCRIPT).read_text()
    assert 'requests.post' not in script_text
    assert 'httpx.post' not in script_text


# ---------------------------------------------------------------------------
# Prompt calibration — rubric content checks
# ---------------------------------------------------------------------------

def _get_prompt_text(tmp_path):
    """Build a prompt from a single synthetic row and return the text."""
    csv_path = _make_csv(tmp_path, [_make_row('rrpool_probe')])
    out = tmp_path / 'output'
    run_script(['--input-csv', str(csv_path), '--output-dir', str(out), '--mode', 'dry_run'])
    reqs = read_jsonl(out / 'azure_label_requests.jsonl')
    assert len(reqs) == 1
    return reqs[0]['prompt']


def test_prompt_contains_arithmetic_structure_convention(tmp_path):
    prompt = _get_prompt_text(tmp_path)
    # The revised rubric must explain that ready = correct structure, not correct arithmetic
    assert 'arithmetic correctness' in prompt.lower() or \
           'arithmetic slip' in prompt.lower() or \
           'arithmetic mistake' in prompt.lower(), (
        'Prompt must contain the arithmetic-structure convention')


def test_prompt_contains_trivial_aggregation_truncation_rule(tmp_path):
    prompt = _get_prompt_text(tmp_path)
    assert 'trivial final aggregation' in prompt.lower() or \
           'trivial aggregation' in prompt.lower(), (
        'Prompt must contain the trivial-final-aggregation truncation rule')


def test_prompt_contains_hesitation_rule(tmp_path):
    prompt = _get_prompt_text(tmp_path)
    assert 'is_hesitant=true' in prompt or 'is_hesitant' in prompt, (
        'Prompt must contain the hesitation rule')
    # Must list at least one trigger condition for hesitation
    assert 'boundary' in prompt.lower() or \
           'truncation' in prompt.lower() or \
           'ambiguity' in prompt.lower() or \
           'arithmetic slip' in prompt.lower(), (
        'Prompt must list trigger conditions for is_hesitant')


def test_prompt_contains_few_shot_examples(tmp_path):
    prompt = _get_prompt_text(tmp_path)
    assert 'FEW-SHOT' in prompt.upper() or 'EXAMPLE' in prompt.upper(), (
        'Prompt must contain few-shot examples section')
    # Should contain at least 2 distinct label outcomes
    assert 'ready' in prompt
    assert 'not_ready' in prompt


def test_prompt_few_shot_examples_are_gold_free(tmp_path):
    prompt = _get_prompt_text(tmp_path)
    # The few-shot examples must not leak any gold/manual metadata terms
    forbidden = [
        'is_correct_offline_metadata',
        'gold_answer_metadata_only',
        'relation_ready_label_manual',
        'first_error_axis_manual',
        'notes_manual',
    ]
    for term in forbidden:
        assert term not in prompt, (
            f'Few-shot examples contain forbidden gold/manual term: {term!r}')


def test_prompt_gold_and_manual_still_excluded_after_rubric_update(tmp_path):
    row = _make_row('rrpool_probe', labeled=True, label='ready', gold='yes')
    csv_path = _make_csv(tmp_path, [row])
    out = tmp_path / 'output'
    run_script(['--input-csv', str(csv_path), '--output-dir', str(out),
                '--mode', 'dry_run', '--include-labeled'])
    reqs = read_jsonl(out / 'azure_label_requests.jsonl')
    assert len(reqs) == 1
    prompt = reqs[0]['prompt']
    assert 'is_correct_offline_metadata' not in prompt
    assert 'relation_ready_label_manual' not in prompt
    assert 'first_error_axis_manual' not in prompt
    assert 'notes_manual' not in prompt


def test_dry_run_still_makes_no_api_call_after_rubric_update(tmp_path):
    csv_path = _make_csv(tmp_path, [_make_row('rrpool_probe')])
    out = tmp_path / 'output'
    run_script(['--input-csv', str(csv_path), '--output-dir', str(out), '--mode', 'dry_run'])
    manifest = json.loads((out / 'run_manifest.json').read_text())
    assert manifest['api_calls_made'] == 0


def test_prompt_contains_no_second_guessing_rule(tmp_path):
    prompt = _get_prompt_text(tmp_path)
    assert 'second-guess' in prompt.lower() or 'independently solve' in prompt.lower(), (
        'Prompt must instruct the judge not to independently solve and second-guess the trace')


def test_prompt_contains_equivalent_formula_rule(tmp_path):
    prompt = _get_prompt_text(tmp_path)
    assert 'algebraically equivalent' in prompt.lower(), (
        'Prompt must state that algebraically equivalent formulas must be accepted')


def test_prompt_few_shot_contains_conversion_factor_example(tmp_path):
    prompt = _get_prompt_text(tmp_path)
    assert ('five-dollar' in prompt.lower() or 'five dollar' in prompt.lower() or
            'five_dollar' in prompt.lower()), (
        'Prompt must include a few-shot example covering correct $20→$5 conversion by ×4')


def test_prompt_few_shot_contains_trivial_sum_example(tmp_path):
    prompt = _get_prompt_text(tmp_path)
    assert '1650' in prompt and '800' in prompt and '2450' in prompt, (
        'Prompt must include the trivial-sum few-shot example with 1650+800=2450')


def test_prompt_hesitation_rule_covers_algebraic_equivalence(tmp_path):
    prompt = _get_prompt_text(tmp_path)
    assert 'algebraically equivalent' in prompt.lower() or \
           'algebraic equivalence' in prompt.lower(), (
        'Hesitation rule must mention checking algebraic equivalence before marking not_ready')


def test_prompt_contains_monetary_subtraction_example(tmp_path):
    prompt = _get_prompt_text(tmp_path)
    # Rubric must include a concrete monetary-subtraction trivial-aggregation example
    assert '$24' in prompt and '$30' in prompt, (
        'Prompt must include the monetary-subtraction trivial-aggregation example ($30 - $24 = $6)')


def test_prompt_trivial_aggregation_includes_subtraction(tmp_path):
    prompt = _get_prompt_text(tmp_path)
    lower = prompt.lower()
    # Trivial aggregation rule must explicitly cover subtraction (not just addition)
    assert 'subtraction' in lower or 'difference' in lower, (
        'Trivial-aggregation rule must cover subtraction, not only addition/sum')


def test_prompt_trivial_aggregation_includes_combination_example(tmp_path):
    prompt = _get_prompt_text(tmp_path)
    # Must include an 8+15=23 or equivalent combination-of-totals example in rubric
    assert '8 + 15' in prompt or '8+15' in prompt or '8 lbs' in prompt.lower() or \
           '15 lbs' in prompt.lower() or '23 pounds' in prompt.lower() or \
           '8 pounds' in prompt.lower(), (
        'Trivial-aggregation rule must reference the combination-of-totals (8+15=23) pattern')


def test_prompt_contains_self_contradiction_check(tmp_path):
    prompt = _get_prompt_text(tmp_path)
    lower = prompt.lower()
    assert 'self-contradiction' in lower or 'contradict' in lower, (
        'Prompt must contain a self-contradiction check for arithmetic_error rationales')


def test_prompt_implicit_intermediate_steps_rule(tmp_path):
    prompt = _get_prompt_text(tmp_path)
    lower = prompt.lower()
    # Must tell the judge to accept implicit intermediate values consistent with source facts
    assert 'implicit' in lower or 'spelled out' in lower or 'sub-derivation' in lower, (
        'Prompt must accept implicit intermediate steps consistent with source facts')


# ---------------------------------------------------------------------------
# 50/100 row boundary — real CSV
# ---------------------------------------------------------------------------

_REAL_CSV = Path(
    'outputs/relation_verifier_positive_candidate_batch_20260516T002059Z/'
    'positive_candidate_batch.csv'
)


@pytest.mark.skipif(not _REAL_CSV.exists(), reason='Real CSV not available')
def test_real_csv_rows_50_99_all_labeled_after_patch(tmp_path):
    # Rows 50-99 were patched with Azure-accepted labels; 0 unlabeled remain.
    out = tmp_path / 'output'
    run_script(['--input-csv', str(_REAL_CSV), '--output-dir', str(out),
                '--mode', 'dry_run', '--start-index', '50', '--max-rows', '50'])
    reqs = read_jsonl(out / 'azure_label_requests.jsonl')
    assert len(reqs) == 0, 'All rows 50-99 should be labeled; 0 unlabeled expected'


@pytest.mark.skipif(not _REAL_CSV.exists(), reason='Real CSV not available')
def test_real_csv_rows_50_99_include_labeled_selects_50(tmp_path):
    # With --include-labeled, all 50 rows 50-99 should be returned.
    out = tmp_path / 'output'
    run_script(['--input-csv', str(_REAL_CSV), '--output-dir', str(out),
                '--mode', 'dry_run', '--start-index', '50', '--max-rows', '50',
                '--include-labeled'])
    reqs = read_jsonl(out / 'azure_label_requests.jsonl')
    assert len(reqs) == 50


@pytest.mark.skipif(not _REAL_CSV.exists(), reason='Real CSV not available')
def test_real_csv_no_gold_leakage_in_requests(tmp_path):
    out = tmp_path / 'output'
    run_script(['--input-csv', str(_REAL_CSV), '--output-dir', str(out),
                '--mode', 'dry_run', '--start-index', '50', '--max-rows', '50'])
    reqs = read_jsonl(out / 'azure_label_requests.jsonl')
    for req in reqs:
        prompt = req.get('prompt', '')
        assert 'is_correct_offline_metadata' not in prompt, (
            f'Gold leakage in row {req["row_id"]}')
        assert 'relation_ready_label_manual' not in prompt, (
            f'Label leakage in row {req["row_id"]}')
        assert 'notes_manual' not in prompt, (
            f'Notes leakage in row {req["row_id"]}')


# ---------------------------------------------------------------------------
# max_completion_tokens — gpt-5.x compatibility
# ---------------------------------------------------------------------------

def test_script_source_uses_max_completion_tokens_not_max_tokens():
    """Script must use max_completion_tokens; gpt-5.4 rejects max_tokens."""
    script_text = Path(SCRIPT).read_text()
    assert 'max_completion_tokens' in script_text, (
        'Script must use max_completion_tokens (required by gpt-5.4 and newer deployments)')
    assert 'max_tokens=' not in script_text, (
        'Script must not use max_tokens= kwarg (not supported by gpt-5.4)')
    assert "'max_tokens'" not in script_text, (
        "Script must not use 'max_tokens' as a dict key in the request payload")


def test_dry_run_requests_record_max_completion_tokens(tmp_path):
    """Dry-run JSONL requests must record max_completion_tokens, not max_tokens."""
    csv_path = _make_csv(tmp_path, [_make_row('rrpool_001')])
    out = tmp_path / 'output'
    run_script(['--input-csv', str(csv_path), '--output-dir', str(out), '--mode', 'dry_run'])
    reqs = read_jsonl(out / 'azure_label_requests.jsonl')
    assert len(reqs) == 1
    req = reqs[0]
    assert 'max_completion_tokens' in req, (
        'Request JSONL must contain max_completion_tokens field')
    assert 'max_tokens' not in req, (
        'Request JSONL must not contain max_tokens field')


def _import_module():
    import importlib.util
    spec = importlib.util.spec_from_file_location('azure_labeler', SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_api_call_uses_max_completion_tokens(tmp_path):
    """Live API call must pass max_completion_tokens= to chat.completions.create."""
    from unittest.mock import MagicMock, patch

    mod = _import_module()
    csv_path = _make_csv(tmp_path, [_make_row('rrpool_mock')])
    out = tmp_path / 'output'
    out.mkdir()

    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps({
        'row_id': 'rrpool_mock',
        'relation_ready_label': 'ready',
        'first_error_axis': '',
        'confidence': 'high',
        'is_hesitant': False,
        'hesitation_reason': '',
        'rationale': 'Test.',
    })
    mock_choice.finish_reason = 'stop'
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage.prompt_tokens = 10
    mock_response.usage.completion_tokens = 5

    mock_create = MagicMock(return_value=mock_response)
    mock_client = MagicMock()
    mock_client.chat.completions.create = mock_create

    env_override = {
        'AZURE_OPENAI_API_KEY': 'fake_key',
        'AZURE_OPENAI_ENDPOINT': 'https://fake.openai.azure.com/openai/v1',
        'AZURE_OPENAI_DEPLOYMENT': 'gpt-4.1-mini',
    }
    with patch.dict(os.environ, env_override):
        with patch('openai.OpenAI', return_value=mock_client):
            args = mod.build_parser().parse_args([
                '--input-csv', str(csv_path),
                '--output-dir', str(out),
                '--mode', 'api',
                '--allow-api',
            ])
            mod.run_api(args, mod.read_csv_rows(csv_path), out)

    assert mock_create.called, 'chat.completions.create was never called'
    call_kwargs = mock_create.call_args.kwargs
    assert 'max_completion_tokens' in call_kwargs, (
        f'API call must use max_completion_tokens. Got kwargs: {list(call_kwargs)}')
    assert 'max_tokens' not in call_kwargs, (
        f'API call must NOT use max_tokens. Got kwargs: {list(call_kwargs)}')


def test_api_call_passes_model_deployment(tmp_path):
    """API call must pass the deployment name as the model= parameter."""
    from unittest.mock import MagicMock, patch

    mod = _import_module()
    csv_path = _make_csv(tmp_path, [_make_row('rrpool_mock')])
    out = tmp_path / 'output'
    out.mkdir()

    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps({
        'row_id': 'rrpool_mock',
        'relation_ready_label': 'ready',
        'first_error_axis': '',
        'confidence': 'high',
        'is_hesitant': False,
        'hesitation_reason': '',
        'rationale': 'Test.',
    })
    mock_choice.finish_reason = 'stop'
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage.prompt_tokens = 10
    mock_response.usage.completion_tokens = 5

    mock_create = MagicMock(return_value=mock_response)
    mock_client = MagicMock()
    mock_client.chat.completions.create = mock_create

    env_override = {
        'AZURE_OPENAI_API_KEY': 'fake_key',
        'AZURE_OPENAI_ENDPOINT': 'https://fake.openai.azure.com/openai/v1',
        'AZURE_OPENAI_DEPLOYMENT': 'gpt-5.4',
    }
    with patch.dict(os.environ, env_override):
        with patch('openai.OpenAI', return_value=mock_client):
            args = mod.build_parser().parse_args([
                '--input-csv', str(csv_path),
                '--output-dir', str(out),
                '--mode', 'api',
                '--allow-api',
                '--deployment', 'gpt-5.4',
            ])
            mod.run_api(args, mod.read_csv_rows(csv_path), out)

    call_kwargs = mock_create.call_args.kwargs
    assert call_kwargs.get('model') == 'gpt-5.4', (
        f'model= must be the deployment name. Got: {call_kwargs.get("model")!r}')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
