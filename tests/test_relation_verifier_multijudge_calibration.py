"""Tests for the no-API multi-judge calibration runner scaffold."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = 'scripts/run_relation_verifier_multijudge_calibration.py'

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def write_jsonl(path, rows):
    with Path(path).open('w', encoding='utf-8') as f:
        for row in rows:
            f.write(json.dumps(row) + '\n')


def read_jsonl(path):
    rows = []
    with Path(path).open('r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def run_script(args, expect_success=True):
    result = subprocess.run(
        [sys.executable, SCRIPT] + args,
        capture_output=True,
        text=True,
    )
    if expect_success:
        assert result.returncode == 0, (
            f'Script failed.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}'
        )
    return result


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_CLEAN_PROMPT = (
    'Please evaluate whether the following candidate trace and answer '
    'correctly represent the semantic relation requested by the question.\n\n'
    'QUESTION:\nHow many apples are left?\n\n'
    'TARGET PHRASE:\napples left\n\n'
    'Note: The target phrase is an automatically extracted hint. '
    'If it is empty, vague, or type-like, use the quantity requested '
    'by the full question as the target.\n\n'
    'CANDIDATE ANSWER:\n5\n\n'
    'CANDIDATE TRACE:\n10 - 5 = 5\n\n'
    'TASK:\nDetermine whether the candidate trace represents the correct '
    'semantic relation for computing the target phrase.\n\n'
    'If the candidate trace is opaque, JSON-only, or lacks reasoning steps, '
    'judge only the visible trace and candidate answer. If the candidate '
    'appears wrong but the exact failure cannot be localized from the visible '
    'trace, use first_error_axis = insufficient_evidence. '
    'Do not infer hidden reasoning.\n\n'
    'Respond with JSON containing:\n- relation_ready_label: ...'
)

_BASE_REQUEST = {
    'row_id': 'rrseed_test_001',
    'problem_id': 'test/problem/1',
    'question': 'How many apples are left?',
    'target_phrase': 'apples left',
    'target_semantic_type': 'number',
    'candidate_source': 'direct_formula_family',
    'candidate_answer': '5',
    'candidate_trace_short': '10 - 5 = 5',
    'prompt': _CLEAN_PROMPT,
    'expected_json_schema': {
        'type': 'object',
        'properties': {
            'relation_ready_label': {'type': 'string'},
            'first_error_axis': {'type': 'string'},
            'confidence': {'type': 'string'},
            'rationale': {'type': 'string'},
        },
        'required': ['relation_ready_label', 'first_error_axis', 'confidence', 'rationale'],
    },
}

_BASE_REQUEST_2 = {**_BASE_REQUEST, 'row_id': 'rrseed_test_002'}

_BASE_MOCK_RESPONSE = {
    'row_id': 'rrseed_test_001',
    'judge_name': 'mock_judge_a',
    'relation_ready_label': 'ready',
    'first_error_axis': '',
    'confidence': 'high',
    'rationale': 'Trace correctly computes the target.',
}

# ---------------------------------------------------------------------------
# dry_run tests
# ---------------------------------------------------------------------------

def test_dry_run_writes_manifest_and_report(tmp_path):
    """Dry-run should write dry_run_request_manifest.jsonl and calibration_run_report.md."""
    requests_path = tmp_path / 'requests.jsonl'
    write_jsonl(requests_path, [_BASE_REQUEST])
    output_dir = tmp_path / 'output'

    run_script([
        '--requests-jsonl', str(requests_path),
        '--output-dir', str(output_dir),
        '--mode', 'dry_run',
    ])

    assert (output_dir / 'dry_run_request_manifest.jsonl').exists()
    assert (output_dir / 'calibration_run_report.md').exists()

    manifest = read_jsonl(output_dir / 'dry_run_request_manifest.jsonl')
    assert len(manifest) == 1
    assert manifest[0]['row_id'] == 'rrseed_test_001'
    assert manifest[0]['has_prompt'] is True
    assert manifest[0]['has_schema'] is True

    report = (output_dir / 'calibration_run_report.md').read_text()
    assert 'dry_run' in report
    assert 'No API calls' in report


def test_dry_run_does_not_require_private_labels(tmp_path):
    """Dry-run must succeed without --private-labels-jsonl."""
    requests_path = tmp_path / 'requests.jsonl'
    write_jsonl(requests_path, [_BASE_REQUEST])
    output_dir = tmp_path / 'output'

    result = run_script([
        '--requests-jsonl', str(requests_path),
        '--output-dir', str(output_dir),
        '--mode', 'dry_run',
    ])
    assert result.returncode == 0
    assert (output_dir / 'dry_run_request_manifest.jsonl').exists()


def test_dry_run_max_rows(tmp_path):
    """--max-rows should limit the number of processed requests."""
    requests_path = tmp_path / 'requests.jsonl'
    write_jsonl(requests_path, [_BASE_REQUEST, _BASE_REQUEST_2])
    output_dir = tmp_path / 'output'

    run_script([
        '--requests-jsonl', str(requests_path),
        '--output-dir', str(output_dir),
        '--mode', 'dry_run',
        '--max-rows', '1',
    ])

    manifest = read_jsonl(output_dir / 'dry_run_request_manifest.jsonl')
    assert len(manifest) == 1


def test_dry_run_detects_missing_field(tmp_path):
    """Dry-run should flag requests missing required fields."""
    bad_req = {**_BASE_REQUEST, 'prompt': ''}
    requests_path = tmp_path / 'requests.jsonl'
    write_jsonl(requests_path, [bad_req])
    output_dir = tmp_path / 'output'

    run_script([
        '--requests-jsonl', str(requests_path),
        '--output-dir', str(output_dir),
        '--mode', 'dry_run',
    ])

    manifest = read_jsonl(output_dir / 'dry_run_request_manifest.jsonl')
    assert 'missing_prompt' in manifest[0]['field_issues']


# ---------------------------------------------------------------------------
# mock_jsonl tests
# ---------------------------------------------------------------------------

def test_mock_jsonl_validates_allowed_labels(tmp_path):
    """Valid mock responses should produce normalized output."""
    requests_path = tmp_path / 'requests.jsonl'
    mock_path = tmp_path / 'mock.jsonl'
    write_jsonl(requests_path, [_BASE_REQUEST])
    write_jsonl(mock_path, [_BASE_MOCK_RESPONSE])
    output_dir = tmp_path / 'output'

    run_script([
        '--requests-jsonl', str(requests_path),
        '--output-dir', str(output_dir),
        '--mode', 'mock_jsonl',
        '--mock-responses-jsonl', str(mock_path),
    ])

    normalized = read_jsonl(output_dir / 'normalized_judge_responses.jsonl')
    assert len(normalized) == 1
    assert normalized[0]['relation_ready_label'] == 'ready'
    assert normalized[0]['row_id'] == 'rrseed_test_001'


def test_invalid_judge_label_is_reported(tmp_path):
    """Invalid relation_ready_label should be excluded from normalized output and flagged."""
    requests_path = tmp_path / 'requests.jsonl'
    write_jsonl(requests_path, [_BASE_REQUEST])
    bad_response = {**_BASE_MOCK_RESPONSE, 'relation_ready_label': 'TOTALLY_WRONG'}
    mock_path = tmp_path / 'mock.jsonl'
    write_jsonl(mock_path, [bad_response])
    output_dir = tmp_path / 'output'

    run_script([
        '--requests-jsonl', str(requests_path),
        '--output-dir', str(output_dir),
        '--mode', 'mock_jsonl',
        '--mock-responses-jsonl', str(mock_path),
    ])

    normalized = read_jsonl(output_dir / 'normalized_judge_responses.jsonl')
    assert len(normalized) == 0, 'Invalid response must not appear in normalized output'

    report = (output_dir / 'judge_agreement_report.md').read_text()
    assert 'Invalid' in report or 'invalid' in report.lower()


def test_invalid_judge_axis_is_reported(tmp_path):
    """Invalid first_error_axis should be flagged."""
    requests_path = tmp_path / 'requests.jsonl'
    write_jsonl(requests_path, [_BASE_REQUEST])
    bad = {**_BASE_MOCK_RESPONSE, 'relation_ready_label': 'not_ready', 'first_error_axis': 'FAKE_AXIS'}
    mock_path = tmp_path / 'mock.jsonl'
    write_jsonl(mock_path, [bad])
    output_dir = tmp_path / 'output'

    run_script([
        '--requests-jsonl', str(requests_path),
        '--output-dir', str(output_dir),
        '--mode', 'mock_jsonl',
        '--mock-responses-jsonl', str(mock_path),
    ])

    normalized = read_jsonl(output_dir / 'normalized_judge_responses.jsonl')
    assert len(normalized) == 0, 'Invalid axis response must be excluded'


def test_private_labels_only_in_offline_report(tmp_path):
    """Private label fields must not appear in normalized_judge_responses.jsonl."""
    requests_path = tmp_path / 'requests.jsonl'
    mock_path = tmp_path / 'mock.jsonl'
    private_path = tmp_path / 'private.jsonl'
    write_jsonl(requests_path, [_BASE_REQUEST])
    write_jsonl(mock_path, [_BASE_MOCK_RESPONSE])
    write_jsonl(private_path, [{
        'row_id': 'rrseed_test_001',
        'relation_ready_label_manual': 'ready',
        'first_error_axis_manual': '',
    }])
    output_dir = tmp_path / 'output'

    run_script([
        '--requests-jsonl', str(requests_path),
        '--output-dir', str(output_dir),
        '--mode', 'mock_jsonl',
        '--mock-responses-jsonl', str(mock_path),
        '--private-labels-jsonl', str(private_path),
    ])

    normalized_text = (output_dir / 'normalized_judge_responses.jsonl').read_text()
    assert 'relation_ready_label_manual' not in normalized_text
    assert 'first_error_axis_manual' not in normalized_text
    assert 'notes_manual' not in normalized_text

    report = (output_dir / 'judge_agreement_report.md').read_text()
    assert 'offline' in report.lower() or 'Private' in report


def test_private_labels_support_human_prefix_convention(tmp_path):
    """Private labels using human_* field names should also be loaded correctly."""
    requests_path = tmp_path / 'requests.jsonl'
    mock_path = tmp_path / 'mock.jsonl'
    private_path = tmp_path / 'private.jsonl'
    write_jsonl(requests_path, [_BASE_REQUEST])
    write_jsonl(mock_path, [_BASE_MOCK_RESPONSE])
    write_jsonl(private_path, [{
        'row_id': 'rrseed_test_001',
        'human_relation_ready_label': 'ready',
        'human_first_error_axis': '',
        'human_notes': 'test note',
    }])
    output_dir = tmp_path / 'output'

    run_script([
        '--requests-jsonl', str(requests_path),
        '--output-dir', str(output_dir),
        '--mode', 'mock_jsonl',
        '--mock-responses-jsonl', str(mock_path),
        '--private-labels-jsonl', str(private_path),
    ])

    report = (output_dir / 'judge_agreement_report.md').read_text()
    assert '1 / 1' in report


def test_agreement_counts_computed_correctly(tmp_path):
    """Agreement count should reflect matching judge majority vs manual labels."""
    requests_path = tmp_path / 'requests.jsonl'
    mock_path = tmp_path / 'mock.jsonl'
    private_path = tmp_path / 'private.jsonl'

    write_jsonl(requests_path, [_BASE_REQUEST, _BASE_REQUEST_2])
    # Judge says ready for both; manual says ready for 001, not_ready for 002
    write_jsonl(mock_path, [
        {**_BASE_MOCK_RESPONSE, 'row_id': 'rrseed_test_001', 'relation_ready_label': 'ready'},
        {**_BASE_MOCK_RESPONSE, 'row_id': 'rrseed_test_002', 'relation_ready_label': 'ready'},
    ])
    write_jsonl(private_path, [
        {'row_id': 'rrseed_test_001', 'relation_ready_label_manual': 'ready', 'first_error_axis_manual': ''},
        {'row_id': 'rrseed_test_002', 'relation_ready_label_manual': 'not_ready', 'first_error_axis_manual': 'arithmetic_only_error'},
    ])
    output_dir = tmp_path / 'output'

    run_script([
        '--requests-jsonl', str(requests_path),
        '--output-dir', str(output_dir),
        '--mode', 'mock_jsonl',
        '--mock-responses-jsonl', str(mock_path),
        '--private-labels-jsonl', str(private_path),
    ])

    report = (output_dir / 'judge_agreement_report.md').read_text()
    assert '1 / 2' in report


def test_rows_needing_review_judge_disagreement(tmp_path):
    """Judge disagreement should trigger human-review flag."""
    requests_path = tmp_path / 'requests.jsonl'
    mock_path = tmp_path / 'mock.jsonl'
    write_jsonl(requests_path, [_BASE_REQUEST])
    write_jsonl(mock_path, [
        {**_BASE_MOCK_RESPONSE, 'judge_name': 'judge_a', 'relation_ready_label': 'ready', 'confidence': 'high'},
        {**_BASE_MOCK_RESPONSE, 'judge_name': 'judge_b', 'relation_ready_label': 'not_ready',
         'confidence': 'low', 'first_error_axis': 'arithmetic_only_error'},
    ])
    output_dir = tmp_path / 'output'

    run_script([
        '--requests-jsonl', str(requests_path),
        '--output-dir', str(output_dir),
        '--mode', 'mock_jsonl',
        '--mock-responses-jsonl', str(mock_path),
    ])

    report = (output_dir / 'judge_agreement_report.md').read_text()
    assert 'rrseed_test_001' in report
    assert 'Needing' in report or 'review' in report.lower()
    assert 'judge_disagreement' in report


def test_rows_needing_review_low_confidence(tmp_path):
    """Low-confidence response should trigger human-review flag."""
    requests_path = tmp_path / 'requests.jsonl'
    mock_path = tmp_path / 'mock.jsonl'
    write_jsonl(requests_path, [_BASE_REQUEST])
    write_jsonl(mock_path, [
        {**_BASE_MOCK_RESPONSE, 'confidence': 'low'},
    ])
    output_dir = tmp_path / 'output'

    run_script([
        '--requests-jsonl', str(requests_path),
        '--output-dir', str(output_dir),
        '--mode', 'mock_jsonl',
        '--mock-responses-jsonl', str(mock_path),
    ])

    report = (output_dir / 'judge_agreement_report.md').read_text()
    assert 'low_confidence' in report


def test_rows_needing_review_uncertain_label(tmp_path):
    """Uncertain label should trigger human-review flag."""
    requests_path = tmp_path / 'requests.jsonl'
    mock_path = tmp_path / 'mock.jsonl'
    write_jsonl(requests_path, [_BASE_REQUEST])
    write_jsonl(mock_path, [
        {**_BASE_MOCK_RESPONSE, 'relation_ready_label': 'uncertain'},
    ])
    output_dir = tmp_path / 'output'

    run_script([
        '--requests-jsonl', str(requests_path),
        '--output-dir', str(output_dir),
        '--mode', 'mock_jsonl',
        '--mock-responses-jsonl', str(mock_path),
    ])

    report = (output_dir / 'judge_agreement_report.md').read_text()
    assert 'uncertain_or_gold_inconsistent' in report


# ---------------------------------------------------------------------------
# Leakage tests
# ---------------------------------------------------------------------------

def test_prompt_leakage_detected_in_dry_run(tmp_path):
    """Dry-run should detect leakage terms embedded in prompts."""
    bad_prompt = _CLEAN_PROMPT + '\nrelation_ready_label_manual: ready\nlikely not_ready'
    bad_req = {**_BASE_REQUEST, 'prompt': bad_prompt}
    requests_path = tmp_path / 'requests.jsonl'
    write_jsonl(requests_path, [bad_req])
    output_dir = tmp_path / 'output'

    run_script([
        '--requests-jsonl', str(requests_path),
        '--output-dir', str(output_dir),
        '--mode', 'dry_run',
    ])

    manifest = read_jsonl(output_dir / 'dry_run_request_manifest.jsonl')
    assert len(manifest[0]['leakage_terms']) > 0
    assert 'relation_ready_label_manual' in manifest[0]['leakage_terms']
    assert 'likely not_ready' in manifest[0]['leakage_terms']

    report = (output_dir / 'calibration_run_report.md').read_text()
    assert 'LEAKAGE' in report


def test_good_judge_should_label_is_a_leakage_term(tmp_path):
    """'good judge should label' must be caught by leakage scan."""
    bad_prompt = _CLEAN_PROMPT + '\nA good judge should label this as not_ready.'
    bad_req = {**_BASE_REQUEST, 'prompt': bad_prompt}
    requests_path = tmp_path / 'requests.jsonl'
    write_jsonl(requests_path, [bad_req])
    output_dir = tmp_path / 'output'

    run_script([
        '--requests-jsonl', str(requests_path),
        '--output-dir', str(output_dir),
        '--mode', 'dry_run',
    ])

    manifest = read_jsonl(output_dir / 'dry_run_request_manifest.jsonl')
    assert 'good judge should label' in manifest[0]['leakage_terms']


def test_clean_prompt_has_no_leakage(tmp_path):
    """Clean prompt from the builder should produce zero leakage terms."""
    requests_path = tmp_path / 'requests.jsonl'
    write_jsonl(requests_path, [_BASE_REQUEST])
    output_dir = tmp_path / 'output'

    run_script([
        '--requests-jsonl', str(requests_path),
        '--output-dir', str(output_dir),
        '--mode', 'dry_run',
    ])

    manifest = read_jsonl(output_dir / 'dry_run_request_manifest.jsonl')
    assert manifest[0]['leakage_terms'] == []


# ---------------------------------------------------------------------------
# SDK / provider import safety test
# ---------------------------------------------------------------------------

def test_no_real_api_code_or_provider_sdk_imports():
    """Script must not contain real provider API calls or SDK imports."""
    script_text = Path(SCRIPT).read_text()
    forbidden = [
        'import anthropic',
        'from anthropic',
        'import openai',
        'from openai',
        'import cohere',
        'from cohere',
        'import boto3',
        'import google.generativeai',
        'requests.post',
        'httpx.post',
    ]
    for term in forbidden:
        assert term not in script_text, f'Script must not contain provider import: {term!r}'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
