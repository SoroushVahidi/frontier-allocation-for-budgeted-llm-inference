"""Tests for multi-judge label request builder script."""

import csv
import json
from pathlib import Path

import pytest


def create_test_csv(tmp_path, rows):
    """Helper to create a test CSV file."""
    csv_path = tmp_path / 'test.csv'
    with csv_path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    return csv_path


def read_jsonl(path):
    """Read JSONL file and return list of objects."""
    objects = []
    with path.open('r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                objects.append(json.loads(line))
    return objects


def test_builds_request_jsonl_from_csv(tmp_path):
    """Test that script builds request JSONL from a small CSV fixture."""
    rows = [
        {
            'row_id': 'test_1',
            'problem_id': 'test/problem/1',
            'question': 'What is 2 + 2?',
            'target_phrase': 'sum of two and two',
            'target_semantic_type': 'number',
            'candidate_source': 'direct_formula_family',
            'candidate_answer': '4',
            'candidate_trace_short': '2 + 2 = 4',
            'relation_ready_label_manual': 'ready',
            'first_error_axis_manual': '',
            'notes_manual': '',
            'gold_answer_metadata_only': '',
        },
    ]
    csv_path = create_test_csv(tmp_path, rows)
    output_dir = tmp_path / 'output'

    # Import and run the script
    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable,
            'scripts/build_relation_verifier_multijudge_label_requests.py',
            '--input-csv',
            str(csv_path),
            '--output-dir',
            str(output_dir),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f'Script should succeed. stderr: {result.stderr}'

    # Check output files
    requests_path = output_dir / 'judge_requests.jsonl'
    assert requests_path.exists(), 'judge_requests.jsonl should be created'

    requests = read_jsonl(requests_path)
    assert len(requests) == 1, 'Should have 1 request'
    assert requests[0]['row_id'] == 'test_1'
    assert 'prompt' in requests[0]
    assert 'expected_json_schema' in requests[0]


def test_prompt_excludes_gold_answer(tmp_path):
    """Test that prompt excludes gold_answer_metadata_only."""
    rows = [
        {
            'row_id': 'test_1',
            'problem_id': 'test/problem/1',
            'question': 'What is 2 + 2?',
            'target_phrase': 'sum',
            'target_semantic_type': 'number',
            'candidate_source': 'direct_formula_family',
            'candidate_answer': '4',
            'candidate_trace_short': '2 + 2 = 4',
            'relation_ready_label_manual': 'ready',
            'first_error_axis_manual': '',
            'notes_manual': '',
            'gold_answer_metadata_only': '4',
        },
    ]
    csv_path = create_test_csv(tmp_path, rows)
    output_dir = tmp_path / 'output'

    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable,
            'scripts/build_relation_verifier_multijudge_label_requests.py',
            '--input-csv',
            str(csv_path),
            '--output-dir',
            str(output_dir),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0

    requests = read_jsonl(output_dir / 'judge_requests.jsonl')
    assert len(requests) == 1
    prompt = requests[0]['prompt']
    assert 'gold_answer' not in prompt, 'Prompt should not contain gold_answer'


def test_prompt_excludes_manual_labels(tmp_path):
    """Test that prompt excludes manual labels and notes."""
    rows = [
        {
            'row_id': 'test_1',
            'problem_id': 'test/problem/1',
            'question': 'What is 2 + 2?',
            'target_phrase': 'sum',
            'target_semantic_type': 'number',
            'candidate_source': 'direct_formula_family',
            'candidate_answer': '4',
            'candidate_trace_short': '2 + 2 = 4',
            'relation_ready_label_manual': 'ready',
            'first_error_axis_manual': 'arithmetic_only_error',
            'notes_manual': 'This is a test note',
            'gold_answer_metadata_only': '',
        },
    ]
    csv_path = create_test_csv(tmp_path, rows)
    output_dir = tmp_path / 'output'

    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable,
            'scripts/build_relation_verifier_multijudge_label_requests.py',
            '--input-csv',
            str(csv_path),
            '--output-dir',
            str(output_dir),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0

    requests = read_jsonl(output_dir / 'judge_requests.jsonl')
    prompt = requests[0]['prompt']
    assert 'relation_ready_label_manual' not in prompt
    assert 'first_error_axis_manual' not in prompt
    assert 'notes_manual' not in prompt
    assert 'test note' not in prompt


def test_expected_json_schema_contains_required_fields(tmp_path):
    """Test that expected JSON schema contains required fields."""
    rows = [
        {
            'row_id': 'test_1',
            'problem_id': 'test/problem/1',
            'question': 'What is 2 + 2?',
            'target_phrase': 'sum',
            'target_semantic_type': 'number',
            'candidate_source': 'direct_formula_family',
            'candidate_answer': '4',
            'candidate_trace_short': '2 + 2 = 4',
            'relation_ready_label_manual': 'ready',
            'first_error_axis_manual': '',
            'notes_manual': '',
            'gold_answer_metadata_only': '',
        },
    ]
    csv_path = create_test_csv(tmp_path, rows)
    output_dir = tmp_path / 'output'

    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable,
            'scripts/build_relation_verifier_multijudge_label_requests.py',
            '--input-csv',
            str(csv_path),
            '--output-dir',
            str(output_dir),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0

    requests = read_jsonl(output_dir / 'judge_requests.jsonl')
    schema = requests[0]['expected_json_schema']
    assert 'properties' in schema
    assert 'relation_ready_label' in schema['properties']
    assert 'first_error_axis' in schema['properties']
    assert 'confidence' in schema['properties']
    assert 'rationale' in schema['properties']


def test_report_created(tmp_path):
    """Test that report Markdown is created."""
    rows = [
        {
            'row_id': 'test_1',
            'problem_id': 'test/problem/1',
            'question': 'What is 2 + 2?',
            'target_phrase': 'sum',
            'target_semantic_type': 'number',
            'candidate_source': 'direct_formula_family',
            'candidate_answer': '4',
            'candidate_trace_short': '2 + 2 = 4',
            'relation_ready_label_manual': 'ready',
            'first_error_axis_manual': '',
            'notes_manual': '',
            'gold_answer_metadata_only': '',
        },
    ]
    csv_path = create_test_csv(tmp_path, rows)
    output_dir = tmp_path / 'output'

    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable,
            'scripts/build_relation_verifier_multijudge_label_requests.py',
            '--input-csv',
            str(csv_path),
            '--output-dir',
            str(output_dir),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0

    report_path = output_dir / 'request_build_report.md'
    assert report_path.exists(), 'request_build_report.md should be created'
    content = report_path.read_text()
    assert 'Summary' in content
    assert 'Emitted requests' in content


def test_private_calibration_file_created_when_requested(tmp_path):
    """Test that calibration_labels_private.jsonl is created when requested."""
    rows = [
        {
            'row_id': 'test_1',
            'problem_id': 'test/problem/1',
            'question': 'What is 2 + 2?',
            'target_phrase': 'sum',
            'target_semantic_type': 'number',
            'candidate_source': 'direct_formula_family',
            'candidate_answer': '4',
            'candidate_trace_short': '2 + 2 = 4',
            'relation_ready_label_manual': 'ready',
            'first_error_axis_manual': '',
            'notes_manual': 'test notes',
            'gold_answer_metadata_only': '',
        },
    ]
    csv_path = create_test_csv(tmp_path, rows)
    output_dir = tmp_path / 'output'

    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable,
            'scripts/build_relation_verifier_multijudge_label_requests.py',
            '--input-csv',
            str(csv_path),
            '--output-dir',
            str(output_dir),
            '--include-human-labels-in-eval-file',
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0

    calib_path = output_dir / 'calibration_labels_private.jsonl'
    assert calib_path.exists(), 'calibration_labels_private.jsonl should be created'

    calib = read_jsonl(calib_path)
    assert len(calib) == 1
    assert calib[0]['row_id'] == 'test_1'
    assert calib[0]['human_relation_ready_label'] == 'ready'
    assert calib[0]['human_notes'] == 'test notes'


def test_default_mode_does_not_write_private_labels(tmp_path):
    """Test that private labels are not written by default."""
    rows = [
        {
            'row_id': 'test_1',
            'problem_id': 'test/problem/1',
            'question': 'What is 2 + 2?',
            'target_phrase': 'sum',
            'target_semantic_type': 'number',
            'candidate_source': 'direct_formula_family',
            'candidate_answer': '4',
            'candidate_trace_short': '2 + 2 = 4',
            'relation_ready_label_manual': 'ready',
            'first_error_axis_manual': '',
            'notes_manual': '',
            'gold_answer_metadata_only': '',
        },
    ]
    csv_path = create_test_csv(tmp_path, rows)
    output_dir = tmp_path / 'output'

    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable,
            'scripts/build_relation_verifier_multijudge_label_requests.py',
            '--input-csv',
            str(csv_path),
            '--output-dir',
            str(output_dir),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0

    calib_path = output_dir / 'calibration_labels_private.jsonl'
    assert not calib_path.exists(), 'calibration file should not be created by default'


def test_skips_rows_with_missing_fields(tmp_path):
    """Test that rows with missing required fields are skipped."""
    rows = [
        {
            'row_id': 'test_1',
            'problem_id': 'test/problem/1',
            'question': 'What is 2 + 2?',
            'target_phrase': 'sum',
            'target_semantic_type': 'number',
            'candidate_source': 'direct_formula_family',
            'candidate_answer': '4',
            'candidate_trace_short': '',  # Missing!
            'relation_ready_label_manual': 'ready',
            'first_error_axis_manual': '',
            'notes_manual': '',
            'gold_answer_metadata_only': '',
        },
    ]
    csv_path = create_test_csv(tmp_path, rows)
    output_dir = tmp_path / 'output'

    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable,
            'scripts/build_relation_verifier_multijudge_label_requests.py',
            '--input-csv',
            str(csv_path),
            '--output-dir',
            str(output_dir),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0

    requests = read_jsonl(output_dir / 'judge_requests.jsonl')
    assert len(requests) == 0, 'Should skip row with missing candidate_trace_short'

    report = (output_dir / 'request_build_report.md').read_text()
    assert 'Skipped' in report


def _run_builder(tmp_path, rows, extra_args=None):
    """Helper: write CSV, run builder, return output_dir."""
    import subprocess, sys
    csv_path = create_test_csv(tmp_path, rows)
    output_dir = tmp_path / 'output'
    cmd = [
        sys.executable,
        'scripts/build_relation_verifier_multijudge_label_requests.py',
        '--input-csv', str(csv_path),
        '--output-dir', str(output_dir),
    ]
    if extra_args:
        cmd.extend(extra_args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0, f'Builder failed: {result.stderr}'
    return output_dir


_BASE_ROW = {
    'row_id': 'test_1',
    'problem_id': 'test/problem/1',
    'question': 'How many apples are left?',
    'target_phrase': 'apples left',
    'target_semantic_type': 'number',
    'candidate_source': 'direct_formula_family',
    'candidate_answer': '5',
    'candidate_trace_short': '10 - 5 = 5',
    'relation_ready_label_manual': 'ready',
    'first_error_axis_manual': '',
    'notes_manual': '',
    'gold_answer_metadata_only': '',
}


def test_empty_target_phrase_uses_fallback(tmp_path):
    """Test that empty target_phrase is replaced with the fallback instruction."""
    row = {**_BASE_ROW, 'target_phrase': ''}
    output_dir = _run_builder(tmp_path, [row])
    requests = read_jsonl(output_dir / 'judge_requests.jsonl')
    assert len(requests) == 1
    prompt = requests[0]['prompt']
    assert 'Not explicitly extracted' in prompt, (
        'Empty target_phrase must use fallback instruction in prompt'
    )
    assert 'Use the question\'s requested quantity as the target' in prompt


def test_whitespace_only_target_phrase_uses_fallback(tmp_path):
    """Test that a whitespace-only target_phrase is also treated as empty."""
    row = {**_BASE_ROW, 'target_phrase': '   '}
    output_dir = _run_builder(tmp_path, [row])
    requests = read_jsonl(output_dir / 'judge_requests.jsonl')
    prompt = requests[0]['prompt']
    assert 'Not explicitly extracted' in prompt


def test_prompt_does_not_contain_likely(tmp_path):
    """Test that prompts do not contain label-hint words like 'likely'."""
    row = {**_BASE_ROW}
    output_dir = _run_builder(tmp_path, [row])
    requests = read_jsonl(output_dir / 'judge_requests.jsonl')
    prompt = requests[0]['prompt']
    assert 'likely not_ready' not in prompt
    assert 'likely ready' not in prompt
    assert 'likely uncertain' not in prompt


def test_prompt_does_not_contain_ready_candidate(tmp_path):
    """Test that prompts do not contain the phrase 'ready candidate'."""
    row = {**_BASE_ROW}
    output_dir = _run_builder(tmp_path, [row])
    requests = read_jsonl(output_dir / 'judge_requests.jsonl')
    prompt = requests[0]['prompt']
    assert 'ready candidate' not in prompt
    assert 'not_ready candidate' not in prompt


def test_report_does_not_contain_label_hints(tmp_path):
    """Test that request_build_report.md contains no expected-label guesses."""
    row = {**_BASE_ROW}
    output_dir = _run_builder(tmp_path, [row])
    report = (output_dir / 'request_build_report.md').read_text()
    for hint in ('likely not_ready', 'likely ready', 'ready candidate', 'uncertain likely'):
        assert hint not in report, f'Report must not contain label hint: {hint!r}'


def test_prompt_includes_target_phrase_heuristic_warning(tmp_path):
    """Test that every prompt includes the target-phrase heuristic note."""
    row = {**_BASE_ROW, 'target_phrase': 'apples left'}
    output_dir = _run_builder(tmp_path, [row])
    requests = read_jsonl(output_dir / 'judge_requests.jsonl')
    prompt = requests[0]['prompt']
    assert 'automatically extracted hint' in prompt, (
        'Prompt must include target-phrase heuristic warning'
    )
    assert 'vague, or type-like' in prompt


def test_vague_type_like_target_phrase_includes_heuristic_warning(tmp_path):
    """Test that a type-like target_phrase such as 'percentage' still includes the warning."""
    row = {**_BASE_ROW, 'target_phrase': 'percentage'}
    output_dir = _run_builder(tmp_path, [row])
    requests = read_jsonl(output_dir / 'judge_requests.jsonl')
    prompt = requests[0]['prompt']
    assert 'automatically extracted hint' in prompt, (
        "Type-like target_phrase 'percentage' must still include heuristic warning"
    )
    assert 'vague, or type-like' in prompt


def test_prompt_includes_opaque_trace_instruction(tmp_path):
    """Test that every prompt includes the opaque/JSON-only trace instruction."""
    row = {**_BASE_ROW}
    output_dir = _run_builder(tmp_path, [row])
    requests = read_jsonl(output_dir / 'judge_requests.jsonl')
    prompt = requests[0]['prompt']
    assert 'opaque' in prompt, 'Prompt must include opaque-trace instruction'
    assert 'JSON-only' in prompt
    assert 'Do not infer hidden reasoning' in prompt
    assert 'insufficient_evidence' in prompt


def test_prompt_does_not_contain_good_judge_should_label(tmp_path):
    """Test that prompts do not contain 'good judge should label' commentary."""
    row = {**_BASE_ROW}
    output_dir = _run_builder(tmp_path, [row])
    requests = read_jsonl(output_dir / 'judge_requests.jsonl')
    prompt = requests[0]['prompt']
    assert 'good judge should label' not in prompt


def test_report_does_not_contain_good_judge_should_label(tmp_path):
    """Test that request_build_report.md does not contain expected-label commentary."""
    row = {**_BASE_ROW}
    output_dir = _run_builder(tmp_path, [row])
    report = (output_dir / 'request_build_report.md').read_text()
    assert 'good judge should label' not in report


# ---------------------------------------------------------------------------
# Refined axis definition tests
# ---------------------------------------------------------------------------

def test_prompt_arithmetic_only_error_definition_is_narrow(tmp_path):
    """arithmetic_only_error must specify correct source facts / computation slip."""
    output_dir = _run_builder(tmp_path, [_BASE_ROW])
    prompt = read_jsonl(output_dir / 'judge_requests.jsonl')[0]['prompt']
    assert 'correct source facts' in prompt, (
        'arithmetic_only_error definition must require correct source facts'
    )
    assert 'numerical computation slip' in prompt, (
        'arithmetic_only_error definition must reference numerical computation slip'
    )


def test_prompt_source_fact_missing_definition_and_example(tmp_path):
    """source_fact_missing must include refined definition and generic example."""
    output_dir = _run_builder(tmp_path, [_BASE_ROW])
    prompt = read_jsonl(output_dir / 'judge_requests.jsonl')[0]['prompt']
    assert 'even if the remaining arithmetic is locally valid' in prompt, (
        'source_fact_missing definition must include locally-valid arithmetic caveat'
    )
    assert 'item A, item B, and item C' in prompt, (
        'source_fact_missing must include the generic total-cost example'
    )


def test_prompt_unit_scale_error_definition_and_example(tmp_path):
    """unit_scale_error must include refined definition and generic example."""
    output_dir = _run_builder(tmp_path, [_BASE_ROW])
    prompt = read_jsonl(output_dir / 'judge_requests.jsonl')[0]['prompt']
    assert 'wrong unit, rate, denominator, or scale' in prompt, (
        'unit_scale_error definition must name unit/rate/denominator/scale'
    )
    assert 'miles per hour' in prompt, (
        'unit_scale_error must include the generic miles-per-hour example'
    )


def test_prompt_insufficient_evidence_is_tightened(tmp_path):
    """insufficient_evidence must state it is a fallback of last resort."""
    output_dir = _run_builder(tmp_path, [_BASE_ROW])
    prompt = read_jsonl(output_dir / 'judge_requests.jsonl')[0]['prompt']
    assert 'too sparse or opaque to localize the failure' in prompt, (
        'insufficient_evidence must require trace to be sparse/opaque'
    )
    assert 'do not use when a missing source fact' in prompt, (
        'insufficient_evidence must explicitly forbid use when other axes apply'
    )


def test_refined_axis_definitions_contain_no_label_leakage(tmp_path):
    """The refined axis definition text must not leak label hints or private fields."""
    output_dir = _run_builder(tmp_path, [_BASE_ROW])
    prompt = read_jsonl(output_dir / 'judge_requests.jsonl')[0]['prompt']
    forbidden = [
        'gold_answer',
        'relation_ready_label_manual',
        'first_error_axis_manual',
        'notes_manual',
        'likely not_ready',
        'likely ready',
        'likely uncertain',
        'ready candidate',
        'not_ready candidate',
        'good judge should label',
    ]
    for term in forbidden:
        assert term not in prompt, f'Refined prompt must not contain leakage term: {term!r}'


def test_refined_axis_examples_are_generic(tmp_path):
    """Generic examples in axis definitions must not reference specific row IDs."""
    output_dir = _run_builder(tmp_path, [_BASE_ROW])
    prompt = read_jsonl(output_dir / 'judge_requests.jsonl')[0]['prompt']
    assert 'rrseed_' not in prompt, 'Axis examples must not embed real row IDs'


# ---------------------------------------------------------------------------
# Final-selection convention tests
# ---------------------------------------------------------------------------

def test_prompt_ready_means_acceptable_for_final_selection(tmp_path):
    """ready label definition must state it means acceptable for final selection."""
    output_dir = _run_builder(tmp_path, [_BASE_ROW])
    prompt = read_jsonl(output_dir / 'judge_requests.jsonl')[0]['prompt']
    assert 'acceptable for final selection' in prompt, (
        'ready label definition must state acceptable for final selection'
    )


def test_prompt_wrong_arithmetic_is_not_ready(tmp_path):
    """Prompt must state that a numerically wrong answer with correct semantic structure is not_ready."""
    output_dir = _run_builder(tmp_path, [_BASE_ROW])
    prompt = read_jsonl(output_dir / 'judge_requests.jsonl')[0]['prompt']
    assert 'numerically wrong answer with correct semantic structure is still not_ready' in prompt, (
        'Prompt must state that wrong arithmetic with correct semantics is still not_ready'
    )


def test_prompt_not_ready_references_arithmetic_only_error(tmp_path):
    """not_ready definition must explicitly reference arithmetic_only_error for computation slips."""
    output_dir = _run_builder(tmp_path, [_BASE_ROW])
    prompt = read_jsonl(output_dir / 'judge_requests.jsonl')[0]['prompt']
    assert 'first_error_axis = arithmetic_only_error' in prompt, (
        'not_ready definition must direct judges to use arithmetic_only_error for numeric slips'
    )


def test_final_selection_convention_contains_no_label_leakage(tmp_path):
    """The final-selection convention text must not introduce any leakage terms."""
    output_dir = _run_builder(tmp_path, [_BASE_ROW])
    prompt = read_jsonl(output_dir / 'judge_requests.jsonl')[0]['prompt']
    forbidden = [
        'gold_answer_metadata_only',
        'relation_ready_label_manual',
        'first_error_axis_manual',
        'notes_manual',
        'likely not_ready',
        'likely ready',
        'likely uncertain',
        'ready candidate',
        'not_ready candidate',
        'uncertain candidate',
        'good judge should label',
    ]
    for term in forbidden:
        assert term not in prompt, (
            f'Final-selection convention text must not contain leakage term: {term!r}'
        )


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
