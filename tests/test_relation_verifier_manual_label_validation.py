"""Tests for relation verifier manual label validation script."""

import csv
import subprocess
import sys
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


def read_markdown_report(md_path):
    """Read a markdown report into text."""
    return md_path.read_text(encoding='utf-8')


def test_valid_labeled_csv_passes(tmp_path):
    """Test that a valid labeled CSV passes validation."""
    rows = [
        {
            'row_id': 'test_1',
            'question': 'Test question',
            'candidate_answer': '42',
            'candidate_source': 'direct_formula_family',
            'split_group_id': 'train',
            'target_phrase': 'test target',
            'target_semantic_type': 'number',
            'relation_ready_label_manual': 'ready',
            'first_error_axis_manual': '',
            'notes_manual': 'Test notes',
        },
        {
            'row_id': 'test_2',
            'question': 'Test question 2',
            'candidate_answer': '99',
            'candidate_source': 'explicit_case_split_family',
            'split_group_id': 'train',
            'target_phrase': 'test target 2',
            'target_semantic_type': 'number',
            'relation_ready_label_manual': 'not_ready',
            'first_error_axis_manual': 'arithmetic_only_error',
            'notes_manual': 'Test notes 2',
        },
    ]
    csv_path = create_test_csv(tmp_path, rows)
    output_md = tmp_path / 'report.md'

    result = subprocess.run(
        [
            sys.executable,
            'scripts/validate_relation_verifier_manual_labels.py',
            '--input-csv',
            str(csv_path),
            '--output-md',
            str(output_md),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f'Validation should pass for valid CSV. stderr: {result.stderr}'
    assert output_md.exists(), 'Output markdown should be created'

    report = read_markdown_report(output_md)
    assert 'ready' in report
    assert 'not_ready' in report
    assert 'arithmetic_only_error' in report


def test_invalid_relation_label_reported(tmp_path):
    """Test that invalid relation labels are reported."""
    rows = [
        {
            'row_id': 'test_1',
            'question': 'Test question',
            'candidate_answer': '42',
            'candidate_source': 'direct_formula_family',
            'split_group_id': 'train',
            'target_phrase': 'test target',
            'target_semantic_type': 'number',
            'relation_ready_label_manual': 'invalid_label',
            'first_error_axis_manual': '',
            'notes_manual': 'Test notes',
        },
    ]
    csv_path = create_test_csv(tmp_path, rows)
    output_md = tmp_path / 'report.md'

    result = subprocess.run(
        [
            sys.executable,
            'scripts/validate_relation_verifier_manual_labels.py',
            '--input-csv',
            str(csv_path),
            '--output-md',
            str(output_md),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0, 'Validation should fail for invalid relation label'

    report = read_markdown_report(output_md)
    assert 'Invalid Relation Labels' in report
    assert 'invalid_label' in report


def test_invalid_error_axis_reported(tmp_path):
    """Test that invalid error axes are reported."""
    rows = [
        {
            'row_id': 'test_1',
            'question': 'Test question',
            'candidate_answer': '42',
            'candidate_source': 'direct_formula_family',
            'split_group_id': 'train',
            'target_phrase': 'test target',
            'target_semantic_type': 'number',
            'relation_ready_label_manual': 'not_ready',
            'first_error_axis_manual': 'invalid_axis',
            'notes_manual': 'Test notes',
        },
    ]
    csv_path = create_test_csv(tmp_path, rows)
    output_md = tmp_path / 'report.md'

    result = subprocess.run(
        [
            sys.executable,
            'scripts/validate_relation_verifier_manual_labels.py',
            '--input-csv',
            str(csv_path),
            '--output-md',
            str(output_md),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0, 'Validation should fail for invalid error axis'

    report = read_markdown_report(output_md)
    assert 'Invalid Error Axes' in report
    assert 'invalid_axis' in report


def test_ready_with_axis_reported(tmp_path):
    """Test that ready rows with non-empty axis are reported."""
    rows = [
        {
            'row_id': 'test_1',
            'question': 'Test question',
            'candidate_answer': '42',
            'candidate_source': 'direct_formula_family',
            'split_group_id': 'train',
            'target_phrase': 'test target',
            'target_semantic_type': 'number',
            'relation_ready_label_manual': 'ready',
            'first_error_axis_manual': 'arithmetic_only_error',
            'notes_manual': 'Test notes',
        },
    ]
    csv_path = create_test_csv(tmp_path, rows)
    output_md = tmp_path / 'report.md'

    result = subprocess.run(
        [
            sys.executable,
            'scripts/validate_relation_verifier_manual_labels.py',
            '--input-csv',
            str(csv_path),
            '--output-md',
            str(output_md),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0, 'Validation should fail for ready row with axis'

    report = read_markdown_report(output_md)
    assert 'Ready Rows with Non-Empty Axis' in report
    assert 'arithmetic_only_error' in report


def test_not_ready_without_axis_reported(tmp_path):
    """Test that not_ready rows without axis are reported."""
    rows = [
        {
            'row_id': 'test_1',
            'question': 'Test question',
            'candidate_answer': '42',
            'candidate_source': 'direct_formula_family',
            'split_group_id': 'train',
            'target_phrase': 'test target',
            'target_semantic_type': 'number',
            'relation_ready_label_manual': 'not_ready',
            'first_error_axis_manual': '',
            'notes_manual': 'Test notes',
        },
    ]
    csv_path = create_test_csv(tmp_path, rows)
    output_md = tmp_path / 'report.md'

    result = subprocess.run(
        [
            sys.executable,
            'scripts/validate_relation_verifier_manual_labels.py',
            '--input-csv',
            str(csv_path),
            '--output-md',
            str(output_md),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0, 'Validation should fail for not_ready row without axis'

    report = read_markdown_report(output_md)
    assert 'Not-Ready Rows with Empty Axis' in report


def test_uncertain_rows_listed(tmp_path):
    """Test that uncertain rows are listed in the report."""
    rows = [
        {
            'row_id': 'test_uncertain_1',
            'question': 'Test question',
            'candidate_answer': '42',
            'candidate_source': 'direct_formula_family',
            'split_group_id': 'train',
            'target_phrase': 'test target',
            'target_semantic_type': 'number',
            'relation_ready_label_manual': 'uncertain',
            'first_error_axis_manual': 'insufficient_evidence',
            'notes_manual': 'Test uncertain notes',
        },
    ]
    csv_path = create_test_csv(tmp_path, rows)
    output_md = tmp_path / 'report.md'

    result = subprocess.run(
        [
            sys.executable,
            'scripts/validate_relation_verifier_manual_labels.py',
            '--input-csv',
            str(csv_path),
            '--output-md',
            str(output_md),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0

    report = read_markdown_report(output_md)
    assert 'All Uncertain Rows' in report
    assert 'test_uncertain_1' in report


def test_markdown_output_created(tmp_path):
    """Test that markdown output file is created."""
    rows = [
        {
            'row_id': 'test_1',
            'question': 'Test question',
            'candidate_answer': '42',
            'candidate_source': 'direct_formula_family',
            'split_group_id': 'train',
            'target_phrase': 'test target',
            'target_semantic_type': 'number',
            'relation_ready_label_manual': 'ready',
            'first_error_axis_manual': '',
            'notes_manual': 'Test notes',
        },
    ]
    csv_path = create_test_csv(tmp_path, rows)
    output_md = tmp_path / 'subdir' / 'report.md'

    result = subprocess.run(
        [
            sys.executable,
            'scripts/validate_relation_verifier_manual_labels.py',
            '--input-csv',
            str(csv_path),
            '--output-md',
            str(output_md),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert output_md.exists(), 'Output markdown file should be created'
    assert output_md.stat().st_size > 0, 'Output markdown file should have content'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
